"""
Aureon SaaS — live platform status ("working").
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Honest health/readiness aggregation across the platform. Composes the existing
health surfaces — the operational core, the system coordinator, and per-domain
reachability — WITHOUT booting the whole organism (that would be heavy and
side-effectful). Degraded/partial states are reported truthfully, not masked.
"""

from __future__ import annotations

import json
import logging
import sys
import time
from typing import Any, Dict, List

from aureon.saas.domains import PRODUCT_DOMAINS, domain_report, product_domain_for
from aureon.saas.observed_runtime import observation, runtime_source_observations, process_observation
from pathlib import Path
from aureon.core.aureon_operational_core import OPERATIONAL_CORE_SNAPSHOT_FILE

logger = logging.getLogger("aureon.saas.status")


def _read_operational_core_snapshot() -> Dict[str, Any] | None:
    """Read a published operational-core health snapshot if one exists."""
    try:
        path = OPERATIONAL_CORE_SNAPSHOT_FILE
        if not path.exists():
            return None
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _operational_health() -> Dict[str, Any]:
    """Report operational-core health from a published snapshot when available.

    The gateway no longer needs _ops_core to exist in its own process; a
    separate trading/operational process can publish its health to disk.
    """
    try:
        now = time.time()
        # Prefer the published cross-process snapshot.
        snapshot = _read_operational_core_snapshot()
        if snapshot is not None:
            freshness = snapshot.get("state_freshness") or {}
            # The snapshot itself carries a source timestamp; use published_at as
            # a receipt clock and the state's last_write as the producer clock.
            meta = observation("operational_core_snapshot", freshness.get("last_write"),
                               now=now, source_path=str(OPERATIONAL_CORE_SNAPSHOT_FILE),
                               clock_kind="producer_timestamp")
            # A stale snapshot is honest "no_data", not a crash.
            fresh = meta["fresh"] and freshness.get("is_stale") is False
            status = snapshot.get("status", "unknown") if fresh else "unknown"
            return {
                **snapshot,
                "available": fresh,
                "source_observation": meta,
                "status": status,
                "truth_status": "real_derived" if fresh else "no_data",
                "source": "published_snapshot",
            }

        # Fallback: operational core lives in this process.
        module = sys.modules.get("aureon.core.aureon_operational_core")
        core = getattr(module, "_ops_core", None)
        if core is None:
            return {"available": False, "status": "unknown", "truth_status": "no_data",
                    "reason": "operational_core_not_observed_in_gateway_process",
                    "source": "in_process_probe"}
        health = core.get_health()
        if isinstance(health, dict):
            freshness = health.get("state_freshness") or {}
            meta = observation("gateway_operational_core", freshness.get("last_write"), now=now)
            fresh = meta["fresh"] and freshness.get("is_stale") is False
            return {**health, "available": fresh, "source_observation": meta,
                    "status": health.get("status", "unknown") if fresh else "unknown",
                    "truth_status": "real_derived" if fresh else "no_data",
                    "source": "in_process_probe"}
        return {"available": False, "status": "unknown", "reason": "operational_health_object_missing"}
    except Exception as exc:  # noqa: BLE001 — health probe must never crash the endpoint
        return {"available": False, "error": str(exc)}


def _coordinator_state() -> Dict[str, Any]:
    # Constructing a request-local coordinator initializes every discovered system
    # as IDLE. That is configuration, not the running coordinator's observation.
    return {"available": False, "truth_status": "no_data",
            "reason": "no_published_coordinator_runtime_snapshot"}


def get_platform_status() -> Dict[str, Any]:
    """
    Aggregate platform health. Cheap probes only — per-domain import-reachability
    + the operational core's own health snapshot + (if present) coordinator state.
    """
    domains = domain_report()
    reachable = sum(1 for d in domains if d["available"])

    # Roll domain reachability up into per-product-domain status.
    pd_reach: Dict[str, List[bool]] = {d: [] for d in PRODUCT_DOMAINS}
    for d in domains:
        pd = product_domain_for(str(d["domain"]))
        pd_reach.setdefault(pd, []).append(bool(d["available"]))
    product_domains = {}
    for pd, flags in pd_reach.items():
        if not flags:
            product_domains[pd] = {"status": "unknown", "reachable": 0, "total": 0}
            continue
        up = sum(1 for f in flags if f)
        product_domains[pd] = {
            "status": "ready" if up == len(flags) else ("degraded" if up else "down"),
            "reachable": up,
            "total": len(flags),
        }

    op = _operational_health()
    coord = _coordinator_state()

    op_status = str(op.get("status") or "").lower()
    if op.get("available") and op_status in {"healthy", "degraded", "critical"}:
        overall = op_status
    elif reachable:
        overall = "degraded"
    else:
        overall = "critical"
    return {
        "status": overall,
        "status_scope": "observed_operational_core_not_whole_platform",
        "reachability_status": "ready" if domains and reachable == len(domains) else "degraded" if reachable else "down",
        "truth_status": "real_derived",
        "source_timestamp": None,
        "receipt_timestamp": time.time(),
        "domains_reachable": reachable,
        "domains_total": len(domains),
        "product_domains": product_domains,
        "operational_core": op,
        "coordinator": coord,
        "runtime_sources": runtime_source_observations(),
        "process_observation": process_observation(),
        "note": "Domain readiness is import-level configuration. Operational health requires an "
                "original source clock; absence in this gateway process does not mean a separate service is down. "
                "Runtime sources carry independent clocks and expiry; this response is not whole-platform live proof.",
    }


__all__ = ["get_platform_status"]

