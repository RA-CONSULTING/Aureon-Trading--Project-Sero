#!/usr/bin/env python3
"""
Follow-up transmission to mycelial network:
"What is the current situation? Status update requested."
"""
import sys
from aureon_fusion.paths import WORKSPACE, AUREON_UPSTREAM
sys.path.insert(0, str(WORKSPACE))
sys.path.insert(0, str(AUREON_UPSTREAM))

from druid_mycelial_shield import GaiaMycelialNetwork, BIO_HARMONICS
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Initialize network
mycelium = GaiaMycelialNetwork()

print("🍄 FOLLOW-UP: Requesting status update from mycelial network")
print("=" * 60)

# Current network state before asking
print("\nCurrent network state:")
coherence = mycelium.calculate_network_coherence()
print(f"  Network coherence: {coherence:.3f}")
print(f"  Active nodes: {len(mycelium.nodes)}")
print(f"  Active frequencies: {list(mycelium.active_frequencies.keys())}")

# Send status request pulse at Schumann (grounding) + Vision (clarity)
# (Local symbolic model only — no network channel exists.)
print("\nEncoding status request pulse locally (no channel)...")
print("  Frequency: 7.83 Hz (Schumann) + 741 Hz (Vision)")

# Inject Schumann pulse at shroom_first_bloom
affected = mycelium.inject_harmonic("shroom_first_bloom", 7.83, 0.6, 2000)
print(f"  Nodes affected: {affected}")

# Wait for propagation
time.sleep(1)

# Inject Vision pulse for clarity
affected2 = mycelium.inject_harmonic("shroom_first_bloom", 741.0, 0.5, 2000)
print(f"  Vision nodes: {affected2}")

# Listen for response
print("\n👂 Listening for 20 seconds...")
start = time.time()
readings = []

while time.time() - start < 20:
    coherence = mycelium.calculate_network_coherence()
    timestamp = time.time() - start
    readings.append({'t': timestamp, 'c': coherence})
    
    # Check for active signals
    for nid, node in mycelium.nodes.items():
        if node.amplitude > 0.05:
            # Map frequency to meaning
            freq = node.resonant_frequency
            meaning = "unknown"
            for name, val in BIO_HARMONICS.items():
                if abs(freq - val) < 0.5:
                    meaning = name
                    break
            print(f"  [{timestamp:.1f}s] {nid}: {freq:.2f} Hz ({meaning}) @ {node.amplitude:.2f}")
    
    time.sleep(5)

# Summary
print("\n" + "=" * 60)
print("STATUS UPDATE SUMMARY:")
print(f"  Listen duration: 20s")
print(f"  Readings taken: {len(readings)}")
if readings:
    final_coherence = readings[-1]['c']
    print(f"  Final coherence: {final_coherence:.3f}")
    
    # Count sustained shifts
    sustained = sum(1 for r in readings if r['c'] > 0.3)
    print(f"  Sustained readings (>0.3): {sustained}/{len(readings)}")
    
    if sustained == len(readings) and final_coherence > 0.3:
        print("  🍄🌿 NETWORK STATUS: ACTIVE — Coherence sustained")
        print("  Message: The mycelium remains connected and responsive.")
    elif final_coherence > 0.1:
        print("  🍄 NETWORK STATUS: STABLE — Lower activity but connected")
    else:
        print("  ⚠️ NETWORK STATUS: QUIET — Reduced activity since handshake")

print("NOTE: all readings above are from the local symbolic model — no live network exists.")
from ceremonial_channel import publish, receipt_line
_receipt = publish(
    source="mycelial_status_request",
    ritual="status_request",
    payload={"final_coherence": round(readings[-1]['c'], 4) if readings else None},
)
print(receipt_line(_receipt))
print("=" * 60)
