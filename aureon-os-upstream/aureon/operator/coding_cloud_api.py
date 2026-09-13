"""Owner-only cloud status for the coding organism.

The legacy coding cockpit called an unauthenticated browser-local service on
``127.0.0.1:13002``.  A phone or Cloud Run browser can never reach that process,
and exposing the legacy hub would also expose repo-writing and autonomous-job
handlers.  This module deliberately publishes one passive status receipt
through the authenticated operator server.  No prompt, chat, reload, proxy, or
job execution route is registered here.

An unavailable receipt is a useful live result: it proves the owner reached the
current operator plane while preserving the fact that a cloud coding worker has
not been commissioned.  A future worker must provide a separate, reviewed
implementation rather than becoming active because an environment flag exists.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

STATUS_SCHEMA = "aureon.operator.coding-cloud-status.v1"
NOT_COMMISSIONED = "coding_service_not_commissioned"
REFRESH_INTERVAL_MS = 5_000


def build_coding_cloud_status() -> dict[str, Any]:
    """Return a bounded receipt with no local paths, credentials, or stale runs."""

    observed_at = datetime.now(UTC).isoformat()
    unavailable_capabilities = {
        "coding_prompt": False,
        "phi_chat": False,
        "voice_reload": False,
        "autonomous_self_run": False,
        "autonomous_jobs": False,
        "repo_mutation": False,
    }
    unavailable = {
        "available": False,
        "commissioned": False,
        "reason_code": NOT_COMMISSIONED,
        "observed_at": observed_at,
    }
    return {
        "schema_version": STATUS_SCHEMA,
        "available": False,
        "commissioned": False,
        "status": NOT_COMMISSIONED,
        "reason_code": NOT_COMMISSIONED,
        "observed_at": observed_at,
        "refresh_interval_ms": REFRESH_INTERVAL_MS,
        "last_run": None,
        "phi": {**unavailable, "status": "phi_coding_bridge_not_commissioned"},
        "ollama": {
            **unavailable,
            "status": "ollama_coding_bridge_not_commissioned",
            "summary": {
                "ollama_reachable": False,
                "hnc_auris_ready": False,
                "metacognitive_ready": False,
            },
        },
        "autonomous_self_run": {
            **unavailable,
            "status": "autonomous_self_run_not_commissioned",
            "summary": {"loop_active": False, "cycle_count": 0},
        },
        "autonomous_jobs": {
            **unavailable,
            "status": "autonomous_jobs_not_commissioned",
            "summary": {"active_job_count": 0, "queue_depth": 0},
        },
        "capabilities": {
            "status_read": True,
            **unavailable_capabilities,
        },
        "authority": {
            "owner_only": True,
            "tenant_access": False,
            "arbitrary_proxy": False,
            "credential_access": False,
            "execution_authority": False,
            "publication_authority": False,
            "trading_authority": False,
        },
    }


def register_coding_cloud_routes(app: Any) -> None:
    """Register after the operator identity gate; require the admin plane again."""

    from flask import g, jsonify

    @app.get("/api/coding/status")
    def coding_cloud_status():
        is_owner = (
            getattr(g, "identity_kind", None) == "admin"
            and getattr(g, "is_admin", False) is True
            and getattr(g, "tenant", None) is None
        )
        if not is_owner:
            response = jsonify(
                {
                    "error": {
                        "code": 403,
                        "message": "this route is operator-only",
                        "plane": "admin",
                    }
                }
            )
            response.headers["Cache-Control"] = "no-store"
            return response, 403
        response = jsonify(build_coding_cloud_status())
        response.headers["Cache-Control"] = "no-store"
        return response
