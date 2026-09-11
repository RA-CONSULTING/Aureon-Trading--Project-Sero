"""Release-record gate tests for the voice modules without dedicated
held/released coverage elsewhere.

Every gated module must fail closed (raise its ``*_hold`` RuntimeError)
while the shared release record is absent, invalid, or does not name it,
and run once the record names it. ``preflight()``-style introspection must
report the gate honestly in both states without ever opening the effect
path by itself.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

import pytest

from aureon.vault import (  # noqa: E402
    AureonVault,
    ChoiceGate,
    SelfDialogueEngine,
    ThoughtStreamLoop,
    build_all_voices,
)
from aureon.vault.voice import document_artifact_skill
from aureon.vault.voice import whole_knowledge_voice
from aureon.vault.voice.document_artifact_skill import (
    DOCUMENT_ARTIFACT_RELEASE_HOLD,
)
from aureon.vault.voice.whole_knowledge_voice import (
    WHOLE_KNOWLEDGE_VOICE_RELEASE_HOLD,
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
        "modules": [
            "vault_voice",
            "self_dialogue",
            "thought_stream_loop",
            "whole_knowledge_voice",
            "document_artifact_skill",
        ],
    }), encoding="utf-8")
    monkeypatch.setenv("GOAL_DISPATCH_RELEASE_RECORD", str(record))
    return record


class _SilentGate(ChoiceGate):
    """A choice gate that always decides to stay silent."""

    def __init__(self) -> None:
        super().__init__(min_interval_s=0.0, urgency_threshold=1.1,
                         background_rate=0.0)


def _silent_engine(vault: Any) -> SelfDialogueEngine:
    return SelfDialogueEngine(
        vault=vault,
        voices=build_all_voices(adapter=None),
        choice_gate=_SilentGate(),
    )


# ─── vault_voice ─────────────────────────────────────────────────────────────


def test_vault_voice_speak_holds_without_a_record() -> None:
    vault = AureonVault()
    voices = build_all_voices(adapter=None)
    with pytest.raises(RuntimeError, match="vault_voice_hold"):
        voices["queen"].speak(vault)


def test_vault_voice_speak_silence_statement_when_released(released) -> None:
    vault = AureonVault()
    vault.love_amplitude = 0.5
    voices = build_all_voices(adapter=None)
    statement = voices["queen"].speak(vault)
    assert statement is not None
    assert "I have no adapter" in statement.text
    assert statement.voice == "queen"


# ─── self_dialogue ───────────────────────────────────────────────────────────


def test_self_dialogue_converse_holds_without_a_record() -> None:
    engine = _silent_engine(AureonVault())
    with pytest.raises(RuntimeError, match="self_dialogue_hold"):
        engine.converse()


def test_self_dialogue_converse_returns_none_on_silent_gate_when_released(
    released,
) -> None:
    engine = _silent_engine(AureonVault())
    assert engine.converse() is None
    assert engine.get_status()["total_decisions"] == 1
    assert engine.get_status()["total_utterances"] == 0


# ─── thought_stream_loop ─────────────────────────────────────────────────────


def test_thought_stream_run_holds_without_a_record() -> None:
    stream = ThoughtStreamLoop(
        vault=AureonVault(), base_interval_s=0.001,
        engine=_silent_engine(AureonVault()),
    )
    with pytest.raises(RuntimeError, match="thought_stream_hold"):
        stream.run_n_cycles(1, sleep_between=False)


def test_thought_stream_run_cycles_silently_when_released(released) -> None:
    vault = AureonVault()
    stream = ThoughtStreamLoop(
        vault=vault, base_interval_s=0.001, engine=_silent_engine(vault),
    )
    assert stream.run_n_cycles(3, sleep_between=False) == []
    status = stream.get_status()
    assert status.cycles == 3
    assert status.utterances == 0


# ─── whole_knowledge_voice ───────────────────────────────────────────────────


def test_whole_knowledge_source_read_holds_without_a_record(tmp_path) -> None:
    src = tmp_path / "note.txt"
    src.write_text("some knowledge", encoding="utf-8")
    with pytest.raises(RuntimeError, match="whole_knowledge_voice_hold"):
        whole_knowledge_voice._read_source_text(src, max_chars=100)
    assert WHOLE_KNOWLEDGE_VOICE_RELEASE_HOLD.startswith(
        "whole_knowledge_voice_hold:")


def test_whole_knowledge_reads_and_profiles_sources_when_released(
    released, tmp_path,
) -> None:
    src = tmp_path / "note.txt"
    body = "phi gamma resonance " * 40
    src.write_text(body, encoding="utf-8")
    text = whole_knowledge_voice._read_source_text(src, max_chars=100)
    assert text == body[:100]
    profile = whole_knowledge_voice.build_expression_profile(
        root=tmp_path,
        evidence_dir=tmp_path,
        source_paths=[src],
        max_chars_per_source=200,
        publish=False,
    )
    assert len(profile.sources) == 1
    assert profile.sources[0].path.endswith("note.txt")


# ─── document_artifact_skill ─────────────────────────────────────────────────


def test_document_artifact_holds_and_preflight_reports_hold() -> None:
    with pytest.raises(RuntimeError, match="document_artifact_hold"):
        document_artifact_skill.load_bhoy_voice_profile()
    status = document_artifact_skill.preflight()
    assert status["status"] == "HOLD"
    assert status["production_ready"] is False
    assert status["effect_enabled"] is False
    assert DOCUMENT_ARTIFACT_RELEASE_HOLD.startswith("document_artifact_hold:")


def test_document_artifact_profile_loads_and_preflight_reports_released(
    released,
) -> None:
    profile = document_artifact_skill.load_bhoy_voice_profile()
    assert profile.sample_count > 0
    assert profile.source_paths
    status = document_artifact_skill.preflight()
    assert status["status"] == "RELEASED"
    assert status["production_ready"] is True
    assert status["effect_enabled"] is True


# ─── malformed record still holds ────────────────────────────────────────────


@pytest.mark.parametrize(
    "module_name,effect_call",
    [
        ("vault_voice", lambda: build_all_voices(adapter=None)["queen"].speak(
            AureonVault())),
        ("self_dialogue", lambda: _silent_engine(AureonVault()).converse()),
        ("thought_stream_loop", lambda: ThoughtStreamLoop(
            vault=AureonVault(), base_interval_s=0.001,
            engine=_silent_engine(AureonVault())).run_n_cycles(1)),
        ("whole_knowledge_voice", None),  # filled in below (needs tmp_path)
        ("document_artifact_skill", None),
    ],
)
def test_malformed_record_still_holds(
    monkeypatch, tmp_path, module_name: str, effect_call: Any,
) -> None:
    record = tmp_path / "dispatch_release.json"
    record.write_text("{ not valid json", encoding="utf-8")
    monkeypatch.setenv("GOAL_DISPATCH_RELEASE_RECORD", str(record))
    if module_name == "whole_knowledge_voice":
        src = tmp_path / "note.txt"
        src.write_text("knowledge", encoding="utf-8")
        effect_call = lambda: whole_knowledge_voice._read_source_text(  # noqa: E731
            src, max_chars=50)
    elif module_name == "document_artifact_skill":
        effect_call = document_artifact_skill.load_bhoy_voice_profile
    with pytest.raises(RuntimeError, match="_hold"):
        effect_call()
