from __future__ import annotations

import importlib
import sys
from pathlib import Path

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
        self.lookup_result = None
        self.fail = False

    def _provider_client_id(self, _order):
        return "provider-client-fixture"

    def submit(self, _order, _credentials, client_id):
        self.submits += 1
        if self.fail:
            raise provider_module.ProviderError("fixture_provider_failure")
        return {"venue": "alpaca", "provider_order_id": "provider-order",
                "provider_client_order_id": client_id, "provider_status": "accepted",
                "provider_readback_sha256": "d" * 64}

    def lookup(self, _order, _credentials, _client_id):
        self.lookups += 1
        return self.lookup_result

    def probe_all(self, _credentials):
        return {"all_authenticated": True, "provider_count": 4}


class Ledger:
    def __init__(self, existing=None):
        self.effect = existing
        self.transitions = []
        self.counter = 0

    def reserve(self, **kwargs):
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
        20, ledger=ledger or Ledger(), providers=providers or Providers(),
        credentials=credentials or Credentials(), clock=lambda: 1_789_000_000,
    )


def test_new_effect_is_durably_marked_submitting_before_one_provider_call():
    ledger, providers = Ledger(), Providers()
    result = executor(ledger, providers).execute(intent(), dispatch_sha256="c" * 64)
    assert ledger.transitions == ["submitting", "observed"]
    assert providers.submits == 1 and providers.lookups == 0
    assert result["status"] == "provider_observed" and result["orders_submitted"] == 1


def test_observed_replay_returns_same_result_without_credentials_or_provider_call():
    existing = {"state": "observed", "update_time": "t2", "order_sha256": "x",
                "provider_order_id": "provider-order", "provider_client_order_id": "provider-client",
                "provider_status": "filled", "provider_readback_sha256": "d" * 64}
    credentials, providers = Credentials(), Providers()
    result = executor(Ledger(existing), providers, credentials).execute(intent(), dispatch_sha256="c" * 64)
    assert result["provider_order_id"] == "provider-order"
    assert credentials.loads == 0 and providers.submits == providers.lookups == 0


def test_uncertain_replay_reconciles_by_client_id_without_resubmitting():
    existing = {"state": "submitting", "update_time": "t1", "order_sha256": "x",
                "provider_order_id": None, "provider_client_order_id": "provider-client",
                "provider_status": "submission_started", "provider_readback_sha256": None}
    providers = Providers()
    providers.lookup_result = {"provider_order_id": "recovered", "provider_client_order_id": "provider-client",
                               "provider_status": "filled", "provider_readback_sha256": "e" * 64}
    ledger = Ledger(existing)
    result = executor(ledger, providers).execute(intent(), dispatch_sha256="c" * 64)
    assert result["provider_order_id"] == "recovered"
    assert providers.lookups == 1 and providers.submits == 0 and ledger.transitions == ["observed"]


def test_capital_replay_never_resubmits_without_deal_reference():
    existing = {"state": "submitting", "update_time": "t1", "order_sha256": "x",
                "provider_order_id": None, "provider_client_order_id": "provider-client",
                "provider_status": "submission_started", "provider_readback_sha256": None}
    providers, ledger = Providers(), Ledger(existing)
    result = executor(ledger, providers).execute(intent("capital"), dispatch_sha256="c" * 64)
    assert result["status"] == "uncertain" and result["orders_submitted"] is None
    assert providers.lookups == providers.submits == 0
    assert ledger.transitions == ["uncertain"]


def test_provider_failure_is_held_as_uncertain_and_never_reported_submitted():
    providers, ledger = Providers(), Ledger()
    providers.fail = True
    result = executor(ledger, providers).execute(intent(), dispatch_sha256="c" * 64)
    assert result["status"] == "uncertain" and result["orders_submitted"] is None
    assert providers.submits == 1 and ledger.transitions == ["submitting", "uncertain"]


def test_provider_probe_uses_pinned_credentials_and_returns_four_provider_result():
    credentials, providers = Credentials(), Providers()
    result = executor(providers=providers, credentials=credentials).provider_probe()
    assert result == {"all_authenticated": True, "provider_count": 4}
    assert credentials.loads == 1
