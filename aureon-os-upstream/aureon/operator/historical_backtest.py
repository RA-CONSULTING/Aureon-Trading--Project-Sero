"""Bounded historical analysis over actual Kraken OHLC; never an exchange order path.

The legacy replay engines import live traders or write learning state. This adapter
uses their public Kraken dataset convention, with a separate explicit momentum
baseline and request-local accounting. No live HNC, Lighthouse or Prism values are
invented. No files, credentials, account balances, trade clients or message buses
are read or written. Registration does not replace the operator's ingress gate.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import statistics
import subprocess
import sys
import threading
import time
import urllib.parse
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

from aureon.core.no_external_calls import no_external_api_calls

SERVICE = "aureon-historical-backtest"
STRATEGY = "momentum_next_open_v1"
CAPABILITY_PATH = "/api/trading/backtest/capabilities"
REPLAY_PATH = "/api/trading/backtest"
PROVIDER_URL = "https://api.kraken.com/0/public/OHLC"
MAX_RESPONSE_BYTES = 512 * 1024
MAX_REQUEST_BYTES = 16 * 1024
MAX_PROVIDER_ROWS = 721
MAX_REPLAY_CANDLES = 672
MAX_CONCURRENT_REPLAYS = 2
SOURCE_PROCESS_TIMEOUT_SECONDS = 15.0
SOURCE_PROCESS_CLEANUP_SECONDS = 2.0
PAIRS = {
    "BTCUSD": ("XBTUSD", frozenset({"XXBTZUSD", "XBTUSD", "BTCUSD"})),
    "ETHUSD": ("ETHUSD", frozenset({"XETHZUSD", "ETHUSD"})),
    "SOLUSD": ("SOLUSD", frozenset({"SOLUSD"})),
}
CONFIG_KEYS = frozenset({"symbol", "startDate", "endDate", "initialCapital", "tradeSize", "stopLoss", "takeProfit",
                         "strategy", "intervalMinutes", "lookbackPeriods", "feeBps", "slippageBps"})
ASSUMPTIONS = [
    "Long/flat momentum baseline: decide using completed closes, enter or exit at the next candle open.",
    "Entry eligibility uses positive volume from the previous completed candle; current-bar volume is never known at its open.",
    "One position, no leverage. Allocation includes entry fees; fees and slippage are user assumptions, not an account fee quote.",
    "Stops/take-profits use OHLC bounds; a bar touching both exits uses the stop first. Gaps through stops use the opening price.",
    "Any open replay position closes at the final candle close. Drawdown uses closing equity observations.",
    "Sharpe uses sample standard deviation, zero risk-free rate and a 365-day crypto calendar; undefined ratios remain unavailable.",
    "Replay fills are hypothetical calculations on real candles. They are not observed provider fills or a live performance claim.",
    "Historical HNC/Lighthouse/Prism/LHE replay is unavailable without a separately timestamped signal ledger.",
]


class BacktestError(ValueError):
    def __init__(self, reason: str, *, code: str = "invalid_request", status: int = 400):
        super().__init__(reason)
        self.code, self.status = code, status


@dataclass(frozen=True)
class Candle:
    ts: int
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(frozen=True)
class Dataset:
    symbol: str
    interval_minutes: int
    candles: tuple[Candle, ...]
    source_url: str
    fetched_at: float
    sha256: str


def _iso(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, timezone.utc).isoformat().replace("+00:00", "Z")


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def account_scope(kind: Any, tenant: Any) -> str:
    """Only an already verified operator identity may bind an analysis request."""
    if kind == "admin":
        subject = "operator-admin"
    elif kind == "tenant" and isinstance(tenant, str) and 0 < len(tenant) <= 200:
        subject = "tenant:" + tenant
    else:
        raise BacktestError("Sign in with an authenticated operator or account identity before replaying.", code="authentication_required", status=401)
    return hashlib.sha256((SERVICE + ":" + subject).encode()).hexdigest()


def validate_config(value: Any, *, now: float | None = None) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != CONFIG_KEYS:
        raise BacktestError("Configuration must contain exactly the supported momentum replay fields.")
    config = dict(value)
    if config["strategy"] != STRATEGY or config["symbol"] not in PAIRS:
        raise BacktestError("Unsupported strategy or Kraken USD pair.")
    numeric = {"initialCapital": (10, 1_000_000_000), "tradeSize": (0.01, 1), "stopLoss": (0.1, 50),
               "takeProfit": (0.1, 100), "feeBps": (0, 1000), "slippageBps": (0, 1000), "lookbackPeriods": (2, 100)}
    for name, (low, high) in numeric.items():
        number = config[name]
        if isinstance(number, bool) or not isinstance(number, (int, float)) or not math.isfinite(number) or not low <= number <= high:
            raise BacktestError(f"Invalid {name}; expected a finite value between {low} and {high}.")
    if int(config["lookbackPeriods"]) != config["lookbackPeriods"]:
        raise BacktestError("lookbackPeriods must be a whole number.")
    if type(config["intervalMinutes"]) is not int or config["intervalMinutes"] not in (60, 1440):
        raise BacktestError("Only 60-minute or daily candles are supported.")
    dates = []
    for field in ("startDate", "endDate"):
        text = config[field]
        if not isinstance(text, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
            raise BacktestError(f"{field} must be a UTC calendar date.")
        try:
            dates.append(datetime.strptime(text, "%Y-%m-%d").replace(tzinfo=timezone.utc))
        except ValueError as exc:
            raise BacktestError(f"{field} is invalid.") from exc
    if dates[1] < dates[0]:
        raise BacktestError("End date must be on or after the start date.")
    end = dates[1] + timedelta(days=1)
    if end.timestamp() > (time.time() if now is None else now):
        raise BacktestError("Only complete historical UTC days may be replayed.")
    bars = int((end - dates[0]).total_seconds() / (config["intervalMinutes"] * 60))
    if bars > MAX_REPLAY_CANDLES or bars + config["lookbackPeriods"] + 1 > 719:
        raise BacktestError("Requested range plus warm-up exceeds the bounded Kraken history window.", code="range_too_large")
    return config


def _window(config: Mapping[str, Any]) -> tuple[int, int]:
    start = int(datetime.strptime(config["startDate"], "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp())
    end = int((datetime.strptime(config["endDate"], "%Y-%m-%d").replace(tzinfo=timezone.utc) + timedelta(days=1)).timestamp())
    return start, end


def parse_kraken_dataset(raw: bytes, *, symbol: str, interval_minutes: int, fetched_at: float, source_url: str) -> Dataset:
    if len(raw) > MAX_RESPONSE_BYTES:
        raise BacktestError("Provider response exceeded the size limit.", code="source_too_large", status=502)
    try:
        payload = json.loads(raw)
    except (ValueError, UnicodeError) as exc:
        raise BacktestError("Provider response was not valid JSON.", code="invalid_source", status=502) from exc
    if not isinstance(payload, dict) or payload.get("error") != [] or not isinstance(payload.get("result"), dict):
        raise BacktestError("Kraken did not return a successful OHLC response.", code="source_unavailable", status=502)
    result = payload["result"]
    keys = [key for key in result if key != "last"]
    if len(keys) != 1 or keys[0] not in PAIRS[symbol][1]:
        raise BacktestError("Provider pair identity did not match the request.", code="source_pair_mismatch", status=502)
    rows = result[keys[0]]
    if not isinstance(rows, list) or not 2 <= len(rows) <= MAX_PROVIDER_ROWS:
        raise BacktestError("Provider candle count is invalid.", code="invalid_source", status=502)
    candles: list[Candle] = []
    previous = -1
    step = interval_minutes * 60
    for row in rows:
        if not isinstance(row, list) or len(row) < 8:
            raise BacktestError("Provider candle shape is invalid.", code="invalid_source", status=502)
        try:
            numbers = [float(row[index]) for index in (0, 1, 2, 3, 4, 6)]
        except (ValueError, TypeError, OverflowError) as exc:
            raise BacktestError("Provider candle contains a non-numeric field.", code="invalid_source", status=502) from exc
        ts, opening, high, low, close, volume = numbers
        if any(isinstance(row[index], bool) for index in (0, 1, 2, 3, 4, 6)) or not all(math.isfinite(n) for n in numbers):
            raise BacktestError("Provider candle contains non-finite values.", code="invalid_source", status=502)
        if ts != int(ts) or ts % step or ts <= previous or ts > fetched_at:
            raise BacktestError("Provider candle timestamps are misaligned, future, duplicate or unordered.", code="invalid_source", status=502)
        if not (0 < low <= min(opening, close) <= max(opening, close) <= high) or volume < 0:
            raise BacktestError("Provider candle violates OHLC or volume integrity.", code="invalid_source", status=502)
        previous = int(ts)
        candles.append(Candle(int(ts), opening, high, low, close, volume))
    # Kraken explicitly documents the last entry as the current uncommitted candle.
    completed = tuple(candle for candle in candles[:-1] if candle.ts + step <= fetched_at)
    if not completed:
        raise BacktestError("No completed provider candles were returned.", code="source_unavailable", status=502)
    return Dataset(symbol, interval_minutes, completed, source_url, fetched_at, hashlib.sha256(raw).hexdigest())


def _run_source_worker(command: list[str], *, timeout_seconds: float = SOURCE_PROCESS_TIMEOUT_SECONDS) -> bytes:
    """A process deadline, independent of every network parser/receive loop.

    The production caller supplies one fixed isolated Python script, never user
    commands. Loopback tests use this internal seam to exercise slow framing.
    Child creation is an OS operation; the deadline starts before creation and
    all remaining runtime is bounded. A timed-out child is killed and reaped
    with a separately bounded cleanup window, never a lingering fetch thread.
    """
    if not math.isfinite(timeout_seconds) or not 0 < timeout_seconds <= SOURCE_PROCESS_TIMEOUT_SECONDS:
        raise BacktestError("Invalid isolated source timeout.", code="invalid_source_budget")
    child_env = {key: os.environ[key] for key in ("SYSTEMROOT", "WINDIR", "TEMP", "TMP", "AUREON_NO_EXTERNAL_API_CALLS") if key in os.environ}
    deadline = time.monotonic() + timeout_seconds
    try:
        process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   env=child_env, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except OSError as exc:
        raise BacktestError("Isolated historical source worker could not start.", code="source_worker_unavailable", status=503) from exc
    try:
        raw, diagnostics = process.communicate(timeout=max(0.001, deadline - time.monotonic()))
    except subprocess.TimeoutExpired as exc:
        try:
            process.kill()
            process.communicate(timeout=SOURCE_PROCESS_CLEANUP_SECONDS)
        except (OSError, subprocess.TimeoutExpired) as cleanup:
            raise BacktestError("Historical source timed out and worker cleanup could not be confirmed.", code="source_worker_cleanup_failed", status=503) from cleanup
        raise BacktestError("Public source exceeded the isolated worker deadline and was terminated.", code="source_timeout", status=504) from exc
    if process.returncode != 0:
        code = "source_unavailable"
        if len(diagnostics) <= 1024:
            try:
                supplied = json.loads(diagnostics).get("reason_code")
                if supplied in {"source_too_large", "source_redirect_refused", "external_reads_held"}:
                    code = supplied
            except (ValueError, AttributeError):
                pass
        raise BacktestError(f"Public historical source unavailable ({code}).", code=code, status=503 if code == "external_reads_held" else 502)
    if time.monotonic() > deadline:
        raise BacktestError("Public source completed outside its isolated worker deadline.", code="source_timeout", status=504)
    if len(raw) > MAX_RESPONSE_BYTES:
        raise BacktestError("Public candle source exceeded its response bound.", code="source_too_large", status=502)
    return raw


def fetch_kraken_dataset(config: Mapping[str, Any]) -> Dataset:
    if no_external_api_calls():
        raise BacktestError("Public source reads are held by AUREON_NO_EXTERNAL_API_CALLS.", code="external_reads_held", status=503)
    start, _ = _window(config)
    step = config["intervalMinutes"] * 60
    since = start - (int(config["lookbackPeriods"]) + 2) * step
    query = urllib.parse.urlencode({"pair": PAIRS[config["symbol"]][0], "interval": config["intervalMinutes"],
                                    "since": since})
    url = PROVIDER_URL + "?" + query
    worker = Path(__file__).with_name("historical_source_worker.py")
    raw = _run_source_worker([sys.executable, "-I", "-S", "-B", str(worker), "--symbol", config["symbol"],
                              "--interval-minutes", str(config["intervalMinutes"]), "--since", str(since)])
    return parse_kraken_dataset(raw, symbol=config["symbol"], interval_minutes=config["intervalMinutes"],
                                fetched_at=time.time(), source_url=url)


def run_replay(dataset: Dataset, configuration: Mapping[str, Any], *, now: float | None = None) -> dict[str, Any]:
    """Request-local arithmetic only. Input candles are real source records; fills are modeled."""
    config = validate_config(dict(configuration), now=now)
    if dataset.symbol != config["symbol"] or dataset.interval_minutes != config["intervalMinutes"]:
        raise BacktestError("Dataset identity or cadence does not match the requested replay.", code="source_pair_mismatch")
    start, end = _window(config)
    step, lookback = config["intervalMinutes"] * 60, int(config["lookbackPeriods"])
    needed = start - (lookback + 1) * step
    candles = [candle for candle in dataset.candles if needed <= candle.ts < end]
    expected = list(range(needed, end, step))
    if [candle.ts for candle in candles] != expected:
        raise BacktestError("Requested range or warm-up is not completely covered by current provider history. Choose a covered range; gaps are never interpolated.", code="historical_range_unavailable", status=422)
    if not math.isfinite(dataset.fetched_at) or not end <= dataset.fetched_at <= (time.time() if now is None else now):
        raise BacktestError("Dataset fetch time is invalid.", code="invalid_source")
    capital = float(config["initialCapital"])
    cash, quantity = capital, 0.0
    fee, slip = config["feeBps"] / 10000, config["slippageBps"] / 10000
    entry: dict[str, Any] | None = None
    trades: list[dict[str, Any]] = []
    equity = [{"date": _iso(start), "equity": capital}]

    def exit_position(raw_price: float, timestamp: int, reason: str) -> None:
        nonlocal cash, quantity, entry
        assert entry is not None
        price = raw_price * (1 - slip)
        proceeds = quantity * price
        exit_fee = proceeds * fee
        cash += proceeds - exit_fee
        pnl = proceeds - exit_fee - entry["entryCost"]
        trades.append({"id": f"replay-{len(trades) + 1}", "kind": "hypothetical_historical_fill", "symbol": config["symbol"],
                       "side": "long", "openedAt": entry["openedAt"], "closedAt": _iso(timestamp), "entryPrice": entry["price"],
                       "exitPrice": price, "quantity": quantity, "entryFee": entry["fee"], "exitFee": exit_fee,
                       "pnl": pnl, "returnPct": pnl / entry["entryCost"] * 100, "closeReason": reason, "currency": "USD"})
        quantity, entry = 0.0, None

    for index in range(lookback + 1, len(candles)):
        candle = candles[index]
        momentum_positive = candles[index - 1].close > candles[index - 1 - lookback].close
        if entry is not None and not momentum_positive:
            exit_position(candle.open, candle.ts, "momentum_exit")
        elif entry is None and momentum_positive and candles[index - 1].volume > 0:
            budget = cash * config["tradeSize"]
            price = candle.open * (1 + slip)
            quantity = budget / (price * (1 + fee))
            entry = {"openedAt": _iso(candle.ts), "price": price, "fee": quantity * price * fee, "entryCost": budget}
            cash -= budget
        if entry is not None:
            stop = entry["price"] * (1 - config["stopLoss"] / 100)
            take = entry["price"] * (1 + config["takeProfit"] / 100)
            if candle.open <= stop:
                exit_position(candle.open, candle.ts, "stop_gap")
            elif candle.low <= stop:
                exit_position(stop, candle.ts + step, "stop_loss_ohlc_assumption")
            elif candle.high >= take:
                exit_position(take, candle.ts + step, "take_profit_ohlc_assumption")
            elif index == len(candles) - 1:
                exit_position(candle.close, candle.ts + step, "end_of_window")
        amount = cash + quantity * candle.close
        if not math.isfinite(amount) or amount < 0:
            raise BacktestError("Replay accounting produced an invalid amount.", code="invalid_accounting", status=422)
        equity.append({"date": _iso(candle.ts + step), "equity": amount})
    wins = [trade for trade in trades if trade["pnl"] > 0]
    losses = [trade for trade in trades if trade["pnl"] < 0]
    peak, drawdown = capital, 0.0
    for point in equity:
        peak = max(peak, point["equity"])
        drawdown = max(drawdown, (peak - point["equity"]) / peak * 100)
    changes = [b["equity"] / a["equity"] - 1 for a, b in zip(equity, equity[1:]) if a["equity"] > 0]
    deviation = statistics.stdev(changes) if len(changes) > 1 else 0.0
    sharpe = statistics.mean(changes) / deviation * math.sqrt(365 * 1440 / config["intervalMinutes"]) if deviation > 0 else None
    results = {"totalTrades": len(trades), "winRate": len(wins) / len(trades) * 100 if trades else None,
               "totalReturn": (equity[-1]["equity"] / capital - 1) * 100, "maxDrawdown": drawdown, "sharpeRatio": sharpe,
               "profitFactor": sum(trade["pnl"] for trade in wins) / -sum(trade["pnl"] for trade in losses) if losses else None,
               "avgWin": statistics.mean(trade["returnPct"] for trade in wins) if wins else None,
               "avgLoss": statistics.mean(trade["returnPct"] for trade in losses) if losses else None,
               "equityCurve": equity, "trades": trades}
    return {"config": config, "results": results, "provenance": {"generated": False, "execution_mode": "historical_replay",
            "source": "Kraken public OHLC", "source_at": _iso(end), "fetched_at": _iso(dataset.fetched_at),
            "source_url": dataset.source_url, "dataset_sha256": dataset.sha256, "currency": "USD", "provider_fills": False,
            "strategy": STRATEGY, "candle_count": len(equity) - 1, "warmup_candles": lookback + 1,
            "interval_minutes": config["intervalMinutes"], "units": {"winRate": "percent", "totalReturn": "percent",
            "maxDrawdown": "percent", "avgWin": "percent", "avgLoss": "percent", "sharpeRatio": "ratio", "profitFactor": "ratio"}},
            "assumptions": list(ASSUMPTIONS), "execution": {"orders_submitted": 0, "credentials_used": False, "state_written": False}}


def register_historical_backtest_routes(app: Any, *, dispatch_available: Callable[[], bool] | None = None,
                                        source_reader: Callable[[Mapping[str, Any]], Dataset] = fetch_kraken_dataset) -> None:
    """Attach views behind the caller's existing authenticated/HNC ingress.

    The trusted server composition must supply actual dispatch readiness. Default
    held prevents a standalone registration from claiming production availability.
    The source-reader injection is an offline test seam, never a client option.
    """
    from flask import g, jsonify, request

    admission_ready = dispatch_available or (lambda: False)
    slots = threading.BoundedSemaphore(MAX_CONCURRENT_REPLAYS)

    def identity() -> str:
        return account_scope(getattr(g, "identity_kind", None), getattr(g, "tenant", None))

    def admitted() -> bool:
        try:
            return admission_ready() is True
        except Exception:
            return False

    def response(payload: dict[str, Any], status: int = 200):
        result = jsonify(payload)
        result.headers["Cache-Control"] = "no-store"
        return result, status

    @app.get(CAPABILITY_PATH)
    def historical_backtest_capabilities():
        scope, reason = None, None
        try:
            scope = identity()
        except BacktestError as exc:
            reason = str(exc)
        ready = admitted()
        external_held = no_external_api_calls()
        if reason is None and not ready:
            reason = "Historical replay dispatch is held by the operator's protected ingress; no production release is configured."
        if reason is None and external_held:
            reason = "Public historical source reads are held by AUREON_NO_EXTERNAL_API_CALLS."
        return response({"schema": "aureon.backtest-capability.v1", "service": SERVICE, "available": bool(scope and ready and not external_held),
                        "execution_mode": "historical_replay", "source_backed": True, "executes_orders": False,
                        "capability_only": True, "account_scope": scope, "reason": reason,
                        "ingress_status": "dispatch_available" if ready else "held", "source_observed": False,
                        "source_policy": "Fresh public Kraken OHLC is read and validated per admitted replay; no archive fallback.",
                        "symbols": list(PAIRS), "intervals": [60, 1440], "max_candles": MAX_REPLAY_CANDLES,
                        "strategy": STRATEGY, "supported_config_fields": sorted(CONFIG_KEYS), "assumptions": list(ASSUMPTIONS)})

    @app.post(REPLAY_PATH)
    def historical_backtest_run():
        acquired = False
        try:
            scope = identity()
            if not admitted():
                raise BacktestError("Historical replay dispatch is held by the operator's protected ingress.", code="ingress_held", status=503)
            if request.content_length is None or request.content_length > MAX_REQUEST_BYTES:
                raise BacktestError("Replay request is missing a bounded content length or is too large.", code="request_too_large", status=413)
            body = request.get_json(silent=True)
            if not isinstance(body, dict) or set(body) != {"config", "request_id", "account_scope"}:
                raise BacktestError("Expected config, request_id and account_scope only.")
            if body["account_scope"] != scope:
                raise BacktestError("Account changed after the capability read. Refresh the service capability.", code="account_scope_changed", status=409)
            request_id = body["request_id"]
            if not isinstance(request_id, str) or not re.fullmatch(r"[A-Za-z0-9-]{16,64}", request_id):
                raise BacktestError("A bounded request identifier is required.")
            config = validate_config(body["config"])
            acquired = slots.acquire(blocking=False)
            if not acquired:
                raise BacktestError("Historical replay capacity is busy. Retry after the current bounded analysis finishes.", code="replay_busy", status=429)
            payload = run_replay(source_reader(config), config)
            payload.update({"schema": "aureon.backtest-result.v1", "service": SERVICE, "request_id": request_id,
                            "account_scope": scope, "config_sha256": hashlib.sha256(_canonical(config)).hexdigest()})
            return response(payload)
        except BacktestError as exc:
            return response({"available": False, "error": str(exc), "reason": str(exc), "reason_code": exc.code}, exc.status)
        except Exception:
            return response({"available": False, "error": "Historical replay could not produce a validated report.", "reason_code": "replay_failed"}, 500)
        finally:
            if acquired:
                slots.release()


def main(argv: list[str] | None = None) -> int:
    """Explicit standalone analysis proof; does not grant or exercise HTTP dispatch."""
    import argparse
    parser = argparse.ArgumentParser(description="Read public Kraken candles and calculate a bounded historical momentum replay. No orders or application state writes.")
    parser.add_argument("--run-read-only-analysis", action="store_true", required=True)
    parser.add_argument("--symbol", choices=tuple(PAIRS), default="BTCUSD")
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--interval-minutes", type=int, choices=(60, 1440), default=60)
    parser.add_argument("--lookback-periods", type=int, default=24)
    parser.add_argument("--fee-bps", type=float, default=40)
    parser.add_argument("--slippage-bps", type=float, default=5)
    args = parser.parse_args(argv)
    end = datetime.now(timezone.utc).date() - timedelta(days=1)
    if not 1 <= args.days <= 672:
        parser.error("days must be between 1 and 672 (the candle bound is checked separately)")
    config = {"symbol": args.symbol, "startDate": (end - timedelta(days=args.days - 1)).isoformat(), "endDate": end.isoformat(),
              "initialCapital": 10000, "tradeSize": 0.5, "stopLoss": 2, "takeProfit": 5, "strategy": STRATEGY,
              "intervalMinutes": args.interval_minutes, "lookbackPeriods": args.lookback_periods,
              "feeBps": args.fee_bps, "slippageBps": args.slippage_bps}
    try:
        config = validate_config(config)
        payload = run_replay(fetch_kraken_dataset(config), config)
        payload.update({"schema": "aureon.local-historical-analysis.v1", "analysis_only": True,
                        "operator_http_dispatch_exercised": False, "production_ingress_released": False})
        print(json.dumps(payload, sort_keys=True, allow_nan=False))
        return 0
    except BacktestError as exc:
        print(json.dumps({"schema": "aureon.local-historical-analysis.v1", "available": False, "reason": str(exc),
                          "reason_code": exc.code, "operator_http_dispatch_exercised": False, "production_ingress_released": False}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
