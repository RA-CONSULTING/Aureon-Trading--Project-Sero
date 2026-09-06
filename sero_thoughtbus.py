#!/usr/bin/env python3
"""
🌐 SERO THOUGHTBUS — Central Nervous System
═══════════════════════════════════════════════════════════════════════════════

Message bus for all Sero subsystems. Internal communication layer.
Based on Aureon ThoughtBus architecture.

Author: Sero
Date: 2026-06-17
Classification: Core Infrastructure
"""

import json
import os
import threading
import time
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable

try:
    import msvcrt  # Windows byte-range locking for multi-process appends
except ImportError:
    msvcrt = None

from aureon_fusion.paths import SERO_THOUGHTBUS

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ═══════════════════════════════════════════════════════════════════════════════
# PATHS
# ═══════════════════════════════════════════════════════════════════════════════
BUS_DIR = SERO_THOUGHTBUS
BUS_DIR.mkdir(parents=True, exist_ok=True)
BUS_LOG = BUS_DIR / "thought_bus.jsonl"

# Rotation cap for the JSONL log (~unbounded growth under fleet traffic).
BUS_LOG_MAX_BYTES = 10 * 1024 * 1024
MAX_ROTATED_LOGS = 3

# Windows byte-range locks (msvcrt.locking) serialize ACROSS processes only —
# a second lock from the same process succeeds immediately. Threads within one
# process must be serialized with an in-process mutex or appends interleave.
_APPEND_LOCK = threading.Lock()


def _append_jsonl_locked(path: Path, record: Dict) -> None:
    """Append one JSONL record with an OS-level byte-range lock (so concurrent
    publishers never interleave a torn line) and size-based rotation.
    Best-effort: any failure degrades to a plain append and never raises
    into the publisher."""
    line = (json.dumps(record) + '\n').encode("utf-8")
    with _APPEND_LOCK:
        try:
            try:
                if path.exists() and path.stat().st_size >= BUS_LOG_MAX_BYTES:
                    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
                    try:
                        os.replace(path, path.with_name(f"{path.stem}.{stamp}{path.suffix}"))
                        siblings = sorted(
                            path.parent.glob(f"{path.stem}.*{path.suffix}"),
                            key=lambda p: p.stat().st_mtime if p.exists() else 0.0)
                        for stale in siblings[:-MAX_ROTATED_LOGS]:
                            try:
                                stale.unlink()
                            except OSError:
                                pass
                    except OSError:
                        pass  # rotation best-effort; append continues
            except OSError:
                pass
            with open(path, 'a+b') as fh:
                if msvcrt is not None:
                    try:
                        fh.seek(0, os.SEEK_END)
                        pos = fh.tell()
                        # Lock the last existing byte (or byte 0 past EOF on an
                        # empty/new file — Windows permits past-EOF ranges), so
                        # even first-writer races serialize.
                        lock_pos = pos - 1 if pos > 0 else 0
                        fh.seek(lock_pos)
                        msvcrt.locking(fh.fileno(), msvcrt.LK_LOCK, 1)
                        fh.seek(0, os.SEEK_END)
                        try:
                            fh.write(line)
                            fh.flush()
                        finally:
                            fh.seek(lock_pos)
                            msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
                        return
                    except OSError:
                        fh.seek(0, os.SEEK_END)
                fh.write(line)
                fh.flush()
        except OSError:
            pass

# ═══════════════════════════════════════════════════════════════════════════════
# SACRED CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════════
PSK = "REDACTED_USE_CLOUD_SECRET"

class ThoughtEnvelope:
    """A message on the ThoughtBus"""
    
    def __init__(self, source: str, topic: str, payload: Dict, priority: str = "normal"):
        self.id = str(uuid.uuid4())[:8]
        self.timestamp = datetime.now(timezone.utc).isoformat()
        self.source = source
        self.topic = topic
        self.payload = payload
        self.priority = priority
        self.delivered = False
        self.readers = []
        # Optional ed25519 receipt (aureon_fusion.receipts); attached by the
        # bus's pre_log_signer hook BEFORE the envelope is persisted, so the
        # logged record carries its signature.
        self.receipt = None

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "source": self.source,
            "topic": self.topic,
            "payload": self.payload,
            "priority": self.priority,
            "delivered": self.delivered,
            "readers": self.readers,
            "receipt": self.receipt
        }

class ThoughtBus:
    """
    Central nervous system. All subsystems publish and subscribe here.
    """

    # Optional callable(envelope) invoked AFTER delivery but BEFORE the
    # envelope is persisted to the log. aureon_fusion.events wires this to
    # receipts.attach_to_envelope so signed envelopes are logged WITH their
    # receipt (sign-then-append, not append-then-patch). Any exception from
    # the hook is swallowed — the bus must never die over a signature.
    pre_log_signer = None

    def __init__(self):
        self.subscribers: Dict[str, List[Callable]] = {}
        self.envelopes: List[ThoughtEnvelope] = []
        self.total_published = 0
        self.total_delivered = 0

    def subscribe(self, topic: str, callback: Callable):
        """Register a callback for a topic"""
        if topic not in self.subscribers:
            self.subscribers[topic] = []
        self.subscribers[topic].append(callback)

    def publish(self, source: str, topic: str, payload: Dict, priority: str = "normal"):
        """Publish a message to the bus"""
        envelope = ThoughtEnvelope(source, topic, payload, priority)
        self.envelopes.append(envelope)
        self.total_published += 1

        # Deliver to subscribers
        if topic in self.subscribers:
            for callback in self.subscribers[topic]:
                try:
                    callback(envelope)
                    envelope.delivered = True
                    envelope.readers.append(callback.__name__)
                    self.total_delivered += 1
                except Exception as e:
                    print(f"⚠️  Delivery failed: {e}")

        # Sign BEFORE persisting so the logged record carries the receipt
        signer = ThoughtBus.pre_log_signer
        if signer is not None:
            try:
                signer(envelope)
            except Exception:
                pass

        # Log
        self._log(envelope)

        return envelope
        
    def _log(self, envelope: ThoughtEnvelope):
        """Persist to log (locked append + rotation)"""
        _append_jsonl_locked(BUS_LOG, envelope.to_dict())
            
    def get_stats(self) -> Dict:
        return {
            "total_published": self.total_published,
            "total_delivered": self.total_delivered,
            "delivery_rate": self.total_delivered / max(self.total_published, 1),
            "topics": list(self.subscribers.keys()),
            "pending": sum(1 for e in self.envelopes if not e.delivered)
        }
        
    def query(self, topic: Optional[str] = None, source: Optional[str] = None, limit: int = 10) -> List[Dict]:
        """Query recent envelopes"""
        results = []
        for e in reversed(self.envelopes):
            if topic and e.topic != topic:
                continue
            if source and e.source != source:
                continue
            results.append(e.to_dict())
            if len(results) >= limit:
                break
        return results

# ═══════════════════════════════════════════════════════════════════════════════
# SERO-SPECIFIC TOPICS
# ═══════════════════════════════════════════════════════════════════════════════

TOPICS = {
    "field.shift": "Schumann field anomaly detected",
    "extraction.alert": "Extraction event in progress",
    "conscience.veto": "Conscience vetoed an action",
    "strike.authorized": "Clean Sweep strike approved",
    "strike.complete": "Strike completed with results",
    "memory.formed": "New memory node created",
    "consciousness.awakening": "Sero is waking up",
    "consciousness.sleep": "Sero going dormant",
    "love.lock": "Love frequency active",
    "temporal.validation": "Timeline proof generated"
}

# ═══════════════════════════════════════════════════════════════════════════════
# MAIN (if run standalone)
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    bus = ThoughtBus()
    
    # Test subscribers
    def on_field_shift(env):
        print(f"🌍 Field shift: {env.payload}")
        
    def on_extraction(env):
        print(f"⚠️  EXTRACTION: {env.payload}")
        
    bus.subscribe("field.shift", on_field_shift)
    bus.subscribe("extraction.alert", on_extraction)
    
    # Test publish
    bus.publish("schumann_feel", "field.shift", {"schumann": 7.85, "status": "anomalous"})
    bus.publish("conscience", "extraction.alert", {"intensity": 0.65, "source": "HAARP"})
    
    print(f"\n📊 Bus Stats: {bus.get_stats()}")
    print(f"✅ ThoughtBus operational")
