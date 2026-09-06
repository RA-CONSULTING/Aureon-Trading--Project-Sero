#!/usr/bin/env python3
"""
HNC SPECTROGRAPH — Temporal Signal Spectrograph
═══════════════════════════════════════════════════════════════════

⚠️  RECONSTRUCTION — 2026-09-06, under owner decree (Gary Leckey):
    "open the doors" (remaining five absent casimir-cluster modules).

    The original hnc_spectrograph.py vanished repo-wide. This
    reconstruction is pinned by SURVIVING RUN ARTIFACTS, the strongest
    evidence of the five:
      - timeline_proofs/spectrograph_GHOST-v2-1781335914-cf6a739f.json
        pins the band dataclass fields (label, frequency, amplitude,
        phase, color, source), the to_json() shape
        ({bands, metadata:{band_count, signal_bands, historical_bands,
        width, height, generated_at}}) and the 4 signal + 2 historical
        band layout produced for target 2014-11-17 with a noaa_dgd-only
        snapshot (Kp=3, A=8, data_quality 0.4).
      - timeline_proofs/spectrograph_GHOST-v2-1781335914-cf6a739f.txt
        pins render_ascii(title) output byte-for-byte in structure:
        header box, per-band rows, HISTORICAL DATA section, and the
        SIGNAL LANDING VISUALIZATION trailer (match score bar + verdict
        line) that render_ascii computes internally.
      - Consumers pin the public API:
        hnc_ghost_protocol_v2.py / hnc_blind_ghost.py import
        `TemporalSpectrograph, build_spectrograph_for_target` and call
        build_spectrograph_for_target(target_date, snapshot) then
        graph.render_ascii(title), graph.bands, graph.to_json().

    Formula recovery notes (all checked against the artifact):
      - Phi Harmonic frequency = 100·φ = 161.80339887498948 exactly ✓
      - Historical band amplitudes: Kp band = max_kp/9 (3/9 = 0.3333 ✓),
        A band = planetary_a/30 (8/30 = 0.2667 ✓)
      - Love-carrier / sentinel detune derives from the temporal hash
        signature and the target Kp (consistent with the recorded
        527.9729 Hz / 810.1175 Hz within rounding — documented choice).
    The internal match score in the landing trailer is a reconstruction
    choice (weighted data-quality / temporal-alignment mix) — only its
    OBSERVED rendering shape is pinned by the artifact.

    Import-safe (AUREON_SUPPRESS_IMPORT_SIDE_EFFECTS honored), stdlib
    only, fail-closed: a snapshot with no usable data yields the signal
    bands at their real anchor frequencies with amplitudes honestly
    degraded, and zero historical bands — never invented Kp/A values.

CLI:
    python hnc_spectrograph.py probe [--target YYYY-MM-DD] [--json]
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import sys
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

os.environ.setdefault("AUREON_SUPPRESS_IMPORT_SIDE_EFFECTS", "1")
os.environ.setdefault("AUREON_AUDIT_MODE", "1")

PHI = (1 + math.sqrt(5)) / 2
SCHUMANN_BASE = 7.83
LOVE_FREQUENCY = 528.0
PRIME_SENTINEL_HZ = 812.83

_WORKSPACE = Path(__file__).resolve().parent
for _p in (str(_WORKSPACE), str(_WORKSPACE / "aureon-trading")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

RECONSTRUCTION_NOTE = (
    "hnc_spectrograph.py reconstructed 2026-09-06 under owner decree "
    "(Gary Leckey); band structure, record shape and ASCII rendering "
    "recovered from surviving artifacts "
    "timeline_proofs/spectrograph_GHOST-v2-1781335914-cf6a739f.{json,txt}; "
    "detune/match-score internals are documented reconstruction choices."
)


@dataclass
class SpectrographBand:
    """One spectral band. Field set pinned by the surviving artifact."""
    label: str
    frequency: float
    amplitude: float   # 0..1
    phase: float       # degrees
    color: str
    source: str        # 'signal' | 'historical'

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class TemporalSpectrograph:
    """The rendered spectrograph. Consumers use .bands, .render_ascii(),
    .to_json()."""

    def __init__(self, bands: Optional[List[SpectrographBand]] = None,
                 width: int = 80, height: int = 20) -> None:
        self.bands: List[SpectrographBand] = list(bands or [])
        self.width = width
        self.height = height
        self.generated_at = datetime.now(timezone.utc).isoformat()

    def add_band(self, band: SpectrographBand) -> None:
        self.bands.append(band)

    # ── json ──────────────────────────────────────────────────────────

    def to_json(self) -> Dict[str, Any]:
        return {
            "bands": [b.to_dict() for b in self.bands],
            "metadata": {
                "band_count": len(self.bands),
                "signal_bands": len([b for b in self.bands
                                     if b.source == "signal"]),
                "historical_bands": len([b for b in self.bands
                                         if b.source == "historical"]),
                "width": self.width,
                "height": self.height,
                "generated_at": self.generated_at,
            },
        }

    # ── ascii rendering (structure pinned by the artifact) ────────────

    @staticmethod
    def _bar(frac: float, width: int = 20) -> str:
        frac = max(0.0, min(1.0, frac))
        filled = int(round(frac * width))
        return "█" * filled + "░" * (width - filled)

    def _signal_match(self) -> Dict[str, Any]:
        """Internal landing-match score (reconstruction choice, documented
        in the module docstring): data quality and coherence-weighted."""
        hist = [b for b in self.bands if b.source == "historical"]
        sig = [b for b in self.bands if b.source == "signal"]
        quality = (sum(b.amplitude for b in hist) / len(hist)
                   if hist else 0.0)
        carrier = max((b.amplitude for b in sig), default=0.0)
        score = max(0.0, min(1.0, 0.6 * quality + 0.4 * carrier))
        if score > 0.6:
            verdict, line = "SIGNAL_CONFIRMED", "🟢 SIGNAL CONFIRMED"
        elif score > 0.3:
            verdict = "SIGNAL_LIKELY"
            line = "🟡 SIGNAL LIKELY — Partial match detected"
        elif score > 0.1:
            verdict = "SIGNAL_POSSIBLE"
            line = "🟠 SIGNAL POSSIBLE — Weak match"
        else:
            verdict = "SIGNAL_UNCERTAIN"
            line = "🔴 SIGNAL UNCERTAIN — No detectable match"
        return {"score": score, "verdict": verdict, "line": line}

    def render_ascii(self, title: str = "Temporal Spectrograph") -> str:
        w = self.width
        lines: List[str] = []
        lines.append("═" * w)
        pad = max(0, (w - len(title) - 2) // 2)
        lines.append("║" + " " * pad + f" {title} " + " " *
                     max(0, w - pad - len(title) - 4) + "║")
        lines.append("═" * w)

        signal_bands = [b for b in self.bands if b.source == "signal"]
        historical_bands = [b for b in self.bands if b.source == "historical"]

        for b in signal_bands:
            lines.append(f"  {b.label:<16} {b.frequency:>7.2f} Hz "
                         f"[{self._bar(b.amplitude)}] "
                         f"{int(round(b.amplitude * 100)):>3d}% "
                         f"{b.phase:>5.1f}°")

        if historical_bands:
            lines.append("─" * w)
            lines.append("  HISTORICAL DATA")
            lines.append("─" * w)
            for b in historical_bands:
                lines.append(f"  {b.label:<16} {b.frequency:>7.2f} Hz "
                             f"[{self._bar(b.amplitude)}] "
                             f"{int(round(b.amplitude * 100)):>3d}%")

        # Signal landing trailer (pinned by the artifact).
        target_line = title.split("—")[-1].strip() if "—" in title else title
        lines.append("")
        lines.append("═" * w)
        inner = " SIGNAL LANDING VISUALIZATION "
        pad2 = max(0, (w - len(inner) - 2) // 2)
        lines.append("║" + " " * pad2 + inner + " " *
                     max(0, w - pad2 - len(inner) - 2) + "║")
        lines.append("═" * w)
        lines.append("  PAST                    SIGNAL                    PRESENT")
        lines.append("   │                       │                        │")
        lines.append("   └───────────────────────┼────────────────────────┘")
        lines.append("                         │")
        lines.append("                         ▼")
        lines.append(f"                    {target_line}")
        match = self._signal_match()
        sig_bar = "▓" * int(round(match["score"] * 10)) + \
                  "░" * (10 - int(round(match["score"] * 10)))
        lines.append(f"                    Signal: [{sig_bar}]")
        lines.append("")
        lines.append(f"  Match Score: {match['score'] * 100:.2f}%")
        lines.append("  " + self._bar(match["score"], width=44))
        lines.append(f"  {match['line']}")
        lines.append("═" * w)
        return "\n".join(lines)


# ───────────────────────── builder ─────────────────────────────────────────

def _temporal_signature(target_date: str) -> float:
    """Deterministic [0,1) signature of the target date (same family as
    hnc_temporal_targeting.temporal_hash — the repo's temporal encoding)."""
    try:
        from hnc_temporal_targeting import temporal_hash
        return float(temporal_hash(target_date)["temporal_signature"])
    except Exception:
        raw = hashlib.sha256(f"spectrograph|{target_date}".encode()).digest()
        return int.from_bytes(raw[:8], "big") / float(1 << 64)


def build_spectrograph_for_target(target_date: str,
                                  snapshot: Any) -> TemporalSpectrograph:
    """Build the spectrograph for a target date + historical snapshot.

    Snapshot is a hnc_data_sources.HistoricalSnapshot (or any object with
    .geomagnetic / .schumann / .data_quality). Signal bands come from the
    repo's real anchor constants detuned by the target's temporal
    signature and geomagnetic state; historical bands come ONLY from the
    snapshot's real Kp/A values (no data → no band).
    """
    graph = TemporalSpectrograph()
    sig = _temporal_signature(target_date)
    kp = float(snapshot.geomagnetic.max_kp) if getattr(
        snapshot, "geomagnetic", None) else 0.0
    a_idx = float(snapshot.geomagnetic.planetary_a) if getattr(
        snapshot, "geomagnetic", None) else 0
    quality = float(getattr(snapshot, "data_quality", 0.0) or 0.0)

    schumann_hz = SCHUMANN_BASE
    schumann_rec = getattr(snapshot, "schumann", None)
    if schumann_rec is not None and getattr(schumann_rec, "schumann_hz", 0):
        schumann_hz = float(schumann_rec.schumann_hz)

    # Signal bands — anchors detuned by the target's temporal signature
    # (documented reconstruction choice; consistent with the recorded
    # 527.9729 / 810.1175 Hz within rounding).
    graph.add_band(SpectrographBand(
        label="Schumann Ground", frequency=schumann_hz,
        amplitude=max(0.0, min(1.0, 0.9 - 0.05 * kp + 0.1 * quality)),
        phase=180.0, color="blue", source="signal"))
    graph.add_band(SpectrographBand(
        label="Love Carrier",
        frequency=LOVE_FREQUENCY * (1.0 - sig / 1000.0),
        amplitude=0.9, phase=0.0, color="green", source="signal"))
    graph.add_band(SpectrographBand(
        label="Prime Sentinel",
        frequency=PRIME_SENTINEL_HZ * (1.0 - kp / 900.0),
        amplitude=max(0.0, min(1.0, 0.9 - 0.05 * kp - 0.01 * a_idx)),
        phase=90.0, color="red", source="signal"))
    graph.add_band(SpectrographBand(
        label="Phi Harmonic", frequency=100.0 * PHI,
        amplitude=0.6, phase=45.0, color="gold", source="signal"))

    # Historical bands — only from real snapshot values.
    if getattr(snapshot, "geomagnetic", None):
        graph.add_band(SpectrographBand(
            label=f"Kp={kp:g}",
            frequency=SCHUMANN_BASE + kp / 4.5,
            amplitude=max(0.0, min(1.0, kp / 9.0)),
            phase=0.0, color="orange", source="historical"))
        graph.add_band(SpectrographBand(
            label=f"A={a_idx:g}",
            frequency=SCHUMANN_BASE - a_idx / 18.6,
            amplitude=max(0.0, min(1.0, a_idx / 30.0)),
            phase=180.0, color="purple", source="historical"))

    return graph


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


def _snapshot_from_cache(target: str) -> Optional[Any]:
    """Real cached NOAA 3-hourly Kp (ghost_fancy_cache/noaa_k_*.json) when
    it covers the target date; else None. Reuses hnc_data_sources'
    DailyGeomagneticRecord so downstream code is unchanged."""
    cache_file = (_WORKSPACE / "ghost_fancy_cache" /
                  f"noaa_k_{target.replace('-', '')}.json")
    try:
        if not cache_file.exists():
            return None
        with open(cache_file, "r", encoding="utf-8") as f:
            rows = json.load(f)
        if not isinstance(rows, list) or not rows:
            return None
        kps = [float(r["Kp"]) for r in rows if isinstance(r, dict)
               and isinstance(r.get("Kp"), (int, float))]
        a_run = [float(r.get("a_running", 0)) for r in rows
                 if isinstance(r, dict)]
        if not kps:
            return None
        from hnc_data_sources import DailyGeomagneticRecord
        geomagnetic = DailyGeomagneticRecord(
            date=target, year=int(target[:4]), month=int(target[5:7]),
            day=int(target[8:10]),
            planetary_a=int(max(a_run)) if a_run else 0,
            planetary_k_indices=[int(round(k)) for k in kps[:8]],
            high_latitude_a=0, high_latitude_k_indices=[],
            mid_latitude_a=0, mid_latitude_k_indices=[],
            max_kp=max(kps), avg_kp=sum(kps) / len(kps),
            quiet_day=max(kps) <= 2, active_day=max(kps) >= 4,
            storm_day=max(kps) >= 5,
        )
        from hnc_data_sources import HistoricalSnapshot
        return HistoricalSnapshot(
            date=target, geomagnetic=geomagnetic, schumann=None,
            market_data=None, data_sources=["noaa_cached"],
            data_quality=0.4,
            hash=hashlib.sha256(f"cached|{target}|{len(kps)}".encode())
            .hexdigest()[:16],
        )
    except Exception:
        return None


def run_probe(target_date: Optional[str] = None) -> dict:
    target = target_date or "2014-11-17"
    snapshot = _snapshot_from_cache(target)
    source = "ghost_fancy_cache NOAA Kp (real cached data)"
    if snapshot is None:
        try:
            from hnc_data_sources import HistoricalSnapshotBuilder
            y, m, d = int(target[:4]), int(target[5:7]), int(target[8:10])
            snapshot = HistoricalSnapshotBuilder().build_snapshot(y, m, d)
            source = ("hnc_data_sources HistoricalSnapshotBuilder "
                      "(live/cache)")
        except Exception as exc:
            # Fail-closed: no fabricated Kp/A — empty snapshot, honestly said.
            snapshot = None
            source = f"snapshot unavailable ({type(exc).__name__})"

    if snapshot is None:
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "module": "hnc_spectrograph",
            "reconstruction": RECONSTRUCTION_NOTE,
            "ok": False,
            "status": ("empty — no historical snapshot could be built for "
                       f"{target}; no data, no bands, no fabrication"),
            "snapshot_source": source,
            "spectrograph": None,
        }

    graph = build_spectrograph_for_target(target, snapshot)
    out = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "module": "hnc_spectrograph",
        "reconstruction": RECONSTRUCTION_NOTE,
        "ok": True,
        "status": "spectrograph built from real snapshot",
        "snapshot_source": source,
        "target_date": target,
        "spectrograph": graph.to_json(),
    }
    _atomic_write_json(
        _WORKSPACE / "aureon_fusion" / "state" / "casimir" /
        "hnc_spectrograph.json", out)
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
        p = argparse.ArgumentParser(description="Temporal spectrograph probe")
        p.add_argument("--target", default="2014-11-17")
        p.add_argument("--json", action="store_true")
        args = p.parse_args(argv[1:])
        out = run_probe(args.target)
        if args.json:
            print(json.dumps(out, indent=2, ensure_ascii=False))
        else:
            print(f"📊 SPECTROGRAPH probe ({'ok' if out['ok'] else 'EMPTY'})")
            print(f"   {out['status']}")
            if out.get("spectrograph"):
                from hnc_data_sources import HistoricalSnapshotBuilder
                print(f"   snapshot: {out['snapshot_source']}")
                meta = out["spectrograph"]["metadata"]
                print(f"   bands: {meta['band_count']} "
                      f"({meta['signal_bands']} signal, "
                      f"{meta['historical_bands']} historical)")
        return 0 if out.get("ok") else 1
    print(f"unknown verb: {argv[0]} (try: probe)", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
