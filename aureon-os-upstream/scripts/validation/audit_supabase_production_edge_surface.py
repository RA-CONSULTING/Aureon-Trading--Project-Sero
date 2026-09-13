#!/usr/bin/env python3
"""Validate the pinned production Supabase Edge Function disposition offline.

The inventory is a provider read-back, but this verifier performs no network
requests. It proves that every production-active slug has local source, every
retired route is inert and gateway-JWT protected for defense in depth, and the
small retained public-data set cannot use credentials or database authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import tomllib
from pathlib import Path
from typing import Any

DEFAULT_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INVENTORY = (
    DEFAULT_REPO_ROOT
    / "docs"
    / "evidence"
    / "supabase"
    / "edge-functions"
    / "20260913"
    / "production_attack_surface.json"
)

EXPECTED_RETAINED = {
    "fetch-binance-market-data",
    "fetch-binance-symbols",
    "fetch-historical-data",
    "fetch-noaa-space-weather",
    "fetch-schumann-data",
}

EXPECTED_BUNDLE_CLASSIFICATION_COUNTS = {
    "retained_production_truth_clean_public_read_only": 2,
    "production_mixed_provider_and_generated_values": 1,
    "deployed_inert_direct_execution_stub": 6,
    "critical_financial_credential_or_global_mutation": 10,
    "sensitive_user_owner_legacy_custody": 6,
    "public_service_role_or_global_data": 12,
    "gateway_jwt_only_service_role_global_read_write": 26,
    "provider_secret_or_cost_without_independent_authority": 7,
    "false_or_weak_authority": 4,
    "custom_key_privileged_gateway": 1,
    "active_broken_unbound_database_reference": 1,
    "unsafe_public_read_proxy": 2,
    "stateless_or_synthetic_not_live": 22,
}

INERT_MARKERS = {
    "LEGACY_GLOBAL_PRIVILEGED_ROUTE_DISABLED",
    "LEGACY_DIRECT_EXECUTION_DISABLED",
    "PRIVILEGED_HEALTH_CHECK_DISABLED",
    "UNVERIFIED_BALANCE_CREDIT_DISABLED",
    "PRIVILEGED_BALANCE_LOOKUP_DISABLED",
    "function_quarantined",
}

FORBIDDEN_RETIRED_FRAGMENTS = (
    "Deno.env.get",
    "SUPABASE_SERVICE_ROLE_KEY",
    "SUPABASE_SECRET_KEY",
    "createClient",
    "req.json(",
    "request.json(",
    ".from(",
    ".insert(",
    ".upsert(",
    ".update(",
    ".delete(",
    ".rpc(",
    "fetch(",
    "../_shared/",
)

FORBIDDEN_RETAINED_FRAGMENTS = (
    "Deno.env.get",
    "SUPABASE_",
    "createClient",
    ".from(",
    ".insert(",
    ".upsert(",
    ".update(",
    ".delete(",
    ".rpc(",
    "Authorization",
    "X-MBX-APIKEY",
    "Math.random(",
)

ALLOWED_RETAINED_HOSTS = {
    "api.binance.com",
    "deno.land",
    "services.swpc.noaa.gov",
}

RETAINED_REQUIRED_FRAGMENTS = {
    "fetch-binance-market-data": (
        "z.string().regex(/^[A-Z]+USDT$/",
        "https://api.binance.com/api/v3/ticker/24hr",
        "https://api.binance.com/api/v3/avgPrice",
        "https://api.binance.com/api/v3/depth",
        "https://api.binance.com/api/v3/trades",
    ),
    "fetch-binance-symbols": (
        "https://api.binance.com/api/v3/exchangeInfo",
        "https://api.binance.com/api/v3/ticker/24hr",
    ),
    "fetch-historical-data": (
        "https://api.binance.com/api/v3/klines",
        "Math.min(limit, 1000)",
    ),
    "fetch-noaa-space-weather": (
        'truthStatus: "live"',
        'sourceId: "noaa_swpc"',
        "liveProvenance(",
        "derivedProvenance(",
        'response.headers.get("Last-Modified")',
        "requireFreshTimestamp(lastModified",
        "TELEMETRY_TTL_MS",
        "generatedValues: false",
    ),
    "fetch-schumann-data": (
        "truthStatus: 'real_derived'",
        "sourceTimestamp",
        "freshnessTtlSeconds",
        "generatedValues: false",
        "not a direct station measurement",
    ),
}


def _load_inventory(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("inventory must be a JSON object")
    return payload


def _config(repo_root: Path) -> dict[str, Any]:
    return tomllib.loads(
        (repo_root / "supabase" / "config.toml").read_text(encoding="utf-8")
    )


def audit(
    repo_root: Path = DEFAULT_REPO_ROOT,
    inventory_path: Path = DEFAULT_INVENTORY,
) -> dict[str, Any]:
    payload = _load_inventory(inventory_path)
    rows = payload.get("functions")
    if not isinstance(rows, list):
        raise ValueError("inventory.functions must be an array")

    errors: list[str] = []
    slugs = [row.get("slug") for row in rows if isinstance(row, dict)]
    if len(rows) != 100:
        errors.append(f"expected 100 active functions, found {len(rows)}")
    if len(slugs) != len(set(slugs)):
        errors.append("production slugs are not unique")
    if any(not isinstance(slug, str) or not slug for slug in slugs):
        errors.append("every production row must have a non-empty slug")
    scope = payload.get("scope", {})
    if not isinstance(scope, dict):
        errors.append("inventory scope must be an object")
        scope = {}
    if scope.get("production_verify_jwt_true_count") != 54:
        errors.append("provider JWT-enabled count drifted from the read-back")
    if scope.get("production_verify_jwt_false_count") != 46:
        errors.append("provider JWT-disabled count drifted from the read-back")
    if payload.get("production_bundle_classification_counts") != (
        EXPECTED_BUNDLE_CLASSIFICATION_COUNTS
    ):
        errors.append("production bundle classification is incomplete or drifted")
    if sum(EXPECTED_BUNDLE_CLASSIFICATION_COUNTS.values()) != len(rows):
        errors.append("production bundle classifications do not cover all rows")

    retained = {
        row["slug"]
        for row in rows
        if isinstance(row, dict)
        and row.get("disposition") == "retained_public_read_only"
    }
    retired = {
        row["slug"]
        for row in rows
        if isinstance(row, dict) and row.get("disposition") == "retired"
    }
    if retained != EXPECTED_RETAINED:
        errors.append(
            "retained public-data set drifted: "
            + ",".join(sorted(retained ^ EXPECTED_RETAINED))
        )
    if len(retired) != 95:
        errors.append(f"expected 95 retired functions, found {len(retired)}")
    if retained & retired or retained | retired != set(slugs):
        errors.append("every active slug must have exactly one disposition")

    if payload.get("retirement_deploy_targets") != sorted(retired):
        errors.append("retirement_deploy_targets does not equal retired inventory")
    hardened_public = {
        "fetch-binance-market-data",
        "fetch-noaa-space-weather",
        "fetch-schumann-data",
    }
    if payload.get("retained_hardening_deploy_targets") != sorted(hardened_public):
        errors.append("retained_hardening_deploy_targets drifted")
    expected_all_deploy = sorted(retired | hardened_public)
    if payload.get("all_deploy_targets") != expected_all_deploy:
        errors.append("all_deploy_targets is not the exact retirement plus hardening set")

    configured = _config(repo_root).get("functions", {})
    if not isinstance(configured, dict):
        errors.append("supabase/config.toml has no functions table")
        configured = {}

    checked_retired = 0
    checked_retained = 0
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("slug"), str):
            continue
        slug = row["slug"]
        source_path = repo_root / "supabase" / "functions" / slug / "index.ts"
        if not source_path.is_file():
            errors.append(f"{slug}: local source missing")
            continue
        source = source_path.read_text(encoding="utf-8")
        source_sha256 = hashlib.sha256(source_path.read_bytes()).hexdigest()
        if row.get("target_source_sha256") != source_sha256:
            errors.append(f"{slug}: target source hash drifted")
        section = configured.get(slug, {})
        if not isinstance(section, dict):
            section = {}
        configured_jwt = section.get("verify_jwt", True)
        if configured_jwt is not row.get("target_verify_jwt"):
            errors.append(f"{slug}: target verify_jwt differs from config")

        if slug in retired:
            checked_retired += 1
            if configured_jwt is not True:
                errors.append(f"{slug}: retired route does not pin verify_jwt=true")
            if not any(marker in source for marker in INERT_MARKERS):
                errors.append(f"{slug}: retired source has no recognized inert marker")
            if "status: 503" not in source and "status: 410" not in source:
                errors.append(f"{slug}: retired source lacks an inert HTTP status")
            if "Cache-Control" not in source or "no-store" not in source:
                errors.append(f"{slug}: retired source lacks no-store response policy")
            for fragment in FORBIDDEN_RETIRED_FRAGMENTS:
                if fragment in source:
                    errors.append(f"{slug}: retired source regained {fragment}")
        elif slug in retained:
            checked_retained += 1
            for fragment in FORBIDDEN_RETAINED_FRAGMENTS:
                if fragment in source:
                    errors.append(f"{slug}: retained public source contains {fragment}")
            hosts = set(
                re.findall(r"https://([A-Za-z0-9.-]+)", source)
            )
            unreviewed_hosts = hosts - ALLOWED_RETAINED_HOSTS
            if unreviewed_hosts:
                errors.append(
                    f"{slug}: unreviewed outbound hosts "
                    + ",".join(sorted(unreviewed_hosts))
                )
            for fragment in RETAINED_REQUIRED_FRAGMENTS[slug]:
                if fragment not in source:
                    errors.append(f"{slug}: required evidence fragment missing: {fragment}")

    inactive = payload.get("inactive_local_routes_retired_to_prevent_redeployment", [])
    if not isinstance(inactive, list):
        errors.append("inactive retirement list must be an array")
        inactive = []
    for slug in inactive:
        source_path = repo_root / "supabase" / "functions" / slug / "index.ts"
        if not source_path.is_file():
            errors.append(f"{slug}: inactive retired source missing")
            continue
        source = source_path.read_text(encoding="utf-8")
        if "LEGACY_GLOBAL_PRIVILEGED_ROUTE_DISABLED" not in source:
            errors.append(f"{slug}: inactive dangerous route is not a standard stub")
        for fragment in FORBIDDEN_RETIRED_FRAGMENTS:
            if fragment in source:
                errors.append(f"{slug}: inactive retired source regained {fragment}")
        section = configured.get(slug, {})
        if not isinstance(section, dict) or section.get("verify_jwt", True) is not True:
            errors.append(f"{slug}: inactive retired route does not pin verify_jwt=true")

    expected_shared = payload.get("shared_source_sha256", {})
    if not isinstance(expected_shared, dict):
        errors.append("shared source hash map must be an object")
    else:
        for relative_path, expected_hash in expected_shared.items():
            shared_path = repo_root / relative_path
            if not shared_path.is_file():
                errors.append(f"{relative_path}: shared source missing")
                continue
            actual_hash = hashlib.sha256(shared_path.read_bytes()).hexdigest()
            if actual_hash != expected_hash:
                errors.append(f"{relative_path}: shared source hash drifted")

    return {
        "schema": "aureon.supabase.production_edge_attack_surface_audit.v1",
        "offline": True,
        "active_count": len(rows),
        "retired_checked": checked_retired,
        "retained_checked": checked_retained,
        "inactive_retirements_checked": len(inactive),
        "errors": errors,
        "ok": not errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=DEFAULT_REPO_ROOT)
    parser.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY)
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args()
    result = audit(args.repo_root.resolve(), args.inventory.resolve())
    print(json.dumps(result, indent=None if args.compact else 2, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
