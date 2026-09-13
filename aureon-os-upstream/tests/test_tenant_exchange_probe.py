"""Offline proofs for the tenant BYOK exchange-authentication boundary."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from urllib.parse import parse_qs, urlsplit

import pytest

from aureon.operator import tenant_exchange_probe as probe
from aureon.operator.connections_catalog import CATALOG

CANARY = "credential-value-must-never-leave-probe"


def test_exchange_probe_credential_shapes_are_exactly_the_catalog_shapes():
    catalog = {connection.id: connection.credential_env for connection in CATALOG
               if connection.category == "exchange"}
    assert catalog == probe.EXCHANGE_CREDENTIAL_FIELDS


def credentials(venue: str) -> dict[str, str]:
    values = {
        "alpaca": {
            "ALPACA_API_KEY": "tenant-alpaca-primary",
            "ALPACA_SECRET_KEY": "tenant-alpaca-secondary",
        },
        "binance": {
            "BINANCE_API_KEY": "tenant-binance-primary",
            "BINANCE_API_SECRET": "tenant-binance-secondary",
        },
        "kraken": {
            "KRAKEN_API_KEY": "tenant-kraken-primary",
            "KRAKEN_API_SECRET": base64.b64encode(b"tenant-kraken-secondary").decode(),
        },
        "capital": {
            "CAPITAL_API_KEY": "tenant-capital-primary",
            "CAPITAL_IDENTIFIER": "tenant@example.invalid",
            "CAPITAL_PASSWORD": "tenant-capital-password",
        },
    }
    return values[venue]


class Response:
    def __init__(self, value, *, status=200, headers=None, raw: bytes | None = None):
        self.status_code = status
        self.headers = dict(headers or {})
        self._raw = raw if raw is not None else json.dumps(value).encode()
        self.content = self._raw
        self.closed = False

    def iter_content(self, chunk_size=1):
        for start in range(0, len(self._raw), chunk_size):
            yield self._raw[start:start + chunk_size]

    def close(self):
        self.closed = True


def successful_response(venue: str) -> Response:
    if venue == "alpaca":
        return Response({"id": CANARY, "status": "ACTIVE", "cash": CANARY})
    if venue == "binance":
        return Response({"accountType": "SPOT", "balances": [{"asset": CANARY, "free": CANARY}]})
    if venue == "kraken":
        return Response({"error": [], "result": {"ZUSD": CANARY}})
    return Response(
        {"currentAccountId": CANARY},
        headers={"CST": "capital-session-token", "X-SECURITY-TOKEN": "capital-security-token"},
    )


@pytest.mark.parametrize("venue", ["alpaca", "binance", "kraken", "capital"])
def test_each_exchange_uses_only_the_fixed_authentication_shape_and_returns_no_account_data(venue):
    calls = []
    response = successful_response(venue)

    def requester(method, url, **kwargs):
        calls.append((method, url, kwargs))
        return response

    result = probe.TenantExchangeProbe(
        requester=requester,
        clock=lambda: 1_789_000_000.125,
        timeout_seconds=1.5,
    ).authenticate(venue, credentials(venue))

    assert result == {
        "ok": True,
        "authenticated": True,
        "http_status": 200,
        "latency_ms": result["latency_ms"],
        "error": "",
        "reason_code": "exchange_authenticated",
        "probe_scope": "credential",
        "provider_mutation_attempted": False,
    }
    assert result["latency_ms"] >= 0
    assert CANARY not in json.dumps(result)
    assert all(value not in json.dumps(result) for value in credentials(venue).values())
    assert response.closed is True
    assert len(calls) == 1

    method, url, kwargs = calls[0]
    expected = {
        "alpaca": ("GET", "api.alpaca.markets", "/v2/account"),
        "binance": ("GET", "api.binance.com", "/api/v3/account"),
        "kraken": ("POST", "api.kraken.com", "/0/private/Balance"),
        "capital": ("POST", "api-capital.backend-capital.com", "/api/v1/session"),
    }[venue]
    parsed = urlsplit(url)
    assert (method, parsed.hostname, parsed.path) == expected
    assert parsed.scheme == "https" and parsed.port is None and parsed.fragment == ""
    assert kwargs["timeout"] == 1.5
    assert kwargs["allow_redirects"] is False
    assert kwargs["stream"] is True
    assert not any(word in parsed.path.lower() for word in ("order", "cancel", "transfer", "withdraw"))

    headers = kwargs["headers"]
    if venue == "alpaca":
        assert headers["APCA-API-KEY-ID"] == credentials(venue)["ALPACA_API_KEY"]
        assert headers["APCA-API-SECRET-KEY"] == credentials(venue)["ALPACA_SECRET_KEY"]
        assert parsed.query == ""
    elif venue == "binance":
        query = parse_qs(parsed.query, strict_parsing=True)
        unsigned = "omitZeroBalances=true&recvWindow=5000&timestamp=1789000000125"
        expected_signature = hmac.new(
            credentials(venue)["BINANCE_API_SECRET"].encode(),
            unsigned.encode(),
            hashlib.sha256,
        ).hexdigest()
        assert query == {
            "omitZeroBalances": ["true"],
            "recvWindow": ["5000"],
            "timestamp": ["1789000000125"],
            "signature": [expected_signature],
        }
        assert headers["X-MBX-APIKEY"] == credentials(venue)["BINANCE_API_KEY"]
    elif venue == "kraken":
        assert kwargs["data"].startswith("nonce=")
        assert int(kwargs["data"].removeprefix("nonce=")) >= int(
            1_789_000_000.125 * 1_000_000_000
        )
        assert headers["API-Key"] == credentials(venue)["KRAKEN_API_KEY"]
        assert isinstance(headers["API-Sign"], str) and headers["API-Sign"]
    else:
        assert headers["X-CAP-API-KEY"] == credentials(venue)["CAPITAL_API_KEY"]
        assert kwargs["json"] == {
            "identifier": credentials(venue)["CAPITAL_IDENTIFIER"],
            "password": credentials(venue)["CAPITAL_PASSWORD"],
        }


@pytest.mark.parametrize("venue", ["alpaca", "binance", "kraken", "capital"])
def test_missing_unknown_and_malformed_credentials_fail_before_transport(venue):
    called = False

    def forbidden(*_args, **_kwargs):
        nonlocal called
        called = True
        raise AssertionError("transport must not run")

    valid = credentials(venue)
    missing = dict(valid)
    missing.pop(next(iter(missing)))
    unknown = {**valid, "UNDECLARED_FIELD": "not-accepted"}
    malformed = dict(valid)
    malformed[next(iter(malformed))] = "bad\r\nheader"
    for values, reason in (
        (missing, "exchange_credentials_incomplete"),
        (unknown, "exchange_credentials_incomplete"),
        (malformed, "exchange_credentials_malformed"),
    ):
        result = probe.TenantExchangeProbe(requester=forbidden).authenticate(venue, values)
        assert result["ok"] is False
        assert result["reason_code"] == reason
        assert result["provider_mutation_attempted"] is False
        assert CANARY not in json.dumps(result)
    assert called is False


def test_redirect_exception_and_oversized_body_fail_with_stable_sanitized_codes():
    values = credentials("alpaca")
    canaries = [*values.values(), CANARY]

    outcomes = []
    for requester in (
        lambda *_args, **_kwargs: Response(
            {}, status=302, headers={"Location": "https://attacker.invalid/?key=" + CANARY}
        ),
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("url contained " + CANARY)),
        lambda *_args, **_kwargs: Response({}, raw=b"x" * (probe.MAX_RESPONSE_BYTES + 1)),
    ):
        outcomes.append(probe.TenantExchangeProbe(requester=requester).authenticate("alpaca", values))

    assert [row["reason_code"] for row in outcomes] == [
        "exchange_probe_redirect_denied",
        "exchange_probe_transport_unavailable",
        "exchange_probe_response_too_large",
    ]
    rendered = json.dumps(outcomes)
    assert all(canary not in rendered for canary in canaries)
    assert all(row["provider_mutation_attempted"] is False for row in outcomes)


def test_default_transport_disables_ambient_proxy_and_redirect_handling(monkeypatch):
    observed = {}
    response = successful_response("alpaca")

    class Session:
        def __init__(self):
            self.trust_env = True
            self.closed = False
            observed["session"] = self

        def request(self, method, url, **kwargs):
            observed.update(method=method, url=url, kwargs=kwargs, trust_env=self.trust_env)
            return response

        def close(self):
            self.closed = True

    monkeypatch.setattr(probe.requests, "Session", Session)
    result = probe.TenantExchangeProbe(timeout_seconds=1).authenticate(
        "alpaca", credentials("alpaca")
    )

    assert result["ok"] is True
    assert observed["trust_env"] is False
    assert observed["kwargs"]["allow_redirects"] is False
    assert observed["kwargs"]["stream"] is True
    assert "proxies" not in observed["kwargs"]
    assert observed["session"].closed is True
    assert response.closed is True


def test_timeout_is_strictly_bounded_before_transport():
    called = False

    def forbidden(*_args, **_kwargs):
        nonlocal called
        called = True
        raise AssertionError("transport must not run")

    for timeout in (0, 10.1, True, float("inf")):
        result = probe.TenantExchangeProbe(
            requester=forbidden, timeout_seconds=timeout
        ).authenticate("alpaca", credentials("alpaca"))
        assert result["reason_code"] == "exchange_probe_timeout_invalid"
    assert called is False
