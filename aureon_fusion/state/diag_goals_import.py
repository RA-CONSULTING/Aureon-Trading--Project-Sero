"""Diagnostic: capture the REAL exception queen_mind's _goals_stage swallows.

Imports aureon_fusion.queen_mind under AUREON_SUPPRESS_IMPORT_SIDE_EFFECTS=1
(exactly like her process), stubs the events spine, then replays the stage's
lazy import + call against the REAL aureon_fusion.goals_will with a
traceback print. Nothing here writes to her runtime state.
"""

import os
import sys
import traceback

os.environ["AUREON_SUPPRESS_IMPORT_SIDE_EFFECTS"] = "1"
os.environ["AUREON_AUDIT_MODE"] = "1"

WS = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if WS not in sys.path:
    sys.path.insert(0, WS)

print("cwd:", os.getcwd())
print("sys.path[0:4]:", sys.path[:4])

import aureon_fusion                                  # noqa: E402
from aureon_fusion import queen_mind as qm            # noqa: E402

# silence the spine (chirp notes must not touch live bus state)
import types                                          # noqa: E402
_silent = types.ModuleType("aureon_fusion.events")
_silent.chirp = lambda *a, **k: None
_silent.publish_event = lambda *a, **k: None
sys.modules["aureon_fusion.events"] = _silent
aureon_fusion.events = _silent

print("queen_mind module file:", qm.__file__)

print("\n-- step 1: plain `import aureon_fusion.goals_will` --")
try:
    import aureon_fusion.goals_will as gw
    print("   OK ->", gw.__file__)
except Exception:
    traceback.print_exc()

print("\n-- step 2: `from aureon_fusion import goals_will` + consider() --")
try:
    from aureon_fusion import goals_will
    out = goals_will.consider(dry_run=True)
    print("   OK ->", out)
except Exception:
    traceback.print_exc()

print("\n-- step 3: the stage exactly as she runs it (with traceback hook) --")
mind = object.__new__(qm.QueenMind)
try:
    from aureon_fusion import goals_will as g2
    considered = g2.consider()
    print("   OK ->", considered)
except Exception:
    traceback.print_exc()

print("\n-- step 4: her actual _goals_stage result --")
res = mind._goals_stage(cycle=0, publish=False)
print("   result:", res)

print("\n-- step 5: compare with grand_wheel import in the same process --")
try:
    from aureon_fusion import grand_wheel
    snap = grand_wheel.snapshot()
    print("   wheel OK -> hq =", snap.get("happiness_quotient"),
          "fresh =", snap.get("fresh"))
except Exception:
    traceback.print_exc()

print("\n-- step 6: how was her module loaded? __main__ twin check --")
print("   'aureon_fusion.queen_mind' in sys.modules:",
      "aureon_fusion.queen_mind" in sys.modules)
print("   '__main__' is queen_mind:", getattr(sys.modules.get("__main__"),
                                              "__file__", None))
