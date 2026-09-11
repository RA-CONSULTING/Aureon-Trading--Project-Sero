"""Read-only executor isolation receipt for trading release gates.

This receipt reports the terminal action path and kill-switch state. It never
submits, publishes, delegates, cancels, opens, closes, or modifies an order.
"""

from __future__ import annotations

import hashlib
import json
import math
import time
from datetime import UTC, datetime
from typing import Any, Mapping


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _json_digest(value: Any) -> str:
    body = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(body).hexdigest()


def _text(value: Any, default: str = "unavailable") -> str:
    text = str(value or "").strip()
    return text[:160] if text else default


def _unique_text(values: list[Any]) -> list[str]:
    out: list[str] = []
    for value in values:
        text = _text(value, "")
        if text and text not in out:
            out.append(text)
    return out


def _number(value: Any) -> float | None:
    if type(value) not in (int, float):
        return None
    try:
        number = float(value)
        return number if math.isfinite(number) and number >= 0 else None
    except OverflowError:
        return None


def _count(value: Any) -> int | None:
    return value if type(value) is int and value >= 0 else None


def _flag(value: Any) -> bool | None:
    return value if type(value) is bool else None


def terminal_source_observation(terminal: Mapping[str, Any], now: float) -> dict[str, Any]:
    """A new HTTP observation cannot refresh an old or missing completed tick."""
    source = terminal.get("last_tick_completed_at")
    timestamp: float | None = None
    if isinstance(source, str):
        try:
            # The producer uses local naive datetimes; preserve that timezone.
            timestamp = datetime.fromisoformat(source.replace("Z", "+00:00")).timestamp()
        except (ValueError, OverflowError, OSError):
            pass
    watchdog = _mapping(terminal.get("runtime_watchdog"))
    reported_limit = _number(watchdog.get("tick_stale_after_sec"))
    max_age = min(reported_limit, 300.0) if reported_limit else 45.0
    wall_age = now - timestamp if timestamp is not None else None
    reported_age = _number(terminal.get("last_tick_age_sec"))
    age = max(0.0, wall_age, reported_age or 0.0) if wall_age is not None else None
    current = (
        age is not None and wall_age is not None and age <= max_age and wall_age >= -5.0
        and terminal.get("ok") is True and terminal.get("stale") is False
        and terminal.get("booting") is not True and terminal.get("duplicate_runtime") is not True
        and watchdog.get("tick_stale") is not True and watchdog.get("tick_long_running") is not True
        and watchdog.get("status_file_fresh") is not False
    )
    return {"source_timestamp": source if isinstance(source, str) else None,
            "source_age_sec": age, "source_max_age_sec": max_age, "source_current": current}


def build_executor_isolation_receipt(
    *,
    terminal_state: Mapping[str, Any] | None = None,
    now: float | None = None,
) -> dict[str, Any]:
    if terminal_state is None:
        from aureon.operator.legacy_runtime_api import _status_handlers

        read_status, _flight, _env = _status_handlers()
        terminal_state = _mapping(read_status())
    observed_at = time.time() if now is None else float(now)
    terminal = dict(_mapping(terminal_state))
    plan = _mapping(terminal.get("exchange_action_plan"))
    latest = _mapping(plan.get("latest_execution"))
    plan_clearances = _unique_text(_list(plan.get("runtime_clearances")))
    latest_clearances = _unique_text(_list(latest.get("runtime_clearances")) + _list(latest.get("guards")) + _list(latest.get("blockers")))
    blockers = _unique_text(plan_clearances + latest_clearances)
    source = terminal_source_observation(terminal, observed_at)
    real_orders_disabled = _flag(plan.get("real_orders_disabled"))
    exchange_mutations_disabled = _flag(plan.get("exchange_mutations_disabled"))
    order_intent_publish_enabled = _flag(plan.get("order_intent_publish_enabled"))
    executor_enabled = _flag(latest.get("executor_enabled"))
    kill_switch_engaged = (
        real_orders_disabled is True and exchange_mutations_disabled is True
        and order_intent_publish_enabled is False
    ) if None not in (real_orders_disabled, exchange_mutations_disabled, order_intent_publish_enabled) else None
    attempted_count = _count(latest.get("attempted_count"))
    submitted_count = _count(latest.get("submitted_count"))
    delegated_count = _count(latest.get("delegated_count"))
    held_order_path_observed = (
        source["source_current"] is True
        and latest.get("trade_path_state") in {"runtime_clearance_hold", "runtime_clearance_pending"}
        and submitted_count == 0 and delegated_count == 0
    )
    # An idle/held order path is not a dry-run test, and enabled flags are not
    # evidence of an isolated process, independent custody or enforced budgets.
    dry_run_order_path_proof = False
    production_executor_ready = False
    if source["source_current"] is not True:
        blockers.append("current_completed_runtime_tick_missing")
    if None in (real_orders_disabled, exchange_mutations_disabled, order_intent_publish_enabled, executor_enabled):
        blockers.append("executor_control_state_incomplete")
    blockers = _unique_text(blockers + [
        "executor_process_isolation_attestation_missing",
        "executor_independent_key_custody_attestation_missing",
        "executor_kill_switch_and_budget_test_receipt_missing",
        "executor_dry_run_test_receipt_missing",
    ])
    evidence = {
        "terminal_ok": terminal.get("ok") is True,
        "terminal_stale": terminal.get("stale") is True,
        "data_ready": terminal.get("data_ready") is True,
        "trading_ready": terminal.get("trading_ready") is True,
        "action_mode": _text(plan.get("mode"), "unknown"),
        "trade_path_state": _text(plan.get("trade_path_state"), "unknown"),
        "latest_execution_trade_path_state": _text(latest.get("trade_path_state"), "unknown"),
        "executor_enabled": executor_enabled,
        "real_orders_disabled": real_orders_disabled,
        "exchange_mutations_disabled": exchange_mutations_disabled,
        "order_intent_publish_enabled": order_intent_publish_enabled,
        "kill_switch_engaged": kill_switch_engaged,
        "dry_run_order_path_proof": dry_run_order_path_proof,
        "held_order_path_observed": held_order_path_observed,
        "kill_switch_currently_observed": source["source_current"] is True and kill_switch_engaged is True,
        "control_evidence_scope": "reported_runtime_flags",
        "process_isolation_verified": False,
        **source,
        "attempted_count": attempted_count,
        "submitted_count": submitted_count,
        "delegated_count": delegated_count,
        "held_count": _count(latest.get("held_count")),
        "blocked_count": _count(latest.get("blocked_count")),
        "route_timeout_sec": _number(latest.get("route_timeout_sec")),
    }
    return {
        "schema": "aureon.operator.executor-isolation.v1",
        "generated_values": False,
        "observed_at": observed_at,
        "observed_at_iso": datetime.fromtimestamp(observed_at, UTC).isoformat().replace("+00:00", "Z"),
        "truth_status": "real_derived" if terminal else "unavailable",
        "read_state": "observed" if source["source_current"] else "recorded" if terminal else "unavailable",
        "available": bool(terminal),
        "production_executor_ready": production_executor_ready,
        "kill_switch_engaged": kill_switch_engaged,
        "provider_mutation_disabled": exchange_mutations_disabled,
        "order_intent_publish_enabled": order_intent_publish_enabled,
        "executor_enabled": executor_enabled,
        "dry_run_order_path_proof": dry_run_order_path_proof,
        "held_order_path_observed": held_order_path_observed,
        "source_current": source["source_current"],
        "process_isolation_verified": False,
        "blockers": blockers,
        "evidence": evidence,
        "production_ready": False,
        "release_authority": False,
        "mutation_authority": False,
        "digest_sha256": _json_digest({"evidence": evidence, "blockers": blockers, "production_executor_ready": production_executor_ready}),
        "digest_scope": "operator_executor_isolation",
    }


__all__ = ["build_executor_isolation_receipt", "terminal_source_observation"]
