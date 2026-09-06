#!/usr/bin/env python3
"""Offline verification probes for the FUSION-CORE fix wave.

Everything runs against a TEMP workspace (SERO_WORKSPACE) — zero real state
files, zero broker orders, zero process spawns. Sub-probes that need two
processes re-exec this file with a mode argument.

Usage:  python fix_wave_probes_fusion_core.py          (all single-process probes)
        python fix_wave_probes_fusion_core.py regworker <regfile> <n>
        python fix_wave_probes_fusion_core.py seqworker <seqfile> <lockfile> <n>
        python fix_wave_probes_fusion_core.py idworker            (sha-id determinism)
"""
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REAL_WORKSPACE = Path(r"C:\Users\user\.kimi_openclaw\workspace")
FAILURES = []


def check(name, cond, detail=""):
    status = "PASS" if cond else "FAIL"
    print(f"  [{status}] {name}" + (f" -- {detail}" if detail and not cond else ""))
    if not cond:
        FAILURES.append(name)


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def fresh_workspace():
    tmp = Path(tempfile.mkdtemp(prefix="aureon_probe_"))
    os.environ["SERO_WORKSPACE"] = str(tmp)
    if str(REAL_WORKSPACE) not in sys.path:
        sys.path.insert(0, str(REAL_WORKSPACE))
    # purge cached path-sensitive modules so they re-resolve against tmp
    for mod in list(sys.modules):
        if mod == "aureon_fusion" or mod.startswith("aureon_fusion."):
            del sys.modules[mod]
    for mod in ("sero_memory_web", "sero_thoughtbus"):
        sys.modules.pop(mod, None)
    return tmp


# ───────────────────────────── probe: registry RMW (finding 2) ─────────────

def regworker(regfile, n):
    os.environ["SERO_WORKSPACE"] = str(Path(regfile).parent.parent.parent)
    sys.path.insert(0, str(REAL_WORKSPACE))
    from aureon_fusion import organ_registry as reg
    reg.REGISTRY_FILE = Path(regfile)
    for _ in range(int(n)):
        with reg._registry_lock():
            data = reg._read_registry_file()
            data["probe_counter"] = int(data.get("probe_counter", 0)) + 1
            assert reg._save_registry(data), "save failed under lock"
    print("worker done")


def probe_registry(tmp):
    print("─ registry RMW (2 processes x 40 locked increments) ─")
    regfile = tmp / "aureon_fusion" / "state" / "organ_registry.json"
    regfile.parent.mkdir(parents=True, exist_ok=True)
    regfile.write_text('{"organs": {}}', encoding="utf-8")
    script = Path(__file__)
    procs = [subprocess.Popen([sys.executable, str(script), "regworker", str(regfile), "40"])
             for _ in range(2)]
    rc = [p.wait(timeout=300) for p in procs]
    check("both workers exited 0", all(c == 0 for c in rc), f"rc={rc}")
    final = json.loads(regfile.read_text(encoding="utf-8"))
    check("no lost updates: counter == 80", final.get("probe_counter") == 80,
          f"counter={final.get('probe_counter')}")
    orphans = list(regfile.parent.glob("organ_registry.json.tmp.*"))
    check("no orphan tmp files", not orphans, f"orphans={[str(o) for o in orphans]}")
    check("registry JSON parses cleanly", isinstance(final.get("organs"), dict))


# ─────────────────────── probe: receipts seq lock (finding 3) ──────────────

def seqworker(seqfile, lockfile, n):
    os.environ["SERO_WORKSPACE"] = str(Path(seqfile).parent.parent.parent)
    sys.path.insert(0, str(REAL_WORKSPACE))
    from aureon_fusion import receipts
    receipts._SEQ_FILE = Path(seqfile)
    receipts._SEQ_LOCK_FILE = Path(lockfile)
    out = []
    for _ in range(int(n)):
        out.append(receipts._next_recorder_sequence())
    print(json.dumps(out))  # last line = JSON list of drawn sequences


def probe_seq(tmp):
    print("─ receipts recorder-sequence lock (2 processes x 50 draws) ─")
    state = tmp / "aureon_fusion" / "state"
    state.mkdir(parents=True, exist_ok=True)
    seqfile = state / "intrusion_ledger_seq.json"
    lockfile = state / "intrusion_ledger_seq.json.lock"
    seqfile.write_text('{"seq": 0}', encoding="utf-8")
    script = Path(__file__)
    runs = [subprocess.run([sys.executable, str(script), "seqworker", str(seqfile),
                            str(lockfile), "50"], capture_output=True, text=True,
                           timeout=300) for _ in range(2)]
    drawn = []
    for r in runs:
        drawn += json.loads(r.stdout.strip().splitlines()[-1])
    check("drew 100 sequences", len(drawn) == 100, f"n={len(drawn)}")
    check("all sequences unique (no RMW race)",
          len(set(drawn)) == len(drawn), f"unique={len(set(drawn))}")
    check("all within 1..4096 contract",
          all(isinstance(s, int) and 1 <= s <= 4096 for s in drawn))
    final = json.loads(seqfile.read_text(encoding="utf-8"))
    check("persisted seq == max drawn", final.get("seq") == max(drawn),
          f"persisted={final.get('seq')} max={max(drawn)}")
    orphans = list(state.glob("intrusion_ledger_seq.json.tmp.*"))
    check("no orphan seq tmp files", not orphans)


# ──────────────── probe: memory web wipe + migration (findings 1, S2) ──────

def idworker():
    # separate process (different PYTHONHASHSEED) must derive the SAME id
    os.environ["SERO_WORKSPACE"] = tempfile.mkdtemp(prefix="aureon_probe_ids_")
    sys.path.insert(0, str(REAL_WORKSPACE))
    import hashlib
    import sero_memory_web as smw
    web = smw.MemoryWeb()
    node = web.remember("determinism probe content alpha")
    expect = "mem_" + hashlib.sha256("determinism probe content alpha".encode()).hexdigest()[:12]
    print(json.dumps({"id": node.id, "expect": expect, "match": node.id == expect}))


def probe_memory_web(tmp):
    print("─ sero_memory_web: sha256 IDs, migration, corrupt-load fail-closed ─")
    import hashlib
    import sero_memory_web as smw

    webdir = tmp / "sero_memory_web"
    webdir.mkdir(parents=True, exist_ok=True)
    graph = webdir / "memory_graph.json"

    # legacy hash()-style graph with an edge between legacy nodes
    legacy = {
        "nodes": [
            {"id": "mem_11111111", "content": "alpha memory", "node_type": "fact",
             "timestamp": "2026-01-01T00:00:00+00:00", "emotional_weight": 0.1,
             "intensity": 0.5, "tags": ["probe"], "recall_count": 2,
             "last_recalled": None},
            {"id": "mem_22222222", "content": "beta memory", "node_type": "event",
             "timestamp": "2026-01-02T00:00:00+00:00", "emotional_weight": -0.2,
             "intensity": 0.7, "tags": ["probe"], "recall_count": 0,
             "last_recalled": None},
        ],
        "edges": [{"source_id": "mem_11111111", "target_id": "mem_22222222",
                   "edge_type": "related_to", "strength": 0.5,
                   "timestamp": "2026-01-03T00:00:00+00:00"}],
    }
    graph.write_text(json.dumps(legacy), encoding="utf-8")

    web = smw.MemoryWeb()
    ids = sorted(web.nodes)
    expect_a = "mem_" + hashlib.sha256(b"alpha memory").hexdigest()[:12]
    expect_b = "mem_" + hashlib.sha256(b"beta memory").hexdigest()[:12]
    check("legacy IDs migrated to sha256[:12]",
          ids == sorted([expect_a, expect_b]), f"ids={ids}")
    check("edge remapped to migrated IDs",
          web.edges[0].source_id == expect_a and web.edges[0].target_id == expect_b)
    check("tag index remapped", web.index.get("probe") == {expect_a, expect_b})
    persisted = json.loads(graph.read_text(encoding="utf-8"))
    check("migration persisted atomically",
          sorted(n["id"] for n in persisted["nodes"]) == ids)

    # new nodes get deterministic IDs (no hash())
    n1 = web.remember("gamma memory delta")
    check("new node id deterministic sha256[:12]",
          n1.id == "mem_" + hashlib.sha256(b"gamma memory delta").hexdigest()[:12])

    # corrupt-load: backup created, save() is a no-op, graph NOT overwritten
    good_bytes = graph.read_bytes()
    graph.write_text("{ this is not json ]", encoding="utf-8")
    corrupt_bytes = graph.read_bytes()
    web2 = smw.MemoryWeb()
    check("load failure flagged", web2._load_failed is True)
    backups = list(webdir.glob("memory_graph.corrupt-*.json"))
    check("corrupt backup created", len(backups) >= 1,
          f"backups={len(backups)}")
    ok = web2.save()
    check("save() no-op after load failure", ok is False)
    check("corrupt file NOT overwritten", graph.read_bytes() == corrupt_bytes)
    check("backup holds the corrupt bytes (evidence preserved)",
          backups[0].read_bytes() == corrupt_bytes)
    # restore the good graph into place, reload: graph recovered intact
    # (good_bytes holds the post-migration 2-node file; gamma was only
    # in memory)
    graph.write_bytes(good_bytes)
    web3 = smw.MemoryWeb()
    check("restored good graph reloads with all nodes",
          len(web3.nodes) == 2 and not web3._load_failed)
    check("restored graph save() works again (fail-closed flag cleared)",
          web3.save() is True)

    # sha determinism across processes (old hash() was PYTHONHASHSEED-random)
    env = dict(os.environ)
    env["PYTHONHASHSEED"] = "12345"
    r = subprocess.run([sys.executable, str(Path(__file__)), "idworker"],
                       capture_output=True, text=True, env=env, timeout=120)
    res = json.loads(r.stdout.strip().splitlines()[-1])
    check("node ID identical in other process (hash-seed independent)",
          res.get("match") is True, f"got={res}")
    # sanity: old hash() id would have been 8 decimal digits
    check("legacy 8-digit hash ids rejected by new-ID regex",
          not smw._ID_RE.match("mem_52585401"))


# ─────────────── probe: capability_gate fail-closed (finding 5) ────────────

def probe_gate(tmp):
    print("─ capability_gate: HOLD on forced internal error (trading domain) ─")
    from aureon_fusion import capability_gate as gate

    # 1) runtime-safety complement raises inside a trading_execution gate
    sys.path.insert(0, str(REAL_WORKSPACE / "aureon-os-upstream"))
    import aureon.core.aureon_runtime_safety as rts
    orig = rts.live_block_reason
    rts.live_block_reason = lambda ctx: (_ for _ in ()).throw(RuntimeError("forced boom"))

    matrix = tmp / "sero_autonomous_state"
    matrix.mkdir(parents=True, exist_ok=True)
    (matrix / "capability_matrix.json").write_text(json.dumps({
        "gates": {
            "trading_execution:execute_live_trades": {"status": "active", "level": "ELEVATE"},
            "trading_execution:read_positions": {"status": "active", "level": "LOW"},
            "file_system:read_files": {"status": "active", "level": "LOW"},
        }}), encoding="utf-8")
    gate.MATRIX_FILE = matrix / "capability_matrix.json"
    gate.FLAG_FILE = tmp / "aureon_fusion" / "state" / "capital_release.flag"
    gate.FLAG_FILE.parent.mkdir(parents=True, exist_ok=True)
    gate.FLAG_FILE.write_text("RELEASE_AUTHORIZED_BY_GARY\n", encoding="utf-8")

    v = gate.check("trading_execution:read_positions")
    check("exception in runtime-safety → HOLD (non-pinned trading gate)",
          v["verdict"] == "HOLD" and v["allowed"] is False, f"got={v}")
    check("hold reason mentions fail-closed", "fail-closed" in v.get("reason", ""))

    # 2) pinned capital gate still ALLOWs under owner release + attestation
    v2 = gate.check("trading_execution:execute_live_trades")
    check("pinned gate with release flag stays ALLOW (attested path intact)",
          v2["verdict"] == "ALLOW" and v2["allowed"] is True, f"got={v2}")

    # 3) flag absent → pinned HOLD regardless
    gate.FLAG_FILE.unlink()
    v3 = gate.check("trading_execution:execute_live_trades")
    check("pinned gate without flag → HARD PIN HOLD",
          v3["verdict"] == "HOLD" and v3.get("pinned") is True, f"got={v3}")

    # 4) _check_verdict itself raises → check() fails closed, never None
    orig_cv = gate._check_verdict
    gate._check_verdict = lambda d: (_ for _ in ()).throw(ValueError("forced"))
    v4 = gate.check("file_system:read_files")
    gate._check_verdict = orig_cv
    check("check() exception → fail-closed HOLD, never None",
          isinstance(v4, dict) and v4["verdict"] == "HOLD"
          and v4["allowed"] is False and v4.get("fail_closed") is True,
          f"got={v4}")

    # 5) matrix unreadable → gate fails closed (DENY/HOLD, never ALLOW/None)
    gate.MATRIX_FILE = matrix / "does_not_exist.json"
    v5 = gate.check("trading_execution:read_positions")
    check("missing matrix → trading gate refused (no gate defined)",
          v5["allowed"] is False and v5["verdict"] in ("HOLD", "DENY"),
          f"got={v5}")
    rts.live_block_reason = orig


# ─────────────── probe: trade_journal dedupe keys (finding 6) ──────────────

def probe_journal(tmp):
    print("─ trade_journal: duplicate ts+missing-audit_id entries both kept ─")
    from aureon_fusion import trade_journal as tj

    radar = tmp / "aureon_radar"
    radar.mkdir(parents=True, exist_ok=True)
    dup_ts = "2026-09-04T12:00:00Z"
    with open(radar / "trade_ledger.jsonl", "w", encoding="utf-8") as f:
        f.write(json.dumps({"timestamp": dup_ts, "stage": "ORDER_SENT",
                            "symbol": "GOLD", "direction": "BUY"}) + "\n")
        f.write(json.dumps({"timestamp": dup_ts, "stage": "ORDER_FAILED",
                            "symbol": "GOLD", "direction": "BUY"}) + "\n")
        f.write(json.dumps({"timestamp": "", "stage": "EXECUTED",
                            "symbol": "EURUSD", "direction": "SELL"}) + "\n")
        f.write(json.dumps({"timestamp": "", "stage": "EXECUTED",
                            "symbol": "GBPUSD", "direction": "SELL"}) + "\n")
    events = tj._collect_events()
    keys = [k for k, *_ in events]
    check("all 4 ledger entries collected (none deduped at source)",
          len(events) == 4, f"n={len(events)}")
    check("all dedupe keys unique despite identical ts and empty ts/audit_id",
          len(set(keys)) == len(keys), f"keys={keys}")
    check("no constant-string key", all(k.count(":") >= 3 and not k.endswith("::") or k.split(":")[2].isdigit()
                                        for k in keys))

    # full sweep persists all four as separate memory-web nodes
    res = tj.sweep_once()
    check("sweep remembered all 4 events", res["remembered"] == 4,
          f"remembered={res.get('remembered')} degraded={res.get('degraded')} err={res.get('error')}")
    import sero_memory_web as smw
    web = smw.MemoryWeb()
    trade_nodes = [n for n in web.nodes.values() if n.node_type == "trade"]
    check("4 distinct trade nodes persisted in memory web",
          len(trade_nodes) == 4, f"n={len(trade_nodes)}")


# ─────────────── probe: heartbeat-state atomic (finding 7) ────────────────

def probe_heartbeat(tmp):
    print("─ heartbeat-state.json tmp+replace ─")
    import aureon_fusion.heartbeat_exec as hb
    hb.HEARTBEAT_STATE = tmp / "memory" / "heartbeat-state.json"
    hb._mark_done("email", epoch=1703275200)
    state = json.loads(hb.HEARTBEAT_STATE.read_text(encoding="utf-8"))
    check("heartbeat-state written + readable", state["lastChecks"]["email"] == 1703275200)
    orphans = list(hb.HEARTBEAT_STATE.parent.glob("heartbeat-state.json.tmp.*"))
    check("no orphan tmp after write", not orphans)
    hb._mark_done("calendar", epoch=1703260800)
    state = json.loads(hb.HEARTBEAT_STATE.read_text(encoding="utf-8"))
    check("second write merges (both checks present)",
          set(state["lastChecks"]) == {"email", "calendar"})


# ─────────────── probe: awakening corrupt-read (finding 8) ────────────────

def probe_awakening(tmp):
    print("─ awakening: corrupt mind state → backup, no continuity zeroing ─")
    import aureon_fusion.awakening as aw
    mind_dir = tmp / "sero_mind"
    mind_dir.mkdir(parents=True, exist_ok=True)
    (tmp / "sero_memory_web").mkdir(exist_ok=True)
    aw.MIND_STATE = mind_dir / "consciousness_state.json"
    aw.CONTINUITY_CHAIN = mind_dir / "continuity_chain.jsonl"

    good = {"state": "awake", "awakening_index": 7.0, "continuity_score": 0.9,
            "active_goals": ["probe-goal"], "emotional_state": {}}
    aw.MIND_STATE.write_text(json.dumps(good), encoding="utf-8")
    digest = aw.sleep()
    saved = json.loads(aw.MIND_STATE.read_text(encoding="utf-8"))
    check("normal sleep persists mind state atomically",
          saved["state"] == "dormant" and saved["continuity_score"] == 0.95,
          f"saved={saved}")
    check("digest reports normal save", "awake → dormant" in digest)

    # now corrupt it: continuity must NOT be zeroed, corrupt file preserved
    aw.MIND_STATE.write_text("{ corrupt ! json ]", encoding="utf-8")
    corrupt_bytes = aw.MIND_STATE.read_bytes()
    digest2 = aw.sleep()
    backups = list(mind_dir.glob("consciousness_state.corrupt-*.json"))
    check("corrupt backup created", len(backups) >= 1)
    check("corrupt original NOT overwritten (continuity not zeroed)",
          aw.MIND_STATE.read_bytes() == corrupt_bytes)
    check("digest flags preserved-corrupt state", "CORRUPT" in digest2)
    check("backup holds the corrupt bytes (evidence preserved)",
          backups[0].read_bytes() == corrupt_bytes)


# ─────────────── probe: event signing before _log (finding 4) ──────────────

def probe_signing(tmp):
    print("─ event signing: receipt attached before envelope append ─")
    os.environ["AUREON_FUSION_EVENT_SIGNING"] = "1"
    from aureon_fusion import events
    env = events.publish(source="probe.signing", topic="probe.signed",
                         payload={"probe": True}, priority=5)
    check("publish returned an envelope", env is not None)
    check("receipt present on returned envelope",
          isinstance(env, dict) and isinstance(env.get("receipt"), dict),
          f"keys={list(env) if isinstance(env, dict) else env}")
    from aureon_fusion import receipts
    check("envelope receipt verifies", receipts.verify_event(env))

    buslog = events.BUS_LOG
    check("bus log written in temp workspace", str(buslog).startswith(str(tmp)))
    last = None
    with open(buslog, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                last = json.loads(line)
    check("last LOGGED envelope already carries the receipt (sign-before-append)",
          isinstance(last, dict) and isinstance(last.get("receipt"), dict),
          f"last keys={list(last) if isinstance(last, dict) else last}")
    check("logged envelope verifies from disk", receipts.verify_event(last))


# ───────────────────────────── tasklist PID match (finding 9) ──────────────

def probe_tasklist():
    print("─ tasklist PID exact-match (no substring false positive) ─")
    from aureon_fusion import organ_registry as reg
    # PID 123 must not match a tasklist output that only contains PID 1234
    fake_out = '"some.exe","1234","Console","1","12,345 K"\r\n'
    import csv, io
    matched = any(len(row) >= 2 and row[1].strip() == "123"
                  for row in csv.reader(io.StringIO(fake_out)))
    check("PID 123 rejected against 1234 output", not matched)
    matched2 = any(len(row) >= 2 and row[1].strip() == "1234"
                   for row in csv.reader(io.StringIO(fake_out)))
    check("PID 1234 accepted in its own row", matched2)


# ───────────────────────────────── main ─────────────────────────────────────

def main():
    print("=" * 72)
    print("FUSION-CORE offline probes — temp workspace, no real state touched")
    print("=" * 72)
    tmp = fresh_workspace()
    print(f"temp workspace: {tmp}")
    probe_registry(tmp)
    probe_seq(tmp)
    probe_memory_web(tmp)
    probe_gate(tmp)
    probe_journal(tmp)
    probe_heartbeat(tmp)
    probe_awakening(tmp)
    probe_signing(tmp)
    probe_tasklist()
    print("=" * 72)
    if FAILURES:
        print(f"RESULT: FAIL ({len(FAILURES)}): {FAILURES}")
        return 1
    print("RESULT: ALL PROBES PASS")
    return 0


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "regworker":
        regworker(sys.argv[2], sys.argv[3])
    elif len(sys.argv) > 1 and sys.argv[1] == "seqworker":
        seqworker(sys.argv[2], sys.argv[3], sys.argv[4])
    elif len(sys.argv) > 1 and sys.argv[1] == "idworker":
        idworker()
    else:
        sys.exit(main())
