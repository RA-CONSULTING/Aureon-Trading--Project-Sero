"""No live providers, runtime modules, process scans, or actor starts in fixtures."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock

import pytest

from aureon.saas import observed_runtime as observed
from aureon.saas import cognitive, consciousness_catalog, automation_index, defense_catalog

NOW = 1_788_887_000.0


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


@pytest.fixture(autouse=True)
def isolated_sources(tmp_path, monkeypatch):
    observed._cache.clear()
    observed._process_cache.clear()
    monkeypatch.setattr(observed, "REPO_ROOT", tmp_path / "upstream")
    monkeypatch.setattr(observed.time, "time", lambda: NOW)
    monkeypatch.setattr(observed, "_canonical_observation", lambda bus: {"available": False})
    monkeypatch.setenv("AUREON_GENESIS_PATH", str(tmp_path / "genesis.json"))
    monkeypatch.setenv("AUREON_HNC_TRACE_PATH", str(tmp_path / "hnc.jsonl"))
    monkeypatch.setenv("AUREON_BUS_TRACE_DIR", str(tmp_path / "traces"))
    monkeypatch.setattr(defense_catalog, "_REPORT_PATH", tmp_path / "benchmark.json")
    monkeypatch.setattr(automation_index, "_wired_by_category", lambda: {})
    monkeypatch.setattr(automation_index, "_surfacing_fraction", lambda: (1.0, {"domains_reachable": 2, "domains_total": 2}))
    yield
    observed._cache.clear()
    observed._process_cache.clear()


def test_queen_report_tail_keeps_original_fields_and_excludes_private_text(tmp_path):
    path = tmp_path / "reports.jsonl"
    record = {"timestamp": NOW - 5, "cycle": 22, "metacognition_state": {"reflection_count": 9, "insight_count": 2},
              "consciousness": {"awakening_index": .2, "level": "recorded-level", "learning_active": True},
              "narration": "private-text-must-not-leave-reader", "thought": {"secret": "not-public"}}
    path.write_bytes(b"x" * (observed.MAX_TAIL_BYTES * 4) + b"\n" + json.dumps(record).encode() + b"\n")
    row = observed.file_observation(path, "queen_report", now=NOW)
    assert row["fresh"] and row["cycle"] == 22 and row["source_timestamp"] == NOW - 5
    assert row["consciousness"]["learning_active"] is True
    assert row["metacognition_state"]["reflection_count"] == 9
    assert row["measurement_kind"] == "computed_runtime_report"
    assert "private-text" not in json.dumps(row) and "secret" not in json.dumps(row)
    assert "self_coherence" not in row  # another monitor's absent field is not substituted


def test_malformed_or_oversized_last_report_does_not_reuse_previous_record(tmp_path):
    path = tmp_path / "reports.jsonl"
    path.write_text(json.dumps({"timestamp": NOW, "cycle": 1}) + "\n{" + " " * observed.MAX_TAIL_BYTES, encoding="utf-8")
    row = observed.file_observation(path, "queen_report", now=NOW)
    assert row["read_state"] == "failed" and row["source_timestamp"] is None


def test_assessment_endpoint_reports_missing_schema_with_real_related_source(tmp_path):
    write_json(tmp_path / "aureon_fusion/state/queen_mind/mind_state.json", {"last_tick": {"timestamp": NOW - 1, "cycle": 2}})
    row = observed.assessment_observation("affect")
    assert row["available"] is False and row["source_timestamp"] is None
    assert row["runtime_sources"]["queen_mind"]["fresh"] is True
    assert "fear" in row["required_producer_fields"] and "fear" not in row


def test_affect_endpoint_reads_complete_harmonic_producer_without_factory(tmp_path):
    write_json(
        tmp_path / "upstream" / "docs" / "audits" / "aureon_harmonic_affect_state.json",
        {
            "schema_version": "aureon-harmonic-affect-state-v1",
            "generated_at": NOW - 1,
            "status": "harmonic_affect_state_ready",
            "summary": {
                "victory": 0.25,
                "defeat": 0.05,
                "fear": 0.1,
                "resolve": 0.7,
                "valence": 0.4,
                "arousal": 0.3,
                "caution_bias": 0.12,
                "affect_phase": "steady_willingness",
                "emotion_anchor": "Willingness",
                "dominant_feeling": "resolve",
                "mood": "Willingness",
                "hnc_coherence_score": 0.66,
                "goal_alignment": 0.5,
                "reward_alignment": 0.25,
                "stability": 0.8,
                "anchor_readiness": 0.9,
                "safety_blocker_count": 0,
                "runtime_stale": False,
            },
            "state_contract": {"safety_boundary": "no affect phase can override gates"},
        },
    )
    row = observed.assessment_observation("affect")
    assert row["available"] is True and row["fresh"] is True
    assert row["truth_status"] == "real_derived"
    assert row["producer"] == "aureon.autonomous.aureon_harmonic_affect_state"
    assert row["victory"] == 0.25 and row["resolve"] == 0.7
    assert row["signals"]["hnc_coherence"]["value"] == 0.66
    assert row["input_observations"]["state_contract"]["safety_boundary"].startswith("no affect")


def test_assessment_snapshot_routes_read_complete_persisted_surfaces(tmp_path):
    write_json(
        tmp_path / "upstream" / "docs" / "audits" / "aureon_assessment_snapshots.json",
        {
            "schema_version": "aureon-assessment-snapshots-v1",
            "generated_at": NOW - 1,
            "status": "assessment_snapshots_ready",
            "producer_contract": {"read_only_methods": "Only assess() methods are called."},
            "assessments": {
                "metacognition": {"available": True, "truth_status": "real_derived", "self_coherence": 0.7, "self_life_score": 0.6, "psi": 0.2, "divergence": 0.1, "contributors": 2, "signals": {"field": {"value": 0.6, "truth_status": "real_derived"}}, "ts": NOW - 1},
                "soul": {"available": True, "truth_status": "real_derived", "agreement": 0.8, "stance": "wait", "resolved": False, "requires_human": False, "voices": {"thought": {"stance": "wait"}}, "dissent": [], "plan": None, "ts": NOW - 1},
                "inner_work": {"available": True, "truth_status": "real_derived", "self_belief": 0.6, "self_love": 0.5, "self_determination": 0.7, "ego_dissolution": 0.8, "stage_index": 3, "stage": "Heart", "potential": 0.4, "signals": {}, "ts": NOW - 1},
                "pursuit": {"available": True, "truth_status": "real_derived", "creator_happiness": 0.5, "aureon_happiness": 0.6, "unified_happiness": 0.55, "energy": 0.25, "freedom": 0.3, "pillars": {"dream": 0.0, "love": 0.6, "gaia": 0.7, "joy": 0.5, "purpose": 1.0}, "signals": {}, "ts": NOW - 1},
            },
        },
    )
    for surface in ["metacognition", "soul", "inner_work", "pursuit"]:
        row = observed.assessment_observation(surface)
        assert row["available"] is True and row["fresh"] is True
        assert row["producer"] == "aureon.autonomous.aureon_assessment_snapshot_producer"
        assert row["measurement_kind"] == "computed_runtime_assessment"
        assert row["input_observations"]["producer_surface"] == surface
    assert observed.assessment_observation("pursuit")["pillars"]["purpose"] == 1.0


def test_historical_brain_keeps_independent_source_dates_and_empty_success(tmp_path, monkeypatch):
    predictions = tmp_path / "predictions.json"
    knowledge = tmp_path / "knowledge.json"
    write_json(predictions, {"last_updated": "2026-01-01T00:00:00Z", "predictions": []})
    write_json(knowledge, [{"timestamp": "2026-01-02T00:00:00Z", "private": "hidden"}])
    monkeypatch.setenv("AUREON_BRAIN_PREDICTIONS_PATH", str(predictions))
    monkeypatch.setenv("AUREON_BRAIN_KNOWLEDGE_PATH", str(knowledge))
    row = cognitive.brain_surface()
    assert row["classification"] == "recorded_history" and row["source_timestamp"] is None
    assert row["historical_available"] and not row["fresh"]
    assert row["accuracy"]["total_predictions"] == 0 and row["accuracy"]["accuracy_pct"] is None
    assert row["accuracy"]["source_timestamp"] != row["knowledge"]["source_timestamp"]
    assert "private" not in json.dumps(row)


def test_bus_is_measured_but_only_stamped_fresh_events_are_recent():
    bus = SimpleNamespace(list_subscribed_topics=lambda: ["symbolic.life.pulse"], subscriber_count=lambda *args: 1,
                          recall=lambda *args, **kwargs: [{"ts": NOW - 1}, {"ts": NOW - 301}, {}])
    row = observed.bus_observation(bus)
    assert row["source_clock_kind"] == "in_process_bus_measurement" and row["max_age_seconds"] == 15
    assert row["source_timestamp"] == NOW and row["fresh"]
    assert all(family["recent"] == 1 for family in row["cognitive_links"].values())
    assert row["truth_status"] == "real_derived"


def test_failed_bus_read_is_unavailable_not_zero_activity():
    row = observed.bus_observation(SimpleNamespace(recall=Mock(side_effect=OSError("fixture"))))
    assert row["read_state"] == "failed" and not row["available"]
    assert "cognitive_links_flowing" not in row


def registry_fixture(tmp_path, identities):
    base = tmp_path / "aureon_fusion/state"
    write_json(base / "organ_registry.json", {"organs": {
        "verified": {"pid": 10, "started_at": NOW - 10, "cmd": ["python.exe", "private-command-not-returned"]},
        "reused": {"pid": 11, "started_at": NOW - 10, "cmd": ["python.exe"]},
        "inferred": {"pid": 12, "started_at": NOW - 10, "cmd": ["python.exe"]},
        "absent": {"pid": 13, "cmd": ["python.exe"]},
        "unrecorded": {"pid": None},
    }})
    write_json(base / "observed_process_identity.json", {"schema": "aureon.process_identity.v1", "organs": identities})


def test_only_exact_bound_pid_creation_identity_is_verified_without_scans(tmp_path):
    identities = {key: {"pid": pid, "process_created_at": NOW - 10, "process_name": "python.exe", "verified_at": NOW - 10000,
                        "spec_match": True, "cwd_match": True} for key, pid in [("verified", 10), ("reused", 11)]}
    registry_fixture(tmp_path, identities)
    calls = []
    def process(pid):
        calls.append(pid)
        if pid == 13:
            raise ProcessLookupError()
        return SimpleNamespace(is_running=lambda: True, name=lambda: "python.exe",
                               create_time=lambda: NOW - (1 if pid == 11 else 10))
    row = observed.process_observation(workspace=tmp_path, now=NOW, process_factory=process)
    by_name = {item["name"]: item for item in row["organs"]}
    assert calls == [10, 11, 12, 13]
    assert by_name["verified"]["identity_verified"] is True
    assert by_name["reused"]["identity_verified"] is False
    assert by_name["inferred"]["launch_time_consistent"] is True and not by_name["inferred"]["identity_verified"]
    assert by_name["absent"]["read_state"] == "absent" and by_name["absent"]["pid_running"] is False
    assert all(item["functional_health"] == "unknown" for item in row["organs"])
    assert row["counts"] == {"registered": 5, "measured": 4, "running_verified": 1, "running_unverified": 2, "absent": 1, "unknown": 1}
    assert "private-command" not in json.dumps(row)


def test_failed_identity_receipt_does_not_turn_liveness_into_verified_identity(tmp_path):
    registry_fixture(tmp_path, {})
    (tmp_path / "aureon_fusion/state/observed_process_identity.json").write_text("{bad", encoding="utf-8")
    row = observed.process_observation(workspace=tmp_path, now=NOW, process_factory=lambda pid: SimpleNamespace(is_running=lambda: True, name=lambda: "python.exe", create_time=lambda: NOW - 10))
    assert row["identity_receipt_read_state"] == "failed"
    assert row["counts"]["running_verified"] == 0 and row["counts"]["running_unverified"] == 4


def test_process_batch_budget_leaves_unmeasured_rows_unknown(tmp_path, monkeypatch):
    registry_fixture(tmp_path, {})
    clock = [0.0]
    monkeypatch.setattr(observed.time, "monotonic", lambda: clock[0])
    called = []
    def process(pid):
        called.append(pid)
        clock[0] = 1.0
        return SimpleNamespace(is_running=lambda: True, name=lambda: "python.exe", create_time=lambda: NOW - 10)
    row = observed.process_observation(workspace=tmp_path, now=NOW, process_factory=process)
    assert called == [10]
    assert row["counts"]["measured"] == 1 and row["counts"]["unknown"] == 4
    assert row["organs"][1]["reason"] == "probe_batch_budget_exhausted"


def test_partial_configuration_cannot_become_full_automation(monkeypatch):
    monkeypatch.setattr(automation_index, "_connectome_fractions", lambda: (None, None, {}))
    row = automation_index.automation_index()
    assert row["dimensions"]["surfacing"]["pct"] == 100
    assert row["index_pct"] is None
    assert "consciousness" in row["missing_dimensions"]
    assert row["classification"] == "software_coverage_not_autonomy"


def test_defense_keeps_historical_metrics_and_missing_pass_separate_from_live_trace(monkeypatch):
    module = next(iter(defense_catalog._TRACE_NAMES))
    monkeypatch.setattr(defense_catalog, "_load_report", lambda: {"ts": "2026-01-01T00:00:00Z", "tier_a": [{"module": "aureon/bio/" + module + ".py", "name": "fixture", "metrics": {"observed": 4}}]})
    monkeypatch.setattr(defense_catalog, "_latest_trace", lambda name: {"ts": NOW - 301, "boundary": "old"})
    stale = defense_catalog.build_defense_catalog()
    row = next(module for group in stale["groups"].values() for module in group["modules"])
    assert row["passed"] is None and row["boundary"] is None
    assert row["runtime_observation"]["fresh"] is False
    assert stale["truth_status"] == "real_derived" and stale["report_observation"]["historical_available"]
    monkeypatch.setattr(defense_catalog, "_latest_trace", lambda name: {"ts": NOW - 1, "boundary": "fresh"})
    fresh = defense_catalog.build_defense_catalog()
    row = next(module for group in fresh["groups"].values() for module in group["modules"])
    assert row["runtime_observation"]["fresh"] is True and row["boundary"] == "fresh"
    assert row["truth_status"] == "real_derived" and row["passed"] is None


def test_historical_surfaces_are_not_counted_as_current_operational_sources(monkeypatch):
    monkeypatch.setattr(cognitive, "_SURFACE_BUILDERS", {"brain": lambda: {"available": False, "fresh": False, "truth_status": "cached_real", "historical_available": True}})
    result = cognitive.build_cognitive_payload()
    assert result["observed_fresh_count"] == 0 and result["operational_ready"] == 0
    assert result["blocked"] == 1


def test_defense_route_serializes_nonfinite_historical_metric_as_unavailable(monkeypatch):
    flask = pytest.importorskip("flask")
    from aureon.saas.gateway import register_saas_routes
    monkeypatch.delenv("AUREON_SUPABASE_JWT_SECRET", raising=False)
    monkeypatch.setattr(defense_catalog, "build_defense_catalog", lambda: {"truth_status": "real_derived", "metric": float("inf")})
    app = flask.Flask(__name__)
    register_saas_routes(app)
    response = app.test_client().get("/api/defense")
    body = json.loads(response.get_data(as_text=True), parse_constant=lambda value: pytest.fail(value))
    assert body["metric"] is None


@pytest.mark.parametrize("endpoint", ["/api/cognition", "/api/consciousness", "/api/automation", "/api/defense", "/api/metacognition", "/api/affect", "/api/soul", "/api/inner-work", "/api/pursuit"])
def test_passive_http_routes_never_call_factories_or_assessment_steps(endpoint, monkeypatch):
    flask = pytest.importorskip("flask")
    from aureon.saas.gateway import register_saas_routes
    factory = Mock(side_effect=AssertionError("live factory/assessment called from GET"))
    for module_name, accessor in [("metacognition_monitor", "get_metacognition_monitor"), ("affect_monitor", "get_affect_monitor"),
                                  ("soul", "get_soul"), ("inner_work", "get_inner_work"), ("pursuit", "get_pursuit"),
                                  ("aureon_mycelium", "get_mycelium"), ("aureon_connectome", "get_connectome"),
                                  ("aureon_thought_bus", "get_thought_bus")]:
        stub = ModuleType("aureon.core." + module_name)
        setattr(stub, accessor, factory)
        monkeypatch.setitem(sys.modules, stub.__name__, stub)
    monkeypatch.delenv("AUREON_SUPABASE_JWT_SECRET", raising=False)
    monkeypatch.setattr(cognitive, "provenance_block", lambda: {})
    app = flask.Flask(__name__)
    register_saas_routes(app)
    response = app.test_client().get(endpoint)
    assert response.status_code == 200
    json.loads(response.get_data(as_text=True), parse_constant=lambda value: pytest.fail(value))
    factory.assert_not_called()
