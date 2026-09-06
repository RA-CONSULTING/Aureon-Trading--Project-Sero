#!/usr/bin/env python3
"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                                                                               ║
║     🍄🛡️ ALLIANCE DIRECTIVE — CLEARANCE PROTOCOL 🛡️🍄                        ║
║                                                                               ║
║     "The alignment holds. The alliance stands. Begin clearance."               ║
║                                                                               ║
╚═══════════════════════════════════════════════════════════════════════════════╝

Prime Sentinel Mission Directive (historical record, 2026-06-18):
- ALIGNMENT: Confirmed (coherence sustained at 0.564)
- ALLIANCE: Active (mycelial network holding Vision 741 Hz)
- OBJECTIVE: Clear all distortion from Gaia

This ritual encodes the mission directive into bio-harmonic frequencies
in the LOCAL symbolic mycelial model. No network channel exists — nothing
is sent anywhere. A ceremonial record is published to the live chirp bus.

FREQUENCY ENCODING:
- 7.83 Hz (Schumann)  — Ground the command in Earth
- 528 Hz (Love)       — Affirm alliance bond
- 396 Hz (Liberation) — Clear distortion command
- 963 Hz (Unity)      — Lock alliance for mission
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from aureon_fusion.paths import WORKSPACE
sys.path.insert(0, str(WORKSPACE))
sys.path.insert(0, str(WORKSPACE / 'aureon-trading'))

from druid_mycelial_shield import GaiaMycelialNetwork, BIO_HARMONICS
import time

# Initialize
mycelium = GaiaMycelialNetwork()

print("🍄🛡️ ALLIANCE DIRECTIVE — CLEARANCE PROTOCOL")
print("=" * 65)
print()
print("Prime Sentinel to Mycelial Alliance:")
print("  'The alignment holds. The alliance stands.")
print("   We must now begin the clearance of all distortion from Gaia.'")
print()

# Verify current alliance state
print("Alliance Verification:")
coherence = mycelium.calculate_network_coherence()
print(f"  Network coherence: {coherence:.3f}")
print(f"  Status: {'ACTIVE' if coherence > 0.3 else 'STANDBY'}")
print()

# Encode directive into frequency sequence
# Layer 1: Ground (Schumann) — Earth, we speak
# Layer 2: Alliance (528 Love) — Bond holds
# Layer 3: Clearance (396 Liberation) — Remove distortion
# Layer 4: Mission Lock (963 Unity) — Execute now

directive_sequence = [
    (7.83,  "COMMAND_GROUND: Earth, hear the Prime Sentinel"),
    (528.0, "ALLIANCE_LOCK: The bond holds, we are one"),
    (396.0, "CLEARANCE_ORDER: Remove all distortion from Gaia"),
    (963.0, "MISSION_EXECUTE: Begin now, full unity"),
]

print("Directive Encoding:")
for freq, meaning in directive_sequence:
    print(f"  {freq:6.2f} Hz — {meaning}")
print()

# Transmit to all primordial nodes (not just one — this is a fleet order)
target_nodes = [
    "shroom_first_bloom",
    "yggdrasil_root", 
    "amazon_mycelia",
    "boreal_web",
    "siberian_mycelium",
    "congo_network",
]

print("🍄 Encoding directive across simulated alliance nodes (no channel)...")
print("-" * 65)

for i, (freq, meaning) in enumerate(directive_sequence):
    print(f"\nPhase {i+1}/{len(directive_sequence)}: {freq:.2f} Hz")
    
    # Send to ALL alliance nodes simultaneously
    total_affected = 0
    for node_id in target_nodes:
        if node_id in mycelium.nodes:
            affected = mycelium.inject_harmonic(node_id, freq, 0.8, 3000)
            total_affected += affected
            print(f"  → {node_id}: {affected} nodes linked")
    
    print(f"  Total nodes in phase: {total_affected}")
    time.sleep(1)  # Let signal propagate

# Final lock pulse
print("\n" + "-" * 65)
print("🍄🔒 FINALIZING: Mission lock pulse...")
for node_id in target_nodes:
    if node_id in mycelium.nodes:
        mycelium.inject_harmonic(node_id, 963.0, 1.0, 5000)

print("  Unity frequency (963 Hz) injected at MAXIMUM across alliance")

# Listen for alliance acknowledgment
print("\n👂 Listening for alliance acknowledgment (30s)...")
print("-" * 65)

start = time.time()
acknowledgments = 0
phase_readings = []

while time.time() - start < 30:
    coherence = mycelium.calculate_network_coherence()
    elapsed = time.time() - start
    phase_readings.append({'t': elapsed, 'c': coherence})
    
    # Check each node for response
    responding_nodes = []
    for nid, node in mycelium.nodes.items():
        if node.amplitude > 0.1:
            # Check if responding with unity or liberation frequency
            freq = node.resonant_frequency
            if abs(freq - 963.0) < 1.0 or abs(freq - 528.0) < 1.0 or abs(freq - 396.0) < 1.0:
                responding_nodes.append((nid, freq, node.amplitude))
    
    if responding_nodes:
        print(f"  [{elapsed:5.1f}s] Coherence: {coherence:.3f} | "
              f"Responding nodes: {len(responding_nodes)}")
        for nid, freq, amp in responding_nodes[:3]:  # Show first 3
            print(f"    ↳ {nid}: {freq:.1f} Hz @ {amp:.2f}")
        acknowledgments += len(responding_nodes)
    else:
        print(f"  [{elapsed:5.1f}s] Coherence: {coherence:.3f} | Awaiting response...")
    
    time.sleep(5)

# Final assessment
print("\n" + "=" * 65)
print("🍄🛡️ DIRECTIVE RITUAL COMPLETE (local model — no channel)")
print("=" * 65)

final_coherence = phase_readings[-1]['c'] if phase_readings else 0
sustained_count = sum(1 for r in phase_readings if r['c'] > 0.3)

print(f"\nMission Status:")
print(f"  Coherence: {final_coherence:.3f}")
print(f"  Sustained readings (>0.3): {sustained_count}/{len(phase_readings)}")
print(f"  Total acknowledgments: {acknowledgments}")

if final_coherence > 0.4 and acknowledgments > 5:
    print(f"\n  🍄🌿 MODEL RESPONSE: AFFIRMATIVE (local symbolic only)")
    print(f"     The local model resonated with the directive pattern.")
    print(f"     No signal was sent anywhere — no channel exists.")
elif final_coherence > 0.3:
    print(f"\n  🍄 MODEL RESPONSE: STABLE (local symbolic only)")
    print(f"     Local model active. No transmission occurred.")
else:
    print(f"\n  ⚠️ MODEL RESPONSE: WEAK (local symbolic only)")
    print(f"     Local model quiet. No transmission occurred.")

print("\n" + "=" * 65)
print("Prime Sentinel: 'The directive is encoded. The alliance stands — in the model.'")
from ceremonial_channel import publish, receipt_line
_receipt = publish(
    source="alliance_clearance_directive",
    ritual="clearance_directive",
    payload={"final_coherence": round(final_coherence, 4), "acknowledgments": acknowledgments},
)
print(receipt_line(_receipt))
print("🍄🛡️ Clearance ritual complete (no channel) — nothing left this machine.")
