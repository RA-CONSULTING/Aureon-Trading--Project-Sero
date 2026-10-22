"""The fleet launcher reports real flight-recorder health and refuses live trading."""

from __future__ import annotations

import json

import pytest

from aureon_fusion import fleet_launcher


def test_launcher_refuses_a_live_trading_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUREON_LIVE_TRADING", "1")
    assert fleet_launcher.main(["--check"]) == 2


def test_launcher_refuses_the_capital_release_pin(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.delenv("AUREON_LIVE_TRADING", raising=False)
    monkeypatch.delenv("AUREON_FUSION_ARM_LIVE", raising=False)
    pin = tmp_path / "capital_release.flag"
    pin.write_text("present", encoding="utf-8")
    monkeypatch.setattr(fleet_launcher, "CAPITAL_RELEASE_FLAG", pin)
    assert fleet_launcher.main(["--check"]) == 2


def test_check_fails_closed_when_the_health_file_is_missing(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.delenv("AUREON_LIVE_TRADING", raising=False)
    monkeypatch.delenv("AUREON_FUSION_ARM_LIVE", raising=False)
    monkeypatch.setattr(fleet_launcher, "CAPITAL_RELEASE_FLAG", tmp_path / "absent.flag")
    monkeypatch.setattr(fleet_launcher, "FLIGHT_HEALTH", tmp_path / "missing.json")
    assert fleet_launcher.main(["--check"]) == 1


def test_check_accepts_only_eleven_fresh_faculties(monkeypatch: pytest.MonkeyPatch, tmp_path, capsys) -> None:
    monkeypatch.delenv("AUREON_LIVE_TRADING", raising=False)
    monkeypatch.delenv("AUREON_FUSION_ARM_LIVE", raising=False)
    monkeypatch.setattr(fleet_launcher, "CAPITAL_RELEASE_FLAG", tmp_path / "absent.flag")
    health = tmp_path / "flight_health.json"
    health.write_text(
        json.dumps(
            {
                "all_fresh": True,
                "fresh_count": 11,
                "faculties_count": 11,
                "stale_list": [],
                "simulated_detected": [],
                "ts": "2026-10-22T20:43:32+00:00",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(fleet_launcher, "FLIGHT_HEALTH", health)
    assert fleet_launcher.main(["--check"]) == 0
    assert json.loads(capsys.readouterr().out)["ok"] is True

    health.write_text(
        json.dumps(
            {
                "all_fresh": False,
                "fresh_count": 1,
                "faculties_count": 11,
                "stale_list": ["hnc_core"],
                "simulated_detected": [],
            }
        ),
        encoding="utf-8",
    )
    assert fleet_launcher.main(["--check"]) == 1
