import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from aureon.command_centers.aureon_system_hub import SystemRegistry


def test_registry_uses_env_workspace(monkeypatch, tmp_path):
    ws = tmp_path / "repo"
    ws.mkdir()
    monkeypatch.setenv("AUREON_WORKSPACE", str(ws))

    registry = SystemRegistry()

    assert registry.workspace_path == ws.resolve()


def test_scan_workspace_resets_state_between_runs(tmp_path):
    ws = tmp_path / "repo"
    ws.mkdir()

    (ws / "aureon_alpha.py").write_text('"""alpha"""\n')
    (ws / "aureon_beta.py").write_text('"""beta"""\n')

    registry = SystemRegistry(workspace_path=str(ws))
    registry.scan_workspace()
    first_count = len(registry.systems)

    registry.scan_workspace()
    second_count = len(registry.systems)
    category_total = sum(cat.system_count for cat in registry.categories.values())

    assert first_count == 2
    assert second_count == 2
    assert category_total == 2


def test_scan_workspace_skips_cache_and_venv_dirs(tmp_path):
    ws = tmp_path / "repo"
    ws.mkdir()

    (ws / "aureon_live.py").write_text('"""root"""\n')
    pycache_dir = ws / "__pycache__"
    pycache_dir.mkdir()
    (pycache_dir / "aureon_hidden.py").write_text('"""hidden"""\n')

    venv_dir = ws / ".venv" / "lib"
    venv_dir.mkdir(parents=True)
    (venv_dir / "aureon_venv.py").write_text('"""venv"""\n')

    registry = SystemRegistry(workspace_path=str(ws))
    registry.scan_workspace()

    assert "aureon_live" in registry.systems
    assert "aureon_hidden" not in registry.systems
    assert "aureon_venv" not in registry.systems


def test_scan_prunes_vendor_and_cache_before_scandir(tmp_path, monkeypatch):
    """Excluded children must never be enumerated, even when they contain Python."""
    ws = tmp_path / "repo"
    ws.mkdir()
    (ws / "live.py").write_text('"""live source"""\n')
    blocked = {"node_modules", ".git", "__pycache__", ".venv", "venv", ".cache",
               ".pytest_cache", ".mypy_cache", ".ruff_cache", ".tox", ".nox"}
    for name in blocked:
        folder = ws / "frontend" / name / "nested"
        folder.mkdir(parents=True)
        (folder / "vendor.py").write_text('"""must never be enumerated"""\n')
    original = os.scandir
    visited = []

    def guarded_scandir(path):
        relative = Path(path).relative_to(ws)
        assert not any(part.lower() in blocked for part in relative.parts)
        visited.append(relative.as_posix())
        return original(path)

    with monkeypatch.context() as context:
        context.setattr(os, "scandir", guarded_scandir)
        registry = SystemRegistry(workspace_path=str(ws))
        registry.scan_workspace()
    assert set(registry.systems) == {"live"}
    assert "frontend" in visited


def test_scan_preserves_real_nested_source_and_metadata(tmp_path):
    ws = tmp_path / "repo"
    source = ws / "aureon" / "autonomy" / "state"
    source.mkdir(parents=True)
    (source / "science_dashboard.py").write_text(
        '"""Measured source dashboard"""\nfrom flask import Flask\n'
        'from aureon.core.aureon_thought_bus import ThoughtBus\n'
        'app = Flask(__name__)\napp.run(port=9123)\n'
    )
    (source / "test_not_catalogued.py").write_text('raise RuntimeError("must not execute")\n')
    registry = SystemRegistry(workspace_path=str(ws))
    registry.scan_workspace()
    assert set(registry.systems) == {"science_dashboard"}
    result = registry.systems["science_dashboard"]
    assert Path(result.filepath).parts == ("aureon", "autonomy", "state", "science_dashboard.py")
    assert result.description == "Measured source dashboard"
    assert result.is_dashboard and result.dashboard_port == 9123
    assert result.has_thought_bus
    assert len(registry.categories) == 12


def test_scan_excludes_reparse_directory_before_descent(tmp_path, monkeypatch):
    """Exercise junction handling without needing Windows symlink privileges."""
    ws = tmp_path / "repo"
    linked = ws / "external_link"
    linked.mkdir(parents=True)
    (linked / "private_source.py").write_text('"""outside source fixture"""\n')
    (ws / "live.py").write_text('"""live"""\n')
    original = Path.lstat

    def with_reparse_marker(path, *args, **kwargs):
        if path == linked:
            return SimpleNamespace(st_file_attributes=0x400, st_mode=original(path).st_mode)
        return original(path, *args, **kwargs)

    with monkeypatch.context() as context:
        context.setattr(Path, "lstat", with_reparse_marker)
        registry = SystemRegistry(workspace_path=str(ws))
        assert [path.name for path in registry._iter_python_files()] == ["live.py"]


def test_scan_does_not_read_symlinked_files_or_follow_directory_cycles(tmp_path):
    ws = tmp_path / "repo"
    ws.mkdir()
    outside = tmp_path / "outside.py"
    outside.write_text('"""not part of this source tree"""\n')
    (ws / "live.py").write_text('"""live"""\n')
    try:
        (ws / "linked.py").symlink_to(outside)
        (ws / "cycle").symlink_to(ws, target_is_directory=True)
    except OSError:
        pytest.skip("host does not grant symlink creation; reparse pruning tested separately")
    registry = SystemRegistry(workspace_path=str(ws))
    assert [path.name for path in registry._iter_python_files()] == ["live.py"]


def test_scan_keeps_deterministic_duplicate_name_resolution(tmp_path):
    ws = tmp_path / "repo"
    for folder in ("z", "a"):
        target = ws / folder
        target.mkdir(parents=True)
        (target / "shared.py").write_text(f'"""{folder} description"""\n')
    registry = SystemRegistry(workspace_path=str(ws))
    registry.scan_workspace()
    assert registry.systems["shared"].description == "z description"
