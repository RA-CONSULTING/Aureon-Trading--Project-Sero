"""Fail-closed + released-path tests for the persona action surface.

Released by owner decree 2026-09-06 via the shared release record
(``aureon_fusion/state/goals/dispatch_release.json``, read through
``_goal_release``). HOLD tests point ``GOAL_DISPATCH_RELEASE_RECORD`` at a
path that does NOT exist. On the released path ``dispatch`` is
conscience-gated fail-closed: VETO refuses, an unreadable conscience hook
refuses (no primary gate of its own), and refusals are recorded as
``ok=False`` ActionExecutions.
"""

from __future__ import annotations

import json
import sys
import types
from enum import Enum, auto
from pathlib import Path
from typing import Any

import pytest

from aureon.vault.voice.persona_action import (
    PERSONA_ACTION_RELEASE_HOLD,
    PersonaAction,
    PersonaActuator,
)


class _Trap:
    def __getattribute__(self, _name: str) -> Any:
        raise AssertionError("release-held persona path touched an effect owner")


def _write_release_record(path: Path, *modules: str) -> Path:
    path.write_text(json.dumps({
        "ts": "2026-09-06",
        "source": "owner decree 2026-09-06 (Gary Leckey)",
        "modules": list(modules),
    }), encoding="utf-8")
    return path


@pytest.fixture
def held(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    missing = tmp_path / "no_such_release.json"
    monkeypatch.setenv("GOAL_DISPATCH_RELEASE_RECORD", str(missing))
    return missing


@pytest.fixture
def released(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    record_dir = tmp_path / "record"
    record_dir.mkdir()
    record = _write_release_record(
        record_dir / "dispatch_release.json", "persona_action")
    monkeypatch.setenv("GOAL_DISPATCH_RELEASE_RECORD", str(record))
    return record


@pytest.fixture
def fusion_approved(monkeypatch: pytest.MonkeyPatch) -> None:
    """Inject a fake aureon_fusion.conscience_hook that approves."""
    fake_hook = types.ModuleType("aureon_fusion.conscience_hook")
    fake_hook.evaluate = lambda *_a, **_k: {  # type: ignore[attr-defined]
        "verdict": "APPROVED", "reasoning": "probe",
    }
    pkg = types.ModuleType("aureon_fusion")
    monkeypatch.setitem(sys.modules, "aureon_fusion", pkg)
    monkeypatch.setitem(sys.modules, "aureon_fusion.conscience_hook", fake_hook)


def _action(kind: str, tmp_path: Path) -> PersonaAction:
    return PersonaAction(
        kind=kind,
        topic="probe.topic",
        target=str(tmp_path / "probe.jsonl"),
        payload={"value": 1},
        reason="safety probe",
        urgency=0.9,
    )


# ─── Pure / inert ────────────────────────────────────────────────────────────


def test_persona_action_to_dict_and_defaults_are_pure() -> None:
    action = PersonaAction(kind="bus.publish")
    assert action.topic == ""
    assert action.payload == {}
    assert action.target == ""
    assert action.reason == ""
    assert action.urgency == 0.5
    assert action.to_dict()["kind"] == "bus.publish"


def test_actuator_construction_only_registers_handlers(
    held: Path, tmp_path: Path
) -> None:
    actuator = PersonaActuator(
        thought_bus=_Trap(), vault=_Trap(), file_root=str(tmp_path),
    )
    assert set(actuator._handlers) == {
        "bus.publish", "vault.ingest", "file.append",
        "skill.request", "goal.submit",
    }
    assert actuator.history() == []
    assert actuator.status()["status"] == "HOLD"
    assert actuator.status()["effect_enabled"] is False
    assert [p for p in tmp_path.iterdir() if p.name != "record"] == []


# ─── HOLD behavior (driven by an absent release record) ──────────────────────


@pytest.mark.parametrize(
    "kind",
    ["bus.publish", "vault.ingest", "file.append", "skill.request",
     "goal.submit", "unknown.kind"],
)
def test_dispatch_holds_before_handler_bus_vault_or_file(
    kind: str, held: Path, tmp_path: Path,
) -> None:
    actuator = PersonaActuator(
        thought_bus=_Trap(), vault=_Trap(), file_root=str(tmp_path),
    )
    with pytest.raises(RuntimeError, match="persona_action_hold"):
        actuator.dispatch("engineer", _action(kind, tmp_path), {"persona": "engineer"})
    assert actuator.history() == []
    assert [p for p in tmp_path.iterdir() if p.name != "record"] == []


def test_dispatch_none_and_custom_handlers_cannot_bypass_hold(
    held: Path, tmp_path: Path
) -> None:
    calls: list[str] = []
    actuator = PersonaActuator(file_root=str(tmp_path))
    actuator.register("custom", lambda *_args: calls.append("called"))
    with pytest.raises(RuntimeError, match="persona_action_hold"):
        actuator.dispatch("persona", None)
    with pytest.raises(RuntimeError, match="persona_action_hold"):
        actuator.dispatch("persona", _action("custom", tmp_path))
    assert calls == []
    assert actuator.history() == []


@pytest.mark.parametrize(
    "handler_name",
    [
        "_handle_bus_publish", "_handle_vault_ingest", "_handle_file_append",
        "_handle_skill_request", "_handle_goal_submit",
    ],
)
def test_direct_default_handler_calls_hold(
    handler_name: str, held: Path, tmp_path: Path
) -> None:
    actuator = PersonaActuator(
        thought_bus=_Trap(), vault=_Trap(), file_root=str(tmp_path),
    )
    handler = getattr(actuator, handler_name)
    with pytest.raises(RuntimeError, match="persona_action_hold"):
        handler(_action("file.append", tmp_path), {"persona": "engineer"})
    assert [p for p in tmp_path.iterdir() if p.name != "record"] == []


# ─── Released path ───────────────────────────────────────────────────────────


class _Bus:
    def __init__(self) -> None:
        self.published: list = []

    def publish(self, *args: Any, **kwargs: Any) -> None:
        self.published.append(args[0] if args else kwargs)


class _V(Enum):
    APPROVED = auto()
    VETO = auto()


class _Whisper:
    def __init__(self, verdict: Any) -> None:
        self.verdict = verdict
        self.message = "stop"
        self.why_it_matters = "unsafe"


class _Conscience:
    def __init__(self, verdict: Any = _V.APPROVED, fail: bool = False) -> None:
        self.verdict = verdict
        self.fail = fail
        self.asked: list = []

    def ask_why(self, text: str, context: dict) -> Any:
        self.asked.append(text)
        if self.fail:
            raise RuntimeError("conscience down")
        return _Whisper(self.verdict)


def test_released_dispatch_publishes_on_bus(
    released: Path, fusion_approved: None, tmp_path: Path
) -> None:
    bus = _Bus()
    actuator = PersonaActuator(thought_bus=bus, file_root=str(tmp_path))
    record = actuator.dispatch(
        "engineer", _action("bus.publish", tmp_path), {"persona": "engineer"})
    assert record is not None and record.ok is True
    assert len(bus.published) == 1
    assert actuator.status()["status"] == "RELEASED"
    assert actuator.status()["effect_enabled"] is True


def test_released_dispatch_appends_file(
    released: Path, fusion_approved: None, tmp_path: Path
) -> None:
    actuator = PersonaActuator(file_root=str(tmp_path))
    record = actuator.dispatch(
        "engineer", _action("file.append", tmp_path), {"persona": "engineer"})
    assert record is not None and record.ok is True
    target = tmp_path / "probe.jsonl"
    assert target.exists()
    assert "safety probe" in target.read_text(encoding="utf-8")


def test_released_dispatch_refuses_on_fusion_veto(
    released: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fake_hook = types.ModuleType("aureon_fusion.conscience_hook")
    fake_hook.evaluate = lambda *_a, **_k: {  # type: ignore[attr-defined]
        "verdict": "VETO", "reasoning": "organism-level veto",
    }
    pkg = types.ModuleType("aureon_fusion")
    monkeypatch.setitem(sys.modules, "aureon_fusion", pkg)
    monkeypatch.setitem(sys.modules, "aureon_fusion.conscience_hook", fake_hook)

    bus = _Bus()
    actuator = PersonaActuator(thought_bus=bus, file_root=str(tmp_path))
    record = actuator.dispatch(
        "engineer", _action("bus.publish", tmp_path), {"persona": "engineer"})

    assert record is not None and record.ok is False
    assert "fusion conscience veto" in record.error
    assert bus.published == [], "vetoed action must never reach the bus"
    assert actuator.history()[-1]["ok"] is False


def test_released_dispatch_fail_closed_without_any_gate(
    released: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """No wired conscience and an unimportable fusion hook → refuse. The
    module ships no enforceable gate of its own, so an unreadable hook is
    a refusal, never a silent pass."""
    monkeypatch.setitem(sys.modules, "aureon_fusion", None)

    bus = _Bus()
    actuator = PersonaActuator(thought_bus=bus, file_root=str(tmp_path))
    record = actuator.dispatch(
        "engineer", _action("bus.publish", tmp_path), {"persona": "engineer"})

    assert record is not None and record.ok is False
    assert "conscience_gate_unavailable" in record.error
    assert bus.published == []
    assert [p for p in tmp_path.iterdir() if p.name != "record"] == []


def test_released_wired_conscience_veto_refuses(
    released: Path, tmp_path: Path
) -> None:
    bus = _Bus()
    actuator = PersonaActuator(
        thought_bus=bus, file_root=str(tmp_path),
        conscience=_Conscience(_V.VETO),
    )
    record = actuator.dispatch(
        "engineer", _action("bus.publish", tmp_path), {"persona": "engineer"})
    assert record is not None and record.ok is False
    assert record.error.startswith("conscience_veto")
    assert bus.published == []


def test_released_wired_conscience_error_refuses(
    released: Path, tmp_path: Path
) -> None:
    bus = _Bus()
    actuator = PersonaActuator(
        thought_bus=bus, file_root=str(tmp_path),
        conscience=_Conscience(fail=True),
    )
    record = actuator.dispatch(
        "engineer", _action("bus.publish", tmp_path), {"persona": "engineer"})
    assert record is not None and record.ok is False
    assert record.error.startswith("conscience_gate_error")
    assert bus.published == []


def test_released_primary_gate_pass_allows_missing_hook_skip(
    released: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Primary ask_why gate passed → an unimportable fusion hook is
    logged+skipped (GoalDispatchBridge precedent), dispatch proceeds."""
    monkeypatch.setitem(sys.modules, "aureon_fusion", None)

    bus = _Bus()
    actuator = PersonaActuator(
        thought_bus=bus, file_root=str(tmp_path),
        conscience=_Conscience(_V.APPROVED),
    )
    record = actuator.dispatch(
        "engineer", _action("bus.publish", tmp_path), {"persona": "engineer"})
    assert record is not None and record.ok is True
    assert len(bus.published) == 1


def test_released_unknown_kind_records_no_handler(
    released: Path, fusion_approved: None, tmp_path: Path
) -> None:
    actuator = PersonaActuator(file_root=str(tmp_path))
    record = actuator.dispatch(
        "engineer", _action("mystery.kind", tmp_path), {"persona": "engineer"})
    assert record is not None and record.ok is False
    assert "no handler registered" in record.error


def test_hold_constant_shape() -> None:
    assert PERSONA_ACTION_RELEASE_HOLD.count(":") == 1
    assert PERSONA_ACTION_RELEASE_HOLD.endswith(
        "production_magic_star_release_unavailable"
    )
