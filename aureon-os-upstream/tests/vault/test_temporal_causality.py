"""Fail-closed tests for TemporalCausalityLaw."""

from __future__ import annotations

from typing import Any, Callable

import json

import pytest

from aureon.vault.voice import temporal_causality as temporal_module
from aureon.vault.voice.temporal_causality import (
    TEMPORAL_CAUSALITY_RELEASE_HOLD,
    GoalEcho,
    GoalState,
    TemporalCausalityLaw,
    get_temporal_causality_law,
    reset_temporal_causality_law,
)


@pytest.fixture(autouse=True)
def _default_held(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv(
        "GOAL_DISPATCH_RELEASE_RECORD", str(tmp_path / "missing.json"))


@pytest.fixture
def released(monkeypatch, tmp_path):
    record_dir = tmp_path / "record"
    record_dir.mkdir()
    record = record_dir / "dispatch_release.json"
    record.write_text(json.dumps({
        "ts": "2026-09-06",
        "source": "owner decree 2026-09-06 (Gary Leckey)",
        "modules": ["temporal_causality"],
    }), encoding="utf-8")
    monkeypatch.setenv("GOAL_DISPATCH_RELEASE_RECORD", str(record))
    return record


class _Trap:
    def __getattribute__(self, _name: str) -> Any:
        raise AssertionError("release-held temporal law touched an effect owner")


def test_goal_echo_data_contract_remains_pure() -> None:
    echo = GoalEcho(goal_id="g1", text="review evidence")
    assert echo.state is GoalState.PROPOSED
    assert echo.is_terminal() is False
    assert echo.to_dict()["goal_id"] == "g1"
    echo.state = GoalState.COMPLETED
    assert echo.is_terminal() is True
    assert TEMPORAL_CAUSALITY_RELEASE_HOLD.startswith("temporal_causality_hold:")


def test_constructor_is_inert_and_empty_queries_remain_available() -> None:
    law = TemporalCausalityLaw(thought_bus=_Trap(), vault=_Trap())
    assert law._subscribed is False
    assert law._goals == {}
    assert law._pulse_count == 0
    assert law.active() == []
    assert law.all() == []
    assert law.summary()["total_goals"] == 0


@pytest.mark.parametrize(
    "name",
    ["_on_submit_request", "_on_submitted", "_on_progress", "_on_completed", "_on_abandoned"],
)
def test_start_and_inbound_callbacks_hold_before_owner_access(name: str) -> None:
    law = TemporalCausalityLaw(thought_bus=_Trap(), vault=_Trap())
    with pytest.raises(RuntimeError, match="temporal_causality_hold"):
        getattr(law, name)(_Trap())
    assert law._goals == {}
    assert law._pulse_count == 0


def test_start_holds_before_subscription() -> None:
    law = TemporalCausalityLaw(thought_bus=_Trap(), vault=_Trap())
    with pytest.raises(RuntimeError, match="temporal_causality_hold"):
        law.start()
    assert law._subscribed is False


@pytest.mark.parametrize(
    "factory",
    [
        lambda law, echo: law.track({"goal_id": "g"}),
        lambda law, echo: law.acknowledge("g"),
        lambda law, echo: law.update_progress("g", 0.5),
        lambda law, echo: law.complete("g", "done"),
        lambda law, echo: law.abandon("g", "reason"),
        lambda law, echo: law.pulse(),
        lambda law, echo: law._record_transition(echo, GoalState.COMPLETED, "done"),
        lambda law, echo: law._publish_echo(echo, "goal.echo"),
        lambda law, echo: law._publish_summary({}),
        lambda law, echo: law._feed_vault(echo),
    ],
)
def test_direct_transition_and_effect_paths_hold_without_state_change(
    factory: Callable[[TemporalCausalityLaw, GoalEcho], Any],
) -> None:
    law = TemporalCausalityLaw(thought_bus=_Trap(), vault=_Trap())
    echo = GoalEcho(goal_id="g")
    with pytest.raises(RuntimeError, match="temporal_causality_hold"):
        factory(law, echo)
    assert law._goals == {}
    assert law._pulse_count == 0
    assert echo.state is GoalState.PROPOSED
    assert echo.transitions == []


def test_singleton_getter_holds_without_creating_singleton() -> None:
    reset_temporal_causality_law()
    assert temporal_module._singleton is None
    with pytest.raises(RuntimeError, match="temporal_causality_hold"):
        get_temporal_causality_law(_Trap(), _Trap())
    assert temporal_module._singleton is None


# ─── Released path ───────────────────────────────────────────────────────────


class _Bus:
    def __init__(self) -> None:
        self.handlers: dict = {}
        self.published: list = []

    def subscribe(self, topic: str, handler: Any) -> None:
        self.handlers.setdefault(topic, []).append(handler)

    def publish(self, *args: Any, **kwargs: Any) -> None:
        self.published.append(args[0] if args else kwargs)


class _Vault:
    def __init__(self) -> None:
        self.ingested: list = []

    def ingest(self, topic: str, payload: Any) -> None:
        self.ingested.append((topic, payload))


class _Thought:
    def __init__(self, topic: str, payload: Any) -> None:
        self.topic = topic
        self.payload = payload


def test_released_full_lifecycle_from_proposal_to_completion(released) -> None:
    bus = _Bus()
    vault = _Vault()
    law = TemporalCausalityLaw(thought_bus=bus, vault=vault, ack_budget_tau=2)
    law.start()
    for topic in law.INBOUND_TOPICS:
        assert topic in bus.handlers
    law._on_submit_request(_Thought("goal.submit.request", {
        "goal_id": "g1", "text": "build", "proposed_by_persona": "engineer",
    }))
    echo = law.get("g1")
    assert echo is not None and echo.state is GoalState.PROPOSED
    law._on_submitted(_Thought("goal.submitted", {
        "goal_id": "g1", "source": "engine",
    }))
    assert law.get("g1").state is GoalState.ACKNOWLEDGED
    assert law.get("g1").acknowledged_by == "engine"
    law._on_progress(_Thought("goal.progress", {"goal_id": "g1", "progress_pct": 0.5}))
    assert law.get("g1").state is GoalState.IN_PROGRESS
    law._on_completed(_Thought("goal.completed", {
        "goal_id": "g1", "result_summary": "done",
    }))
    echo = law.get("g1")
    assert echo.state is GoalState.COMPLETED
    assert echo.is_terminal()
    assert echo.progress_pct == 1.0
    assert echo.result_summary == "done"
    states = [t["state"] for t in echo.transitions]
    assert states == ["PROPOSED", "ACKNOWLEDGED", "IN_PROGRESS", "COMPLETED"]
    topics = [getattr(t, "topic", None) for t in bus.published]
    assert "goal.echo" in topics
    assert ("goal.echo", echo.to_dict()) in vault.ingested
    assert law.summary()["counts"]["COMPLETED"] == 1


def test_released_pulse_orphans_stale_proposed_goal_and_publishes_summary(
    released,
) -> None:
    bus = _Bus()
    law = TemporalCausalityLaw(thought_bus=bus, ack_budget_tau=1)
    law.track({"goal_id": "g1", "text": "stale goal"})
    summary = law.pulse()
    echo = law.get("g1")
    assert echo.state is GoalState.ORPHANED
    assert echo.is_terminal()
    topics = [getattr(t, "topic", None) for t in bus.published]
    assert "goal.echo.orphaned" in topics
    assert "goal.echo.summary" in topics
    assert summary["counts"]["ORPHANED"] == 1
    assert summary["pulse"] == 1
