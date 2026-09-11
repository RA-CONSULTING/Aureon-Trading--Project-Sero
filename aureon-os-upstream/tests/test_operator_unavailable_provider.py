"""Offline provider absence cannot pass as a model answer or a live line."""

from types import SimpleNamespace

from aureon.inhouse_ai.llm_adapter import AureonStubAdapter, LLMResponse
from aureon.operator.aureon_operator import AureonOperator
from aureon.operator.providers import (
    AureonUnavailableAdapter,
    build_registry,
    describe_provider_set,
)
from aureon.operator.schemas import CognitionResult, OperatorResponse


def test_empty_and_offline_registry_return_unavailable_status():
    for force_offline in (True, False):
        registry = build_registry(specs=[], force_offline=force_offline)
        assert list(registry) == ["offline"]
        adapter = registry["offline"]
        assert isinstance(adapter, AureonUnavailableAdapter)
        response = adapter.prompt([{"role": "user", "content": "fixture"}])
        assert response.text.startswith("[ERROR]")
        assert response.stop_reason == "error"
        assert response.usage == {} and response.raw is None
        assert adapter.health_check() is False
        assert CognitionResult(text=response.text).status() == "honest_unavailable"


def test_unavailable_stream_has_error_terminal_chunk():
    adapter = AureonUnavailableAdapter()
    chunks = list(adapter.stream([]))
    assert chunks[0].text.startswith("[ERROR]")
    assert chunks[-1].done and chunks[-1].stop_reason == "error"


def test_operator_classifies_unavailable_line_and_consensus_without_actor_boot():
    # Exercise the real classifier/consensus with no bus, provider HTTP or factories.
    operator = AureonOperator.__new__(AureonOperator)
    operator.config = SimpleNamespace(max_retries=0)
    operator._breaker = SimpleNamespace(is_open=lambda _: False, record=lambda *_: None)
    operator._call_with_timeout = lambda adapter, messages, system: adapter.prompt(messages)
    operator._emit_consensus = lambda _: None
    answer = operator._call_line("offline", AureonUnavailableAdapter(), [], "")
    assert answer.ok is False
    assert answer.error.startswith("[ERROR]")
    result = OperatorResponse(answers=[answer])
    operator._consensus(result)
    assert result.status() == "honest_unavailable"
    assert result.consensus.n_answers == 0
    assert result.consensus.winner == ""


def test_descriptors_separate_configuration_from_fallback_without_probing():
    real = SimpleNamespace(model="requested-model")
    descriptions = describe_provider_set({"offline": AureonUnavailableAdapter(), "local": real})
    assert descriptions[0] == {
        "name": "offline", "adapter": "AureonUnavailableAdapter",
        "model": "aureon-operator-unavailable", "is_fallback": True,
        "configured": False, "status": "unavailable",
    }
    assert descriptions[1]["configured"] is True
    assert descriptions[1]["is_fallback"] is False
    assert descriptions[1]["status"] == "configured"
    assert "source_timestamp" not in descriptions[1]
    assert "live" not in descriptions[1]


def test_general_stub_fixture_behavior_is_preserved_but_not_a_configured_provider():
    stub = AureonStubAdapter("recorded fixture", model="fixture-model")
    response = stub.prompt([])
    assert isinstance(response, LLMResponse)
    assert response.text == "recorded fixture"
    assert response.stop_reason == "end_turn" and stub.health_check() is True
    description = describe_provider_set({"fixture": stub})[0]
    assert description["model"] == "fixture-model"
    assert description["is_fallback"] is True and description["configured"] is False
