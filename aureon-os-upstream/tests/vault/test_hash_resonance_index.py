"""Pure hash tests and fail-closed runtime-index tests."""

from __future__ import annotations

from typing import Any, Callable

import json

import pytest

from aureon.vault.voice.hash_resonance_index import (
    HASH_RESONANCE_RELEASE_HOLD,
    BondRecord,
    HashResonanceIndex,
    _bonding_fingerprint,
    _normalise_payload,
    bond_strength,
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
        "modules": ["hash_resonance_index"],
    }), encoding="utf-8")
    monkeypatch.setenv("GOAL_DISPATCH_RELEASE_RECORD", str(record))
    return record


class _Trap:
    def __getattribute__(self, _name: str) -> Any:
        raise AssertionError("release-held hash index touched an effect owner")


def test_hash_normalisation_and_strength_remain_pure() -> None:
    normalised = _normalise_payload({"ts": 1, "value": 1.23456, "name": "x"})
    assert normalised == {"name": "x", "value": 1.235}
    left = _bonding_fingerprint(
        persona="engineer", intent_phrase="build", payload={"ts": 1, "x": 2},
        source_topic="goal", category="intent",
    )
    right = _bonding_fingerprint(
        persona="engineer", intent_phrase="build", payload={"ts": 99, "x": 2},
        source_topic="goal", category="intent",
    )
    assert left == right
    assert bond_strength(1) == 0.0
    assert bond_strength(8) > bond_strength(2)
    assert HASH_RESONANCE_RELEASE_HOLD.startswith("hash_resonance_index_hold:")


def test_constructor_is_inert_and_empty_queries_are_local() -> None:
    index = HashResonanceIndex(vault=_Trap(), thought_bus=_Trap())
    assert index._subscribed is False
    assert index.summary()["total_cards"] == 0
    assert index.strongest_bonds() == []
    assert index.bond_count("missing") == 0
    assert index.fingerprint_for_content("missing") is None


@pytest.mark.parametrize(
    "factory",
    [
        lambda index, bond: index.start(),
        lambda index, bond: index.rebuild_from_vault(),
        lambda index, bond: index._on_vault_card_added(_Trap()),
        lambda index, bond: index._index_card(_Trap(), _publish=True),
        lambda index, bond: index._publish_bond(bond, 3),
    ],
)
def test_indexing_subscription_and_publish_paths_are_held(
    factory: Callable[[HashResonanceIndex, BondRecord], Any],
) -> None:
    index = HashResonanceIndex(vault=_Trap(), thought_bus=_Trap())
    bond = BondRecord("fp")
    with pytest.raises(RuntimeError, match="hash_resonance_index_hold"):
        factory(index, bond)
    assert index._subscribed is False
    assert index.summary()["total_cards"] == 0


# ─── Released path ───────────────────────────────────────────────────────────


class _Bus:
    def __init__(self) -> None:
        self.handlers: dict = {}
        self.published: list = []

    def subscribe(self, topic: str, handler: Any) -> None:
        self.handlers.setdefault(topic, []).append(handler)

    def publish(self, *args: Any, **kwargs: Any) -> None:
        self.published.append(args[0] if args else kwargs)


class _Card:
    def __init__(
        self,
        content_id: str,
        payload: Any = None,
        source_topic: str = "goal",
        category: str = "intent",
    ) -> None:
        self.content_id = content_id
        self.payload = payload or {}
        self.source_topic = source_topic
        self.category = category


def test_released_indexing_publishes_standing_wave_bond_at_threshold(released) -> None:
    bus = _Bus()
    index = HashResonanceIndex(vault=object(), thought_bus=bus)
    payload = {"persona": "engineer", "text": "build", "value": 1.23456}
    fp = None
    for i in range(3):
        fp = index._index_card(_Card(f"c{i}", payload), _publish=True)
    assert fp is not None
    assert index.bond_count(fp) == 3
    assert index.bond_strength(fp) == pytest.approx(bond_strength(3))
    bonds = [
        t for t in bus.published
        if getattr(t, "topic", None) == "standing.wave.bond"
    ]
    assert len(bonds) == 1
    assert bonds[0].payload["threshold_crossed"] == 3
    assert bonds[0].payload["count"] == 3


def test_released_start_subscribes_and_rebuild_is_safe(released) -> None:
    bus = _Bus()
    index = HashResonanceIndex(vault=object(), thought_bus=bus)
    index.start()
    assert "vault.card.added" in bus.handlers
    assert index._subscribed is True
    assert index.rebuild_from_vault() == 0
    # Re-indexing the same content_id must not double-count the bond.
    card = _Card("c0", {"persona": "engineer", "text": "build"})
    first = index._index_card(card, _publish=True)
    again = index._index_card(card, _publish=True)
    assert first == again
    assert index.bond_count(first) == 1
