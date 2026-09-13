"""Focused contracts for the operator's passive Orca position projection."""

from __future__ import annotations

from copy import deepcopy

import pytest

from aureon.operator.legacy_runtime_api import register_legacy_runtime_routes
from aureon.operator.orca_observations import (
    PROVIDERS,
    SCHEMA_VERSION,
    SCOPE,
    SERVICE,
    build_operator_orca_observations,
)

Flask = pytest.importorskip("flask", reason="operator HTTP surface requires Flask").Flask


NOW = 1_800_000_000.0


def _position(provider: str) -> dict:
    source = {
        "capital": "capital:GET /positions",
        "alpaca": "alpaca:GET /v2/positions",
    }[provider]
    return {
        "provider": provider,
        "kind": "positions",
        "source": source,
        "source_timestamp": NOW - 2,
        "source_timestamp_kind": "provider_http_date",
        "received_at": NOW - 1,
        "max_age_seconds": 300,
        "generated_values": False,
        "status": "observed",
        "reason": "upstream_reason",
        "observed_count": 1,
        "inventory_complete": True,
        "account_id": "must-not-project",
        "rows": [{
            "reference": "a" * 16,
            "symbol": "EXAMPLE",
            "side": "BUY",
            "quantity": 2.5,
            "entry_price": 12.25,
            "currency": "USD",
            "source_timestamp": NOW - 2,
            "received_at": NOW - 1,
            "raw": {"credential": "must-not-project"},
        }],
    }


def _state() -> dict:
    return {
        "provider_observations": {
            "capital": {"positions": _position("capital")},
            "alpaca": {"positions": _position("alpaca")},
            "kraken": {"accounts": {"status": "observed"}},
            "binance": {"positions": {
                **_position("alpaca"),
                "provider": "binance",
                "source": "binance:GET /invented-positions",
            }},
        },
        "api_key": "must-not-project",
    }


def test_projection_is_allowlisted_four_provider_read_only_contract() -> None:
    state = _state()
    original = deepcopy(state)
    result = build_operator_orca_observations(state, now=NOW)

    assert result["schema_version"] == SCHEMA_VERSION
    assert result["service"] == SERVICE
    assert result["scope"] == SCOPE
    assert result["provider_calls"] is False
    assert result["mutation_authority"] is False
    assert tuple(result["provider_positions"]) == PROVIDERS
    assert result["provider_positions"]["capital"]["status"] == "observed"
    assert result["provider_positions"]["alpaca"]["status"] == "observed"
    assert result["provider_positions"]["kraken"]["status"] == "unavailable"
    assert result["provider_positions"]["binance"]["status"] == "unavailable"
    assert "must-not-project" not in str(result)
    assert state == original


def test_stale_invalid_or_unattested_receipts_fail_closed() -> None:
    state = _state()
    state["provider_observations"]["capital"]["positions"]["source_timestamp"] = NOW - 301
    assert build_operator_orca_observations(state, now=NOW)["provider_positions"]["capital"]["status"] == "unavailable"

    state = _state()
    state["provider_observations"]["alpaca"]["positions"]["rows"][0]["quantity"] = "2.5"
    assert build_operator_orca_observations(state, now=NOW)["provider_positions"]["alpaca"]["rows"] == []

    state = _state()
    state["provider_observations"]["alpaca"]["positions"].update(rows=[], observed_count=0, inventory_complete=False)
    assert build_operator_orca_observations(state, now=NOW)["provider_positions"]["alpaca"]["observed_count"] is None


def test_complete_empty_inventory_is_observed_but_missing_is_not_zero() -> None:
    state = _state()
    state["provider_observations"]["alpaca"]["positions"].update(rows=[], observed_count=0, inventory_complete=True)
    result = build_operator_orca_observations(state, now=NOW)
    assert result["provider_positions"]["alpaca"]["observed_count"] == 0
    assert build_operator_orca_observations({}, now=NOW)["provider_positions"]["alpaca"]["observed_count"] is None


def test_http_route_reads_terminal_state_once_and_sets_no_store(monkeypatch) -> None:
    import aureon.operator.legacy_runtime_api as api

    calls = []

    def read_status():
        calls.append("read")
        return _state()

    monkeypatch.setattr(api, "_status_handlers", lambda: (read_status, lambda: {}, lambda: {}))
    app = Flask(__name__)
    assert register_legacy_runtime_routes(app) >= 9
    response = app.test_client().get("/api/orca-observations")
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    assert response.get_json()["schema_version"] == SCHEMA_VERSION
    assert calls == ["read"]


def test_http_route_returns_stable_unavailable_contract_on_status_failure(monkeypatch) -> None:
    import aureon.operator.legacy_runtime_api as api

    def failed():
        raise RuntimeError("private failure detail")

    monkeypatch.setattr(api, "_status_handlers", lambda: (failed, lambda: {}, lambda: {}))
    app = Flask(__name__)
    register_legacy_runtime_routes(app)
    response = app.test_client().get("/api/orca-observations")
    body = response.get_json()
    assert response.status_code == 200
    assert body["schema_version"] == SCHEMA_VERSION
    assert all(body["provider_positions"][provider]["status"] == "unavailable" for provider in PROVIDERS)
    assert "private failure detail" not in str(body)
