"""
_goal_release — fail-closed release-record gate for the goal modules
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Both goal modules (goal_dispatch_bridge, goal_skill_aligner) shipped
hard-HOLD: every effect method raised before touching the bus, the
conscience, or the engine. The owner decree of 2026-09-06 (Gary Leckey)
released them. This module is the shared release-state authority.

Release state lives in a release record:
``aureon_fusion/state/goals/dispatch_release.json`` (workspace root, next
to the upstream repo), in the same spirit as
``aureon_fusion/state/capital_release.flag``. The record must be a JSON
object carrying a non-empty ``ts``, a ``source`` string, and a
``modules`` list naming the module being released.

FAIL-CLOSED, always:

  * record absent           → HOLD
  * record unreadable       → HOLD
  * record not valid JSON   → HOLD
  * record missing ts/source/modules, or the module not listed → HOLD
  * any exception anywhere  → HOLD

The record is re-read on every check (no caching): deleting the record
re-holds the modules instantly, which is what makes the fail-closed
property testable and enforceable.

Import-safe: nothing runs at import time; all work happens inside
functions. Resolution order for the record path:

  1. ``GOAL_DISPATCH_RELEASE_RECORD`` env var (tests / overrides)
  2. ``<workspace>/aureon_fusion/state/goals/dispatch_release.json``
     where ``<workspace>`` is the upstream repo's parent directory
  3. ``<repo>/aureon_fusion/state/goals/dispatch_release.json``
     (vendored-fusion fallback)

Gary Leckey · Aureon Institute — September 2026
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

_ENV_VAR = "GOAL_DISPATCH_RELEASE_RECORD"
_RECORD_NAME = Path("aureon_fusion") / "state" / "goals" / "dispatch_release.json"

_read_lock = threading.Lock()


def release_record_candidates() -> List[Path]:
    """Candidate record paths, most specific first. When the
    ``GOAL_DISPATCH_RELEASE_RECORD`` env var is set it is authoritative —
    only that path is consulted (tests and operators use it to force HOLD
    or point at an alternate record). Never raises."""
    env = os.environ.get(_ENV_VAR)
    if env:
        return [Path(env)]
    candidates: List[Path] = []
    try:
        repo_root = Path(__file__).resolve().parents[3]
        candidates.append(repo_root.parent / _RECORD_NAME)
        candidates.append(repo_root / _RECORD_NAME)
    except Exception:
        pass
    return candidates


def _validate(record: Any, module_name: str) -> bool:
    if not isinstance(record, dict):
        return False
    ts = record.get("ts")
    if not ts:
        return False
    if not isinstance(record.get("source"), str) or not record["source"]:
        return False
    modules = record.get("modules")
    if not isinstance(modules, list):
        return False
    return module_name in modules


def read_release_record() -> Optional[Dict[str, Any]]:
    """Return the parsed, schema-valid release record from the first
    candidate path that yields one; None when every candidate is absent
    or invalid (fail-closed)."""
    with _read_lock:
        for path in release_record_candidates():
            try:
                if not path.is_file():
                    continue
                with open(path, "r", encoding="utf-8") as f:
                    record = json.load(f)
            except Exception:
                continue
            if isinstance(record, dict) and record.get("ts"):
                return record
    return None


def is_released(module_name: str) -> bool:
    """True only when a valid release record names ``module_name``."""
    record = read_release_record()
    if record is None:
        return False
    try:
        return _validate(record, module_name)
    except Exception:
        return False


def release_status(module_name: str) -> Dict[str, Any]:
    """Introspection helper for stats(): where the gate stands."""
    record = read_release_record()
    released = False
    try:
        released = _validate(record, module_name) if record else False
    except Exception:
        released = False
    return {
        "released": released,
        "record": record if released else None,
    }


__all__ = [
    "release_record_candidates",
    "read_release_record",
    "is_released",
    "release_status",
]
