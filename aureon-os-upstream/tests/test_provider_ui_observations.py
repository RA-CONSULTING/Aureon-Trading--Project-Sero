from copy import deepcopy
from aureon.exchanges.provider_ui_observations import project_capital_observation, record_capital_ui_observation


class Receipt(list):
    def __init__(self, rows=(), *, truth_status="real_observed", timestamp=1000, complete=True):
        super().__init__(rows)
        self.truth_status = truth_status
        self.source_timestamp = timestamp
        self.received_at = timestamp + 1
        self.generated_values = False
        self.inventory_complete = complete


def account(currency="GBP", amount=0):
    return {"accountId": "private-account", "accountName": "private-name", "source_id": "capital_account:private-account",
            "currency": currency, "balance": amount, "available": amount, "status": "ENABLED",
            "truth_status": "real_observed", "generated_values": False, "source_timestamp": 1000, "received_at": 1001,
            "extra_secret": "must-not-be-projected"}


def position():
    return {"source_id": "capital_position:private-deal", "truth_status": "real_observed", "generated_values": False,
            "source_timestamp": 100, "receipt_source_timestamp": 1000, "received_at": 1001,
            "terminal_fill_receipt_complete": False,
            "position": {"dealId": "private-deal", "size": 0.1, "level": 2500, "direction": "BUY", "currency": "USD"},
            "market": {"epic": "GOLD"}}


def test_accounts_preserve_real_zero_and_currency_without_identifiers_or_extra_fields():
    receipt = Receipt([account(), account("USD", 12)])
    original = deepcopy(receipt)
    projected = project_capital_observation(receipt, "accounts", demo_mode=False, now=1010)
    assert projected["status"] == "observed"
    assert [(row["currency"], row["balance"]) for row in projected["rows"]] == [("GBP", 0), ("USD", 12)]
    assert "private-account" not in str(projected)
    assert "private-name" not in str(projected)
    assert "must-not-be-projected" not in str(projected)
    assert receipt == original


def test_unreconciled_positions_stay_visible_using_receipt_time_not_opened_at():
    receipt = Receipt([position()], truth_status="incomplete")
    projected = project_capital_observation(receipt, "positions", demo_mode=False, now=1010)
    assert projected["observed_count"] == 1
    assert projected["inventory_complete"] is True
    assert projected["rows"][0]["source_timestamp"] == 1000
    assert projected["rows"][0]["opened_at"] == 100
    assert projected["rows"][0]["fill_reconciled"] is False
    assert "private-deal" not in str(projected)


def test_missing_stale_future_or_demo_receipts_do_not_produce_balances_or_zero_positions():
    for receipt, demo in [(Receipt([], truth_status="no_data"), False), (Receipt([account()], timestamp=1), False),
                          (Receipt([account()], timestamp=1200), False), (Receipt([account()]), True)]:
        projected = project_capital_observation(receipt, "accounts", demo_mode=demo, now=1010)
        assert projected["status"] == "unavailable"
        assert projected["observed_count"] is None
        assert projected["rows"] == []


def test_zero_positions_require_complete_provider_inventory():
    observed = project_capital_observation(Receipt(), "positions", demo_mode=False, now=1010)
    incomplete = project_capital_observation(Receipt(complete=False), "positions", demo_mode=False, now=1010)
    assert observed["observed_count"] == 0
    assert incomplete["observed_count"] is None


def test_partial_provider_inventory_is_never_a_complete_count():
    receipt = Receipt([position()], truth_status="incomplete", complete=False)
    projected = project_capital_observation(receipt, "positions", demo_mode=False, now=1010)
    assert projected["observed_count"] == 1
    assert projected["inventory_complete"] is False


def test_capture_does_not_fetch_or_modify_original_receipt(monkeypatch):
    monkeypatch.setattr("aureon.exchanges.provider_ui_observations.time.time", lambda: 1010)
    receipt = Receipt([account()])
    class Client:
        demo_mode = False
        calls = 0
        @record_capital_ui_observation("accounts")
        def get_accounts(self):
            self.calls += 1
            return receipt
    client = Client()
    assert client.get_accounts() is receipt
    assert client.calls == 1
    assert client.last_ui_accounts_observation["source_timestamp"] == 1000
    receipt.truth_status = "no_data"
    client.get_accounts()
    assert client.last_ui_accounts_observation["status"] == "unavailable"
