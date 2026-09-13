"""Cloud Run product entry and independently authenticated private VM bridge.

This package contains no operator credentials and grants no release authority.
The marketed entry carries a browser Supabase bearer; the private VM bridge
asks the loopback operator to verify it before treating the designated owner as
an owner. IAP remains an independent commissioning/recovery identity.
"""
from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass
import hashlib
import http.client
import ipaddress
import json
import math
import os
from pathlib import Path
import re
import secrets
import socket
import ssl
import threading
import time
from urllib.parse import quote, urlsplit, unquote

import jwt
from cryptography import x509
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from flask import Flask, Response, jsonify, request

HOLDS = {
    "AUREON_DEPLOYMENT_HOLD": "1", "AUREON_DISABLE_REAL_ORDERS": "1",
    "AUREON_DISABLE_EXCHANGE_MUTATIONS": "1", "AUREON_ORDER_INTENT_PUBLISH": "0",
    "AUREON_LIVE_TRADING": "0", "AUREON_UNIFIED_ORDER_EXECUTOR": "0",
}
IAP_KEYS = "https://www.gstatic.com/iap/verify/public_key"
SERVICE_KEYS = "https://www.googleapis.com/oauth2/v1/certs"
METADATA_IDENTITY = "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/identity"
IAP_ADMIN_EMAIL_COMMITMENT_DOMAIN = b"aureon-iap-admin-email-v1\x00"
HEALTH = "/__aureon_health"
MAX_BODY = 256 * 1024
MAX_RESPONSE = 8 * 1024 * 1024
BRIDGE_COGNITION_TIMEOUT_SECONDS = 70
ENTRY_COGNITION_TIMEOUT_SECONDS = 75
SAFE_METHODS = {"GET", "HEAD"}
INSTANCE_ONLY_API_PATHS = frozenset({
    "/api/coding/status",
    "/api/terminal-state",
    "/api/flight-test",
    "/api/orca-observations",
})
INTENT_AUDIENCE = "aureon-operator-switchboard-intent"
INTENT_ISSUER = "aureon-private-bridge"
INTENT_SCHEMA = "aureon.operator.cloud-switchboard-intent.v2"
INTENT_HEADER = "X-Aureon-Operator-Intent"
TENANT_INTENT_AUDIENCE = "aureon-operator-tenant-route-intent"
TENANT_INTENT_SCHEMA = "aureon.operator.cloud-tenant-route-intent.v2"
SUPABASE_OWNER_INTENT_AUDIENCE = "aureon-operator-supabase-owner-route-intent"
SUPABASE_OWNER_INTENT_SCHEMA = "aureon.operator.cloud-supabase-owner-route-intent.v1"
_INTENT_PATH = re.compile(r"/api/switchboard/[A-Z0-9_]{1,64}")
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
_ROUTE_CONTRACTS = {
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


def _intent_route_rule(method, target):
    if method == "POST" and _INTENT_PATH.fullmatch(target):
        return "/api/switchboard/<flag_id>"
    exact = _OWNER_EXACT_ROUTES.get((method, target))
    if exact is not None:
        return exact
    for expected_method, pattern, rule in _OWNER_ROUTE_PATTERNS:
        if method == expected_method and pattern.fullmatch(target):
            return rule
    return None


def _tenant_intent_route_rule(method, path):
    exact = _TENANT_EXACT_ROUTES.get((method, path))
    if exact is not None:
        return exact
    for expected_method, pattern, rule in _TENANT_ROUTE_PATTERNS:
        if method == expected_method and pattern.fullmatch(path):
            return rule
    return None


def _route_contract(method, route_rule):
    if route_rule is None:
        return None
    raw = _ROUTE_CONTRACTS.get((method, route_rule))
    if raw is None:
        return None
    return {"method": method, "route_rule": route_rule, **raw}


def _owner_intent_route_contract(method, path):
    return _route_contract(method, _intent_route_rule(method, path))


def _tenant_intent_route_contract(method, path):
    return _route_contract(method, _tenant_intent_route_rule(method, path))


def _decode_json_segment(segment):
    if not isinstance(segment, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", segment):
        raise BoundaryError("tenant_bearer_shape_invalid")
    try:
        raw = base64.urlsafe_b64decode(segment + "=" * (-len(segment) % 4))
        if base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii") != segment:
            raise ValueError("noncanonical")

        def pairs(values):
            result = {}
            for key, value in values:
                if key in result:
                    raise ValueError("duplicate")
                result[key] = value
            return result

        value = json.loads(
            raw.decode("utf-8", errors="strict"),
            object_pairs_hook=pairs,
            parse_constant=lambda _value: (_ for _ in ()).throw(ValueError("constant")),
        )
    except (ValueError, TypeError, UnicodeError, binascii.Error, json.JSONDecodeError):
        raise BoundaryError("tenant_bearer_shape_invalid") from None
    if not isinstance(value, dict):
        raise BoundaryError("tenant_bearer_shape_invalid")
    return value


def _tenant_bearer_subject(authorization):
    """Validate compact-JWT shape and return only its untrusted asserted subject.

    The bridge uses this value only as signed commitment input. The operator
    separately verifies the bearer with Supabase before joining that verified
    identity to the receipt.
    """

    if not isinstance(authorization, str) or not authorization.startswith("Bearer "):
        raise BoundaryError("tenant_bearer_required")
    token = authorization[7:]
    try:
        if (
            not 20 <= len(token.encode("ascii", errors="strict")) <= 8185
            or not re.fullmatch(r"[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+", token)
        ):
            raise BoundaryError("tenant_bearer_shape_invalid")
    except UnicodeError:
        raise BoundaryError("tenant_bearer_shape_invalid") from None
    encoded_header, encoded_payload, encoded_signature = token.split(".")
    header = _decode_json_segment(encoded_header)
    payload = _decode_json_segment(encoded_payload)
    # Decode the signature solely to prove canonical bounded compact-JWT shape.
    try:
        decoded_signature = base64.urlsafe_b64decode(
            encoded_signature + "=" * (-len(encoded_signature) % 4)
        )
    except (ValueError, TypeError, binascii.Error):
        raise BoundaryError("tenant_bearer_shape_invalid") from None
    if (
        not decoded_signature
        or base64.urlsafe_b64encode(decoded_signature).rstrip(b"=").decode("ascii")
        != encoded_signature
        or not isinstance(header.get("alg"), str)
        or not re.fullmatch(r"[A-Za-z0-9_-]{3,16}", header["alg"])
        or header["alg"].casefold() == "none"
        or "crit" in header
    ):
        raise BoundaryError("tenant_bearer_shape_invalid")
    subject = payload.get("sub")
    if not isinstance(subject, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9:_-]{0,199}", subject):
        raise BoundaryError("tenant_bearer_shape_invalid")
    return subject


def _identity_commitment(subject):
    return hashlib.sha256(
        b"aureon-tenant-identity-v1\x00" + subject.encode("utf-8", errors="strict")
    ).hexdigest()


def _owner_identity_commitment(subject):
    return hashlib.sha256(
        b"aureon-supabase-owner-identity-v1\x00"
        + subject.encode("utf-8", errors="strict")
    ).hexdigest()


def _bearer_commitment(authorization):
    return hashlib.sha256(
        b"aureon-tenant-bearer-v1\x00" + authorization.encode("ascii", errors="strict")
    ).hexdigest()


def _strict_json_object(raw):
    if not raw:
        return {}
    try:
        def pairs(values):
            result = {}
            for key, value in values:
                if key in result:
                    raise ValueError("duplicate")
                result[key] = value
            return result

        value = json.loads(
            raw.decode("utf-8", errors="strict"),
            object_pairs_hook=pairs,
            parse_constant=lambda _value: (_ for _ in ()).throw(ValueError("constant")),
        )
    except (ValueError, TypeError, UnicodeError, json.JSONDecodeError):
        raise BoundaryError("tenant_intent_body_invalid") from None
    if not isinstance(value, dict):
        raise BoundaryError("tenant_intent_body_invalid")
    pending = [value]
    visited = 0
    while pending:
        current = pending.pop()
        visited += 1
        if visited > 20_000:
            raise BoundaryError("tenant_intent_body_invalid")
        if isinstance(current, float) and not math.isfinite(current):
            raise BoundaryError("tenant_intent_body_invalid")
        if isinstance(current, dict):
            pending.extend(current.values())
        elif isinstance(current, list):
            pending.extend(current)
    return value


def _bounded_text(value, *, minimum=0, maximum, line_breaks=False):
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


def _credential_map(value):
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


def _reasoning_payload(value):
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


def _stream_query_allowed(query):
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


def _backtest_payload(value):
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


def _intent_payload(mode, method, path, query, body, contract):
    schema = contract["payload_schema"]
    if schema == "aureon.operator.reasoning-stream-query.v1":
        if method != "GET" or body or not _stream_query_allowed(query):
            raise BoundaryError("intent_signing_scope_denied")
        return
    if method == "GET" or query:
        raise BoundaryError("intent_signing_scope_denied")
    if schema == "aureon.operator.empty-body.v1":
        if method != "DELETE" or body:
            raise BoundaryError("intent_signing_scope_denied")
        return
    if not body:
        raise BoundaryError("intent_signing_scope_denied")
    value = _strict_json_object(body)
    allowed = True
    if schema in {
        "aureon.operator.provider-configuration.v1",
        "aureon.operator.provider-probe.v1",
    }:
        fields = {"api_key", "base_url", "model", "enabled"}
        allowed = bool(
            not (set(value) - fields)
            and (schema != "aureon.operator.provider-configuration.v1" or value)
            and ("api_key" not in value or _bounded_text(value["api_key"], minimum=1, maximum=8192))
            and ("base_url" not in value or _bounded_text(value["base_url"], maximum=2048))
            and ("model" not in value or _bounded_text(value["model"], maximum=256))
            and ("enabled" not in value or type(value["enabled"]) is bool)
        )
    elif schema in {
        "aureon.operator.connection-configuration.v1",
        "aureon.operator.connection-probe.v1",
    }:
        fields = {"api_key", "extra"}
        if schema == "aureon.operator.connection-configuration.v1":
            fields.add("enabled")
        allowed = bool(
            not (set(value) - fields)
            and ("api_key" not in value or _bounded_text(value["api_key"], maximum=8192))
            and ("extra" not in value or _credential_map(value["extra"]))
            and ("enabled" not in value or type(value["enabled"]) is bool)
        )
    elif schema == "aureon.operator.approval-decision.v1":
        allowed = bool(
            set(value) <= {"decision", "note"}
            and value.get("decision") in {"approve", "reject"}
            and ("note" not in value or _bounded_text(value["note"], maximum=4096, line_breaks=True))
        )
    elif schema == "aureon.operator.reasoning-request.v1":
        allowed = _reasoning_payload(value)
    elif schema == "aureon.operator.historical-backtest-request.v1":
        allowed = _backtest_payload(value)
    elif schema == "aureon.operator.telegram-notification.v1":
        required = {"message"} | ({"botToken", "chatId"} if mode == "user" else set())
        allowed = bool(
            required <= set(value) <= {"botToken", "chatId", "message", "parseMode"}
            and _bounded_text(value.get("message"), minimum=1, maximum=16 * 1024, line_breaks=True)
            and ("botToken" not in value or _bounded_text(value["botToken"], minimum=1, maximum=4096))
            and ("chatId" not in value or _bounded_text(value["chatId"], minimum=1, maximum=256))
            and ("parseMode" not in value or value["parseMode"] in {"Markdown", "MarkdownV2", "HTML"})
        )
    elif schema == "aureon.operator.switchboard-change.v1":
        allowed = bool(
            {"enabled"} <= set(value) <= {"enabled", "confirm"}
            and type(value["enabled"]) is bool
            and ("confirm" not in value or _bounded_text(value["confirm"], minimum=1, maximum=64))
        )
    elif schema == "aureon.operator.authorization-lease-command.v1":
        action = value.get("action")
        allowed = bool(
            (
                action == "grant"
                and set(value) == {"action", "confirm", "duration_seconds"}
                and value["confirm"] == "AUREON_72_HOUR_OPERATOR_AUTHORIZATION"
                and type(value["duration_seconds"]) is int
                and 60 <= value["duration_seconds"] <= 259200
            )
            or (
                action == "revoke"
                and set(value) == {"action", "confirm"}
                and value["confirm"] == "REVOKE_AUREON_OPERATOR_AUTHORIZATION"
            )
        )
    elif schema == "aureon.operator.cloud-trading-release-command.v1":
        expected = {
            "activate": "APPLY_AUREON_CLOUD_LIVE_TRADING",
            "hold": "HOLD_AUREON_CLOUD_LIVE_TRADING",
        }.get(value.get("action"))
        allowed = bool(
            expected is not None
            and set(value) == {"action", "confirm"}
            and value["confirm"] == expected
        )
    else:
        allowed = False
    if not allowed:
        raise BoundaryError("intent_signing_scope_denied")


def _tenant_intent_payload(method, path, query, body):
    contract = _tenant_intent_route_contract(method, path)
    if contract is None:
        raise BoundaryError("intent_signing_scope_denied")
    _intent_payload("user", method, path, query, body, contract)
    return contract


def _owner_intent_payload(method, path, query, body):
    contract = _owner_intent_route_contract(method, path)
    if contract is None:
        raise BoundaryError("intent_signing_scope_denied")
    _intent_payload("iap", method, path, query, body, contract)
    return contract


class BoundaryError(RuntimeError):
    """Fixed codes only: never format tokens, claims, paths, or exception text."""


def iap_admin_email_commitment(email: str) -> str:
    """Commit a verified IAP email without retaining it in configuration."""

    if not isinstance(email, str) or len(email) > 320:
        raise BoundaryError("identity_claims_invalid")
    normalized = email.strip().casefold()
    if not re.fullmatch(
        r"[a-z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-z0-9.-]+", normalized
    ):
        raise BoundaryError("identity_claims_invalid")
    return hashlib.sha256(
        IAP_ADMIN_EMAIL_COMMITMENT_DOMAIN + normalized.encode("utf-8")
    ).hexdigest()


def holds_ready():
    return all(os.environ.get(name) == value for name, value in HOLDS.items())


@dataclass(frozen=True)
class Config:
    role: str
    origin: str
    iap_audience: str
    iap_admin_email_sha256: str
    service_email: str
    service_id: str
    bridge_url: str
    revision: str
    ca_file: str = ""
    access_mode: str = "iap"
    owner_origin: str = ""
    intent_key_file: str = ""

    @classmethod
    def from_env(cls):
        return cls(os.environ.get("AUREON_PUBLIC_ROLE", ""), os.environ.get("AUREON_PUBLIC_ORIGIN", ""),
                   os.environ.get("AUREON_IAP_AUDIENCE", ""),
                   os.environ.get("AUREON_IAP_ADMIN_EMAIL_SHA256", ""),
                   os.environ.get("AUREON_ENTRY_SERVICE_ACCOUNT_EMAIL", ""),
                   os.environ.get("AUREON_ENTRY_SERVICE_ACCOUNT_ID", ""),
                   os.environ.get("AUREON_BRIDGE_URL", ""), os.environ.get("AUREON_REVISION", ""),
                   os.environ.get("AUREON_BRIDGE_CA_FILE", ""),
                   os.environ.get("AUREON_PUBLIC_ACCESS_MODE", "iap"),
                   os.environ.get("AUREON_OWNER_ORIGIN", ""),
                   os.environ.get("AUREON_OPERATOR_INTENT_KEY_FILE", ""))

    def origins(self):
        values = {self.origin} if self.origin else set()
        if self.role == "bridge" and self.owner_origin:
            values.add(self.owner_origin)
        return frozenset(values)

    def validate(self):
        if self.role not in {"entry", "bridge"}:
            raise BoundaryError("role_invalid")
        allowed_modes = {"iap", "user"} if self.role == "entry" else {"iap", "user", "hybrid"}
        if self.access_mode not in allowed_modes:
            raise BoundaryError("access_mode_invalid")
        if self.access_mode in {"iap", "hybrid"}:
            if not re.fullmatch(r"/projects/[0-9]{6,20}/locations/[a-z]+-[a-z]+[0-9]/services/[a-z][a-z0-9-]{0,62}", self.iap_audience):
                raise BoundaryError("iap_audience_invalid")
            if not re.fullmatch(r"[0-9a-f]{64}", self.iap_admin_email_sha256):
                raise BoundaryError("iap_admin_email_commitment_invalid")
        elif self.iap_admin_email_sha256:
            raise BoundaryError("iap_admin_email_commitment_forbidden")
        if self.access_mode == "hybrid" and not self.owner_origin:
            raise BoundaryError("owner_origin_required")
        if not re.fullmatch(r"[a-z][a-z0-9-]{4,28}[a-z0-9]@[a-z][a-z0-9-]+\.iam\.gserviceaccount\.com", self.service_email):
            raise BoundaryError("service_account_invalid")
        if not re.fullmatch(r"[0-9]{10,25}", self.service_id) or not re.fullmatch(r"[0-9a-f]{40}", self.revision):
            raise BoundaryError("identity_or_revision_invalid")
        parsed = urlsplit(self.bridge_url)
        try:
            address = ipaddress.ip_address(parsed.hostname or "")
            valid_ip = address.version == 4 and any(address in ipaddress.ip_network(cidr)
                        for cidr in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"))
            valid = valid_ip and parsed.port == 8443 and self.bridge_url == f"https://{address}:8443"
        except ValueError:
            valid = False
        if not valid:
            raise BoundaryError("bridge_destination_invalid")
        # Empty origin is the explicit all-denied bootstrap state. Wildcards and
        # guessed host suffix trust are never accepted once it is commissioned.
        for origin in self.origins():
            if not re.fullmatch(r"https://[a-z0-9][a-z0-9-]+(?:\.[a-z0-9][a-z0-9-]*)?\.run\.app", origin):
                raise BoundaryError("public_origin_invalid")
        if self.role == "bridge" and self.intent_key_file:
            key_path = Path(self.intent_key_file)
            if not key_path.is_absolute():
                raise BoundaryError("intent_key_path_invalid")


class OperatorIntentSigner:
    """Use the VM-only RSA identity to sign one short-lived intent receipt."""

    def __init__(self, key_file, *, clock=time.time, nonce=secrets.token_urlsafe):
        path = Path(str(key_file or ""))
        try:
            resolved = path.resolve(strict=True)
            raw = resolved.read_bytes()
        except OSError as exc:
            raise BoundaryError("intent_signing_key_unavailable") from exc
        if not path.is_absolute() or path.is_symlink() or not 0 < len(raw) <= 64 * 1024:
            raise BoundaryError("intent_signing_key_invalid")
        try:
            key = serialization.load_pem_private_key(raw, password=None)
        except (ValueError, TypeError) as exc:
            raise BoundaryError("intent_signing_key_invalid") from exc
        if not isinstance(key, rsa.RSAPrivateKey) or key.key_size < 2048:
            raise BoundaryError("intent_signing_key_invalid")
        self._key = key
        self._clock = clock
        self._nonce = nonce

    def sign(
        self,
        *,
        method,
        target,
        body,
        mode,
        revision,
        query=b"",
        authorization="",
        tenant_subject=None,
        verified_owner_identity_sha256=None,
    ):
        if not isinstance(query, bytes):
            raise BoundaryError("intent_signing_scope_denied")
        if mode == "iap":
            route_rule = _intent_route_rule(method, target)
            if route_rule is None:
                raise BoundaryError("intent_signing_scope_denied")
            contract = _owner_intent_payload(method, target, query, body)
            schema = INTENT_SCHEMA
            audience = INTENT_AUDIENCE
        elif mode == "supabase_owner":
            route_rule = _intent_route_rule(method, target)
            if route_rule is None:
                raise BoundaryError("intent_signing_scope_denied")
            asserted_subject = _tenant_bearer_subject(authorization)
            expected_identity = _owner_identity_commitment(asserted_subject)
            if (
                not isinstance(verified_owner_identity_sha256, str)
                or not secrets.compare_digest(
                    verified_owner_identity_sha256, expected_identity
                )
            ):
                raise BoundaryError("owner_identity_proof_invalid")
            contract = _owner_intent_payload(method, target, query, body)
            schema = SUPABASE_OWNER_INTENT_SCHEMA
            audience = SUPABASE_OWNER_INTENT_AUDIENCE
        elif mode == "user":
            route_rule = _tenant_intent_route_rule(method, target)
            if route_rule is None:
                raise BoundaryError("intent_signing_scope_denied")
            asserted_subject = _tenant_bearer_subject(authorization)
            if tenant_subject is not None and tenant_subject != asserted_subject:
                raise BoundaryError("tenant_bearer_shape_invalid")
            tenant_subject = asserted_subject
            contract = _tenant_intent_payload(method, target, query, body)
            schema = TENANT_INTENT_SCHEMA
            audience = TENANT_INTENT_AUDIENCE
        else:
            raise BoundaryError("intent_signing_scope_denied")
        now = int(self._clock())
        claims = {
            "aud": audience,
            "body_sha256": hashlib.sha256(body).hexdigest(),
            "effect_class": contract["effect_class"],
            "exp": now + 10,
            "iat": now,
            "iss": INTENT_ISSUER,
            "jti": self._nonce(32),
            "method": method,
            "mode": mode,
            "path": target,
            "payload_schema": contract["payload_schema"],
            "query_sha256": hashlib.sha256(query).hexdigest(),
            "revision": revision,
            "route_rule": route_rule,
            "schema": schema,
        }
        if mode == "user":
            claims.update(
                {
                    "bearer_sha256": _bearer_commitment(authorization),
                    "tenant_identity_sha256": _identity_commitment(tenant_subject),
                }
            )
        elif mode == "supabase_owner":
            claims.update(
                {
                    "bearer_sha256": _bearer_commitment(authorization),
                    "owner_identity_sha256": verified_owner_identity_sha256,
                }
            )
        return jwt.encode(
            claims,
            self._key,
            algorithm="RS256",
            headers={"typ": "JWT"},
        )


def identity_fetch(url, *, metadata=False):
    if metadata:
        if not url.startswith(METADATA_IDENTITY + "?audience="):
            raise BoundaryError("identity_destination_invalid")
    elif url not in {IAP_KEYS, SERVICE_KEYS}:
        raise BoundaryError("identity_destination_invalid")
    headers = {"Metadata-Flavor": "Google"} if metadata else {"Accept": "application/json"}
    parsed = urlsplit(url)
    # Fixed hosts, direct socket transport: proxy environment variables, ambient
    # SDK credentials, redirects, and arbitrary key endpoints are not consulted.
    connection = (http.client.HTTPConnection(parsed.hostname, timeout=5) if metadata
                  else http.client.HTTPSConnection(parsed.hostname, timeout=5))
    timer = None
    deadline = time.monotonic() + 8
    try:
        connection.connect()
        wire_socket = connection.sock
        def expire():
            try:
                wire_socket.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
        timer = threading.Timer(max(0, deadline - time.monotonic()), expire)
        timer.daemon = True
        timer.start()
        connection.request("GET", parsed.path + ("?" + parsed.query if parsed.query else ""), headers=headers)
        response = connection.getresponse()
        if response.status != 200 or (metadata and response.getheader("Metadata-Flavor") != "Google"):
            raise BoundaryError("identity_fetch_failed")
        content = response.read(131073)
        if len(content) > 131072 or time.monotonic() >= deadline:
            raise BoundaryError("identity_response_too_large")
        return content
    except (OSError, ValueError, http.client.HTTPException):
        raise BoundaryError("identity_fetch_failed") from None
    finally:
        if timer:
            timer.cancel()
        connection.close()


class GoogleVerifier:
    """Google keys cached for five minutes; unknown keys refresh with a bound.

    No key, issuer, algorithm, or URL is chosen from untrusted JWT claims.
    Unverified JWT headers are used solely as a lookup in the fixed key set.
    """
    def __init__(self, fetch=identity_fetch):
        self.fetch = fetch
        self.cache = {}
        self.lock = threading.Lock()

    def key(self, url, kid):
        with self.lock:
            now = time.monotonic()
            loaded, keys = self.cache.get(url, (0, {}))
            if now - loaded >= 300 or not keys or (kid not in keys and now - loaded >= 30):
                try:
                    keys = json.loads(self.fetch(url))
                    if not isinstance(keys, dict) or not 0 < len(keys) <= 100:
                        raise ValueError()
                    if any(not isinstance(k, str) or not isinstance(v, str) or len(v) > 16384 for k, v in keys.items()):
                        raise ValueError()
                    self.cache[url] = now, keys
                except (ValueError, TypeError):
                    raise BoundaryError("identity_keys_invalid") from None
            if kid not in keys:
                raise BoundaryError("identity_key_unknown")
            pem = keys[kid]
            if pem.startswith("-----BEGIN CERTIFICATE-----"):
                return x509.load_pem_x509_certificate(pem.encode("ascii")).public_key()
            return pem

    def verify(self, token, *, audience, service=False):
        try:
            if not isinstance(token, str) or not re.fullmatch(r"[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+", token) or len(token) > 16384:
                raise BoundaryError("identity_token_invalid")
            header = jwt.get_unverified_header(token)
            algorithm = "RS256" if service else "ES256"
            if header.get("alg") != algorithm or not isinstance(header.get("kid"), str) or len(header["kid"]) > 128 or "crit" in header:
                raise BoundaryError("identity_header_invalid")
            key = self.key(SERVICE_KEYS if service else IAP_KEYS, header["kid"])
            claims = jwt.decode(token, key, algorithms=[algorithm], audience=audience,
                                issuer=("https://accounts.google.com", "accounts.google.com") if service else "https://cloud.google.com/iap",
                                leeway=30, options={"require": ["exp", "iat", "aud", "iss", "sub", "email"], "strict_aud": True})
            if (any(type(claims.get(k)) is not int for k in ("iat", "exp"))
                    or not isinstance(claims.get("sub"), str) or not claims["sub"]
                    or not isinstance(claims.get("email"), str)):
                raise BoundaryError("identity_claims_invalid")
            if not 0 < claims["exp"] - claims["iat"] <= (3660 if service else 660):
                raise BoundaryError("identity_lifetime_invalid")
            return claims
        except (jwt.PyJWTError, ValueError, TypeError, UnicodeError):
            raise BoundaryError("identity_token_invalid") from None

    def user(self, token, config):
        claims = self.verify(token, audience=config.iap_audience)
        actual = iap_admin_email_commitment(claims["email"])
        if not secrets.compare_digest(actual, config.iap_admin_email_sha256):
            raise BoundaryError("user_not_authorized")
        return claims

    def service(self, header, config):
        if not isinstance(header, str) or not header.startswith("Bearer "):
            raise BoundaryError("service_identity_required")
        claims = self.verify(header[7:], audience=config.bridge_url, service=True)
        if (claims["email"] != config.service_email or claims["sub"] != config.service_id
                or claims.get("email_verified") is not True):
            raise BoundaryError("service_identity_denied")
        return claims


class MetadataIdentity:
    def __init__(self, config, verifier, fetch=identity_fetch):
        self.config, self.verifier, self.fetch = config, verifier, fetch
        self.lock = threading.Lock()
        self.cached, self.expires = "", 0

    def __call__(self):
        with self.lock:
            if self.expires <= time.time() + 90:
                raw = self.fetch(METADATA_IDENTITY + "?audience=" + quote(self.config.bridge_url, safe="") + "&format=full", metadata=True)
                try:
                    token = raw.decode("ascii")
                except UnicodeError:
                    raise BoundaryError("metadata_identity_invalid") from None
                claims = self.verifier.service("Bearer " + token, self.config)
                self.cached, self.expires = token, claims["exp"]
            return self.cached


def request_gate(environ, config):
    if not config.origin:
        raise BoundaryError("entry_not_commissioned")
    actual = environ.get("HTTP_HOST") if config.role == "entry" else environ.get("HTTP_X_AUREON_PUBLIC_HOST")
    request_origin = next((origin for origin in config.origins() if origin.removeprefix("https://") == actual), None)
    if request_origin is None:
        raise BoundaryError("public_host_mismatch")
    if config.role == "entry" and environ.get("HTTP_X_FORWARDED_PROTO") != "https":
        raise BoundaryError("https_required")
    if "HTTP_ORIGIN" in environ and environ["HTTP_ORIGIN"] != request_origin:
        raise BoundaryError("same_origin_required")
    method = environ.get("REQUEST_METHOD", "")
    path = environ.get("PATH_INFO", "")
    if method not in {"GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"}:
        raise BoundaryError("method_denied")
    if method not in SAFE_METHODS and environ.get("HTTP_ORIGIN") != request_origin:
        raise BoundaryError("csrf_origin_required")
    if path == "/api" or path.startswith("/api/") or method not in SAFE_METHODS:
        if environ.get("HTTP_SEC_FETCH_SITE") not in {None, "same-origin"}:
            raise BoundaryError("cross_site_request_denied")
        if environ.get("HTTP_ORIGIN") != request_origin and environ.get("HTTP_SEC_FETCH_SITE") != "same-origin":
            raise BoundaryError("same_origin_evidence_required")
    for name, limit in (("HTTP_AUTHORIZATION", 8192), ("HTTP_X_AUREON_AUTH_RESOLUTION", 128)):
        if name in environ and (not isinstance(environ[name], str) or len(environ[name]) > limit or re.search(r"[\r\n\x00]", environ[name])):
            raise BoundaryError("auth_header_invalid")


def forwarded_headers(environ):
    result = {}
    for source, target in (("HTTP_ACCEPT", "Accept"), ("CONTENT_TYPE", "Content-Type"),
                           ("HTTP_AUTHORIZATION", "Authorization"),
                           ("HTTP_X_AUREON_AUTH_RESOLUTION", "X-Aureon-Auth-Resolution"),
                           ("HTTP_ORIGIN", "Origin"), ("HTTP_SEC_FETCH_SITE", "Sec-Fetch-Site")):
        if source in environ:
            value = environ[source]
            if len(value) > 8192 or re.search(r"[\r\n\x00]", value):
                raise BoundaryError("request_header_invalid")
            result[target] = value
    # Deliberate allowlist: no Cookie, client forwarding/identity headers, serverless
    # authorization, proxy headers, websocket upgrades, or arbitrary destinations.
    return result


def entry_mode_allowed(config, mode):
    if config.access_mode == "hybrid":
        return mode in {"iap", "user"}
    return mode == config.access_mode


def request_target(environ):
    path, query = environ.get("PATH_INFO", ""), environ.get("QUERY_STRING", "")
    if not path.startswith("/") or path.startswith("//") or re.search(r"[\x00-\x20\\]", path + query):
        raise BoundaryError("request_target_invalid")
    if any(part in {".", ".."} for part in unquote(path).split("/")):
        raise BoundaryError("request_target_invalid")
    # WSGI PATH_INFO is already URL decoded. Re-encode delimiters so a decoded '?'
    # cannot become a new query and encoded slashes cannot create another origin.
    target = quote(path, safe="/!$&'()*+,;=:@-._~")
    return target + ("?" + query if query else "")


def exchange(host, port, method, target, headers, body, *, context=None, timeout=30, limit=MAX_RESPONSE):
    connection = (http.client.HTTPSConnection(host, port, context=context, timeout=timeout)
                  if context is not None else http.client.HTTPConnection(host, port, timeout=timeout))
    timer = None
    deadline = time.monotonic() + timeout
    try:
        connection.connect()
        wire_socket = connection.sock
        def expire():
            try:
                wire_socket.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
        timer = threading.Timer(max(0, deadline - time.monotonic()), expire)
        timer.daemon = True
        timer.start()
        connection.request(method, target, body=body, headers=headers)
        upstream = connection.getresponse()
        if 300 <= upstream.status < 400 or upstream.getheader("Content-Encoding", "identity") != "identity":
            raise BoundaryError("upstream_response_denied")
        content = upstream.read(limit + 1)
        if len(content) > limit or time.monotonic() >= deadline:
            raise BoundaryError("upstream_response_limit")
        result_headers = {"Content-Type": upstream.getheader("Content-Type", "application/octet-stream")}
        retry = upstream.getheader("Retry-After", "")
        if re.fullmatch(r"[0-9]{1,6}(?:\.[0-9]{1,3})?", retry):
            result_headers["Retry-After"] = retry
        return upstream.status, result_headers, content
    except (OSError, http.client.HTTPException, ValueError):
        raise BoundaryError("upstream_unavailable") from None
    finally:
        if timer:
            timer.cancel()
        connection.close()


class Transport:
    def __init__(self, config):
        self.config = config
        self.context = None
        if config.role == "entry" and config.origin:
            if not config.ca_file or not Path(config.ca_file).is_file():
                raise BoundaryError("bridge_certificate_required")
            # This trust store contains ONLY the deployment's VM certificate.
            self.context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            self.context.minimum_version = ssl.TLSVersion.TLSv1_2
            self.context.load_verify_locations(cafile=config.ca_file)

    def __call__(self, method, target, headers, body, *, health=False):
        cognition = target.split("?", 1)[0] in {
            "/api/cognition/reason", "/api/cognition/stream",
            "/api/operator/respond", "/api/operator/stream",
        }
        if self.config.role == "entry":
            return exchange(
                urlsplit(self.config.bridge_url).hostname, 8443, method, target,
                headers, body, context=self.context,
                timeout=ENTRY_COGNITION_TIMEOUT_SECONDS if cognition else 30,
            )
        return exchange("127.0.0.1", 5173, method, target, headers, body,
                        timeout=(3 if health else BRIDGE_COGNITION_TIMEOUT_SECONDS
                                 if cognition else 30),
                        limit=4096 if health else MAX_RESPONSE)


def _verified_loopback_route_mode(transport, authorization, asserted_subject):
    """Ask the loopback operator to re-verify this exact bearer.

    A malformed/unavailable proof is a least-privilege result, never an owner
    result. The actual request still reaches the operator with the bearer, where
    it is verified again before any handler or signed receipt can be accepted.
    """

    proof_headers = {
        "Accept": "application/json",
        "Authorization": authorization,
        "Origin": "http://127.0.0.1:5173",
        "Sec-Fetch-Site": "same-origin",
        "X-Aureon-Auth-Resolution": "tenant-bearer",
    }
    status, response_headers, raw = transport(
        "GET", "/api/me", proof_headers, b""
    )
    if status != 200 or not isinstance(raw, bytes) or len(raw) > 64 * 1024:
        return "user", None
    content_type = str(response_headers.get("Content-Type", "")).split(";", 1)[0]
    if content_type != "application/json":
        return "user", None
    try:
        value = json.loads(raw.decode("utf-8", errors="strict"))
    except (UnicodeError, ValueError, TypeError, json.JSONDecodeError):
        return "user", None
    if not isinstance(value, dict):
        return "user", None
    if (
        value.get("kind") == "owner"
        and value.get("is_admin") is True
        and value.get("plane") == "instance"
        and value.get("auth_source") == "supabase_auth_server"
        and value.get("owner_designation_verified") is True
    ):
        expected = _owner_identity_commitment(asserted_subject)
        received = value.get("identity_commitment_sha256")
        if isinstance(received, str) and secrets.compare_digest(received, expected):
            return "supabase_owner", received
    return "user", None


def create_app(
    config=None,
    *,
    verifier=None,
    transport=None,
    identity=None,
    intent_signer=None,
):
    config = config or Config.from_env()
    config.validate()
    verifier = verifier or GoogleVerifier()
    transport = transport or Transport(config)
    identity = identity or MetadataIdentity(config, verifier)
    if config.role == "bridge" and intent_signer is None and config.intent_key_file:
        intent_signer = OperatorIntentSigner(config.intent_key_file)
    app = Flask("aureon_public_" + config.role, static_folder=None)
    app.config["MAX_CONTENT_LENGTH"] = MAX_BODY

    @app.after_request
    def response_policy(response):
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        if config.role == "entry":
            response.headers["Strict-Transport-Security"] = "max-age=31536000"
        return response

    @app.route("/", defaults={"rest": ""}, methods=["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
    @app.route("/<path:rest>", methods=["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
    def proxy(rest):
        del rest
        if not config.origin or not holds_ready():
            return jsonify(error="entry_not_commissioned", available=False), 503
        try:
            request_gate(request.environ, config)
            assertion = request.headers.get("X-Goog-Iap-Jwt-Assertion", "") if config.role == "entry" else request.headers.get("X-Aureon-Iap-Assertion", "")
            if config.role == "bridge":
                if request.host != urlsplit(config.bridge_url).netloc:
                    raise BoundaryError("bridge_host_mismatch")
                verifier.service(request.headers.get("X-Aureon-Service-Authorization", ""), config)
                entry_mode = request.headers.get("X-Aureon-Entry-Mode", "")
                if not entry_mode and config.access_mode == "iap":
                    # Backward-compatible owner bridge deployments predate the
                    # explicit route-mode header and are IAP-only by contract.
                    entry_mode = "iap"
                if not entry_mode_allowed(config, entry_mode):
                    raise BoundaryError("entry_mode_denied")
            else:
                entry_mode = config.access_mode
            tenant_subject = None
            if entry_mode == "user" and (request.path == "/api" or request.path.startswith("/api/")):
                # The customer origin must never rely on a downstream registrar
                # to distinguish anonymous traffic from the instance's legacy
                # telemetry processes. Require a tenant-shaped bearer for every
                # API request at the outer boundary and keep the three non-
                # operator loopback surfaces owner-only for every tenant.
                authorization = request.headers.get("Authorization", "")
                tenant_subject = _tenant_bearer_subject(authorization)
                if config.role == "bridge" and request.headers.get(
                    "X-Aureon-Auth-Resolution"
                ) != "tenant-bearer":
                    raise BoundaryError("tenant_auth_resolution_required")
                # The public entry cannot decide whether this verified-shape
                # bearer belongs to the owner. The private bridge asks the
                # loopback operator before any owner-only route is elevated.
            if entry_mode == "iap":
                verifier.user(assertion, config)
            elif assertion:
                # A public-user request cannot smuggle an identity assertion
                # into the bridge and have it interpreted by a different mode.
                raise BoundaryError("unexpected_iap_assertion")
            target = request_target(request.environ)
            headers = forwarded_headers(request.environ)
        except BoundaryError:
            return jsonify(error="request_not_authorized", available=False), 403
        try:
            if config.role == "entry":
                headers.update({"X-Aureon-Service-Authorization": "Bearer " + identity(),
                                "X-Aureon-Entry-Mode": entry_mode,
                                "X-Aureon-Public-Host": config.origin.removeprefix("https://")})
                if entry_mode == "iap":
                    headers["X-Aureon-Iap-Assertion"] = assertion
                else:
                    authorization = headers.get("Authorization", "")
                    headers["X-Aureon-Auth-Resolution"] = (
                        "tenant-bearer"
                        if re.fullmatch(r"Bearer [A-Za-z0-9._-]{20,8192}", authorization)
                        else "anonymous"
                    )
            else:
                # Every bridge request requires live, matching loopback health.
                status, _, raw = transport("GET", HEALTH, {}, b"", health=True)
                state = json.loads(raw)
                if (status != 200 or not isinstance(state, dict) or state.get("schema") != "aureon.cloud-http-health.v1"
                        or state.get("role") != "ui-gateway" or state.get("revision") != config.revision
                        or state.get("ready") is not True or state.get("deployment_hold") is not True
                        or state.get("release_authority") is not False):
                    raise BoundaryError("runtime_not_ready")
                # Only after BOTH signed identities + origin checks are valid may
                # the bridge supply same-origin evidence to the loopback gateway.
                # Any client Authorization/failed marker remains present exactly.
                headers.update({"Origin": "http://127.0.0.1:5173", "Sec-Fetch-Site": "same-origin"})
                effective_mode = entry_mode
                owner_identity_sha256 = None
                candidate_owner_route = _intent_route_rule(request.method, request.path)
                tenant_route = (
                    _tenant_intent_route_rule(request.method, request.path)
                    if entry_mode == "user"
                    else None
                )
                if entry_mode == "user" and (
                    candidate_owner_route is not None
                    or request.path in INSTANCE_ONLY_API_PATHS
                ):
                    effective_mode, owner_identity_sha256 = _verified_loopback_route_mode(
                        transport,
                        headers.get("Authorization", ""),
                        tenant_subject,
                    )
                    if (
                        request.path in INSTANCE_ONLY_API_PATHS
                        and effective_mode != "supabase_owner"
                    ):
                        return jsonify(error="request_not_authorized", available=False), 403
                    if (
                        candidate_owner_route is not None
                        and tenant_route is None
                        and effective_mode != "supabase_owner"
                    ):
                        return jsonify(error="request_not_authorized", available=False), 403
                owner_route = (
                    candidate_owner_route
                    if effective_mode in {"iap", "supabase_owner"}
                    else None
                )
                if effective_mode == "supabase_owner":
                    tenant_route = None
                if owner_route is not None or tenant_route is not None:
                    if intent_signer is None:
                        raise BoundaryError("intent_signer_unavailable")
                    headers[INTENT_HEADER] = intent_signer.sign(
                        method=request.method,
                        target=request.path,
                        query=bytes(request.query_string),
                        body=request.get_data(),
                        mode=effective_mode,
                        revision=config.revision,
                        authorization=headers.get("Authorization", ""),
                        tenant_subject=tenant_subject,
                        verified_owner_identity_sha256=owner_identity_sha256,
                    )
            status, response_headers, body = transport(request.method, target, headers, request.get_data())
            return Response(body, status=status, headers=response_headers)
        except (BoundaryError, ValueError, TypeError):
            return jsonify(error="cloud_runtime_unavailable", available=False), 502

    @app.errorhandler(413)
    def too_large(error):
        del error
        return jsonify(error="request_too_large"), 413

    return app
