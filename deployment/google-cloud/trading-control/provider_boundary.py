"""Pinned-secret, live-provider boundary for the isolated executor.

Only normalized hashes and provider order identifiers leave this module.  The
credential payload and transient Capital session tokens remain in memory.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import math
import re
import time
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Protocol
from urllib.parse import quote, urlencode

import requests


PROJECT_NUMBER = "4435775023"
SECRET = "aureon-owner-exchange-credentials-20260912"
SECRET_VERSION = "1"
SECRET_RESOURCE = f"projects/{PROJECT_NUMBER}/secrets/{SECRET}/versions/{SECRET_VERSION}"
SECRET_URL = "https://secretmanager.googleapis.com/v1/" + SECRET_RESOURCE + ":access"
EXPECTED_KEYS = {
    "ALPACA_API_KEY", "ALPACA_SECRET_KEY", "ALPACA_DRY_RUN", "ALPACA_PAPER",
    "BINANCE_API_KEY", "BINANCE_API_SECRET", "BINANCE_DRY_RUN", "BINANCE_USE_TESTNET",
    "CAPITAL_API_KEY", "CAPITAL_IDENTIFIER", "CAPITAL_PASSWORD", "CAPITAL_DEMO",
    "KRAKEN_API_KEY", "KRAKEN_API_SECRET", "KRAKEN_DRY_RUN",
}
LIVE_MODES = {
    "ALPACA_DRY_RUN": "false", "ALPACA_PAPER": "false",
    "BINANCE_DRY_RUN": "false", "BINANCE_USE_TESTNET": "false",
    "CAPITAL_DEMO": "0", "KRAKEN_DRY_RUN": "false",
}
_ORDER_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:/-]{1,127}")


class ProviderError(RuntimeError):
    """Stable provider-boundary failure."""


class Response(Protocol):
    status_code: int
    content: bytes
    headers: Mapping[str, str]

    def json(self) -> Any: ...


Requester = Callable[..., Response]
Token = Callable[[], str]


def _token() -> str:
    from google.auth import default as google_auth_default
    from google.auth.transport.requests import Request as GoogleAuthRequest

    credentials, _ = google_auth_default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    credentials.refresh(GoogleAuthRequest())
    token = credentials.token
    if not isinstance(token, str) or not 20 <= len(token) <= 8192:
        raise ProviderError("provider_cloud_identity_unavailable")
    return token


def _crc32c(data: bytes) -> int:
    value = 0xFFFFFFFF
    for byte in data:
        value ^= byte
        for _ in range(8):
            value = (value >> 1) ^ (0x82F63B78 if value & 1 else 0)
    return value ^ 0xFFFFFFFF


def _canonical(value: Any) -> bytes:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("ascii")
    except (ValueError, TypeError, UnicodeError) as exc:
        raise ProviderError("provider_response_invalid") from exc


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _decimal(value: Any) -> str:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ProviderError("provider_order_number_invalid")
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise ProviderError("provider_order_number_invalid")
    return format(number, ".12f").rstrip("0").rstrip(".")


@dataclass
class CredentialBoundary:
    requester: Requester = requests.request
    token_provider: Token = _token
    timeout_seconds: float = 8.0

    def load(self) -> dict[str, str]:
        token = self.token_provider()
        response = self.requester(
            "GET", SECRET_URL,
            headers={"Authorization": "Bearer " + token, "Accept": "application/json"},
            timeout=self.timeout_seconds,
        )
        token = ""
        if response.status_code != 200 or len(response.content) > 65_536:
            raise ProviderError("credential_secret_access_failed")
        try:
            envelope = response.json()
            if not isinstance(envelope, Mapping) or envelope.get("name") != SECRET_RESOURCE:
                raise ProviderError("credential_secret_resource_mismatch")
            payload = envelope["payload"]
            raw = base64.b64decode(payload["data"], validate=True)
            checksum = payload["dataCrc32c"]
            if not isinstance(checksum, str) or int(checksum) != _crc32c(raw):
                raise ProviderError("credential_secret_checksum_mismatch")
            value = json.loads(raw)
        except (KeyError, ValueError, TypeError, UnicodeError, binascii.Error) as exc:
            raise ProviderError("credential_secret_invalid") from exc
        if not isinstance(value, dict) or set(value) != EXPECTED_KEYS:
            raise ProviderError("credential_secret_shape_invalid")
        if any(not isinstance(item, str) or not item or len(item) > 4096 for item in value.values()):
            raise ProviderError("credential_secret_value_invalid")
        if any(value[key].strip().lower() != expected for key, expected in LIVE_MODES.items()):
            raise ProviderError("credential_secret_not_live")
        return value


@dataclass
class ProviderBoundary:
    requester: Requester = requests.request
    clock: Callable[[], float] = time.time
    timeout_seconds: float = 8.0

    def _json(self, method: str, url: str, *, statuses: tuple[int, ...] = (200,), **kwargs: Any) -> tuple[int, Any, Mapping[str, str]]:
        response = self.requester(method, url, timeout=self.timeout_seconds, **kwargs)
        if response.status_code not in statuses or len(response.content) > 1_048_576:
            raise ProviderError("provider_http_status_" + str(response.status_code))
        try:
            value = response.json()
        except (ValueError, TypeError) as exc:
            raise ProviderError("provider_response_invalid") from exc
        _canonical(value)
        return response.status_code, value, response.headers

    @staticmethod
    def _evidence(venue: str, value: Any, *, account: bool = False) -> dict[str, Any]:
        return {
            "venue": venue,
            "authenticated": True,
            ("account_binding_sha256" if account else "provider_readback_sha256"): _digest(value),
        }

    def _binance(self, method: str, path: str, credentials: Mapping[str, str], params: Mapping[str, Any],
                  *, statuses: tuple[int, ...] = (200,)) -> tuple[int, Any, Mapping[str, str]]:
        values = {**params, "recvWindow": 5000, "timestamp": int(self.clock() * 1000)}
        encoded = urlencode(values, safe="")
        signature = hmac.new(credentials["BINANCE_API_SECRET"].encode("ascii"), encoded.encode("ascii"), hashlib.sha256).hexdigest()
        url = "https://api.binance.com" + path + "?" + encoded + "&signature=" + signature
        return self._json(method, url, statuses=statuses, headers={"X-MBX-APIKEY": credentials["BINANCE_API_KEY"]})

    def _kraken(self, path: str, credentials: Mapping[str, str], params: Mapping[str, Any]) -> Any:
        values = {"nonce": str(int(self.clock() * 1_000_000)), **params}
        encoded = urlencode(values)
        message = path.encode("ascii") + hashlib.sha256((values["nonce"] + encoded).encode("ascii")).digest()
        try:
            secret = base64.b64decode(credentials["KRAKEN_API_SECRET"], validate=True)
        except (ValueError, binascii.Error) as exc:
            raise ProviderError("kraken_secret_invalid") from exc
        signature = base64.b64encode(hmac.new(secret, message, hashlib.sha512).digest()).decode("ascii")
        _, value, _ = self._json(
            "POST", "https://api.kraken.com" + path,
            headers={"API-Key": credentials["KRAKEN_API_KEY"], "API-Sign": signature,
                     "Content-Type": "application/x-www-form-urlencoded"}, data=encoded,
        )
        if not isinstance(value, Mapping) or value.get("error") != [] or not isinstance(value.get("result"), Mapping):
            raise ProviderError("kraken_provider_error")
        return value

    def _capital_session(self, credentials: Mapping[str, str]) -> dict[str, str]:
        _, value, headers = self._json(
            "POST", "https://api-capital.backend-capital.com/api/v1/session",
            headers={"X-CAP-API-KEY": credentials["CAPITAL_API_KEY"], "Content-Type": "application/json"},
            json={"identifier": credentials["CAPITAL_IDENTIFIER"], "password": credentials["CAPITAL_PASSWORD"]},
        )
        cst, security = headers.get("CST"), headers.get("X-SECURITY-TOKEN")
        if not isinstance(cst, str) or not isinstance(security, str) or not cst or not security:
            raise ProviderError("capital_session_tokens_missing")
        return {"CST": cst, "X-SECURITY-TOKEN": security, "Content-Type": "application/json"}

    def probe_all(self, credentials: Mapping[str, str]) -> dict[str, Any]:
        results: dict[str, Any] = {}
        _, alpaca, _ = self._json(
            "GET", "https://api.alpaca.markets/v2/account",
            headers={"APCA-API-KEY-ID": credentials["ALPACA_API_KEY"],
                     "APCA-API-SECRET-KEY": credentials["ALPACA_SECRET_KEY"]},
        )
        results["alpaca"] = self._evidence("alpaca", alpaca, account=True)
        _, binance, _ = self._binance("GET", "/api/v3/account", credentials, {"omitZeroBalances": "true"})
        results["binance"] = self._evidence("binance", binance, account=True)
        kraken = self._kraken("/0/private/Balance", credentials, {})
        results["kraken"] = self._evidence("kraken", kraken, account=True)
        capital_headers = self._capital_session(credentials)
        _, capital, _ = self._json(
            "GET", "https://api-capital.backend-capital.com/api/v1/accounts", headers=capital_headers,
        )
        results["capital"] = self._evidence("capital", capital, account=True)
        if set(results) != {"alpaca", "binance", "capital", "kraken"}:
            raise ProviderError("all_four_provider_probe_incomplete")
        return {
            "schema": "aureon.cloud-trade-provider-readback.v1",
            "providers": results,
            "provider_count": 4,
            "all_authenticated": True,
            "provider_mutation_attempted": False,
            "readback_sha256": _digest(results),
        }

    @staticmethod
    def _provider_client_id(order: Mapping[str, Any]) -> str:
        value = str(order["client_order_id"])
        if not _ORDER_ID.fullmatch(value):
            raise ProviderError("provider_client_order_id_invalid")
        hashed = hashlib.sha256(value.encode("ascii")).hexdigest()
        if order.get("venue") == "kraken":
            return hashed[:32]
        if order.get("venue") == "binance":
            return "aureon" + hashed[:30]
        return "aureon-" + hashed[:28]

    def lookup(self, order: Mapping[str, Any], credentials: Mapping[str, str], provider_client_id: str) -> dict[str, Any] | None:
        venue = order["venue"]
        if venue == "alpaca":
            status, value, _ = self._json(
                "GET", "https://api.alpaca.markets/v2/orders:by_client_order_id",
                statuses=(200, 404), params={"client_order_id": provider_client_id},
                headers={"APCA-API-KEY-ID": credentials["ALPACA_API_KEY"],
                         "APCA-API-SECRET-KEY": credentials["ALPACA_SECRET_KEY"]},
            )
            return None if status == 404 else self._normalize_order("alpaca", value, provider_client_id, "id", "status")
        if venue == "binance":
            symbol = re.sub(r"[/_.-]", "", str(order["symbol"]))
            status, value, _ = self._binance(
                "GET", "/api/v3/order", credentials,
                {"symbol": symbol, "origClientOrderId": provider_client_id}, statuses=(200, 400),
            )
            if status == 400 and isinstance(value, Mapping) and value.get("code") == -2013:
                return None
            if status != 200:
                raise ProviderError("binance_order_lookup_failed")
            return self._normalize_order("binance", value, provider_client_id, "orderId", "status")
        if venue == "kraken":
            for path in ("/0/private/OpenOrders", "/0/private/ClosedOrders"):
                value = self._kraken(path, credentials, {"cl_ord_id": provider_client_id})
                orders = value.get("result", {})
                for group in ("open", "closed"):
                    rows = orders.get(group, {}) if isinstance(orders, Mapping) else {}
                    if isinstance(rows, Mapping):
                        for provider_id, row in rows.items():
                            if isinstance(row, Mapping) and row.get("cl_ord_id") == provider_client_id:
                                normalized = dict(row)
                                normalized["provider_id"] = provider_id
                                return self._normalize_order("kraken", normalized, provider_client_id, "provider_id", "status")
            return None
        # Capital has no caller-supplied idempotency key. A retry without the
        # provider deal reference is always held for manual reconciliation.
        return None

    @staticmethod
    def _normalize_order(venue: str, value: Any, client_id: str, id_key: str, status_key: str) -> dict[str, Any]:
        if not isinstance(value, Mapping):
            raise ProviderError("provider_order_response_invalid")
        provider_id, status = value.get(id_key), value.get(status_key)
        if not isinstance(provider_id, (str, int)) or not isinstance(status, str):
            raise ProviderError("provider_order_response_invalid")
        return {
            "venue": venue, "provider_order_id": str(provider_id),
            "provider_client_order_id": client_id, "provider_status": status,
            "provider_readback_sha256": _digest(value),
        }

    def submit(self, order: Mapping[str, Any], credentials: Mapping[str, str], provider_client_id: str) -> dict[str, Any]:
        venue = order["venue"]
        quantity = _decimal(order["quantity"])
        if venue == "alpaca":
            body = {"symbol": order["symbol"], "qty": quantity, "side": str(order["side"]).lower(),
                    "type": str(order["order_type"]).lower(), "time_in_force": "gtc" if "/" in str(order["symbol"]) else "day",
                    "client_order_id": provider_client_id}
            if order["order_type"] == "LIMIT":
                body["limit_price"] = _decimal(order["limit_price"])
            _, value, _ = self._json(
                "POST", "https://api.alpaca.markets/v2/orders", json=body,
                headers={"APCA-API-KEY-ID": credentials["ALPACA_API_KEY"],
                         "APCA-API-SECRET-KEY": credentials["ALPACA_SECRET_KEY"]},
            )
            self._normalize_order("alpaca", value, provider_client_id, "id", "status")
            observed = self.lookup(order, credentials, provider_client_id)
            if observed is None:
                raise ProviderError("alpaca_order_readback_missing")
            return observed
        if venue == "binance":
            params: dict[str, Any] = {"symbol": re.sub(r"[/_.-]", "", str(order["symbol"])),
                                      "side": order["side"], "type": order["order_type"],
                                      "quantity": quantity, "newClientOrderId": provider_client_id,
                                      "newOrderRespType": "RESULT"}
            if order["order_type"] == "LIMIT":
                params.update(timeInForce="GTC", price=_decimal(order["limit_price"]))
            _, value, _ = self._binance("POST", "/api/v3/order", credentials, params)
            self._normalize_order("binance", value, provider_client_id, "orderId", "status")
            observed = self.lookup(order, credentials, provider_client_id)
            if observed is None:
                raise ProviderError("binance_order_readback_missing")
            return observed
        if venue == "kraken":
            params = {"pair": order["symbol"], "type": str(order["side"]).lower(),
                      "ordertype": str(order["order_type"]).lower(), "volume": quantity,
                      "cl_ord_id": provider_client_id}
            if order["order_type"] == "LIMIT":
                params["price"] = _decimal(order["limit_price"])
            value = self._kraken("/0/private/AddOrder", credentials, params)
            txid = value.get("result", {}).get("txid")
            if not isinstance(txid, list) or len(txid) != 1 or not isinstance(txid[0], str):
                raise ProviderError("kraken_order_ack_invalid")
            observed = self.lookup(order, credentials, provider_client_id)
            if observed is None:
                raise ProviderError("kraken_order_readback_missing")
            return observed
        if venue == "capital":
            headers = self._capital_session(credentials)
            if order["order_type"] == "MARKET":
                path = "/api/v1/positions"
                body = {"epic": order["symbol"], "direction": order["side"], "size": float(quantity), "guaranteedStop": False}
            else:
                path = "/api/v1/workingorders"
                body = {"epic": order["symbol"], "direction": order["side"], "size": float(quantity),
                        "level": float(order["limit_price"]), "type": "LIMIT", "guaranteedStop": False}
            _, value, _ = self._json("POST", "https://api-capital.backend-capital.com" + path, headers=headers, json=body)
            deal_reference = value.get("dealReference") if isinstance(value, Mapping) else None
            if not isinstance(deal_reference, str) or not deal_reference:
                raise ProviderError("capital_deal_reference_missing")
            _, confirmation, _ = self._json(
                "GET", "https://api-capital.backend-capital.com/api/v1/confirms/" + quote(deal_reference, safe=""),
                headers=headers,
            )
            if not isinstance(confirmation, Mapping) or confirmation.get("dealReference") != deal_reference:
                raise ProviderError("capital_confirmation_mismatch")
            status = confirmation.get("dealStatus")
            provider_id = confirmation.get("dealId") or deal_reference
            if not isinstance(status, str) or not isinstance(provider_id, str):
                raise ProviderError("capital_confirmation_invalid")
            return {"venue": "capital", "provider_order_id": provider_id,
                    "provider_client_order_id": deal_reference, "provider_status": status,
                    "provider_readback_sha256": _digest(confirmation)}
        raise ProviderError("provider_venue_unsupported")


__all__ = ["CredentialBoundary", "ProviderBoundary", "ProviderError"]
