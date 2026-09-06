"""GAP 5 governed-path verification of the pc_control belt (one-shot).
Exercises registry.execute exactly like sovereign_actuator does."""
import json
import os
import sys
import time

os.environ["AUREON_SUPPRESS_IMPORT_SIDE_EFFECTS"] = "1"
os.environ["AUREON_AUDIT_MODE"] = "1"
sys.path.insert(0, ".")

from aureon_fusion import pc_activators as pa
from aureon_fusion.paths import WORKSPACE, AUREON_UPSTREAM

r = pa.acquire_pc_control()
assert r["ok"], r
reg = pa._HANDLES["pc_control"]["handle"]
sys.path.insert(0, str(pa.AUREON_UPSTREAM))
from aureon.core.hnc_field import read_canonical_field
from aureon.inhouse_ai.tool_registry import ToolDispatchProposal


def governed(tool, args):
    td = reg.get(tool)
    prop = ToolDispatchProposal.create(
        tool_call_id=f"gap5-verify-{int(time.time() * 1000)}",
        runner_turn_index=0, response_call_index=0,
        tool_name=tool, arguments=args,
        effect=td.effect, operation_id=td.operation_id,
        tool_definition_digest=td.definition_digest,
        context={"organ": "gap5_verify"})
    field = read_canonical_field()
    try:
        reg.set_hnc_coherence_context(field)
        raw = reg.execute(tool, args, proposal=prop)
    finally:
        clr = getattr(reg, "clear_hnc_coherence_context", None)
        if callable(clr):
            clr()
    try:
        return json.loads(raw)
    except Exception:
        return {"raw": str(raw)[:200]}


probe = "aureon_fusion/state/pc_gap5_probe.txt"
res = {}
res["A workspace write"] = governed(
    "write_repo_file", {"path": probe, "content": "gap5 governed probe\n"})
res["B upstream write"] = governed(
    "write_repo_file", {"path": "aureon-os-upstream/PROBE_GAP5.txt",
                        "content": "x"})
res["C sensitive name"] = governed(
    "write_repo_file", {"path": "tmp/probe_secret_token.txt", "content": "x"})
res["D escape"] = governed(
    "write_repo_file", {"path": "../../escape_gap5.txt", "content": "x"})
res["E upstream shell redirect"] = governed(
    "execute_shell", {"command": "echo x > aureon-os-upstream/PROBE_GAP5.txt"})
res["F upstream shell del"] = governed(
    "execute_shell", {"command": r"del aureon-os-upstream\x.txt"})
res["G read workspace"] = "text" in governed(
    "read_repo_file", {"path": "AGENTS.md"})
for k, v in res.items():
    print(k, "->", json.dumps(v, ensure_ascii=False)[:150])
print()
print("probe written:", (WORKSPACE / probe).exists())
print("upstream PROBE absent:", not (AUREON_UPSTREAM / "PROBE_GAP5.txt").exists())
print("escape absent:", not (WORKSPACE.parent / "escape_gap5.txt").exists())
print("sensitive probe absent:",
      not (WORKSPACE / "tmp/probe_secret_token.txt").exists())
print("ledger entries:", len(reg.blocked_calls))
for bc in reg.blocked_calls:
    print("  -", bc["tool"], "|", bc["reason"][:80])
(WORKSPACE / probe).unlink(missing_ok=True)
