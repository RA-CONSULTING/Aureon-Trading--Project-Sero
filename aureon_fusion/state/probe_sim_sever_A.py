#!/usr/bin/env python3
"""Offline fail-closed probes for SIM-SEVER-A.

Forces every failure path (bad URL/key/absent device/no live source) and
asserts that no fabricated value is ever produced untagged. Run with:
  AUREON_SUPPRESS_IMPORT_SIDE_EFFECTS=1 AUREON_AUDIT_MODE=1
"""
import importlib
import json
import os
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

WS = Path(os.environ["PROBE_WORKSPACE"])
sys.path.insert(0, str(WS))
os.chdir(os.environ["PROBE_CWD"])  # temp workspace — relative files land here

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

RESULTS = []


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond), detail))
    print(f"{'PASS' if cond else 'FAIL'} | {name} | {detail}")


def fresh_env():
    os.environ.pop("AUREON_ALLOW_SIM_FALLBACK", None)
    os.environ.pop("AUREON_RUNTIME_PROFILE", None)
    os.environ.pop("PYTEST_CURRENT_TEST", None)


def allow_sim():
    os.environ["AUREON_ALLOW_SIM_FALLBACK"] = "1"
    os.environ["AUREON_RUNTIME_PROFILE"] = "test"


# ─── 1. signal_monitor ──────────────────────────────────────────────────────
fresh_env()
import signal_monitor

mon = signal_monitor.SignalMonitor(log_path=str(Path(os.environ["PROBE_CWD"]) / "sm_log.jsonl"))
# Force the "no live source" path: no sensor_state.json in the temp cwd and
# no Schumann bridge (the real bridge may reach live network in this probe).
mon.schumann_bridge = None
r = mon._get_schumann()
check("signal_monitor._get_schumann default None", r is None, f"got {r!r}")
m = mon.measure()
check("signal_monitor.measure default None", m is None)

allow_sim()
mon2 = signal_monitor.SignalMonitor(log_path=str(Path(os.environ["PROBE_CWD"]) / "sm_log2.jsonl"))
mon2.schumann_bridge = None
r = mon2._get_schumann()
check("signal_monitor sim allowed tagged",
      r is not None and r.get("source") == "simulation" and r.get("simulation") is True,
      f"source={r and r.get('source')}, simulation={r and r.get('simulation')}")
fresh_env()

# ─── 2. hnc_lightweight_daemon ──────────────────────────────────────────────
import hnc_lightweight_daemon as hld

tmp = Path(os.environ["PROBE_CWD"])
hld.PID_FILE = tmp / "hnc_daemon.pid"
hld.STATE_FILE = tmp / "hnc_state.json"
hld.LOG_FILE = tmp / "hnc_daemon.log"

# 2a. all fetchers fail -> no state write at all
hld.fetch_kp = lambda: None
hld.fetch_schumann = lambda: None
hld.fetch_quakes = lambda: None
real_sleep = hld.time.sleep

def stop_after_first(_s):
    hld.running = False

hld.time.sleep = stop_after_first
hld.STATE_FILE.unlink(missing_ok=True)
hld.main()
hld.time.sleep = real_sleep
check("lightweight_daemon no write on total fetch failure",
      not hld.STATE_FILE.exists(),
      f"state file exists: {hld.STATE_FILE.exists()}")
log_txt = hld.LOG_FILE.read_text() if hld.LOG_FILE.exists() else ""
check("lightweight_daemon fail-closed logged",
      "fail-closed" in log_txt, log_txt.strip().splitlines()[-1] if log_txt.strip() else "no log")

# 2b. schumann response missing frequency -> treated unavailable, no 7.83 default
hld.fetch_kp = lambda: {"time_tag": "2026-01-01T00:00Z", "kp": 3.0}
hld.fetch_schumann = lambda: {"activity_index": 40}  # no schumann_frequency_hz
hld.running = True
hld.time.sleep = stop_after_first
hld.STATE_FILE.unlink(missing_ok=True)
hld.main()
hld.time.sleep = real_sleep
check("lightweight_daemon missing freq -> no fabricated 7.83 write",
      not hld.STATE_FILE.exists())

# 2c. full live data -> write with real_data true; quake failure -> quakes None
hld.fetch_schumann = lambda: {"schumann_frequency_hz": 7.91, "activity_index": 40}
hld.fetch_quakes = lambda: None
hld.running = True
hld.time.sleep = stop_after_first
hld.STATE_FILE.unlink(missing_ok=True)
hld.main()
hld.time.sleep = real_sleep
state = json.loads(hld.STATE_FILE.read_text()) if hld.STATE_FILE.exists() else {}
check("lightweight_daemon live write real_data=true",
      state.get("real_data") is True and state.get("simulation") is False
      and state.get("schumann_hz") == 7.91 and state.get("kp") == 3.0,
      f"schumann_hz={state.get('schumann_hz')}")
check("lightweight_daemon quake failure -> quakes_1hr None, not invented 0",
      state.get("quakes_1hr") is None and state.get("quakes_available") is False,
      f"quakes_1hr={state.get('quakes_1hr')}")

# ─── 3. schumann_real_daemon ────────────────────────────────────────────────
import schumann_real_daemon as srd

srd.PID_FILE = tmp / "schumann_sensor.pid"
srd.STATE_FILE = tmp / "schumann_state.json"
srd.LOG_FILE = tmp / "schumann_sensor.log"

# 3a. response missing frequency (bad key) -> skip write, no 7.83 default
srd.fetch = lambda: {"error": "unauthorized"}  # missing/invalid API key shape
real_sleep = srd.time.sleep
srd.time.sleep = lambda _s: setattr(srd, "running", False)
srd.STATE_FILE.unlink(missing_ok=True)
srd.main()
srd.time.sleep = real_sleep
check("schumann_real_daemon missing key/freq -> no write, no 7.83 default",
      not srd.STATE_FILE.exists())

# 3b. fetch failure -> no write
srd.fetch = lambda: None
srd.running = True
srd.time.sleep = lambda _s: setattr(srd, "running", False)
srd.STATE_FILE.unlink(missing_ok=True)
srd.main()
srd.time.sleep = real_sleep
check("schumann_real_daemon fetch failure -> no write",
      not srd.STATE_FILE.exists())

# 3c. live data -> write real_data true with measured freq
srd.fetch = lambda: {"schumann_frequency_hz": 7.85, "activity_index": 55}
srd.running = True
srd.time.sleep = lambda _s: setattr(srd, "running", False)
srd.STATE_FILE.unlink(missing_ok=True)
srd.main()
srd.time.sleep = real_sleep
state = json.loads(srd.STATE_FILE.read_text()) if srd.STATE_FILE.exists() else {}
check("schumann_real_daemon live write measured freq",
      state.get("real_data") is True and state.get("frequency_hz") == 7.85,
      f"frequency_hz={state.get('frequency_hz')}")

# ─── 4. sero_schumann_feel ──────────────────────────────────────────────────
import sero_schumann_feel as ssf

ssf.FELT_LOG = tmp / "schumann_felt.jsonl"
ssf.FIELD_HISTORY = tmp / "field_history.json"
ssf.SENSORY_STATE = tmp / "sensory_state.json"

# 4a. synthesize_readings default -> None
fresh_env()
check("sero.synthesize_readings default None", ssf.synthesize_readings() is None)
allow_sim()
synth = ssf.synthesize_readings()
check("sero.synthesize_readings allowed -> tagged felt/synthesis",
      synth is not None and all("felt/synthesis" in r.source for r in synth))
fresh_env()

# 4b. cached reading with no activity_index -> amplitude unmeasured, no RNG
ts = datetime.now(timezone.utc).isoformat()
(tmp / "cache_state.json").write_text(json.dumps({
    "timestamp": ts, "frequency_hz": 7.9, "real_data": True}))
ssf.SCHUMANN_STATE = tmp / "cache_state.json"
cached = ssf.cached_schumann_reading()
check("sero.cached reading missing activity -> amplitude unmeasured, not RNG",
      cached is not None and cached.amplitude is None
      and cached.amplitude_source == "unmeasured",
      f"amplitude={cached and cached.amplitude}, src={cached and cached.amplitude_source}")

# 4c. cached entry missing frequency -> None (no 7.83 default)
(tmp / "cache_state.json").write_text(json.dumps({"timestamp": ts, "real_data": True}))
check("sero.cached missing freq -> None (no 7.83 default)",
      ssf.cached_schumann_reading() is None)

# 4d. live VLF parse path -> amplitude unmeasured (RNG removed)
ssf._http_get = lambda url, timeout=None, ttl_s=60: json.dumps({"schumann_frequency_hz": 7.88})
live = ssf.fetch_vlf_reading()
check("sero.fetch_vlf amplitude unmeasured (no RNG on live path)",
      live is not None and live.amplitude is None and live.amplitude_source == "unmeasured")

# 4e. take_reading with no live sources, default -> None
ssf.SCHUMANN_STATE = tmp / "nonexistent_state.json"
ssf.fetch_vlf_reading = lambda deadline=None: None
ssf.fetch_geomag_reading = lambda deadline=None: None
feel = ssf.SchumannFeel()
sensation = feel.take_reading()
check("sero.take_reading default None (fail-closed)",
      sensation is None, f"got {sensation!r}")
check("sero.take_reading default wrote nothing",
      (not ssf.FELT_LOG.exists()) or ssf.FELT_LOG.read_text().strip() == "")

# 4f. take_reading with sim allowed -> sensation from tagged synthesis
allow_sim()
feel2 = ssf.SchumannFeel()
sensation2 = feel2.take_reading()
check("sero.take_reading sim allowed -> sensation produced",
      sensation2 is not None)
if ssf.FELT_LOG.exists():
    lines = [json.loads(l) for l in ssf.FELT_LOG.read_text().splitlines() if l.strip()]
    synth_lines = [l for l in lines if l.get("data", {}).get("source", "").startswith("felt/")]
    check("sero sim readings tagged felt/synthesis in log",
          bool(synth_lines) and all(
              "felt/" in l["data"]["source"] for l in synth_lines))
fresh_env()

# ─── 5. wearable_bridge ─────────────────────────────────────────────────────
import wearable_bridge as wb

node = wb.HumanSensorNode()
node.connected = False
node.detect_watch = lambda: False
reading = node.read_biometrics()
check("wearable.read_biometrics no watch -> None (no sine-wave vitals)",
      reading is None)

node2 = wb.HumanSensorNode()
node2.connected = True
node2.detect_watch = lambda: True
reading2 = node2.read_biometrics()
check("wearable record carries simulated=true + wearable_present",
      reading2 is not None and reading2.get("simulated") is True
      and reading2.get("wearable_present") is True,
      f"simulated={reading2 and reading2.get('simulated')}")

# monitor loop with no watch must append nothing to history
wb.WORKSPACE = tmp
iface = wb.WearableBroadcastInterface()
iface.sensor = wb.HumanSensorNode()
iface.sensor.connected = False
iface.sensor.detect_watch = lambda: False
orig_sleep = wb.time.sleep
wb.time.sleep = lambda _s: None
iface.monitor_and_broadcast(duration=1)
wb.time.sleep = orig_sleep
check("wearable monitor with no watch records nothing",
      len(iface.sensor.history) == 0, f"history={len(iface.sensor.history)}")
iface.save_session_log()
logs = list((tmp / "wearable_logs").glob("wearable_session_*.json"))
ok = False
if logs:
    data = json.loads(logs[-1].read_text())
    ok = (data.get("wearable_present") is False
          and data.get("history") == []
          and data.get("sensor_node", {}).get("connected") is False)
check("wearable session log has wearable_present=false, empty history",
      ok and bool(logs))

# ─── 6. hnc_master_orchestrator ─────────────────────────────────────────────
import hnc_master_orchestrator as hmo

fresh_env()
prover = hmo.SchumannProver()
check("orchestrator.SchumannProver default None", prover.get_schumann_reading() is None)
check("orchestrator.validate_transmission default None",
      prover.validate_transmission(1) is None)
gp = hmo.GhostProtocolV2()
check("orchestrator.capture_field default None", gp.capture_field("BEFORE") is None)

orch = hmo.HNCMasterOrchestrator(max_transmissions=1)
res = orch.run_single_transmission(1)
check("orchestrator.run_single_transmission default skipped (None)",
      res is None, f"got {type(res).__name__ if res is not None else None}")
check("orchestrator no proof persisted on skipped cycle",
      not list(orch.log_dir.glob("transmission_*.json")))

allow_sim()
prover2 = hmo.SchumannProver()
reading = prover2.get_schumann_reading()
check("orchestrator prover allowed -> simulated reading", reading is not None)
val = prover2.validate_transmission(1)
check("orchestrator validation tagged simulation=true",
      val is not None and val.get("simulation") is True)
field = hmo.GhostProtocolV2().capture_field("BEFORE")
check("orchestrator capture_field allowed -> tagged simulation=true",
      field is not None and field.get("simulation") is True)
orch2 = hmo.HNCMasterOrchestrator(max_transmissions=1)
orch2.settling_time = 0
orch2.run_campaign("probe")
persisted = list(orch2.log_dir.glob("transmission_*.json"))
persisted_sim = None
if persisted:
    persisted_sim = json.loads(persisted[-1].read_text()).get("simulation")
res2 = orch2.results[-1] if orch2.results else None
result_sim = res2.simulation if res2 is not None else persisted_sim
check("orchestrator allowed cycle -> result carries simulation=true",
      result_sim is True,
      f"result_sim={result_sim}, results_len={len(orch2.results)}")
check("orchestrator persisted proof carries simulation=true",
      bool(persisted) and persisted_sim is True)
fresh_env()

# ─── 7. hnc_mandala_effect ──────────────────────────────────────────────────
# hnc_blind_ghost depends on hnc_temporal_targeting / hnc_spectrograph,
# which do not exist in the workspace (pre-existing broken import) — stub
# the blind protocol so the gate logic itself can be probed offline.
import types as _types

if "hnc_blind_ghost" not in sys.modules:
    _stub = _types.ModuleType("hnc_blind_ghost")

    class _StubBlindGhostProtocol:
        def pick_random_date(self):
            return "2014-11-17"

        def generate_blind_signal(self, reveal: bool = False):
            return {
                "target_date": "2014-11-17",
                "proof_id": "PROBE-PROOF",
                "signal_hash": "0xdeadbeef",
            }

    _stub.BlindGhostProtocol = _StubBlindGhostProtocol
    sys.modules["hnc_blind_ghost"] = _stub

import hnc_mandala_effect as hme

tmp_mandala = tmp / "mandala_ws"
tmp_mandala.mkdir(exist_ok=True)
hme.WORKSPACE = tmp_mandala  # dedicated dir — no hnc_state.json at all
fresh_env()
check("mandala._live_hnc_state None without state file",
      hme._live_hnc_state() is None)

engine = hme.MandalaEffectEngine()
engine.news_capturer.capture = lambda max_headlines=10: []
report = engine.measure(delay_seconds=0)
check("mandala live run with no live state -> verdict HOLD",
      report.verdict == "HOLD" and "insufficient live data" in report.queen_verdict,
      f"verdict={report.verdict!r}, queen={report.queen_verdict!r}")

# real_data=false state -> still HOLD
(tmp_mandala / "hnc_state.json").write_text(json.dumps({
    "timestamp": ts, "real_data": False,
    "hnc": {"lambda": 0.5, "gamma": 0.6, "beta": 0.8}}))
check("mandala real_data=false state -> None (unavailable)",
      hme._live_hnc_state() is None)
report2 = engine.measure(delay_seconds=0)
check("mandala fabricated state file -> HOLD",
      report2.verdict == "HOLD")

# real live state -> gate proceeds deterministically (no RNG gating).
# lambda must clear the Queen stability bar (>0.6) or the Queen may
# legitimately VETO — a veto is a real verdict on real data, not a sim.
(tmp_mandala / "hnc_state.json").write_text(json.dumps({
    "timestamp": ts, "real_data": True, "schumann_hz": 7.8,
    "hnc": {"lambda": 0.75, "gamma": 0.6, "beta": 0.8}}))
live_state = hme._live_hnc_state()
check("mandala live state parsed", live_state == {
    "lambda": 0.75, "coherence": 0.6, "beta": 0.8, "schumann": 7.8})
report3 = engine.measure(delay_seconds=0)
check("mandala live state -> real verdict produced (not HOLD)",
      report3.verdict != "HOLD", f"verdict={report3.verdict!r}")

# ─── 8. hnc_daemon (ghost mission seed gate) ────────────────────────────────
# hnc_daemon's own deps casimir_harmonia / hnc_calibrator / temporal_love_engine
# / leckey_love_box / ghost_fancy_protocol do NOT exist in the workspace
# (pre-existing broken imports) — stub them so the seed gate can be probed.
try:
    class _AnyModule(_types.ModuleType):
        def __getattr__(self, name):
            return object

    for _missing in ("casimir_harmonia", "hnc_calibrator",
                     "temporal_love_engine", "leckey_love_box",
                     "ghost_fancy_protocol"):
        if _missing not in sys.modules:
            sys.modules[_missing] = _AnyModule(_missing)

    import hnc_daemon as hnd
    fresh_env()
    daemon = hnd.HNCDaemon.__new__(hnd.HNCDaemon)
    daemon.lambda_history = []
    daemon.coherence_history = []
    daemon.schumann_history = []
    daemon.calibrator = None
    out = daemon.run_ghost_mission(2014, 11, 17, 14, 0, "probe", "probe")
    check("hnc_daemon ghost mission no history + gate off -> fail-closed",
          out.get("success") is False and out.get("real_data") is False
          and "insufficient live data" in out.get("error", ""),
          f"error={out.get('error')!r}")
    allow_sim()

    class _Target:
        data_sources_available = []
        def to_iso(self):
            return "2014-11-17T14:00:00"
        def to_dict(self):
            return {"date": "2014-11-17"}

    class _Result:
        verdict = "APPROVED"
        penetration_score = 0.5
        confidence = 0.5
        proof_hash = "x" * 32

    class _GhostFancyStub:
        captured_state = None
        def create_target(self, **kwargs):
            return _Target()
        def execute_and_validate(self, target, hnc_state):
            _GhostFancyStub.captured_state = hnc_state
            return _Result()

    class _GaiaTrackerStub:
        goals = []
        def update_from_penetration(self, result):
            pass
        def save_goals(self):
            pass
        def get_status(self):
            return {}

    daemon2 = hnd.HNCDaemon.__new__(hnd.HNCDaemon)
    daemon2.lambda_history = []
    daemon2.coherence_history = []
    daemon2.schumann_history = []
    daemon2.calibrator = None
    daemon2.ghost_fancy = _GhostFancyStub()
    daemon2.gaia_tracker = _GaiaTrackerStub()
    out2 = daemon2.run_ghost_mission(2014, 11, 17, 14, 0, "probe", "probe")
    seeded_state = _GhostFancyStub.captured_state or {}
    check("hnc_daemon ghost mission seed only when explicitly allowed",
          out2.get("success") is True and out2.get("seeded") is True
          and out2.get("simulation") is True and out2.get("real_data") is False
          and seeded_state.get("simulation") is True
          and seeded_state.get("real_data") is False,
          f"seeded={out2.get('seeded')}, simulation={out2.get('simulation')}, "
          f"success={out2.get('success')}, err={out2.get('error')!r}")
    fresh_env()
except Exception as e:
    check("hnc_daemon ghost mission probe", False, f"import/probe error: {e!r}")

# ─── summary ────────────────────────────────────────────────────────────────
failed = [r for r in RESULTS if not r[1]]
print(f"\n{'='*70}\nPROBE SUMMARY: {len(RESULTS) - len(failed)}/{len(RESULTS)} passed")
for name, ok_, detail in RESULTS:
    if not ok_:
        print(f"  FAILED: {name} — {detail}")
sys.exit(1 if failed else 0)
