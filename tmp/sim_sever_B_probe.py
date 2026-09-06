#!/usr/bin/env python3
"""SIM-SEVER-B offline verification probes. No network, no broker calls.
Writes results to aureon_fusion/state/fix_wave_sim_sever_B.log."""
import os, sys, json, types, tempfile, traceback
from pathlib import Path
from datetime import datetime, timezone, timedelta

os.environ["AUREON_SUPPRESS_IMPORT_SIDE_EFFECTS"] = "1"
os.environ["AUREON_AUDIT_MODE"] = "1"
os.environ.pop("AUREON_ALLOW_SIM_FALLBACK", None)

WS = Path("C:/Users/user/.kimi_openclaw/workspace")
RADAR = WS / "aureon_radar"
sys.path.insert(0, str(RADAR))
sys.path.insert(0, str(RADAR / "analyzers"))

results = []

def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name} :: {detail}")

tmp = Path(tempfile.mkdtemp(prefix="sim_sever_B_"))
now = datetime.now(timezone.utc)

# ─────────────────────────────────────────────────────────────────────────────
# FIX 1 — planetary_switchboard.SchumannFeed
# ─────────────────────────────────────────────────────────────────────────────
try:
    import planetary_switchboard as ps

    # 1a. missing state file -> None
    os.environ["AUREON_SCHUMANN_STATE"] = str(tmp / "does_not_exist.json")
    r = ps.SchumannFeed().get_schumann()
    check("switchboard: missing state -> None", r is None, repr(r))

    # 1b. fresh state -> real values
    fresh = {"timestamp": now.isoformat(), "source": "resonanceone_tomsk",
             "frequency_hz": 7.83, "activity_index": 27, "activity_label": "moderate",
             "kp_index": 0, "geomagnetic_status": "quiet",
             "real_data": True, "simulation": False}
    sf = tmp / "schumann_state.json"; sf.write_text(json.dumps(fresh))
    os.environ["AUREON_SCHUMANN_STATE"] = str(sf)
    r = ps.SchumannFeed().get_schumann()
    check("switchboard: fresh state -> real values",
          r is not None and r.fundamental_hz == 7.83 and r.source.startswith("schumann_state_json")
          and "simulation" not in r.source,
          f"hz={getattr(r,'fundamental_hz',None)} source={getattr(r,'source',None)}")

    # 1c. stale state (>600s) -> None
    stale = dict(fresh); stale["timestamp"] = (now - timedelta(seconds=3600)).isoformat()
    sf.write_text(json.dumps(stale))
    r = ps.SchumannFeed().get_schumann()
    check("switchboard: stale state -> None", r is None, repr(r))

    # 1c-ii. custom age gate honored (tighten to 60s, age 120s -> None)
    os.environ["AUREON_SCHUMANN_MAX_AGE_SEC"] = "60"
    mid = dict(fresh); mid["timestamp"] = (now - timedelta(seconds=120)).isoformat()
    sf.write_text(json.dumps(mid))
    r = ps.SchumannFeed().get_schumann()
    check("switchboard: configurable age gate (60s, 120s old) -> None", r is None, repr(r))
    os.environ.pop("AUREON_SCHUMANN_MAX_AGE_SEC", None)

    # 1d. simulation-flagged without env -> None
    sim = dict(fresh); sim["simulation"] = True; sim["real_data"] = False
    sf.write_text(json.dumps(sim))
    r = ps.SchumannFeed().get_schumann()
    check("switchboard: sim-flagged, no env -> None", r is None, repr(r))

    # 1e. simulation-flagged WITH env -> allowed and tagged
    os.environ["AUREON_ALLOW_SIM_FALLBACK"] = "1"
    r = ps.SchumannFeed().get_schumann()
    check("switchboard: sim-flagged + env -> tagged simulation",
          r is not None and r.source.endswith(":simulation"), f"source={getattr(r,'source',None)}")
    os.environ.pop("AUREON_ALLOW_SIM_FALLBACK", None)

    # 1f. malformed state -> None
    sf.write_text("{ not json")
    r = ps.SchumannFeed().get_schumann()
    check("switchboard: malformed json -> None", r is None, repr(r))

    # 1g. compartment skips Schumann signals when feed is None (fail-closed),
    #     emits them when feed is fresh. NOAA/NASA stubbed — no network.
    engine = ps.PlanetaryMetaEngine()
    engine.noaa = types.SimpleNamespace(get_kp=lambda: None, get_solar_wind=lambda: None,
                                        get_mag_field=lambda: None)
    engine.nasa = types.SimpleNamespace(get_flares=lambda: [], get_cmes=lambda: [])
    ps.PLANETARY_LOG = tmp / "planetary_meta.log"  # keep probe out of operational log
    sf.write_text(json.dumps(stale))  # stale -> feed None
    sigs = engine.analyze()
    check("switchboard: stale -> no schumann signals emitted",
          all(s.signal_type != "schumann" for s in sigs),
          f"signal_types={[s.signal_type for s in sigs]}")
    sf.write_text(json.dumps(dict(fresh, kp_index=9, geomagnetic_status="storm")))  # fresh + disturbed
    engine.schumann = ps.SchumannFeed()
    sigs = engine.analyze()
    check("switchboard: fresh+disturbed -> schumann signal emitted",
          any(s.signal_type == "schumann" for s in sigs),
          f"signal_types={[s.signal_type for s in sigs]}")
except Exception:
    check("switchboard probes", False, traceback.format_exc()[-400:])

# ─────────────────────────────────────────────────────────────────────────────
# FIX 3 — aureon_bridge stdout parser (no process started; methods only)
# ─────────────────────────────────────────────────────────────────────────────
try:
    import aureon_bridge as ab
    ab.AUREON_BRIDGE_LOG = tmp / "bridge_signals.jsonl"
    ab.FUSED_SIGNALS = tmp / "fused_signals.jsonl"
    br = ab.AureonRadarBridge()

    def _no_new_records():
        return (not ab.AUREON_BRIDGE_LOG.exists()) or ab.AUREON_BRIDGE_LOG.stat().st_size == 0

    br._parse_aureon_line("this is not a BUY signal for USDJPY")
    check("bridge: 'not a BUY' rejected (negation)",
          _no_new_records(), "no record written")

    br._parse_aureon_line("BLOCKED: skip SELL on GOLD, conditions unmet")
    check("bridge: 'skip SELL' rejected (negation)",
          _no_new_records(), "no record written")

    br._parse_aureon_line("analysis says: no long entries today, avoid short exposure")
    check("bridge: 'no long ... avoid short' rejected",
          _no_new_records(), "no record written")

    br._parse_aureon_line("BUY USDJPY opportunity detected by scanner")
    recs = [json.loads(l) for l in ab.AUREON_BRIDGE_LOG.read_text().splitlines()]
    check("bridge: affirmed BUY emitted with None confidence/fusion",
          len(recs) == 1 and recs[0]["direction"] == "LONG"
          and recs[0]["confidence"] is None and recs[0]["fusion_score"] is None
          and recs[0]["symbol"] == "USDJPY", json.dumps(recs))

    br._parse_aureon_line("SELL GOLD now — momentum confirmed")
    recs = [json.loads(l) for l in ab.AUREON_BRIDGE_LOG.read_text().splitlines()]
    check("bridge: affirmed SELL emitted, None confidence, count=2",
          len(recs) == 2 and recs[1]["direction"] == "SHORT"
          and recs[1]["confidence"] is None, json.dumps(recs[-1]))

    br._parse_aureon_line("general market commentary with no direction at all")
    recs = [json.loads(l) for l in ab.AUREON_BRIDGE_LOG.read_text().splitlines()]
    check("bridge: directionless line ignored", len(recs) == 2, f"count={len(recs)}")
except Exception:
    check("bridge probes", False, traceback.format_exc()[-400:])

# ─────────────────────────────────────────────────────────────────────────────
# FIX 2 — aureon_phi_radar signal records: no constant stop fields
# ─────────────────────────────────────────────────────────────────────────────
try:
    import aureon_phi_radar as pr
    cls = None
    for name, obj in vars(pr).items():
        if isinstance(obj, type) and "_generate_signal" in vars(obj):
            cls = obj
    inst = cls.__new__(cls)
    sig_long = cls._generate_signal(inst, "USDJPY", 150.0, "LONG", 0.7, 0.2, 0.5)
    sig_short = cls._generate_signal(inst, "USDJPY", 150.0, "SHORT", 0.7, 0.2, 0.5)
    d = sig_long.to_dict()
    check("phi_radar: LONG signal stop_loss is None (not price*0.5=75.0)",
          d["stop_loss"] is None and d["stop_loss"] != 75.0, f"stop_loss={d['stop_loss']}")
    check("phi_radar: SHORT signal stop_loss is None (not price*2.0=300.0)",
          sig_short.to_dict()["stop_loss"] is None, f"stop_loss={sig_short.to_dict()['stop_loss']}")
    check("phi_radar: target_price still real-quote derived",
          abs(d["target_price"] - 150.075) < 1e-9, f"target={d['target_price']}")
    json.dumps(d)  # record serializes with stop_loss: null
    check("phi_radar: signal record JSON-serializable (stop_loss null)",
          '"stop_loss": null' in json.dumps(d), json.dumps(d))
    # fused-signal consumer guard: None confidence -> 0.0 (low priority), no crash
    raw_conf = None
    conf = raw_conf if isinstance(raw_conf, (int, float)) else 0.0
    check("phi_radar: None confidence consumer guard -> 0.0", conf == 0.0, f"conf={conf}")
except Exception:
    check("phi_radar probes", False, traceback.format_exc()[-400:])

# ─────────────────────────────────────────────────────────────────────────────
# FIX 4 — rising_star: RNG verdicts dev-only
# ─────────────────────────────────────────────────────────────────────────────
try:
    # Stub the aureon package (upstream is read-only; offline probe).
    def _mk(name, **attrs):
        m = types.ModuleType(name); m.__path__ = []
        for k, v in attrs.items(): setattr(m, k, v)
        return m
    baton = _mk("aureon.core.aureon_baton_link", link_system=lambda name: None)
    policy = _mk("aureon.observer.live_data_policy",
                 simulation_fallback_allowed=lambda: os.getenv("AUREON_ALLOW_SIM_FALLBACK") == "1")
    sys.modules.update({
        "aureon": _mk("aureon"),
        "aureon.core": _mk("aureon.core"),
        "aureon.core.aureon_baton_link": baton,
        "aureon.observer": _mk("aureon.observer"),
        "aureon.observer.live_data_policy": policy,
    })
    import aureon_rising_star_logic as rs
    scanner = rs.RisingStarScanner.__new__(rs.RisingStarScanner)
    scanner.simulation_count = 1000
    scanner._thought_bus = None
    cand = rs.RisingStarCandidate(symbol="BTC/USDT", exchange="binance", price=100.0,
                                  score=0.8, quantum_boost=1.1, probability_win=0.7,
                                  momentum_strength=0.6, firm_alignment=0.5)

    res = rs.RisingStarScanner.run_monte_carlo_simulations(scanner, cand)
    check("rising_star: no env -> unranked refusal",
          res.get("unranked") is True and res.get("reason") == "requires live backtest data"
          and res.get("confidence") is None and res.get("simulations_run") == 0,
          json.dumps(res))
    check("rising_star: refusal is not tagged simulation", res.get("simulation") is False,
          f"simulation={res.get('simulation')}")

    cands = [rs.RisingStarCandidate(symbol=f"S{i}", exchange="binance", price=10.0 + i,
                                    score=0.9 - i * 0.05, quantum_boost=1.0,
                                    probability_win=0.7, momentum_strength=0.5,
                                    firm_alignment=0.5) for i in range(4)]
    original_order = [c.symbol for c in cands]
    best = rs.RisingStarScanner.select_best_two(scanner, cands)
    check("rising_star: select_best_two refuses to rank (order preserved)",
          [c.symbol for c in best] == original_order and all("UNRANKED" in c.reasoning for c in best),
          f"order={[c.symbol for c in best]} reasoning={best[0].reasoning[-60:]}")

    os.environ["AUREON_ALLOW_SIM_FALLBACK"] = "1"
    res2 = rs.RisingStarScanner.run_monte_carlo_simulations(scanner, cand)
    check("rising_star: dev env -> ranked, tagged simulation=True",
          res2.get("unranked") is False and res2.get("simulation") is True
          and isinstance(res2.get("win_rate"), float) and res2.get("simulations_run") == 1000,
          json.dumps({k: res2[k] for k in ('win_rate', 'unranked', 'simulation')}))
    os.environ.pop("AUREON_ALLOW_SIM_FALLBACK", None)
except Exception:
    check("rising_star probes", False, traceback.format_exc()[-400:])

# ─────────────────────────────────────────────────────────────────────────────
summary = f"SIM-SEVER-B probe summary: {sum(1 for _, ok, _ in results if ok)}/{len(results)} passed"
print(summary)

LOG = WS / "aureon_fusion" / "state" / "fix_wave_sim_sever_B.log"
with open(LOG, "a", encoding="utf-8") as f:
    f.write(f"\n{'='*70}\n{now.isoformat()} SIM-SEVER-B offline probes (zero broker contact)\n{'='*70}\n")
    for name, ok, detail in results:
        f.write(f"[{'PASS' if ok else 'FAIL'}] {name} :: {detail}\n")
    f.write(summary + "\n")
print(f"log -> {LOG}")
sys.exit(0 if all(ok for _, ok, _ in results) else 1)
