"""Private Pub/Sub worker that writes the signed live-release state."""
from __future__ import annotations

import base64
import binascii
import json
import os
import re
import time
from dataclasses import dataclass
from typing import Any, Callable, Mapping

from flask import Flask, jsonify, request

from cloud_state import CloudStateError, FirestoreControlState, validate_probe_attestation
from contract import ContractError, canonical_bytes, digest, validate_controls
from release_gate import RELEASE_SCHEMA
from service import CloudBoundaryError, KmsBoundary, PubSubPublisher


REQUEST_SCHEMA = "aureon.cloud-trade-release-request.v1"
CONTROLLER_ID = "gcp:aureon-trade-controller"
_HEX64 = re.compile(r"[0-9a-f]{64}")
_REVISION = re.compile(r"[0-9a-f]{40,64}")
_KEY = re.compile(
    r"projects/aureon-trading/locations/europe-west1/keyRings/aureon-trading-prod/"
    r"cryptoKeys/aureon-controller-signing/cryptoKeyVersions/1"
)
_TOPIC = re.compile(r"projects/aureon-trading/topics/aureon-trade-release-receipts-v1")
_REQUEST_FIELDS = {
    "schema", "request_id", "action", "created_at_ms", "expires_at_ms",
    "requested_controls", "authorization_event_sha256",
    "authorization_expires_at_ms", "probe_receipt_sha256",
    "provider_readback_sha256", "source_revision",
}


class ControllerError(RuntimeError):
    """Stable controller failure."""


@dataclass(frozen=True)
class ControllerConfig:
    project: str
    revision: str
    key_version: str
    output_topic: str

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> "ControllerConfig":
        env = os.environ if environ is None else environ
        value = cls(
            project=str(env.get("AUREON_GCP_PROJECT") or ""),
            revision=str(env.get("AUREON_REVISION") or ""),
            key_version=str(env.get("AUREON_KMS_KEY_VERSION") or ""),
            output_topic=str(env.get("AUREON_OUTPUT_TOPIC") or ""),
        )
        if (value.project != "aureon-trading" or not _REVISION.fullmatch(value.revision)
                or not _KEY.fullmatch(value.key_version) or not _TOPIC.fullmatch(value.output_topic)):
            raise ControllerError("controller_config_invalid")
        return value


def _decode_push(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping) or not isinstance(value.get("message"), Mapping):
        raise ContractError("release_pubsub_envelope_invalid")
    encoded = value["message"].get("data")
    try:
        raw = base64.b64decode(encoded, validate=True)
        decoded = json.loads(raw)
    except (ValueError, TypeError, UnicodeError, binascii.Error) as exc:
        raise ContractError("release_pubsub_data_invalid") from exc
    if not isinstance(decoded, dict) or canonical_bytes(decoded) != raw:
        raise ContractError("release_pubsub_data_not_canonical")
    return decoded


def validate_request(value: Any, *, now_ms: int) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != _REQUEST_FIELDS:
        raise ContractError("release_request_shape_invalid")
    row = dict(value)
    unsigned = dict(row)
    request_id = unsigned.pop("request_id", None)
    if (row["schema"] != REQUEST_SCHEMA or row["action"] not in {"activate", "hold"}
            or not _HEX64.fullmatch(str(request_id or "")) or request_id != digest(unsigned)
            or type(row["created_at_ms"]) is not int or type(row["expires_at_ms"]) is not int
            or not row["created_at_ms"] <= now_ms + 5_000
            or not now_ms <= row["expires_at_ms"] <= row["created_at_ms"] + 60_000
            or not _REVISION.fullmatch(str(row["source_revision"] or ""))):
        raise ContractError("release_request_invalid")
    validate_controls(row["requested_controls"], live=row["action"] == "activate")
    if row["action"] == "activate":
        if (any(not _HEX64.fullmatch(str(row[key] or "")) for key in (
                "authorization_event_sha256", "probe_receipt_sha256", "provider_readback_sha256"))
                or type(row["authorization_expires_at_ms"]) is not int
                or not now_ms < row["authorization_expires_at_ms"] <= now_ms + 259_200_000):
            raise ContractError("release_authorization_invalid")
    else:
        if (row["authorization_event_sha256"] is not None
                or row["authorization_expires_at_ms"] is not None
                or row["probe_receipt_sha256"] is not None
                or row["provider_readback_sha256"] is not None):
            raise ContractError("held_release_evidence_forbidden")
    return row


def _release_fields(request_value: Mapping[str, Any], *, generation: int,
                    now_ms: int, key_version: str, signer: Any) -> dict[str, Any]:
    active = request_value["action"] == "activate"
    zeros = "0" * 64
    unsigned = {
        "schema": RELEASE_SCHEMA,
        "state": "active" if active else "held",
        "generation": generation,
        "request_id": request_value["request_id"],
        "requested_controls_sha256": digest(request_value["requested_controls"]),
        "authorization_event_sha256": request_value["authorization_event_sha256"] or zeros,
        "authorization_expires_at_ms": request_value["authorization_expires_at_ms"] or 0,
        "probe_receipt_sha256": request_value["probe_receipt_sha256"] or zeros,
        "provider_readback_sha256": request_value["provider_readback_sha256"] or zeros,
        "source_revision": request_value["source_revision"],
        "signed_at_ms": now_ms,
        "controller_key_version": key_version,
    }
    return {**unsigned, "signature": signer.sign(canonical_bytes(unsigned))}


def process_release_request(value: Mapping[str, Any], *, now_ms: int,
                            config: ControllerConfig, signer: Any,
                            store: FirestoreControlState, publisher: Any) -> dict[str, Any]:
    row = validate_request(value, now_ms=now_ms)
    if row["source_revision"] != config.revision:
        raise ContractError("release_source_revision_mismatch")
    current = store.read_release()
    generation = int(current.get("generation", 0)) + 1 if current else 1
    if row["action"] == "activate":
        probe = validate_probe_attestation(store.read_probe(), now_ms=now_ms)
        if (probe["receipt_sha256"] != row["probe_receipt_sha256"]
                or probe["provider_readback_sha256"] != row["provider_readback_sha256"]
                or probe["authorization_event_sha256"] != row["authorization_event_sha256"]
                or probe["authorization_expires_at_ms"] != row["authorization_expires_at_ms"]):
            raise ContractError("release_probe_evidence_mismatch")
    fields = _release_fields(
        row, generation=generation, now_ms=now_ms,
        key_version=config.key_version, signer=signer,
    )
    written = store.put_release(
        fields, expected_update_time=current.get("update_time") if current else None,
    )
    receipt = {
        "schema": "aureon.cloud-trade-release-receipt.v1",
        "controller_authority_id": CONTROLLER_ID,
        "release_state_sha256": digest(fields),
        "state": fields["state"],
        "generation": fields["generation"],
        "request_id": fields["request_id"],
        "authorization_expires_at_ms": fields["authorization_expires_at_ms"],
        "controller_key_version": fields["controller_key_version"],
        "signature": fields["signature"],
        "release_authority": fields["state"] == "active",
        "mutation_authority": False,
        "recorded_at_ms": now_ms,
    }
    publisher.publish(receipt)
    return {**receipt, "firestore_update_time": written["update_time"]}


def create_app(*, config: ControllerConfig | None = None, signer: Any | None = None,
               store: FirestoreControlState | None = None, publisher: Any | None = None,
               clock: Callable[[], float] = time.time) -> Flask:
    cfg = config or ControllerConfig.from_env()
    stage_signer = signer or KmsBoundary(cfg.key_version)
    state_store = store or FirestoreControlState()
    output = publisher or PubSubPublisher(cfg.output_topic)
    app = Flask(__name__)
    app.config.update(MAX_CONTENT_LENGTH=100_000, JSON_SORT_KEYS=True)

    @app.get("/healthz")
    def healthz():
        return jsonify({
            "ok": True, "schema": "aureon.cloud-trade-controller-health.v1",
            "revision": cfg.revision, "release_authority": False,
            "mutation_authority": False,
        })

    @app.post("/process")
    def process():
        try:
            value = _decode_push(request.get_json(silent=True))
            process_release_request(
                value, now_ms=int(clock() * 1000), config=cfg,
                signer=stage_signer, store=state_store, publisher=output,
            )
            return "", 204
        except ContractError as exc:
            app.logger.warning("release_request_rejected reason_code=%s", str(exc))
            return "", 204
        except (CloudStateError, CloudBoundaryError, ControllerError) as exc:
            app.logger.warning("release_request_deferred reason_code=%s", str(exc))
            return jsonify({"ok": False, "reason_code": str(exc), "retryable": True}), 503
        except Exception:
            return jsonify({"ok": False, "reason_code": "release_controller_failed", "retryable": True}), 503

    return app


__all__ = ["ControllerConfig", "ControllerError", "create_app", "process_release_request", "validate_request"]
