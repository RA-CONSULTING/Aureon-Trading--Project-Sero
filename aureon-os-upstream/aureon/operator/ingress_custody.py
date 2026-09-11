"""Read-only ingress custody receipt for the local operator boundary.

The receipt describes what the serving HTTP boundary can prove now. It does
not grant release, trading, filing, payment, or provider mutation authority.
"""

from __future__ import annotations

import hashlib
import ipaddress
import json
import os
import time
from datetime import datetime, timezone
from typing import Any, Mapping


def _json_digest(value: Any) -> str:
    body = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(body).hexdigest()


def _is_loopback_host(value: str | None) -> bool:
    host = str(value or "").strip().strip("[]").casefold()
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _bool(value: Any) -> bool:
    return bool(value)


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def build_ingress_custody_receipt(
    *,
    security: Any | None = None,
    jwt_secret_set: bool | None = None,
    request_view: Mapping[str, Any] | None = None,
    boundary_summary: Mapping[str, Any] | None = None,
    host: str | None = None,
    port: int | str | None = None,
    now: float | None = None,
) -> dict[str, Any]:
    if security is None:
        from aureon.operator.security import SecurityConfig

        security = SecurityConfig.from_env()
    observed_at = time.time() if now is None else float(now)
    configured_host = str(host or os.environ.get("AUREON_OPERATOR_HOST", "127.0.0.1") or "127.0.0.1")
    configured_port = int(port or os.environ.get("AUREON_OPERATOR_PORT", "8080") or 8080)
    request_info = dict(_mapping(request_view))
    direct_client = str(request_info.get("direct_client") or "")
    resolved_client = str(request_info.get("resolved_client") or direct_client)
    host_loopback = _is_loopback_host(configured_host)
    client_loopback = _is_loopback_host(direct_client) if direct_client else None
    auth_required = bool(str(getattr(security, "api_key", "") or "").strip() or jwt_secret_set)
    rate_limit_enabled = bool(getattr(security, "rate_enabled", False))
    private_ingress = host_loopback and (client_loopback is not False)
    blockers: list[str] = []
    if not private_ingress:
        blockers.append("operator_ingress_not_loopback_private")
    if not auth_required:
        blockers.append("operator_auth_not_required")
    if not rate_limit_enabled:
        blockers.append("operator_rate_limit_disabled")
    http_security_ready = private_ingress and auth_required and rate_limit_enabled
    boundary = dict(_mapping(boundary_summary))
    durable_custody = (
        boundary.get("production_ready") is True
        and boundary.get("magic_star_durable_custody_attested") is True
        and boundary.get("external_head_anchor_attested") is True
        and boundary.get("local_development_only") is False
    )
    if not durable_custody:
        blockers.append("protected_ingress_durable_custody_unattested")
    production_ingress_ready = http_security_ready and durable_custody
    controls = {
        "host_loopback": host_loopback,
        "client_loopback": client_loopback,
        "auth_required": auth_required,
        "rate_limit_enabled": rate_limit_enabled,
        "rate_rps": float(getattr(security, "rate_rps", 0.0) or 0.0),
        "rate_burst": int(getattr(security, "burst", 0) or 0),
        "max_body_bytes": int(getattr(security, "max_body_bytes", 0) or 0),
        "trusted_proxy_count": len(tuple(getattr(security, "trusted_proxies", ()) or ())),
        "http_processes": int(getattr(security, "http_processes", 0) or 0),
        "replicas": int(getattr(security, "replicas", 0) or 0),
        "mutating_methods_hnc_protected": True,
        "query_driven_effect_gets_hnc_protected": True,
        "ordinary_remote_without_auth_policy": "rejected_before_handler",
        "ordinary_mutation_without_hnc_policy": "quarantined_before_handler",
        "response_cache_policy": "no-store",
    }
    digest_body = {
        "configured_host": configured_host,
        "configured_port": configured_port,
        "environment": str(getattr(security, "environment", "development") or "development"),
        "controls": controls,
        "private_ingress_custody": private_ingress,
        "production_ingress_ready": production_ingress_ready,
        "http_security_ready": http_security_ready,
        "durable_custody_attested": durable_custody,
        "blockers": blockers,
    }
    return {
        "schema": "aureon.operator.ingress-custody.v1",
        "generated_values": False,
        "observed_at": observed_at,
        "observed_at_iso": datetime.fromtimestamp(observed_at, timezone.utc).isoformat().replace("+00:00", "Z"),
        "truth_status": "real_derived",
        "read_state": "observed",
        "available": True,
        "configured_host": configured_host,
        "configured_port": configured_port,
        "environment": str(getattr(security, "environment", "development") or "development"),
        "direct_client": direct_client or None,
        "resolved_client": resolved_client or None,
        "identity_kind": str(request_info.get("identity_kind") or "unavailable"),
        "is_admin": _bool(request_info.get("is_admin")),
        "private_ingress_custody": private_ingress,
        "production_ingress_ready": production_ingress_ready,
        "http_security_ready": http_security_ready,
        "durable_custody_attested": durable_custody,
        "controls": controls,
        "blockers": blockers,
        "boundary": boundary,
        "production_ready": False,
        "release_authority": False,
        "mutation_authority": False,
        "digest_sha256": _json_digest(digest_body),
        "digest_scope": "operator_http_ingress_custody",
    }


__all__ = ["build_ingress_custody_receipt"]
