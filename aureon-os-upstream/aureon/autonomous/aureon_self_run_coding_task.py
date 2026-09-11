"""Compact, fail-closed adapter from the self-run loop to Aureon's self-coder.

The adapter does not author code and does not grant review or release authority.
It invokes at most one already-guarded internal coding experiment.  Current
transient-seal evidence always returns HOLD, and any existing evidence blocks a
second brain cycle until it is manually archived.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from aureon.autonomous.aureon_internal_coding_workforce import WorkforceHold
from aureon.autonomous.aureon_internal_patch_loop import InternalPatchHold
from aureon.autonomous.aureon_internal_self_coder import (
    DEFAULT_EVIDENCE_PATH,
    InternalSelfCoderHold,
    read_self_coding_evidence,
    run_autonomous_self_coding,
)
from aureon.autonomous.aureon_internal_work_ledger import WorkLedgerError

SelfCoder = Callable[..., Mapping[str, Any]]
_HEX_64 = re.compile(r"[0-9a-f]{64}")
COMPACT_SELF_CODER_SUMMARY_FIELDS = frozenset(
    {
        "reason_code",
        "applied",
        "pending_senior_review",
        "release_ready",
        "codex_implementation",
        "action_eligible",
        "economic_eligible",
    }
)
_FALSE_EFFECT_FIELDS = frozenset(
    {
        "action_eligible",
        "applied",
        "codex_implementation",
        "economic_eligible",
        "effect_attempted",
        "execution_authorized",
        "filesystem_mutation_attempted",
        "final_applier_invoked",
        "generated_code_execution_authorized",
        "generated_code_execution_implemented",
        "production_magic_star_release_available",
        "production_ready",
        "release_authorized",
        "repository_mutation_authorized",
        "repository_mutation_implemented",
        "subprocess_test_execution_implemented",
        "test_commands_executed",
    }
)


def _evidence_digest(value: Mapping[str, Any]) -> str:
    try:
        encoded = json.dumps(
            dict(value),
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    except (TypeError, ValueError):
        return ""
    return hashlib.sha256(encoded).hexdigest()


def _effect_flags_are_false(value: Any, *, allow_local_apply: bool = False) -> bool:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if key in _FALSE_EFFECT_FIELDS and item is not False:
                # In bounded autonomous apply mode, local-only effect fields may be True
                # as long as no production/economic/release authority is granted.
                if allow_local_apply and key in {
                    "applied",
                    "effect_attempted",
                    "repository_mutation_implemented",
                    "subprocess_test_execution_implemented",
                    "test_commands_executed",
                }:
                    continue
                return False
            if not _effect_flags_are_false(item, allow_local_apply=allow_local_apply):
                return False
        return True
    if isinstance(value, (list, tuple)):
        return all(_effect_flags_are_false(item, allow_local_apply=allow_local_apply) for item in value)
    return True


def _is_local_only_autonomous_apply(result: Mapping[str, Any]) -> bool:
    """True when the receipt describes a bounded local-only patch apply."""
    protection = (result.get("patch_cycle") or {}).get("proposal_protection") or {}
    if not isinstance(protection, Mapping):
        return False
    return (
        protection.get("local_development_only") is True
        and protection.get("production_ready") is not True
        and result.get("release_authorized") is not True
        and result.get("economic_eligible") is not True
        and result.get("action_eligible") is not True
    )


def _held_result(reason_code: str, *, status: str = "internal_self_coder_held") -> dict[str, Any]:
    summary: dict[str, Any] = {
        "reason_code": reason_code,
        "applied": False,
        "pending_senior_review": False,
        "release_ready": False,
        "codex_implementation": False,
        "action_eligible": False,
        "economic_eligible": False,
    }
    assert set(summary) == COMPACT_SELF_CODER_SUMMARY_FIELDS
    return {
        "status": status,
        "ok": False,
        "summary": summary,
        "output_files": [],
    }


def _evidence_has_completed_transient_seal(result: Mapping[str, Any]) -> bool:
    """True when the self-coder produced a valid transient HNC seal.

    Accepts both the historical seal-held handoff state (patch not yet applied)
    and the bounded autonomous-apply completion state (patch applied locally).
    """

    if not isinstance(result, Mapping):
        return False
    status = result.get("status")
    if status not in (
        "internal_patch_transient_hnc_seal_held",
        "internal_self_coder_seal_complete",
    ):
        return False
    if result.get("transient_hnc_seal_verified") is not True:
        return False
    patch_cycle = result.get("patch_cycle") or {}
    patch_status = patch_cycle.get("status")
    if patch_status not in (
        "internal_patch_transient_hnc_seal_held",
        "internal_self_coder_seal_complete",
        "applied",
    ):
        return False
    proposal = patch_cycle.get("proposal") or {}
    if proposal.get("status") != "approved":
        return False
    return True


def _compact_result(result: Mapping[str, Any]) -> dict[str, Any]:
    """Return a success envelope for a valid transient seal, else a generic HOLD.

    A successful seal means Aureon's workforce authored a diff, the pre-apply
    council accepted it, and SafeCodeControl recorded it.  The patch is still
    not applied by the self-coder; the autonomous coherence-gate director owns
    the apply step.  No authority or economic eligibility is granted here.
    """

    if not isinstance(result, Mapping):
        return _held_result("internal_self_coder_receipt_invalid")
    digest = result.get("evidence_digest")
    digest_core = {key: value for key, value in result.items() if key != "evidence_digest"}
    allow_local_apply = _is_local_only_autonomous_apply(result)
    if (
        not isinstance(digest, str)
        or _HEX_64.fullmatch(digest) is None
        or digest != _evidence_digest(digest_core)
        or not _effect_flags_are_false(result, allow_local_apply=allow_local_apply)
    ):
        return _held_result("internal_self_coder_receipt_invalid")
    if _evidence_has_completed_transient_seal(result):
        return {
            "status": "internal_self_coder_seal_complete",
            "ok": True,
            "summary": {
                "reason_code": "internal_self_coder_seal_complete",
                "applied": bool(result.get("applied")),
                "pending_senior_review": False,
                "release_ready": False,
                "codex_implementation": False,
                "action_eligible": False,
                "economic_eligible": False,
            },
            "output_files": [str(DEFAULT_EVIDENCE_PATH)],
        }
    return _held_result(
        "internal_self_coder_receipt_unattested",
        status="internal_self_coder_evidence_hold",
    )


def run_self_coding_task(
    root: Path,
    goal: str,
    *,
    enabled: bool = False,
    target_path: str = "",
    test_commands: Sequence[Sequence[str]] = (),
    resolver: Any = None,
    coder: SelfCoder = run_autonomous_self_coding,
) -> dict[str, Any]:
    """Run one Aureon-owned seal experiment; evidence blocks another cycle."""

    if enabled is not True:
        return _held_result(
            "internal_self_coder_not_enabled",
            status="internal_self_coder_disabled",
        )
    repo_root = Path(root).resolve()
    evidence_file = repo_root / DEFAULT_EVIDENCE_PATH
    if evidence_file.exists():
        try:
            prior = read_self_coding_evidence(root=repo_root)
        except InternalSelfCoderHold:
            return _held_result("existing_self_coder_evidence_invalid")
        compact = _compact_result(prior)
        if compact["status"] == "internal_self_coder_evidence_hold":
            compact["status"] = "internal_self_coder_existing_evidence_hold"
        return compact

    try:
        result = coder(
            root=repo_root,
            goal=str(goal or "").strip(),
            target_path=str(target_path or ""),
            test_commands=test_commands,
            resolver=resolver,
        )
    except InternalPatchHold:
        return _held_result("internal_patch_hold")
    except InternalSelfCoderHold:
        return _held_result("internal_self_coder_hold")
    except WorkLedgerError:
        return _held_result("internal_work_ledger_hold")
    except WorkforceHold:
        return _held_result("internal_coding_workforce_hold")
    except Exception:
        return _held_result(
            "unexpected_internal_self_coder_error",
            status="internal_self_coder_error",
        )
    if not isinstance(result, Mapping):
        return _held_result("internal_self_coder_receipt_invalid")
    return _compact_result(result)


def self_coding_patch_lane_blocked(root: Path) -> bool:
    """Fail closed when pending or invalid evidence forbids another code mutation.

    A completed transient seal is not a blocker: it is the hand-off signal for
    the autonomous coherence-gate director to apply the approved proposal.
    """

    repo_root = Path(root).resolve()
    evidence_file = repo_root / DEFAULT_EVIDENCE_PATH
    if not evidence_file.exists():
        return False
    try:
        evidence = read_self_coding_evidence(root=repo_root)
    except InternalSelfCoderHold:
        return True
    return not _evidence_has_completed_transient_seal(evidence)


__all__ = [
    "COMPACT_SELF_CODER_SUMMARY_FIELDS",
    "run_self_coding_task",
    "self_coding_patch_lane_blocked",
]
