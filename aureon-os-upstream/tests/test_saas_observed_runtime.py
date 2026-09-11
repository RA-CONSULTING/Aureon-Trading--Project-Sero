"""Passive runtime status must retain clocks and never initialize active organs."""
from __future__ import annotations

import io
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from aureon.saas import observed_runtime as observed
from aureon.saas import status

NOW = 1_788_884_400.0


@pytest.fixture(autouse=True)
def isolated_observation_cache(monkeypatch):
    observed._cache.clear()
    monkeypatch.setattr(status, "process_observation", lambda: {"available": False, "reason": "isolated_fixture"})
    yield
    observed._cache.clear()


def write_state(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


@pytest.mark.parametrize("stamp", [None, True, float("inf"), float("nan"), 1e100, -1, "unknown", NOW + 6, "2026-09-08T16:00:00"])
def test_invalid_or_future_source_is_never_fresh(stamp):
    row = observed.observation("fixture", stamp, now=NOW)
    assert row["fresh"] is False
    assert row["available"] is False
    assert row["receipt_timestamp"] == NOW
    assert row["read_state"] == "unavailable"


def test_only_explicit_timezone_iso_clocks_are_accepted():
    assert observed.source_epoch("2026-09-08T16:00:00Z") == observed.source_epoch("2026-09-08T17:00:00+01:00")
    assert observed.source_epoch("2026-09-08T16:00:00") is None


def test_source_clock_expires_even_when_receipt_and_cache_are_recent(tmp_path):
    path = tmp_path / "queen.json"
    write_state(path, {"last_tick": {"timestamp": NOW - 290, "cycle": 42}, "private_narration": "must never be returned"})
    fresh = observed.file_observation(path, "queen_mind", now=NOW)
    expired = observed.file_observation(path, "queen_mind", now=NOW + 11)
    assert fresh["fresh"] is True and fresh["cycle"] == 42
    assert expired["fresh"] is False and expired["read_state"] == "stale"
    assert expired["source_timestamp"] == fresh["source_timestamp"] == NOW - 290
    assert expired["receipt_timestamp"] == NOW + 11
    assert "private_narration" not in json.dumps(fresh)


def test_success_replaces_clock_but_failed_read_does_not_retain_observed_data(tmp_path, monkeypatch):
    clock = [1.0]
    monkeypatch.setattr(observed.time, "monotonic", lambda: clock[0])
    path = tmp_path / "hnc.json"
    write_state(path, {"timestamp": NOW - 10, "step": 1})
    first = observed.file_observation(path, "hnc_core", now=NOW)
    clock[0] += 3
    write_state(path, {"timestamp": NOW - 1, "step": 2})
    second = observed.file_observation(path, "hnc_core", now=NOW)
    assert first["source_timestamp"] == NOW - 10
    assert second["source_timestamp"] == NOW - 1 and second["step"] == 2
    clock[0] += 3
    path.write_text("{partial", encoding="utf-8")
    failed = observed.file_observation(path, "hnc_core", now=NOW)
    assert failed["read_state"] == "failed" and failed["fresh"] is False
    assert failed["source_timestamp"] is None and "step" not in failed


def test_empty_missing_and_malformed_records_do_not_manufacture_zero_counts(tmp_path):
    missing = observed.file_observation(tmp_path / "missing.json", "queen_mind", now=NOW)
    assert missing["read_state"] == "missing" and "cycle" not in missing
    path = tmp_path / "empty.json"
    write_state(path, {})
    empty = observed.file_observation(path, "queen_mind", now=NOW)
    assert empty["cycle"] is None and not empty["fresh"]


def test_oversized_source_read_is_bounded_and_unavailable(tmp_path, monkeypatch):
    requests = []
    class TrackedFile(io.BytesIO):
        def read(self, size=-1):
            requests.append(size)
            return super().read(size)
    raw = b" " * (observed.MAX_RECORD_BYTES * 3)
    monkeypatch.setattr(Path, "open", lambda *args, **kwargs: TrackedFile(raw))
    result = observed.file_observation(tmp_path / "large.json", "queen_mind", now=NOW)
    assert requests == [observed.MAX_RECORD_BYTES + 1]
    assert result["read_state"] == "failed" and not result["fresh"]


def test_persisted_connectome_has_no_invented_total_or_coverage(tmp_path):
    path = tmp_path / "connectome.json"
    write_state(path, {"saved_at": NOW - 1, "records": {"a": {"status": "woven"}, "b": {"status": "failed"}}, "linked": ["a"]})
    result = observed.file_observation(path, "connectome", now=NOW)
    assert result["fresh"] is True and result["woven"] == 1 and result["failed"] == 1
    assert result["nodes"] is None and result["coverage_pct"] is None


def test_organism_does_not_cold_boot_and_fresh_external_queen_remains_visible(tmp_path, monkeypatch):
    factory = Mock(side_effect=AssertionError("GET initialized an organ"))
    modules = {
        "aureon.core.aureon_mycelium": SimpleNamespace(get_mycelium=factory, _mycelium_instance=None),
        "aureon.core.aureon_connectome": SimpleNamespace(get_connectome=factory),
        "aureon.core.aureon_thought_bus": SimpleNamespace(get_thought_bus=factory, _thought_bus_instance=None),
    }
    monkeypatch.setattr(observed, "_canonical_observation", lambda bus: {"available": False})
    write_state(tmp_path / "aureon_fusion/state/queen_mind/mind_state.json", {"last_tick": {"timestamp": NOW - 60, "cycle": 9}})
    result = observed.observed_organism(now=NOW, repo_root=tmp_path / "upstream", workspace=tmp_path, modules=modules)
    assert result["runtime_sources"]["queen_mind"]["fresh"] is True
    assert result["available"] is True
    assert result["mycelium"]["available"] is False
    assert result["connectome"]["read_state"] == "missing"
    assert result["unification"]["field_flowing"] is False
    assert result["unification"]["symbolic_life_score"] is None
    assert result["source_timestamp"] is None
    factory.assert_not_called()


def test_stale_or_untimed_bus_events_cannot_make_edges_flow(tmp_path, monkeypatch):
    bus = SimpleNamespace(recall=lambda *args, **kwargs: [
        {"ts": NOW - 301, "payload": {"symbolic_life_score": .9}},
        {"payload": {"symbolic_life_score": .8}},
    ])
    modules = {"aureon.core.aureon_thought_bus": SimpleNamespace(_thought_bus_instance=bus)}
    monkeypatch.setattr(observed, "_canonical_observation", lambda facade: {"available": True, "source_timestamp": NOW - 301, "symbolic_life_score": .9})
    result = observed.observed_organism(now=NOW, repo_root=tmp_path, workspace=tmp_path, modules=modules)
    assert result["recent_pulses"] == []
    assert set(result["unification"]["edges"].values()) == {0}
    assert result["unification"]["field_flowing"] is False
    assert result["unification"]["symbolic_life_score"] is None


def test_status_never_constructs_core_and_degrades_when_core_unobserved(monkeypatch):
    factory = Mock(side_effect=AssertionError("cold core construction"))
    monkeypatch.setitem(status.sys.modules, "aureon.core.aureon_operational_core", SimpleNamespace(_ops_core=None, get_operational_core=factory))
    monkeypatch.setattr(status, "domain_report", lambda: [{"available": True, "domain": "core"}])
    monkeypatch.setattr(status, "runtime_source_observations", lambda: {"queen_mind": {"fresh": True}})
    result = status.get_platform_status()
    assert result["status"] == "degraded"
    assert result["reachability_status"] == "ready"
    assert result["truth_status"] == "real_derived"
    assert result["coordinator"]["available"] is False
    factory.assert_not_called()


def test_operational_core_requires_fresh_source_and_preserves_degraded_health(monkeypatch):
    monkeypatch.setattr(status.time, "time", lambda: NOW)
    source = {"status": "degraded", "state_freshness": {"last_write": NOW - 2, "is_stale": False}}
    core = SimpleNamespace(get_health=lambda: source)
    monkeypatch.setitem(status.sys.modules, "aureon.core.aureon_operational_core", SimpleNamespace(_ops_core=core))
    assert status._operational_health()["status"] == "degraded"
    source["state_freshness"]["last_write"] = NOW - 301
    stale = status._operational_health()
    assert stale["available"] is False and stale["status"] == "unknown"


def test_organism_http_route_keeps_missing_sources_no_data_and_does_not_boot(tmp_path, monkeypatch):
    flask = pytest.importorskip("flask")
    from aureon.saas.gateway import register_saas_routes
    from aureon.saas import cognitive
    monkeypatch.delenv("AUREON_SUPABASE_JWT_SECRET", raising=False)
    monkeypatch.setattr(observed, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(observed, "_canonical_observation", lambda bus: {"available": False})
    monkeypatch.setattr(cognitive, "provenance_block", lambda: {"policy": "fixture"})
    app = flask.Flask(__name__)
    register_saas_routes(app)
    response = app.test_client().get("/api/organism")
    assert response.status_code == 200
    result = json.loads(response.get_data(as_text=True), parse_constant=lambda value: pytest.fail(value))
    assert result["truth_status"] == "no_data"
    assert result["source_timestamp"] is None
    assert result["runtime_sources"]["queen_mind"]["read_state"] == "missing"


def test_status_route_preserves_source_truth_classification(monkeypatch):
    flask = pytest.importorskip("flask")
    from aureon.saas.gateway import register_saas_routes
    from aureon.saas import cognitive
    monkeypatch.delenv("AUREON_SUPABASE_JWT_SECRET", raising=False)
    monkeypatch.setattr(status, "get_platform_status", lambda: {"status": "unknown", "truth_status": "real_derived"})
    monkeypatch.setattr(cognitive, "provenance_block", lambda: {})
    app = flask.Flask(__name__)
    register_saas_routes(app)
    response = app.test_client().get("/api/status")
    assert response.json["truth_status"] == "real_derived"
    assert response.json["status"] == "unknown"

def test_stale_harmonic_affect_report_is_not_current_assessment(tmp_path, monkeypatch):
    monkeypatch.setattr(observed, "REPO_ROOT", tmp_path)
    write_state(
        tmp_path / "docs" / "audits" / "aureon_harmonic_affect_state.json",
        {
            "schema_version": "aureon-harmonic-affect-state-v1",
            "generated_at": NOW - 400,
            "status": "harmonic_affect_state_ready",
            "summary": {
                "victory": 0.1,
                "defeat": 0.1,
                "fear": 0.4,
                "resolve": 0.5,
                "valence": 0.2,
                "arousal": 0.6,
                "caution_bias": 0.35,
                "affect_phase": "protective_recalibration",
                "emotion_anchor": "Reason",
            },
            "state_contract": {},
        },
    )
    row = observed.assessment_observation("affect")
    assert row["available"] is False
    assert row["read_state"] == "stale"
    assert row["reason"] == "source_timestamp_expired"
    assert row["truth_status"] == "real_derived"

def test_stale_assessment_snapshot_is_not_current_route_data(tmp_path, monkeypatch):
    monkeypatch.setattr(observed, "REPO_ROOT", tmp_path)
    write_state(
        tmp_path / "docs" / "audits" / "aureon_assessment_snapshots.json",
        {
            "schema_version": "aureon-assessment-snapshots-v1",
            "generated_at": NOW - 400,
            "assessments": {
                "metacognition": {
                    "available": True,
                    "truth_status": "real_derived",
                    "contributors": 1,
                    "signals": {},
                    "ts": NOW - 400,
                }
            },
        },
    )
    row = observed.assessment_observation("metacognition")
    assert row["available"] is False
    assert row["read_state"] == "stale"
    assert row["reason"] == "source_timestamp_expired"
    assert row["truth_status"] == "real_derived"

