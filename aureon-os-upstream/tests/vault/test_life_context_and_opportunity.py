"""Pure life-context tests and fail-closed opportunity-scanner tests."""

from __future__ import annotations

from typing import Any

import json

import pytest

from aureon.vault.voice.aureon_personas import (
    ArtistVoice,
    EngineerVoice,
    MysticVoice,
    QuantumPhysicistVoice,
)
from aureon.vault.voice.life_context import LifeContext, LifeEvent
from aureon.vault.voice.opportunity_scanner import OpportunityHit, OpportunityScanner
from aureon.vault.voice.persona_action import PersonaActuator


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
        "modules": ["life_context", "opportunity_scanner", "persona_action"],
    }), encoding="utf-8")
    monkeypatch.setenv("GOAL_DISPATCH_RELEASE_RECORD", str(record))
    return record


class _Trap:
    def __getattribute__(self, _name: str) -> Any:
        raise AssertionError("release-held opportunity path touched an effect owner")


def test_life_event_round_trip_payload() -> None:
    event = LifeEvent(
        event_id="e1",
        title="Wedding in May",
        tags=["wedding", "family"],
        date="May 12",
    )
    payload = event.to_dict()
    assert payload["event_id"] == "e1"
    assert payload["title"] == "Wedding in May"
    assert payload["tags"] == ["wedding", "family"]
    assert payload["date"] == "May 12"


def test_life_context_local_add_archive_complete_and_remove() -> None:
    context = LifeContext()
    wedding = context.add("Wedding in May", tags=["wedding"], date="May 12")
    work = context.add("Finish design for work", tags=["work"])
    assert {event.event_id for event in context.active()} == {wedding.event_id, work.event_id}
    assert context.archive(wedding.event_id) is True
    assert {event.event_id for event in context.active()} == {work.event_id}
    assert context.complete(work.event_id) is True
    assert context.active() == []
    assert context.remove(wedding.event_id) is True


def test_life_context_vault_mutation_and_reload_paths_are_held() -> None:
    context = LifeContext(vault=_Trap())
    with pytest.raises(RuntimeError, match="life_context_hold"):
        context.add("Must not persist")
    assert len(context) == 0

    local = LifeContext()
    event = local.add("Local draft")
    local._vault = _Trap()
    with pytest.raises(RuntimeError, match="life_context_hold"):
        local.archive(event.event_id)
    assert event.status == "active"
    with pytest.raises(RuntimeError, match="life_context_hold"):
        local.complete(event.event_id)
    assert event.status == "active"
    with pytest.raises(RuntimeError, match="life_context_hold"):
        local._persist(event)
    with pytest.raises(RuntimeError, match="life_context_hold"):
        local.load_from_vault(_Trap())


def test_persona_opportunity_scans_are_pure() -> None:
    wedding = LifeEvent("w", "Wedding in May", tags=["wedding"], date="May 12")
    research = LifeEvent("r", "Research thesis", tags=["research"])
    work = LifeEvent("x", "Work deadline", tags=["work"])
    assert "visual" in (ArtistVoice().scan_for_opportunity(wedding) or "")
    assert "528 Hz" in (MysticVoice().scan_for_opportunity(wedding) or "")
    assert "most-cited" in (QuantumPhysicistVoice().scan_for_opportunity(research) or "")
    assert "small tool" in (EngineerVoice().scan_for_opportunity(work) or "")


def test_scanner_start_scan_dispatch_and_loop_are_held(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "aureon.vault.voice.opportunity_scanner.threading.Thread",
        lambda *_args, **_kwargs: pytest.fail("scanner must not create a thread"),
    )
    context = LifeContext()
    event = context.add("Wedding in May", tags=["wedding"])
    scanner = OpportunityScanner(
        personas={"artist": ArtistVoice()},
        life_context=context,
        actuator=PersonaActuator(thought_bus=_Trap()),
    )
    hit = OpportunityHit("artist", event.event_id, "build a visual", 0.7)
    calls = (
        scanner.start,
        scanner.scan_once,
        lambda: scanner._dispatch(hit, event),
        scanner._loop,
    )
    for call in calls:
        with pytest.raises(RuntimeError, match="opportunity_scanner_hold"):
            call()
    assert scanner.running is False
    assert scanner.history() == []


# ─── Released path ───────────────────────────────────────────────────────────


class _Vault:
    def __init__(self) -> None:
        self.ingested: list = []

    def ingest(self, topic: str, payload: Any) -> None:
        self.ingested.append((topic, payload))


class _Bus:
    def __init__(self) -> None:
        self.handlers: dict = {}
        self.published: list = []

    def subscribe(self, topic: str, handler: Any) -> None:
        self.handlers.setdefault(topic, []).append(handler)

    def publish(self, *args: Any, **kwargs: Any) -> None:
        self.published.append(args[0] if args else kwargs)


class _ApprovedConscience:
    def ask_why(self, *_args: Any, **_kwargs: Any) -> Any:
        class _Whisper:
            verdict = "APPROVED"
            message = "probe"
        return _Whisper()


def test_released_life_context_add_persists_life_event_card(released) -> None:
    vault = _Vault()
    context = LifeContext(vault=vault)
    event = context.add("Wedding in May", tags=["wedding"], date="May 12")
    topics = [topic for topic, _ in vault.ingested]
    assert topics == ["life.event"]
    payload = vault.ingested[0][1]
    assert payload["event_id"] == event.event_id
    assert payload["title"] == "Wedding in May"
    assert context.complete(event.event_id) is True
    assert vault.ingested[-1][1]["status"] == "completed"


def test_released_scanner_dispatches_goal_submit_through_actuator(released) -> None:
    bus = _Bus()
    context = LifeContext()
    event = context.add("Wedding in May", tags=["wedding"])
    actuator = PersonaActuator(thought_bus=bus, conscience=_ApprovedConscience())
    scanner = OpportunityScanner(
        personas={"artist": ArtistVoice()},
        life_context=context,
        actuator=actuator,
    )
    hits = scanner.scan_once()
    assert len(hits) == 1
    assert hits[0].persona == "artist"
    assert hits[0].event_id == event.event_id
    # The actuator's conscience gate passed and the goal went on the bus.
    submissions = [
        t for t in bus.published
        if getattr(t, "topic", None) == "goal.submit.request"
    ]
    assert len(submissions) == 1
    assert submissions[0].payload["proposed_by_persona"] == "artist"
    assert submissions[0].payload["parameters"]["source"] == "opportunity_scanner"
    history = actuator.history()
    assert len(history) == 1
    assert history[0]["ok"] is True
    assert history[0]["error"] == ""
    assert scanner.history() == [hits[0].to_dict()]
