"""Caller contract for retired Supabase order-mutation functions."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND_CALLERS = (
    "frontend/src/core/forceValidatedTrade.ts",
    "frontend/src/components/IgnitionButton.tsx",
    "frontend/src/hooks/useTradeValidation.ts",
    "frontend/src/core/startupHarvester.ts",
    "frontend/src/core/unifiedOrchestrator.ts",
    "frontend/src/hooks/useAutonomousTrading.ts",
    "frontend/src/hooks/useOMSQueue.ts",
    "frontend/src/hooks/useQGITAAutoTrading.ts",
)
EDGE_ORCHESTRATORS = (
    "supabase/functions/automated-hunt-loop/index.ts",
    "supabase/functions/queen-hive-orchestrator/index.ts",
)
RETIRED_FUNCTIONS = (
    "force-validated-trade",
    "poll-trade-confirmations",
    "confirm-trade",
    "execute-trade",
    "oms-leaky-bucket",
    "binance-algo-twap",
)
UNAVAILABLE_CODE = "GOVERNED_ORDER_REVIEW_DISPATCH_CLIENT_UNAVAILABLE"


def _source(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_frontend_callers_do_not_invoke_retired_order_mutations() -> None:
    invocation = re.compile(
        r"functions\s*\.\s*invoke\s*\(\s*['\"](" + "|".join(map(re.escape, RETIRED_FUNCTIONS)) + r")[\"']"
    )
    for relative_path in FRONTEND_CALLERS:
        source = _source(relative_path)
        assert invocation.search(source) is None, relative_path


def test_frontend_actions_share_an_explicit_non_mutating_unavailable_contract() -> None:
    contract = _source("frontend/src/lib/tradingActionAvailability.ts")
    assert UNAVAILABLE_CODE in contract
    assert "tenant_runtime_authority: false" in contract
    assert "provider_mutation_attempted: false" in contract

    for relative_path in FRONTEND_CALLERS:
        source = _source(relative_path)
        assert "tradingActionAvailability" in source, relative_path


def test_tenant_edge_orchestrators_keep_analysis_but_cannot_route_orders() -> None:
    for relative_path in EDGE_ORCHESTRATORS:
        source = _source(relative_path)
        assert UNAVAILABLE_CODE in source, relative_path
        assert "providerMutationAttempted: false" in source, relative_path
        assert "tenantRuntimeAuthority: false" in source, relative_path
        for retired in ("oms-leaky-bucket", "binance-algo-twap"):
            assert retired not in source, (relative_path, retired)
        assert "/api/v3/order" not in source, relative_path


def test_oms_queue_remains_read_only_and_has_no_auto_processor() -> None:
    source = _source("frontend/src/hooks/useOMSQueue.ts")
    assert ".from('oms_order_queue')" in source
    assert ".select('*')" in source
    assert "setInterval(() => {\n      processQueue()" not in source
    assert "mutationActionsAvailable: false" in source
