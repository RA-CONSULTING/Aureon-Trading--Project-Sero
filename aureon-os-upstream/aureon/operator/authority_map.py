"""Read-only independent authority mapping receipt.

This receipt maps review, dispatch, executor, and receipt authority surfaces.
It does not sign, approve, dispatch, or execute protected actions.
"""

from __future__ import annotations

import hashlib
import json
import time
from datetime import UTC, datetime
from typing import Any, Mapping


def _json_digest(value: Any) -> str:
    body = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(body).hexdigest()


def _text(value: Any, default: str = "unavailable") -> str:
    text = str(value or "").strip()
    return text[:160] if text else default


def observe_signed_authority_chain(
    *,
    pinned_authorities: Mapping[str, Any] | None = None,
    signed_chain: Mapping[str, bytes | str] | None = None,
    now: float,
) -> dict[str, Any]:
    """Passively verify the existing v0.3 wire contract, without signing or dispatch.

    Pins must come from trusted service composition, separately from receipt or
    request data. Distinct keys prove cryptographic identities, not independent
    administrators, key custody, process isolation, or permission for a new action.
    Historical terminal chains remain verifiable after their command expires.
    """
    observation: dict[str, Any] = {
        "signed_chain_verified": False,
        "distinct_pinned_authorities": False,
        "authority_ids": {},
        "chain": None,
        "blockers": [],
    }
    if not isinstance(pinned_authorities, Mapping) or not pinned_authorities:
        observation["blockers"].append("trusted_authority_pins_missing")
    if not isinstance(signed_chain, Mapping) or not signed_chain:
        observation["blockers"].append("observed_signed_terminal_chain_missing")
    if observation["blockers"]:
        return observation
    # The early missing-evidence return also narrows the trusted input types.
    if not isinstance(pinned_authorities, Mapping) or not isinstance(signed_chain, Mapping):
        return observation
    try:
        from aureon.plumber.crypto import canonical_json_bytes
        from aureon.plumber.production_release_broker_v03 import (
            AuthorityBindingV03,
            ProductionReleaseVerifierV03,
            decode_dispatch_claim_v03,
            decode_executor_evidence_v03,
            decode_release_command_v03,
            decode_review_authorization_v03,
            decode_terminal_receipt_v03,
        )

        roles = ("review", "dispatch", "executor", "receipt")
        if any(type(pinned_authorities.get(role)) is not AuthorityBindingV03 for role in roles):
            raise ValueError("invalid authority pins")
        verifier = ProductionReleaseVerifierV03(
            review_authority=pinned_authorities["review"],
            dispatch_authority=pinned_authorities["dispatch"],
            executor_authority=pinned_authorities["executor"],
            receipt_authority=pinned_authorities["receipt"],
            trusted_now_ms=lambda: int(now * 1000),
        )
        observation["distinct_pinned_authorities"] = True
        observation["authority_ids"] = verifier.authority_ids
        names = ("command", "review", "dispatch", "executor", "receipt")
        if any(
            not isinstance(signed_chain.get(name), (bytes, str))
            or not 0 < len(signed_chain[name]) <= 65_536
            for name in names
        ):
            raise ValueError("invalid signed wire")
        command = decode_release_command_v03(signed_chain["command"])
        review = decode_review_authorization_v03(signed_chain["review"])
        dispatch = decode_dispatch_claim_v03(signed_chain["dispatch"])
        executor = decode_executor_evidence_v03(signed_chain["executor"])
        receipt = decode_terminal_receipt_v03(signed_chain["receipt"])
        verifier.verify_terminal(command, review, dispatch, receipt, executor)
        observation["signed_chain_verified"] = True
        observation["chain"] = {
            "command_commitment": command.commitment,
            "review_commitment": review.commitment,
            "dispatch_commitment": dispatch.commitment,
            "executor_evidence_commitment": executor.commitment,
            "receipt_id": receipt.receipt_id,
            "effect_id": command.effect_id,
            "request_nonce": command.request_nonce,
            "terminal_at_ms": receipt.terminal_at_ms,
            "disposition": receipt.disposition.value,
            "executor_outcome": executor.outcome.value,
            "result_sha256": executor.result_sha256,
            "provider_readback_sha256": executor.provider_readback_sha256,
            "terminal_receipt_sha256": hashlib.sha256(canonical_json_bytes(receipt.wire_dict())).hexdigest(),
        }
    except Exception:
        # Do not expose raw wire bodies, keys, exception payloads or signatures.
        observation["blockers"].append("signed_terminal_chain_verification_failed")
    return observation


def build_authority_map_receipt(
    *,
    pinned_authorities: Mapping[str, Any] | None = None,
    signed_chain: Mapping[str, bytes | str] | None = None,
    now: float | None = None,
) -> dict[str, Any]:
    observed_at = time.time() if now is None else float(now)
    authority_map: dict[str, dict[str, Any]] = {
        "review": {
            "role_id": "client_acceptance_officer",
            "surface": "/cognition/agents",
            "receipt": None,
            "signed_receipt": False,
        },
        "dispatch": {
            "role_id": "client_brief_broker",
            "surface": "/ops/approvals",
            "receipt": None,
            "signed_receipt": False,
        },
        "executor": {
            "role_id": "exchange_execution_specialist",
            "surface": "/api/operator/executor-isolation",
            "receipt": "/api/operator/executor-isolation",
            "signed_receipt": False,
        },
        "terminal_receipt": {
            "role_id": "terminal_receipt_service",
            "surface": "/api/operator/terminal-receipt",
            "receipt": "/api/operator/terminal-receipt",
            "signed_receipt": False,
        },
    }
    role_ids = [_text(row.get("role_id")) for row in authority_map.values()]
    distinct_authority_roles = len(set(role_ids)) == len(role_ids)
    verification = observe_signed_authority_chain(
        pinned_authorities=pinned_authorities, signed_chain=signed_chain, now=observed_at,
    )
    verified = verification["signed_chain_verified"] is True
    for role, row in authority_map.items():
        pin_role = "receipt" if role == "terminal_receipt" else role
        row["authority_id"] = verification["authority_ids"].get(pin_role)
        row["signed_receipt"] = verified
        row["identity_scope"] = "pinned_signature" if verified else "role_catalog_only"
    signed_receipt_count = len(authority_map) if verified else 0
    blockers = ([] if verified else [
        "signed_review_authority_receipt_missing",
        "signed_dispatch_authority_receipt_missing",
        "signed_executor_authority_receipt_missing",
        "signed_terminal_receipt_authority_missing",
    ]) + verification["blockers"] + ["independent_administration_and_key_custody_attestation_missing"]
    # No independent custody verifier or deployed authority composition exists in
    # this service. A valid chain is useful evidence, never that missing proof.
    ready = False
    digest_body = {
        "authority_map": authority_map,
        "distinct_authority_roles": distinct_authority_roles,
        "signed_receipt_count": signed_receipt_count,
        "verification": verification,
        "ready": ready,
        "blockers": blockers,
    }
    return {
        "schema": "aureon.operator.authority-map.v1",
        "generated_values": False,
        "observed_at": observed_at,
        "observed_at_iso": datetime.fromtimestamp(observed_at, UTC).isoformat().replace("+00:00", "Z"),
        "truth_status": "real_derived",
        "read_state": "observed",
        "available": True,
        "distinct_authority_roles": distinct_authority_roles,
        "signed_receipt_count": signed_receipt_count,
        "required_signed_receipt_count": len(authority_map),
        "signed_chain_verified": verified,
        "distinct_pinned_authorities": verification["distinct_pinned_authorities"],
        "independent_administration_verified": False,
        "verification": verification,
        "independent_authorities_ready": ready,
        "authority_map": authority_map,
        "blockers": blockers,
        "production_ready": False,
        "release_authority": False,
        "mutation_authority": False,
        "digest_sha256": _json_digest(digest_body),
        "digest_scope": "operator_independent_authorities",
    }


__all__ = ["build_authority_map_receipt", "observe_signed_authority_chain"]
