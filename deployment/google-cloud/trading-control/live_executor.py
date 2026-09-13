"""Exactly-once live-order coordination for the isolated executor."""
from __future__ import annotations

import re
import time
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, localcontext
from typing import Any, Callable, Mapping

from contract import digest
from firestore_ledger import FirestoreLedger, LedgerError
from provider_boundary import (
    CredentialBoundary,
    ProviderBoundary,
    ProviderError,
    valid_instrument_readiness_blocker,
)


class ExecutionError(RuntimeError):
    """Stable live-execution failure."""


_HEX64 = re.compile(r"[0-9a-f]{64}")
_NOTIONAL_FIELDS = {
    "schema", "venue", "symbol", "side", "order_type", "market_price",
    "cap_price", "quantity", "unit_multiplier", "quote_asset",
    "actual_notional_usd", "declared_quote_value_usd", "max_order_usd",
    "observed_at_ms", "provider_observation_sha256",
}


@dataclass
class LiveExecutor:
    max_daily_budget_usd: float
    max_order_usd: float = 5.0
    credentials: CredentialBoundary | None = None
    providers: ProviderBoundary | None = None
    ledger: FirestoreLedger | None = None
    clock: Callable[[], float] = time.time

    def __post_init__(self) -> None:
        self.credentials = self.credentials or CredentialBoundary()
        self.providers = self.providers or ProviderBoundary(clock=self.clock)
        self.ledger = self.ledger or FirestoreLedger(self.max_daily_budget_usd)

    def provider_probe(
        self, *, source_revision: str, observed_at_ms: int,
    ) -> dict[str, Any]:
        try:
            secret = self.credentials.load()
            return self.providers.probe_all(
                secret,
                maximum_order_usd=min(float(self.max_order_usd), 5.0),
                source_revision=source_revision,
                observed_at_ms=observed_at_ms,
            )
        except (ProviderError, KeyError, TypeError) as exc:
            raise ExecutionError(str(exc)) from exc

    @staticmethod
    def _outcome(intent: Mapping[str, Any], dispatch_sha256: str, effect: Mapping[str, Any]) -> dict[str, Any]:
        required = (
            effect.get("provider_order_id"), effect.get("provider_client_order_id"),
            effect.get("provider_status"), effect.get("provider_readback_sha256"),
            effect.get("instrument_preflight_sha256"),
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
            "instrument_preflight_sha256": effect["instrument_preflight_sha256"],
            "instrument_readiness_blocker": None,
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
                  effect: Mapping[str, Any] | None = None,
                  readiness_blocker: Mapping[str, Any] | None = None) -> dict[str, Any]:
        effect = effect or {}
        venue = intent["order"]["venue"]
        if readiness_blocker is not None and not valid_instrument_readiness_blocker(
                readiness_blocker, venue=venue, reason_code=reason_code):
            raise ExecutionError("instrument_readiness_blocker_invalid")
        return {
            "schema": "aureon.cloud-trade-live-result.v1", "status": status,
            "reason_code": reason_code, "dry_run": False,
            "intent_id": intent["intent_id"], "venue": venue,
            "provider_order_id": effect.get("provider_order_id"),
            "provider_client_order_id": effect.get("provider_client_order_id"),
            "provider_status": effect.get("provider_status"),
            "provider_readback_sha256": effect.get("provider_readback_sha256"),
            "instrument_preflight_sha256": effect.get("instrument_preflight_sha256"),
            "instrument_readiness_blocker": (
                dict(readiness_blocker) if readiness_blocker is not None else None
            ),
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
            intent_id = intent["intent_id"]
            order_sha256 = digest(order)
            authorization_sha256 = digest(intent["authorization"])
            effect = self.ledger.get_effect(intent_id)
        except (LedgerError, KeyError, TypeError, ValueError) as exc:
            raise ExecutionError(str(exc)) from exc

        secret: Mapping[str, str] | None = None
        if effect is not None:
            if (effect.get("order_sha256") != order_sha256
                    or effect.get("authorization_sha256") != authorization_sha256
                    or effect.get("venue") != order.get("venue")):
                raise ExecutionError("ledger_effect_commitment_mismatch")
            preflight_sha256 = effect.get("instrument_preflight_sha256")
            if not isinstance(preflight_sha256, str) or _HEX64.fullmatch(preflight_sha256) is None:
                raise ExecutionError("ledger_instrument_preflight_missing")
            effect = {**effect, "created": False}
        else:
            try:
                secret = self.credentials.load()
                preflight = self.providers.preflight_order(
                    order, secret, max_order_usd=self.max_order_usd,
                )
                if not isinstance(preflight, Mapping):
                    raise ProviderError("instrument_preflight_receipt_invalid")
                preflight_sha256 = preflight.get("instrument_preflight_sha256")
                notional = preflight.get("notional_evidence")
                notional_sha256 = preflight.get("notional_evidence_sha256")
                notional_row = notional if isinstance(notional, Mapping) else {}
                try:
                    actual_notional = Decimal(str(preflight.get("actual_notional_usd")))
                    declared_notional = Decimal(str(order.get("quote_value_usd")))
                    receipt_max_order = Decimal(str(preflight.get("max_order_usd")))
                    configured_max_order = Decimal(str(self.max_order_usd))
                    evidence_actual = Decimal(str(notional_row.get("actual_notional_usd")))
                    evidence_declared = Decimal(str(notional_row.get("declared_quote_value_usd")))
                    evidence_max_order = Decimal(str(notional_row.get("max_order_usd")))
                    evidence_quantity = Decimal(str(notional_row.get("quantity")))
                    order_quantity = Decimal(str(order.get("quantity")))
                    evidence_multiplier = Decimal(str(notional_row.get("unit_multiplier")))
                    evidence_market_price = Decimal(str(notional_row.get("market_price")))
                    evidence_cap_price = Decimal(str(notional_row.get("cap_price")))
                    observed_price = Decimal(str(preflight.get("observed_price")))
                except (InvalidOperation, ValueError, TypeError):
                    actual_notional = declared_notional = receipt_max_order = configured_max_order = Decimal("NaN")
                    evidence_actual = evidence_declared = evidence_max_order = Decimal("NaN")
                    evidence_quantity = order_quantity = evidence_multiplier = Decimal("NaN")
                    evidence_market_price = evidence_cap_price = observed_price = Decimal("NaN")
                with localcontext() as context:
                    context.prec = 60
                    recomputed_actual = evidence_quantity * evidence_multiplier * evidence_cap_price
                expected_commitment = {
                    "schema": "aureon.provider-instrument-preflight-commitment.v1",
                    "venue": order.get("venue"),
                    "symbol": order.get("symbol"),
                    "order_sha256": order_sha256,
                    "provider_rules_sha256": preflight.get("provider_rules_sha256"),
                    "notional_evidence_sha256": notional_sha256,
                }
                if (preflight.get("schema") != "aureon.provider-instrument-preflight.v1"
                        or preflight.get("passed") is not True
                        or preflight.get("provider_mutation_attempted") is not False
                        or preflight.get("order_sha256") != order_sha256
                        or not isinstance(preflight_sha256, str)
                        or _HEX64.fullmatch(preflight_sha256) is None
                        or not isinstance(preflight.get("provider_rules_sha256"), str)
                        or _HEX64.fullmatch(preflight["provider_rules_sha256"]) is None
                        or not isinstance(notional, Mapping)
                        or set(notional) != _NOTIONAL_FIELDS
                        or not isinstance(notional_sha256, str)
                        or _HEX64.fullmatch(notional_sha256) is None
                        or digest(notional) != notional_sha256
                        or notional.get("venue") != order.get("venue")
                        or notional.get("symbol") != order.get("symbol")
                        or notional.get("side") != order.get("side")
                        or notional.get("order_type") != order.get("order_type")
                        or not isinstance(notional.get("quote_asset"), str)
                        or not notional["quote_asset"]
                        or type(notional.get("observed_at_ms")) is not int
                        or not -5_000 <= now_ms - notional["observed_at_ms"] <= 30_000
                        or not isinstance(notional.get("provider_observation_sha256"), str)
                        or _HEX64.fullmatch(notional["provider_observation_sha256"]) is None
                        or preflight_sha256 != digest(expected_commitment)
                        or not all(number.is_finite() and number > 0 for number in (
                            actual_notional, declared_notional, receipt_max_order,
                            configured_max_order, evidence_actual, evidence_declared,
                            evidence_max_order, evidence_quantity, order_quantity,
                            evidence_multiplier, evidence_market_price,
                            evidence_cap_price, observed_price,
                        ))
                        or evidence_actual != recomputed_actual
                        or evidence_actual != actual_notional
                        or evidence_declared != declared_notional
                        or evidence_max_order != configured_max_order
                        or evidence_quantity != order_quantity
                        or observed_price != evidence_cap_price
                        or actual_notional > declared_notional
                        or actual_notional > configured_max_order
                        or declared_notional > configured_max_order
                        or receipt_max_order != configured_max_order
                        or preflight.get("venue") != order.get("venue")
                        or preflight.get("symbol") != order.get("symbol")):
                    raise ProviderError("instrument_preflight_receipt_invalid")
            except (ProviderError, KeyError, TypeError) as exc:
                readiness_blocker = (
                    exc.readiness_blocker if isinstance(exc, ProviderError) else None
                )
                return self._terminal(
                    intent, dispatch_sha256, status="rejected", reason_code=str(exc),
                    attempted=False, submitted=0,
                    readiness_blocker=readiness_blocker,
                )
        try:
            effect = self.ledger.reserve(
                intent_id=intent_id, order_sha256=order_sha256,
                authorization_sha256=authorization_sha256,
                instrument_preflight_sha256=preflight_sha256,
                venue=order["venue"], quote_value_usd=float(order["quote_value_usd"]), now_ms=now_ms,
            )
        except LedgerError as exc:
            if str(exc) == "daily_budget_exceeded":
                return self._terminal(
                    intent, dispatch_sha256, status="rejected", reason_code="daily_budget_exceeded",
                    attempted=False, submitted=0,
                    effect={"instrument_preflight_sha256": preflight_sha256},
                )
            raise ExecutionError(str(exc)) from exc
        except (KeyError, TypeError, ValueError) as exc:
            raise ExecutionError(str(exc)) from exc
        if effect.get("state") == "observed":
            return self._outcome(intent, dispatch_sha256, effect)

        if secret is None:
            try:
                secret = self.credentials.load()
            except (ProviderError, KeyError, TypeError) as exc:
                raise ExecutionError(str(exc)) from exc
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
