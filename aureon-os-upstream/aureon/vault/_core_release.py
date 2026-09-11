"""
_core_release — fail-closed release-record gate for the core vault modules
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

The core vault modules (aureon_vault, casimir_quantifier, harmonic_pinger,
self_feedback_loop) shipped hard-HOLD: their effect methods raised before
touching the bus, the conscience, or the engine. The owner decree of
2026-09-06 (Gary Leckey) released them. This module is the shared
release-state authority, in parallel with
``aureon.vault.voice._goal_release`` (which owns the voice modules only).

Release state lives in a release record:
``aureon_fusion/state/vault/core_release.json`` (workspace root, next to
the upstream repo), in the same spirit as
``aureon_fusion/state/goals/dispatch_release.json``. The record must be a
JSON object carrying a non-empty ``ts``, a ``source`` string, and a
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

  1. ``AUREON_CORE_RELEASE_RECORD`` env var (tests / overrides)
  2. ``<workspace>/aureon_fusion/state/vault/core_release.json``
     where ``<workspace>`` is the upstream repo's parent directory
  3. ``<repo>/aureon_fusion/state/vault/core_release.json``
     (vendored-fusion fallback)

Also provides ``conscience_permits`` — the advisory-additive fusion
conscience second opinion used on released effect paths, per the
goal_dispatch_bridge precedent: a VETO can only tighten (the caller must
abort); an unavailable or erroring hook is logged and skipped, never
silently opening anything.

Gary Leckey · Aureon Institute — September 2026
"""

from __future__ import annotations

import json
import logging
import os
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("aureon.vault.core_release")

_ENV_VAR = "AUREON_CORE_RELEASE_RECORD"
_RECORD_NAME = Path("aureon_fusion") / "state" / "vault" / "core_release.json"

# Modules released under the owner decree of 2026-09-06. Voice-vault
# modules are owned by a separate authority (_goal_release) and are
# deliberately not listed here.
CORE_VAULT_MODULES = (
    "aureon_vault",
    "casimir_quantifier",
    "harmonic_pinger",
    "self_feedback_loop",
)

_read_lock = threading.Lock()


def release_record_candidates() -> List[Path]:
    """Candidate record paths, most specific first. When the
    ``AUREON_CORE_RELEASE_RECORD`` env var is set it is authoritative —
    only that path is consulted (tests and operators use it to force HOLD
    or point at an alternate record). Never raises."""
    env = os.environ.get(_ENV_VAR)
    if env:
        return [Path(env)]
    candidates: List[Path] = []
    try:
        repo_root = Path(__file__).resolve().parents[2]
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
    """Introspection helper: where the gate stands."""
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


def conscience_permits(
    action: str,
    context: Optional[Dict[str, Any]] = None,
) -> bool:
    """Advisory-additive fusion conscience second opinion.

    Routes the action through ``aureon_fusion.conscience_hook.evaluate``
    when that package is importable (the organism runtime puts the
    workspace root on sys.path). By design this layer can only tighten:
    a VETO returns False and the caller must refuse the effect; an
    unavailable or erroring hook is logged and skipped (the enforceable
    fail-closed gate is the release record, already applied). Never
    raises.
    """
    try:
        from aureon_fusion.conscience_hook import evaluate  # type: ignore
    except Exception as e:
        logger.debug("core release: fusion conscience hook not importable "
                     "(%s); primary release gate already applied", e)
        return True
    try:
        verdict = evaluate(action, dict(context or {}))
    except Exception as e:
        logger.debug("core release: fusion conscience hook evaluation "
                     "failed (%s); primary release gate already applied", e)
        return True
    v = str((verdict or {}).get("verdict", "")).upper()
    if v == "VETO":
        logger.warning(
            "core release: conscience VETO for '%s': %s",
            action, (verdict or {}).get("reasoning", ""),
        )
        return False
    return True


__all__ = [
    "CORE_VAULT_MODULES",
    "release_record_candidates",
    "read_release_record",
    "is_released",
    "release_status",
    "conscience_permits",
]
