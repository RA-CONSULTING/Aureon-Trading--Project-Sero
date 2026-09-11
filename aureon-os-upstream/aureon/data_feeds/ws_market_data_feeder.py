#!/usr/bin/env python3
"""WS Market Data Feeder

Purpose:
- Use FREE exchange WebSocket streams (heavy-lifting) to keep an on-disk price+ticker cache fresh.
- Designed to be OPTIONAL and production-friendly.
- Does NOT change trading logic; it only publishes data the trader can optionally consume.

Current backends:
- Binance: all-market tickers via !miniTicker@arr (free)
- Kraken: public REST ticker snapshots (free, budgeted)
- Alpaca: authenticated stock/crypto snapshots when credentials exist
- Capital: authenticated CFD/stock snapshots when credentials exist

Output JSON schema (stable):
{
  "generated_at": 1234567890.0,
  "source": "multi_exchange_stream_cache",
  "sources": ["binance_ws", "kraken_public_rest", ...],
  "prices": {"BTC": 43000.0, ...},
  "ticker_cache": {
    "BTCUSDT": {"price": 43000.0, "change24h": 1.23, "volume": 1234.0, "base": "BTC", "quote": "USDT", "exchange": "binance"},
    "binance:BTCUSDT": {...}
  },
  "source_health": {"binance": {"active": true, ...}}
}
"""

from __future__ import annotations

import os
import sys

if os.getenv("AUREON_STREAM_FEEDER_BATON", "0").strip().lower() in {"1", "true", "yes", "on"}:
    from aureon.core.aureon_baton_link import link_system as _baton_link

    _baton_link(__name__)

# ttt
# WINDOWS UTF-8 FIX - MUST BE AT TOP BEFORE ANY PRINT STATEMENTS
# ttt
if sys.platform == 'win32':
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    try:
        import io

        def _is_utf8_wrapper(stream):
            return (
                isinstance(stream, io.TextIOWrapper)
                and hasattr(stream, 'encoding')
                and stream.encoding
                and stream.encoding.lower().replace('-', '') == 'utf8'
            )

        if hasattr(sys.stdout, 'buffer') and not _is_utf8_wrapper(sys.stdout):
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=True)
        # Skip stderr wrapping (causes Windows exit errors)
    except Exception:
        pass

import argparse
import asyncio
import atexit
import ctypes
import json
import math
import subprocess
import threading
import time
import urllib.parse
import urllib.request
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List, Optional
from http.server import BaseHTTPRequestHandler, HTTPServer

from aureon.core.no_external_calls import no_external_api_calls

try:
    import websockets
except Exception:
    websockets = None

REPO_ROOT = Path(__file__).resolve().parents[2]
STATE_DIR = REPO_ROOT / "state"
PUBLIC_DIR = REPO_ROOT / "frontend" / "public"
LIVE_WAVEFORM_RECORDER_STATE_PATH = STATE_DIR / "aureon_live_waveform_recorder.json"
LIVE_WAVEFORM_RECORDER_PUBLIC_PATH = PUBLIC_DIR / "aureon_live_waveform_recorder.json"
DEFAULT_FEEDER_LOCK_PATH = STATE_DIR / "aureon_ws_market_data_feeder.lock"
DEFAULT_PRICE_CACHE_PATH = REPO_ROOT / "ws_cache" / "ws_prices.json"
BINANCE_TICKER_STREAM_URL = "wss://stream.binance.com:9443/ws/!miniTicker@arr"
STREAM_DATA_MAX_AGE_SEC = float(os.getenv("MARKET_CACHE_TTL", "30"))
STREAM_CLOCK_SKEW_SEC = 5.0
PUBLIC_SNAPSHOT_PORT = int(os.getenv("AUREON_STREAM_PUBLIC_SNAPSHOT_PORT", "8794"))
PUBLIC_SNAPSHOT_MAX_ROWS = 1000
PUBLIC_SNAPSHOT_MAX_BYTES = 1024 * 1024
PUBLIC_SNAPSHOT_MAX_AGE_SEC = 5.0

KRAKEN_DEFAULT_PAIRS = [
    "XBTUSD",
    "ETHUSD",
    "SOLUSD",
    "XRPUSD",
    "ADAUSD",
    "DOGEUSD",
    "LTCUSD",
    "BCHUSD",
    "DOTUSD",
    "LINKUSD",
    "AVAXUSD",
    "XLMUSD",
]

ALPACA_DEFAULT_SYMBOLS = [
    "BTC/USD",
    "ETH/USD",
    "SOL/USD",
    "AAPL",
    "TSLA",
    "NVDA",
    "SPY",
    "QQQ",
]

CAPITAL_DEFAULT_SYMBOLS = [
    "GOLD",
    "GCM2026",
    "GLD",
    "GDX",
    "AAPL",
    "TSLA",
    "NVDA",
    "SPY",
    "QQQ",
    "MSFT",
    "AMZN",
    "META",
    "GOOGL",
]


def _split_env_list(value: str, default: List[str]) -> List[str]:
    items = [item.strip() for item in str(value or "").replace(";", ",").split(",") if item.strip()]
    return items or list(default)


def _fetch_binance_all_tickers_rest() -> List[Dict[str, Any]]:
    request = urllib.request.Request(
        "https://api.binance.com/api/v3/ticker/24hr",
        headers={"User-Agent": "AureonLiveStreamCache/1.0"},
    )
    with urllib.request.urlopen(request, timeout=10) as response:  # nosec B310 - public market-data endpoint
        payload = json.loads(response.read().decode("utf-8", errors="replace"))
    return payload if isinstance(payload, list) else []


def _timestamp_seconds(value: Any) -> float:
    """Normalize provider timestamps without substituting the current time."""
    try:
        timestamp = float(value)
    except (ValueError, TypeError):
        try:
            timestamp = datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
        except (ValueError, TypeError):
            return 0.0
    if not math.isfinite(timestamp) or timestamp <= 0:
        return 0.0
    if timestamp >= 100_000_000_000_000:
        return timestamp / 1_000_000
    if timestamp >= 100_000_000_000:
        return timestamp / 1_000
    return timestamp


def _refresh_source_freshness(health: Dict[str, Any], now: float) -> Dict[str, Any]:
    health = dict(health)
    timestamp = _timestamp_seconds(health.get("data_timestamp", health.get("last_success_at") or health.get("generated_at")))
    age = now - timestamp if timestamp > 0 else None
    health["data_age_sec"] = round(age, 3) if age is not None else None
    health["freshness_limit_sec"] = STREAM_DATA_MAX_AGE_SEC
    health["fresh"] = bool(health.get("active") and age is not None and -STREAM_CLOCK_SKEW_SEC <= age <= STREAM_DATA_MAX_AGE_SEC)
    return health


def _source_health(
    source_key: str,
    payload: Dict[str, Any],
    *,
    ticker_count: Optional[int] = None,
    reason: str = "",
) -> Dict[str, Any]:
    generated_at = payload.get("generated_at", time.time())
    try:
        generated_at_f = float(generated_at)
    except Exception:
        generated_at_f = time.time()
    cache = payload.get("ticker_cache", {}) if isinstance(payload.get("ticker_cache"), dict) else {}
    count = int(ticker_count if ticker_count is not None else len(cache))
    timestamps = [_timestamp_seconds(entry.get("timestamp")) for entry in cache.values() if isinstance(entry, dict)]
    data_timestamp = max(timestamps, default=0.0)
    return _refresh_source_freshness({
        "source": payload.get("source") or source_key,
        "present": True,
        "active": count > 0,
        "fresh": count > 0,
        "ticker_count": count,
        "generated_at": generated_at_f,
        "data_timestamp": data_timestamp,
        "last_success_at": generated_at_f,
        "age_sec": round(max(0.0, time.time() - generated_at_f), 3),
        "mode": payload.get("mode", ""),
        "reason": reason or payload.get("reason", ""),
    }, time.time())


def _disabled_snapshot(source_key: str, reason: str) -> Dict[str, Any]:
    now = time.time()
    return {
        "generated_at": now,
        "source": source_key,
        "mode": "disabled_or_unavailable",
        "reason": reason,
        "prices": {},
        "ticker_cache": {},
        "source_health": {
            source_key: {
                "source": source_key,
                "present": True,
                "active": False,
                "fresh": False,
                "ticker_count": 0,
                "generated_at": now,
                "age_sec": 0.0,
                "mode": "disabled_or_unavailable",
                "reason": reason,
            }
        },
    }


def _ticker_count(payload: Dict[str, Any]) -> int:
    cache = payload.get("ticker_cache", {}) if isinstance(payload.get("ticker_cache"), dict) else {}
    return len(cache)


def _snapshot_success_timestamp(source_key: str, payload: Dict[str, Any]) -> float:
    source_health = payload.get("source_health", {}) if isinstance(payload.get("source_health"), dict) else {}
    health = source_health.get(source_key, {}) if isinstance(source_health.get(source_key), dict) else {}
    for field in ("last_success_at", "generated_at"):
        try:
            value = health.get(field) if isinstance(health, dict) else None
            if value is not None:
                return float(value)
        except Exception:
            pass
    try:
        return float(payload.get("generated_at", time.time()) or time.time())
    except Exception:
        return time.time()


def _cached_last_good_snapshot(source_key: str, payload: Dict[str, Any], reason: str) -> Dict[str, Any]:
    cached = dict(payload)
    original_generated_at_f = _snapshot_success_timestamp(source_key, cached)
    now = time.time()
    cached["generated_at"] = now
    cached["mode"] = "cached_last_good_during_provider_backoff"
    cached["reason"] = f"cached_last_good_due_to:{reason}" if reason else "cached_last_good"
    # Older caches omitted entry timestamps. Freeze them at the original
    # observation, so a fresh merged-file write cannot rejuvenate old prices.
    cached["ticker_cache"] = {
        key: {"timestamp": original_generated_at_f, **entry}
        for key, entry in payload.get("ticker_cache", {}).items()
        if isinstance(entry, dict)
    }
    source_health = cached.get("source_health", {}) if isinstance(cached.get("source_health"), dict) else {}
    health = dict(source_health.get(source_key, {})) if isinstance(source_health.get(source_key), dict) else {}
    health.update(
        {
            "source": cached.get("source") or source_key,
            "present": True,
            "active": _ticker_count(cached) > 0,
            "fresh": _ticker_count(cached) > 0,
            "ticker_count": _ticker_count(cached),
            "generated_at": now,
            "age_sec": 0.0,
            "data_age_sec": round(max(0.0, now - original_generated_at_f), 3),
            "last_success_at": original_generated_at_f,
            "mode": "cached_last_good_during_provider_backoff",
            "reason": cached["reason"],
        }
    )
    cached["source_health"] = {source_key: _refresh_source_freshness(health, now)}
    return cached


def _pid_is_running(pid: int) -> bool:
    if pid <= 0:
        return False
    if sys.platform == "win32":
        try:
            result = subprocess.run(
                ["tasklist", "/FI", f"PID eq {int(pid)}", "/FO", "CSV", "/NH"],
                capture_output=True,
                text=True,
                timeout=2,
                check=False,
            )
            return str(int(pid)) in (result.stdout or "")
        except Exception:
            pass
        try:
            handle = ctypes.windll.kernel32.OpenProcess(0x100000, False, int(pid))
            if not handle:
                return False
            wait_result = ctypes.windll.kernel32.WaitForSingleObject(handle, 0)
            ctypes.windll.kernel32.CloseHandle(handle)
            return wait_result == 0x00000102
        except Exception:
            return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _read_lock_payload(lock_path: Path) -> Dict[str, Any]:
    try:
        payload = json.loads(lock_path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _acquire_single_writer_lock(lock_path: Path, *, out_path: Path, allow_duplicate: bool = False) -> Optional[Path]:
    if allow_duplicate:
        return None
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "pid": os.getpid(),
        "out_path": str(out_path.resolve()),
        "started_at": time.time(),
        "command": " ".join(sys.argv),
    }
    for _ in range(2):
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2, sort_keys=True)
            return lock_path
        except FileExistsError:
            existing = _read_lock_payload(lock_path)
            existing_pid = int(existing.get("pid") or 0)
            if existing_pid and _pid_is_running(existing_pid):
                raise SystemExit(
                    "ws_market_data_feeder already running "
                    f"(pid={existing_pid}, out={existing.get('out_path', '')}). "
                    "Stop the old feeder or set AUREON_ALLOW_DUPLICATE_STREAM_FEEDER=1."
                )
            try:
                lock_path.unlink()
            except FileNotFoundError:
                pass
    raise SystemExit(f"Could not acquire stream feeder lock: {lock_path}")


def _release_single_writer_lock(lock_path: Optional[Path]) -> None:
    if lock_path is None:
        return
    try:
        payload = _read_lock_payload(lock_path)
        if int(payload.get("pid") or 0) == os.getpid():
            lock_path.unlink()
    except FileNotFoundError:
        pass
    except Exception:
        pass


def _merge_market_snapshots(snapshots: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    prices: Dict[str, float] = {}
    ticker_cache: Dict[str, Dict[str, Any]] = {}
    source_health: Dict[str, Dict[str, Any]] = {}
    active_sources: List[str] = []
    ordered_keys = ["binance", "kraken", "alpaca", "capital"]
    ordered_keys += sorted(key for key in snapshots if key not in ordered_keys)

    for key in ordered_keys:
        payload = snapshots.get(key)
        if not isinstance(payload, dict):
            continue
        raw_prices = payload.get("prices", {}) if isinstance(payload.get("prices"), dict) else {}
        for base, price in raw_prices.items():
            base_norm = str(base or "").upper().strip()
            if not base_norm or base_norm in prices:
                continue
            try:
                price_f = float(price)
            except Exception:
                continue
            if price_f > 0:
                prices[base_norm] = price_f

        cache = payload.get("ticker_cache", {}) if isinstance(payload.get("ticker_cache"), dict) else {}
        for cache_key, entry in cache.items():
            if isinstance(entry, dict):
                ticker_cache[str(cache_key)] = dict(entry)

        nested_health = payload.get("source_health", {}) if isinstance(payload.get("source_health"), dict) else {}
        if isinstance(nested_health.get(key), dict):
            health = dict(nested_health[key])
        else:
            health = _source_health(key, payload, ticker_count=len(cache))
        try:
            health_at = float(health.get("generated_at", time.time()) or time.time())
        except Exception:
            health_at = time.time()
        health["age_sec"] = round(max(0.0, time.time() - health_at), 3)
        source_health[key] = _refresh_source_freshness(health, time.time())
        if health.get("active"):
            active_sources.append(str(health.get("source") or key))

    return {
        "generated_at": time.time(),
        "source": "multi_exchange_stream_cache",
        "mode": "multi_exchange_world_financial_ocean_scan",
        "sources": active_sources,
        "source_count": len(source_health),
        "active_source_count": len(active_sources),
        "prices": prices,
        "ticker_cache": ticker_cache,
        "source_health": source_health,
    }


def _snapshots_from_merged_cache(payload: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    if not isinstance(payload, dict):
        return {}
    source_health = payload.get("source_health", {}) if isinstance(payload.get("source_health"), dict) else {}
    ticker_cache = payload.get("ticker_cache", {}) if isinstance(payload.get("ticker_cache"), dict) else {}
    snapshots: Dict[str, Dict[str, Any]] = {}
    for source_key, health in source_health.items():
        key = str(source_key or "").lower().strip()
        if not key or not isinstance(health, dict):
            continue
        source_tickers: Dict[str, Dict[str, Any]] = {}
        prices: Dict[str, float] = {}
        for ticker_key, entry in ticker_cache.items():
            if not isinstance(entry, dict) or str(entry.get("exchange", "")).lower() != key:
                continue
            entry_copy = dict(entry)
            source_tickers[str(ticker_key)] = entry_copy
            base = str(entry_copy.get("base") or entry_copy.get("symbol") or "").upper().strip()
            try:
                price = float(entry_copy.get("price", 0) or 0)
            except Exception:
                price = 0.0
            if base and price > 0 and base not in prices:
                prices[base] = price
        snapshots[key] = {
            "generated_at": health.get("generated_at") or payload.get("generated_at") or time.time(),
            "source": health.get("source") or key,
            "mode": health.get("mode") or "hydrated_from_merged_stream_cache",
            "reason": health.get("reason") or "",
            "prices": prices,
            "ticker_cache": source_tickers,
            "source_health": {key: dict(health)},
        }
    return snapshots


class MarketSnapshotStore:
    def __init__(self, out_path: Path, history_recorder: Optional["LiveWaveformHistoryRecorder"] = None):
        self.out_path = out_path
        self._snapshots: Dict[str, Dict[str, Any]] = {}
        self._lock = asyncio.Lock()
        self._history_recorder = history_recorder
        self._memory_lock = threading.RLock()
        self._memory_snapshots: Dict[str, Dict[str, Any]] = {}

    def publish_memory(self, source_key: str, payload: Dict[str, Any]) -> None:
        if source_key not in {"binance", "kraken", "alpaca", "capital"}:
            return
        with self._memory_lock:
            previous = self._memory_snapshots.get(source_key, {})
            self._memory_snapshots[source_key] = _coalesce_ticker_snapshots(source_key, previous, payload)

    def public_quote_snapshot(self) -> Dict[str, Any]:
        with self._memory_lock:
            snapshots = dict(self._memory_snapshots)
        return _public_quote_projection(snapshots, now=time.time())

    async def _run_io(self, operation: Any, *args: Any) -> Any:
        # Keep ownership of the async store lock until the worker finishes,
        # even if its caller is cancelled. There remains exactly one writer.
        job = asyncio.get_running_loop().run_in_executor(None, lambda: operation(*args))
        cancelled = False
        while not job.done():
            try:
                await asyncio.shield(job)
            except asyncio.CancelledError:
                cancelled = True
            except Exception:
                break
        if cancelled:
            try:
                job.result()
            except Exception:
                pass
            raise asyncio.CancelledError
        return job.result()

    def _hydrate_from_existing_cache_unlocked(self) -> None:
        if len(self._snapshots) >= 4 or not self.out_path.exists():
            return
        try:
            existing = json.loads(self.out_path.read_text(encoding="utf-8"))
        except Exception:
            return
        for source_key, payload in _snapshots_from_merged_cache(existing).items():
            current = self._snapshots.get(source_key)
            if current is None or (_ticker_count(payload) > 0 and _ticker_count(current) <= 0):
                self._snapshots[source_key] = payload

    async def last_good_snapshot(self, source_key: str) -> Optional[Dict[str, Any]]:
        async with self._lock:
            await self._run_io(self._hydrate_from_existing_cache_unlocked)
            payload = self._snapshots.get(source_key)
            if isinstance(payload, dict) and _ticker_count(payload) > 0:
                return dict(payload)
        return None

    async def update(self, source_key: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        self.publish_memory(source_key, payload)
        async with self._lock:
            return await self._run_io(self._update_unlocked, source_key, payload)

    def _update_unlocked(self, source_key: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        self._hydrate_from_existing_cache_unlocked()
        self._snapshots[source_key] = dict(payload)
        merged = _merge_market_snapshots(self._snapshots)
        _atomic_write_json(self.out_path, merged)
        if self._history_recorder is not None:
            self._history_recorder.record_if_due(merged)
        return merged

    async def update_preserving_existing(self, source_key: str, payload: Dict[str, Any], existing: Dict[str, Any]) -> Dict[str, Any]:
        self.publish_memory(source_key, payload)
        async with self._lock:
            return await self._run_io(self._update_preserving_existing_unlocked, source_key, payload, existing)

    def _update_preserving_existing_unlocked(self, source_key: str, payload: Dict[str, Any], existing: Dict[str, Any]) -> Dict[str, Any]:
        for existing_key, existing_payload in _snapshots_from_merged_cache(existing).items():
            current = self._snapshots.get(existing_key)
            if current is None or (_ticker_count(existing_payload) > 0 and _ticker_count(current) <= 0):
                self._snapshots[existing_key] = existing_payload
        return self._update_unlocked(source_key, payload)


def _coalesce_ticker_snapshots(source_key: str, previous: Dict[str, Any], incoming: Dict[str, Any]) -> Dict[str, Any]:
    """Keep each symbol's latest source observation across incremental batches."""
    previous_cache = previous.get("ticker_cache", {})
    incoming_cache = incoming.get("ticker_cache", {})
    cache = {key: dict(entry) for key, entry in previous_cache.items() if isinstance(entry, dict)}
    for key, entry in incoming_cache.items():
        if not isinstance(entry, dict):
            continue
        old = cache.get(key)
        if old is None or _timestamp_seconds(entry.get("timestamp")) > _timestamp_seconds(old.get("timestamp")):
            cache[key] = dict(entry)

    def price_clocks(payload: Dict[str, Any]) -> Dict[str, float]:
        result: Dict[str, float] = {}
        prices = payload.get("prices", {})
        for entry in payload.get("ticker_cache", {}).values():
            if not isinstance(entry, dict):
                continue
            base = str(entry.get("base") or "")
            if base and entry.get("price") == prices.get(base):
                result[base] = max(result.get(base, 0.0), _timestamp_seconds(entry.get("timestamp")))
        return result

    prices = dict(previous.get("prices", {}))
    previous_clocks, incoming_clocks = price_clocks(previous), price_clocks(incoming)
    for base, price in incoming.get("prices", {}).items():
        if base not in prices or incoming_clocks.get(base, 0.0) > previous_clocks.get(base, 0.0):
            prices[base] = price
    newest = incoming if _timestamp_seconds(incoming.get("generated_at")) >= _timestamp_seconds(previous.get("generated_at")) else previous
    merged = {**newest, "ticker_cache": cache, "prices": prices}
    merged["source_health"] = {source_key: _source_health(source_key, merged, ticker_count=len(cache))}
    return merged


class LatestSnapshotPublisher:
    """A single bounded pending snapshot feeding the store's existing writer."""
    def __init__(self, store: MarketSnapshotStore, source_key: str, *, quiet: bool = True):
        self.store = store
        self.source_key = source_key
        self.quiet = quiet
        self._latest: Dict[str, Any] = {}
        self._pending: Optional[Dict[str, Any]] = None
        self._task: Optional[asyncio.Task] = None
        self.last_error = ""

    def submit(self, payload: Dict[str, Any]) -> None:
        self._latest = _coalesce_ticker_snapshots(self.source_key, self._latest, payload)
        self.store.publish_memory(self.source_key, self._latest)
        self._pending = self._latest
        if self._task is None:
            self._task = asyncio.create_task(self._drain())

    async def _drain(self) -> None:
        try:
            while self._pending is not None:
                payload, self._pending = self._pending, None
                try:
                    await self.store.update(self.source_key, payload)
                    self.last_error = ""
                except Exception as exc:
                    self.last_error = str(exc)
                    if not self.quiet:
                        print(f"{self.source_key} snapshot write failed: {exc}")
        finally:
            self._task = None

    async def flush(self) -> None:
        while self._task is not None:
            await asyncio.shield(self._task)


def _public_quote_projection(snapshots: Dict[str, Dict[str, Any]], *, now: float) -> Dict[str, Any]:
    """Project only public quote fields; never copy arbitrary provider payloads."""
    candidates: Dict[str, Dict[str, Any]] = {}
    known_sources = {
        "binance_ws", "binance_rest_preflight", "binance_rest_ws_gap_fill", "binance_rest_fallback",
        "kraken_public_rest", "alpaca_authenticated_rest", "capital_authenticated_rest",
    }
    for source_key, payload in snapshots.items():
        if source_key not in {"binance", "kraken", "alpaca", "capital"}:
            continue
        cache = payload.get("ticker_cache", {}) if isinstance(payload, dict) else {}
        for cache_key, entry in cache.items():
            if not isinstance(entry, dict) or entry.get("exchange", source_key) != source_key:
                continue
            timestamp = _timestamp_seconds(entry.get("timestamp"))
            try:
                price = float(entry.get("price"))
            except (ValueError, TypeError):
                continue
            if not math.isfinite(price) or price <= 0 or timestamp <= 0 or timestamp > now + STREAM_CLOCK_SKEW_SEC:
                continue
            symbol = str(entry.get("pair") or entry.get("symbol") or str(cache_key).split(":")[-1])[:64]
            if not symbol or not all(char.isalnum() or char in "/_.:-" for char in symbol):
                continue
            key = f"{source_key}:{symbol}"
            if key in candidates and timestamp <= _timestamp_seconds(candidates[key].get("timestamp")):
                continue
            source = str(entry.get("source") or source_key)
            row: Dict[str, Any] = {"exchange": source_key, "source": source if source in known_sources else source_key, "pair": symbol, "price": price}
            for field in ("base", "quote"):
                value = str(entry.get(field) or "")[:24]
                if value and value.isalnum():
                    row[field] = value
            for field in ("bid", "ask", "change24h", "volume"):
                value = entry.get(field)
                if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value):
                    if field not in {"bid", "ask"} or value > 0:
                        row[field] = value
            for field in ("timestamp", "provider_timestamp", "received_at"):
                value = entry.get(field)
                if isinstance(value, (str, int, float)) and not isinstance(value, bool) and _timestamp_seconds(value) > 0 and (not isinstance(value, str) or len(value) <= 64):
                    row[field] = value
            kind = entry.get("timestamp_kind")
            if kind in {"provider_event", "provider_window_close", "received_at"}:
                row["timestamp_kind"] = kind
            candidates[key] = row
    selected = dict(sorted(candidates.items(), key=lambda item: _timestamp_seconds(item[1].get("timestamp")), reverse=True)[:PUBLIC_SNAPSHOT_MAX_ROWS])
    prices: Dict[str, float] = {}
    health: Dict[str, Dict[str, Any]] = {}
    for row in selected.values():
        if row.get("base"):
            prices.setdefault(row["base"], row["price"])
    for source_key in sorted({row["exchange"] for row in selected.values()}):
        rows = [row for row in selected.values() if row["exchange"] == source_key]
        data_timestamp = max(_timestamp_seconds(row.get("timestamp")) for row in rows)
        age = now - data_timestamp
        health[source_key] = {
            "source": source_key, "present": True, "active": True,
            "fresh": -STREAM_CLOCK_SKEW_SEC <= age <= PUBLIC_SNAPSHOT_MAX_AGE_SEC,
            "ticker_count": len(rows), "data_timestamp": data_timestamp,
            "data_age_sec": round(age, 3), "freshness_limit_sec": PUBLIC_SNAPSHOT_MAX_AGE_SEC,
        }
    fresh = any(row["fresh"] for row in health.values())
    return {
        "schema_version": 1, "transport": "loopback_memory", "producer_pid": os.getpid(),
        "generated_at": max((_timestamp_seconds(value.get("generated_at")) for value in snapshots.values()), default=0.0),
        "source": "multi_exchange_stream_cache", "mode": "public_quote_snapshot",
        "available": bool(selected), "fresh": fresh,
        "data_status": "live" if fresh else ("stale" if selected else "no_data"),
        "sources": sorted(health), "source_count": len(health),
        "prices": prices, "ticker_cache": selected, "source_health": health,
        "truncated": len(candidates) > len(selected), "max_rows": PUBLIC_SNAPSHOT_MAX_ROWS,
    }


def start_public_snapshot_server(store: MarketSnapshotStore, *, port: int = PUBLIC_SNAPSHOT_PORT) -> HTTPServer:
    class QuoteHandler(BaseHTTPRequestHandler):
        server_version = "AureonPublicQuotes"
        sys_version = ""

        def setup(self) -> None:
            super().setup()
            self.connection.settimeout(1.0)

        def log_message(self, format: str, *args: Any) -> None:
            pass

        def _send(self, status: int, body: bytes) -> None:
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "close")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            if self.path != "/api/quotes":
                self._send(404, b'{"error":"not_found"}')
                return
            snapshot = store.public_quote_snapshot()
            body = json.dumps(snapshot, ensure_ascii=True, allow_nan=False, separators=(",", ":")).encode("utf-8")
            if len(body) > PUBLIC_SNAPSHOT_MAX_BYTES:
                self._send(503, b'{"error":"public_snapshot_size_limit","data_status":"no_data"}')
                return
            self._send(200, body)

        def _method_not_allowed(self) -> None:
            self._send(405, b'{"error":"method_not_allowed"}')

        do_POST = do_PUT = do_PATCH = do_DELETE = do_HEAD = do_OPTIONS = _method_not_allowed

    server = HTTPServer(("127.0.0.1", int(port)), QuoteHandler)
    threading.Thread(target=server.serve_forever, name="public-quote-snapshot-http", daemon=True).start()
    return server


def _build_binance_snapshot(
    data: List[Dict[str, Any]],
    *,
    binance_uk_mode: bool,
    source: str,
    mode: str,
) -> Dict[str, Any]:
    prices, ticker_cache = _extract_prices_and_tickers(data, binance_uk_mode=binance_uk_mode, source_name=source)
    payload = {
        "generated_at": time.time(),
        "source": source,
        "mode": mode,
        "prices": prices,
        "ticker_cache": ticker_cache,
    }
    payload["source_health"] = {"binance": _source_health("binance", payload, ticker_count=len(ticker_cache))}
    return payload


async def _write_binance_rest_snapshot(
    *,
    out_path: Path,
    binance_uk_mode: bool,
    source: str,
    store: Optional[MarketSnapshotStore] = None,
) -> int:
    data = await asyncio.to_thread(_fetch_binance_all_tickers_rest)
    payload = _build_binance_snapshot(
        data,
        binance_uk_mode=binance_uk_mode,
        source=source,
        mode="rest_snapshot_for_stream_continuity",
    )
    if store is None:
        _atomic_write_json(out_path, payload)
    else:
        existing: Dict[str, Any] = {}
        try:
            if out_path.exists():
                loaded = json.loads(out_path.read_text(encoding="utf-8"))
                existing = loaded if isinstance(loaded, dict) else {}
        except Exception:
            existing = {}
        existing_sources = existing.get("source_health", {}) if isinstance(existing.get("source_health"), dict) else {}
        if len(existing_sources) > 1:
            await store.update_preserving_existing("binance", payload, existing)
        else:
            await store.update("binance", payload)
    return len(payload.get("ticker_cache", {}))


async def run_binance_all_tickers_rest_fallback(
    *,
    out_path: Path,
    binance_uk_mode: bool,
    write_interval_s: float,
    quiet: bool,
    store: Optional[MarketSnapshotStore] = None,
) -> None:
    interval = max(2.0, write_interval_s)
    if not quiet:
        print("Binance WS unavailable; using budgeted public REST ticker fallback")
    while True:
        try:
            ticker_count = await _write_binance_rest_snapshot(
                out_path=out_path,
                binance_uk_mode=binance_uk_mode,
                source='binance_rest_fallback',
                store=store,
            )
            if not quiet:
                print(f"   wrote REST fallback {ticker_count} tickers")
        except asyncio.CancelledError:
            raise
        except Exception as e:
            if not quiet:
                print(f"Binance REST fallback error: {e} (retrying in {interval:.1f}s)")
        await asyncio.sleep(interval)


def _atomic_write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(payload, ensure_ascii=False)
    last_error: Optional[BaseException] = None
    for attempt in range(8):
        tmp = path.with_name(f"{path.name}.{os.getpid()}.{int(time.time() * 1000)}.{attempt}.tmp")
        try:
            tmp.write_text(encoded, encoding="utf-8")
            os.replace(tmp, path)
            return
        except OSError as exc:
            last_error = exc
            try:
                tmp.unlink(missing_ok=True)
            except Exception:
                pass
            if getattr(exc, "winerror", None) != 5 and not isinstance(exc, PermissionError):
                raise
            time.sleep(min(0.5, 0.05 * (attempt + 1)))
    if last_error is not None:
        raise last_error


def _binance_quote_priority(binance_uk_mode: bool) -> List[str]:
    # Keep consistent with micro_profit_labyrinth.py logic
    return ['USDC', 'USDT', 'USD', 'BUSD'] if binance_uk_mode else ['USDT', 'USD', 'BUSD', 'USDC']


def _extract_prices_and_tickers(
    tickers: List[Dict[str, Any]],
    *,
    binance_uk_mode: bool,
    source_name: str = "binance_ws",
) -> tuple[Dict[str, float], Dict[str, Dict[str, Any]]]:
    prices: Dict[str, float] = {}
    ticker_cache: Dict[str, Dict[str, Any]] = {}

    quote_priority = _binance_quote_priority(binance_uk_mode)
    generated_at = time.time()

    # Binance miniTicker provides last/open prices; percentage change is
    # derived from these actual observations. REST/full tickers provide P.
    for t in tickers:
        symbol = str(t.get('s') or t.get('symbol') or '').upper()
        if not symbol:
            continue

        try:
            price = float(t.get('c') or t.get('lastPrice') or t.get('weightedAvgPrice') or 0)
            bid = float(t.get('b') or t.get('bidPrice') or 0)
            ask = float(t.get('a') or t.get('askPrice') or 0)
        except Exception:
            price = 0.0
        if price <= 0:
            continue

        try:
            raw_change = t.get('P', t.get('priceChangePercent'))
            if raw_change is not None:
                change = float(raw_change)
            else:
                open_price = float(t.get('o') or t.get('openPrice') or 0)
                if open_price <= 0:
                    continue
                change = (price - open_price) / open_price * 100.0
        except Exception:
            continue

        try:
            volume = float(t.get('q') or t.get('quoteVolume') or t.get('v') or t.get('volume') or 0)
        except Exception:
            volume = 0.0

        matched_quote: Optional[str] = None
        base: Optional[str] = None
        for quote in quote_priority:
            if symbol.endswith(quote):
                matched_quote = quote
                base = symbol[: -len(quote)]
                break

        if not matched_quote or not base:
            continue

        # Prefer first-seen base per run (quote_priority orders it)
        if base not in prices:
            prices[base] = price

        provider_timestamp = _timestamp_seconds(t.get('E') or t.get('closeTime'))
        entry = {
            'price': price,
            'bid': bid,
            'ask': ask,
            'change24h': change,
            'volume': volume,
            'base': base,
            'quote': matched_quote,
            'exchange': 'binance',
            'source': source_name,
            'timestamp': provider_timestamp,
            'provider_timestamp': provider_timestamp or None,
            'received_at': generated_at,
            'timestamp_kind': 'provider_event' if t.get('E') and provider_timestamp else ('provider_window_close' if provider_timestamp else 'missing_provider_timestamp'),
            'pair': symbol,
        }
        ticker_cache[symbol] = entry
        ticker_cache[f"binance:{symbol}"] = entry

    return prices, ticker_cache


def _normalize_kraken_asset(value: str) -> str:
    raw = str(value or "").upper().strip()
    if len(raw) == 4 and raw[0] in {"X", "Z"}:
        raw = raw[1:]
    if raw == "XBT":
        return "BTC"
    return raw


def _split_kraken_pair(pair: str) -> tuple[str, str]:
    raw = str(pair or "").upper().strip()
    for quote in ("ZUSD", "USD", "USDT", "USDC", "ZEUR", "EUR", "ZGBP", "GBP"):
        if raw.endswith(quote):
            base = _normalize_kraken_asset(raw[: -len(quote)])
            quote_norm = quote[1:] if quote.startswith("Z") else quote
            return base, quote_norm
    return "", ""


def _fetch_kraken_public_tickers_rest(pairs: List[str]) -> Dict[str, Any]:
    pair_param = ",".join(pairs)
    url = "https://api.kraken.com/0/public/Ticker?" + urllib.parse.urlencode({"pair": pair_param})
    request = urllib.request.Request(url, headers={"User-Agent": "AureonLiveStreamCache/1.0"})
    with urllib.request.urlopen(request, timeout=10) as response:  # nosec B310 - public market-data endpoint
        payload = json.loads(response.read().decode("utf-8", errors="replace"))
    result = payload.get("result", {}) if isinstance(payload, dict) else {}
    return result if isinstance(result, dict) else {}


def _extract_kraken_prices_and_tickers(result: Dict[str, Any]) -> tuple[Dict[str, float], Dict[str, Dict[str, Any]]]:
    prices: Dict[str, float] = {}
    ticker_cache: Dict[str, Dict[str, Any]] = {}
    generated_at = time.time()
    for pair, item in result.items():
        if not isinstance(item, dict):
            continue
        base, quote = _split_kraken_pair(str(pair))
        if not base or not quote:
            continue
        try:
            price = float((item.get("c") or [0])[0] or 0)
            bid = float((item.get("b") or [0])[0] or 0)
            ask = float((item.get("a") or [0])[0] or 0)
            open_price = float(item.get("o") or 0)
            base_volume = float((item.get("v") or [0, 0])[-1] or 0)
        except Exception:
            continue
        if price <= 0:
            continue
        change = ((price - open_price) / open_price * 100.0) if open_price > 0 else 0.0
        volume = base_volume * price
        symbol = f"{base}{quote}"
        if quote in {"USD", "USDT", "USDC"} and base not in prices:
            prices[base] = price
        entry = {
            "price": price,
            "bid": bid,
            "ask": ask,
            "change24h": change,
            "volume": volume,
            "base": base,
            "quote": quote,
            "exchange": "kraken",
            "source": "kraken_public_rest",
            "timestamp": generated_at,
            "received_at": generated_at,
            "timestamp_kind": "received_at",
            "pair": str(pair),
        }
        ticker_cache[symbol] = entry
        ticker_cache[f"kraken:{symbol}"] = entry
    return prices, ticker_cache


async def _build_kraken_snapshot(pairs: List[str]) -> Dict[str, Any]:
    result = await asyncio.to_thread(_fetch_kraken_public_tickers_rest, pairs)
    prices, ticker_cache = _extract_kraken_prices_and_tickers(result)
    payload = {
        "generated_at": time.time(),
        "source": "kraken_public_rest",
        "mode": "budgeted_public_rest_snapshot",
        "prices": prices,
        "ticker_cache": ticker_cache,
    }
    payload["source_health"] = {"kraken": _source_health("kraken", payload, ticker_count=len(ticker_cache))}
    return payload


def _extract_base_quote(symbol: str) -> tuple[str, str]:
    raw = str(symbol or "").upper().replace("/", "").replace("-", "").strip()
    for quote in ("USDT", "USDC", "USD", "GBP", "EUR"):
        if raw.endswith(quote) and len(raw) > len(quote):
            return raw[: -len(quote)], quote
    return raw, "USD"


def _build_generic_ticker_cache(
    rows: List[Dict[str, Any]],
    *,
    exchange: str,
    source: str,
) -> tuple[Dict[str, float], Dict[str, Dict[str, Any]]]:
    prices: Dict[str, float] = {}
    ticker_cache: Dict[str, Dict[str, Any]] = {}
    generated_at = time.time()
    for row in rows:
        raw_symbol = str(row.get("symbol") or row.get("ticker") or row.get("epic") or "").upper().strip()
        if not raw_symbol:
            continue
        base, quote = _extract_base_quote(raw_symbol)
        try:
            price = float(row.get("price") or row.get("lastPrice") or 0)
            bid = float(row.get("bid") or row.get("bp") or 0)
            ask = float(row.get("ask") or row.get("ap") or 0)
            change = float(row.get("change_pct") or row.get("priceChangePercent") or 0)
            volume = float(row.get("volume") or row.get("quoteVolume") or row.get("dailyVolume") or 0)
        except Exception:
            continue
        if price <= 0 or not base:
            continue
        if base not in prices:
            prices[base] = price
        normalized_symbol = f"{base}{quote}"
        provider_timestamp = _timestamp_seconds(row.get("provider_timestamp") or row.get("timestamp") or row.get("t"))
        entry = {
            "price": price,
            "bid": bid,
            "ask": ask,
            "change24h": change,
            "volume": volume,
            "base": base,
            "quote": quote,
            "exchange": exchange,
            "source": source,
            "timestamp": provider_timestamp or generated_at,
            "provider_timestamp": provider_timestamp or None,
            "received_at": generated_at,
            "timestamp_kind": "provider_event" if provider_timestamp else "received_at",
            "pair": raw_symbol,
            "epic": row.get("epic", ""),
        }
        ticker_cache[normalized_symbol] = entry
        ticker_cache[f"{exchange}:{normalized_symbol}"] = entry
    return prices, ticker_cache


def _quote_for_waveform(quote: Any) -> str:
    raw = str(quote or "USD").upper().strip()
    if raw in {"USDT", "USDC", "BUSD", "ZUSD"}:
        return "USD"
    if raw in {"ZGBP"}:
        return "GBP"
    if raw in {"ZEUR"}:
        return "EUR"
    return raw or "USD"


def _ticker_cache_to_waveform_bars(
    payload: Dict[str, Any],
    *,
    now_ms: int,
    bucket_ms: int,
    max_symbols: int,
) -> List[Dict[str, Any]]:
    ticker_cache = payload.get("ticker_cache", {}) if isinstance(payload.get("ticker_cache"), dict) else {}
    if not ticker_cache:
        return []

    prefixed = {key: value for key, value in ticker_cache.items() if ":" in str(key)}
    source_items = prefixed or ticker_cache
    ranked_items: List[tuple[float, str, Dict[str, Any]]] = []
    seen: set[tuple[str, str]] = set()
    for cache_key, entry in source_items.items():
        if not isinstance(entry, dict):
            continue
        exchange = str(entry.get("exchange") or str(cache_key).split(":", 1)[0] or "unknown").lower().strip()
        pair = str(entry.get("pair") or str(cache_key).split(":", 1)[-1] or "").upper().strip()
        base = str(entry.get("base") or "").upper().strip()
        quote = _quote_for_waveform(entry.get("quote"))
        if not base:
            continue
        try:
            price = float(entry.get("price") or 0)
        except Exception:
            price = 0.0
        if price <= 0:
            continue
        identity = (exchange, pair or f"{base}{quote}")
        if identity in seen:
            continue
        seen.add(identity)
        try:
            volume = float(entry.get("volume") or entry.get("volume_24h") or 0)
        except Exception:
            volume = 0.0
        try:
            change_abs = abs(float(entry.get("change24h") or entry.get("change_24h") or 0))
        except Exception:
            change_abs = 0.0
        score = min(1_000_000_000_000.0, max(0.0, volume)) + (change_abs * 1_000_000.0)
        ranked_items.append((score, str(cache_key), entry))

    ranked_items.sort(key=lambda item: item[0], reverse=True)
    time_start_ms = int(now_ms // max(1, bucket_ms) * max(1, bucket_ms))
    time_end_ms = time_start_ms + max(1, bucket_ms)
    bars: List[Dict[str, Any]] = []
    for _score, cache_key, entry in ranked_items[: max(1, int(max_symbols or 1))]:
        exchange = str(entry.get("exchange") or str(cache_key).split(":", 1)[0] or "unknown").lower().strip()
        base = str(entry.get("base") or "").upper().strip()
        quote = _quote_for_waveform(entry.get("quote"))
        symbol = f"{base}{quote}"
        pair = str(entry.get("pair") or symbol).upper().strip()
        try:
            price = float(entry.get("price") or 0)
            bid = float(entry.get("bid") or price)
            ask = float(entry.get("ask") or price)
            volume = float(entry.get("volume") or entry.get("volume_24h") or 0)
        except Exception:
            continue
        if price <= 0:
            continue
        low = min(value for value in (price, bid, ask) if value > 0)
        high = max(price, bid, ask)
        raw_json = json.dumps(
            {
                "cache_key": cache_key,
                "entry": entry,
                "cache_source": payload.get("source"),
                "cache_generated_at": payload.get("generated_at"),
            },
            ensure_ascii=False,
        )
        bars.append(
            {
                "provider": "aureon_live_stream_cache",
                "venue": exchange.upper(),
                "symbol_id": f"{exchange.upper()}:{pair}",
                "symbol": symbol,
                "period_id": f"LIVE_{int(max(1, bucket_ms) / 1000)}S",
                "time_start_ms": time_start_ms,
                "time_end_ms": time_end_ms,
                "open": price,
                "high": high,
                "low": low,
                "close": price,
                "volume": volume,
                "trades_count": None,
                "ingested_at_ms": now_ms,
                "raw_json": raw_json,
            }
        )
    return bars


class LiveWaveformHistoryRecorder:
    def __init__(
        self,
        *,
        interval_s: float,
        max_symbols: int,
        bucket_s: float,
        state_path: Path = LIVE_WAVEFORM_RECORDER_STATE_PATH,
        public_path: Path = LIVE_WAVEFORM_RECORDER_PUBLIC_PATH,
    ):
        self.interval_s = max(5.0, float(interval_s or 60.0))
        self.max_symbols = max(1, int(max_symbols or 512))
        self.bucket_ms = max(1000, int(max(1.0, float(bucket_s or 60.0)) * 1000))
        self.state_path = state_path
        self.public_path = public_path
        self._last_record_at = 0.0

    def record_if_due(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        now = time.time()
        if now - self._last_record_at < self.interval_s:
            return {}
        self._last_record_at = now
        now_ms = int(now * 1000)
        bars = _ticker_cache_to_waveform_bars(
            payload,
            now_ms=now_ms,
            bucket_ms=self.bucket_ms,
            max_symbols=self.max_symbols,
        )
        inserted = 0
        error = ""
        try:
            from aureon.core.aureon_global_history_db import connect, insert_market_bar

            conn = connect(None, check_same_thread=False)
            try:
                for bar in bars:
                    if insert_market_bar(conn, bar):
                        inserted += 1
                conn.commit()
            finally:
                conn.close()
        except Exception as exc:
            error = str(exc)

        source_health = payload.get("source_health", {}) if isinstance(payload.get("source_health"), dict) else {}
        summary = {
            "schema_version": 1,
            "generated_at": time.time(),
            "mode": "planetary_financial_waveform_recorder",
            "history_db": str(STATE_DIR / "aureon_global_history.sqlite"),
            "cache_source": payload.get("source"),
            "cache_generated_at": payload.get("generated_at"),
            "cache_ticker_count": len(payload.get("ticker_cache", {}) if isinstance(payload.get("ticker_cache"), dict) else {}),
            "selected_bar_count": len(bars),
            "inserted_bar_count": inserted,
            "period_id": f"LIVE_{int(self.bucket_ms / 1000)}S",
            "record_interval_sec": self.interval_s,
            "max_symbols_per_cycle": self.max_symbols,
            "source_health": source_health,
            "usable_for_waveform_memory": bool(inserted > 0 and not error),
            "error": error,
        }
        for path in (self.state_path, self.public_path):
            try:
                _atomic_write_json(path, summary)
            except Exception:
                pass
        return summary


async def _build_alpaca_snapshot(symbols: List[str]) -> Dict[str, Any]:
    def _fetch() -> tuple[List[Dict[str, Any]], str]:
        from aureon.exchanges.alpaca_client import AlpacaClient

        client = AlpacaClient()
        if getattr(client, "init_error", "") or not getattr(client, "is_authenticated", True):
            return [], str(getattr(client, "init_error", "") or "not_authenticated")
        rows: List[Dict[str, Any]] = []
        for symbol in symbols:
            ticker = client.get_ticker(symbol) or {}
            if not isinstance(ticker, dict):
                continue
            raw = ticker.get("raw", {}) if isinstance(ticker.get("raw"), dict) else {}
            rows.append(
                {
                    "symbol": ticker.get("symbol") or symbol,
                    "price": ticker.get("price"),
                    "bid": ticker.get("bid"),
                    "ask": ticker.get("ask"),
                    "change_pct": raw.get("todaysChangePerc", ticker.get("change_pct", 0)),
                    "volume": raw.get("dailyVolume", 0),
                    "provider_timestamp": ticker.get("provider_timestamp") or ticker.get("timestamp") or raw.get("t"),
                }
            )
        return rows, "" if rows else "missing_credentials_or_no_snapshot_rows"

    rows, reason = await asyncio.to_thread(_fetch)
    prices, ticker_cache = _build_generic_ticker_cache(rows, exchange="alpaca", source="alpaca_rest_snapshot")
    payload = {
        "generated_at": time.time(),
        "source": "alpaca_rest_snapshot",
        "mode": "budgeted_authenticated_market_snapshot",
        "prices": prices,
        "ticker_cache": ticker_cache,
        "reason": "" if ticker_cache else reason,
    }
    payload["source_health"] = {"alpaca": _source_health("alpaca", payload, ticker_count=len(ticker_cache))}
    return payload


async def _build_capital_snapshot(symbols: List[str]) -> Dict[str, Any]:
    def _fetch() -> tuple[List[Dict[str, Any]], str]:
        from aureon.exchanges.capital_client import CapitalClient

        client = CapitalClient()
        if not getattr(client, "enabled", False):
            return [], str(getattr(client, "init_error", "") or "credentials_missing")
        if getattr(client, "init_error", ""):
            return [], str(getattr(client, "init_error", ""))
        rows = client.get_stock_snapshot_watchlist(symbols)
        reason = str(getattr(client, "init_error", "") or "")
        return rows, "" if rows else (reason or "missing_credentials_or_no_snapshot_rows")

    rows, reason = await asyncio.to_thread(_fetch)
    prices, ticker_cache = _build_generic_ticker_cache(rows, exchange="capital", source="capital_rest_snapshot")
    payload = {
        "generated_at": time.time(),
        "source": "capital_rest_snapshot",
        "mode": "budgeted_authenticated_market_snapshot",
        "prices": prices,
        "ticker_cache": ticker_cache,
        "reason": "" if ticker_cache else reason,
    }
    payload["source_health"] = {"capital": _source_health("capital", payload, ticker_count=len(ticker_cache))}
    return payload


async def run_budgeted_snapshot_feed(
    *,
    source_key: str,
    store: MarketSnapshotStore,
    interval_s: float,
    quiet: bool,
    builder,
) -> None:
    interval = max(5.0, float(interval_s or 30.0))
    fallback_grace_sec = max(0.0, float(os.getenv("AUREON_STREAM_LAST_GOOD_GRACE_SEC", "300") or "300"))
    last_good_payload: Optional[Dict[str, Any]] = None
    while True:
        try:
            payload = await builder()
            if _ticker_count(payload) > 0:
                last_good_payload = dict(payload)
                await store.update(source_key, payload)
            elif last_good_payload is not None and fallback_grace_sec > 0:
                last_success_at = _snapshot_success_timestamp(source_key, last_good_payload)
                if time.time() - last_success_at <= fallback_grace_sec:
                    await store.update(
                        source_key,
                        _cached_last_good_snapshot(
                            source_key,
                            last_good_payload,
                            str(payload.get("reason", "") or "empty_snapshot"),
                        ),
                    )
                else:
                    await store.update(source_key, payload)
            elif fallback_grace_sec > 0:
                persisted_good = await store.last_good_snapshot(source_key)
                if persisted_good is not None and time.time() - _snapshot_success_timestamp(source_key, persisted_good) <= fallback_grace_sec:
                    last_good_payload = dict(persisted_good)
                    await store.update(
                        source_key,
                        _cached_last_good_snapshot(
                            source_key,
                            persisted_good,
                            str(payload.get("reason", "") or "empty_snapshot"),
                        ),
                    )
                else:
                    await store.update(source_key, payload)
            else:
                await store.update(source_key, payload)
            if not quiet:
                count = _ticker_count(payload)
                print(f"   wrote {source_key} snapshot tickers={count}")
        except asyncio.CancelledError:
            raise
        except Exception as e:
            persisted_good = None
            if last_good_payload is None and fallback_grace_sec > 0:
                try:
                    persisted_good = await store.last_good_snapshot(source_key)
                except Exception:
                    persisted_good = None
                if persisted_good is not None:
                    last_good_payload = dict(persisted_good)
            if last_good_payload is not None and fallback_grace_sec > 0:
                last_success_at = _snapshot_success_timestamp(source_key, last_good_payload)
                if time.time() - last_success_at <= fallback_grace_sec:
                    await store.update(source_key, _cached_last_good_snapshot(source_key, last_good_payload, f"snapshot_error:{e}"))
                else:
                    await store.update(source_key, _disabled_snapshot(source_key, f"snapshot_error:{e}"))
            else:
                await store.update(source_key, _disabled_snapshot(source_key, f"snapshot_error:{e}"))
            if not quiet:
                print(f"{source_key} snapshot error: {e} (retrying in {interval:.1f}s)")
        await asyncio.sleep(interval)


async def run_binance_all_tickers(
    *,
    out_path: Path,
    binance_uk_mode: bool,
    write_interval_s: float,
    quiet: bool,
    store: Optional[MarketSnapshotStore] = None,
) -> None:
    store = store or MarketSnapshotStore(out_path)
    if not websockets:
        await run_binance_all_tickers_rest_fallback(
            out_path=out_path,
            binance_uk_mode=binance_uk_mode,
            write_interval_s=max(5.0, write_interval_s),
            quiet=quiet,
            store=store,
        )
        return

    # The former !ticker@arr stream was retired by Binance on 2026-03-26.
    url = BINANCE_TICKER_STREAM_URL
    last_write = 0.0
    publisher = LatestSnapshotPublisher(store, "binance", quiet=quiet)

    if not quiet:
        print(f"🌐 Binance WS feeder connecting: {url}")
        print(f"   Output: {out_path}")

    while True:
        try:
            try:
                ticker_count = await _write_binance_rest_snapshot(
                    out_path=out_path,
                    binance_uk_mode=binance_uk_mode,
                    source='binance_rest_preflight',
                    store=store,
                )
                last_write = time.time()
                if not quiet:
                    print(f"   preflight REST snapshot wrote {ticker_count} tickers")
            except Exception as e:
                if not quiet:
                    print(f"   REST preflight failed: {e}")
            async with websockets.connect(url, ping_interval=20, ping_timeout=20) as ws:
                if not quiet:
                    print("   ✅ Connected")

                while True:
                    now = time.time()
                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=max(5.0, write_interval_s * 5.0))
                    except asyncio.TimeoutError:
                        if now - last_write >= max(5.0, write_interval_s * 3.0):
                            try:
                                ticker_count = await _write_binance_rest_snapshot(
                                    out_path=out_path,
                                    binance_uk_mode=binance_uk_mode,
                                    source='binance_rest_ws_gap_fill',
                                    store=store,
                                )
                                last_write = time.time()
                                if not quiet:
                                    print(f"   gap-fill REST snapshot wrote {ticker_count} tickers")
                            except Exception as e:
                                if not quiet:
                                    print(f"   REST gap-fill failed: {e}")
                        continue

                    # throttle writes to disk
                    if now - last_write < write_interval_s:
                        continue

                    try:
                        data = json.loads(raw)
                    except Exception:
                        continue

                    if not isinstance(data, list):
                        continue

                    payload = _build_binance_snapshot(
                        data,
                        binance_uk_mode=binance_uk_mode,
                        source="binance_ws",
                        mode="websocket_all_market_ticker_stream",
                    )
                    publisher.submit(payload)
                    prices = payload.get("prices", {})
                    ticker_cache = payload.get("ticker_cache", {})
                    last_write = now

                    if not quiet:
                        print(f"   🟡 queued {len(prices)} base prices / {len(ticker_cache)} tickers")

        except asyncio.CancelledError:
            raise
        except Exception as e:
            if not quiet:
                print(f"⚠️ Binance WS feeder error: {e} (reconnecting in 2s)")
            await asyncio.sleep(2)


def main() -> int:
    parser = argparse.ArgumentParser(description="WS market data feeder (free APIs)")
    parser.add_argument(
        "--out",
        default=os.getenv("WS_PRICE_CACHE_PATH", str(DEFAULT_PRICE_CACHE_PATH)),
        help="Output JSON cache path (default: ws_cache/ws_prices.json)",
    )
    parser.add_argument(
        "--binance",
        action="store_true",
        default=True,
        help="Enable Binance all-market tickers feed (default: on)",
    )
    parser.add_argument(
        "--kraken",
        action="store_true",
        default=os.getenv("AUREON_STREAM_ENABLE_KRAKEN", "0") in ("1", "true", "TRUE", "yes", "YES"),
        help="Enable budgeted Kraken public ticker snapshots",
    )
    parser.add_argument(
        "--alpaca",
        action="store_true",
        default=os.getenv("AUREON_STREAM_ENABLE_ALPACA", "0") in ("1", "true", "TRUE", "yes", "YES"),
        help="Enable budgeted Alpaca authenticated market snapshots when credentials exist",
    )
    parser.add_argument(
        "--capital",
        action="store_true",
        default=os.getenv("AUREON_STREAM_ENABLE_CAPITAL", "0") in ("1", "true", "TRUE", "yes", "YES"),
        help="Enable budgeted Capital authenticated market snapshots when credentials exist",
    )
    parser.add_argument(
        "--binance-uk-mode",
        action="store_true",
        default=os.getenv("BINANCE_UK_MODE", "0") in ("1", "true", "TRUE", "yes", "YES"),
        help="Prefer USDC quotes (UK mode)",
    )
    parser.add_argument(
        "--write-interval-s",
        type=float,
        default=float(os.getenv("WS_FEED_WRITE_INTERVAL_S", "1.0")),
        help="Minimum seconds between cache writes (default: 1.0)",
    )
    parser.add_argument(
        "--public-snapshot-port",
        type=int,
        default=PUBLIC_SNAPSHOT_PORT,
        help="Loopback-only public quote GET port (default: 8794; 0 disables)",
    )
    parser.add_argument(
        "--kraken-interval-s",
        type=float,
        default=float(os.getenv("KRAKEN_STREAM_CACHE_INTERVAL_S", "60")),
        help="Seconds between Kraken public snapshots (default: 60)",
    )
    parser.add_argument(
        "--alpaca-interval-s",
        type=float,
        default=float(os.getenv("ALPACA_STREAM_CACHE_INTERVAL_S", "30")),
        help="Seconds between Alpaca snapshots (default: 30)",
    )
    parser.add_argument(
        "--capital-interval-s",
        type=float,
        default=float(os.getenv("CAPITAL_STREAM_CACHE_INTERVAL_S", "30")),
        help="Seconds between Capital snapshots (default: 30)",
    )
    parser.add_argument(
        "--history-recording",
        action="store_true",
        default=os.getenv("AUREON_RECORD_LIVE_WAVEFORM_HISTORY", "0") in ("1", "true", "TRUE", "yes", "YES"),
        help="Persist budgeted live cache bars into state/aureon_global_history.sqlite",
    )
    parser.add_argument(
        "--history-record-interval-s",
        type=float,
        default=float(os.getenv("AUREON_LIVE_WAVEFORM_RECORD_INTERVAL_S", "60")),
        help="Minimum seconds between live waveform history writes (default: 60)",
    )
    parser.add_argument(
        "--history-max-symbols",
        type=int,
        default=int(os.getenv("AUREON_LIVE_WAVEFORM_MAX_SYMBOLS", "512")),
        help="Maximum ticker entries recorded per history cycle (default: 512)",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        default=os.getenv("WS_FEED_QUIET", "0") in ("1", "true", "TRUE"),
        help="Reduce console output",
    )
    parser.add_argument(
        "--lock-path",
        default=os.getenv("AUREON_STREAM_FEEDER_LOCK_PATH", str(DEFAULT_FEEDER_LOCK_PATH)),
        help="Single-writer lock path (default: state/aureon_ws_market_data_feeder.lock)",
    )
    parser.add_argument(
        "--allow-duplicate",
        action="store_true",
        default=os.getenv("AUREON_ALLOW_DUPLICATE_STREAM_FEEDER", "0") in ("1", "true", "TRUE", "yes", "YES"),
        help="Allow multiple cache writers. Intended only for isolated tests.",
    )

    args = parser.parse_args()

    out_path = Path(args.out)
    lock_path = _acquire_single_writer_lock(Path(args.lock_path), out_path=out_path, allow_duplicate=args.allow_duplicate)
    atexit.register(_release_single_writer_lock, lock_path)
    history_recorder = (
        LiveWaveformHistoryRecorder(
            interval_s=args.history_record_interval_s,
            max_symbols=args.history_max_symbols,
            bucket_s=args.history_record_interval_s,
        )
        if args.history_recording
        else None
    )
    store = MarketSnapshotStore(out_path, history_recorder=history_recorder)
    if args.public_snapshot_port > 0:
        try:
            snapshot_server = start_public_snapshot_server(store, port=args.public_snapshot_port)
            def close_public_snapshot_server() -> None:
                snapshot_server.shutdown()
                snapshot_server.server_close()
            atexit.register(close_public_snapshot_server)
            if not args.quiet:
                print(f"Public quotes: http://127.0.0.1:{snapshot_server.server_port}/api/quotes")
        except OSError as exc:
            print(f"Loopback quote endpoint unavailable: {exc}; file cache remains enabled")
    kraken_pairs = _split_env_list(os.getenv("KRAKEN_STREAM_PAIRS", ""), KRAKEN_DEFAULT_PAIRS)
    alpaca_symbols = _split_env_list(os.getenv("ALPACA_STREAM_SYMBOLS", ""), ALPACA_DEFAULT_SYMBOLS)
    capital_symbols = _split_env_list(os.getenv("CAPITAL_STREAM_SYMBOLS", ""), CAPITAL_DEFAULT_SYMBOLS)

    async def _run() -> None:
        if no_external_api_calls():
            if args.binance and not args.quiet:
                print("Binance feed held: no_external_api_calls")
            args.binance = False
            await store.update("binance", _disabled_snapshot("binance", "held: no_external_api_calls"))
        tasks = []
        if args.binance:
            tasks.append(
                run_binance_all_tickers(
                    out_path=out_path,
                    binance_uk_mode=args.binance_uk_mode,
                    write_interval_s=max(0.1, args.write_interval_s),
                    quiet=args.quiet,
                    store=store,
                )
            )
        if args.kraken:
            tasks.append(
                run_budgeted_snapshot_feed(
                    source_key="kraken",
                    store=store,
                    interval_s=args.kraken_interval_s,
                    quiet=args.quiet,
                    builder=lambda: _build_kraken_snapshot(kraken_pairs),
                )
            )
        if args.alpaca:
            tasks.append(
                run_budgeted_snapshot_feed(
                    source_key="alpaca",
                    store=store,
                    interval_s=args.alpaca_interval_s,
                    quiet=args.quiet,
                    builder=lambda: _build_alpaca_snapshot(alpaca_symbols),
                )
            )
        else:
            await store.update("alpaca", _disabled_snapshot("alpaca", "alpaca_stream_snapshot_not_enabled"))
        if args.capital:
            tasks.append(
                run_budgeted_snapshot_feed(
                    source_key="capital",
                    store=store,
                    interval_s=args.capital_interval_s,
                    quiet=args.quiet,
                    builder=lambda: _build_capital_snapshot(capital_symbols),
                )
            )
        else:
            await store.update("capital", _disabled_snapshot("capital", "capital_stream_snapshot_not_enabled"))
        if not tasks:
            raise SystemExit("No feeds enabled")
        await asyncio.gather(*tasks)

    asyncio.run(_run())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
