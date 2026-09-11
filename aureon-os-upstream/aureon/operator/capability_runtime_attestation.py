"""Read-only route binding for current operator capability claims.

This endpoint turns broad UI capability claims into a compact current receipt:
which operator route was read, what non-secret status was observed, and whether
that surface was available. It never grants production authority and never
executes a provider, order, file, payment, or company action.
"""

from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Mapping

SurfaceReader = Callable[[], Mapping[str, Any]]

_CAPABILITY_SURFACES = (
    {
        "id": "operator_status",
        "label": "Operator platform status",
        "route": "/api/status",
        "source": "aureon.saas.status.get_platform_status",
        "evidence": ("truth_status", "status", "product_domains", "process_observation"),
    },
    {
        "id": "company_workforce",
        "label": "Agent company workforce",
        "route": "/api/company",
        "source": "aureon.autonomous.aureon_agent_company_builder + observed_runtime.process_observation",
        "evidence": ("role_count", "department_count", "runtime_verification"),
    },
    {
        "id": "coverage_map",
        "label": "Whole-system coverage map",
        "route": "/api/coverage",
        "source": "aureon.saas.coverage.build_coverage_audit",
        "evidence": ("truth_status", "all_covered", "domains", "coverage_fraction"),
    },
    {
        "id": "feature_switchboard",
        "label": "Feature switchboard",
        "route": "/api/switchboard",
        "source": "aureon.operator.feature_switchboard",
        "evidence": ("groups", "summary", "hard_boundary_total", "armed"),
    },
    {
        "id": "terminal_state",
        "label": "Terminal runtime state",
        "route": "/api/terminal-state",
        "source": "aureon.exchanges.unified_market_status_server._read_status",
        "evidence": ("ok", "stale", "data_ready", "trading_ready", "last_tick_completed_at"),
    },
    {
        "id": "terminal_receipt",
        "label": "Terminal receipt service",
        "route": "/api/operator/terminal-receipt",
        "source": "aureon.operator.legacy_runtime_api._terminal_receipt_payload",
        "evidence": ("schema", "available", "digest_sha256", "mutation_authority"),
    },
    {
        "id": "release_readiness",
        "label": "Production release readiness",
        "route": "/api/operator/release-readiness",
        "source": "aureon.operator.release_readiness.build_operator_release_readiness",
        "evidence": ("schema", "state", "production_ready", "work_orders"),
    },
    {
        "id": "ingress_custody",
        "label": "Operator ingress custody",
        "route": "/api/operator/ingress-custody",
        "source": "aureon.operator.ingress_custody.build_ingress_custody_receipt",
        "evidence": ("schema", "private_ingress_custody", "production_ingress_ready", "controls"),
    },
    {
        "id": "executor_isolation",
        "label": "Executor isolation",
        "route": "/api/operator/executor-isolation",
        "source": "aureon.operator.executor_isolation.build_executor_isolation_receipt",
        "evidence": ("schema", "production_executor_ready", "kill_switch_engaged", "blockers"),
    },
    {
        "id": "authority_map",
        "label": "Independent authority map",
        "route": "/api/operator/authority-map",
        "source": "aureon.operator.authority_map.build_authority_map_receipt",
        "evidence": ("schema", "distinct_authority_roles", "signed_receipt_count", "blockers"),
    },
    {
        "id": "result_binding",
        "label": "Protected result binding",
        "route": "/api/operator/result-binding",
        "source": "aureon.operator.result_binding.build_result_binding_receipt",
        "evidence": ("schema", "protected_result_bound", "correlation_id_available", "blockers"),
    },
    {
        "id": "release_ledger",
        "label": "Durable release ledger",
        "route": "/api/operator/release-ledger",
        "source": "aureon.operator.release_ledger.build_release_ledger_receipt",
        "evidence": ("schema", "available", "chain_valid", "event_count"),
    },
)


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _bounded_int(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value if value <= 9_007_199_254_740_991 else None


def _text(value: Any, default: str = "unavailable") -> str:
    text = str(value or "").strip()
    return text[:160] if text else default


def _json_digest(value: Any) -> str:
    body = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(body).hexdigest()


def _default_readers() -> Dict[str, SurfaceReader]:
    def status() -> Mapping[str, Any]:
        from aureon.saas.status import get_platform_status

        return _mapping(get_platform_status())

    def company() -> Mapping[str, Any]:
        from aureon.autonomous.aureon_agent_company_builder import DEPARTMENTS, _role_specs

        roles = list(_role_specs())
        try:
            from aureon.saas.observed_runtime import process_observation

            process = _mapping(process_observation())
        except Exception as exc:  # noqa: BLE001 - report the read failure, never sink the route
            process = {
                "available": False,
                "fresh": False,
                "read_state": "failed",
                "reason": f"process_observation_failed:{type(exc).__name__}",
            }
        return {
            "truth_status": "real_derived",
            "role_count": len(roles),
            "department_count": len(DEPARTMENTS),
            "runtime_verification": {
                "process_available": process.get("available"),
                "process_fresh": process.get("fresh"),
                "read_state": process.get("read_state"),
                "running_verified": _mapping(process.get("counts")).get("running_verified"),
            },
        }

    def coverage() -> Mapping[str, Any]:
        from aureon.saas.coverage import build_coverage_audit

        return _mapping(build_coverage_audit())

    def switchboard() -> Mapping[str, Any]:
        from aureon.operator import feature_switchboard

        return {
            "groups": feature_switchboard.grouped_view(),
            "summary": feature_switchboard.summary(),
        }

    def terminal_state() -> Mapping[str, Any]:
        from aureon.operator.legacy_runtime_api import _status_handlers

        read_status, _flight, _env = _status_handlers()
        return _mapping(read_status())

    def terminal_receipt() -> Mapping[str, Any]:
        from aureon.operator.legacy_runtime_api import _status_handlers, _terminal_receipt_payload

        read_status, _flight, _env = _status_handlers()
        return _mapping(_terminal_receipt_payload(dict(_mapping(read_status()))))

    def release_readiness() -> Mapping[str, Any]:
        from aureon.operator.release_readiness import build_operator_release_readiness

        return _mapping(build_operator_release_readiness())

    def ingress_custody() -> Mapping[str, Any]:
        from aureon.operator.ingress_custody import build_ingress_custody_receipt

        return _mapping(build_ingress_custody_receipt())

    def executor_isolation() -> Mapping[str, Any]:
        from aureon.operator.executor_isolation import build_executor_isolation_receipt

        return _mapping(build_executor_isolation_receipt())

    def authority_map() -> Mapping[str, Any]:
        from aureon.operator.authority_map import build_authority_map_receipt

        return _mapping(build_authority_map_receipt())

    def result_binding() -> Mapping[str, Any]:
        from aureon.operator.result_binding import build_result_binding_receipt

        return _mapping(build_result_binding_receipt())

    def release_ledger() -> Mapping[str, Any]:
        from aureon.operator.release_ledger import build_release_ledger_receipt

        return _mapping(build_release_ledger_receipt())

    return {
        "operator_status": status,
        "company_workforce": company,
        "coverage_map": coverage,
        "feature_switchboard": switchboard,
        "terminal_state": terminal_state,
        "terminal_receipt": terminal_receipt,
        "release_readiness": release_readiness,
        "ingress_custody": ingress_custody,
        "executor_isolation": executor_isolation,
        "authority_map": authority_map,
        "result_binding": result_binding,
        "release_ledger": release_ledger,
    }


def _project_payload(surface_id: str, payload: Mapping[str, Any]) -> Dict[str, Any]:
    if surface_id == "operator_status":
        domains = _mapping(payload.get("product_domains"))
        process = _mapping(payload.get("process_observation"))
        counts = _mapping(process.get("counts"))
        return {
            "truth_status": _text(payload.get("truth_status"), "no_data"),
            "status": _text(payload.get("status"), "unknown"),
            "domain_count": len(domains),
            "domains_reachable": _bounded_int(payload.get("domains_reachable")),
            "domains_total": _bounded_int(payload.get("domains_total")),
            "running_verified": _bounded_int(counts.get("running_verified")),
        }
    if surface_id == "company_workforce":
        summary = _mapping(payload.get("summary"))
        runtime = _mapping(payload.get("runtime_verification"))
        role_count = _bounded_int(payload.get("role_count")) or _bounded_int(summary.get("role_count"))
        department_count = _bounded_int(payload.get("department_count")) or _bounded_int(summary.get("department_count"))
        return {
            "truth_status": _text(payload.get("truth_status"), "real_derived"),
            "role_count": role_count,
            "department_count": department_count,
            "runtime_state": _text(runtime.get("live_company_operation_state") or runtime.get("read_state"), "observed"),
            "process_available": runtime.get("process_available"),
        }
    if surface_id == "coverage_map":
        domains = payload.get("domains")
        return {
            "truth_status": _text(payload.get("truth_status"), "real_derived"),
            "all_covered": payload.get("all_covered") is True,
            "domain_count": len(domains) if isinstance(domains, list) else 0,
            "coverage_fraction": payload.get("coverage_fraction"),
            "uncovered_count": len(payload.get("uncovered")) if isinstance(payload.get("uncovered"), list) else 0,
        }
    if surface_id == "feature_switchboard":
        summary = _mapping(payload.get("summary"))
        groups = payload.get("groups")
        return {
            "truth_status": "real_derived",
            "group_count": len(groups) if isinstance(groups, list) else 0,
            "flag_count": _bounded_int(summary.get("total")),
            "enabled_count": _bounded_int(summary.get("enabled")),
            "armed_hard_boundaries": _bounded_int(summary.get("armed")),
            "pending_restart": _bounded_int(summary.get("pending_restart")),
        }
    if surface_id == "terminal_state":
        return {
            "truth_status": "real_derived" if payload.get("ok") is True else "no_data",
            "ok": payload.get("ok") is True,
            "stale": payload.get("stale") is True,
            "data_ready": payload.get("data_ready") is True,
            "trading_ready": payload.get("trading_ready") is True,
            "last_tick_completed_at": payload.get("last_tick_completed_at"),
            "source": _text(payload.get("source"), "unknown"),
        }
    if surface_id == "terminal_receipt":
        terminal = _mapping(payload.get("terminal"))
        return {
            "truth_status": _text(payload.get("truth_status"), "unavailable"),
            "schema": _text(payload.get("schema"), "unknown"),
            "available": payload.get("available") is True,
            "terminal_action_mode": _text(terminal.get("action_mode"), "unknown"),
            "execution_authority": terminal.get("execution_authority") is True,
            "mutation_authority": payload.get("mutation_authority") is True,
        }
    if surface_id == "release_readiness":
        work_orders = payload.get("work_orders")
        integrated = 0
        blocking = 0
        if isinstance(work_orders, list):
            for item in work_orders:
                row = _mapping(item)
                if row.get("status") == "integrated":
                    integrated += 1
                else:
                    blocking += 1
        return {
            "truth_status": "real_derived",
            "schema": _text(payload.get("schema"), "unknown"),
            "state": _text(payload.get("state"), "unknown"),
            "production_ready": payload.get("production_ready") is True,
            "release_available": payload.get("release_available") is True,
            "work_order_count": len(work_orders) if isinstance(work_orders, list) else 0,
            "integrated_work_orders": integrated,
            "blocking_work_orders": blocking,
        }
    if surface_id == "ingress_custody":
        controls = _mapping(payload.get("controls"))
        blockers = payload.get("blockers")
        return {
            "truth_status": _text(payload.get("truth_status"), "real_derived"),
            "schema": _text(payload.get("schema"), "unknown"),
            "private_ingress_custody": payload.get("private_ingress_custody") is True,
            "production_ingress_ready": payload.get("production_ingress_ready") is True,
            "auth_required": controls.get("auth_required") is True,
            "rate_limit_enabled": controls.get("rate_limit_enabled") is True,
            "response_cache_policy": _text(controls.get("response_cache_policy"), "unknown"),
            "ordinary_mutation_without_hnc_policy": _text(controls.get("ordinary_mutation_without_hnc_policy"), "unknown"),
            "blocker_count": len(blockers) if isinstance(blockers, list) else 0,
        }
    if surface_id == "executor_isolation":
        evidence = _mapping(payload.get("evidence"))
        blockers = payload.get("blockers")
        return {
            "truth_status": _text(payload.get("truth_status"), "real_derived"),
            "schema": _text(payload.get("schema"), "unknown"),
            "production_executor_ready": payload.get("production_executor_ready") is True,
            "kill_switch_engaged": payload.get("kill_switch_engaged") is True,
            "executor_enabled": payload.get("executor_enabled") is True,
            "provider_mutation_disabled": payload.get("provider_mutation_disabled") is True,
            "action_mode": _text(evidence.get("action_mode"), "unknown"),
            "trade_path_state": _text(evidence.get("trade_path_state"), "unknown"),
            "blocker_count": len(blockers) if isinstance(blockers, list) else 0,
        }
    if surface_id == "authority_map":
        blockers = payload.get("blockers")
        return {
            "truth_status": _text(payload.get("truth_status"), "real_derived"),
            "schema": _text(payload.get("schema"), "unknown"),
            "distinct_authority_roles": payload.get("distinct_authority_roles") is True,
            "signed_receipt_count": _bounded_int(payload.get("signed_receipt_count")),
            "required_signed_receipt_count": _bounded_int(payload.get("required_signed_receipt_count")),
            "independent_authorities_ready": payload.get("independent_authorities_ready") is True,
            "blocker_count": len(blockers) if isinstance(blockers, list) else 0,
        }
    if surface_id == "result_binding":
        evidence = _mapping(payload.get("evidence"))
        blockers = payload.get("blockers")
        return {
            "truth_status": _text(payload.get("truth_status"), "real_derived"),
            "schema": _text(payload.get("schema"), "unknown"),
            "protected_result_bound": payload.get("protected_result_bound") is True,
            "correlation_id_available": payload.get("correlation_id_available") is True,
            "independent_receipts_available": payload.get("independent_receipts_available") is True,
            "terminal_result_available": payload.get("terminal_result_available") is True,
            "active_lifecycle_count": _bounded_int(evidence.get("active_lifecycle_count")),
            "complete_lifecycle_count": _bounded_int(evidence.get("complete_lifecycle_count")),
            "blocker_count": len(blockers) if isinstance(blockers, list) else 0,
        }
    if surface_id == "release_ledger":
        ledger = _mapping(payload.get("ledger"))
        return {
            "truth_status": "real_derived" if payload.get("available") is True else "unavailable",
            "schema": _text(payload.get("schema"), "unknown"),
            "available": payload.get("available") is True,
            "event_count": _bounded_int(ledger.get("event_count")),
            "chain_valid": ledger.get("chain_valid") is True,
            "latest_event_type": _text(ledger.get("latest_event_type"), "none"),
            "append_route_mode": _text(payload.get("append_route_mode"), "unknown"),
        }
    return {"truth_status": "no_data"}


def _surface_row(surface: Mapping[str, Any], readers: Mapping[str, SurfaceReader]) -> Dict[str, Any]:
    surface_id = str(surface["id"])
    try:
        reader = readers.get(surface_id)
        if reader is None:
            raise KeyError(surface_id)
        payload = _mapping(reader())
        projection = _project_payload(surface_id, payload)
        read_state = "observed" if payload else "unavailable"
        truth_status = _text(projection.get("truth_status"), "no_data" if read_state == "unavailable" else "real_derived")
        evidence = list(surface.get("evidence") or ())
        evidence_digest = _json_digest(projection)
        return {
            "id": surface_id,
            "label": str(surface["label"]),
            "route": str(surface["route"]),
            "method": "GET",
            "source": str(surface["source"]),
            "mode": "read_only",
            "mutation_authority": False,
            "read_state": read_state,
            "truth_status": truth_status,
            "current": read_state == "observed",
            "evidence": evidence,
            "evidence_digest_sha256": evidence_digest,
            "summary": projection,
        }
    except Exception as exc:  # noqa: BLE001 - one failed surface must not hide the rest
        return {
            "id": surface_id,
            "label": str(surface["label"]),
            "route": str(surface["route"]),
            "method": "GET",
            "source": str(surface["source"]),
            "mode": "read_only",
            "mutation_authority": False,
            "read_state": "unavailable",
            "truth_status": "unavailable",
            "current": False,
            "evidence": list(surface.get("evidence") or ()),
            "evidence_digest_sha256": None,
            "summary": {"reason": f"surface_read_failed:{type(exc).__name__}"},
        }


def build_operator_capability_runtime_attestation(
    readers: Mapping[str, SurfaceReader] | None = None,
    *,
    now: float | None = None,
) -> Dict[str, Any]:
    """Build a current, non-secret capability-to-runtime receipt.

    The receipt proves read-only route binding and current observation state. It
    intentionally keeps release authority false: this route cannot open trading,
    publish order intents, charge billing, file company records, or execute tools.
    """
    when = time.time() if now is None else float(now)
    active_readers = _default_readers() if readers is None else readers
    rows = [_surface_row(surface, active_readers) for surface in _CAPABILITY_SURFACES]
    observed = sum(1 for row in rows if row["current"] is True)
    digest_body = {
        "schema": "aureon.operator.capability-runtime-attestation.v1",
        "surfaces": rows,
        "surface_count": len(rows),
        "observed_surface_count": observed,
    }
    return {
        "schema": "aureon.operator.capability-runtime-attestation.v1",
        "generated_values": False,
        "observed_at": when,
        "observed_at_iso": datetime.fromtimestamp(when, timezone.utc).isoformat().replace("+00:00", "Z"),
        "surface_count": len(rows),
        "observed_surface_count": observed,
        "unavailable_surface_count": len(rows) - observed,
        "all_surfaces_observed": observed == len(rows),
        "production_ready": False,
        "release_authority": False,
        "mutation_authority": False,
        "routes": rows,
        "digest_sha256": _json_digest(digest_body),
        "digest_scope": "capability_route_evidence_matrix",
    }


__all__ = ["build_operator_capability_runtime_attestation"]
