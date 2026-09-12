"""Passive description of the serving operator's unreleased implementation.

This module performs no I/O and supplies no release authority. Requirement
states describe integration into create_app, not whether external services or
keys exist. A new production composition needs its own verified contract;
neither this report nor a configuration flag can authorize a handler.
"""

_RELEASE_REQUIREMENTS = (
    {
        "id": "production_ingress_custody",
        "state": "not_integrated",
        "label": "Production ingress custody",
        "owner_surface": "/ops/connections",
        "verification_route": "/api/operator/ingress-custody",
        "blocked_until": "operator_protected_ingress_attested",
        "work_order": "Bind the production ingress to an operator-protected server boundary and capture a custody receipt before any protected request can route beyond loopback.",
        "evidence_required": (
            "HTTPS or private ingress custody receipt for the serving operator boundary",
            "request identity, rate-limit, and no-store response attestation",
            "negative test showing public remote clients cannot reach protected handlers",
        ),
    },
    {
        "id": "independent_authorities",
        "state": "not_integrated",
        "label": "Independent review, dispatch, executor and receipt authorities",
        "owner_surface": "/cognition/agents",
        "verification_route": "/api/operator/authority-map",
        "blocked_until": "separate_authority_receipts_attested",
        "work_order": "Separate review, dispatch, executor, and receipt authority so one component cannot approve and execute a protected action by itself.",
        "evidence_required": (
            "signed review-authority receipt",
            "signed dispatch-authority receipt",
            "independent executor and terminal receipt authority mapping",
        ),
    },
    {
        "id": "isolated_executor",
        "state": "not_integrated",
        "label": "Isolated executor",
        "owner_surface": "/trading/hft",
        "verification_route": "/api/operator/executor-isolation",
        "blocked_until": "executor_isolation_and_kill_switch_attested",
        "work_order": "Run protected execution through an isolated executor with explicit kill switch, budget, venue, and dry-run regression receipts.",
        "evidence_required": (
            "executor process isolation receipt",
            "kill-switch and budget guard test receipt",
            "dry-run order path proof with provider mutation disabled",
        ),
    },
    {
        "id": "durable_release_ledger",
        "state": "integrated",
        "label": "Durable release ledger",
        "owner_surface": "/ops/approvals",
        "verification_route": "/api/operator/release-ledger",
        "blocked_until": "append_only_release_ledger_attested",
        "work_order": "Persist every release decision, config digest, operator approval, and protected-action result in an append-only ledger with replayable hashes.",
        "evidence_required": (
            "append-only ledger storage receipt",
            "config digest and source hash receipt",
            "replay check proving old receipts cannot be silently rewritten",
        ),
    },
    {
        "id": "terminal_receipt_service",
        "state": "integrated",
        "label": "Terminal receipt service",
        "owner_surface": "/ops/operational",
        "verification_route": "/api/operator/terminal-receipt",
        "blocked_until": "terminal_receipt_service_current_readback_attested",
        "work_order": "Keep the terminal receipt service current by binding runtime observations, provider timestamps, command outcomes, and operator-visible UI state.",
        "evidence_required": (
            "terminal receipt API contract",
            "provider timestamp and UI read-back binding",
            "receipt expiry test for stale or missing terminal observations",
        ),
    },
    {
        "id": "capability_runtime_attestation",
        "state": "integrated",
        "label": "Capability and runtime attestation",
        "owner_surface": "/platform/coverage",
        "verification_route": "/api/operator/capability-runtime-attestation",
        "blocked_until": "capabilities_bound_to_current_runtime_receipts",
        "work_order": "Attach every claimed capability to a current runtime receipt, test, or explicit unavailable state before it can count toward production readiness.",
        "evidence_required": (
            "capability-to-runtime receipt matrix",
            "current browser read-back for each production surface",
            "negative proof rejecting stale generated report clocks",
        ),
    },
    {
        "id": "verified_result_binding",
        "state": "not_integrated",
        "label": "Verified result binding",
        "owner_surface": "/defense",
        "verification_route": "/api/operator/result-binding",
        "blocked_until": "protected_result_bound_to_independent_receipt",
        "work_order": "Bind each protected result to the initiating intent, independent authority receipts, provider or terminal output, and final UI read-back.",
        "evidence_required": (
            "intent-to-result correlation id",
            "independent receipt comparison",
            "UI and terminal read-back proving the same completed result",
        ),
    },
)

_OPERATOR_HANDOFF = {
    "state": "blocked",
    "control_surface": "/platform/switchboard",
    "release_status_route": "/api/operator/release-readiness",
    "protected_request_policy": (
        "mutating requests require HNC custody and release authority before handlers run"
    ),
    "operator_can_record_intent": True,
    "operator_can_release_execution": False,
}


def _requirement_row(requirement: dict) -> dict:
    return {
        "id": requirement["id"],
        "state": requirement["state"],
        "label": requirement["label"],
        "owner_surface": requirement["owner_surface"],
        "verification_route": requirement["verification_route"],
        "blocked_until": requirement["blocked_until"],
        "work_order": requirement["work_order"],
        "evidence_required": list(requirement["evidence_required"]),
    }


def _work_order_row(requirement: dict) -> dict:
    return {
        "id": "release:" + requirement["id"],
        "title": requirement["label"],
        "status": requirement["state"],
        "owner_surface": requirement["owner_surface"],
        "verification_route": requirement["verification_route"],
        "blocked_until": requirement["blocked_until"],
        "evidence_required": list(requirement["evidence_required"]),
    }


def build_operator_release_readiness() -> dict:
    """Return a fresh public mapping without probing or changing anything.

    No observation clock is minted: this is an implementation contract, not a
    provider, source-attestation, or deployment-health measurement. HTTP clients
    may date and expire their receipt independently.
    """
    blocked_requirement_ids = [
        requirement["id"]
        for requirement in _RELEASE_REQUIREMENTS
        if requirement["state"] != "integrated"
    ]
    return {
        "schema": "aureon.operator.release-readiness.v1",
        "scope": "operator_protected_http_ingress",
        "basis": "serving_implementation_contract",
        "state": "held",
        "reason_code": "production_magic_star_release_unavailable",
        "release_available": False,
        "production_ready": False,
        "source_attestation": None,
        "configuration_attestation": None,
        "requirements": [
            _requirement_row(requirement)
            for requirement in _RELEASE_REQUIREMENTS
        ],
        "work_orders": [
            _work_order_row(requirement)
            for requirement in _RELEASE_REQUIREMENTS
        ],
        "operator_handoff": {
            **_OPERATOR_HANDOFF,
            "blocked_requirement_ids": blocked_requirement_ids,
        },
    }
