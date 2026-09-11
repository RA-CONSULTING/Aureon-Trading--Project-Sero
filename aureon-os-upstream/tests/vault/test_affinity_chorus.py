"""Pure aggregation and release-HOLD tests for AffinityChorus."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import pytest

from aureon.vault.voice.affinity_chorus import (
    AffinityChorus,
    AffinityContribution,
    make_vault_seed_fn,
    vault_fingerprint_seed,
)
from aureon.vault.voice.aureon_personas import build_aureon_personas
from aureon.vault.voice.persona_vacuum import PersonaVacuum


@pytest.fixture(autouse=True)
def _default_held(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
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
        "modules": ["affinity_chorus", "persona_vacuum", "persona_action"],
    }), encoding="utf-8")
    monkeypatch.setenv("GOAL_DISPATCH_RELEASE_RECORD", str(record))
    return record


class _Trap:
    def __getattribute__(self, _name: str) -> Any:
        raise AssertionError("release-held chorus touched an effect owner")


def test_contribution_payload_is_a_copy() -> None:
    contribution = AffinityContribution("peer", {"mystic": 2.0}, ts=4.0)
    payload = contribution.to_payload()
    payload["scores"]["mystic"] = 9.0
    assert contribution.scores["mystic"] == 2.0


def test_add_replace_merge_and_clear_are_local_only() -> None:
    chorus = AffinityChorus(ttl_s=60.0)
    chorus.add("a", {"mystic": 2.0, "engineer": 0.0}, ts=time.time())
    chorus.add("b", {"mystic": 0.0, "engineer": 2.0}, ts=time.time())
    assert chorus.peer_count() == 2
    assert chorus.merged() == {"mystic": 1.0, "engineer": 1.0}
    chorus.add("a", {"mystic": 4.0}, ts=time.time())
    assert chorus.peer_count() == 2
    merged = chorus.merged(self_scores={"engineer": 4.0}, self_peer_id="local")
    assert merged["mystic"] == pytest.approx(4.0 / 3.0)
    assert merged["engineer"] == pytest.approx(2.0)
    chorus.clear()
    assert chorus.contributions() == []


def test_stale_contributions_are_pruned_by_pure_merge() -> None:
    chorus = AffinityChorus(ttl_s=0.01)
    chorus.add("stale", {"x": 1.0}, ts=time.time() - 1.0)
    assert chorus.merged() == {}
    assert chorus.peer_count() == 0


def test_bus_start_and_publish_are_held_before_subscription_or_local_stamp() -> None:
    chorus = AffinityChorus(thought_bus=_Trap())
    with pytest.raises(RuntimeError, match="affinity_chorus_hold"):
        chorus.start()
    with pytest.raises(RuntimeError, match="affinity_chorus_hold"):
        chorus.publish("peer", {"mystic": 1.0})
    assert chorus._subscribed is False
    assert chorus.contributions() == []


def test_vault_seed_is_stable_and_changes_with_fingerprint() -> None:
    class Vault:
        def __init__(self, value: str):
            self.value = value

        def fingerprint(self) -> str:
            return self.value

    a = Vault("a")
    b = Vault("b")
    assert vault_fingerprint_seed(a) == vault_fingerprint_seed(a)
    assert vault_fingerprint_seed(a) != vault_fingerprint_seed(b)
    assert make_vault_seed_fn(a)() == vault_fingerprint_seed(a)


def test_vacuum_cannot_publish_or_merge_chorus_contributions() -> None:
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


# ─── Released path ───────────────────────────────────────────────────────────


class _Bus:
    def __init__(self) -> None:
        self.handlers: dict = {}
        self.published: list = []

    def subscribe(self, topic: str, handler) -> None:
        self.handlers.setdefault(topic, []).append(handler)

    def publish(self, *args: Any, **kwargs: Any) -> None:
        self.published.append(args[0] if args else kwargs)


def test_released_start_subscribes_and_publish_stamps_local(released: Path) -> None:
    bus = _Bus()
    chorus = AffinityChorus(thought_bus=bus)
    chorus.start()
    assert AffinityChorus.TOPIC in bus.handlers
    chorus.publish("peer-a", {"mystic": 2.0})
    assert chorus.merged() == {"mystic": 2.0}
    published = [t for t in bus.published
                 if getattr(t, "topic", "") == AffinityChorus.TOPIC]
    assert len(published) == 1
    assert published[0].payload["peer_id"] == "peer-a"


def test_released_vacuum_contributes_and_samples_through_chorus(
    released: Path,
) -> None:
    bus = _Bus()
    chorus = AffinityChorus(thought_bus=bus, ttl_s=60.0)
    import random
    vacuum = PersonaVacuum(
        personas=build_aureon_personas(),
        thought_bus=bus,
        chorus=chorus,
        rng=random.Random(3),
    )
    scores = vacuum.contribute_affinity()
    assert scores, "local affinity vector must be returned for inspection"
    assert chorus.merged(), "contribution must land in the chorus"
    winner, probs, _ = vacuum._sample({})
    assert winner in vacuum.persona_names
    assert abs(sum(probs.values()) - 1.0) < 1e-9
