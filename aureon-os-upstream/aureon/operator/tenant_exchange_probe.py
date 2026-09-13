"""Credential-authentication probes for tenant-owned exchange connections.

The operator UI must be able to prove that a signed-in account's BYOK
credentials authenticate without moving money.  This module therefore exposes
only four fixed, read-only provider request shapes.  Provider response bodies,
account identifiers, balances, session tokens and credentials are consumed in
memory and never leave this boundary.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import re
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Protocol
from urllib.parse import urlencode, urlsplit

import requests

MAX_CREDENTIAL_BYTES = 4096
MAX_RESPONSE_BYTES = 256 * 1024
MIN_TIMEOUT_SECONDS = 0.1
MAX_TIMEOUT_SECONDS = 10.0

EXCHANGE_CREDENTIAL_FIELDS: dict[str, tuple[str, ...]] = {
    "alpaca": ("ALPACA_API_KEY", "ALPACA_SECRET_KEY"),
    "binance": ("BINANCE_API_KEY", "BINANCE_API_SECRET"),
    "capital": ("CAPITAL_API_KEY", "CAPITAL_IDENTIFIER", "CAPITAL_PASSWORD"),
    "kraken": ("KRAKEN_API_KEY", "KRAKEN_API_SECRET"),
}

_FIXED_REQUESTS = frozenset(
    {
        ("GET", "api.alpaca.markets", "/v2/account"),
        ("GET", "api.binance.com", "/api/v3/account"),
        ("POST", "api.kraken.com", "/0/private/Balance"),
        ("POST", "api-capital.backend-capital.com", "/api/v1/session"),
    }
)
_SAFE_HEADER_VALUE = re.compile(r"[^\r\n\x00]{1,8192}")
_KRAKEN_NONCE_LOCK = threading.Lock()
_KRAKEN_LAST_NONCE = 0


class ProbeResponse(Protocol):
    status_code: int
    headers: Mapping[str, str]
    content: bytes

    def iter_content(self, chunk_size: int = ...) -> Any: ...

    def close(self) -> None: ...


Requester = Callable[..., ProbeResponse]


class _OwnedSessionResponse:
    """Keep a one-request Session alive until the streamed response is closed."""

    def __init__(self, response: Any, session: requests.Session) -> None:
        self._response = response
        self._session = session

    @property
    def status_code(self) -> int:
        return self._response.status_code

    @property
    def headers(self) -> Mapping[str, str]:
        return self._response.headers

    @property
    def content(self) -> bytes:
        return self._response.content

    def iter_content(self, chunk_size: int = 1) -> Any:
        return self._response.iter_content(chunk_size=chunk_size)

    def close(self) -> None:
        try:
            self._response.close()
        finally:
            self._session.close()


class ExchangeProbeFailure(RuntimeError):
    """A stable failure code with an optional non-sensitive HTTP status."""

    def __init__(self, reason_code: str, *, http_status: int = 0) -> None:
        super().__init__(reason_code)
        self.reason_code = reason_code
        self.http_status = http_status if type(http_status) is int else 0


def _bounded_timeout(value: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ExchangeProbeFailure("exchange_probe_timeout_invalid")
    timeout = float(value)
    if not MIN_TIMEOUT_SECONDS <= timeout <= MAX_TIMEOUT_SECONDS:
        raise ExchangeProbeFailure("exchange_probe_timeout_invalid")
    return timeout


def _validate_fixed_url(method: str, url: str) -> None:
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except (TypeError, ValueError):
        raise ExchangeProbeFailure("exchange_probe_endpoint_denied") from None
    if (
        parsed.scheme != "https"
        or parsed.username is not None
        or parsed.password is not None
        or port not in {None, 443}
        or bool(parsed.fragment)
        or (method, parsed.hostname or "", parsed.path) not in _FIXED_REQUESTS
    ):
        raise ExchangeProbeFailure("exchange_probe_endpoint_denied")
    if parsed.path != "/api/v3/account" and parsed.query:
        raise ExchangeProbeFailure("exchange_probe_endpoint_denied")


def _fixed_request(method: str, url: str, **kwargs: Any) -> ProbeResponse:
    """Issue one request with ambient proxy/netrc discovery disabled."""

    _validate_fixed_url(method, url)
    kwargs["allow_redirects"] = False
    kwargs["stream"] = True
    session = requests.Session()
    session.trust_env = False
    try:
        return _OwnedSessionResponse(session.request(method, url, **kwargs), session)
    except Exception:  # noqa: BLE001 — never surface transport exception text
        session.close()
        raise ExchangeProbeFailure("exchange_probe_transport_unavailable") from None


def _bounded_body(response: ProbeResponse) -> bytes:
    content_length = str(response.headers.get("Content-Length", "") or "")
    if content_length:
        if not content_length.isascii() or not content_length.isdigit():
            raise ExchangeProbeFailure("exchange_probe_response_invalid")
        if int(content_length) > MAX_RESPONSE_BYTES:
            raise ExchangeProbeFailure("exchange_probe_response_too_large")

    iterator = getattr(response, "iter_content", None)
    if callable(iterator):
        chunks: list[bytes] = []
        size = 0
        for raw in iterator(chunk_size=16 * 1024):
            if not isinstance(raw, bytes):
                raise ExchangeProbeFailure("exchange_probe_response_invalid")
            size += len(raw)
            if size > MAX_RESPONSE_BYTES:
                raise ExchangeProbeFailure("exchange_probe_response_too_large")
            chunks.append(raw)
        return b"".join(chunks)

    # Test doubles and a few requests-compatible clients expose only content.
    raw = getattr(response, "content", None)
    if not isinstance(raw, bytes):
        raise ExchangeProbeFailure("exchange_probe_response_invalid")
    if len(raw) > MAX_RESPONSE_BYTES:
        raise ExchangeProbeFailure("exchange_probe_response_too_large")
    return raw


def _strict_json(raw: bytes) -> Any:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate")
            result[key] = value
        return result

    try:
        value = json.loads(
            raw.decode("utf-8", errors="strict"),
            object_pairs_hook=pairs,
            parse_constant=lambda _value: (_ for _ in ()).throw(ValueError("constant")),
        )
    except (UnicodeError, ValueError, TypeError, json.JSONDecodeError, RecursionError):
        raise ExchangeProbeFailure("exchange_probe_response_invalid") from None

    pending = [value]
    visited = 0
    while pending:
        current = pending.pop()
        visited += 1
        if visited > 20_000:
            raise ExchangeProbeFailure("exchange_probe_response_invalid")
        if isinstance(current, dict):
            pending.extend(current.values())
        elif isinstance(current, list):
            pending.extend(current)
    return value


def _request_json(
    requester: Requester,
    method: str,
    url: str,
    *,
    timeout: float,
    **kwargs: Any,
) -> tuple[Any, Mapping[str, str]]:
    _validate_fixed_url(method, url)
    response: ProbeResponse | None = None
    try:
        response = requester(
            method,
            url,
            timeout=timeout,
            allow_redirects=False,
            stream=True,
            **kwargs,
        )
        status = getattr(response, "status_code", None)
        headers = getattr(response, "headers", None)
        if type(status) is not int or not isinstance(headers, Mapping):
            raise ExchangeProbeFailure("exchange_probe_response_invalid")
        if 300 <= status < 400:
            raise ExchangeProbeFailure("exchange_probe_redirect_denied", http_status=status)
        if status != 200:
            raise ExchangeProbeFailure("exchange_authentication_rejected", http_status=status)
        return _strict_json(_bounded_body(response)), headers
    except ExchangeProbeFailure:
        raise
    except Exception:
        # Never include exception text: requests errors commonly contain the
        # full URL, including the Binance signature or a query credential.
        raise ExchangeProbeFailure("exchange_probe_transport_unavailable") from None
    finally:
        if response is not None:
            closer = getattr(response, "close", None)
            if callable(closer):
                try:
                    closer()
                except Exception:
                    pass


def validate_credentials(venue: str, credentials: Mapping[str, Any]) -> dict[str, str]:
    expected = EXCHANGE_CREDENTIAL_FIELDS.get(venue)
    if expected is None:
        raise ExchangeProbeFailure("exchange_probe_unsupported")
    if not isinstance(credentials, Mapping) or set(credentials) != set(expected):
        raise ExchangeProbeFailure("exchange_credentials_incomplete")
    clean: dict[str, str] = {}
    for name in expected:
        value = credentials.get(name)
        if not isinstance(value, str):
            raise ExchangeProbeFailure("exchange_credentials_malformed")
        try:
            encoded = value.encode("utf-8", errors="strict")
        except UnicodeError:
            raise ExchangeProbeFailure("exchange_credentials_malformed") from None
        if (
            not encoded
            or len(encoded) > MAX_CREDENTIAL_BYTES
            or b"\x00" in encoded
            or b"\r" in encoded
            or b"\n" in encoded
        ):
            raise ExchangeProbeFailure("exchange_credentials_malformed")
        clean[name] = value
    return clean


@dataclass
class TenantExchangeProbe:
    requester: Requester = _fixed_request
    clock: Callable[[], float] = time.time
    timeout_seconds: float = 8.0

    def _nonce(self) -> str:
        global _KRAKEN_LAST_NONCE
        with _KRAKEN_NONCE_LOCK:
            candidate = int(self.clock() * 1_000_000_000)
            _KRAKEN_LAST_NONCE = max(candidate, _KRAKEN_LAST_NONCE + 1)
            return str(_KRAKEN_LAST_NONCE)

    @staticmethod
    def _require_mapping(value: Any) -> Mapping[str, Any]:
        if not isinstance(value, Mapping):
            raise ExchangeProbeFailure("exchange_probe_response_invalid")
        return value

    def authenticate(self, venue: str, credentials: Mapping[str, Any]) -> dict[str, Any]:
        started = time.perf_counter()
        http_status = 0
        try:
            timeout = _bounded_timeout(self.timeout_seconds)
            clean = validate_credentials(venue, credentials)
            if venue == "alpaca":
                value, _ = _request_json(
                    self.requester,
                    "GET",
                    "https://api.alpaca.markets/v2/account",
                    timeout=timeout,
                    headers={
                        "APCA-API-KEY-ID": clean["ALPACA_API_KEY"],
                        "APCA-API-SECRET-KEY": clean["ALPACA_SECRET_KEY"],
                        "Accept": "application/json",
                    },
                )
                account = self._require_mapping(value)
                if not isinstance(account.get("id"), str) or not isinstance(account.get("status"), str):
                    raise ExchangeProbeFailure("exchange_probe_response_invalid")
            elif venue == "binance":
                params = {
                    "omitZeroBalances": "true",
                    "recvWindow": 5000,
                    "timestamp": int(self.clock() * 1000),
                }
                encoded = urlencode(params, safe="")
                try:
                    signature = hmac.new(
                        clean["BINANCE_API_SECRET"].encode("ascii", errors="strict"),
                        encoded.encode("ascii"),
                        hashlib.sha256,
                    ).hexdigest()
                    api_key = clean["BINANCE_API_KEY"].encode("ascii", errors="strict").decode("ascii")
                except UnicodeError:
                    raise ExchangeProbeFailure("exchange_credentials_malformed") from None
                value, _ = _request_json(
                    self.requester,
                    "GET",
                    "https://api.binance.com/api/v3/account?" + encoded + "&signature=" + signature,
                    timeout=timeout,
                    headers={"X-MBX-APIKEY": api_key, "Accept": "application/json"},
                )
                account = self._require_mapping(value)
                if not isinstance(account.get("accountType"), str) or not isinstance(account.get("balances"), list):
                    raise ExchangeProbeFailure("exchange_probe_response_invalid")
            elif venue == "kraken":
                nonce = self._nonce()
                encoded = urlencode({"nonce": nonce})
                message = b"/0/private/Balance" + hashlib.sha256((nonce + encoded).encode("ascii")).digest()
                try:
                    secret = base64.b64decode(clean["KRAKEN_API_SECRET"], validate=True)
                    signature = base64.b64encode(hmac.new(secret, message, hashlib.sha512).digest()).decode("ascii")
                    api_key = clean["KRAKEN_API_KEY"].encode("ascii", errors="strict").decode("ascii")
                except (UnicodeError, ValueError, binascii.Error):
                    raise ExchangeProbeFailure("exchange_credentials_malformed") from None
                value, _ = _request_json(
                    self.requester,
                    "POST",
                    "https://api.kraken.com/0/private/Balance",
                    timeout=timeout,
                    headers={
                        "API-Key": api_key,
                        "API-Sign": signature,
                        "Content-Type": "application/x-www-form-urlencoded",
                        "Accept": "application/json",
                    },
                    data=encoded,
                )
                account = self._require_mapping(value)
                if account.get("error") != [] or not isinstance(account.get("result"), Mapping):
                    raise ExchangeProbeFailure("exchange_authentication_rejected", http_status=200)
            elif venue == "capital":
                value, headers = _request_json(
                    self.requester,
                    "POST",
                    "https://api-capital.backend-capital.com/api/v1/session",
                    timeout=timeout,
                    headers={
                        "X-CAP-API-KEY": clean["CAPITAL_API_KEY"],
                        "Content-Type": "application/json",
                        "Accept": "application/json",
                    },
                    json={
                        "identifier": clean["CAPITAL_IDENTIFIER"],
                        "password": clean["CAPITAL_PASSWORD"],
                    },
                )
                self._require_mapping(value)
                cst = headers.get("CST")
                security = headers.get("X-SECURITY-TOKEN")
                if (
                    not isinstance(cst, str)
                    or not isinstance(security, str)
                    or _SAFE_HEADER_VALUE.fullmatch(cst) is None
                    or _SAFE_HEADER_VALUE.fullmatch(security) is None
                ):
                    raise ExchangeProbeFailure("exchange_authentication_rejected", http_status=200)
            else:
                raise ExchangeProbeFailure("exchange_probe_unsupported")
            http_status = 200
            return {
                "ok": True,
                "authenticated": True,
                "http_status": http_status,
                "latency_ms": int((time.perf_counter() - started) * 1000),
                "error": "",
                "reason_code": "exchange_authenticated",
                "probe_scope": "credential",
                "provider_mutation_attempted": False,
            }
        except ExchangeProbeFailure as exc:
            return {
                "ok": False,
                "authenticated": False,
                "http_status": exc.http_status,
                "latency_ms": int((time.perf_counter() - started) * 1000),
                "error": exc.reason_code,
                "reason_code": exc.reason_code,
                "probe_scope": "credential",
                "provider_mutation_attempted": False,
            }
        except Exception:
            return {
                "ok": False,
                "authenticated": False,
                "http_status": http_status,
                "latency_ms": int((time.perf_counter() - started) * 1000),
                "error": "exchange_probe_unavailable",
                "reason_code": "exchange_probe_unavailable",
                "probe_scope": "credential",
                "provider_mutation_attempted": False,
            }


__all__ = [
    "EXCHANGE_CREDENTIAL_FIELDS",
    "ExchangeProbeFailure",
    "MAX_CREDENTIAL_BYTES",
    "MAX_RESPONSE_BYTES",
    "TenantExchangeProbe",
    "validate_credentials",
]
