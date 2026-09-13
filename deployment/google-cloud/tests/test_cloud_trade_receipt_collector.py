from __future__ import annotations

import base64
import importlib.util
import json
import sys
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


GOOGLE_CLOUD = Path(__file__).parents[1]
MODULE = GOOGLE_CLOUD / "trading-control"
sys.path.insert(0, str(MODULE))

from contract import canonical_bytes  # noqa: E402
from make_probe import build_probe  # noqa: E402
from service import ServiceConfig, create_app  # noqa: E402


spec = importlib.util.spec_from_file_location(
    "cloud_trade_receipt_collector", GOOGLE_CLOUD / "cloud_trade_receipt_collector.py"
)
assert spec and spec.loader
collector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(collector)


class Keys:
    def __init__(self):
        self.private = {role: Ed25519PrivateKey.generate() for role in collector.KEYS}

    def signer(self, role):
        outer = self

        class Signer:
            key_version = collector.KEYS[role]

            def sign(self, data):
                return base64.b64encode(outer.private[role].sign(data)).decode()

        return Signer()

    def verifier(self):
        outer = self

        class Verifier:
            def verify(self, key_version, data, signature):
                role = next(name for name, value in collector.KEYS.items() if value == key_version)
                outer.private[role].public_key().verify(base64.b64decode(signature), data)

        return Verifier()

    def public_reader(self, url, **_kwargs):
        key_version = url.removeprefix("https://cloudkms.googleapis.com/v1/").removesuffix("/publicKey")
        role = next(name for name, value in collector.KEYS.items() if value == key_version)
        pem = self.private[role].public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode()
        return json.dumps({
            "name": key_version, "algorithm": "EC_SIGN_ED25519", "pem": pem,
        }).encode()


class Capture:
    def __init__(self):
        self.value = None

    def publish(self, value):
        self.value = dict(value)
        return "message-1"


CONTROLLER_KEY = (
    "projects/aureon-trading/locations/europe-west1/keyRings/aureon-trading-prod/"
    "cryptoKeys/aureon-controller-signing/cryptoKeyVersions/1"
)


def config(role, *, live=False):
    return ServiceConfig(
        role=role,
        project_id="aureon-trading",
        revision="a" * 40,
        key_version=collector.KEYS[role],
        output_topic="projects/aureon-trading/topics/aureon-trade-next-v1",
        review_key_version=collector.KEYS["review"],
        dispatch_key_version=collector.KEYS["dispatch"],
        executor_key_version=collector.KEYS["executor"],
        live_execution_release=live,
        durable_budget_ledger=live,
        order_adapter_ready=live,
        max_order_usd=5,
        controller_key_version=CONTROLLER_KEY if live else None,
    )


def push(value):
    return {"message": {"data": base64.b64encode(canonical_bytes(value)).decode()}}


class AllowRelease:
    @staticmethod
    def is_active(_intent, *, now_ms):
        return now_ms > 0


class LiveExecutor:
    def __init__(self, budget, max_order):
        assert budget == 20
        assert max_order == 5

    def execute(self, intent, *, dispatch_sha256):
        return {
            "schema": "aureon.cloud-trade-live-result.v1", "status": "provider_observed",
            "reason_code": "provider_order_observed", "dry_run": False,
            "intent_id": intent["intent_id"], "venue": intent["order"]["venue"],
            "provider_order_id": "provider-order-1", "provider_client_order_id": "client-order-1",
            "provider_status": "accepted", "provider_readback_sha256": "8" * 64,
            "instrument_preflight_sha256": "9" * 64,
            "provider_mutation_attempted": True, "orders_attempted": 1,
            "orders_submitted": 1, "dispatch_sha256": dispatch_sha256,
        }


class RuleRejectedExecutor:
    def __init__(self, budget, max_order):
        assert budget == 20
        assert max_order == 5

    def execute(self, intent, *, dispatch_sha256):
        return {
            "schema": "aureon.cloud-trade-live-result.v1", "status": "rejected",
            "reason_code": "alpaca_quantity_below_minimum", "dry_run": False,
            "intent_id": intent["intent_id"], "venue": intent["order"]["venue"],
            "provider_order_id": None, "provider_client_order_id": None,
            "provider_status": None, "provider_readback_sha256": None,
            "instrument_preflight_sha256": None,
            "instrument_readiness_blocker": {
                "schema": "aureon.provider-instrument-readiness-blocker.v1",
                "venue": "alpaca", "reason_code": "alpaca_quantity_below_minimum",
                "minimum_quantity": "0.001", "quantity_step": "0.001",
                "minimum_notional_usd": None, "price_step": None,
                "quantity_unit": None,
            },
            "provider_mutation_attempted": False, "orders_attempted": 0,
            "orders_submitted": 0, "dispatch_sha256": dispatch_sha256,
        }


def terminal_chain(now_ms=1_800_000_000_000, *, live=False, executor_factory=LiveExecutor):
    keys = Keys()
    value = build_probe(
        event_sha256="1" * 64,
        lease_expires_at_ms=now_ms + 3_600_000,
        revision="a" * 40,
        now_ms=now_ms,
    )
    if live:
        value.update({
            "kind": "order", "dry_run": False,
            "requested_controls": {
                "AUREON_DEPLOYMENT_HOLD": False, "AUREON_DISABLE_REAL_ORDERS": False,
                "AUREON_DISABLE_EXCHANGE_MUTATIONS": False, "AUREON_LIVE_TRADING": True,
                "AUREON_ORDER_INTENT_PUBLISH": True, "AUREON_UNIFIED_ORDER_EXECUTOR": True,
            },
            "order": {"venue": "alpaca", "symbol": "BTC/USD", "side": "BUY",
                      "order_type": "MARKET", "quantity": 0.00001, "quote_value_usd": 1.0,
                      "limit_price": None, "client_order_id": "aureon-order-00000003"},
        })
    for role in ("review", "dispatch", "executor", "receipt"):
        capture = Capture()
        app = create_app(
            config=config(role, live=live), signer=keys.signer(role), verifier=keys.verifier(),
            publisher=capture, clock=lambda: now_ms / 1000,
            release_gate=AllowRelease() if live else None,
            executor_factory=executor_factory if role == "executor" and live else None,
        )
        response = app.test_client().post("/process", json=push(value))
        assert response.status_code == 204
        value = capture.value
    return keys, value


def test_collector_verifies_all_four_keys_and_historical_probe():
    now = 1_800_000_000_000
    keys, receipt = terminal_chain(now)
    summary = collector.verify_terminal_receipt(
        receipt, token="x" * 40, now_ms=now + 600_000, reader=keys.public_reader,
    )
    assert summary["chain_verified"] is True
    assert summary["provider_mutation_attempted"] is False
    assert summary["orders_attempted"] == summary["orders_submitted"] == 0
    assert set(summary["authority_ids"]) == {"review", "dispatch", "executor", "receipt"}
    assert summary["source_revision"] == "a" * 40
    assert summary["runtime_measurement_sha256"] == receipt[
        "executor"
    ]["result"]["dispatch"]["review"]["intent"]["runtime_measurement_sha256"]


def test_collector_rejects_tampered_terminal_chain():
    keys, receipt = terminal_chain()
    receipt["executor"]["result"]["outcome"]["orders_attempted"] = 1
    with pytest.raises(RuntimeError, match="terminal_signature_invalid"):
        collector.verify_terminal_receipt(
            receipt, token="x" * 40, now_ms=1_800_000_600_000, reader=keys.public_reader,
        )


def test_collector_binds_provider_observed_live_order_receipt():
    now = 1_800_000_000_000
    keys, receipt = terminal_chain(now, live=True)
    summary = collector.verify_terminal_receipt(
        receipt, token="x" * 40, now_ms=now + 600_000, reader=keys.public_reader,
    )
    assert summary["chain_verified"] is True and summary["dry_run"] is False
    assert summary["outcome_status"] == "provider_observed"
    assert summary["venue"] == "alpaca" and summary["provider_order_id"] == "provider-order-1"
    assert summary["instrument_preflight_sha256"] == "9" * 64
    assert summary["orders_attempted"] == summary["orders_submitted"] == 1


def test_collector_exposes_sanitized_per_venue_rule_readiness_blocker():
    now = 1_800_000_000_000
    keys, receipt = terminal_chain(now, live=True, executor_factory=RuleRejectedExecutor)
    summary = collector.verify_terminal_receipt(
        receipt, token="x" * 40, now_ms=now + 600_000, reader=keys.public_reader,
    )
    assert summary["outcome_status"] == "rejected"
    assert summary["provider_mutation_attempted"] is False
    assert summary["orders_attempted"] == summary["orders_submitted"] == 0
    assert summary["instrument_preflight_sha256"] is None
    assert summary["instrument_readiness_blocker"] == {
        "schema": "aureon.provider-instrument-readiness-blocker.v1",
        "venue": "alpaca", "reason_code": "alpaca_quantity_below_minimum",
        "minimum_quantity": "0.001", "quantity_step": "0.001",
        "minimum_notional_usd": None, "price_step": None, "quantity_unit": None,
    }


def test_active_lease_publishes_canonical_held_probe_without_order():
    calls = []

    def reader(url, **kwargs):
        calls.append((url, kwargs))
        if url == collector.METADATA:
            return json.dumps({"access_token": "x" * 40, "expires_in": 3600}).encode()
        assert url == collector.PROBE_TOPIC
        return b'{"messageIds":["123456789"]}'

    result = collector.publish_control_probe(
        revision="a" * 40,
        reader=reader,
        current_time=lambda: 1_800_000_000,
        environ=dict(collector.REQUIRED_PROBE_HOLDS),
        authorization_builder=lambda **_kwargs: {
            "active": True,
            "ledger_event_sha256": "1" * 64,
            "expires_at": 1_800_003_600,
        },
    )
    assert result and result["message_id"] == "123456789"
    body = json.loads(calls[-1][1]["body"])
    probe = json.loads(base64.b64decode(body["messages"][0]["data"], validate=True))
    assert probe["kind"] == "control_plane_probe" and probe["dry_run"] is True
    assert probe["order"] is None and probe["authorization"]["mutation_authority"] is False
    assert probe["requested_controls"] == {
        "AUREON_DEPLOYMENT_HOLD": True,
        "AUREON_DISABLE_REAL_ORDERS": True,
        "AUREON_DISABLE_EXCHANGE_MUTATIONS": True,
        "AUREON_LIVE_TRADING": False,
        "AUREON_ORDER_INTENT_PUBLISH": False,
        "AUREON_UNIFIED_ORDER_EXECUTOR": False,
    }


def test_active_signed_release_turns_probe_into_exact_generation_bound_refresh():
    calls = []

    def reader(url, **kwargs):
        calls.append((url, kwargs))
        if url == collector.METADATA:
            return json.dumps({"access_token": "x" * 40, "expires_in": 3600}).encode()
        assert url == collector.PROBE_TOPIC
        return b'{"messageIds":["123456789"]}'

    now = 1_800_000_000
    expires_ms = int((now + 3600) * 1000)
    release = {
        "schema": "aureon.cloud-trade-release-state.v1",
        "state": "active",
        "generation": 9,
        "request_id": "2" * 64,
        "requested_controls_sha256": "3" * 64,
        "authorization_event_sha256": "1" * 64,
        "authorization_expires_at_ms": expires_ms,
        "probe_receipt_sha256": "4" * 64,
        "provider_readback_sha256": "5" * 64,
        "source_revision": "a" * 40,
        "signed_at_ms": int((now - 60) * 1000),
        "controller_key_version": CONTROLLER_KEY,
        "signature": "signed-controller-state",
        "update_time": "2026-09-13T15:00:00Z",
    }
    result = collector.publish_control_probe(
        revision="a" * 40,
        reader=reader,
        current_time=lambda: now,
        environ=dict(collector.REQUIRED_PROBE_HOLDS),
        authorization_builder=lambda **_kwargs: {
            "active": True,
            "ledger_event_sha256": "1" * 64,
            "expires_at": now + 3600,
        },
        release=release,
    )
    assert result["mode"] == "periodic_readiness"
    body = json.loads(calls[-1][1]["body"])
    probe = json.loads(base64.b64decode(body["messages"][0]["data"], validate=True))
    binding = probe["authorization"]["readiness_release"]
    assert binding["generation"] == 9
    assert binding["request_id"] == release["request_id"]
    assert binding["authorization_expires_at_ms"] == expires_ms
    assert binding["source_revision"] == "a" * 40
    assert probe["authorization"]["release_authority"] is False
    assert probe["authorization"]["mutation_authority"] is False
    assert probe["order"] is None


def test_probe_publisher_requires_holds_and_active_lease():
    inactive = collector.publish_control_probe(
        revision="a" * 40,
        environ=dict(collector.REQUIRED_PROBE_HOLDS),
        current_time=lambda: 1_800_000_000,
        authorization_builder=lambda **_kwargs: {"active": False},
    )
    assert inactive is None
    weakened = dict(collector.REQUIRED_PROBE_HOLDS)
    weakened["AUREON_DISABLE_REAL_ORDERS"] = "0"
    with pytest.raises(RuntimeError, match="probe_runtime_holds_not_enforced"):
        collector.publish_control_probe(
            revision="a" * 40,
            environ=weakened,
            current_time=lambda: 1_800_000_000,
            authorization_builder=lambda **_kwargs: {"active": False},
        )
