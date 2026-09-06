#!/usr/bin/env python3
"""One-hour flight recorder — samples fleet health every 60 s to JSONL."""
import json, os, subprocess, sys, time
from datetime import datetime, timezone
from pathlib import Path

WS = Path(r"C:\Users\user\.kimi_openclaw\workspace")
OUT = WS / "aureon_fusion" / "state" / "bugwatch"
OUT.mkdir(parents=True, exist_ok=True)
REC = OUT / "recorder.jsonl"
DEADLINE = time.time() + 65 * 60
ENV = dict(os.environ, AUREON_SUPPRESS_IMPORT_SIDE_EFFECTS="1",
           AUREON_AUDIT_MODE="1")

LOGS = [
    ("queen_mind", "logs/organ_queen_mind.log"),
    ("hnc_core", "logs/organ_hnc_core.log"),
    ("soul_daemon", "logs/organ_soul_protection_daemon.log"),
    ("radar_suite", "logs/organ_aureon_radar_suite.log"),
    ("radar_bridge", "logs/organ_aureon_radar_bridge.log"),
    ("schumann", "logs/organ_schumann_real_daemon.log"),
    ("data_feeder", "logs/organ_real_time_data_feeder.log"),
    ("space_weather", "logs/organ_sero_space_weather.log"),
    ("expansion", "logs/organ_sero_autonomous_expansion.log"),
    ("selfq", "logs/organ_self_questioning_ai.log"),
]
ERR_RE = ("Traceback", "ERROR", "CRITICAL", "Exception", "🚨")

def log_err_counts():
    counts = {}
    for name, rel in LOGS:
        p = WS / rel
        if not p.exists():
            counts[name] = -1
            continue
        try:
            data = p.read_bytes()[-200_000:].decode("utf-8", "replace")
            counts[name] = sum(data.count(e) for e in ERR_RE)
        except Exception:
            counts[name] = -2
    return counts

def file_age_s(rel):
    p = WS / rel
    try:
        return round(time.time() - p.stat().st_mtime, 1)
    except Exception:
        return None

def journal_counts():
    out = {}
    for rel in ("aureon_fusion/state/learning_will/journal.jsonl",
                "aureon_fusion/state/doors/journal.jsonl"):
        p = WS / rel
        try:
            out[Path(rel).parent.name + "_journal"] = sum(
                1 for l in p.read_text(encoding="utf-8", errors="replace").splitlines()
                if l.strip().startswith("{"))
        except Exception:
            out[Path(rel).parent.name + "_journal"] = None
    return out

sample_i = 0
while time.time() < DEADLINE:
    sample_i += 1
    rec = {"ts": datetime.now(timezone.utc).isoformat(), "i": sample_i}
    try:
        r = subprocess.run(
            [sys.executable, "-m", "aureon_fusion.organ_registry", "status"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=120, cwd=str(WS), env=ENV)
        rec["organs_green"] = r.stdout.count("🟢")
        rec["organs_down"] = r.stdout.count("🔴") + r.stdout.count("🟡")
        if r.returncode != 0:
            rec["registry_stderr"] = (r.stderr or "")[-200:]
    except Exception as e:
        rec["registry_error"] = type(e).__name__
    rec["log_err_counts"] = log_err_counts()
    rec["ages"] = {
        "fused_signals": file_age_s("aureon_radar/fused_signals.jsonl"),
        "schumann_state": file_age_s("schumann_state.json"),
        "hnc_state": file_age_s("aureon_fusion/state/hnc_core_state.json"),
        "knowledge_dataset": file_age_s("aureon_fusion/state/queen_mind/knowledge_dataset.json"),
        "real_time_data": file_age_s("real_time_data.json"),
    }
    try:
        hnc = json.loads((WS / "aureon_fusion/state/hnc_core_state.json").read_text(encoding="utf-8"))
        rec["gamma"] = hnc.get("coherence_gamma")
        rec["lambda_t"] = hnc.get("lambda_t")
    except Exception:
        pass
    rec.update(journal_counts())
    with open(REC, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    time.sleep(60)

with open(OUT / "DONE", "w") as f:
    f.write("recorder finished\n")
