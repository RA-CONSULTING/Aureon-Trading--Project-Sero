from __future__ import annotations

import json

from aureon.operator import cloud_trading_control as control


def readback(received_at=1_000.0, *, ready=False):
    return {
        "schema": control.READBACK_SCHEMA,
        "received_at": received_at,
        "pubsub_message_id": "123",
        "receipt": {
            "intent_id": "1" * 64,
            "receipt_sha256": "2" * 64,
            "chain_verified": True,
            "dry_run": True,
            "provider_mutation_attempted": False,
            "orders_attempted": 0,
            "orders_submitted": 0,
            "executor_capabilities": {
                "live_execution_release": ready,
                "durable_budget_ledger": ready,
                "order_adapter_ready": ready,
                "live_result_binding_ready": ready,
            },
            "provider_readback": ({
                "provider_count": 4, "all_authenticated": True,
                "readback_sha256": "4" * 64, "providers": {},
            } if ready else None),
            "authority_ids": {
                "review": "gcp:aureon-trade-review",
                "dispatch": "gcp:aureon-trade-dispatch",
                "executor": "gcp:aureon-trade-executor",
                "receipt": "gcp:aureon-trade-receipt",
            },
            "key_versions": {
                "review": "review-key/1", "dispatch": "dispatch-key/1",
                "executor": "executor-key/1", "receipt": "receipt-key/1",
            },
        },
        "production_ready": False,
        "release_authority": False,
        "mutation_authority": False,
    }


def patch_sources(monkeypatch, *, requested=None, active=True, controller=False):
    desired = dict(control.LIVE_CONTROLS if requested is None else requested)
    monkeypatch.setattr(control, "_controls", lambda: (desired, {
        "AUREON_DEPLOYMENT_HOLD": True,
        "AUREON_DISABLE_REAL_ORDERS": True,
        "AUREON_DISABLE_EXCHANGE_MUTATIONS": True,
        "AUREON_LIVE_TRADING": False,
        "AUREON_ORDER_INTENT_PUBLISH": False,
        "AUREON_UNIFIED_ORDER_EXECUTOR": False,
    }))
    monkeypatch.setattr(control, "_authorization", lambda: {
        "active": active,
        "state": "active" if active else "expired",
        "expires_at_iso": "2026-09-15T18:13:51Z",
        "ledger_event_sha256": "3" * 64,
    })
    release = ({
        "schema": "aureon.cloud-trade-release-state.v1",
        "state": "held", "generation": 1, "request_id": "7" * 64,
        "requested_controls_sha256": control._digest(control.LIVE_CONTROLS),
        "authorization_event_sha256": "0" * 64,
        "authorization_expires_at_ms": 0,
        "probe_receipt_sha256": "0" * 64,
        "provider_readback_sha256": "0" * 64,
        "source_revision": "a" * 40, "signed_at_ms": 1_000_000,
        "controller_key_version": "controller-key/1", "signature": "signed", "update_time": "now",
    } if controller else None)
    monkeypatch.setattr(
        control, "read_controller_release",
        lambda **_kwargs: (release, None) if controller else (None, "cloud_release_controller_unconfigured"),
    )


def test_current_signed_probe_is_reported_without_granting_live_authority(tmp_path, monkeypatch):
    path = tmp_path / "receipt.json"
    path.write_text(json.dumps(readback()), encoding="utf-8")
    patch_sources(monkeypatch)
    result = control.build_cloud_trading_control_receipt(
        environ={}, now=1_010, readback_path=path,
    )
    assert result["last_probe"]["current"] is True
    assert result["capabilities"]["signed_authority_chain"] is True
    assert result["capabilities"]["distinct_runtime_identities"] is True
    assert result["last_probe"]["provider_mutation_attempted"] is False
    assert result["operator_can_request_controls"] is True
    assert result["operator_can_apply_live"] is False
    assert result["production_ready"] is False
    assert result["release_authority"] is result["mutation_authority"] is False
    assert "live_execution_release_held" in result["blockers"]
    assert "cloud_release_controller_unconfigured" in result["blockers"]


def test_missing_readback_and_expired_lease_fail_closed(tmp_path, monkeypatch):
    patch_sources(monkeypatch, requested={**control.LIVE_CONTROLS, "AUREON_LIVE_TRADING": False}, active=False)
    result = control.build_cloud_trading_control_receipt(
        environ={}, now=1_010, readback_path=tmp_path / "missing.json",
    )
    assert result["truth_status"] == "unavailable"
    assert result["read_state"] == "unavailable"
    assert result["last_probe"] is None
    assert "terminal_readback_missing" in result["blockers"]
    assert "operator_authorization_lease_inactive" in result["blockers"]
    assert "operator_live_control_set_not_fully_requested" in result["blockers"]


def test_even_complete_configuration_claims_cannot_self_release(tmp_path, monkeypatch):
    path = tmp_path / "receipt.json"
    path.write_text(json.dumps(readback()), encoding="utf-8")
    patch_sources(monkeypatch)
    env = {
        "AUREON_LIVE_EXECUTION_RELEASE": "1",
        "AUREON_DURABLE_BUDGET_LEDGER": "1",
        "AUREON_ORDER_ADAPTER_READY": "1",
        "AUREON_CLOUD_TRADE_RELEASE_RECEIPT_SHA256": "4" * 64,
        "AUREON_CLOUD_TRADE_PROVIDER_READBACK_SHA256": "5" * 64,
        "AUREON_CLOUD_TRADE_LIVE_RESULT_BINDING_SHA256": "6" * 64,
    }
    result = control.build_cloud_trading_control_receipt(
        environ=env, now=1_010, readback_path=path,
    )
    assert result["capabilities"]["live_execution_release"] is False
    assert result["operator_can_apply_live"] is False
    assert result["production_ready"] is False
    assert "live_execution_release_held" in result["blockers"]
    assert "durable_budget_ledger_unconfigured" in result["blockers"]
    assert "live_order_adapter_unavailable" in result["blockers"]
    assert "all_four_provider_readback_receipt_missing" in result["blockers"]


def test_signed_executor_and_provider_evidence_still_requires_controller(tmp_path, monkeypatch):
    path = tmp_path / "receipt.json"
    path.write_text(json.dumps(readback(ready=True)), encoding="utf-8")
    patch_sources(monkeypatch)
    env = {
        "AUREON_CLOUD_TRADE_RELEASE_RECEIPT_SHA256": "5" * 64,
        "AUREON_CLOUD_TRADE_LIVE_RESULT_BINDING_SHA256": "6" * 64,
    }
    result = control.build_cloud_trading_control_receipt(environ=env, now=1_010, readback_path=path)
    assert result["capabilities"]["durable_budget_ledger"] is True
    assert result["capabilities"]["order_adapter_ready"] is True
    assert result["capabilities"]["all_four_provider_readback_pinned"] is True
    assert result["operator_can_apply_live"] is False
    assert result["blockers"] == [
        "cloud_release_controller_unconfigured", "live_execution_release_held",
    ]


def test_signed_held_controller_makes_operator_activation_eligible(tmp_path, monkeypatch):
    path = tmp_path / "receipt.json"
    path.write_text(json.dumps(readback(ready=True)), encoding="utf-8")
    patch_sources(monkeypatch, controller=True)
    result = control.build_cloud_trading_control_receipt(environ={}, now=1_010, readback_path=path)
    assert result["operator_can_apply_live"] is True
    assert result["production_ready"] is False
    assert result["release_authority"] is False
    assert result["blockers"] == ["live_execution_release_held"]
