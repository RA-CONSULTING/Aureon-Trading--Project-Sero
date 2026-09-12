from __future__ import annotations

import base64
import importlib.util
import json
import sys
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


class Providers:
    def __init__(self):
        self.calls = []
        self.kraken_client_id = None
        self.capital_reference = "o_fixture-reference"

    def __call__(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        if url.endswith("/v2/account"):
            return Response(200, {"id": "alpaca-account", "status": "ACTIVE"})
        if "/v2/orders:by_client_order_id" in url:
            client = kwargs["params"]["client_order_id"]
            return Response(200, {"id": "alpaca-order", "client_order_id": client, "status": "accepted"})
        if url.endswith("/v2/orders"):
            body = kwargs["json"]
            return Response(200, {"id": "alpaca-order", "client_order_id": body["client_order_id"], "status": "accepted"})
        if "/api/v3/account?" in url:
            return Response(200, {"accountType": "SPOT", "canTrade": True})
        if "/api/v3/order?" in url:
            query = parse_qs(url.split("?", 1)[1])
            client = (query.get("newClientOrderId") or query.get("origClientOrderId"))[0]
            return Response(200, {"orderId": 42, "clientOrderId": client, "status": "NEW"})
        if url.endswith("/0/private/Balance"):
            return Response(200, {"error": [], "result": {"ZUSD": "10"}})
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
            return Response(200, {"accounts": [{"accountId": "capital-account"}]})
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
    result = provider.ProviderBoundary(requester=fake, clock=lambda: 1_789_000_000).probe_all(credentials())
    assert result["all_authenticated"] is True and result["provider_count"] == 4
    assert set(result["providers"]) == {"alpaca", "binance", "capital", "kraken"}
    encoded = json.dumps(result).lower()
    for forbidden in ("alpaca-key", "binance-key", "capital-password", "kraken-key", "cst", "security-token"):
        assert forbidden not in encoded


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
