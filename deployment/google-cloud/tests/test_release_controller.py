from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1] / "trading-control"
sys.path.insert(0, str(ROOT))
from contract import (  # noqa: E402
    canonical_bytes,
    digest,
    probe_runtime_measurement_sha256,
    provider_readback_commitment_sha256,
)
spec = importlib.util.spec_from_file_location("release_controller", ROOT / "release_controller.py")
controller = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = controller
spec.loader.exec_module(controller)


KEY = "projects/aureon-trading/locations/europe-west1/keyRings/aureon-trading-prod/cryptoKeys/aureon-controller-signing/cryptoKeyVersions/1"
REVISION = "a" * 40


def execution_readiness(revision=REVISION, observed_at_ms=1_000_000):
    enough = {"status": "sufficient", "allowance_usd": "5"}
    return {
        "schema": "aureon.cloud-trade-execution-budget-readiness.v1",
        "source_revision": revision,
        "observed_at_ms": observed_at_ms,
        "maximum_order_usd": "5",
        "venues": {
            "alpaca": {"authenticated": True, "quotes": {"USD": dict(enough)}},
            "binance": {"authenticated": True, "quotes": {
                asset: dict(enough) for asset in ("FDUSD", "USD", "USDC", "USDT")
            }},
            "capital": {"authenticated": True, "quotes": {"USD": dict(enough)}},
            "kraken": {"authenticated": True, "quotes": {
                asset: dict(enough) for asset in ("FDUSD", "USD", "USDC", "USDT")
            }},
        },
    }


def provider_readback(revision=REVISION, observed_at_ms=1_000_000):
    providers = {
        venue: {
            "venue": venue, "authenticated": True,
            "account_binding_sha256": str(index) * 64,
        }
        for index, venue in enumerate(("alpaca", "binance", "capital", "kraken"), 1)
    }
    readiness = execution_readiness(revision, observed_at_ms)
    accounts_sha = digest(providers)
    readiness_sha = digest(readiness)
    return {
        "schema": "aureon.cloud-trade-provider-readback.v1",
        "providers": providers, "provider_count": 4, "all_authenticated": True,
        "provider_mutation_attempted": False, "instrument_preflight_enforced": True,
        "provider_accounts_sha256": accounts_sha,
        "execution_budget_readiness": readiness,
        "execution_budget_readiness_sha256": readiness_sha,
        "readback_sha256": provider_readback_commitment_sha256(accounts_sha, readiness_sha),
    }


class Signer:
    def sign(self, _data):
        return "c2lnbmF0dXJl" * 6


class Publisher:
    def __init__(self):
        self.values = []

    def publish(self, value):
        self.values.append(value)
        return "message-1"


class Store:
    def __init__(self, probe):
        self.probe = probe
        self.release = None

    def read_probe(self):
        return self.probe

    def read_release(self):
        return self.release

    def put_release(self, fields, *, expected_update_time):
        assert expected_update_time is None
        self.release = {**fields, "update_time": "2026-09-12T20:00:00Z"}
        return self.release


def config():
    return controller.ControllerConfig(
        project="aureon-trading", revision=REVISION, key_version=KEY,
        output_topic="projects/aureon-trading/topics/aureon-trade-release-receipts-v1",
    )


def request(*, action="activate", now=1_000_000):
    live = {
        "AUREON_DEPLOYMENT_HOLD": False,
        "AUREON_DISABLE_REAL_ORDERS": False,
        "AUREON_DISABLE_EXCHANGE_MUTATIONS": False,
        "AUREON_LIVE_TRADING": True,
        "AUREON_ORDER_INTENT_PUBLISH": True,
        "AUREON_UNIFIED_ORDER_EXECUTOR": True,
    }
    if action == "hold":
        live.update(AUREON_DEPLOYMENT_HOLD=True, AUREON_DISABLE_REAL_ORDERS=True,
                    AUREON_DISABLE_EXCHANGE_MUTATIONS=True, AUREON_LIVE_TRADING=False,
                    AUREON_ORDER_INTENT_PUBLISH=False, AUREON_UNIFIED_ORDER_EXECUTOR=False)
    row = {
        "schema": controller.REQUEST_SCHEMA, "action": action,
        "created_at_ms": now, "expires_at_ms": now + 60_000,
        "requested_controls": live,
        "authorization_event_sha256": "1" * 64 if action == "activate" else None,
        "authorization_expires_at_ms": now + 200_000 if action == "activate" else None,
        "probe_receipt_sha256": "2" * 64 if action == "activate" else None,
        "provider_readback_sha256": provider_readback(observed_at_ms=now)["readback_sha256"] if action == "activate" else None,
        "source_revision": REVISION,
    }
    row["request_id"] = controller.digest(row)
    return row


def probe(now=1_000_000, revision=REVISION):
    provider = provider_readback(revision=revision, observed_at_ms=now)
    readiness = provider["execution_budget_readiness"]
    return {
        "schema": "aureon.cloud-trade-probe-attestation.v2",
        "receipt_sha256": "2" * 64, "intent_id": "4" * 64,
        "intent_created_at_ms": now - 1_000, "stored_at_ms": now,
        "authorization_event_sha256": "1" * 64,
        "authorization_expires_at_ms": now + 200_000,
        "provider_readback_sha256": provider["readback_sha256"], "provider_count": 4,
        "provider_accounts_sha256": provider["provider_accounts_sha256"],
        "execution_budget_readiness_sha256": provider["execution_budget_readiness_sha256"],
        "execution_budget_readiness_json": canonical_bytes(readiness).decode("ascii"),
        "all_authenticated": True, "durable_budget_ledger": True,
        "order_adapter_ready": True, "live_result_binding_ready": True,
        "instrument_preflight_enforced": True,
        "runtime_measurement_sha256": probe_runtime_measurement_sha256(revision),
        "source_revision": revision,
        "update_time": "2026-09-12T20:00:00Z",
    }


def terminal_probe(revision=REVISION):
    provider = provider_readback(revision, 1_000_000)
    return {
        "executor": {"result": {
            "dispatch": {"review": {"intent": {
                "intent_id": "4" * 64,
                "kind": "control_plane_probe",
                "created_at_ms": 999_000,
                "source_revision": revision,
                "runtime_measurement_sha256": probe_runtime_measurement_sha256(revision),
                "authorization": {
                    "event_sha256": "1" * 64,
                    "expires_at_ms": 1_200_000,
                },
            }}},
            "outcome": {
                "executor_capabilities": {
                    "live_execution_release": False,
                    "durable_budget_ledger": True,
                    "order_adapter_ready": True,
                    "live_result_binding_ready": True,
                    "instrument_preflight_enforced": True,
                },
                "provider_readback": {
                    **provider,
                },
            },
        }},
    }


def test_activate_requires_current_matching_probe_and_writes_signed_state():
    output = Publisher()
    store = Store(probe())
    receipt = controller.process_release_request(
        request(), now_ms=1_000_000, config=config(), signer=Signer(),
        store=store, publisher=output,
    )
    assert store.release["state"] == "active"
    assert store.release["generation"] == 1
    assert receipt["release_authority"] is True
    assert receipt["mutation_authority"] is False
    assert output.values == [{key: value for key, value in receipt.items() if key != "firestore_update_time"}]


def test_hold_is_always_available_without_probe_or_lease():
    store = Store(None)
    receipt = controller.process_release_request(
        request(action="hold"), now_ms=1_000_000, config=config(), signer=Signer(),
        store=store, publisher=Publisher(),
    )
    assert receipt["state"] == "held" and receipt["release_authority"] is False


def test_activate_rejects_mismatched_probe():
    mismatched = probe()
    mismatched["provider_readback_sha256"] = "9" * 64
    with pytest.raises(controller.CloudStateError, match="probe_attestation_invalid"):
        controller.process_release_request(
            request(), now_ms=1_000_000, config=config(), signer=Signer(),
            store=Store(mismatched), publisher=Publisher(),
        )


def test_activate_rejects_probe_from_before_instrument_preflight_gate():
    legacy = probe()
    legacy.pop("instrument_preflight_enforced")
    with pytest.raises(controller.CloudStateError, match="probe_attestation_invalid"):
        controller.process_release_request(
            request(), now_ms=1_000_000, config=config(), signer=Signer(),
            store=Store(legacy), publisher=Publisher(),
        )


def test_activate_rejects_fresh_signed_probe_from_an_old_source_revision():
    old_revision = "b" * 40
    stale = probe(revision=old_revision)
    with pytest.raises(controller.ContractError, match="release_probe_evidence_mismatch"):
        controller.process_release_request(
            request(), now_ms=1_000_000, config=config(), signer=Signer(),
            store=Store(stale), publisher=Publisher(),
        )


def test_probe_attestation_storage_binds_signed_measurement_to_service_revision(monkeypatch):
    state = controller.FirestoreControlState()
    writes = []
    monkeypatch.setattr(state, "read_probe", lambda: None)
    monkeypatch.setattr(
        state, "_write",
        lambda document, fields, *, expected_update_time: writes.append(
            (document, dict(fields), expected_update_time)
        ) or {**fields, "update_time": "now"},
    )
    written = state.put_probe_attestation(
        terminal_probe(), source_revision=REVISION, stored_at_ms=1_000_000,
    )
    assert written["source_revision"] == REVISION
    assert written["runtime_measurement_sha256"] == probe_runtime_measurement_sha256(REVISION)
    assert len(writes) == 1

    with pytest.raises(controller.CloudStateError, match="probe_attestation_shape_invalid"):
        state.put_probe_attestation(
            terminal_probe("b" * 40), source_revision=REVISION, stored_at_ms=1_000_000,
        )
    assert len(writes) == 1
