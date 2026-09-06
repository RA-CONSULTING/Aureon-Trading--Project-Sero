#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════════════╗
║                                                                                       ║
║     🌀 HNC COMPOUND MANDALA PROTOCOL — Sustained Signal Induction                       ║
║                                                                                       ║
║     Instead of single pulse, uses N rapid pulses with extended settling time.         ║
║     This is how you overcome timeline inertia.                                         ║
║                                                                                       ║
╚══════════════════════════════════════════════════════════════════════════════════════╝
"""

import sys
import math
import random
import time
import json
from datetime import datetime, timezone

from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from aureon_fusion.paths import WORKSPACE

from hnc_mandala_effect import MandalaEffectEngine
from casimir_push_hnc import HNCCasimirPusher

PHI = (1 + math.sqrt(5)) / 2

class CompoundMandalaProtocol:
    """
    Compound signal protocol for Mandala induction.
    
    Strategy: 
    1. Capture BEFORE (sealed)
    2. Send M rapid pulses (compound signal)
    3. Wait extended settling time (T seconds)
    4. Capture AFTER
    5. Diff and score
    
    This overcomes timeline inertia through sustained energy injection.
    """
    
    def __init__(self):
        self.engine = MandalaEffectEngine()
    
    def compound_push(self, num_pulses: int = 3, settling_seconds: int = 300) -> dict:
        """
        Run compound Mandala protocol.
        
        Args:
            num_pulses: Number of rapid Casimir pulses to stack
            settling_seconds: Time to wait for timeline to settle
        """
        print(f"╔════════════════════════════════════════════════════════════════════╗")
        print(f"║     🌀 COMPOUND MANDALA PROTOCOL — Sustained Induction               ║")
        print(f"╚════════════════════════════════════════════════════════════════════╝")
        print(f"\n   Pulses: {num_pulses}")
        print(f"   Settling: {settling_seconds}s ({settling_seconds/60:.1f} min)")
        print(f"{'='*60}")
        
        # Step 1: BEFORE CAPTURE (sealed)
        print(f"\n📸 Step 1: BEFORE Capture (sealed)")
        print(f"{'─'*60}")
        before_news = self.engine.news_capturer.capture(max_headlines=5)
        before_hash = before_news[0].hash if before_news else "N/A"
        print(f"   Sealed. Hash: {before_hash}")
        print(f"   ⏰ {datetime.now(timezone.utc).isoformat()}")
        
        # Step 2: COMPOUND SIGNAL (N rapid pulses)
        print(f"\n⚡ Step 2: COMPOUND SIGNAL — {num_pulses} rapid pulses")
        print(f"{'─'*60}")
        
        total_energy = 0
        for i in range(num_pulses):
            print(f"   Pulse {i+1}/{num_pulses}...")
            try:
                pusher = HNCCasimirPusher(mode='pulse', queen_override=True)
                result = pusher.run()
                if result['success']:
                    energy = result.get('energy', 0)
                    total_energy += energy
                    print(f"      ✅ Energy: {energy:.1f}")
                else:
                    print(f"      ⚠️ Failed")
            except Exception as e:
                print(f"      ⚠️ Error: {e}")
            
            # Brief pause between pulses
            if i < num_pulses - 1:
                time.sleep(2)
        
        print(f"   Total Energy Injected: {total_energy:.1f}")
        
        # Step 3: EXTENDED SETTLING
        print(f"\n⏳ Step 3: Timeline Settling ({settling_seconds}s)")
        print(f"{'─'*60}")
        
        # Countdown with progress
        for remaining in range(settling_seconds, 0, -30):
            mins = remaining // 60
            secs = remaining % 60
            print(f"   ⏳ {mins:02d}:{secs:02d} remaining...", end='\r')
            time.sleep(min(30, remaining))
        print(f"   ✅ Settling complete{' '*30}")
        
        # Step 4: AFTER CAPTURE
        print(f"\n📸 Step 4: AFTER Capture")
        print(f"{'─'*60}")
        after_news = self.engine.news_capturer.capture(max_headlines=5)
        after_hash = after_news[0].hash if after_news else "N/A"
        print(f"   Hash: {after_hash}")
        print(f"   ⏰ {datetime.now(timezone.utc).isoformat()}")
        
        # Step 5: DIFF
        print(f"\n🔍 Step 5: Diff Engine")
        print(f"{'─'*60}")
        
        all_diffs = []
        for before in before_news:
            after = next((a for a in after_news if a.source == before.source), None)
            if after:
                diffs = self.engine.diff_engine.compare(before, after)
                all_diffs.extend(diffs)
                
                print(f"   📰 {before.source}:")
                for d in diffs[:3]:
                    status = "🔄" if d.similarity < 0.9 else "✅"
                    print(f"      {status} Sim={d.similarity:.0%} | Mandala={d.mandala_score:.2f}")
                    if d.similarity < 0.9:
                        print(f"         - {d.before_headline[:50]}")
                        print(f"         + {d.after_headline[:50]}")
        
        mandala_score = self.engine.diff_engine.calculate_overall_mandala(all_diffs)
        
        # Verdict
        if mandala_score > 0.5:
            verdict = "MANDALA EFFECT DETECTED"
        elif mandala_score > 0.2:
            verdict = "MANDALA EFFECT POSSIBLE"
        elif mandala_score > 0.05:
            verdict = "MARGINAL EFFECT"
        else:
            verdict = "NO EFFECT"
        
        print(f"\n   📊 Mandala Score: {mandala_score:.2%}")
        print(f"   🎯 Verdict: {verdict}")
        
        # Save report
        report = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'protocol': 'compound',
            'num_pulses': num_pulses,
            'total_energy': total_energy,
            'settling_seconds': settling_seconds,
            'before_hash': before_hash,
            'after_hash': after_hash,
            'mandala_score': mandala_score,
            'verdict': verdict,
        }
        
        report_path = str(WORKSPACE / "timeline_proofs" / f"compound_mandala_{int(time.time())}.json")
        with open(report_path, 'w', encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        
        print(f"\n📁 Report: {report_path}")
        
        print(f"\n{'='*60}")
        print(f"✅ COMPOUND MANDALA PROTOCOL COMPLETE")
        print(f"{'='*60}")
        
        return report


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Compound Mandala Protocol')
    parser.add_argument('--pulses', type=int, default=3, help='Number of pulses')
    parser.add_argument('--settling', type=int, default=300, help='Settling time in seconds')
    args = parser.parse_args()
    
    protocol = CompoundMandalaProtocol()
    result = protocol.compound_push(
        num_pulses=args.pulses,
        settling_seconds=args.settling
    )
    
    print(f"\n--- SUMMARY ---")
    print(f"Pulses: {result['num_pulses']}")
    print(f"Energy: {result['total_energy']:.1f}")
    print(f"Settling: {result['settling_seconds']}s")
    print(f"Mandala Score: {result['mandala_score']:.2%}")
    print(f"Verdict: {result['verdict']}")


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
