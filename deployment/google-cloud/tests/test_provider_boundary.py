from __future__ import annotations

import base64
import importlib.util
import json
import sys
import time
from pathlib import Path
from urllib.parse import parse_qs

import pytest


MODULE = Path(__file__).resolve().parents[1] / "trading-control" / "provider_boundary.py"
spec = importlib.util.spec_from_file_location("provider_boundary", MODULE)
provider = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = provider
spec.loader.exec_module(provider)


class Response:
    def __init__(self, status, value, headers=None):
        self.status_code, self.value, self.headers = status, value, headers or {}
        self.content = json.dumps(value).encode()

    def json(self):
        return self.value


def credentials():
    return {
        "ALPACA_API_KEY": "alpaca-key", "ALPACA_SECRET_KEY": "alpaca-secret",
        "ALPACA_DRY_RUN": "false", "ALPACA_PAPER": "false",
        "BINANCE_API_KEY": "binance-key", "BINANCE_API_SECRET": "binance-secret",
        "BINANCE_DRY_RUN": "false", "BINANCE_USE_TESTNET": "false",
        "CAPITAL_API_KEY": "capital-key", "CAPITAL_IDENTIFIER": "capital-user",
        "CAPITAL_PASSWORD": "capital-password", "CAPITAL_DEMO": "0",
        "KRAKEN_API_KEY": "kraken-key",
        "KRAKEN_API_SECRET": base64.b64encode(b"kraken-secret-material").decode(),
        "KRAKEN_DRY_RUN": "false",
    }


def secret_response(value):
    raw = json.dumps(value, sort_keys=True).encode()
    payload = {
        "data": base64.b64encode(raw).decode(),
        "dataCrc32c": str(provider._crc32c(raw)),
    }
    return Response(200, {"name": provider.SECRET_RESOURCE, "payload": payload})


def test_pinned_secret_requires_exact_live_shape_and_checksum():
    value = credentials()
    boundary = provider.CredentialBoundary(
        requester=lambda *_args, **_kwargs: secret_response(value),
        token_provider=lambda: "t" * 40,
    )
    assert boundary.load() == value
    value["ALPACA_PAPER"] = "true"
    with pytest.raises(provider.ProviderError, match="not_live"):
        boundary.load()


def test_production_http_disables_environment_proxies_and_redirects(monkeypatch):
    captured = {}
    monkeypatch.setenv("HTTP_PROXY", "http://credential-bearing-proxy.invalid")
    monkeypatch.setenv("HTTPS_PROXY", "http://credential-bearing-proxy.invalid")
    monkeypatch.setenv("ALL_PROXY", "http://credential-bearing-proxy.invalid")

    class Session:
        trust_env = True

        def request(self, method, url, **kwargs):
            captured.update(method=method, url=url, kwargs=kwargs, trust_env=self.trust_env)
            return Response(200, {"ok": True})

        def close(self):
            captured["closed"] = True

    monkeypatch.setattr(provider.requests, "Session", Session)
    provider._fixed_request(
        "GET", "https://api.binance.com/api/v3/exchangeInfo",
        timeout=1, allow_redirects=True,
    )
    assert captured["trust_env"] is False
    assert captured["kwargs"]["allow_redirects"] is False
    assert captured["closed"] is True


def test_provider_http_rejects_noncanonical_hosts_before_request():
    called = False

    def requester(*_args, **_kwargs):
        nonlocal called
        called = True
        return Response(200, {})

    boundary = provider.ProviderBoundary(requester=requester)
    with pytest.raises(provider.ProviderError, match="endpoint_not_allowlisted"):
        boundary._json("GET", "https://example.invalid/api/v3/exchangeInfo")
    assert called is False


def test_transport_exception_is_sanitized(monkeypatch):
    class Session:
        trust_env = True

        def request(self, *_args, **_kwargs):
            raise provider.requests.ConnectionError("credential-bearing-detail")

        def close(self):
            pass

    monkeypatch.setattr(provider.requests, "Session", Session)
    with pytest.raises(provider.ProviderError) as caught:
        provider._fixed_request("GET", "https://api.kraken.com/0/public/AssetPairs")
    assert str(caught.value) == "provider_transport_failed"
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None


class Providers:
    def __init__(self):
        self.calls = []
        self.kraken_client_id = None
        self.capital_reference = "o_fixture-reference"

    def __call__(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        if url.endswith("/v2/account"):
            return Response(200, {
                "id": "alpaca-account", "status": "ACTIVE", "cash": "10.25",
            })
        if "/v2/assets/" in url:
            return Response(200, {
                "symbol": "BTC/USD", "status": "active", "tradable": True,
                "class": "crypto",
                "fractionable": True, "min_order_size": "0.0001",
                "min_trade_increment": "0.0001", "price_increment": "1",
            })
        if url.endswith("/v1beta3/crypto/us/latest/quotes"):
            symbol = kwargs["params"]["symbols"]
            return Response(200, {"quotes": {
                symbol: {"bp": "999", "ap": "1000", "t": 1_789_000_000},
            }})
        if "/v2/orders:by_client_order_id" in url:
            client = kwargs["params"]["client_order_id"]
            return Response(200, {"id": "alpaca-order", "client_order_id": client, "status": "accepted"})
        if url.endswith("/v2/orders"):
            body = kwargs["json"]
            return Response(200, {"id": "alpaca-order", "client_order_id": body["client_order_id"], "status": "accepted"})
        if "/api/v3/account?" in url:
            return Response(200, {
                "accountType": "SPOT", "canTrade": True,
                "balances": [
                    {"asset": "USDT", "free": "10.5", "locked": "9000"},
                    {"asset": "USDC", "free": "1", "locked": "0"},
                ],
            })
        if url.endswith("/api/v3/exchangeInfo"):
            symbol = kwargs["params"]["symbol"]
            return Response(200, {"symbols": [{
                "symbol": symbol, "status": "TRADING", "isSpotTradingAllowed": True,
                "quoteAsset": "USDT", "orderTypes": ["MARKET", "LIMIT"],
                "filters": [
                    {"filterType": "LOT_SIZE", "minQty": "0.0001", "maxQty": "100",
                     "stepSize": "0.0001"},
                    {"filterType": "MARKET_LOT_SIZE", "minQty": "0", "maxQty": "10",
                     "stepSize": "0"},
                    {"filterType": "MIN_NOTIONAL", "minNotional": "0.5", "applyToMarket": True},
                    {"filterType": "PRICE_FILTER", "minPrice": "0.1", "maxPrice": "1000000",
                     "tickSize": "0.1"},
                ],
            }]})
        if url.endswith("/api/v3/ticker/24hr"):
            symbol = kwargs["params"]["symbol"]
            return Response(200, {
                "symbol": symbol, "bidPrice": "999", "askPrice": "1000",
                "closeTime": 1_789_000_000_000,
            })
        if "/api/v3/order?" in url:
            query = parse_qs(url.split("?", 1)[1])
            client = (query.get("newClientOrderId") or query.get("origClientOrderId"))[0]
            return Response(200, {"orderId": 42, "clientOrderId": client, "status": "NEW"})
        if url.endswith("/0/private/Balance"):
            return Response(200, {"error": [], "result": {"ZUSD": "10"}})
        if url.endswith("/0/public/AssetPairs"):
            return Response(200, {"error": [], "result": {"BTC/USD": {
                "altname": "XBTUSD", "wsname": "XBT/USD", "base": "BTC", "quote": "USD",
                "lot": "unit", "lot_multiplier": 1, "lot_decimals": 4,
                "pair_decimals": 1, "tick_size": "0.1", "ordermin": "0.0001",
                "costmin": "0.5", "status": "online",
            }}})
        if url.endswith("/0/public/Ticker"):
            return Response(200, {"error": [], "result": {
                "BTC/USD": {"a": ["1000", "1", "1"], "b": ["999", "1", "1"]},
            }})
        if url.endswith("/0/public/Time"):
            return Response(200, {"error": [], "result": {"unixtime": 1_789_000_000}})
        if url.endswith("/0/private/AddOrder"):
            parsed = parse_qs(kwargs["data"])
            self.kraken_client_id = parsed["cl_ord_id"][0]
            return Response(200, {"error": [], "result": {"txid": ["KRAKEN-ORDER"]}})
        if url.endswith("/0/private/OpenOrders"):
            row = {"cl_ord_id": self.kraken_client_id, "status": "open"} if self.kraken_client_id else {}
            return Response(200, {"error": [], "result": {"open": {"KRAKEN-ORDER": row} if row else {}}})
        if url.endswith("/0/private/ClosedOrders"):
            return Response(200, {"error": [], "result": {"closed": {}}})
        if url.endswith("/api/v1/session"):
            return Response(200, {"accountType": "CFD"}, {"CST": "session", "X-SECURITY-TOKEN": "security"})
        if url.endswith("/api/v1/accounts"):
            return Response(200, {"accounts": [{
                "accountId": "capital-account", "currency": "USD",
                "balance": {"available": "10.75", "balance": "10000"},
            }]})
        if "/api/v1/markets/" in url and method == "GET":
            epic = url.rsplit("/", 1)[-1]
            return Response(200, {
                "instrument": {
                    "epic": epic, "currency": "USD", "lotSize": 1,
                },
                "snapshot": {
                    "marketStatus": "TRADEABLE", "bid": "999", "offer": "1000",
                    "updateTimeUTC": 1_789_000_000,
                },
                "dealingRules": {
                    "minDealSize": {"unit": "POINTS", "value": "0.001"},
                    "maxDealSize": {"unit": "POINTS", "value": "100"},
                    "minSizeIncrement": {"unit": "POINTS", "value": "0.001"},
                    "marketOrderPreference": "AVAILABLE_DEFAULT_ON",
                },
            })
        if url.endswith("/api/v1/positions") and method == "POST":
            return Response(200, {"dealReference": self.capital_reference})
        if "/api/v1/confirms/" in url:
            return Response(200, {"dealReference": self.capital_reference, "dealStatus": "ACCEPTED", "dealId": "capital-deal"})
        raise AssertionError((method, url, kwargs))


def order(venue, symbol):
    return {"venue": venue, "symbol": symbol, "side": "BUY", "order_type": "MARKET",
            "quantity": 0.001, "quote_value_usd": 1.0, "limit_price": None,
            "client_order_id": "intent-order-12345678"}


def test_all_four_read_only_provider_probes_emit_only_hashes():
    fake = Providers()
    result = provider.ProviderBoundary(requester=fake, clock=lambda: 1_789_000_000).probe_all(
        credentials(), maximum_order_usd=5, source_revision="a" * 40,
        observed_at_ms=1_789_000_000_000,
    )
    assert result["all_authenticated"] is True and result["provider_count"] == 4
    assert set(result["providers"]) == {"alpaca", "binance", "capital", "kraken"}
    assert result["instrument_preflight_enforced"] is True
    readiness = result["execution_budget_readiness"]
    assert readiness["source_revision"] == "a" * 40
    assert readiness["maximum_order_usd"] == "5"
    assert readiness["venues"]["alpaca"]["quotes"]["USD"] == {
        "status": "sufficient", "allowance_usd": "5",
    }
    assert readiness["venues"]["binance"]["quotes"]["USDC"] == {
        "status": "insufficient", "allowance_usd": "0",
    }
    encoded = json.dumps(result).lower()
    for forbidden in (
        "alpaca-key", "binance-key", "capital-password", "kraken-key", "cst",
        "security-token",
    ):
        assert forbidden not in encoded
    threshold_only = json.dumps(readiness)
    for forbidden in ("10.25", "10.5", "10.75"):
        assert forbidden not in threshold_only
    assert {
        row["allowance_usd"]
        for venue in readiness["venues"].values()
        for row in venue["quotes"].values()
    } <= {"0", "5"}
    mutation_paths = ("/v2/orders", "/api/v3/order", "/0/private/AddOrder", "/api/v1/positions")
    assert not any(any(path in url for path in mutation_paths) for _, url, _ in fake.calls)


def test_probe_reports_insufficient_threshold_without_disclosing_small_balance():
    class LowFunds(Providers):
        def __call__(self, method, url, **kwargs):
            if url.endswith("/v2/account"):
                self.calls.append((method, url, kwargs))
                return Response(200, {"id": "alpaca-account", "status": "ACTIVE", "cash": "4.99"})
            return super().__call__(method, url, **kwargs)

    fake = LowFunds()
    result = provider.ProviderBoundary(requester=fake, clock=lambda: 1_789_000_000).probe_all(
        credentials(), maximum_order_usd=5, source_revision="a" * 40,
        observed_at_ms=1_789_000_000_000,
    )
    assert result["execution_budget_readiness"]["venues"]["alpaca"]["quotes"]["USD"] == {
        "status": "insufficient", "allowance_usd": "0",
    }
    assert "4.99" not in json.dumps(result)


def test_kraken_nonce_preserves_nanosecond_high_water_and_monotonicity():
    boundary = provider.ProviderBoundary(requester=Providers(), clock=lambda: 1_789_000_000)
    first = int(boundary._next_kraken_nonce())
    second = int(boundary._next_kraken_nonce())
    assert first == 1_789_000_000_000_000_000
    assert second == first + 1


@pytest.mark.parametrize("venue,symbol", [
    ("alpaca", "BTC/USD"), ("binance", "BTC/USDT"),
    ("kraken", "BTC/USD"), ("capital", "SILVER"),
])
def test_each_live_adapter_submits_once_and_returns_provider_readback(venue, symbol):
    fake = Providers()
    boundary = provider.ProviderBoundary(requester=fake, clock=lambda: 1_789_000_000)
    request = order(venue, symbol)
    client_id = boundary._provider_client_id(request)
    result = boundary.submit(request, credentials(), client_id)
    assert result["venue"] == venue
    assert result["provider_order_id"] and result["provider_status"]
    assert len(result["provider_readback_sha256"]) == 64
    if venue == "kraken":
        assert len(client_id) == 32 and client_id.isalnum()
    if venue == "binance":
        assert len(client_id) == 36


def test_capital_uncertain_replay_never_auto_resubmits():
    boundary = provider.ProviderBoundary(requester=Providers(), clock=lambda: 1_789_000_000)
    request = order("capital", "SILVER")
    assert boundary.lookup(request, credentials(), boundary._provider_client_id(request)) is None


@pytest.mark.parametrize("venue,symbol", [
    ("alpaca", "BTC/USD"), ("binance", "BTC/USDT"),
    ("kraken", "BTC/USD"), ("capital", "SILVER"),
])
def test_each_provider_preflight_binds_live_instrument_rules_without_order_mutation(venue, symbol):
    fake = Providers()
    boundary = provider.ProviderBoundary(requester=fake, clock=lambda: 1_789_000_000)
    request = order(venue, symbol)
    result = boundary.preflight_order(request, credentials(), max_order_usd=5)
    assert result["schema"] == "aureon.provider-instrument-preflight.v1"
    assert result["venue"] == venue and result["symbol"] == symbol
    assert result["passed"] is True and result["provider_mutation_attempted"] is False
    assert len(result["provider_rules_sha256"]) == len(result["instrument_preflight_sha256"]) == 64
    assert result["actual_notional_usd"] == "1.000"
    assert result["max_order_usd"] == "5"
    assert result["notional_evidence"]["symbol"] == symbol
    assert provider._digest(result["notional_evidence"]) == result["notional_evidence_sha256"]
    mutation_paths = ("/v2/orders", "/api/v3/order", "/0/private/AddOrder", "/api/v1/positions")
    assert not any(any(path in url for path in mutation_paths) for _, url, _ in fake.calls)
    assert all(kwargs.get("allow_redirects") is False for _, _, kwargs in fake.calls)
    encoded = json.dumps(result).lower()
    assert not any(value.lower() in encoded for value in credentials().values() if len(value) > 5)


@pytest.mark.parametrize("venue,symbol,quantity,quote_value,reason,expected", [
    ("alpaca", "BTC/USD", 0.00015, 1.0, "alpaca_quantity_increment_invalid",
     {"minimum_quantity": "0.0001", "quantity_step": "0.0001",
      "minimum_notional_usd": None, "price_step": None, "quantity_unit": None}),
    ("binance", "BTC/USDT", 0.0004, 0.4, "binance_notional_below_minimum",
     {"minimum_quantity": "0.0001", "quantity_step": "0.0001",
      "minimum_notional_usd": "0.5", "price_step": None, "quantity_unit": None}),
    ("kraken", "BTC/USD", 0.00005, 1.0, "kraken_quantity_below_minimum",
     {"minimum_quantity": "0.0001", "quantity_step": "0.0001",
      "minimum_notional_usd": "0.5", "price_step": None, "quantity_unit": None}),
    ("capital", "SILVER", 0.0005, 1.0, "capital_quantity_below_minimum",
     {"minimum_quantity": "0.001", "quantity_step": "0.001",
      "minimum_notional_usd": None, "price_step": None, "quantity_unit": "POINTS"}),
])
def test_provider_preflight_rejects_non_executable_sizing(
    venue, symbol, quantity, quote_value, reason, expected,
):
    fake = Providers()
    request = order(venue, symbol)
    request.update(quantity=quantity, quote_value_usd=quote_value)
    with pytest.raises(provider.ProviderError, match=reason) as caught:
        provider.ProviderBoundary(
            requester=fake, clock=lambda: 1_789_000_000,
        ).preflight_order(
            request, credentials(), max_order_usd=5,
        )
    blocker = caught.value.readiness_blocker
    assert provider.valid_instrument_readiness_blocker(
        blocker, venue=venue, reason_code=reason,
    )
    assert blocker == {
        "schema": "aureon.provider-instrument-readiness-blocker.v1",
        "venue": venue,
        "reason_code": reason,
        **expected,
    }
    assert set(blocker) == {
        "schema", "venue", "reason_code", "minimum_quantity", "quantity_step",
        "minimum_notional_usd", "price_step", "quantity_unit",
    }
    assert "symbol" not in blocker and "credential" not in json.dumps(blocker).lower()
    mutation_paths = ("/v2/orders", "/api/v3/order", "/0/private/AddOrder", "/api/v1/positions")
    assert not any(any(path in url for path in mutation_paths) for _, url, _ in fake.calls)


@pytest.mark.parametrize("venue,symbol,endpoint,mutate,reason", [
    ("alpaca", "BTC/USD", "/v2/assets/", lambda value: value.pop("min_trade_increment"),
     "alpaca_trade_increment_invalid"),
    ("binance", "BTC/USDT", "/api/v3/exchangeInfo",
     lambda value: value["symbols"][0]["filters"].append(dict(value["symbols"][0]["filters"][0])),
     "binance_instrument_response_invalid"),
    ("kraken", "BTC/USD", "/0/public/AssetPairs",
     lambda value: next(iter(value["result"].values())).__setitem__("lot_decimals", "4"),
     "kraken_lot_rule_invalid"),
    ("capital", "SILVER", "/api/v1/markets/",
     lambda value: value["dealingRules"].__setitem__("marketOrderPreference", "AVAILABLE_UNKNOWN"),
     "capital_dealing_rules_invalid"),
])
def test_malformed_or_unknown_provider_rule_shapes_fail_closed(venue, symbol, endpoint, mutate, reason):
    fake = Providers()

    def requester(method, url, **kwargs):
        response = fake(method, url, **kwargs)
        if endpoint in url:
            mutate(response.value)
            response.content = json.dumps(response.value).encode()
        return response

    with pytest.raises(provider.ProviderError) as caught:
        provider.ProviderBoundary(requester=requester).preflight_order(
            order(venue, symbol), credentials(), max_order_usd=5,
        )
    assert str(caught.value) == reason
    assert provider.valid_instrument_readiness_blocker(
        caught.value.readiness_blocker, venue=venue, reason_code=reason,
    )
    assert "credential" not in str(caught.value).lower()


def test_binance_exchange_info_requires_explicit_spot_permission_shape():
    fake = Providers()

    def requester(method, url, **kwargs):
        response = fake(method, url, **kwargs)
        if url.endswith("/api/v3/exchangeInfo"):
            response.value["symbols"][0].pop("isSpotTradingAllowed")
            response.content = json.dumps(response.value).encode()
        return response

    with pytest.raises(provider.ProviderError) as caught:
        provider.ProviderBoundary(requester=requester).preflight_order(
            order("binance", "BTC/USDT"), credentials(), max_order_usd=5,
        )
    assert str(caught.value) == "binance_instrument_not_tradable"
    assert provider.valid_instrument_readiness_blocker(caught.value.readiness_blocker)


@pytest.mark.parametrize("venue,symbol,endpoint", [
    ("alpaca", "BTC/USD", "/v1beta3/crypto/us/latest/quotes"),
    ("binance", "BTC/USDT", "/api/v3/ticker/24hr"),
    ("kraken", "BTC/USD", "/0/public/Ticker"),
    ("capital", "SILVER", "/api/v1/markets/"),
])
def test_extreme_provider_price_rejects_all_four_venues_before_mutation(
    venue, symbol, endpoint,
):
    fake = Providers()

    def requester(method, url, **kwargs):
        response = fake(method, url, **kwargs)
        if endpoint in url:
            if venue == "alpaca":
                quote = next(iter(response.value["quotes"].values()))
                quote.update(bp="9999", ap="10000")
            elif venue == "binance":
                response.value.update(bidPrice="9999", askPrice="10000")
            elif venue == "kraken":
                ticker = next(iter(response.value["result"].values()))
                ticker.update(a=["10000", "1", "1"], b=["9999", "1", "1"])
            else:
                response.value["snapshot"].update(bid="9999", offer="10000")
            response.content = json.dumps(response.value).encode()
        return response

    with pytest.raises(
        provider.ProviderError, match=venue + "_actual_notional_budget_exceeded",
    ) as caught:
        provider.ProviderBoundary(
            requester=requester, clock=lambda: 1_789_000_000,
        ).preflight_order(order(venue, symbol), credentials(), max_order_usd=5)
    assert provider.valid_instrument_readiness_blocker(caught.value.readiness_blocker)
    mutation_paths = ("/v2/orders", "/api/v3/order", "/0/private/AddOrder", "/api/v1/positions")
    assert not any(any(path in url for path in mutation_paths) for _, url, _ in fake.calls)


@pytest.mark.parametrize("venue,symbol", [
    ("alpaca", "BTC/USD"), ("binance", "BTC/USDT"),
    ("kraken", "BTC/USD"), ("capital", "SILVER"),
])
@pytest.mark.parametrize("quote_value,max_order,reason", [
    (0.5, 5, "actual_notional_budget_exceeded"),
    (6, 5, "declared_notional_budget_exceeded"),
])
def test_provider_preflight_independently_enforces_both_notional_caps(
    venue, symbol, quote_value, max_order, reason,
):
    fake = Providers()
    request = order(venue, symbol)
    request["quote_value_usd"] = quote_value
    with pytest.raises(provider.ProviderError, match=f"{venue}_{reason}"):
        provider.ProviderBoundary(
            requester=fake, clock=lambda: 1_789_000_000,
        ).preflight_order(request, credentials(), max_order_usd=max_order)
    mutation_paths = ("/v2/orders", "/api/v3/order", "/0/private/AddOrder", "/api/v1/positions")
    assert not any(any(path in url for path in mutation_paths) for _, url, _ in fake.calls)


@pytest.mark.parametrize("venue,symbol,endpoint", [
    ("alpaca", "BTC/USD", "/v1beta3/crypto/us/latest/quotes"),
    ("binance", "BTC/USDT", "/api/v3/ticker/24hr"),
    ("kraken", "BTC/USD", "/0/public/Time"),
    ("capital", "SILVER", "/api/v1/markets/"),
])
def test_stale_provider_price_observation_rejects_all_four_before_mutation(
    venue, symbol, endpoint,
):
    fake = Providers()

    def requester(method, url, **kwargs):
        response = fake(method, url, **kwargs)
        if endpoint in url:
            if venue == "alpaca":
                next(iter(response.value["quotes"].values()))["t"] = 1_788_999_900
            elif venue == "binance":
                response.value["closeTime"] = 1_788_999_900_000
            elif venue == "kraken":
                response.value["result"]["unixtime"] = 1_788_999_900
            else:
                response.value["snapshot"]["updateTimeUTC"] = 1_788_999_900
            response.content = json.dumps(response.value).encode()
        return response

    with pytest.raises(provider.ProviderError, match=f"{venue}_market_price_not_fresh"):
        provider.ProviderBoundary(
            requester=requester, clock=lambda: 1_789_000_000,
        ).preflight_order(order(venue, symbol), credentials(), max_order_usd=5)
    mutation_paths = ("/v2/orders", "/api/v3/order", "/0/private/AddOrder", "/api/v1/positions")
    assert not any(any(path in url for path in mutation_paths) for _, url, _ in fake.calls)


def test_capital_exact_usd_unit_conversion_is_required_before_mutation():
    fake = Providers()

    def requester(method, url, **kwargs):
        response = fake(method, url, **kwargs)
        if "/api/v1/markets/" in url:
            response.value["instrument"]["currency"] = "EUR"
            response.content = json.dumps(response.value).encode()
        return response

    with pytest.raises(
        provider.ProviderError, match="capital_notional_currency_conversion_unavailable",
    ):
        provider.ProviderBoundary(
            requester=requester, clock=lambda: 1_789_000_000,
        ).preflight_order(order("capital", "SILVER"), credentials(), max_order_usd=5)
    assert not any("/api/v1/positions" in url for _, url, _ in fake.calls)


def test_provider_json_error_drops_exception_body_and_cause():
    class InvalidJson(Response):
        def json(self):
            raise ValueError("credential-bearing-response-body")

    boundary = provider.ProviderBoundary(
        requester=lambda *_args, **_kwargs: InvalidJson(200, {"ignored": True}),
    )
    with pytest.raises(provider.ProviderError) as caught:
        boundary._json("GET", "https://api.binance.com/api/v3/exchangeInfo")
    assert str(caught.value) == "provider_response_invalid"
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None
    assert "credential-bearing" not in repr(caught.value)


def test_secret_json_error_drops_secret_body_and_cause():
    raw = b'{"credential":"credential-bearing-secret"'
    response = Response(200, {
        "name": provider.SECRET_RESOURCE,
        "payload": {
            "data": base64.b64encode(raw).decode(),
            "dataCrc32c": str(provider._crc32c(raw)),
        },
    })
    boundary = provider.CredentialBoundary(
        requester=lambda *_args, **_kwargs: response,
        token_provider=lambda: "t" * 40,
    )
    with pytest.raises(provider.ProviderError) as caught:
        boundary.load()
    assert str(caught.value) == "credential_secret_invalid"
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None
    assert "credential-bearing" not in repr(caught.value)


def test_four_provider_readiness_probe_has_global_deadline_below_server_timeout(monkeypatch):
    fake = Providers()

    def slow_reader(method, url, **kwargs):
        time.sleep(0.05)
        return fake(method, url, **kwargs)

    monkeypatch.setattr(provider, "PROVIDER_PROBE_DEADLINE_SECONDS", 0.01)
    with pytest.raises(provider.ProviderError, match="provider_probe_deadline_exceeded"):
        provider.ProviderBoundary(requester=slow_reader).probe_all(
            credentials(),
            maximum_order_usd=5,
            source_revision="a" * 40,
            observed_at_ms=1_800_000_000_000,
        )
    dockerfile = (MODULE.parent / "Dockerfile").read_text(encoding="utf-8")
    assert provider.PROVIDER_PROBE_DEADLINE_SECONDS < 120
    assert "--timeout 120" in dockerfile
