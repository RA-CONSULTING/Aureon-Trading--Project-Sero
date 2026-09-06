"""Fail-closed goal validation coverage.

Owner decree: partial success is 'partial' (never 'completed'), and
coherence below threshold gates step execution AND blocks promotion of
a plan to 'completed' (warn AND gate).
"""

from __future__ import annotations

from aureon.core.goal_execution_engine import (
    GoalExecutionEngine,
    GoalPlan,
    GoalStep,
)


def _plan(steps: list[GoalStep], threshold: float = 0.3) -> GoalPlan:
    return GoalPlan(
        original_text="test",
        objective="test objective",
        steps=steps,
        coherence_threshold=threshold,
    )


def test_partial_step_success_is_partial_not_completed() -> None:
    plan = _plan([
        GoalStep(title="ok", intent="read_file", status="completed",
                 coherence_at_execution=0.9),
        GoalStep(title="bad", intent="read_file", status="failed",
                 coherence_at_execution=0.9),
    ])
    GoalExecutionEngine()._validate_goal(plan)
    assert plan.status == "partial"


def test_all_steps_completed_with_coherence_promotes_to_completed() -> None:
    plan = _plan([
        GoalStep(title="a", intent="read_file", status="completed",
                 coherence_at_execution=0.9),
        GoalStep(title="b", intent="read_file", status="completed",
                 coherence_at_execution=0.8),
    ])
    GoalExecutionEngine()._validate_goal(plan)
    assert plan.status == "completed"


def test_low_avg_coherence_blocks_completed_promotion() -> None:
    plan = _plan([
        GoalStep(title="a", intent="read_file", status="completed",
                 coherence_at_execution=0.2),
        GoalStep(title="b", intent="read_file", status="completed",
                 coherence_at_execution=0.1),
    ])
    GoalExecutionEngine()._validate_goal(plan)
    assert plan.status == "partial"


def test_no_steps_is_failed() -> None:
    plan = _plan([])
    GoalExecutionEngine()._validate_goal(plan)
    assert plan.status == "failed"


def test_low_coherence_gates_step_execution(monkeypatch) -> None:
    engine = GoalExecutionEngine()
    monkeypatch.setattr(engine, "_get_coherence", lambda: 0.1)

    executed: list[str] = []
    monkeypatch.setattr(
        engine, "_execute_step",
        lambda step: executed.append(step.step_id) or {"success": True},
    )

    plan = _plan([GoalStep(title="gated", intent="read_file")],
                 threshold=0.3)
    engine._execute_plan_sequential(plan)

    step = plan.steps[0]
    assert executed == []                      # step never executed
    assert step.status == "skipped"            # gated, fail-closed
    assert step.validation_result["valid"] is False


def test_adequate_coherence_allows_step_execution(monkeypatch) -> None:
    engine = GoalExecutionEngine()
    monkeypatch.setattr(engine, "_get_coherence", lambda: 0.9)

    executed: list[str] = []
    monkeypatch.setattr(
        engine, "_execute_step",
        lambda step: executed.append(step.step_id) or {"success": True},
    )

    plan = _plan([GoalStep(title="runs", intent="read_file")],
                 threshold=0.3)
    engine._execute_plan_sequential(plan)

    assert len(executed) == 1
    assert plan.steps[0].status in ("completed", "failed")  # ran + validated
