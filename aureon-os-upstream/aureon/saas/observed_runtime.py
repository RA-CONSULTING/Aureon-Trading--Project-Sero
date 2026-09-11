"""Bounded, passive UI observations. Never construct an organ to inspect it.

Source clocks are retained separately from the time this process read a source.
The small cache contains only allowlisted projections, never tenant/account data.
"""
from __future__ import annotations

import copy
import json
import math
import os
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
MAX_RECORD_BYTES = 1024 * 1024
MAX_TAIL_BYTES = 256 * 1024
SOURCE_MAX_AGE_SECONDS = 300.0
_CACHE_SECONDS = 2.0
_cache: dict[tuple[str, str], tuple[float, dict[str, Any]]] = {}
_cache_lock = threading.Lock()
_CONNECTOME_COUNTS = ("nodes", "baton_linked", "touched", "woven", "failed", "retryable", "denied", "unfelt", "coverage_pct")
_EDGE_TOPICS = ("symbolic.life.pulse", "symbolic.life.subfield", "auris.throne.cosmic_state", "lighthouse.event", "operator.action.verdict", "cognition.complete", "baton.link")


def source_epoch(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        if isinstance(value, (int, float)):
            result = float(value)
        else:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            if parsed.tzinfo is None or parsed.utcoffset() is None:
                return None
            result = parsed.timestamp()
        return result if math.isfinite(result) and 0 < result < 253402300800 else None
    except (ValueError, TypeError, OverflowError, OSError):
        return None


def observation(source: str, timestamp: Any, *, now: float, max_age: float = SOURCE_MAX_AGE_SECONDS,
                source_path: str | None = None, read_state: str = "observed", reason: str | None = None,
                clock_kind: str = "producer_timestamp") -> dict[str, Any]:
    stamp = source_epoch(timestamp)
    age = now - stamp if stamp is not None else None
    fresh = read_state == "observed" and age is not None and -5 <= age <= max_age
    if read_state == "observed" and not fresh:
        read_state = "stale" if age is not None and age > max_age else "unavailable"
        reason = "source_timestamp_expired" if read_state == "stale" else "source_timestamp_missing_invalid_or_future"
    return {"source": source, "source_path": source_path, "source_timestamp": stamp,
            "source_clock_kind": clock_kind, "receipt_timestamp": now, "age_seconds": age,
            "max_age_seconds": max_age, "fresh": fresh, "available": fresh,
            "read_state": read_state, "reason": reason}


def _count(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 9007199254740991 else None


def _finite(value: Any) -> float | None:
    try:
        return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) else None
    except (ValueError, OverflowError):
        return None


def _project(data: Any, kind: str) -> dict[str, Any]:
    if kind == "queen_report":
        meta = data.get("metacognition_state") or {}
        metrics = data.get("consciousness") or {}
        meta = meta if isinstance(meta, dict) else {}
        metrics = metrics if isinstance(metrics, dict) else {}
        projected_metrics = {k: _finite(metrics.get(k)) for k in ("awakening_index", "self_awareness", "brain_coherence", "learning_active", "temporal_awareness")}
        projected_metrics["level"] = metrics.get("level")[:80] if isinstance(metrics.get("level"), str) else None
        if isinstance(metrics.get("learning_active"), bool):
            projected_metrics["learning_active"] = metrics["learning_active"]
        return {"source_timestamp": data.get("timestamp"), "cycle": _count(data.get("cycle")),
                "metacognition_state": {k: _count(meta.get(k)) for k in ("reflection_count", "insight_count")},
                "consciousness": projected_metrics,
                "measurement_kind": "computed_runtime_report",
                "scope_note": "Queen software-model output; not a provider measurement or a different monitor's assessment."}
    if kind == "process_identity":
        if data.get("schema") != "aureon.process_identity.v1" or not isinstance(data.get("organs"), dict) or len(data["organs"]) > 128:
            raise ValueError("identity_receipt_schema_invalid")
        rows = {}
        for name, row in data["organs"].items():
            if isinstance(row, dict):
                rows[str(name)[:100]] = {"pid": _count(row.get("pid")),
                                        "process_created_at": source_epoch(row.get("process_created_at")),
                                        "process_name": str(row.get("process_name", "")).lower()[:100],
                                        "verified_at": source_epoch(row.get("verified_at")),
                                        "spec_match": row.get("spec_match") is True, "cwd_match": row.get("cwd_match") is True}
        return {"organs": rows}
    if kind == "registry":
        organs = data.get("organs")
        if not isinstance(organs, dict) or len(organs) > 128:
            raise ValueError("bounded_registry_object_required")
        rows = []
        for name, row in organs.items():
            if not isinstance(row, dict):
                continue
            cmd = row.get("cmd")
            executable = Path(str(cmd[0])).name.lower() if isinstance(cmd, list) and cmd else None
            rows.append({"name": str(name)[:100], "pid": _count(row.get("pid")),
                         "registry_started_at": source_epoch(row.get("started_at")),
                         "expected_created_at": source_epoch(row.get("process_created_at")),
                         "expected_process_name": executable})
        return {"organs": rows}
    if kind == "brain_predictions":
        predictions = data.get("predictions")
        if not isinstance(predictions, list):
            raise ValueError("prediction_list_required")
        validated = [p for p in predictions if isinstance(p, dict) and p.get("validated") is True]
        correct = [p for p in validated if p.get("was_correct") is True]
        return {"source_timestamp": data.get("last_updated"), "total_predictions": len(predictions),
                "validated": len(validated), "correct": len(correct),
                "accuracy_pct": 100.0 * len(correct) / len(validated) if validated else None}
    if kind == "brain_knowledge":
        entries = data if isinstance(data, list) else data.get("entries")
        if not isinstance(entries, list):
            raise ValueError("knowledge_list_required")
        last = entries[-1] if entries else {}
        return {"entries": len(entries), "source_timestamp": last.get("timestamp") if isinstance(last, dict) else None}
    if kind == "queen_mind":
        tick = data.get("last_tick")
        tick = tick if isinstance(tick, dict) else {}
        return {"source_timestamp": tick.get("timestamp"), "cycle": _count(tick.get("cycle"))}
    if kind == "hnc_core":
        return {"source_timestamp": data.get("timestamp"), "step": _count(data.get("step")),
                "input_count": _count(data.get("input_count")), "measurement_kind": "computed_runtime_state"}
    if kind == "genome":
        return {"source_timestamp": data.get("last_awakened_at"), "generation": _count(data.get("generation")),
                "first_awakened_at": data.get("first_awakened_at"), "last_awakened_at": data.get("last_awakened_at")}
    if kind == "harmonic_affect":
        return _project_harmonic_affect(data)
    if kind.startswith("assessment_snapshot:"):
        return _project_assessment_snapshot(data, kind.split(":", 1)[1])
    if kind == "connectome":
        records = data.get("records")
        if not isinstance(records, dict):
            raise ValueError("connectome_records_missing")
        statuses: dict[str, int] = {}
        for row in records.values():
            if isinstance(row, dict) and row.get("status") in {"touched", "woven", "failed", "denied"}:
                key = row["status"]
                statuses[key] = statuses.get(key, 0) + 1
        linked = data.get("linked")
        return {"source_timestamp": data.get("saved_at"), "nodes": None,
                "baton_linked": len(linked) if isinstance(linked, list) else None,
                "touched": statuses.get("touched", 0) + statuses.get("woven", 0),
                "woven": statuses.get("woven", 0), "failed": statuses.get("failed", 0),
                "denied": statuses.get("denied", 0), "retryable": None, "unfelt": None,
                "coverage_pct": None, "note": "Persisted coverage records; total inventory and current process health are not attested."}
    raise ValueError("unknown_projection")


def _safe_text(value: Any, limit: int = 160) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text[:limit] if text else None


def _signal_row(value: Any, detail: str) -> dict[str, Any]:
    number = _finite(value)
    return {"value": number, "truth_status": "real_derived" if number is not None else "no_data", "detail": detail[:200]}


def _project_harmonic_affect(data: dict[str, Any]) -> dict[str, Any]:
    if data.get("schema_version") != "aureon-harmonic-affect-state-v1":
        raise ValueError("harmonic_affect_schema_invalid")
    summary = data.get("summary")
    if not isinstance(summary, dict):
        raise ValueError("harmonic_affect_summary_missing")
    required = ("victory", "defeat", "fear", "resolve", "valence", "arousal", "caution_bias")
    numbers = {key: _finite(summary.get(key)) for key in required}
    if any(value is None for value in numbers.values()):
        raise ValueError("harmonic_affect_required_fields_missing")
    phase = _safe_text(summary.get("affect_phase"))
    emotion = _safe_text(summary.get("emotion_anchor"))
    if not phase or not emotion:
        raise ValueError("harmonic_affect_phase_missing")
    feelings = {key: numbers[key] for key in ("victory", "defeat", "fear", "resolve")}
    dominant = _safe_text(summary.get("dominant_feeling")) or max(feelings, key=feelings.get)
    mood = _safe_text(summary.get("mood")) or emotion
    input_summary_keys = (
        "hnc_coherence_score", "goal_alignment", "reward_alignment", "stability",
        "anchor_readiness", "safety_blocker_count", "blind_spot_count",
        "trade_evidence_count", "nexus_total_trades", "runtime_stale",
    )
    input_summary = {key: summary.get(key) for key in input_summary_keys if key in summary}
    signals = {
        "goal_alignment": _signal_row(summary.get("goal_alignment"), "Weighted signal quality, win rate, freshness and anchor readiness."),
        "reward_alignment": _signal_row(summary.get("reward_alignment"), "Learning reward and positive-PnL contribution from the cognitive trade evidence report."),
        "stability": _signal_row(summary.get("stability"), "Penalty-adjusted runtime stability from blind spots, blockers and stale clocks."),
        "hnc_coherence": _signal_row(summary.get("hnc_coherence_score"), "HNC/Auris coherence score emitted by the harmonic affect producer."),
        "anchor_readiness": _signal_row(summary.get("anchor_readiness"), "Fraction of expected HNC/Auris anchor sources present in the repo."),
        "safety_blockers": _signal_row(summary.get("safety_blocker_count"), "Current blocker count used by the affect safety model."),
        "runtime_stale": _signal_row(1.0 if summary.get("runtime_stale") is True else 0.0, "One means the producer observed stale runtime evidence; zero means not stale."),
    }
    return {
        "source_timestamp": data.get("generated_at"),
        "producer": "aureon.autonomous.aureon_harmonic_affect_state",
        "measurement_kind": "computed_runtime_assessment",
        "truth_status": "real_derived",
        "freshness_ttl_ms": 15_000,
        "victory": numbers["victory"],
        "defeat": numbers["defeat"],
        "fear": numbers["fear"],
        "resolve": numbers["resolve"],
        "valence": numbers["valence"],
        "arousal": numbers["arousal"],
        "caution_bias": numbers["caution_bias"],
        "affect_phase": phase,
        "emotion_anchor": emotion,
        "mood": mood,
        "dominant_feeling": dominant,
        "self_coherence": _finite(summary.get("hnc_coherence_score")),
        "psi": None,
        "signals": signals,
        "input_observations": {
            "source_manifest_status": _safe_text(data.get("status")),
            "summary_inputs": input_summary,
            "state_contract": data.get("state_contract") if isinstance(data.get("state_contract"), dict) else {},
        },
        "scope_note": "Dedicated harmonic affect producer output. These are software-model measurements only and cannot open trading, payment, filing, credential, or security gates.",
    }


def _project_assessment_snapshot(data: dict[str, Any], surface: str) -> dict[str, Any]:
    if data.get("schema_version") != "aureon-assessment-snapshots-v1":
        raise ValueError("assessment_snapshot_schema_invalid")
    assessments = data.get("assessments")
    if not isinstance(assessments, dict):
        raise ValueError("assessment_snapshot_rows_missing")
    payload = assessments.get(surface)
    if not isinstance(payload, dict):
        raise ValueError("assessment_snapshot_surface_missing")
    required: dict[str, tuple[str, ...]] = {
        "metacognition": ("contributors", "signals"),
        "soul": ("agreement", "stance", "resolved", "requires_human", "voices", "dissent"),
        "inner_work": ("self_belief", "self_love", "self_determination", "ego_dissolution", "stage_index", "potential"),
        "pursuit": ("creator_happiness", "aureon_happiness", "unified_happiness", "energy", "freedom", "pillars"),
    }
    for key in required.get(surface, ()):  # fail closed if the persisted shape is incomplete
        if key not in payload:
            raise ValueError("assessment_snapshot_required_field_missing")
    truth = _safe_text(payload.get("truth_status"), 80) or "no_data"
    source_ts = payload.get("ts") if payload.get("available") is True and truth != "no_data" else None
    row = copy.deepcopy(payload)
    row.pop("ts", None)
    row.update({
        "source_timestamp": source_ts,
        "producer": "aureon.autonomous.aureon_assessment_snapshot_producer",
        "measurement_kind": "computed_runtime_assessment",
        "truth_status": truth,
        "freshness_ttl_ms": 15_000,
        "input_observations": {
            "snapshot_generated_at": data.get("generated_at"),
            "producer_surface": surface,
            "producer_contract": data.get("producer_contract") if isinstance(data.get("producer_contract"), dict) else {},
        },
        "scope_note": "Persisted read-only assess() output. This cannot execute actions, submit orders, send payments, file records, or bypass credentials/security gates.",
    })
    return row


def _read_projected(path: Path, kind: str) -> dict[str, Any]:
    """Read at most 1 MiB; cache only the sanitized result, including read errors."""
    key = (str(path), kind)
    with _cache_lock:
        cached = _cache.get(key)
        checked = time.monotonic()
        if cached is not None and checked - cached[0] < _CACHE_SECONDS:
            return copy.deepcopy(cached[1])
        try:
            with path.open("rb") as handle:
                if kind == "queen_report":
                    handle.seek(0, os.SEEK_END)
                    size = handle.tell()
                    start = max(0, size - MAX_TAIL_BYTES)
                    handle.seek(start)
                    lines = handle.read(MAX_TAIL_BYTES).splitlines()
                    if start:
                        lines = lines[1:]  # discard the possibly partial first record
                    raw = next((line for line in reversed(lines) if line.strip()), b"")
                else:
                    raw = handle.read(MAX_RECORD_BYTES + 1)
            if len(raw) > MAX_RECORD_BYTES:
                raise ValueError("source_record_exceeds_read_limit")
            data = json.loads(raw)
            if not isinstance(data, dict) and not (kind == "brain_knowledge" and isinstance(data, list)):
                raise ValueError("source_object_required")
            result = {"read_state": "observed", "data": _project(data, kind)}
        except FileNotFoundError:
            result = {"read_state": "missing", "data": {}, "reason": "source_file_missing"}
        except (OSError, ValueError, TypeError, UnicodeError):
            result = {"read_state": "failed", "data": {}, "reason": "source_file_unreadable_invalid_or_oversized"}
        if len(_cache) >= 16 and key not in _cache:
            _cache.pop(next(iter(_cache)))
        _cache[key] = (checked, result)
        return copy.deepcopy(result)


def file_observation(path: Path, kind: str, *, now: float) -> dict[str, Any]:
    read = _read_projected(path, kind)
    data = read["data"]
    meta = observation(kind, data.get("source_timestamp"), now=now, source_path=str(path),
                       read_state=read["read_state"], reason=read.get("reason"))
    return {**data, **meta}


def runtime_source_observations(*, now: float | None = None, workspace: Path | None = None) -> dict[str, Any]:
    now = time.time() if now is None else now
    base = (workspace or REPO_ROOT.parent) / "aureon_fusion" / "state"
    return {"queen_mind": file_observation(base / "queen_mind" / "mind_state.json", "queen_mind", now=now),
            "queen_report": file_observation(base / "queen_mind" / "reports.jsonl", "queen_report", now=now),
            "hnc_core": file_observation(base / "hnc_core_state.json", "hnc_core", now=now)}


_process_cache: dict[str, tuple[float, dict[str, Any]]] = {}
_process_lock = threading.Lock()


def process_observation(*, workspace: Path | None = None, now: float | None = None,
                        process_factory: Any = None) -> dict[str, Any]:
    """Only registered PIDs: no registry imports, reconciliation, cmdlines or scans.

    A native creation time recorded in the ledger can verify its association.
    Rounded launch times only support an explicitly weaker consistency check. Liveness
    is never functional health. The 0.5s budget limits batches, not OS-call latency.
    """
    now = time.time() if now is None else now
    path = (workspace or REPO_ROOT.parent) / "aureon_fusion/state/organ_registry.json"
    key = str(path)
    with _process_lock:
        cached = _process_cache.get(key)
        if process_factory is None and cached and time.monotonic() - cached[0] < 5:
            result = copy.deepcopy(cached[1])
            result.update(observation("registered_pid_os_probe", result.get("source_timestamp"), now=now,
                                      max_age=15, source_path=key, clock_kind="os_process_measurement"))
            return result
        ledger = _read_projected(path, "registry")
        if ledger["read_state"] != "observed":
            return {**observation("registered_pid_os_probe", None, now=now, max_age=15,
                                 source_path=key, read_state=ledger["read_state"], reason=ledger.get("reason"),
                                 clock_kind="os_process_measurement"), "organs": [], "counts": None}
        identities = _read_projected(path.with_name("observed_process_identity.json"), "process_identity")
        identity_rows = identities["data"].get("organs", {})
        native = process_factory
        if native is None:
            try:
                import psutil
                native = psutil.Process
            except ImportError:
                return {**observation("registered_pid_os_probe", None, now=now, max_age=15,
                                     read_state="unavailable", reason="native_process_reader_missing"), "organs": [], "counts": None}
        started = time.monotonic()
        rows = []
        for entry in ledger["data"]["organs"]:
            row = {"name": entry["name"], "pid": entry["pid"], "pid_running": None,
                   "identity_verified": False, "functional_health": "unknown", "source_timestamp": None,
                   "read_state": "unavailable", "source_clock_kind": "os_process_measurement", "max_age_seconds": 15}
            if not entry["pid"]:
                row["reason"] = "no_recorded_pid"
            elif time.monotonic() - started > .5:
                row["reason"] = "probe_batch_budget_exhausted"
            else:
                try:
                    process = native(entry["pid"])
                    running = bool(process.is_running())
                    created = source_epoch(process.create_time())
                    name = str(process.name()).lower()
                    expected = entry.get("expected_process_name")
                    launch = entry.get("registry_started_at")
                    expected_created = entry.get("expected_created_at")
                    identity = identity_rows.get(entry["name"], {})
                    verified_at = identity.get("verified_at")
                    receipt_matched = identity.get("pid") == entry["pid"] and identity.get("process_created_at") == created and identity.get("process_name") == name and identity.get("spec_match") is True and identity.get("cwd_match") is True and verified_at is not None and verified_at <= now + 5
                    verified = running and created is not None and (receipt_matched or (expected_created is not None and created == expected_created and name == expected))
                    consistent = running and created is not None and launch is not None and abs(created - launch) <= 3 and name == expected
                    row.update(pid_running=running, process_name=name, process_created_at=created,
                               identity_verified=verified, launch_time_consistent=consistent, source_timestamp=now,
                               read_state="observed",
                               identity_verified_at=verified_at if receipt_matched else None,
                               reason=None if verified else "pid_identity_not_matched_to_recorded_launch")
                except Exception as exc:
                    absent = type(exc).__name__ in {"NoSuchProcess", "ProcessLookupError"}
                    row["reason"] = "recorded_pid_absent" if absent else "process_observation_unavailable"
                    row["read_state"] = "absent" if absent else "failed"
                    if absent:
                        row.update(pid_running=False, source_timestamp=now)
            rows.append(row)
        measured = [row for row in rows if row["source_timestamp"] is not None]
        result = {**observation("registered_pid_os_probe", now if measured else None, now=now, max_age=15,
                               source_path=key, clock_kind="os_process_measurement"),
                  "organs": rows, "counts": {"registered": len(rows), "measured": len(measured),
                  "running_verified": sum(row["identity_verified"] for row in rows),
                  "running_unverified": sum(row["pid_running"] is True and not row["identity_verified"] for row in rows),
                  "absent": sum(row["read_state"] == "absent" for row in rows),
                  "unknown": sum(row["source_timestamp"] is None for row in rows)},
                  "identity_receipt_read_state": identities["read_state"],
                  "scope_note": "OS process liveness and launch identity only. Functional health requires an independent producer observation."}
        if process_factory is None:
            _process_cache.clear()  # one workspace, no unbounded per-path objects
            _process_cache[key] = (time.monotonic(), copy.deepcopy(result))
        return result


def historical_file_observation(path: Path, kind: str, *, now: float | None = None) -> dict[str, Any]:
    row = file_observation(path, kind, now=time.time() if now is None else now)
    row.update(classification="recorded_history", historical_available=row["source_timestamp"] is not None and row["read_state"] in {"observed", "stale"})
    row["truth_status"] = "cached_real" if row["historical_available"] else "no_data"
    return row


def assessment_observation(surface: str) -> dict[str, Any]:
    """Expose only complete assessment producer snapshots.

    Lambda history/subfield values and Queen's different models cannot be
    substituted for a missing monitor assessment. The affect surface has a
    dedicated producer manifest; the other surfaces stay fail-closed until their
    own complete schemas are persisted.
    """
    fields = {
        "metacognition": ["self_coherence", "self_life_score", "psi", "lambda_t", "divergence", "contributors", "signals"],
        "affect": ["victory", "defeat", "fear", "resolve", "valence", "arousal", "caution_bias", "affect_phase", "signals"],
        "soul": ["agreement", "stance", "resolved", "requires_human", "voices", "dissent", "plan"],
        "inner_work": ["self_belief", "self_love", "self_determination", "ego_dissolution", "stage_index", "potential", "signals"],
        "pursuit": ["creator_happiness", "aureon_happiness", "unified_happiness", "energy", "freedom", "pillars", "signals"],
    }
    now = time.time()
    runtime_sources = runtime_source_observations(now=now)
    if surface == "affect":
        report = file_observation(REPO_ROOT / "docs" / "audits" / "aureon_harmonic_affect_state.json", "harmonic_affect", now=now)
        if report["read_state"] != "missing":
            report.setdefault("truth_status", "no_data")
            report.setdefault("measurement_kind", "computed_runtime_assessment")
            report["runtime_sources"] = runtime_sources
            report["required_producer_fields"] = ["source_timestamp", "producer", "input_observations", *fields["affect"]]
            report["note"] = "Affect is backed by the harmonic affect producer; related runtime reports keep their own names and clocks."
            return report
    if surface in {"metacognition", "soul", "inner_work", "pursuit"}:
        report = file_observation(REPO_ROOT / "docs" / "audits" / "aureon_assessment_snapshots.json", f"assessment_snapshot:{surface}", now=now)
        if report["read_state"] != "missing":
            report.setdefault("truth_status", "no_data")
            report.setdefault("measurement_kind", "computed_runtime_assessment")
            report["runtime_sources"] = runtime_sources
            report["required_producer_fields"] = ["source_timestamp", "producer", "input_observations", *fields.get(surface, [])]
            report["note"] = "This route is backed by the read-only assessment snapshot producer; related runtime reports keep their own names and clocks."
            return report
    return {**observation(surface, None, now=now, read_state="missing", reason="complete_producer_assessment_snapshot_not_published"),
            "truth_status": "no_data", "measurement_kind": "computed_runtime_assessment",
            "required_producer_fields": ["source_timestamp", "producer", "input_observations", *fields.get(surface, [])],
            "runtime_sources": runtime_sources,
            "note": "Related Queen/HNC records retain their own names and clocks; they do not fill this monitor's missing schema."}


class _ObservedBus:
    """Expose only timestamped, unexpired events from an already existing bus."""
    def __init__(self, bus: Any, now: float):
        self.bus, self.now = bus, now
        self.failed_topics: set[str] = set()

    def recall(self, topic: str, limit: int = 200) -> list[Any]:
        if self.bus is None:
            return []
        try:
            rows = self.bus.recall(topic, limit=min(limit, 200)) or []
            return [row for row in rows if observation(topic, _event_timestamp(row), now=self.now)["fresh"]]
        except Exception:
            self.failed_topics.add(topic)
            return []


def _event_timestamp(row: Any) -> Any:
    return row.get("ts", row.get("timestamp")) if isinstance(row, dict) else getattr(row, "ts", None)


def _event_payload(row: Any) -> dict[str, Any]:
    value = row.get("payload", {}) if isinstance(row, dict) else getattr(row, "payload", {})
    return value if isinstance(value, dict) else {}


def _canonical_observation(bus: _ObservedBus) -> dict[str, Any]:
    # This reader validates the existing receipt contract, including native evidence.
    # Passing the inert facade prevents the reader from constructing a thought bus.
    from aureon.core.hnc_field import read_canonical_field
    return read_canonical_field(bus).to_dict()


def canonical_surface(bus: Any = None) -> dict[str, Any]:
    now = time.time()
    if bus is None:
        bus = getattr(sys.modules.get("aureon.core.aureon_thought_bus"), "_thought_bus_instance", None)
    try:
        canonical = _canonical_observation(_ObservedBus(bus, now))
    except Exception:
        canonical = {"available": False}
    meta = observation("canonical_hnc_receipt", canonical.get("source_timestamp"), now=now,
                       source_path=None if canonical.get("evidence_transport") == "thought_bus" else str(Path(os.environ.get("AUREON_HNC_TRACE_PATH") or (REPO_ROOT / "state/hnc_live_trace.jsonl"))),
                       read_state="observed" if canonical.get("available") is True else "unavailable",
                       reason=None if canonical.get("available") is True else "validated_canonical_receipt_unavailable")
    if not meta["fresh"]:
        canonical = {"available": False}
    return {**meta, "canonical": canonical, "truth_status": canonical.get("truth_status", "no_data"),
            "subfields": {"available": False, "count": None, "sources": [], "reason": "no_timestamped_public_subfield_projection"},
            "blended": {"available": False}, "consensus_event": None, "producers": []}


def bus_observation(bus: Any = None) -> dict[str, Any]:
    now = time.time()
    if bus is None:
        bus = getattr(sys.modules.get("aureon.core.aureon_thought_bus"), "_thought_bus_instance", None)
    if bus is None:
        return {**observation("gateway_thought_bus", None, now=now, max_age=15, read_state="missing", reason="bus_not_observed_in_gateway_process"), "truth_status": "no_data"}
    try:
        subscribed = bus.list_subscribed_topics() if hasattr(bus, "list_subscribed_topics") else None
        subscribers = bus.subscriber_count() if hasattr(bus, "subscriber_count") else None
        facade = _ObservedBus(bus, now)
        families = {topic: {"recent": len(facade.recall(topic, limit=200)),
                            "subscribers": bus.subscriber_count(topic) if hasattr(bus, "subscriber_count") else None} for topic in _EDGE_TOPICS}
        if facade.failed_topics:
            raise ValueError("retained_event_read_failed")
        return {**observation("gateway_thought_bus", now, now=now, max_age=15, clock_kind="in_process_bus_measurement"),
                "truth_status": "real_derived", "subscribed_topics": sorted(subscribed) if isinstance(subscribed, (list, set, tuple)) else None,
                "subscribed_topic_count": len(subscribed) if isinstance(subscribed, (list, set, tuple)) else None,
                "total_subscribers": _count(subscribers), "cognitive_links": families,
                "cognitive_links_flowing": sum(row["recent"] > 0 for row in families.values()),
                "event_window_seconds": SOURCE_MAX_AGE_SECONDS,
                "scope_note": "Measured gateway-local bus topology. Only timestamped unexpired events count as recent."}
    except Exception:
        return {**observation("gateway_thought_bus", None, now=now, max_age=15, read_state="failed", reason="bus_observation_failed"), "truth_status": "no_data"}


def brain_observation() -> dict[str, Any]:
    now = time.time()
    accuracy = historical_file_observation(Path(os.environ.get("AUREON_BRAIN_PREDICTIONS_PATH") or (REPO_ROOT / "brain_predictions_history.json")), "brain_predictions", now=now)
    knowledge = historical_file_observation(Path(os.environ.get("AUREON_BRAIN_KNOWLEDGE_PATH") or (REPO_ROOT / "miner_brain_knowledge.json")), "brain_knowledge", now=now)
    # Aggregate has no single clock: each recorded component qualifies independently.
    historical = accuracy["historical_available"] or knowledge["historical_available"]
    return {"available": False, "fresh": False, "source_timestamp": None, "receipt_timestamp": now,
            "classification": "recorded_history", "historical_available": historical,
            "truth_status": "cached_real" if historical else "no_data", "accuracy": accuracy, "knowledge": knowledge,
            "reason": "independent_historical_component_clocks_not_current_brain_health"}


def observed_organism(*, now: float | None = None, repo_root: Path | None = None,
                      workspace: Path | None = None, modules: Any = None) -> dict[str, Any]:
    now = time.time() if now is None else now
    root = repo_root or REPO_ROOT
    modules = sys.modules if modules is None else modules
    bus_module = modules.get("aureon.core.aureon_thought_bus")
    bus = _ObservedBus(getattr(bus_module, "_thought_bus_instance", None), now)
    connectome = file_observation(root / "state" / "organism_connectome.json", "connectome", now=now)
    pulses = bus.recall("organism.connectome.pulse", limit=5)
    if pulses:
        latest = pulses[-1]
        counts = {k: v for k, v in _event_payload(latest).items() if k in _CONNECTOME_COUNTS
                  and isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and v >= 0}
        connectome = {**counts, **observation("organism.connectome.pulse", _event_timestamp(latest), now=now)}
    mesh = getattr(modules.get("aureon.core.aureon_mycelium"), "_mycelium_instance", None)
    # Mesh existence is process-local configuration, with no attested metric clock.
    mycelium = {**observation("gateway_mycelium", None, now=now, read_state="unavailable",
                             reason="mesh_source_clock_not_attested" if mesh is not None else "mesh_not_observed_in_gateway_process"),
                "process_instance_present": mesh is not None,
                "connected_systems": [], "truth_status": "no_data",
                "reason": "mesh_source_clock_not_attested" if mesh is not None else "mesh_not_observed_in_gateway_process"}
    try:
        canonical = _canonical_observation(bus)
    except Exception:
        canonical = {"available": False}
    trace_path = Path(os.environ.get("AUREON_HNC_TRACE_PATH") or (root / "state" / "hnc_live_trace.jsonl"))
    field_meta = observation("canonical_hnc_receipt", canonical.get("source_timestamp"), now=now,
                             source_path=str(trace_path) if canonical.get("evidence_transport") != "thought_bus" else None,
                             read_state="observed" if canonical.get("available") is True else "unavailable",
                             reason=None if canonical.get("available") is True else "validated_canonical_receipt_unavailable")
    field_meta["evidence_transport"] = canonical.get("evidence_transport")
    field_fresh = field_meta["fresh"] and canonical.get("available") is True
    edges = {topic: len(bus.recall(topic, limit=50)) if bus.bus is not None else None for topic in _EDGE_TOPICS}
    edges.update({topic: None for topic in bus.failed_topics})
    runtime_sources = runtime_source_observations(now=now, workspace=workspace or root.parent)
    genome_path = Path(os.environ.get("AUREON_GENESIS_PATH") or (root / "state" / "aureon_genesis.json"))
    awakening = file_observation(genome_path, "genome", now=now)
    queen = getattr(modules.get("aureon.utils.aureon_queen_hive_mind"), "_QUEEN", None)
    children = getattr(queen, "children", None)
    any_observed = any(item.get("fresh") for item in [connectome, awakening, field_meta, *runtime_sources.values()])
    return {"available": any_observed, "truth_status": "real_derived" if any_observed else "no_data",
            "receipt_timestamp": now, "source_timestamp": None, "status_scope": "separate_source_observations",
            "connectome": connectome, "recent_pulses": [{"ts": _event_timestamp(row), "source": "organism.connectome.pulse"} for row in pulses],
            "mycelium": mycelium, "awakening": awakening, "queen_children": len(children) if isinstance(children, (dict, list)) else None,
            "runtime_sources": runtime_sources,
            "process_observation": process_observation(workspace=workspace or root.parent, now=now),
            "unification": {"field_flowing": field_fresh,
                            "symbolic_life_score": canonical.get("symbolic_life_score") if field_fresh else None,
                            "coherence_gamma": canonical.get("coherence_gamma") if field_fresh else None,
                            "field_observation": field_meta, "edges": edges,
                            "edge_window_seconds": SOURCE_MAX_AGE_SECONDS,
                            "note": "Retained events are counted only with original timestamps inside the window; missing bus is unknown."}}
