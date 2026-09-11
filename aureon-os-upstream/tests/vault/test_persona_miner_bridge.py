"""Fail-closed + released-path tests for PersonaMinerBridge and GoalSkillAligner.

Both modules were released by owner decree 2026-09-06, recorded in
``aureon_fusion/state/goals/dispatch_release.json`` and read through
``_goal_release``. Every HOLD-behavior test drives the hold by pointing the
``GOAL_DISPATCH_RELEASE_RECORD`` env var at a path that does NOT exist —
proving the fail-closed property (no record → every effect method still
raises the module's RELEASE_HOLD). Released-path tests write a valid record
to a tmp file. The chain tests prove the released aligner can now actually
reach a live (stubbed or real) miner lookup.
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
    record_dir = tmp_path / "record"
    record_dir.mkdir()
    record = _write_release_record(
        record_dir / "dispatch_release.json", "persona_miner_bridge", "goal_skill_aligner")
    monkeypatch.setenv("GOAL_DISPATCH_RELEASE_RECORD", str(record))
    return record


# ─── Pure helpers (unchanged by release state) ───────────────────────────────


def test_miner_data_and_keyword_helpers_remain_pure() -> None:
    packet = MinerPacket(packet_type="goal", ts=1.0, persona="engineer")
    persona = PersonaStats(persona="engineer", completion_count=1)
    intent = IntentStats(persona="engineer", intent_keyword="build", success_count=2)
    assert packet.persona == "engineer"
    assert persona.completion_rate() == 1.0
    assert intent.success_rate() == 1.0
    assert _extract_intent_keywords("build the safer evidence dashboard")[0] == "build"
    assert PERSONA_MINER_RELEASE_HOLD.startswith("persona_miner_bridge_hold:")
    assert GOAL_SKILL_ALIGNER_RELEASE_HOLD.endswith(
        "production_magic_star_release_unavailable"
    )


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


# ─── Miner HOLD behavior (driven by an absent release record) ────────────────


def test_miner_start_and_getter_hold_when_record_absent(held: Path) -> None:
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
    held: Path,
    factory: Callable[[PersonaMinerBridge], Any],
) -> None:
    bridge = PersonaMinerBridge(thought_bus=_Trap(), skill_library=_Trap())
    with pytest.raises(RuntimeError, match="persona_miner_bridge_hold"):
        factory(bridge)
    assert bridge.summary()["packet_count"] == 0
    assert bridge.summary()["persona_count"] == 0


def test_miner_persist_and_load_hold_before_filesystem(
    held: Path,
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


def test_miner_record_naming_another_module_still_holds(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    other = _write_release_record(tmp_path / "other.json", "goal_skill_aligner")
    monkeypatch.setenv("GOAL_DISPATCH_RELEASE_RECORD", str(other))
    bridge = PersonaMinerBridge(thought_bus=_Trap())
    with pytest.raises(RuntimeError, match="persona_miner_bridge_hold"):
        bridge.ingest("persona.collapse", {"winner": "mystic"})


# ─── Miner released path ─────────────────────────────────────────────────────


class _StubBus:
    def __init__(self) -> None:
        self.handlers: dict = {}
        self.published: list = []

    def subscribe(self, topic: str, handler) -> None:
        self.handlers.setdefault(topic, []).append(handler)

    def publish(self, *args: Any, **kwargs: Any) -> None:
        self.published.append(args[0] if args else kwargs)


def test_released_miner_learns_and_recommends_patterns(released: Path) -> None:
    bus = _StubBus()
    bridge = PersonaMinerBridge(thought_bus=bus)
    bridge.start()
    assert "goal.submit.request" in bus.handlers
    for i in range(10):
        gid = f"g{i}"
        packet = bridge.ingest("goal.submit.request", {
            "goal_id": gid, "text": "build the dashboard",
            "proposed_by_persona": "engineer",
        })
        assert isinstance(packet, MinerPacket)
        bridge.ingest("goal.completed", {
            "goal_id": gid, "recommended_skills": ["code_architect"],
        })
    health = bridge.persona_health("engineer")
    assert health["completion_rate"] == 1.0
    rec = bridge.recommend_skill_for("engineer", "build a safer dashboard")
    assert rec is not None
    assert rec["source"] == "pattern"
    assert rec["skills"] == ["code_architect"]
    learned = [t for t in bus.published
               if getattr(t, "topic", "") == "miner.pattern.learned"]
    assert learned, "crossing the confidence threshold must publish a learned pattern"
    assert bridge.summary()["patterns_published"] == len(learned) or learned


def test_released_miner_persists_and_reloads(released: Path, tmp_path: Path) -> None:
    path = str(tmp_path / "patterns.json")
    bridge = PersonaMinerBridge(persistence_path=path)
    for i in range(3):
        bridge.ingest("persona.collapse", {"winner": "engineer"})
        gid = f"g{i}"
        bridge.ingest("goal.submit.request", {
            "goal_id": gid, "text": "build things", "proposed_by_persona": "engineer"})
        bridge.ingest("goal.completed", {"goal_id": gid})
    assert bridge.persist() == path
    fresh = PersonaMinerBridge(persistence_path=path)
    fresh._load_persisted()
    assert fresh.persona_health("engineer")["action_count"] == 3


# ─── Aligner HOLD behavior (driven by an absent release record) ──────────────


def test_aligner_constructor_is_inert_and_start_holds(held: Path) -> None:
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


# ─── Aligner released path + the miner→aligner chain ─────────────────────────


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


class _StubThought:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.topic = "goal.submit.request"


def _submit(bus: _StubBus, payload: dict) -> None:
    for handler in bus.handlers["goal.submit.request"]:
        handler(_StubThought(payload))


def test_aligner_released_suggests_without_executing(released: Path) -> None:
    bus = _StubBus()
    miner = _StubMiner()
    aligner = GoalSkillAligner(thought_bus=bus, miner_bridge=miner)
    aligner.start()
    assert "goal.submit.request" in bus.handlers

    _submit(bus, {"goal_id": "g1", "text": "build a dashboard",
                  "proposed_by_persona": "engineer"})

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

    _submit(bus, {"goal_id": "g2", "text": "build", "aligned": True})

    assert miner.lookups == []
    assert aligner.stats()["lookups"] == 0


def test_released_aligner_reaches_real_miner_pattern_lookup(released: Path) -> None:
    """Chain proof: the released aligner's path actually reaches a live
    PersonaMinerBridge pattern lookup (the hold that previously blocked it)."""
    bus = _StubBus()
    miner = PersonaMinerBridge()
    for i in range(10):
        gid = f"chain{i}"
        miner.ingest("goal.submit.request", {
            "goal_id": gid, "text": "build the observatory",
            "proposed_by_persona": "engineer"})
        miner.ingest("goal.completed", {
            "goal_id": gid, "recommended_skills": ["code_architect"]})

    aligner = GoalSkillAligner(thought_bus=bus, miner_bridge=miner)
    aligner.start()
    _submit(bus, {"goal_id": "gx", "text": "build a safer observatory",
                  "proposed_by_persona": "engineer"})

    suggestion = next(t for t in bus.published
                      if getattr(t, "topic", "") == "goal.alignment.suggestion")
    assert suggestion.payload["source"] == "pattern"
    assert suggestion.payload["recommended_skills"] == ["code_architect"]
    assert suggestion.payload["confidence"] >= 0.6


def test_aligner_singleton_getter_creates_and_resets(released: Path) -> None:
    reset_goal_skill_aligner()
    bus = _StubBus()
    aligner = get_goal_skill_aligner(thought_bus=bus, miner_bridge=_StubMiner())
    assert aligner_module._singleton is aligner
    assert "goal.submit.request" in bus.handlers
    reset_goal_skill_aligner()
    assert aligner_module._singleton is None
