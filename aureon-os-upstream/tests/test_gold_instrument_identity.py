import pytest

from aureon.autonomous.aureon_gold_capital_intelligence_company import (
    _extract_orderbook_evidence,
    _extract_shadow_focus_items,
    _gold_related_blob,
    _gold_shadow_context_relation,
)


@pytest.mark.parametrize("symbol", ["EGLDUSD", "EGLDUSDT", "SUPERGLD", "GOLDEN", "XAUFAKE"])
def test_substring_is_not_gold_evidence(symbol):
    assert not _gold_related_blob(symbol)
    assert _gold_shadow_context_relation(symbol, "binance", "gold strategy") != "gold_target_candidate"


@pytest.mark.parametrize("symbol", ["GOLD", "XAUUSD", "XAU/USD", "XAU_USD", "XAU-USD"])
def test_exact_capital_gold_instrument_can_be_a_candidate(symbol):
    assert _gold_related_blob(symbol)
    assert _gold_shadow_context_relation(symbol, "capital") == "gold_target_candidate"


@pytest.mark.parametrize("symbol", ["GLD", "GDX", "GDXJ", "IAU", "GC=F", "GCM2026"])
def test_related_market_does_not_become_direct_capital_target(symbol):
    assert _gold_related_blob(symbol)
    assert _gold_shadow_context_relation(symbol, "alpaca") == "gold_market_confirmation_context"


def test_equity_gold_symbol_and_strategy_prose_cannot_become_capital_target():
    assert _gold_shadow_context_relation("GOLD", "alpaca") == "gold_market_confirmation_context"
    assert _gold_shadow_context_relation("BTCUSD", "kraken", "GOLD XAUUSD strategy") != "gold_target_candidate"
    assert _gold_shadow_context_relation("GOLD") == "gold_market_confirmation_context"
    assert _gold_shadow_context_relation("G-O-L-D", "capital") != "gold_target_candidate"


def test_real_report_shape_keeps_egld_out_of_target_and_direct_pressure_counts():
    payload = {"shadows": [
        {"symbol": "EGLDUSD", "venue": "kraken", "side": "BUY", "confidence": 1.0,
         "route_signature": "gold_watch", "orderbook_pressure": {"available": True, "score": 0.9}},
        {"symbol": "GOLD", "venue": "capital", "side": "BUY",
         "orderbook_pressure": {"available": False, "score": 0.0}},
    ]}
    rows = _extract_shadow_focus_items(payload, source="offline fixture")
    assert all(row["symbol"] != "EGLDUSD" for row in rows if row["relation_to_gold"] == "gold_target_candidate")
    evidence = _extract_orderbook_evidence(payload)
    assert evidence["gold_sample_count"] == 0
    assert evidence["status"] != "gold_orderbook_pressure_ready"
    payload["shadows"][1]["orderbook_pressure"] = {"available": True, "score": 0.8}
    assert _extract_orderbook_evidence(payload)["gold_sample_count"] == 1


@pytest.mark.parametrize("pressure", [{}, {"available": "false", "score": 0.8}, {"available": "true", "score": 0.8}, {"available": True}, {"available": True, "score": float("nan")}, {"available": True, "score": True}])
def test_missing_or_invalid_availability_cannot_become_direct_pressure(pressure):
    payload = {"shadows": [{"symbol": "GOLD", "venue": "capital", "side": "BUY", "orderbook_score": 0.8, "orderbook_pressure": pressure}]}
    if pressure.get("available") is True and "score" not in pressure:
        payload["shadows"][0].pop("orderbook_score")
    assert _extract_orderbook_evidence(payload)["gold_sample_count"] == 0


def test_available_direct_evidence_survives_unavailable_higher_scored_duplicate():
    payload = {"shadows": [
        {"symbol": "GOLD", "venue": "capital", "side": "BUY", "orderbook_pressure": {"available": False, "score": 0.9}},
        {"symbol": "GOLD", "venue": "capital", "side": "BUY", "orderbook_pressure": {"available": True, "score": 0.8}},
    ]}
    evidence = _extract_orderbook_evidence(payload)
    assert evidence["gold_sample_count"] == 1
    assert evidence["samples"][0]["orderbook_available"] is True
