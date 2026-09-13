from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1] / "trading-control"
sys.path.insert(0, str(ROOT))
live = importlib.import_module("live_executor")
provider_module = importlib.import_module("provider_boundary")


def intent(venue="alpaca"):
    return {
        "intent_id": "a" * 64,
        "authorization": {"event_sha256": "b" * 64, "active": True},
        "order": {"venue": venue, "symbol": "BTC/USD", "side": "BUY", "order_type": "MARKET",
                  "quantity": 0.001, "quote_value_usd": 1.0, "limit_price": None,
                  "client_order_id": "client-order-fixture"},
    }


class Credentials:
    def __init__(self):
        self.loads = 0

    def load(self):
        self.loads += 1
        return {"fixture": "credential"}


class Providers:
    def __init__(self):
        self.submits = 0
        self.lookups = 0
        self.preflights = 0
        self.lookup_result = None
        self.fail = False
        self.preflight_fail = False

    def _provider_client_id(self, _order):
        return "provider-client-fixture"

    def submit(self, _order, _credentials, client_id):
        self.submits += 1
        if self.fail:
            raise provider_module.ProviderError("fixture_provider_failure")
        return {"venue": "alpaca", "provider_order_id": "provider-order",
                "provider_client_order_id": client_id, "provider_status": "accepted",
                "provider_readback_sha256": "d" * 64}

    def preflight_order(self, order, _credentials, *, max_order_usd):
        self.preflights += 1
        if self.preflight_fail:
            raise provider_module.ProviderError(
                "alpaca_quantity_below_minimum",
                readiness_blocker={
                    "schema": "aureon.provider-instrument-readiness-blocker.v1",
                    "venue": "alpaca",
                    "reason_code": "alpaca_quantity_below_minimum",
                    "minimum_quantity": "0.001",
                    "quantity_step": "0.001",
                    "minimum_notional_usd": None,
                    "price_step": None,
                    "quantity_unit": None,
                },
            )
        notional = {
            "schema": "aureon.provider-notional-observation.v1",
            "venue": order["venue"], "symbol": order["symbol"],
            "side": order["side"], "order_type": order["order_type"],
            "market_price": "1000", "cap_price": "1000",
            "quantity": "0.001", "unit_multiplier": "1", "quote_asset": "USD",
            "actual_notional_usd": "1.000",
            "declared_quote_value_usd": "1.0",
            "max_order_usd": str(max_order_usd),
            "observed_at_ms": 1_789_000_000_000,
            "provider_observation_sha256": "d" * 64,
        }
        notional_sha256 = live.digest(notional)
        commitment = {
            "schema": "aureon.provider-instrument-preflight-commitment.v1",
            "venue": order["venue"], "symbol": order["symbol"],
            "order_sha256": live.digest(order), "provider_rules_sha256": "e" * 64,
            "notional_evidence_sha256": notional_sha256,
        }
        return {
            "schema": "aureon.provider-instrument-preflight.v1",
            "venue": order["venue"], "symbol": order["symbol"], "passed": True,
            "provider_mutation_attempted": False,
            "order_sha256": live.digest(order), "provider_rules_sha256": "e" * 64,
            "notional_evidence": notional,
            "notional_evidence_sha256": notional_sha256,
            "actual_notional_usd": "1.000", "observed_price": "1000",
            "max_order_usd": str(max_order_usd),
            "instrument_preflight_sha256": live.digest(commitment),
        }

    def lookup(self, _order, _credentials, _client_id):
        self.lookups += 1
        return self.lookup_result

    def probe_all(self, _credentials, **kwargs):
        return {"all_authenticated": True, "provider_count": 4, "probe_kwargs": kwargs}


class Ledger:
    def __init__(self, existing=None):
        self.effect = existing
        self.transitions = []
        self.counter = 0
        self.reserves = 0

    def reserve(self, **kwargs):
        self.reserves += 1
        if self.effect is not None:
            return {**self.effect, "created": False}
        self.effect = {**kwargs, "state": "claimed", "update_time": "t0",
                       "provider_order_id": None, "provider_client_order_id": None,
                       "provider_status": None, "provider_readback_sha256": None}
        return {**self.effect, "created": True}

    def transition(self, _intent_id, *, expected_update_time, state, now_ms, **evidence):
        assert expected_update_time == self.effect["update_time"]
        self.counter += 1
        self.effect = {**self.effect, **evidence, "state": state, "updated_at_ms": now_ms,
                       "update_time": f"t{self.counter}"}
        self.transitions.append(state)
        return dict(self.effect)

    def get_effect(self, _intent_id):
        return dict(self.effect) if self.effect is not None else None


def executor(ledger=None, providers=None, credentials=None):
    return live.LiveExecutor(
        20, max_order_usd=5, ledger=ledger or Ledger(), providers=providers or Providers(),
        credentials=credentials or Credentials(), clock=lambda: 1_789_000_000,
    )


def test_new_effect_is_durably_marked_submitting_before_one_provider_call():
    ledger, providers = Ledger(), Providers()
    result = executor(ledger, providers).execute(intent(), dispatch_sha256="c" * 64)
    assert ledger.transitions == ["submitting", "observed"]
    assert providers.preflights == providers.submits == 1 and providers.lookups == 0
    assert len(ledger.effect["instrument_preflight_sha256"]) == 64
    assert result["status"] == "provider_observed" and result["orders_submitted"] == 1


def test_observed_replay_returns_same_result_without_credentials_or_provider_call():
    source = intent()
    existing = {"state": "observed", "update_time": "t2",
                "order_sha256": live.digest(source["order"]),
                "authorization_sha256": live.digest(source["authorization"]), "venue": "alpaca",
                "instrument_preflight_sha256": "f" * 64,
                "provider_order_id": "provider-order", "provider_client_order_id": "provider-client",
                "provider_status": "filled", "provider_readback_sha256": "d" * 64}
    credentials, providers = Credentials(), Providers()
    result = executor(Ledger(existing), providers, credentials).execute(source, dispatch_sha256="c" * 64)
    assert result["provider_order_id"] == "provider-order"
    assert credentials.loads == 0 and providers.preflights == providers.submits == providers.lookups == 0


def test_uncertain_replay_reconciles_by_client_id_without_resubmitting():
    source = intent()
    existing = {"state": "submitting", "update_time": "t1",
                "order_sha256": live.digest(source["order"]),
                "authorization_sha256": live.digest(source["authorization"]), "venue": "alpaca",
                "instrument_preflight_sha256": "f" * 64,
                "provider_order_id": None, "provider_client_order_id": "provider-client",
                "provider_status": "submission_started", "provider_readback_sha256": None}
    providers = Providers()
    providers.lookup_result = {"provider_order_id": "recovered", "provider_client_order_id": "provider-client",
                               "provider_status": "filled", "provider_readback_sha256": "e" * 64}
    ledger = Ledger(existing)
    result = executor(ledger, providers).execute(source, dispatch_sha256="c" * 64)
    assert result["provider_order_id"] == "recovered"
    assert providers.lookups == 1 and providers.submits == 0 and ledger.transitions == ["observed"]


def test_capital_replay_never_resubmits_without_deal_reference():
    source = intent("capital")
    existing = {"state": "submitting", "update_time": "t1",
                "order_sha256": live.digest(source["order"]),
                "authorization_sha256": live.digest(source["authorization"]), "venue": "capital",
                "instrument_preflight_sha256": "f" * 64,
                "provider_order_id": None, "provider_client_order_id": "provider-client",
                "provider_status": "submission_started", "provider_readback_sha256": None}
    providers, ledger = Providers(), Ledger(existing)
    result = executor(ledger, providers).execute(source, dispatch_sha256="c" * 64)
    assert result["status"] == "uncertain" and result["orders_submitted"] is None
    assert providers.lookups == providers.submits == 0
    assert ledger.transitions == ["uncertain"]


def test_provider_failure_is_held_as_uncertain_and_never_reported_submitted():
    providers, ledger = Providers(), Ledger()
    providers.fail = True
    result = executor(ledger, providers).execute(intent(), dispatch_sha256="c" * 64)
    assert result["status"] == "uncertain" and result["orders_submitted"] is None
    assert providers.submits == 1 and ledger.transitions == ["submitting", "uncertain"]


def test_instrument_preflight_failure_rejects_before_budget_reservation_or_submission():
    providers, ledger = Providers(), Ledger()
    providers.preflight_fail = True
    result = executor(ledger, providers).execute(intent(), dispatch_sha256="c" * 64)
    assert result["status"] == "rejected"
    assert result["reason_code"] == "alpaca_quantity_below_minimum"
    assert result["provider_mutation_attempted"] is False
    assert result["instrument_preflight_sha256"] is None
    assert result["instrument_readiness_blocker"] == {
        "schema": "aureon.provider-instrument-readiness-blocker.v1",
        "venue": "alpaca",
        "reason_code": "alpaca_quantity_below_minimum",
        "minimum_quantity": "0.001",
        "quantity_step": "0.001",
        "minimum_notional_usd": None,
        "price_step": None,
        "quantity_unit": None,
    }
    assert providers.preflights == 1 and providers.submits == 0 and ledger.reserves == 0


def test_malformed_or_over_budget_preflight_cannot_reserve_or_mutate():
    class OverBudgetProviders(Providers):
        def preflight_order(self, order, credentials, *, max_order_usd):
            result = super().preflight_order(
                order, credentials, max_order_usd=max_order_usd,
            )
            result["actual_notional_usd"] = "500"
            return result

    providers, ledger = OverBudgetProviders(), Ledger()
    result = executor(ledger, providers).execute(intent(), dispatch_sha256="c" * 64)
    assert result["status"] == "rejected"
    assert result["reason_code"] == "instrument_preflight_receipt_invalid"
    assert result["provider_mutation_attempted"] is False
    assert providers.submits == 0 and ledger.reserves == 0


def test_legacy_effect_without_preflight_commitment_cannot_replay_or_submit():
    source = intent()
    existing = {
        "state": "observed", "update_time": "t2",
        "order_sha256": live.digest(source["order"]),
        "authorization_sha256": live.digest(source["authorization"]), "venue": "alpaca",
        "provider_order_id": "provider-order", "provider_client_order_id": "provider-client",
        "provider_status": "filled", "provider_readback_sha256": "d" * 64,
    }
    credentials, providers, ledger = Credentials(), Providers(), Ledger(existing)
    with pytest.raises(live.ExecutionError, match="ledger_instrument_preflight_missing"):
        executor(ledger, providers, credentials).execute(source, dispatch_sha256="c" * 64)
    assert credentials.loads == providers.preflights == providers.submits == ledger.reserves == 0


def test_provider_probe_uses_pinned_credentials_and_returns_four_provider_result():
    credentials, providers = Credentials(), Providers()
    result = executor(providers=providers, credentials=credentials).provider_probe(
        source_revision="a" * 40, observed_at_ms=1_789_000_000_000,
    )
    assert result == {
        "all_authenticated": True,
        "provider_count": 4,
        "probe_kwargs": {
            "maximum_order_usd": 5.0,
            "source_revision": "a" * 40,
            "observed_at_ms": 1_789_000_000_000,
        },
    }
    assert credentials.loads == 1
