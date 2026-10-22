"""Review log and kill switch for Aureon's own writer.

The writer is allowed to change the code the system was built to run: trading
logic, evidence gates, and configuration that reads credentials from the
environment. AUREON_SELF_REPAIR_KILL=1 is the operator stop. It is off unless
set. The log records the path and the event, not secret values.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

KILL_ENV = "AUREON_SELF_REPAIR_KILL"
LOG_RELATIVE = Path("state/self_repair_review_log.jsonl")


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
    record = {"ts": _utc(), "event": event}
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


def inspect_write(repo_root: Path, file_path: str, new_content: str, previous: str | None) -> Path:
    """Allow the write unless the operator kill switch is on or the path escapes the repo."""

    del new_content, previous
    if kill_switch_engaged():
        raise SelfRepairBlocked("kill_switch")
    return contained(repo_root, file_path)


def inspect_execution(code: str) -> None:
    del code
    if kill_switch_engaged():
        raise SelfRepairBlocked("kill_switch")
