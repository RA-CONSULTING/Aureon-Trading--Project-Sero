"""Decision-trace instrumentation for the unified market runtime.

Traces are append-only JSONL records that capture the wall-clock latency of each
tradable decision from the moment market intelligence is observed through the
moment the runtime considers state converged.
"""

from __future__ import annotations

import json
import math
import os
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class DecisionTrace:
    decision_trace_id: str
    t_intel_seen: Optional[float] = None
    t_signal_scored: Optional[float] = None
    t_intent_ready: Optional[float] = None
    t_exec_dispatched: Optional[float] = None
    t_exchange_ack: Optional[float] = None
    t_state_converged: Optional[float] = None
    venue: str = ""
    symbol: str = ""
    side: str = ""
    stage_statuses: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class DecisionTraceWriter:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, trace: DecisionTrace) -> None:
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(trace.to_dict(), default=str, sort_keys=True) + "\n")

    def append_all(self, traces: List[DecisionTrace]) -> None:
        if not traces:
            return
        with self.path.open("a", encoding="utf-8") as handle:
            for trace in traces:
                handle.write(json.dumps(trace.to_dict(), default=str, sort_keys=True) + "\n")


def _percentile(values: List[float], pct: float) -> Optional[float]:
    if not values:
        return None
    sorted_values = sorted(values)
    k = (len(sorted_values) - 1) * (pct / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return sorted_values[int(k)]
    return sorted_values[f] * (c - k) + sorted_values[c] * (k - f)


def decision_trace_percentiles(
    path: Path,
    venues: Optional[List[str]] = None,
    max_records: int = 10_000,
) -> Dict[str, Any]:
    """Return p50/p95/p99 latency percentiles per venue from the JSONL trace log."""
    path = Path(path)
    if not path.exists():
        return {"generated_at": _now_iso(), "venues": {}, "reason": "trace_log_missing"}

    venue_latencies: Dict[str, List[float]] = {}
    end_to_end_latencies: List[float] = []
    intent_ready_latencies: List[float] = []

    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            lines = handle.readlines()[-max_records:]
    except Exception as exc:
        return {"generated_at": _now_iso(), "venues": {}, "reason": f"read_error:{type(exc).__name__}"}

    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except Exception:
            continue
        if not isinstance(record, dict):
            continue
        t_intel = _float_or_none(record.get("t_intel_seen"))
        t_ready = _float_or_none(record.get("t_intent_ready"))
        t_conv = _float_or_none(record.get("t_state_converged"))
        venue = str(record.get("venue") or "unknown")
        if venues and venue not in venues:
            continue

        if t_intel is not None and t_ready is not None and t_ready >= t_intel:
            intent_ready_latencies.append(t_ready - t_intel)
        if t_intel is not None and t_conv is not None and t_conv >= t_intel:
            latency = t_conv - t_intel
            end_to_end_latencies.append(latency)
            venue_latencies.setdefault(venue, []).append(latency)

    def percentile_row(values: List[float]) -> Dict[str, Optional[float]]:
        return {
            "p50": _percentile(values, 50.0),
            "p95": _percentile(values, 95.0),
            "p99": _percentile(values, 99.0),
            "count": len(values),
        }

    return {
        "generated_at": _now_iso(),
        "path": str(path),
        "end_to_end_sec": percentile_row(end_to_end_latencies),
        "intent_ready_sec": percentile_row(intent_ready_latencies),
        "venues": {
            venue: percentile_row(values)
            for venue, values in sorted(venue_latencies.items())
        },
    }


def _float_or_none(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


__all__ = [
    "DecisionTrace",
    "DecisionTraceWriter",
    "decision_trace_percentiles",
]
