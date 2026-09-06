"""Fail-closed tests for PersonaMinerBridge and GoalSkillAligner.

The miner stays hard-HOLD (owner release does not cover it). The aligner
was released by owner decree 2026-09-06, recorded in
``aureon_fusion/state/goals/dispatch_release.json``; its HOLD tests below
drive the hold by pointing the ``GOAL_DISPATCH_RELEASE_RECORD`` env var at
a path that does not exist (fail-closed proof), and a released-path test
writes a valid record to a tmp file.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

import pytest

from aureon.vault.voice import goal_skill_aligner as aligner_module
from aureon.vault.voice import persona_miner_bridge as miner_module
from aureon.vault.voice.goal_skill_aligner import (
    GOAL_SKILL_ALIGNER_RELEASE_HOLD,
    GoalSkillAligner,
    get_goal_skill_aligner,
    reset_goal_skill_aligner,
)
from aureon.vault.voice.persona_miner_bridge import (
    PERSONA_MINER_RELEASE_HOLD,
    IntentStats,
    MinerPacket,
    PersonaMinerBridge,
    PersonaStats,
    _extract_intent_keywords,
    get_persona_miner_bridge,
    reset_persona_miner_bridge,
)


class _Trap:
    def __getattribute__(self, _name: str) -> Any:
        raise AssertionError("release-held miner/aligner touched an effect owner")


@pytest.fixture
def held(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Point the release record at a path that does not exist → HOLD."""
    missing = tmp_path / "no_such_release.json"
    monkeypatch.setenv("GOAL_DISPATCH_RELEASE_RECORD", str(missing))
    return missing


@pytest.fixture
def released(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    record = tmp_path / "dispatch_release.json"
    record.write_text(json.dumps({
        "ts": "2026-09-06",
        "source": "owner decree 2026-09-06 (Gary Leckey)",
        "modules": ["goal_skill_aligner"],
    }), encoding="utf-8")
    monkeypatch.setenv("GOAL_DISPATCH_RELEASE_RECORD", str(record))
    return record


def test_miner_data_and_keyword_helpers_remain_pure() -> None:
    packet = MinerPacket(packet_type="goal", ts=1.0, persona="engineer")
    persona = PersonaStats(persona="engineer", completion_count=1)
    intent = IntentStats(persona="engineer", intent_keyword="build", success_count=2)
    assert packet.persona == "engineer"
    assert persona.completion_rate() == 1.0
    assert intent.success_rate() == 1.0
    assert _extract_intent_keywords("build the safer evidence dashboard")[0] == "build"
    assert PERSONA_MINER_RELEASE_HOLD.startswith("persona_miner_bridge_hold:")


def test_miner_constructor_does_not_probe_persisted_state(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        Path,
        "exists",
        lambda *_args, **_kwargs: pytest.fail("constructor must not probe disk"),
    )
    bridge = PersonaMinerBridge(
        thought_bus=_Trap(),
        skill_library=_Trap(),
        persistence_path=str(tmp_path / "patterns.json"),
    )
    summary = bridge.summary()
    assert bridge._subscribed is False
    assert summary["packet_count"] == 0
    assert summary["persona_count"] == 0
    assert list(tmp_path.iterdir()) == []


def test_miner_start_and_getter_hold_before_subscription_or_singleton() -> None:
    bridge = PersonaMinerBridge(thought_bus=_Trap(), skill_library=_Trap())
    with pytest.raises(RuntimeError, match="persona_miner_bridge_hold"):
        bridge.start()
    assert bridge._subscribed is False

    reset_persona_miner_bridge()
    assert miner_module._singleton is None
    with pytest.raises(RuntimeError, match="persona_miner_bridge_hold"):
        get_persona_miner_bridge(_Trap(), _Trap())
    assert miner_module._singleton is None


@pytest.mark.parametrize(
    "factory",
    [
        lambda bridge: bridge._on_thought(_Trap()),
        lambda bridge: bridge.ingest("goal.submit.request", {"goal_id": "g"}),
        lambda bridge: bridge._persona_stat("engineer"),
        lambda bridge: bridge._intent_stat("engineer", "build"),
        lambda bridge: bridge._record_persona_collapse({}, 1.0),
        lambda bridge: bridge._record_goal_request({}, 1.0),
        lambda bridge: bridge._record_goal_terminal("goal.completed", {}, 1.0),
        lambda bridge: bridge._record_reflection({}, 1.0),
        lambda bridge: bridge._record_raw("topic", {}, 1.0),
        lambda bridge: bridge._maybe_publish_pattern("engineer", "build"),
        lambda bridge: bridge._publish("topic", {}),
        lambda bridge: bridge.recommend_skill_for("engineer", "build dashboard"),
        lambda bridge: bridge._lookup_skill("build"),
    ],
)
def test_miner_execution_paths_hold_without_learning(
    factory: Callable[[PersonaMinerBridge], Any],
) -> None:
    bridge = PersonaMinerBridge(thought_bus=_Trap(), skill_library=_Trap())
    with pytest.raises(RuntimeError, match="persona_miner_bridge_hold"):
        factory(bridge)
    assert bridge.summary()["packet_count"] == 0
    assert bridge.summary()["persona_count"] == 0


def test_miner_persist_and_load_hold_before_filesystem(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def _fail(*_args, **_kwargs):
        pytest.fail("held miner persistence touched the filesystem")

    monkeypatch.setattr(Path, "exists", _fail)
    monkeypatch.setattr(Path, "mkdir", _fail)
    monkeypatch.setattr("builtins.open", _fail)
    bridge = PersonaMinerBridge(persistence_path=str(tmp_path / "patterns.json"))
    with pytest.raises(RuntimeError, match="persona_miner_bridge_hold"):
        bridge.persist()
    with pytest.raises(RuntimeError, match="persona_miner_bridge_hold"):
        bridge._load_persisted()
    assert list(tmp_path.iterdir()) == []


def test_aligner_constructor_is_inert_and_start_holds(
    held: Path,
) -> None:
    aligner = GoalSkillAligner(thought_bus=_Trap(), miner_bridge=_Trap())
    assert aligner.stats()["subscribed"] is False
    assert aligner.stats()["lookups"] == 0
    assert aligner.stats()["suggestions"] == 0
    with pytest.raises(RuntimeError, match="goal_skill_aligner_hold"):
        aligner.start()
    assert aligner.stats()["subscribed"] is False


@pytest.mark.parametrize(
    "factory",
    [
        lambda aligner: aligner._on_request(_Trap()),
        lambda aligner: aligner._lookup({"text": "build"}),
        lambda aligner: aligner._publish_suggestion({}, {}),
        lambda aligner: aligner._publish_aligned_request({}, {}),
    ],
)
def test_aligner_execution_paths_hold_without_lookup_or_publish(
    held: Path,
    factory: Callable[[GoalSkillAligner], Any],
) -> None:
    aligner = GoalSkillAligner(thought_bus=_Trap(), miner_bridge=_Trap())
    with pytest.raises(RuntimeError, match="goal_skill_aligner_hold"):
        factory(aligner)
    assert aligner.stats()["lookups"] == 0
    assert aligner.stats()["suggestions"] == 0


def test_aligner_singleton_getter_holds_without_creation(held: Path) -> None:
    reset_goal_skill_aligner()
    assert aligner_module._singleton is None
    with pytest.raises(RuntimeError, match="goal_skill_aligner_hold"):
        get_goal_skill_aligner(_Trap(), _Trap())
    assert aligner_module._singleton is None
    assert GOAL_SKILL_ALIGNER_RELEASE_HOLD.endswith(
        "production_magic_star_release_unavailable"
    )


# ─── Aligner released path (owner decree 2026-09-06) ─────────────────────────


class _StubBus:
    def __init__(self) -> None:
        self.handlers: dict = {}
        self.published: list = []

    def subscribe(self, topic: str, handler) -> None:
        self.handlers.setdefault(topic, []).append(handler)

    def publish(self, *args: Any, **kwargs: Any) -> None:
        self.published.append(args[0] if args else kwargs)


class _StubMiner:
    def __init__(self) -> None:
        self.lookups: list = []

    def recommend_skill_for(self, persona: str, intent_text: str,
                            min_confidence: float = 0.0):
        self.lookups.append((persona, intent_text))
        return {
            "intent_keyword": "build",
            "skills": ["code_architect"],
            "confidence": 0.9,
            "source": "pattern",
        }


def test_aligner_released_suggests_without_executing(released: Path) -> None:
    bus = _StubBus()
    miner = _StubMiner()
    aligner = GoalSkillAligner(thought_bus=bus, miner_bridge=miner)
    aligner.start()
    assert "goal.submit.request" in bus.handlers

    class Thought:
        payload = {"goal_id": "g1", "text": "build a dashboard",
                   "proposed_by_persona": "engineer"}

    for handler in bus.handlers["goal.submit.request"]:
        handler(Thought())

    assert miner.lookups == [("engineer", "build a dashboard")]
    topics = [getattr(t, "topic", None) for t in bus.published]
    assert "goal.alignment.suggestion" in topics
    assert "goal.submit.request.aligned" in topics
    suggestion = next(t for t in bus.published
                      if getattr(t, "topic", "") == "goal.alignment.suggestion")
    assert suggestion.payload["recommended_skills"] == ["code_architect"]
    # The aligner only ever suggests — it never executes anything.
    assert aligner.stats()["suggestions"] == 1
    assert aligner.stats()["lookups"] == 1


def test_aligner_released_skips_already_aligned(released: Path) -> None:
    bus = _StubBus()
    miner = _StubMiner()
    aligner = GoalSkillAligner(thought_bus=bus, miner_bridge=miner)
    aligner.start()

    class Thought:
        payload = {"goal_id": "g2", "text": "build", "aligned": True}

    for handler in bus.handlers["goal.submit.request"]:
        handler(Thought())

    assert miner.lookups == []
    assert aligner.stats()["lookups"] == 0
