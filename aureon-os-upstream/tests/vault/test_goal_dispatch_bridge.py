"""Fail-closed + released-path tests for GoalDispatchBridge.

The bridge's release state is read from a release record
(``aureon_fusion/state/goals/dispatch_release.json``, overridable via the
``GOAL_DISPATCH_RELEASE_RECORD`` env var). Every HOLD-behavior test here
drives the hold by pointing that env var at a path that does NOT exist —
proving the fail-closed property (no record → every effect method still
raises ``GOAL_DISPATCH_RELEASE_HOLD``). The released-path tests write a
valid record to a tmp file and point the env var at it.
"""

from __future__ import annotations

import json
from enum import Enum, auto
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

from aureon.vault.voice import goal_dispatch_bridge as bridge_module
from aureon.vault.voice._goal_claims import GoalClaims
from aureon.vault.voice.goal_dispatch_bridge import (
    GOAL_DISPATCH_RELEASE_HOLD,
    GoalDispatchBridge,
    get_goal_dispatch_bridge,
    reset_goal_dispatch_bridge,
)


class _Trap:
    def __getattribute__(self, _name: str) -> Any:
        raise AssertionError("release-held goal bridge touched an effect owner")


def _write_release_record(path: Path, *modules: str) -> Path:
    path.write_text(json.dumps({
        "ts": "2026-09-06",
        "source": "owner decree 2026-09-06 (Gary Leckey)",
        "modules": list(modules),
    }), encoding="utf-8")
    return path


@pytest.fixture
def held(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Point the release record at a path that does not exist → HOLD."""
    missing = tmp_path / "no_such_release.json"
    monkeypatch.setenv("GOAL_DISPATCH_RELEASE_RECORD", str(missing))
    return missing


@pytest.fixture
def released(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Point the release record at a valid record naming the bridge."""
    record = _write_release_record(
        tmp_path / "dispatch_release.json", "goal_dispatch_bridge")
    monkeypatch.setenv("GOAL_DISPATCH_RELEASE_RECORD", str(record))
    return record


@pytest.fixture(autouse=True)
def _clean_claims():
    GoalClaims.clear()
    yield
    GoalClaims.clear()


# ─── HOLD behavior (driven by an absent release record) ─────────────────────


def test_hold_without_release_record_is_fail_closed(held: Path) -> None:
    assert not held.exists()
    bridge = GoalDispatchBridge(
        thought_bus=_Trap(), conscience=_Trap(), goal_engine=_Trap(),
        vault=_Trap(),
    )
    stats = bridge.stats()
    assert stats["status"] == "HOLD"
    assert stats["reason_code"] == "production_magic_star_release_unavailable"
    assert stats["production_ready"] is False
    assert stats["effect_enabled"] is False
    assert stats["dispatched"] == 0
    assert stats["vetoed"] == 0
    assert stats["abandoned"] == 0


def test_start_and_intake_hold_when_record_absent(
    held: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "aureon.vault.voice.goal_dispatch_bridge.threading.Thread",
        lambda *_args, **_kwargs: pytest.fail("goal bridge must not create a thread"),
    )
    bridge = GoalDispatchBridge(
        thought_bus=_Trap(), conscience=_Trap(), goal_engine=_Trap(),
        vault=_Trap(),
    )
    with pytest.raises(RuntimeError, match="goal_dispatch_bridge_hold"):
        bridge.start()
    with pytest.raises(RuntimeError, match="goal_dispatch_bridge_hold"):
        bridge._on_submit_request(_Trap())
    assert bridge._dispatched == set()
    assert bridge.stats()["subscribed"] is False


@pytest.mark.parametrize(
    "call_name",
    ["dispatch", "engine", "abandon", "unavailable", "publish"],
)
def test_direct_effect_helpers_hold_when_record_absent(
    held: Path, call_name: str
) -> None:
    bridge = GoalDispatchBridge(
        thought_bus=_Trap(), conscience=_Trap(), goal_engine=_Trap(),
    )
    calls = {
        "dispatch": lambda: bridge._dispatch("g", "goal", {}, {}),
        "engine": lambda: bridge._run_engine_submit("g", "goal"),
        "abandon": lambda: bridge._publish_abandoned("g", "reason"),
        "unavailable": lambda: bridge._publish_dispatch_unavailable("g", "goal"),
        "publish": lambda: bridge._publish("topic", {"x": 1}),
    }
    with pytest.raises(RuntimeError, match="goal_dispatch_bridge_hold"):
        calls[call_name]()
    assert bridge.stats()["dispatched"] == 0
    assert bridge.stats()["vetoed"] == 0
    assert bridge.stats()["abandoned"] == 0


def test_malformed_or_unnaming_record_still_holds(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("{ not json", encoding="utf-8")
    monkeypatch.setenv("GOAL_DISPATCH_RELEASE_RECORD", str(bad))
    bridge = GoalDispatchBridge(goal_engine=_Trap())
    with pytest.raises(RuntimeError, match="goal_dispatch_bridge_hold"):
        bridge._run_engine_submit("g", "goal")

    other = _write_release_record(tmp_path / "other.json", "goal_skill_aligner")
    monkeypatch.setenv("GOAL_DISPATCH_RELEASE_RECORD", str(other))
    with pytest.raises(RuntimeError, match="goal_dispatch_bridge_hold"):
        bridge._run_engine_submit("g", "goal")


def test_singleton_getter_holds_when_record_absent(held: Path) -> None:
    reset_goal_dispatch_bridge()
    assert bridge_module._singleton is None
    with pytest.raises(RuntimeError, match="goal_dispatch_bridge_hold"):
        get_goal_dispatch_bridge(
            thought_bus=_Trap(), conscience=_Trap(), goal_engine=_Trap(),
        )
    assert bridge_module._singleton is None
    reset_goal_dispatch_bridge()


# ─── Pure helpers (unchanged by release state) ───────────────────────────────


def test_context_building_is_pure_and_bounded() -> None:
    class Vault:
        current_symbolic_life_score = 1.7

    bridge = GoalDispatchBridge(vault=Vault())
    context = bridge._build_context({
        "goal_id": "g",
        "proposed_by_persona": "engineer",
        "urgency": 0.8,
        "parameters": {"risk": 0.2, "leverage": 2, "ignored": "x"},
    })
    assert context == {
        "persona": "engineer",
        "goal_id": "g",
        "urgency": 0.8,
        "symbolic_life_score": 1.0,
        "risk": 0.2,
        "leverage": 2,
    }


def test_verdict_and_reason_helpers_are_pure() -> None:
    class Verdict(Enum):
        VETO = auto()

    class Whisper:
        verdict = Verdict.VETO
        message = "stop"
        why_it_matters = "unsafe"

    assert GoalDispatchBridge._verdict_label(Whisper()) == "VETO"
    assert GoalDispatchBridge._whisper_reason(Whisper()) == "stop | unsafe"


# ─── Released path ───────────────────────────────────────────────────────────


class _StubBus:
    """Minimal ThoughtBus stand-in: records subscribed handlers and
    captures published thoughts."""

    def __init__(self) -> None:
        self.handlers: Dict[str, list] = {}
        self.published: List[Any] = []

    def subscribe(self, topic: str, handler) -> None:
        self.handlers.setdefault(topic, []).append(handler)

    def publish(self, *args: Any, **kwargs: Any) -> None:
        if args:
            self.published.append(args[0])
        else:
            self.published.append(kwargs)


class _StubThought:
    def __init__(self, payload: Dict[str, Any]) -> None:
        self.payload = payload
        self.topic = "goal.submit.request"


class _Whisper:
    def __init__(self, verdict: Any, message: str = "", why: str = "") -> None:
        self.verdict = verdict
        self.message = message
        self.why_it_matters = why


class _StubConscience:
    def __init__(self, verdict: Any = None, fail: bool = False,
                 message: str = "", why: str = "") -> None:
        self.verdict = verdict
        self.fail = fail
        self.message = message
        self.why = why
        self.asked: List[tuple] = []

    def ask_why(self, text: str, context: Dict[str, Any]) -> Any:
        self.asked.append((text, context))
        if self.fail:
            raise RuntimeError("conscience down")
        if self.verdict is None:
            return None
        return _Whisper(self.verdict, self.message, self.why)


class _StubEngine:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.submitted: List[str] = []

    def submit_goal(self, text: str) -> None:
        if self.fail:
            raise RuntimeError("engine boom")
        self.submitted.append(text)


def _make_released_bridge(bus: _StubBus, conscience: Any, engine: Any,
                          run_in_thread: bool = False) -> GoalDispatchBridge:
    bridge = GoalDispatchBridge(
        thought_bus=bus, conscience=conscience, goal_engine=engine,
    )
    bridge._run_in_thread = run_in_thread
    bridge.start()
    return bridge


def _submit(bus: _StubBus, payload: Dict[str, Any]) -> None:
    for handler in bus.handlers["goal.submit.request"]:
        handler(_StubThought(payload))


def test_released_bridge_subscribes_and_reports_released(released: Path) -> None:
    bus = _StubBus()
    bridge = _make_released_bridge(bus, _StubConscience(), _StubEngine())
    assert "goal.submit.request" in bus.handlers
    stats = bridge.stats()
    assert stats["status"] == "RELEASED"
    assert stats["production_ready"] is True
    assert stats["effect_enabled"] is True
    assert stats["subscribed"] is True


def test_released_dispatch_reaches_engine_on_conscience_pass(
    released: Path,
) -> None:
    bus = _StubBus()
    engine = _StubEngine()
    conscience = _StubConscience(verdict="APPROVED")
    bridge = _make_released_bridge(bus, conscience, engine)

    _submit(bus, {"goal_id": "g1", "text": "build the safer dashboard",
                  "proposed_by_persona": "engineer", "urgency": 0.7})

    assert engine.submitted == ["build the safer dashboard"]
    assert conscience.asked, "conscience gate must be consulted"
    text, context = conscience.asked[0]
    assert text == "build the safer dashboard"
    assert context["persona"] == "engineer"
    assert bridge.stats()["dispatched"] == 1
    assert bridge.stats()["vetoed"] == 0


def test_released_dispatch_refuses_on_conscience_veto(released: Path) -> None:
    class _V(Enum):
        VETO = auto()

    bus = _StubBus()
    engine = _StubEngine()
    conscience = _StubConscience(
        verdict=_V.VETO, message="stop", why="unsafe substrate")
    bridge = _make_released_bridge(bus, conscience, engine)

    _submit(bus, {"goal_id": "g2", "text": "risky move",
                  "proposed_by_persona": "scout"})

    assert engine.submitted == [], "vetoed goal must never reach the engine"
    abandoned = [t for t in bus.published
                 if getattr(t, "topic", None) == "goal.abandoned"]
    assert len(abandoned) == 1
    assert abandoned[0].payload["goal_id"] == "g2"
    assert "stop | unsafe substrate" in abandoned[0].payload["reason"]
    assert bridge.stats()["vetoed"] == 1
    assert bridge.stats()["dispatched"] == 0


def test_released_dispatch_fail_closed_without_conscience(released: Path) -> None:
    bus = _StubBus()
    engine = _StubEngine()
    bridge = _make_released_bridge(bus, None, engine)

    _submit(bus, {"goal_id": "g3", "text": "un gated goal"})

    assert engine.submitted == [], "missing conscience must never fail open"
    abandoned = [t for t in bus.published
                 if getattr(t, "topic", None) == "goal.abandoned"]
    assert len(abandoned) == 1
    assert "conscience_gate_unavailable" in abandoned[0].payload["reason"]


def test_released_dispatch_fail_closed_on_conscience_error(
    released: Path,
) -> None:
    bus = _StubBus()
    engine = _StubEngine()
    conscience = _StubConscience(fail=True)
    bridge = _make_released_bridge(bus, conscience, engine)

    _submit(bus, {"goal_id": "g4", "text": "goal while conscience down"})

    assert engine.submitted == [], "failing conscience must never fail open"
    abandoned = [t for t in bus.published
                 if getattr(t, "topic", None) == "goal.abandoned"]
    assert len(abandoned) == 1
    assert "conscience_gate_error" in abandoned[0].payload["reason"]


def test_released_fusion_hook_veto_refuses_dispatch(
    released: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A VETO from aureon_fusion.conscience_hook (second opinion) refuses
    dispatch even when the primary conscience passes."""
    import sys
    import types as _types

    fake_hook = _types.ModuleType("aureon_fusion.conscience_hook")

    def _evaluate(action_desc: str, context: Optional[dict] = None) -> dict:
        return {"verdict": "VETO", "reasoning": "organism-level veto"}

    fake_hook.evaluate = _evaluate  # type: ignore[attr-defined]
    pkg = _types.ModuleType("aureon_fusion")
    monkeypatch.setitem(sys.modules, "aureon_fusion", pkg)
    monkeypatch.setitem(sys.modules, "aureon_fusion.conscience_hook", fake_hook)

    bus = _StubBus()
    engine = _StubEngine()
    conscience = _StubConscience(verdict="APPROVED")
    bridge = _make_released_bridge(bus, conscience, engine)

    _submit(bus, {"goal_id": "g5", "text": "organism-vetoed goal"})

    assert engine.submitted == []
    abandoned = [t for t in bus.published
                 if getattr(t, "topic", None) == "goal.abandoned"]
    assert len(abandoned) == 1
    assert "fusion conscience veto" in abandoned[0].payload["reason"]
    assert bridge.stats()["vetoed"] == 1


def test_released_duplicate_goal_id_dispatches_once(released: Path) -> None:
    bus = _StubBus()
    engine = _StubEngine()
    conscience = _StubConscience(verdict="APPROVED")
    bridge = _make_released_bridge(bus, conscience, engine)

    payload = {"goal_id": "g6", "text": "dedup me"}
    _submit(bus, payload)
    _submit(bus, dict(payload))

    assert engine.submitted == ["dedup me"]
    assert bridge.stats()["dispatched"] == 1


def test_released_claimed_goal_id_is_skipped(released: Path) -> None:
    GoalClaims.claim("g7", "skill_executor_bridge")
    bus = _StubBus()
    engine = _StubEngine()
    conscience = _StubConscience(verdict="APPROVED")
    bridge = _make_released_bridge(bus, conscience, engine)

    _submit(bus, {"goal_id": "g7", "text": "already claimed"})

    assert engine.submitted == []
    assert conscience.asked == []


def test_released_empty_text_abandons(released: Path) -> None:
    bus = _StubBus()
    engine = _StubEngine()
    conscience = _StubConscience(verdict="APPROVED")
    bridge = _make_released_bridge(bus, conscience, engine)

    _submit(bus, {"goal_id": "g8", "text": "   "})

    assert engine.submitted == []
    abandoned = [t for t in bus.published
                 if getattr(t, "topic", None) == "goal.abandoned"]
    assert len(abandoned) == 1
    assert "no goal text" in abandoned[0].payload["reason"]


def test_released_no_engine_publishes_unavailable(released: Path) -> None:
    bus = _StubBus()
    conscience = _StubConscience(verdict="APPROVED")
    bridge = _make_released_bridge(bus, conscience, None)

    _submit(bus, {"goal_id": "g9", "text": "no engine wired"})

    unavailable = [t for t in bus.published
                   if getattr(t, "topic", None) == "goal.dispatch.unavailable"]
    assert len(unavailable) == 1
    assert unavailable[0].payload["has_engine"] is False
    assert unavailable[0].payload["generated_values"] is False
    assert unavailable[0].payload["action_enabled"] is False


def test_released_engine_error_publishes_abandoned(released: Path) -> None:
    bus = _StubBus()
    engine = _StubEngine(fail=True)
    conscience = _StubConscience(verdict="APPROVED")
    bridge = _make_released_bridge(bus, conscience, engine)

    _submit(bus, {"goal_id": "g10", "text": "engine will fail"})

    abandoned = [t for t in bus.published
                 if getattr(t, "topic", None) == "goal.abandoned"]
    assert len(abandoned) == 1
    assert "engine error" in abandoned[0].payload["reason"]
    assert bridge.stats()["dispatched"] == 0


def test_released_singleton_getter_creates_and_starts(released: Path) -> None:
    reset_goal_dispatch_bridge()
    bus = _StubBus()
    bridge = get_goal_dispatch_bridge(
        thought_bus=bus, conscience=_StubConscience("APPROVED"),
        goal_engine=_StubEngine(),
    )
    assert bridge_module._singleton is bridge
    assert "goal.submit.request" in bus.handlers
    same = get_goal_dispatch_bridge()
    assert same is bridge
    reset_goal_dispatch_bridge()
    assert bridge_module._singleton is None
