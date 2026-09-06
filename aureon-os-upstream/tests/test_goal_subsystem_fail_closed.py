"""Fail-closed probes for the goals subsystem.

Covers the honest-behavior fixes in:
  - aureon/portfolio/aureon_billion_goal_tracker.py
    (past deadline -> expired_needs_renewal, never a silent 0.0 required
    daily return; state files anchored under GOAL_STATE_DIR / SERO_WORKSPACE /
    repo state/goals, never bare CWD)
  - aureon/simulation/aureon_quantum_goal_engine.py
    (anchored state file; duplicate open goal with same title+scale is
    skipped instead of minted again)
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path

from pytest import MonkeyPatch


def _reload_tracker(monkeypatch: MonkeyPatch):
    monkeypatch.delenv("GOAL_STATE_DIR", raising=False)
    monkeypatch.delenv("SERO_WORKSPACE", raising=False)
    monkeypatch.delenv("BILLION_GOAL_DEADLINE", raising=False)
    import aureon.portfolio.aureon_billion_goal_tracker as tracker_mod

    return importlib.reload(tracker_mod)


def test_past_deadline_marks_expired_needs_renewal(monkeypatch, tmp_path):
    tracker_mod = _reload_tracker(monkeypatch)
    monkeypatch.setenv("GOAL_STATE_DIR", str(tmp_path))

    # Default deadline (2026-02-20) is in the past.
    assert tracker_mod.is_deadline_expired()
    assert tracker_mod.get_deadline_status() == "expired_needs_renewal"
    assert tracker_mod.DEADLINE_MODE is False

    # Required daily return must fail closed: None, never a silent 0.0.
    assert tracker_mod.get_required_daily_return(1_000.0) is None
    assert tracker_mod.get_required_daily_return(0.0) is None

    # Urgency must not pretend we are in a critical final push.
    assert "EXPIRED" in tracker_mod.get_deadline_urgency()
    assert "CRITICAL" not in tracker_mod.get_deadline_urgency()

    # The tracker persists the expired state on disk.
    tracker = tracker_mod.BillionDollarGoalTracker()
    data = json.loads(tracker.persist_path.read_text(encoding="utf-8"))
    assert data["deadline"]["status"] == "expired_needs_renewal"
    dashboard = tracker.get_dashboard()
    assert dashboard["deadline"]["status"] == "expired_needs_renewal"
    assert dashboard["deadline"]["required_daily_return_pct"] is None


def test_configured_future_deadline_reactivates(monkeypatch, tmp_path):
    monkeypatch.setenv("GOAL_STATE_DIR", str(tmp_path))
    monkeypatch.setenv("BILLION_GOAL_DEADLINE", "2027-12-31T23:59:59")
    import aureon.portfolio.aureon_billion_goal_tracker as tracker_mod

    tracker_mod = importlib.reload(tracker_mod)

    assert not tracker_mod.is_deadline_expired()
    assert tracker_mod.get_deadline_status() == "active"
    assert tracker_mod.DEADLINE_MODE is True
    required = tracker_mod.get_required_daily_return(1_000.0)
    assert required is not None and required > 0
    assert "CRITICAL" not in tracker_mod.get_deadline_urgency()


def test_invalid_deadline_env_falls_back_to_default(monkeypatch, tmp_path):
    monkeypatch.setenv("BILLION_GOAL_DEADLINE", "not-a-date")
    tracker_mod = _reload_tracker(monkeypatch)
    monkeypatch.setenv("GOAL_STATE_DIR", str(tmp_path))

    # Falls back to the default (past) deadline and stays honest about it.
    assert tracker_mod.DEADLINE_DATE == tracker_mod.DEFAULT_DEADLINE
    assert tracker_mod.get_deadline_status() == "expired_needs_renewal"


def test_state_files_anchor_under_goal_state_dir(monkeypatch, tmp_path):
    state_dir = tmp_path / "anchored_goal_state"
    monkeypatch.setenv("GOAL_STATE_DIR", str(state_dir))
    import aureon.portfolio.aureon_billion_goal_tracker as tracker_mod

    tracker_mod = importlib.reload(tracker_mod)

    tracker = tracker_mod.BillionDollarGoalTracker()
    assert tracker.persist_path == state_dir / "billion_goal_progress.json"
    assert tracker.persist_path.exists()
    assert not (Path.cwd() / "billion_goal_progress.json").exists()

    import aureon.simulation.aureon_quantum_goal_engine as engine_mod

    engine_mod = importlib.reload(engine_mod)
    engine = engine_mod.QuantumGoalEngine()
    assert Path(engine.state_file) == state_dir / "quantum_goal_engine_state.json"
    engine.create_goal(
        title="Reach $1",
        description="anchor probe",
        scale=engine_mod.GoalScale.MICRO,
        target_value=1.0,
    )
    assert Path(engine.state_file).exists()
    assert not (Path.cwd() / "quantum_goal_engine_state.json").exists()


def test_sero_workspace_anchor(monkeypatch, tmp_path):
    monkeypatch.delenv("GOAL_STATE_DIR", raising=False)
    monkeypatch.setenv("SERO_WORKSPACE", str(tmp_path))
    import aureon.portfolio.aureon_billion_goal_tracker as tracker_mod

    tracker_mod = importlib.reload(tracker_mod)

    assert tracker_mod.get_goal_state_dir() == tmp_path / "state" / "goals"


def test_duplicate_open_goal_is_skipped(monkeypatch, tmp_path):
    monkeypatch.setenv("GOAL_STATE_DIR", str(tmp_path))
    import aureon.portfolio.aureon_billion_goal_tracker as tracker_mod

    importlib.reload(tracker_mod)
    import aureon.simulation.aureon_quantum_goal_engine as engine_mod

    engine_mod = importlib.reload(engine_mod)
    engine = engine_mod.QuantumGoalEngine()

    first = engine.create_goal(
        title="Reach $1",
        description="first",
        scale=engine_mod.GoalScale.MICRO,
        target_value=1.0,
    )
    created = engine.state.total_goals_created
    duplicate = engine.create_goal(
        title="Reach $1",
        description="duplicate",
        scale=engine_mod.GoalScale.MICRO,
        target_value=1.0,
    )

    assert duplicate is first
    assert engine.state.total_goals_created == created  # no new goal minted
    same_title = [g for g in engine.state.active_goals if g.title == "Reach $1"]
    assert len(same_title) == 1

    # A different scale with the same title is still allowed.
    meso = engine.create_goal(
        title="Reach $1",
        description="different scale",
        scale=engine_mod.GoalScale.MESO,
        target_value=1.0,
    )
    assert meso is not first


def test_micro_goal_loop_mints_no_duplicates(monkeypatch, tmp_path):
    monkeypatch.setenv("GOAL_STATE_DIR", str(tmp_path))
    import aureon.portfolio.aureon_billion_goal_tracker as tracker_mod

    importlib.reload(tracker_mod)
    import aureon.simulation.aureon_quantum_goal_engine as engine_mod

    engine_mod = importlib.reload(engine_mod)
    engine = engine_mod.QuantumGoalEngine()
    assert engine.billion_tracker is not None

    engine._generate_micro_goals(count=3)

    micro = [g for g in engine.state.active_goals if g.scale == engine_mod.GoalScale.MICRO]
    assert len(micro) == 1  # ceil(balance)+1 title is identical each cycle
    assert engine.state.total_goals_created == 1
