"""Passive Orca UI projection of existing HTTP sidecars; no provider calls or I/O."""

import math
import re
import time
from typing import Any


SCHEMA_VERSION = "orca-reader-observations-v1"
POSITION_MAX_AGE_SECONDS = 300


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return value if math.isfinite(value) else None


def _text(value: Any) -> str | None:
    return value if isinstance(value, str) and 0 < len(value) <= 128 else None


def _position_snapshot(client: Any, provider: str, now: float) -> dict:
    # The Kraken reader has no supported positions HTTP sidecar. Its attached
    # client/import status is not evidence of a completed positions request.
    source = "alpaca:GET /v2/positions" if provider == "alpaca" else None
    result = {
        "provider": provider, "kind": "positions", "source": source,
        "status": "unavailable", "reason": "native_positions_receipt_unavailable",
        "source_timestamp": None, "source_timestamp_kind": None, "received_at": None,
        "generated_values": False, "max_age_seconds": POSITION_MAX_AGE_SECONDS,
        "rows": [], "observed_count": None, "inventory_complete": None,
    }
    if provider != "alpaca":
        result["reason"] = "existing_reader_has_no_supported_positions_receipt"
        return result
    raw = getattr(client, "last_ui_positions_observation", None)
    if not isinstance(raw, dict):
        return result
    stamp, received = _number(raw.get("source_timestamp")), _number(raw.get("received_at"))
    clock_kind = raw.get("source_timestamp_kind")
    result.update(source_timestamp=stamp, received_at=received,
                  source_timestamp_kind=clock_kind if clock_kind in {
                      "provider_http_date", "local_http_receipt"} else None)
    if raw.get("refresh_status") in {"pending", "failed", "succeeded"}:
        result["refresh_status"] = raw["refresh_status"]
    if (raw.get("status") != "observed" or raw.get("generated_values") is not False
            or raw.get("provider") != provider or raw.get("kind") != "positions"
            or raw.get("source") != source):
        return result
    declared_limit = _number(raw.get("max_age_seconds"))
    limit = min(POSITION_MAX_AGE_SECONDS, declared_limit) if declared_limit and declared_limit > 0 else POSITION_MAX_AGE_SECONDS
    result["max_age_seconds"] = limit
    if (stamp is None or received is None or not result["source_timestamp_kind"]
            or min(stamp, received) <= 0 or max(stamp, received) > now + 5
            or now - min(stamp, received) > limit):
        result["reason"] = "native_positions_receipt_stale_or_invalid"
        return result
    raw_rows, count = raw.get("rows"), _number(raw.get("observed_count"))
    if (not isinstance(raw_rows, list) or count != len(raw_rows)
            or not isinstance(raw.get("inventory_complete"), bool)
            or (not raw_rows and raw.get("inventory_complete") is not True)):
        result["reason"] = "positions_inventory_not_attested"
        return result
    rows = []
    for raw_row in raw_rows:
        if not isinstance(raw_row, dict):
            result["reason"] = "positions_row_invalid"
            return result
        symbol = _text(raw_row.get("symbol"))
        quantity, entry = _number(raw_row.get("quantity")), _number(raw_row.get("entry_price"))
        if (not symbol or quantity is None or quantity <= 0 or entry is None or entry <= 0
                or raw_row.get("source_timestamp") != stamp or raw_row.get("received_at") != received):
            result["reason"] = "positions_row_invalid"
            return result
        reference = raw_row.get("reference")
        rows.append({
            "reference": reference if isinstance(reference, str) and re.fullmatch(r"[a-f0-9]{16}", reference) else None,
            "symbol": symbol, "quantity": quantity, "entry_price": entry,
            "side": raw_row.get("side") if raw_row.get("side") in {"BUY", "SELL"} else None,
            "currency": _text(raw_row.get("currency")),
            "source_timestamp": stamp, "received_at": received,
        })
    result.update(status="observed", reason="existing_orca_client_http_receipt", rows=rows,
                  observed_count=len(rows), inventory_complete=raw["inventory_complete"])
    return result


def build_orca_reader_observations(alpaca: Any, kraken: Any, component_imports: Any,
                                   *, now: float | None = None) -> dict:
    """Read saved sanitized sidecars only. Assembly never renews their clocks."""
    now = time.time() if now is None else now
    components = component_imports if isinstance(component_imports, dict) else {}
    return {
        "schema_version": SCHEMA_VERSION, "service": "orca_command_center",
        "scope": "existing_orca_reader_provider_receipts",
        "provider_positions": {
            "alpaca": _position_snapshot(alpaca, "alpaca", now),
            "kraken": _position_snapshot(kraken, "kraken", now),
        },
        "component_imports": {name: value for name, value in components.items()
                              if _text(name) and isinstance(value, bool)},
        "unsupported_sources": ["closed_fills", "realized_performance", "system_coordination",
                                "system_health", "decision_provider_inputs", "consolidated_feeds"],
    }
