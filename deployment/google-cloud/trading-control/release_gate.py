"""Verify the controller-signed, expiring cloud live-release state."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping, Protocol

from cloud_state import CloudStateError, FirestoreControlState
from contract import (
    build_readiness_release_binding,
    canonical_bytes,
    digest,
    periodic_readiness_probe,
)


RELEASE_SCHEMA = "aureon.cloud-trade-release-state.v1"
LIVE_CONTROLS = {
    "AUREON_DEPLOYMENT_HOLD": False,
    "AUREON_DISABLE_REAL_ORDERS": False,
    "AUREON_DISABLE_EXCHANGE_MUTATIONS": False,
    "AUREON_LIVE_TRADING": True,
    "AUREON_ORDER_INTENT_PUBLISH": True,
    "AUREON_UNIFIED_ORDER_EXECUTOR": True,
}
_HEX64 = re.compile(r"[0-9a-f]{64}")
_REVISION = re.compile(r"[0-9a-f]{40,64}")
_KEY_VERSION = re.compile(
    r"projects/aureon-trading/locations/europe-west1/keyRings/aureon-trading-prod/"
    r"cryptoKeys/aureon-controller-signing/cryptoKeyVersions/1"
)
_FIELDS = {
    "schema", "state", "generation", "request_id", "requested_controls_sha256",
    "authorization_event_sha256", "authorization_expires_at_ms",
    "probe_receipt_sha256", "provider_readback_sha256", "source_revision",
    "signed_at_ms", "controller_key_version", "signature", "update_time",
}


class ReleaseGateError(RuntimeError):
    """Stable release-gate failure."""


class Verifier(Protocol):
    def verify(self, key_version: str, data: bytes, signature: str) -> None: ...


def validate_release_state(value: Any, *, controller_key_version: str,
                           verifier: Verifier) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != _FIELDS:
        raise ReleaseGateError("release_state_shape_invalid")
    row = dict(value)
    unsigned = {key: row[key] for key in _FIELDS - {"signature", "update_time"}}
    if (row["schema"] != RELEASE_SCHEMA or row["state"] not in {"active", "held"}
            or type(row["generation"]) is not int or row["generation"] < 1
            or any(not _HEX64.fullmatch(str(row[key] or "")) for key in (
                "request_id", "requested_controls_sha256", "authorization_event_sha256",
                "probe_receipt_sha256", "provider_readback_sha256"))
            or type(row["authorization_expires_at_ms"]) is not int
            or type(row["signed_at_ms"]) is not int
            or not _REVISION.fullmatch(str(row["source_revision"] or ""))
            or row["controller_key_version"] != controller_key_version
            or not _KEY_VERSION.fullmatch(controller_key_version)
            or not isinstance(row["signature"], str)
            or not isinstance(row["update_time"], str)):
        raise ReleaseGateError("release_state_invalid")
    try:
        verifier.verify(controller_key_version, canonical_bytes(unsigned), row["signature"])
    except Exception as exc:
        raise ReleaseGateError("release_state_signature_invalid") from exc
    return row


@dataclass
class ReleaseGate:
    controller_key_version: str
    verifier: Verifier
    expected_revision: str
    store: FirestoreControlState | None = None

    def __post_init__(self) -> None:
        if not _KEY_VERSION.fullmatch(self.controller_key_version):
            raise ReleaseGateError("release_controller_key_invalid")
        if not _REVISION.fullmatch(self.expected_revision):
            raise ReleaseGateError("release_expected_revision_invalid")
        self.store = self.store or FirestoreControlState()

    def active_state(self, intent: Mapping[str, Any], *, now_ms: int) -> dict[str, Any] | None:
        """Return the verified state only when it authorizes this exact message.

        A periodic readiness probe additionally carries a non-authoritative
        binding to the current generation.  A held, replaced, or re-signed
        release therefore invalidates the refresh without touching its lease.
        """
        authorization = intent.get("authorization") if isinstance(intent, Mapping) else None
        if not isinstance(authorization, Mapping):
            raise ReleaseGateError("release_intent_authorization_invalid")
        try:
            raw = self.store.read_release()
        except CloudStateError as exc:
            raise ReleaseGateError(str(exc)) from exc
        if raw is None:
            return False
        row = validate_release_state(
            raw, controller_key_version=self.controller_key_version, verifier=self.verifier,
        )
        if row["state"] != "active":
            return None
        active = bool(
            row["requested_controls_sha256"] == digest(LIVE_CONTROLS)
            and row["source_revision"] == self.expected_revision
            and intent.get("source_revision") == self.expected_revision
            and row["authorization_event_sha256"] == authorization.get("event_sha256")
            and row["authorization_expires_at_ms"] == authorization.get("expires_at_ms")
            and row["authorization_expires_at_ms"] >= int(intent.get("expires_at_ms") or 0)
            and row["signed_at_ms"] <= now_ms + 5_000
            and row["authorization_expires_at_ms"] > now_ms
        )
        if not active:
            return None
        if periodic_readiness_probe(intent):
            try:
                expected_binding = build_readiness_release_binding(row)
            except Exception as exc:
                raise ReleaseGateError("readiness_release_binding_invalid") from exc
            if authorization.get("readiness_release") != expected_binding:
                return None
        return row

    def is_active(self, intent: Mapping[str, Any], *, now_ms: int) -> bool:
        return self.active_state(intent, now_ms=now_ms) is not None


__all__ = ["LIVE_CONTROLS", "RELEASE_SCHEMA", "ReleaseGate", "ReleaseGateError", "validate_release_state"]
