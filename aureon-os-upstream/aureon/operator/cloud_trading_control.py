"""Read-only cloud trading control and authority-chain status for the operator."""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import time
from pathlib import Path
from typing import Any, Mapping

SCHEMA = "aureon.operator.cloud-trading-control.v1"
READBACK_SCHEMA = "aureon.cloud-trade-terminal-readback.v1"
DEFAULT_READBACK = Path("/srv/aureon/cache/trading-control/latest-terminal-receipt.json")
CONTROL_IDS = (
    "AUREON_DEPLOYMENT_HOLD",
    "AUREON_DISABLE_REAL_ORDERS",
    "AUREON_DISABLE_EXCHANGE_MUTATIONS",
    "AUREON_LIVE_TRADING",
    "AUREON_ORDER_INTENT_PUBLISH",
    "AUREON_UNIFIED_ORDER_EXECUTOR",
)
LIVE_CONTROLS = {
    "AUREON_DEPLOYMENT_HOLD": False,
    "AUREON_DISABLE_REAL_ORDERS": False,
    "AUREON_DISABLE_EXCHANGE_MUTATIONS": False,
    "AUREON_LIVE_TRADING": True,
    "AUREON_ORDER_INTENT_PUBLISH": True,
    "AUREON_UNIFIED_ORDER_EXECUTOR": True,
}
_HEX64 = re.compile(r"[0-9a-f]{64}")
_TRUTHY = {"1", "true", "yes", "on"}


def _flag(environ: Mapping[str, str], key: str) -> bool:
    return str(environ.get(key) or "").strip().lower() in _TRUTHY


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode()).hexdigest()


def _read(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    if not path.is_absolute():
        return None, "terminal_readback_path_invalid"
    try:
        resolved = path.resolve(strict=True)
        stat = resolved.stat()
    except OSError:
        return None, "terminal_readback_missing"
    if path.is_symlink() or not resolved.is_file() or not 0 < stat.st_size <= 262_144:
        return None, "terminal_readback_invalid"
    try:
        value = json.loads(resolved.read_bytes())
    except (OSError, ValueError, TypeError, UnicodeError):
        return None, "terminal_readback_invalid"
    if not isinstance(value, dict) or value.get("schema") != READBACK_SCHEMA:
        return None, "terminal_readback_invalid"
    return value, None


def _controls() -> tuple[dict[str, bool], dict[str, bool]]:
    from aureon.operator import feature_switchboard

    views = {row["id"]: row for group in feature_switchboard.grouped_view() for row in group["flags"]}
    requested = {
        key: bool(views[key]["stored"] if views[key]["stored"] is not None else views[key]["enabled"])
        for key in CONTROL_IDS
    }
    effective = {key: bool(views[key]["enabled"]) for key in CONTROL_IDS}
    return requested, effective


def _authorization() -> Mapping[str, Any]:
    from aureon.operator.authorization_lease import build_operator_authorization_receipt

    return build_operator_authorization_receipt()


def build_cloud_trading_control_receipt(
    *,
    environ: Mapping[str, str] | None = None,
    now: float | None = None,
    readback_path: Path | None = None,
) -> dict[str, Any]:
    env = os.environ if environ is None else environ
    current = time.time() if now is None else float(now)
    if not math.isfinite(current) or current <= 0:
        raise ValueError("cloud_trading_control_time_invalid")
    configured_path = str(env.get("AUREON_CLOUD_TRADE_READBACK_PATH") or "").strip()
    path = Path(configured_path) if configured_path else (readback_path or DEFAULT_READBACK)
    readback, read_error = _read(path)
    receipt = readback.get("receipt") if isinstance(readback, Mapping) else None
    received_at = readback.get("received_at") if isinstance(readback, Mapping) else None
    age = None
    if isinstance(received_at, (int, float)) and not isinstance(received_at, bool):
        age = current - float(received_at)
    receipt_valid = (
        isinstance(receipt, Mapping)
        and receipt.get("chain_verified") is True
        and receipt.get("dry_run") is True
        and receipt.get("provider_mutation_attempted") is False
        and receipt.get("orders_attempted") == 0
        and receipt.get("orders_submitted") == 0
        and isinstance(receipt.get("receipt_sha256"), str)
        and _HEX64.fullmatch(receipt["receipt_sha256"]) is not None
        and isinstance(receipt.get("authority_ids"), Mapping)
        and len(set(receipt["authority_ids"].values())) == 4
        and isinstance(receipt.get("key_versions"), Mapping)
        and len(set(receipt["key_versions"].values())) == 4
    )
    probe_current = bool(receipt_valid and age is not None and -5 <= age <= 300)
    requested, effective = _controls()
    authorization = _authorization()
    lease_active = authorization.get("active") is True
    desired_live_state = requested == LIVE_CONTROLS
    release_receipt = str(env.get("AUREON_CLOUD_TRADE_RELEASE_RECEIPT_SHA256") or "")
    release_receipt_pinned = _HEX64.fullmatch(release_receipt) is not None
    provider_readback = str(env.get("AUREON_CLOUD_TRADE_PROVIDER_READBACK_SHA256") or "")
    provider_readback_pinned = _HEX64.fullmatch(provider_readback) is not None
    result_binding = str(env.get("AUREON_CLOUD_TRADE_LIVE_RESULT_BINDING_SHA256") or "")
    live_result_binding_pinned = _HEX64.fullmatch(result_binding) is not None
    capabilities = {
        "signed_authority_chain": probe_current,
        "distinct_runtime_identities": receipt_valid,
        "isolated_executor_probe": probe_current,
        "no_mutation_probe": probe_current,
        "live_execution_release": _flag(env, "AUREON_LIVE_EXECUTION_RELEASE"),
        "durable_budget_ledger": _flag(env, "AUREON_DURABLE_BUDGET_LEDGER"),
        "order_adapter_ready": _flag(env, "AUREON_ORDER_ADAPTER_READY"),
        "release_receipt_pinned": release_receipt_pinned,
        "all_four_provider_readback_pinned": provider_readback_pinned,
        "live_result_binding_pinned": live_result_binding_pinned,
    }
    blockers: list[str] = []
    if not lease_active:
        blockers.append("operator_authorization_lease_inactive")
    if not desired_live_state:
        blockers.append("operator_live_control_set_not_fully_requested")
    if not probe_current:
        blockers.append(read_error or "current_signed_authority_probe_missing")
    for key, ready in (
        ("live_execution_release_held", capabilities["live_execution_release"]),
        ("durable_budget_ledger_unconfigured", capabilities["durable_budget_ledger"]),
        ("live_order_adapter_unavailable", capabilities["order_adapter_ready"]),
        ("production_release_receipt_missing", capabilities["release_receipt_pinned"]),
        ("all_four_provider_readback_receipt_missing", capabilities["all_four_provider_readback_pinned"]),
        ("live_order_result_binding_receipt_missing", capabilities["live_result_binding_pinned"]),
    ):
        if not ready:
            blockers.append(key)
    # This observer never applies configuration.  The governed controller that
    # atomically changes the publisher/executor state is not yet installed, so
    # even a complete evidence set remains non-authoritative here.
    blockers.append("governed_live_handoff_controller_not_integrated")
    handoff_ready = False
    probe_summary = None
    if receipt_valid and isinstance(receipt, Mapping):
        probe_summary = {
            "intent_id": receipt.get("intent_id"),
            "receipt_sha256": receipt.get("receipt_sha256"),
            "received_at": received_at,
            "age_seconds": age,
            "current": probe_current,
            "chain_verified": True,
            "authority_ids": dict(receipt["authority_ids"]),
            "key_versions": dict(receipt["key_versions"]),
            "provider_mutation_attempted": False,
            "orders_attempted": 0,
            "orders_submitted": 0,
        }
    body = {
        "requested_controls": requested,
        "effective_controls": effective,
        "desired_live_state": desired_live_state,
        "lease_active": lease_active,
        "authorization_event_sha256": authorization.get("ledger_event_sha256"),
        "authorization_expires_at_iso": authorization.get("expires_at_iso"),
        "capabilities": capabilities,
        "last_probe": probe_summary,
        "blockers": blockers,
        "handoff_ready": handoff_ready,
    }
    return {
        "schema": SCHEMA,
        "observed_at": current,
        "truth_status": "real_derived" if receipt_valid else "unavailable",
        "read_state": "observed" if probe_current else "recorded" if receipt_valid else "unavailable",
        "operator_can_request_controls": True,
        "operator_can_apply_live": handoff_ready,
        "requested_controls": requested,
        "effective_controls": effective,
        "desired_live_state": desired_live_state,
        "authorization": {
            "active": lease_active,
            "state": authorization.get("state"),
            "expires_at_iso": authorization.get("expires_at_iso"),
            "ledger_event_sha256": authorization.get("ledger_event_sha256"),
            "release_authority": False,
            "mutation_authority": False,
        },
        "capabilities": capabilities,
        "last_probe": probe_summary,
        "blockers": blockers,
        "production_ready": handoff_ready,
        "release_authority": False,
        "mutation_authority": False,
        "digest_sha256": _digest(body),
        "digest_scope": "operator_cloud_trading_control",
    }


__all__ = ["build_cloud_trading_control_receipt"]
