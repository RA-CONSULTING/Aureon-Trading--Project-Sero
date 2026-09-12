"""Exactly-once live-order coordination for the isolated executor."""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable, Mapping

from contract import digest
from firestore_ledger import FirestoreLedger, LedgerError
from provider_boundary import CredentialBoundary, ProviderBoundary, ProviderError


class ExecutionError(RuntimeError):
    """Stable live-execution failure."""


@dataclass
class LiveExecutor:
    max_daily_budget_usd: float
    credentials: CredentialBoundary | None = None
    providers: ProviderBoundary | None = None
    ledger: FirestoreLedger | None = None
    clock: Callable[[], float] = time.time

    def __post_init__(self) -> None:
        self.credentials = self.credentials or CredentialBoundary()
        self.providers = self.providers or ProviderBoundary(clock=self.clock)
        self.ledger = self.ledger or FirestoreLedger(self.max_daily_budget_usd)

    def provider_probe(self) -> dict[str, Any]:
        try:
            secret = self.credentials.load()
            return self.providers.probe_all(secret)
        except (ProviderError, KeyError, TypeError) as exc:
            raise ExecutionError(str(exc)) from exc

    @staticmethod
    def _outcome(intent: Mapping[str, Any], dispatch_sha256: str, effect: Mapping[str, Any]) -> dict[str, Any]:
        required = (
            effect.get("provider_order_id"), effect.get("provider_client_order_id"),
            effect.get("provider_status"), effect.get("provider_readback_sha256"),
        )
        if any(not isinstance(value, str) or not value for value in required):
            raise ExecutionError("provider_observed_effect_incomplete")
        return {
            "schema": "aureon.cloud-trade-live-result.v1",
            "status": "provider_observed", "dry_run": False,
            "intent_id": intent["intent_id"], "venue": intent["order"]["venue"],
            "provider_order_id": effect["provider_order_id"],
            "provider_client_order_id": effect["provider_client_order_id"],
            "provider_status": effect["provider_status"],
            "provider_readback_sha256": effect["provider_readback_sha256"],
            "provider_mutation_attempted": True, "orders_attempted": 1,
            "orders_submitted": 1, "dispatch_sha256": dispatch_sha256,
        }

    @staticmethod
    def _provider_evidence(value: Mapping[str, Any]) -> dict[str, Any]:
        return {
            key: value[key]
            for key in ("provider_order_id", "provider_client_order_id", "provider_status", "provider_readback_sha256")
        }

    @staticmethod
    def _terminal(intent: Mapping[str, Any], dispatch_sha256: str, *, status: str,
                  reason_code: str, attempted: bool, submitted: int | None,
                  effect: Mapping[str, Any] | None = None) -> dict[str, Any]:
        effect = effect or {}
        return {
            "schema": "aureon.cloud-trade-live-result.v1", "status": status,
            "reason_code": reason_code, "dry_run": False,
            "intent_id": intent["intent_id"], "venue": intent["order"]["venue"],
            "provider_order_id": effect.get("provider_order_id"),
            "provider_client_order_id": effect.get("provider_client_order_id"),
            "provider_status": effect.get("provider_status"),
            "provider_readback_sha256": effect.get("provider_readback_sha256"),
            "provider_mutation_attempted": attempted,
            "orders_attempted": 1 if attempted else 0,
            "orders_submitted": submitted, "dispatch_sha256": dispatch_sha256,
        }

    def execute(self, intent: Mapping[str, Any], *, dispatch_sha256: str) -> dict[str, Any]:
        order = intent.get("order")
        if not isinstance(order, Mapping):
            raise ExecutionError("live_order_missing")
        now_ms = int(self.clock() * 1000)
        try:
            effect = self.ledger.reserve(
                intent_id=intent["intent_id"], order_sha256=digest(order),
                authorization_sha256=digest(intent["authorization"]),
                venue=order["venue"], quote_value_usd=float(order["quote_value_usd"]), now_ms=now_ms,
            )
        except LedgerError as exc:
            if str(exc) == "daily_budget_exceeded":
                return self._terminal(
                    intent, dispatch_sha256, status="rejected", reason_code="daily_budget_exceeded",
                    attempted=False, submitted=0,
                )
            raise ExecutionError(str(exc)) from exc
        except (KeyError, TypeError, ValueError) as exc:
            raise ExecutionError(str(exc)) from exc
        if effect.get("state") == "observed":
            return self._outcome(intent, dispatch_sha256, effect)

        secret = self.credentials.load()
        provider_client_id = str(
            effect.get("provider_client_order_id") or self.providers._provider_client_id(order)
        )
        if effect.get("created") is not True:
            if order["venue"] != "capital":
                observed = self.providers.lookup(order, secret, provider_client_id)
                if observed is not None:
                    updated = self.ledger.transition(
                        intent["intent_id"], expected_update_time=effect["update_time"],
                        state="observed", now_ms=now_ms, **self._provider_evidence(observed),
                    )
                    return self._outcome(intent, dispatch_sha256, updated)
            if effect.get("state") != "uncertain":
                self.ledger.transition(
                    intent["intent_id"], expected_update_time=effect["update_time"],
                    state="uncertain", now_ms=now_ms,
                    provider_client_order_id=provider_client_id,
                    provider_status="manual_reconciliation_required",
                )
            return self._terminal(
                intent, dispatch_sha256, status="uncertain",
                reason_code="uncertain_order_requires_reconciliation",
                attempted=True, submitted=None, effect=self.ledger.get_effect(intent["intent_id"]) or effect,
            )

        submitting = self.ledger.transition(
            intent["intent_id"], expected_update_time=effect["update_time"],
            state="submitting", now_ms=now_ms,
            provider_client_order_id=provider_client_id,
            provider_status="submission_started",
        )
        try:
            observed = self.providers.submit(order, secret, provider_client_id)
            updated = self.ledger.transition(
                intent["intent_id"], expected_update_time=submitting["update_time"],
                state="observed", now_ms=int(self.clock() * 1000), **self._provider_evidence(observed),
            )
        except (ProviderError, LedgerError, KeyError, TypeError):
            try:
                self.ledger.transition(
                    intent["intent_id"], expected_update_time=submitting["update_time"],
                    state="uncertain", now_ms=int(self.clock() * 1000),
                    provider_client_order_id=provider_client_id,
                    provider_status="manual_reconciliation_required",
                )
            except LedgerError:
                pass
            latest = self.ledger.get_effect(intent["intent_id"]) or submitting
            return self._terminal(
                intent, dispatch_sha256, status="uncertain",
                reason_code="provider_submission_outcome_uncertain",
                attempted=True, submitted=None, effect=latest,
            )
        return self._outcome(intent, dispatch_sha256, updated)


__all__ = ["ExecutionError", "LiveExecutor"]
