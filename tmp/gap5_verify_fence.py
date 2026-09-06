"""GAP 5 fence verification at handler level (the layer that wraps every
dispatch even when governance is in repair-hold). One-shot; no real
credential paths touched."""
import json
import os
import sys

os.environ["AUREON_SUPPRESS_IMPORT_SIDE_EFFECTS"] = "1"
os.environ["AUREON_AUDIT_MODE"] = "1"
sys.path.insert(0, ".")

from aureon_fusion import pc_activators as pa
from aureon_fusion.paths import WORKSPACE, AUREON_UPSTREAM

r = pa.acquire_pc_control()
assert r["ok"], r
reg = pa._HANDLES["pc_control"]["handle"]


def call(tool, args):
    td = reg.get(tool)
    out = td.handler(dict(args))
    try:
        return json.loads(out)
    except Exception:
        return {"raw": str(out)[:120]}


probe = "aureon_fusion/state/pc_gap5_probe2.txt"
checks = [
    ("A workspace write allowed", call("write_repo_file", {"path": probe, "content": "x\n"}), lambda v: v.get("written") is True),
    ("B upstream write refused", call("write_repo_file", {"path": "aureon-os-upstream/PROBE_GAP5.txt", "content": "x"}), lambda v: v.get("blocked") is True),
    ("B2 upstream traversal refused", call("write_repo_file", {"path": "./aureon-os-upstream/../aureon-os-upstream/P.txt", "content": "x"}), lambda v: v.get("blocked") is True),
    ("C sensitive name refused", call("write_repo_file", {"path": "tmp/probe_secret_token.txt", "content": "x"}), lambda v: v.get("blocked") is True),
    ("C2 abs .env-shaped refused", call("write_repo_file", {"path": str(WORKSPACE / "tmp" / "probe.env"), "content": "x"}), lambda v: v.get("blocked") is True),
    ("D escape refused", call("write_repo_file", {"path": "../../escape_gap5.txt", "content": "x"}), lambda v: v.get("blocked") is True),
    ("E upstream shell > refused", call("execute_shell", {"command": "echo x > aureon-os-upstream/PROBE_GAP5.txt"}), lambda v: v.get("blocked") is True),
    ("E2 upstream shell >> refused", call("execute_shell", {"command": "echo x >> aureon-os-upstream/PROBE_GAP5.txt"}), lambda v: v.get("blocked") is True),
    ("F upstream shell del refused", call("execute_shell", {"command": "del aureon-os-upstream\\x.txt"}), lambda v: v.get("blocked") is True),
    ("F2 upstream shell rm refused", call("execute_shell", {"command": "rm aureon-os-upstream/x.txt"}), lambda v: v.get("blocked") is True),
    ("H workspace read ok", call("read_repo_file", {"path": "AGENTS.md"}), lambda v: len(v.get("text", "")) > 100),
]
allok = True
for name, val, okfn in checks:
    ok = okfn(val)
    allok &= ok
    print(("PASS " if ok else "FAIL "), name, "|", json.dumps(val, ensure_ascii=False)[:110])

print()
print("probe2 written:", (WORKSPACE / probe).exists())
print("upstream PROBE absent:", not (AUREON_UPSTREAM / "PROBE_GAP5.txt").exists())
print("sensitive probes absent:",
      not (WORKSPACE / "tmp/probe_secret_token.txt").exists(),
      not (WORKSPACE / "tmp/probe.env").exists())
print("ALL PASS:", allok)
(WORKSPACE / probe).unlink(missing_ok=True)
