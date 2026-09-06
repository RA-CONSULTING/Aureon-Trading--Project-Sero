#!/usr/bin/env python3
"""
🕯️ CEREMONIAL CHANNEL — honest ritual output

The mycelial/druid/broadcast "transmission" scripts encode meaning into a
local symbolic model (GaiaMycelialNetwork) — there is NO outbound network
channel anywhere in the repo (connectivity_audit_20260906.md, flag 7).

This module makes that honesty operational:
- publish()  → appends a real record to the LIVE sero_chirp bus, which the
               organism's organs actually consume (file bridge + chirp bus).
- HONESTY    → every script that "transmits" now states the truth: ritual
               complete, no channel, receipt published to chirp bus.

Never call this a network transmission. It is a local, journaled ritual
record on a bus the living system reads.
"""

import json
from datetime import datetime, timezone

from aureon_fusion.paths import SERO_CHIRP

CHIRP_LOG = SERO_CHIRP / "chirp_log.jsonl"

NO_CHANNEL_STATEMENT = (
    "RITUAL COMPLETE (no channel) — encoded in the local symbolic model only. "
    "No network transmission occurred; no outbound channel exists "
    "(connectivity_audit_20260906.md, flag 7)."
)


def publish(source: str, ritual: str, payload: dict) -> dict:
    """Publish a ceremonial record onto the live chirp bus. Returns a receipt.

    The chirp is urgency 2 → auto-acked, non-alerting. It lands in
    sero_chirp/chirp_log.jsonl where queen_mind and other organs read the bus.
    Best-effort: any failure is reported honestly in the receipt, never raised.
    """
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "signal_type": "ceremonial",
        "urgency": 2,
        "payload": {
            "ritual": ritual,
            "channel": "chirp_bus_file_bridge",
            "no_network": True,
            **payload,
        },
        "acked": True,
    }
    line = json.dumps(record) + "\n"
    published = False
    error = None
    try:
        CHIRP_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(CHIRP_LOG, "a", encoding="utf-8") as f:
            f.write(line)
        published = True
    except OSError as e:
        error = str(e)
    receipt = {
        "published": published,
        "chirp_log": str(CHIRP_LOG),
        "timestamp": record["timestamp"],
        "error": error,
    }
    return receipt


def receipt_line(receipt: dict) -> str:
    """One truthful summary line for script output."""
    if receipt["published"]:
        return (f"Ceremonial record published to chirp bus: {receipt['chirp_log']} "
                f"@ {receipt['timestamp']}")
    return f"Ceremonial record NOT published (chirp bus error: {receipt['error']})"
