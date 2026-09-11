"""Offline evidence tests. Generated fixture keys never become service pins."""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from datetime import UTC, datetime

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from aureon.operator.authority_map import build_authority_map_receipt
from aureon.operator.executor_isolation import build_executor_isolation_receipt
from aureon.operator.result_binding import build_result_binding_receipt
from aureon.plumber.crypto import canonical_json_bytes, ed25519_public_key_hex
from aureon.plumber.production_release_broker_v03 import (
    AuthorityBindingV03,
    ExecutorOutcome,
    ReceiptDisposition,
    ReleaseCommandV03,
    sign_dispatch_claim_v03,
    sign_executor_evidence_v03,
    sign_review_authorization_v03,
    sign_terminal_receipt_v03,
    terminal_receipt_id_v03,
)


def digest(value: str | bytes) -> str:
    return hashlib.sha256(value.encode() if isinstance(value, str) else value).hexdigest()


@pytest.fixture
def signed_observation():
    roles = ("review", "dispatch", "executor", "receipt")
    keys = {role: Ed25519PrivateKey.generate() for role in roles}
    pins = {role: AuthorityBindingV03(
        role=role.upper(), authority_id=f"test-{role}", key_id=f"test-{role}-key",
        public_key_hex=ed25519_public_key_hex(keys[role]),
    ) for role in roles}
    command = ReleaseCommandV03(
        command_id=digest("command"), packet_commitment=digest("packet"),
        admission_commitment=digest("admission"), effect_id=digest("effect"),
        capability_id=digest("capability"), capability_measurement_sha256=digest("capability-code"),
        runtime_measurement_sha256=digest("runtime"), authorization_context_sha256=digest("context"),
        request_nonce=digest("nonce"), issued_at_ms=1_000, expires_at_ms=10_000,
    )
    review = sign_review_authorization_v03(
        keys["review"], review_id=digest("review"), command_commitment=command.commitment,
        decision="ALLOW", issued_at_ms=1_100, expires_at_ms=9_000,
        authority_id=pins["review"].authority_id, key_id=pins["review"].key_id,
    )
    dispatch = sign_dispatch_claim_v03(
        keys["dispatch"], command_commitment=command.commitment, review_commitment=review.commitment,
        effect_id=command.effect_id, request_nonce=command.request_nonce, dispatch_nonce=digest("dispatch"),
        claimed_at_ms=2_000, claim_expires_at_ms=2_500,
        authority_id=pins["dispatch"].authority_id, key_id=pins["dispatch"].key_id,
    )
    result_body = b'{"result":"fixture-only"}'
    provider_body = b'{"provider_receipt":"fixture-only"}'
    evidence = sign_executor_evidence_v03(
        keys["executor"], evidence_id=digest("evidence"), command_commitment=command.commitment,
        review_commitment=review.commitment, dispatch_commitment=dispatch.commitment,
        effect_id=command.effect_id, capability_id=command.capability_id,
        runtime_measurement_sha256=command.runtime_measurement_sha256, request_nonce=command.request_nonce,
        outcome=ExecutorOutcome.CONSUMED, result_sha256=digest(result_body),
        provider_readback_sha256=digest(provider_body), reason_code="effect_consumed_with_provider_readback",
        terminal_at_ms=2_100, authority_id=pins["executor"].authority_id, key_id=pins["executor"].key_id,
    )
    receipt = sign_terminal_receipt_v03(
        keys["receipt"], denied=False, receipt_id=terminal_receipt_id_v03(evidence.commitment),
        command_commitment=command.commitment, review_commitment=review.commitment,
        executor_evidence_commitment=evidence.commitment, effect_id=command.effect_id,
        request_nonce=command.request_nonce, disposition=ReceiptDisposition.RELEASED,
        reason_code=evidence.reason_code, terminal_at_ms=evidence.terminal_at_ms,
        authority_id=pins["receipt"].authority_id, key_id=pins["receipt"].key_id,
    )
    chain = {name: canonical_json_bytes(item.wire_dict()) for name, item in (
        ("command", command), ("review", review), ("dispatch", dispatch),
        ("executor", evidence), ("receipt", receipt),
    )}
    readbacks = {"terminal_receipt_wire": chain["receipt"], "result_bytes": result_body,
                 "provider_readback_bytes": provider_body, "ui_terminal_receipt_wire": chain["receipt"],
                 "ui_observed_at": 20.0}
    return pins, chain, readbacks


def result_receipt(pins=None, chain=None, readbacks=None, **kwargs):
    return build_result_binding_receipt(
        terminal_state=kwargs.pop("terminal_state", {}), release_ledger=kwargs.pop("release_ledger", {}),
        authority_map=kwargs.pop("authority_map", {}), pinned_authorities=pins,
        signed_chain=chain, result_readbacks=readbacks, now=kwargs.pop("now", 20.0), **kwargs,
    )


def test_valid_historical_chain_is_not_independent_custody(signed_observation):
    pins, chain, _ = signed_observation
    receipt = build_authority_map_receipt(pinned_authorities=pins, signed_chain=chain, now=20.0)
    assert receipt["signed_chain_verified"] is True
    assert receipt["signed_receipt_count"] == 4
    assert receipt["distinct_pinned_authorities"] is True
    assert receipt["verification"]["chain"]["terminal_at_ms"] == 2100
    assert receipt["independent_authorities_ready"] is False
    assert receipt["independent_administration_verified"] is False
    assert receipt["production_ready"] is False
    assert "signature_hex" not in json.dumps(receipt)
    assert "public_key_hex" not in json.dumps(receipt)


@pytest.mark.parametrize("fault", ["missing_pins", "wrong_pin", "shared_key", "missing_dispatch", "tampered_nonce", "forged_signature", "oversized_wire"])
def test_invalid_or_untrusted_chains_never_count_as_signed_receipts(signed_observation, fault):
    pins, chain, _ = signed_observation
    if fault == "missing_pins":
        pins = None
    elif fault == "wrong_pin":
        pins["review"] = replace(pins["review"], public_key_hex=ed25519_public_key_hex(Ed25519PrivateKey.generate()))
    elif fault == "shared_key":
        pins["executor"] = replace(pins["executor"], public_key_hex=pins["review"].public_key_hex)
    elif fault == "missing_dispatch":
        del chain["dispatch"]
    elif fault == "oversized_wire":
        chain["command"] = b" " * 65_537
    else:
        name = "command" if fault == "tampered_nonce" else "receipt"
        value = json.loads(chain[name])
        value["request_nonce" if fault == "tampered_nonce" else "signature_hex"] = digest("other") if fault == "tampered_nonce" else "0" * 128
        chain[name] = canonical_json_bytes(value)
    receipt = build_authority_map_receipt(pinned_authorities=pins, signed_chain=chain, now=20.0)
    assert receipt["signed_chain_verified"] is False
    assert receipt["signed_receipt_count"] == 0
    assert receipt["verification"]["chain"] is None
    assert receipt["independent_authorities_ready"] is False


def test_exact_readbacks_bind_historical_evidence_without_release_authority(signed_observation):
    receipt = result_receipt(*signed_observation)
    assert receipt["signed_result_readbacks_bound"] is True
    assert receipt["terminal_result_available"] is True
    assert receipt["ui_readback_available"] is True
    assert receipt["result_evidence_scope"] == "historical_signed_chain"
    assert receipt["protected_result_bound"] is False
    assert receipt["release_authority"] is False
    assert receipt["mutation_authority"] is False


@pytest.mark.parametrize("fault", ["result", "provider", "terminal", "ui", "missing_ui_time", "old_ui", "future_ui", "digest_only"])
def test_no_binding_from_unrelated_or_old_readback(signed_observation, fault):
    pins, chain, readbacks = signed_observation
    if fault in ("result", "provider"):
        readbacks["result_bytes" if fault == "result" else "provider_readback_bytes"] = b"unrelated"
    elif fault in ("terminal", "ui"):
        value = json.loads(chain["receipt"])
        value["signature_hex"] = "0" * 128
        readbacks["terminal_receipt_wire" if fault == "terminal" else "ui_terminal_receipt_wire"] = canonical_json_bytes(value)
    elif fault == "missing_ui_time":
        del readbacks["ui_observed_at"]
    elif fault == "old_ui":
        readbacks["ui_observed_at"] = -11.0
    elif fault == "future_ui":
        readbacks["ui_observed_at"] = 21.0
    else:
        readbacks["result_bytes"] = digest(readbacks["result_bytes"])
    receipt = result_receipt(pins, chain, readbacks)
    assert receipt["signed_chain_verified"] is True
    assert receipt["signed_result_readbacks_bound"] is False
    assert receipt["protected_result_bound"] is False


def test_boolean_authorities_unrelated_events_and_complete_lifecycle_cannot_bind():
    receipt = result_receipt(
        terminal_state={"ok": True, "stale": False, "exchange_action_plan": {
            "correlation_id": "unrelated", "latest_execution": {"order_lifecycle": {
                "active_lifecycles": [{"continuity_complete": True, "outcome_recorded": True}],
            }},
        }},
        release_ledger={"ledger": {"recent_events": [{"event_type": "protected_action_result"}]}},
        authority_map={"independent_authorities_ready": True, "signed_receipt_count": 4},
    )
    assert receipt["evidence"]["complete_lifecycle_count"] == 1
    assert receipt["evidence"]["protected_result_ledger_count"] == 1
    for key in ("protected_result_bound", "signed_chain_verified", "correlation_id_available", "terminal_result_available", "ui_readback_available"):
        assert receipt[key] is False


def fresh_terminal(now=100.0):
    return {"ok": True, "stale": False,
            "last_tick_completed_at": datetime.fromtimestamp(now, UTC).isoformat(),
            "exchange_action_plan": {"real_orders_disabled": True, "exchange_mutations_disabled": True,
                "order_intent_publish_enabled": False, "latest_execution": {"executor_enabled": False,
                    "submitted_count": 0, "delegated_count": 0, "trade_path_state": "runtime_clearance_hold"}}}


def test_current_hold_is_an_observation_not_dry_run_or_process_isolation():
    receipt = build_executor_isolation_receipt(terminal_state=fresh_terminal(), now=100.0)
    assert receipt["held_order_path_observed"] is True
    assert receipt["kill_switch_engaged"] is True
    assert receipt["dry_run_order_path_proof"] is False
    assert receipt["process_isolation_verified"] is False
    assert receipt["production_executor_ready"] is False
    assert receipt["evidence"]["attempted_count"] is None


@pytest.mark.parametrize("fault", ["missing_tick", "old_tick", "future_tick", "stale", "duplicate", "reported_old", "watchdog"])
def test_new_observation_cannot_refresh_stale_executor_evidence(fault):
    terminal = fresh_terminal()
    if fault == "missing_tick":
        del terminal["last_tick_completed_at"]
    elif fault in ("old_tick", "future_tick"):
        terminal["last_tick_completed_at"] = fresh_terminal(1.0 if fault == "old_tick" else 106.0)["last_tick_completed_at"]
    elif fault == "reported_old":
        terminal["last_tick_age_sec"] = 90.0
    elif fault == "watchdog":
        terminal["runtime_watchdog"] = {"tick_long_running": True}
    else:
        terminal["stale" if fault == "stale" else "duplicate_runtime"] = True
    terminal["generated_at"] = datetime.fromtimestamp(100.0, UTC).isoformat()
    receipt = build_executor_isolation_receipt(terminal_state=terminal, now=100.0)
    assert receipt["source_current"] is False
    assert receipt["held_order_path_observed"] is False
    assert receipt["production_executor_ready"] is False


def test_missing_and_malformed_flags_and_counts_remain_unknown():
    terminal = fresh_terminal()
    terminal["exchange_action_plan"] = {"order_intent_publish_enabled": "false", "latest_execution": {
        "submitted_count": "0", "delegated_count": False, "attempted_count": -1, "route_timeout_sec": float("nan"),
    }}
    receipt = build_executor_isolation_receipt(terminal_state=terminal, now=100.0)
    for key in ("kill_switch_engaged", "provider_mutation_disabled", "order_intent_publish_enabled", "executor_enabled"):
        assert receipt[key] is None
    for key in ("submitted_count", "delegated_count", "attempted_count", "route_timeout_sec"):
        assert receipt["evidence"][key] is None
    assert receipt["held_order_path_observed"] is False


def test_enabled_runtime_flags_never_attest_production_isolation():
    terminal = fresh_terminal()
    terminal["exchange_action_plan"].update({"real_orders_disabled": False, "exchange_mutations_disabled": False,
        "order_intent_publish_enabled": True, "latest_execution": {"executor_enabled": True}})
    receipt = build_executor_isolation_receipt(terminal_state=terminal, now=100.0)
    assert receipt["executor_enabled"] is True
    assert receipt["kill_switch_engaged"] is False
    assert receipt["production_executor_ready"] is False
    assert "executor_process_isolation_attestation_missing" in receipt["blockers"]
