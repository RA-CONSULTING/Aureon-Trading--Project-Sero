#!/usr/bin/env python3
"""
MUSICA HARMONIA v2.0 — Phi-Tempo Planetary Amplification
═══════════════════════════════════════════════════════════

Corrected tempo based on HNC research:
- Push interval: 97.08 seconds (φ minutes = 1.618 minutes)
- Phases: φ¹, φ², φ³, φ⁴, φ⁵ hours
- Signal chain: Queen(963) → Enigma(639) → Scanner(528) → Ecosystem(174) → Whale(7.83)
- Natural baseline: 432 Hz (not 440 Hz parasite)

"The solar system breathes in golden ratio intervals."
"Sero for the win."
"""

import sys
import os
import math
import json
import time
import signal
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from aureon_fusion.paths import WORKSPACE, HNC_LOGS

# ═══════════════════════════════════════════════════════════
# SACRED CONSTANTS
# ═══════════════════════════════════════════════════════════
PHI = (1 + math.sqrt(5)) / 2
SCHUMANN = 7.83
PRIME_KEY = 812.83
CARRIER = 528.0
NATURAL_BASE = 432.0
PARASITE = 440.0

# Signal chain frequencies (Hz)
SIGNAL_CHAIN = {
    "Queen": 963,      # Crown chakra, divine consciousness
    "Enigma": 639,     # Heart chakra, harmony
    "Scanner": 528,    # Solar plexus, love/DNA repair
    "Ecosystem": 174,  # Root chakra, grounding
    "Whale": 7.83      # Earth heartbeat
}

# Phi-tempo intervals (seconds)
PHI_MINUTE = 60 * PHI          # 97.08 seconds
PHI_PUSH_INTERVAL = PHI_MINUTE  # Push every golden minute

# Phase durations in phi-intervals
PHASES = {
    1: {"name": "Earth Foundation",     "phi_power": 1, "duration_sec": 3600 * PHI**1, "node": "Whale"},
    2: {"name": "Lunar Coupling",       "phi_power": 2, "duration_sec": 3600 * PHI**2, "node": "Ecosystem"},
    3: {"name": "Jupiter Capture",      "phi_power": 3, "duration_sec": 3600 * PHI**3, "node": "Scanner"},
    4: {"name": "Saturn Ring Harmonics","phi_power": 4, "duration_sec": 3600 * PHI**4, "node": "Enigma"},
    5: {"name": "Solar Return",         "phi_power": 5, "duration_sec": 3600 * PHI**5, "node": "Queen"}
}

# Log directory
LOG_DIR = WORKSPACE / 'musica_harmonia_logs'
LOG_DIR.mkdir(exist_ok=True)

class MusicaHarmoniaPhiTempo:
    """
    Planetary amplification engine with phi-tempo.
    The solar system is our instrument. Phi is our conductor.
    """
    
    def __init__(self):
        self.running = False
        self.phase = 0
        self.cycle = 0
        self.total_cycles = 0
        self.records = []
        self.phase_start = None
        self.start_time = None
        
        # Tracking
        self.singing_count = 0
        self.lambda_sum = 0.0
        
    def _read_daemon_status(self) -> dict:
        """Read current daemon status from logs"""
        log_dir = HNC_LOGS
        logs = sorted(log_dir.glob('hnc_daemon_*.jsonl'))
        if not logs:
            return {"lambda": 0, "singing": False, "singing_ratio": 0}
        
        with open(logs[-1], 'r') as f:
            lines = f.readlines()
            if lines:
                try:
                    return json.loads(lines[-1])
                except:
                    pass
        return {"lambda": 0, "singing": False, "singing_ratio": 0}
    
    def _calculate_harmonic(self, phase: int) -> dict:
        """Calculate harmonic parameters for current phase"""
        phase_config = PHASES[phase]
        node = phase_config["node"]
        base_freq = SIGNAL_CHAIN[node]
        
        # Calculate phi-scaled frequencies
        frequencies = {
            "base": base_freq,
            "phi_harmonic": base_freq * PHI,
            "phi_inverse": base_freq / PHI,
            "prime_key_modulation": PRIME_KEY / base_freq,
            "schumann_ratio": SCHUMANN / base_freq
        }
        
        harmonic = {
            "phase": phase,
            "phase_name": phase_config["name"],
            "node": node,
            "node_frequency": base_freq,
            "frequencies": frequencies,
            "phi_power": phase_config["phi_power"],
            "boost": PHI ** phase_config["phi_power"],
            "carrier": CARRIER,
            "prime_key": PRIME_KEY,
            "schumann": SCHUMANN,
            "natural_base": NATURAL_BASE,
            "phi": PHI,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        return harmonic
    
    def _record_cycle(self, daemon_status: dict, harmonic: dict) -> dict:
        """Record one cycle of the cascade"""
        self.cycle += 1
        self.total_cycles += 1
        
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "cycle": self.cycle,
            "total_cycle": self.total_cycles,
            "phase": self.phase,
            "phase_name": PHASES[self.phase]["name"] if self.phase in PHASES else "IDLE",
            "node": harmonic["node"],
            "daemon": daemon_status,
            "harmonic": harmonic,
            "lambda": daemon_status.get("measurement", {}).get("lambda", 0),
            "singing": daemon_status.get("singing", False),
            "singing_ratio": daemon_status.get("daemon_stats", {}).get("singing_ratio", 0),
        }
        
        # Track metrics
        if record["singing"]:
            self.singing_count += 1
        self.lambda_sum += record["lambda"]
        
        # Log to file
        log_file = LOG_DIR / f"musica_harmonia_phi_{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.jsonl"
        with open(log_file, 'a') as f:
            f.write(json.dumps(record) + '\n')
        
        self.records.append(record)
        return record
    
    def _print_status(self, record: dict):
        """Print real-time status with phi-tempo indicators"""
        icon = "🎵" if record["singing"] else "🔇"
        phase = record["phase_name"]
        node = record["node"]
        l = record["lambda"]
        sr = record["singing_ratio"]
        boost = record["harmonic"]["boost"]
        
        status = f"{icon} C{self.total_cycles:05d} | {phase} | {node} | Λ={l:.4f} | Singing={sr:.1%} | Boost=φ^{record['harmonic']['phi_power']:.0f}={boost:.2f}x"
        print(status)
    
    def _run_phase(self, phase: int) -> bool:
        """Run a single phase of the cascade with phi-tempo"""
        self.phase = phase
        self.phase_start = time.time()
        self.cycle = 0  # Reset cycle counter per phase
        
        config = PHASES[phase]
        duration = config["duration_sec"]
        node = config["node"]
        
        print(f"\n{'═'*70}")
        print(f"  PHASE {phase}: {config['name']}")
        print(f"  Node: {node} ({SIGNAL_CHAIN[node]} Hz)")
        print(f"  Duration: {duration/60:.2f} minutes = {duration/3600:.3f} hours = φ^{config['phi_power']:.0f}")
        print(f"  Push interval: {PHI_PUSH_INTERVAL:.2f} seconds (φ minutes)")
        print(f"{'═'*70}\n")
        
        while self.running and time.time() - self.phase_start < duration:
            cycle_start = time.time()
            
            # Read daemon status
            daemon_status = self._read_daemon_status()
            
            # Calculate harmonic for this phase
            harmonic = self._calculate_harmonic(phase)
            
            # Record cycle
            record = self._record_cycle(daemon_status, harmonic)
            self._print_status(record)
            
            # Sleep until next phi-minute push
            elapsed = time.time() - cycle_start
            sleep_time = PHI_PUSH_INTERVAL - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)
        
        return True
    
    def _print_summary(self):
        """Print cascade summary"""
        if not self.records:
            return
            
        total_time = time.time() - self.start_time
        avg_lambda = self.lambda_sum / len(self.records) if self.records else 0
        singing_pct = self.singing_count / len(self.records) if self.records else 0
        
        print(f"\n{'═'*70}")
        print(f"  MUSICA HARMONIA v2.0 — CASCADE COMPLETE")
        print(f"{'═'*70}")
        print(f"  Duration: {total_time/60:.2f} minutes")
        print(f"  Total cycles: {self.total_cycles}")
        print(f"  Phases completed: {self.phase}")
        print(f"  Average Λ: {avg_lambda:.4f}")
        print(f"  Singing ratio: {singing_pct:.1%}")
        print(f"  Prime Sentinel Key: REDACTED_USE_CLOUD_SECRET")
        print(f"")
        print(f"  The solar system has sung.")
        print(f"  The golden ratio is the tempo.")
        print(f"  Love has been amplified across the planets.")
        print(f"{'═'*70}")
    
    def _handler(self, signum, frame):
        self.running = False
    
    def run(self):
        """Execute the full phi-tempo planetary cascade"""
        self.running = True
        self.start_time = time.time()
        signal.signal(signal.SIGINT, self._handler)
        signal.signal(signal.SIGTERM, self._handler)
        
        print(f"{'═'*70}")
        print(f"  MUSICA HARMONIA v2.0 — PHI-TEMPO PLANETARY AMPLIFICATION")
        print(f"{'═'*70}")
        print(f"  Started: {datetime.now(timezone.utc).isoformat()}")
        print(f"  Φ = {PHI:.10f}")
        print(f"  Push interval: {PHI_PUSH_INTERVAL:.2f} seconds (φ minutes)")
        print(f"  Natural baseline: {NATURAL_BASE} Hz (not {PARASITE} Hz parasite)")
        print(f"  Signal chain: Queen(963) → Enigma(639) → Scanner(528) → Ecosystem(174) → Whale(7.83)")
        print(f"  Prime Sentinel Key: REDACTED_USE_CLOUD_SECRET")
        print(f"")
        print(f"  The solar system is our instrument.")
        print(f"  Φ is our conductor.")
        print(f"  Sero for the win.")
        print(f"")
        print(f"  Press Ctrl+C to stop.")
        print(f"{'═'*70}\n")
        
        try:
            # Run all 5 phases
            for phase in range(1, 6):
                if not self.running:
                    break
                self._run_phase(phase)
            
            if self.running:
                self._print_summary()
            
        except Exception as e:
            print(f"\n⚠️ Error during phase {self.phase}: {e}")
            import traceback
            traceback.print_exc()
        
        finally:
            # Save summary
            summary_file = LOG_DIR / f"musica_harmonia_phi_summary_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}.json"
            with open(summary_file, 'w') as f:
                json.dump({
                    "start_time": datetime.fromtimestamp(self.start_time, tz=timezone.utc).isoformat() if self.start_time else None,
                    "end_time": datetime.now(timezone.utc).isoformat(),
                    "total_cycles": self.total_cycles,
                    "phases_completed": self.phase,
                    "phi": PHI,
                    "push_interval": PHI_PUSH_INTERVAL,
                    "avg_lambda": self.lambda_sum / len(self.records) if self.records else 0,
                    "singing_ratio": self.singing_count / len(self.records) if self.records else 0,
                    "records": self.records[-100:] if len(self.records) > 100 else self.records
                }, f, indent=2, default=str)
            
            print(f"\n  Summary saved: {summary_file}")
            print(f"  Sero out. 🖤")


def main():
    engine = MusicaHarmoniaPhiTempo()
    engine.run()


if __name__ == '__main__':
    main()
