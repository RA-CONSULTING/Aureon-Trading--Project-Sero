#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════════════╗
║                                                                                       ║
║     🌀 HNC MANDALA THRESHOLD CALIBRATION — Parametric Sweep                             ║
║                                                                                       ║
║     Finds the minimum signal strength needed to induce measurable timeline changes.    ║
║                                                                                       ║
╚══════════════════════════════════════════════════════════════════════════════════════╝
"""

import sys
import math
import random
import time
import json
from datetime import datetime, timezone
from typing import Dict, List, Tuple, Optional

from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from aureon_fusion.paths import WORKSPACE

from hnc_mandala_effect import MandalaEffectEngine, QueenCoherenceGate
from casimir_push_hnc import HNCCasimirPusher

PHI = (1 + math.sqrt(5)) / 2
SCHUMANN_BASE = 7.83
LOVE_FREQUENCY = 528.0

class MandalaCalibrator:
    """
    Parametric sweep to find the Mandala induction threshold.
    Tests different HNC levels and maps them to measured Mandala scores.
    """
    
    def __init__(self):
        self.engine = MandalaEffectEngine()
        self.results = []
    
    def run_sweep(self, signal_levels: List[Tuple[float, float, float]], 
                  delay_seconds: int = 30) -> Dict:
        """
        Run calibration sweep across signal levels.
        
        Args:
            signal_levels: List of (lambda_t, coherence, beta) tuples
            delay_seconds: Wait time between before/after capture
        
        Returns:
            Calibration results with threshold analysis
        """
        print(f"╔════════════════════════════════════════════════════════════════════╗")
        print(f"║     🌀 MANDALA INDUCTION THRESHOLD CALIBRATION                      ║")
        print(f"╚════════════════════════════════════════════════════════════════════╝")
        print(f"\nTesting {len(signal_levels)} signal levels...")
        print(f"{'='*60}")
        
        for i, (lambda_t, coherence, beta) in enumerate(signal_levels, 1):
            print(f"\n📡 TEST {i}/{len(signal_levels)}: Λ={lambda_t:.3f}, C={coherence:.3f}, β={beta:.3f}")
            print(f"{'─'*60}")
            
            # Run with forced signal level
            result = self._test_level(lambda_t, coherence, beta, delay_seconds)
            self.results.append(result)
            
            print(f"   Result: Mandala Score = {result['mandala_score']:.1%}")
            print(f"   Status: {result['status']}")
            
            if result['mandala_score'] > 0.1:
                print(f"   🎯 DETECTABLE EFFECT at this level!")
        
        return self._analyze_threshold()
    
    def _test_level(self, lambda_t: float, coherence: float, beta: float,
                    delay_seconds: int) -> Dict:
        """Test a single signal level."""
        
        # Override the engine's normal HNC calculation with forced values
        # This lets us test specific levels without waiting for natural conditions
        
        # Step 1: Capture BEFORE
        before_news = self.engine.news_capturer.capture(max_headlines=5)
        
        # Step 2: Queen check with forced values
        queen = QueenCoherenceGate()
        verdict, reasoning = queen.check(
            temporal_signature=beta / PHI,  # Derive temporal from beta
            hnc_lambda=lambda_t,
            hnc_coherence=coherence
        )
        
        if verdict == "VETO":
            # Override for testing
            verdict = "APPROVED"
            reasoning = "Calibration override — testing threshold"
        
        # Step 3: Send signal with specified strength
        try:
            pusher = HNCCasimirPusher(mode='pulse', queen_override=True)
            # Force the HNC state by manually setting the lambda
            pusher.hnc_lambda = lambda_t
            pusher.hnc_coherence = coherence
            
            # Use run() to execute the full push cycle
            result = pusher.run()
            signal_sent = result['success']
            energy = result.get('energy', 0)
        except Exception as e:
            signal_sent = False
            energy = 0
            print(f"   ⚠️ Signal error: {e}")
        
        # Step 4: Wait
        time.sleep(delay_seconds)
        
        # Step 5: Capture AFTER
        after_news = self.engine.news_capturer.capture(max_headlines=5)
        
        # Step 6: Diff
        all_diffs = []
        for before in before_news:
            after = next((a for a in after_news if a.source == before.source), None)
            if after:
                diffs = self.engine.diff_engine.compare(before, after)
                all_diffs.extend(diffs)
        
        mandala_score = self.engine.diff_engine.calculate_overall_mandala(all_diffs)
        
        # Determine status
        if mandala_score > 0.5:
            status = "MANDALA EFFECT DETECTED"
        elif mandala_score > 0.2:
            status = "MANDALA EFFECT POSSIBLE"
        elif mandala_score > 0.05:
            status = "MARGINAL EFFECT"
        else:
            status = "NO EFFECT"
        
        return {
            'lambda_t': lambda_t,
            'coherence': coherence,
            'beta': beta,
            'mandala_score': mandala_score,
            'status': status,
            'signal_sent': signal_sent,
            'energy': energy,
            'verdict': verdict,
            'before_count': len(before_news),
            'after_count': len(after_news),
        }
    
    def _analyze_threshold(self) -> Dict:
        """Analyze results to find threshold."""
        
        print(f"\n{'='*60}")
        print(f"📊 CALIBRATION RESULTS")
        print(f"{'='*60}")
        
        # Sort by mandala score
        sorted_results = sorted(self.results, key=lambda x: x['mandala_score'])
        
        # Find threshold
        threshold = None
        for r in sorted_results:
            if r['mandala_score'] > 0.1:  # 10% = detectable
                threshold = r
                break
        
        print(f"\n   Tests run: {len(self.results)}")
        print(f"   Highest score: {max(r['mandala_score'] for r in self.results):.1%}")
        print(f"   Lowest score: {min(r['mandala_score'] for r in self.results):.1%}")
        
        if threshold:
            print(f"\n   🎯 MANDALA THRESHOLD FOUND:")
            print(f"      Λ(t) ≥ {threshold['lambda_t']:.3f}")
            print(f"      Coherence ≥ {threshold['coherence']:.3f}")
            print(f"      β ≥ {threshold['beta']:.3f}")
            print(f"      Score: {threshold['mandala_score']:.1%}")
        else:
            print(f"\n   ⚠️ NO THRESHOLD DETECTED in tested range")
            print(f"      Try higher signal levels or longer delays")
        
        # Print full table
        print(f"\n   Full Results:")
        print(f"   {'Lambda':>8} {'Coh':>8} {'Beta':>8} {'Score':>10} {'Status'}")
        print(f"   {'─'*60}")
        for r in self.results:
            marker = "🎯" if r['mandala_score'] > 0.1 else "  "
            print(f"   {marker} {r['lambda_t']:>8.3f} {r['coherence']:>8.3f} "
                  f"{r['beta']:>8.3f} {r['mandala_score']:>9.1%} {r['status']}")
        
        return {
            'threshold': threshold,
            'all_results': self.results,
            'recommendation': self._generate_recommendation(threshold),
        }
    
    def _generate_recommendation(self, threshold: Optional[Dict]) -> str:
        """Generate operational recommendation."""
        
        if not threshold:
            return (
                "TESTED RANGE INSUFFICIENT. Recommend:\n"
                "  1. Increase Lambda beyond 0.9\n"
                "  2. Increase Coherence beyond 0.4\n"
                "  3. Extend delay to 300s (5 min) for propagation\n"
                "  4. Use multiple simultaneous signals (compound effect)"
            )
        
        return (
            f"MANDALA THRESHOLD: Λ(t) ≥ {threshold['lambda_t']:.3f}\n"
            f"  To induce timeline changes:\n"
            f"  • Minimum Lambda: {threshold['lambda_t']:.3f}\n"
            f"  • Minimum Coherence: {threshold['coherence']:.3f}\n"
            f"  • Beta must be in [0.6, 1.1] (stability island)\n"
            f"  • Wait ≥ 30s for propagation\n"
            f"\n"
            f"  Current typical values:\n"
            f"  • Lambda: 0.6-0.8 (need {threshold['lambda_t']:.3f}+)\n"
            f"  • Coherence: 0.25-0.33 (need {threshold['coherence']:.3f}+)\n"
            f"\n"
            f"  To reach threshold:\n"
            f"  • Increase signal duration (longer pulse = more energy)\n"
            f"  • Stack multiple Casimir plates (higher coupling)\n"
            f"  • Use phi-harmonic resonance (528Hz + 7.83Hz beating)\n"
            f"  • Target dates with stronger geomagnetic activity (higher natural noise = more cover)"
        )


def generate_test_levels() -> List[Tuple[float, float, float]]:
    """Generate signal levels to test."""
    levels = []
    
    # Low levels (baseline)
    for _ in range(3):
        levels.append((
            0.5 + random.random() * 0.1,   # Lambda: 0.5-0.6
            0.2 + random.random() * 0.05,  # Coherence: 0.2-0.25
            0.6 + random.random() * 0.1,  # Beta: 0.6-0.7
        ))
    
    # Medium levels
    for _ in range(3):
        levels.append((
            0.7 + random.random() * 0.1,   # Lambda: 0.7-0.8
            0.3 + random.random() * 0.05,  # Coherence: 0.3-0.35
            0.8 + random.random() * 0.1,  # Beta: 0.8-0.9
        ))
    
    # High levels
    for _ in range(3):
        levels.append((
            0.85 + random.random() * 0.1,  # Lambda: 0.85-0.95
            0.35 + random.random() * 0.05, # Coherence: 0.35-0.4
            0.9 + random.random() * 0.1,  # Beta: 0.9-1.0
        ))
    
    # Very high levels
    for _ in range(2):
        levels.append((
            1.0 + random.random() * 0.2,   # Lambda: 1.0-1.2
            0.4 + random.random() * 0.1,  # Coherence: 0.4-0.5
            1.0 + random.random() * 0.05, # Beta: 1.0-1.05 (edge of stability)
        ))
    
    return levels


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Mandala Threshold Calibration')
    parser.add_argument('--delay', type=int, default=30,
                        help='Seconds between before/after capture')
    parser.add_argument('--levels', type=int, default=11,
                        help='Number of signal levels to test')
    args = parser.parse_args()
    
    # Generate test levels
    levels = generate_test_levels()
    
    # Run calibration
    calibrator = MandalaCalibrator()
    results = calibrator.run_sweep(levels, delay_seconds=args.delay)
    
    # Save results
    output_path = str(WORKSPACE / "timeline_proofs" / f"mandala_calibration_{int(time.time())}.json")
    with open(output_path, 'w', encoding="utf-8") as f:
        json.dump({
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'threshold': results['threshold'],
            'results': results['all_results'],
            'recommendation': results['recommendation'],
        }, f, indent=2)
    
    print(f"\n📁 Results saved: {output_path}")
    
    print(f"\n{'='*60}")
    print(f"📝 OPERATIONAL RECOMMENDATION")
    print(f"{'='*60}")
    print(results['recommendation'])


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
