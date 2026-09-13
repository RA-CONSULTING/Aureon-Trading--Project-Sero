"""Pinned production Edge Function attack-surface contract."""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUDITOR = ROOT / "scripts" / "validation" / "audit_supabase_production_edge_surface.py"


def _load_auditor():
    spec = importlib.util.spec_from_file_location(
        "audit_supabase_production_edge_surface", AUDITOR
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_every_active_production_edge_function_has_a_closed_disposition() -> None:
    auditor = _load_auditor()
    result = auditor.audit(ROOT)

    assert result == {
        "schema": "aureon.supabase.production_edge_attack_surface_audit.v1",
        "offline": True,
        "active_count": 100,
        "retired_checked": 95,
        "retained_checked": 5,
        "inactive_retirements_checked": 5,
        "errors": [],
        "ok": True,
    }


def test_routed_frontend_cannot_reach_any_supabase_edge_function() -> None:
    routed_contract_path = ROOT / "tests" / "test_frontend_routed_surface_contract.py"
    spec = importlib.util.spec_from_file_location(
        "test_frontend_routed_surface_contract", routed_contract_path
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    findings = []
    for path, source in module._reachable_sources().items():
        if "supabase.functions.invoke" in source or "/functions/v1/" in source:
            findings.append(path.relative_to(ROOT).as_posix())
    assert findings == []
