"""Read-only audit tests and fail-closed patch tests."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import json

import pytest

from aureon.vault.voice.vault_feed_audit import (
    VAULT_FEED_AUDIT_RELEASE_HOLD,
    VaultFeedAudit,
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
        "modules": ["vault_feed_audit"],
    }), encoding="utf-8")
    monkeypatch.setenv("GOAL_DISPATCH_RELEASE_RECORD", str(record))
    return record


class _Trap:
    def __getattribute__(self, _name: str) -> Any:
        raise AssertionError("release-held vault patch touched an effect owner")


class _FlightReadStub:
    def topology(self):
        return {
            "topics": [
                {"topic": "goal.completed", "publications": 6},
                {"topic": "persona.collapse", "publications": 1},
            ]
        }


class _VaultReadStub:
    DEFAULT_SUBSCRIPTIONS = ["persona.*"]
    _contents = {
        "c1": SimpleNamespace(source_topic="persona.collapse"),
    }


def test_read_only_coverage_and_subscription_diff_remain_available() -> None:
    audit = VaultFeedAudit(_VaultReadStub(), _FlightReadStub())
    report = audit.coverage_report()
    assert report["high_severity_dead_branches"] == ["goal.completed"]
    assert report["covered_count"] == 1
    patch = audit.subscription_patch()
    assert patch["missing_topics"] == ["goal.completed"]
    assert patch["already_covered_topics"] == ["persona.collapse"]
    assert audit.last_report()["total_topics"] == 2


@pytest.mark.parametrize("rewire", [False, True])
def test_apply_patch_holds_before_diff_mutation_or_subscription(rewire: bool) -> None:
    audit = VaultFeedAudit(_Trap(), _Trap())
    with pytest.raises(RuntimeError, match="vault_feed_audit_hold"):
        audit.apply_patch(rewire=rewire)
    assert audit.last_report() == {}
    assert VAULT_FEED_AUDIT_RELEASE_HOLD.endswith(
        "production_magic_star_release_unavailable"
    )


# ─── Released path ───────────────────────────────────────────────────────────


class _FlightStub:
    def topology(self):
        return {"topics": [
            {"topic": "goal.completed", "publications": 6},
            {"topic": "persona.collapse", "publications": 1},
        ]}


class _VaultStub:
    DEFAULT_SUBSCRIPTIONS = ["persona.*"]
    _contents = {}
    _thought_bus = None
    _on_thought = None


class _RewireBus:
    def __init__(self):
        self.wired: list = []

    def subscribe(self, topic: str, handler) -> None:
        self.wired.append(topic)


def test_released_apply_patch_widens_subscriptions_and_rewires(released) -> None:
    class Vault(_VaultStub):
        pass

    vault = Vault()
    vault._thought_bus = _RewireBus()
    vault._on_thought = lambda *_a, **_k: None
    audit = VaultFeedAudit(vault, _FlightStub())
    result = audit.apply_patch(rewire=True)
    assert result["ok"] is True
    assert result["added"] == ["goal.completed"]
    assert result["rewired"] == ["goal.completed"]
    assert "goal.completed" in vault.DEFAULT_SUBSCRIPTIONS
    assert vault._thought_bus.wired == ["goal.completed"]


def test_released_apply_patch_without_rewire_only_widens(released) -> None:
    class Vault(_VaultStub):
        pass

    vault = Vault()
    audit = VaultFeedAudit(vault, _FlightStub())
    result = audit.apply_patch(rewire=False)
    assert result["added"] == ["goal.completed"]
    assert result["rewired"] == []
