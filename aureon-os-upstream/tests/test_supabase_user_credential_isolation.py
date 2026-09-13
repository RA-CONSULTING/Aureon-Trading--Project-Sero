"""Static security contract for account-owned exchange credential storage."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "supabase" / "migrations"
FUNCTIONS = ROOT / "supabase" / "functions"
FRONTEND = ROOT / "frontend" / "src"
ROLLBACK = (
    MIGRATIONS
    / "rollback"
    / "20260913101606_harden_user_credential_ownership.down.sql"
)
CATALOG_RECEIPT = ROOT / "docs" / "audits" / "SUPABASE_PRECUTOVER_CATALOG_20260913.md"


def _migration() -> str:
    matches = list(MIGRATIONS.glob("*_harden_user_credential_ownership.sql"))
    assert len(matches) == 1
    return matches[0].read_text(encoding="utf-8")


def test_browser_cannot_write_or_select_encrypted_credential_columns() -> None:
    sql = _migration()

    assert (
        "REVOKE ALL PRIVILEGES ON TABLE public.user_binance_credentials\n"
        "  FROM PUBLIC, anon, authenticated;"
    ) in sql
    assert (
        "GRANT SELECT (id, user_id, created_at, updated_at, last_used_at)\n"
        "  ON TABLE public.user_binance_credentials TO authenticated;"
    ) in sql
    grant_block = sql.split(
        "GRANT SELECT (id, user_id, created_at, updated_at, last_used_at)", 1
    )[1].split(
        "GRANT ALL PRIVILEGES ON TABLE public.user_binance_credentials", 1
    )[0]
    assert "api_key_encrypted" not in grant_block
    assert "api_secret_encrypted" not in grant_block


def test_browser_has_only_safe_session_status_rpc() -> None:
    sql = _migration()

    assert (
        "REVOKE ALL PRIVILEGES ON TABLE public.aureon_user_sessions\n"
        "  FROM PUBLIC, anon, authenticated;"
    ) in sql
    assert "CREATE FUNCTION public.get_aureon_user_session_status()" in sql
    assert "SECURITY DEFINER\nSET search_path = ''" in sql
    assert "WHERE session.user_id = (SELECT auth.uid());" in sql
    assert (
        "GRANT EXECUTE ON FUNCTION public.get_aureon_user_session_status()\n"
        "  TO authenticated, service_role;"
    ) in sql
    assert "Users can insert own session" in sql and "DROP POLICY IF EXISTS" in sql
    assert "Users can update own session" in sql and "DROP POLICY IF EXISTS" in sql

    result_contract = sql.split("RETURNS TABLE (", 1)[1].split(")\nLANGUAGE sql", 1)[0]
    for forbidden in (
        "api_key_encrypted",
        "api_secret_encrypted",
        "password_encrypted",
        "is_trading_active",
        "trading_mode",
        "recent_trades",
        "payment_completed",
    ):
        assert forbidden not in result_contract
    for status in (
        "binance_credentials_configured",
        "kraken_credentials_configured",
        "alpaca_credentials_configured",
        "capital_credentials_configured",
    ):
        assert status in result_contract


def test_session_migration_checks_effective_schema_contract_and_removes_realtime() -> None:
    sql = _migration()

    assert "pg_catalog.pg_publication_tables" in sql
    assert "ALTER PUBLICATION supabase_realtime DROP TABLE public.aureon_user_sessions" in sql
    assert "has_table_privilege('authenticated', 'public.aureon_user_sessions', 'SELECT')" in sql
    assert "has_column_privilege(" in sql
    assert "has_function_privilege(" in sql
    assert "aureon_user_sessions_sensitive_column_acl_contract_failed" in sql
    assert "aureon_user_session_status_rpc_contract_failed" in sql
    assert "user_binance_credentials_browser_table_acl_contract_failed" in sql
    assert "user_binance_credentials_safe_column_acl_contract_failed" in sql
    assert "user_binance_credentials_sensitive_column_acl_contract_failed" in sql
    assert "data_access_audit_browser_acl_contract_failed" in sql
    assert "data_access_audit_authenticated_policy_contract_failed" in sql
    assert "data_access_audit_service_policy_contract_failed" in sql
    assert "pg_catalog.pg_policy" in sql
    assert "pg_catalog.pg_get_expr" in sql


def test_legacy_credential_export_is_fixed_410_and_has_no_decrypt_path() -> None:
    source = (FUNCTIONS / "get-binance-credentials" / "index.ts").read_text(encoding="utf-8")

    assert 'error: "CREDENTIAL_EXPORT_RETIRED"' in source
    assert "status: 410" in source
    assert "decryptCredential" not in source
    assert ".select(" not in source
    assert "apiKey," not in source
    assert "apiSecret," not in source


def test_legacy_binance_portfolio_route_is_inert_and_cannot_export_credentials() -> None:
    portfolio = (FUNCTIONS / "fetch-binance-portfolio" / "index.ts").read_text(encoding="utf-8")
    assert "functions.invoke('get-binance-credentials'" not in portfolio
    assert "LEGACY_GLOBAL_PRIVILEGED_ROUTE_DISABLED" in portfolio
    assert "decryptCredential" not in portfolio
    assert "user_binance_credentials" not in portfolio
    assert "aureon_user_sessions" not in portfolio
    assert "SUPABASE_SERVICE_ROLE_KEY" not in portfolio
    assert "Deno.env.get" not in portfolio
    assert "req.json(" not in portfolio
    assert "API Key (first 8 chars)" not in portfolio

    health = (FUNCTIONS / "backend-health-check" / "index.ts").read_text(encoding="utf-8")
    assert "PRIVILEGED_HEALTH_CHECK_DISABLED" in health
    assert "functions.invoke('get-binance-credentials'" not in health
    assert "decryptCredential" not in health


def test_browser_source_uses_safe_status_rpc_instead_of_session_table() -> None:
    browser_sources = [
        path
        for path in FRONTEND.rglob("*")
        if path.suffix in {".ts", ".tsx"}
        and path.name != "types.ts"
        and "generated" not in path.parts
    ]
    direct_references = []
    for path in browser_sources:
        # Search ASCII contract tokens as bytes so an unrelated legacy source
        # encoded as Windows-1252 cannot make this security census fail early.
        source = path.read_bytes()
        if b"aureon_user_sessions" in source:
            direct_references.append(path.relative_to(FRONTEND).as_posix())
    assert direct_references == []

    rpc_users = [
        path
        for path in browser_sources
        if b"get_aureon_user_session_status" in path.read_bytes()
    ]
    assert rpc_users


def test_safe_session_rpc_consumers_do_not_read_removed_authority_fields() -> None:
    consumers = (
        FRONTEND / "hooks" / "useAureonSession.ts",
        FRONTEND / "hooks" / "useTerminalSync.ts",
        FRONTEND / "hooks" / "useBrainState.ts",
        FRONTEND / "hooks" / "useUserDataVerification.ts",
        FRONTEND / "core" / "globalSystemsManager.ts",
        FRONTEND / "components" / "ExchangeStatusSummary.tsx",
        FRONTEND / "components" / "ExchangeCredentialsManager.tsx",
        FRONTEND / "components" / "TradingConfigPanel.tsx",
    )
    forbidden_result_access = (
        b"session.recent_trades",
        b"session.trading_mode",
        b"session.is_trading_active",
        b"data.recent_trades",
        b"data.trading_mode",
        b"data.is_trading_active",
        b"sessionData.recent_trades",
        b"sessionData.trading_mode",
        b"sessionData.is_trading_active",
    )

    violations = []
    for path in consumers:
        source = path.read_bytes()
        for token in forbidden_result_access:
            if token in source:
                violations.append(f"{path.relative_to(FRONTEND).as_posix()}:{token.decode()}")
    assert violations == []


def test_account_audit_insert_is_bound_to_both_user_columns() -> None:
    sql = _migration()

    assert 'FOR INSERT TO service_role\n  WITH CHECK (true);' in sql
    assert 'FOR INSERT TO authenticated' in sql
    assert '(SELECT auth.uid()) = user_id' in sql
    assert '(SELECT auth.uid()) = accessed_by' in sql
    assert "GRANT SELECT, INSERT ON TABLE public.data_access_audit TO authenticated;" in sql


def test_pre_cutover_catalog_and_exact_down_migration_are_preserved() -> None:
    receipt = CATALOG_RECEIPT.read_text(encoding="utf-8")
    rollback = ROLLBACK.read_text(encoding="utf-8")

    assert "2026-09-13T13:14:50.069662+00:00" in receipt
    assert "No table rows or credential values were selected" in receipt
    for policy in (
        "Users can insert own session",
        "Users can update own session",
        "Users can view own session",
        "Users can insert own credentials",
        "Users can update own credentials",
        "Users can view own credentials",
        "Service can insert audit logs",
    ):
        assert f'CREATE POLICY "{policy}"' in rollback
        assert f'`{policy}`' in receipt

    assert (
        "GRANT SELECT, INSERT, UPDATE ON TABLE public.aureon_user_sessions"
        in rollback
    )
    assert (
        "GRANT ALL PRIVILEGES ON TABLE public.user_binance_credentials TO authenticated;"
        in rollback
    )
    assert (
        "GRANT ALL PRIVILEGES ON TABLE public.data_access_audit TO authenticated;"
        in rollback
    )
    assert (
        "ALTER PUBLICATION supabase_realtime ADD TABLE public.aureon_user_sessions"
        in rollback
    )
    assert "DROP FUNCTION IF EXISTS public.get_aureon_user_session_status();" in rollback
    assert rollback.startswith("-- Exact rollback") and rollback.rstrip().endswith("COMMIT;")
