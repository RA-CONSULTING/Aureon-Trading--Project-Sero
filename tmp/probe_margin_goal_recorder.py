#!/usr/bin/env python3
"""Probe: margin_goal_recorder defensive record_scan + anchored proof file.

Proves:
  1. record_scan no longer crashes on short tuples (5-tuple) or garbage.
  2. Proof file is written to the anchored dir (MARGIN_GOAL_PROOF_DIR /
     SERO_WORKSPACE), never bare CWD — verified by chdir'ing away.
"""
import importlib
import json
import os
import sys
import tempfile
from pathlib import Path

WORKSPACE = Path(r"C:\Users\user\.kimi_openclaw\workspace")
sys.path.insert(0, str(WORKSPACE / "aureon-os-upstream"))

ORIG_CWD = Path.cwd()
failures = []


def check(name, cond, detail=""):
    status = "PASS" if cond else "FAIL"
    print(f"[{status}] {name}" + (f" — {detail}" if detail and not cond else ""))
    if not cond:
        failures.append(name)


class FakeInfo:
    pair = "BTC/USD"
    momentum = 0.42
    spread_pct = 0.01
    volume_24h = 1234567.0


class OtherInfo:
    pair = "ETH/USD"
    momentum = 0.10
    spread_pct = 0.02
    volume_24h = 999.0


with tempfile.TemporaryDirectory() as tmp:
    anchored = Path(tmp) / "anchored_proof"
    os.environ["MARGIN_GOAL_PROOF_DIR"] = str(anchored)
    os.chdir(tmp)  # CWD is now the temp dir; a CWD-relative write would land here

    try:
        from aureon.monitors import margin_goal_recorder as mgr

        full = (FakeInfo(), "long", 0.5, 100.0, 5, 0.9, 0.31, 0.36, 0.88, 12.0, 0.77)
        ten = (OtherInfo(), "long", 0.5, 100.0, 5, 0.9, 0.31, 0.36, 0.88, 12.0)   # no route_to_profit
        five = (FakeInfo(), "short", 0.1)                                        # short tuple
        garbage = 42                                                             # not unpackable

        rec = mgr.MarginGoalRecorder()
        try:
            scan_id = rec.record_scan([full, ten, five, garbage], "BTC/USD", "long")
            check("record_scan returns scan_id (no raise on 5-tuple/garbage)",
                  isinstance(scan_id, str) and bool(scan_id))
        except Exception as e:
            check("record_scan returns scan_id (no raise on 5-tuple/garbage)", False, repr(e))
            scan_id = None

        proof = anchored / "margin_goal_proof.jsonl"
        check("proof file written to ANCHORED dir", proof.is_file(), f"missing: {proof}")
        check("no stray proof file in CWD", not (Path(tmp) / "margin_goal_proof.jsonl").exists())

        if proof.is_file() and scan_id:
            line = json.loads(proof.read_text(encoding="utf-8").splitlines()[-1])
            rows = line["candidates"]
            check("all 3 valid candidates recorded (garbage skipped)", len(rows) == 3,
                  f"got {len(rows)}")
            by_rank = {r["rank"]: r for r in rows}
            check("full tuple: route_to_profit preserved",
                  by_rank[1].get("route_to_profit") == 0.77, repr(by_rank.get(1)))
            check("10-tuple: missing route_to_profit -> None",
                  "route_to_profit" in by_rank[2] and by_rank[2]["route_to_profit"] is None)
            check("5-tuple: missing fields -> None, no crash",
                  by_rank[3].get("pair") == "BTC/USD"
                  and by_rank[3].get("goal_score") is None
                  and by_rank[3].get("eta_minutes") is None,
                  repr(by_rank.get(3)))
            check("selected flag set exactly on winner",
                  sum(1 for r in rows if r["selected"]) == 1,
                  repr([r["selected"] for r in rows]))
    finally:
        os.chdir(ORIG_CWD)  # Windows cannot remove a temp dir that is the CWD

# --- SERO_WORKSPACE anchoring (no MARGIN_GOAL_PROOF_DIR override) ---
with tempfile.TemporaryDirectory() as tmp:
    ws = Path(tmp) / "fake_ws"
    (ws / "aureon-os-upstream" / "aureon" / "monitors").mkdir(parents=True)
    src = WORKSPACE / "aureon-os-upstream" / "aureon" / "monitors" / "margin_goal_recorder.py"
    (ws / "aureon-os-upstream" / "aureon" / "monitors" / "margin_goal_recorder.py").write_text(
        src.read_text(encoding="utf-8"), encoding="utf-8")
    os.environ.pop("MARGIN_GOAL_PROOF_DIR", None)
    os.environ["SERO_WORKSPACE"] = str(ws)
    sys.modules.pop("aureon.monitors.margin_goal_recorder", None)
    mgr2 = importlib.import_module("aureon.monitors.margin_goal_recorder")
    check("SERO_WORKSPACE anchor resolves", mgr2._proof_path().parent == ws,
          str(mgr2._proof_path()))
    os.environ.pop("SERO_WORKSPACE", None)

print()
print("ALL PASS" if not failures else f"FAILURES: {failures}")
sys.exit(1 if failures else 0)
