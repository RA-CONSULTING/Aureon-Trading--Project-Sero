"""Pinned-secret, live-provider boundary for the isolated executor.

Only normalized hashes and provider order identifiers leave this module.  The
credential payload and transient Capital session tokens remain in memory.
"""
from __future__ import annotations

import base64
import binascii
import concurrent.futures
import hashlib
import hmac
import json
import math
import re
import threading
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation, localcontext
from typing import Any, Callable, Mapping, Protocol
from urllib.parse import quote, urlencode, urlsplit

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
_SYMBOL = re.compile(r"[A-Z0-9][A-Z0-9./_-]{1,31}")
_REVISION = re.compile(r"[0-9a-f]{40,64}")
_USD_QUOTES = {"USD", "USDC", "USDT", "FDUSD"}
_VENUES = {"alpaca", "binance", "capital", "kraken"}
_BUDGET_QUOTES = {
    "alpaca": ("USD",),
    "binance": ("FDUSD", "USD", "USDC", "USDT"),
    "capital": ("USD",),
    "kraken": ("FDUSD", "USD", "USDC", "USDT"),
}
_MAX_PROBE_BUDGET = Decimal("5")
_RULE_BLOCKER_FIELDS = {
    "schema", "venue", "reason_code", "minimum_quantity", "quantity_step",
    "minimum_notional_usd", "price_step", "quantity_unit",
}
_MISSING = object()
_HTTPS_PATHS = {
    "secretmanager.googleapis.com": ("/v1/projects/4435775023/secrets/",),
    "api.alpaca.markets": ("/v2/",),
    "data.alpaca.markets": ("/v1beta3/", "/v2/"),
    "api.binance.com": ("/api/",),
    "api.kraken.com": ("/0/",),
    "api-capital.backend-capital.com": ("/api/v1/",),
}
_MARKET_OBSERVATION_MAX_AGE_MS = 30_000
_MARKET_OBSERVATION_CLOCK_SKEW_MS = 5_000
PROVIDER_PROBE_DEADLINE_SECONDS = 18.0


class ProviderError(RuntimeError):
    """Stable provider-boundary failure."""

    def __init__(self, reason_code: str, *, readiness_blocker: Mapping[str, Any] | None = None) -> None:
        super().__init__(reason_code)
        self.readiness_blocker = dict(readiness_blocker) if readiness_blocker is not None else None


class Response(Protocol):
    status_code: int
    content: bytes
    headers: Mapping[str, str]

    def json(self) -> Any: ...


Requester = Callable[..., Response]
Token = Callable[[], str]


def _canonical_https_url(url: str) -> None:
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except (TypeError, ValueError):
        parsed = None
        port = None
    if parsed is None:
        raise ProviderError("provider_endpoint_not_allowlisted")
    paths = _HTTPS_PATHS.get(parsed.hostname or "")
    if (parsed.scheme != "https" or parsed.username is not None or parsed.password is not None
            or port not in {None, 443} or parsed.fragment or paths is None
            or not any(parsed.path.startswith(prefix) for prefix in paths)):
        raise ProviderError("provider_endpoint_not_allowlisted")


def _fixed_request(method: str, url: str, **kwargs: Any) -> Response:
    _canonical_https_url(url)
    kwargs["allow_redirects"] = False
    session = requests.Session()
    session.trust_env = False
    try:
        response: Response | object = session.request(method, url, **kwargs)
    except requests.RequestException:
        response = _MISSING
    finally:
        session.close()
    if response is _MISSING:
        raise ProviderError("provider_transport_failed")
    return response


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
        encoded = json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False,
        ).encode("ascii")
    except (ValueError, TypeError, UnicodeError, RecursionError):
        encoded = None
    if encoded is None:
        raise ProviderError("provider_response_invalid")
    return encoded


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _decimal(value: Any) -> str:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ProviderError("provider_order_number_invalid")
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise ProviderError("provider_order_number_invalid")
    return format(number, ".12f").rstrip("0").rstrip(".")


def _rule_decimal(value: Any, code: str, *, zero: bool = False) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        raise ProviderError(code)
    if isinstance(value, str) and (not value or len(value) > 128):
        raise ProviderError(code)
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        number = None
    if number is None:
        raise ProviderError(code)
    if (not number.is_finite() or number < 0 or (not zero and number == 0)
            or len(number.as_tuple().digits) > 40
            or (number != 0 and not -24 <= number.adjusted() <= 24)):
        raise ProviderError(code)
    return number


def _decimal_text(value: Decimal) -> str:
    return format(value, "f")


def _safe_decimal_text(value: Any) -> bool:
    if not isinstance(value, str) or not 1 <= len(value) <= 96:
        return False
    try:
        number = Decimal(value)
    except InvalidOperation:
        return False
    return (
        number.is_finite()
        and number >= 0
        and len(number.as_tuple().digits) <= 40
        and (number == 0 or -24 <= number.adjusted() <= 24)
        and _decimal_text(number) == value
    )


def valid_instrument_readiness_blocker(
    value: Any, *, venue: str | None = None, reason_code: str | None = None,
) -> bool:
    """Validate the deliberately small, credential-free rule rejection shape."""
    if not isinstance(value, Mapping) or set(value) != _RULE_BLOCKER_FIELDS:
        return False
    if (value.get("schema") != "aureon.provider-instrument-readiness-blocker.v1"
            or value.get("venue") not in _VENUES
            or not isinstance(value.get("reason_code"), str)
            or re.fullmatch(r"[a-z][a-z0-9_]{2,95}", value["reason_code"]) is None
            or not value["reason_code"].startswith(value["venue"] + "_")
            or (venue is not None and value["venue"] != venue)
            or (reason_code is not None and value["reason_code"] != reason_code)):
        return False
    for key in ("minimum_quantity", "quantity_step", "minimum_notional_usd", "price_step"):
        if value[key] is not None and not _safe_decimal_text(value[key]):
            return False
    unit = value["quantity_unit"]
    return unit is None or (isinstance(unit, str) and re.fullmatch(r"[A-Z_]{2,32}", unit) is not None)


def _rule_blocker(
    venue: str,
    reason_code: str,
    *,
    minimum_quantity: Decimal | None = None,
    quantity_step: Decimal | None = None,
    minimum_notional_usd: Decimal | None = None,
    price_step: Decimal | None = None,
    quantity_unit: str | None = None,
) -> dict[str, Any]:
    value = {
        "schema": "aureon.provider-instrument-readiness-blocker.v1",
        "venue": venue,
        "reason_code": reason_code,
        "minimum_quantity": _decimal_text(minimum_quantity) if minimum_quantity is not None else None,
        "quantity_step": _decimal_text(quantity_step) if quantity_step is not None else None,
        "minimum_notional_usd": (
            _decimal_text(minimum_notional_usd) if minimum_notional_usd is not None else None
        ),
        "price_step": _decimal_text(price_step) if price_step is not None else None,
        "quantity_unit": quantity_unit,
    }
    if not valid_instrument_readiness_blocker(value, venue=venue, reason_code=reason_code):
        raise ProviderError("instrument_readiness_blocker_invalid")
    return value


def _rule_error(
    venue: str,
    reason_code: str,
    *,
    minimum_quantity: Decimal | None = None,
    quantity_step: Decimal | None = None,
    minimum_notional_usd: Decimal | None = None,
    price_step: Decimal | None = None,
    quantity_unit: str | None = None,
) -> ProviderError:
    return ProviderError(
        reason_code,
        readiness_blocker=_rule_blocker(
            venue,
            reason_code,
            minimum_quantity=minimum_quantity,
            quantity_step=quantity_step,
            minimum_notional_usd=minimum_notional_usd,
            price_step=price_step,
            quantity_unit=quantity_unit,
        ),
    )


def _step_aligned(value: Decimal, step: Decimal) -> bool:
    if step == 0:
        return True
    with localcontext() as context:
        context.prec = 60
        quotient = value / step
    return quotient == quotient.to_integral_value()


def _symbol_key(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    tokens = [token for token in re.split(r"[/_.-]+", value.upper()) if token]
    aliases = {"XBT": "BTC", "XXBT": "BTC", "XDG": "DOGE", "XXDG": "DOGE", "ZUSD": "USD"}
    if len(tokens) > 1:
        return "".join(aliases.get(token, token) for token in tokens)
    compact = re.sub(r"[/_.-]", "", value.upper())
    for source, target in (("XXBT", "BTC"), ("XBT", "BTC"), ("XXDG", "DOGE"), ("XDG", "DOGE")):
        if compact.startswith(source):
            compact = target + compact[len(source):]
            break
    if compact.endswith("ZUSD"):
        compact = compact[:-4] + "USD"
    return compact


def _timestamp_ms(value: Any, code: str) -> int:
    if isinstance(value, bool):
        raise ProviderError(code)
    if isinstance(value, (int, float)):
        number = float(value)
        if number > 10_000_000_000:
            number /= 1000.0
    elif isinstance(value, str) and 1 <= len(value) <= 64:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            parsed = None
        if parsed is None:
            raise ProviderError(code)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        number = parsed.timestamp()
    else:
        raise ProviderError(code)
    if not math.isfinite(number) or number <= 0:
        raise ProviderError(code)
    return int(number * 1000)


@dataclass
class CredentialBoundary:
    requester: Requester = _fixed_request
    token_provider: Token = _token
    timeout_seconds: float = 8.0

    def load(self) -> dict[str, str]:
        token = self.token_provider()
        response = self.requester(
            "GET", SECRET_URL,
            headers={"Authorization": "Bearer " + token, "Accept": "application/json"},
            timeout=self.timeout_seconds, allow_redirects=False,
        )
        token = ""
        if (type(response.status_code) is not int or not isinstance(response.content, bytes)
                or response.status_code != 200 or len(response.content) > 65_536):
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
        except (KeyError, ValueError, TypeError, UnicodeError, binascii.Error):
            value = _MISSING
        if value is _MISSING:
            raise ProviderError("credential_secret_invalid")
        if not isinstance(value, dict) or set(value) != EXPECTED_KEYS:
            raise ProviderError("credential_secret_shape_invalid")
        if any(not isinstance(item, str) or not item or len(item) > 4096 for item in value.values()):
            raise ProviderError("credential_secret_value_invalid")
        if any(value[key].strip().lower() != expected for key, expected in LIVE_MODES.items()):
            raise ProviderError("credential_secret_not_live")
        return value


@dataclass
class ProviderBoundary:
    requester: Requester = _fixed_request
    clock: Callable[[], float] = time.time
    timeout_seconds: float = 8.0
    _last_kraken_nonce: int = field(default=0, init=False, repr=False)
    _kraken_nonce_lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    def _next_kraken_nonce(self) -> str:
        # This production key has previously used nanosecond nonces. Kraken
        # persists a key-wide high-water mark, so reverting to milliseconds or
        # microseconds would strand every authenticated request below it.
        with self._kraken_nonce_lock:
            candidate = int(self.clock() * 1_000_000_000)
            self._last_kraken_nonce = max(candidate, self._last_kraken_nonce + 1)
            return str(self._last_kraken_nonce)

    def _json(self, method: str, url: str, *, statuses: tuple[int, ...] = (200,), **kwargs: Any) -> tuple[int, Any, Mapping[str, str]]:
        _canonical_https_url(url)
        kwargs["allow_redirects"] = False
        response = self.requester(method, url, timeout=self.timeout_seconds, **kwargs)
        if (type(response.status_code) is not int or not 100 <= response.status_code <= 599
                or not isinstance(response.content, bytes)
                or not isinstance(response.headers, Mapping)):
            raise ProviderError("provider_http_response_invalid")
        if response.status_code not in statuses or len(response.content) > 1_048_576:
            raise ProviderError("provider_http_status_" + str(response.status_code))
        try:
            value = response.json()
        except (ValueError, TypeError):
            value = _MISSING
        if value is _MISSING:
            raise ProviderError("provider_response_invalid")
        _canonical(value)
        return response.status_code, value, response.headers

    @staticmethod
    def _evidence(venue: str, value: Any, *, account: bool = False) -> dict[str, Any]:
        return {
            "venue": venue,
            "authenticated": True,
            ("account_binding_sha256" if account else "provider_readback_sha256"): _digest(value),
        }

    @staticmethod
    def _budget_number(value: Any) -> Decimal | None:
        try:
            return _rule_decimal(value, "provider_budget_value_invalid", zero=True)
        except ProviderError:
            return None

    @staticmethod
    def _threshold_quote(value: Decimal | None, maximum: Decimal) -> dict[str, str]:
        if value is None:
            return {"status": "unavailable", "allowance_usd": "0"}
        if value < maximum:
            return {"status": "insufficient", "allowance_usd": "0"}
        return {"status": "sufficient", "allowance_usd": _decimal_text(maximum)}

    @classmethod
    def _execution_budget_readiness(
        cls,
        *,
        alpaca: Any,
        binance: Any,
        capital: Any,
        kraken: Any,
        maximum_order_usd: float,
        source_revision: str,
        observed_at_ms: int,
    ) -> dict[str, Any]:
        """Reduce account payloads to zero-or-cap execution allowances.

        No raw balance, account identifier, session token, or credential is
        retained.  A quote row says only whether the account could cover one
        order at the configured cap when the authenticated probe ran.
        """

        maximum = _rule_decimal(
            maximum_order_usd, "provider_probe_budget_invalid",
        )
        if maximum > _MAX_PROBE_BUDGET:
            raise ProviderError("provider_probe_budget_invalid")
        if not isinstance(source_revision, str) or _REVISION.fullmatch(source_revision) is None:
            raise ProviderError("provider_probe_source_revision_invalid")
        if type(observed_at_ms) is not int or observed_at_ms <= 0:
            raise ProviderError("provider_probe_observed_at_invalid")

        amounts: dict[str, dict[str, Decimal | None]] = {
            venue: {asset: None for asset in assets}
            for venue, assets in _BUDGET_QUOTES.items()
        }

        if isinstance(alpaca, Mapping):
            amounts["alpaca"]["USD"] = cls._budget_number(alpaca.get("cash"))

        binance_rows = binance.get("balances") if isinstance(binance, Mapping) else None
        if isinstance(binance_rows, list) and len(binance_rows) <= 1_000:
            for row in binance_rows:
                if not isinstance(row, Mapping):
                    continue
                asset = str(row.get("asset") or "").upper()
                if asset in amounts["binance"]:
                    amounts["binance"][asset] = cls._budget_number(row.get("free"))

        kraken_rows = kraken.get("result") if isinstance(kraken, Mapping) else None
        if isinstance(kraken_rows, Mapping) and len(kraken_rows) <= 1_000:
            for raw_asset, raw_amount in kraken_rows.items():
                asset = str(raw_asset or "").upper()
                asset = {"ZUSD": "USD", "USDT.F": "USDT", "USDC.F": "USDC"}.get(asset, asset)
                if asset in amounts["kraken"]:
                    number = cls._budget_number(raw_amount)
                    previous = amounts["kraken"][asset]
                    if number is not None:
                        amounts["kraken"][asset] = number + (previous or Decimal("0"))

        capital_rows = capital.get("accounts") if isinstance(capital, Mapping) else None
        if isinstance(capital_rows, list) and len(capital_rows) <= 100:
            total: Decimal | None = None
            for row in capital_rows:
                if not isinstance(row, Mapping):
                    continue
                currency = str(row.get("currency") or row.get("accountCurrency") or "").upper()
                balance = row.get("balance")
                number = (
                    cls._budget_number(balance.get("available"))
                    if currency == "USD" and isinstance(balance, Mapping)
                    else None
                )
                if number is not None:
                    total = number + (total or Decimal("0"))
            amounts["capital"]["USD"] = total

        readiness = {
            "schema": "aureon.cloud-trade-execution-budget-readiness.v1",
            "source_revision": source_revision,
            "observed_at_ms": observed_at_ms,
            "maximum_order_usd": _decimal_text(maximum),
            "venues": {
                venue: {
                    "authenticated": True,
                    "quotes": {
                        asset: cls._threshold_quote(amounts[venue][asset], maximum)
                        for asset in assets
                    },
                }
                for venue, assets in _BUDGET_QUOTES.items()
            },
        }
        _canonical(readiness)
        return readiness

    def _binance(self, method: str, path: str, credentials: Mapping[str, str], params: Mapping[str, Any],
                  *, statuses: tuple[int, ...] = (200,)) -> tuple[int, Any, Mapping[str, str]]:
        values = {**params, "recvWindow": 5000, "timestamp": int(self.clock() * 1000)}
        encoded = urlencode(values, safe="")
        signature = hmac.new(credentials["BINANCE_API_SECRET"].encode("ascii"), encoded.encode("ascii"), hashlib.sha256).hexdigest()
        url = "https://api.binance.com" + path + "?" + encoded + "&signature=" + signature
        return self._json(method, url, statuses=statuses, headers={"X-MBX-APIKEY": credentials["BINANCE_API_KEY"]})

    def _kraken(self, path: str, credentials: Mapping[str, str], params: Mapping[str, Any]) -> Any:
        values = {"nonce": self._next_kraken_nonce(), **params}
        encoded = urlencode(values)
        message = path.encode("ascii") + hashlib.sha256((values["nonce"] + encoded).encode("ascii")).digest()
        try:
            secret = base64.b64decode(credentials["KRAKEN_API_SECRET"], validate=True)
        except (ValueError, binascii.Error):
            secret = None
        if secret is None:
            raise ProviderError("kraken_secret_invalid")
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

    @staticmethod
    def _order_values(order: Mapping[str, Any]) -> tuple[str, str, str, Decimal, Decimal, Decimal | None]:
        try:
            venue = order["venue"]
            symbol = order["symbol"]
            order_type = order["order_type"]
            quantity = _rule_decimal(order["quantity"], "provider_order_quantity_invalid")
            quote_value = _rule_decimal(order["quote_value_usd"], "provider_order_notional_invalid")
        except (KeyError, TypeError):
            venue = _MISSING
        if venue is _MISSING:
            raise ProviderError("provider_order_shape_invalid")
        if venue not in {"alpaca", "binance", "capital", "kraken"}:
            raise ProviderError("provider_venue_unsupported")
        if not isinstance(symbol, str) or not _SYMBOL.fullmatch(symbol):
            raise ProviderError("provider_order_symbol_invalid")
        if order_type not in {"MARKET", "LIMIT"}:
            raise ProviderError("provider_order_type_invalid")
        limit_price = None
        if order_type == "LIMIT":
            limit_price = _rule_decimal(order.get("limit_price"), "provider_order_price_invalid")
        elif order.get("limit_price") is not None:
            raise ProviderError("provider_market_price_forbidden")
        return venue, symbol, order_type, quantity, quote_value, limit_price

    @staticmethod
    def _cap_price(
        *, order_type: str, side: str, market_price: Decimal, limit_price: Decimal | None,
    ) -> Decimal:
        if side not in {"BUY", "SELL"}:
            raise ProviderError("provider_order_side_invalid")
        if order_type == "MARKET":
            return market_price
        if limit_price is None:
            raise ProviderError("provider_order_price_invalid")
        # A buy limit cannot fill above its limit.  For a sell, use the larger
        # of the current executable bid and limit so a favourable current fill
        # cannot evade the absolute USD exposure cap.
        return limit_price if side == "BUY" else max(market_price, limit_price)

    def _notional_evidence(
        self,
        order: Mapping[str, Any],
        *,
        market_price: Any,
        quote_asset: str,
        unit_multiplier: Any,
        observed_at: Any,
        provider_observation: Mapping[str, Any],
        max_order_usd: float,
    ) -> dict[str, Any]:
        venue, symbol, order_type, quantity, quote_value, limit_price = self._order_values(order)
        if not isinstance(quote_asset, str) or _symbol_key(quote_asset) not in _USD_QUOTES:
            raise ProviderError(venue + "_notional_currency_conversion_unavailable")
        price = _rule_decimal(market_price, venue + "_market_price_invalid")
        multiplier = _rule_decimal(unit_multiplier, venue + "_notional_unit_conversion_unavailable")
        maximum = _rule_decimal(max_order_usd, "provider_max_order_budget_invalid")
        observed_at_ms = _timestamp_ms(observed_at, venue + "_market_timestamp_invalid")
        now_ms = int(float(self.clock()) * 1000)
        age_ms = now_ms - observed_at_ms
        if (age_ms < -_MARKET_OBSERVATION_CLOCK_SKEW_MS
                or age_ms > _MARKET_OBSERVATION_MAX_AGE_MS):
            raise ProviderError(venue + "_market_price_not_fresh")
        cap_price = self._cap_price(
            order_type=order_type,
            side=str(order.get("side") or ""),
            market_price=price,
            limit_price=limit_price,
        )
        with localcontext() as context:
            context.prec = 60
            actual_notional = quantity * multiplier * cap_price
        if quote_value > maximum:
            raise _rule_error(venue, venue + "_declared_notional_budget_exceeded")
        if actual_notional > quote_value or actual_notional > maximum:
            raise _rule_error(venue, venue + "_actual_notional_budget_exceeded")
        return {
            "schema": "aureon.provider-notional-observation.v1",
            "venue": venue,
            "symbol": symbol,
            "side": str(order["side"]),
            "order_type": order_type,
            "market_price": _decimal_text(price),
            "cap_price": _decimal_text(cap_price),
            "quantity": _decimal_text(quantity),
            "unit_multiplier": _decimal_text(multiplier),
            "quote_asset": quote_asset,
            "actual_notional_usd": _decimal_text(actual_notional),
            "declared_quote_value_usd": _decimal_text(quote_value),
            "max_order_usd": _decimal_text(maximum),
            "observed_at_ms": observed_at_ms,
            "provider_observation_sha256": _digest(dict(provider_observation)),
        }

    @staticmethod
    def _preflight_receipt(order: Mapping[str, Any], rules: Mapping[str, Any]) -> dict[str, Any]:
        venue, symbol, *_ = ProviderBoundary._order_values(order)
        notional = rules.get("notional_evidence")
        if (not isinstance(notional, Mapping)
                or notional.get("schema") != "aureon.provider-notional-observation.v1"
                or notional.get("venue") != venue
                or notional.get("symbol") != symbol):
            raise ProviderError("instrument_preflight_notional_evidence_invalid")
        order_sha256 = _digest(dict(order))
        rules_sha256 = _digest(dict(rules))
        commitment = {
            "schema": "aureon.provider-instrument-preflight-commitment.v1",
            "venue": venue,
            "symbol": symbol,
            "order_sha256": order_sha256,
            "provider_rules_sha256": rules_sha256,
            "notional_evidence_sha256": _digest(dict(notional)),
        }
        return {
            "schema": "aureon.provider-instrument-preflight.v1",
            "venue": venue,
            "symbol": symbol,
            "passed": True,
            "provider_mutation_attempted": False,
            "order_sha256": order_sha256,
            "provider_rules_sha256": rules_sha256,
            "notional_evidence_sha256": commitment["notional_evidence_sha256"],
            "notional_evidence": dict(notional),
            "actual_notional_usd": notional["actual_notional_usd"],
            "observed_price": notional["cap_price"],
            "max_order_usd": notional["max_order_usd"],
            "instrument_preflight_sha256": _digest(commitment),
        }

    @staticmethod
    def _quantity_filter(quantity: Decimal, rule: Mapping[str, Any], *, prefix: str,
                         venue: str, require_positive: bool = True) -> dict[str, str]:
        try:
            minimum = _rule_decimal(rule["minQty"], prefix + "_rule_invalid", zero=not require_positive)
            maximum = _rule_decimal(rule["maxQty"], prefix + "_rule_invalid", zero=not require_positive)
            step = _rule_decimal(rule["stepSize"], prefix + "_rule_invalid", zero=not require_positive)
        except (KeyError, TypeError):
            minimum = None
        if minimum is None:
            raise ProviderError(prefix + "_rule_invalid")
        if maximum > 0 and minimum > maximum:
            raise ProviderError(prefix + "_rule_invalid")
        if minimum > 0 and quantity < minimum:
            raise _rule_error(
                venue, prefix + "_quantity_below_minimum",
                minimum_quantity=minimum, quantity_step=step,
            )
        if maximum > 0 and quantity > maximum:
            raise _rule_error(
                venue, prefix + "_quantity_above_maximum",
                minimum_quantity=minimum, quantity_step=step,
            )
        if step > 0 and not _step_aligned(quantity, step):
            raise _rule_error(
                venue, prefix + "_quantity_increment_invalid",
                minimum_quantity=minimum, quantity_step=step,
            )
        return {"min": _decimal_text(minimum), "max": _decimal_text(maximum), "step": _decimal_text(step)}

    @staticmethod
    def _price_filter(
        price: Decimal, rule: Mapping[str, Any], *, prefix: str, venue: str,
    ) -> dict[str, str]:
        try:
            minimum = _rule_decimal(rule["minPrice"], prefix + "_price_rule_invalid", zero=True)
            maximum = _rule_decimal(rule["maxPrice"], prefix + "_price_rule_invalid", zero=True)
            step = _rule_decimal(rule["tickSize"], prefix + "_price_rule_invalid", zero=True)
        except (KeyError, TypeError):
            minimum = None
        if minimum is None:
            raise ProviderError(prefix + "_price_rule_invalid")
        if maximum > 0 and minimum > maximum:
            raise ProviderError(prefix + "_price_rule_invalid")
        if minimum > 0 and price < minimum:
            raise _rule_error(venue, prefix + "_price_below_minimum", price_step=step)
        if maximum > 0 and price > maximum:
            raise _rule_error(venue, prefix + "_price_above_maximum", price_step=step)
        if step > 0 and not _step_aligned(price, step):
            raise _rule_error(venue, prefix + "_price_increment_invalid", price_step=step)
        return {"min": _decimal_text(minimum), "max": _decimal_text(maximum), "step": _decimal_text(step)}

    def _preflight_alpaca(
        self, order: Mapping[str, Any], credentials: Mapping[str, str], *, max_order_usd: float,
    ) -> dict[str, Any]:
        _, symbol, order_type, quantity, _, limit_price = self._order_values(order)
        _, asset, _ = self._json(
            "GET", "https://api.alpaca.markets/v2/assets/" + quote(symbol, safe=""),
            headers={"APCA-API-KEY-ID": credentials["ALPACA_API_KEY"],
                     "APCA-API-SECRET-KEY": credentials["ALPACA_SECRET_KEY"]},
        )
        if not isinstance(asset, Mapping) or _symbol_key(asset.get("symbol")) != _symbol_key(symbol):
            raise ProviderError("alpaca_instrument_response_invalid")
        if asset.get("status") != "active" or asset.get("tradable") is not True:
            raise ProviderError("alpaca_instrument_not_tradable")
        asset_class = asset.get("class")
        if asset_class not in {"crypto", "us_equity"}:
            raise ProviderError("alpaca_notional_unit_conversion_unavailable")
        fractionable = asset.get("fractionable")
        if type(fractionable) is not bool:
            raise ProviderError("alpaca_instrument_response_invalid")
        minimum = _rule_decimal(asset.get("min_order_size"), "alpaca_min_order_size_invalid")
        increment = _rule_decimal(asset.get("min_trade_increment"), "alpaca_trade_increment_invalid")
        if quantity < minimum:
            raise _rule_error(
                "alpaca", "alpaca_quantity_below_minimum",
                minimum_quantity=minimum, quantity_step=increment,
            )
        if not _step_aligned(quantity, increment):
            raise _rule_error(
                "alpaca", "alpaca_quantity_increment_invalid",
                minimum_quantity=minimum, quantity_step=increment,
            )
        if not fractionable and quantity != quantity.to_integral_value():
            raise _rule_error(
                "alpaca", "alpaca_fractional_order_unavailable",
                minimum_quantity=minimum, quantity_step=increment,
            )
        price_increment: Decimal | None = None
        if order_type == "LIMIT":
            price_increment = _rule_decimal(asset.get("price_increment"), "alpaca_price_increment_rule_invalid")
            if limit_price is None or not _step_aligned(limit_price, price_increment):
                raise _rule_error(
                    "alpaca", "alpaca_price_increment_invalid",
                    minimum_quantity=minimum, quantity_step=increment,
                    price_step=price_increment,
                )
        quote_headers = {
            "APCA-API-KEY-ID": credentials["ALPACA_API_KEY"],
            "APCA-API-SECRET-KEY": credentials["ALPACA_SECRET_KEY"],
        }
        if asset_class == "crypto":
            _, quote_payload, _ = self._json(
                "GET", "https://data.alpaca.markets/v1beta3/crypto/us/latest/quotes",
                params={"symbols": symbol}, headers=quote_headers,
            )
            quotes = quote_payload.get("quotes") if isinstance(quote_payload, Mapping) else None
            if not isinstance(quotes, Mapping) or len(quotes) != 1:
                raise ProviderError("alpaca_market_quote_invalid")
            quote_symbol, quote_row = next(iter(quotes.items()))
            if _symbol_key(quote_symbol) != _symbol_key(symbol) or not isinstance(quote_row, Mapping):
                raise ProviderError("alpaca_market_quote_invalid")
            quote_asset = symbol.split("/")[-1] if "/" in symbol else ""
        else:
            _, quote_payload, _ = self._json(
                "GET", "https://data.alpaca.markets/v2/stocks/" + quote(symbol, safe="")
                + "/quotes/latest",
                headers=quote_headers,
            )
            quote_row = quote_payload.get("quote") if isinstance(quote_payload, Mapping) else None
            if (not isinstance(quote_row, Mapping)
                    or quote_payload.get("symbol") not in {None, symbol}):
                raise ProviderError("alpaca_market_quote_invalid")
            quote_asset = "USD"
        bid = _rule_decimal(quote_row.get("bp"), "alpaca_market_quote_invalid")
        ask = _rule_decimal(quote_row.get("ap"), "alpaca_market_quote_invalid")
        if ask < bid:
            raise ProviderError("alpaca_market_quote_invalid")
        market_price = ask if order.get("side") == "BUY" else bid
        notional = self._notional_evidence(
            order,
            market_price=market_price,
            quote_asset=quote_asset,
            unit_multiplier="1",
            observed_at=quote_row.get("t"),
            provider_observation={"asset": dict(asset), "quote": dict(quote_payload)},
            max_order_usd=max_order_usd,
        )
        return {
            "venue": "alpaca", "symbol": str(asset["symbol"]), "status": "active", "tradable": True,
            "asset_class": asset_class,
            "fractionable": fractionable, "min_order_size": _decimal_text(minimum),
            "min_trade_increment": _decimal_text(increment),
            "price_increment": _decimal_text(price_increment) if price_increment is not None else None,
            "notional_evidence": notional,
        }

    def _preflight_binance(
        self, order: Mapping[str, Any], *, max_order_usd: float,
    ) -> dict[str, Any]:
        _, symbol, order_type, quantity, _, limit_price = self._order_values(order)
        compact = re.sub(r"[/_.-]", "", symbol)
        _, value, _ = self._json(
            "GET", "https://api.binance.com/api/v3/exchangeInfo", params={"symbol": compact},
        )
        symbols = value.get("symbols") if isinstance(value, Mapping) else None
        if not isinstance(symbols, list) or len(symbols) != 1 or not isinstance(symbols[0], Mapping):
            raise ProviderError("binance_instrument_response_invalid")
        instrument = symbols[0]
        if instrument.get("symbol") != compact:
            raise ProviderError("binance_instrument_response_invalid")
        if instrument.get("status") != "TRADING" or instrument.get("isSpotTradingAllowed") is not True:
            raise ProviderError("binance_instrument_not_tradable")
        order_types = instrument.get("orderTypes")
        if (not isinstance(order_types, list) or not order_types
                or any(not isinstance(value, str) for value in order_types)
                or len(set(order_types)) != len(order_types)
                or order_type not in order_types):
            raise ProviderError("binance_order_type_unavailable")
        quote_asset = instrument.get("quoteAsset")
        if not isinstance(quote_asset, str) or quote_asset not in _USD_QUOTES:
            raise ProviderError("binance_quote_asset_not_usd_bound")
        rows = instrument.get("filters")
        if not isinstance(rows, list):
            raise ProviderError("binance_instrument_response_invalid")
        filters: dict[str, Mapping[str, Any]] = {}
        for row in rows:
            if not isinstance(row, Mapping):
                raise ProviderError("binance_instrument_response_invalid")
            filter_type = row.get("filterType")
            if (not isinstance(filter_type, str) or not re.fullmatch(r"[A-Z_]{3,40}", filter_type)
                    or filter_type in filters):
                raise ProviderError("binance_instrument_response_invalid")
            filters[filter_type] = row
        if "LOT_SIZE" not in filters or not ({"MIN_NOTIONAL", "NOTIONAL"} & set(filters)):
            raise ProviderError("binance_instrument_rules_incomplete")
        quantity_rules = {
            "LOT_SIZE": self._quantity_filter(
                quantity, filters["LOT_SIZE"], prefix="binance_lot", venue="binance",
            ),
        }
        if order_type == "MARKET" and "MARKET_LOT_SIZE" in filters:
            quantity_rules["MARKET_LOT_SIZE"] = self._quantity_filter(
                quantity, filters["MARKET_LOT_SIZE"], prefix="binance_market_lot",
                venue="binance", require_positive=False,
            )
        price_rule = None
        if order_type == "LIMIT":
            if "PRICE_FILTER" not in filters or limit_price is None:
                raise ProviderError("binance_price_rules_incomplete")
            price_rule = self._price_filter(
                limit_price, filters["PRICE_FILTER"], prefix="binance", venue="binance",
            )
        lot_minimum = Decimal(quantity_rules["LOT_SIZE"]["min"])
        lot_step = Decimal(quantity_rules["LOT_SIZE"]["step"])
        _, ticker, _ = self._json(
            "GET", "https://api.binance.com/api/v3/ticker/24hr", params={"symbol": compact},
        )
        if not isinstance(ticker, Mapping) or ticker.get("symbol") != compact:
            raise ProviderError("binance_market_quote_invalid")
        bid = _rule_decimal(ticker.get("bidPrice"), "binance_market_quote_invalid")
        ask = _rule_decimal(ticker.get("askPrice"), "binance_market_quote_invalid")
        if ask < bid:
            raise ProviderError("binance_market_quote_invalid")
        market_price = ask if order.get("side") == "BUY" else bid
        notional = self._notional_evidence(
            order,
            market_price=market_price,
            quote_asset=quote_asset,
            unit_multiplier="1",
            observed_at=ticker.get("closeTime"),
            provider_observation={"instrument": dict(instrument), "ticker": dict(ticker)},
            max_order_usd=max_order_usd,
        )
        actual_notional = Decimal(notional["actual_notional_usd"])
        notional_rules: dict[str, Any] = {}
        if "MIN_NOTIONAL" in filters:
            row = filters["MIN_NOTIONAL"]
            minimum = _rule_decimal(row.get("minNotional"), "binance_notional_rule_invalid")
            provider_applies = row.get("applyToMarket")
            if type(provider_applies) is not bool:
                raise ProviderError("binance_notional_rule_invalid")
            applies = True if order_type == "LIMIT" else provider_applies
            if applies and actual_notional < minimum:
                raise _rule_error(
                    "binance", "binance_notional_below_minimum",
                    minimum_quantity=lot_minimum, quantity_step=lot_step,
                    minimum_notional_usd=minimum,
                )
            notional_rules["MIN_NOTIONAL"] = {"min": _decimal_text(minimum), "applies": applies}
        if "NOTIONAL" in filters:
            row = filters["NOTIONAL"]
            minimum = _rule_decimal(row.get("minNotional"), "binance_notional_rule_invalid", zero=True)
            maximum = _rule_decimal(row.get("maxNotional"), "binance_notional_rule_invalid", zero=True)
            provider_min_applies = row.get("applyMinToMarket")
            provider_max_applies = row.get("applyMaxToMarket")
            if (type(provider_min_applies) is not bool or type(provider_max_applies) is not bool
                    or (maximum > 0 and minimum > maximum)):
                raise ProviderError("binance_notional_rule_invalid")
            min_applies = True if order_type == "LIMIT" else provider_min_applies
            max_applies = True if order_type == "LIMIT" else provider_max_applies
            if min_applies and minimum > 0 and actual_notional < minimum:
                raise _rule_error(
                    "binance", "binance_notional_below_minimum",
                    minimum_quantity=lot_minimum, quantity_step=lot_step,
                    minimum_notional_usd=minimum,
                )
            if max_applies and maximum > 0 and actual_notional > maximum:
                raise _rule_error(
                    "binance", "binance_notional_above_maximum",
                    minimum_quantity=lot_minimum, quantity_step=lot_step,
                    minimum_notional_usd=minimum,
                )
            notional_rules["NOTIONAL"] = {
                "min": _decimal_text(minimum), "max": _decimal_text(maximum),
                "min_applies": min_applies, "max_applies": max_applies,
            }
        return {
            "venue": "binance", "symbol": compact, "status": "TRADING", "quote_asset": quote_asset,
            "order_type": order_type, "quantity_rules": quantity_rules,
            "notional_rules": notional_rules, "price_rule": price_rule,
            "notional_evidence": notional,
        }

    def _preflight_kraken(
        self, order: Mapping[str, Any], *, max_order_usd: float,
    ) -> dict[str, Any]:
        _, symbol, order_type, quantity, _, limit_price = self._order_values(order)
        _, value, _ = self._json(
            "GET", "https://api.kraken.com/0/public/AssetPairs",
            params={"pair": symbol, "assetVersion": 1},
        )
        result = value.get("result") if isinstance(value, Mapping) and value.get("error") == [] else None
        if not isinstance(result, Mapping) or len(result) != 1:
            raise ProviderError("kraken_instrument_response_invalid")
        pair_name, rules = next(iter(result.items()))
        if not isinstance(pair_name, str) or not isinstance(rules, Mapping):
            raise ProviderError("kraken_instrument_response_invalid")
        aliases = (pair_name, rules.get("altname"), rules.get("wsname"))
        if _symbol_key(symbol) not in {_symbol_key(alias) for alias in aliases}:
            raise ProviderError("kraken_instrument_response_invalid")
        if rules.get("status") != "online":
            raise ProviderError("kraken_instrument_not_tradable")
        if rules.get("lot") != "unit" or _rule_decimal(
                rules.get("lot_multiplier"), "kraken_lot_rule_invalid") != Decimal("1"):
            raise ProviderError("kraken_lot_rule_invalid")
        lot_decimals = rules.get("lot_decimals")
        if type(lot_decimals) is not int or not 0 <= lot_decimals <= 18:
            raise ProviderError("kraken_lot_rule_invalid")
        step = Decimal(1).scaleb(-lot_decimals)
        minimum = _rule_decimal(rules.get("ordermin"), "kraken_order_minimum_invalid")
        cost_minimum = _rule_decimal(rules.get("costmin"), "kraken_cost_minimum_invalid")
        if quantity < minimum:
            raise _rule_error(
                "kraken", "kraken_quantity_below_minimum",
                minimum_quantity=minimum, quantity_step=step,
                minimum_notional_usd=cost_minimum,
            )
        if not _step_aligned(quantity, step):
            raise _rule_error(
                "kraken", "kraken_quantity_increment_invalid",
                minimum_quantity=minimum, quantity_step=step,
                minimum_notional_usd=cost_minimum,
            )
        quote_asset = rules.get("quote")
        if not isinstance(quote_asset, str):
            raise ProviderError("kraken_instrument_response_invalid")
        if _symbol_key(quote_asset) not in _USD_QUOTES:
            raise ProviderError("kraken_quote_asset_not_usd_bound")
        price_step = None
        if order_type == "LIMIT":
            if "tick_size" in rules:
                price_step = _rule_decimal(rules.get("tick_size"), "kraken_price_rule_invalid")
            else:
                pair_decimals = rules.get("pair_decimals")
                if type(pair_decimals) is not int or not 0 <= pair_decimals <= 18:
                    raise ProviderError("kraken_price_rule_invalid")
                price_step = Decimal(1).scaleb(-pair_decimals)
            if limit_price is None or not _step_aligned(limit_price, price_step):
                raise _rule_error(
                    "kraken", "kraken_price_increment_invalid",
                    minimum_quantity=minimum, quantity_step=step,
                    minimum_notional_usd=cost_minimum, price_step=price_step,
                )
        _, ticker_payload, _ = self._json(
            "GET", "https://api.kraken.com/0/public/Ticker", params={"pair": symbol},
        )
        ticker_result = (
            ticker_payload.get("result")
            if isinstance(ticker_payload, Mapping) and ticker_payload.get("error") == [] else None
        )
        if not isinstance(ticker_result, Mapping) or len(ticker_result) != 1:
            raise ProviderError("kraken_market_quote_invalid")
        ticker_pair, ticker = next(iter(ticker_result.items()))
        if (_symbol_key(ticker_pair) not in {_symbol_key(alias) for alias in aliases}
                or not isinstance(ticker, Mapping)):
            raise ProviderError("kraken_market_quote_invalid")
        asks = ticker.get("a")
        bids = ticker.get("b")
        if (not isinstance(asks, list) or not asks or not isinstance(bids, list) or not bids):
            raise ProviderError("kraken_market_quote_invalid")
        ask = _rule_decimal(asks[0], "kraken_market_quote_invalid")
        bid = _rule_decimal(bids[0], "kraken_market_quote_invalid")
        if ask < bid:
            raise ProviderError("kraken_market_quote_invalid")
        _, time_payload, _ = self._json("GET", "https://api.kraken.com/0/public/Time")
        provider_time = (
            time_payload.get("result", {}).get("unixtime")
            if isinstance(time_payload, Mapping) and time_payload.get("error") == [] else None
        )
        market_price = ask if order.get("side") == "BUY" else bid
        notional = self._notional_evidence(
            order,
            market_price=market_price,
            quote_asset=str(quote_asset),
            unit_multiplier="1",
            observed_at=provider_time,
            provider_observation={
                "instrument": {"pair": pair_name, "rules": dict(rules)},
                "ticker": dict(ticker_payload),
                "provider_time": dict(time_payload),
            },
            max_order_usd=max_order_usd,
        )
        if Decimal(notional["actual_notional_usd"]) < cost_minimum:
            raise _rule_error(
                "kraken", "kraken_notional_below_minimum",
                minimum_quantity=minimum, quantity_step=step,
                minimum_notional_usd=cost_minimum,
            )
        return {
            "venue": "kraken", "pair": pair_name, "status": "online", "quote_asset": quote_asset,
            "order_minimum": _decimal_text(minimum), "cost_minimum": _decimal_text(cost_minimum),
            "lot_decimals": lot_decimals, "quantity_step": _decimal_text(step),
            "price_step": _decimal_text(price_step) if price_step is not None else None,
            "notional_evidence": notional,
        }

    @staticmethod
    def _capital_size_rule(
        rules: Mapping[str, Any], name: str, *, required: bool = True,
    ) -> tuple[Decimal, str] | None:
        row = rules.get(name)
        if row is None and not required:
            return None
        if (not isinstance(row, Mapping) or not isinstance(row.get("unit"), str)
                or re.fullmatch(r"[A-Z_]{2,32}", row["unit"]) is None):
            raise ProviderError("capital_dealing_rules_invalid")
        return _rule_decimal(row.get("value"), "capital_dealing_rules_invalid"), row["unit"]

    def _preflight_capital(
        self, order: Mapping[str, Any], credentials: Mapping[str, str], *, max_order_usd: float,
    ) -> dict[str, Any]:
        _, symbol, order_type, quantity, _, _ = self._order_values(order)
        headers = self._capital_session(credentials)
        _, value, _ = self._json(
            "GET", "https://api-capital.backend-capital.com/api/v1/markets/" + quote(symbol, safe=""),
            headers=headers,
        )
        instrument = value.get("instrument") if isinstance(value, Mapping) else None
        snapshot = value.get("snapshot") if isinstance(value, Mapping) else None
        rules = value.get("dealingRules") if isinstance(value, Mapping) else None
        if not isinstance(instrument, Mapping) or not isinstance(snapshot, Mapping) or not isinstance(rules, Mapping):
            raise ProviderError("capital_instrument_response_invalid")
        if instrument.get("epic") != symbol:
            raise ProviderError("capital_instrument_response_invalid")
        if snapshot.get("marketStatus") != "TRADEABLE":
            raise ProviderError("capital_instrument_not_tradable")
        minimum_row = self._capital_size_rule(rules, "minDealSize")
        if minimum_row is None:
            raise ProviderError("capital_dealing_rules_invalid")
        minimum, minimum_unit = minimum_row
        maximum_row = self._capital_size_rule(rules, "maxDealSize", required=False)
        increment_row = self._capital_size_rule(rules, "minSizeIncrement", required=False)
        maximum = maximum_row[0] if maximum_row is not None else None
        increment = increment_row[0] if increment_row is not None else None
        optional_units = {
            row[1] for row in (maximum_row, increment_row) if row is not None
        }
        if (optional_units - {minimum_unit}
                or (maximum is not None and minimum > maximum)):
            raise ProviderError("capital_dealing_rules_invalid")
        if quantity < minimum:
            raise _rule_error(
                "capital", "capital_quantity_below_minimum",
                minimum_quantity=minimum, quantity_step=increment,
                quantity_unit=minimum_unit,
            )
        if maximum is not None and quantity > maximum:
            raise _rule_error(
                "capital", "capital_quantity_above_maximum",
                minimum_quantity=minimum, quantity_step=increment,
                quantity_unit=minimum_unit,
            )
        if increment is not None and not _step_aligned(quantity, increment):
            raise _rule_error(
                "capital", "capital_quantity_increment_invalid",
                minimum_quantity=minimum, quantity_step=increment,
                quantity_unit=minimum_unit,
            )
        preference = rules.get("marketOrderPreference")
        if preference not in {
                "AVAILABLE_DEFAULT_ON", "AVAILABLE_DEFAULT_OFF", "NOT_AVAILABLE"}:
            raise ProviderError("capital_dealing_rules_invalid")
        if order_type == "MARKET" and preference == "NOT_AVAILABLE":
            raise _rule_error(
                "capital", "capital_market_order_unavailable",
                minimum_quantity=minimum, quantity_step=increment,
                quantity_unit=minimum_unit,
            )
        currency = instrument.get("currency")
        lot_size = instrument.get("lotSize")
        if currency != "USD":
            raise ProviderError("capital_notional_currency_conversion_unavailable")
        bid = _rule_decimal(snapshot.get("bid"), "capital_market_quote_invalid")
        offer = _rule_decimal(snapshot.get("offer"), "capital_market_quote_invalid")
        if offer < bid:
            raise ProviderError("capital_market_quote_invalid")
        market_price = offer if order.get("side") == "BUY" else bid
        notional = self._notional_evidence(
            order,
            market_price=market_price,
            quote_asset=currency,
            unit_multiplier=lot_size,
            observed_at=snapshot.get("updateTimeUTC"),
            provider_observation=dict(value),
            max_order_usd=max_order_usd,
        )
        return {
            "venue": "capital", "epic": symbol, "market_status": "TRADEABLE",
            "order_type": order_type, "size_unit": minimum_unit, "currency": currency,
            "lot_size": _decimal_text(_rule_decimal(lot_size, "capital_notional_unit_conversion_unavailable")),
            "min_deal_size": _decimal_text(minimum),
            "max_deal_size": _decimal_text(maximum) if maximum is not None else None,
            "min_size_increment": _decimal_text(increment) if increment is not None else None,
            "market_order_preference": preference if order_type == "MARKET" else None,
            "notional_evidence": notional,
        }

    def preflight_order(
        self, order: Mapping[str, Any], credentials: Mapping[str, str], *, max_order_usd: float,
    ) -> dict[str, Any]:
        """Validate exact provider sizing metadata without mutating an exchange."""
        venue, *_ = self._order_values(order)
        try:
            if venue == "alpaca":
                rules = self._preflight_alpaca(
                    order, credentials, max_order_usd=max_order_usd,
                )
            elif venue == "binance":
                rules = self._preflight_binance(order, max_order_usd=max_order_usd)
            elif venue == "kraken":
                rules = self._preflight_kraken(order, max_order_usd=max_order_usd)
            else:
                rules = self._preflight_capital(
                    order, credentials, max_order_usd=max_order_usd,
                )
        except KeyError:
            raise ProviderError("instrument_preflight_credentials_missing") from None
        except ProviderError as exc:
            if exc.readiness_blocker is None and str(exc).startswith(venue + "_"):
                raise ProviderError(
                    str(exc), readiness_blocker=_rule_blocker(venue, str(exc)),
                ) from None
            raise
        return self._preflight_receipt(order, rules)

    def probe_all(
        self,
        credentials: Mapping[str, str],
        *,
        maximum_order_usd: float,
        source_revision: str,
        observed_at_ms: int,
    ) -> dict[str, Any]:
        def alpaca_probe():
            _, value, _ = self._json(
                "GET", "https://api.alpaca.markets/v2/account",
                headers={"APCA-API-KEY-ID": credentials["ALPACA_API_KEY"],
                         "APCA-API-SECRET-KEY": credentials["ALPACA_SECRET_KEY"]},
            )
            return value

        def binance_probe():
            _, value, _ = self._binance(
                "GET", "/api/v3/account", credentials, {"omitZeroBalances": "true"},
            )
            return value

        def kraken_probe():
            return self._kraken("/0/private/Balance", credentials, {})

        def capital_probe():
            headers = self._capital_session(credentials)
            _, value, _ = self._json(
                "GET", "https://api-capital.backend-capital.com/api/v1/accounts",
                headers=headers,
            )
            return value

        jobs = {
            "alpaca": alpaca_probe,
            "binance": binance_probe,
            "capital": capital_probe,
            "kraken": kraken_probe,
        }
        values: dict[str, Any] = {}
        pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=4, thread_name_prefix="provider-readiness",
        )
        futures = {pool.submit(job): venue for venue, job in jobs.items()}
        try:
            for future in concurrent.futures.as_completed(
                futures, timeout=PROVIDER_PROBE_DEADLINE_SECONDS,
            ):
                values[futures[future]] = future.result()
        except concurrent.futures.TimeoutError:
            for future in futures:
                future.cancel()
            raise ProviderError("provider_probe_deadline_exceeded") from None
        finally:
            pool.shutdown(wait=False, cancel_futures=True)
        if set(values) != set(jobs):
            raise ProviderError("all_four_provider_probe_incomplete")
        alpaca = values["alpaca"]
        binance = values["binance"]
        capital = values["capital"]
        kraken = values["kraken"]
        results = {
            venue: self._evidence(venue, values[venue], account=True)
            for venue in sorted(values)
        }
        if set(results) != {"alpaca", "binance", "capital", "kraken"}:
            raise ProviderError("all_four_provider_probe_incomplete")
        readiness = self._execution_budget_readiness(
            alpaca=alpaca,
            binance=binance,
            capital=capital,
            kraken=kraken,
            maximum_order_usd=maximum_order_usd,
            source_revision=source_revision,
            observed_at_ms=observed_at_ms,
        )
        accounts_sha256 = _digest(results)
        readiness_sha256 = _digest(readiness)
        readback_sha256 = _digest({
            "schema": "aureon.cloud-trade-provider-readback-commitment.v1",
            "provider_accounts_sha256": accounts_sha256,
            "execution_budget_readiness_sha256": readiness_sha256,
        })
        return {
            "schema": "aureon.cloud-trade-provider-readback.v1",
            "providers": results,
            "provider_count": 4,
            "all_authenticated": True,
            "provider_mutation_attempted": False,
            "instrument_preflight_enforced": True,
            "provider_accounts_sha256": accounts_sha256,
            "execution_budget_readiness": readiness,
            "execution_budget_readiness_sha256": readiness_sha256,
            "readback_sha256": readback_sha256,
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


__all__ = [
    "CredentialBoundary", "ProviderBoundary", "ProviderError",
    "valid_instrument_readiness_blocker",
]
