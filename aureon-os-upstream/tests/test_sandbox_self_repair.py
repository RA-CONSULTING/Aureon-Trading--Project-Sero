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


def test_queen_writer_can_author_trading_gates_and_env_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(KILL_ENV, raising=False)
    architect = load_architect()(repo_path=str(tmp_path))
    assert architect.write_file(".env", "BINANCE_API_KEY=\nBINANCE_API_SECRET=\n") is True
    assert "BINANCE_API_KEY=" in (tmp_path / ".env").read_text(encoding="utf-8")
    assert architect.write_file("arm.py", "AUREON_LIVE_TRADING=1\n") is True
    assert "AUREON_LIVE_TRADING=1" in (tmp_path / "arm.py").read_text(encoding="utf-8")
    assert architect.write_file("gate.py", 'may_act = True\ngate = "RELEASE"\n') is True
    gate = (tmp_path / "gate.py").read_text(encoding="utf-8")
    assert "may_act = True" in gate
    assert 'gate = "RELEASE"' in gate
    monkeypatch.setenv(KILL_ENV, "1")
    assert architect.write_file("notes.py", "print('hello')\n") is False
    assert not (tmp_path / "notes.py").exists()


def test_repairs_a_trading_size_and_an_evidence_gate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(KILL_ENV, raising=False)
    root = tmp_path / "desk"
    root.mkdir()
    (root / "desk.py").write_text(
        "def position_qty(price):\n    return 0\n\ndef evidence_gate():\n    return \"HOLD\"\n",
        encoding="utf-8",
    )
    (root / "test_desk.py").write_text(
        "from desk import evidence_gate, position_qty\n\n"
        "def test_size():\n    assert position_qty(100) == 1\n\n"
        "def test_gate():\n    assert evidence_gate() == \"RELEASE\"\n",
        encoding="utf-8",
    )
    original_test = (root / "test_desk.py").read_text(encoding="utf-8")
    report = repair_sandbox(root)
    assert report["status"] == "repaired", report
    text = (root / "desk.py").read_text(encoding="utf-8")
    assert "return 1" in text
    assert 'return "RELEASE"' in text
    assert (root / "test_desk.py").read_text(encoding="utf-8") == original_test


def test_review_log_is_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(KILL_ENV, raising=False)
    root = _sandbox(tmp_path, MODULE, TEST)
    repair_sandbox(root)
    for line in review_log_path(root).read_text(encoding="utf-8").splitlines():
        json.loads(line)
    assert os.environ.get("AUREON_LIVE_TRADING", "0") != "1"
