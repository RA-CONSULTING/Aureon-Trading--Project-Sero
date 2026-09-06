#!/usr/bin/env python3
"""
MUSICA HARMONIA — Planetary Amplification Engine
═════════════════════════════════════════════════

Executes the 5-phase planetary cascade:
1. Earth Foundation (60 min) — stabilize 7.83 Hz
2. Lunar Coupling (30 min) — match tidal resonance
3. Jupiter Capture (12 hours) — Io plasma torus amplification
4. Saturn Ring Harmonics (6 hours) — geometric coherence
5. Solar Return (24 hours) — chorus returns amplified

"The solar system is our instrument. We are the conductor."
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

# Constants
PHI = (1 + math.sqrt(5)) / 2
SCHUMANN = 7.83
PRIME_KEY = 812.83
CARRIER = 528.0

# Phase definitions
PHASES = {
    1: {"name": "Earth Foundation", "duration": 3600, "target_lambda": 1.0, "target_singing": 1.0, "boost": 1.2},
    2: {"name": "Lunar Coupling", "duration": 1800, "target_lambda": 1.0, "target_singing": 1.0, "boost": 1.5, "modulation": "tidal_12.4h"},
    3: {"name": "Jupiter Capture", "duration": 43200, "target_lambda": 1.0, "target_singing": 1.0, "boost": 5.0, "amplification": "io_plasma"},
    4: {"name": "Saturn Ring Harmonics", "duration": 21600, "target_lambda": 1.0, "target_singing": 1.0, "boost": 8.09, "phi_lock": True},
    5: {"name": "Solar Return", "duration": 86400, "target_lambda": 1.0, "target_singing": 1.0, "boost": 10.0, "chorus": True}
}

# Log directory
LOG_DIR = WORKSPACE / 'musica_harmonia_logs'
LOG_DIR.mkdir(exist_ok=True)

class MusicaHarmoniaEngine:
    """
    Planetary amplification engine. Interfaces with the HNC daemon
    to execute the 5-phase cascade.
    """
    
    def __init__(self):
        self.running = False
        self.phase = 0
        self.cycle = 0
        self.phase_start = None
        self.records = []
        
    def _read_daemon_status(self) -> dict:
        """Read current daemon status from logs"""
        log_dir = HNC_LOGS
        logs = sorted(log_dir.glob('hnc_daemon_*.jsonl'))
        if not logs:
            return {"lambda": 0, "singing": False, "singing_ratio": 0}
        
        # Read last line of latest log
        with open(logs[-1], 'r') as f:
            lines = f.readlines()
            if lines:
                try:
                    return json.loads(lines[-1])
                except:
                    pass
        return {"lambda": 0, "singing": False, "singing_ratio": 0}
    
    def _inject_planetary_harmonic(self, phase: int) -> dict:
        """Calculate and inject planetary harmonic for current phase"""
        phase_config = PHASES[phase]
        
        # Base frequencies
        frequencies = {
            1: [SCHUMANN, PRIME_KEY],  # Earth
            2: [SCHUMANN, 12.4/24 * SCHUMANN, PRIME_KEY],  # Earth + Lunar tidal
            3: [SCHUMANN, 0.000023 * 1000000, PRIME_KEY],  # Jupiter magnetosphere
            4: [SCHUMANN, 0.000009 * 1000000, PRIME_KEY],  # Saturn rings
            5: [SCHUMANN, CARRIER, PRIME_KEY]  # Full chorus
        }
        
        harmonic = {
            "phase": phase,
            "phase_name": phase_config["name"],
            "frequencies": frequencies[phase],
            "boost": phase_config["boost"],
            "carrier": CARRIER,
            "prime_key": PRIME_KEY,
            "phi": PHI,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        return harmonic
    
    def _record_cycle(self, daemon_status: dict, harmonic: dict) -> dict:
        """Record one cycle of the cascade"""
        self.cycle += 1
        
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "cycle": self.cycle,
            "phase": self.phase,
            "phase_name": PHASES[self.phase]["name"] if self.phase in PHASES else "IDLE",
            "daemon": daemon_status,
            "harmonic": harmonic,
            "lambda": daemon_status.get("measurement", {}).get("lambda", 0),
            "singing": daemon_status.get("singing", False),
            "singing_ratio": daemon_status.get("daemon_stats", {}).get("singing_ratio", 0),
        }
        
        # Log to file
        log_file = LOG_DIR / f"musica_harmonia_{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.jsonl"
        with open(log_file, 'a') as f:
            f.write(json.dumps(record) + '\n')
        
        self.records.append(record)
        return record
    
    def _print_status(self, record: dict):
        """Print real-time status"""
        icon = "🎵" if record["singing"] else "🔇"
        phase = record["phase_name"]
        l = record["lambda"]
        sr = record["singing_ratio"]
        boost = record["harmonic"]["boost"]
        
        status = f"{icon} C{self.cycle:05d} | {phase} | Λ={l:.4f} | Singing={sr:.1%} | Boost={boost:.1f}x"
        print(status)
    
    def _run_phase(self, phase: int) -> bool:
        """Run a single phase of the cascade"""
        self.phase = phase
        self.phase_start = time.time()
        config = PHASES[phase]
        duration = config["duration"]
        
        print(f"\n{'═'*60}")
        print(f"  PHASE {phase}: {config['name']}")
        print(f"  Duration: {duration//60} minutes")
        print(f"  Target: Λ={config['target_lambda']}, Singing={config['target_singing']:.0%}")
        print(f"  Boost: {config['boost']}x")
        print(f"{'═'*60}\n")
        
        while self.running and time.time() - self.phase_start < duration:
            # Read daemon status
            daemon_status = self._read_daemon_status()
            
            # Calculate harmonic for this phase
            harmonic = self._inject_planetary_harmonic(phase)
            
            # Record cycle
            record = self._record_cycle(daemon_status, harmonic)
            self._print_status(record)
            
            # Sleep 10 seconds between checks
            for _ in range(10):
                if not self.running:
                    break
                time.sleep(1)
        
        return True
    
    def _handler(self, signum, frame):
        self.running = False
    
    def run(self):
        """Execute the full planetary cascade"""
        self.running = True
        signal.signal(signal.SIGINT, self._handler)
        signal.signal(signal.SIGTERM, self._handler)
        
        print(f"{'═'*60}")
        print(f"  MUSICA HARMONIA — PLANETARY AMPLIFICATION")
        print(f"{'═'*60}")
        print(f"  Started: {datetime.now(timezone.utc).isoformat()}")
        print(f"  The solar system is our instrument.")
        print(f"  We are the conductor.")
        print(f"  Press Ctrl+C to stop.")
        print(f"{'═'*60}\n")
        
        try:
            # Run all 5 phases
            for phase in range(1, 6):
                if not self.running:
                    break
                self._run_phase(phase)
            
            if self.running:
                print(f"\n{'═'*60}")
                print(f"  CASCADE COMPLETE")
                print(f"  The solar system has sung.")
                print(f"  Love has been amplified across the planets.")
                print(f"{'═'*60}")
            
        except Exception as e:
            print(f"\n⚠️ Error during phase {self.phase}: {e}")
            import traceback
            traceback.print_exc()
        
        finally:
            # Save summary
            summary_file = LOG_DIR / f"musica_harmonia_summary_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}.json"
            with open(summary_file, 'w') as f:
                json.dump({
                    "start_time": self.records[0]["timestamp"] if self.records else None,
                    "end_time": datetime.now(timezone.utc).isoformat(),
                    "total_cycles": self.cycle,
                    "phases_completed": self.phase,
                    "records": self.records[-100:] if len(self.records) > 100 else self.records
                }, f, indent=2, default=str)
            
            print(f"\n  Summary saved: {summary_file}")
            print(f"  Total cycles: {self.cycle}")
            print(f"  Phases completed: {self.phase}")


def main():
    engine = MusicaHarmoniaEngine()
    engine.run()


if __name__ == '__main__':
    main()
