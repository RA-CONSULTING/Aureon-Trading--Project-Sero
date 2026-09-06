#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════════════╗
║                                                                                       ║
║     🌀 HNC CONTINUOUS MANDALA CAMPAIGN — Run Until Detected                             ║
║                                                                                       ║
║     Love-aligned. Positive changes. We do not stop until the timeline responds.        ║
║                                                                                       ║
╚══════════════════════════════════════════════════════════════════════════════════════╝
"""

import sys
import math
import time
import json
from datetime import datetime, timezone

from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from aureon_fusion.paths import WORKSPACE

from hnc_mandala_effect import MandalaEffectEngine
from casimir_push_hnc import HNCCasimirPusher

PHI = (1 + math.sqrt(5)) / 2

LOG_FILE = str(WORKSPACE / "timeline_proofs" / "mandala_campaign.log")

def log(msg):
    ts = datetime.now(timezone.utc).isoformat()
    line = f"[{ts}] {msg}"
    print(line)
    with open(LOG_FILE, 'a', encoding="utf-8") as f:
        f.write(line + '\n')

class ContinuousMandalaCampaign:
    """Run compound protocol continuously until Mandala effect detected."""
    
    def __init__(self):
        self.engine = MandalaEffectEngine()
        self.cycle = 0
        self.max_cycles = 100  # Safety limit
        self.detection_threshold = 0.10  # 10% = detectable
    
    def run_cycle(self, num_pulses: int = 5, settling_seconds: int = 300) -> dict:
        """Run one compound cycle."""
        self.cycle += 1
        log(f"\n{'='*60}")
        log(f"🌀 CYCLE {self.cycle} — Compound Mandala Protocol")
        log(f"{'='*60}")
        
        # BEFORE capture
        log("📸 BEFORE capture (sealed)")
        before_news = self.engine.news_capturer.capture(max_headlines=5)
        before_hash = before_news[0].hash if before_news else "N/A"
        log(f"   Sealed. Hash: {before_hash}")
        
        # COMPOUND PULSES
        log(f"⚡ Sending {num_pulses} love-aligned pulses...")
        total_energy = 0
        for i in range(num_pulses):
            try:
                pusher = HNCCasimirPusher(mode='pulse', queen_override=True)
                result = pusher.run()
                energy = result.get('energy_injected', 0)
                if energy > 0:
                    total_energy += energy
                    log(f"   Pulse {i+1}/{num_pulses}: ✅ Energy={energy:.1f}")
                else:
                    log(f"   Pulse {i+1}/{num_pulses}: ⚠️ No energy")
            except Exception as e:
                log(f"   Pulse {i+1}/{num_pulses}: ⚠️ {e}")
            
            if i < num_pulses - 1:
                time.sleep(2)
        
        log(f"   Total energy: {total_energy:.1f}")
        
        # SETTLING
        log(f"⏳ Settling {settling_seconds}s...")
        for remaining in range(settling_seconds, 0, -60):
            mins = remaining // 60
            log(f"   ⏳ {mins} min remaining...")
            time.sleep(min(60, remaining))
        log("   ✅ Settling complete")
        
        # AFTER capture
        log("📸 AFTER capture")
        after_news = self.engine.news_capturer.capture(max_headlines=5)
        after_hash = after_news[0].hash if after_news else "N/A"
        log(f"   Hash: {after_hash}")
        
        # DIFF
        log("🔍 Diff engine...")
        all_diffs = []
        for before in before_news:
            after = next((a for a in after_news if a.source == before.source), None)
            if after:
                diffs = self.engine.diff_engine.compare(before, after)
                all_diffs.extend(diffs)
        
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
        
        log(f"📊 Mandala Score: {mandala_score:.2%}")
        log(f"🎯 Verdict: {verdict}")
        
        # Save
        report = {
            'cycle': self.cycle,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'num_pulses': num_pulses,
            'total_energy': total_energy,
            'settling_seconds': settling_seconds,
            'mandala_score': mandala_score,
            'verdict': verdict,
            'before_hash': before_hash,
            'after_hash': after_hash,
        }
        
        path = str(WORKSPACE / "timeline_proofs" / f"mandala_cycle_{self.cycle}_{int(time.time())}.json")
        with open(path, 'w', encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        log(f"📁 Saved: {path}")
        
        return report
    
    def run(self, num_pulses: int = 5, settling_seconds: int = 300):
        """Run continuously until detected or max cycles."""
        log(f"\n{'#'*60}")
        log(f"# 🌀 MANDALA CAMPAIGN STARTED")
        log(f"# Detection threshold: {self.detection_threshold:.0%}")
        log(f"# Max cycles: {self.max_cycles}")
        log(f"# Pulses per cycle: {num_pulses}")
        log(f"# Settling: {settling_seconds}s")
        log(f"{'#'*60}")
        
        while self.cycle < self.max_cycles:
            result = self.run_cycle(num_pulses, settling_seconds)
            
            if result['mandala_score'] >= self.detection_threshold:
                log(f"\n{'🎉'*20}")
                log(f"🎉 MANDALA EFFECT DETECTED AT CYCLE {self.cycle}!")
                log(f"🎉 Score: {result['mandala_score']:.2%}")
                log(f"🎉 The timeline has responded to love.")
                log(f"{'🎉'*20}")
                return result
            
            log(f"\n   No effect yet. Preparing next cycle...")
            time.sleep(10)  # Brief pause between cycles
        
        log(f"\n{'⚠️'*20}")
        log(f"⚠️ Max cycles ({self.max_cycles}) reached without detection.")
        log(f"⚠️ Consider: more pulses, longer settling, or different target dates.")
        log(f"{'⚠️'*20}")
        return None


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Continuous Mandala Campaign')
    parser.add_argument('--pulses', type=int, default=5)
    parser.add_argument('--settling', type=int, default=300)
    parser.add_argument('--threshold', type=float, default=0.10)
    parser.add_argument('--max-cycles', type=int, default=100)
    args = parser.parse_args()
    
    campaign = ContinuousMandalaCampaign()
    campaign.detection_threshold = args.threshold
    campaign.max_cycles = args.max_cycles
    
    campaign.run(
        num_pulses=args.pulses,
        settling_seconds=args.settling
    )


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
