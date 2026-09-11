"""Passive, redacted activity receipts. No learning/research producer imports.

These records describe software-reported outcomes, not verified knowledge,
scientific facts, current permissions or functional health.
"""
from __future__ import annotations

import copy
import json
import math
import os
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any

SCHEMA = "aureon-research-activity-v1"
MAX_READ_BYTES = 64 * 1024
MAX_EVENTS = 10
RECENT_SECONDS = 300
CACHE_SECONDS = 2.0
MODES = ("proactive", "topic", "questions", "actuator")
OUTCOMES = {"absorbed", "refused", "deferred", "no_intent", "held_incoherent", "vetoed"}
CONSCIENCE = {"APPROVED", "CONCERNED", "VETO", "TEACHING_MOMENT"}
AUTHORIZATION = {"ALLOW", "HOLD", "DENY"}
GATE_OUTCOMES = {"authorized", "vetoed", "held_incoherent", "deferred"}
LEARNING_COUNTS = ("absorbed", "contested_stored", "dropped")
RESEARCH_COUNTS = ("questions_processed", "items_pulled", "fragments_added",
                   "items_filtered_novelty", "novelty_errors", "corroborated_items",
                   "questions_marked_researched")
INGESTER_COUNTS = ("items_pulled", "vault_ingests", "errors")
_cache: dict[tuple[str, str], tuple[float, dict[str, Any]]] = {}
_lock = threading.Lock()


def _epoch(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        if isinstance(value, (int, float)):
            result = float(value)
        elif isinstance(value, str):
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if parsed.tzinfo is None or parsed.utcoffset() is None:
                return None
            result = parsed.timestamp()
        else:
            return None
        return result if math.isfinite(result) and 0 < result < 253402300800 else None
    except (ValueError, TypeError, OverflowError, OSError):
        return None


def _count(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 9007199254740991 else None


def _boolean(value: Any) -> bool | None:
    return value if isinstance(value, bool) else None


def _enum(value: Any, allowed: set[str]) -> str | None:
    return value if isinstance(value, str) and value in allowed else None


def _counts(value: Any, fields: tuple[str, ...]) -> dict[str, int | None]:
    source = value if isinstance(value, dict) else {}
    return {name: _count(source.get(name)) for name in fields}


def _gate(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    conscience = value.get("conscience")
    coherence = value.get("coherence")
    authorization = value.get("authorization")
    conscience = conscience if isinstance(conscience, dict) else {}
    coherence = coherence if isinstance(coherence, dict) else {}
    authorization = authorization if isinstance(authorization, dict) else {}
    result = {
        "passed": _boolean(value.get("passed")),
        "outcome": _enum(value.get("outcome"), GATE_OUTCOMES),
        "conscience_verdict": _enum(conscience.get("verdict"), CONSCIENCE),
        "coherence_passed": _boolean(coherence.get("passed")),
        "authorization_passed": _boolean(authorization.get("passed")),
        "authorization_verdict": _enum(authorization.get("verdict"), AUTHORIZATION),
        "record_consistent": True,
    }
    contradictory = result["passed"] is True and (
        result["outcome"] not in (None, "authorized")
        or result["conscience_verdict"] == "VETO"
        or result["coherence_passed"] is False
        or result["authorization_passed"] is False
        or result["authorization_verdict"] in {"HOLD", "DENY"})
    if contradictory:
        result["passed"] = None
        result["record_consistent"] = False
    elif result["passed"] is None or (result["passed"] is True and not (
            result["outcome"] == "authorized" and result["conscience_verdict"] is not None
            and result["coherence_passed"] is True and result["authorization_passed"] is True
            and result["authorization_verdict"] == "ALLOW")):
        result["passed"] = None
        result["record_consistent"] = None
    return result


def _learning_event(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    stamp = _epoch(value.get("ts"))
    outcome = _enum(value.get("outcome"), OUTCOMES)
    dry = _boolean(value.get("dry_run"))
    if stamp is None or outcome is None or dry is None:
        return None
    return {"source_timestamp": stamp, "source_timestamp_original": value["ts"],
            "source_clock_kind": "producer_run_start", "outcome": outcome,
            "dry_run": dry, "gate": _gate(value.get("gate")),
            "reported_counts": _counts(value.get("batch"), LEARNING_COUNTS)}


def _research_record(mode: str, value: Any) -> dict[str, Any]:
    unavailable = {"mode": mode, "read_state": "missing", "reason_code": "mode_not_recorded"}
    if value is None:
        return unavailable
    if not isinstance(value, dict):
        return {**unavailable, "read_state": "failed", "reason_code": "mode_record_invalid"}
    result = value.get("last_result")
    stamp = _epoch(value.get("last_run_at"))
    if (stamp is None or not isinstance(result, dict)
            or result.get("outcome") != "researched"
            or result.get("mode", mode) != mode):
        return {**unavailable, "read_state": "failed", "reason_code": "mode_record_invalid"}
    return {"mode": mode, "read_state": "observed", "source_timestamp": stamp,
            "source_timestamp_original": value["last_run_at"],
            "source_clock_kind": "producer_run_start", "outcome": "researched",
            "reported_counts": _counts(result, RESEARCH_COUNTS),
            "reported_ingester_counts": _counts(result.get("ingester_stats"), INGESTER_COUNTS)}


def _read_journal(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        handle.seek(0, os.SEEK_END)
        size = handle.tell()
        start = max(0, size - MAX_READ_BYTES)
        handle.seek(start)
        raw = handle.read(MAX_READ_BYTES)
    lines = raw.splitlines()
    start_truncated = start > 0
    partial_last = bool(raw and not raw.endswith(b"\n"))
    if start_truncated:
        lines = lines[1:]  # never parse a possibly partial first record
    if partial_last and lines:
        lines = lines[:-1]  # append may still be in progress
    events = []
    invalid = 0
    for line in lines:
        if not line.strip():
            continue
        try:
            event = _learning_event(json.loads(line))
        except (ValueError, TypeError, UnicodeError):
            event = None
        if event is None:
            invalid += 1
        else:
            events.append(event)
    omitted = max(0, len(events) - MAX_EVENTS)
    return {
        "read_state": "observed" if events else "empty" if not raw else "failed",
        "reason_code": None if events else "journal_empty" if not raw else "no_valid_complete_journal_records",
        "events": events[-MAX_EVENTS:],
        "coverage": {"scope": "current_journal_file_only", "max_read_bytes": MAX_READ_BYTES,
                     "bytes_read": len(raw), "start_truncated": start_truncated,
                     "partial_last_record": partial_last, "invalid_records": invalid,
                     "records_omitted_from_tail": omitted, "returned_records": min(len(events), MAX_EVENTS),
                     "includes_rotated_or_pid_sidecars": False},
    }


def _read_research(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        raw = handle.read(MAX_READ_BYTES + 1)
    if len(raw) > MAX_READ_BYTES:
        raise ValueError("oversized")
    data = json.loads(raw)
    if not isinstance(data, dict) or data.get("saved_by") != "research_faculty":
        raise ValueError("source_schema_invalid")
    modes = data.get("modes")
    if modes is not None and not isinstance(modes, dict):
        raise ValueError("modes_invalid")
    modes = modes or {}
    # A legacy proactive receipt can be read without manufacturing a new date.
    if "proactive" not in modes and "last_run_at" in data:
        modes = {**modes, "proactive": {"last_run_at": data.get("last_run_at"), "last_result": data.get("last_result")}}
    return {"read_state": "observed", "reason_code": None,
            "records": [_research_record(mode, modes.get(mode)) for mode in MODES],
            "coverage": {"scope": "last_recorded_run_per_named_mode", "max_read_bytes": MAX_READ_BYTES,
                         "bytes_read": len(raw), "includes_unrecorded_attempts": False}}


def _read(path: Path, kind: str, now: float) -> dict[str, Any]:
    key = (str(path), kind)
    with _lock:
        tick = time.monotonic()
        cached = _cache.get(key)
        if cached is not None and tick - cached[0] < CACHE_SECONDS:
            return copy.deepcopy(cached[1])
        try:
            result = _read_journal(path) if kind == "learning_will" else _read_research(path)
        except FileNotFoundError:
            result = {"read_state": "missing", "reason_code": "source_file_missing"}
        except (OSError, ValueError, TypeError, UnicodeError, RecursionError):
            result = {"read_state": "failed", "reason_code": "source_file_invalid_unreadable_or_oversized"}
        result.update(source_id=kind, file_read_at=now)
        if len(_cache) >= 8 and key not in _cache:
            _cache.pop(next(iter(_cache)))
        _cache[key] = (tick, result)
        return copy.deepcopy(result)


def _age(record: dict[str, Any], now: float, *, learning: bool) -> dict[str, Any]:
    if record.get("read_state") in {"missing", "failed"}:
        return record
    stamp = record["source_timestamp"]
    age = now - stamp
    if age < -5:
        # Do not return the remaining contents of a future-dated event as evidence.
        return {"mode": record["mode"], "read_state": "failed", "reason_code": "source_timestamp_future"} if not learning else {
            "read_state": "failed", "reason_code": "source_timestamp_future"}
    dry_run = learning and record["dry_run"] is True
    return {**record, "age_seconds": age, "max_age_seconds": RECENT_SECONDS,
            "recent": not dry_run and age <= RECENT_SECONDS,
            "classification": "dry_run_record" if dry_run else "recorded_activity"}


def research_activity_observation(*, workspace: Path | None = None, now: float | None = None) -> dict[str, Any]:
    """Read existing fixed files only; no process probes, producer calls or writes."""
    current = time.time() if now is None else now
    if not isinstance(current, (int, float)) or _epoch(current) is None:
        return {"schema_version": SCHEMA, "measurement_kind": "producer_reported_activity",
                "recent_window_seconds": RECENT_SECONDS,
                **{kind: {"source_id": source, "read_state": "failed", "reason_code": "current_clock_invalid"}
                   for kind, source in (("learning_will", "learning_will"), ("research_faculty", "research_faculty"))}}
    base = (workspace or Path(__file__).resolve().parents[3]) / "aureon_fusion" / "state"
    learning = _read(base / "learning_will" / "journal.jsonl", "learning_will", current)
    research = _read(base / "research_throttle.json", "research_faculty", current)
    if "events" in learning:
        learning["events"] = [_age(event, current, learning=True) for event in learning["events"]]
    if "records" in research:
        research["records"] = [_age(record, current, learning=False) for record in research["records"]]
    return {"schema_version": SCHEMA, "measurement_kind": "producer_reported_activity",
            "recent_window_seconds": RECENT_SECONDS, "learning_will": learning, "research_faculty": research}
