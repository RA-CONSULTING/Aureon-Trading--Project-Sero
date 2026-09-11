"""Fail-closed and pure-math tests for PersonaVacuum."""

from __future__ import annotations

import json
import math
import random
from pathlib import Path
from typing import Any

import pytest

from aureon.vault.voice.affinity_chorus import AffinityChorus
from aureon.vault.voice.aureon_personas import build_aureon_personas
from aureon.vault.voice.persona_vacuum import (
    PersonaVacuum,
    _softmax,
    get_persona_vacuum,
)


@pytest.fixture(autouse=True)
def _default_held(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Default every test in this file to HOLD via a missing record path."""
    monkeypatch.setenv(
        "GOAL_DISPATCH_RELEASE_RECORD", str(tmp_path / "missing.json"))


@pytest.fixture
def released(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    record_dir = tmp_path / "record"
    record_dir.mkdir()
    record = record_dir / "dispatch_release.json"
    record.write_text(json.dumps({
        "ts": "2026-09-06",
        "source": "owner decree 2026-09-06 (Gary Leckey)",
        "modules": ["persona_vacuum", "persona_action"],
    }), encoding="utf-8")
    monkeypatch.setenv("GOAL_DISPATCH_RELEASE_RECORD", str(record))
    return record


class _Trap:
    def __getattribute__(self, _name: str) -> Any:
        raise AssertionError("release-held vacuum touched an effect owner")


def test_softmax_is_normalized_and_temperature_sensitive() -> None:
    cold = _softmax([0.0, 1.0, 2.0], 0.25)
    warm = _softmax([0.0, 1.0, 2.0], 2.0)
    assert math.isclose(sum(cold), 1.0, rel_tol=0.0, abs_tol=1e-12)
    assert math.isclose(sum(warm), 1.0, rel_tol=0.0, abs_tol=1e-12)
    assert cold[2] > warm[2]
    assert _softmax([], 1.0) == []


def test_constructor_is_inert_and_does_not_auto_wire_bus(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        PersonaVacuum,
        "_load_thought_bus",
        staticmethod(lambda: pytest.fail("constructor must not load ThoughtBus")),
    )
    monkeypatch.setattr(
        "aureon.vault.voice.persona_vacuum.build_aureon_personas",
        lambda *_args, **_kwargs: pytest.fail("constructor must not build provider personas"),
    )
    vacuum = PersonaVacuum(rng=random.Random(4))
    assert vacuum._thought_bus is None
    assert vacuum.persona_names == []
    assert vacuum.collapse_count == 0
    assert vacuum.last_winner is None
    assert vacuum.last_probabilities == {}
    assert vacuum.status() == {
        "status": "HOLD",
        "reason_code": "production_magic_star_release_unavailable",
        "production_ready": False,
        "effect_enabled": False,
        "subscribed": False,
        "persona_count": 0,
        "collapse_count": 0,
    }


def test_local_sampling_without_chorus_remains_pure_and_deterministic() -> None:
    personas_a = build_aureon_personas()
    personas_b = build_aureon_personas()
    state = {
        "love_amplitude": 0.7,
        "gratitude_score": 0.6,
        "cortex": {"gamma": 0.4},
        "coherence_gamma": 0.8,
        "consciousness_psi": 0.5,
        "node_readings": {},
        "dj_drop": {},
    }
    a = PersonaVacuum(personas=personas_a, rng=random.Random(9))
    b = PersonaVacuum(personas=personas_b, rng=random.Random(9))
    assert a._sample(state) == b._sample(state)
    assert a.collapse_count == 0
    assert b.collapse_count == 0


def test_start_observe_trigger_and_singleton_are_held() -> None:
    vacuum = PersonaVacuum(thought_bus=_Trap())
    for call in (
        vacuum.start,
        lambda: vacuum.observe(_Trap()),
        lambda: vacuum._on_observe_trigger(_Trap()),
        PersonaVacuum._load_thought_bus,
        get_persona_vacuum,
    ):
        with pytest.raises(RuntimeError, match="persona_vacuum_hold"):
            call()
    assert vacuum._subscribed is False
    assert vacuum.collapse_count == 0


def test_chorus_paths_hold_before_publish_or_merge() -> None:
    chorus = AffinityChorus(thought_bus=_Trap())
    vacuum = PersonaVacuum(
        personas=build_aureon_personas(),
        thought_bus=_Trap(),
        chorus=chorus,
    )
    with pytest.raises(RuntimeError, match="persona_vacuum_hold"):
        vacuum.contribute_affinity()
    with pytest.raises(RuntimeError, match="persona_vacuum_hold"):
        vacuum._sample({})
    assert chorus.contributions() == []


def test_private_provider_publish_and_vault_helpers_are_held() -> None:
    personas = build_aureon_personas(adapter=_Trap())
    vacuum = PersonaVacuum(personas=personas, thought_bus=_Trap(), vault=_Trap())
    persona = next(iter(personas.values()))
    calls = (
        lambda: vacuum._safe_speak(persona, _Trap(), {}),
        lambda: vacuum._publish_collapse("mystic", {}, {}, {}),
        lambda: vacuum._publish_thought(None),  # type: ignore[arg-type]
        lambda: vacuum._feed_vault(_Trap(), None),  # type: ignore[arg-type]
    )
    for call in calls:
        with pytest.raises(RuntimeError, match="persona_vacuum_hold"):
            call()


# ─── Released path ───────────────────────────────────────────────────────────


class _Bus:
    def __init__(self) -> None:
        self.handlers: dict = {}
        self.published: list = []

    def subscribe(self, topic: str, handler) -> None:
        self.handlers.setdefault(topic, []).append(handler)

    def publish(self, *args: Any, **kwargs: Any) -> None:
        self.published.append(args[0] if args else kwargs)


@pytest.fixture
def fusion_approved(monkeypatch: pytest.MonkeyPatch) -> None:
    """The vacuum's actuator gate needs a readable conscience hook (or a
    wired conscience) before dispatch proceeds."""
    import sys, types
    fake_hook = types.ModuleType("aureon_fusion.conscience_hook")
    fake_hook.evaluate = lambda *_a, **_k: {  # type: ignore[attr-defined]
        "verdict": "APPROVED", "reasoning": "probe"}
    pkg = types.ModuleType("aureon_fusion")
    monkeypatch.setitem(sys.modules, "aureon_fusion", pkg)
    monkeypatch.setitem(sys.modules, "aureon_fusion.conscience_hook", fake_hook)


def test_released_status_reports_released(released: Path) -> None:
    vacuum = PersonaVacuum(rng=random.Random(4))
    status = vacuum.status()
    assert status["status"] == "RELEASED"
    assert status["production_ready"] is True
    assert status["effect_enabled"] is True


def test_released_start_subscribes_trigger_topics(released: Path) -> None:
    bus = _Bus()
    vacuum = PersonaVacuum(personas=build_aureon_personas(), thought_bus=bus)
    vacuum.start()
    for topic in ("dj.track.drop", "queen.source_law.cognition",
                  "persona.observe", "symbolic.life.pulse"):
        assert topic in bus.handlers
    assert vacuum.status()["subscribed"] is True


def test_released_observe_collapses_and_publishes(
    released: Path, fusion_approved: None
) -> None:
    bus = _Bus()
    vacuum = PersonaVacuum(
        personas=build_aureon_personas(), thought_bus=bus, rng=random.Random(9))
    statement = vacuum.observe()
    assert vacuum.collapse_count == 1
    assert vacuum.last_winner in vacuum.persona_names
    topics = [getattr(t, "topic", None) for t in bus.published]
    assert "persona.collapse" in topics
    assert "persona.thought" in topics
    assert statement is None or statement.voice == vacuum.last_winner
