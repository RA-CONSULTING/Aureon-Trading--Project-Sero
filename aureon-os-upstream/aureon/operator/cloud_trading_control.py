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

from aureon.operator.cloud_trading_release import (
    LIVE_CONTROLS,
    probe_runtime_measurement_sha256,
    read_controller_release,
)

SCHEMA = "aureon.operator.cloud-trading-control.v1"
READBACK_SCHEMA = "aureon.cloud-trade-terminal-readback.v1"
DEFAULT_READBACK = Path("/srv/aureon/cache/trading-control/latest-terminal-receipt.json")
BRIDGE_STATUS_SCHEMA = "aureon.cloud-order-intent-bridge-status.v1"
DEFAULT_BRIDGE_STATUS = Path("/srv/aureon/cache/trading-control/latest-order-intent-bridge.json")
BRIDGE_STATUS_PATH_ENV = "AUREON_CLOUD_TRADE_BRIDGE_STATUS_PATH"
CONTROL_IDS = (
    "AUREON_DEPLOYMENT_HOLD",
    "AUREON_DISABLE_REAL_ORDERS",
    "AUREON_DISABLE_EXCHANGE_MUTATIONS",
    "AUREON_LIVE_TRADING",
    "AUREON_ORDER_INTENT_PUBLISH",
    "AUREON_UNIFIED_ORDER_EXECUTOR",
)
_HEX64 = re.compile(r"[0-9a-f]{64}")
_REVISION = re.compile(r"[0-9a-f]{40,64}")
_MESSAGE_ID = re.compile(r"[0-9]{1,64}")
_BRIDGE_SYMBOL = re.compile(r"[A-Z0-9][A-Z0-9./_-]{1,31}")
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


def _read_intent_bridge(
    path: Path,
    *,
    now: float,
    expected_revision: str,
) -> tuple[dict[str, Any] | None, str | None]:
    if not path.is_absolute():
        return None, "order_intent_bridge_status_path_invalid"
    try:
        resolved = path.resolve(strict=True)
        stat = resolved.stat()
    except OSError:
        return None, "order_intent_bridge_status_missing"
    if path.is_symlink() or not resolved.is_file() or not 0 < stat.st_size <= 262_144:
        return None, "order_intent_bridge_status_invalid"
    try:
        value = json.loads(resolved.read_bytes())
    except (OSError, ValueError, TypeError, UnicodeError):
        return None, "order_intent_bridge_status_invalid"
    fields = {
        "schema", "observed_at", "revision", "state", "operational",
        "candidate_ready", "blockers", "source", "controller_release",
        "last_publish", "release_authority", "mutation_authority",
    }
    if (
        not isinstance(value, dict)
        or set(value) != fields
        or value.get("schema") != BRIDGE_STATUS_SCHEMA
        or not _REVISION.fullmatch(str(value.get("revision") or ""))
        or value.get("revision") != expected_revision
        or value.get("state") not in {"blocked", "idle", "published", "publish_outcome_unknown"}
        or type(value.get("operational")) is not bool
        or type(value.get("candidate_ready")) is not bool
        or not isinstance(value.get("blockers"), list)
        or any(not isinstance(item, str) or not item or len(item) > 128 for item in value["blockers"])
        or isinstance(value.get("observed_at"), bool)
        or not isinstance(value.get("observed_at"), (int, float))
        or not math.isfinite(float(value["observed_at"]))
        or not -5 <= now - float(value["observed_at"]) <= 45
        or type(value.get("release_authority")) is not bool
        or value.get("mutation_authority") is not False
    ):
        return None, "order_intent_bridge_status_invalid"
    source = value.get("source")
    release = value.get("controller_release")
    last_publish = value.get("last_publish")
    if source is not None and (
        not isinstance(source, Mapping)
        or set(source) != {"runtime_status_sha256", "generated_at_ms", "age_ms"}
        or not _HEX64.fullmatch(str(source.get("runtime_status_sha256") or ""))
        or type(source.get("generated_at_ms")) is not int
        or type(source.get("age_ms")) is not int
        or abs(
            (int(float(value["observed_at"]) * 1000) - source["generated_at_ms"])
            - source["age_ms"]
        ) > 2
    ):
        return None, "order_intent_bridge_status_invalid"
    if release is not None and (
        not isinstance(release, Mapping)
        or set(release) != {
            "state", "generation", "request_id", "source_revision",
            "authorization_event_sha256", "authorization_expires_at_ms",
        }
        or release.get("state") != "active"
        or release.get("source_revision") != expected_revision
        or type(release.get("generation")) is not int
        or release["generation"] < 1
        or not _HEX64.fullmatch(str(release.get("request_id") or ""))
        or not _HEX64.fullmatch(str(release.get("authorization_event_sha256") or ""))
        or type(release.get("authorization_expires_at_ms")) is not int
        or release["authorization_expires_at_ms"] <= int(float(value["observed_at"]) * 1000)
    ):
        return None, "order_intent_bridge_status_invalid"
    if last_publish is not None and (
        not isinstance(last_publish, Mapping)
        or set(last_publish) != {
            "topic", "intent_id", "client_order_id", "intent_sha256",
            "market_evidence_sha256", "venue", "symbol", "side",
            "quote_value_usd", "pubsub_message_id", "published_at_ms",
        }
        or last_publish.get("topic") != "projects/aureon-trading/topics/aureon-trade-intents-v1"
        or any(not _HEX64.fullmatch(str(last_publish.get(key) or "")) for key in (
            "intent_id", "client_order_id", "intent_sha256", "market_evidence_sha256",
        ))
        or last_publish.get("venue") not in {"alpaca", "binance", "capital", "kraken"}
        or not _BRIDGE_SYMBOL.fullmatch(str(last_publish.get("symbol") or ""))
        or last_publish.get("side") not in {"BUY", "SELL"}
        or isinstance(last_publish.get("quote_value_usd"), bool)
        or not isinstance(last_publish.get("quote_value_usd"), (int, float))
        or not math.isfinite(float(last_publish["quote_value_usd"]))
        or not 0 < float(last_publish["quote_value_usd"]) <= 5
        or not _MESSAGE_ID.fullmatch(str(last_publish.get("pubsub_message_id") or ""))
        or type(last_publish.get("published_at_ms")) is not int
        or not 0 <= int(float(value["observed_at"]) * 1000) - last_publish["published_at_ms"] <= 86_400_000
    ):
        return None, "order_intent_bridge_status_invalid"
    if (
        (value["release_authority"] != (release is not None))
        or (value["operational"] and (source is None or release is None or value["release_authority"] is not True))
        or (value["state"] == "published" and (
            value["operational"] is not True
            or value["candidate_ready"] is not True
            or value["blockers"] != []
            or last_publish is None
        ))
        or (value["state"] != "published" and last_publish is not None)
    ):
        return None, "order_intent_bridge_status_invalid"
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
    bridge_status_path: Path | None = None,
) -> dict[str, Any]:
    env = os.environ if environ is None else environ
    current = time.time() if now is None else float(now)
    if not math.isfinite(current) or current <= 0:
        raise ValueError("cloud_trading_control_time_invalid")
    expected_revision = str(env.get("AUREON_REVISION") or env.get("AUREON_OPERATOR_REVISION") or "")
    expected_probe_measurement = (
        probe_runtime_measurement_sha256(expected_revision)
        if _REVISION.fullmatch(expected_revision) else None
    )
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
        and receipt.get("source_revision") == expected_revision
        and receipt.get("runtime_measurement_sha256") == expected_probe_measurement
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
    executor_capabilities = receipt.get("executor_capabilities") if isinstance(receipt, Mapping) else None
    provider_readback = receipt.get("provider_readback") if isinstance(receipt, Mapping) else None
    provider_readback_pinned = bool(
        receipt_valid and isinstance(provider_readback, Mapping)
        and provider_readback.get("provider_count") == 4
        and provider_readback.get("all_authenticated") is True
        and provider_readback.get("instrument_preflight_enforced") is True
        and isinstance(provider_readback.get("readback_sha256"), str)
        and _HEX64.fullmatch(provider_readback["readback_sha256"]) is not None
    )
    controller_release, controller_error = read_controller_release(environ=env)
    controller_integrated = controller_release is not None
    authorization_event = authorization.get("ledger_event_sha256")
    authorization_expires = authorization.get("expires_at")
    release_active = bool(
        controller_integrated
        and controller_release.get("state") == "active"
        and controller_release.get("requested_controls_sha256") == _digest(LIVE_CONTROLS)
        and controller_release.get("authorization_event_sha256") == authorization_event
        and isinstance(authorization_expires, (int, float))
        and not isinstance(authorization_expires, bool)
        and controller_release.get("authorization_expires_at_ms") == int(float(authorization_expires) * 1000)
        and controller_release.get("authorization_expires_at_ms", 0) > int(current * 1000)
        and controller_release.get("signed_at_ms", 0) <= int(current * 1000) + 5_000
        and controller_release.get("source_revision") == expected_revision
    )
    configured_bridge_path = str(env.get(BRIDGE_STATUS_PATH_ENV) or "").strip()
    bridge_path = (
        Path(configured_bridge_path)
        if configured_bridge_path
        else (bridge_status_path or DEFAULT_BRIDGE_STATUS)
    )
    intent_bridge, bridge_error = _read_intent_bridge(
        bridge_path,
        now=current,
        expected_revision=expected_revision,
    ) if _REVISION.fullmatch(expected_revision) else (None, "order_intent_bridge_revision_unconfigured")
    intent_bridge_operational = bool(
        isinstance(intent_bridge, Mapping)
        and intent_bridge.get("operational") is True
        and intent_bridge.get("release_authority") is True
        and intent_bridge.get("mutation_authority") is False
        and isinstance(intent_bridge.get("controller_release"), Mapping)
        and intent_bridge["controller_release"].get("authorization_event_sha256") == authorization_event
        and isinstance(authorization_expires, (int, float))
        and not isinstance(authorization_expires, bool)
        and intent_bridge["controller_release"].get("authorization_expires_at_ms") == int(float(authorization_expires) * 1000)
    )
    live_result_binding_ready = bool(
        isinstance(executor_capabilities, Mapping)
        and executor_capabilities.get("live_result_binding_ready") is True
    )
    instrument_preflight_ready = bool(
        isinstance(executor_capabilities, Mapping)
        and executor_capabilities.get("instrument_preflight_enforced") is True
        and isinstance(provider_readback, Mapping)
        and provider_readback.get("instrument_preflight_enforced") is True
    )
    capabilities = {
        "signed_authority_chain": probe_current,
        "distinct_runtime_identities": receipt_valid,
        "isolated_executor_probe": probe_current,
        "no_mutation_probe": probe_current,
        "live_execution_release": release_active,
        "durable_budget_ledger": bool(isinstance(executor_capabilities, Mapping) and executor_capabilities.get("durable_budget_ledger") is True),
        "order_adapter_ready": bool(isinstance(executor_capabilities, Mapping) and executor_capabilities.get("order_adapter_ready") is True),
        "release_receipt_pinned": controller_integrated,
        "all_four_provider_readback_pinned": provider_readback_pinned,
        "live_result_binding_pinned": live_result_binding_ready,
        "live_result_binding_ready": live_result_binding_ready,
        "instrument_preflight_enforced": instrument_preflight_ready,
        "controller_integrated": controller_integrated,
        "governed_order_intent_bridge": intent_bridge_operational,
    }
    blockers: list[str] = []
    if not lease_active:
        blockers.append("operator_authorization_lease_inactive")
    if not desired_live_state:
        blockers.append("operator_live_control_set_not_fully_requested")
    if not probe_current:
        blockers.append(read_error or "current_signed_authority_probe_missing")
    for key, ready in (
        ("durable_budget_ledger_unconfigured", capabilities["durable_budget_ledger"]),
        ("live_order_adapter_unavailable", capabilities["order_adapter_ready"]),
        ("all_four_provider_readback_receipt_missing", capabilities["all_four_provider_readback_pinned"]),
        ("live_order_result_binding_receipt_missing", capabilities["live_result_binding_pinned"]),
        ("provider_instrument_preflight_receipt_missing", capabilities["instrument_preflight_enforced"]),
        (controller_error or "governed_live_handoff_controller_not_integrated", capabilities["controller_integrated"]),
    ):
        if not ready:
            blockers.append(key)
    prerequisite_blockers = list(blockers)
    handoff_ready = not prerequisite_blockers
    if not release_active:
        blockers.append("live_execution_release_held")
    elif not intent_bridge_operational:
        bridge_blockers = intent_bridge.get("blockers") if isinstance(intent_bridge, Mapping) else None
        if isinstance(bridge_blockers, list) and bridge_blockers:
            blockers.extend(str(item) for item in bridge_blockers if str(item))
        else:
            blockers.append(bridge_error or "governed_order_intent_bridge_not_ready")
    production_ready = handoff_ready and release_active and intent_bridge_operational
    probe_summary = None
    if receipt_valid and isinstance(receipt, Mapping):
        probe_summary = {
            "intent_id": receipt.get("intent_id"),
            "receipt_sha256": receipt.get("receipt_sha256"),
            "source_revision": receipt.get("source_revision"),
            "runtime_measurement_sha256": receipt.get("runtime_measurement_sha256"),
            "received_at": received_at,
            "age_seconds": age,
            "current": probe_current,
            "chain_verified": True,
            "authority_ids": dict(receipt["authority_ids"]),
            "key_versions": dict(receipt["key_versions"]),
            "provider_mutation_attempted": False,
            "orders_attempted": 0,
            "orders_submitted": 0,
            "executor_capabilities": dict(executor_capabilities) if isinstance(executor_capabilities, Mapping) else None,
            "provider_readback": dict(provider_readback) if isinstance(provider_readback, Mapping) else None,
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
        "controller_release": controller_release,
        "intent_bridge": intent_bridge,
        "blockers": blockers,
        "handoff_ready": handoff_ready,
        "production_ready": production_ready,
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
            "release_authority": release_active,
            "mutation_authority": False,
        },
        "capabilities": capabilities,
        "last_probe": probe_summary,
        "controller_release": controller_release,
        "intent_bridge": intent_bridge,
        "blockers": blockers,
        "production_ready": production_ready,
        "release_authority": release_active,
        "mutation_authority": False,
        "digest_sha256": _digest(body),
        "digest_scope": "operator_cloud_trading_control",
    }


__all__ = ["build_cloud_trading_control_receipt"]
