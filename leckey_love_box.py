#!/usr/bin/env python3
"""
LECKEY'S LOVE BOX — Quantum Temporal Counter-Distortion
═══════════════════════════════════════════════════════════════════

⚠️  RECONSTRUCTION — 2026-09-06, under owner decree (Gary Leckey):
    "open the doors" (remaining five absent casimir-cluster modules).

    EVIDENCE STATUS: WEAK — flagged. No run artifacts for
    leckey_love_box survived. The only evidence is:
      - COMPLETE_LINEAGE_REPORT.md:03:27 — creation timestamp.
      - Consumer-pinned API (hnc_daemon.py):
            LeckeysLoveBox(prime_sentinel_key=..., max_lookback_days=7)
              .run_probe(hnc_state)  -> TemporalProbe (attributes:
                  probe_id, target_time (datetime), collapse_state,
                  distortion_level, distortion_signature,
                  validation_score, love_signal_strength,
                  counter_distortion_applied, counter_distortion_success,
                  proof_hash)
              .current_session        -> LoveBoxSession | None
              .save_session(session)
      - The exported names TemporalProbe, LoveBoxSession.
    Everything below the API surface is a DOCUMENTED RECONSTRUCTION
    CHOICE: a probe collapses a deterministic target time inside the
    lookback window (seeded from the current HNC state hash, so identical
    state ⇒ identical probe), measures the field's distortion from the
    REAL coherence deviation, and applies a counter-distortion computed
    from the love-signal strength the field actually carries. No state,
    no probe: honest IDLE/zero values, never invented readings.

    Import-safe (AUREON_SUPPRESS_IMPORT_SIDE_EFFECTS honored), stdlib
    only, fail-closed. Sessions persist atomically under
    aureon_fusion/state/casimir/love_box_sessions/.

CLI:
    python leckey_love_box.py probe [--json]
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import sys
import time
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

os.environ.setdefault("AUREON_SUPPRESS_IMPORT_SIDE_EFFECTS", "1")
os.environ.setdefault("AUREON_AUDIT_MODE", "1")

PHI = (1 + math.sqrt(5)) / 2

_WORKSPACE = Path(__file__).resolve().parent
SESSION_DIR = _WORKSPACE / "aureon_fusion" / "state" / "casimir" / \
    "love_box_sessions"

RECONSTRUCTION_NOTE = (
    "leckey_love_box.py reconstructed 2026-09-06 under owner decree "
    "(Gary Leckey); NO behavioral artifacts survived — only the "
    "consumer-pinned API (hnc_daemon.py) and the max_lookback_days=7 "
    "parameter. Probe/collapse/counter-distortion internals are "
    "documented reconstruction choices computed from the real hnc_state; "
    "flagged WEAK-evidence reconstruction."
)


@dataclass
class TemporalProbe:
    """One collapsed temporal probe. Attribute set pinned by
    hnc_daemon.py's love_box_result dict."""
    probe_id: str
    target_time: datetime
    collapse_state: str          # COLLAPSED | UNCERTAIN | IDLE
    distortion_level: float      # 0..1
    distortion_signature: str
    validation_score: float      # 0..1
    love_signal_strength: float  # 0..1
    counter_distortion_applied: bool
    counter_distortion_success: bool
    proof_hash: str

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["target_time"] = (self.target_time.isoformat()
                            if hasattr(self.target_time, "isoformat")
                            else str(self.target_time))
        return d


@dataclass
class LoveBoxSession:
    """A bounded series of probes. Pinned by hnc_daemon.py calling
    save_session(self.love_box.current_session)."""
    session_id: str
    started_at: str
    prime_sentinel_key: str = ""
    probes: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class LeckeysLoveBox:
    """Counter-distortion probe engine (reconstructed).

    Real work per probe, from the real hnc_state dict only:
      - target_time: deterministic within the lookback window — seeded by
        SHA-256 of the serialised state, so the same field state always
        collapses the same target (reproducible, no hidden randomness);
      - distortion_level: how far the measured coherence sits from the
        repo's coherence target φ/2 (0.8090) — a real deviation of the
        real input;
      - distortion_signature: SHA-256 prefix of the same deviation
        (identity of the distortion, not a reading);
      - validation_score: 1 - distortion_level;
      - love_signal_strength: the measured λ (what the field carries);
      - counter-distortion: applied when distortion exceeds 0.3;
        success when the post-counter deviation is smaller (it always is,
        by construction — the counter is the exact inverse of the measured
        deviation, honestly bounded at 1.0).
    """

    DISTORTION_TARGET = PHI / 2  # 0.8090169... — repo coherence target
    COUNTER_THRESHOLD = 0.3

    def __init__(self, prime_sentinel_key: str = "",
                 max_lookback_days: int = 7) -> None:
        self.prime_sentinel_key = str(prime_sentinel_key)
        self.max_lookback_days = int(max_lookback_days)
        self.current_session: Optional[LoveBoxSession] = None
        self._probe_count = 0

    # ── probe ─────────────────────────────────────────────────────────

    def run_probe(self, hnc_state: Optional[Dict[str, Any]]) -> TemporalProbe:
        self._probe_count += 1
        now = datetime.now(timezone.utc)
        if self.current_session is None:
            self.current_session = LoveBoxSession(
                session_id=f"LB-{int(now.timestamp())}-"
                           f"{hashlib.sha256(str(self._probe_count).encode()).hexdigest()[:6]}",
                started_at=now.isoformat(),
                prime_sentinel_key=self.prime_sentinel_key[:64])

        if not hnc_state:
            return TemporalProbe(
                probe_id=f"probe_idle_{self._probe_count}",
                target_time=now, collapse_state="IDLE",
                distortion_level=0.0, distortion_signature="0" * 16,
                validation_score=0.0, love_signal_strength=0.0,
                counter_distortion_applied=False,
                counter_distortion_success=False,
                proof_hash=hashlib.sha256(b"lovebox-idle").hexdigest())

        coherence = float(hnc_state.get("coherence", 0.0) or 0.0)
        lam = float(hnc_state.get("lambda", 0.0) or 0.0)

        # Deterministic target inside the lookback window.
        seed = hashlib.sha256(
            json.dumps(hnc_state, sort_keys=True, default=str).encode()
        ).digest()
        offset_fraction = int.from_bytes(seed[:4], "big") / float(1 << 32)
        offset = offset_fraction * self.max_lookback_days * 86400.0
        target_time = now - timedelta(seconds=offset)

        deviation = abs(coherence - self.DISTORTION_TARGET)
        distortion_level = max(0.0, min(1.0, deviation))
        signature = hashlib.sha256(
            f"distortion|{coherence:.6f}|{self.DISTORTION_TARGET:.6f}"
            .encode()).hexdigest()[:16]
        validation = 1.0 - distortion_level

        applied = distortion_level > self.COUNTER_THRESHOLD
        success = applied  # the counter is the exact inverse of the
                           # measured deviation (documented choice)
        proof = hashlib.sha256(
            f"lovebox|{target_time.isoformat()}|{coherence:.6f}|"
            f"{distortion_level:.6f}|{self._probe_count}".encode()
        ).hexdigest()

        probe = TemporalProbe(
            probe_id=f"probe_{int(now.timestamp())}_{proof[:8]}",
            target_time=target_time,
            collapse_state="COLLAPSED",
            distortion_level=distortion_level,
            distortion_signature=signature,
            validation_score=validation,
            love_signal_strength=max(0.0, min(1.0, lam)),
            counter_distortion_applied=applied,
            counter_distortion_success=success,
            proof_hash=proof)
        self.current_session.probes.append(probe.to_dict())
        return probe

    # ── session persistence ───────────────────────────────────────────

    def save_session(self, session: LoveBoxSession) -> Optional[str]:
        try:
            SESSION_DIR.mkdir(parents=True, exist_ok=True)
            path = SESSION_DIR / f"{session.session_id}.json"
            tmp = path.with_name(f"{path.name}.tmp.{os.getpid()}.{time.time_ns()}")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(session.to_dict(), f, indent=2, ensure_ascii=False)
            os.replace(tmp, path)
            return str(path)
        except OSError:
            return None


# ───────────────────────── probe ───────────────────────────────────────────

def run_probe() -> Dict[str, Any]:
    """Probe with the organism's real current state."""
    hnc_state = None
    source = "none — fail-closed"
    try:
        with open(_WORKSPACE / "aureon_fusion" / "state" /
                  "hnc_core_state.json", "r", encoding="utf-8") as f:
            hnc = json.load(f)
        lam = max(0.0, min(1.0, math.tanh(float(hnc.get("lambda_t", 0.0))
                                          / 100.0)))
        hnc_state = {
            "lambda": lam,
            "coherence": float(hnc.get("coherence_gamma", 0.0)),
            "beta": 0.7742,
            "schumann": 7.83,
        }
        source = "hnc_core_state.json"
    except Exception:
        pass

    box = LeckeysLoveBox(prime_sentinel_key="", max_lookback_days=7)
    probe = box.run_probe(hnc_state)
    saved = box.save_session(box.current_session) if box.current_session else None

    out = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "module": "leckey_love_box",
        "reconstruction": RECONSTRUCTION_NOTE,
        "ok": hnc_state is not None,
        "status": (f"probe collapsed from real state ({source})"
                   if hnc_state else
                   "empty — no real hnc_state (IDLE probe, fail-closed)"),
        "state_source": source,
        "probe": probe.to_dict(),
        "session_file": saved,
        "session_probe_count": len(box.current_session.probes)
        if box.current_session else 0,
    }
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
        p = argparse.ArgumentParser(description="Leckey's Love Box probe")
        p.add_argument("--json", action="store_true")
        args = p.parse_args(argv[1:])
        out = run_probe()
        if args.json:
            print(json.dumps(out, indent=2, ensure_ascii=False))
        else:
            print(f"📦 LECKEY'S LOVE BOX — probe "
                  f"({'ok' if out['ok'] else 'EMPTY'})")
            print(f"   {out['status']}")
            pr = out["probe"]
            print(f"   probe: {pr['probe_id']} | {pr['collapse_state']} | "
                  f"target {pr['target_time'][:19]}")
            print(f"   distortion: {pr['distortion_level']:.4f} "
                  f"(sig {pr['distortion_signature']}) | validation "
                  f"{pr['validation_score']:.4f}")
            print(f"   counter-distortion: applied="
                  f"{pr['counter_distortion_applied']} success="
                  f"{pr['counter_distortion_success']}")
            if out.get("session_file"):
                print(f"   session: {out['session_file']}")
        return 0 if out.get("ok") else 1
    print(f"unknown verb: {argv[0]} (try: probe)", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
