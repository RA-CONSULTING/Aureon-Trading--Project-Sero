"""Account display provenance at real client HTTP/cache boundaries, without providers.

Client methods are extracted from their source AST so credential-loading module
initializers never run. All transports and clocks below are isolated test doubles.
"""
import ast
from copy import deepcopy
from email.utils import formatdate
import logging
from pathlib import Path
import threading
from types import MethodType, SimpleNamespace
from unittest.mock import Mock

import pytest

from aureon.exchanges.provider_ui_observations import (
    begin_provider_http_observation, client_ui_observations, fail_provider_http_observation,
    project_provider_http_observation, record_provider_http_observation,
)

NOW = 1_800_000_000.0
HEADERS = {"Date": formatdate(NOW, usegmt=True), "private-header": "do-not-project"}
ROOT = Path(__file__).resolve().parents[1]


def project(provider, path, payload, **kwargs):
    return project_provider_http_observation(provider, "POST" if provider == "kraken" else "GET", path,
        payload, headers=kwargs.pop("headers", HEADERS), received_at=kwargs.pop("received_at", NOW + 1),
        live_endpoint=kwargs.pop("live_endpoint", True), **kwargs)


def test_binance_observes_native_assets_zero_and_real_free_plus_locked_without_identity():
    payload = {"uid": "private-account-id", "apiKey": "do-not-project", "updateTime": 1234,
               "balances": [{"asset": "BTC", "free": "1.25", "locked": "0.25"},
                            {"asset": "EUR", "free": "0", "locked": "0"}]}
    original = deepcopy(payload)
    result = project("binance", "/api/v3/account", payload)
    assert result["status"] == "observed"
    assert result["source_timestamp"] == NOW  # Old updateTime is not snapshot time.
    assert result["provider_updated_at"] == 1.234
    assert [(row["currency"], row["balance"], row["available"]) for row in result["rows"]] == [("BTC", 1.5, 1.25), ("EUR", 0, 0)]
    assert result["inventory_complete"] is True
    assert payload == original
    assert "private-account-id" not in str(result) and "do-not-project" not in str(result)


def test_kraken_preserves_raw_asset_code_and_does_not_invent_available_cash():
    result = project("kraken", "/0/private/Balance", {"ZGBP": "12.3", "XXBT": "0"})
    assert result["status"] == "observed"
    assert [(row["currency"], row["balance"], row["available"]) for row in result["rows"]] == [("ZGBP", 12.3, None), ("XXBT", 0, None)]


def test_alpaca_equity_cash_and_buying_power_are_separate_and_position_currency_not_assumed():
    account = project("alpaca", "/v2/account", {"id": "private-id", "account_number": "private-number",
        "currency": "USD", "equity": "125", "cash": "80", "buying_power": "160", "status": "ACTIVE"})
    row = account["rows"][0]
    assert (row["balance_kind"], row["balance"], row["cash"], row["buying_power"], row["available"]) == ("equity", 125, 80, 160, None)
    assert "private-id" not in str(account) and "private-number" not in str(account)
    positions = project("alpaca", "/v2/positions", [{"asset_id": "private-asset", "symbol": "AAPL", "side": "long", "qty": "2", "avg_entry_price": "150"}])
    assert positions["rows"][0]["currency"] is None
    assert positions["rows"][0]["fill_reconciled"] is False


def test_missing_provider_date_uses_explicit_local_http_receipt_label():
    result = project("kraken", "/0/private/Balance", {"ZUSD": "2"}, headers={})
    assert result["source_timestamp"] == result["received_at"] == NOW + 1
    assert result["source_timestamp_kind"] == "local_http_receipt"


@pytest.mark.parametrize("provider,path,payload", [
    ("binance", "/api/v3/account", {"balances": [{"asset": "USD", "free": "1", "locked": "0"}]}),
    ("kraken", "/0/private/Balance", {"ZUSD": "1"}),
    ("alpaca", "/v2/account", {"currency": "USD", "equity": "1"}),
])
def test_paper_testnet_and_stale_provider_headers_are_unavailable(provider, path, payload):
    for kwargs in [{"live_endpoint": False}, {"headers": {"Date": formatdate(NOW - 301, usegmt=True)}},
                   {"headers": {"Date": formatdate(NOW + 100, usegmt=True)}}]:
        result = project(provider, path, payload, **kwargs)
        assert result["status"] == "unavailable" and result["rows"] == [] and result["observed_count"] is None


def test_malformed_amounts_do_not_default_to_zero_or_claim_complete_inventory():
    assert project("kraken", "/0/private/Balance", {"USD": "invalid"})["status"] == "unavailable"
    assert project("binance", "/api/v3/account", {"balances": [{"asset": "USD", "free": "1e308", "locked": "1e308"}]})["status"] == "unavailable"
    partial = project("kraken", "/0/private/Balance", {"USD": "1", "EUR": None})
    assert partial["observed_count"] == 1 and partial["inventory_complete"] is False
    assert project("alpaca", "/v2/positions", {})["observed_count"] is None
    assert project("alpaca", "/v2/positions", [])["observed_count"] == 0


def extracted_method(filename, class_name, method, clock):
    tree = ast.parse((ROOT / "aureon" / "exchanges" / filename).read_text(encoding="utf-8-sig"))
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == class_name)
    node = next(node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == method)
    node.decorator_list = []
    namespace = {
        "Dict": dict, "Any": object, "List": list, "time": clock,
        "logger": logging.getLogger("provider-ui-test"),
        "begin_provider_http_observation": begin_provider_http_observation,
        "fail_provider_http_observation": fail_provider_http_observation,
        "record_provider_http_observation": record_provider_http_observation,
        "client_ui_observations": client_ui_observations,
        "BINANCE_MAINNET": "https://api.binance.com", "KRAKEN_BASE": "https://api.kraken.com",
        "ALPACA_LIVE_BASE": "https://api.alpaca.markets",
        "_is_kraken_economic_mutation_path": lambda path: False,
        "_is_alpaca_economic_mutation_path": lambda method, path: False,
        "_get_next_nonce": lambda: 123,
        "EconomicGovernanceBlocked": RuntimeError,
        "requests": SimpleNamespace(exceptions=SimpleNamespace(Timeout=TimeoutError)),
        "copy": SimpleNamespace(deepcopy=deepcopy),
    }
    exec(compile(ast.Module(body=[node], type_ignores=[]), filename, "exec"), namespace)
    return namespace[method]


def response(payload):
    return SimpleNamespace(status_code=200, ok=True, headers=HEADERS, json=lambda: payload,
                           raise_for_status=Mock(), text="")


def test_binance_actual_http_return_records_once_and_failed_next_read_invalidates():
    clock = SimpleNamespace(time=lambda: NOW + 1)
    payload = {"balances": [{"asset": "GBP", "free": "2", "locked": "1"}]}
    client = SimpleNamespace(base="https://api.binance.com", use_testnet=False, max_retries=0,
                             uk_mode=False, session=SimpleNamespace(request=Mock(return_value=response(payload))))
    method = MethodType(extracted_method("binance_client.py", "BinanceClient", "_do_request", clock), client)
    assert method("GET", "/api/v3/account") is payload
    assert client.session.request.call_count == 1
    assert client.last_ui_accounts_observation["rows"][0]["balance"] == 3
    client.session.request.side_effect = TimeoutError("test-only network failure")
    with pytest.raises(TimeoutError):
        method("GET", "/api/v3/account")
    assert client.last_ui_accounts_observation["status"] == "unavailable"
    assert client.last_ui_accounts_observation["received_at"] == NOW + 1


def test_kraken_existing_balance_cache_does_not_refresh_http_provenance():
    current = [NOW + 1]
    clock = SimpleNamespace(time=lambda: current[0], sleep=Mock())
    payload = {"ZGBP": "10"}
    client = SimpleNamespace(base="https://api.kraken.com", use_testnet=False, dry_run=False,
        api_key="test-only", api_secret="test-only", _private_lock=threading.Lock(), _rate_limit_until=0,
        _private_bucket=None, _last_private_call=0, _min_call_interval=0, _consecutive_rate_limits=0,
        _kraken_sign=Mock(return_value="test-signature"), _discard_economic_dispatch=Mock(),
        _private_http_post=Mock(return_value=response({"error": [], "result": payload})),
        _balance_cache={}, _balance_cache_time=0, _balance_cache_ttl=30)
    client._private = MethodType(extracted_method("kraken_client.py", "KrakenClient", "_private", clock), client)
    account = MethodType(extracted_method("kraken_client.py", "KrakenClient", "account", clock), client)
    account()
    original = client.last_ui_accounts_observation
    current[0] += 10
    account()
    assert client._private_http_post.call_count == 1
    assert client.last_ui_accounts_observation is original
    assert original["received_at"] == NOW + 1


def test_alpaca_http_and_account_caches_do_not_mint_new_receipt_times():
    current = [NOW + 1]
    clock = SimpleNamespace(time=lambda: current[0], sleep=Mock())
    class Cache(dict):
        def set(self, key, value):
            self[key] = value
    payload = {"currency": "USD", "equity": "10", "cash": "4", "buying_power": "8"}
    client = SimpleNamespace(base_url="https://api.alpaca.markets", use_paper=False, _closed=False,
        is_authenticated=True, max_retries=0, _response_cache=Cache(), _account_cache=Cache(),
        _global_rate_budget=None, _rate_limiter=SimpleNamespace(wait_trading=Mock(), wait_data=Mock()),
        _alpaca_http_request=Mock(return_value=response(payload)), _discard_economic_dispatch=Mock())
    client._request = MethodType(extracted_method("alpaca_client.py", "AlpacaClient", "_request", clock), client)
    account = MethodType(extracted_method("alpaca_client.py", "AlpacaClient", "get_account", clock), client)
    assert account() is payload
    original = client.last_ui_accounts_observation
    current[0] += 10
    assert account() is payload
    assert client._request("GET", "/v2/account", request_type="trading") is payload
    assert client._alpaca_http_request.call_count == 1
    assert client.last_ui_accounts_observation is original
    assert original["received_at"] == NOW + 1


def test_runtime_account_carrier_preserves_receipt_across_partial_analysis_without_provider_calls():
    clock = SimpleNamespace(time=lambda: NOW + 100)
    observation = project("kraken", "/0/private/Balance", {"ZGBP": "2"})
    carrier = SimpleNamespace(kraken=SimpleNamespace(client=SimpleNamespace(last_ui_accounts_observation=observation)),
        _latest_completed_dashboard_payload={"generated_at": "previous-completed-analysis", "hnc_cognitive_proof": {"score": 0.5}})
    carrier._provider_ui_observations = MethodType(extracted_method("unified_market_trader.py", "UnifiedMarketTrader", "_provider_ui_observations", clock), carrier)
    carrier._copy_payload = deepcopy
    store = MethodType(extracted_method("unified_market_trader.py", "UnifiedMarketTrader", "_store_dashboard_snapshot", clock), carrier)
    store({"generated_at": "new-incomplete-analysis"}, completed=False)
    observed = carrier._latest_dashboard_payload
    assert observed["generated_at"] == "previous-completed-analysis"
    assert observed["provider_observations"]["kraken"]["accounts"]["received_at"] == NOW + 1
    assert observed["provider_observations"]["kraken"]["accounts"] is observation


NATIVE_ROUTES = [
    ("binance", "/api/v3/account", "accounts", {"balances": [{"asset": "GBP", "free": "2", "locked": "1"}]}),
    ("kraken", "/0/private/Balance", "accounts", {"ZGBP": "3"}),
    ("alpaca", "/v2/account", "accounts", {"currency": "USD", "equity": "3"}),
    ("alpaca", "/v2/positions", "positions", []),
]


def native_request_fixture(provider, clock, transport):
    if provider == "binance":
        client = SimpleNamespace(base="https://api.binance.com", use_testnet=False, max_retries=0,
            uk_mode=False, session=SimpleNamespace(request=transport))
        method = MethodType(extracted_method("binance_client.py", "BinanceClient", "_do_request", clock), client)
        return client, lambda path: method("GET", path)
    if provider == "kraken":
        client = SimpleNamespace(base="https://api.kraken.com", use_testnet=False, dry_run=False,
            api_key="test-only", api_secret="test-only", _private_lock=threading.Lock(), _rate_limit_until=0,
            _private_bucket=None, _last_private_call=0, _min_call_interval=0, _consecutive_rate_limits=0,
            _kraken_sign=Mock(return_value="test-signature"), _discard_economic_dispatch=Mock(),
            _private_http_post=transport)
        method = MethodType(extracted_method("kraken_client.py", "KrakenClient", "_private", clock), client)
        return client, lambda path: method(path)
    class Cache(dict):
        def set(self, key, value):
            self[key] = value
    client = SimpleNamespace(base_url="https://api.alpaca.markets", use_paper=False, _closed=False,
        is_authenticated=True, max_retries=0, _response_cache=Cache(), _global_rate_budget=None,
        _rate_limiter=SimpleNamespace(wait_trading=Mock(), wait_data=Mock()),
        _alpaca_http_request=transport, _discard_economic_dispatch=Mock())
    method = MethodType(extracted_method("alpaca_client.py", "AlpacaClient", "_request", clock), client)
    return client, lambda path: method("GET", path, request_type="trading")


@pytest.mark.parametrize("provider,path,kind,payload", NATIVE_ROUTES)
@pytest.mark.parametrize("outcome", ["success", "timeout", "http_error", "json_error"])
def test_native_refresh_keeps_original_receipt_while_pending_and_distinguishes_outcomes(provider, path, kind, payload, outcome):
    clock = SimpleNamespace(time=lambda: NOW + 51, sleep=Mock())
    transport = Mock()
    client, request = native_request_fixture(provider, clock, transport)
    previous = project(provider, path, payload)
    original = deepcopy(previous)
    setattr(client, f"last_ui_{kind}_observation", previous)

    def complete(*args, **kwargs):
        pending = getattr(client, f"last_ui_{kind}_observation")
        assert pending["status"] == "observed"
        assert pending["refresh_status"] == "pending"
        assert pending["source_timestamp"] == NOW
        assert pending["received_at"] == NOW + 1
        assert pending["rows"] == original["rows"]
        assert pending["max_age_seconds"] == 300
        if outcome == "timeout":
            raise TimeoutError("test-only transport failure")
        raw = {"error": [], "result": payload} if provider == "kraken" else payload
        result = response(raw)
        result.headers = {"Date": formatdate(NOW + 50, usegmt=True)}
        if outcome == "http_error":
            result.status_code, result.ok = 500, False
            result.raise_for_status.side_effect = RuntimeError("test-only HTTP failure")
        if outcome == "json_error":
            result.json = Mock(side_effect=ValueError("test-only invalid JSON"))
        return result

    transport.side_effect = complete
    if outcome == "success":
        assert request(path) is payload
    elif provider == "alpaca":
        assert request(path) == {}
    else:
        with pytest.raises((TimeoutError, RuntimeError, ValueError)):
            request(path)
    transport.assert_called_once()
    current = getattr(client, f"last_ui_{kind}_observation")
    if outcome == "success":
        assert current["status"] == "observed" and current["refresh_status"] == "succeeded"
        assert current["source_timestamp"] == NOW + 50 and current["received_at"] == NOW + 51
    else:
        assert current["status"] == "unavailable" and current["refresh_status"] == "failed"
        assert current["reason"] == "provider_read_failed" and current["rows"] == []
        assert current["source_timestamp"] == NOW and current["received_at"] == NOW + 1
    assert previous == original


@pytest.mark.parametrize("provider,path,kind,payload", NATIVE_ROUTES)
def test_pending_never_qualifies_expired_or_previously_failed_receipts(provider, path, kind, payload):
    method = "POST" if provider == "kraken" else "GET"
    client = SimpleNamespace()
    setattr(client, f"last_ui_{kind}_observation", project(provider, path, payload))
    token = begin_provider_http_observation(client, provider, method, path, now=NOW + 301)
    expired = getattr(client, f"last_ui_{kind}_observation")
    assert expired["status"] == "unavailable" and expired["refresh_status"] == "pending"
    assert expired["source_timestamp"] == NOW and expired["received_at"] == NOW + 1
    setattr(client, f"last_ui_{kind}_observation", project(provider, path, payload))
    fail_provider_http_observation(client, provider, method, path, refresh_token=token)
    begin_provider_http_observation(client, provider, method, path, now=NOW + 50)
    retry = getattr(client, f"last_ui_{kind}_observation")
    assert retry["status"] == "unavailable" and retry["refresh_status"] == "pending"
    assert retry["rows"] == []


@pytest.mark.parametrize("older_outcome", ["failure", "success"])
def test_older_overlapping_refresh_cannot_replace_newer_success(older_outcome):
    client = SimpleNamespace(last_ui_accounts_observation=project("kraken", "/0/private/Balance", {"ZGBP": "1"}))
    old_token = begin_provider_http_observation(client, "kraken", "POST", "/0/private/Balance", now=NOW + 40)
    new_token = begin_provider_http_observation(client, "kraken", "POST", "/0/private/Balance", now=NOW + 41)
    record_provider_http_observation(client, "kraken", "POST", "/0/private/Balance", {"ZGBP": "2"},
        headers={"Date": formatdate(NOW + 42, usegmt=True)}, received_at=NOW + 43,
        live_endpoint=True, refresh_token=new_token)
    newer = client.last_ui_accounts_observation
    if older_outcome == "failure":
        fail_provider_http_observation(client, "kraken", "POST", "/0/private/Balance", refresh_token=old_token)
    else:
        record_provider_http_observation(client, "kraken", "POST", "/0/private/Balance", {"ZGBP": "9"},
            headers={"Date": formatdate(NOW + 44, usegmt=True)}, received_at=NOW + 45,
            live_endpoint=True, refresh_token=old_token)
    assert client.last_ui_accounts_observation is newer
    assert newer["status"] == "observed" and newer["refresh_status"] == "succeeded"
    assert newer["source_timestamp"] == NOW + 42 and newer["received_at"] == NOW + 43


def test_kraken_successful_http_provider_error_invalidates_prior_receipt():
    transport = Mock(return_value=response({"error": ["EGeneral:Invalid arguments"], "result": {}}))
    client, request = native_request_fixture("kraken", SimpleNamespace(time=lambda: NOW + 51, sleep=Mock()), transport)
    client.last_ui_accounts_observation = project("kraken", "/0/private/Balance", {"ZGBP": "1"})
    with pytest.raises(RuntimeError, match="Kraken error"):
        request("/0/private/Balance")
    assert client.last_ui_accounts_observation["status"] == "unavailable"
    assert client.last_ui_accounts_observation["refresh_status"] == "failed"
    assert client.last_ui_accounts_observation["source_timestamp"] == NOW
