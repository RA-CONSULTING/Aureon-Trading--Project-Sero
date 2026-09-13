"""Read-only local status API for the unified market runtime.

This server starts before the heavy trading/cognitive runtime. It gives the
frontend a stable heartbeat while the full trader imports, wires cognition, and
connects exchanges. The trader keeps writing state/unified_runtime_status.json;
this process only serves that file and never places orders.
"""

from __future__ import annotations

import argparse
import copy
import json
import math
import os
import re
import time
import threading
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from http.client import HTTPConnection, HTTPException
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from aureon.core.aureon_env import apply_env_aliases, env_presence
from aureon.harmonic.hnc_quantum_packet_crypto import (
    LEGACY_MASTER_KEY_ENV,
    MASTER_KEY_ENV,
    HNCPacketError,
    build_hnc_packet_evidence,
    encode_env_packet,
    is_env_packet,
    normalize_hnc_key_material,
    packet_master_key_from_env,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
STATE_ROOT = REPO_ROOT / "state"
STATUS_PATH = REPO_ROOT / "state" / "unified_runtime_status.json"
STREAM_CACHE_PATH = Path(os.getenv("WS_PRICE_CACHE_PATH") or (REPO_ROOT / "ws_cache" / "ws_prices.json"))
MARKET_INTENT_PATH = STATE_ROOT / "aureon_market_reboot_intent.json"
ENV_UPDATE_INTENT_PATH = STATE_ROOT / "aureon_env_update_intent.json"
HNC_PACKET_EVIDENCE_PATH = STATE_ROOT / "aureon_hnc_quantum_packet_last_run.json"
WORLD_FINANCIAL_ECOSYSTEM_STATE_PATH = STATE_ROOT / "aureon_world_financial_ecosystem_intelligence.json"
PRISM_FREQUENCY_STATE_PATH = STATE_ROOT / "aureon_prism_frequency.json"
HNC_SYMBOLIC_ROUTE_SEAL_STATE_PATH = STATE_ROOT / "aureon_hnc_symbolic_route_seal.json"
SCANNER_FUSION_MATRIX_STATE_PATH = STATE_ROOT / "aureon_scanner_fusion_matrix.json"
PROBABILITY_FUSION_STATE_PATH = STATE_ROOT / "aureon_probability_fusion.json"
DECISION_TRACE_LOG_PATH = STATE_ROOT / "aureon_decision_traces.jsonl"
ENV_PATH = Path(os.getenv("AUREON_ENV_FILE") or (REPO_ROOT / ".env")).expanduser()
CREDENTIAL_UPDATE_FILESYSTEM_HOLD = "credential_update_filesystem_release_hold"
CREDENTIAL_STATUS_READ_HOLD = "credential_status_read_release_hold"
HOST = "127.0.0.1"
STATUS_FILE_STALE_AFTER_SEC = float(os.getenv("UNIFIED_STATUS_FILE_STALE_AFTER_SEC", "60") or 60)
TICK_STALE_AFTER_SEC = float(os.getenv("UNIFIED_READY_STALE_AFTER_SEC", "45") or 45)
STREAM_MEMORY_PORT = 8794
STREAM_MEMORY_TIMEOUT_SEC = 0.25
STREAM_MEMORY_MAX_BYTES = 1024 * 1024
_runtime_file_cache = None
_stream_file_cache = None


def _load_json_file_snapshot(path: Path) -> dict[str, Any]:
    """Run only on the file reader in production; preserve the opened file's mtime."""
    try:
        for attempt in range(3):
            try:
                with path.open("r", encoding="utf-8") as handle:
                    payload = json.load(handle)
                    mtime = os.fstat(handle.fileno()).st_mtime
                break
            except PermissionError:
                if attempt == 2:
                    raise
                time.sleep(0.01)
        if not isinstance(payload, dict):
            raise ValueError("JSON object required")
        return {"payload": payload, "mtime": mtime, "read_at": time.time(), "state": "observed"}
    except FileNotFoundError:
        return {"payload": None, "mtime": None, "read_at": time.time(), "state": "missing"}
    except (OSError, ValueError, TypeError) as exc:
        return {"payload": None, "mtime": None, "read_at": time.time(), "state": "failed", "error": type(exc).__name__}


class _BackgroundFileSnapshot:
    """One replaceable file snapshot; no file operations run under the read lock."""
    def __init__(self, path: Path, interval_sec: float = 0.5):
        self.path = path
        self.interval_sec = interval_sec
        self._snapshot = {"payload": None, "mtime": None, "read_at": None, "state": "pending"}
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = None

    def refresh(self) -> None:
        snapshot = _load_json_file_snapshot(self.path)
        with self._lock:
            self._snapshot = snapshot

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return self._snapshot

    def _run(self) -> None:
        while not self._stop.is_set():
            self.refresh()
            self._stop.wait(self.interval_sec)

    def start(self) -> None:
        if self._thread is None:
            self._thread = threading.Thread(target=self._run, name=f"status-file-reader:{self.path.name}", daemon=True)
            self._thread.start()

    def stop(self) -> None:
        self._stop.set()


def _read_live_market_cache() -> dict[str, Any] | None:
    """Read only the fixed loopback feeder endpoint, without proxies or redirects."""
    connection = HTTPConnection("127.0.0.1", STREAM_MEMORY_PORT, timeout=STREAM_MEMORY_TIMEOUT_SEC)
    try:
        connection.request("GET", "/api/quotes", headers={"Accept": "application/json"})
        response = connection.getresponse()
        if response.status != 200:
            return None
        length = response.getheader("Content-Length")
        if length is None or not 0 < int(length) <= STREAM_MEMORY_MAX_BYTES:
            return None
        raw = response.read(int(length))
        if len(raw) != int(length):
            return None
        payload = json.loads(raw)
        return payload if isinstance(payload, dict) and isinstance(payload.get("ticker_cache"), dict) else None
    except (OSError, ValueError, TypeError, HTTPException):
        return None
    finally:
        connection.close()


def _is_local_browser_origin(origin: str) -> bool:
    if not isinstance(origin, str) or not origin:
        return False
    try:
        parsed = urlsplit(origin)
        return (
            parsed.scheme in {"http", "https"}
            and parsed.hostname in {"127.0.0.1", "::1", "localhost"}
            and parsed.username is None
            and parsed.password is None
            and parsed.path in {"", "/"}
            and not parsed.query
            and not parsed.fragment
        )
    except ValueError:
        return False
TICK_RUNNING_STALE_AFTER_SEC = max(
    TICK_STALE_AFTER_SEC,
    float(os.getenv("UNIFIED_TICK_RUNNING_STALE_AFTER_SEC", "600") or 600),
)

EXCHANGE_ENV_FIELDS: dict[str, tuple[str, ...]] = {
    "binance": ("BINANCE_API_KEY", "BINANCE_API_SECRET"),
    "kraken": ("KRAKEN_API_KEY", "KRAKEN_API_SECRET"),
    "alpaca": ("ALPACA_API_KEY", "ALPACA_SECRET_KEY"),
    "capital": ("CAPITAL_API_KEY", "CAPITAL_IDENTIFIER", "CAPITAL_PASSWORD"),
}

FRIENDLY_CREDENTIAL_KEYS: dict[str, dict[str, str]] = {
    "binance": {"binanceApiKey": "BINANCE_API_KEY", "binanceApiSecret": "BINANCE_API_SECRET"},
    "kraken": {"krakenApiKey": "KRAKEN_API_KEY", "krakenApiSecret": "KRAKEN_API_SECRET"},
    "alpaca": {"alpacaApiKey": "ALPACA_API_KEY", "alpacaSecretKey": "ALPACA_SECRET_KEY"},
    "capital": {
        "capitalApiKey": "CAPITAL_API_KEY",
        "capitalIdentifier": "CAPITAL_IDENTIFIER",
        "capitalPassword": "CAPITAL_PASSWORD",
    },
}

ENV_KEY_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")


def _parse_iso_timestamp(value: Any) -> float:
    if not value:
        return 0.0
    try:
        text = str(value).strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        return datetime.fromisoformat(text).timestamp()
    except Exception:
        return 0.0


def _runtime_watchdog(payload: dict[str, Any], status_file_age_sec: float | None = None) -> dict[str, Any]:
    existing = payload.get("runtime_watchdog")
    watchdog = dict(existing) if isinstance(existing, dict) else {}

    now = time.time()
    last_completed_ts = _parse_iso_timestamp(payload.get("last_tick_completed_at"))
    last_started_ts = _parse_iso_timestamp(payload.get("last_tick_started_at"))
    last_tick_age_sec = payload.get("last_tick_age_sec")
    try:
        stored_age = float(last_tick_age_sec) if last_tick_age_sec is not None else None
        measured_age = max(0.0, now - last_completed_ts) if last_completed_ts else None
        ages = [age for age in (stored_age, measured_age) if age is not None]
        last_tick_age = max(ages) if ages else None
    except Exception:
        last_tick_age = None
    tick_running_sec = max(0.0, now - last_started_ts) if last_started_ts > last_completed_ts else 0.0

    existing_reason = str(payload.get("stale_reason") or watchdog.get("tick_stale_reason") or "")
    active_tick = bool(last_started_ts > last_completed_ts)
    stale_reason = ""
    tick_stale = False
    if not active_tick and last_tick_age is not None and last_tick_age > TICK_STALE_AFTER_SEC:
        tick_stale = True
        stale_reason = "last_tick_age_exceeded"
    if active_tick and tick_running_sec > TICK_RUNNING_STALE_AFTER_SEC:
        tick_stale = True
        stale_reason = "tick_in_progress_stalled"
    # Honor the runtime's own stale flag unless fresh tick-age data proves
    # otherwise. The old gate required a NON-empty custom reason, so an
    # explicit ``stale: true`` with no reason string was silently ignored —
    # with open positions that downgraded a critical position-monitor hold
    # to "healthy".
    tick_provably_fresh = (
        not active_tick
        and last_tick_age is not None
        and last_tick_age <= TICK_STALE_AFTER_SEC
    )
    if not tick_stale and not tick_provably_fresh and bool(payload.get("stale") or watchdog.get("tick_stale")):
        tick_stale = True
        stale_reason = existing_reason or "runtime_reported_stale"

    status_file_fresh = status_file_age_sec is None or status_file_age_sec <= STATUS_FILE_STALE_AFTER_SEC
    open_positions = _has_open_positions(payload)
    severity = "critical" if tick_stale and open_positions else "degraded" if tick_stale else "healthy"
    recovery_action = (
        "preserve_position_monitoring_and_defer_restart_until_flat_downtime"
        if tick_stale and open_positions
        else "restart_in_downtime_window"
        if tick_stale
        else "none"
    )

    watchdog.update(
        {
            "status_file_fresh": status_file_fresh,
            "status_file_age_sec": round(float(status_file_age_sec), 3) if status_file_age_sec is not None else None,
            "heartbeat_fresh_but_tick_stale": bool(status_file_fresh and tick_stale),
            "tick_stale": tick_stale,
            "tick_stale_reason": stale_reason,
            "tick_stale_after_sec": TICK_STALE_AFTER_SEC,
            "tick_active": active_tick,
            "tick_long_running": bool(active_tick and tick_running_sec > TICK_STALE_AFTER_SEC),
            "tick_running_stale_after_sec": TICK_RUNNING_STALE_AFTER_SEC,
            "last_tick_age_sec": round(float(last_tick_age), 3) if last_tick_age is not None else None,
            "last_tick_running_sec": round(float(tick_running_sec), 3) if tick_running_sec > 0 else 0.0,
            "open_positions": open_positions,
            "severity": severity,
            "recovery_action": recovery_action,
        }
    )
    return watchdog


def _read_market_stream() -> dict[str, Any]:
    """Observe the feeder's memory snapshot, falling back to its original file quotes."""
    now = time.time()
    observed_at = datetime.now(timezone.utc).isoformat()
    result: dict[str, Any] = {
        "source": "ws_market_data_feeder", "mode": "observed_market_cache",
        "fresh": False, "symbol_count": 0, "max_age_sec": 5.0,
        "reason": "no_fresh_stream_tickers", "generated_at": observed_at,
        "observed_at": observed_at, "quotes": [],
    }
    try:
        cache = _read_live_market_cache()
        if cache is not None:
            result["transport"] = "loopback_memory"
            result["producer_pid"] = cache.get("producer_pid")
        else:
            snapshot = _stream_file_cache.snapshot() if _stream_file_cache is not None else _load_json_file_snapshot(STREAM_CACHE_PATH)
            cache = snapshot.get("payload")
            result.update(transport="file_snapshot", file_read_state=snapshot.get("state"), file_read_at=snapshot.get("read_at"))
            if not isinstance(cache, dict):
                result["reason"] = "market_cache_unavailable_or_invalid"
                return result
        now = time.time()
        observed_at = datetime.now(timezone.utc).isoformat()
        result.update(generated_at=observed_at, observed_at=observed_at)
        quotes = []
        seen = set()
        for key, ticker in cache.get("ticker_cache", {}).items():
            if not isinstance(ticker, dict):
                continue
            try:
                timestamp = float(ticker.get("timestamp", 0))
                price = float(ticker.get("price", 0))
            except (TypeError, ValueError):
                continue
            age = now - timestamp
            if not math.isfinite(timestamp) or not math.isfinite(price) or price <= 0 or not -5 <= age <= 5:
                continue
            identity = (ticker.get("source") or ticker.get("exchange"), ticker.get("symbol") or ticker.get("pair") or key)
            if identity in seen:
                continue
            seen.add(identity)
            quotes.append({
                "symbol": ticker.get("symbol") or ticker.get("pair") or key,
                "base": ticker.get("base"), "quote": ticker.get("quote"),
                "price": price,
                "bid": ticker.get("bid") if isinstance(ticker.get("bid"), (int, float)) and ticker["bid"] > 0 else None,
                "ask": ticker.get("ask") if isinstance(ticker.get("ask"), (int, float)) and ticker["ask"] > 0 else None,
                "source": ticker.get("source") or ticker.get("exchange"),
                "timestamp": timestamp, "timestamp_kind": ticker.get("timestamp_kind", "cache_timestamp"),
                "age_sec": round(max(0, age), 3),
            })
        preferred = {"BTC": 0, "ETH": 1, "SOL": 2, "XRP": 3}
        quotes.sort(key=lambda q: (preferred.get(q.get("base"), 10), str(q.get("symbol"))))
        result["symbol_count"] = len(quotes)
        result["quotes"] = quotes[:16]
        if quotes:
            result.update(fresh=True, reason="fresh_provider_market_quotes",
                          newest_selected_age_sec=min(q["age_sec"] for q in quotes),
                          oldest_selected_age_sec=max(q["age_sec"] for q in quotes))
    except (OSError, ValueError, TypeError, AttributeError):
        result["reason"] = "market_cache_unavailable_or_invalid"
    return result


def _read_runtime_status() -> dict[str, Any]:
    snapshot = _runtime_file_cache.snapshot() if _runtime_file_cache is not None else _load_json_file_snapshot(STATUS_PATH)
    if isinstance(snapshot.get("payload"), dict):
        try:
            payload = copy.deepcopy(snapshot["payload"])
            if isinstance(payload, dict):
                mtime = snapshot["mtime"]
                age_sec = max(0.0, time.time() - mtime)
                payload.setdefault("ok", True)
                payload.setdefault("source", "unified-market-status-server")
                payload.setdefault(
                    "generated_at",
                    payload.get("dashboard_generated_at")
                    or payload.get("last_tick_completed_at")
                    or datetime.fromtimestamp(mtime, timezone.utc).isoformat(),
                )
                payload["status_file"] = str(STATUS_PATH)
                payload["status_file_mtime"] = datetime.fromtimestamp(mtime, timezone.utc).isoformat()
                payload["status_file_read_at"] = snapshot.get("read_at")
                payload["status_file_read_state"] = snapshot.get("state")
                payload["status_file_age_sec"] = round(age_sec, 3)
                payload["runtime_watchdog"] = _runtime_watchdog(payload, age_sec)
                payload["observed_at"] = datetime.now(timezone.utc).isoformat()
                payload["last_tick_age_sec"] = payload["runtime_watchdog"].get("last_tick_age_sec")
                payload["tick_stale_after_sec"] = TICK_STALE_AFTER_SEC
                # A running cycle is process liveness, not fresh completed data.
                # Only downgrade to stale based on last-completed age when the
                # runtime is not actively inside a tick that is still within the
                # long-running stall threshold.
                watchdog = payload["runtime_watchdog"]
                tick_active = bool(watchdog.get("tick_active"))
                tick_running_sec = float(watchdog.get("last_tick_running_sec") or 0.0)
                tick_age = payload["last_tick_age_sec"]
                if tick_active and tick_running_sec >= 1.0 and tick_running_sec <= TICK_RUNNING_STALE_AFTER_SEC:
                    if not watchdog.get("tick_stale"):
                        payload["stale"] = False
                        if str(payload.get("stale_reason") or "") == "last_completed_tick_unavailable_or_expired":
                            payload["stale_reason"] = ""
                elif tick_age is None or tick_age > TICK_STALE_AFTER_SEC:
                    payload["stale"] = True
                    payload["stale_reason"] = "last_completed_tick_unavailable_or_expired"
                if watchdog.get("tick_stale"):
                    payload["stale"] = True
                    payload["stale_reason"] = watchdog.get("tick_stale_reason")
                elif str(payload.get("stale_reason") or "") in {"last_tick_age_exceeded", "tick_in_progress_stalled"}:
                    payload["stale"] = False
                    payload["stale_reason"] = ""
                payload.setdefault("stale_reason", "")
                if (
                    not payload.get("stale")
                    and bool(payload.get("trading_ready"))
                    and bool(payload.get("data_ready"))
                    and not bool(payload.get("duplicate_runtime"))
                ):
                    payload["ok"] = True
                if age_sec > STATUS_FILE_STALE_AFTER_SEC:
                    payload["stale"] = True
                    payload.setdefault("warnings", [])
                    if isinstance(payload["warnings"], list):
                        payload["warnings"].append("runtime_status_file_stale")
                if payload.get("stale"):
                    payload["ok"] = False
                return payload
        except Exception as exc:
            return {
                "ok": False,
                "source": "unified-market-status-server",
                "error": f"status_file_read_failed: {exc}",
                "status_file": str(STATUS_PATH),
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }

    if snapshot.get("state") == "failed":
        return {"ok": False, "stale": True, "source": "unified-market-status-server",
                "error": f"status_file_read_failed: {snapshot.get('error', 'unknown')}",
                "status_file": str(STATUS_PATH), "status_file_read_state": "failed",
                "status_file_read_at": snapshot.get("read_at"), "generated_at": datetime.now(timezone.utc).isoformat()}

    return {
        "ok": True,
        "source": "unified-market-status-server",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "service": "unified-market-trader",
        "trading_ready": False,
        "data_ready": False,
        "stale": True,
        "lines": "UNIFIED MARKET STATUS | Runtime status server is awake. Trader is still booting.",
        "terminal_lines": [
            "UNIFIED MARKET STATUS",
            "Runtime status server is awake.",
            "Trader is still booting and wiring exchange/cognitive systems.",
        ],
        "status_file": str(STATUS_PATH),
        "status_file_read_state": snapshot.get("state"),
        "status_file_read_at": snapshot.get("read_at"),
        "combined": {
            "open_positions": 0,
            "kraken_equity": 0.0,
            "capital_equity_gbp": 0.0,
        },
        "exchanges": {
            "kraken_ready": False,
            "capital_ready": False,
            "alpaca_ready": False,
            "binance_ready": False,
        },
    }




def _load_state_file_receipt(path: Path) -> dict[str, Any]:
    """Read a published state file and return a UI-backed receipt."""
    missing_receipt = {
        "path": str(path),
        "available": False,
        "truth_status": "no_data",
        "generated_values": False,
        "source_timestamp": None,
        "source_timestamp_iso": None,
        "expires_at": None,
        "expires_at_iso": None,
        "source": None,
        "reason": "state_file_missing",
        "state": "missing",
    }
    try:
        if not path.exists():
            return missing_receipt
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            return {
                **missing_receipt,
                "reason": "state_file_invalid",
                "state": "invalid",
            }
        generated_at = payload.get("generated_at")
        source_ts = _parse_iso_timestamp(generated_at) if generated_at else path.stat().st_mtime
        if source_ts <= 0:
            source_ts = time.time()
        expires_ts = source_ts + 3600.0
        source_dt = datetime.fromtimestamp(source_ts, tz=timezone.utc)
        expires_dt = datetime.fromtimestamp(expires_ts, tz=timezone.utc)
        receipt: dict[str, Any] = {
            "path": str(path),
            "available": True,
            "truth_status": "real_derived",
            "generated_values": False,
            "source_timestamp": source_ts,
            "source_timestamp_iso": source_dt.isoformat(),
            "expires_at": expires_ts,
            "expires_at_iso": expires_dt.isoformat(),
            "source": str(path),
            "reason": "observed",
            "generated_at": generated_at,
            "schema_version": payload.get("schema_version"),            "enabled": payload.get("enabled"),            "mode": payload.get("mode"),
            "summary": payload.get("summary"),
            "decision_symbol_count": payload.get("decision_symbol_count")
            if "decision_symbol_count" in payload
            else len(payload.get("decision_symbols", {})) if isinstance(payload.get("decision_symbols"), dict) else None,
        }
        # Pass through payload-specific fields expected by the frontend.
        for key in (
            "frequency", "level", "resonance", "harmonic_purity", "love_locked",
            "layers", "state", "coherence", "global_resonance", "market_energy",
            "ecosystem_coherence", "dominant_frequency", "active_waveforms",
            "systems", "sources", "prime_coherence", "seal_lock", "systems_contributing",
            "consensus_signal", "intent_text", "packet_value", "fused_probability",
            "fusedProbability", "action", "confidence", "wave_state", "waveState",
            "harmonic_lock", "harmonicLock", "probability_6d", "probability6D",
            "probability_hnc", "probabilityHNC", "probability_lighthouse",
            "probabilityLighthouse", "weight_6d", "weight6D", "weight_hnc",
            "weightHNC", "weight_lighthouse", "weightLighthouse", "resonance_boost",
            "resonanceBoost",
        ):
            if key in payload:
                receipt[key] = payload[key]
        # Normalize ecosystem systems array to the dict expected by the UI.
        systems = receipt.get("systems")
        if isinstance(systems, list):
            normalized: dict[str, Any] = {}
            for entry in systems:
                if not isinstance(entry, dict):
                    continue
                name = entry.get("name")
                if not isinstance(name, str) or not name:
                    continue
                fresh = entry.get("fresh") is True
                usable = entry.get("usable_for_decision") is True
                normalized[name] = {
                    "available": fresh and usable,
                    "truth_status": "real_derived",
                    "generated_values": False,
                    "coherence": 1.0 if fresh and usable else 0.0,
                    "value": 1.0 if fresh and usable else 0.0,
                    "status": entry.get("reason") or "Runtime system observed.",
                    "reason": entry.get("blocker") or "Runtime system observed.",
                    "source_timestamp": source_ts,
                    "source_timestamp_iso": source_dt.isoformat(),
                    "source": str(path),
                }
            receipt["systems"] = normalized
        # Normalize ecosystem sources array to the systems dict expected by the UI.
        sources = receipt.get("sources")
        if isinstance(sources, list):
            normalized_sources: dict[str, Any] = {}
            for entry in sources:
                if not isinstance(entry, dict):
                    continue
                name = entry.get("system")
                if not isinstance(name, str) or not name:
                    continue
                fresh = entry.get("fresh") is True
                usable = entry.get("usable_for_decision") is True
                normalized_sources[name] = {
                    "available": fresh and usable,
                    "truth_status": "real_derived",
                    "generated_values": False,
                    "coherence": 1.0 if fresh and usable else 0.0,
                    "value": 1.0 if fresh and usable else 0.0,
                    "status": entry.get("reason") or "Runtime source observed.",
                    "reason": entry.get("blocker") or "Runtime source observed.",
                    "source_timestamp": source_ts,
                    "source_timestamp_iso": source_dt.isoformat(),
                    "source": str(path),
                }
            if not isinstance(receipt.get("systems"), dict):
                receipt["systems"] = {}
            receipt["systems"].update(normalized_sources)
        # Derive ecosystem scalar metrics from available source counts.
        if "global_resonance" not in receipt:
            active_count = payload.get("active_source_count")
            usable_count = payload.get("usable_source_count")
            if isinstance(active_count, int) and isinstance(usable_count, int) and active_count > 0:
                receipt["global_resonance"] = usable_count / active_count
        if "ecosystem_coherence" not in receipt:
            active_count = payload.get("active_source_count")
            usable_count = payload.get("usable_source_count")
            if isinstance(active_count, int) and isinstance(usable_count, int) and active_count > 0:
                receipt["ecosystem_coherence"] = usable_count / active_count
        if "active_waveforms" not in receipt:
            source_rows = payload.get("sources")
            if isinstance(source_rows, list):
                receipt["active_waveforms"] = [
                    str(s.get("system")) for s in source_rows
                    if isinstance(s, dict) and s.get("fresh") is True and isinstance(s.get("system"), str)
                ]
        # Derive Prism UI fields from runtime publisher output if not present.
        if "prism_state" in payload or "prism_result" in payload:
            prism_state = payload.get("prism_state") if isinstance(payload.get("prism_state"), dict) else {}
            prism_result = payload.get("prism_result") if isinstance(payload.get("prism_result"), dict) else {}
            level_values = prism_result.get("level_values") if isinstance(prism_result.get("level_values"), dict) else {}
            levels = {int(key.split("_")[0][1:]) for key in level_values if isinstance(key, str) and key.startswith("L") and "_" in key}
            if "frequency" not in receipt:
                receipt["frequency"] = prism_state.get("prism_output") if isinstance(prism_state.get("prism_output"), (int, float)) else prism_result.get("prism_output")
            if "level" not in receipt:
                receipt["level"] = max(levels) if levels else None
            if "resonance" not in receipt:
                receipt["resonance"] = prism_state.get("resonance") if isinstance(prism_state.get("resonance"), (int, float)) else prism_result.get("resonance")
            if "harmonic_purity" not in receipt:
                receipt["harmonic_purity"] = payload.get("coherence") if isinstance(payload.get("coherence"), (int, float)) else prism_state.get("coherence_index")
            if "state" not in receipt:
                is_love = bool(prism_state.get("is_love") or prism_result.get("is_love"))
                is_pure = bool(prism_state.get("is_pure") or prism_result.get("is_pure"))
                is_aligned = bool(prism_state.get("is_aligned") or prism_result.get("is_aligned"))
                if is_love:
                    receipt["state"] = "LOVE"
                elif is_pure:
                    receipt["state"] = "PURE"
                elif is_aligned:
                    receipt["state"] = "ALIGNED"
                else:
                    receipt["state"] = "RESONANT"
            if "love_locked" not in receipt:
                receipt["love_locked"] = bool(prism_state.get("is_love") or prism_result.get("is_love"))
            if "layers" not in receipt and level_values:
                receipt["layers"] = {k: v for k, v in level_values.items() if isinstance(v, (int, float))}
        # Flatten HNC symbolic route seal fields if the runtime uses nested shapes.
        seal = payload.get("seal") if isinstance(payload.get("seal"), dict) else {}
        summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
        if seal or summary:
            catalog_summary = seal.get("catalog_summary") if isinstance(seal.get("catalog_summary"), dict) else {}
            route = seal.get("route") if isinstance(seal.get("route"), dict) else {}
            selected_rune = route.get("selected_rune") if isinstance(route.get("selected_rune"), dict) else {}
            star_symbols = route.get("selected_star_symbols") if isinstance(route.get("selected_star_symbols"), dict) else {}
            auris = route.get("selected_auris_symbol") if isinstance(route.get("selected_auris_symbol"), dict) else {}
            if "prime_coherence" not in receipt:
                catalog_count = catalog_summary.get("catalog_count") if isinstance(catalog_summary.get("catalog_count"), int) else 0
                catalogs_present = catalog_summary.get("catalogs_present") if isinstance(catalog_summary.get("catalogs_present"), int) else 0
                provenance_count = catalog_summary.get("provenance_count") if isinstance(catalog_summary.get("provenance_count"), int) else 0
                provenance_present = catalog_summary.get("provenance_present") if isinstance(catalog_summary.get("provenance_present"), int) else 0
                ratios: list[float] = []
                if catalog_count > 0:
                    ratios.append(catalogs_present / catalog_count)
                if provenance_count > 0:
                    ratios.append(provenance_present / provenance_count)
                receipt["prime_coherence"] = sum(ratios) / len(ratios) if ratios else (1.0 if summary.get("valid") is True else 0.0)
            if "seal_lock" not in receipt:
                receipt["seal_lock"] = summary.get("valid") is True or seal.get("valid") is True
            if "systems_contributing" not in receipt:
                contributors: list[str] = []
                for key, entry in star_symbols.items():
                    if isinstance(entry, dict) and entry.get("name"):
                        contributors.append(str(entry["name"]))
                if isinstance(auris, dict) and auris.get("name"):
                    contributors.append(str(auris["name"]))
                if selected_rune.get("name"):
                    contributors.append(str(selected_rune["name"]))
                receipt["systems_contributing"] = contributors
            if "consensus_signal" not in receipt:
                rune_signal = selected_rune.get("trading_signal") if isinstance(selected_rune.get("trading_signal"), dict) else {}
                receipt["consensus_signal"] = rune_signal.get("bias") if rune_signal.get("bias") else "NEUTRAL"
            if "intent_text" not in receipt:
                receipt["intent_text"] = seal.get("purpose") or summary.get("purpose") or "Observing"
            if "packet_value" not in receipt:
                symbol_count = catalog_summary.get("symbol_count") if isinstance(catalog_summary.get("symbol_count"), int) else 0
                receipt["packet_value"] = float(symbol_count)
        return receipt
    except Exception as exc:
        return {
            **missing_receipt,
            "reason": f"state_file_failed: {type(exc).__name__}",
            "state": "failed",
            "error": type(exc).__name__,
        }


def _decision_trace_tail(path: Path, n: int = 16) -> list[dict[str, Any]]:
    try:
        if not path.exists():
            return []
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        out = []
        for line in reversed(lines):
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except Exception:
                continue
            if isinstance(record, dict):
                out.append(record)
                if len(out) >= n:
                    break
        return list(reversed(out))
    except Exception:
        return []


def _enrich_terminal_state(payload: dict[str, Any]) -> None:
    """Add live publisher receipts and provider position metadata to the status payload."""
    if not isinstance(payload, dict):
        return
    payload.setdefault("ecosystem_receipt", _load_state_file_receipt(WORLD_FINANCIAL_ECOSYSTEM_STATE_PATH))
    payload.setdefault("prism_receipt", _load_state_file_receipt(PRISM_FREQUENCY_STATE_PATH))
    payload.setdefault("prime_seal_receipt", _load_state_file_receipt(HNC_SYMBOLIC_ROUTE_SEAL_STATE_PATH))
    payload.setdefault("probability_fusion_receipt", _load_state_file_receipt(PROBABILITY_FUSION_STATE_PATH))

    provider_positions = payload.get("provider_positions")
    if not isinstance(provider_positions, dict):
        provider_positions = {}
        for venue in ("kraken", "capital", "alpaca", "binance"):
            venue_payload = payload.get(venue) if isinstance(payload.get(venue), dict) else {}
            positions = venue_payload.get("positions") if isinstance(venue_payload.get("positions"), list) else []
            provider_positions[venue] = {
                "available": bool(venue_payload.get("ok") or venue_payload.get("data_status") == "live"),
                "count": len(positions),
                "truth_status": "real_observed" if positions else "no_data",
                "reason": "provider_positions_observed" if positions else "no_positions_observed",
                "source_timestamp": None,
                "positions": positions[:16],
            }
        payload["provider_positions"] = provider_positions

    if not payload.get("decision_traces"):
        payload["decision_traces"] = _decision_trace_tail(DECISION_TRACE_LOG_PATH)
    if not payload.get("decision_latency_percentiles"):
        try:
            from aureon.trading.decision_trace import decision_trace_percentiles
            payload["decision_latency_percentiles"] = decision_trace_percentiles(DECISION_TRACE_LOG_PATH)
        except Exception:
            payload["decision_latency_percentiles"] = {}

def _read_status() -> dict[str, Any]:
    payload = _read_runtime_status()
    payload.setdefault("data_ready", False)
    _enrich_terminal_state(payload)
    payload.setdefault("trading_ready", False)
    payload.setdefault("stale", True)
    payload["observed_at"] = datetime.now(timezone.utc).isoformat()
    payload["decision_stream_cache"] = payload.get("live_stream_cache")
    payload["live_stream_cache"] = _read_market_stream()
    # Legacy producer clocks are local naive datetimes. Resolve their instant
    # on the producer host before sending them to browsers in other timezones.
    for record, fields in (
        (payload, ("generated_at", "dashboard_generated_at", "last_tick_completed_at", "last_tick_started_at", "status_file_mtime")),
        (payload.get("analysis_snapshot"), ("generated_at",)),
        (payload.get("hnc_cognitive_proof"), ("generated_at",)),
        (payload.get("runtime_writer"), ("heartbeat_at",)),
    ):
        if not isinstance(record, dict):
            continue
        for field in fields:
            value = record.get(field)
            if isinstance(value, str):
                epoch = _parse_iso_timestamp(value)
                if epoch > 0:
                    record[field] = datetime.fromtimestamp(epoch, timezone.utc).isoformat()
    return payload


def _day_allowed(day_name: str, allowed_days: str | None) -> bool:
    raw = (allowed_days or "Sun").strip().lower()
    if raw in {"*", "all", "daily", "everyday"}:
        return True
    names = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
    current = day_name[:3].lower()
    for part in raw.replace(";", ",").split(","):
        item = part.strip()
        if not item:
            continue
        if item == current or item == day_name.lower():
            return True
        if "-" in item:
            start_raw, end_raw = [piece.strip()[:3].lower() for piece in item.split("-", 1)]
            if start_raw in names and end_raw in names and current in names:
                start = names.index(start_raw)
                end = names.index(end_raw)
                now = names.index(current)
                if start <= end and start <= now <= end:
                    return True
                if start > end and (now >= start or now <= end):
                    return True
    return False


def _parse_clock(value: str | None, fallback: str) -> tuple[int, int]:
    raw = value or fallback
    try:
        hour_raw, minute_raw = raw.split(":", 1)
        return max(0, min(23, int(hour_raw))), max(0, min(59, int(minute_raw)))
    except Exception:
        hour_raw, minute_raw = fallback.split(":", 1)
        return int(hour_raw), int(minute_raw)


def _market_downtime_window() -> bool:
    days = os.getenv("AUREON_MARKET_DOWNTIME_DAYS") or os.getenv("AUREON_MIND_DOWNTIME_DAYS") or "Sun"
    start_h, start_m = _parse_clock(
        os.getenv("AUREON_MARKET_DOWNTIME_START_LOCAL") or os.getenv("AUREON_MIND_DOWNTIME_START_LOCAL"),
        "03:00",
    )
    end_h, end_m = _parse_clock(
        os.getenv("AUREON_MARKET_DOWNTIME_END_LOCAL") or os.getenv("AUREON_MIND_DOWNTIME_END_LOCAL"),
        "03:15",
    )
    now = datetime.now()
    start = now.replace(hour=start_h, minute=start_m, second=0, microsecond=0)
    end = now.replace(hour=end_h, minute=end_m, second=0, microsecond=0)
    if end <= start:
        end += timedelta(days=1)
    if _day_allowed(now.strftime("%A"), days) and start <= now < end:
        return True
    if end_h < start_h or (end_h == start_h and end_m <= start_m):
        yesterday = now - timedelta(days=1)
        previous_start = start - timedelta(days=1)
        previous_end = end - timedelta(days=1)
        if _day_allowed(yesterday.strftime("%A"), days) and previous_start <= now < previous_end:
            return True
    return False


def _read_market_intent() -> dict[str, Any] | None:
    try:
        if not MARKET_INTENT_PATH.exists():
            return None
        payload = json.loads(MARKET_INTENT_PATH.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            return payload
    except Exception:
        return None
    return None


def _read_env_update_intent() -> dict[str, Any] | None:
    try:
        if not ENV_UPDATE_INTENT_PATH.exists():
            return None
        payload = json.loads(ENV_UPDATE_INTENT_PATH.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            return payload
    except Exception:
        return None
    return None


def _parse_env_values(path: Path | None = None) -> dict[str, str]:
    target = path or ENV_PATH
    values: dict[str, str] = {}
    if not target.exists():
        return values
    for raw_line in target.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not ENV_KEY_RE.match(key):
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values[key] = value
    return values


def _env_packet_master_key(env_values: dict[str, str] | None = None) -> str:
    values = env_values or _parse_env_values()
    return packet_master_key_from_env(os.environ) or str(
        values.get(MASTER_KEY_ENV) or values.get(LEGACY_MASTER_KEY_ENV) or ""
    )


def _env_packet_master_key_status(master_key: str) -> dict[str, Any]:
    """Report whether configured key material meets the active write policy.

    The public status deliberately contains no key value, fingerprint, or
    length. A malformed key is configured but cannot truthfully be reported as
    enabling packet encryption.
    """

    if not master_key:
        return {"configured": False, "valid": False, "error_code": None}
    try:
        normalize_hnc_key_material(master_key)
    except HNCPacketError:
        return {
            "configured": True,
            "valid": False,
            "error_code": "hnc_master_key_invalid",
        }
    return {"configured": True, "valid": True, "error_code": None}


def _packetize_env_updates(
    updates: dict[str, str],
) -> tuple[dict[str, str], list[str], dict[str, Any]]:
    master_key = _env_packet_master_key()
    if not master_key:
        raise HNCPacketError("credential_update_requires_valid_hnc_master_key")
    normalize_hnc_key_material(master_key)
    stored: dict[str, str] = {}
    encrypted_keys: list[str] = []
    for key, value in updates.items():
        token = encode_env_packet(value, master_key, env_key=key)
        stored[key] = token
        encrypted_keys.append(key)
    evidence = build_hnc_packet_evidence(stored)
    return stored, sorted(encrypted_keys), evidence


def _write_env_updates(updates: dict[str, str]) -> dict[str, Any]:
    # The public credential writer is not released.  Hold before inspecting or
    # creating any filesystem path so neither plaintext nor encrypted values
    # can be persisted through this local status server.
    raise HNCPacketError(CREDENTIAL_UPDATE_FILESYSTEM_HOLD)


def _env_credentials_status() -> dict[str, Any]:
    env_values = _parse_env_values()
    apply_env_aliases(env_values, override=False)
    master_key = _env_packet_master_key(env_values)
    master_key_status = _env_packet_master_key_status(master_key)
    packet_encoded_keys = sorted(key for key, value in env_values.items() if is_env_packet(value))
    exchanges: dict[str, Any] = {}
    for exchange, keys in EXCHANGE_ENV_FIELDS.items():
        presence = env_presence(keys, env_values)
        missing = [key for key, meta in presence.items() if not meta.get("set")]
        exchanges[exchange] = {
            "present": not missing,
            "missing_keys": missing,
            "keys": presence,
        }
    intent = _read_env_update_intent()
    pending_restart = bool(intent and intent.get("status") == "pending")
    return {
        "ok": True,
        "service": "unified-market-status-server",
        "generated_at": datetime.now().isoformat(),
        "env_file": str(ENV_PATH),
        "env_file_exists": ENV_PATH.exists(),
        "writable": ENV_PATH.exists() and os.access(ENV_PATH, os.W_OK) or os.access(ENV_PATH.parent, os.W_OK),
        "exchanges": exchanges,
        "restart_required": pending_restart,
        "restart_intent": intent,
        "hnc_packet_encryption": {
            "enabled": False,
            "format": "hncqp1",
            "encoded_key_count": len(packet_encoded_keys),
            "encoded_keys": packet_encoded_keys,
            "master_key_present": master_key_status["configured"],
            "master_key_valid": master_key_status["valid"],
            "packetization_available": master_key_status["valid"],
            "filesystem_write_released": False,
            "release_hold": CREDENTIAL_UPDATE_FILESYSTEM_HOLD,
            "configuration_error": master_key_status["error_code"],
            "evidence_file": str(HNC_PACKET_EVIDENCE_PATH),
            "policy": "credential filesystem updates are held; in-memory HNC packetization does not persist values or evidence",
            "secret_policy": "metadata_only_no_values_returned",
        },
        "secret_policy": "metadata_only_no_values_returned",
    }


def _extract_env_updates(exchange: str, credentials: dict[str, Any]) -> dict[str, str]:
    normalized = exchange.strip().lower()
    if normalized not in EXCHANGE_ENV_FIELDS:
        raise ValueError(f"unsupported_exchange:{exchange}")
    allowed = set(EXCHANGE_ENV_FIELDS[normalized])
    friendly = FRIENDLY_CREDENTIAL_KEYS.get(normalized, {})
    updates: dict[str, str] = {}
    for raw_key, raw_value in credentials.items():
        key = friendly.get(str(raw_key), str(raw_key))
        if key not in allowed:
            continue
        value = str(raw_value or "").strip()
        if value:
            updates[key] = value
    if not updates:
        raise ValueError("no_supported_non_empty_credentials")
    return updates


def _record_env_update_intent(exchange: str, updated_keys: list[str]) -> dict[str, Any]:
    STATE_ROOT.mkdir(parents=True, exist_ok=True)
    payload = {
        "status": "pending",
        "surface": "env_credentials",
        "exchange": exchange,
        "reason": "credentials_updated_from_local_console",
        "updated_keys": sorted(updated_keys),
        "env_file": str(ENV_PATH),
        "restart_required": True,
        "created_at": datetime.now().isoformat(),
        "secret_policy": "metadata_only_no_values_returned",
    }
    ENV_UPDATE_INTENT_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    market_payload = {
        "status": "pending",
        "surface": "market",
        "requested_by": "unified-market-status-server",
        "reason": "env_credentials_updated_from_local_console",
        "change_id": f"env_credentials_{exchange}",
        "updated_keys": sorted(updated_keys),
        "requested_at": datetime.now().isoformat(),
        "policy": "restart only when runtime is live, configured downtime window is active, and no open positions are reported",
        "secret_policy": "metadata_only_no_values_returned",
    }
    MARKET_INTENT_PATH.write_text(json.dumps(market_payload, indent=2), encoding="utf-8")
    return payload


def _has_open_positions(payload: dict[str, Any]) -> bool:
    combined = payload.get("combined")
    if isinstance(combined, dict):
        try:
            return int(combined.get("open_positions", 0) or 0) > 0
        except Exception:
            return True
    positions = payload.get("positions")
    if isinstance(positions, list):
        return len(positions) > 0
    return True


def _flight_test() -> dict[str, Any]:
    status = _read_status()
    intent = _read_market_intent()
    env_intent = _read_env_update_intent()
    pending_restart = bool(intent and intent.get("status") == "pending") or bool(env_intent and env_intent.get("status") == "pending")
    watchdog = status.get("runtime_watchdog") if isinstance(status.get("runtime_watchdog"), dict) else _runtime_watchdog(status)
    stale = bool(status.get("stale") or watchdog.get("tick_stale"))
    open_positions = _has_open_positions(status)
    downtime = _market_downtime_window()
    should_reboot = pending_restart or stale
    can_reboot_now = bool(should_reboot and downtime and not open_positions)
    if can_reboot_now:
        reason = "downtime_window_active_and_no_open_positions"
    elif stale and open_positions:
        reason = "runtime_tick_stale_with_open_positions"
    elif open_positions:
        reason = "open_positions_reported"
    elif not downtime:
        reason = "outside_market_downtime_window"
    elif stale:
        reason = "runtime_tick_stale"
    else:
        reason = "no_restart_needed"

    return {
        "ok": bool(status.get("ok")) and not stale,
        "service": "unified-market-status-server",
        "generated_at": datetime.now().isoformat(),
        "checks": {
            "status_file_exists": STATUS_PATH.exists(),
            "runtime_ok": bool(status.get("ok")),
            "trading_ready": bool(status.get("trading_ready")),
            "data_ready": bool(status.get("data_ready")),
            "tick_fresh": not stale,
            "heartbeat_fresh_but_tick_stale": bool(watchdog.get("heartbeat_fresh_but_tick_stale")),
            "open_positions": open_positions,
            "downtime_window": downtime,
            "pending_restart": pending_restart,
        },
        "reboot_advice": {
            "surface": "market",
            "should_reboot": should_reboot,
            "can_reboot_now": can_reboot_now,
            "decision": (
                "reboot_now"
                if can_reboot_now
                else "hold_monitor_positions"
                if stale and open_positions
                else ("hold" if should_reboot else "none")
            ),
            "reason": reason,
            "recovery_action": watchdog.get("recovery_action"),
        },
        "intent": intent,
        "env_update_intent": env_intent,
        "runtime": {
            "last_tick_started_at": status.get("last_tick_started_at"),
            "last_tick_completed_at": status.get("last_tick_completed_at"),
            "last_tick_age_sec": status.get("last_tick_age_sec"),
            "last_tick_running_sec": status.get("last_tick_running_sec"),
            "runtime_watchdog": watchdog,
            "combined": status.get("combined"),
            "exchanges": status.get("exchanges"),
        },
    }


class StatusHandler(BaseHTTPRequestHandler):
    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self) -> None:
        if self.path in {"/", "/health", "/api/terminal-state", "/api/flight-test", "/api/reboot-advice", "/api/env-credentials"}:
            if self.path == "/api/env-credentials":
                # Credential presence, key names, master-key state and local
                # filesystem paths are security-sensitive even without values.
                # Hold the public read before inspecting any credential source.
                self._json(
                    403,
                    {"ok": False, "error": CREDENTIAL_STATUS_READ_HOLD},
                )
                return
            if self.path in {"/api/flight-test", "/api/reboot-advice"}:
                self._json(200, _flight_test())
                return
            payload = _read_status()
            if self.path == "/health":
                payload = {
                    "ok": True,
                    "service": "unified-market-status-server",
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "status_file": str(STATUS_PATH),
                    "status_file_exists": payload.get("status_file_read_state") == "observed",
                    "served_status_ok": bool(payload.get("ok", False)),
                }
            self._json(200, payload)
            return
        self._json(404, {"ok": False, "error": "not_found"})

    def do_POST(self) -> None:
        if self.path != "/api/env-credentials":
            self._json(404, {"ok": False, "error": "not_found"})
            return
        if not self._local_origin_allowed():
            self._json(403, {"ok": False, "error": "local_origin_required"})
            return
        if self.headers.get("X-Aureon-Local-Operator") != "1":
            self._json(403, {"ok": False, "error": "operator_header_required"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0") or 0)
            if length <= 0 or length > 65536:
                self._json(400, {"ok": False, "error": "invalid_body_length"})
                return
            body = json.loads(self.rfile.read(length).decode("utf-8"))
            exchange = str(body.get("exchange") or "").strip().lower()
            credentials = body.get("credentials") if isinstance(body.get("credentials"), dict) else {}
            updates = _extract_env_updates(exchange, credentials)
            result = _write_env_updates(updates)
            intent = _record_env_update_intent(exchange, result["updated_keys"])
            self._json(
                200,
                {
                    "ok": True,
                    "service": "unified-market-status-server",
                    "generated_at": datetime.now().isoformat(),
                    "exchange": exchange,
                    "updated_keys": result["updated_keys"],
                    "hnc_packet_encrypted_keys": result.get("hnc_packet_encrypted_keys", []),
                    "env_file": result["env_file"],
                    "backup_file": result["backup_file"],
                    "restart_required": True,
                    "restart_intent": intent,
                    "credential_status": _env_credentials_status(),
                    "secret_policy": "metadata_only_no_values_returned",
                },
            )
        except ValueError as exc:
            self._json(400, {"ok": False, "error": str(exc)})
        except Exception as exc:
            self._json(500, {"ok": False, "error": f"env_update_failed:{type(exc).__name__}"})

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _cors(self) -> None:
        origin = self.headers.get("Origin", "")
        if _is_local_browser_origin(origin):
            self.send_header("Access-Control-Allow-Origin", origin)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Aureon-Local-Operator")

    def _local_origin_allowed(self) -> bool:
        origin = self.headers.get("Origin", "")
        return not origin or _is_local_browser_origin(origin)

    def _json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, default=str).encode("utf-8")
        self.send_response(status)
        self._cors()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    global _runtime_file_cache, _stream_file_cache
    parser = argparse.ArgumentParser(description="Read-only unified market status server")
    parser.add_argument("--port", type=int, default=8790)
    args = parser.parse_args()

    server = ThreadingHTTPServer((HOST, int(args.port)), StatusHandler)
    _runtime_file_cache = _BackgroundFileSnapshot(STATUS_PATH)
    _stream_file_cache = _BackgroundFileSnapshot(STREAM_CACHE_PATH, interval_sec=1.0)
    _runtime_file_cache.start()
    _stream_file_cache.start()
    print(
        f"[{datetime.now().isoformat()}] unified market status server online: "
        f"http://{HOST}:{args.port}/api/terminal-state",
        flush=True,
    )
    try:
        while True:
            server.handle_request()
            time.sleep(0.001)
    except KeyboardInterrupt:
        pass
    finally:
        _runtime_file_cache.stop()
        _stream_file_cache.stop()
        server.server_close()


if __name__ == "__main__":
    main()
