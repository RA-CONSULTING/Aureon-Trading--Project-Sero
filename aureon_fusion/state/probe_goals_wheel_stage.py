"""Probe for the queen_mind goals/wheel metacognitive stage (W7 wiring).

Loads aureon_fusion.queen_mind with AUREON_SUPPRESS_IMPORT_SIDE_EFFECTS=1,
builds a bare QueenMind instance (no faculty wake), and exercises the two
new stage methods under three regimes:

  1. success  — stub goals_will + grand_wheel injected via sys.modules
  2. raising  — stubs present but consider()/snapshot() raise
  3. absent   — stubs removed (ImportError path)

It also no-ops aureon_fusion.events so the fail-closed chirp notes never
touch the live spine, and reproduces the exact run() cycle-line format to
show the hq= token placement.

Read-only with respect to queen_mind runtime state: no cycle_once(), no
state saves, no reports.jsonl writes.
"""

import json
import os
import sys
import types

os.environ["AUREON_SUPPRESS_IMPORT_SIDE_EFFECTS"] = "1"
os.environ["AUREON_AUDIT_MODE"] = "1"

WS = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))           # workspace root
if WS not in sys.path:
    sys.path.insert(0, WS)

import aureon_fusion                                  # noqa: E402
from aureon_fusion import queen_mind as qm            # noqa: E402

# silence the spine: the note helpers must not touch live bus state
_silent_events = types.ModuleType("aureon_fusion.events")
_silent_events.chirp = lambda *a, **k: None
_silent_events.publish_event = lambda *a, **k: None
sys.modules["aureon_fusion.events"] = _silent_events
aureon_fusion.events = _silent_events

STUB_GOALS = "aureon_fusion.goals_will"
STUB_WHEEL = "aureon_fusion.grand_wheel"


def _install_stubs(goals_raise=False, wheel_raise=False):
    g = types.ModuleType(STUB_GOALS)
    if goals_raise:
        def _consider():
            raise RuntimeError("goals organ on fire")
    else:
        def _consider():
            return {
                "considered": True,
                "reason": "novelty threshold crossed",
                "outcome": "adopted",
                "gates": {"conscience": "clear", "hnc": 0.42,
                          "capability": "allowed"},
            }
    g.consider = _consider
    w = types.ModuleType(STUB_WHEEL)
    if wheel_raise:
        def _snapshot():
            raise ValueError("wheel stuck")
    else:
        def _snapshot():
            return {
                "ts": 1750000000.0,
                "happiness_quotient": 0.61,
                "subconscious_bias": -0.07,
                "pillars": {"coherence": {"value": 0.8, "fresh": True,
                                          "source": "hnc"}},
                "fresh": True,
            }
    w.snapshot = _snapshot
    sys.modules[STUB_GOALS] = g
    sys.modules[STUB_WHEEL] = w
    setattr(aureon_fusion, "goals_will", g)
    setattr(aureon_fusion, "grand_wheel", w)


def _remove_stubs():
    for name, attr in ((STUB_GOALS, "goals_will"),
                       (STUB_WHEEL, "grand_wheel")):
        sys.modules.pop(name, None)
        if hasattr(aureon_fusion, attr):
            delattr(aureon_fusion, attr)


def _bare_mind():
    # the stage methods touch no instance state beyond _goals_note
    return object.__new__(qm.QueenMind)


def _cycle_line(report):
    """Byte-for-byte replica of the run() cycle-line builder (post-edit)."""
    flag = " ⚠" if report["anomalies"] else ""
    gamma = report["gamma"]
    gamma_s = f"{gamma:.4f}" if gamma is not None else "—"
    learn = report.get("learning_will") or {}
    learn_outcome = learn.get("outcome")
    learn_s = (f" learn={learn_outcome}" if learn_outcome not in
               (None, "unavailable", "no_intent") else "")
    doors = report.get("doors") or {}
    doors_action = doors.get("action")
    doors_s = (f" doors={doors_action}:{doors.get('door')}"
               if doors_action not in (None, "none") else "")
    wheel_hq = qm._finite((report.get("wheel") or {}).get(
        "happiness_quotient"))
    wheel_s = f" hq={wheel_hq:.2f}" if wheel_hq is not None else ""
    return (f"👑 cycle {report['cycle']:<5} {report['action']:<7} "
            f"persona={report['persona']:<5} Γ={gamma_s} "
            f"organs={len(report['organs']['running'])}"
            f" narr={report['narration_source']}{flag}{learn_s}"
            f"{doors_s}{wheel_s}")


def main():
    mind = _bare_mind()
    ok = True

    def check(label, cond):
        nonlocal ok
        print(f"  [{'PASS' if cond else 'FAIL'}] {label}")
        ok = ok and cond

    print("== path 0: REAL aureon_fusion.goals_will (no stub) ==")
    _remove_stubs()
    goals = mind._goals_stage(cycle=0, publish=False)
    wheel = mind._wheel_stage(cycle=0)
    print("  goals =", json.dumps(goals, default=str))
    print("  wheel hq =", (wheel or {}).get("happiness_quotient"),
          "fresh =", (wheel or {}).get("fresh"))
    check("goals is not the unavailable sentinel", "error" not in goals)
    check("goals.reason non-empty", bool(goals.get("reason")))
    check("goals considered flag is a bool",
          isinstance(goals.get("considered"), bool))
    check("wheel still works alongside", wheel is not None
          and wheel.get("happiness_quotient") is not None)

    print("== path 1: success (stubbed goals_will + grand_wheel) ==")
    _install_stubs()
    goals = mind._goals_stage(cycle=1, publish=False)
    wheel = mind._wheel_stage(cycle=1)
    print("  goals =", json.dumps(goals, default=str))
    print("  wheel =", json.dumps(wheel, default=str))
    check("goals.considered is True", goals.get("considered") is True)
    check("goals.reason recorded", goals.get("reason") == "novelty threshold crossed")
    check("goals gate/outcome fields carried through",
          goals.get("outcome") == "adopted" and isinstance(goals.get("gates"), dict))
    check("wheel.happiness_quotient == 0.61",
          wheel.get("happiness_quotient") == 0.61)
    check("wheel.subconscious_bias == -0.07",
          wheel.get("subconscious_bias") == -0.07)
    check("wheel.fresh is True", wheel.get("fresh") is True)

    line = _cycle_line({
        "cycle": 42, "action": "EXECUTE", "persona": "sage",
        "gamma": 0.8123, "organs": {"running": [1, 2, 3]},
        "narration_source": "native", "anomalies": [],
        "learning_will": {"outcome": "refused"},
        "doors": {"action": "none"}, "wheel": wheel,
    })
    print("  line  =", line)
    check("cycle line ends with hq=0.61", line.endswith(" hq=0.61"))
    check("existing tokens intact (learn=refused)",
          " learn=refused" in line and " doors=" not in line)

    print("== path 1b: class-only organ (GoalsWill, no module consider) ==")
    gcls = types.ModuleType(STUB_GOALS)

    class FakeGoalsWill:
        def consider(self, dry_run=False):
            return {"considered": False, "outcome": "open_goals_active",
                    "reason": "stub goals open"}

    gcls.GoalsWill = FakeGoalsWill
    sys.modules[STUB_GOALS] = gcls
    aureon_fusion.goals_will = gcls
    goals = mind._goals_stage(cycle=1, publish=False)
    print("  goals =", json.dumps(goals, default=str))
    check("class-only organ consulted (the original bug shape)",
          goals.get("reason") == "stub goals open")
    check("no unavailable sentinel on class-only shape", "error" not in goals)
    _remove_stubs()

    print("== path 2: components raise ==")
    _install_stubs(goals_raise=True, wheel_raise=True)
    goals = mind._goals_stage(cycle=2, publish=False)
    wheel = mind._wheel_stage(cycle=2)
    print("  goals =", json.dumps(goals, default=str))
    print("  wheel =", wheel)
    check("goals degraded to fail-closed dict",
          goals == {"considered": False, "error": "unavailable"})
    check("wheel degraded to None", wheel is None)

    line = _cycle_line({
        "cycle": 43, "action": "EXECUTE", "persona": "sage",
        "gamma": 0.8123, "organs": {"running": [1, 2, 3]},
        "narration_source": "native", "anomalies": [],
        "learning_will": {"outcome": "refused"},
        "doors": {"action": "none"}, "wheel": wheel,
    })
    print("  line  =", line)
    check("no hq= token when wheel is None", "hq=" not in line)

    print("== path 3: components absent (ImportError) ==")
    _remove_stubs()
    # None in sys.modules makes `from aureon_fusion import X` raise
    # ImportError even when the .py exists on disk — true absence
    sys.modules[STUB_GOALS] = None
    sys.modules[STUB_WHEEL] = None
    goals = mind._goals_stage(cycle=3, publish=False)
    wheel = mind._wheel_stage(cycle=3)
    sys.modules.pop(STUB_GOALS, None)
    sys.modules.pop(STUB_WHEEL, None)
    print("  goals =", json.dumps(goals, default=str))
    print("  wheel =", wheel)
    check("goals fail-closed on ImportError",
          goals == {"considered": False, "error": "unavailable"})
    check("wheel None on ImportError", wheel is None)
    check("goals dict is JSON-serializable",
          bool(json.dumps(goals)) and json.dumps(None) == "null")

    print()
    print("ALL PASS" if ok else "FAILURES PRESENT")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
