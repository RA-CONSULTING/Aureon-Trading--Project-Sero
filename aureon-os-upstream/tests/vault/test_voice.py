#!/usr/bin/env python3
"""
Fail-closed voice-layer tests.

Prompt composition and choice logic remain pure. Provider calls, vault
mutation, bus publishing, and background execution sit behind the shared
fail-closed release record (``aureon.vault.voice._goal_release``): they
raise the module's HOLD error while the record is absent or invalid, and
run only while the record names the module. Every test here defaults to a
missing record (autouse fixture); released-path tests opt into a released
fixture. Released-path speak tests use no adapter or a silent choice gate,
so no provider is ever contacted.
"""

import json
import os
import sys

import pytest

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from aureon.vault import (  # noqa: E402
    AureonSelfFeedbackLoop,
    AureonVault,
    ChoiceGate,
    SelfDialogueEngine,
    ThoughtStreamLoop,
    build_all_voices,
)


@pytest.fixture(autouse=True)
def _default_held(monkeypatch, tmp_path) -> None:
    """Default every test to the fail-closed HOLD: point the release
    record at a path that does not exist."""
    monkeypatch.setenv(
        "GOAL_DISPATCH_RELEASE_RECORD", str(tmp_path / "missing.json"))


@pytest.fixture
def released(monkeypatch, tmp_path):
    """Opt into the released path. Names the whole voice chain:
    self_dialogue speaks through vault_voice, and the thought stream
    ticks through self_dialogue."""
    record_dir = tmp_path / "record"
    record_dir.mkdir()
    record = record_dir / "dispatch_release.json"
    record.write_text(json.dumps({
        "ts": "2026-09-06",
        "source": "owner decree 2026-09-06 (Gary Leckey)",
        "modules": ["vault_voice", "self_dialogue", "thought_stream_loop"],
    }), encoding="utf-8")
    monkeypatch.setenv("GOAL_DISPATCH_RELEASE_RECORD", str(record))
    return record


PASS = 0
FAIL = 0


def check(condition: bool, msg: str) -> None:
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  [OK] {msg}")
    else:
        FAIL += 1
        print(f"  [!!] {msg}")


def test_voices_compose_pure_prompts_but_speaking_is_held():
    print("\n[1] Voice prompt composition is pure and speaking is held")
    vault = AureonVault()

    vault.love_amplitude = 0.3
    vault.gratitude_score = 0.5
    vault.last_casimir_force = 0.1
    vault.dominant_chakra = "foundation"
    vault.cortex_snapshot = {
        "delta": 0.3,
        "theta": 0.1,
        "alpha": 0.1,
        "beta": 0.1,
        "gamma": 0.1,
    }

    class BombAdapter:
        def prompt(self, *_args, **_kwargs):
            raise AssertionError("release-held voice must not call a provider")

    voices = build_all_voices(adapter=BombAdapter())
    prompts_1 = {
        name: "\n".join(voice._compose_prompt_lines(voice._extract_slice(vault)))
        for name, voice in voices.items()
    }
    assert prompts_1
    for name, voice in voices.items():
        with pytest.raises(RuntimeError, match="vault_voice_hold"):
            voice.speak(vault)
        check(len(prompts_1[name]) > 20, f"{name} pure prompt is substantial")

    vault.love_amplitude = 0.9
    vault.gratitude_score = 0.85
    vault.last_casimir_force = 5.2
    vault.dominant_chakra = "crown"
    vault.rally_active = True
    vault.cortex_snapshot = {
        "delta": 0.1,
        "theta": 0.1,
        "alpha": 0.4,
        "beta": 0.35,
        "gamma": 0.55,
    }

    prompts_2 = {
        name: "\n".join(voice._compose_prompt_lines(voice._extract_slice(vault)))
        for name, voice in voices.items()
    }

    different_count = sum(
        1
        for name in prompts_1
        if name in prompts_2 and prompts_1[name] != prompts_2[name]
    )
    check(
        different_count >= len(prompts_1) // 2,
        f"at least half the voices' prompts changed with state ({different_count}/{len(prompts_1)})",
    )

    vault.last_lambda_t = 0.87
    queen_prompt = "\n".join(
        voices["queen"]._compose_prompt_lines(voices["queen"]._extract_slice(vault))
    )
    check(
        "0.870" in queen_prompt or "+0.87" in queen_prompt,
        "Queen voice names Lambda(t) from state",
    )

    vault.last_casimir_force = 4.321
    miner_prompt = "\n".join(
        voices["miner"]._compose_prompt_lines(voices["miner"]._extract_slice(vault))
    )
    check(
        "4.321" in miner_prompt,
        "Miner voice names the Casimir drift value from state",
    )


def test_choice_gate():
    print("\n[2] ChoiceGate decides based on vault state")
    vault = AureonVault()
    gate = ChoiceGate(min_interval_s=0.0, urgency_threshold=0.3, background_rate=0.0)

    vault.love_amplitude = 0.2
    vault.gratitude_score = 0.5
    vault.last_casimir_force = 0.05
    vault.cortex_snapshot["gamma"] = 0.05
    quiet = gate.decide(vault)
    check(not quiet.should_speak, f"quiet vault -> silent (urgency={quiet.urgency:.2f})")

    vault.rally_active = True
    rally = gate.decide(vault)
    check(rally.should_speak, f"rally mode -> speak (urgency={rally.urgency:.2f})")
    check(rally.preferred_voice == "council", f"rally prefers council voice (got {rally.preferred_voice})")

    vault.rally_active = False
    vault.cortex_snapshot["gamma"] = 0.8
    gamma = gate.decide(vault)
    check(gamma.should_speak, f"gamma spike -> speak (urgency={gamma.urgency:.2f})")
    check(gamma.preferred_voice == "queen", f"gamma prefers queen (got {gamma.preferred_voice})")

    vault.cortex_snapshot["gamma"] = 0.05
    vault.last_casimir_force = 5.0
    drift = gate.decide(vault)
    check(drift.preferred_voice == "miner", f"drift prefers miner (got {drift.preferred_voice})")

    vault.last_casimir_force = 0.1
    vault.love_amplitude = 0.85
    love = gate.decide(vault)
    check(love.preferred_voice == "lover", f"high love prefers lover (got {love.preferred_voice})")

    gate_rl = ChoiceGate(min_interval_s=10.0, urgency_threshold=0.0, background_rate=1.0)
    vault.rally_active = True
    first = gate_rl.decide(vault)
    second = gate_rl.decide(vault)
    check(first.should_speak, "first call passes rate limit")
    check(not second.should_speak, "second call within interval is suppressed")


def test_self_dialogue_engine_is_inert_and_all_effect_entrypoints_hold():
    print("\n[3] SelfDialogueEngine is inert and effect entrypoints hold")
    vault = AureonVault()
    engine = SelfDialogueEngine(vault=vault)
    size_before = len(vault)
    assert engine.voices == {}
    assert engine._thought_bus is None
    for call in (
        engine.converse,
        lambda: engine.respond_to_human("hello"),
        lambda: engine.speak_as("queen"),
        engine._wire_thought_bus,
    ):
        with pytest.raises(RuntimeError, match="self_dialogue_hold"):
            call()
    assert len(vault) == size_before
    assert engine.history == []
    assert engine.get_status()["total_decisions"] == 0


def test_human_response_hold_precedes_provider_vault_and_bus_effects():
    print("\n[4] Human response HOLD precedes providers, vault writes, and bus writes")
    vault = AureonVault()

    class BombVoice:
        def speak(self, *_args, **_kwargs):
            raise AssertionError("provider path reached")

    class BombBus:
        def publish(self, *_args, **_kwargs):
            raise AssertionError("bus path reached")

    engine = SelfDialogueEngine(
        vault=vault,
        voices={"queen": BombVoice()},  # type: ignore[dict-item]
        thought_bus=BombBus(),
        adapter=object(),
    )
    before = len(vault)
    with pytest.raises(RuntimeError, match="self_dialogue_hold"):
        engine.respond_to_human("Do all of you hear me?", voice_name="queen")
    assert len(vault) == before
    assert engine.history == []


def test_thought_stream_loop_never_spawns_or_executes(monkeypatch: pytest.MonkeyPatch):
    print("\n[5] ThoughtStreamLoop never spawns or executes")
    vault = AureonVault()
    monkeypatch.setattr(
        "aureon.vault.voice.thought_stream_loop.threading.Thread",
        lambda *_args, **_kwargs: pytest.fail("release-held stream must not create a thread"),
    )
    stream = ThoughtStreamLoop(vault=vault, base_interval_s=0.001)
    assert stream.engine is None
    for call in (
        stream.start,
        stream._loop,
        stream._tick_once,
        lambda: stream.run_n_cycles(5, sleep_between=False),
    ):
        with pytest.raises(RuntimeError, match="thought_stream_hold"):
            call()
    status = stream.get_status()
    assert status.running is False
    assert status.cycles == 0
    assert status.utterances == 0


def test_self_feedback_loop_voice_integration():
    print("\n[6] Self-feedback voice integration: fail-closed; voice stays "
          "inert when the core record releases the loop")
    import json as _json
    import shutil
    import tempfile

    env_var = "AUREON_CORE_RELEASE_RECORD"
    old = os.environ.get(env_var)
    tmpdir = tempfile.mkdtemp()
    try:
        # HOLD path: record absent → the loop refuses the effectful flag.
        os.environ[env_var] = os.path.join(tmpdir, "no_such_record.json")
        with pytest.raises(RuntimeError, match="aureon_self_feedback_loop_hold"):
            AureonSelfFeedbackLoop(base_interval_s=0.01, enable_voice=True)

        # Released path: the loop's own gate opens, but the voice provider
        # modules are voice-owned and are NOT released by the core record —
        # the voice engine must stay inert.
        record = os.path.join(tmpdir, "core_release.json")
        with open(record, "w", encoding="utf-8") as f:
            _json.dump({
                "ts": "2026-09-06",
                "source": "owner decree 2026-09-06 (Gary Leckey)",
                "modules": ["aureon_vault", "casimir_quantifier",
                            "harmonic_pinger", "self_feedback_loop"],
            }, f)
        os.environ[env_var] = record
        loop = AureonSelfFeedbackLoop(base_interval_s=0.01, enable_voice=True)
        check(loop.voice_engine is None,
              "voice engine stays inert under core release (voice-owned)")
        check(loop._running is False, "released loop starts inert")
    finally:
        if old is None:
            os.environ.pop(env_var, None)
        else:
            os.environ[env_var] = old
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_released_voices_speak_silence_without_adapter(released) -> None:
    print("\n[7] Released voices speak the safe silence statement with no adapter")
    vault = AureonVault()
    vault.love_amplitude = 0.6
    vault.gratitude_score = 0.7
    vault.last_lambda_t = 0.42
    voices = build_all_voices(adapter=None)
    for name, voice in voices.items():
        statement = voice.speak(vault)
        check(statement is not None, f"{name} released speak returns a statement")
        check(
            "I have no adapter" in (statement.text or ""),
            f"{name} speaks the silence statement without an adapter",
        )
        check(statement.voice == name, f"{name} statement names its voice")


def test_released_self_dialogue_converse_stays_silent_when_gate_says_so(
    released,
) -> None:
    print("\n[8] Released SelfDialogueEngine honours a silent choice gate")
    vault = AureonVault()
    silent_gate = ChoiceGate(min_interval_s=0.0, urgency_threshold=1.1,
                             background_rate=0.0)
    engine = SelfDialogueEngine(
        vault=vault,
        voices=build_all_voices(adapter=None),
        choice_gate=silent_gate,
    )
    check(engine.converse() is None, "silent gate -> converse() returns None")
    check(engine.get_status()["total_decisions"] == 1,
          "the decision was still counted")


def test_released_thought_stream_counts_cycles_without_utterances(
    released,
) -> None:
    print("\n[9] Released ThoughtStreamLoop runs cycles against a silent engine")
    vault = AureonVault()
    silent_gate = ChoiceGate(min_interval_s=0.0, urgency_threshold=1.1,
                             background_rate=0.0)
    engine = SelfDialogueEngine(
        vault=vault,
        voices=build_all_voices(adapter=None),
        choice_gate=silent_gate,
    )
    stream = ThoughtStreamLoop(vault=vault, base_interval_s=0.001, engine=engine)
    utterances = stream.run_n_cycles(3, sleep_between=False)
    check(utterances == [], "silent engine -> no utterances")
    status = stream.get_status()
    check(status.cycles == 3, f"three cycles ran (got {status.cycles})")
    check(status.utterances == 0, "no utterances recorded")


def main():
    print("=" * 80)
    print("  VAULT VOICE TEST SUITE")
    print("=" * 80)

    import shutil
    import tempfile

    env_var = "GOAL_DISPATCH_RELEASE_RECORD"
    old_env = os.environ.get(env_var)
    tmpdir = tempfile.mkdtemp()
    try:
        # Held sections: point the release record at a missing path.
        os.environ[env_var] = os.path.join(tmpdir, "missing.json")
        test_voices_compose_pure_prompts_but_speaking_is_held()
        test_choice_gate()
        test_self_dialogue_engine_is_inert_and_all_effect_entrypoints_hold()
        test_human_response_hold_precedes_provider_vault_and_bus_effects()
        test_thought_stream_loop_never_spawns_or_executes(pytest.MonkeyPatch())
        test_self_feedback_loop_voice_integration()

        # Released sections: write a real record naming the voice chain.
        record_dir = os.path.join(tmpdir, "record")
        os.makedirs(record_dir, exist_ok=True)
        record = os.path.join(record_dir, "dispatch_release.json")
        with open(record, "w", encoding="utf-8") as f:
            json.dump({
                "ts": "2026-09-06",
                "source": "owner decree 2026-09-06 (Gary Leckey)",
                "modules": ["vault_voice", "self_dialogue", "thought_stream_loop"],
            }, f)
        os.environ[env_var] = record
        # main() is not pytest: the tests below only need the env var the
        # fixture would have set, so pass a placeholder for the fixture arg.
        test_released_voices_speak_silence_without_adapter(None)
        test_released_self_dialogue_converse_stays_silent_when_gate_says_so(None)
        test_released_thought_stream_counts_cycles_without_utterances(None)
    finally:
        if old_env is None:
            os.environ.pop(env_var, None)
        else:
            os.environ[env_var] = old_env
        shutil.rmtree(tmpdir, ignore_errors=True)

    print()
    print("=" * 80)
    print(f"  RESULT: {PASS} passed, {FAIL} failed")
    print("=" * 80)
    sys.exit(0 if FAIL == 0 else 1)


if __name__ == "__main__":
    main()
