"""Status rendering is isolated from credential-loading imports and all provider I/O."""
import ast
from copy import deepcopy
import math
from pathlib import Path
from types import MethodType, SimpleNamespace
from typing import List
from unittest.mock import Mock

import pytest

ROOT = Path(__file__).resolve().parents[1]


def method_from_source(filename, class_name, method_name, **extra_globals):
    tree = ast.parse((ROOT / "aureon" / "exchanges" / filename).read_text(encoding="utf-8"))
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == class_name)
    method = next(node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == method_name)
    module = ast.Module(body=[method], type_ignores=[])
    ast.fix_missing_locations(module)
    namespace = {"List": List, "math": math, "HAS_QUAD_GATES": True,
                 "time": SimpleNamespace(time=lambda: 1_800_001_000.0)}
    namespace.update(extra_globals)
    exec(compile(module, filename, "exec"), namespace)
    return namespace[method_name]


def capital_fixture():
    observation = {"status": "observed", "generated_values": False, "source": "capital:GET /accounts",
                   "source_timestamp": 1_800_000_000.5, "received_at": 1_800_000_001.5,
                   "max_age_seconds": 300, "rows": [{"currency": "GBP", "balance": 12.5, "available": 0.0}]}
    no_read = lambda: Mock(side_effect=AssertionError("status rendering initiated a read"))
    client = SimpleNamespace(last_ui_accounts_observation=observation, get_accounts=no_read(), get_account_balance=no_read())
    capital = SimpleNamespace(client=client, _latest_status_lines=["previous diagnostics"],
        _capital_snapshot_cache={"equity_gbp": 12.5, "source_timestamp": 1_800_000_000.5, "received_at": 1_800_000_001.5},
        _capital_snapshot_error="previous provider failure", get_capital_snapshot=no_read(),
        _build_capital_risk_envelope=no_read(), _compute_growth_metrics=no_read(), _compute_self_confidence=no_read())
    capital.status_lines = MethodType(method_from_source("capital_cfd_trader.py", "CapitalCFDTrader", "status_lines"), capital)
    return capital


def test_cached_status_preserves_native_zero_currency_and_original_old_receipt_without_calls():
    capital = capital_fixture()
    observation = capital.client.last_ui_accounts_observation
    old_observation, old_snapshot, old_lines = deepcopy(observation), deepcopy(capital._capital_snapshot_cache), list(capital._latest_status_lines)
    first = capital.status_lines(cached_only=True)
    second = capital.status_lines(cached_only=True)
    assert first == second
    assert "balance=12.5 GBP | available=0.0 GBP" in "\n".join(first)
    assert "source_timestamp=1800000000.5" in "\n".join(first)
    assert "received_at=1800000001.5" in "\n".join(first)
    assert "current freshness not evaluated" in "\n".join(first)
    assert capital.client.last_ui_accounts_observation is observation
    assert observation == old_observation
    assert capital._capital_snapshot_cache == old_snapshot
    assert capital._latest_status_lines == old_lines
    assert capital._capital_snapshot_error == "previous provider failure"
    for target in [capital.client.get_accounts, capital.client.get_account_balance, capital.get_capital_snapshot,
                   capital._build_capital_risk_envelope, capital._compute_growth_metrics, capital._compute_self_confidence]:
        target.assert_not_called()


def test_missing_cached_account_receipt_is_unavailable_without_zero_defaults():
    capital = capital_fixture()
    capital.client = None
    capital._latest_status_lines = []
    lines = capital.status_lines(cached_only=True)
    assert "Cached native account receipt unavailable" in "\n".join(lines)
    assert "Equity=0" not in "\n".join(lines)
    capital.get_capital_snapshot.assert_not_called()


def test_default_status_path_still_uses_existing_snapshot_refresh():
    capital = capital_fixture()
    capital.stats = {"winning_trades": 0, "losing_trades": 0, "trades_closed": 0, "total_pnl_gbp": 0}
    with pytest.raises(AssertionError, match="status rendering initiated a read"):
        capital.status_lines()
    capital.get_capital_snapshot.assert_called_once_with()


@pytest.mark.parametrize("method_name", ["get_status_lines", "print_status"])
def test_unified_status_render_selects_cached_capital_branch(method_name):
    capital = capital_fixture()
    old_observation = deepcopy(capital.client.last_ui_accounts_observation)
    old_snapshot = deepcopy(capital._capital_snapshot_cache)
    original = capital.status_lines
    capital.status_lines = Mock(wraps=original)
    trader = SimpleNamespace(start_time=1_800_000_000.0, _central_beat_feed={},
        _build_preflight_report=lambda: {}, _load_kraken_spot_fast_profit_state=lambda: {}, _api_governor_snapshot=lambda: {},
        alpaca=None, alpaca_error="unavailable", binance=None, binance_error="unavailable",
        kraken_ready=False, kraken=None, kraken_error="unavailable", capital_ready=True, capital=capital)
    printed = Mock()
    render = MethodType(method_from_source("unified_market_trader.py", "UnifiedMarketTrader", method_name,
                                           _safe_print=printed), trader)
    result = render()
    lines = result if method_name == "get_status_lines" else [str(call.args[0]) for call in printed.call_args_list if call.args]
    capital.status_lines.assert_called_once_with(cached_only=True)
    assert any("Cached account:" in line for line in lines)
    capital.client.get_accounts.assert_not_called()
    capital.get_capital_snapshot.assert_not_called()
    assert capital.client.last_ui_accounts_observation == old_observation
    assert capital._capital_snapshot_cache == old_snapshot


@pytest.mark.parametrize("enabled,expected_error", [(True, ""), (False, "provider configuration unavailable")])
def test_unified_startup_uses_cached_diagnostics_and_preserves_readiness_and_retry_guard(enabled, expected_error):
    capital = capital_fixture()
    capital.enabled = enabled
    capital.init_error = "provider configuration unavailable"
    capital.status_lines = Mock(wraps=capital.status_lines)
    old_observation = deepcopy(capital.client.last_ui_accounts_observation)
    old_snapshot = deepcopy(capital._capital_snapshot_cache)
    trader = SimpleNamespace(capital=capital, _last_capital_startup_attempt=0.0,
                             capital_ready=False, capital_error="")
    startup = MethodType(method_from_source("unified_market_trader.py", "UnifiedMarketTrader", "_startup_capital",
                                            EXCHANGE_REINIT_INTERVAL_SEC=60, logger=Mock()), trader)
    startup()
    capital.status_lines.assert_called_once_with(cached_only=True)
    assert trader.capital_ready is enabled
    assert trader.capital_error == expected_error
    assert trader._last_capital_startup_attempt == 1_800_001_000.0
    startup()
    capital.status_lines.assert_called_once_with(cached_only=True)
    assert capital.client.last_ui_accounts_observation == old_observation
    assert capital._capital_snapshot_cache == old_snapshot
    for target in [capital.client.get_accounts, capital.client.get_account_balance, capital.get_capital_snapshot,
                   capital._build_capital_risk_envelope, capital._compute_growth_metrics, capital._compute_self_confidence]:
        target.assert_not_called()
