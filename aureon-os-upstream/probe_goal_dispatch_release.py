"""End-to-end probe: goal.submit.request -> GoalDispatchBridge -> engine.

Proves, against the real release record resolution:
  1. HELD   (release record absent)  -> handler raises GOAL_DISPATCH_RELEASE_HOLD,
                                        engine never touched.
  2. RELEASED + conscience APPROVED  -> engine.submit_goal called once.
  3. RELEASED + conscience VETO      -> engine not called, goal.abandoned published.
  4. duplicate goal_id dispatches once; GoalClaims prevents double dispatch.
"""

import json
import os
import sys
from enum import Enum, auto

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from aureon.core.aureon_thought_bus import Thought
from aureon.vault.voice._goal_claims import GoalClaims
from aureon.vault.voice.goal_dispatch_bridge import (
    GOAL_DISPATCH_RELEASE_HOLD,
    GoalDispatchBridge,
)
from aureon.vault.voice import _goal_release

results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond)))
    print(f"  [{'PASS' if cond else 'FAIL'}] {name} {detail}")


class StubBus:
    def __init__(self):
        self.handlers = {}
        self.published = []

    def subscribe(self, topic, handler):
        self.handlers.setdefault(topic, []).append(handler)

    def publish(self, thought):
        self.published.append(thought)


class Whisper:
    def __init__(self, verdict):
        self.verdict = verdict
        self.message = "probe"
        self.why_it_matters = "probe"


class Conscience:
    verdict = None

    def ask_why(self, text, context):
        return Whisper(self.verdict)


class Engine:
    def __init__(self):
        self.calls = []

    def submit_goal(self, text):
        self.calls.append(text)


def submit(bus, payload):
    t = Thought(source="probe", topic="goal.submit.request", payload=payload)
    for h in bus.handlers["goal.submit.request"]:
        h(t)


print("release record candidates:",
      [str(p) for p in _goal_release.release_record_candidates()])
print("release status (real record):",
      _goal_release.release_status("goal_dispatch_bridge"))

# ── 1. HELD: env var points at a nonexistent record ─────────────────────────
os.environ["GOAL_DISPATCH_RELEASE_RECORD"] = os.path.abspath("__no_such__.json")
held_bus, held_engine = StubBus(), Engine()
held_bridge = GoalDispatchBridge(
    thought_bus=held_bus, conscience=Conscience(), goal_engine=held_engine)
try:
    held_bridge.start()
    raised = None
except RuntimeError as e:
    raised = str(e)
check("held: start() raises GOAL_DISPATCH_RELEASE_HOLD",
      raised == GOAL_DISPATCH_RELEASE_HOLD, repr(raised))
check("held: stats reports HOLD", held_bridge.stats()["status"] == "HOLD")
check("held: engine untouched", held_engine.calls == [])

# ── 2-4. RELEASED: point env var at the real workspace record ────────────────
real = None
for cand in _goal_release.release_record_candidates():
    pass  # env var currently overrides; recompute without it
del os.environ["GOAL_DISPATCH_RELEASE_RECORD"]
for cand in _goal_release.release_record_candidates():
    if cand.is_file():
        real = cand
        break
assert real is not None, "real release record not found"
os.environ["GOAL_DISPATCH_RELEASE_RECORD"] = str(real)
print("using release record:", real)

class V(Enum):
    APPROVED = auto()
    VETO = auto()

Conscience.verdict = V.APPROVED
bus, engine = StubBus(), Engine()
bridge = GoalDispatchBridge(
    thought_bus=bus, conscience=Conscience(), goal_engine=engine)
bridge._run_in_thread = False
bridge.start()
check("released: subscribed to goal.submit.request",
      "goal.submit.request" in bus.handlers)
check("released: stats reports RELEASED", bridge.stats()["status"] == "RELEASED")

submit(bus, {"goal_id": "probe-1", "text": "build the evidence dashboard",
             "proposed_by_persona": "engineer"})
check("released+approved: engine dispatched once",
      engine.calls == ["build the evidence dashboard"], repr(engine.calls))
check("released+approved: stats dispatched==1", bridge.stats()["dispatched"] == 1)

submit(bus, {"goal_id": "probe-1", "text": "build the evidence dashboard"})
check("released: duplicate goal_id not re-dispatched", engine.calls == [
      "build the evidence dashboard"])

GoalClaims.claim("probe-2", "skill_executor_bridge")
submit(bus, {"goal_id": "probe-2", "text": "claimed goal"})
check("released: GoalClaims-claimed goal skipped", engine.calls == [
      "build the evidence dashboard"])

Conscience.verdict = V.VETO
submit(bus, {"goal_id": "probe-3", "text": "vetoed goal"})
check("released+veto: engine not called", engine.calls == [
      "build the evidence dashboard"])
abandoned = [t for t in bus.published if t.topic == "goal.abandoned"]
check("released+veto: goal.abandoned published", len(abandoned) == 1
      and abandoned[0].payload["goal_id"] == "probe-3")
check("released+veto: stats vetoed==1", bridge.stats()["vetoed"] == 1)

print(json.dumps({"checks": len(results),
                  "failed": sum(1 for _, ok in results if not ok)}))
sys.exit(1 if any(not ok for _, ok in results) else 0)
