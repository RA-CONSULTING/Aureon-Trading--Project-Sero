"""Fail-closed tests for MetaCognitionObserver."""

from __future__ import annotations

from typing import Any, Callable

import json

import pytest

from aureon.vault.voice import meta_cognition_observer as meta_module
from aureon.vault.voice.meta_cognition_observer import (
    META_COGNITION_RELEASE_HOLD,
    MetaCognitionObserver,
    ReflectionCard,
    get_meta_cognition_observer,
    reset_meta_cognition_observer,
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
        "modules": ["meta_cognition_observer"],
    }), encoding="utf-8")
    monkeypatch.setenv("GOAL_DISPATCH_RELEASE_RECORD", str(record))
    return record


class _Trap:
    def __getattribute__(self, _name: str) -> Any:
        raise AssertionError("release-held meta observer touched an effect owner")


def test_reflection_card_data_contract_remains_pure() -> None:
    card = ReflectionCard(reflection_id="r1", persona="engineer")
    payload = card.to_dict()
    assert payload["reflection_id"] == "r1"
    assert payload["persona"] == "engineer"
    assert META_COGNITION_RELEASE_HOLD.startswith("meta_cognition_observer_hold:")


def test_constructor_is_inert() -> None:
    observer = MetaCognitionObserver(
        thought_bus=_Trap(),
        vault=_Trap(),
        hash_resonance_index=_Trap(),
        queen_metacognition=_Trap(),
    )
    assert observer._subscribed is False
    assert observer._running is False
    assert observer._closer_thread is None
    assert observer.open_window_count == 0
    assert observer.closed_cards == []


def test_start_holds_before_subscription_or_thread(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "aureon.vault.voice.meta_cognition_observer.threading.Thread",
        lambda *_args, **_kwargs: pytest.fail("meta observer must not create a thread"),
    )
    observer = MetaCognitionObserver(thought_bus=_Trap(), vault=_Trap())
    with pytest.raises(RuntimeError, match="meta_cognition_observer_hold"):
        observer.start()
    assert observer._subscribed is False
    assert observer._running is False
    assert observer._closer_thread is None


@pytest.mark.parametrize(
    "factory",
    [
        lambda obs, card: obs._on_thought(_Trap()),
        lambda obs, card: obs._open_window({}),
        lambda obs, card: obs._closer_loop(),
        lambda obs, card: obs._sweep_closed(),
        lambda obs, card: obs.close_expired(),
        lambda obs, card: obs._finalise(_Trap()),
        lambda obs, card: obs._compute_bond(_Trap()),
        lambda obs, card: obs._publish_card(card),
        lambda obs, card: obs._feed_vault(card),
        lambda obs, card: obs._feed_queen_metacognition(card),
    ],
)
def test_direct_runtime_paths_hold_without_opening_or_closing_windows(
    factory: Callable[[MetaCognitionObserver, ReflectionCard], Any],
) -> None:
    observer = MetaCognitionObserver(
        thought_bus=_Trap(), vault=_Trap(),
        hash_resonance_index=_Trap(), queen_metacognition=_Trap(),
    )
    card = ReflectionCard(reflection_id="r1")
    with pytest.raises(RuntimeError, match="meta_cognition_observer_hold"):
        factory(observer, card)
    assert observer.open_window_count == 0
    assert observer.closed_cards == []


def test_singleton_getter_holds_without_creating_singleton() -> None:
    reset_meta_cognition_observer()
    assert meta_module._singleton is None
    with pytest.raises(RuntimeError, match="meta_cognition_observer_hold"):
        get_meta_cognition_observer(_Trap(), _Trap(), _Trap(), _Trap())
    assert meta_module._singleton is None


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


class _QMC:
    def __init__(self) -> None:
        self.reflections: list = []

    def ingest_external_reflection(self, card_dict: Any) -> None:
        self.reflections.append(card_dict)


class _Thought:
    def __init__(self, topic: str, payload: Any) -> None:
        self.topic = topic
        self.payload = payload


def test_released_start_subscribes_watched_topics(released) -> None:
    bus = _Bus()
    observer = MetaCognitionObserver(thought_bus=bus, window_s=0.2)
    observer.start()
    try:
        for topic in MetaCognitionObserver.WATCHED_TOPICS:
            assert topic in bus.handlers
        assert observer._subscribed is True
    finally:
        observer.stop()


def test_released_window_lifecycle_publishes_and_feeds_everywhere(released) -> None:
    bus = _Bus()
    vault = _Vault()
    qmc = _QMC()
    observer = MetaCognitionObserver(
        thought_bus=bus, vault=vault, queen_metacognition=qmc, window_s=30.0,
    )
    observer._on_thought(_Thought("persona.collapse", {
        "winner": "artist", "probabilities": {"artist": 0.8},
    }))
    assert observer.open_window_count == 1
    observer._on_thought(_Thought("persona.thought", {"text": "let us build"}))
    observer._on_thought(_Thought("goal.submit.request", {"goal_id": "g1"}))
    observer._on_thought(_Thought("goal.completed", {"goal_id": "g1"}))
    # Force the window closed deterministically (no sleeping).
    with observer._lock:
        observer._open_windows[0].close_at = 0.0
    assert observer.close_expired() == 1
    assert observer.open_window_count == 0
    cards = observer.closed_cards
    assert len(cards) == 1
    card = cards[0]
    assert card.persona == "artist"
    assert card.decision == "goal.submit"
    assert card.outcome == "COMPLETED"
    assert len(card.downstream_effects) == 3
    reflections = [
        t for t in bus.published
        if getattr(t, "topic", None) == "meta.reflection"
    ]
    assert len(reflections) == 1
    assert reflections[0].payload["reflection_id"] == card.reflection_id
    assert ("meta.reflection", card.to_dict()) in vault.ingested
    assert len(qmc.reflections) == 1
    assert qmc.reflections[0]["outcome"] == "COMPLETED"
    assert "artist" in card.reasoning
