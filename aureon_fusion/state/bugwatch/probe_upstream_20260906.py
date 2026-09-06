"""GAP 3 probe driver — runs the named upstream majors through
aureon_fusion.upstream_probe in isolated subprocesses (one per module,
120s hard timeout, py-spy dump on hang). Results land in
aureon_fusion/state/upstream_probe_20260906/results.json.

One-off build tooling for the 2026-09-06 GAP 3 census doors; not an organ.
"""

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path(r"C:\Users\user\.kimi_openclaw\workspace")
RESULTS_DIR = WORKSPACE / "aureon_fusion" / "state" / "upstream_probe_20260906"
RESULTS_FILE = RESULTS_DIR / "results.json"
HARD_TIMEOUT = 120

CLUSTERS = {
    "unified_ecosystem": "aureon.trading.aureon_unified_ecosystem",
    "queen_quantum_frog": "aureon.queen.queen_quantum_frog",
    "unified_market_trader": "aureon.exchanges.unified_market_trader",
    "gold_capital_intelligence_company":
        "aureon.autonomous.aureon_gold_capital_intelligence_company",
    "pro_dashboard": "aureon.monitors.aureon_pro_dashboard",
    "command_centers": "aureon.command_centers.aureon_command_center",
    "gaia_reclaimers": "aureon.bots.gaia_planetary_reclaimer",
    "full_autonomy": "aureon.autonomous.aureon_full_autonomy",
    "vault": "aureon.vault.aureon_vault",
    "simulation": "aureon.simulation.aureon_hnc_simulation",
    "saas": "aureon.saas.catalog",
    "grants": "aureon.grants",
    "true_consciousness": "aureon.utils.aureon_queen_true_consciousness",
    "self_awareness": "aureon.intelligence.aureon_self_awareness",
    "sentient_loop": "aureon.queen.queen_sentient_loop",
}

ENV = dict(os.environ)
ENV["AUREON_SUPPRESS_IMPORT_SIDE_EFFECTS"] = "1"
ENV["AUREON_AUDIT_MODE"] = "1"


def _py_spy_dump(pid: int) -> str:
    try:
        proc = subprocess.run(
            ["py-spy", "dump", "--pid", str(pid)],
            capture_output=True, text=True, timeout=30)
        return ((proc.stdout or "") + (proc.stderr or ""))[:3000]
    except Exception as exc:  # noqa: BLE001
        return f"py-spy unavailable: {type(exc).__name__}"


def probe(cluster: str, module: str) -> dict:
    cmd = [sys.executable, "-X", "utf8", "-m", "aureon_fusion.upstream_probe",
           module, "--timeout", str(HARD_TIMEOUT - 15)]
    rec = {"cluster": cluster, "module": module, "started_at":
           datetime.now(timezone.utc).isoformat()}
    t0 = time.monotonic()
    try:
        proc = subprocess.Popen(
            cmd, cwd=str(WORKSPACE), env=ENV,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace")
        try:
            out, err = proc.communicate(timeout=HARD_TIMEOUT)
        except subprocess.TimeoutExpired:
            rec["pyspy"] = _py_spy_dump(proc.pid)
            proc.kill()
            out, err = proc.communicate()
            rec.update(ok=False, error_type="HardTimeout",
                       error=f"process exceeded {HARD_TIMEOUT}s hard timeout",
                       wall_s=round(time.monotonic() - t0, 1), rc=None)
            return rec
        rec["wall_s"] = round(time.monotonic() - t0, 1)
        rec["rc"] = proc.returncode
        if out.strip():
            marker = "__AUREON_PROBE_JSON__"
            payload = out.split(marker, 1)[1] if marker in out else out
            try:
                rec.update(json.loads(payload))
            except json.JSONDecodeError:
                rec["raw_stdout"] = out[-800:]
        if proc.returncode != 0 and err.strip():
            rec["stderr_tail"] = err[-800:]
        return rec
    except Exception as exc:  # noqa: BLE001
        rec.update(ok=False, error_type=type(exc).__name__, error=str(exc)[:300],
                   wall_s=round(time.monotonic() - t0, 1))
        return rec


def main() -> int:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    results = []
    for cluster, module in CLUSTERS.items():
        rec = probe(cluster, module)
        results.append(rec)
        ok = rec.get("ok")
        print(f"[{len(results):>2}/{len(CLUSTERS)}] {cluster:<36} "
              f"{'OK' if ok else 'FAIL'} "
              f"{rec.get('error_type', '')} {rec.get('wall_s')}s", flush=True)
        RESULTS_FILE.write_text(json.dumps({
            "driver": "probe_upstream_20260906",
            "hard_timeout_s": HARD_TIMEOUT,
            "finished": len(results) == len(CLUSTERS),
            "results": results}, indent=2, ensure_ascii=False),
            encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
