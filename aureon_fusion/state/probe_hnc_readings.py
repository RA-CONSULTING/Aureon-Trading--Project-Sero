"""Offline verification probes for the HNC SENSOR LAYER
(hnc_core.gather_readings — BUILD-CORE deliverable, SCOPE A).

Every scenario runs against a TEMP state slice: the sensor files
(real_time_data.json, knowledge_pulse.json, planetary_signals.jsonl) are
redirected per scenario via module-constant seams on hnc_core, and the
LambdaEngine instances used for the Γ arithmetic live entirely in temp
state paths. NOTHING here touches the live organism: no organ restart, no
events-spine publish, no SQLite memory write, zero network, zero writes
outside the temp dirs.

Physics under test (verified against the live engine upstream):
Γ = 1 - σ/μ over raw reading VALUES only — confidence never enters Γ.
The existing cluster sits at ~0.35-0.45, so the new sensors (quakes,
knowledge_pulse, planetary) are normalized to anchor near 0.40: agreeing
inputs raise Γ, divergent ones lower it honestly.

Probes (fail-closed paths exercised, not just happy paths):
  1. BUGWATCH-4 — kp entry aged ~200 s on the ~300 s source cadence is
     HEALTHY (full confidence, not stale); aged ~700 s is stale (degraded
     confidence, honest meta flag). Values never altered by staleness.
  2. quakes probe — count field read; list-payload fallback; malformed
     shapes (string, count-free dict, null) contribute NO reading and
     never raise.
  3. knowledge_pulse probe — missing file = no reading (fail-closed);
     fresh pulse 0.5 lands at the 0.40 cluster anchor at full confidence;
     stale pulse is degraded (0.3) and honestly meta-labelled.
  4. planetary probe — fresh jsonl yields an activity reading anchored
     near 0.40; missing file contributes nothing; unparseable lines are
     skipped without raising.
  5. Γ arithmetic — on a gathered baseline cluster: a MATCHING extra
     reading raises Γ; a DIVERGENT extra reading lowers Γ.

Exit codes: 0 = all probes pass; 1 = at least one failed.
Usage:  python aureon_fusion/state/probe_hnc_readings.py [-v]
"""

import contextlib
import json
import math
import os
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

os.environ.setdefault("AUREON_SUPPRESS_IMPORT_SIDE_EFFECTS", "1")
os.environ.setdefault("AUREON_AUDIT_MODE", "1")

WORKSPACE = Path(__file__).resolve().parents[2]
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

import aureon_fusion.hnc_core as hnc

_results = []


def log(msg):
    print(msg)


def check(name, cond, detail=""):
    ok = bool(cond)
    _results.append((name, ok))
    mark = "PASS" if ok else "FAIL"
    log(f"  [{mark}] {name}" + (f" — {detail}" if detail and not ok else ""))
    return ok


# ───────────────────────── fixture helpers ─────────────────────────────────

def iso(age_s: float = 0.0) -> str:
    return (datetime.now(timezone.utc) - timedelta(seconds=age_s)).isoformat()


def live_fixture(kp_age_s=30.0, quakes="OMIT", kp_est=3.6):
    """A real_time_data.json shaped like the live feeder file. `quakes` may
    be "OMIT" (no key), a dict (used as-is), or any other value (written
    verbatim to prove defensiveness)."""
    summary = {
        "kp": {"timestamp": iso(kp_age_s), "kp_index": int(kp_est),
               "estimated_kp": kp_est, "kp": "quiet"},
        "solar_wind": {"time_tag": iso(30.0), "density": 5.0, "speed": 420.0,
                       "temperature": 100000},
        "xray": {"time_tag": iso(30.0), "flux": 2.5e-8, "energy": "0.1-0.8nm"},
    }
    if quakes != "OMIT":
        summary["quakes"] = quakes
    return {"timestamp": iso(30.0), "source": "fixture", "summary": summary}


class Harness:
    """Per-scenario temp state + module seams."""

    PATH_ATTRS = ("LIVE_DATA_PATH", "SCHUMANN_STATE_PATH", "RADAR_SIGNALS_PATH",
                  "PLANETARY_SIGNALS_PATH", "KNOWLEDGE_PULSE_PATH")

    def __init__(self, name):
        self.name = name
        self.tmp = Path(tempfile.mkdtemp(prefix=f"hnc_probe_{name}_"))
        self.live_file = self.tmp / "real_time_data.json"
        self.knowledge_pulse_file = self.tmp / "knowledge_pulse.json"
        self.planetary_file = self.tmp / "planetary_signals.jsonl"
        self._patches = []

    def patch_paths(self):
        self.patch(hnc, "LIVE_DATA_PATH", self.live_file)
        self.patch(hnc, "SCHUMANN_STATE_PATH", self.tmp / "schumann_state.json")
        self.patch(hnc, "RADAR_SIGNALS_PATH", self.tmp / "fused_signals.jsonl")
        self.patch(hnc, "PLANETARY_SIGNALS_PATH", self.planetary_file)
        self.patch(hnc, "KNOWLEDGE_PULSE_PATH", self.knowledge_pulse_file)

    def patch(self, obj, attr, value):
        old = getattr(obj, attr, None)
        setattr(obj, attr, value)
        self._patches.append((obj, attr, old))

    def write_live(self, doc):
        self.live_file.write_text(json.dumps(doc), encoding="utf-8")

    def write_pulse(self, doc):
        self.knowledge_pulse_file.write_text(json.dumps(doc), encoding="utf-8")

    def write_planetary(self, docs):
        self.planetary_file.write_text(
            "".join(json.dumps(d) + "\n" for d in docs), encoding="utf-8")

    def restore(self):
        for obj, attr, old in reversed(self._patches):
            setattr(obj, attr, old)
        self._patches.clear()


@contextlib.contextmanager
def temp_engine():
    """A LambdaEngine whose entire state lives in a temp dir."""
    from aureon.core.aureon_lambda_engine import LambdaEngine

    tmp = Path(tempfile.mkdtemp(prefix=f"hnc_probe_engine_"))
    engine = LambdaEngine(state_path=tmp / "lambda_history.json")
    try:
        yield engine
    finally:
        try:
            engine.save_history(source_receipt_ids=("probe:hnc_readings",))
        except Exception:
            pass


def gamma_of(engine, readings):
    return engine.step(readings=readings, auto_persist=False).coherence_gamma


# ───────────────────────── probes ──────────────────────────────────────────

def probe_bugwatch4_stale_windows():
    log("\n== 1. BUGWATCH-4: per-source staleness windows (kp) ==")
    h = Harness("bugwatch4")
    try:
        h.patch_paths()
        # ~200 s old: healthy on the ~300 s source cadence, used to be
        # mis-marked stale by the 2x60 s = 120 s file-level window.
        h.write_live(live_fixture(kp_age_s=200.0))
        readings, meta = hnc.gather_readings()
        kp = next((r for r in readings if r.name == "kp_index"), None)
        check("kp reading present", kp is not None)
        check("200 s kp data is HEALTHY (full confidence 0.85)",
              kp is not None and kp.confidence == 0.85,
              f"confidence={getattr(kp, 'confidence', None)}")
        check("200 s kp data not meta-flagged stale",
              "kp_stale" not in meta, str(meta))
        check("staleness never alters the value",
              kp is not None and abs(kp.value - 3.6 / 9.0) < 1e-9,
              f"value={getattr(kp, 'value', None)}")

        # ~700 s old: genuinely stale — degraded confidence, honest meta.
        h.write_live(live_fixture(kp_age_s=700.0))
        readings, meta = hnc.gather_readings()
        kp = next((r for r in readings if r.name == "kp_index"), None)
        check("700 s kp data degraded (confidence 0.425)",
              kp is not None and kp.confidence == 0.425,
              f"confidence={getattr(kp, 'confidence', None)}")
        check("700 s kp data meta-flagged stale",
              meta.get("kp_stale") is True, str(meta))
        check("stale kp value still honest",
              kp is not None and abs(kp.value - 3.6 / 9.0) < 1e-9,
              f"value={getattr(kp, 'value', None)}")
    finally:
        h.restore()


def probe_quakes():
    log("\n== 2. quakes probe (defensive shapes) ==")
    h = Harness("quakes")
    try:
        h.patch_paths()

        h.write_live(live_fixture(quakes={"count": 8, "latest": None}))
        readings, meta = hnc.gather_readings()
        q = next((r for r in readings if r.name == "seismic_quakes"), None)
        check("count=8 yields a reading anchored at 0.40",
              q is not None and abs(q.value - 0.40) < 1e-9,
              f"value={getattr(q, 'value', None)}")
        check("fresh quakes at full confidence 0.6",
              q is not None and q.confidence == 0.6,
              f"confidence={getattr(q, 'confidence', None)}")
        check("quake count in meta", meta.get("quake_count") == 8, str(meta))

        h.write_live(live_fixture(quakes={"count": 30}))
        readings, _ = hnc.gather_readings()
        q = next((r for r in readings if r.name == "seismic_quakes"), None)
        expect = hnc._clamp01(0.40 + 0.10 * math.tanh((30 - 8) / 6))
        check("count=30 follows the tanh normalization",
              q is not None and abs(q.value - expect) < 1e-9,
              f"value={getattr(q, 'value', None)} expect≈{expect:.4f}")

        # list-payload fallback
        h.write_live(live_fixture(
            quakes={"features": [{"id": 1}, {"id": 2}, {"id": 3}]}))
        readings, meta = hnc.gather_readings()
        q = next((r for r in readings if r.name == "seismic_quakes"), None)
        check("list payload falls back to len() (3 quakes)",
              q is not None and meta.get("quake_count") == 3,
              str(meta))

        # malformed shapes: no reading, no raise
        for label, bad in (("string entry", "boom"),
                           ("count-free dict", {"latest": None}),
                           ("null entry", None),
                           ("numeric entry", 7)):
            h.write_live(live_fixture(quakes=bad))
            try:
                readings, _ = hnc.gather_readings()
                absent = all(r.name != "seismic_quakes" for r in readings)
            except Exception as exc:  # noqa: BLE001  (probe: any raise fails)
                absent = False
                log(f"       ({label} raised: {exc!r})")
            check(f"malformed quakes ({label}) -> no reading, no raise",
                  absent)

        # missing key entirely
        h.write_live(live_fixture(quakes="OMIT"))
        readings, _ = hnc.gather_readings()
        check("missing quakes key -> no reading",
              all(r.name != "seismic_quakes" for r in readings))
    finally:
        h.restore()


def probe_knowledge_pulse():
    log("\n== 3. knowledge_pulse probe (fail-closed) ==")
    h = Harness("pulse")
    try:
        h.patch_paths()
        h.write_live(live_fixture(quakes={"count": 8}))

        # missing file = no reading (fail-closed)
        readings, meta = hnc.gather_readings()
        check("missing knowledge_pulse.json -> no reading",
              all(r.name != "knowledge_pulse" for r in readings))

        # fresh pulse 0.5 -> 0.40 cluster anchor, full confidence
        h.write_pulse({"timestamp": iso(10.0), "pulse": 0.5,
                       "components": {"journal": 0.5}})
        readings, meta = hnc.gather_readings()
        p = next((r for r in readings if r.name == "knowledge_pulse"), None)
        check("fresh pulse 0.5 lands at the 0.40 anchor",
              p is not None and abs(p.value - 0.40) < 1e-9,
              f"value={getattr(p, 'value', None)}")
        check("fresh pulse at full confidence 0.65",
              p is not None and p.confidence == 0.65,
              f"confidence={getattr(p, 'confidence', None)}")
        check("pulse in meta, not flagged stale",
              meta.get("knowledge_pulse") == 0.5
              and "knowledge_pulse_stale" not in meta, str(meta))

        # deviation moves the value honestly
        h.write_pulse({"timestamp": iso(10.0), "pulse": 1.0, "components": {}})
        readings, _ = hnc.gather_readings()
        p = next((r for r in readings if r.name == "knowledge_pulse"), None)
        check("pulse 1.0 -> 0.46 (honest upward deviation)",
              p is not None and abs(p.value - 0.46) < 1e-9,
              f"value={getattr(p, 'value', None)}")

        # stale pulse: degraded confidence, honest meta, value untouched
        h.write_pulse({"timestamp": iso(600.0), "pulse": 0.5, "components": {}})
        readings, meta = hnc.gather_readings()
        p = next((r for r in readings if r.name == "knowledge_pulse"), None)
        check("stale pulse degraded to 0.3",
              p is not None and p.confidence == 0.3,
              f"confidence={getattr(p, 'confidence', None)}")
        check("stale pulse value still honest (0.40)",
              p is not None and abs(p.value - 0.40) < 1e-9,
              f"value={getattr(p, 'value', None)}")
        check("stale pulse meta-flagged",
              meta.get("knowledge_pulse_stale") is True, str(meta))

        # malformed file = no reading
        h.knowledge_pulse_file.write_text("{not json", encoding="utf-8")
        readings, _ = hnc.gather_readings()
        check("corrupt knowledge_pulse.json -> no reading",
              all(r.name != "knowledge_pulse" for r in readings))
    finally:
        h.restore()


def probe_planetary():
    log("\n== 4. planetary probe (freshness-gated) ==")
    h = Harness("planetary")
    try:
        h.patch_paths()
        h.write_live(live_fixture(quakes={"count": 8}))

        # missing file = no reading
        readings, meta = hnc.gather_readings()
        check("missing planetary_signals.jsonl -> no reading",
              all(r.name != "planetary_band" for r in readings))

        # 5 fresh signals in the last hour -> anchored at 0.40
        docs = [{"timestamp": iso(60.0 * i), "signal": f"sig-{i}", "strength": 0.7}
                for i in range(5)]
        h.write_planetary(docs)
        readings, meta = hnc.gather_readings()
        p = next((r for r in readings if r.name == "planetary_band"), None)
        check("5 fresh signals anchor at 0.40",
              p is not None and abs(p.value - 0.40) < 1e-9,
              f"value={getattr(p, 'value', None)}")
        check("fresh planetary at full confidence 0.55",
              p is not None and p.confidence == 0.55,
              f"confidence={getattr(p, 'confidence', None)}")
        check("hour-count in meta",
              meta.get("planetary_signals_hour") == 5, str(meta))

        # 20 fresh signals -> tanh normalization above the anchor
        docs = [{"timestamp": iso(30.0 * i), "signal": f"sig-{i}"}
                for i in range(20)]
        h.write_planetary(docs)
        readings, meta = hnc.gather_readings()
        p = next((r for r in readings if r.name == "planetary_band"), None)
        expect = hnc._clamp01(0.40 + 0.10 * math.tanh((20 - 5) / 4))
        check("20 signals follow the tanh normalization",
              p is not None and abs(p.value - expect) < 1e-9,
              f"value={getattr(p, 'value', None)} expect≈{expect:.4f}")

        # stale last line (mtime fallback will also be old after rewrite):
        # degrade confidence, flag meta, keep value honest
        docs = [{"timestamp": iso(5000.0), "signal": "old"}]
        h.write_planetary(docs)
        readings, meta = hnc.gather_readings()
        p = next((r for r in readings if r.name == "planetary_band"), None)
        check("stale planetary degraded to 0.25",
              p is not None and p.confidence == 0.25,
              f"confidence={getattr(p, 'confidence', None)}")
        check("stale planetary meta-flagged",
              meta.get("planetary_stale") is True, str(meta))

        # unparseable lines skipped without raising
        h.planetary_file.write_text("not json\n{bad\n" + json.dumps(
            {"timestamp": iso(10.0)}) + "\n", encoding="utf-8")
        try:
            readings, _ = hnc.gather_readings()
            ok = True
        except Exception as exc:  # noqa: BLE001
            ok = False
            log(f"       (planetary malformed raised: {exc!r})")
        check("unparseable lines -> no raise", ok)
    finally:
        h.restore()


def probe_gamma_arithmetic():
    log("\n== 5. Γ arithmetic: matching raises, divergent lowers ==")
    h = Harness("gamma")
    try:
        h.patch_paths()
        # A quiet, median world: every sensor sits in the 0.35-0.45 band.
        h.write_live(live_fixture(quakes={"count": 8}))
        h.write_pulse({"timestamp": iso(10.0), "pulse": 0.5, "components": {}})
        h.write_planetary([{"timestamp": iso(60.0 * i)} for i in range(5)])
        base_readings, _ = hnc.gather_readings()
        check("baseline gathers the full agreeing cluster (>= 5 readings)",
              len(base_readings) >= 5, f"got {len(base_readings)}")

        from aureon.core.aureon_lambda_engine import SubsystemReading

        mu = sum(r.value for r in base_readings) / len(base_readings)
        matching = SubsystemReading(name="probe_matching", value=mu,
                                    confidence=0.5, state="at cluster mean")
        divergent = SubsystemReading(name="probe_divergent", value=0.95,
                                     confidence=0.5, state="far from cluster")

        with temp_engine() as engine:
            gamma_base = gamma_of(engine, list(base_readings))
            gamma_match = gamma_of(engine, list(base_readings) + [matching])
            gamma_div = gamma_of(engine, list(base_readings) + [divergent])

        check(f"baseline Γ computed ({gamma_base:.4f})", math.isfinite(gamma_base))
        check("matching reading RAISES Γ vs baseline",
              gamma_match > gamma_base,
              f"match={gamma_match:.4f} base={gamma_base:.4f}")
        check("divergent reading LOWERS Γ vs baseline",
              gamma_div < gamma_base,
              f"div={gamma_div:.4f} base={gamma_base:.4f}")
    finally:
        h.restore()


# ───────────────────────── runner ──────────────────────────────────────────

def main(argv=None):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    log("=" * 72)
    log("HNC SENSOR LAYER — offline probes (gather_readings + Γ arithmetic)")
    log("=" * 72)

    probe_bugwatch4_stale_windows()
    probe_quakes()
    probe_knowledge_pulse()
    probe_planetary()
    probe_gamma_arithmetic()

    passed = sum(1 for _, ok in _results if ok)
    total = len(_results)
    log("\n" + "=" * 72)
    log(f"RESULT: {passed}/{total} probes passed")
    if passed != total:
        log("FAILURES:")
        for name, ok in _results:
            if not ok:
                log(f"  - {name}")
    log("=" * 72)
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
