"""Verify one route-bound cloud intent from the private bridge.

The owner schema covers an explicit reviewed IAP control-plane allowlist. A
separate identity-bound tenant schema admits only enumerated account-owned,
non-trading effects. Neither schema grants exchange, order, payment, filing, or
production release authority.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import math
import os
import re
import sqlite3
import stat
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping

from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from aureon.operator.identity import owner_identity_commitment

INTENT_AUDIENCE = "aureon-operator-switchboard-intent"
INTENT_ISSUER = "aureon-private-bridge"
INTENT_SCHEMA = "aureon.operator.cloud-switchboard-intent.v2"
INTENT_HEADER = "X-Aureon-Operator-Intent"
TENANT_INTENT_AUDIENCE = "aureon-operator-tenant-route-intent"
TENANT_INTENT_SCHEMA = "aureon.operator.cloud-tenant-route-intent.v2"
SUPABASE_OWNER_INTENT_AUDIENCE = "aureon-operator-supabase-owner-route-intent"
SUPABASE_OWNER_INTENT_SCHEMA = "aureon.operator.cloud-supabase-owner-route-intent.v1"
MAX_INTENT_TOKEN_BYTES = 8 * 1024
MAX_INTENT_LIFETIME_SECONDS = 15
_FLAG_PATH = re.compile(r"/api/switchboard/[A-Z0-9_]{1,64}")
_AUTHORIZATION_PATH = "/api/operator/authorization-lease"
_CLOUD_TRADING_RELEASE_PATH = "/api/operator/cloud-trading-control/apply"
_TENANT_ROUTE_ID = r"[a-z0-9][a-z0-9_-]{0,63}"
_TENANT_ROUTE_PATTERNS = (
    ("POST", re.compile(rf"/api/providers/{_TENANT_ROUTE_ID}"), "/api/providers/<provider_id>"),
    ("DELETE", re.compile(rf"/api/providers/{_TENANT_ROUTE_ID}"), "/api/providers/<provider_id>"),
    (
        "POST",
        re.compile(rf"/api/providers/{_TENANT_ROUTE_ID}/test"),
        "/api/providers/<provider_id>/test",
    ),
    (
        "POST",
        re.compile(rf"/api/connections/{_TENANT_ROUTE_ID}"),
        "/api/connections/<conn_id>",
    ),
    (
        "DELETE",
        re.compile(rf"/api/connections/{_TENANT_ROUTE_ID}"),
        "/api/connections/<conn_id>",
    ),
    (
        "POST",
        re.compile(rf"/api/connections/{_TENANT_ROUTE_ID}/test"),
        "/api/connections/<conn_id>/test",
    ),
)
_TENANT_EXACT_ROUTES = {
    ("POST", "/api/cognition/reason"): "/api/cognition/reason",
    ("POST", "/api/operator/respond"): "/api/operator/respond",
    ("GET", "/api/cognition/stream"): "/api/cognition/stream",
    ("GET", "/api/operator/stream"): "/api/operator/stream",
    ("POST", "/api/trading/backtest"): "/api/trading/backtest",
    ("POST", "/api/notifications/telegram"): "/api/notifications/telegram",
}
_OWNER_ROUTE_PATTERNS = _TENANT_ROUTE_PATTERNS + (
    (
        "POST",
        re.compile(rf"/api/approvals/{_TENANT_ROUTE_ID}"),
        "/api/approvals/<item_id>",
    ),
)
_OWNER_EXACT_ROUTES = {
    **_TENANT_EXACT_ROUTES,
    ("POST", _AUTHORIZATION_PATH): _AUTHORIZATION_PATH,
    ("POST", _CLOUD_TRADING_RELEASE_PATH): _CLOUD_TRADING_RELEASE_PATH,
}
_ROUTE_CONTRACTS: dict[tuple[str, str], dict[str, Any]] = {
    ("POST", "/api/switchboard/<flag_id>"): {
        "effect_class": "configuration_mutation",
        "payload_schema": "aureon.operator.switchboard-change.v1",
        "state_mutation": True,
        "configuration_mutation": True,
        "external_read": False,
        "external_communication": False,
        "owner_control": True,
    },
    ("POST", _AUTHORIZATION_PATH): {
        "effect_class": "authorization_record_mutation",
        "payload_schema": "aureon.operator.authorization-lease-command.v1",
        "state_mutation": True,
        "configuration_mutation": False,
        "external_read": False,
        "external_communication": False,
        "owner_control": True,
    },
    ("POST", _CLOUD_TRADING_RELEASE_PATH): {
        "effect_class": "governed_release_request_mutation",
        "payload_schema": "aureon.operator.cloud-trading-release-command.v1",
        "state_mutation": True,
        "configuration_mutation": False,
        "external_read": False,
        "external_communication": False,
        "owner_control": True,
    },
    ("POST", "/api/providers/<provider_id>"): {
        "effect_class": "configuration_mutation",
        "payload_schema": "aureon.operator.provider-configuration.v1",
        "state_mutation": True,
        "configuration_mutation": True,
        "external_read": False,
        "external_communication": False,
        "owner_control": True,
    },
    ("DELETE", "/api/providers/<provider_id>"): {
        "effect_class": "configuration_deletion",
        "payload_schema": "aureon.operator.empty-body.v1",
        "state_mutation": True,
        "configuration_mutation": True,
        "external_read": False,
        "external_communication": False,
        "owner_control": True,
    },
    ("POST", "/api/providers/<provider_id>/test"): {
        "effect_class": "external_provider_probe_with_status_record",
        "payload_schema": "aureon.operator.provider-probe.v1",
        "state_mutation": True,
        "configuration_mutation": False,
        "external_read": True,
        "external_communication": False,
        "owner_control": False,
    },
    ("POST", "/api/connections/<conn_id>"): {
        "effect_class": "configuration_mutation",
        "payload_schema": "aureon.operator.connection-configuration.v1",
        "state_mutation": True,
        "configuration_mutation": True,
        "external_read": False,
        "external_communication": False,
        "owner_control": True,
    },
    ("DELETE", "/api/connections/<conn_id>"): {
        "effect_class": "configuration_deletion",
        "payload_schema": "aureon.operator.empty-body.v1",
        "state_mutation": True,
        "configuration_mutation": True,
        "external_read": False,
        "external_communication": False,
        "owner_control": True,
    },
    ("POST", "/api/connections/<conn_id>/test"): {
        "effect_class": "external_provider_probe_with_status_record",
        "payload_schema": "aureon.operator.connection-probe.v1",
        "state_mutation": True,
        "configuration_mutation": False,
        "external_read": True,
        "external_communication": False,
        "owner_control": False,
    },
    ("POST", "/api/approvals/<item_id>"): {
        "effect_class": "approval_record_mutation",
        "payload_schema": "aureon.operator.approval-decision.v1",
        "state_mutation": True,
        "configuration_mutation": False,
        "external_read": False,
        "external_communication": False,
        "owner_control": True,
    },
    ("POST", "/api/cognition/reason"): {
        "effect_class": "model_reasoning_request",
        "payload_schema": "aureon.operator.reasoning-request.v1",
        "state_mutation": False,
        "configuration_mutation": False,
        "external_read": True,
        "external_communication": False,
        "owner_control": False,
    },
    ("POST", "/api/operator/respond"): {
        "effect_class": "model_reasoning_request",
        "payload_schema": "aureon.operator.reasoning-request.v1",
        "state_mutation": False,
        "configuration_mutation": False,
        "external_read": True,
        "external_communication": False,
        "owner_control": False,
    },
    ("GET", "/api/cognition/stream"): {
        "effect_class": "model_reasoning_stream",
        "payload_schema": "aureon.operator.reasoning-stream-query.v1",
        "state_mutation": False,
        "configuration_mutation": False,
        "external_read": True,
        "external_communication": False,
        "owner_control": False,
    },
    ("GET", "/api/operator/stream"): {
        "effect_class": "model_reasoning_stream",
        "payload_schema": "aureon.operator.reasoning-stream-query.v1",
        "state_mutation": False,
        "configuration_mutation": False,
        "external_read": True,
        "external_communication": False,
        "owner_control": False,
    },
    ("POST", "/api/trading/backtest"): {
        "effect_class": "public_historical_read_analysis",
        "payload_schema": "aureon.operator.historical-backtest-request.v1",
        "state_mutation": False,
        "configuration_mutation": False,
        "external_read": True,
        "external_communication": False,
        "owner_control": False,
    },
    ("POST", "/api/notifications/telegram"): {
        "effect_class": "external_communication",
        "payload_schema": "aureon.operator.telegram-notification.v1",
        "state_mutation": False,
        "configuration_mutation": False,
        "external_read": False,
        "external_communication": True,
        "owner_control": True,
    },
}
_REVISION = re.compile(r"[0-9a-f]{40}")
_JTI = re.compile(r"[A-Za-z0-9_-]{24,96}")
_OWNER_CLAIMS = frozenset(
    {
        "aud",
        "body_sha256",
        "effect_class",
        "exp",
        "iat",
        "iss",
        "jti",
        "method",
        "mode",
        "path",
        "payload_schema",
        "query_sha256",
        "revision",
        "route_rule",
        "schema",
    }
)
_TENANT_CLAIMS = _OWNER_CLAIMS | frozenset(
    {"bearer_sha256", "tenant_identity_sha256"}
)
_SUPABASE_OWNER_CLAIMS = _OWNER_CLAIMS | frozenset(
    {"bearer_sha256", "owner_identity_sha256"}
)


class CloudIntentCustodyError(RuntimeError):
    """Fixed failure codes only; never include a token or key in the message."""


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _identity_commitment(tenant: str) -> str:
    return _sha(b"aureon-tenant-identity-v1\x00" + tenant.encode("utf-8", errors="strict"))


def _bearer_commitment(authorization: str) -> str:
    return _sha(b"aureon-tenant-bearer-v1\x00" + authorization.encode("ascii", errors="strict"))


def _tenant_identity_valid(tenant: object) -> bool:
    if not isinstance(tenant, str):
        return False
    try:
        return 0 < len(tenant.encode("utf-8", errors="strict")) <= 512
    except UnicodeError:
        return False


def _authorization_valid(authorization: object) -> bool:
    try:
        return bool(
            isinstance(authorization, str)
            and re.fullmatch(
                r"Bearer [A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+",
                authorization,
            )
            is not None
            and len(authorization.encode("ascii", errors="strict")) <= 8192
        )
    except UnicodeError:
        return False


def owner_intent_route_rule(method: str, path: str) -> str | None:
    """Return a rule only for a reviewed owner-IAP control-plane effect."""

    if method == "POST" and _FLAG_PATH.fullmatch(path):
        return "/api/switchboard/<flag_id>"
    exact = _OWNER_EXACT_ROUTES.get((method, path))
    if exact is not None:
        return exact
    for expected_method, pattern, rule in _OWNER_ROUTE_PATTERNS:
        if method == expected_method and pattern.fullmatch(path):
            return rule
    return None


def tenant_intent_route_rule(method: str, path: str) -> str | None:
    """Return a rule only for a reviewed tenant-owned, non-trading effect."""

    exact = _TENANT_EXACT_ROUTES.get((method, path))
    if exact is not None:
        return exact
    for expected_method, pattern, rule in _TENANT_ROUTE_PATTERNS:
        if method == expected_method and pattern.fullmatch(path):
            return rule
    return None


def _route_contract(method: str, route_rule: str | None) -> dict[str, Any] | None:
    if route_rule is None:
        return None
    raw = _ROUTE_CONTRACTS.get((method, route_rule))
    if raw is None:
        return None
    return {"method": method, "route_rule": route_rule, **raw}


def owner_intent_route_contract(method: str, path: str) -> dict[str, Any] | None:
    """Describe the exact effect and payload schema for one admitted owner route."""

    return _route_contract(method, owner_intent_route_rule(method, path))


def tenant_intent_route_contract(method: str, path: str) -> dict[str, Any] | None:
    """Describe the exact effect and payload schema for one admitted tenant route."""

    return _route_contract(method, tenant_intent_route_rule(method, path))


def _bounded_text(
    value: Any,
    *,
    minimum: int = 0,
    maximum: int,
    line_breaks: bool = False,
) -> bool:
    if not isinstance(value, str):
        return False
    try:
        raw = value.encode("utf-8", errors="strict")
    except UnicodeError:
        return False
    return bool(
        minimum <= len(raw) <= maximum
        and b"\x00" not in raw
        and (line_breaks or (b"\r" not in raw and b"\n" not in raw))
    )


def _credential_map(value: Any) -> bool:
    return bool(
        isinstance(value, dict)
        and len(value) <= 8
        and all(
            isinstance(key, str)
            and re.fullmatch(r"[A-Z][A-Z0-9_]{0,63}", key)
            and _bounded_text(item, maximum=8192)
            for key, item in value.items()
        )
    )


def _reasoning_payload(value: dict[str, Any]) -> bool:
    return bool(
        set(value) <= {"prompt", "session_id"}
        and "prompt" in value
        and _bounded_text(value["prompt"], minimum=1, maximum=32 * 1024, line_breaks=True)
        and (
            "session_id" not in value
            or value["session_id"] is None
            or _bounded_text(value["session_id"], minimum=1, maximum=256)
        )
    )


def _stream_query_allowed(query: bytes) -> bool:
    if not query or len(query) > 16 * 1024:
        return False
    try:
        raw = query.decode("ascii", errors="strict")
        if re.search(r"%(?![0-9A-Fa-f]{2})", raw):
            return False
        from urllib.parse import parse_qsl

        pairs = parse_qsl(
            raw,
            keep_blank_values=True,
            strict_parsing=True,
            encoding="utf-8",
            errors="strict",
            max_num_fields=2,
        )
    except (UnicodeError, ValueError):
        return False
    values = dict(pairs)
    return bool(
        len(values) == len(pairs)
        and set(values) <= {"prompt", "session_id"}
        and "prompt" in values
        and _bounded_text(values["prompt"], minimum=1, maximum=32 * 1024, line_breaks=True)
        and (
            "session_id" not in values
            or _bounded_text(values["session_id"], minimum=1, maximum=256)
        )
    )


_BACKTEST_CONFIG_KEYS = frozenset(
    {
        "symbol",
        "startDate",
        "endDate",
        "initialCapital",
        "tradeSize",
        "stopLoss",
        "takeProfit",
        "strategy",
        "intervalMinutes",
        "lookbackPeriods",
        "feeBps",
        "slippageBps",
    }
)


def _backtest_payload(value: dict[str, Any]) -> bool:
    config = value.get("config")
    if (
        set(value) != {"config", "request_id", "account_scope"}
        or not isinstance(config, dict)
        or set(config) != _BACKTEST_CONFIG_KEYS
        or not _bounded_text(value.get("request_id"), minimum=16, maximum=64)
        or re.fullmatch(r"[A-Za-z0-9-]{16,64}", value["request_id"]) is None
        or not isinstance(value.get("account_scope"), str)
        or re.fullmatch(r"[0-9a-f]{64}", value["account_scope"]) is None
    ):
        return False
    if not all(
        _bounded_text(config.get(field), minimum=1, maximum=32)
        for field in ("symbol", "startDate", "endDate", "strategy")
    ):
        return False
    numeric = {
        "initialCapital",
        "tradeSize",
        "stopLoss",
        "takeProfit",
        "intervalMinutes",
        "lookbackPeriods",
        "feeBps",
        "slippageBps",
    }
    return all(
        not isinstance(config.get(field), bool)
        and isinstance(config.get(field), (int, float))
        and math.isfinite(config[field])
        for field in numeric
    )


def _payload_allowed(
    *,
    mode: str,
    method: str,
    path: str,
    query: bytes,
    body: bytes,
    contract: Mapping[str, Any],
) -> bool:
    schema = contract["payload_schema"]
    if schema == "aureon.operator.reasoning-stream-query.v1":
        return method == "GET" and not body and _stream_query_allowed(query)
    if method == "GET" or query:
        return False
    if schema == "aureon.operator.empty-body.v1":
        return method == "DELETE" and not body
    if not body:
        return False
    try:
        value = _strict_object(body)
    except (UnicodeError, ValueError, TypeError, json.JSONDecodeError):
        return False
    if schema in {
        "aureon.operator.provider-configuration.v1",
        "aureon.operator.provider-probe.v1",
    }:
        allowed = {"api_key", "base_url", "model", "enabled"}
        if set(value) - allowed:
            return False
        if schema.endswith("provider-configuration.v1") and not value:
            return False
        return bool(
            ("api_key" not in value or _bounded_text(value["api_key"], minimum=1, maximum=8192))
            and ("base_url" not in value or _bounded_text(value["base_url"], maximum=2048))
            and ("model" not in value or _bounded_text(value["model"], maximum=256))
            and ("enabled" not in value or type(value["enabled"]) is bool)
        )
    if schema in {
        "aureon.operator.connection-configuration.v1",
        "aureon.operator.connection-probe.v1",
    }:
        allowed = {"api_key", "extra"}
        if schema.endswith("connection-configuration.v1"):
            allowed.add("enabled")
        return bool(
            not (set(value) - allowed)
            and ("api_key" not in value or _bounded_text(value["api_key"], maximum=8192))
            and ("extra" not in value or _credential_map(value["extra"]))
            and ("enabled" not in value or type(value["enabled"]) is bool)
        )
    if schema == "aureon.operator.approval-decision.v1":
        return bool(
            set(value) <= {"decision", "note"}
            and value.get("decision") in {"approve", "reject"}
            and ("note" not in value or _bounded_text(value["note"], maximum=4096, line_breaks=True))
        )
    if schema == "aureon.operator.reasoning-request.v1":
        return _reasoning_payload(value)
    if schema == "aureon.operator.historical-backtest-request.v1":
        return _backtest_payload(value)
    if schema == "aureon.operator.telegram-notification.v1":
        required = {"message"} | ({"botToken", "chatId"} if mode == "user" else set())
        return bool(
            required <= set(value) <= {"botToken", "chatId", "message", "parseMode"}
            and _bounded_text(value.get("message"), minimum=1, maximum=16 * 1024, line_breaks=True)
            and ("botToken" not in value or _bounded_text(value["botToken"], minimum=1, maximum=4096))
            and ("chatId" not in value or _bounded_text(value["chatId"], minimum=1, maximum=256))
            and (
                "parseMode" not in value
                or value["parseMode"] in {"Markdown", "MarkdownV2", "HTML"}
            )
        )
    if schema == "aureon.operator.switchboard-change.v1":
        return bool(
            {"enabled"} <= set(value) <= {"enabled", "confirm"}
            and type(value["enabled"]) is bool
            and ("confirm" not in value or _bounded_text(value["confirm"], minimum=1, maximum=64))
        )
    if schema == "aureon.operator.authorization-lease-command.v1":
        action = value.get("action")
        if action == "grant":
            return bool(
                set(value) == {"action", "confirm", "duration_seconds"}
                and value["confirm"] == "AUREON_72_HOUR_OPERATOR_AUTHORIZATION"
                and type(value["duration_seconds"]) is int
                and 60 <= value["duration_seconds"] <= 259200
            )
        return bool(
            action == "revoke"
            and set(value) == {"action", "confirm"}
            and value["confirm"] == "REVOKE_AUREON_OPERATOR_AUTHORIZATION"
        )
    if schema == "aureon.operator.cloud-trading-release-command.v1":
        action = value.get("action")
        expected = {
            "activate": "APPLY_AUREON_CLOUD_LIVE_TRADING",
            "hold": "HOLD_AUREON_CLOUD_LIVE_TRADING",
        }.get(action)
        return bool(
            expected is not None
            and set(value) == {"action", "confirm"}
            and value["confirm"] == expected
        )
    return False


def _tenant_payload_allowed(*, method: str, path: str, query: bytes, body: bytes) -> bool:
    """Narrow HTTP shapes before a tenant receipt can bypass the generic hold."""

    contract = tenant_intent_route_contract(method, path)
    return bool(
        contract is not None
        and _payload_allowed(
            mode="user",
            method=method,
            path=path,
            query=query,
            body=body,
            contract=contract,
        )
    )


def _owner_payload_allowed(*, method: str, path: str, query: bytes, body: bytes) -> bool:
    """Validate the bounded request shape for an owner allowlisted route."""

    contract = owner_intent_route_contract(method, path)
    return bool(
        contract is not None
        and _payload_allowed(
            mode="iap",
            method=method,
            path=path,
            query=query,
            body=body,
            contract=contract,
        )
    )


def _strict_object(raw: bytes) -> dict[str, Any]:
    def pairs(values: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in values:
            if key in result:
                raise ValueError("duplicate_key")
            result[key] = value
        return result

    value = json.loads(
        raw.decode("utf-8", errors="strict"),
        object_pairs_hook=pairs,
        parse_constant=lambda _value: (_ for _ in ()).throw(ValueError("constant")),
    )
    if not isinstance(value, dict):
        raise ValueError("object_required")
    pending: list[Any] = [value]
    visited = 0
    while pending:
        current = pending.pop()
        visited += 1
        if visited > 20_000:
            raise ValueError("object_too_complex")
        if isinstance(current, float) and not math.isfinite(current):
            raise ValueError("finite_number_required")
        if isinstance(current, dict):
            pending.extend(current.values())
        elif isinstance(current, list):
            pending.extend(current)
    return value


def _decode_segment(value: str) -> bytes:
    if not re.fullmatch(r"[A-Za-z0-9_-]+", value):
        raise ValueError("segment_invalid")
    try:
        return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    except (ValueError, binascii.Error) as exc:
        raise ValueError("segment_invalid") from exc


def _regular_file(path: str, *, label: str, maximum: int) -> Path:
    candidate = Path(path)
    if not candidate.is_absolute():
        raise CloudIntentCustodyError(label + "_absolute_path_required")
    try:
        resolved = candidate.resolve(strict=True)
        stat = resolved.stat()
    except OSError as exc:
        raise CloudIntentCustodyError(label + "_unavailable") from exc
    if candidate.is_symlink() or not resolved.is_file() or not 0 < stat.st_size <= maximum:
        raise CloudIntentCustodyError(label + "_invalid")
    return resolved


class CloudSwitchboardIntentCustody:
    """Pinned-certificate verifier with a durable one-use receipt ledger."""

    intent_only = True
    production_action_release = False
    release_authority = False
    mutation_authority = True
    economic_mutation_authority = False
    unbounded_mutation_authority = False

    def __init__(self, *, certificate_file: str, replay_ledger: str, revision: str) -> None:
        if not _REVISION.fullmatch(str(revision or "")):
            raise CloudIntentCustodyError("intent_revision_invalid")
        certificate_path = _regular_file(
            certificate_file, label="intent_certificate", maximum=64 * 1024
        )
        try:
            certificate = x509.load_pem_x509_certificate(certificate_path.read_bytes())
            public_key = certificate.public_key()
        except (OSError, ValueError, TypeError) as exc:
            raise CloudIntentCustodyError("intent_certificate_invalid") from exc
        if not isinstance(public_key, rsa.RSAPublicKey) or public_key.key_size < 2048:
            raise CloudIntentCustodyError("intent_certificate_key_invalid")
        current = datetime.now(UTC)
        if not (
            certificate.not_valid_before_utc <= current <= certificate.not_valid_after_utc
        ):
            raise CloudIntentCustodyError("intent_certificate_expired")
        ledger = Path(replay_ledger)
        if not ledger.is_absolute() or (ledger.exists() and ledger.is_symlink()):
            raise CloudIntentCustodyError("intent_replay_ledger_path_invalid")
        try:
            ledger.parent.mkdir(parents=True, exist_ok=True)
            parent = ledger.parent.resolve(strict=True)
        except OSError as exc:
            raise CloudIntentCustodyError("intent_replay_ledger_parent_unavailable") from exc
        self._certificate = certificate
        self._public_key = public_key
        self._ledger = parent / ledger.name
        self._revision = revision
        self._fingerprint = certificate.fingerprint(hashes.SHA256()).hex()
        self._preflight_ledger()

    @classmethod
    def from_env(cls, environ: Mapping[str, str]) -> CloudSwitchboardIntentCustody | None:
        certificate = str(environ.get("AUREON_OPERATOR_INTENT_CERT_FILE") or "").strip()
        ledger = str(environ.get("AUREON_OPERATOR_INTENT_LEDGER") or "").strip()
        revision = str(environ.get("AUREON_OPERATOR_REVISION") or "").strip()
        if not certificate and not ledger and not revision:
            return None
        if not certificate or not ledger or not revision:
            raise CloudIntentCustodyError("cloud_intent_custody_config_incomplete")
        return cls(certificate_file=certificate, replay_ledger=ledger, revision=revision)

    def _connect(self) -> sqlite3.Connection:
        if self._ledger.exists() and self._ledger.is_symlink():
            raise CloudIntentCustodyError("intent_replay_ledger_path_invalid")
        connection = sqlite3.connect(str(self._ledger), timeout=5, isolation_level=None)
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=FULL")
        connection.execute("PRAGMA busy_timeout=5000")
        return connection

    def _preflight_ledger(self) -> None:
        try:
            with self._connect() as connection:
                connection.execute(
                    "CREATE TABLE IF NOT EXISTS consumed_intents ("
                    "jti TEXT PRIMARY KEY NOT NULL, token_sha256 TEXT NOT NULL, "
                    "path TEXT NOT NULL, consumed_at INTEGER NOT NULL, expires_at INTEGER NOT NULL)"
                )
                columns = connection.execute("PRAGMA table_info(consumed_intents)").fetchall()
        except (OSError, sqlite3.Error) as exc:
            raise CloudIntentCustodyError("intent_replay_ledger_unavailable") from exc
        if [row[1] for row in columns] != [
            "jti", "token_sha256", "path", "consumed_at", "expires_at"
        ]:
            raise CloudIntentCustodyError("intent_replay_ledger_schema_invalid")
        try:
            self._ledger.chmod(0o600)
            if os.name == "posix" and stat.S_IMODE(self._ledger.stat().st_mode) != 0o600:
                raise OSError("ledger_mode")
        except OSError as exc:
            raise CloudIntentCustodyError("intent_replay_ledger_permissions_invalid") from exc

    def _consume(self, *, jti: str, token: str, path: str, now: int, expires: int) -> None:
        try:
            connection = self._connect()
            try:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute("DELETE FROM consumed_intents WHERE expires_at < ?", (now - 60,))
                connection.execute(
                    "INSERT INTO consumed_intents(jti,token_sha256,path,consumed_at,expires_at) "
                    "VALUES(?,?,?,?,?)",
                    (jti, _sha(token.encode("ascii")), path, now, expires),
                )
                connection.commit()
            finally:
                connection.close()
        except sqlite3.IntegrityError as exc:
            raise CloudIntentCustodyError("cloud_intent_receipt_replayed") from exc
        except (OSError, sqlite3.Error) as exc:
            raise CloudIntentCustodyError("intent_replay_ledger_unavailable") from exc

    def authorize_and_consume(
        self,
        *,
        token: str,
        method: str,
        path: str,
        route_rule: str,
        query: bytes,
        body: bytes,
        identity_kind: str,
        is_admin: bool,
        authorization: str = "",
        tenant: str | None = None,
        now: int | None = None,
    ) -> dict[str, Any]:
        owner_route = owner_intent_route_rule(method, path)
        tenant_route = tenant_intent_route_rule(method, path)
        iap_owner_mode = identity_kind == "admin" and is_admin is True
        supabase_owner_mode = (
            identity_kind == "owner"
            and is_admin is True
            and _tenant_identity_valid(tenant)
            and _authorization_valid(authorization)
        )
        owner_mode = iap_owner_mode or supabase_owner_mode
        tenant_mode = (
            identity_kind == "tenant"
            and is_admin is False
            and _tenant_identity_valid(tenant)
        )
        if owner_mode:
            expected_route = owner_route
            expected_contract = owner_intent_route_contract(method, path)
            expected_mode = "supabase_owner" if supabase_owner_mode else "iap"
            expected_claims = (
                _SUPABASE_OWNER_CLAIMS if supabase_owner_mode else _OWNER_CLAIMS
            )
            if not _owner_payload_allowed(
                method=method, path=path, query=query, body=body
            ):
                expected_route = None
        elif tenant_mode:
            expected_route = tenant_route
            expected_contract = tenant_intent_route_contract(method, path)
            expected_mode = "user"
            expected_claims = _TENANT_CLAIMS
            if not _authorization_valid(authorization) or not _tenant_payload_allowed(
                method=method, path=path, query=query, body=body
            ):
                expected_route = None
        else:
            expected_route = None
            expected_contract = None
            expected_mode = ""
            expected_claims = frozenset()
        if (
            expected_route is None
            or expected_contract is None
            or route_rule != expected_route
        ):
            raise CloudIntentCustodyError("cloud_intent_scope_denied")
        if not isinstance(token, str) or not 0 < len(token.encode("utf-8")) <= MAX_INTENT_TOKEN_BYTES:
            raise CloudIntentCustodyError("cloud_intent_receipt_missing")
        if not re.fullmatch(r"[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+", token):
            raise CloudIntentCustodyError("cloud_intent_receipt_invalid")
        try:
            encoded_header, encoded_claims, encoded_signature = token.split(".")
            header = _strict_object(_decode_segment(encoded_header))
            claims = _strict_object(_decode_segment(encoded_claims))
            self._public_key.verify(
                _decode_segment(encoded_signature),
                (encoded_header + "." + encoded_claims).encode("ascii"),
                padding.PKCS1v15(),
                hashes.SHA256(),
            )
        except (InvalidSignature, UnicodeError, ValueError, TypeError) as exc:
            raise CloudIntentCustodyError("cloud_intent_receipt_invalid") from exc
        if (
            set(header) != {"alg", "typ"}
            or header.get("alg") != "RS256"
            or header.get("typ") != "JWT"
        ):
            raise CloudIntentCustodyError("cloud_intent_receipt_header_invalid")
        if not isinstance(claims, dict) or set(claims) != expected_claims:
            raise CloudIntentCustodyError("cloud_intent_receipt_claims_invalid")
        issued, expires = claims.get("iat"), claims.get("exp")
        current = int(time.time()) if now is None else int(now)
        if (
            type(issued) is not int
            or type(expires) is not int
            or expires <= issued
            or expires - issued > MAX_INTENT_LIFETIME_SECONDS
            or issued > current + 2
            or expires < current - 2
        ):
            raise CloudIntentCustodyError("cloud_intent_receipt_time_invalid")
        jti = claims.get("jti")
        expected = {
            "schema": (
                SUPABASE_OWNER_INTENT_SCHEMA
                if supabase_owner_mode
                else INTENT_SCHEMA
                if owner_mode
                else TENANT_INTENT_SCHEMA
            ),
            "aud": (
                SUPABASE_OWNER_INTENT_AUDIENCE
                if supabase_owner_mode
                else INTENT_AUDIENCE
                if owner_mode
                else TENANT_INTENT_AUDIENCE
            ),
            "iss": INTENT_ISSUER,
            "method": method,
            "mode": expected_mode,
            "path": path,
            "route_rule": route_rule,
            "query_sha256": _sha(query),
            "body_sha256": _sha(body),
            "effect_class": expected_contract["effect_class"],
            "payload_schema": expected_contract["payload_schema"],
            "revision": self._revision,
        }
        if supabase_owner_mode:
            expected.update(
                {
                    "bearer_sha256": _bearer_commitment(authorization),
                    "owner_identity_sha256": owner_identity_commitment(str(tenant)),
                }
            )
        elif tenant_mode:
            expected.update(
                {
                    "bearer_sha256": _bearer_commitment(authorization),
                    "tenant_identity_sha256": _identity_commitment(tenant),
                }
            )
        if (
            not isinstance(jti, str)
            or not _JTI.fullmatch(jti)
            or any(claims.get(key) != value for key, value in expected.items())
        ):
            raise CloudIntentCustodyError("cloud_intent_receipt_join_invalid")
        self._consume(jti=jti, token=token, path=path, now=current, expires=expires)
        state_mutation = expected_contract["state_mutation"] is True
        configuration_mutation = expected_contract["configuration_mutation"] is True
        external_read = expected_contract["external_read"] is True
        external_communication = expected_contract["external_communication"] is True
        owner_control = owner_mode and expected_contract["owner_control"] is True
        return {
            "schema": "aureon.operator.cloud-switchboard-intent-custody.v2",
            "intent_recording_authorized": owner_mode,
            "owner_route_authorized": owner_mode,
            "tenant_route_authorized": tenant_mode,
            "identity_bound": tenant_mode or supabase_owner_mode,
            "owner_identity_bound": supabase_owner_mode,
            "effect_class": expected_contract["effect_class"],
            "payload_schema": expected_contract["payload_schema"],
            "request_method": method,
            "request_path": path,
            "request_revision": self._revision,
            "route_rule": route_rule,
            "query_sha256": _sha(query),
            "production_action_release": False,
            "release_authority": False,
            "mutation_authority": state_mutation or external_communication,
            "state_mutation_authority": state_mutation,
            "configuration_mutation_authority": configuration_mutation,
            "external_read_authority": external_read,
            "external_communication_authority": external_communication,
            "tool_dispatch_authority": False,
            "economic_mutation_authority": False,
            "owner_control_authority": owner_control,
            "tenant_account_mutation_authority": tenant_mode and state_mutation,
            "certificate_fingerprint_sha256": self._fingerprint,
            "token_sha256": _sha(token.encode("ascii")),
            "path_sha256": _sha(path.encode("utf-8")),
            "body_sha256": _sha(body),
            "consumed_at": current,
        }

    def public_summary(self) -> dict[str, Any]:
        return {
            "schema": "aureon.operator.cloud-switchboard-intent-custody.v2",
            "configured": True,
            "intent_recording_authority": True,
            "tenant_route_custody": True,
            "identity_bound_tenant_intents": True,
            "identity_bound_supabase_owner_intents": True,
            "scope": "owner_iap_or_verified_supabase_owner_intent_and_enumerated_tenant_non_trading_routes",
            "effect_classification": "exact_route_and_payload_schema_per_receipt",
            "durable_replay_ledger": True,
            "certificate_fingerprint_sha256": self._fingerprint,
            "production_action_release": False,
            "production_ready": False,
            "release_authority": False,
            "mutation_authority": True,
            "mutation_authority_scope": "exact_signed_route_only",
            "state_mutation_authority": True,
            "configuration_mutation_authority": True,
            "external_read_authority": True,
            "external_communication_authority": True,
            "unbounded_mutation_authority": False,
            "tool_dispatch_authority": False,
            "economic_mutation_authority": False,
            "owner_control_authority": True,
        }

    @property
    def revision(self) -> str:
        """Return the immutable deployment revision bound into every receipt."""

        return self._revision


__all__ = [
    "CloudIntentCustodyError",
    "CloudSwitchboardIntentCustody",
    "INTENT_AUDIENCE",
    "INTENT_HEADER",
    "INTENT_ISSUER",
    "INTENT_SCHEMA",
    "TENANT_INTENT_AUDIENCE",
    "TENANT_INTENT_SCHEMA",
    "SUPABASE_OWNER_INTENT_AUDIENCE",
    "SUPABASE_OWNER_INTENT_SCHEMA",
    "owner_intent_route_rule",
    "owner_intent_route_contract",
    "tenant_intent_route_rule",
    "tenant_intent_route_contract",
]
