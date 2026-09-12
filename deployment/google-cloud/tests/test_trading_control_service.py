from __future__ import annotations

import base64
import hashlib
import sys
from pathlib import Path

import pytest


MODULE = Path(__file__).parents[1] / "trading-control"
sys.path.insert(0, str(MODULE))

from contract import (  # noqa: E402
    ContractError,
    DISPATCH_SCHEMA,
    EXECUTOR_SCHEMA,
    INTENT_SCHEMA,
    RECEIPT_SCHEMA,
    REVIEW_SCHEMA,
    canonical_bytes,
    validate_intent,
)
from service import ServiceConfig, create_app  # noqa: E402


PROJECT = "aureon-trading"
PREFIX = f"projects/{PROJECT}/locations/europe-west1/keyRings/aureon-trading-prod/cryptoKeys"
KEYS = {
    "review": f"{PREFIX}/aureon-review-signing/cryptoKeyVersions/1",
    "dispatch": f"{PREFIX}/aureon-dispatch-signing/cryptoKeyVersions/1",
    "executor": f"{PREFIX}/aureon-executor-signing/cryptoKeyVersions/1",
    "receipt": f"{PREFIX}/aureon-receipt-signing/cryptoKeyVersions/1",
}


class FakeKms:
    def __init__(self, key_version: str):
        self.key_version = key_version

    @staticmethod
    def _signature(key_version: str, data: bytes) -> str:
        return base64.b64encode(hashlib.sha512(key_version.encode() + b"\0" + data).digest()).decode()

    def sign(self, data: bytes) -> str:
        return self._signature(self.key_version, data)

    def verify(self, key_version: str, data: bytes, signature: str) -> None:
        if signature != self._signature(key_version, data):
            raise RuntimeError("signature mismatch")


class CapturePublisher:
    def __init__(self):
        self.values: list[dict] = []

    def publish(self, value):
        self.values.append(dict(value))
        return f"message-{len(self.values)}"


def config(role: str, *, live=False, budget=False, adapter=False, provider_probe=False) -> ServiceConfig:
    return ServiceConfig(
        role=role,
        project_id=PROJECT,
        revision="a" * 40,
        key_version=KEYS[role],
        output_topic=f"projects/{PROJECT}/topics/aureon-trade-next-v1",
        review_key_version=KEYS["review"] if role in {"dispatch", "executor", "receipt"} else None,
        dispatch_key_version=KEYS["dispatch"] if role in {"executor", "receipt"} else None,
        executor_key_version=KEYS["executor"] if role == "receipt" else None,
        live_execution_release=live,
        durable_budget_ledger=budget,
        order_adapter_ready=adapter,
        max_order_usd=5.0,
        provider_probe_enabled=provider_probe,
        max_daily_budget_usd=20.0,
    )


def probe(now_ms=1_800_000_000_000):
    safe = {
        "AUREON_DEPLOYMENT_HOLD": True,
        "AUREON_DISABLE_REAL_ORDERS": True,
        "AUREON_DISABLE_EXCHANGE_MUTATIONS": True,
        "AUREON_LIVE_TRADING": False,
        "AUREON_ORDER_INTENT_PUBLISH": False,
        "AUREON_UNIFIED_ORDER_EXECUTOR": False,
    }
    return {
        "schema": INTENT_SCHEMA,
        "intent_id": "1" * 64,
        "kind": "control_plane_probe",
        "tenant_commitment": "2" * 64,
        "account_scope": "owner",
        "created_at_ms": now_ms,
        "expires_at_ms": now_ms + 30_000,
        "authorization": {
            "active": True,
            "expires_at_ms": now_ms + 3_600_000,
            "event_sha256": "3" * 64,
            "scope_sha256": "4" * 64,
            "release_authority": False,
            "mutation_authority": False,
        },
        "requested_controls": safe,
        "market_evidence_sha256": "5" * 64,
        "runtime_measurement_sha256": "6" * 64,
        "order": None,
        "dry_run": True,
    }


def push(value: dict) -> dict:
    return {
        "message": {
            "messageId": "provider-message-1",
            "data": base64.b64encode(canonical_bytes(value)).decode(),
        },
        "subscription": "projects/aureon-trading/subscriptions/test",
    }


def run_stage(role: str, value: dict, *, now_ms=1_800_000_000_000,
              live=False, budget=False, adapter=False, provider_probe=False,
              executor_factory=None):
    out = CapturePublisher()
    cfg = config(role, live=live, budget=budget, adapter=adapter, provider_probe=provider_probe)
    app = create_app(
        config=cfg,
        signer=FakeKms(KEYS[role]),
        verifier=FakeKms(KEYS[role]),
        publisher=out,
        clock=lambda: now_ms / 1000,
        executor_factory=executor_factory,
    )
    response = app.test_client().post("/process", json=push(value))
    return response, out.values


def test_probe_crosses_four_distinct_signed_stages_without_mutation():
    source = probe()
    review_response, review_values = run_stage("review", source)
    assert review_response.status_code == 204
    review = review_values[0]
    assert review["schema"] == REVIEW_SCHEMA
    assert review["key_version"] == KEYS["review"]

    dispatch_response, dispatch_values = run_stage("dispatch", review)
    assert dispatch_response.status_code == 204
    dispatch = dispatch_values[0]
    assert dispatch["schema"] == DISPATCH_SCHEMA
    assert dispatch["key_version"] == KEYS["dispatch"]

    executor_response, executor_values = run_stage("executor", dispatch)
    assert executor_response.status_code == 204
    executor = executor_values[0]
    assert executor["schema"] == EXECUTOR_SCHEMA
    assert executor["key_version"] == KEYS["executor"]
    assert executor["result"]["outcome"] == {
        "schema": "aureon.cloud-trade-probe-result.v1",
        "status": "probe_passed",
        "dry_run": True,
        "provider_mutation_attempted": False,
        "orders_attempted": 0,
        "orders_submitted": 0,
        "dispatch_sha256": executor["result"]["outcome"]["dispatch_sha256"],
        "provider_readback": None,
        "executor_capabilities": {
            "live_execution_release": False,
            "durable_budget_ledger": False,
            "order_adapter_ready": False,
        },
    }

    receipt_response, receipt_values = run_stage("receipt", executor)
    assert receipt_response.status_code == 204
    receipt = receipt_values[0]
    assert receipt["schema"] == RECEIPT_SCHEMA
    assert receipt["key_version"] == KEYS["receipt"]
    assert receipt["executor"]["result"]["outcome"]["provider_mutation_attempted"] is False


def test_redelivery_produces_identical_review_wire():
    value = probe()
    first, first_values = run_stage("review", value)
    second, second_values = run_stage("review", value)
    assert first.status_code == second.status_code == 204
    assert canonical_bytes(first_values[0]) == canonical_bytes(second_values[0])


def test_order_is_rejected_while_release_is_held():
    value = probe()
    value.update({
        "kind": "order", "dry_run": False,
        "requested_controls": {
            "AUREON_DEPLOYMENT_HOLD": False,
            "AUREON_DISABLE_REAL_ORDERS": False,
            "AUREON_DISABLE_EXCHANGE_MUTATIONS": False,
            "AUREON_LIVE_TRADING": True,
            "AUREON_ORDER_INTENT_PUBLISH": True,
            "AUREON_UNIFIED_ORDER_EXECUTOR": True,
        },
        "order": {
            "venue": "binance", "symbol": "BTCUSDT", "side": "BUY",
            "order_type": "MARKET", "quantity": 0.00001, "quote_value_usd": 1.0,
            "limit_price": None, "client_order_id": "aureon-order-00000001",
        },
    })
    response, values = run_stage("review", value)
    assert response.status_code == 400
    assert response.get_json()["reason_code"] == "live_execution_release_held"
    assert values == []


def test_order_contract_rejects_budget_excess_before_transport():
    value = probe()
    value.update({
        "kind": "order", "dry_run": False,
        "requested_controls": {
            "AUREON_DEPLOYMENT_HOLD": False,
            "AUREON_DISABLE_REAL_ORDERS": False,
            "AUREON_DISABLE_EXCHANGE_MUTATIONS": False,
            "AUREON_LIVE_TRADING": True,
            "AUREON_ORDER_INTENT_PUBLISH": True,
            "AUREON_UNIFIED_ORDER_EXECUTOR": True,
        },
        "order": {
            "venue": "kraken", "symbol": "BTC/USD", "side": "BUY",
            "order_type": "LIMIT", "quantity": 0.001, "quote_value_usd": 6.0,
            "limit_price": 60_000.0, "client_order_id": "aureon-order-00000002",
        },
    })
    with pytest.raises(ContractError, match="order_budget_exceeded"):
        validate_intent(value, now_ms=value["created_at_ms"], max_order_usd=5.0, live_release=True)


def test_service_config_rejects_wrong_role_key():
    values = {
        "AUREON_TRADING_AUTHORITY_ROLE": "executor",
        "AUREON_GCP_PROJECT": PROJECT,
        "AUREON_REVISION": "a" * 40,
        "AUREON_KMS_KEY_VERSION": KEYS["review"],
        "AUREON_OUTPUT_TOPIC": f"projects/{PROJECT}/topics/out",
    }
    with pytest.raises(RuntimeError, match="service_signing_key_invalid"):
        ServiceConfig.from_env(values)


def test_health_reports_probe_ready_and_live_held():
    out = CapturePublisher()
    app = create_app(config=config("review"), signer=FakeKms(KEYS["review"]),
                     verifier=FakeKms(KEYS["review"]), publisher=out)
    payload = app.test_client().get("/healthz").get_json()
    assert payload["ok"] is True
    assert payload["probe_path_ready"] is True
    assert payload["live_execution_release"] is False
    assert payload["production_ready"] is False


class FakeLiveExecutor:
    def __init__(self, daily_budget):
        assert daily_budget == 20.0

    def provider_probe(self):
        return {"schema": "aureon.cloud-trade-provider-readback.v1", "provider_count": 4,
                "all_authenticated": True, "providers": {}, "provider_mutation_attempted": False,
                "readback_sha256": "7" * 64}

    def execute(self, intent, *, dispatch_sha256):
        return {"schema": "aureon.cloud-trade-live-result.v1", "status": "provider_observed",
                "reason_code": "provider_order_observed", "dry_run": False,
                "intent_id": intent["intent_id"], "venue": intent["order"]["venue"],
                "provider_order_id": "provider-order", "provider_client_order_id": "provider-client",
                "provider_status": "accepted", "provider_readback_sha256": "8" * 64,
                "provider_mutation_attempted": True, "orders_attempted": 1,
                "orders_submitted": 1, "dispatch_sha256": dispatch_sha256}


def test_executor_probe_can_bind_all_four_read_only_provider_accounts():
    source = probe()
    _, reviews = run_stage("review", source)
    _, dispatches = run_stage("dispatch", reviews[0])
    response, executors = run_stage(
        "executor", dispatches[0], provider_probe=True,
        executor_factory=lambda budget: FakeLiveExecutor(budget),
    )
    assert response.status_code == 204
    provider_readback = executors[0]["result"]["outcome"]["provider_readback"]
    assert provider_readback["provider_count"] == 4 and provider_readback["all_authenticated"] is True


def test_released_order_crosses_executor_and_receipt_with_provider_readback():
    source = probe()
    source.update({
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
    _, reviews = run_stage("review", source, live=True)
    _, dispatches = run_stage("dispatch", reviews[0], live=True)
    executor_response, executors = run_stage(
        "executor", dispatches[0], live=True, budget=True, adapter=True,
        executor_factory=lambda budget: FakeLiveExecutor(budget),
    )
    assert executor_response.status_code == 204
    outcome = executors[0]["result"]["outcome"]
    assert outcome["orders_submitted"] == 1 and outcome["provider_readback_sha256"] == "8" * 64
    receipt_response, receipts = run_stage("receipt", executors[0], live=True)
    assert receipt_response.status_code == 204
    assert receipts[0]["executor"]["result"]["outcome"]["status"] == "provider_observed"
