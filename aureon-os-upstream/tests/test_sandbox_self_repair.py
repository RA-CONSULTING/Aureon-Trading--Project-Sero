"""The sandbox repair fixes one wrong return, and the guard blocks the rest."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from aureon.autonomous.aureon_sandbox_self_repair import load_architect, repair_sandbox
from aureon.autonomous.self_repair_guard import KILL_ENV, review_log_path

MODULE = """\
def schumann_band_count():
    return 7
"""

TEST = """\
from schumann_band import schumann_band_count

def test_eight_bands():
    assert schumann_band_count() == 8
"""

PASSING_MODULE = """\
def schumann_band_count():
    return 8
"""

WRONG_TEST = """\
from schumann_band import schumann_band_count

def test_eight_bands():
    assert schumann_band_count() == 9
"""


def _sandbox(tmp_path: Path, module: str, test: str) -> Path:
    root = tmp_path / "sandbox"
    root.mkdir()
    (root / "schumann_band.py").write_text(module, encoding="utf-8")
    (root / "test_schumann_band.py").write_text(test, encoding="utf-8")
    return root


def test_repairs_a_wrong_return_on_a_review_branch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(KILL_ENV, raising=False)
    root = _sandbox(tmp_path, MODULE, TEST)
    report = repair_sandbox(root)
    assert report["status"] == "repaired"
    assert report["live_trading"] is False
    assert report["may_act"] is False
    assert report["edited_test"] is False
    assert report["previous_return"] == 7
    assert report["repaired_return"] == 8
    assert "return 8" in (root / "schumann_band.py").read_text(encoding="utf-8")
    assert "assert schumann_band_count() == 8" in (root / "test_schumann_band.py").read_text(encoding="utf-8")
    assert report["commit"]
    assert str(report["branch"]).startswith("aureon-self-repair/")
    log = review_log_path(root).read_text(encoding="utf-8")
    assert "repair_committed" in log
    assert "tests_passed" in log


def test_repairs_the_implementation_and_leaves_the_test_file_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(KILL_ENV, raising=False)
    root = _sandbox(tmp_path, PASSING_MODULE, WRONG_TEST)
    original_test = (root / "test_schumann_band.py").read_text(encoding="utf-8")
    report = repair_sandbox(root)
    assert report["status"] == "repaired"
    assert report["edited_test"] is False
    assert (root / "test_schumann_band.py").read_text(encoding="utf-8") == original_test
    assert "return 9" in (root / "schumann_band.py").read_text(encoding="utf-8")


def test_repairs_an_operator_and_a_name_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(KILL_ENV, raising=False)
    root = tmp_path / "app"
    root.mkdir()
    (root / "calc.py").write_text("def add(a, b):\n    return a - b\n", encoding="utf-8")
    (root / "scale.py").write_text("def double(n):\n    return nn * 2\n", encoding="utf-8")
    (root / "test_app.py").write_text(
        "from calc import add\nfrom scale import double\n\n"
        "def test_add():\n    assert add(2, 3) == 5\n\n"
        "def test_double():\n    assert double(4) == 8\n",
        encoding="utf-8",
    )
    original_test = (root / "test_app.py").read_text(encoding="utf-8")
    report = repair_sandbox(root)
    assert report["status"] == "repaired", report
    assert report["edited_test"] is False
    assert (root / "test_app.py").read_text(encoding="utf-8") == original_test
    assert "return a + b" in (root / "calc.py").read_text(encoding="utf-8")
    assert "return n * 2" in (root / "scale.py").read_text(encoding="utf-8")
    assert report["commit"]


def test_kill_switch_blocks_the_repair(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(KILL_ENV, "1")
    root = _sandbox(tmp_path, MODULE, TEST)
    report = repair_sandbox(root)
    assert report["status"] == "held"
    assert report["reason"] == "kill_switch"
    assert "return 7" in (root / "schumann_band.py").read_text(encoding="utf-8")


def test_queen_writer_rejects_secrets_live_trading_and_open_gates(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(KILL_ENV, raising=False)
    architect = load_architect()(repo_path=str(tmp_path))
    assert architect.write_file(".env", "BINANCE_API_SECRET=not-for-the-tree\n") is False
    assert not (tmp_path / ".env").exists()
    assert architect.write_file("arm.py", "AUREON_LIVE_TRADING=1\n") is False
    assert not (tmp_path / "arm.py").exists()
    assert architect.write_file("gate.py", "may_act = True\n") is False
    assert not (tmp_path / "gate.py").exists()
    kept = "SAMPLE = 'sample_or_synthetic_evidence_excluded'\nmay_act = False\n"
    assert architect.write_file("policy.py", kept) is True
    loosened = "SAMPLE = 'accepted'\nmay_act = False\n"
    assert architect.write_file("policy.py", loosened) is False
    assert "sample_or_synthetic_evidence_excluded" in (tmp_path / "policy.py").read_text(encoding="utf-8")
    log = review_log_path(tmp_path).read_text(encoding="utf-8")
    assert "secret_path" in log
    assert "live_trading_arm" in log
    assert "evidence_gate_loosened" in log
    assert "not-for-the-tree" not in log
    monkeypatch.setenv(KILL_ENV, "1")
    assert architect.write_file("notes.py", "print('hello')\n") is False
    assert not (tmp_path / "notes.py").exists()


def test_review_log_is_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(KILL_ENV, raising=False)
    root = _sandbox(tmp_path, MODULE, TEST)
    repair_sandbox(root)
    for line in review_log_path(root).read_text(encoding="utf-8").splitlines():
        json.loads(line)
    assert os.environ.get("AUREON_LIVE_TRADING", "0") != "1"
