"""Passive operator projection of position receipts already in terminal state.

The projector accepts only the sanitized ``provider_observations`` carried by
the unified runtime status document.  It performs no provider I/O and exposes
no execution or mutation surface.  Every output field is rebuilt from a small
allowlist so a future terminal-state field cannot leak through implicitly.
"""

from __future__ import annotations

import math
import re
import time
from collections.abc import Mapping
from typing import Any

SCHEMA_VERSION = "aureon.operator.orca-observations.v2"
SERVICE = "aureon_operator"
SCOPE = "terminal_state_sanitized_provider_position_receipts"
PROVIDERS = ("capital", "alpaca", "kraken", "binance")
POSITION_MAX_AGE_SECONDS = 300.0
MAX_POSITION_ROWS = 1_000

# These are the only position readers currently captured into terminal state.
# Kraken and Binance account receipts must never be promoted into positions.
_SUPPORTED_POSITION_SOURCES = {
    "capital": "capital:GET /positions",
    "alpaca": "alpaca:GET /v2/positions",
}
_CLOCK_KINDS = frozenset({"provider_http_date", "local_http_receipt"})
_REFERENCE = re.compile(r"[a-f0-9]{16}")


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    result = float(value)
    return result if math.isfinite(result) else None


def _text(value: Any, *, limit: int = 128) -> str | None:
    return value if isinstance(value, str) and 0 < len(value) <= limit else None


def _unavailable(provider: str, reason: str, *, source: str | None = None) -> dict[str, Any]:
    return {
        "provider": provider,
        "kind": "positions",
        "source": source,
        "source_timestamp": None,
        "source_timestamp_kind": None,
        "received_at": None,
        "max_age_seconds": POSITION_MAX_AGE_SECONDS,
        "generated_values": False,
        "status": "unavailable",
        "reason": reason,
        "rows": [],
        "observed_count": None,
        "inventory_complete": None,
    }


def _project_row(raw: Any, *, source_timestamp: float, received_at: float) -> dict[str, Any] | None:
    if not isinstance(raw, Mapping):
        return None
    symbol = _text(raw.get("symbol"))
    quantity = _number(raw.get("quantity"))
    entry_price = _number(raw.get("entry_price"))
    if (
        symbol is None
        or quantity is None
        or quantity <= 0
        or entry_price is None
        or entry_price <= 0
        or _number(raw.get("source_timestamp")) != source_timestamp
        or _number(raw.get("received_at")) != received_at
    ):
        return None
    reference = raw.get("reference")
    side = raw.get("side")
    opened_at = _number(raw.get("opened_at"))
    fill_reconciled = raw.get("fill_reconciled")
    return {
        "reference": reference if isinstance(reference, str) and _REFERENCE.fullmatch(reference) else None,
        "symbol": symbol,
        "side": side if side in {"BUY", "SELL"} else None,
        "quantity": quantity,
        "entry_price": entry_price,
        "currency": _text(raw.get("currency"), limit=16),
        "opened_at": opened_at if opened_at is not None and opened_at > 0 else None,
        "source_timestamp": source_timestamp,
        "received_at": received_at,
        "fill_reconciled": fill_reconciled if isinstance(fill_reconciled, bool) else None,
    }


def _project_position_observation(provider: str, raw: Any, *, now: float) -> dict[str, Any]:
    expected_source = _SUPPORTED_POSITION_SOURCES.get(provider)
    if expected_source is None:
        return _unavailable(provider, "operator_position_reader_not_supported")

    def unavailable(reason: str) -> dict[str, Any]:
        return _unavailable(provider, reason, source=expected_source)

    if not isinstance(raw, Mapping):
        return unavailable("terminal_position_receipt_unavailable")
    if (
        raw.get("provider") != provider
        or raw.get("kind") != "positions"
        or raw.get("source") != expected_source
        or raw.get("status") != "observed"
        or raw.get("generated_values") is not False
    ):
        return unavailable("terminal_position_receipt_unavailable")

    source_timestamp = _number(raw.get("source_timestamp"))
    received_at = _number(raw.get("received_at"))
    clock_kind = raw.get("source_timestamp_kind")
    declared_age = _number(raw.get("max_age_seconds"))
    if (
        source_timestamp is None
        or source_timestamp <= 0
        or received_at is None
        or received_at <= 0
        or clock_kind not in _CLOCK_KINDS
        or declared_age is None
        or declared_age <= 0
    ):
        return unavailable("terminal_position_provenance_invalid")
    max_age = min(POSITION_MAX_AGE_SECONDS, declared_age)
    if (
        source_timestamp > now + 5
        or received_at > now + 5
        or now - source_timestamp > max_age
        or now - received_at > max_age
    ):
        return unavailable("terminal_position_receipt_stale")

    raw_rows = raw.get("rows")
    observed_count = _number(raw.get("observed_count"))
    inventory_complete = raw.get("inventory_complete")
    if (
        not isinstance(raw_rows, list)
        or len(raw_rows) > MAX_POSITION_ROWS
        or observed_count is None
        or not observed_count.is_integer()
        or int(observed_count) != len(raw_rows)
        or not isinstance(inventory_complete, bool)
        or (not raw_rows and inventory_complete is not True)
    ):
        return unavailable("terminal_position_inventory_invalid")
    rows = [
        _project_row(row, source_timestamp=source_timestamp, received_at=received_at)
        for row in raw_rows
    ]
    if any(row is None for row in rows):
        return unavailable("terminal_position_row_invalid")
    return {
        "provider": provider,
        "kind": "positions",
        "source": expected_source,
        "source_timestamp": source_timestamp,
        "source_timestamp_kind": clock_kind,
        "received_at": received_at,
        "max_age_seconds": max_age,
        "generated_values": False,
        "status": "observed",
        "reason": "terminal_state_provider_position_receipt",
        "rows": rows,
        "observed_count": len(rows),
        "inventory_complete": inventory_complete,
    }


def build_operator_orca_observations(
    terminal_state: Any,
    *,
    now: float | None = None,
) -> dict[str, Any]:
    """Build the read-only v2 contract without refreshing any receipt clock."""
    moment = time.time() if now is None else now
    state = terminal_state if isinstance(terminal_state, Mapping) else {}
    provider_observations = state.get("provider_observations")
    providers = provider_observations if isinstance(provider_observations, Mapping) else {}
    positions: dict[str, Any] = {}
    for provider in PROVIDERS:
        provider_value = providers.get(provider)
        provider_value = provider_value if isinstance(provider_value, Mapping) else {}
        positions[provider] = _project_position_observation(
            provider,
            provider_value.get("positions"),
            now=moment,
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "service": SERVICE,
        "scope": SCOPE,
        "provider_calls": False,
        "mutation_authority": False,
        "provider_positions": positions,
        "unsupported_sources": [
            "closed_fills",
            "realized_performance",
            "current_market_quotes",
            "execution_readiness",
        ],
    }


__all__ = [
    "PROVIDERS",
    "SCHEMA_VERSION",
    "SCOPE",
    "SERVICE",
    "build_operator_orca_observations",
]
