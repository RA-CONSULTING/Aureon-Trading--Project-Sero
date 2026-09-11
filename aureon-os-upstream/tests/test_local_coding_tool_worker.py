from __future__ import annotations

import importlib.util
from pathlib import Path

from aureon.autonomous.workers.local_coding_tool_worker import build_local_coding_tool


def test_worker_creates_expected_files(tmp_path: Path) -> None:
    result = build_local_coding_tool(
        "Build a local quantum spline inventory generator tool",
        root=tmp_path,
        families=["coding"],
        task_family="coding",
        build_id="test123",
    )
    assert result["ok"] is True
    paths = [Path(p) for p in result["output_files"] if not str(p).startswith("/")]
    names = {p.name for p in paths}
    assert names >= {"tool.py", "index.html", "skill.json", "RUNBOOK.md"}


def test_tool_run_returns_ok(tmp_path: Path) -> None:
    result = build_local_coding_tool(
        "Build a local quantum spline inventory generator tool",
        root=tmp_path,
        families=["coding"],
        task_family="coding",
        build_id="test123",
    )
    tool_path = next(Path(p) for p in result["output_files"] if Path(p).name == "tool.py")
    spec = importlib.util.spec_from_file_location("generated_tool", tool_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    output = module.run()
    assert isinstance(output, dict)
    assert output["ok"] is True
    assert "spline_samples" in output


def test_tool_has_no_forbidden_authorities(tmp_path: Path) -> None:
    result = build_local_coding_tool(
        "Build a local quantum spline inventory generator tool",
        root=tmp_path,
        families=["coding"],
        task_family="coding",
        build_id="test123",
    )
    tool_path = next(Path(p) for p in result["output_files"] if Path(p).name == "tool.py")
    raw = tool_path.read_text(encoding="utf-8")
    # The generated tool contains a safety disclaimer string; strip it before
    # scanning for actionable authority code so the test does not flag its own
    # safety boundary text.
    content = raw.lower()
    for line in raw.splitlines():
        if '"authority":' in line or "authority:" in line.lower():
            content = content.replace(line.lower(), "")
    forbidden = [
        "live trading",
        "payment",
        "filing",
        "credential",
        "api_key",
        "private_key",
        "destructive",
        "rm -rf",
        "shutil.rmtree",
    ]
    for needle in forbidden:
        assert needle not in content, f"found forbidden authority needle: {needle}"
