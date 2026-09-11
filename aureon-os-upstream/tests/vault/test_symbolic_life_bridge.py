"""Fail-closed tests for SymbolicLifeBridge."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import json

import pytest

from aureon.vault.voice.symbolic_life_bridge import (
    SYMBOLIC_LIFE_RELEASE_HOLD,
    SymbolicLifeBridge,
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
        "modules": ["symbolic_life_bridge"],
    }), encoding="utf-8")
    monkeypatch.setenv("GOAL_DISPATCH_RELEASE_RECORD", str(record))
    return record


class _Trap:
    def __getattribute__(self, _name: str) -> Any:
        raise AssertionError("release-held symbolic bridge touched an effect owner")


def test_constructor_does_not_import_or_build_default_engine(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        SymbolicLifeBridge,
        "_build_lambda_engine",
        staticmethod(lambda: pytest.fail("constructor must not build LambdaEngine")),
    )
    monkeypatch.setattr(
        SymbolicLifeBridge,
        "_import_reading_cls",
        staticmethod(lambda: pytest.fail("constructor must not import reading type")),
    )
    bridge = SymbolicLifeBridge(thought_bus=_Trap(), vault=_Trap(), interval_s=0.1)
    assert bridge._lambda_engine is None
    assert bridge._SubsystemReading is None
    assert bridge._subscribed is False
    assert bridge._running is False
    assert bridge._thread is None
    assert bridge.pulse_count == 0


def test_start_holds_before_subscription_or_thread(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "aureon.vault.voice.symbolic_life_bridge.threading.Thread",
        lambda *_args, **_kwargs: pytest.fail("symbolic bridge must not create a thread"),
    )
    bridge = SymbolicLifeBridge(
        thought_bus=_Trap(), vault=_Trap(), lambda_engine=_Trap(), interval_s=0.1
    )
    with pytest.raises(RuntimeError, match="symbolic_life_bridge_hold"):
        bridge.start()
    assert bridge._subscribed is False
    assert bridge._running is False


@pytest.mark.parametrize(
    "name",
    [
        "_on_persona_collapse",
        "_on_persona_thought",
        "_on_goal_request",
        "_on_life_event",
        "_on_peer_state",
        "_on_conversation_turn",
        "_on_goal_echo_summary",
        "_on_goal_echo_orphaned",
    ],
)
def test_callbacks_hold_before_reading_input_or_mutating_state(name: str) -> None:
    bridge = SymbolicLifeBridge(lambda_engine=_Trap())
    before = bridge.rolling_summary()
    with pytest.raises(RuntimeError, match="symbolic_life_bridge_hold"):
        getattr(bridge, name)(_Trap())
    assert bridge.rolling_summary() == before


@pytest.mark.parametrize("name", ["readings", "pulse", "publish", "loop", "engine", "type"])
def test_direct_execution_paths_are_held(name: str) -> None:
    bridge = SymbolicLifeBridge(thought_bus=_Trap(), vault=_Trap(), lambda_engine=_Trap())
    calls = {
        "readings": bridge._build_readings,
        "pulse": bridge.pulse,
        "publish": lambda: bridge._publish_pulse(_Trap(), []),
        "loop": bridge._loop,
        "engine": bridge._build_lambda_engine,
        "type": bridge._import_reading_cls,
    }
    with pytest.raises(RuntimeError, match="symbolic_life_bridge_hold"):
        calls[name]()
    assert bridge.pulse_count == 0
    assert bridge.last_state is None


def test_payload_translation_remains_pure() -> None:
    state = SimpleNamespace(symbolic_life_score=0.5, lambda_t=1.0)
    payload = SymbolicLifeBridge._state_to_payload(state, [])
    assert payload["symbolic_life_score"] == 0.5
    assert SYMBOLIC_LIFE_RELEASE_HOLD.startswith("symbolic_life_bridge_hold:")


# ─── Released path ───────────────────────────────────────────────────────────


class _Bus:
    def __init__(self) -> None:
        self.handlers: dict = {}
        self.published: list = []

    def subscribe(self, topic: str, handler: Any) -> None:
        self.handlers.setdefault(topic, []).append(handler)

    def publish(self, *args: Any, **kwargs: Any) -> None:
        self.published.append(args[0] if args else kwargs)


class _FakeEngine:
    def __init__(self) -> None:
        self.calls: list = []

    def step(self, *, readings: Any, volatility: float, vault: Any) -> Any:
        self.calls.append({"readings": list(readings), "volatility": volatility})
        return SimpleNamespace(
            lambda_t=1.0,
            consciousness_psi=0.5,
            consciousness_level=2,
            coherence_gamma=0.9,
            coherence_phi=0.8,
            symbolic_life_score=0.7,
        )


class _Thought:
    def __init__(self, topic: str, payload: Any) -> None:
        self.topic = topic
        self.payload = payload


def test_released_start_subscribes_and_callbacks_bump_rolling(released) -> None:
    bus = _Bus()
    bridge = SymbolicLifeBridge(thought_bus=bus, lambda_engine=_FakeEngine())
    bridge.start()
    for topic in SymbolicLifeBridge.TOPICS:
        assert topic in bus.handlers
    assert bridge._subscribed is True
    bridge._on_persona_collapse(_Thought("persona.collapse", {
        "winner": "artist", "probabilities": {"artist": 0.9},
    }))
    bridge._on_goal_request(_Thought("goal.submit.request", {"urgency": 0.8}))
    summary = bridge.rolling_summary()
    assert summary["persona_collapse"]["count"] == 1.0
    assert summary["chorus_coherence"]["count"] == 1.0
    assert summary["goal_commitment"]["count"] == 1.0


def test_released_pulse_steps_engine_and_publishes_symbolic_life_pulse(
    released,
) -> None:
    bus = _Bus()
    engine = _FakeEngine()
    bridge = SymbolicLifeBridge(thought_bus=bus, lambda_engine=engine)
    bridge._on_persona_collapse(_Thought("persona.collapse", {
        "winner": "artist", "probabilities": {"artist": 0.9},
    }))
    state = bridge.pulse()
    assert state is not None
    assert state.symbolic_life_score == 0.7
    assert bridge.pulse_count == 1
    assert bridge.last_state is state
    assert len(engine.calls) == 1
    readings = engine.calls[0]["readings"]
    assert {r.name for r in readings} == set(SymbolicLifeBridge.SUBSYSTEMS)
    pulses = [
        t for t in bus.published
        if getattr(t, "topic", None) == "symbolic.life.pulse"
    ]
    assert len(pulses) == 1
    assert pulses[0].payload["symbolic_life_score"] == 0.7
    assert pulses[0].payload["lambda_t"] == 1.0
    assert len(pulses[0].payload["readings"]) == len(SymbolicLifeBridge.SUBSYSTEMS)
