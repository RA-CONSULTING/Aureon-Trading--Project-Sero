"""Firestore custody for verified probes and signed live-release state."""
from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Any, Callable, Mapping
from urllib.parse import quote

import requests

from contract import digest
from firestore_ledger import LedgerError, _document, _fields, _token


PROJECT = "aureon-trading"
DATABASE = "(default)"
BASE = f"https://firestore.googleapis.com/v1/projects/{PROJECT}/databases/{DATABASE}"
PROBE_DOCUMENT = "aureon_trade_attestations/current_probe"
RELEASE_DOCUMENT = "aureon_trade_release/current"
_HEX64 = re.compile(r"[0-9a-f]{64}")


class CloudStateError(RuntimeError):
    """Stable cloud-state failure."""


@dataclass
class FirestoreControlState:
    requester: Callable[..., Any] = requests.request
    token_provider: Callable[[], str] = _token
    timeout_seconds: float = 8.0

    def _request(self, method: str, path: str, *, body: Mapping[str, Any] | None = None,
                 params: Mapping[str, Any] | None = None,
                 statuses: tuple[int, ...] = (200,)) -> tuple[int, Any]:
        try:
            token = self.token_provider()
        except LedgerError as exc:
            raise CloudStateError(str(exc)) from exc
        if not isinstance(token, str) or not 20 <= len(token) <= 8192:
            raise CloudStateError("cloud_state_identity_unavailable")
        response = self.requester(
            method, BASE + path,
            headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
            params=dict(params or {}), json=dict(body) if body is not None else None,
            timeout=self.timeout_seconds,
        )
        token = ""
        if response.status_code not in statuses:
            raise CloudStateError("cloud_state_http_status_" + str(response.status_code))
        if response.status_code == 404:
            return 404, None
        try:
            value = response.json()
        except (ValueError, TypeError) as exc:
            raise CloudStateError("cloud_state_response_invalid") from exc
        if not isinstance(value, Mapping):
            raise CloudStateError("cloud_state_response_invalid")
        return response.status_code, dict(value)

    def _read(self, document: str) -> dict[str, Any] | None:
        status, value = self._request(
            "GET", "/documents/" + quote(document, safe="/"), statuses=(200, 404),
        )
        if status == 404:
            return None
        try:
            return _document(value)
        except LedgerError as exc:
            raise CloudStateError(str(exc)) from exc

    def read_probe(self) -> dict[str, Any] | None:
        return self._read(PROBE_DOCUMENT)

    def read_release(self) -> dict[str, Any] | None:
        return self._read(RELEASE_DOCUMENT)

    def _write(self, document: str, fields: Mapping[str, Any], *,
               expected_update_time: str | None) -> dict[str, Any]:
        params: dict[str, Any] = {"updateMask.fieldPaths": list(fields)}
        if expected_update_time is None:
            params["currentDocument.exists"] = "false"
        else:
            params["currentDocument.updateTime"] = expected_update_time
        try:
            encoded = _fields(fields)
        except LedgerError as exc:
            raise CloudStateError(str(exc)) from exc
        _, value = self._request(
            "PATCH", "/documents/" + quote(document, safe="/"),
            body={"fields": encoded}, params=params,
        )
        try:
            return _document(value)
        except LedgerError as exc:
            raise CloudStateError(str(exc)) from exc

    def put_probe_attestation(self, terminal: Mapping[str, Any], *,
                              stored_at_ms: int | None = None) -> dict[str, Any]:
        current = int(time.time() * 1000) if stored_at_ms is None else stored_at_ms
        try:
            executor = terminal["executor"]
            result = executor["result"]
            dispatch = result["dispatch"]
            intent = dispatch["review"]["intent"]
            outcome = result["outcome"]
            capabilities = outcome["executor_capabilities"]
            provider = outcome["provider_readback"]
        except (KeyError, TypeError) as exc:
            raise CloudStateError("probe_attestation_shape_invalid") from exc
        expected_capabilities = {
            "live_execution_release", "durable_budget_ledger", "order_adapter_ready",
            "live_result_binding_ready",
        }
        if (intent.get("kind") != "control_plane_probe"
                or set(capabilities) != expected_capabilities
                or any(type(value) is not bool for value in capabilities.values())
                or provider.get("provider_count") != 4
                or provider.get("all_authenticated") is not True
                or not _HEX64.fullmatch(str(provider.get("readback_sha256") or ""))):
            raise CloudStateError("probe_attestation_shape_invalid")
        authorization = intent.get("authorization")
        revision = intent.get("runtime_measurement_sha256")
        # The runtime measurement is a digest; source revision is carried by
        # the service and is added by the caller below when available.
        if (not isinstance(authorization, Mapping)
                or not _HEX64.fullmatch(str(authorization.get("event_sha256") or ""))
                or type(authorization.get("expires_at_ms")) is not int
                or not _HEX64.fullmatch(str(revision or ""))):
            raise CloudStateError("probe_attestation_shape_invalid")
        fields = {
            "schema": "aureon.cloud-trade-probe-attestation.v1",
            "receipt_sha256": digest(terminal),
            "intent_id": intent["intent_id"],
            "intent_created_at_ms": intent["created_at_ms"],
            "stored_at_ms": current,
            "authorization_event_sha256": authorization["event_sha256"],
            "authorization_expires_at_ms": authorization["expires_at_ms"],
            "provider_readback_sha256": provider["readback_sha256"],
            "provider_count": 4,
            "all_authenticated": True,
            "durable_budget_ledger": capabilities["durable_budget_ledger"],
            "order_adapter_ready": capabilities["order_adapter_ready"],
            "live_result_binding_ready": capabilities["live_result_binding_ready"],
            "runtime_measurement_sha256": revision,
        }
        existing = self.read_probe()
        return self._write(
            PROBE_DOCUMENT, fields,
            expected_update_time=existing.get("update_time") if existing else None,
        )

    def put_release(self, fields: Mapping[str, Any], *,
                    expected_update_time: str | None) -> dict[str, Any]:
        if not isinstance(fields, Mapping) or len(fields) > 24:
            raise CloudStateError("release_state_invalid")
        return self._write(RELEASE_DOCUMENT, fields, expected_update_time=expected_update_time)


def validate_probe_attestation(value: Any, *, now_ms: int) -> dict[str, Any]:
    required = {
        "schema", "receipt_sha256", "intent_id", "intent_created_at_ms", "stored_at_ms",
        "authorization_event_sha256", "authorization_expires_at_ms",
        "provider_readback_sha256", "provider_count", "all_authenticated",
        "durable_budget_ledger", "order_adapter_ready", "live_result_binding_ready",
        "runtime_measurement_sha256", "update_time",
    }
    if not isinstance(value, Mapping) or set(value) != required:
        raise CloudStateError("probe_attestation_invalid")
    row = dict(value)
    if (row["schema"] != "aureon.cloud-trade-probe-attestation.v1"
            or any(not _HEX64.fullmatch(str(row[key] or "")) for key in (
                "receipt_sha256", "intent_id", "authorization_event_sha256",
                "provider_readback_sha256", "runtime_measurement_sha256"))
            or any(type(row[key]) is not int for key in (
                "intent_created_at_ms", "stored_at_ms", "authorization_expires_at_ms"))
            or not 0 <= now_ms - row["stored_at_ms"] <= 300_000
            or row["authorization_expires_at_ms"] <= now_ms
            or row["provider_count"] != 4 or row["all_authenticated"] is not True
            or row["durable_budget_ledger"] is not True
            or row["order_adapter_ready"] is not True
            or row["live_result_binding_ready"] is not True
            or not isinstance(row["update_time"], str)):
        raise CloudStateError("probe_attestation_invalid")
    return row


__all__ = ["CloudStateError", "FirestoreControlState", "validate_probe_attestation"]
