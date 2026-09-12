"""Canonical contracts for the isolated Google Cloud trading authority chain.

The contract carries no credentials and performs no network I/O.  A message is
accepted only when it is small, current, exactly shaped, and joined to the same
intent through every stage.  Live orders remain unavailable until every service
is deployed with an explicit release state; the probe path can never mutate an
exchange.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from typing import Any, Mapping


INTENT_SCHEMA = "aureon.cloud-trade-intent.v1"
REVIEW_SCHEMA = "aureon.cloud-trade-review.v1"
DISPATCH_SCHEMA = "aureon.cloud-trade-dispatch.v1"
EXECUTOR_SCHEMA = "aureon.cloud-trade-executor-result.v1"
RECEIPT_SCHEMA = "aureon.cloud-trade-terminal-receipt.v1"
PROBE_KIND = "control_plane_probe"
ORDER_KIND = "order"
MAX_MESSAGE_BYTES = 65_536
MAX_INTENT_LIFETIME_MS = 60_000
MAX_CLOCK_SKEW_MS = 5_000
_HEX64 = re.compile(r"[0-9a-f]{64}")
_OPAQUE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{7,127}")
_SYMBOL = re.compile(r"[A-Z0-9][A-Z0-9./_-]{1,31}")
_VENUES = {"alpaca", "binance", "capital", "kraken"}
_CONTROL_KEYS = {
    "AUREON_DEPLOYMENT_HOLD",
    "AUREON_DISABLE_REAL_ORDERS",
    "AUREON_DISABLE_EXCHANGE_MUTATIONS",
    "AUREON_LIVE_TRADING",
    "AUREON_ORDER_INTENT_PUBLISH",
    "AUREON_UNIFIED_ORDER_EXECUTOR",
}


class ContractError(ValueError):
    """Stable fail-closed contract error."""


def canonical_bytes(value: Mapping[str, Any]) -> bytes:
    try:
        data = json.dumps(value, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=True, allow_nan=False).encode("ascii")
    except (TypeError, ValueError, UnicodeError) as exc:
        raise ContractError("message_not_canonical_json") from exc
    if not 0 < len(data) <= MAX_MESSAGE_BYTES:
        raise ContractError("message_size_invalid")
    return data


def digest(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _exact(value: Any, keys: set[str], code: str) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != keys:
        raise ContractError(code)
    return dict(value)


def _hex(value: Any, code: str) -> str:
    if not isinstance(value, str) or not _HEX64.fullmatch(value):
        raise ContractError(code)
    return value


def _opaque(value: Any, code: str) -> str:
    if not isinstance(value, str) or not _OPAQUE.fullmatch(value):
        raise ContractError(code)
    return value


def _uint(value: Any, code: str) -> int:
    if type(value) is not int or value < 0:
        raise ContractError(code)
    return value


def _number(value: Any, code: str, *, positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ContractError(code)
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ContractError(code) from exc
    if not math.isfinite(result) or result < 0 or (positive and result <= 0):
        raise ContractError(code)
    return result


def validate_controls(value: Any, *, live: bool) -> dict[str, bool]:
    controls = _exact(value, _CONTROL_KEYS, "control_shape_invalid")
    if any(type(item) is not bool for item in controls.values()):
        raise ContractError("control_value_invalid")
    if live:
        required = {
            "AUREON_DEPLOYMENT_HOLD": False,
            "AUREON_DISABLE_REAL_ORDERS": False,
            "AUREON_DISABLE_EXCHANGE_MUTATIONS": False,
            "AUREON_LIVE_TRADING": True,
            "AUREON_ORDER_INTENT_PUBLISH": True,
            "AUREON_UNIFIED_ORDER_EXECUTOR": True,
        }
        if controls != required:
            raise ContractError("live_control_state_not_armed")
    else:
        if controls["AUREON_DEPLOYMENT_HOLD"] is not True:
            raise ContractError("probe_requires_deployment_hold")
        if controls["AUREON_DISABLE_REAL_ORDERS"] is not True:
            raise ContractError("probe_requires_real_orders_disabled")
        if controls["AUREON_DISABLE_EXCHANGE_MUTATIONS"] is not True:
            raise ContractError("probe_requires_exchange_mutations_disabled")
        if controls["AUREON_LIVE_TRADING"] is not False:
            raise ContractError("probe_requires_live_trading_disabled")
    return controls


def validate_order(value: Any, *, max_order_usd: float) -> dict[str, Any]:
    order = _exact(value, {
        "venue", "symbol", "side", "order_type", "quantity", "quote_value_usd",
        "limit_price", "client_order_id",
    }, "order_shape_invalid")
    venue = order["venue"]
    if venue not in _VENUES:
        raise ContractError("order_venue_invalid")
    if not isinstance(order["symbol"], str) or not _SYMBOL.fullmatch(order["symbol"]):
        raise ContractError("order_symbol_invalid")
    if order["side"] not in {"BUY", "SELL"}:
        raise ContractError("order_side_invalid")
    if order["order_type"] not in {"MARKET", "LIMIT"}:
        raise ContractError("order_type_invalid")
    quantity = _number(order["quantity"], "order_quantity_invalid", positive=True)
    quote = _number(order["quote_value_usd"], "order_quote_value_invalid", positive=True)
    if quote > max_order_usd:
        raise ContractError("order_budget_exceeded")
    limit_price = order["limit_price"]
    if order["order_type"] == "LIMIT":
        _number(limit_price, "order_limit_price_invalid", positive=True)
    elif limit_price is not None:
        raise ContractError("market_order_limit_price_forbidden")
    _opaque(order["client_order_id"], "client_order_id_invalid")
    return {**order, "quantity": quantity, "quote_value_usd": quote}


def validate_intent(value: Any, *, now_ms: int, max_order_usd: float,
                    live_release: bool) -> dict[str, Any]:
    intent = _exact(value, {
        "schema", "intent_id", "kind", "tenant_commitment", "account_scope",
        "created_at_ms", "expires_at_ms", "authorization", "requested_controls",
        "market_evidence_sha256", "runtime_measurement_sha256", "order", "dry_run",
    }, "intent_shape_invalid")
    if intent["schema"] != INTENT_SCHEMA:
        raise ContractError("intent_schema_invalid")
    _hex(intent["intent_id"], "intent_id_invalid")
    _hex(intent["tenant_commitment"], "tenant_commitment_invalid")
    if intent["account_scope"] != "owner":
        raise ContractError("account_scope_invalid")
    created = _uint(intent["created_at_ms"], "intent_created_at_invalid")
    expires = _uint(intent["expires_at_ms"], "intent_expires_at_invalid")
    if (expires <= created or expires - created > MAX_INTENT_LIFETIME_MS
            or created > now_ms + MAX_CLOCK_SKEW_MS or expires < now_ms):
        raise ContractError("intent_time_invalid")
    authorization = _exact(intent["authorization"], {
        "active", "expires_at_ms", "event_sha256", "scope_sha256",
        "release_authority", "mutation_authority",
    }, "authorization_shape_invalid")
    if authorization["active"] is not True:
        raise ContractError("operator_authorization_inactive")
    lease_expires = _uint(authorization["expires_at_ms"], "authorization_expiry_invalid")
    if lease_expires < expires:
        raise ContractError("operator_authorization_expires_before_intent")
    _hex(authorization["event_sha256"], "authorization_event_invalid")
    _hex(authorization["scope_sha256"], "authorization_scope_invalid")
    if authorization["release_authority"] is not False or authorization["mutation_authority"] is not False:
        raise ContractError("operator_lease_claims_forbidden_authority")
    _hex(intent["market_evidence_sha256"], "market_evidence_invalid")
    _hex(intent["runtime_measurement_sha256"], "runtime_measurement_invalid")
    kind = intent["kind"]
    dry_run = intent["dry_run"]
    if type(dry_run) is not bool or kind not in {PROBE_KIND, ORDER_KIND}:
        raise ContractError("intent_kind_or_mode_invalid")
    if kind == PROBE_KIND:
        if dry_run is not True or intent["order"] is not None:
            raise ContractError("probe_must_be_non_mutating")
        validate_controls(intent["requested_controls"], live=False)
    else:
        if dry_run is True:
            raise ContractError("order_dry_run_kind_invalid")
        if live_release is not True:
            raise ContractError("live_execution_release_held")
        validate_controls(intent["requested_controls"], live=True)
        validate_order(intent["order"], max_order_usd=max_order_usd)
    canonical_bytes(intent)
    return intent


def validate_stage(value: Any, *, schema: str, payload_key: str,
                   prior_digest: str | None = None) -> dict[str, Any]:
    stage = _exact(value, {
        "schema", "stage_id", "intent_id", "prior_sha256", payload_key,
        "authority_id", "key_version", "signed_at_ms", "signature",
    }, "stage_shape_invalid")
    if stage["schema"] != schema:
        raise ContractError("stage_schema_invalid")
    _hex(stage["stage_id"], "stage_id_invalid")
    _hex(stage["intent_id"], "stage_intent_id_invalid")
    actual_prior = _hex(stage["prior_sha256"], "stage_prior_digest_invalid")
    if prior_digest is not None and actual_prior != prior_digest:
        raise ContractError("stage_prior_join_invalid")
    _opaque(stage["authority_id"], "stage_authority_invalid")
    if not isinstance(stage["key_version"], str) or not stage["key_version"].endswith("/cryptoKeyVersions/1"):
        raise ContractError("stage_key_version_invalid")
    _uint(stage["signed_at_ms"], "stage_signed_at_invalid")
    if not isinstance(stage["signature"], str) or not 40 <= len(stage["signature"]) <= 1024:
        raise ContractError("stage_signature_invalid")
    canonical_bytes(stage)
    return stage


def unsigned_stage(stage: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(stage)
    result.pop("signature", None)
    return result


__all__ = [
    "ContractError", "DISPATCH_SCHEMA", "EXECUTOR_SCHEMA", "INTENT_SCHEMA",
    "MAX_MESSAGE_BYTES", "ORDER_KIND", "PROBE_KIND", "RECEIPT_SCHEMA",
    "REVIEW_SCHEMA", "canonical_bytes", "digest", "unsigned_stage",
    "validate_controls", "validate_intent", "validate_order", "validate_stage",
]
