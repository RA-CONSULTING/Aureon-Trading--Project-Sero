"""Fail-closed contract for the Management API migration fallback."""

from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "operations" / "supabase_credential_hardening_cutover.py"


def _module():
    spec = importlib.util.spec_from_file_location("supabase_credential_cutover", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_pinned_migration_and_rollback_hashes_match() -> None:
    module = _module()
    assert hashlib.sha256(module.MIGRATION_PATH.read_bytes()).hexdigest() == module.MIGRATION_SHA256
    assert hashlib.sha256(module.ROLLBACK_PATH.read_bytes()).hexdigest() == module.ROLLBACK_SHA256


def test_provider_state_classification_fails_closed() -> None:
    module = _module()
    ready = {
        "baseline_history_exact": True,
        "history_present": False,
        "history_exact": False,
        "legacy_schema_exact": True,
        "target_schema_exact": False,
    }
    applied = {
        "baseline_history_exact": True,
        "history_present": True,
        "history_exact": True,
        "legacy_schema_exact": False,
        "target_schema_exact": True,
    }
    assert module.classify_state(ready) == "ready_to_apply"
    assert module.classify_state(applied) == "applied"
    for key in ready:
        drifted = dict(ready)
        drifted[key] = not drifted[key]
        assert module.classify_state(drifted) == "inconsistent"
    for key in applied:
        drifted = dict(applied)
        drifted[key] = not drifted[key]
        assert module.classify_state(drifted) == "inconsistent"


def test_fallback_is_one_atomic_exact_version_transaction() -> None:
    module = _module()
    migration = module.MIGRATION_PATH.read_bytes().decode("utf-8")
    sql = module.build_apply_sql(migration)

    assert sql.startswith("BEGIN;\n") and sql.rstrip().endswith("COMMIT;")
    assert "\nBEGIN;\n" not in module._migration_body(migration)
    assert "\nCOMMIT;" not in module._migration_body(migration)
    assert "pg_advisory_xact_lock" in sql
    assert sql.index("aureon_supabase_preflight_state_mismatch") < sql.index(
        'CREATE POLICY "Users can view own safe session status"'
    )
    assert sql.index("aureon_supabase_post_schema_contract_failed") < sql.index(
        "INSERT INTO supabase_migrations.schema_migrations"
    )
    assert sql.index("INSERT INTO supabase_migrations.schema_migrations") < sql.index(
        "aureon_supabase_post_history_contract_failed"
    )
    assert f"'{module.VERSION}'" in sql
    assert "ARRAY[$aureon_migration_source_20260913101606$" in sql
    assert "version, statements, name" in sql
    assert "created_by, idempotency_key, rollback" not in sql


def test_catalog_readback_is_metadata_only_and_checks_effective_boundaries() -> None:
    module = _module()
    sql = module.catalog_state_sql()
    for required in (
        "supabase_migrations.schema_migrations",
        "baseline_history_exact",
        "pg_catalog.pg_policy",
        "has_table_privilege",
        "has_column_privilege",
        "has_function_privilege",
        "pg_catalog.pg_publication_tables",
        "target_schema_exact",
        "legacy_schema_exact",
    ):
        assert required in sql
    for forbidden in (
        "SELECT * FROM public.aureon_user_sessions",
        "SELECT * FROM public.user_binance_credentials",
        "api_key_encrypted =",
        "api_secret_encrypted =",
    ):
        assert forbidden not in sql
