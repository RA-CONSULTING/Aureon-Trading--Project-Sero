"""The production engines stay at the workspace root. Unreferenced clutter does not."""

from pathlib import Path

from aureon_fusion.paths import (
    HNC_DAEMON,
    PLANETARY_DAEMON,
    REALTIME_FEEDER,
    SCHUMANN_DAEMON,
    SERO_AUTONOMOUS_EXPANSION,
    SERO_MASTER_ORCHESTRATOR,
)


ROOT = Path(__file__).resolve().parents[1]


def test_launched_engines_remain_at_the_workspace_root() -> None:
    for path in (
        HNC_DAEMON,
        PLANETARY_DAEMON,
        REALTIME_FEEDER,
        SCHUMANN_DAEMON,
        SERO_AUTONOMOUS_EXPANSION,
        SERO_MASTER_ORCHESTRATOR,
    ):
        assert path.is_file(), path
        assert path.parent == ROOT


def test_unreferenced_root_clutter_lives_in_the_archive() -> None:
    assert not (ROOT / "AOIA-Core_Pitch_Deck.md").exists()
    assert (ROOT / "archive" / "workspace-root" / "notes" / "AOIA-Core_Pitch_Deck.md").is_file()
    assert (ROOT / "archive" / "workspace-root" / "scripts" / "_download_academia_papers.py").is_file()
    assert (ROOT / "PRODUCTION_READINESS.md").is_file()
    assert (ROOT / "SELF_REPAIR.md").is_file()
