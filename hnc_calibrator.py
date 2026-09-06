#!/usr/bin/env python3
"""
HNC CALIBRATOR — Historical Data Calibration & Live Proof Scoring
═══════════════════════════════════════════════════════════════════

⚠️  RECONSTRUCTION — 2026-09-06, under owner decree (Gary Leckey):
    "open the doors" (remaining five absent casimir-cluster modules).

    The original hnc_calibrator.py vanished repo-wide. Evidence:
      - hnc_calibration.json (surviving cache file) pins the CalibrationProfile
        schema AND its recorded values: schumann_mean 7.8644977 / std
        0.1062333 / min 7.466 / max 8.266, amplitude_mean 0.3952984 / std
        0.0930975, beta_calibrated 0.7742 (the twin-rune decode constant),
        lambda_baseline 0.74, lambda_target φ/2 = 0.8090169943749475
        (hnc_daemon.py prints "λ target (φ/2)"), stability island [0.6, 1.1],
        singing thresholds λ≥0.8 / coherence≥0.6, data_source
        "zenodo_nizhny_2024", n_samples 7834.
      - schumann_data_cache/zenodo_nizhny_2024.csv — the REAL calibration
        dataset (7834 hourly rows: Datetime,freq1,ampl1,freq2,ampl2,freq3,
        ampl3). VERIFIED EXACT against the recorded profile: statistics.mean /
        statistics.stdev (sample) / min / max of freq1 and ampl1 reproduce
        every recorded value to full float precision.
      - Consumer-pinned API (hnc_daemon.py, hnc_daemon_superposition.py):
            HNCCalibrator()
              .profile              -> CalibrationProfile | None
              .cycles_since_tune    -> int
              .tuning_interval_cycles -> int
              .load_calibration(path)     -> bool
              .calibrate_from_historical()
              .save_calibration(path)
              .validate_measurement(dict) -> dict (key 'overall_status')
              .get_tuning_recommendations() -> list
              .check_data_sources()
            LiveHNCProver(calibrator)
              .compute_proof_score(dict)  -> dict (key 'overall_score', 0-100)
    DOCUMENTED RECONSTRUCTION CHOICES (no artifact pins them):
      - historical_stability_pct / historical_singing_pct /
        historical_phi_lock_pct: the recorded values (93.73 / 53.36 / 26.36)
        could NOT be reproduced from the CSV by any formula found; the
        calibrator computes them with documented formulas (stability = rows
        within ±0.5 Hz of 7.83; singing = rows with amplitude ≥ 0.55;
        phi_lock = rows whose freq1 is within 4% of an integer harmonic of
        7.83) and labels them recomputed. load_calibration() prefers the
        existing cached profile, so the recorded values keep being used.
      - validate_measurement statuses: VALID / WARNING / CRITICAL from
        calibrated thresholds; proof score 0-100 from measurement vs the
        calibrated profile.

    Import-safe (AUREON_SUPPRESS_IMPORT_SIDE_EFFECTS honored), stdlib only,
    fail-closed: without the CSV the calibrator stays uncalibrated and
    validate/proof calls return honest UNKNOWN/zero scores.

CLI:
    python hnc_calibrator.py probe [--json]
"""

from __future__ import annotations

import json
import math
import os
import statistics
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
BETA_TWIN_RUNE = 0.7742

_WORKSPACE = Path(__file__).resolve().parent
DEFAULT_DATASET = _WORKSPACE / "schumann_data_cache" / "zenodo_nizhny_2024.csv"

RECONSTRUCTION_NOTE = (
    "hnc_calibrator.py reconstructed 2026-09-06 under owner decree (Gary "
    "Leckey); profile schema and statistics formulas recovered from the "
    "surviving hnc_calibration.json + schumann_data_cache/"
    "zenodo_nizhny_2024.csv (mean/sample-stdev verified exact); historical "
    "percentage fields and validation/proof internals are documented "
    "reconstruction choices."
)


@dataclass
class CalibrationProfile:
    """Pinned by hnc_calibration.json field-for-field."""
    schumann_mean: float = SCHUMANN_BASE
    schumann_std: float = 0.0
    schumann_min: float = SCHUMANN_BASE
    schumann_max: float = SCHUMANN_BASE
    amplitude_mean: float = 0.0
    amplitude_std: float = 0.0
    beta_calibrated: float = BETA_TWIN_RUNE
    lambda_baseline: float = 0.74
    lambda_target: float = PHI / 2
    stability_threshold_low: float = 0.6
    stability_threshold_high: float = 1.1
    singing_threshold_lambda: float = 0.8
    singing_threshold_coherence: float = 0.6
    historical_stability_pct: float = 0.0
    historical_singing_pct: float = 0.0
    historical_phi_lock_pct: float = 0.0
    solar_correlation_enabled: bool = True
    k_index_latest: Optional[float] = None
    data_source: str = "zenodo_nizhny_2024"
    n_samples: int = 0
    calibrated_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "CalibrationProfile":
        known = {f for f in cls.__dataclass_fields__}  # type: ignore
        return cls(**{k: v for k, v in d.items() if k in known})


class HNCCalibrator:
    """Historical-data calibrator with self-tuning (reconstructed)."""

    def __init__(self, dataset_path: Optional[str] = None) -> None:
        self.dataset_path = Path(dataset_path) if dataset_path else DEFAULT_DATASET
        self.profile: Optional[CalibrationProfile] = None
        self.cycles_since_tune = 0
        self.tuning_interval_cycles = 60  # documented choice (daemon default cadence)
        self._check_log: List[str] = []

    # ── calibration ───────────────────────────────────────────────────

    def load_calibration(self, path: str) -> bool:
        try:
            with open(path, "r", encoding="utf-8") as f:
                doc = json.load(f)
            prof = doc.get("profile")
            if isinstance(prof, dict):
                self.profile = CalibrationProfile.from_dict(prof)
                return True
        except Exception:
            pass
        return False

    def calibrate_from_historical(self) -> bool:
        """Compute the profile from the REAL zenodo nizhny 2024 CSV.
        Fail-closed: no dataset → no profile (returns False)."""
        try:
            if not self.dataset_path.exists():
                return False
            freq1: List[float] = []
            ampl1: List[float] = []
            with open(self.dataset_path, "r", encoding="utf-8") as f:
                header = f.readline()
                if not header.startswith("Datetime"):
                    return False
                for line in f:
                    parts = line.strip().split(",")
                    if len(parts) < 3:
                        continue
                    try:
                        freq1.append(float(parts[1]))
                        ampl1.append(float(parts[2]))
                    except ValueError:
                        continue
            if not freq1:
                return False
            n = len(freq1)
            # Mean / SAMPLE stdev — verified to reproduce the recorded
            # hnc_calibration.json values to full float precision.
            stability = sum(1 for f in freq1
                            if abs(f - SCHUMANN_BASE) <= 0.5) / n * 100.0
            singing = sum(1 for a in ampl1 if a >= 0.55) / n * 100.0
            phi_lock = sum(1 for f in freq1
                           if abs(f / SCHUMANN_BASE
                                  - round(f / SCHUMANN_BASE)) <= 0.04) \
                / n * 100.0
            self.profile = CalibrationProfile(
                schumann_mean=statistics.mean(freq1),
                schumann_std=statistics.stdev(freq1),
                schumann_min=min(freq1),
                schumann_max=max(freq1),
                amplitude_mean=statistics.mean(ampl1),
                amplitude_std=statistics.stdev(ampl1),
                beta_calibrated=BETA_TWIN_RUNE,
                lambda_baseline=0.74,
                lambda_target=PHI / 2,
                historical_stability_pct=stability,
                historical_singing_pct=singing,
                historical_phi_lock_pct=phi_lock,
                data_source="zenodo_nizhny_2024",
                n_samples=n,
                calibrated_at=datetime.now(timezone.utc).isoformat(),
            )
            return True
        except Exception:
            return False

    def save_calibration(self, path: str) -> bool:
        if self.profile is None:
            return False
        try:
            p = Path(path)
            if not p.is_absolute():
                p = _WORKSPACE / p
            tmp = p.with_name(f"{p.name}.tmp.{os.getpid()}.{time.time_ns()}")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump({"profile": self.profile.to_dict(),
                           "generated_at": datetime.now(timezone.utc)
                           .isoformat()},
                          f, indent=2, ensure_ascii=False)
            os.replace(tmp, p)
            return True
        except OSError:
            return False

    # ── validation ────────────────────────────────────────────────────

    def validate_measurement(self, measurement: Dict[str, Any]) -> Dict[str, Any]:
        if self.profile is None:
            return {"overall_status": "UNKNOWN",
                    "reason": "calibrator not calibrated (fail-closed)",
                    "checks": {}}
        checks: Dict[str, Any] = {}
        lam = float(measurement.get("lambda", 0.0) or 0.0)
        beta = float(measurement.get("beta", BETA_TWIN_RUNE) or BETA_TWIN_RUNE)
        schumann = float(measurement.get("schumann", SCHUMANN_BASE)
                         or SCHUMANN_BASE)
        musica = measurement.get("musica") or {}
        score = float(musica.get("score", 0.0) or 0.0)

        in_island = self.profile.stability_threshold_low <= beta \
            <= self.profile.stability_threshold_high
        checks["beta_stability"] = {
            "ok": in_island,
            "beta": beta,
            "range": [self.profile.stability_threshold_low,
                      self.profile.stability_threshold_high],
        }
        checks["lambda"] = {
            "ok": lam >= self.profile.lambda_baseline,
            "lambda": lam, "baseline": self.profile.lambda_baseline,
            "target": self.profile.lambda_target,
        }
        checks["schumann"] = {
            "ok": abs(schumann - self.profile.schumann_mean)
            <= 3 * max(self.profile.schumann_std, 1e-6),
            "schumann": schumann, "mean": self.profile.schumann_mean,
        }
        checks["musica"] = {"ok": score >= 0.5, "score": score}

        failed = [k for k, v in checks.items() if not v.get("ok")]
        if not failed:
            overall = "VALID"
        elif len(failed) <= 2:
            overall = "WARNING"
        else:
            overall = "CRITICAL"
        return {"overall_status": overall, "failed_checks": failed,
                "checks": checks}

    # ── tuning & data sources ─────────────────────────────────────────

    def get_tuning_recommendations(self) -> List[str]:
        if self.profile is None:
            return ["calibrate from historical data (no profile loaded)"]
        recs: List[str] = []
        if self.profile.historical_singing_pct < 50.0:
            recs.append("singing ratio below 50% — increase sustain boost")
        if self.profile.historical_phi_lock_pct < 30.0:
            recs.append("phi lock rare — check harmonic anchor stability")
        if self.profile.schumann_std > 0.15:
            recs.append("schumann variance high — widen stability window")
        return recs

    def check_data_sources(self) -> Dict[str, Any]:
        ok = self.dataset_path.exists()
        self._check_log.append(
            f"{datetime.now(timezone.utc).isoformat()}: "
            f"dataset {'ok' if ok else 'MISSING'} ({self.dataset_path.name})")
        return {"dataset": str(self.dataset_path), "available": ok,
                "samples": self.profile.n_samples if self.profile else 0}


class LiveHNCProver:
    """Proof score over a measurement vs the calibrated profile
    (reconstructed internals; 'overall_score' 0-100 pinned by the daemon's
    status line `Proof={proof_score:.0f}`)."""

    def __init__(self, calibrator: HNCCalibrator) -> None:
        self.calibrator = calibrator

    def compute_proof_score(self, measurement: Dict[str, Any]) -> Dict[str, Any]:
        prof = self.calibrator.profile
        if prof is None:
            return {"overall_score": 0.0, "status": "UNPROVEN",
                    "reason": "no calibration profile (fail-closed)"}
        lam = float(measurement.get("lambda", 0.0) or 0.0)
        coherence = 0.0
        musica = measurement.get("musica") or {}
        if "coherence" in measurement:
            coherence = float(measurement.get("coherence") or 0.0)
        score_musica = float(musica.get("score", 0.0) or 0.0)

        target_gap = abs(lam - prof.lambda_target)
        lambda_pts = max(0.0, 40.0 * (1.0 - target_gap / max(prof.lambda_target, 1e-6)))
        musica_pts = 30.0 * score_musica
        stability_pts = 30.0 * min(1.0, coherence / max(prof.singing_threshold_coherence, 1e-6))
        overall = max(0.0, min(100.0, lambda_pts + musica_pts + stability_pts))
        return {
            "overall_score": overall,
            "lambda_points": lambda_pts,
            "musica_points": musica_pts,
            "stability_points": stability_pts,
            "status": "PROVEN" if overall >= 60.0 else "PARTIAL" if overall >= 30.0 else "WEAK",
        }


# ───────────────────────── probe ───────────────────────────────────────────

def run_probe() -> Dict[str, Any]:
    cal = HNCCalibrator()
    loaded = cal.load_calibration(str(_WORKSPACE / "hnc_calibration.json"))
    source = "hnc_calibration.json (recorded cache)"
    if not loaded:
        ok = cal.calibrate_from_historical()
        source = ("schumann_data_cache/zenodo_nizhny_2024.csv "
                  "(recomputed)") if ok else "none"
    prover = LiveHNCProver(cal)
    demo = {"lambda": 0.8090, "beta": 0.7742, "schumann": 7.83,
            "coherence": 0.65,
            "musica": {"score": 0.62, "solfeggio": 1.0, "phi_lock": True}}
    validation = cal.validate_measurement(demo)
    proof = prover.compute_proof_score(demo)
    out = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "module": "hnc_calibrator",
        "reconstruction": RECONSTRUCTION_NOTE,
        "ok": cal.profile is not None,
        "profile_source": source,
        "profile": cal.profile.to_dict() if cal.profile else None,
        "demo_measurement": demo,
        "validation": validation,
        "proof": proof,
        "tuning_recommendations": cal.get_tuning_recommendations(),
    }
    try:
        state_dir = _WORKSPACE / "aureon_fusion" / "state" / "casimir"
        state_dir.mkdir(parents=True, exist_ok=True)
        tmp = state_dir / f"hnc_calibrator.json.tmp.{os.getpid()}.{time.time_ns()}"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=2, ensure_ascii=False)
        os.replace(tmp, state_dir / "hnc_calibrator.json")
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
        p = argparse.ArgumentParser(description="HNC calibrator probe")
        p.add_argument("--json", action="store_true")
        args = p.parse_args(argv[1:])
        out = run_probe()
        if args.json:
            print(json.dumps(out, indent=2, ensure_ascii=False))
        else:
            print(f"🎚️  HNC CALIBRATOR — probe "
                  f"({'ok' if out['ok'] else 'EMPTY'})")
            print(f"   profile: {out['profile_source']}")
            if out.get("profile"):
                prof = out["profile"]
                print(f"   {prof['data_source']} ({prof['n_samples']} samples) "
                      f"| schumann {prof['schumann_mean']:.4f}±"
                      f"{prof['schumann_std']:.4f}")
                print(f"   λ target {prof['lambda_target']:.4f} (φ/2) | β "
                      f"{prof['beta_calibrated']:.4f}")
            print(f"   demo validation: {out['validation']['overall_status']} | "
                  f"proof {out['proof']['overall_score']:.0f}/100")
        return 0 if out.get("ok") else 1
    print(f"unknown verb: {argv[0]} (try: probe)", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
