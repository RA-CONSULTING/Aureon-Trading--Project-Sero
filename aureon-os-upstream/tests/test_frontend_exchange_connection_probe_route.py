"""Static browser contract for read-only exchange credential authentication."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend" / "src"
MANAGER = FRONTEND / "components" / "ExchangeCredentialsManager.tsx"
CONNECTIONS_PAGE = FRONTEND / "shell" / "pages" / "ConnectionsPage.tsx"


def test_browser_exchange_credential_tests_use_the_same_origin_operator_route() -> None:
    source = MANAGER.read_text(encoding="utf-8")

    browser_sources = (
        path
        for path in FRONTEND.rglob("*")
        if path.suffix in {".ts", ".tsx"}
    )
    assert [
        path.relative_to(FRONTEND).as_posix()
        for path in browser_sources
        if b"test-exchange-connection" in path.read_bytes()
    ] == []
    assert "supabase.functions.invoke" not in source.split("const testConnection", 1)[1].split(
        "const handleSaveCredentials", 1
    )[0]
    assert "`/api/connections/${encodeURIComponent(exchange)}/test`" in source
    assert "{ api_key: apiKey, extra }" in source
    assert "provider_mutation_attempted === false" in source
    assert "data.authenticated === true" in source
    assert "data.probe_scope === 'credential'" in source
    assert "data.probe_scope === 'signed_cloud_executor_receipt'" in source


def test_exchange_test_request_uses_only_catalog_credential_field_names() -> None:
    source = MANAGER.read_text(encoding="utf-8")
    test_block = source.split("const testConnection", 1)[1].split(
        "const handleSaveCredentials", 1
    )[0]

    assigned_fields = set(re.findall(r"extra\.([A-Z][A-Z0-9_]*)\s*=", test_block))
    assert assigned_fields == {
        "ALPACA_SECRET_KEY",
        "BINANCE_API_SECRET",
        "CAPITAL_IDENTIFIER",
        "CAPITAL_PASSWORD",
        "KRAKEN_API_SECRET",
    }
    for unsafe_output in ("details", "http_status", "reason_code", "data.error"):
        assert unsafe_output not in test_block
    assert "console.error" not in test_block


def test_current_connections_page_requires_a_non_mutating_authentication_receipt() -> None:
    source = CONNECTIONS_PAGE.read_text(encoding="utf-8")

    assert "v.authenticated === true" in source
    assert "v.provider_mutation_attempted === false" in source
    assert "v.probe_scope === 'credential'" in source
    assert "v.probe_scope === 'signed_cloud_executor_receipt'" in source
    assert "No current read-only authentication receipt was returned." in source
