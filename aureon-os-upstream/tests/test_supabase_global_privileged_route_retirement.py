"""Regression contract for retired global Supabase service-role routes.

Gateway JWT verification only proves that a caller has a Supabase token. It
does not authorize that caller to bypass RLS for shared telemetry. These routes
remain inert until an operator-only publisher or a subject-bound tenant schema
replaces them.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROUTES = (
    "analyze-solar-correlations",
    "analyze-space-weather-correlation",
    "analyze-stargate-patterns",
    "emergency-stop",
    "fetch-binance-margin-data",
    "forecast-coherence",
    "gas-tank-deduct-fee",
    "get-binance-balances",
    "ingest-10-9-1-packet",
    "ingest-6d-harmonic",
    "ingest-adaptive-learning",
    "ingest-decision-fusion",
    "ingest-eckoushic-cascade",
    "ingest-exchange-learning",
    "ingest-ftcp-detector",
    "ingest-integral-aqal",
    "ingest-master-equation",
    "ingest-omega-equation",
    "ingest-planetary-modulation",
    "ingest-prism-state",
    "ingest-probability-matrix",
    "ingest-rainbow-bridge",
    "ingest-risk-manager",
    "ingest-smart-router",
    "ingest-stargate-network",
    "ingest-telescope-state",
    "ingest-temporal-anchor",
    "ingest-terminal-state",
    "ingest-ticker-snapshot",
    "ingest-trades",
    "ingest-unity-event",
    "primelines-protocol-gateway",
    "sync-exchange-assets",
    "test-exchange-connection",
    "unified-field-analysis",
    "update-bot-credentials",
)

FORBIDDEN_PRIVILEGE_MARKERS = (
    "SUPABASE_SERVICE_ROLE_KEY",
    "createClient",
    "req.json(",
    ".from(",
    ".insert(",
    ".upsert(",
    ".update(",
    ".delete(",
    "fetch(",
    "Deno.env.get",
)

CALLER_ROOTS = (
    ROOT / "frontend" / "src",
    ROOT / "aureon",
    ROOT / "scripts",
    ROOT / "supabase" / "functions",
)
CALLER_SUFFIXES = {".ts", ".tsx", ".js", ".jsx", ".py", ".sh", ".ps1"}


def test_global_privileged_routes_are_self_contained_fail_closed_stubs() -> None:
    for route in ROUTES:
        source = (
            ROOT / "supabase" / "functions" / route / "index.ts"
        ).read_text(encoding="utf-8")

        assert "LEGACY_GLOBAL_PRIVILEGED_ROUTE_DISABLED" in source
        assert f"route: '{route}'" in source
        assert "status: 503" in source
        assert "mutationAuthority: false" in source
        assert "providerCallsAttempted: 0" in source
        assert "generatedValues: false" in source
        assert "'Cache-Control': 'no-store'" in source
        assert "../_shared/" not in source
        for marker in FORBIDDEN_PRIVILEGE_MARKERS:
            assert marker not in source, f"{route} regained privileged marker {marker}"


def test_retired_routes_keep_gateway_jwt_verification_enabled() -> None:
    config = (ROOT / "supabase" / "config.toml").read_text(encoding="utf-8")
    for route in ROUTES:
        section = re.search(
            rf"(?ms)^\[functions\.{re.escape(route)}\]\s*$(.*?)(?=^\[|\Z)",
            config,
        )
        assert section is not None, f"missing config section for {route}"
        assert re.search(r"(?m)^verify_jwt\s*=\s*true\s*$", section.group(1))


def test_runtime_code_does_not_call_retired_routes() -> None:
    invocation_patterns = {
        route: (
            re.compile(
                rf"functions\.invoke\s*\(\s*['\"]{re.escape(route)}['\"]"
            ),
            re.compile(rf"/functions/v1/{re.escape(route)}(?:['\"/?]|$)"),
        )
        for route in ROUTES
    }

    violations: list[str] = []
    for caller_root in CALLER_ROOTS:
        for path in caller_root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in CALLER_SUFFIXES:
                continue
            if (
                path.name == "index.ts"
                and path.parent.name in ROUTES
                and path.parent.parent.name == "functions"
            ):
                continue
            source = path.read_text(encoding="utf-8", errors="ignore")
            for route, patterns in invocation_patterns.items():
                if any(pattern.search(source) for pattern in patterns):
                    violations.append(f"{path.relative_to(ROOT)} -> {route}")

    assert violations == []
