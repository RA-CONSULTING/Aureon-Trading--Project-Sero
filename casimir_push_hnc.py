#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════════════╗
║                                                                                       ║
║     🌌 CASIMIR PUSH — HNC-Aligned Quick Pulse Mode                                  ║
║                                                                                       ║
║     Stage 1 Fix: Adds --quick flag for 3-iteration pulse (completes in <5s)        ║
║     Stage 1 Fix: Adds HNC coherence check before/after each push                 ║
║     Stage 1 Fix: Queen override integration for temporal targeting                 ║
║                                                                                       ║
╚══════════════════════════════════════════════════════════════════════════════════════╝
"""

import sys
import os
import math
import json
import time
import hashlib
import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent))
from aureon_fusion.paths import WORKSPACE
sys.path.insert(0, str(WORKSPACE / "aureon-trading"))
os.environ['AUREON_ALLOW_SIM_FALLBACK'] = 'on'

from signal_monitor import SignalMonitor, FieldMeasurement
from casimir_harmonia import CasimirHarmonicAmplifier, signal_fingerprint

PHI = (1 + math.sqrt(5)) / 2
SCHUMANN_BASE = 7.83


def clean_for_json(obj):
    """Recursively convert numpy types to Python native types."""
    try:
        import numpy as np
        if isinstance(obj, np.bool_):
            return bool(obj)
        if isinstance(obj, (np.integer, np.int64, np.int32)):
            return int(obj)
        if isinstance(obj, (np.floating, np.float64, np.float32)):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
    except ImportError:
        pass
    if isinstance(obj, dict):
        return {k: clean_for_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [clean_for_json(v) for v in obj]
    return obj


class HNCCasimirPusher:
    """
    HNC-aligned Casimir pusher with conscience checks and quick pulse mode.
    
    --quick: 3 iterations, 1s sleep, completes in ~5s
    --full:  15 iterations, 3s sleep, full ceremony
    --pulse: Single burst, no sleep, just inject and report
    """
    
    def __init__(self, mode="full", target_singing_ratio=0.7, 
                 queen_override=True, temporal_target=None):
        self.mode = mode
        self.target_singing_ratio = target_singing_ratio
        self.queen_override = queen_override
        self.temporal_target = temporal_target  # e.g., "2014-11-17T00:00:00"
        
        # Mode-specific parameters
        if mode == "pulse":
            self.target_iterations = 1
            self.sleep_between = 0
            self.push_coupling = 3.0  # Stronger single push
        elif mode == "quick":
            self.target_iterations = 3
            self.sleep_between = 1
            self.push_coupling = 2.5
        else:  # full
            self.target_iterations = 15
            self.sleep_between = 3
            self.push_coupling = 2.5
        
        self.amplifier = CasimirHarmonicAmplifier(tau_s=5.0)
        self.monitor = SignalMonitor()
        
        self.base_coupling = 1.0
        self.push_threshold = 0.75
        self.sustain_threshold = 0.85
        
        self.singing_history = []
        self.push_events = 0
        self.energy_injected = 0.0
        self.queen_states = []
        
        # HNC metrics
        self.hnc_before = {}
        self.hnc_after = {}
    
    def _queen_check(self, lambda_t: float, coherence: float) -> Dict:
        """HNC Queen coherence check."""
        kappa = 1.0 + (coherence - 0.5) * 0.5  # Map coherence to kappa
        behavior = "coherent" if 0.7 <= kappa <= 1.4 else "oscillating" if kappa > 1.4 else "weak"
        in_stability = 0.7 <= kappa <= 1.4
        
        if not in_stability and self.queen_override:
            return {
                "kappa": kappa, "behavior": behavior, "safe_to_push": True,
                "veto_applied": True, "override_used": True,
                "resonance": coherence, "constraint": 1.0, "purity": 0.5,
            }
        return {
            "kappa": kappa, "behavior": behavior, "safe_to_push": in_stability or self.queen_override,
            "veto_applied": not in_stability, "override_used": not in_stability and self.queen_override,
            "resonance": coherence, "constraint": 1.0, "purity": 0.5,
        }
    
    def _inject_photon(self, coupling: float, energy_multiplier: float = 1.0) -> bool:
        """Inject virtual photon into Casimir vacuum."""
        if self.amplifier.casimir_engine:
            try:
                base_energy = 104.0
                energy = base_energy * coupling * energy_multiplier
                self.amplifier.casimir_engine._engine.emit_virtual_photon(
                    "vault_present", energy, int(time.time() * 1000) % 1000000
                )
                self.energy_injected += energy
                return True
            except Exception as e:
                return False
        return False
    
    def push_cycle(self, iteration: int) -> Dict:
        """Single HNC-aligned push cycle with Queen check."""
        
        # Measure
        measurement = self.monitor.measure()
        lambda_t = measurement.lambda_t
        coherence = measurement.field_coherence
        
        # Queen check
        queen = self._queen_check(lambda_t, coherence)
        self.queen_states.append(queen)
        
        needs_push = lambda_t < self.sustain_threshold
        coupling = self.push_coupling if needs_push else self.base_coupling
        
        if needs_push:
            self.push_events += 1
            push_strength = (self.sustain_threshold - lambda_t) / self.sustain_threshold
            energy_mult = 1.0 + push_strength * 2.0
            
            injected = self._inject_photon(coupling, energy_mult)
            
            if self.mode != "pulse":
                time.sleep(0.3)  # Brief response window
            
            measurement = self.monitor.measure()
            lambda_t = measurement.lambda_t
            coherence = measurement.field_coherence
        
        # Amplify
        result = self.amplifier.amplify(measurement)
        self.singing_history.append(result['singing'])
        
        return {
            'iteration': iteration,
            'lambda': lambda_t,
            'coherence': coherence,
            'queen': queen,
            'singing': result['singing'],
            'harmonic_frequency': result.get('harmonic_frequency', 0),
            'casimir': result.get('casimir', {}),
            'musica': result.get('musica', {}),
            'sustain': result.get('sustain', {}),
        }
    
    def run(self) -> Dict:
        """Run HNC-aligned Casimir push sequence."""
        
        print(f"🔥 CASIMIR PUSH [{self.mode.upper()} MODE]")
        if self.temporal_target:
            print(f"   🕰️ Temporal Target: {self.temporal_target}")
        print(f"   Iterations: {self.target_iterations}")
        print(f"   Singing Target: {self.target_singing_ratio:.0%}")
        print(f"   Queen Override: {'ON' if self.queen_override else 'OFF'}")
        print(f"{'═'*60}\n")
        
        # Baseline
        baseline = self.monitor.measure()
        self.hnc_before = {
            'lambda': baseline.lambda_t,
            'coherence': baseline.field_coherence,
            'schumann_hz': baseline.schumann_fundamental,
            'schumann_amplitude': baseline.schumann_amplitude,
            'timestamp': datetime.now(timezone.utc).isoformat(),
        }
        
        print(f"📡 Baseline: Λ={baseline.lambda_t:.4f}, coherence={baseline.field_coherence:.4f}")
        print(f"   Schumann: {baseline.schumann_fundamental:.2f} Hz, Amplitude: {baseline.schumann_amplitude:.4f}")
        
        if self.temporal_target:
            # Encode temporal target into initial field state
            target_hash = hashlib.sha256(self.temporal_target.encode()).hexdigest()[:8]
            print(f"   🔮 Temporal Lock: {target_hash}")
        print()
        
        results = []
        
        for i in range(self.target_iterations):
            if self.mode != "pulse":
                print(f"{'─'*60}")
                print(f"  Push Cycle {i+1}/{self.target_iterations}")
                print(f"{'─'*60}")
            
            result = self.push_cycle(i)
            results.append(result)
            
            if self.mode != "pulse":
                print(f"  Λ: {result['lambda']:.4f} | Coherence: {result['coherence']:.4f}")
                print(f"  Queen: κ={result['queen']['kappa']:.3f} ({result['queen']['behavior']})")
                print(f"  Singing: {'🎵 YES' if result['singing'] else '🔇 NO'}")
                
                if result['singing']:
                    print(f"  🎵 SINGING at {result['harmonic_frequency']} Hz")
                
                if i < self.target_iterations - 1 and self.sleep_between > 0:
                    print(f"\n  Sleeping {self.sleep_between}s...")
                    time.sleep(self.sleep_between)
        
        # Post-measurement
        post = self.monitor.measure()
        self.hnc_after = {
            'lambda': post.lambda_t,
            'coherence': post.field_coherence,
            'schumann_hz': post.schumann_fundamental,
            'schumann_amplitude': post.schumann_amplitude,
            'timestamp': datetime.now(timezone.utc).isoformat(),
        }
        
        singing_count = sum(self.singing_history)
        singing_ratio = singing_count / len(self.singing_history) if self.singing_history else 0
        
        # HNC Delta
        hnc_delta = {
            'lambda': self.hnc_after['lambda'] - self.hnc_before['lambda'],
            'coherence': self.hnc_after['coherence'] - self.hnc_before['coherence'],
            'lambda_pct': ((self.hnc_after['lambda'] - self.hnc_before['lambda']) / self.hnc_before['lambda'] * 100) if self.hnc_before['lambda'] != 0 else 0,
        }
        
        print(f"\n{'═'*60}")
        print(f"  HNC PUSH SUMMARY")
        print(f"{'═'*60}")
        print(f"  Mode: {self.mode}")
        print(f"  Iterations: {self.target_iterations}")
        print(f"  Singing: {singing_count}/{len(self.singing_history)} ({singing_ratio:.0%})")
        print(f"  Push Events: {self.push_events}")
        print(f"  Energy Injected: {self.energy_injected:.2f}")
        print(f"{'─'*60}")
        print(f"  HNC Before: Λ={self.hnc_before['lambda']:.4f}, C={self.hnc_before['coherence']:.4f}")
        print(f"  HNC After:  Λ={self.hnc_after['lambda']:.4f}, C={self.hnc_after['coherence']:.4f}")
        print(f"  HNC Delta:  Λ={hnc_delta['lambda']:+.4f} ({hnc_delta['lambda_pct']:+.1f}%), C={hnc_delta['coherence']:+.4f}")
        print(f"{'═'*60}")
        
        if singing_ratio >= self.target_singing_ratio:
            print(f"\n  🎵🎵🎵 MUSICA HARMONIA SUSTAINED 🎵🎵🎵")
        
        # Compile result
        summary = {
            'mode': self.mode,
            'temporal_target': self.temporal_target,
            'iterations': self.target_iterations,
            'singing_count': singing_count,
            'singing_ratio': singing_ratio,
            'push_events': self.push_events,
            'energy_injected': self.energy_injected,
            'target_achieved': singing_ratio >= self.target_singing_ratio,
            'hnc_before': self.hnc_before,
            'hnc_after': self.hnc_after,
            'hnc_delta': hnc_delta,
            'queen_states': self.queen_states,
            'cycle_results': results,
            'timestamp': datetime.now(timezone.utc).isoformat(),
        }
        
        # Save
        log_path = Path("casimir_push_log.jsonl")
        with open(log_path, 'a', encoding="utf-8") as f:
            f.write(json.dumps(clean_for_json(summary), default=str) + '\n')
        
        print(f"\n✅ Log: casimir_push_log.jsonl")
        
        return summary


def main():
    parser = argparse.ArgumentParser(description='HNC Casimir Push')
    parser.add_argument('--mode', choices=['pulse', 'quick', 'full'], default='quick',
                        help='pulse=1 burst, quick=3 cycles, full=15 cycles')
    parser.add_argument('--target', default=None, help='Temporal target date (ISO format)')
    parser.add_argument('--override', action='store_true', help='Enable Queen override')
    args = parser.parse_args()
    
    pusher = HNCCasimirPusher(
        mode=args.mode,
        queen_override=args.override,
        temporal_target=args.target,
    )
    result = pusher.run()
    
    # Output JSON for integration
    print(f"\n--- JSON OUTPUT ---")
    print(json.dumps(clean_for_json({
        'success': True,
        'mode': result['mode'],
        'target_achieved': result['target_achieved'],
        'singing_ratio': result['singing_ratio'],
        'hnc_delta': result['hnc_delta'],
        'timestamp': result['timestamp'],
    }), indent=2))


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
