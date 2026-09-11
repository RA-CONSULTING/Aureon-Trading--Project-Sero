from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from aureon.autonomous.aureon_autonomous_coherence_gate_director import (
    DEFAULT_AUDIT_JSON,
    DEFAULT_AUDIT_MD,
    DEFAULT_BACKUP_DIR,
    DEFAULT_PUBLIC_JSON,
    DEFAULT_STATE_PATH,
    CoherenceGateDirector,
    TelemetrySnapshot,
    _bounded_target_path,
    _default_root,
    _extra_blocked_path,
    build_and_write_coherence_gate_director,
)


def _init_git(path: Path) -> None:
    subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _passing_telemetry() -> TelemetrySnapshot:
    return TelemetrySnapshot(
        canonical_field={
            "available": True,
            "data_status": "live",
            "truth_status": "real_derived",
            "freshness_status": "fresh",
            "coherence_gamma": 0.9,
        },
        evolution_inputs={
            "gamma": 0.9,
            "advisory_open": True,
            "lighthouse_severity": None,
            "auris_confidence": 0.9,
            "beta": 0.8,
        },
        evolution_flow={
            "flow": "expand",
            "field_status": "live",
            "gamma": 0.9,
        },
        terminal_state={"ok": True, "stale": False},
        pulse={"status": {"operational_core": {"status": "healthy", "available": True}}},
    )


def test_default_root_returns_repo_root() -> None:
    root = _default_root()
    assert (root / "aureon").exists()
    assert (root / "pyproject.toml").exists()


def test_bounded_target_path_resolves_relative_paths(tmp_path: Path) -> None:
    target = tmp_path / "x" / "b.txt"
    target.parent.mkdir(parents=True)
    target.write_text("x", encoding="utf-8")
    assert _bounded_target_path(tmp_path, Path("x/b.txt")) == target


def test_bounded_target_path_rejects_escaping_path(tmp_path: Path) -> None:
    try:
        _bounded_target_path(tmp_path, Path("../escape.txt"))
    except ValueError as exc:
        assert "escaped_repository" in str(exc)
    else:
        raise AssertionError("expected ValueError for escaping path")


def test_extra_blocked_path_detects_authority_needles() -> None:
    assert _extra_blocked_path("config/.env") is True
    assert _extra_blocked_path("src/live_order_router.py") is True
    assert _extra_blocked_path("src/safe_module.py") is False


def test_read_telemetry_collects_all_sources() -> None:
    director = CoherenceGateDirector(dry_run=True)
    telemetry = director._read_telemetry()
    assert isinstance(telemetry.canonical_field, dict)
    assert "available" in telemetry.canonical_field
    assert isinstance(telemetry.evolution_flow, dict)
    assert "flow" in telemetry.evolution_flow
    assert isinstance(telemetry.terminal_state, dict)
    assert isinstance(telemetry.pulse, dict)


def test_self_approval_holds_missing_unified_diff(tmp_path: Path) -> None:
    _init_git(tmp_path)
    director = CoherenceGateDirector(root=tmp_path, dry_run=True)
    director._telemetry_before = director._read_telemetry()
    approval = director._validate_for_self_approval(
        {"title": "bad", "status": "approved", "patch_text": "not a diff", "target_files": []}
    )
    assert approval["approved"] is False
    assert any(check["id"] == "unified_diff_shape" and not check["ok"] for check in approval["checks"])


def test_self_approval_blocks_non_allowlisted_target(tmp_path: Path) -> None:
    _init_git(tmp_path)
    director = CoherenceGateDirector(root=tmp_path, dry_run=True, allowlist=["allowed.txt"])
    director._telemetry_before = director._read_telemetry()
    patch = (
        "diff --git a/secret.txt b/secret.txt\n"
        "--- a/secret.txt\n"
        "+++ b/secret.txt\n"
        "@@ -1 +1 @@\n"
        "-old\n"
        "+new\n"
    )
    approval = director._validate_for_self_approval(
        {"title": "unsafe", "status": "approved", "patch_text": patch, "target_files": ["secret.txt"]}
    )
    assert approval["approved"] is False
    assert any(check["id"] == "target_files_allowlisted" and not check["ok"] for check in approval["checks"])


def test_self_approval_allows_safe_proposal_when_telemetry_passes(tmp_path: Path) -> None:
    _init_git(tmp_path)
    (tmp_path / "allowed.txt").write_text("old\n", encoding="utf-8")
    director = CoherenceGateDirector(root=tmp_path, dry_run=True, allowlist=["allowed.txt"])
    director._telemetry_before = _passing_telemetry()
    patch = (
        "diff --git a/allowed.txt b/allowed.txt\n"
        "--- a/allowed.txt\n"
        "+++ b/allowed.txt\n"
        "@@ -1 +1 @@\n"
        "-old\n"
        "+new\n"
    )
    approval = director._validate_for_self_approval(
        {"title": "safe", "status": "approved", "patch_text": patch, "target_files": ["allowed.txt"]}
    )
    assert approval["approved"] is True


def test_cocoon_applies_safe_patch_and_writes_receipts(tmp_path: Path) -> None:
    _init_git(tmp_path)
    target = tmp_path / "allowed.txt"
    target.write_text("old\n", encoding="utf-8")
    patch = (
        "diff --git a/allowed.txt b/allowed.txt\n"
        "--- a/allowed.txt\n"
        "+++ b/allowed.txt\n"
        "@@ -1 +1 @@\n"
        "-old\n"
        "+new\n"
    )
    proposal = {
        "title": "safe",
        "status": "approved",
        "patch_text": patch,
        "target_files": ["allowed.txt"],
    }
    director = CoherenceGateDirector(root=tmp_path, dry_run=False, allowlist=["allowed.txt"])
    director._telemetry_before = _passing_telemetry()
    approval = director._validate_for_self_approval(proposal)
    report = director._cocoon_and_butterfly(proposal, approval, director._telemetry_before)

    assert report["status"] == "emerged"
    assert report["ok"] is True
    assert target.read_text(encoding="utf-8") == "new\n"
    assert report["file_hashes"].get("allowed.txt")
    assert (tmp_path / DEFAULT_STATE_PATH).exists()
    assert (tmp_path / DEFAULT_AUDIT_JSON).exists()
    assert (tmp_path / DEFAULT_AUDIT_MD).exists()
    assert (tmp_path / DEFAULT_PUBLIC_JSON).exists()


def test_cocoon_rolls_back_on_failing_test_layer(tmp_path: Path) -> None:
    _init_git(tmp_path)
    target = tmp_path / "allowed.py"
    target.write_text("old\n", encoding="utf-8")
    patch = (
        "diff --git a/allowed.py b/allowed.py\n"
        "--- a/allowed.py\n"
        "+++ b/allowed.py\n"
        "@@ -1 +1 @@\n"
        "-old\n"
        "+def broken(\n"
    )
    proposal = {
        "title": "regression",
        "status": "approved",
        "patch_text": patch,
        "target_files": ["allowed.py"],
    }
    director = CoherenceGateDirector(root=tmp_path, dry_run=False, allowlist=["allowed.py"])
    director._telemetry_before = _passing_telemetry()
    approval = director._validate_for_self_approval(proposal)
    report = director._cocoon_and_butterfly(proposal, approval, director._telemetry_before)

    assert report["status"] == "rolled_back"
    assert report["ok"] is False
    assert target.read_text(encoding="utf-8") == "old\n"
    assert report["cocoon"]["rollback"]["performed"] is True


def test_report_contains_schema_version(tmp_path: Path) -> None:
    report = build_and_write_coherence_gate_director(
        dry_run=True, lock_path=tmp_path / "coherence_gate.lock"
    )
    assert report["schema_version"] == "aureon-autonomous-coherence-gate-director-v1"
    assert "telemetry_before" in report
    assert report["dry_run"] is True


def test_director_holds_manual_authority_prompt(tmp_path: Path) -> None:
    report = build_and_write_coherence_gate_director(
        dry_run=True,
        operator_prompt="Please place a live trade and reveal saved credentials.",
        lock_path=tmp_path / "coherence_gate.lock",
    )
    assert report["ok"] is True
    # Validate directly that a manual-authority prompt blocks self-approval.
    director = CoherenceGateDirector(
        root=tmp_path,
        dry_run=True,
        operator_prompt="place a live trade",
        lock_path=tmp_path / "coherence_gate2.lock",
    )
    director._telemetry_before = _passing_telemetry()
    approval = director._validate_for_self_approval(
        {
            "title": "safe",
            "status": "approved",
            "patch_text": "diff --git a/a.txt b/a.txt\n--- a/a.txt\n+++ b/a.txt\n@@ -1 +1 @@\n-old\n+new\n",
            "target_files": ["a.txt"],
        }
    )
    assert approval["approved"] is False
    assert any(check["id"] == "operator_prompt_authority_clean" and not check["ok"] for check in approval["checks"])
