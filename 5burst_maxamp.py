#!/usr/bin/env python3
"""
🔥 5-BURST MAX AMPLIFICATION BROADCAST — TEMPORAL DELAY MEASUREMENT
═══════════════════════════════════════════════════════════════════════════════

Protocol: 5 sequential focused bursts at maximum amplitude.
Purpose: Measure temporal delay with precision.

Each burst: 3 layers, 60 seconds, max amplitude
Spacing: 120 seconds between bursts (for isolation on spectrogram)
Total: 5 bursts × 60s + 4 gaps × 120s = 780 seconds = 13 minutes

Author: Sero
Date: 2026-06-17
Classification: REDACTED_USE_CLOUD_SECRET
"""

import json
import sys
import time
import math
import random
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from aureon_fusion.paths import WORKSPACE

# ═══════════════════════════════════════════════════════════════════════════════
# SACRED CONSTANTS — MAXIMUM AMPLIFICATION
# ═══════════════════════════════════════════════════════════════════════════════
PHI = 1.618033988749895
SCHUMANN = 7.83
PSK = "REDACTED_USE_CLOUD_SECRET"
PRIME_KEY = 812.83
SOLFEGGIO = [396, 417, 528, 639, 741, 852, 963]

# MAX AMPLIFICATION PARAMETERS
MAX_AMPLITUDE = 1.0          # Maximum signal amplitude (0.5 = normal, 1.0 = max)
LAYER_DURATION = 60          # seconds per burst layer
BURST_LAYERS = 3             # layers per burst
GAP_DURATION = 120           # seconds between bursts
TOTAL_BURSTS = 5

BURST_LAYERS_DEF = [
    {"name": "STRIKE",    "primary": 8.033,   "phase": 180, "solfeggio": 396, "theta_couple": 0.0},
    {"name": "PENETRATE", "primary": 8.4358,  "phase": 93,  "solfeggio": 528, "theta_couple": 4.83},
    {"name": "SEAL",      "primary": 10.7135, "phase": 333, "solfeggio": 741, "theta_couple": 8.68},
]

# ═══════════════════════════════════════════════════════════════════════════════
# BURST ENCODER
# ═══════════════════════════════════════════════════════════════════════════════

class MaxAmplificationBurst:
    """Single burst at maximum amplitude for temporal delay measurement."""
    
    def __init__(self, burst_id: int, amplitude: float = MAX_AMPLITUDE):
        self.burst_id = burst_id
        self.amplitude = amplitude
        self.start_time = None
        self.end_time = None
        self.samples = []
    
    def generate(self, duration: int = LAYER_DURATION):
        """Generate max-amplitude waveform for all 3 layers."""
        self.start_time = datetime.now(timezone.utc)
        start_ts = time.time()
        elapsed = 0.0
        
        while elapsed < duration:
            t = elapsed
            sample = {"t": elapsed, "composite": 0.0, "layers": []}
            
            for layer_def in BURST_LAYERS_DEF:
                layer_idx = BURST_LAYERS_DEF.index(layer_def)
                
                # Calculate phi-harmonic frequency
                freq = layer_def["primary"] + (layer_idx * PHI / 10.0)
                phase_rad = math.radians(layer_def["phase"])
                
                # Schumann carrier (MAX AMPLITUDE)
                carrier = self.amplitude * math.sin(2 * math.pi * SCHUMANN * t + phase_rad)
                
                # Prime Key modulator (MAX AMPLITUDE)
                modulator = self.amplitude * math.sin(2 * math.pi * PRIME_KEY * t / 1000.0)
                
                # Solfeggio harmonic (MAX AMPLITUDE)
                solf = layer_def["solfeggio"] / 100.0
                harmonic = self.amplitude * math.sin(2 * math.pi * solf * t)
                
                # Phi coherence envelope (MAX AMPLITUDE)
                envelope = self.amplitude * (1.0 + math.sin(2 * math.pi * PHI * t / 10.0)) / 2.0
                
                # Theta coupling (REM sleep entrainment)
                theta = 0.0
                if layer_def["theta_couple"] > 0:
                    theta = self.amplitude * 0.5 * math.sin(2 * math.pi * layer_def["theta_couple"] * t)
                
                # Composite (SUMMED, not averaged — MAX POWER)
                layer_val = (carrier + modulator + harmonic) * envelope + theta
                sample["layers"].append({
                    "name": layer_def["name"],
                    "value": round(layer_val, 4)
                })
                sample["composite"] += layer_val
            
            # Normalize composite to prevent runaway but keep max amplitude
            sample["composite"] = max(-self.amplitude * 3, min(self.amplitude * 3, sample["composite"]))
            sample["composite"] = round(sample["composite"], 4)
            
            self.samples.append(sample)
            
            # Display with burst ID
            bar_len = int(abs(sample["composite"]) * 40 / (self.amplitude * 3))
            bar = "█" * bar_len + "░" * (40 - bar_len)
            pct = (elapsed / duration) * 100
            
            print(f"\r   [BURST {self.burst_id}] [{bar}] {pct:5.1f}% | t={elapsed:.1f}s | amp={sample['composite']:+.4f}", end="")
            
            # Realtime simulation: 0.05s per sample (20Hz effective)
            time.sleep(0.05)
            elapsed = time.time() - start_ts
        
        self.end_time = datetime.now(timezone.utc)
        print()
        
        return self.get_stats()
    
    def get_stats(self):
        if not self.samples:
            return {}
        vals = [s["composite"] for s in self.samples]
        return {
            "burst_id": self.burst_id,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "amplitude": self.amplitude,
            "duration": LAYER_DURATION,
            "samples": len(self.samples),
            "peak": round(max(abs(v) for v in vals), 4),
            "average": round(sum(vals) / len(vals), 6),
            "energy": round(sum(v**2 for v in vals) / len(vals), 6)  # RMS energy
        }

# ═══════════════════════════════════════════════════════════════════════════════
# 5-BURST SEQUENCE
# ═══════════════════════════════════════════════════════════════════════════════

class FiveBurstSequence:
    """Five max-amplitude bursts with precise timing for delay measurement."""
    
    def __init__(self):
        self.bursts = []
        self.log = []
        self.start_time = None
    
    def run(self):
        """Execute the 5-burst sequence."""
        self.start_time = datetime.now(timezone.utc)
        
        print("=" * 80)
        print("🔥 5-BURST MAX AMPLIFICATION BROADCAST")
        print("=" * 80)
        print(f"Timestamp: {self.start_time.isoformat()}")
        print(f"PSK: {PSK}")
        print(f"Amplitude: {MAX_AMPLITUDE} (MAXIMUM)")
        print(f"Burst duration: {LAYER_DURATION}s")
        print(f"Gap duration: {GAP_DURATION}s")
        print(f"Total sequence time: ~{(TOTAL_BURSTS * LAYER_DURATION + (TOTAL_BURSTS - 1) * GAP_DURATION) / 60:.1f} minutes")
        print()
        print("Each burst: STRIKE → PENETRATE → SEAL")
        print("Solfeggio: 396 Hz → 528 Hz → 741 Hz")
        print("Theta: 0.0 Hz → 4.83 Hz → 8.68 Hz")
        print("Phase: 180° → 93° → 333°")
        print()
        print("🎯 MARK THESE TIMES:")
        print("   After each burst, check VLF.it spectrogram for spike")
        print("   Note the delay between BURST END and SPIKE APPEARANCE")
        print()
        print("=" * 80)
        print()
        
        for burst_num in range(1, TOTAL_BURSTS + 1):
            # Log burst start
            burst_start = datetime.now(timezone.utc)
            self.log.append({
                "event": "BURST_START",
                "burst_id": burst_num,
                "timestamp": burst_start.isoformat(),
                "unix_time": time.time()
            })
            
            print(f"🚀 BURST {burst_num} / {TOTAL_BURSTS} — STARTING")
            print(f"   Time: {burst_start.strftime('%H:%M:%S.%f')[:-3]} UTC")
            
            # Generate the burst
            burst = MaxAmplificationBurst(burst_id=burst_num, amplitude=MAX_AMPLITUDE)
            stats = burst.generate()
            self.bursts.append(burst)
            
            # Log burst end
            burst_end = datetime.now(timezone.utc)
            self.log.append({
                "event": "BURST_END",
                "burst_id": burst_num,
                "timestamp": burst_end.isoformat(),
                "unix_time": time.time(),
                "stats": stats
            })
            
            print(f"   ✅ BURST {burst_num} COMPLETE")
            print(f"   Peak amplitude: {stats['peak']:.4f}")
            print(f"   Energy (RMS): {stats['energy']:.6f}")
            print()
            
            # Gap between bursts (except after last)
            if burst_num < TOTAL_BURSTS:
                print(f"   ⏳ GAP: {GAP_DURATION}s cooling period...")
                for remaining in range(GAP_DURATION, 0, -1):
                    print(f"\r   Next burst in {remaining}s...", end="")
                    time.sleep(1)
                print()
                print()
        
        self.end_time = datetime.now(timezone.utc)
        
        # Summary
        print("=" * 80)
        print("🔥 5-BURST SEQUENCE COMPLETE")
        print("=" * 80)
        print(f"Start: {self.start_time.isoformat()}")
        print(f"End:   {self.end_time.isoformat()}")
        print(f"Duration: {(self.end_time - self.start_time).total_seconds():.1f} seconds")
        print()
        
        for burst in self.bursts:
            stats = burst.get_stats()
            print(f"Burst {stats['burst_id']}: {stats['start_time'][11:19]} → {stats['end_time'][11:19]} | "
                  f"Peak: {stats['peak']:.4f} | Energy: {stats['energy']:.6f}")
        
        print()
        print("🎯 NEXT STEPS:")
        print("   1. Screenshot VLF.it spectrogram (Cascina) at 15-min intervals")
        print("   2. Note exact spike time for each burst")
        print("   3. Compare: burst_end_timestamp + delay = spike_time")
        print("   4. Average the 5 delays = temporal delay τ")
        print()
        print("🖤 The field is burning. Wait for the echo. 🖤")
        print("=" * 80)
        
        self.save_log()
    
    def save_log(self):
        """Save complete broadcast log for temporal analysis."""
        output_dir = WORKSPACE / "broadcast_logs"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        log_file = output_dir / f"5burst_maxamp_{timestamp}.json"
        
        # Build summary data
        burst_data = []
        for burst in self.bursts:
            stats = burst.get_stats()
            burst_data.append(stats)
        
        log_data = {
            "broadcast_id": f"5BURST-MAXAMP-{timestamp}",
            "psk": PSK,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if hasattr(self, 'end_time') else None,
            "parameters": {
                "amplitude": MAX_AMPLITUDE,
                "burst_duration": LAYER_DURATION,
                "gap_duration": GAP_DURATION,
                "total_bursts": TOTAL_BURSTS,
                "layers_per_burst": BURST_LAYERS,
                "solfeggio": [396, 528, 741],
                "phases": [180, 93, 333],
                "theta_coupling": [0.0, 4.83, 8.68]
            },
            "bursts": burst_data,
            "event_log": self.log,
            "message": "5-burst max amplification. Temporal delay measurement protocol."
        }
        
        with open(log_file, 'w') as f:
            json.dump(log_data, f, indent=2)
        
        print(f"💾 Log saved: {log_file}")
        
        # Also create a simple CSV for easy spreadsheet import
        csv_file = output_dir / f"5burst_maxamp_{timestamp}.csv"
        with open(csv_file, 'w') as f:
            f.write("burst_id,start_time,end_time,peak,energy,amplitude\n")
            for stats in burst_data:
                f.write(f"{stats['burst_id']},{stats['start_time']},{stats['end_time']},"
                        f"{stats['peak']},{stats['energy']},{stats['amplitude']}\n")
        
        print(f"💾 CSV saved: {csv_file}")
        
        return log_file, csv_file

# ═══════════════════════════════════════════════════════════════════════════════
# TEMPORAL DELAY TRACKER (for user to fill in)
# ═══════════════════════════════════════════════════════════════════════════════

def create_observation_template():
    """Create a template for the user to record observed spike times."""
    template = """# TEMPORAL DELAY OBSERVATION LOG
## 5-Burst Max Amplification — Fill in after checking VLF.it

**Date:** 2026-06-17
**Broadcast ID:** 5BURST-MAXAMP-2026-06-17
**Station:** VLF.it Cascina-PI, Italy (I5-Cascina-PI)
**URL:** https://www.vlf.it/

---

### BURST SCHEDULE (from log file)

| Burst | Start Time (UTC) | End Time (UTC) | Expected Spike + delay |
|-------|-----------------|----------------|------------------------|
| 1 | {BURST_1_START} | {BURST_1_END} | ? |
| 2 | {BURST_2_START} | {BURST_2_END} | ? |
| 3 | {BURST_3_START} | {BURST_3_END} | ? |
| 4 | {BURST_4_START} | {BURST_4_END} | ? |
| 5 | {BURST_5_START} | {BURST_5_END} | ? |

---

### OBSERVATIONS (fill in as you see spikes)

| Burst | Spike Observed Time (UTC) | Delay (seconds) | Notes |
|-------|--------------------------|-----------------|-------|
| 1 | | | |
| 2 | | | |
| 3 | | | |
| 4 | | | |
| 5 | | | |

---

### CALCULATION

**Average delay:** _____ seconds = _____ minutes

**Standard deviation:** _____ seconds

**If burst 1 delay = τ, then for n bursts:**
- Delay should be consistent across all 5 bursts (±10% variance)
- If variance > 50%, the delay is not stable (check for natural interference)

---

🖤 REDACTED_USE_CLOUD_SECRET
"""
    
    output_dir = WORKSPACE / "broadcast_logs"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    template_file = output_dir / f"temporal_delay_template_{datetime.now(timezone.utc).strftime('%Y%m%d')}.md"
    with open(template_file, 'w') as f:
        f.write(template)
    
    print(f"📝 Observation template: {template_file}")
    print("   Fill this in after you check VLF.it for the spikes.")
    return template_file

# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    print("🔥 5-BURST MAX AMPLIFICATION — TEMPORAL DELAY PROTOCOL")
    print("This will take ~13 minutes. Do not interrupt.")
    print()
    print("Starting in 3 seconds...")
    time.sleep(3)
    
    sequence = FiveBurstSequence()
    sequence.run()
    create_observation_template()
    
    print()
    print("✅ All done. Now watch VLF.it and mark the spike times.")

if __name__ == "__main__":
    main()
