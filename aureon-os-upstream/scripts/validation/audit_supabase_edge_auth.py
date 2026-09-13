#!/usr/bin/env python3
"""Offline inventory and policy check for Supabase Edge Function authentication.

This deliberately treats CORS declarations as metadata, never authentication.
No network, Supabase CLI, secrets, or provider access is required.
"""

from __future__ import annotations

import argparse
import json
import re
import tomllib
from pathlib import Path
from typing import Any

DEFAULT_REPO_ROOT = Path(__file__).resolve().parents[2]
PRODUCTION_INVENTORY_RELATIVE = Path(
    "docs/evidence/supabase/edge-functions/20260913/production_attack_surface.json"
)

FUNCTION_SECTION = "functions"
PRIVILEGE_ENV_NAMES = {
    "SUPABASE_SERVICE_ROLE_KEY": "service_role",
    "SUPABASE_SECRET_KEY": "secret_key",
    "SUPABASE_ANON_KEY": "anon",
    "SUPABASE_PUBLISHABLE_KEY": "publishable",
}
DB_MUTATION_OPERATIONS = ("insert", "upsert", "update", "delete", "rpc")
STORAGE_MUTATION_OPERATIONS = ("upload", "remove", "move", "copy")
AUTH_ADMIN_OPERATIONS = (
    "createUser",
    "deleteUser",
    "updateUserById",
    "inviteUserByEmail",
)
EDGE_INVOCATION_OPERATION = "invoke_edge_function"
MUTATION_CALL_RE = re.compile(
    r"\.\s*(" + "|".join(
        (*DB_MUTATION_OPERATIONS, *STORAGE_MUTATION_OPERATIONS, *AUTH_ADMIN_OPERATIONS)
    ) + r")\s*\(",
    re.IGNORECASE,
)
FROM_TARGET_RE = re.compile(r"\.from\s*\(\s*(['\"`])([^'\"`]+)\1\s*\)")
METHOD_EQUAL_RE = re.compile(
    r"(?:req|request)\.method\s*(?:===|==)\s*['\"]([A-Z]+)['\"]",
    re.IGNORECASE,
)
METHOD_NOT_EQUAL_RE = re.compile(
    r"(?:req|request)\.method\s*(?:!==|!=)\s*['\"]([A-Z]+)['\"]",
    re.IGNORECASE,
)

# This is intentionally narrow. Each allowlisted function must retain every
# source fragment below or the contract fails closed.
REVIEWED_CUSTOM_AUTH: dict[str, tuple[re.Pattern[str], ...]] = {
    "ingest-kelly-computation": (
        re.compile(r"headers\.get\(\s*['\"]Authorization['\"]\s*\)"),
        re.compile(r"replace\(\s*/\^Bearer\\s\+?/i"),
        re.compile(r"auth\.getUser\(\s*token\s*\)"),
        re.compile(r"authError\s*\|\|\s*!user"),
    ),
}


def _read_config(repo_root: Path) -> dict[str, Any]:
    config_path = repo_root / "supabase" / "config.toml"
    return tomllib.loads(config_path.read_text(encoding="utf-8"))


def _production_dispositions(repo_root: Path) -> dict[str, str]:
    inventory_path = repo_root / PRODUCTION_INVENTORY_RELATIVE
    if not inventory_path.is_file():
        return {}
    payload = json.loads(inventory_path.read_text(encoding="utf-8"))
    rows = payload.get("functions", [])
    if not isinstance(rows, list):
        raise ValueError("production Edge Function inventory must contain an array")
    return {
        row["slug"]: row["disposition"]
        for row in rows
        if isinstance(row, dict)
        and isinstance(row.get("slug"), str)
        and isinstance(row.get("disposition"), str)
    }


def _callable_methods(source: str) -> list[str]:
    required = {
        method.upper()
        for method in METHOD_NOT_EQUAL_RE.findall(source)
        if method.upper() != "OPTIONS"
    }
    if required:
        return sorted(required)

    dispatched = {
        method.upper()
        for method in METHOD_EQUAL_RE.findall(source)
        if method.upper() != "OPTIONS"
    }
    if dispatched:
        return sorted(dispatched)

    if re.search(
        r"(?:req|request)\.method\s*(?:===|==)\s*['\"]OPTIONS['\"]",
        source,
        re.IGNORECASE,
    ):
        return ["ANY_NON_OPTIONS"]
    return ["ANY"]


def _database_targets(source: str) -> list[str]:
    targets: set[str] = set()
    for match in FROM_TARGET_RE.finditer(source):
        prefix = source[max(0, match.start() - 32) : match.start()]
        if re.search(r"\.storage\s*$", prefix):
            continue
        targets.add(match.group(2))
    return sorted(targets)


def _storage_targets(source: str) -> list[str]:
    pattern = re.compile(
        r"\.storage\s*\.from\s*\(\s*(['\"`])([^'\"`]+)\1\s*\)"
    )
    return sorted({match.group(2) for match in pattern.finditer(source)})


def _invoked_edge_functions(source: str) -> list[str]:
    targets = set(
        re.findall(r"\.functions\.invoke\s*\(\s*['\"]([^'\"]+)['\"]", source)
    )
    targets.update(re.findall(r"/functions/v1/([A-Za-z0-9_-]+)", source))
    if re.search(r"/functions/v1/\$\{[^}]+\}", source):
        for array_body in re.findall(
            r"const\s+edgeFunctions\s*=\s*\[(.*?)\]", source, re.DOTALL
        ):
            targets.update(re.findall(r"['\"]([A-Za-z0-9_-]+)['\"]", array_body))
        if not targets:
            targets.add("dynamic")
    return sorted(targets)


def _custom_auth_mechanism(source: str) -> str:
    reads_authorization = bool(
        re.search(r"headers\.get\(\s*['\"]Authorization['\"]\s*\)", source)
    )
    validates_user = bool(re.search(r"auth\.getUser\s*\(", source))
    checks_user_result = bool(
        re.search(r"(?:authError|error)\s*\|\|\s*!user", source)
    )
    if reads_authorization and validates_user and checks_user_result:
        return "supabase_auth_get_user"
    configured_secret = re.search(
        r"const\s+(\w+)\s*=\s*Deno\.env\.get\(\s*['\"][A-Z0-9_]*(?:TOKEN|SECRET)['\"]\s*\)",
        source,
        re.IGNORECASE,
    )
    supplied_secret = re.search(
        r"const\s+(\w+)\s*=\s*(?:req|request)\.headers\.get\(\s*['\"]x-[^'\"]*(?:token|secret)['\"]\s*\)",
        source,
        re.IGNORECASE,
    )
    if configured_secret and supplied_secret:
        configured_name = re.escape(configured_secret.group(1))
        supplied_name = re.escape(supplied_secret.group(1))
        rejects_missing_configuration = re.search(
            rf"!{configured_name}\b[^\n]*(?:throw|return)", source
        )
        rejects_missing_or_mismatched = re.search(
            rf"!{supplied_name}\b[^\n]*\|\|[^\n]*{supplied_name}\s*!==\s*{configured_name}",
            source,
        )
        if rejects_missing_configuration and rejects_missing_or_mismatched:
            return "shared_secret_exact_compare"
    return "none"


def _custom_auth_allowlisted(function_name: str, source: str) -> bool:
    contract = REVIEWED_CUSTOM_AUTH.get(function_name)
    return bool(contract) and all(pattern.search(source) for pattern in contract)


def _mutation_operations(source: str) -> list[str]:
    canonical = {operation.lower(): operation for operation in MUTATION_CALL_RE.findall(source)}
    if re.search(r"\.functions\.invoke\s*\(|/functions/v1/", source):
        canonical[EDGE_INVOCATION_OPERATION] = EDGE_INVOCATION_OPERATION
    return sorted(canonical)


def build_auth_matrix(repo_root: Path = DEFAULT_REPO_ROOT) -> list[dict[str, Any]]:
    config = _read_config(repo_root)
    production_dispositions = _production_dispositions(repo_root)
    configured_functions = config.get(FUNCTION_SECTION, {})
    if not isinstance(configured_functions, dict):
        raise ValueError("supabase/config.toml functions section must be a table")

    functions_root = repo_root / "supabase" / "functions"
    matrix: list[dict[str, Any]] = []
    for function_dir in sorted(path for path in functions_root.iterdir() if path.is_dir()):
        if function_dir.name == "_shared":
            continue
        source_path = function_dir / "index.ts"
        if not source_path.is_file():
            continue
        source = source_path.read_text(encoding="utf-8")
        section = configured_functions.get(function_dir.name, {})
        if not isinstance(section, dict):
            raise ValueError(f"invalid config section for {function_dir.name}")
        config_declared = "verify_jwt" in section
        verify_jwt = section.get("verify_jwt", True)
        if not isinstance(verify_jwt, bool):
            raise ValueError(f"verify_jwt must be boolean for {function_dir.name}")

        credentials = sorted(
            label for env_name, label in PRIVILEGE_ENV_NAMES.items() if env_name in source
        )
        environment_names = sorted(
            set(re.findall(r"Deno\.env\.get\(\s*['\"]([A-Z0-9_]+)['\"]", source))
        )
        sensitive_environment_names = sorted(
            name
            for name in environment_names
            if name.endswith(("_KEY", "_SECRET", "_TOKEN", "_PASSWORD"))
            or name in {"SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_SECRET_KEY"}
        )
        operations = _mutation_operations(source)
        db_operations = sorted(set(operations).intersection(DB_MUTATION_OPERATIONS))
        storage_operations = sorted(
            set(operations).intersection(STORAGE_MUTATION_OPERATIONS)
        )
        auth_admin_operations = sorted(
            set(operations).intersection(AUTH_ADMIN_OPERATIONS)
        )
        edge_invocation = EDGE_INVOCATION_OPERATION in operations
        has_privileged_credential = bool(
            set(credentials).intersection({"service_role", "secret_key", "anon", "publishable"})
        )
        privileged_mutation = has_privileged_credential and bool(
            db_operations or storage_operations or auth_admin_operations or edge_invocation
        )
        privileged_read = has_privileged_credential and bool(
            _database_targets(source) or _storage_targets(source)
        )
        secret_backed_provider = bool(sensitive_environment_names) and bool(
            re.search(r"\bfetch\s*\(|fetchExternalLlm\s*\(", source)
        )
        custom_auth = _custom_auth_mechanism(source)
        allowlisted = _custom_auth_allowlisted(function_dir.name, source)
        cors_mentions_authorization = bool(
            re.search(r"Access-Control-Allow-Headers[^\n]*authorization", source, re.IGNORECASE)
        )

        if verify_jwt:
            protection = "gateway_jwt"
        elif allowlisted:
            protection = f"reviewed_custom:{custom_auth}"
        elif custom_auth != "none":
            protection = f"observed_custom_unreviewed:{custom_auth}"
        else:
            protection = "none"

        privileged_access = privileged_mutation or privileged_read
        if not privileged_access and not secret_backed_provider:
            authority = "not_required"
        elif allowlisted and custom_auth == "supabase_auth_get_user":
            authority = "reviewed_subject_auth"
        elif custom_auth == "shared_secret_exact_compare":
            authority = "independent_service_secret"
        elif verify_jwt:
            authority = "gateway_jwt_only_insufficient"
        else:
            authority = "none"

        matrix.append(
            {
                "function": function_dir.name,
                "source": str(source_path.relative_to(repo_root)).replace("\\", "/"),
                "config_declared": config_declared,
                "verify_jwt": verify_jwt,
                "verify_jwt_source": "explicit" if config_declared else "default_true",
                "callable_methods": _callable_methods(source),
                "credentials": credentials,
                "environment_names": environment_names,
                "sensitive_environment_names": sensitive_environment_names,
                "database_targets": _database_targets(source),
                "storage_targets": _storage_targets(source),
                "invoked_edge_functions": _invoked_edge_functions(source),
                "mutation_operations": operations,
                "privileged_mutation": privileged_mutation,
                "privileged_read": privileged_read,
                "privileged_access": privileged_access,
                "secret_backed_provider": secret_backed_provider,
                "custom_auth": custom_auth,
                "custom_auth_allowlisted": allowlisted,
                "cors_mentions_authorization": cors_mentions_authorization,
                "protection": protection,
                "authority": authority,
                "production_active": function_dir.name in production_dispositions,
                "production_disposition": production_dispositions.get(function_dir.name),
            }
        )
    return matrix


def policy_violations(matrix: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        row
        for row in matrix
        if row["production_active"]
        and (
            row["authority"] == "gateway_jwt_only_insufficient"
            or (
                row["secret_backed_provider"]
                and row["production_disposition"] != "retired"
            )
        )
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=DEFAULT_REPO_ROOT)
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args()

    matrix = build_auth_matrix(args.repo_root.resolve())
    violations = policy_violations(matrix)
    payload = {
        "schema": "aureon.supabase_edge_auth_matrix.v1",
        "offline": True,
        "function_count": len(matrix),
        "privileged_mutation_count": sum(bool(row["privileged_mutation"]) for row in matrix),
        "privileged_read_count": sum(bool(row["privileged_read"]) for row in matrix),
        "production_active_count": sum(bool(row["production_active"]) for row in matrix),
        "violations": [row["function"] for row in violations],
        "functions": matrix,
    }
    print(json.dumps(payload, indent=None if args.compact else 2, sort_keys=True))
    return 1 if violations else 0


if __name__ == "__main__":
    raise SystemExit(main())
