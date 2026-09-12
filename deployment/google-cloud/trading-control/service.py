"""Authenticated Cloud Run worker for the isolated trading authority chain."""
from __future__ import annotations

import base64
import binascii
import hashlib
import json
import math
import os
import re
import time
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Protocol

import requests
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from flask import Flask, jsonify, request

from contract import (
    ContractError,
    DISPATCH_SCHEMA,
    EXECUTOR_SCHEMA,
    INTENT_SCHEMA,
    ORDER_KIND,
    PROBE_KIND,
    RECEIPT_SCHEMA,
    REVIEW_SCHEMA,
    canonical_bytes,
    digest,
    unsigned_stage,
    validate_intent,
    validate_stage,
)


_PROJECT = re.compile(r"[a-z][a-z0-9-]{4,61}[a-z0-9]")
_KEY_VERSION = re.compile(
    r"projects/[a-z][a-z0-9-]{4,61}[a-z0-9]/locations/[a-z0-9-]+/"
    r"keyRings/[A-Za-z0-9_-]+/cryptoKeys/[A-Za-z0-9_-]+/cryptoKeyVersions/[1-9][0-9]*"
)
_TOPIC = re.compile(r"projects/[a-z][a-z0-9-]{4,61}[a-z0-9]/topics/[A-Za-z][A-Za-z0-9._~-]{2,254}")
_ROLE_CONFIG = {
    "review": (REVIEW_SCHEMA, "intent", 1),
    "dispatch": (DISPATCH_SCHEMA, "review", 2),
    "executor": (EXECUTOR_SCHEMA, "result", 3),
    "receipt": (RECEIPT_SCHEMA, "executor", 4),
}
_AUTHORITY_IDS = {
    "review": "gcp:aureon-trade-review",
    "dispatch": "gcp:aureon-trade-dispatch",
    "executor": "gcp:aureon-trade-executor",
    "receipt": "gcp:aureon-trade-receipt",
}
_EXPECTED_KEYS = {
    "review": "aureon-review-signing",
    "dispatch": "aureon-dispatch-signing",
    "executor": "aureon-executor-signing",
    "receipt": "aureon-receipt-signing",
}
_STAGE_PAYLOAD = {
    REVIEW_SCHEMA: "intent",
    DISPATCH_SCHEMA: "review",
    EXECUTOR_SCHEMA: "result",
    RECEIPT_SCHEMA: "executor",
}


class CloudBoundaryError(RuntimeError):
    """Stable cloud transport/configuration failure."""


class Signer(Protocol):
    key_version: str

    def sign(self, data: bytes) -> str: ...


class Verifier(Protocol):
    def verify(self, key_version: str, data: bytes, signature: str) -> None: ...


class Publisher(Protocol):
    def publish(self, value: Mapping[str, Any]) -> str: ...


def _token() -> str:
    from google.auth import default as google_auth_default
    from google.auth.transport.requests import Request as GoogleAuthRequest

    credentials, _ = google_auth_default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    credentials.refresh(GoogleAuthRequest())
    token = credentials.token
    if not isinstance(token, str) or not 20 <= len(token) <= 8192:
        raise CloudBoundaryError("cloud_identity_token_unavailable")
    return token


def _response_json(response: requests.Response, code: str) -> dict[str, Any]:
    if response.status_code < 200 or response.status_code >= 300:
        raise CloudBoundaryError(code)
    try:
        value = response.json()
    except (ValueError, TypeError) as exc:
        raise CloudBoundaryError(code) from exc
    if not isinstance(value, dict):
        raise CloudBoundaryError(code)
    return value


@dataclass(frozen=True)
class KmsBoundary:
    key_version: str
    timeout_seconds: float = 8.0

    def __post_init__(self) -> None:
        if not _KEY_VERSION.fullmatch(self.key_version):
            raise CloudBoundaryError("kms_key_version_invalid")

    @staticmethod
    def _headers() -> dict[str, str]:
        return {"Authorization": "Bearer " + _token(), "Accept": "application/json"}

    def sign(self, data: bytes) -> str:
        if not isinstance(data, bytes) or not 0 < len(data) <= 65_536:
            raise CloudBoundaryError("kms_signing_payload_invalid")
        response = requests.post(
            "https://cloudkms.googleapis.com/v1/" + self.key_version + ":asymmetricSign",
            headers={**self._headers(), "Content-Type": "application/json"},
            json={"data": base64.b64encode(data).decode("ascii")},
            timeout=self.timeout_seconds,
        )
        result = _response_json(response, "kms_signing_failed")
        signature = result.get("signature")
        if result.get("name") != self.key_version or not isinstance(signature, str):
            raise CloudBoundaryError("kms_signing_response_invalid")
        try:
            raw = base64.b64decode(signature, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise CloudBoundaryError("kms_signature_invalid") from exc
        if len(raw) != 64:
            raise CloudBoundaryError("kms_signature_invalid")
        return signature

    def verify(self, key_version: str, data: bytes, signature: str) -> None:
        if not _KEY_VERSION.fullmatch(key_version):
            raise CloudBoundaryError("kms_verification_key_invalid")
        response = requests.get(
            "https://cloudkms.googleapis.com/v1/" + key_version + "/publicKey",
            headers=self._headers(), timeout=self.timeout_seconds,
        )
        result = _response_json(response, "kms_public_key_read_failed")
        pem = result.get("pem")
        algorithm = result.get("algorithm")
        if result.get("name") != key_version or algorithm != "EC_SIGN_ED25519" or not isinstance(pem, str):
            raise CloudBoundaryError("kms_public_key_response_invalid")
        try:
            public = serialization.load_pem_public_key(pem.encode("ascii"))
            raw_signature = base64.b64decode(signature, validate=True)
        except (ValueError, TypeError, UnicodeError, binascii.Error) as exc:
            raise CloudBoundaryError("stage_signature_invalid") from exc
        if not isinstance(public, Ed25519PublicKey) or len(raw_signature) != 64:
            raise CloudBoundaryError("stage_signature_invalid")
        try:
            public.verify(raw_signature, data)
        except InvalidSignature as exc:
            raise CloudBoundaryError("stage_signature_invalid") from exc


@dataclass(frozen=True)
class PubSubPublisher:
    topic: str
    timeout_seconds: float = 8.0

    def __post_init__(self) -> None:
        if not _TOPIC.fullmatch(self.topic):
            raise CloudBoundaryError("output_topic_invalid")

    def publish(self, value: Mapping[str, Any]) -> str:
        wire = canonical_bytes(value)
        response = requests.post(
            "https://pubsub.googleapis.com/v1/" + self.topic + ":publish",
            headers={
                "Authorization": "Bearer " + _token(),
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            json={"messages": [{
                "data": base64.b64encode(wire).decode("ascii"),
                "attributes": {
                    "schema": str(value.get("schema") or ""),
                    "intent_id": str(value.get("intent_id") or ""),
                },
                "orderingKey": str(value.get("intent_id") or ""),
            }]},
            timeout=self.timeout_seconds,
        )
        result = _response_json(response, "pubsub_publish_failed")
        ids = result.get("messageIds")
        if not isinstance(ids, list) or len(ids) != 1 or not isinstance(ids[0], str) or not ids[0]:
            raise CloudBoundaryError("pubsub_publish_response_invalid")
        return ids[0]


@dataclass(frozen=True)
class ServiceConfig:
    role: str
    project_id: str
    revision: str
    key_version: str
    output_topic: str | None
    review_key_version: str | None
    dispatch_key_version: str | None
    executor_key_version: str | None
    live_execution_release: bool
    durable_budget_ledger: bool
    order_adapter_ready: bool
    max_order_usd: float
    provider_probe_enabled: bool = False
    max_daily_budget_usd: float = 20.0

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> "ServiceConfig":
        values = os.environ if environ is None else environ
        role = str(values.get("AUREON_TRADING_AUTHORITY_ROLE") or "")
        project = str(values.get("AUREON_GCP_PROJECT") or "")
        revision = str(values.get("AUREON_REVISION") or "")
        key_version = str(values.get("AUREON_KMS_KEY_VERSION") or "")
        output = str(values.get("AUREON_OUTPUT_TOPIC") or "") or None
        if role not in _ROLE_CONFIG or not _PROJECT.fullmatch(project):
            raise CloudBoundaryError("service_identity_config_invalid")
        if not re.fullmatch(r"[0-9a-f]{40,64}", revision):
            raise CloudBoundaryError("service_revision_invalid")
        if not _KEY_VERSION.fullmatch(key_version) or f"/cryptoKeys/{_EXPECTED_KEYS[role]}/" not in key_version:
            raise CloudBoundaryError("service_signing_key_invalid")
        if output is None or not _TOPIC.fullmatch(output):
            raise CloudBoundaryError("service_output_topic_invalid")
        max_order = float(values.get("AUREON_MAX_ORDER_USD") or "5")
        if not math.isfinite(max_order) or not 0 < max_order <= 100:
            raise CloudBoundaryError("service_order_budget_invalid")
        max_daily_budget = float(values.get("AUREON_MAX_DAILY_ORDER_USD") or "20")
        if not math.isfinite(max_daily_budget) or not max_order <= max_daily_budget <= 10_000:
            raise CloudBoundaryError("service_daily_budget_invalid")
        def flag(key: str) -> bool:
            return str(values.get(key) or "0").strip().lower() in {"1", "true", "yes", "on"}

        return cls(
            role=role, project_id=project, revision=revision, key_version=key_version,
            output_topic=output,
            review_key_version=str(values.get("AUREON_REVIEW_KEY_VERSION") or "") or None,
            dispatch_key_version=str(values.get("AUREON_DISPATCH_KEY_VERSION") or "") or None,
            executor_key_version=str(values.get("AUREON_EXECUTOR_KEY_VERSION") or "") or None,
            live_execution_release=flag("AUREON_LIVE_EXECUTION_RELEASE"),
            durable_budget_ledger=flag("AUREON_DURABLE_BUDGET_LEDGER"),
            order_adapter_ready=flag("AUREON_ORDER_ADAPTER_READY"),
            max_order_usd=max_order,
            provider_probe_enabled=flag("AUREON_PROVIDER_PROBE_ENABLED"),
            max_daily_budget_usd=max_daily_budget,
        )


def _decode_push(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping) or not isinstance(value.get("message"), Mapping):
        raise ContractError("pubsub_envelope_invalid")
    message = value["message"]
    encoded = message.get("data")
    if not isinstance(encoded, str) or not 1 <= len(encoded) <= 90_000:
        raise ContractError("pubsub_data_invalid")
    try:
        raw = base64.b64decode(encoded, validate=True)
        decoded = json.loads(raw)
    except (ValueError, TypeError, UnicodeError, binascii.Error, json.JSONDecodeError) as exc:
        raise ContractError("pubsub_data_invalid") from exc
    if not isinstance(decoded, dict) or canonical_bytes(decoded) != raw:
        raise ContractError("pubsub_data_not_canonical")
    return decoded


def _stage_id(role: str, intent_id: str, prior: str, authority: str) -> str:
    return hashlib.sha256((role + "\x00" + intent_id + "\x00" + prior + "\x00" + authority).encode()).hexdigest()


def _verify_stage(stage: Mapping[str, Any], *, schema: str, payload_key: str,
                  verifier: Verifier, expected_key: str) -> dict[str, Any]:
    result = validate_stage(stage, schema=schema, payload_key=payload_key)
    if result["key_version"] != expected_key:
        raise ContractError("stage_key_pin_mismatch")
    verifier.verify(expected_key, canonical_bytes(unsigned_stage(result)), result["signature"])
    return result


def _intent_from_chain(value: Mapping[str, Any]) -> dict[str, Any]:
    current: Any = value
    for _ in range(4):
        if not isinstance(current, Mapping):
            break
        if current.get("schema") == INTENT_SCHEMA:
            return dict(current)
        payload_key = _STAGE_PAYLOAD.get(str(current.get("schema") or ""))
        if payload_key is None:
            break
        current = current.get(payload_key)
        if isinstance(current, Mapping) and current.get("schema") == EXECUTOR_SCHEMA:
            current = current.get("result")
        if isinstance(current, Mapping) and "dispatch" in current and "outcome" in current:
            current = current.get("dispatch")
    raise ContractError("intent_chain_missing")


def _review(input_value: Mapping[str, Any], config: ServiceConfig, signer: Signer,
            _verifier: Verifier, now_ms: int) -> dict[str, Any]:
    intent = validate_intent(input_value, now_ms=now_ms, max_order_usd=config.max_order_usd,
                             live_release=config.live_execution_release)
    prior = digest(intent)
    stage = {
        "schema": REVIEW_SCHEMA,
        "stage_id": _stage_id("review", intent["intent_id"], prior, _AUTHORITY_IDS["review"]),
        "intent_id": intent["intent_id"], "prior_sha256": prior, "intent": intent,
        "authority_id": _AUTHORITY_IDS["review"], "key_version": signer.key_version,
        "signed_at_ms": intent["created_at_ms"] + 1, "signature": "pending",
    }
    stage["signature"] = signer.sign(canonical_bytes(unsigned_stage(stage)))
    return validate_stage(stage, schema=REVIEW_SCHEMA, payload_key="intent", prior_digest=prior)


def _dispatch(input_value: Mapping[str, Any], config: ServiceConfig, signer: Signer,
              verifier: Verifier, now_ms: int) -> dict[str, Any]:
    if config.review_key_version is None:
        raise CloudBoundaryError("review_key_pin_missing")
    review = _verify_stage(input_value, schema=REVIEW_SCHEMA, payload_key="intent",
                           verifier=verifier, expected_key=config.review_key_version)
    intent = validate_intent(review["intent"], now_ms=now_ms, max_order_usd=config.max_order_usd,
                             live_release=config.live_execution_release)
    if review["intent_id"] != intent["intent_id"] or review["prior_sha256"] != digest(intent):
        raise ContractError("review_intent_join_invalid")
    prior = digest(review)
    stage = {
        "schema": DISPATCH_SCHEMA,
        "stage_id": _stage_id("dispatch", intent["intent_id"], prior, _AUTHORITY_IDS["dispatch"]),
        "intent_id": intent["intent_id"], "prior_sha256": prior, "review": review,
        "authority_id": _AUTHORITY_IDS["dispatch"], "key_version": signer.key_version,
        "signed_at_ms": intent["created_at_ms"] + 2, "signature": "pending",
    }
    stage["signature"] = signer.sign(canonical_bytes(unsigned_stage(stage)))
    return validate_stage(stage, schema=DISPATCH_SCHEMA, payload_key="review", prior_digest=prior)


def _executor(input_value: Mapping[str, Any], config: ServiceConfig, signer: Signer,
              verifier: Verifier, now_ms: int, executor_factory: Callable[[float], Any] | None = None) -> dict[str, Any]:
    if config.dispatch_key_version is None or config.review_key_version is None:
        raise CloudBoundaryError("executor_key_pins_missing")
    dispatch = _verify_stage(input_value, schema=DISPATCH_SCHEMA, payload_key="review",
                             verifier=verifier, expected_key=config.dispatch_key_version)
    review = _verify_stage(dispatch["review"], schema=REVIEW_SCHEMA, payload_key="intent",
                           verifier=verifier, expected_key=config.review_key_version)
    intent = validate_intent(review["intent"], now_ms=now_ms, max_order_usd=config.max_order_usd,
                             live_release=config.live_execution_release)
    if dispatch["intent_id"] != intent["intent_id"] or dispatch["prior_sha256"] != digest(review):
        raise ContractError("dispatch_review_join_invalid")
    execution_error: type[Exception] | tuple[()] = ()
    if executor_factory is None:
        from live_executor import ExecutionError, LiveExecutor
        executor_factory = LiveExecutor
        execution_error = ExecutionError
    if intent["kind"] == ORDER_KIND:
        if not config.durable_budget_ledger:
            raise ContractError("durable_budget_ledger_unconfigured")
        if not config.order_adapter_ready:
            raise ContractError("live_order_adapter_unavailable")
        try:
            outcome = executor_factory(config.max_daily_budget_usd).execute(
                intent, dispatch_sha256=digest(dispatch),
            )
        except execution_error as exc:
            raise CloudBoundaryError(str(exc)) from exc
        if not isinstance(outcome, Mapping) or outcome.get("schema") != "aureon.cloud-trade-live-result.v1":
            raise CloudBoundaryError("live_executor_result_invalid")
        outcome = dict(outcome)
    else:
        if intent["kind"] != PROBE_KIND or intent["dry_run"] is not True:
            raise ContractError("executor_probe_contract_invalid")
        provider_readback = None
        if config.provider_probe_enabled:
            try:
                provider_readback = executor_factory(config.max_daily_budget_usd).provider_probe()
            except execution_error as exc:
                raise CloudBoundaryError(str(exc)) from exc
        outcome = {
            "schema": "aureon.cloud-trade-probe-result.v1",
            "status": "probe_passed", "dry_run": True,
            "provider_mutation_attempted": False, "orders_attempted": 0,
            "orders_submitted": 0, "dispatch_sha256": digest(dispatch),
            "provider_readback": provider_readback,
            "executor_capabilities": {
                "live_execution_release": config.live_execution_release,
                "durable_budget_ledger": config.durable_budget_ledger,
                "order_adapter_ready": config.order_adapter_ready,
            },
        }
    result = {"dispatch": dispatch, "outcome": outcome}
    prior = digest(dispatch)
    stage = {
        "schema": EXECUTOR_SCHEMA,
        "stage_id": _stage_id("executor", intent["intent_id"], prior, _AUTHORITY_IDS["executor"]),
        "intent_id": intent["intent_id"], "prior_sha256": prior, "result": result,
        "authority_id": _AUTHORITY_IDS["executor"], "key_version": signer.key_version,
        "signed_at_ms": intent["created_at_ms"] + 3, "signature": "pending",
    }
    stage["signature"] = signer.sign(canonical_bytes(unsigned_stage(stage)))
    return validate_stage(stage, schema=EXECUTOR_SCHEMA, payload_key="result", prior_digest=prior)


def _receipt(input_value: Mapping[str, Any], config: ServiceConfig, signer: Signer,
             verifier: Verifier, now_ms: int) -> dict[str, Any]:
    if config.executor_key_version is None:
        raise CloudBoundaryError("executor_key_pin_missing")
    executor = _verify_stage(input_value, schema=EXECUTOR_SCHEMA, payload_key="result",
                             verifier=verifier, expected_key=config.executor_key_version)
    result = executor["result"]
    if not isinstance(result, Mapping) or not isinstance(result.get("dispatch"), Mapping):
        raise ContractError("executor_result_shape_invalid")
    intent = _intent_from_chain(executor)
    validate_intent(intent, now_ms=now_ms, max_order_usd=config.max_order_usd,
                    live_release=config.live_execution_release)
    outcome = result.get("outcome")
    if not isinstance(outcome, Mapping) or outcome.get("intent_id", intent["intent_id"]) != intent["intent_id"]:
        raise ContractError("terminal_outcome_invalid")
    if intent["kind"] == PROBE_KIND:
        if (outcome.get("schema") != "aureon.cloud-trade-probe-result.v1"
                or outcome.get("provider_mutation_attempted") is not False
                or outcome.get("orders_attempted") != 0 or outcome.get("orders_submitted") != 0):
            raise ContractError("probe_terminal_outcome_invalid")
    else:
        status = outcome.get("status")
        valid = (
            outcome.get("schema") == "aureon.cloud-trade-live-result.v1"
            and outcome.get("dry_run") is False
            and outcome.get("dispatch_sha256") == digest(result["dispatch"])
            and status in {"provider_observed", "rejected", "uncertain"}
            and ((status == "provider_observed" and outcome.get("provider_mutation_attempted") is True
                  and outcome.get("orders_attempted") == 1 and outcome.get("orders_submitted") == 1
                  and isinstance(outcome.get("provider_readback_sha256"), str))
                 or (status == "rejected" and outcome.get("provider_mutation_attempted") is False
                     and outcome.get("orders_attempted") == 0 and outcome.get("orders_submitted") == 0)
                 or (status == "uncertain" and outcome.get("provider_mutation_attempted") is True
                     and outcome.get("orders_attempted") == 1 and outcome.get("orders_submitted") is None))
        )
        if not valid:
            raise ContractError("live_terminal_outcome_invalid")
    prior = digest(executor)
    stage = {
        "schema": RECEIPT_SCHEMA,
        "stage_id": _stage_id("receipt", intent["intent_id"], prior, _AUTHORITY_IDS["receipt"]),
        "intent_id": intent["intent_id"], "prior_sha256": prior, "executor": executor,
        "authority_id": _AUTHORITY_IDS["receipt"], "key_version": signer.key_version,
        "signed_at_ms": intent["created_at_ms"] + 4, "signature": "pending",
    }
    stage["signature"] = signer.sign(canonical_bytes(unsigned_stage(stage)))
    return validate_stage(stage, schema=RECEIPT_SCHEMA, payload_key="executor", prior_digest=prior)


_HANDLERS = {"review": _review, "dispatch": _dispatch, "executor": _executor, "receipt": _receipt}


def create_app(*, config: ServiceConfig | None = None, signer: Signer | None = None,
               verifier: Verifier | None = None, publisher: Publisher | None = None,
               clock=time.time, executor_factory: Callable[[float], Any] | None = None) -> Flask:
    cfg = ServiceConfig.from_env() if config is None else config
    kms = KmsBoundary(cfg.key_version)
    stage_signer = kms if signer is None else signer
    stage_verifier = kms if verifier is None else verifier
    if stage_signer.key_version != cfg.key_version:
        raise CloudBoundaryError("service_signer_key_mismatch")
    stage_publisher = (
        PubSubPublisher(cfg.output_topic) if publisher is None and cfg.output_topic is not None
        else publisher
    )
    if stage_publisher is None:
        raise CloudBoundaryError("service_publisher_missing")
    app = Flask(__name__)
    app.config.update(MAX_CONTENT_LENGTH=100_000, JSON_SORT_KEYS=True)

    @app.get("/healthz")
    def healthz():
        return jsonify({
            "ok": True, "schema": "aureon.cloud-trade-authority-health.v1",
            "role": cfg.role, "revision": cfg.revision,
            "production_ready": False,
            "live_execution_release": cfg.live_execution_release,
            "durable_budget_ledger": cfg.durable_budget_ledger,
            "order_adapter_ready": cfg.order_adapter_ready,
            "probe_path_ready": True,
        })

    @app.post("/process")
    def process():
        try:
            value = _decode_push(request.get_json(silent=True))
            handler = _HANDLERS[cfg.role]
            if cfg.role == "executor":
                result = handler(value, cfg, stage_signer, stage_verifier,
                                 int(float(clock()) * 1000), executor_factory)
            else:
                result = handler(value, cfg, stage_signer, stage_verifier, int(float(clock()) * 1000))
            published = stage_publisher.publish(result)
            return jsonify({
                "ok": True, "role": cfg.role, "intent_id": result["intent_id"],
                "stage_id": result["stage_id"], "published": published is not None,
            }), 204
        except ContractError as exc:
            app.logger.warning("authority_request_rejected reason_code=%s", str(exc))
            return jsonify({"ok": False, "reason_code": str(exc), "retryable": False}), 400
        except CloudBoundaryError as exc:
            app.logger.warning("authority_request_deferred reason_code=%s", str(exc))
            return jsonify({"ok": False, "reason_code": str(exc), "retryable": True}), 503
        except Exception:
            return jsonify({"ok": False, "reason_code": "authority_service_failed", "retryable": True}), 503

    return app


__all__ = [
    "CloudBoundaryError", "KmsBoundary", "PubSubPublisher", "ServiceConfig", "create_app",
]
