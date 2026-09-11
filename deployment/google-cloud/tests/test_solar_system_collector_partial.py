"""Offline regression for optional-provider failure in the VM collector.

Import dependencies are isolated so no shared API cache, live workspace, network,
or running collector state can be opened by these tests.
"""
import importlib.util
import json
from pathlib import Path
import sys
import types

import pytest


@pytest.fixture
def collector_module(monkeypatch, tmp_path):
    paths = types.ModuleType("aureon_fusion.paths")
    paths.WORKSPACE = tmp_path
    communion = types.ModuleType("aureon_fusion.api_communion")
    def forbidden(*args, **kwargs):
        pytest.fail("network/shared-cache access is forbidden")
    communion.get_json = forbidden
    package = types.ModuleType("aureon_fusion")
    package.__path__ = []
    for name, module in (("aureon_fusion", package), ("aureon_fusion.paths", paths),
                         ("aureon_fusion.api_communion", communion), ("requests", types.ModuleType("requests"))):
        monkeypatch.setitem(sys.modules, name, module)
    source = Path(__file__).resolve().parents[3] / "solar_system_collector.py"
    spec = importlib.util.spec_from_file_location("isolated_solar_collector", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def complete_raw():
    observed = "2026-09-11T10:00:00Z"
    return {
        "sunspot_cycle": [{"time_tag": "2026-08", "ssn": 80, "f10.7": 120, "smoothed_ssn": 90}],
        "solar_wind_l1": [{"time_tag": observed, "proton_speed": 420, "proton_density": 6, "proton_temperature": 110000}],
        "mag_field_l1": [{"time_tag": observed, "bx_gsm": 1, "by_gsm": 2, "bz_gsm": -3, "bt": 4}],
        "proton_flux": [{"time_tag": observed, "flux": 0.3, "energy": ">=10 MeV"}],
        "electron_flux": [{"time_tag": observed, "flux": 70.0, "energy": ">=2 MeV"}],
        "xray_flux": [{"time_tag": observed, "flux": 2e-6}],
        "alerts": [{"product_id": "R", "scale": 1}],
        "aurora_forecast": {"Forecast Time": observed, "Observation Time": observed, "coordinates": [[0, 70, 5]]},
    }


def configured(module, monkeypatch, raw):
    collector = module.SolarSystemCollector()
    by_url = {config["url"]: raw.get(name) for name, config in module.SOLAR_SOURCES.items()}
    monkeypatch.setattr(collector, "_fetch", lambda url, *args: by_url[url])
    return collector


def test_none_electron_preserves_other_seven_readings_and_provider_clocks(collector_module, monkeypatch):
    module = collector_module
    raw = complete_raw()
    raw["electron_flux"] = []  # Actual failure: fetch succeeds; parser returns None.
    collector = configured(module, monkeypatch, raw)
    state = collector.collect()
    assert state["collection_status"] == {
        "total_sources": 8, "successful_sources": 7, "failed_sources": 1,
        "available_source_names": sorted(set(raw) - {"electron_flux"}),
        "unavailable_source_names": ["electron_flux"], "complete": False,
    }
    assert "electron_flux" not in state["particle_environment"]
    assert "electron_flux" not in state["raw_results"]
    assert state["particle_environment"]["proton_flux"] == 0.3
    assert state["raw_results"]["proton_flux"]["time_tag"] == raw["proton_flux"][0]["time_tag"]
    assert state["solar_wind"]["time_tag"] == raw["solar_wind_l1"][0]["time_tag"]
    assert state["timestamp_kind"] == "collection_time"
    assert state["solar_system_health"]["data_complete"] is False
    assert json.loads(module.STATE_FILE.read_text())["particle_environment"] == state["particle_environment"]


@pytest.mark.parametrize("missing", list(complete_raw()))
def test_each_optional_fetch_can_be_missing_without_losing_others(collector_module, monkeypatch, missing):
    raw = complete_raw()
    raw[missing] = None
    state = configured(collector_module, monkeypatch, raw).collect()
    assert state["collection_status"]["successful_sources"] == 7
    assert state["collection_status"]["unavailable_source_names"] == [missing]


def test_direct_build_with_none_does_not_count_it_as_successful(collector_module):
    collector = collector_module.SolarSystemCollector()
    proton = collector._parse_proton_flux(complete_raw()["proton_flux"])
    state = collector._build_state({"electron_flux": None, "proton_flux": proton})
    assert state["collection_status"]["successful_sources"] == 1
    assert state["particle_environment"] == {"proton_flux": 0.3, "sep_level": "none"}


def test_all_sources_unavailable_does_not_refresh_previous_state(collector_module, monkeypatch):
    module = collector_module
    collector = configured(module, monkeypatch, {})
    prior = '{"timestamp":"prior-provider-cycle","sentinel":"unchanged"}'
    module.STATE_FILE.write_text(prior)
    assert collector.collect() is None
    assert collector._build_state({name: None for name in module.SOLAR_SOURCES}) is None
    assert module.STATE_FILE.read_text() == prior
    assert not module.TIMESERIES_FILE.exists()


def test_no_wind_does_not_invent_a_speed_or_magnetic_coupling(collector_module, monkeypatch):
    raw = complete_raw()
    raw["solar_wind_l1"] = []
    state = configured(collector_module, monkeypatch, raw).collect()
    assert state["solar_wind"] == {}
    assert state["magnetic_field"]["bz"] == -3
    assert state["magnetic_field"]["coupling_efficiency"] is None
    assert state["magnetic_field"]["time_tag"] == raw["mag_field_l1"][0]["time_tag"]


def test_source_parse_exception_is_isolated(collector_module, monkeypatch):
    raw = complete_raw()
    raw["sunspot_cycle"][0]["f10.7"] = "malformed-provider-value"
    state = configured(collector_module, monkeypatch, raw).collect()
    assert state["collection_status"]["unavailable_source_names"] == ["sunspot_cycle"]
    assert state["collection_status"]["successful_sources"] == 7
    assert state["particle_environment"]["electron_flux"] == 70.0


@pytest.mark.parametrize("parser_name", ["_parse_electron_flux", "_parse_proton_flux", "_parse_xray"])
@pytest.mark.parametrize("flux", [None, "missing", float("nan"), float("inf"), -1, True])
def test_missing_or_invalid_particle_flux_is_not_synthesized_as_zero(collector_module, parser_name, flux):
    collector = collector_module.SolarSystemCollector()
    parser = getattr(collector, parser_name)
    assert parser([{"time_tag": "provider-time"}]) is None
    assert parser([{"flux": flux, "time_tag": "provider-time"}]) is None


@pytest.mark.parametrize("parser_name", ["_parse_electron_flux", "_parse_proton_flux", "_parse_xray"])
def test_observed_zero_particle_flux_is_preserved(collector_module, parser_name):
    result = getattr(collector_module.SolarSystemCollector(), parser_name)([{"flux": 0, "time_tag": "provider-time"}])
    assert result["flux"] == 0 and result["time_tag"] == "provider-time"


def test_complete_cycle_keeps_existing_values_and_reports_complete(collector_module, monkeypatch):
    state = configured(collector_module, monkeypatch, complete_raw()).collect()
    assert state["collection_status"]["successful_sources"] == 8
    assert state["collection_status"]["failed_sources"] == 0
    assert state["collection_status"]["complete"] is True
    assert state["magnetic_field"]["coupling_efficiency"] == 1.26
    assert state["particle_environment"]["electron_flux"] == 70.0
