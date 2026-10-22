"""Guardrails for Aureon's self-coding and self-repair writes.

The Queen writer and the sandbox repair both call this before a file changes.
A kill switch stops every write. The guard refuses secret paths, live-trading
arming, and evidence-gate loosening. It appends a review line and does not
record secret values.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

KILL_ENV = "AUREON_SELF_REPAIR_KILL"
LOG_RELATIVE = Path("state/self_repair_review_log.jsonl")

_LIVE_ARM = re.compile(
    r"(AUREON_LIVE_TRADING\s*=\s*['\"]?1\b"
    r"|AUREON_FUSION_ARM_LIVE\s*=\s*['\"]?1\b"
    r"|CONFIRM_LIVE_TRADING\s*=\s*['\"]?yes\b"
    r"|BINANCE_TESTNET\s*=\s*['\"]?false\b"
    r"|PAPER_MODE\s*=\s*['\"]?false\b"
    r"|AUREON_DISABLE_REAL_ORDERS\s*=\s*['\"]?0\b"
    r"|testnet\s*:\s*false\b)",
    re.IGNORECASE,
)
_GATE_OPEN = re.compile(
    r"(\bmay_act\b|\baction_eligible\b|\beconomic_mutation\b)\s*[:=]\s*True\b"
    r"|(['\"]may_act['\"]|['\"]action_eligible['\"]|['\"]economic_mutation['\"])\s*:\s*True\b"
    r"|(['\"]gate['\"]|\bgate\b)\s*[:=]\s*['\"]RELEASE['\"]",
)
_EVIDENCE_MARKER = "sample_or_synthetic_evidence_excluded"


class SelfRepairBlocked(RuntimeError):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def kill_switch_engaged() -> bool:
    return os.environ.get(KILL_ENV, "").strip().lower() in {"1", "true", "yes", "on"}


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def review_log_path(repo_root: Path) -> Path:
    return repo_root / LOG_RELATIVE


def append_review(repo_root: Path, event: str, **fields: object) -> None:
    path = review_log_path(repo_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {"ts": _utc(), "event": event, "live_trading": False, "may_act": False}
    for key, value in fields.items():
        if str(key).lower() in {"secret", "token", "authorization", "api_key", "api_secret", "content"}:
            continue
        record[key] = value
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True, default=str) + "\n")


def contained(repo_root: Path, file_path: str) -> Path:
    root = repo_root.resolve()
    candidate = Path(file_path)
    if not candidate.is_absolute():
        candidate = root / candidate
    resolved = candidate.resolve()
    if resolved != root and root not in resolved.parents:
        raise SelfRepairBlocked("path_outside_repository")
    return resolved


def _secret_name(path: Path) -> bool:
    name = path.name.lower()
    if name == ".env" or (name.startswith(".env.") and "example" not in name and "template" not in name):
        return True
    return any(token in name for token in ("secret", "credential", "id_rsa", "wallet", ".pem", "private_key"))


def inspect_write(repo_root: Path, file_path: str, new_content: str, previous: str | None) -> Path:
    """Raise SelfRepairBlocked when a write is not allowed. Return the resolved path."""

    if kill_switch_engaged():
        raise SelfRepairBlocked("kill_switch")
    resolved = contained(repo_root, file_path)
    if _secret_name(resolved):
        raise SelfRepairBlocked("secret_path")
    if _LIVE_ARM.search(new_content):
        raise SelfRepairBlocked("live_trading_arm")
    if _GATE_OPEN.search(new_content):
        raise SelfRepairBlocked("evidence_gate_loosened")
    if previous and _EVIDENCE_MARKER in previous and _EVIDENCE_MARKER not in new_content:
        raise SelfRepairBlocked("evidence_gate_loosened")
    return resolved


def inspect_execution(code: str) -> None:
    if kill_switch_engaged():
        raise SelfRepairBlocked("kill_switch")
    if _LIVE_ARM.search(code) or _GATE_OPEN.search(code):
        raise SelfRepairBlocked("execution_would_loosen_safety")
    if re.search(r"(\.env\b|id_rsa|private_key|api_secret|credentials\.json)", code, re.IGNORECASE):
        raise SelfRepairBlocked("execution_touches_secrets")
