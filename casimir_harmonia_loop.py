#!/usr/bin/env python3
"""
CASIMIR HARMONIC AMPLIFIER — Loop Mode
═══════════════════════════════════════════════════════════════════

Runs the Casimir amplifier in a continuous loop, feeding the amplified
state back into the next measurement cycle. This creates a feedback loop
that should stabilize the field into a singing state.

Usage: python3 casimir_harmonia_loop.py [--iterations N] [--interval S]
"""

import sys
import os
import math
import json
import time
import argparse
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from aureon_fusion.paths import WORKSPACE
sys.path.insert(0, str(WORKSPACE / "aureon-trading"))
os.environ['AUREON_ALLOW_SIM_FALLBACK'] = 'on'

from signal_monitor import SignalMonitor, FieldMeasurement
from casimir_harmonia import CasimirHarmonicAmplifier, signal_fingerprint


def run_loop(iterations: int = 10, interval: float = 5.0):
    """Run the Casimir amplifier in a feedback loop"""
    
    print("🔬 Casimir Harmonic Amplifier — Loop Mode")
    print(f"   Iterations: {iterations}")
    print(f"   Interval: {interval}s")
    print(f"{'═'*60}\n")
    
    monitor = SignalMonitor()
    amplifier = CasimirHarmonicAmplifier(tau_s=interval)
    
    # Take first measurement to seed history
    print("📡 Seeding history...")
    baseline = monitor.measure()
    amplifier.signal_history.append({
        'epoch': time.time(),
        'fingerprint': signal_fingerprint(baseline),
        'lambda': baseline.lambda_t,
        'coherence': baseline.field_coherence,
    })
    print(f"   Baseline Λ(t): {baseline.lambda_t:.6f}")
    print(f"   Baseline coherence: {baseline.field_coherence:.6f}")
    print(f"   Baseline awakening: {baseline.awakening_index:.2f}%")
    print()
    
    results = []
    singing_count = 0
    
    for i in range(iterations):
        print(f"{'─'*60}")
        print(f"  Iteration {i+1}/{iterations}")
        print(f"{'─'*60}")
        
        # Measure current field
        measurement = monitor.measure()
        
        # Amplify with Casimir
        result = amplifier.amplify(measurement)
        results.append(result)
        
        # Print brief report
        c = result['casimir']
        m = result['musica']
        s = result['sustain']
        
        print(f"  Λ(t): {s['lambda_original']:.6f} → {s['lambda_amplified']:.6f}")
        print(f"  Casimir Force: {c['force']:.6f}")
        print(f"  Sustain Boost: {s['boost']:.6f}x")
        print(f"  Musica Score: {m['musica_score']:.6f}")
        print(f"  Solfeggio: {m['solfeggio_coherence']:.1%}")
        print(f"  Phi Lock: {'✅' if m['phi_lock'] else '❌'}")
        print(f"  Singing: {'🎵 YES' if result['singing'] else '🔇 NO'}")
        
        if result['singing']:
            singing_count += 1
            print(f"\n  🎵🎵🎵 MUSICA HARMONIA ACHIEVED 🎵🎵🎵")
            print(f"     The field is singing at {result['harmonic_frequency']} Hz")
            print(f"     Sustain boost: {s['boost']:.6f}x")
            print(f"     β amplified: {s['beta_amplified']:.4f}")
        
        # Log
        log_path = Path("casimir_harmonia_loop_log.jsonl")
        with open(log_path, 'a', encoding="utf-8") as f:
            f.write(json.dumps(result, default=str) + '\n')
        
        if i < iterations - 1:
            print(f"\n  Sleeping {interval}s...")
            time.sleep(interval)
    
    # Summary
    print(f"\n{'═'*60}")
    print(f"  LOOP SUMMARY")
    print(f"{'═'*60}")
    
    lambdas_orig = [r['sustain']['lambda_original'] for r in results]
    lambdas_amp = [r['sustain']['lambda_amplified'] for r in results]
    forces = [r['casimir']['force'] for r in results]
    musica_scores = [r['musica']['musica_score'] for r in results]
    
    print(f"  Iterations: {iterations}")
    print(f"  Singing states: {singing_count}/{iterations}")
    print(f"  Λ(t) range: {min(lambdas_orig):.6f} → {max(lambdas_orig):.6f}")
    print(f"  Λ(t) amplified: {min(lambdas_amp):.6f} → {max(lambdas_amp):.6f}")
    print(f"  Casimir force range: {min(forces):.6f} → {max(forces):.6f}")
    print(f"  Musica score range: {min(musica_scores):.6f} → {max(musica_scores):.6f}")
    print(f"  Final status: {'🎵 SINGING' if results[-1]['singing'] else '🔇 SILENT'}")
    
    if singing_count > 0:
        print(f"\n  🎵 THE FIELD SANG {singing_count} TIMES")
        print(f"     Musica Harmonia is possible.")
    
    print(f"{'═'*60}")
    print(f"\n✅ Log saved to: casimir_harmonia_loop_log.jsonl")


def main():
    parser = argparse.ArgumentParser(description='Casimir Harmonic Amplifier — Loop Mode')
    parser.add_argument('--iterations', type=int, default=10, help='Number of iterations')
    parser.add_argument('--interval', type=float, default=5.0, help='Seconds between iterations')
    args = parser.parse_args()
    
    run_loop(iterations=args.iterations, interval=args.interval)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
