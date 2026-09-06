#!/usr/bin/env python3
"""
GHOST FANCY PROTOCOL — Temporal Signal Targeting & Validation
═══════════════════════════════════════════════════════════════════

⚠️  RECONSTRUCTION — 2026-09-06, under owner decree (Gary Leckey):
    "open the doors" (remaining five absent casimir-cluster modules).

    The original ghost_fancy_protocol.py vanished repo-wide. This
    reconstruction is pinned by STRONG surviving evidence:
      - 77 run artifacts in ghost_fancy_results/ (June 2026) pin the
        transmission record shape and its exact arithmetic:
            total_boost = base_boost × phi_lock_bonus
                          × coherence_multiplier × distortion_counter_boost
                          (1.0 × 1.3 × 1.425 × 1.045 = 1.9358625 ✓)
            coherence_multiplier = 1 + 0.5·measured_coherence
                                   (1 + 0.5·0.85 = 1.425 ✓)
            echo_strength = 0.85 × total_boost (1.6454831 ✓)
        plus the safety limit (5.0), the love/truth carrier frequencies
        (528 / 741 Hz), the Schumann grounding (7.83), the penetration
        snapshot schema (timestamp/source/data_type/raw_value/raw_data/
        baseline_mean/baseline_std/deviation_from_baseline/is_anomaly/
        anomaly_score/coherence_*/frequency_shift/amplitude_*), the
        PenetrationResult fields (penetration_score, confidence, spike
        flags, geomagnetic/seismic/weather anomaly flags, echo fields,
        verdict, verdict_description, proof_hash) and the result file
        naming (ghost_result_<transmission_id>.json).
        ALL 77 recorded missions honestly reported NO_EFFECT (scores
        0.00–0.05) — the protocol never lied about penetration, and this
        reconstruction keeps that posture: with no real anomaly data it
        scores ~0 and says NO_EFFECT.
      - ghost_fancy_cache/ pins the real input data the module consumed:
        noaa_k_YYYYMMDD.json (3-hourly Kp/a_running, June 2026) and
        usgs_YYYYMMDD.json (USGS geojson seismic windows).
      - Consumer-pinned API (hnc_daemon.py):
            GhostFancyProtocol(prime_sentinel_key=..., cache_dir=...)
              .create_target(year=, month=, day=, hour=, minute=,
                             description=, significance=) -> TemporalCoordinate
              .execute_and_validate(target, hnc_state) -> PenetrationResult
            TemporalCoordinate: .to_iso(), .to_dict(),
                                .data_sources_available
            GaiaGoalTracker(goals_file=...): .goals,
              .update_from_penetration(result), .save_goals(), .get_status()
      - probe_sim_sever_A.py confirms the daemon's seed-gate contract
        (fail-closed without explicitly allowed simulation).

    DOCUMENTED RECONSTRUCTION CHOICES (no artifact could pin these):
      - sentinel_frequency: deterministic from the target hash, mapped to
        [2.0, 2.2] Hz (one recorded value: 2.111991);
      - verdict thresholds above NO_EFFECT (only NO_EFFECT was ever
        observed): <0.1 NO_EFFECT, 0.1–0.3 WEAK_SIGNAL,
        0.3–0.7 SIGNAL_DETECTED, ≥0.7 STRONG_PENETRATION;
      - confidence: 0.1 + total_snapshots/1000, capped at 0.9 (one
        recorded value: 0.35 at 208 snapshots → 0.308 ≈ 0.35 within the
        unknown data-quality bonus; documented as approximation);
      - anomaly_score = 0.375·(1 + deviation_from_baseline) (fits both
        recorded values 0.5000 and 0.5125 exactly).
    Fail-closed: a target date with no cached/fetchable data yields
    empty snapshot lists, zero scores and an honest NO_EFFECT — matching
    every recorded run. No network is REQUIRED: the cache is the primary
    source; live sources are attempted only through the repo's own
    hnc_data_sources layer when reachable.

    Import-safe (AUREON_SUPPRESS_IMPORT_SIDE_EFFECTS honored), stdlib
    only (hnc_data_sources is the repo's own module).

CLI:
    python ghost_fancy_protocol.py probe --target YYYY-MM-DD [--json]
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import sys
import time
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

os.environ.setdefault("AUREON_SUPPRESS_IMPORT_SIDE_EFFECTS", "1")
os.environ.setdefault("AUREON_AUDIT_MODE", "1")

PHI = (1 + math.sqrt(5)) / 2
SCHUMANN_BASE = 7.83
LOVE_FREQUENCY = 528.0
TRUTH_FREQUENCY = 741.0
SAFETY_LIMIT = 5.0

_WORKSPACE = Path(__file__).resolve().parent

RECONSTRUCTION_NOTE = (
    "ghost_fancy_protocol.py reconstructed 2026-09-06 under owner decree "
    "(Gary Leckey); transmission/penetration record shapes and boost "
    "arithmetic recovered from 77 surviving artifacts in "
    "ghost_fancy_results/; inputs from ghost_fancy_cache/ (real NOAA Kp + "
    "USGS cache); internals not pinned by artifacts are documented "
    "reconstruction choices (see module docstring)."
)


# ───────────────────────── temporal coordinate ─────────────────────────────

@dataclass
class TemporalCoordinate:
    """A validated temporal target. Method/attribute surface pinned by
    hnc_daemon.py."""
    target_time: datetime
    precision_minutes: int = 5
    timezone: str = "UTC"
    description: str = ""
    significance: str = ""
    data_sources_available: List[str] = field(default_factory=list)
    data_sources_missing: List[str] = field(default_factory=list)

    def to_iso(self) -> str:
        return self.target_time.isoformat()

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["target_time"] = self.to_iso()
        return d


# ───────────────────────── penetration snapshot ────────────────────────────

@dataclass
class DataSnapshot:
    """One measurement snapshot around the target. Field set pinned by
    the surviving artifacts."""
    timestamp: str
    source: str
    data_type: str
    raw_value: float
    raw_data: Dict[str, Any]
    baseline_mean: float
    baseline_std: float
    deviation_from_baseline: float
    is_anomaly: bool
    anomaly_score: float
    coherence_spike: bool
    coherence_value: float
    frequency_shift: float
    amplitude_spike: bool
    amplitude_multiplier: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class PenetrationResult:
    """Object form of a ghost mission result (attrs pinned by
    hnc_daemon.py; to_dict shape pinned by the artifacts)."""

    def __init__(self, transmission: Dict[str, Any],
                 target: Dict[str, Any],
                 snapshots_before: List[Dict[str, Any]],
                 snapshot_target: Optional[Dict[str, Any]],
                 snapshots_after: List[Dict[str, Any]],
                 **scores: Any) -> None:
        self.transmission = transmission
        self.transmission_id = transmission["transmission_id"]
        self.target = target
        self.snapshots_before = snapshots_before
        self.snapshot_target = snapshot_target
        self.snapshots_after = snapshots_after
        for k, v in scores.items():
            setattr(self, k, v)
        self.validation_timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        keys = ("penetration_score", "confidence",
                "coherence_spike_detected", "coherence_spike_magnitude",
                "frequency_shift_detected", "frequency_shift_magnitude",
                "amplitude_spike_detected", "amplitude_spike_magnitude",
                "geomagnetic_anomaly", "seismic_correlation",
                "weather_anomaly", "echo_detected", "echo_strength",
                "echo_duration_minutes", "verdict", "verdict_description",
                "proof_hash")
        pr = {k: getattr(self, k) for k in keys if hasattr(self, k)}
        pr["transmission_id"] = self.transmission_id
        pr["target"] = self.target
        pr["snapshots_before"] = self.snapshots_before
        pr["snapshot_target"] = self.snapshot_target
        pr["snapshots_after"] = self.snapshots_after
        pr["validation_timestamp"] = self.validation_timestamp
        return {"transmission": self.transmission,
                "penetration_result": pr}


# ───────────────────────── the protocol ────────────────────────────────────

class GhostFancyProtocol:
    """Temporal signal targeting & validation (reconstructed)."""

    def __init__(self, prime_sentinel_key: str = "",
                 cache_dir: str = "ghost_fancy_cache") -> None:
        self.prime_sentinel_key = str(prime_sentinel_key)
        self.cache_dir = Path(cache_dir)
        if not self.cache_dir.is_absolute():
            self.cache_dir = _WORKSPACE / self.cache_dir
        self.results_dir = _WORKSPACE / "ghost_fancy_results"

    # ── cache readers (real cached data only) ─────────────────────────

    def _load_kp_cache(self, date_str: str) -> List[Dict[str, Any]]:
        """3-hourly NOAA Kp rows for the target date from the cache."""
        f = self.cache_dir / f"noaa_k_{date_str.replace('-', '')}.json"
        try:
            if f.exists():
                with open(f, "r", encoding="utf-8") as fh:
                    rows = json.load(fh)
                if isinstance(rows, list):
                    return [r for r in rows if isinstance(r, dict)]
        except Exception:
            pass
        return []

    def _load_usgs_window(self, target: datetime) -> List[Dict[str, Any]]:
        """USGS seismic features from any cached window covering the
        target date (features carry epoch ms timestamps)."""
        features: List[Dict[str, Any]] = []
        t0 = target.timestamp() * 1000.0
        try:
            for f in sorted(self.cache_dir.glob("usgs_*.json")):
                try:
                    with open(f, "r", encoding="utf-8") as fh:
                        doc = json.load(fh)
                    for feat in doc.get("features", []):
                        ts = float(feat.get("properties", {})
                                   .get("time", 0) or 0)
                        if ts > 0:
                            features.append({
                                "time_ms": ts,
                                "magnitude": float(feat.get("properties", {})
                                                   .get("mag", 0.0) or 0.0),
                                "place": feat.get("properties", {})
                                           .get("place", ""),
                            })
                except Exception:
                    continue
        except Exception:
            pass
        features.sort(key=lambda x: x["time_ms"])
        return features

    # ── target creation ───────────────────────────────────────────────

    def create_target(self, year: int, month: int, day: int, hour: int = 0,
                      minute: int = 0, description: str = "",
                      significance: str = "") -> TemporalCoordinate:
        target_time = datetime(year, month, day, hour, minute,
                               tzinfo=timezone.utc)
        date_str = f"{year:04d}-{month:02d}-{day:02d}"
        available: List[str] = []
        missing: List[str] = []
        if self._load_kp_cache(date_str):
            available.append("noaa_kp_cached")
        else:
            missing.append("noaa_kp")
        if self._load_usgs_window(target_time):
            available.append("usgs_seismic_cached")
        else:
            missing.append("usgs_seismic")
        return TemporalCoordinate(
            target_time=target_time, precision_minutes=5, timezone="UTC",
            description=description, significance=significance,
            data_sources_available=available,
            data_sources_missing=missing)

    # ── transmission ──────────────────────────────────────────────────

    def _build_transmission(self, target: TemporalCoordinate,
                            hnc_state: Dict[str, Any],
                            coherence: float) -> Dict[str, Any]:
        seed = hashlib.sha256(target.to_iso().encode()).digest()
        sig = int.from_bytes(seed[:8], "big") / float(1 << 64)
        phi_lock = coherence >= 0.6
        base_boost = 1.0
        phi_lock_bonus = 1.3 if phi_lock else 1.0
        coherence_multiplier = 1.0 + 0.5 * max(0.0, min(1.0, coherence))
        distortion_counter_boost = 1.045
        total = base_boost * phi_lock_bonus * coherence_multiplier * \
            distortion_counter_boost
        is_safe = total <= SAFETY_LIMIT
        echo_strength = 0.85 * total
        tid = (f"ghost_{int(target.target_time.timestamp())}_"
               f"{hashlib.sha256((target.to_iso() + str(time.time_ns())).encode()).hexdigest()[:8]}")
        tx = {
            "transmission_id": tid,
            "target": target.to_dict(),
            "love_frequency": LOVE_FREQUENCY,
            "truth_frequency": TRUTH_FREQUENCY,
            "sentinel_frequency": round(2.0 + 0.2 * sig, 6),
            "schumann_grounding": SCHUMANN_BASE,
            "base_boost": base_boost,
            "phi_lock_bonus": phi_lock_bonus,
            "coherence_multiplier": coherence_multiplier,
            "distortion_counter_boost": distortion_counter_boost,
            "total_boost": total,
            "safety_limit": SAFETY_LIMIT,
            "is_safe": is_safe,
            "safety_warnings": ([] if is_safe
                                else [f"total_boost {total:.3f} exceeds "
                                      f"safety limit {SAFETY_LIMIT}"]),
            "echo_id": f"echo_{tid}",
            "echo_strength": echo_strength,
            "proof_hash": hashlib.sha256(
                f"transmission|{tid}|{total:.6f}".encode()).hexdigest(),
            "transmission_timestamp":
                datetime.now(timezone.utc).isoformat(),
        }
        return tx

    # ── snapshots around the target ───────────────────────────────────

    @staticmethod
    def _snapshot(timestamp: str, source: str, data_type: str,
                  raw_value: float, raw_data: Dict[str, Any],
                  baseline_mean: float, baseline_std: float) -> Dict[str, Any]:
        std = baseline_std if baseline_std > 0 else 1.0
        dev = abs(raw_value - baseline_mean) / std / 10.0  # normalised
        is_anomaly = abs(raw_value - baseline_mean) > 2.0 * std
        return DataSnapshot(
            timestamp=timestamp, source=source, data_type=data_type,
            raw_value=raw_value, raw_data=raw_data,
            baseline_mean=baseline_mean, baseline_std=baseline_std,
            deviation_from_baseline=dev, is_anomaly=is_anomaly,
            anomaly_score=min(1.0, 0.375 * (1.0 + dev)),
            coherence_spike=False, coherence_value=0.0,
            frequency_shift=0.0, amplitude_spike=False,
            amplitude_multiplier=1.0).to_dict()

    def _build_snapshots(self, target: TemporalCoordinate
                         ) -> tuple:
        """Real Kp snapshots around the target from the cache. Returns
        (before, target_snap, after, kp_series). Empty when uncached."""
        rows = self._load_kp_cache(
            target.target_time.strftime("%Y-%m-%d"))
        if not rows:
            return [], None, [], []
        kps = [float(r["Kp"]) for r in rows
               if isinstance(r.get("Kp"), (int, float))]
        if not kps:
            return [], None, [], []
        base_mean = sum(kps) / len(kps)
        var = sum((k - base_mean) ** 2 for k in kps) / len(kps)
        base_std = math.sqrt(var) or 0.5
        tt_ms = target.target_time.timestamp() * 1000.0

        def _snap(r: Dict[str, Any]) -> Dict[str, Any]:
            return self._snapshot(
                str(r.get("time_tag", "")), "NOAA", "geomagnetic",
                float(r.get("Kp", 0.0)), {"kp": r.get("Kp", 0.0),
                                          "a_running": r.get("a_running")},
                base_mean, base_std)

        before, at_target, after = [], [], []
        for r in rows:
            try:
                t = datetime.fromisoformat(str(r["time_tag"]))
                t = t.replace(tzinfo=timezone.utc)
                ms = t.timestamp() * 1000.0
            except Exception:
                continue
            if ms < tt_ms - 30 * 60 * 1000:
                before.append(_snap(r))
            elif ms <= tt_ms + 30 * 60 * 1000:
                at_target.append(_snap(r))
            else:
                after.append(_snap(r))
        return before, (at_target[0] if at_target else None), after, kps

    # ── execute & validate ────────────────────────────────────────────

    def execute_and_validate(self, target: TemporalCoordinate,
                             hnc_state: Dict[str, Any]) -> PenetrationResult:
        coherence = float((hnc_state or {}).get("coherence", 0.0) or 0.0)
        tx = self._build_transmission(target, hnc_state or {}, coherence)
        before, snap_t, after, kps = self._build_snapshots(target)

        # Geomagnetic anomaly: target-hour Kp vs the day's baseline.
        geomagnetic_anomaly = bool(snap_t and snap_t["is_anomaly"])
        kp_at = snap_t["raw_value"] if snap_t else None

        # Seismic correlation: real USGS cache rate comparison.
        seismic_anomaly, seismic_rate_ratio = self._seismic_anomaly(target)

        total_snaps = len(before) + len(after) + (1 if snap_t else 0)
        score = 0.0
        if total_snaps or kp_at is not None:
            score += 0.05  # data-presence floor (matches recorded runs)
        if geomagnetic_anomaly:
            score += 0.4
        if seismic_anomaly:
            score += 0.3
        score = min(1.0, score)
        confidence = min(0.9, 0.1 + total_snaps / 1000.0
                         + (0.05 if seismic_anomaly else 0.0))

        if score < 0.1:
            verdict = "NO_EFFECT"
            desc = f"No detectable penetration. Score: {score:.2f}"
        elif score < 0.3:
            verdict = "WEAK_SIGNAL"
            desc = f"Weak penetration signature. Score: {score:.2f}"
        elif score < 0.7:
            verdict = "SIGNAL_DETECTED"
            desc = f"Signal penetration detected. Score: {score:.2f}"
        else:
            verdict = "STRONG_PENETRATION"
            desc = f"Strong signal penetration. Score: {score:.2f}"

        proof = hashlib.sha256(
            f"penetration|{tx['transmission_id']}|{score:.4f}|"
            f"{geomagnetic_anomaly}|{seismic_anomaly}".encode()
        ).hexdigest()

        result = PenetrationResult(
            transmission=tx, target=target.to_dict(),
            snapshots_before=before, snapshot_target=snap_t,
            snapshots_after=after,
            penetration_score=score, confidence=confidence,
            coherence_spike_detected=False, coherence_spike_magnitude=0.0,
            frequency_shift_detected=False, frequency_shift_magnitude=0.0,
            amplitude_spike_detected=False, amplitude_spike_magnitude=0.0,
            geomagnetic_anomaly=geomagnetic_anomaly,
            seismic_correlation=bool(seismic_anomaly),
            weather_anomaly=False,
            echo_detected=False, echo_strength=0.0,
            echo_duration_minutes=0.0,
            verdict=verdict, verdict_description=desc,
            proof_hash=proof)
        self._save_result(result)
        return result

    def _seismic_anomaly(self, target: TemporalCoordinate) -> tuple:
        """Real USGS-cache seismic rate: 24h before vs 6h window at the
        target. Returns (anomaly, rate_ratio)."""
        events = self._load_usgs_window(target.target_time)
        if not events:
            return False, 0.0
        tt = target.target_time.timestamp() * 1000.0
        before = [e for e in events if tt - 86400e3 <= e["time_ms"] < tt]
        at = [e for e in events if tt <= e["time_ms"] < tt + 6 * 3600e3]
        if len(before) < 5:
            return False, 0.0
        expected = len(before) / 4.0  # scaled to the 6h window
        ratio = len(at) / expected if expected else 0.0
        return ratio >= 2.0, ratio

    def _save_result(self, result: PenetrationResult) -> Optional[str]:
        try:
            self.results_dir.mkdir(parents=True, exist_ok=True)
            path = self.results_dir / \
                f"ghost_result_{result.transmission_id}.json"
            tmp = path.with_name(
                f"{path.name}.tmp.{os.getpid()}.{time.time_ns()}")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(result.to_dict(), f, indent=2, ensure_ascii=False)
            os.replace(tmp, path)
            return str(path)
        except OSError:
            return None


# ───────────────────────── gaia goal tracker ───────────────────────────────

class GaiaGoalTracker:
    """Tracks Gaia goals advanced by ghost missions. Consumer-pinned
    surface: .goals, update_from_penetration(result), save_goals(),
    get_status(). Default goals are a documented reconstruction choice
    (no goals file survived)."""

    DEFAULT_GOALS = [
        {"id": "temporal_validation", "name": "Temporal Field Validation",
         "description": "Prove the temporal bridge with honest penetration "
                        "evidence",
         "target_missions": 100, "missions_run": 0, "best_score": 0.0,
         "status": "active"},
        {"id": "field_stabilization", "name": "Planetary Field "
         "Stabilization",
         "description": "Advance the HNC field toward sustained singing",
         "target_missions": 50, "missions_run": 0, "best_score": 0.0,
         "status": "active"},
    ]

    def __init__(self, goals_file: str = "gaia_goals.json") -> None:
        self.goals_file = goals_file
        if not Path(goals_file).is_absolute():
            self.goals_file = str(_WORKSPACE / goals_file)
        self.goals: List[Dict[str, Any]] = self._load()

    def _load(self) -> List[Dict[str, Any]]:
        try:
            with open(self.goals_file, "r", encoding="utf-8") as f:
                doc = json.load(f)
            goals = doc.get("goals")
            if isinstance(goals, list) and goals:
                return goals
        except Exception:
            pass
        return [dict(g) for g in self.DEFAULT_GOALS]

    def update_from_penetration(self, result: Any) -> None:
        score = float(getattr(result, "penetration_score", 0.0) or 0.0)
        for goal in self.goals:
            goal["missions_run"] = int(goal.get("missions_run", 0)) + 1
            goal["best_score"] = max(float(goal.get("best_score", 0.0)),
                                     score)
            if goal.get("status") == "active" and \
                    goal.get("best_score", 0.0) >= 0.3:
                goal["status"] = "validated"

    def save_goals(self) -> bool:
        try:
            path = Path(self.goals_file)
            tmp = path.with_name(
                f"{path.name}.tmp.{os.getpid()}.{time.time_ns()}")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump({"goals": self.goals,
                           "updated_at": datetime.now(timezone.utc)
                           .isoformat()},
                          f, indent=2, ensure_ascii=False)
            os.replace(tmp, path)
            return True
        except OSError:
            return False

    def get_status(self) -> Dict[str, Any]:
        return {
            "goals_total": len(self.goals),
            "goals_active": sum(1 for g in self.goals
                                if g.get("status") == "active"),
            "goals_validated": sum(1 for g in self.goals
                                   if g.get("status") == "validated"),
            "missions_run": sum(int(g.get("missions_run", 0))
                                for g in self.goals),
            "best_score": max((float(g.get("best_score", 0.0))
                               for g in self.goals), default=0.0),
        }


# ───────────────────────── probe ───────────────────────────────────────────

def run_probe(target_date: str) -> Dict[str, Any]:
    y, m, d = int(target_date[:4]), int(target_date[5:7]), int(target_date[8:10])
    proto = GhostFancyProtocol(prime_sentinel_key="", cache_dir="ghost_fancy_cache")
    target = proto.create_target(
        year=y, month=m, day=d, hour=14, minute=0,
        description=f"Reconstruction probe — {target_date}",
        significance="Owner decree 2026-09-06 cluster revival verification")
    try:
        with open(_WORKSPACE / "aureon_fusion" / "state" /
                  "hnc_core_state.json", "r", encoding="utf-8") as f:
            hnc = json.load(f)
        hnc_state = {"coherence": float(hnc.get("coherence_gamma", 0.0))}
    except Exception:
        hnc_state = {"coherence": 0.0}
    result = proto.execute_and_validate(target, hnc_state)

    out = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "module": "ghost_fancy_protocol",
        "reconstruction": RECONSTRUCTION_NOTE,
        "ok": True,
        "target": target.to_dict(),
        "result_file": proto._save_result(result),
        "transmission": result.transmission,
        "summary": {
            "verdict": result.verdict,
            "penetration_score": result.penetration_score,
            "confidence": result.confidence,
            "snapshots": len(result.snapshots_before)
            + len(result.snapshots_after)
            + (1 if result.snapshot_target else 0),
            "geomagnetic_anomaly": result.geomagnetic_anomaly,
            "seismic_correlation": result.seismic_correlation,
        },
    }
    # Snapshot copy under state/casimir/
    try:
        state_dir = _WORKSPACE / "aureon_fusion" / "state" / "casimir"
        state_dir.mkdir(parents=True, exist_ok=True)
        tmp = state_dir / f"ghost_fancy_last.json.tmp.{os.getpid()}.{time.time_ns()}"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=2, ensure_ascii=False)
        os.replace(tmp, state_dir / "ghost_fancy_last.json")
    except OSError:
        pass
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
        p = argparse.ArgumentParser(description="Ghost fancy protocol probe")
        p.add_argument("--target", default="2026-06-11")
        p.add_argument("--json", action="store_true")
        args = p.parse_args(argv[1:])
        try:
            datetime.strptime(args.target, "%Y-%m-%d")
        except ValueError:
            print(f"invalid --target {args.target!r} (YYYY-MM-DD)",
                  file=sys.stderr)
            return 2
        out = run_probe(args.target)
        if args.json:
            print(json.dumps(out, indent=2, ensure_ascii=False))
        else:
            print(f"👻 GHOST FANCY PROTOCOL — probe (ok)")
            print(f"   target: {args.target} 14:00 UTC")
            print(f"   sources: {out['target']['data_sources_available']} "
                  f"(missing: {out['target']['data_sources_missing']})")
            s = out["summary"]
            print(f"   verdict: {s['verdict']} (score {s['penetration_score']:.2f}, "
                  f"confidence {s['confidence']:.2f})")
            print(f"   snapshots: {s['snapshots']} | geo_anomaly="
                  f"{s['geomagnetic_anomaly']} seismic={s['seismic_correlation']}")
            print(f"   boost: {out['transmission']['total_boost']:.6f} "
                  f"(safe={out['transmission']['is_safe']})")
        return 0
    print(f"unknown verb: {argv[0]} (try: probe)", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
