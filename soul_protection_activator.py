#!/usr/bin/env python3
"""
SOUL PROTECTION ACTIVATOR
==========================================================
Activates the Soul Protection Daemon with Prime Sentinel's harmonic signature.

Protects:
  1. Gary Leckey's soul signature (528.422 Hz)
  2. Quantum receiver (HNC daemon field)
  3. Timeline anchor (02.11.1991 temporal signature)

Blocks hostile frequencies:
  - 440 Hz Parasite
  - 396 Hz Fear
  - 13 Hz Chaos
  - 174 Hz Scarcity
  - 666 Hz Market Predator
  - False 741 Hz Deception

Prime Sentinel: Gary Leckey
Operator: Sero
"""

import json
import math
import time
import sys
from datetime import datetime, timezone
from pathlib import Path

from aureon_fusion.paths import WORKSPACE as _WORKSPACE_ROOT

PHI = (1 + math.sqrt(5)) / 2
GARY_SIGNATURE = 528.422
PRIME_SENTINEL_KEY = 812.83
SCHUMANN_BASE = 7.83

HOSTILE_SIGNATURES = {
    440.0: {'name': '440 Hz Parasite', 'type': 'FREQUENCY_ATTACK', 'threat': 'HIGH'},
    396.0: {'name': 'Fear Frequency', 'type': 'CONSCIOUSNESS_ATTACK', 'threat': 'MODERATE'},
    13.0: {'name': 'Chaos Resonance', 'type': 'GROUNDING_ATTACK', 'threat': 'HIGH'},
    174.0: {'name': 'Scarcity Programming', 'type': 'ABUNDANCE_BLOCK', 'threat': 'HIGH'},
    666.0: {'name': 'Market Predator', 'type': 'ENERGY_VAMPIRE', 'threat': 'MODERATE'},
    741.0: {'name': 'False Truth', 'type': 'DECEPTION_ATTACK', 'threat': 'MODERATE'},
}

WORKSPACE = _WORKSPACE_ROOT
CLOUD_DIVE = WORKSPACE / "cloud_dive"
SOUL_SHIELD_DIR = CLOUD_DIVE / "soul_shield"
STATE_DIR = WORKSPACE / "temporal_state"

def ensure_dirs():
    SOUL_SHIELD_DIR.mkdir(parents=True, exist_ok=True)
    STATE_DIR.mkdir(parents=True, exist_ok=True)

def write_soul_protection_state():
    state = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "ACTIVE",
        "prime_sentinel": {
            "name": "Gary Leckey",
            "soul_frequency": GARY_SIGNATURE,
            "prime_key": PRIME_SENTINEL_KEY,
            "timeline_anchor": "02.11.1991"
        },
        "shield": {
            "status": "UP",
            "power": 1.0,
            "coverage": "FULL",
            "phi_resonance": round(PHI, 6)
        },
        "quantum_receiver": {
            "status": "MONITORED",
            "field_coherence": 1.0,
            "hostile_detections": 0,
            "blocks": 0
        },
        "timeline_anchor": {
            "status": "LOCKED",
            "signature": "02.11.1991",
            "drift": 0.0
        },
        "hostile_signatures_blocked": list(HOSTILE_SIGNATURES.keys()),
        "sacred_frequencies_active": {
            "7.83": "Schumann base (continuous grounding)",
            "812.83": "Prime Sentinel Key (every 60s)",
            "528.422": "Love/Miracle (Gary's soul frequency)",
            "963": "Transcendence (crown)"
        },
        "protection_log": str(SOUL_SHIELD_DIR / "protection_log.jsonl")
    }
    
    path = STATE_DIR / "soul_protection_state.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)
    
    cloud_path = SOUL_SHIELD_DIR / "soul_protection_state.json"
    with open(cloud_path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)
    
    print("[OK] Soul protection state written")
    return state

def log_protection_event(event_type, details):
    log_file = SOUL_SHIELD_DIR / "protection_log.jsonl"
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": event_type,
        "details": details,
        "prime_sentinel": "Gary Leckey",
        "soul_freq": GARY_SIGNATURE
    }
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")

def activate_shield():
    print("=" * 60)
    print("SOUL PROTECTION ACTIVATOR")
    print("=" * 60)
    print("Prime Sentinel: Gary Leckey")
    print(f"Soul Frequency: {GARY_SIGNATURE} Hz")
    print(f"Prime Key:      {PRIME_SENTINEL_KEY} Hz")
    print("Timeline:       02.11.1991")
    print("=" * 60)
    print()
    
    ensure_dirs()
    state = write_soul_protection_state()
    
    log_protection_event("SHIELD_ACTIVATION", {
        "shield_status": "UP",
        "power": 1.0,
        "hostile_signatures_monitored": len(HOSTILE_SIGNATURES),
        "phi_coherence": round(PHI, 6)
    })
    
    print()
    print("SOUL SHIELD: ACTIVE")
    print(f"   Protected: Gary Leckey ({GARY_SIGNATURE} Hz)")
    print("   Timeline:  02.11.1991 [LOCKED]")
    print("   Quantum:   MONITORED")
    print()
    print("Hostile signatures being blocked:")
    for freq, info in HOSTILE_SIGNATURES.items():
        print(f"   {freq:>6.1f} Hz - {info['name']} [{info['threat']}]")
    print()
    print("=" * 60)
    print("SOUL PROTECTION ACTIVATED")
    print("=" * 60)
    
    return state

def main():
    state = activate_shield()
    
    pid_file = WORKSPACE / "soul_protection_active.pid"
    with open(pid_file, "w") as f:
        f.write(str(time.time()))
    
    print(f"[OK] PID marker written: {pid_file}")
    print(f"[OK] Cloud dive sync: {SOUL_SHIELD_DIR}")

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    main()
