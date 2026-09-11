"""Fail-closed tests for the package-exported bus flight observer."""

from __future__ import annotations

import json
from typing import Any

import pytest

from aureon.vault.voice import bus_flight_check as flight_module
from aureon.vault.voice.bus_flight_check import (
    BUS_FLIGHT_CHECK_RELEASE_HOLD,
    BusFlightCheck,
    get_bus_flight_check,
    reset_bus_flight_check,
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
        "modules": ["bus_flight_check"],
    }), encoding="utf-8")
    monkeypatch.setenv("GOAL_DISPATCH_RELEASE_RECORD", str(record))
    return record


class _Trap:
    def __getattribute__(self, _name: str) -> Any:
        raise AssertionError("release-held flight check touched an effect owner")


def test_constructor_is_inert() -> None:
    check = BusFlightCheck(_Trap())
    assert check.thought_bus is not None
    assert check._subscribed is False
    assert check._running is False
    assert check._thread is None
    assert dict(check._activity) == {}


def test_start_and_watcher_hold_before_subscription_or_thread(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "aureon.vault.voice.bus_flight_check.threading.Thread",
        lambda *_args, **_kwargs: pytest.fail("flight check must not create a thread"),
    )
    check = BusFlightCheck(_Trap())
    with pytest.raises(RuntimeError, match="bus_flight_check_hold"):
        check.start()
    with pytest.raises(RuntimeError, match="bus_flight_check_hold"):
        check.start_watching()
    assert check._subscribed is False
    assert check._running is False
    assert check._thread is None


@pytest.mark.parametrize("entrypoint", ["callback", "loop", "publish"])
def test_direct_runtime_entrypoints_are_held(entrypoint: str) -> None:
    check = BusFlightCheck(_Trap())
    calls = {
        "callback": lambda: check._on_any_thought(_Trap()),
        "loop": check._watch_loop,
        "publish": lambda: check._publish_pulse({}),
    }
    with pytest.raises(RuntimeError, match="bus_flight_check_hold"):
        calls[entrypoint]()
    assert dict(check._activity) == {}


def test_singleton_getter_holds_without_creating_singleton() -> None:
    reset_bus_flight_check()
    assert flight_module._singleton is None
    with pytest.raises(RuntimeError, match="bus_flight_check_hold"):
        get_bus_flight_check(_Trap())
    assert flight_module._singleton is None


def test_topic_matching_remains_pure() -> None:
    assert BUS_FLIGHT_CHECK_RELEASE_HOLD.endswith(
        "production_magic_star_release_unavailable"
    )
    assert BusFlightCheck._matches("goal.completed", "goal.*") is True
    assert BusFlightCheck._matches("goal.completed", "persona.*") is False


# ─── Released path ───────────────────────────────────────────────────────────


class _Bus:
    def __init__(self) -> None:
        self.handlers: dict = {}
        self.published: list = []
        self._subs: dict = {}

    def subscribe(self, topic: str, handler) -> None:
        self.handlers.setdefault(topic, []).append(handler)
        self._subs.setdefault(topic, []).append(handler)

    def publish(self, *args: Any, **kwargs: Any) -> None:
        self.published.append(args[0] if args else kwargs)

    def list_subscribed_topics(self):
        return list(self._subs.keys())

    def subscriber_count(self, pattern: str) -> int:
        return len(self._subs.get(pattern, []))


class _Thought:
    def __init__(self, topic: str, source: str = "probe") -> None:
        self.topic = topic
        self.source = source


def test_released_start_observes_and_reports_topology(released) -> None:
    bus = _Bus()
    check = BusFlightCheck(bus)
    check.start()
    assert "*" in bus.handlers
    for handler in bus.handlers["*"]:
        handler(_Thought("goal.completed", "engine"))
        handler(_Thought("persona.collapse", "vacuum"))
    topo = check.topology()
    topics = {r["topic"] for r in topo["topics"]}
    assert {"goal.completed", "persona.collapse"} <= topics
    report = check.standing_wave_report()
    assert 0.0 <= report["health"] <= 1.0


def test_released_publish_pulse_emits_compact_report(released) -> None:
    bus = _Bus()
    check = BusFlightCheck(bus)
    check._publish_pulse({"ts": 1.0, "health": 0.5, "covered_ratio": 0.5,
                          "active_ratio": 0.5, "publication_balance": 0.5,
                          "active_topic_count": 1, "dormant_topic_count": 0,
                          "subscribed_topic_count": 1, "total_publications": 2,
                          "orphans_published_unsubscribed": [],
                          "orphans_subscribed_unpublished": []})
    pulses = [t for t in bus.published
              if getattr(t, "topic", "") == "flight.check.pulse"]
    assert len(pulses) == 1
    assert pulses[0].payload["health"] == 0.5


def test_released_singleton_getter_creates_and_resets(released) -> None:
    reset_bus_flight_check()
    bus = _Bus()
    check = get_bus_flight_check(bus)
    assert flight_module._singleton is check
    assert "*" in bus.handlers
    reset_bus_flight_check()
    assert flight_module._singleton is None
