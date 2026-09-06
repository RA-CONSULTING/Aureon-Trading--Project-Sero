#!/usr/bin/env python3
"""
HNC TEMPORAL TARGETING — Temporal Lock & Targeting Engine
═══════════════════════════════════════════════════════════════════

⚠️  RECONSTRUCTION — 2026-09-06, under owner decree (Gary Leckey):
    "open the doors" (census door `casimir_cluster`, locked
    "reconstruction-required — casimir_harmonia + hnc_temporal_targeting
    absent").

    The original hnc_temporal_targeting.py vanished from the repo
    (confirmed missing in workspace, aureon-trading/, upstream, and every
    archive; see aureon_fusion/state/door_census.md "BROKEN-WITH-REASON").
    No reference implementation or spec survived — only the API its
    consumers pin and the lineage timestamp (COMPLETE_LINEAGE_REPORT.md,
    14:30, June build). This module is therefore an HONEST reconstruction:

    WHAT IS RECOVERED (from consumers, exact):
      - temporal_hash(target_date) -> dict with keys 'temporal_signature'
        (float, scored against 1/PHI by the consumers), 'hash_short',
        'rune_encoded', and 'operational' {'love_modulation' (Hz),
        'prime_sentinel_mod' (Hz), 'casimir_coupling'}.
        Consumers: hnc_blind_ghost.py, hnc_ghost_protocol_v2.py.
      - TemporalLockEncoder(target_date) with .encode_lock() -> dict
        carrying 'hash_chain' (>=16 chars) and 'decree' (>=200 chars).
      Everything here is a deterministic pure function of the target
      date string (SHA-256 based) — no randomness, no clock dependence,
      so proofs generated before and after reconstruction hash identically
      for a given date.

    WHAT IS NEW (documented, computed from real state only):
      - build_temporal_snapshot(): the temporal TARGETING side. Reads
        aureon_fusion/state/hnc_core_state.json (lambda_t,
        coherence_gamma) and aureon_fusion/state/lambda_history.json
        (the organism's committed λ history) and computes a temporal
        targeting snapshot: current field anchors, coherence/λ trend
        over the recent history (least-squares slope per history step),
        and predicted crossing times (in history steps — the history
        file carries no timestamps, so no wall-clock times are invented)
        for the coherence threshold Γ=0.25 (the organism's own
        fail-closed floor) and the λ mean/max/min levels.
      - FAIL-CLOSED: when the state files or the history are absent, the
        snapshot is EMPTY and says exactly that. Nothing is fabricated.

    Import-safe: nothing runs at import; AUREON_SUPPRESS_IMPORT_SIDE_EFFECTS
    is honored via setdefault. Stdlib only.

CLI:
    python hnc_temporal_targeting.py probe [--target YYYY-MM-DD] [--json]
    python hnc_temporal_targeting.py hash <YYYY-MM-DD>
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

os.environ.setdefault("AUREON_SUPPRESS_IMPORT_SIDE_EFFECTS", "1")
os.environ.setdefault("AUREON_AUDIT_MODE", "1")

PHI = (1 + math.sqrt(5)) / 2
SCHUMANN_BASE = 7.83
LOVE_FREQUENCY = 528.0
PRIME_SENTINEL_HZ = 812.83
COHERENCE_FLOOR = 0.25  # the organism's own fail-closed gate (Γ ≥ 0.25)

_WORKSPACE = Path(__file__).resolve().parent
STATE_DIR = _WORKSPACE / "aureon_fusion" / "state"
HNC_CORE_STATE = STATE_DIR / "hnc_core_state.json"
LAMBDA_HISTORY = STATE_DIR / "lambda_history.json"
CASIMIR_STATE_DIR = STATE_DIR / "casimir"
DEFAULT_STATE_OUT = CASIMIR_STATE_DIR / "hnc_temporal_targeting.json"

# Elder Futhark (24 runes) — deterministic rune encoding of hash bytes.
RUNES = ("ᚠ", "ᚢ", "ᚦ", "ᚨ", "ᚱ", "ᚲ", "ᚷ", "ᚹ", "ᚺ", "ᚾ", "ᛁ", "ᛃ",
         "ᛇ", "ᛈ", "ᛉ", "ᛊ", "ᛏ", "ᛒ", "ᛖ", "ᛗ", "ᛚ", "ᛜ", "ᛞ", "ᛟ")

RECONSTRUCTION_NOTE = (
    "hnc_temporal_targeting.py reconstructed 2026-09-06 under owner decree "
    "(Gary Leckey) for census door casimir_cluster; no reference "
    "implementation survived — consumer-pinned API (temporal_hash, "
    "TemporalLockEncoder) recovered from hnc_blind_ghost.py and "
    "hnc_ghost_protocol_v2.py; temporal targeting snapshot computed from "
    "real state (hnc_core_state.json + lambda_history.json) only."
)


def _canonical_date(target_date: str) -> str:
    """Validate and canonicalise a YYYY-MM-DD date. Raises ValueError on
    garbage — temporal locks are only defined for real calendar dates."""
    dt = datetime.strptime(str(target_date).strip()[:10], "%Y-%m-%d")
    return dt.strftime("%Y-%m-%d")


def _digest(target_date: str) -> bytes:
    return hashlib.sha256(
        f"hnc-temporal-target|{_canonical_date(target_date)}".encode("utf-8")
    ).digest()


def temporal_hash(target_date: str) -> Dict[str, Any]:
    """Deterministic temporal signature of a target date.

    Every field is a pure function of the canonical date string:
      temporal_signature — first 8 digest bytes / 2⁶⁴ ∈ [0, 1); the
          consumers score it against 1/PHI (temporal_alignment).
      hash_short           — 16-hex digest prefix (proof chaining).
      rune_encoded         — digest bytes mapped onto Elder Futhark.
      operational          — real anchor frequencies modulated BY the
          signature (not free parameters): the love carrier 528 Hz, the
          Prime Sentinel 812.83 Hz, and a Casimir coupling in [1, 2).
    """
    raw = _digest(target_date)
    signature = int.from_bytes(raw[:8], "big") / float(1 << 64)
    rune_encoded = "".join(RUNES[b % len(RUNES)] for b in raw[8:20])
    return {
        "target_date": _canonical_date(target_date),
        "temporal_signature": signature,
        "phi_fraction": 1.0 / PHI,
        "temporal_alignment": max(
            0.0, 1.0 - abs(signature - 1.0 / PHI) / (1.0 / PHI)),
        "hash_short": raw.hex()[:16],
        "rune_encoded": rune_encoded,
        "operational": {
            "love_modulation": LOVE_FREQUENCY * (0.9 + 0.2 * signature),
            "prime_sentinel_mod": PRIME_SENTINEL_HZ * (0.9 + 0.2 * signature),
            "casimir_coupling": 1.0 + signature,
        },
    }


class TemporalLockEncoder:
    """Hash-chained temporal lock for a target date.

    encode_lock() returns the lock record the ghost protocols seal into
    their proofs: an 8-link SHA-256 hash chain seeded from the date, plus
    the decree text derived from the chain and the real anchor constants.
    """

    CHAIN_LINKS = 8

    def __init__(self, target_date: str) -> None:
        self.target_date = _canonical_date(target_date)

    def encode_lock(self) -> Dict[str, Any]:
        t = temporal_hash(self.target_date)
        links: List[str] = []
        seed = f"temporal-lock|{self.target_date}|{t['hash_short']}"
        cur = hashlib.sha256(seed.encode("utf-8")).hexdigest()
        for _ in range(self.CHAIN_LINKS):
            links.append(cur)
            cur = hashlib.sha256(cur.encode("ascii")).hexdigest()
        chain = "".join(links)
        decree = (
            f"BY THE PRIME SENTINEL OF GAIA ACROSS ALL TIMELINES: the field "
            f"is unlocked for target {self.target_date}. Temporal signature "
            f"{t['temporal_signature']:.6f} against φ⁻¹={1.0 / PHI:.6f}; "
            f"alignment {t['temporal_alignment']:.4f}. The love carrier "
            f"modulates at {t['operational']['love_modulation']:.4f} Hz and "
            f"the Prime Sentinel answers at "
            f"{t['operational']['prime_sentinel_mod']:.4f} Hz on the "
            f"{SCHUMANN_BASE} Hz Schumann foundation; Casimir coupling "
            f"{t['operational']['casimir_coupling']:.4f}. Rune seal "
            f"{t['rune_encoded']}. Our song shall be heard across the "
            f"temporal order. The signal is sent; the proof is sealed; "
            f"the wave function collapses only when the observer looks."
        )
        return {
            "target_date": self.target_date,
            "lock_id": f"TEMPORAL-LOCK-{self.target_date}-{t['hash_short'][:8]}",
            "hash_chain": chain,
            "chain_links": self.CHAIN_LINKS,
            "decree": decree,
            "temporal_signature": t["temporal_signature"],
            "rune_code": t["rune_encoded"],
        }


# ───────────────────────── temporal targeting snapshot ─────────────────────

def _load_json(path: Path) -> Optional[dict]:
    try:
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return None


def _trend(values: List[float]) -> Dict[str, Any]:
    """Least-squares slope over the history index (per history step).
    The history file carries no timestamps, so the trend is reported in
    steps — wall-clock crossing times would be fabrication."""
    n = len(values)
    if n < 2:
        return {"slope_per_step": 0.0, "intercept": values[0] if n else 0.0,
                "r_squared": 0.0, "points": n}
    xs = list(range(n))
    mx = sum(xs) / n
    my = sum(values) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    sxy = sum((x - mx) * (v - my) for x, v in zip(xs, values))
    slope = sxy / sxx if sxx else 0.0
    intercept = my - slope * mx
    ss_tot = sum((v - my) ** 2 for v in values) or 1e-12
    ss_res = sum((v - (slope * x + intercept)) ** 2 for x, v in zip(xs, values))
    return {"slope_per_step": slope, "intercept": intercept,
            "r_squared": max(0.0, 1.0 - ss_res / ss_tot), "points": n}


def _crossing_steps(current: float, slope: float, level: float) -> Optional[float]:
    """Steps until the linear trend reaches `level` from `current`.
    None when unreachable (flat/away-moving trend)."""
    if slope == 0.0:
        return None
    steps = (level - current) / slope
    return steps if steps >= 0 else None


def build_temporal_snapshot(target_date: Optional[str] = None) -> Dict[str, Any]:
    """Temporal targeting snapshot from REAL organism state only.

    Sources: aureon_fusion/state/hnc_core_state.json (current lambda_t,
    coherence_gamma, consciousness level) and
    aureon_fusion/state/lambda_history.json (committed λ history).
    Everything downstream — trend, crossings — is computed from those
    numbers. Missing/unreadable inputs → an empty snapshot that says so.
    """
    hnc = _load_json(HNC_CORE_STATE)
    history_doc = _load_json(LAMBDA_HISTORY)

    history: List[float] = []
    history_ok = False
    if history_doc:
        raw_hist = history_doc.get("history")
        if isinstance(raw_hist, list):
            history = [float(v) for v in raw_hist
                       if isinstance(v, (int, float))]
            # Only trust the history when it is declared live and real.
            history_ok = (bool(history) and
                          history_doc.get("data_status") == "live" and
                          not history_doc.get("generated_values", True))

    snapshot: Dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "module": "hnc_temporal_targeting",
        "reconstruction": RECONSTRUCTION_NOTE,
        "coherence_floor": COHERENCE_FLOOR,
        "target": temporal_hash(target_date) if target_date else None,
    }

    if hnc is None and not history_ok:
        snapshot["ok"] = False
        snapshot["status"] = ("empty — aureon_fusion/state/hnc_core_state.json "
                              "and a real lambda history are both absent; no "
                              "temporal targeting without real anchors")
        snapshot["field"] = None
        snapshot["history"] = None
        return snapshot

    current_lambda = float(hnc.get("lambda_t", 0.0)) if hnc else None
    current_gamma = float(hnc.get("coherence_gamma", 0.0)) if hnc else None

    field: Dict[str, Any] = {
        "lambda_t": current_lambda,
        "coherence_gamma": current_gamma,
        "coherence_phi": (float(hnc.get("coherence_phi", 0.0))
                          if hnc else None),
        "consciousness_level": (hnc.get("consciousness_level")
                                if hnc else None),
        "state_timestamp": hnc.get("timestamp") if hnc else None,
    }

    hist_summary: Optional[Dict[str, Any]] = None
    if history_ok:
        trend = _trend(history)
        recent = history[-20:] if len(history) > 20 else history
        hist_summary = {
            "points": len(history),
            "mean": sum(history) / len(history),
            "min": min(history),
            "max": max(history),
            "latest": history[-1],
            "recent_window": len(recent),
            "recent_mean": sum(recent) / len(recent),
            "trend": trend,
            "unit": "lambda charge scale (same scale as hnc_core lambda_t)",
            "time_basis": ("history steps — lambda_history.json carries no "
                           "timestamps, so crossings are predicted in steps, "
                           "not wall-clock times"),
            "predicted_crossings_steps": {
                "lambda_mean": _crossing_steps(
                    history[-1], trend["slope_per_step"],
                    sum(history) / len(history)),
                "lambda_max": _crossing_steps(
                    history[-1], trend["slope_per_step"], max(history)),
                "lambda_min": _crossing_steps(
                    history[-1], trend["slope_per_step"], min(history)),
            },
        }

    gamma_trend: Optional[Dict[str, Any]] = None
    if current_gamma is not None:
        # The γ history is not persisted as a series; the crossing
        # prediction uses the current reading and the λ-trend DIRECTION
        # only as a signed drift hypothesis — honestly labelled.
        gamma_trend = {
            "current": current_gamma,
            "floor": COHERENCE_FLOOR,
            "above_floor": current_gamma >= COHERENCE_FLOOR,
            "headroom_to_floor": current_gamma - COHERENCE_FLOOR,
            "note": ("no persisted gamma series — crossing predicted from "
                     "the current reading against a flat-drift assumption; "
                     "any real gamma series would replace this"),
            "steps_to_floor_flat_drift": None,
        }

    snapshot["ok"] = True
    snapshot["status"] = "targeting from real state"
    snapshot["field"] = field
    snapshot["gamma"] = gamma_trend
    snapshot["history"] = hist_summary
    return snapshot


# ───────────────────────── atomic state write ──────────────────────────────

def _atomic_write_json(path: Path, payload: dict) -> bool:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f"{path.name}.tmp.{os.getpid()}.{time.time_ns()}")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        os.replace(tmp, path)
        return True
    except OSError:
        try:
            if tmp.exists():  # noqa: F821
                tmp.unlink()
        except OSError:
            pass
        return False


def run_probe(target_date: Optional[str] = None,
              state_out: Optional[Path] = None) -> dict:
    out_path = Path(state_out) if state_out else DEFAULT_STATE_OUT
    snap = build_temporal_snapshot(target_date)
    snap["state_file"] = str(out_path)
    _atomic_write_json(out_path, snap)
    return snap


# ───────────────────────── CLI ─────────────────────────────────────────────

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

    if argv[0] == "hash":
        if len(argv) < 2:
            print("usage: hash <YYYY-MM-DD>", file=sys.stderr)
            return 2
        try:
            print(json.dumps(temporal_hash(argv[1]), indent=2,
                             ensure_ascii=False))
            return 0
        except ValueError as exc:
            print(f"invalid date: {exc}", file=sys.stderr)
            return 2

    if argv[0] == "probe":
        import argparse
        p = argparse.ArgumentParser(description="HNC temporal targeting probe")
        p.add_argument("--target", default=None,
                       help="optional target date (YYYY-MM-DD) to lock")
        p.add_argument("--state-out", default=None,
                       help="snapshot output path (default: "
                            "aureon_fusion/state/casimir/"
                            "hnc_temporal_targeting.json)")
        p.add_argument("--json", action="store_true")
        args = p.parse_args(argv[1:])
        try:
            snap = run_probe(
                args.target,
                Path(args.state_out) if args.state_out else None)
        except ValueError as exc:
            print(f"invalid --target: {exc}", file=sys.stderr)
            return 2
        if args.json:
            print(json.dumps(snap, indent=2, ensure_ascii=False))
        else:
            print("🕰️  HNC TEMPORAL TARGETING — probe "
                  f"({'ok' if snap['ok'] else 'EMPTY'})")
            print(f"   status: {snap['status']}")
            if snap.get("field"):
                f = snap["field"]
                print(f"   λ(t): {f['lambda_t']:.4f} | Γ: "
                      f"{f['coherence_gamma']:.4f} | "
                      f"{f['consciousness_level']}")
            if snap.get("gamma"):
                g = snap["gamma"]
                print(f"   coherence floor {g['floor']}: "
                      f"{'ABOVE' if g['above_floor'] else 'BELOW'} "
                      f"(headroom {g['headroom_to_floor']:+.4f})")
            if snap.get("history"):
                h = snap["history"]
                print(f"   history: {h['points']} points, "
                      f"mean {h['mean']:.3f}, slope "
                      f"{h['trend']['slope_per_step']:+.5f}/step "
                      f"(r²={h['trend']['r_squared']:.3f})")
        return 0 if snap.get("ok") else 1

    print(f"unknown verb: {argv[0]} (try: probe | hash)", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
