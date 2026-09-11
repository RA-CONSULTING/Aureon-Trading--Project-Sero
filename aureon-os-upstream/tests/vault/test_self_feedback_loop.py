"""Fail-closed + released-path contract for the self-feedback effect owner.

Release state is read from the core release record
(``aureon_fusion/state/vault/core_release.json``, overridable via the
``AUREON_CORE_RELEASE_RECORD`` env var). Every HOLD-behavior test drives
the hold by pointing that env var at a path that does NOT exist —
proving the fail-closed property (no record → every effect method still
raises ``SELF_FEEDBACK_RELEASE_HOLD``). The released-path tests write a
valid record to a tmp file and point the env var at it.
"""

from __future__ import annotations

import json

import pytest

from aureon.vault import self_feedback_loop as loop_module
from aureon.vault.self_feedback_loop import AureonSelfFeedbackLoop
from aureon.vault.aureon_vault import AureonVault
from aureon.vault.casimir_quantifier import CasimirQuantifier
from aureon.vault.harmonic_pinger import HarmonicPinger

_HOLD_ENV_VAR = "AUREON_CORE_RELEASE_RECORD"
_ALL_CORE_MODULES = (
    "aureon_vault",
    "casimir_quantifier",
    "harmonic_pinger",
    "self_feedback_loop",
)


def _write_release_record(path, *modules):
    path.write_text(json.dumps({
        "ts": "2026-09-06",
        "source": "owner decree 2026-09-06 (Gary Leckey)",
        "modules": list(modules),
    }), encoding="utf-8")
    return path


@pytest.fixture
def held(monkeypatch, tmp_path):
    """Point the release record at a path that does not exist → HOLD."""
    missing = tmp_path / "no_such_core_release.json"
    monkeypatch.setenv(_HOLD_ENV_VAR, str(missing))
    return missing


@pytest.fixture
def released_all(monkeypatch, tmp_path):
    """Point the release record at a valid record naming all core modules."""
    record = _write_release_record(
        tmp_path / "core_release.json", *_ALL_CORE_MODULES)
    monkeypatch.setenv(_HOLD_ENV_VAR, str(record))
    return record


def test_default_constructor_is_inert_and_provider_modules_are_not_loaded() -> None:
    loop = AureonSelfFeedbackLoop(base_interval_s=0.01)

    assert loop._running is False
    assert loop._thread is None
    assert loop.voice_engine is None
    assert loop._enhance_enabled is False
    assert loop._enhancer is None
    assert loop.vault._thought_bus is None
    assert loop.vault._subscribed is False
    assert loop.casimir._engine is None
    assert loop.casimir._engine_kind == "stub"
    assert loop.pinger._chirp_bus is None
    assert loop.pinger._thought_bus is None
    assert loop_module.SelfDialogueEngine is None
    assert loop_module.get_self_enhancement_engine is None


@pytest.mark.parametrize(
    "flag",
    [
        "auto_wire_bus",
        "enable_voice",
        "enable_self_enhancement",
        "enable_native_casimir",
        "enable_harmonic_buses",
    ],
)
def test_every_effectful_constructor_option_is_held(flag: str, held) -> None:
    with pytest.raises(RuntimeError, match="aureon_self_feedback_loop_hold"):
        AureonSelfFeedbackLoop(**{flag: True})


def test_tick_run_and_start_hold_before_vault_bus_coder_or_thread(
    monkeypatch: pytest.MonkeyPatch,
    held,
) -> None:
    loop = AureonSelfFeedbackLoop()
    monkeypatch.setattr(
        loop.vault,
        "ingest",
        lambda *_args, **_kwargs: pytest.fail("HOLD must not ingest"),
    )
    monkeypatch.setattr(
        loop_module.threading,
        "Thread",
        lambda *_args, **_kwargs: pytest.fail("HOLD must not create thread"),
    )
    loop._enhancer = type(
        "GuardedEnhancer",
        (),
        {"enhance_once": lambda _self: pytest.fail("HOLD must not self-code")},
    )()
    loop._enhance_enabled = True

    for effect in (
        loop.tick,
        lambda: loop.run(cycles=1),
        loop.start,
    ):
        with pytest.raises(RuntimeError, match="aureon_self_feedback_loop_hold"):
            effect()

    assert loop._cycle == 0
    assert loop._running is False
    assert loop._thread is None
    assert loop.tick_history == []


def test_singleton_accessor_creates_only_an_inert_loop(
    monkeypatch: pytest.MonkeyPatch,
    held,
) -> None:
    monkeypatch.setattr(loop_module, "_loop_instance", None)

    first = loop_module.get_self_feedback_loop()
    second = loop_module.get_self_feedback_loop()

    assert first is second
    assert first.voice_engine is None
    assert first._enhance_enabled is False
    with pytest.raises(RuntimeError, match="aureon_self_feedback_loop_hold"):
        first.tick()


# ─── Released path (record names the module) ─────────────────────────────────


@pytest.mark.parametrize(
    "flag",
    [
        "auto_wire_bus",
        "enable_voice",
        "enable_self_enhancement",
        "enable_native_casimir",
        "enable_harmonic_buses",
    ],
)
def test_effectful_constructor_options_open_when_released(
    monkeypatch: pytest.MonkeyPatch,
    released_all,
    flag: str,
) -> None:
    """With a valid record the loop's own gate opens. Keep the sub-organs'
    real attachments (shared-memory ChirpBus, process ThoughtBus, native
    miner engine) stubbed — those have their own gates and hazards."""
    monkeypatch.setattr(
        AureonVault, "wire_thought_bus", lambda self: True)
    monkeypatch.setattr(
        HarmonicPinger, "_load_chirp_bus", lambda self: None)
    monkeypatch.setattr(
        HarmonicPinger, "_load_thought_bus", lambda self: None)
    monkeypatch.setattr(
        CasimirQuantifier, "_load_engine", lambda self: None)

    loop = AureonSelfFeedbackLoop(**{flag: True})

    # Voice and self-enhancement providers are voice/queen-owned and are
    # NOT released here — they must stay inert even with a core record.
    assert loop.voice_engine is None
    assert loop._enhance_enabled is False


def test_released_tick_runs_full_local_cycle(released_all) -> None:
    """tick chains into casimir.measure and pinger.ping — those modules'
    own gates must also see the record (chained release)."""
    loop = AureonSelfFeedbackLoop(base_interval_s=0.01)

    results = loop.run(cycles=2)

    assert len(results) == 2
    assert loop._cycle == 2
    assert loop._running is False
    assert loop.tick_history == results
    last = results[-1]
    # No buses are wired in this in-memory run: honest no-send ping.
    assert last.ping_sent is False
    assert 0.0 <= last.casimir_force <= 10.0
    # Inert providers stay inert on the released path too.
    assert last.spoke is False
    assert loop.voice_engine is None
    # Bootstrap ingest fires once per tick while the vault has < 3 cards.
    assert last.vault_size >= 2

    # start/stop also run on the released path (daemon thread, real tick).
    loop.start()
    assert loop._running is True
    loop.stop()
    assert loop._running is False
