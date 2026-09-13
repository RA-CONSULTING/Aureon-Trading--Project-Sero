#!/usr/bin/env python3
"""Audit or atomically apply the pinned Supabase credential-boundary migration.

The normal release path is ``supabase db push``.  This tool is the narrow
fallback for a host where the Supabase CLI cannot establish its temporary
database login role but the authenticated Management API is available.

Audit mode is read-only.  Apply mode executes one database transaction which:

* takes a migration-specific advisory lock;
* proves the exact captured legacy catalog and absent migration history;
* applies the checked-in migration without its nested BEGIN/COMMIT;
* re-proves the hardened catalog;
* records the exact local version and source with the canonical CLI columns;
* commits only after every check succeeds.

The tool never reads application rows or credential values.  It never prints
the Management API token or database error response bodies.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
PROJECT_REF = "siihxcwetdjdsrfdexmb"
VERSION = "20260913101606"
NAME = "harden_user_credential_ownership"
BASELINE_MIGRATION_COUNT = 67
BASELINE_LATEST_VERSION = "20260912180127"
BASELINE_HISTORY_SHA256 = "88a16076f8be053585e33db2d09c8995aff2538a4aae5c9ac8712a02064e6b61"
MIGRATION_PATH = (
    REPO_ROOT / "supabase" / "migrations" / f"{VERSION}_{NAME}.sql"
)
ROLLBACK_PATH = (
    REPO_ROOT
    / "supabase"
    / "migrations"
    / "rollback"
    / f"{VERSION}_{NAME}.down.sql"
)
MIGRATION_SHA256 = "ec9c3f99f024f06904765c6c7805ade8cdfbb52a3613c85192b58d1b477c9c66"
ROLLBACK_SHA256 = "4bb881f8c3efe5818c7463e0ec924c101abcd98656f545b69454eb19aa32308f"
API_ROOT = "https://api.supabase.com/v1"

TABLES = (
    "aureon_user_sessions",
    "user_binance_credentials",
    "data_access_audit",
)


class CutoverError(RuntimeError):
    """A fail-closed cutover validation or provider error."""


class NoRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise CutoverError("Management API redirect denied")


def _policy_exists(
    table: str,
    name: str,
    command: str,
    role: str,
    *,
    using_contains: tuple[str, ...] = (),
    check_contains: tuple[str, ...] = (),
) -> str:
    clauses = [
        "namespace.nspname = 'public'",
        f"relation.relname = '{table}'",
        f"policy.polname = '{name}'",
        f"policy.polcmd = '{command}'",
        f"policy.polroles = ARRAY[('{role}'::regrole)::oid]::oid[]",
    ]
    for token in using_contains:
        clauses.append(
            "COALESCE(pg_catalog.pg_get_expr(policy.polqual, policy.polrelid), '') "
            f"LIKE '%{token}%'"
        )
    for token in check_contains:
        clauses.append(
            "COALESCE(pg_catalog.pg_get_expr(policy.polwithcheck, policy.polrelid), '') "
            f"LIKE '%{token}%'"
        )
    return """EXISTS (
      SELECT 1
      FROM pg_catalog.pg_policy AS policy
      JOIN pg_catalog.pg_class AS relation ON relation.oid = policy.polrelid
      JOIN pg_catalog.pg_namespace AS namespace ON namespace.oid = relation.relnamespace
      WHERE {clauses}
    )""".format(clauses="\n        AND ".join(clauses))


def _policy_count(table: str, count: int) -> str:
    return f"""(
      SELECT count(*) = {count}
      FROM pg_catalog.pg_policy AS policy
      JOIN pg_catalog.pg_class AS relation ON relation.oid = policy.polrelid
      JOIN pg_catalog.pg_namespace AS namespace ON namespace.oid = relation.relnamespace
      WHERE namespace.nspname = 'public'
        AND relation.relname = '{table}'
    )"""


def _all_table_privileges(role: str, table: str, expected: bool) -> list[str]:
    prefix = "" if expected else "NOT "
    return [
        f"{prefix}has_table_privilege('{role}', 'public.{table}', '{privilege}')"
        for privilege in (
            "SELECT",
            "INSERT",
            "UPDATE",
            "DELETE",
            "TRUNCATE",
            "REFERENCES",
            "TRIGGER",
        )
    ]


OLD_SCHEMA_CHECKS = [
    "to_regprocedure('public.get_aureon_user_session_status()') IS NULL",
    "NOT EXISTS (SELECT 1 FROM pg_catalog.pg_proc p JOIN pg_catalog.pg_namespace n "
    "ON n.oid = p.pronamespace WHERE n.nspname = 'public' "
    "AND p.proname = 'get_aureon_user_session_status')",
    "to_regclass('public.aureon_user_session_status') IS NULL",
    "EXISTS (SELECT 1 FROM pg_catalog.pg_publication_tables WHERE "
    "pubname = 'supabase_realtime' AND schemaname = 'public' "
    "AND tablename = 'aureon_user_sessions')",
    _policy_count("aureon_user_sessions", 4),
    _policy_count("user_binance_credentials", 3),
    _policy_count("data_access_audit", 2),
    _policy_exists(
        "aureon_user_sessions",
        "Service role can manage sessions",
        "*",
        "service_role",
        using_contains=("true",),
        check_contains=("true",),
    ),
    _policy_exists(
        "aureon_user_sessions",
        "Users can view own session",
        "r",
        "authenticated",
        using_contains=("auth.uid()", "user_id"),
    ),
    _policy_exists(
        "aureon_user_sessions",
        "Users can insert own session",
        "a",
        "authenticated",
        check_contains=("auth.uid()", "user_id"),
    ),
    _policy_exists(
        "aureon_user_sessions",
        "Users can update own session",
        "w",
        "authenticated",
        using_contains=("auth.uid()", "user_id"),
        check_contains=("auth.uid()", "user_id"),
    ),
    _policy_exists(
        "user_binance_credentials",
        "Users can view own credentials",
        "r",
        "authenticated",
        using_contains=("auth.uid()", "user_id"),
    ),
    _policy_exists(
        "user_binance_credentials",
        "Users can insert own credentials",
        "a",
        "authenticated",
        check_contains=("auth.uid()", "user_id"),
    ),
    _policy_exists(
        "user_binance_credentials",
        "Users can update own credentials",
        "w",
        "authenticated",
        using_contains=("auth.uid()", "user_id"),
    ),
    _policy_exists(
        "data_access_audit",
        "Admins can read audit logs",
        "r",
        "authenticated",
        using_contains=("private.has_role", "admin"),
    ),
    _policy_exists(
        "data_access_audit",
        "Service can insert audit logs",
        "a",
        "service_role",
        check_contains=("true",),
    ),
    "has_table_privilege('authenticated', 'public.aureon_user_sessions', 'SELECT')",
    "has_table_privilege('authenticated', 'public.aureon_user_sessions', 'INSERT')",
    "has_table_privilege('authenticated', 'public.aureon_user_sessions', 'UPDATE')",
    "NOT has_table_privilege('authenticated', 'public.aureon_user_sessions', 'DELETE')",
    *_all_table_privileges("authenticated", "user_binance_credentials", True),
    *_all_table_privileges("authenticated", "data_access_audit", True),
    *_all_table_privileges("service_role", "aureon_user_sessions", True),
    *_all_table_privileges("service_role", "user_binance_credentials", True),
    *_all_table_privileges("service_role", "data_access_audit", True),
]

SAFE_BINANCE_COLUMNS = ("id", "user_id", "created_at", "updated_at", "last_used_at")
SESSION_RPC_COLUMNS = (
    "id",
    "user_id",
    "current_coherence",
    "current_lambda",
    "current_lighthouse_signal",
    "dominant_node",
    "prism_level",
    "prism_state",
    "measurement_truth_status",
    "measurement_source_id",
    "measurement_source_timestamp",
    "measurement_collected_at",
    "measurement_generated_values",
    "total_equity_usdt",
    "total_equity_usd",
    "available_balance_usdt",
    "total_trades",
    "winning_trades",
    "total_pnl_usdt",
    "gas_tank_balance",
    "last_trade_at",
    "last_quantum_update_at",
    "created_at",
    "updated_at",
    "binance_credentials_configured",
    "kraken_credentials_configured",
    "alpaca_credentials_configured",
    "capital_credentials_configured",
)

_rpc_columns_sql = ", ".join(f"'{column}'" for column in SESSION_RPC_COLUMNS)
_safe_binance_columns_sql = ", ".join(f"'{column}'" for column in SAFE_BINANCE_COLUMNS)

TARGET_SCHEMA_CHECKS = [
    "to_regclass('public.aureon_user_session_status') IS NULL",
    "NOT EXISTS (SELECT 1 FROM pg_catalog.pg_publication_tables WHERE "
    "pubname = 'supabase_realtime' AND schemaname = 'public' "
    "AND tablename = 'aureon_user_sessions')",
    _policy_count("aureon_user_sessions", 2),
    _policy_count("user_binance_credentials", 1),
    _policy_count("data_access_audit", 3),
    _policy_exists(
        "aureon_user_sessions",
        "Service role can manage sessions",
        "*",
        "service_role",
        using_contains=("true",),
        check_contains=("true",),
    ),
    _policy_exists(
        "aureon_user_sessions",
        "Users can view own safe session status",
        "r",
        "authenticated",
        using_contains=("auth.uid()", "user_id"),
    ),
    _policy_exists(
        "user_binance_credentials",
        "Users can view own credential status",
        "r",
        "authenticated",
        using_contains=("auth.uid()", "user_id"),
    ),
    _policy_exists(
        "data_access_audit",
        "Admins can read audit logs",
        "r",
        "authenticated",
        using_contains=("private.has_role", "admin"),
    ),
    _policy_exists(
        "data_access_audit",
        "Service role can insert audit logs",
        "a",
        "service_role",
        check_contains=("true",),
    ),
    _policy_exists(
        "data_access_audit",
        "Users can insert own audit logs",
        "a",
        "authenticated",
        check_contains=("auth.uid()", "user_id", "accessed_by"),
    ),
    *_all_table_privileges("anon", "aureon_user_sessions", False),
    *_all_table_privileges("authenticated", "aureon_user_sessions", False),
    "NOT EXISTS (SELECT 1 FROM information_schema.columns c WHERE "
    "c.table_schema = 'public' AND c.table_name = 'aureon_user_sessions' "
    "AND (has_column_privilege('authenticated', 'public.aureon_user_sessions', "
    "c.column_name, 'SELECT') OR has_column_privilege('authenticated', "
    "'public.aureon_user_sessions', c.column_name, 'INSERT') OR "
    "has_column_privilege('authenticated', 'public.aureon_user_sessions', "
    "c.column_name, 'UPDATE'))) ",
    *_all_table_privileges("anon", "user_binance_credentials", False),
    "NOT has_table_privilege('authenticated', 'public.user_binance_credentials', 'SELECT')",
    "NOT has_table_privilege('authenticated', 'public.user_binance_credentials', 'INSERT')",
    "NOT has_table_privilege('authenticated', 'public.user_binance_credentials', 'UPDATE')",
    "NOT has_table_privilege('authenticated', 'public.user_binance_credentials', 'DELETE')",
    "NOT has_table_privilege('authenticated', 'public.user_binance_credentials', 'TRUNCATE')",
    "NOT has_table_privilege('authenticated', 'public.user_binance_credentials', 'REFERENCES')",
    "NOT has_table_privilege('authenticated', 'public.user_binance_credentials', 'TRIGGER')",
    "NOT EXISTS (SELECT 1 FROM information_schema.columns c WHERE "
    "c.table_schema = 'public' AND c.table_name = 'user_binance_credentials' "
    f"AND c.column_name NOT IN ({_safe_binance_columns_sql}) "
    "AND has_column_privilege('authenticated', 'public.user_binance_credentials', "
    "c.column_name, 'SELECT'))",
    "NOT EXISTS (SELECT 1 FROM information_schema.columns c WHERE "
    "c.table_schema = 'public' AND c.table_name = 'user_binance_credentials' "
    "AND (has_column_privilege('authenticated', 'public.user_binance_credentials', "
    "c.column_name, 'INSERT') OR has_column_privilege('authenticated', "
    "'public.user_binance_credentials', c.column_name, 'UPDATE')))",
    *[
        "has_column_privilege('authenticated', 'public.user_binance_credentials', "
        f"'{column}', 'SELECT')"
        for column in SAFE_BINANCE_COLUMNS
    ],
    *_all_table_privileges("anon", "data_access_audit", False),
    "has_table_privilege('authenticated', 'public.data_access_audit', 'SELECT')",
    "has_table_privilege('authenticated', 'public.data_access_audit', 'INSERT')",
    "NOT has_table_privilege('authenticated', 'public.data_access_audit', 'UPDATE')",
    "NOT has_table_privilege('authenticated', 'public.data_access_audit', 'DELETE')",
    "NOT has_table_privilege('authenticated', 'public.data_access_audit', 'TRUNCATE')",
    "NOT has_table_privilege('authenticated', 'public.data_access_audit', 'REFERENCES')",
    "NOT has_table_privilege('authenticated', 'public.data_access_audit', 'TRIGGER')",
    "EXISTS (SELECT 1 FROM pg_catalog.pg_proc p JOIN pg_catalog.pg_namespace n "
    "ON n.oid = p.pronamespace WHERE n.nspname = 'public' "
    "AND p.proname = 'get_aureon_user_session_status' "
    "AND pg_catalog.pg_get_function_identity_arguments(p.oid) = '' "
    "AND p.prosecdef AND p.provolatile = 's' "
    "AND 'search_path=\"\"' = ANY(p.proconfig) "
    f"AND p.proargnames = ARRAY[{_rpc_columns_sql}]::text[] "
    "AND pg_catalog.pg_get_function_result(p.oid) !~ "
    "'(api_key_encrypted|api_secret_encrypted|password_encrypted|is_trading_active|trading_mode|recent_trades)' "
    "AND pg_catalog.pg_get_functiondef(p.oid) LIKE '%session.user_id%' "
    "AND pg_catalog.pg_get_functiondef(p.oid) LIKE '%auth.uid()%')",
    "(SELECT count(*) = 1 FROM pg_catalog.pg_proc p "
    "JOIN pg_catalog.pg_namespace n ON n.oid = p.pronamespace "
    "WHERE n.nspname = 'public' AND p.proname = 'get_aureon_user_session_status')",
    "NOT has_function_privilege('anon', "
    "'public.get_aureon_user_session_status()', 'EXECUTE')",
    "has_function_privilege('authenticated', "
    "'public.get_aureon_user_session_status()', 'EXECUTE')",
    "has_function_privilege('service_role', "
    "'public.get_aureon_user_session_status()', 'EXECUTE')",
    *_all_table_privileges("service_role", "aureon_user_sessions", True),
    *_all_table_privileges("service_role", "user_binance_credentials", True),
    *_all_table_privileges("service_role", "data_access_audit", True),
]

RLS_CHECK = """(
  SELECT count(*) = 3
  FROM pg_catalog.pg_class relation
  JOIN pg_catalog.pg_namespace namespace ON namespace.oid = relation.relnamespace
  WHERE namespace.nspname = 'public'
    AND relation.relname IN ('aureon_user_sessions', 'user_binance_credentials', 'data_access_audit')
    AND relation.relkind IN ('r', 'p')
    AND relation.relrowsecurity
    AND NOT relation.relforcerowsecurity
)"""


def _and(checks: list[str]) -> str:
    return "\n    AND ".join(f"({check})" for check in checks)


def catalog_state_sql() -> str:
    """Return the metadata-only provider readback query."""

    old = _and([RLS_CHECK, *OLD_SCHEMA_CHECKS])
    target = _and([RLS_CHECK, *TARGET_SCHEMA_CHECKS])
    table_names = ", ".join(f"'{table}'" for table in TABLES)
    return f"""
SELECT
  (
    SELECT count(*) = {BASELINE_MIGRATION_COUNT}
      AND max(version) = '{BASELINE_LATEST_VERSION}'
      AND pg_catalog.encode(extensions.digest(
        string_agg(
          version || ':' || COALESCE(name, ''), E'\\n' ORDER BY version
        ),
        'sha256'
      ), 'hex') = '{BASELINE_HISTORY_SHA256}'
    FROM supabase_migrations.schema_migrations
    WHERE version <> '{VERSION}'
  ) AS baseline_history_exact,
  EXISTS (
    SELECT 1 FROM supabase_migrations.schema_migrations
    WHERE version = '{VERSION}'
  ) AS history_present,
  COALESCE((
    SELECT name = '{NAME}'
      AND array_length(statements, 1) = 1
      AND pg_catalog.encode(
        extensions.digest(statements[1], 'sha256'), 'hex'
      ) = '{MIGRATION_SHA256}'
      AND created_by IS NULL
      AND idempotency_key IS NULL
      AND rollback IS NULL
    FROM supabase_migrations.schema_migrations
    WHERE version = '{VERSION}'
  ), false) AS history_exact,
  ({old}) AS legacy_schema_exact,
  ({target}) AS target_schema_exact,
  (SELECT count(*) FROM pg_catalog.pg_policy policy
    JOIN pg_catalog.pg_class relation ON relation.oid = policy.polrelid
    JOIN pg_catalog.pg_namespace namespace ON namespace.oid = relation.relnamespace
    WHERE namespace.nspname = 'public'
      AND relation.relname = ANY(ARRAY[{table_names}]::text[])) AS policy_count,
  EXISTS (SELECT 1 FROM pg_catalog.pg_publication_tables
    WHERE pubname = 'supabase_realtime'
      AND schemaname = 'public'
      AND tablename = 'aureon_user_sessions') AS session_in_realtime,
  (SELECT count(*) FROM pg_catalog.pg_proc p
    JOIN pg_catalog.pg_namespace n ON n.oid = p.pronamespace
    WHERE n.nspname = 'public'
      AND p.proname = 'get_aureon_user_session_status') AS status_rpc_count;
"""


def classify_state(row: dict[str, Any]) -> str:
    if (
        row.get("baseline_history_exact") is True
        and row.get("history_present") is False
        and row.get("history_exact") is False
        and row.get("legacy_schema_exact") is True
        and row.get("target_schema_exact") is False
    ):
        return "ready_to_apply"
    if (
        row.get("baseline_history_exact") is True
        and row.get("history_present") is True
        and row.get("history_exact") is True
        and row.get("legacy_schema_exact") is False
        and row.get("target_schema_exact") is True
    ):
        return "applied"
    return "inconsistent"


def _verified_source(path: Path, expected_sha256: str) -> str:
    raw = path.read_bytes()
    actual = hashlib.sha256(raw).hexdigest()
    if actual != expected_sha256:
        raise CutoverError(f"source hash mismatch: {path.name}: {actual}")
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise CutoverError(f"source is not UTF-8: {path.name}") from error


def _migration_body(source: str) -> str:
    begin_matches = list(re.finditer(r"(?m)^BEGIN;\s*$", source))
    commit_matches = list(re.finditer(r"(?m)^COMMIT;\s*$", source))
    if len(begin_matches) != 1 or len(commit_matches) != 1:
        raise CutoverError("migration must contain exactly one standalone BEGIN and COMMIT")
    begin = begin_matches[0]
    commit = commit_matches[0]
    if begin.start() >= commit.start() or source[commit.end() :].strip():
        raise CutoverError("migration transaction markers are not the outer boundary")
    return source[: begin.start()] + source[begin.end() : commit.start()] + source[commit.end() :]


def _dollar_quote(value: str, tag: str) -> str:
    marker = f"${tag}$"
    if marker in value:
        raise CutoverError(f"SQL source contains reserved dollar-quote marker {marker}")
    return f"{marker}{value}{marker}"


def build_apply_sql(migration: str) -> str:
    body = _migration_body(migration)
    state = catalog_state_sql().strip().removesuffix(";")
    migration_literal = _dollar_quote(migration, "aureon_migration_source_20260913101606")
    return f"""BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '120s';
SET LOCAL idle_in_transaction_session_timeout = '60s';
SELECT pg_catalog.pg_advisory_xact_lock(
  pg_catalog.hashtextextended('aureon.supabase.{PROJECT_REF}.{VERSION}', 0)
);

DO $aureon_preflight$
DECLARE
  state record;
BEGIN
  SELECT * INTO state FROM ({state}) AS catalog_state;
  IF NOT state.baseline_history_exact
     OR state.history_present
     OR state.history_exact
     OR NOT state.legacy_schema_exact
     OR state.target_schema_exact THEN
    RAISE EXCEPTION 'aureon_supabase_preflight_state_mismatch';
  END IF;
END
$aureon_preflight$;

{body.rstrip()}

DO $aureon_post_schema$
DECLARE
  state record;
BEGIN
  SELECT * INTO state FROM ({state}) AS catalog_state;
  IF NOT state.baseline_history_exact
     OR state.history_present
     OR state.history_exact
     OR state.legacy_schema_exact
     OR NOT state.target_schema_exact THEN
    RAISE EXCEPTION 'aureon_supabase_post_schema_contract_failed';
  END IF;
END
$aureon_post_schema$;

INSERT INTO supabase_migrations.schema_migrations (
  version, statements, name
) VALUES (
  '{VERSION}',
  ARRAY[{migration_literal}]::text[],
  '{NAME}'
);

DO $aureon_post_history$
DECLARE
  state record;
BEGIN
  SELECT * INTO state FROM ({state}) AS catalog_state;
  IF NOT state.baseline_history_exact
     OR NOT state.history_present
     OR NOT state.history_exact
     OR state.legacy_schema_exact
     OR NOT state.target_schema_exact THEN
    RAISE EXCEPTION 'aureon_supabase_post_history_contract_failed';
  END IF;
END
$aureon_post_history$;
COMMIT;
"""


def _token(env_name: str, credential_target: str | None) -> str:
    value = os.environ.get(env_name, "").strip()
    if not value and credential_target:
        if sys.platform != "win32":
            raise CutoverError("Windows Credential Manager is unavailable on this host")
        try:
            import win32cred  # type: ignore[import-not-found]

            blob = win32cred.CredRead(
                credential_target,
                win32cred.CRED_TYPE_GENERIC,
            )["CredentialBlob"]
        except Exception as error:  # pragma: no cover - provider/host dependent
            raise CutoverError("could not read the named Windows credential") from error
        value = blob.decode("utf-8") if isinstance(blob, (bytes, bytearray)) else str(blob)
        value = value.strip()
    if not value or any(ord(character) > 127 for character in value):
        raise CutoverError("a valid Management API access token was not supplied")
    return value


def _query(token: str, sql: str, *, read_only: bool) -> list[dict[str, Any]]:
    payload: dict[str, Any] = {"query": sql, "read_only": read_only}
    request = urllib.request.Request(
        f"{API_ROOT}/projects/{PROJECT_REF}/database/query",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "aureon-supabase-credential-cutover/1",
        },
        method="POST",
    )
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({}), NoRedirects()
    )
    try:
        with opener.open(request, timeout=150) as response:
            result = json.load(response)
    except urllib.error.HTTPError as error:
        raise CutoverError(f"Management API HTTP {error.code}; response body withheld") from error
    except (OSError, TimeoutError, urllib.error.URLError, ValueError) as error:
        raise CutoverError("Management API outcome uncertain; run audit without retrying apply") from error
    if not isinstance(result, list) or any(not isinstance(row, dict) for row in result):
        raise CutoverError("Management API returned an unexpected response shape")
    return result


def audit(token: str) -> dict[str, Any]:
    rows = _query(token, catalog_state_sql(), read_only=True)
    if len(rows) != 1:
        raise CutoverError("catalog readback did not return exactly one row")
    row = rows[0]
    state = classify_state(row)
    return {
        "schema": "aureon.supabase.credential_hardening_cutover.v1",
        "project_ref": PROJECT_REF,
        "migration_version": VERSION,
        "migration_sha256": MIGRATION_SHA256,
        "state": state,
        "catalog": row,
        "contains_application_rows": False,
        "contains_credentials": False,
    }


def apply(token: str, acknowledgement: str) -> dict[str, Any]:
    if acknowledgement.lower() != MIGRATION_SHA256:
        raise CutoverError("apply acknowledgement does not match the pinned migration SHA-256")
    migration = _verified_source(MIGRATION_PATH, MIGRATION_SHA256)
    _verified_source(ROLLBACK_PATH, ROLLBACK_SHA256)
    before = audit(token)
    if before["state"] == "applied":
        return {**before, "operation": "no_op_already_applied"}
    if before["state"] != "ready_to_apply":
        raise CutoverError("provider catalog/history are inconsistent; no mutation attempted")

    sql = build_apply_sql(migration)
    try:
        _query(token, sql, read_only=False)
    except CutoverError as error:
        # Do not retry an uncertain write.  A fresh readback distinguishes a
        # committed transaction from a rolled-back/no-op outcome.
        after_error = audit(token)
        if after_error["state"] == "applied":
            return {
                **after_error,
                "operation": "applied_provider_confirmed_after_uncertain_response",
            }
        raise CutoverError(
            f"apply did not produce a provider-confirmed target state ({after_error['state']})"
        ) from error

    after = audit(token)
    if after["state"] != "applied":
        raise CutoverError("apply response returned but provider readback is not the target state")
    return {**after, "operation": "applied_provider_confirmed"}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("audit", "apply"), nargs="?", default="audit")
    parser.add_argument("--project-ref", default=PROJECT_REF)
    parser.add_argument("--access-token-env", default="SUPABASE_ACCESS_TOKEN")
    parser.add_argument("--windows-credential-target")
    parser.add_argument("--acknowledge-sha256", default="")
    parser.add_argument("--compact", action="store_true")
    return parser


def main() -> int:
    args = _parser().parse_args()
    if args.project_ref != PROJECT_REF:
        raise CutoverError(f"project ref must be exactly {PROJECT_REF}")
    token = _token(args.access_token_env, args.windows_credential_target)
    result = (
        audit(token)
        if args.mode == "audit"
        else apply(token, args.acknowledge_sha256)
    )
    print(json.dumps(result, indent=None if args.compact else 2, sort_keys=True))
    return 0 if result["state"] in {"ready_to_apply", "applied"} else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except CutoverError as error:
        print(json.dumps({"ok": False, "error": str(error)}, sort_keys=True), file=sys.stderr)
        raise SystemExit(1) from error
