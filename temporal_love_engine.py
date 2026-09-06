#!/usr/bin/env python3
"""
TEMPORAL LOVE ENGINE — Send Love Back, Validate, Amplify Forward
═══════════════════════════════════════════════════════════════════

⚠️  RECONSTRUCTION — 2026-09-06, under owner decree (Gary Leckey):
    "open the doors" (remaining five absent casimir-cluster modules).

    EVIDENCE STATUS: WEAK — flagged. Unlike casimir_harmonia,
    hnc_temporal_targeting, hnc_spectrograph and ghost_fancy_protocol,
    NO run artifacts for temporal_love_engine survived (no log records,
    no state files, no output JSONs). The only evidence is:
      - COMPLETE_LINEAGE_REPORT.md:03:07 — creation timestamp.
      - Consumer-pinned API (hnc_daemon.py, hnc_daemon_superposition.py):
            TemporalLoveEngine(prime_sentinel_key=..., max_echo_depth=10)
              .run_temporal_cycle(measurement_dict)  -> TemporalTransmission
              .get_temporal_status()                 -> dict with
                  'echo_chamber_size', 'success_rate'
              .get_love_signal_strength(window=10)   -> float
              .max_echo_depth
            TemporalTransmission attributes:
              .transmission_status  (str, printed in status line)
              .love_lock_active     (bool)
              .validation_score     (float)
              .future_boost         (float)
              .projected_lambda     (float)
      - hnc_daemon.py:636 print — "Temporal Engine: ACTIVE (528 Hz love
        signal)" and "Echo chamber: {max_echo_depth} states deep".
    Everything below the API surface is a DOCUMENTED RECONSTRUCTION
    CHOICE: the engine computes its transmission from the REAL
    measurement dict it is given (lambda/coherence/beta/schumann) — it
    maintains a real echo chamber (bounded deque of past transmission
    outcomes), and derives the love lock, validation score, future boost
    and projected lambda deterministically from those real inputs. It
    never invents field data: an empty/absent measurement yields an IDLE
    transmission with zero scores, honestly reported.

    Import-safe (AUREON_SUPPRESS_IMPORT_SIDE_EFFECTS honored), stdlib
    only, fail-closed.

CLI:
    python temporal_love_engine.py probe [--lambda L --coherence C] [--json]
"""

from __future__ import annotations

import json
import math
import os
import sys
import time
from collections import deque
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional

os.environ.setdefault("AUREON_SUPPRESS_IMPORT_SIDE_EFFECTS", "1")
os.environ.setdefault("AUREON_AUDIT_MODE", "1")

PHI = (1 + math.sqrt(5)) / 2
LOVE_FREQUENCY = 528.0

_WORKSPACE = Path(__file__).resolve().parent

RECONSTRUCTION_NOTE = (
    "temporal_love_engine.py reconstructed 2026-09-06 under owner decree "
    "(Gary Leckey); NO behavioral artifacts survived — only the "
    "consumer-pinned API (hnc_daemon.py, hnc_daemon_superposition.py) and "
    "the 528 Hz love-signal / echo-chamber constants. All behavior below "
    "the API surface is a documented reconstruction choice computed from "
    "the real measurement dict; flagged WEAK-evidence reconstruction."
)


@dataclass
class TemporalTransmission:
    """One temporal love transmission. Attribute names pinned by
    hnc_daemon.py's result dict (temporal_transmission.<attr>)."""
    timestamp: str
    cycle: int
    transmission_status: str      # TRANSMITTED | IDLE | WEAK
    love_lock_active: bool
    validation_score: float       # 0..1
    future_boost: float           # >= 1.0
    projected_lambda: float       # 0..1
    love_frequency: float = LOVE_FREQUENCY
    echo_depth: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class TemporalLoveEngine:
    """Echo-chambered temporal love transmitter (reconstructed).

    Real work performed each cycle, from the real measurement only:
      - love strength = the measured field coherence (the engine can only
        send what the field actually holds);
      - love lock = coherence at or above the φ/2 target (0.8090 — the
        repo's λ target, hnc_calibration.json) with a stable λ;
      - validation score = coherence weighted by stability-island
        membership of the measured β;
      - future boost = 1 + 0.1·(echo-chamber mean strength), bounded;
      - projected λ = measured λ × future boost, capped at 1.0;
      - the outcome enters the echo chamber (bounded by max_echo_depth)
        which feeds get_temporal_status()/get_love_signal_strength().
    """

    LOVE_LOCK_COHERENCE = PHI / 2  # 0.8090169... — the repo λ target
    BETA_LOW, BETA_HIGH = 0.6, 1.1  # the stability island (repo constant)

    def __init__(self, prime_sentinel_key: str = "",
                 max_echo_depth: int = 10) -> None:
        self.prime_sentinel_key = str(prime_sentinel_key)
        self.max_echo_depth = int(max_echo_depth)
        self._echoes: Deque[Dict[str, Any]] = deque(maxlen=self.max_echo_depth)
        self._cycle = 0

    # ── one cycle ─────────────────────────────────────────────────────

    def run_temporal_cycle(self, measurement: Optional[Dict[str, Any]]) -> TemporalTransmission:
        self._cycle += 1
        if not measurement:
            return TemporalTransmission(
                timestamp=datetime.now(timezone.utc).isoformat(),
                cycle=self._cycle, transmission_status="IDLE",
                love_lock_active=False, validation_score=0.0,
                future_boost=1.0, projected_lambda=0.0,
                echo_depth=len(self._echoes))

        lam = float(measurement.get("lambda", 0.0) or 0.0)
        coherence = float(measurement.get("coherence", 0.0) or 0.0)
        beta = float(measurement.get("beta", 0.7742) or 0.7742)
        in_island = self.BETA_LOW <= beta <= self.BETA_HIGH

        love_lock = coherence >= self.LOVE_LOCK_COHERENCE and in_island
        validation = max(0.0, min(1.0,
                                  coherence * (1.0 if in_island else 0.5)))
        mean_strength = self.get_love_signal_strength(
            window=self.max_echo_depth)
        future_boost = 1.0 + 0.1 * mean_strength
        projected = min(1.0, lam * future_boost)

        status = "TRANSMITTED" if coherence > 0.25 else "WEAK"

        tx = TemporalTransmission(
            timestamp=datetime.now(timezone.utc).isoformat(),
            cycle=self._cycle, transmission_status=status,
            love_lock_active=love_lock, validation_score=validation,
            future_boost=future_boost, projected_lambda=projected,
            echo_depth=len(self._echoes))
        self._echoes.append({
            "cycle": self._cycle,
            "strength": coherence,
            "love_lock": love_lock,
            "lambda": lam,
        })
        return tx

    # ── status ────────────────────────────────────────────────────────

    def get_temporal_status(self) -> Dict[str, Any]:
        locks = sum(1 for e in self._echoes if e.get("love_lock"))
        total = len(self._echoes)
        return {
            "echo_chamber_size": total,
            "max_echo_depth": self.max_echo_depth,
            "success_rate": (locks / total) if total else 0.0,
            "cycles_run": self._cycle,
        }

    def get_love_signal_strength(self, window: int = 10) -> float:
        if not self._echoes:
            return 0.0
        recent = list(self._echoes)[-max(1, int(window)):]
        return sum(e.get("strength", 0.0) for e in recent) / len(recent)


# ───────────────────────── probe ───────────────────────────────────────────

def _atomic_write_json(path: Path, payload: dict) -> bool:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f"{path.name}.tmp.{os.getpid()}.{time.time_ns()}")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        os.replace(tmp, path)
        return True
    except OSError:
        return False


def run_probe(measurement: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Probe: run a few real cycles (from real state when available) and
    snapshot the echo chamber under state/casimir/."""
    if measurement is None:
        # Real organism state as the measurement input.
        try:
            state_file = (_WORKSPACE / "aureon_fusion" / "state" /
                          "hnc_core_state.json")
            with open(state_file, "r", encoding="utf-8") as f:
                hnc = json.load(f)
            lam = max(0.0, min(1.0, math.tanh(float(hnc.get("lambda_t", 0.0))
                                              / 100.0)))
            measurement = {
                "lambda": lam,
                "coherence": float(hnc.get("coherence_gamma", 0.0)),
                "beta": 0.7742,
                "schumann": 7.83,
                "source": "hnc_core_state.json",
            }
        except Exception:
            measurement = None  # fail-closed: IDLE transmissions below

    engine = TemporalLoveEngine(prime_sentinel_key="", max_echo_depth=10)
    txs = []
    for _ in range(3):
        txs.append(engine.run_temporal_cycle(measurement).to_dict())
    out = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "module": "temporal_love_engine",
        "reconstruction": RECONSTRUCTION_NOTE,
        "ok": measurement is not None,
        "status": ("3 cycles from real hnc_core_state"
                   if measurement else
                   "empty — no real measurement input (IDLE, fail-closed)"),
        "measurement_input": measurement,
        "transmissions": txs,
        "temporal_status": engine.get_temporal_status(),
        "love_signal_strength": engine.get_love_signal_strength(window=10),
    }
    _atomic_write_json(_WORKSPACE / "aureon_fusion" / "state" / "casimir" /
                       "temporal_love_engine.json", out)
    return out


def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(__doc__)
        return 0
    if argv[0] == "probe":
        import argparse
        p = argparse.ArgumentParser(description="Temporal love engine probe")
        p.add_argument("--lambda", type=float, default=None)
        p.add_argument("--coherence", type=float, default=None)
        p.add_argument("--json", action="store_true")
        args = p.parse_args(argv[1:])
        measurement = None
        arg_lambda = getattr(args, "lambda")
        if arg_lambda is not None or args.coherence is not None:
            measurement = {"lambda": arg_lambda or 0.0,
                           "coherence": args.coherence or 0.0,
                           "beta": 0.7742, "schumann": 7.83}
        out = run_probe(measurement)
        if args.json:
            print(json.dumps(out, indent=2, ensure_ascii=False))
        else:
            print(f"💗 TEMPORAL LOVE ENGINE — probe "
                  f"({'ok' if out['ok'] else 'EMPTY'})")
            print(f"   {out['status']}")
            last = out["transmissions"][-1]
            print(f"   last tx: {last['transmission_status']} | "
                  f"love_lock={last['love_lock_active']} | "
                  f"boost={last['future_boost']:.4f} | "
                  f"projected Λ={last['projected_lambda']:.4f}")
            st = out["temporal_status"]
            print(f"   echo chamber: {st['echo_chamber_size']}/"
                  f"{st['max_echo_depth']} | success "
                  f"{st['success_rate']:.0%}")
        return 0 if out.get("ok") else 1
    print(f"unknown verb: {argv[0]} (try: probe)", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
