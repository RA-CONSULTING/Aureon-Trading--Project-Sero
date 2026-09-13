from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "supabase" / "migrations"

FILES = {
    "tenant": MIGRATIONS / "20260912143248_harden_public_product_tenant_boundaries.sql",
    "public": MIGRATIONS / "20260912144634_close_unrestricted_public_rls_policies.sql",
    "roles": MIGRATIONS / "20260912144718_finish_public_schema_role_normalization.sql",
    "helpers": MIGRATIONS / "20260912144946_move_rls_helpers_out_of_exposed_schema.sql",
}


def test_provider_migration_versions_and_security_contract_are_pinned():
    sql = {name: path.read_text(encoding="utf-8") for name, path in FILES.items()}

    assert all(path.is_file() for path in FILES.values())
    assert 'CREATE POLICY "Service manages orders"' in sql["tenant"]
    assert 'ON public.oms_order_queue FOR ALL TO service_role' in sql["tenant"]
    assert 'DROP POLICY IF EXISTS "Authenticated users can read trade audit log"' in sql["tenant"]
    assert 'WITH CHECK ((SELECT auth.uid()) = user_id)' in sql["tenant"]

    assert "roles @> ARRAY['public']::name[]" in sql["public"]
    assert "REVOKE ALL PRIVILEGES ON TABLE public.%I FROM anon" in sql["public"]
    assert "GRANT SELECT ON TABLE public.crypto_assets_registry TO anon" in sql["public"]

    assert 'ON public.exchange_balance_cache FOR ALL TO service_role' in sql["roles"]
    assert 'ON public.harmonic_nexus_performance_metrics FOR ALL TO service_role' in sql["roles"]

    assert "ALTER FUNCTION public.has_role(uuid, public.app_role) SET SCHEMA private" in sql["helpers"]
    assert "ALTER FUNCTION public.session_belongs_to_current_user(uuid) SET SCHEMA private" in sql["helpers"]
    assert "REVOKE ALL ON SCHEMA private FROM PUBLIC, anon, authenticated" in sql["helpers"]
