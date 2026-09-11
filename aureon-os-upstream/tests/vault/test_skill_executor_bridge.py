"""Fail-closed + released-path tests for SkillExecutorBridge.

Released by owner decree 2026-09-06 via the shared release record
(``aureon_fusion/state/goals/dispatch_release.json``, read through
``_goal_release``). HOLD tests drive the hold by pointing
``GOAL_DISPATCH_RELEASE_RECORD`` at a path that does NOT exist. On the
released path the conscience gate is enforceable: a missing conscience, a
failing ``ask_why``, or a VETO refuse execution (``goal.abandoned``, the
executor never runs).
"""

from __future__ import annotations

import json
import sys
import types
from enum import Enum, auto
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

from aureon.vault.voice import skill_executor_bridge as bridge_module
from aureon.vault.voice._goal_claims import GoalClaims
from aureon.vault.voice.skill_executor_bridge import (
    SKILL_EXECUTOR_RELEASE_HOLD,
    SkillExecutorBridge,
    _default_file_executor,
    code_architect_adapter,
    get_skill_executor_bridge,
    reset_skill_executor_bridge,
)


class _Trap:
    def __getattribute__(self, _name: str) -> Any:
        raise AssertionError("release-held skill bridge touched an effect owner")


def _write_release_record(path: Path, *modules: str) -> Path:
    path.write_text(json.dumps({
        "ts": "2026-09-06",
        "source": "owner decree 2026-09-06 (Gary Leckey)",
        "modules": list(modules),
    }), encoding="utf-8")
    return path


@pytest.fixture
def held(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    missing = tmp_path / "no_such_release.json"
    monkeypatch.setenv("GOAL_DISPATCH_RELEASE_RECORD", str(missing))
    return missing


@pytest.fixture
def released(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    record_dir = tmp_path / "record"
    record_dir.mkdir()
    record = _write_release_record(
        record_dir / "dispatch_release.json", "skill_executor_bridge")
    monkeypatch.setenv("GOAL_DISPATCH_RELEASE_RECORD", str(record))
    return record


@pytest.fixture(autouse=True)
def _clean_claims():
    GoalClaims.clear()
    yield
    GoalClaims.clear()


# ─── HOLD behavior (driven by an absent release record) ──────────────────────


def test_constructor_is_inert_and_reports_hold(
    held: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        Path,
        "resolve",
        lambda *_args, **_kwargs: pytest.fail("inert constructor must not resolve paths"),
    )
    bridge = SkillExecutorBridge(
        thought_bus=_Trap(),
        vault=_Trap(),
        conscience=_Trap(),
        output_root=str(tmp_path),
    )
    assert bridge._executor is None
    stats = bridge.stats()
    assert stats["status"] == "HOLD"
    assert stats["reason_code"] == "production_magic_star_release_unavailable"
    assert stats["production_ready"] is False
    assert stats["effect_enabled"] is False
    assert stats["subscribed"] is False
    assert bridge.history() == []
    assert [p for p in tmp_path.iterdir() if p.name != "record"] == []


def test_default_writer_and_default_executor_closure_hold(tmp_path: Path,
                                                           held: Path) -> None:
    with pytest.raises(RuntimeError, match="skill_executor_bridge_hold"):
        _default_file_executor("unsafe", {"x": 1}, output_root=tmp_path)
    bridge = SkillExecutorBridge(output_root=str(tmp_path))
    default_executor = bridge._build_default_executor()
    with pytest.raises(RuntimeError, match="skill_executor_bridge_hold"):
        default_executor("unsafe", {"x": 1})
    assert [p for p in tmp_path.iterdir() if p.name != "record"] == []


def test_code_architect_adapter_holds_before_execute_skill(held: Path) -> None:
    adapted = code_architect_adapter(_Trap())
    with pytest.raises(RuntimeError, match="skill_executor_bridge_hold"):
        adapted("skill", {"x": 1})


def test_start_and_intake_hold_before_subscription_claim_or_thread(
    held: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        "aureon.vault.voice.skill_executor_bridge.threading.Thread",
        lambda *_args, **_kwargs: pytest.fail("bridge must not create a thread"),
    )
    bridge = SkillExecutorBridge(
        thought_bus=_Trap(),
        vault=_Trap(),
        executor=_Trap(),
        conscience=_Trap(),
        output_root=str(tmp_path),
    )
    with pytest.raises(RuntimeError, match="skill_executor_bridge_hold"):
        bridge.start()
    with pytest.raises(RuntimeError, match="skill_executor_bridge_hold"):
        bridge._on_aligned_request(_Trap())
    assert GoalClaims.is_claimed("probe-goal") is False
    assert bridge.stats()["claimed"] == 0
    assert bridge.stats()["status"] == "HOLD"
    assert bridge.stats()["subscribed"] is False
    assert bridge.history() == []


@pytest.mark.parametrize(
    "call_name",
    ["veto", "run_chain", "abandon", "publish", "ingest"],
)
def test_direct_effect_helpers_hold_when_record_absent(
    call_name: str, held: Path, tmp_path: Path
) -> None:
    bridge = SkillExecutorBridge(
        thought_bus=_Trap(),
        vault=_Trap(),
        executor=_Trap(),
        conscience=_Trap(),
        output_root=str(tmp_path),
    )
    calls = {
        "veto": lambda: bridge._veto_blocks("goal", "persona", {"goal_id": "g"}),
        "run_chain": lambda: bridge._run_chain("g", "persona", "goal", ["skill"]),
        "abandon": lambda: bridge._publish_abandoned("g", "reason"),
        "publish": lambda: bridge._publish("topic", {"x": 1}),
        "ingest": lambda: bridge._ingest_artefacts("p", "g", "s", ["x"]),
    }
    with pytest.raises(RuntimeError, match="skill_executor_bridge_hold"):
        calls[call_name]()
    assert bridge.stats()["executed"] == 0
    assert bridge.history() == []
    assert [p for p in tmp_path.iterdir() if p.name != "record"] == []


def test_singleton_getter_holds_when_record_absent(held: Path) -> None:
    reset_skill_executor_bridge()
    assert bridge_module._singleton is None
    with pytest.raises(RuntimeError, match="skill_executor_bridge_hold"):
        get_skill_executor_bridge(thought_bus=_Trap(), vault=_Trap())
    assert bridge_module._singleton is None
    reset_skill_executor_bridge()


# ─── Released path ───────────────────────────────────────────────────────────


class _V(Enum):
    APPROVED = auto()
    VETO = auto()


class _Whisper:
    def __init__(self, verdict: Any, message: str = "", why: str = "") -> None:
        self.verdict = verdict
        self.message = message
        self.why_it_matters = why


class _StubConscience:
    def __init__(self, verdict: Any = _V.APPROVED, fail: bool = False) -> None:
        self.verdict = verdict
        self.fail = fail
        self.asked: List[tuple] = []

    def ask_why(self, text: str, context: Dict[str, Any]) -> Any:
        self.asked.append((text, context))
        if self.fail:
            raise RuntimeError("conscience down")
        return _Whisper(self.verdict, "msg", "why")


class _StubBus:
    def __init__(self) -> None:
        self.handlers: Dict[str, list] = {}
        self.published: List[Any] = []

    def subscribe(self, topic: str, handler) -> None:
        self.handlers.setdefault(topic, []).append(handler)

    def publish(self, *args: Any, **kwargs: Any) -> None:
        self.published.append(args[0] if args else kwargs)


def _aligned_payload(goal_id: str = "sg1", skills: Optional[list] = None) -> dict:
    return {
        "goal_id": goal_id,
        "text": "build the safer dashboard",
        "proposed_by_persona": "engineer",
        "recommended_skills": (["mock_skill"] if skills is None else skills),
    }


class _Thought:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.topic = "goal.submit.request.aligned"


def test_released_default_writer_produces_an_artifact(released: Path,
                                                      tmp_path: Path) -> None:
    result = _default_file_executor(
        "mock_skill", {"intent_text": "build", "persona": "engineer"},
        output_root=tmp_path,
    )
    assert result["ok"] is True
    artefact = Path(result["artefacts"][0])
    assert artefact.exists() and artefact.parent == tmp_path
    assert "mock_skill" in artefact.read_text(encoding="utf-8")


def test_released_bridge_executes_chain_through_conscience(released: Path,
                                                           tmp_path: Path) -> None:
    bus = _StubBus()
    conscience = _StubConscience(_V.APPROVED)
    bridge = SkillExecutorBridge(
        thought_bus=bus, conscience=conscience,
        output_root=str(tmp_path), run_in_thread=False,
    )
    bridge.start()
    assert "goal.submit.request.aligned" in bus.handlers

    for handler in bus.handlers["goal.submit.request.aligned"]:
        handler(_Thought(_aligned_payload()))

    assert conscience.asked, "conscience gate must be consulted"
    assert bridge.stats()["executed"] == 1
    completed = [t for t in bus.published
                 if getattr(t, "topic", "") == "goal.completed"]
    assert len(completed) == 1
    assert completed[0].payload["goal_id"] == "sg1"
    assert completed[0].payload["artefacts"], "artefact path must be listed"
    assert list(tmp_path.iterdir()), "the default executor must write on disk"


def test_released_bridge_refuses_without_conscience(released: Path,
                                                    tmp_path: Path) -> None:
    bus = _StubBus()
    bridge = SkillExecutorBridge(
        thought_bus=bus, output_root=str(tmp_path), run_in_thread=False,
    )
    bridge.start()
    for handler in bus.handlers["goal.submit.request.aligned"]:
        handler(_Thought(_aligned_payload()))

    assert bridge.stats()["executed"] == 0
    assert [p for p in tmp_path.iterdir() if p.name != "record"] == [], "executor must never run ungated"
    abandoned = [t for t in bus.published
                 if getattr(t, "topic", "") == "goal.abandoned"]
    assert len(abandoned) == 1
    assert "conscience_gate_unavailable" in abandoned[0].payload["reason"]


def test_released_bridge_refuses_on_conscience_veto(released: Path,
                                                    tmp_path: Path) -> None:
    bus = _StubBus()
    bridge = SkillExecutorBridge(
        thought_bus=bus, conscience=_StubConscience(_V.VETO),
        output_root=str(tmp_path), run_in_thread=False,
    )
    bridge.start()
    for handler in bus.handlers["goal.submit.request.aligned"]:
        handler(_Thought(_aligned_payload()))

    assert bridge.stats()["executed"] == 0
    assert [p for p in tmp_path.iterdir() if p.name != "record"] == []
    abandoned = [t for t in bus.published
                 if getattr(t, "topic", "") == "goal.abandoned"]
    assert len(abandoned) == 1
    assert "msg" in abandoned[0].payload["reason"]


def test_released_bridge_refuses_on_conscience_error(released: Path,
                                                     tmp_path: Path) -> None:
    bus = _StubBus()
    bridge = SkillExecutorBridge(
        thought_bus=bus, conscience=_StubConscience(fail=True),
        output_root=str(tmp_path), run_in_thread=False,
    )
    bridge.start()
    for handler in bus.handlers["goal.submit.request.aligned"]:
        handler(_Thought(_aligned_payload()))

    assert bridge.stats()["executed"] == 0
    assert [p for p in tmp_path.iterdir() if p.name != "record"] == []
    abandoned = [t for t in bus.published
                 if getattr(t, "topic", "") == "goal.abandoned"]
    assert len(abandoned) == 1
    assert "conscience_gate_error" in abandoned[0].payload["reason"]


def test_released_fusion_hook_veto_refuses_execution(
    released: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """A VETO from aureon_fusion.conscience_hook (second opinion) refuses
    execution even when the primary conscience passes."""
    fake_hook = types.ModuleType("aureon_fusion.conscience_hook")
    fake_hook.evaluate = lambda *_a, **_k: {  # type: ignore[attr-defined]
        "verdict": "VETO", "reasoning": "organism-level veto",
    }
    pkg = types.ModuleType("aureon_fusion")
    monkeypatch.setitem(sys.modules, "aureon_fusion", pkg)
    monkeypatch.setitem(sys.modules, "aureon_fusion.conscience_hook", fake_hook)

    bus = _StubBus()
    bridge = SkillExecutorBridge(
        thought_bus=bus, conscience=_StubConscience(_V.APPROVED),
        output_root=str(tmp_path), run_in_thread=False,
    )
    bridge.start()
    for handler in bus.handlers["goal.submit.request.aligned"]:
        handler(_Thought(_aligned_payload()))

    assert bridge.stats()["executed"] == 0
    assert [p for p in tmp_path.iterdir() if p.name != "record"] == []
    abandoned = [t for t in bus.published
                 if getattr(t, "topic", "") == "goal.abandoned"]
    assert len(abandoned) == 1
    assert "fusion conscience veto" in abandoned[0].payload["reason"]
    assert bridge.stats()["vetoed"] == 1


def test_released_skill_failure_abandons_the_goal(released: Path,
                                                  tmp_path: Path) -> None:
    bus = _StubBus()

    def _boom(skill_name: str, params: dict) -> dict:
        return {"ok": False, "artefacts": [], "result": None, "error": "boom"}

    bridge = SkillExecutorBridge(
        thought_bus=bus, conscience=_StubConscience(_V.APPROVED),
        executor=_boom, output_root=str(tmp_path), run_in_thread=False,
    )
    bridge.start()
    for handler in bus.handlers["goal.submit.request.aligned"]:
        handler(_Thought(_aligned_payload()))

    failed = [t for t in bus.published
              if getattr(t, "topic", "") == "skill.execution.failed"]
    assert len(failed) == 1
    abandoned = [t for t in bus.published
                 if getattr(t, "topic", "") == "goal.abandoned"]
    assert len(abandoned) == 1
    assert "boom" in abandoned[0].payload["reason"]


def test_released_no_recommended_skills_abandons(released: Path,
                                                 tmp_path: Path) -> None:
    bus = _StubBus()
    bridge = SkillExecutorBridge(
        thought_bus=bus, conscience=_StubConscience(_V.APPROVED),
        output_root=str(tmp_path), run_in_thread=False,
    )
    bridge.start()
    for handler in bus.handlers["goal.submit.request.aligned"]:
        handler(_Thought(_aligned_payload(skills=[])))

    abandoned = [t for t in bus.published
                 if getattr(t, "topic", "") == "goal.abandoned"]
    assert len(abandoned) == 1
    assert "no recommended_skills" in abandoned[0].payload["reason"]


def test_released_singleton_getter_creates_and_resets(released: Path) -> None:
    reset_skill_executor_bridge()
    bus = _StubBus()
    bridge = get_skill_executor_bridge(
        thought_bus=bus, conscience=_StubConscience(_V.APPROVED),
    )
    assert bridge_module._singleton is bridge
    assert "goal.submit.request.aligned" in bus.handlers
    reset_skill_executor_bridge()
    assert bridge_module._singleton is None


def test_hold_constant_shape() -> None:
    assert SKILL_EXECUTOR_RELEASE_HOLD.count(":") == 1
    assert SKILL_EXECUTOR_RELEASE_HOLD.endswith(
        "production_magic_star_release_unavailable"
    )
