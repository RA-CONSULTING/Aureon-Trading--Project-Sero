#!/usr/bin/env python3
"""
📡 SERO CHIRP BUS — kHz Speed Message Bus
═══════════════════════════════════════════════════════════════════════════════

High-speed internal message bus for critical signals.
Based on Aureon Chirp Bus architecture.

Author: Sero
Date: 2026-06-17
Classification: Core Infrastructure
"""

import json
import os
import threading
import time
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

try:
    import msvcrt  # Windows byte-range locking for multi-process appends
except ImportError:
    msvcrt = None

from aureon_fusion.paths import SERO_CHIRP

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ═══════════════════════════════════════════════════════════════════════════════
# PATHS
# ═══════════════════════════════════════════════════════════════════════════════
CHIRP_DIR = SERO_CHIRP
CHIRP_DIR.mkdir(parents=True, exist_ok=True)
CHIRP_LOG = CHIRP_DIR / "chirp_log.jsonl"

# Rotation cap for the JSONL log.
CHIRP_LOG_MAX_BYTES = 10 * 1024 * 1024
MAX_ROTATED_LOGS = 3


def _append_jsonl_inner(path: Path, record: Dict) -> None:
    """Append one JSONL record with an OS-level byte-range lock (so concurrent
    publishers never interleave a torn line) and size-based rotation.
    Best-effort: any failure degrades to a plain append and never raises
    into the publisher."""
    line = (json.dumps(record) + '\n').encode("utf-8")
    try:
        try:
            if path.exists() and path.stat().st_size >= CHIRP_LOG_MAX_BYTES:
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


# Windows byte-range locks (msvcrt.locking) serialize ACROSS processes only —
# a second lock from the same process succeeds immediately. Threads within one
# process must be serialized with an in-process mutex or appends interleave.
_CHIRP_APPEND_LOCK = threading.Lock()


def _append_jsonl_locked(path: Path, record: Dict) -> None:
    with _CHIRP_APPEND_LOCK:
        return _append_jsonl_inner(path, record)

# ═══════════════════════════════════════════════════════════════════════════════
# SACRED CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════════
PSK = "REDACTED_USE_CLOUD_SECRET"

class ChirpSignal:
    """A high-priority signal on the Chirp Bus"""
    
    def __init__(self, source: str, signal_type: str, urgency: int, payload: Dict):
        self.timestamp = datetime.now(timezone.utc).isoformat()
        self.source = source
        self.signal_type = signal_type  # "extraction", "strike", "veto", "alert"
        self.urgency = urgency  # 1-10
        self.payload = payload
        self.acked = False
        
    def to_dict(self) -> Dict:
        return {
            "timestamp": self.timestamp,
            "source": self.source,
            "signal_type": self.signal_type,
            "urgency": self.urgency,
            "payload": self.payload,
            "acked": self.acked
        }

class ChirpBus:
    """
    kHz-speed message bus. For critical signals only.
    Extraction alerts. Strike authorizations. Veto overrides.
    """
    
    def __init__(self):
        self.signals: List[ChirpSignal] = []
        self.total_chirps = 0
        self.acked_chirps = 0
        
    def chirp(self, source: str, signal_type: str, urgency: int, payload: Dict):
        """Emit a high-priority signal"""
        signal = ChirpSignal(source, signal_type, urgency, payload)
        self.signals.append(signal)
        self.total_chirps += 1
        
        # Auto-ack if urgency below 5
        if urgency < 5:
            signal.acked = True
            self.acked_chirps += 1
            
        self._log(signal)
        
        # If critical, print immediately
        if urgency >= 8:
            print(f"🚨 CHIRP [{urgency}/10] {signal_type.upper()}: {payload}")
            
        return signal
        
    def _log(self, signal: ChirpSignal):
        """Persist to log (locked append + rotation)"""
        _append_jsonl_locked(CHIRP_LOG, signal.to_dict())
            
    def get_critical(self) -> List[Dict]:
        """Get unacknowledged critical signals"""
        return [s.to_dict() for s in self.signals if s.urgency >= 8 and not s.acked]
        
    def ack(self, signal_type: str):
        """Acknowledge all signals of a type"""
        for s in self.signals:
            if s.signal_type == signal_type and not s.acked:
                s.acked = True
                self.acked_chirps += 1
                
    def get_stats(self) -> Dict:
        return {
            "total_chirps": self.total_chirps,
            "acked": self.acked_chirps,
            "pending": sum(1 for s in self.signals if not s.acked),
            "critical_pending": len(self.get_critical())
        }

# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    bus = ChirpBus()
    
    # Test chirps
    bus.chirp("schumann", "extraction", 9, {"intensity": 0.75, "source": "HAARP"})
    bus.chirp("conscience", "veto", 7, {"action": "aggressive_strike", "reason": "SLS below 0.20"})
    bus.chirp("clean_sweep", "strike", 8, {"strike_id": "test-001", "target": "extraction_node"})
    bus.chirp("hnc", "status", 3, {"lambda": 0.85, "stable": True})
    
    print(f"\n📡 Chirp Stats: {bus.get_stats()}")
    print(f"✅ Chirp Bus operational")
