"""Read-only protected result binding receipt.

This receipt checks whether a protected result can be tied back to its intent,
independent authority receipts, terminal/provider output, and UI readback. It
does not create or mutate any order/result state.
"""

from __future__ import annotations

import hashlib
import json
import math
import time
from datetime import UTC, datetime
from typing import Any, Mapping


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _json_digest(value: Any) -> str:
    body = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(body).hexdigest()


def _receipt_digest(wire: Any) -> str | None:
    if not isinstance(wire, (bytes, str)) or not 0 < len(wire) <= 65_536:
        return None
    try:
        from aureon.plumber.crypto import canonical_json_bytes
        from aureon.plumber.production_release_broker_v03 import decode_terminal_receipt_v03

        receipt = decode_terminal_receipt_v03(wire)
        return hashlib.sha256(canonical_json_bytes(receipt.wire_dict())).hexdigest()
    except Exception:
        return None


def _body_digest(body: Any) -> str | None:
    # Hash exact observed bytes, never a caller's claimed digest or reserialized
    # provider object. Keep passive audit work bounded.
    return hashlib.sha256(body).hexdigest() if isinstance(body, bytes) and len(body) <= 4_194_304 else None


def build_result_binding_receipt(
    *,
    terminal_state: Mapping[str, Any] | None = None,
    release_ledger: Mapping[str, Any] | None = None,
    authority_map: Mapping[str, Any] | None = None,
    pinned_authorities: Mapping[str, Any] | None = None,
    signed_chain: Mapping[str, bytes | str] | None = None,
    result_readbacks: Mapping[str, Any] | None = None,
    now: float | None = None,
) -> dict[str, Any]:
    """Observe an exact historical result chain without granting new authority.

    A trusted composition must supply pins independently and read canonical
    terminal_receipt_wire from the durable receipt authority, result_bytes and
    provider_readback_bytes from their readers, and ui_terminal_receipt_wire plus
    ui_observed_at from an actual UI readback. No such production adapter is
    currently installed. Ledger event labels, lifecycle flags and supplied
    authority-map booleans remain context; they cannot satisfy these joins.
    """
    if terminal_state is None:
        from aureon.operator.legacy_runtime_api import _status_handlers

        read_status, _flight, _env = _status_handlers()
        terminal_state = _mapping(read_status())
    if release_ledger is None:
        from aureon.operator.release_ledger import build_release_ledger_receipt

        release_ledger = _mapping(build_release_ledger_receipt())
    if authority_map is None:
        from aureon.operator.authority_map import build_authority_map_receipt

        authority_map = _mapping(build_authority_map_receipt())
    observed_at = time.time() if now is None else float(now)
    terminal = _mapping(terminal_state)
    plan = _mapping(terminal.get("exchange_action_plan"))
    latest_execution = _mapping(plan.get("latest_execution"))
    lifecycle = _mapping(latest_execution.get("order_lifecycle"))
    lifecycles = _list(lifecycle.get("active_lifecycles"))
    complete_lifecycles = [
        row for row in lifecycles
        if _mapping(row).get("continuity_complete") is True
        and _mapping(row).get("outcome_recorded") is True
    ]
    ledger_rows = _mapping(release_ledger.get("ledger")).get("recent_events")
    protected_results = [
        row for row in _list(ledger_rows)
        if _mapping(row).get("event_type") == "protected_action_result"
    ]
    from aureon.operator.authority_map import observe_signed_authority_chain
    from aureon.operator.executor_isolation import terminal_source_observation

    verification = observe_signed_authority_chain(
        pinned_authorities=pinned_authorities, signed_chain=signed_chain, now=observed_at,
    )
    verified = verification["signed_chain_verified"] is True
    chain = _mapping(verification.get("chain"))
    readbacks = _mapping(result_readbacks)
    expected_receipt = chain.get("terminal_receipt_sha256")
    terminal_receipt_matches = verified and _receipt_digest(readbacks.get("terminal_receipt_wire")) == expected_receipt
    provider_readback_matches = verified and _body_digest(readbacks.get("provider_readback_bytes")) == chain.get("provider_readback_sha256")
    result_bytes_match = verified and _body_digest(readbacks.get("result_bytes")) == chain.get("result_sha256")
    if verified and chain.get("executor_outcome") == "DENIED":
        result_bytes_match = chain.get("result_sha256") == "0" * 64 and readbacks.get("result_bytes") is None
    ui_observed_at = readbacks.get("ui_observed_at")
    ui_age = None
    if isinstance(ui_observed_at, (int, float)) and not isinstance(ui_observed_at, bool):
        try:
            ui_age = observed_at - ui_observed_at if math.isfinite(ui_observed_at) else None
        except OverflowError:
            pass
    ui_readback_available = (
        verified and ui_age is not None and 0 <= ui_age <= 30
        and _receipt_digest(readbacks.get("ui_terminal_receipt_wire")) == expected_receipt
    )
    correlation_id_available = verified
    # A signature proves key control. No deployed independent-administration
    # verifier is installed, and authority_map is an observational input only.
    independent_receipts_available = False
    terminal_result_available = terminal_receipt_matches and provider_readback_matches and result_bytes_match
    signed_result_readbacks_bound = terminal_result_available and ui_readback_available
    protected_result_bound = (
        correlation_id_available
        and independent_receipts_available
        and terminal_result_available
        and ui_readback_available
    )
    blockers: list[str] = []
    if not correlation_id_available:
        blockers.append("intent_to_result_correlation_missing")
    if not independent_receipts_available:
        blockers.append("independent_authority_administration_attestation_missing")
    if not terminal_receipt_matches:
        blockers.append("exact_durable_terminal_receipt_readback_missing")
    if not provider_readback_matches:
        blockers.append("signed_provider_readback_bytes_missing_or_mismatched")
    if not result_bytes_match:
        blockers.append("signed_result_bytes_missing_or_mismatched")
    if not terminal_result_available:
        blockers.append("completed_protected_result_readback_missing")
    if not ui_readback_available:
        blockers.append("current_exact_ui_receipt_readback_missing")
    blockers.extend(verification["blockers"])
    source = terminal_source_observation(terminal, observed_at)
    evidence = {
        "terminal_stale": terminal.get("stale") is True,
        "action_mode": str(plan.get("mode") or "unknown"),
        "trade_path_state": str(plan.get("trade_path_state") or "unknown"),
        "active_lifecycle_count": len(lifecycles),
        "complete_lifecycle_count": len(complete_lifecycles),
        "protected_result_ledger_count": len(protected_results),
        "lifecycle_and_event_counts_are_binding_evidence": False,
        "reported_authorities_ready": _mapping(authority_map).get("independent_authorities_ready") is True,
        "signed_chain_verified": verified,
        "terminal_receipt_matches": terminal_receipt_matches,
        "provider_readback_matches": provider_readback_matches,
        "result_bytes_match": result_bytes_match,
        "signed_result_readbacks_bound": signed_result_readbacks_bound,
        "ui_readback_age_sec": ui_age,
        "verified_chain": chain if verified else None,
        **source,
        "correlation_id_available": correlation_id_available,
        "independent_receipts_available": independent_receipts_available,
        "terminal_result_available": terminal_result_available,
        "ui_readback_available": ui_readback_available,
    }
    return {
        "schema": "aureon.operator.result-binding.v1",
        "generated_values": False,
        "observed_at": observed_at,
        "observed_at_iso": datetime.fromtimestamp(observed_at, UTC).isoformat().replace("+00:00", "Z"),
        "truth_status": "real_derived" if terminal or verified else "unavailable",
        "read_state": "observed" if source["source_current"] or ui_readback_available else "recorded" if terminal or verified else "unavailable",
        "available": bool(terminal) or verified,
        "protected_result_bound": protected_result_bound,
        "signed_chain_verified": verified,
        "signed_result_readbacks_bound": signed_result_readbacks_bound,
        "result_evidence_scope": "historical_signed_chain" if verified else "unverified_observations",
        "correlation_id_available": correlation_id_available,
        "independent_receipts_available": independent_receipts_available,
        "terminal_result_available": terminal_result_available,
        "ui_readback_available": ui_readback_available,
        "blockers": blockers,
        "evidence": evidence,
        "production_ready": False,
        "release_authority": False,
        "mutation_authority": False,
        "digest_sha256": _json_digest({"evidence": evidence, "blockers": blockers, "protected_result_bound": protected_result_bound}),
        "digest_scope": "operator_protected_result_binding",
    }


__all__ = ["build_result_binding_receipt"]
