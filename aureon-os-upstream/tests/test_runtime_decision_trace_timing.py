"""Exercise current orchestration source offline, without importing runtime boot code.

Only the three named methods are compiled from their AST. Every route, ledger,
thought publication and persistence dependency is replaced by an in-memory fake.
"""
from __future__ import annotations

import ast
import copy
import math
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List, Optional

import pytest

SOURCE = Path(__file__).resolve().parents[1] / "aureon/exchanges/unified_market_trader.py"


def exercise(result, *, return_at=112.0, raise_route=False):
    tree = ast.parse(SOURCE.read_text(encoding="utf-8-sig"))
    original = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "UnifiedMarketTrader")
    names = {"_execute_runtime_order_actions", "_submission_receipt_state", "_provider_order_id"}
    methods = [node for node in original.body if isinstance(node, ast.FunctionDef) and node.name in names]
    assert len(methods) == len(names)
    selected = ast.ClassDef(name="OfflineTrader", bases=[], keywords=[], body=methods, decorator_list=[])
    clock = SimpleNamespace(now=100.0)
    namespace = {
        "Any": Any, "Dict": Dict, "List": List, "Optional": Optional, "math": math, "datetime": datetime,
        "time": SimpleNamespace(time=lambda: clock.now),
        "ORDER_EXECUTOR_QUOTE_USD": 1.0, "KRAKEN_SPOT_QUOTE_USD": 1.0,
        "ORDER_EXECUTOR_ROUTE_TIMEOUT_SEC": 1.0, "ORDER_EXECUTOR_MAX_PER_TICK": 1,
        "ORDER_INTENT_MIN_CONFIDENCE": 0.5, "ORDER_EXECUTOR_SYMBOL_COOLDOWN_SEC": 0,
    }
    exec(compile(ast.fix_missing_locations(ast.Module(body=[selected], type_ignores=[])), str(SOURCE), "exec"), namespace)
    trader = namespace["OfflineTrader"]()
    trace = SimpleNamespace(t_exec_dispatched=None, t_exchange_ack=1.0, t_state_converged=1.0, stage_statuses={})
    route_calls = []
    trader._execution_memory = {}
    trader._execution_blockers = lambda *_: []
    trader._unified_executor_enabled = lambda: True
    trader._executor_route_snapshot = lambda: {}
    trader._order_lifecycle_snapshot = lambda: {}
    trader._order_lifecycle_enabled_now = lambda: False
    trader._order_route_key = lambda *_: "kraken:spot:BTCUSD:BUY"
    trader._decision_trace_for = lambda *_args, **_kwargs: trace
    trader._record_order_lifecycle = lambda *_args, **_kwargs: None
    trader._broker_identity_from_result = lambda *_: {}
    trader._publish_thought = lambda *_: None
    trader._persist_execution_summary = lambda *_: None
    trader._confirmed_fill_receipt = lambda *_: {"data_status": "no_data"}
    trader._governor = lambda: SimpleNamespace(record_error=lambda *_: None)

    def identify(_item):
        # Five seconds pass between the cycle timestamp and executor handoff.
        clock.now = 105.0
        return "candidate-fixture", "lifecycle-fixture"

    def route(*_args):
        route_calls.append(clock.now)
        # The provider result arrives seven seconds after dispatch.
        clock.now = return_at
        if raise_route:
            raise TimeoutError("offline fixture timeout")
        return copy.deepcopy(result)

    trader._candidate_lifecycle_identity = identify
    trader._run_executor_route_with_timeout = route
    payload = {
        "exchange_action_plan": {"order_intent_publish_enabled": True, "global_blockers": []},
        "shared_order_flow": {"active_order_flow": [{
            "symbol": "BTCUSD", "side": "BUY", "confidence": 0.9,
            "execution_routes": [{"venue": "kraken", "market_type": "spot", "symbol": "BTCUSD", "ready": True}],
        }]},
    }
    summary = trader._execute_runtime_order_actions(payload)
    assert route_calls == [105.0]
    return trace, summary


def acknowledged(**overrides):
    return {"ok": True, "submitted": True, "result": {
        "orderId": "provider-fixture-id", "status": "NEW", "generated_values": False,
    }, **overrides}


def test_acknowledgment_records_actual_result_observation_not_cycle_start():
    trace, summary = exercise(acknowledged())
    assert trace.t_exec_dispatched == 105.0
    assert trace.t_exchange_ack == 112.0
    assert trace.t_exchange_ack - trace.t_exec_dispatched == 7.0
    assert trace.stage_statuses["exchange_ack_clock"] == "local_route_result_observation"
    assert trace.stage_statuses["exchange_ack"] == "ok"
    assert trace.t_state_converged is None
    assert trace.stage_statuses["state_converged"] == "pending_reconciliation"
    assert summary["submitted_count"] == 1


@pytest.mark.parametrize("result", [
    {"ok": True, "submitted": True},
    {"ok": True, "submitted": True, "result": {"status": "NEW"}},
    {"ok": True, "submitted": True, "fast_profit_position": {"id": "local-position"}},
    acknowledged(submitted=False),
    acknowledged(result={"orderId": "provider-fixture-id", "status": "REJECTED"}),
    acknowledged(result={"orderId": "provider-fixture-id", "generated_values": True}),
    acknowledged(result={"orderId": "provider-fixture-id", "error": "denied"}),
    {"ok": False, "submitted": False, "reason": "execution_blocked"},
])
def test_generic_success_local_positions_or_rejected_receipts_do_not_create_acknowledgment(result):
    trace, _ = exercise(result)
    assert trace.t_exchange_ack is None
    assert trace.t_state_converged is None
    assert trace.stage_statuses["exchange_ack"] != "ok"


def test_timeout_does_not_create_acknowledgment_or_convergence():
    trace, _ = exercise({}, raise_route=True)
    assert trace.t_exec_dispatched == 105.0
    assert trace.t_exchange_ack is None
    assert trace.t_state_converged is None
    assert trace.stage_statuses["exchange_ack"] == "held"


@pytest.mark.parametrize("return_at", [104.0, float("inf"), float("nan")])
def test_invalid_or_backward_observation_clock_does_not_invent_a_timestamp(return_at):
    trace, _ = exercise(acknowledged(), return_at=return_at)
    assert trace.t_exchange_ack is None
    assert trace.t_state_converged is None
    assert trace.stage_statuses["exec_hold_reason"] == "execution_observation_clock_invalid"


def test_fill_claim_does_not_manufacture_independent_state_convergence():
    trace, _ = exercise(acknowledged(result={
        "orderId": "provider-fixture-id", "status": "FILLED", "generated_values": False,
        "fill_receipt_complete": True, "filled_qty": 1, "filled_avg_price": 10, "fee": 0,
    }, fill_confirmed=True))
    assert trace.t_exchange_ack == 112.0
    assert trace.t_state_converged is None
