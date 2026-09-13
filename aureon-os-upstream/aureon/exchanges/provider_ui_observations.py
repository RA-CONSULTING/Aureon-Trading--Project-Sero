"""Allowlisted read-only projections of observations already fetched by clients.

This module performs no I/O and never changes a returned provider receipt,
execution eligibility, accounting, or reconciliation state.
"""

import hashlib
import math
import time
from email.utils import parsedate_to_datetime
from functools import wraps
from threading import RLock
from typing import Any


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return result if math.isfinite(result) else None


def _reference(value: Any) -> str | None:
    return hashlib.sha256(value.encode()).hexdigest()[:16] if isinstance(value, str) and value else None


def project_capital_observation(observation: Any, kind: str, *, demo_mode: bool,
                                max_age_seconds: float = 300, now: float | None = None) -> dict:
    now = time.time() if now is None else now
    timestamp = _number(getattr(observation, "source_timestamp", None))
    received_at = _number(getattr(observation, "received_at", None))
    result = {
        "provider": "capital", "kind": kind, "source": f"capital:GET /{kind}",
        "source_timestamp": timestamp, "source_timestamp_kind": "provider_http_date",
        "received_at": received_at,
        "max_age_seconds": max_age_seconds, "generated_values": False,
        "status": "unavailable", "reason": "provider_observation_unavailable", "rows": [],
        "observed_count": None, "inventory_complete": None,
    }
    if demo_mode:
        result["reason"] = "demo_provider_observation_excluded"
        return result
    if (timestamp is None or timestamp <= 0 or received_at is None or received_at <= 0
            or timestamp > now + 5 or received_at > now + 5
            or now - timestamp > max_age_seconds or now - received_at > max_age_seconds):
        result["reason"] = "provider_timestamp_missing_or_stale"
        return result
    if (not isinstance(observation, list) or getattr(observation, "truth_status", "no_data") == "no_data"
            or getattr(observation, "generated_values", None) is not False):
        return result
    rows = []
    for raw in observation:
        if not isinstance(raw, dict) or raw.get("truth_status") != "real_observed" or raw.get("generated_values") is not False:
            continue
        if kind == "accounts":
            balance, available = _number(raw.get("balance")), _number(raw.get("available"))
            currency = raw.get("currency")
            row_timestamp = _number(raw.get("source_timestamp"))
            if balance is None or available is None or not isinstance(currency, str) or not currency:
                continue
            if row_timestamp != timestamp:
                continue
            rows.append({
                "reference": _reference(raw.get("source_id")), "currency": currency,
                "balance": balance, "available": available, "account_status": raw.get("status"),
                "source_timestamp": row_timestamp, "received_at": _number(raw.get("received_at")),
            })
        elif kind == "positions":
            position = raw.get("position") if isinstance(raw.get("position"), dict) else {}
            market = raw.get("market") if isinstance(raw.get("market"), dict) else {}
            quantity, entry_price = _number(position.get("size")), _number(position.get("level"))
            currency = position.get("currency")
            row_timestamp = _number(raw.get("receipt_source_timestamp"))
            if quantity is None or quantity <= 0 or entry_price is None or entry_price <= 0:
                continue
            if row_timestamp != timestamp or not isinstance(currency, str) or not currency:
                continue
            rows.append({
                "reference": _reference(raw.get("source_id")),
                "symbol": market.get("epic") if isinstance(market.get("epic"), str) else None,
                "side": position.get("direction") if position.get("direction") in {"BUY", "SELL"} else None,
                "quantity": quantity, "entry_price": entry_price, "currency": currency,
                "opened_at": _number(raw.get("source_timestamp")),
                "source_timestamp": row_timestamp, "received_at": _number(raw.get("received_at")),
                "fill_reconciled": raw.get("terminal_fill_receipt_complete") is True,
            })
    complete = len(rows) == len(observation) and (
        getattr(observation, "inventory_complete", None) is True if kind == "positions"
        else getattr(observation, "truth_status", None) == "real_observed"
    )
    if not rows and not (kind == "positions" and complete):
        result["reason"] = "complete_provider_rows_unavailable"
        return result
    result.update({"status": "observed", "reason": "fresh_provider_readback", "rows": rows,
                   "observed_count": len(rows), "inventory_complete": complete})
    return result


def record_capital_ui_observation(kind: str, *, max_age_seconds: float = 300):
    """Retain a safe view when an existing account/position read returns."""
    def decorate(method):
        @wraps(method)
        def observed(self, *args, **kwargs):
            receipt = method(self, *args, **kwargs)
            try:
                projection = project_capital_observation(
                    receipt, kind, demo_mode=getattr(self, "demo_mode", True),
                    max_age_seconds=max_age_seconds,
                )
            except Exception:
                projection = {"provider": "capital", "kind": kind, "status": "unavailable",
                              "reason": "ui_projection_unavailable", "rows": [], "observed_count": None}
            setattr(self, f"last_ui_{kind}_observation", projection)
            return receipt
        return observed
    return decorate


_HTTP_OBSERVATION_ROUTES = {
    ("binance", "GET", "/api/v3/account"): "accounts",
    ("kraken", "POST", "/0/private/Balance"): "accounts",
    ("alpaca", "GET", "/v2/account"): "accounts",
    ("alpaca", "GET", "/v2/positions"): "positions",
}


_UI_OBSERVATION_LOCK = RLock()


def _serialize_ui_observation(method):
    """Serialize sidecar assignments only; no network operation holds this lock."""
    @wraps(method)
    def serialized(*args, **kwargs):
        with _UI_OBSERVATION_LOCK:
            return method(*args, **kwargs)
    return serialized


@_serialize_ui_observation
def begin_provider_http_observation(client: Any, provider: str, method: str, path: str,
                                    *, now: float | None = None) -> object | None:
    """Mark an existing HTTP read pending without expiring a valid prior receipt."""
    kind = _HTTP_OBSERVATION_ROUTES.get((provider, method, path))
    if kind is None:
        return None
    now = time.time() if now is None else now
    previous = getattr(client, f"last_ui_{kind}_observation", {})
    previous = previous if isinstance(previous, dict) else {}
    timestamp, received_at = _number(previous.get("source_timestamp")), _number(previous.get("received_at"))
    limit = _number(previous.get("max_age_seconds"))
    source = f"{provider}:{method} {path}"
    qualified = (previous.get("status") == "observed" and previous.get("generated_values") is False
                 and previous.get("source") == source and limit is not None and 0 < limit <= 300
                 and timestamp is not None and timestamp > 0 and received_at is not None and received_at > 0
                 and -5 <= now - timestamp <= limit and -5 <= now - received_at <= limit)
    token = object()
    setattr(client, f"_ui_{kind}_refresh_token", token)
    pending = {**previous, "provider": provider, "kind": kind, "source": source,
               "refresh_status": "pending", "generated_values": False}
    if not qualified:
        pending.update({"status": "unavailable", "reason": "provider_receipt_unavailable_refresh_pending",
                        "rows": [], "observed_count": None, "inventory_complete": None})
    setattr(client, f"last_ui_{kind}_observation", pending)
    return token


@_serialize_ui_observation
def fail_provider_http_observation(client: Any, provider: str, method: str, path: str,
                                   *, refresh_token: object | None = None) -> None:
    """A failed read invalidates its sidecar; an older overlapping read cannot."""
    kind = _HTTP_OBSERVATION_ROUTES.get((provider, method, path))
    if kind is None or (refresh_token is not None
            and getattr(client, f"_ui_{kind}_refresh_token", None) is not refresh_token):
        return
    previous = getattr(client, f"last_ui_{kind}_observation", {})
    previous = previous if isinstance(previous, dict) else {}
    setattr(client, f"last_ui_{kind}_observation", {
        **previous, "provider": provider, "kind": kind, "source": f"{provider}:{method} {path}",
        "status": "unavailable", "refresh_status": "failed", "reason": "provider_read_failed", "rows": [],
        "observed_count": None, "inventory_complete": None, "generated_values": False,
    })


def _text(value: Any) -> str | None:
    return value if isinstance(value, str) and 0 < len(value) <= 128 else None


def project_provider_http_observation(provider: str, method: str, path: str, payload: Any,
                                      *, headers: Any, received_at: float, live_endpoint: bool,
                                      max_age_seconds: float = 300) -> dict | None:
    """Project only existing successful HTTP receipts; never fetch or infer permissions.

    HTTP Date describes this response. Binance updateTime and position opening
    dates describe business events and are not substituted for snapshot time.
    If Date is absent, the actual local receipt is labelled explicitly.
    """
    kind = _HTTP_OBSERVATION_ROUTES.get((provider, method, path))
    if kind is None:
        return None
    timestamp = None
    try:
        header = headers.get("Date") or headers.get("date")
        if header:
            timestamp = parsedate_to_datetime(header).timestamp()
    except (AttributeError, TypeError, ValueError, OverflowError):
        pass
    timestamp_kind = "provider_http_date" if timestamp is not None else "local_http_receipt"
    timestamp = received_at if timestamp is None else timestamp
    result = {
        "provider": provider, "kind": kind, "source": f"{provider}:{method} {path}",
        "source_timestamp": timestamp, "source_timestamp_kind": timestamp_kind,
        "received_at": received_at, "max_age_seconds": max_age_seconds,
        "generated_values": False, "status": "unavailable", "reason": "provider_rows_unavailable",
        "rows": [], "observed_count": None, "inventory_complete": None,
    }
    if not live_endpoint:
        result["reason"] = "paper_testnet_or_noncanonical_endpoint_excluded"
        return result
    if (not _number(received_at) or received_at <= 0 or not _number(timestamp)
            or timestamp <= 0 or timestamp > received_at + 5 or received_at - timestamp > max_age_seconds):
        result["reason"] = "provider_response_timestamp_invalid_or_stale"
        return result
    rows = []
    raw_count = None
    provenance = {"source_timestamp": timestamp, "received_at": received_at}
    if provider == "binance" and isinstance(payload, dict) and isinstance(payload.get("balances"), list):
        raw_rows = payload["balances"]
        raw_count = len(raw_rows)
        update_time = _number(payload.get("updateTime"))
        result["provider_updated_at"] = update_time / 1000 if update_time is not None and update_time > 0 else None
        for raw in raw_rows:
            if not isinstance(raw, dict):
                continue
            currency = _text(raw.get("asset"))
            free, locked = _number(raw.get("free")), _number(raw.get("locked"))
            if currency is None or free is None or locked is None or free < 0 or locked < 0:
                continue
            balance = _number(free + locked)
            if balance is None:
                continue
            rows.append({"reference": _reference(f"binance:asset:{currency}"), "currency": currency,
                         "balance": balance, "balance_kind": "free_plus_locked", "available": free,
                         "locked": locked, **provenance})
    elif provider == "kraken" and isinstance(payload, dict):
        # Preserve Kraken's asset code and total Balance amount. No zero locked
        # amount or free/withdrawable cash is invented by the UI projection.
        raw_count = len(payload)
        for asset, amount in payload.items():
            currency, balance = _text(asset), _number(amount)
            if currency is None or balance is None or balance < 0:
                continue
            rows.append({"reference": _reference(f"kraken:asset:{currency}"), "currency": currency,
                         "balance": balance, "balance_kind": "total_asset_balance", "available": None,
                         **provenance})
    elif provider == "alpaca" and kind == "accounts" and isinstance(payload, dict):
        currency, equity = _text(payload.get("currency")), _number(payload.get("equity"))
        if currency is not None and equity is not None:
            raw_count = 1
            rows.append({"reference": _reference(payload.get("id")), "currency": currency,
                         "balance": equity, "balance_kind": "equity", "available": None,
                         "cash": _number(payload.get("cash")), "buying_power": _number(payload.get("buying_power")),
                         "account_status": _text(payload.get("status")), **provenance})
    elif provider == "alpaca" and kind == "positions" and isinstance(payload, list):
        raw_count = len(payload)
        for raw in payload:
            if not isinstance(raw, dict):
                continue
            symbol, quantity, entry_price = _text(raw.get("symbol")), _number(raw.get("qty")), _number(raw.get("avg_entry_price"))
            if symbol is None or quantity is None or quantity == 0 or entry_price is None or entry_price <= 0:
                continue
            rows.append({"reference": _reference(raw.get("asset_id")), "symbol": symbol,
                         "side": {"long": "BUY", "short": "SELL"}.get(raw.get("side")),
                         "quantity": abs(quantity), "entry_price": entry_price,
                         # Do not assume account USD or convert currencies.
                         "currency": _text(raw.get("currency")), "fill_reconciled": False, **provenance})
    if raw_count is None or (not rows and raw_count > 0):
        return result
    result.update({"status": "observed", "reason": "existing_http_provider_readback", "rows": rows,
                   "observed_count": len(rows), "inventory_complete": len(rows) == raw_count})
    return result


@_serialize_ui_observation
def record_provider_http_observation(client: Any, provider: str, method: str, path: str,
                                     payload: Any, *, headers: Any, received_at: float,
                                     live_endpoint: bool, refresh_token: object | None = None) -> None:
    """Best-effort display sidecar; the original client result stays unchanged."""
    kind = _HTTP_OBSERVATION_ROUTES.get((provider, method, path))
    if kind is None or (refresh_token is not None
            and getattr(client, f"_ui_{kind}_refresh_token", None) is not refresh_token):
        return
    try:
        observation = project_provider_http_observation(provider, method, path, payload,
            headers=headers, received_at=received_at, live_endpoint=live_endpoint)
        if observation is not None:
            observation["refresh_status"] = "succeeded" if observation.get("status") == "observed" else "failed"
            setattr(client, f"last_ui_{observation['kind']}_observation", observation)
    except Exception:
        fail_provider_http_observation(client, provider, method, path, refresh_token=refresh_token)


def client_ui_observations(client: Any) -> dict:
    """Read already-sanitized sidecars without calling a provider or refreshing ages."""
    return {kind: value for kind in ("accounts", "positions")
            if isinstance(value := getattr(client, f"last_ui_{kind}_observation", None), dict)}
