"""
Aureon Operator — connections logic (view · readiness · probe · set).
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Pure-ish helpers behind the ``/api/connections`` surface, kept out of the Flask
module so they're unit-testable. Secrets are always masked on the way out; the
raw key only ever travels inward (set/test).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Mapping
from urllib.parse import urlsplit

from aureon.observer.live_data_policy import simulation_fallback_allowed
from aureon.observer.real_data_contract import TRUTH_STATUSES, load_source_registry
from aureon.operator import keystore
from aureon.operator.connections_catalog import CATEGORIES, Connection, get_connection
from aureon.operator.identity import build_runtime_context
from aureon.operator.tenant_exchange_probe import (
    EXCHANGE_CREDENTIAL_FIELDS,
    MAX_CREDENTIAL_BYTES,
    TenantExchangeProbe,
)

_RUNTIME_STATUS = Path(__file__).resolve().parents[2] / "state" / "unified_runtime_status.json"
_REPO_ROOT = Path(__file__).resolve().parents[2]
_REAL_SOURCE_PROBE_REPORTS = (
    _REPO_ROOT / "state" / "real_source_probe.json",
    _REPO_ROOT / "docs" / "audits" / "aureon_real_source_probe.json",
)
_CLOUD_EXECUTOR_VENUES = frozenset({"alpaca", "binance", "capital", "kraken"})
_HEX64 = re.compile(r"[0-9a-f]{64}")
CLOUD_EXCHANGE_CREDENTIALS_PINNED_ENV = "AUREON_CLOUD_EXCHANGE_CREDENTIALS_PINNED"
PINNED_CLOUD_SECRET_ERROR_ID = "PINNED_CLOUD_SECRET_READ_ONLY"
PINNED_CLOUD_SECRET_REASON = (
    "Managed by a pinned cloud secret. Update the pinned Secret Manager version "
    "and redeploy to change this owner configuration."
)
GENERIC_PROBE_MAX_TIMEOUT_SECONDS = 10.0


class ConnectionPayloadError(ValueError):
    """Stable request/store shape failure; never contains a credential value."""


def _credential_text(value: Any, *, allow_empty: bool = True) -> str:
    if not isinstance(value, str):
        raise ConnectionPayloadError("connection_credential_malformed")
    try:
        raw = value.encode("utf-8", errors="strict")
    except UnicodeError:
        raise ConnectionPayloadError("connection_credential_malformed") from None
    if (
        len(raw) > MAX_CREDENTIAL_BYTES
        or b"\x00" in raw
        or b"\r" in raw
        or b"\n" in raw
        or (not allow_empty and not raw)
    ):
        raise ConnectionPayloadError("connection_credential_malformed")
    return value.strip()


def validate_connection_payload(
    conn: Connection,
    body: Mapping[str, Any],
    *,
    operation: str,
) -> Dict[str, Any]:
    """Accept only the catalog-declared credential slots for one connection."""

    if not isinstance(body, Mapping):
        raise ConnectionPayloadError("connection_payload_object_required")
    allowed = {"api_key", "extra"}
    if operation == "save":
        allowed.add("enabled")
    elif operation != "test":
        raise ConnectionPayloadError("connection_operation_invalid")
    if not all(isinstance(key, str) for key in body) or set(body) - allowed:
        raise ConnectionPayloadError("connection_payload_fields_invalid")

    result: Dict[str, Any] = {}
    if "api_key" in body:
        if not conn.key_env:
            raise ConnectionPayloadError("connection_primary_credential_not_declared")
        result["api_key"] = _credential_text(body["api_key"])
    if "extra" in body:
        raw_extra = body["extra"]
        if not isinstance(raw_extra, Mapping):
            raise ConnectionPayloadError("connection_extra_credentials_invalid")
        if (
            not all(isinstance(key, str) for key in raw_extra)
            or set(raw_extra) - set(conn.extra_envs)
        ):
            raise ConnectionPayloadError("connection_extra_credentials_invalid")
        result["extra"] = {
            name: _credential_text(value)
            for name, value in raw_extra.items()
        }
    if "enabled" in body:
        if type(body["enabled"]) is not bool:
            raise ConnectionPayloadError("connection_enabled_invalid")
        result["enabled"] = body["enabled"]
    return result


def validate_stored_connection_entry(
    conn: Connection, store: Mapping[str, Any]
) -> Dict[str, Any]:
    raw = store.get(conn.id, {})
    if not isinstance(raw, Mapping):
        raise ConnectionPayloadError("connection_credential_store_invalid")
    primary = raw.get("api_key", "")
    if not isinstance(primary, str):
        raise ConnectionPayloadError("connection_credential_store_invalid")
    extra = raw.get("extra", {}) or {}
    if (
        not isinstance(extra, Mapping)
        or not all(isinstance(key, str) for key in extra)
        or set(extra) - set(conn.extra_envs)
        or any(not isinstance(value, str) for value in extra.values())
    ):
        raise ConnectionPayloadError("connection_credential_store_invalid")
    try:
        clean_primary = _credential_text(primary)
        clean_extra = {name: _credential_text(value) for name, value in extra.items()}
    except ConnectionPayloadError:
        raise ConnectionPayloadError("connection_credential_store_invalid") from None
    return {"api_key": clean_primary, "extra": clean_extra}


def exchange_credential_values(
    conn: Connection,
    payload: Mapping[str, Any],
    store: Mapping[str, Any],
) -> Dict[str, str]:
    """Resolve one tenant's exact exchange fields with no instance-env fallback."""

    expected = EXCHANGE_CREDENTIAL_FIELDS.get(conn.id)
    if conn.category != "exchange" or expected is None or tuple(conn.credential_env) != expected:
        raise ConnectionPayloadError("exchange_credential_catalog_invalid")
    stored = validate_stored_connection_entry(conn, store)
    primary = payload.get("api_key", stored["api_key"])
    extra = dict(stored["extra"])
    extra.update(payload.get("extra", {}))
    values: Dict[str, str] = {}
    if primary:
        values[conn.key_env] = primary
    for name in conn.extra_envs:
        if extra.get(name):
            values[name] = extra[name]
    return values


def credential_management(provider_id: str, *, tenant: str | None,
                          category: str | None = None) -> Dict[str, Any]:
    """Describe the effective write authority for one credential row."""
    if tenant is not None:
        return {
            "credential_scope": "account",
            "credential_management": "account_keystore",
            "credential_writable": True,
            "credential_management_reason": "",
        }
    resolved_category = category
    if resolved_category is None:
        conn = get_connection(provider_id)
        resolved_category = conn.category if conn is not None else "ai_llm"
    pinned = bool(keystore.protected_provider_fields(provider_id))
    if resolved_category == "exchange":
        pinned = pinned or os.environ.get(CLOUD_EXCHANGE_CREDENTIALS_PINNED_ENV) == "1"
    if pinned:
        return {
            "credential_scope": "instance",
            "credential_management": "pinned_cloud_secret",
            "credential_writable": False,
            "credential_management_reason": PINNED_CLOUD_SECRET_REASON,
        }
    return {
        "credential_scope": "instance",
        "credential_management": "instance_configuration",
        "credential_writable": True,
        "credential_management_reason": "",
    }


def _account_real_data_policy_summary() -> Dict[str, Any]:
    """Return the tenant policy without reading instance probe files or env.

    A tenant's connection readiness used to include the owner's global probe
    counts and local report path.  Those values describe the instance runtime,
    not the signed-in account.  Until account-scoped probes exist, report an
    explicit held/no-observation state.
    """
    return {
        "simulation_fallback_allowed": False,
        "truth_statuses": sorted(TRUTH_STATUSES),
        "source_registry_count": 0,
        "probe_summary": {
            "live": 0,
            "real_derived": 0,
            "cached_real": 0,
            "no_data": 0,
            "test_fixture": 0,
            "operational_ready": 0,
            "blocked": 1,
        },
        "probe_report_path": "",
        "probe_report_status": "account_unprobed",
    }


def _current_executor_authentication(control: Mapping[str, Any] | None) -> Dict[str, Any] | None:
    """Return only current, signed and internally consistent executor auth evidence.

    This is deliberately separate from local/tenant key presence: the isolated cloud
    executor may authenticate with a Secret Manager version that must never be copied
    into the UI process or counted as a browser-visible key.
    """
    if not isinstance(control, Mapping) or control.get("schema") != "aureon.operator.cloud-trading-control.v1":
        return None
    if control.get("read_state") != "observed":
        return None
    capabilities = control.get("capabilities")
    probe = control.get("last_probe")
    if (not isinstance(capabilities, Mapping)
            or capabilities.get("all_four_provider_readback_pinned") is not True
            or not isinstance(probe, Mapping) or probe.get("current") is not True):
        return None
    provider = probe.get("provider_readback")
    providers = provider.get("providers") if isinstance(provider, Mapping) else None
    if (not isinstance(provider, Mapping) or set(provider) != {
                "provider_count", "all_authenticated", "instrument_preflight_enforced",
                "provider_accounts_sha256", "execution_budget_readiness_sha256",
                "readback_sha256", "providers",
            }
            or provider.get("provider_count") != 4
            or provider.get("all_authenticated") is not True
            or provider.get("instrument_preflight_enforced") is not True
            or not isinstance(providers, Mapping) or set(providers) != _CLOUD_EXECUTOR_VENUES):
        return None
    clean: Dict[str, Dict[str, Any]] = {}
    for venue, raw in providers.items():
        if (not isinstance(raw, Mapping) or set(raw) != {
                    "authenticated", "account_binding_sha256",
                }
                or raw.get("authenticated") is not True
                or not isinstance(raw.get("account_binding_sha256"), str)
                or _HEX64.fullmatch(raw["account_binding_sha256"]) is None):
            return None
        clean[str(venue)] = {
            "authenticated": True,
            "account_binding_sha256": raw["account_binding_sha256"],
        }
    # The signed executor hashes rows that include the venue. The collector removes
    # that redundant field from the UI projection while preserving the account and
    # execution-budget commitments needed to recompute the composite binding.
    digest_rows = {venue: {"venue": venue, **row} for venue, row in clean.items()}
    expected_accounts = hashlib.sha256(json.dumps(
        digest_rows, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode()).hexdigest()
    provider_accounts_sha256 = provider.get("provider_accounts_sha256")
    execution_budget_readiness_sha256 = provider.get("execution_budget_readiness_sha256")
    readback_sha256 = provider.get("readback_sha256")
    if (provider_accounts_sha256 != expected_accounts
            or not isinstance(execution_budget_readiness_sha256, str)
            or _HEX64.fullmatch(execution_budget_readiness_sha256) is None
            or not isinstance(readback_sha256, str)
            or _HEX64.fullmatch(readback_sha256) is None):
        return None
    expected_readback = hashlib.sha256(json.dumps({
        "schema": "aureon.cloud-trade-provider-readback-commitment.v1",
        "provider_accounts_sha256": provider_accounts_sha256,
        "execution_budget_readiness_sha256": execution_budget_readiness_sha256,
    }, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
    if readback_sha256 != expected_readback:
        return None
    received_at = probe.get("received_at")
    if not isinstance(received_at, (int, float)) or isinstance(received_at, bool):
        return None
    return {
        "providers": clean,
        "received_at": float(received_at),
        "readback_sha256": readback_sha256,
    }


# ── credential presence (keystore first, then env / aliases) ──────────────────

# ``allow_env`` is the tenancy switch. ``os.environ`` holds the INSTANCE's credentials, so a tenant
# view must never consult it: otherwise a signed-in end user enumerates which of the operator's
# exchange keys exist, where each comes from, and its last 4 characters. Default True keeps the
# admin / single-operator view byte-for-byte unchanged.

def _key_source(conn: Connection, store: Dict[str, Any], *, allow_env: bool = True) -> str:
    if store.get(conn.id, {}).get("api_key"):
        return "keystore"
    if allow_env and conn.key_env and os.environ.get(conn.key_env, "").strip():
        return "env"
    return "none"


def _key_masked(conn: Connection, store: Dict[str, Any], *, allow_env: bool = True) -> str:
    stored = store.get(conn.id, {}).get("api_key")
    if stored:
        return keystore.mask(stored)
    if not allow_env:
        return ""
    envv = os.environ.get(conn.key_env, "") if conn.key_env else ""
    return keystore.mask(envv) if envv else ""


def _has_key(conn: Connection, store: Dict[str, Any], *, allow_env: bool = True) -> bool:
    if conn.requirement == "keyless":
        return True
    return _key_source(conn, store, allow_env=allow_env) != "none"


def _exchange_ready() -> Dict[str, bool]:
    """Best-effort read of the trader's runtime status (exchanges.*_ready)."""
    try:
        data = json.loads(_RUNTIME_STATUS.read_text(encoding="utf-8"))
        ex = data.get("exchanges", {}) or {}
        return {k.replace("_ready", ""): bool(v) for k, v in ex.items() if k.endswith("_ready")}
    except Exception:  # noqa: BLE001 — status file optional
        return {}


def _real_data_policy_summary() -> Dict[str, Any]:
    summary: Dict[str, Any] = {
        "simulation_fallback_allowed": simulation_fallback_allowed(),
        "truth_statuses": sorted(TRUTH_STATUSES),
        "source_registry_count": 0,
        "probe_summary": {
            "live": 0,
            "real_derived": 0,
            "cached_real": 0,
            "no_data": 0,
            "test_fixture": 0,
            "operational_ready": 0,
            "blocked": 0,
        },
        "probe_report_path": "",
        "probe_report_status": "missing",
    }
    try:
        registry = load_source_registry(_REPO_ROOT)
        sources = registry.get("sources", {})
        summary["source_registry_count"] = len(sources) if isinstance(sources, dict) else 0
    except Exception as exc:  # noqa: BLE001
        summary["source_registry_error"] = str(exc)[:160]

    for path in _REAL_SOURCE_PROBE_REPORTS:
        if not path.exists():
            continue
        try:
            report = json.loads(path.read_text(encoding="utf-8", errors="replace"))
            probe_summary = report.get("summary") if isinstance(report, dict) else {}
            if isinstance(probe_summary, dict):
                summary["probe_summary"].update(
                    {key: int(probe_summary.get(key, 0) or 0) for key in summary["probe_summary"]}
                )
            summary["probe_report_path"] = str(path)
            summary["probe_report_status"] = "loaded"
            break
        except Exception as exc:  # noqa: BLE001
            summary["probe_report_path"] = str(path)
            summary["probe_report_status"] = f"unreadable:{type(exc).__name__}"
            break
    return summary


def connection_public(conn: Connection, store: Dict[str, Any], ready: Dict[str, bool],
                      *, allow_env: bool = True,
                      executor_auth: Mapping[str, Any] | None = None,
                      tenant: str | None = None) -> Dict[str, Any]:
    management = credential_management(
        conn.id,
        tenant=tenant,
        category=conn.category,
    )
    receipt_managed_exchange = (
        conn.category == "exchange"
        and management["credential_management"] == "pinned_cloud_secret"
    )
    local_env_allowed = allow_env and not receipt_managed_exchange
    effective_store = (
        {key: value for key, value in store.items() if key != conn.id}
        if management["credential_management"] == "pinned_cloud_secret"
        else store
    )
    entry = effective_store.get(conn.id, {})
    d = conn.to_public_dict()
    d.update({
        "has_key": _has_key(conn, effective_store, allow_env=local_env_allowed),
        "key_masked": _key_masked(conn, effective_store, allow_env=local_env_allowed),
        "key_source": _key_source(conn, effective_store, allow_env=local_env_allowed),
        "enabled": bool(entry.get("enabled", True)) if entry else (conn.requirement == "keyless"),
        "extra_masked": {k: keystore.mask(v) for k, v in (entry.get("extra") or {}).items()},
        **management,
        "probe_scope": "credential" if conn.probe_auth != "none" else "public_endpoint",
    })
    if conn.category == "exchange":
        d["runtime_ready"] = ready.get(conn.id)
        provider = executor_auth.get("providers", {}).get(conn.id) if executor_auth else None
        d["executor_authenticated"] = bool(
            isinstance(provider, Mapping) and provider.get("authenticated") is True
        )
        if d["executor_authenticated"]:
            d["executor_evidence_received_at"] = executor_auth.get("received_at")
            d["executor_readback_sha256"] = executor_auth.get("readback_sha256")
    return d


# ── the unified categorized view ──────────────────────────────────────────────

def build_view(llm_providers: List[Dict[str, Any]], *, tenant: str | None = None,
               executor_control: Mapping[str, Any] | None = None) -> Dict[str, Any]:
    """Categorized connections. ``llm_providers`` is the operator's LLM provider
    view (from providers_list); everything else comes from the catalog.

    ``tenant`` scopes the non-LLM half to that user's isolated store. The LLM half was already
    per-tenant via ``_provider_view(tenant)``; this closes the same gap for the exchange / data-source
    rows, which is where the real money keys are. Under a tenant, ``os.environ`` is not consulted and
    the instance's exchange runtime readiness is withheld — both describe the instance, not the user.
    """
    store = keystore.load(tenant=tenant)
    allow_env = tenant is None
    ready = _exchange_ready() if tenant is None else {}
    executor_auth = _current_executor_authentication(executor_control) if tenant is None else None
    llm_rows = [{
        "id": p["id"], "label": p["label"], "category": "ai_llm",
        "requirement": "optional", "consumed_by": "operator",
        "has_key": p["has_key"], "key_masked": p["key_masked"], "key_source": p["key_source"],
        "enabled": p["enabled"], "connected": p.get("live"),
        **credential_management(p["id"], tenant=tenant, category="ai_llm"),
        "unlocks": "LLM model for the operator switchboard",
        "get_keys_url": p.get("get_keys_url", ""), "docs_url": p.get("docs_url", ""),
    } for p in llm_providers]

    sections = []
    for cat_id, cat_label in CATEGORIES:
        if cat_id == "ai_llm":
            items = llm_rows
        else:
            items = [connection_public(
                c, store, ready, allow_env=allow_env, executor_auth=executor_auth,
                tenant=tenant,
            ) for c in _by_cat(cat_id)]
        sections.append({"category": cat_id, "label": cat_label, "connections": items})
    return {
        "runtime_context": build_runtime_context(is_admin=tenant is None),
        "categories": sections,
    }


def _by_cat(cat_id: str) -> List[Connection]:
    from aureon.operator.connections_catalog import CATALOG

    return [c for c in CATALOG if c.category == cat_id]


# ── full operational-capacity readiness (presence only, no network) ───────────

def readiness(llm_providers: List[Dict[str, Any]], *, tenant: str | None = None,
              executor_control: Mapping[str, Any] | None = None) -> Dict[str, Any]:
    """Presence-only readiness. ``tenant`` scopes it to that user's store (see :func:`build_view`)."""
    store = keystore.load(tenant=tenant)
    allow_env = tenant is None
    executor_auth = _current_executor_authentication(executor_control) if tenant is None else None
    items: List[Dict[str, Any]] = []

    for p in llm_providers:
        items.append({
            "id": p["id"], "label": p["label"], "category": "ai_llm",
            "requirement": "optional", "present": bool(p["has_key"]),
            "unlocks": "LLM model for the switchboard", "get_keys_url": p.get("get_keys_url", ""),
        })
    from aureon.operator.connections_catalog import CATALOG

    for c in CATALOG:
        management = credential_management(c.id, tenant=tenant, category=c.category)
        receipt_managed_exchange = (
            c.category == "exchange"
            and management["credential_management"] == "pinned_cloud_secret"
        )
        effective_store = (
            {key: value for key, value in store.items() if key != c.id}
            if management["credential_management"] == "pinned_cloud_secret"
            else store
        )
        executor_provider = (
            executor_auth.get("providers", {}).get(c.id)
            if executor_auth is not None and c.category == "exchange"
            else None
        )
        executor_present = bool(
            isinstance(executor_provider, Mapping)
            and executor_provider.get("authenticated") is True
        )
        local_present = _has_key(
            c,
            effective_store,
            allow_env=allow_env and not receipt_managed_exchange,
        )
        items.append({
            "id": c.id, "label": c.label, "category": c.category,
            "requirement": c.requirement,
            "present": local_present or executor_present,
            "presence_basis": (
                "signed_executor_readback"
                if executor_present
                else "credential_inventory"
                if local_present
                else "unavailable"
            ),
            "unlocks": c.unlocks, "get_keys_url": c.get_keys_url,
        })

    def _count(req: str):
        rows = [i for i in items if i["requirement"] == req]
        return sum(1 for i in rows if i["present"]), len(rows)

    req_present, req_total = _count("required")
    opt_present, opt_total = _count("optional")
    keyless_total = sum(1 for i in items if i["requirement"] == "keyless")
    missing = [i for i in items if i["requirement"] != "keyless" and not i["present"]]
    keyed_total = req_total + opt_total
    keyed_present = req_present + opt_present
    capacity_pct = round(100 * keyed_present / keyed_total) if keyed_total else 100
    executor_authenticated = len(executor_auth["providers"]) if executor_auth else 0
    owner_instance = tenant is None
    credential_core_ready = req_present == req_total
    credential_inventory_complete = len(missing) == 0
    executor_evidence_current = bool(
        owner_instance
        and executor_authenticated == len(_CLOUD_EXECUTOR_VENUES)
    )
    real_data_policy = (
        _real_data_policy_summary()
        if owner_instance
        else _account_real_data_policy_summary()
    )
    # required-gap = the system can't run its core without these (currently none);
    # all_connected = every enrichment key also present → true full capacity.
    return {
        "runtime_context": build_runtime_context(is_admin=tenant is None),
        "summary": {
            "required_present": req_present, "required_total": req_total,
            "optional_present": opt_present, "optional_total": opt_total,
            "keyless": keyless_total,
            "keyed_present": keyed_present, "keyed_total": keyed_total,
            "capacity_pct": capacity_pct,
            "credential_core_ready": credential_core_ready,
            "credential_inventory_complete": credential_inventory_complete,
            # A tenant inventory is useful setup evidence, but its runtime is
            # held and unprobed.  Never translate key presence into a claim that
            # the owner's core or connections are ready.
            "core_ready": credential_core_ready if owner_instance else False,
            "all_connected": credential_inventory_complete if owner_instance else False,
            "missing_count": len(missing),
            "executor_authenticated": executor_authenticated,
            "executor_provider_total": len(_CLOUD_EXECUTOR_VENUES) if owner_instance else 0,
            "executor_evidence_current": executor_evidence_current,
            "operational_ready": None if owner_instance else False,
            "readiness_basis": "instance_evidence" if owner_instance else "account_credentials_only",
            "real_data_policy": real_data_policy,
        },
        "missing": missing,
        "items": items,
    }


# ── connectivity probes (real outbound; never raise or echo transport text) ──

def probe(conn: Connection, api_key: str = "", timeout: float = 8.0) -> Dict[str, Any]:
    """Probe a catalog endpoint without following redirects or ambient proxies.

    This generic path deliberately consumes no response body. Credential-bearing
    URLs and headers therefore cannot be reflected by a provider body, redirect,
    proxy error or exception string. Exchange credentials use the stricter
    authenticated adapters below instead of their catalog's public ping URL.
    """
    if not conn.probe_url:
        return {"ok": False, "http_status": 0, "latency_ms": 0,
                "error": "probe_endpoint_unavailable", "reason_code": "probe_endpoint_unavailable"}
    if conn.requirement != "keyless" and conn.probe_auth != "none" and not api_key:
        return {"ok": False, "http_status": 0, "latency_ms": 0,
                "error": "no key to test", "reason_code": "probe_credential_missing"}
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not 0.1 <= float(timeout) <= GENERIC_PROBE_MAX_TIMEOUT_SECONDS:
        return {"ok": False, "http_status": 0, "latency_ms": 0,
                "error": "probe_timeout_invalid", "reason_code": "probe_timeout_invalid"}
    try:
        parsed = urlsplit(conn.probe_url)
        port = parsed.port
    except (TypeError, ValueError):
        parsed = None
        port = None
    if (
        parsed is None
        or parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or port not in {None, 443}
        or bool(parsed.fragment)
    ):
        return {"ok": False, "http_status": 0, "latency_ms": 0,
                "error": "probe_endpoint_denied", "reason_code": "probe_endpoint_denied"}
    session = None
    response = None
    t0 = time.perf_counter()
    try:
        import requests

        headers: Dict[str, str] = {}
        params: Dict[str, str] = {}
        if api_key and conn.probe_auth == "header" and conn.probe_header:
            headers[conn.probe_header] = api_key
        elif api_key and conn.probe_auth == "bearer":
            headers["Authorization"] = f"Bearer {api_key}"
        elif api_key and conn.probe_auth == "query":
            params[conn.probe_query_param] = api_key
        session = requests.Session()
        session.trust_env = False
        response = session.get(
            conn.probe_url,
            headers=headers,
            params=params or None,
            timeout=float(timeout),
            allow_redirects=False,
            stream=True,
        )
        elapsed = int((time.perf_counter() - t0) * 1000)
        status = getattr(response, "status_code", None)
        if type(status) is not int:
            return {"ok": False, "http_status": 0, "latency_ms": elapsed,
                    "error": "probe_response_invalid", "reason_code": "probe_response_invalid"}
        if 300 <= status < 400:
            return {"ok": False, "http_status": status, "latency_ms": elapsed,
                    "error": "probe_redirect_denied", "reason_code": "probe_redirect_denied"}
        ok = 200 <= status < 300
        reason = "" if ok else "probe_http_error"
        return {"ok": ok, "http_status": status, "latency_ms": elapsed,
                "error": reason, "reason_code": "probe_succeeded" if ok else reason}
    except Exception:  # noqa: BLE001 — exception text may contain a credential-bearing URL
        return {"ok": False, "http_status": 0, "latency_ms": 0,
                "error": "probe_transport_unavailable", "reason_code": "probe_transport_unavailable"}
    finally:
        if response is not None:
            try:
                response.close()
            except Exception:  # noqa: BLE001
                pass
        if session is not None:
            try:
                session.close()
            except Exception:  # noqa: BLE001
                pass


def probe_tenant_exchange(
    conn: Connection,
    *,
    payload: Mapping[str, Any],
    store: Mapping[str, Any],
    exchange_probe: TenantExchangeProbe | None = None,
) -> Dict[str, Any]:
    """Authenticate only the supplied tenant's catalog-declared credentials."""

    try:
        values = exchange_credential_values(conn, payload, store)
    except ConnectionPayloadError as exc:
        reason = str(exc)
        return {
            "ok": False,
            "authenticated": False,
            "http_status": 0,
            "latency_ms": 0,
            "error": reason,
            "reason_code": reason,
            "probe_scope": "credential",
            "provider_mutation_attempted": False,
        }
    return (exchange_probe or TenantExchangeProbe()).authenticate(conn.id, values)


def probe_owner_exchange_receipt(
    conn: Connection,
    executor_control: Mapping[str, Any] | None,
) -> Dict[str, Any]:
    """Project the signed executor auth receipt; never load UI-process keys."""

    current = _current_executor_authentication(executor_control)
    provider = current.get("providers", {}).get(conn.id) if current else None
    authenticated = bool(isinstance(provider, Mapping) and provider.get("authenticated") is True)
    reason = "exchange_authenticated_by_cloud_executor" if authenticated else "cloud_executor_authentication_receipt_unavailable"
    result: Dict[str, Any] = {
        "ok": authenticated,
        "authenticated": authenticated,
        "http_status": 200 if authenticated else 0,
        "latency_ms": 0,
        "error": "" if authenticated else reason,
        "reason_code": reason,
        "probe_scope": "signed_cloud_executor_receipt",
        "provider_mutation_attempted": False,
    }
    if authenticated and current is not None:
        result["executor_evidence_received_at"] = current["received_at"]
        result["executor_readback_sha256"] = current["readback_sha256"]
    return result


# ── writing an exchange credential — delegate to the existing .env writer ─────

def set_exchange_credential(conn: Connection, api_key: str, extra: Dict[str, str]) -> Dict[str, Any]:
    """Route exchange keys through the trader's existing .env writer + restart
    intent (never the operator keystore). Returns a status dict."""
    creds: Dict[str, str] = {}
    if api_key and conn.key_env:
        creds[conn.key_env] = api_key
    for var, val in (extra or {}).items():
        if val:
            creds[var] = val
    if not creds:
        return {"ok": False, "error": "no credentials provided"}
    try:
        from aureon.exchanges.unified_market_status_server import (
            _extract_env_updates,
            _record_env_update_intent,
            _write_env_updates,
        )

        updates = _extract_env_updates(conn.id, creds)
        if not updates:
            return {"ok": False, "error": "no recognised credential keys"}
        _write_env_updates(updates)
        _record_env_update_intent(conn.id, list(updates.keys()))
        return {"ok": True, "updated_keys": list(updates.keys()),
                "restart_required": True,
                "note": "written to .env; the trading process picks it up on its next restart"}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"exchange writer unavailable: {type(exc).__name__}: {str(exc)[:120]}"}


__all__ = [
    "build_view",
    "readiness",
    "probe",
    "probe_tenant_exchange",
    "probe_owner_exchange_receipt",
    "connection_public",
    "credential_management",
    "exchange_credential_values",
    "validate_connection_payload",
    "validate_stored_connection_entry",
    "ConnectionPayloadError",
    "set_exchange_credential",
    "CLOUD_EXCHANGE_CREDENTIALS_PINNED_ENV",
    "PINNED_CLOUD_SECRET_ERROR_ID",
    "PINNED_CLOUD_SECRET_REASON",
]
