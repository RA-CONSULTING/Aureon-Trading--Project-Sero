"""Static truth boundary for code mounted by the current frontend router."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND_SRC = ROOT / "frontend" / "src"
ROUTES = FRONTEND_SRC / "shell" / "routes.tsx"
IMPORT = re.compile(r"(?:\bfrom\s*|\bimport\s*\()\s*['\"]([^'\"]+)['\"]")
REPORT = re.compile(r"['\"](/aureon_[^'\"]+\.json)['\"]")
OPTIONAL_UNAVAILABLE_REPORTS = {
    "/aureon_autonomous_capability_switchboard.json",
    "/aureon_cognitive_trade_evidence.json",
    "/aureon_frontend_evolution_queue.json",
    "/aureon_harmonic_affect_state.json",
    "/aureon_hnc_cognitive_proof.json",
    "/aureon_live_cognition_benchmark.json",
    "/aureon_organism_runtime_status.json",
    "/aureon_wake_up_manifest.json",
}
ALLOWED_ROUTED_API_MUTATIONS = {
    ("del", "/api/providers/${p.id}"),
    ("post", "/api/approvals/${encodeURIComponent(id)}"),
    ("post", "/api/cognition/reason"),
    ("post", "/api/connections/${encodeURIComponent(c.id)}"),
    ("post", "/api/connections/${encodeURIComponent(c.id)}/test"),
    ("post", "/api/operator/authorization-lease"),
    ("post", "/api/operator/cloud-trading-control/apply"),
    ("post", "/api/providers/${p.id}"),
    ("post", "/api/providers/${p.id}/test"),
    ("post", "/api/switchboard/${encodeURIComponent(options.flag.id)}"),
    ("post", "/api/trading/backtest"),
}
RETIRED_LEGACY_FRONTEND_FILES = {
    "frontend/src/components/ConsciousnessCoherenceTracker.tsx",
    "frontend/src/components/ExchangeCredentialsManager.tsx",
    "frontend/src/components/LiveDataPuller.tsx",
    "frontend/src/components/RecentTrades.tsx",
    "frontend/src/components/StatusPanel.tsx",
    "frontend/src/core/automatedSimulationEngine.ts",
}


def _resolve_import(source: Path, specifier: str) -> Path | None:
    if specifier.startswith("@/"):
        base = FRONTEND_SRC / specifier[2:]
    elif specifier.startswith("."):
        base = source.parent / specifier
    else:
        return None
    candidates = [base]
    if not base.suffix:
        candidates.extend(base.with_suffix(ext) for ext in (".ts", ".tsx"))
        candidates.extend(base / f"index{ext}" for ext in (".ts", ".tsx"))
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    return None


def _reachable_sources() -> dict[Path, str]:
    pending = [ROUTES.resolve()]
    reached: dict[Path, str] = {}
    while pending:
        path = pending.pop()
        if path in reached:
            continue
        text = path.read_text(encoding="utf-8")
        reached[path] = text
        for specifier in IMPORT.findall(text):
            imported = _resolve_import(path, specifier)
            if imported is not None and imported not in reached:
                pending.append(imported)
    return reached


def test_routed_surface_has_no_supabase_edge_or_direct_database_mutation() -> None:
    findings: list[str] = []
    direct_write = re.compile(
        r"\bsupabase\s*\.\s*from\s*\([^;]{0,800}?\)\s*\.\s*"
        r"(?:insert|update|upsert|delete)\s*\(",
        re.DOTALL,
    )
    for path, text in _reachable_sources().items():
        relative = path.relative_to(ROOT).as_posix()
        if re.search(r"\bsupabase\s*\.\s*functions\s*\.\s*invoke\s*\(", text):
            findings.append(f"{relative}: Supabase Edge Function invocation")
        if direct_write.search(text):
            findings.append(f"{relative}: direct Supabase database mutation")
    assert findings == []


def test_routed_api_mutations_stay_on_the_reviewed_same_origin_allowlist() -> None:
    api_mutation = re.compile(
        r"\bapi\.(post|put|patch|del)\s*(?:<[\s\S]{0,800}?>)?\s*"
        r"\(\s*(['\"`])(/api/[\s\S]*?)\2"
    )
    found = {
        (match.group(1), match.group(3))
        for text in _reachable_sources().values()
        for match in api_mutation.finditer(text)
    }
    assert found - ALLOWED_ROUTED_API_MUTATIONS == set()

    raw_fetch_mutation = re.compile(
        r"\bfetch\s*\([^;]{0,1000}?method\s*:\s*['\"]"
        r"(?:POST|PUT|PATCH|DELETE)['\"]",
        re.DOTALL | re.IGNORECASE,
    )
    assert {
        path.relative_to(ROOT).as_posix()
        for path, text in _reachable_sources().items()
        if raw_fetch_mutation.search(text)
    } == set()


def test_routed_surface_has_no_browser_random_generation_or_retired_legacy_panels() -> None:
    reached = _reachable_sources()
    assert {
        path.relative_to(ROOT).as_posix()
        for path, text in reached.items()
        if "Math.random(" in text
    } == set()
    relative_paths = {path.relative_to(ROOT).as_posix() for path in reached}
    assert relative_paths & RETIRED_LEGACY_FRONTEND_FILES == set()


def test_routed_reports_do_not_link_to_new_missing_artifacts() -> None:
    public = ROOT / "frontend" / "public"
    referenced = {
        report
        for text in _reachable_sources().values()
        for report in REPORT.findall(text)
    }
    missing = {report for report in referenced if not (public / report.lstrip("/")).is_file()}
    assert missing - OPTIONAL_UNAVAILABLE_REPORTS == set()


def test_retired_or_uncommissioned_routes_are_not_mounted() -> None:
    nav = (FRONTEND_SRC / "shell" / "nav.ts").read_text(encoding="utf-8")
    retired = {
        "/platform/console",
        "/cognition/agents",
        "/coding/skills",
        "/coding/work-orders",
        "/coding/director",
        "/ops/gold-capital",
    }
    assert {route for route in retired if f'path: "{route}"' in nav} == set()
