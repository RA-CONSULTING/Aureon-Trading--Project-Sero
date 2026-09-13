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
    build_periodic_readiness_statement,
    build_readiness_release_binding,
    canonical_bytes,
    digest,
    probe_runtime_measurement_sha256,
    provider_readback_commitment_sha256,
    validate_intent,
    validate_readiness_envelope,
)
from service import ServiceConfig, create_app  # noqa: E402
from cloud_state import (  # noqa: E402
    FirestoreControlState,
    validate_periodic_readiness_document,
)


PROJECT = "aureon-trading"
PREFIX = f"projects/{PROJECT}/locations/europe-west1/keyRings/aureon-trading-prod/cryptoKeys"
KEYS = {
    "review": f"{PREFIX}/aureon-review-signing/cryptoKeyVersions/1",
    "dispatch": f"{PREFIX}/aureon-dispatch-signing/cryptoKeyVersions/1",
    "executor": f"{PREFIX}/aureon-executor-signing/cryptoKeyVersions/1",
    "receipt": f"{PREFIX}/aureon-receipt-signing/cryptoKeyVersions/1",
    "controller": f"{PREFIX}/aureon-controller-signing/cryptoKeyVersions/1",
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


def config(role: str, *, live=False, budget=False, adapter=False, provider_probe=False,
           attestation_store=False) -> ServiceConfig:
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
        controller_key_version=KEYS["controller"] if live else None,
        attestation_store_enabled=attestation_store,
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
        "runtime_measurement_sha256": probe_runtime_measurement_sha256("a" * 40),
        "source_revision": "a" * 40,
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
              executor_factory=None, release_gate=None, attestation_store=None):
    out = CapturePublisher()
    cfg = config(
        role, live=live, budget=budget, adapter=adapter,
        provider_probe=provider_probe,
        attestation_store=attestation_store is not None,
    )
    class AllowRelease:
        @staticmethod
        def is_active(_intent, *, now_ms):
            assert now_ms == 1_800_000_000_000
            return True
    app = create_app(
        config=cfg,
        signer=FakeKms(KEYS[role]),
        verifier=FakeKms(KEYS[role]),
        publisher=out,
        clock=lambda: now_ms / 1000,
        executor_factory=executor_factory,
        release_gate=release_gate or (AllowRelease() if live else None),
        attestation_store=attestation_store,
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
            "live_result_binding_ready": True,
            "instrument_preflight_enforced": True,
        },
    }

    receipt_response, receipt_values = run_stage("receipt", executor)
    assert receipt_response.status_code == 204
    receipt = receipt_values[0]
    assert receipt["schema"] == RECEIPT_SCHEMA
    assert receipt["key_version"] == KEYS["receipt"]
    assert receipt["executor"]["result"]["outcome"]["provider_mutation_attempted"] is False


def test_authority_rejects_fresh_probe_from_another_source_revision():
    source = probe()
    source["source_revision"] = "b" * 40
    source["runtime_measurement_sha256"] = probe_runtime_measurement_sha256("b" * 40)
    response, values = run_stage("review", source)
    assert response.status_code == 204
    assert values == []


def test_probe_measurement_cannot_be_replayed_under_another_signed_revision():
    source = probe()
    source["runtime_measurement_sha256"] = probe_runtime_measurement_sha256("b" * 40)
    response, values = run_stage("review", source)
    assert response.status_code == 204
    assert values == []


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
    assert response.status_code == 204
    assert response.data == b""
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
    def __init__(self, daily_budget, max_order):
        assert daily_budget == 20.0
        assert max_order == 5.0

    def provider_probe(self, *, source_revision, observed_at_ms):
        assert source_revision == "a" * 40
        readiness = {
            "schema": "aureon.cloud-trade-execution-budget-readiness.v1",
            "source_revision": source_revision,
            "observed_at_ms": observed_at_ms,
            "maximum_order_usd": "5",
            "venues": {
                "alpaca": {"authenticated": True, "quotes": {
                    "USD": {"status": "sufficient", "allowance_usd": "5"},
                }},
                "binance": {"authenticated": True, "quotes": {
                    asset: {"status": "sufficient", "allowance_usd": "5"}
                    for asset in ("FDUSD", "USD", "USDC", "USDT")
                }},
                "capital": {"authenticated": True, "quotes": {
                    "USD": {"status": "sufficient", "allowance_usd": "5"},
                }},
                "kraken": {"authenticated": True, "quotes": {
                    asset: {"status": "sufficient", "allowance_usd": "5"}
                    for asset in ("FDUSD", "USD", "USDC", "USDT")
                }},
            },
        }
        providers = {
            venue: {
                "venue": venue, "authenticated": True,
                "account_binding_sha256": str(index) * 64,
            }
            for index, venue in enumerate(("alpaca", "binance", "capital", "kraken"), 1)
        }
        accounts_sha = digest(providers)
        readiness_sha = digest(readiness)
        return {
            "schema": "aureon.cloud-trade-provider-readback.v1", "provider_count": 4,
            "all_authenticated": True, "providers": providers,
            "provider_mutation_attempted": False,
            "instrument_preflight_enforced": True,
            "provider_accounts_sha256": accounts_sha,
            "execution_budget_readiness": readiness,
            "execution_budget_readiness_sha256": readiness_sha,
            "readback_sha256": provider_readback_commitment_sha256(
                accounts_sha, readiness_sha,
            ),
        }

    def execute(self, intent, *, dispatch_sha256):
        return {"schema": "aureon.cloud-trade-live-result.v1", "status": "provider_observed",
                "reason_code": "provider_order_observed", "dry_run": False,
                "intent_id": intent["intent_id"], "venue": intent["order"]["venue"],
                "provider_order_id": "provider-order", "provider_client_order_id": "provider-client",
                "provider_status": "accepted", "provider_readback_sha256": "8" * 64,
                "instrument_preflight_sha256": "9" * 64,
                "provider_mutation_attempted": True, "orders_attempted": 1,
                "orders_submitted": 1, "dispatch_sha256": dispatch_sha256}


class FakeRuleRejectedExecutor:
    def __init__(self, daily_budget, max_order):
        assert daily_budget == 20.0
        assert max_order == 5.0

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


def active_release(now_ms=1_800_000_000_000, *, generation=7):
    return {
        "schema": "aureon.cloud-trade-release-state.v1",
        "state": "active",
        "generation": generation,
        "request_id": "a" * 64,
        "requested_controls_sha256": digest({
            "AUREON_DEPLOYMENT_HOLD": False,
            "AUREON_DISABLE_REAL_ORDERS": False,
            "AUREON_DISABLE_EXCHANGE_MUTATIONS": False,
            "AUREON_LIVE_TRADING": True,
            "AUREON_ORDER_INTENT_PUBLISH": True,
            "AUREON_UNIFIED_ORDER_EXECUTOR": True,
        }),
        "authorization_event_sha256": "3" * 64,
        "authorization_expires_at_ms": now_ms + 3_600_000,
        "probe_receipt_sha256": "b" * 64,
        "provider_readback_sha256": "c" * 64,
        "source_revision": "a" * 40,
        "signed_at_ms": now_ms - 30_000,
        "controller_key_version": KEYS["controller"],
        "signature": "controller-signature",
        "update_time": "2026-09-13T15:00:00Z",
    }


class BoundRelease:
    def __init__(self, value):
        self.value = value

    def active_state(self, intent, *, now_ms):
        binding = intent.get("authorization", {}).get("readiness_release")
        if (
            binding == build_readiness_release_binding(self.value)
            and self.value["authorization_expires_at_ms"] > now_ms
        ):
            return self.value
        return None


class ActiveRelease:
    def __init__(self, value):
        self.value = value

    def active_state(self, intent, *, now_ms):
        authorization = intent.get("authorization", {})
        if (
            self.value["authorization_event_sha256"] == authorization.get("event_sha256")
            and self.value["authorization_expires_at_ms"] == authorization.get("expires_at_ms")
            and self.value["authorization_expires_at_ms"] > now_ms
        ):
            return self.value
        return None


class ReadinessStore:
    def __init__(self):
        self.periodic = []
        self.activation = []

    def put_periodic_readiness_attestation(
        self, executor_attestation, receipt_endorsement, *, stored_at_ms,
    ):
        self.periodic.append((executor_attestation, receipt_endorsement, stored_at_ms))
        return {"update_time": "now"}

    def put_probe_attestation(self, terminal, *, source_revision, stored_at_ms):
        self.activation.append((terminal, source_revision, stored_at_ms))
        return {"update_time": "now"}


def periodic_probe(now_ms=1_800_000_000_000, *, release=None):
    value = probe(now_ms)
    current_release = release or active_release(now_ms)
    value["authorization"]["readiness_release"] = build_readiness_release_binding(
        current_release,
    )
    return value


def test_periodic_readiness_crosses_chain_and_writes_two_detached_kms_envelopes():
    now_ms = 1_800_000_000_000
    release = active_release(now_ms)
    gate = BoundRelease(release)
    value = periodic_probe(now_ms, release=release)
    store = ReadinessStore()
    for role in ("review", "dispatch", "executor", "receipt"):
        response, values = run_stage(
            role,
            value,
            now_ms=now_ms,
            live=True,
            budget=True,
            adapter=True,
            provider_probe=role == "executor",
            executor_factory=(
                (lambda budget, maximum: FakeLiveExecutor(budget, maximum))
                if role == "executor" else None
            ),
            release_gate=gate,
            attestation_store=store if role == "receipt" else None,
        )
        assert response.status_code == 204
        value = values[0]
    assert store.activation == [] and len(store.periodic) == 1
    executor_attestation, receipt_endorsement, stored_at_ms = store.periodic[0]
    executor_attestation = validate_readiness_envelope(
        executor_attestation, role="executor", now_ms=now_ms,
    )
    receipt_endorsement = validate_readiness_envelope(
        receipt_endorsement,
        role="receipt",
        now_ms=now_ms,
        executor_attestation_sha256=digest(executor_attestation),
    )
    statement = executor_attestation["statement"]
    assert stored_at_ms == statement["observed_at_ms"] == now_ms
    assert statement["expires_at_ms"] == now_ms + 300_000
    assert statement["authorization_expires_at_ms"] == release["authorization_expires_at_ms"]
    assert statement["release_generation"] == release["generation"]
    assert receipt_endorsement["release_state_sha256"] == statement["release_state_sha256"]
    assert executor_attestation["key_version"] == KEYS["executor"]
    assert receipt_endorsement["key_version"] == KEYS["receipt"]
    serialized = canonical_bytes(executor_attestation).decode("ascii").lower()
    for forbidden in (
        "balance", "deployable_cash", "api_key", "secret_key", "password", "token",
    ):
        assert forbidden not in serialized
    assert float(statement["maximum_order_usd"]) <= 5
    allowances = {
        quote["allowance_usd"]
        for venue in statement["execution_budget_readiness"]["venues"].values()
        for quote in venue["quotes"].values()
    }
    assert allowances <= {"0", "5"}
    firestore = FirestoreControlState()
    firestore.read_readiness = lambda: None
    firestore._write = lambda _document, fields, *, expected_update_time: {
        **fields, "update_time": "now",
    }
    document = firestore.put_periodic_readiness_attestation(
        executor_attestation, receipt_endorsement, stored_at_ms=now_ms,
    )
    validated_document = validate_periodic_readiness_document(
        document, now_ms=now_ms,
    )
    assert validated_document["release_generation"] == release["generation"]
    assert len(document["executor_attestation_json"]) <= 4096
    assert len(document["receipt_endorsement_json"]) <= 4096


def test_active_release_keeps_the_pinned_activation_probe_immutable():
    now_ms = 1_800_000_000_000
    release = active_release(now_ms)
    gate = ActiveRelease(release)
    value = probe(now_ms)
    store = ReadinessStore()
    for role in ("review", "dispatch", "executor", "receipt"):
        response, values = run_stage(
            role,
            value,
            now_ms=now_ms,
            live=True,
            budget=True,
            adapter=True,
            provider_probe=role == "executor",
            executor_factory=(
                (lambda budget, maximum: FakeLiveExecutor(budget, maximum))
                if role == "executor" else None
            ),
            release_gate=gate,
            attestation_store=store if role == "receipt" else None,
        )
        assert response.status_code == 204
        value = values[0]
    assert store.activation == []
    assert store.periodic == []


def test_periodic_readiness_wrong_generation_fails_before_provider_probe():
    now_ms = 1_800_000_000_000
    release = active_release(now_ms)
    value = periodic_probe(now_ms, release=active_release(now_ms, generation=6))
    _, reviews = run_stage("review", value, live=True, release_gate=BoundRelease(release))
    _, dispatches = run_stage(
        "dispatch", reviews[0], live=True, release_gate=BoundRelease(release),
    )

    class MustNotProbe:
        def __init__(self, *_args):
            pass

        def provider_probe(self, **_kwargs):
            raise AssertionError("provider probe must remain unopened")

    response, values = run_stage(
        "executor",
        dispatches[0],
        live=True,
        budget=True,
        adapter=True,
        provider_probe=True,
        executor_factory=MustNotProbe,
        release_gate=BoundRelease(release),
    )
    assert response.status_code == 204 and values == []


def test_periodic_refresh_rotates_evidence_without_extending_controller_lease():
    first_ms = 1_800_000_000_000
    second_ms = first_ms + 120_000
    release = active_release(first_ms)
    binding = build_readiness_release_binding(release)
    capabilities = {
        "live_execution_release": True,
        "durable_budget_ledger": True,
        "order_adapter_ready": True,
        "live_result_binding_ready": True,
        "instrument_preflight_enforced": True,
    }
    statements = []
    for observed_at_ms in (first_ms, second_ms):
        candidate = probe(observed_at_ms)
        candidate["authorization"]["expires_at_ms"] = release[
            "authorization_expires_at_ms"
        ]
        candidate["authorization"]["readiness_release"] = binding
        provider_readback = FakeLiveExecutor(20, 5).provider_probe(
            source_revision="a" * 40,
            observed_at_ms=observed_at_ms,
        )
        statements.append(build_periodic_readiness_statement(
            candidate, provider_readback, capabilities, now_ms=observed_at_ms,
        ))
    first, second = statements
    assert first["release_state_sha256"] == second["release_state_sha256"]
    assert first["release_generation"] == second["release_generation"] == 7
    assert first["authorization_expires_at_ms"] == second[
        "authorization_expires_at_ms"
    ] == release["authorization_expires_at_ms"]
    assert second["expires_at_ms"] == second_ms + 300_000
    assert second["expires_at_ms"] < release["authorization_expires_at_ms"]
    assert digest(first) != digest(second)


def test_executor_probe_can_bind_all_four_read_only_provider_accounts():
    source = probe()
    _, reviews = run_stage("review", source)
    _, dispatches = run_stage("dispatch", reviews[0])
    response, executors = run_stage(
        "executor", dispatches[0], provider_probe=True,
        executor_factory=lambda budget, max_order: FakeLiveExecutor(budget, max_order),
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
        executor_factory=lambda budget, max_order: FakeLiveExecutor(budget, max_order),
    )
    assert executor_response.status_code == 204
    outcome = executors[0]["result"]["outcome"]
    assert outcome["orders_submitted"] == 1 and outcome["provider_readback_sha256"] == "8" * 64
    receipt_response, receipts = run_stage("receipt", executors[0], live=True)
    assert receipt_response.status_code == 204
    assert receipts[0]["executor"]["result"]["outcome"]["status"] == "provider_observed"


def test_executor_refuses_live_result_without_instrument_preflight_commitment():
    class MissingPreflight(FakeLiveExecutor):
        def execute(self, intent, *, dispatch_sha256):
            result = super().execute(intent, dispatch_sha256=dispatch_sha256)
            result.pop("instrument_preflight_sha256")
            return result

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
                  "limit_price": None, "client_order_id": "aureon-order-00000004"},
    })
    _, reviews = run_stage("review", source, live=True)
    _, dispatches = run_stage("dispatch", reviews[0], live=True)
    response, values = run_stage(
        "executor", dispatches[0], live=True, budget=True, adapter=True,
        executor_factory=lambda budget, max_order: MissingPreflight(budget, max_order),
    )
    assert response.status_code == 503 and values == []


def test_rule_rejection_crosses_signed_receipt_with_only_sanitized_readiness_metadata():
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
                  "limit_price": None, "client_order_id": "aureon-order-00000005"},
    })
    _, reviews = run_stage("review", source, live=True)
    _, dispatches = run_stage("dispatch", reviews[0], live=True)
    executor_response, executors = run_stage(
        "executor", dispatches[0], live=True, budget=True, adapter=True,
        executor_factory=FakeRuleRejectedExecutor,
    )
    assert executor_response.status_code == 204
    outcome = executors[0]["result"]["outcome"]
    assert outcome["orders_attempted"] == outcome["orders_submitted"] == 0
    assert set(outcome["instrument_readiness_blocker"]) == {
        "schema", "venue", "reason_code", "minimum_quantity", "quantity_step",
        "minimum_notional_usd", "price_step", "quantity_unit",
    }
    receipt_response, receipts = run_stage("receipt", executors[0], live=True)
    assert receipt_response.status_code == 204
    assert receipts[0]["executor"]["result"]["outcome"]["instrument_readiness_blocker"] == (
        outcome["instrument_readiness_blocker"]
    )


def test_executor_rejects_readiness_blocker_with_extra_provider_or_credential_data():
    class LeakyRuleRejectedExecutor(FakeRuleRejectedExecutor):
        def execute(self, intent, *, dispatch_sha256):
            result = super().execute(intent, dispatch_sha256=dispatch_sha256)
            result["instrument_readiness_blocker"]["provider_body"] = "credential-bearing-body"
            return result

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
                  "limit_price": None, "client_order_id": "aureon-order-00000006"},
    })
    _, reviews = run_stage("review", source, live=True)
    _, dispatches = run_stage("dispatch", reviews[0], live=True)
    response, values = run_stage(
        "executor", dispatches[0], live=True, budget=True, adapter=True,
        executor_factory=LeakyRuleRejectedExecutor,
    )
    assert response.status_code == 503 and values == []
