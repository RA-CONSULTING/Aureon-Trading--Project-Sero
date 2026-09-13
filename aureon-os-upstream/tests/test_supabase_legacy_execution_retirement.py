"""Source contract for retired Supabase direct-order functions.

The Cloud executor is the sole order-submission owner. These legacy functions
must remain inert until they are replaced by the governed tenant-intent path.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROUTES = (
    "binance-algo-twap",
    "confirm-trade",
    "execute-trade",
    "execute-trade-user-alpaca",
    "execute-trade-user-capital",
    "force-validated-trade",
    "execute-trade-alpaca",
    "execute-trade-capital",
    "execute-trade-kraken",
    "oms-leaky-bucket",
    "poll-trade-confirmations",
)
FORBIDDEN_DIRECT_MUTATION_MARKERS = (
    "/api/v3/order",
    "/v2/orders",
    "/api/v1/positions",
    "/0/private/AddOrder",
    "/sapi/v1/algo/spot/newOrderTwap",
    "ALPACA_API_KEY",
    "BINANCE_API_SECRET",
    "CAPITAL_PASSWORD",
    "KRAKEN_API_SECRET",
    "decryptCredential",
)


def test_legacy_direct_execution_handlers_are_inert():
    for route in ROUTES:
        source = (ROOT / "supabase" / "functions" / route / "index.ts").read_text(encoding="utf-8")
        assert "LEGACY_DIRECT_EXECUTION_DISABLED" in source
        assert f"route: '{route}'" in source
        assert "status: 503" in source
        assert "governed_cloud_executor" in source
        assert "Deno.env.get" not in source
        assert "await req.json" not in source
        assert "../_shared/" not in source
        for marker in FORBIDDEN_DIRECT_MUTATION_MARKERS:
            assert marker not in source
