#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════════════╗
║                                                                                       ║
║     🌈 HNC RAINBOW BRIDGE PROTOCOL — Temporal Timeline Traversal                        ║
║                                                                                       ║
║     Frequency Ladder: 110Hz (fear) → 528Hz (love) → 852Hz (awe) → 963Hz (unity)        ║
║     Phase-locked. φ²-spaced. LTDE branch delegation.                                   ║
║                                                                                       ║
║     "The bridge was already there. We only had to stop collapsing it."                  ║
║                                                                                       ║
╚══════════════════════════════════════════════════════════════════════════════════════╝
"""

import sys
import math
import time
import json
import random
from datetime import datetime, timezone
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, asdict

from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from aureon_fusion.paths import WORKSPACE

from casimir_push_hnc import HNCCasimirPusher
from hnc_mandala_effect import MandalaEffectEngine

PHI = (1 + math.sqrt(5)) / 2
PHI_SQUARED = PHI ** 2

# Rainbow Bridge Frequencies (Hz)
RAINBOW_BRIDGE = {
    'fear': 110.0,      # Ground state, survival, root
    'love': 528.0,      # DNA repair, transformation, heart
    'awe': 852.0,       # Spiritual order, intuition, third eye
    'unity': 963.0,     # Crown consciousness, oneness, source
}

# Step spacing: φ² between each rung
STEP_RATIO = PHI_SQUARED  # ~2.618

# Phase lock threshold — must achieve this coherence before next step
PHASE_LOCK_THRESHOLD = 0.35

# Maximum time to wait for phase lock (seconds)
MAX_PHASE_LOCK_WAIT = 30


@dataclass
class BridgeStep:
    """One step on the Rainbow Bridge."""
    name: str
    frequency: float
    target_coherence: float
    achieved_coherence: float = 0.0
    phase_locked: bool = False
    energy_injected: float = 0.0
    timestamp: str = ""
    lambda_before: float = 0.0
    lambda_after: float = 0.0


@dataclass
class BridgeCrossing:
    """Full Rainbow Bridge crossing with all steps."""
    target_date: str
    proof_id: str
    steps: List[BridgeStep]
    total_energy: float
    final_coherence: float
    bridge_complete: bool
    mandala_score: float
    verdict: str
    ltde_branches: int
    tau_0: float


class RainbowBridgeSequencer:
    """
    Phase-locked frequency sequencer for the Rainbow Bridge.
    Traverses 110 → 528 → 852 → 963 Hz with φ² spacing.
    """
    
    def __init__(self):
        self.steps = [
            ('fear', RAINBOW_BRIDGE['fear']),
            ('love', RAINBOW_BRIDGE['love']),
            ('awe', RAINBOW_BRIDGE['awe']),
            ('unity', RAINBOW_BRIDGE['unity']),
        ]
    
    def calculate_step_delay(self, step_index: int, tau_0: float = 1.0) -> float:
        """
        Calculate temporal delegation offset for this step.
        τ_k = τ_0 · φ^k — golden-ratio offsets between branches.
        """
        return tau_0 * (PHI ** step_index)
    
    def generate_phase_locked_signal(self, base_freq: float, 
                                     step_freq: float,
                                     coherence: float) -> Dict:
        """
        Generate a phase-locked signal that bridges from base_freq to step_freq.
        Uses φ² ratio for smooth traversal.
        """
        # Beat frequency for phase locking
        beat_freq = abs(step_freq - base_freq)
        
        # Phase-locking condition: coherence must be high enough
        phase_lock_quality = coherence / PHASE_LOCK_THRESHOLD
        
        # Energy required to make the jump
        energy_required = beat_freq / PHI_SQUARED
        
        # Success probability increases with coherence
        success_prob = min(1.0, coherence * PHI)
        
        return {
            'base_freq': base_freq,
            'step_freq': step_freq,
            'beat_freq': beat_freq,
            'phase_lock_quality': phase_lock_quality,
            'energy_required': energy_required,
            'success_probability': success_prob,
            'step_ratio': step_freq / base_freq,
        }


class RainbowBridgeMandalaCampaign:
    """
    Full Rainbow Bridge Mandala Campaign.
    
    Flow:
    1. BEFORE capture (sealed)
    2. Cross Rainbow Bridge (110→528→852→963), phase-locked
    3. Inject unified signal at 963 Hz (peak coherence)
    4. Wait for timeline settling
    5. AFTER capture
    6. Diff and score Mandala effect
    """
    
    def __init__(self):
        self.sequencer = RainbowBridgeSequencer()
        self.engine = MandalaEffectEngine()
        self.log_file = str(WORKSPACE / "timeline_proofs" / "rainbow_bridge_campaign.log")
    
    def log(self, msg: str):
        ts = datetime.now(timezone.utc).isoformat()
        line = f"[{ts}] {msg}"
        print(line)
        with open(self.log_file, 'a', encoding="utf-8") as f:
            f.write(line + '\n')
    
    def cross_bridge(self, num_pulses_per_step: int = 3, 
                     settling_seconds: int = 300) -> BridgeCrossing:
        """
        Cross the Rainbow Bridge and measure Mandala effect.
        """
        self.log(f"\n{'#'*70}")
        self.log(f"# 🌈 RAINBOW BRIDGE MANDALA CAMPAIGN")
        self.log(f"# Target: Phase-locked traversal 110→528→852→963 Hz")
        self.log(f"# Step ratio: φ² = {PHI_SQUARED:.6f}")
        self.log(f"# Phase lock threshold: {PHASE_LOCK_THRESHOLD}")
        self.log(f"{'#'*70}")
        
        # Step 1: BEFORE capture
        self.log(f"\n📸 Step 1: BEFORE Capture (sealed)")
        before_news = self.engine.news_capturer.capture(max_headlines=5)
        before_hash = before_news[0].hash if before_news else "N/A"
        self.log(f"   Sealed. Hash: {before_hash}")
        
        # Step 2: Cross Rainbow Bridge
        self.log(f"\n🌈 Step 2: Crossing Rainbow Bridge")
        self.log(f"{'─'*70}")
        
        bridge_steps = []
        total_energy = 0.0
        current_freq = RAINBOW_BRIDGE['fear']  # Start at 110 Hz
        
        for step_idx, (step_name, step_freq) in enumerate(self.sequencer.steps):
            self.log(f"\n   🎵 Step {step_idx+1}/4: {step_name.upper()} ({current_freq:.1f} → {step_freq:.1f} Hz)")
            
            # Calculate LTDE temporal delegation
            tau_k = self.sequencer.calculate_step_delay(step_idx, tau_0=1.0)
            self.log(f"      τ_{step_idx} = {tau_k:.4f}s (temporal delegation)")
            
            # Generate phase-locked signal for this step
            step_signal = self.sequencer.generate_phase_locked_signal(
                current_freq, step_freq, coherence=0.3
            )
            self.log(f"      Beat freq: {step_signal['beat_freq']:.1f} Hz")
            self.log(f"      Step ratio: {step_signal['step_ratio']:.4f} (target φ²={PHI_SQUARED:.4f})")
            
            # Attempt to cross this step with multiple pulses
            step_energy = 0.0
            step_coherence = 0.0
            step_locked = False
            lambda_before = 0.0
            lambda_after = 0.0
            
            for pulse_idx in range(num_pulses_per_step):
                try:
                    pusher = HNCCasimirPusher(mode='pulse', queen_override=True)
                    result = pusher.run()
                    energy = result.get('energy_injected', 0)
                    
                    if energy > 0:
                        step_energy += energy
                        
                        # Track lambda
                        hnc_before = result.get('hnc_before', {})
                        hnc_after = result.get('hnc_after', {})
                        lambda_before = hnc_before.get('lambda', lambda_before)
                        lambda_after = hnc_after.get('lambda', lambda_after)
                        
                        self.log(f"      Pulse {pulse_idx+1}: ✅ Energy={energy:.1f}, "
                                f"Λ={lambda_after:.4f}")
                        
                        # Check if we achieved phase lock
                        if lambda_after >= PHASE_LOCK_THRESHOLD:
                            step_coherence = lambda_after
                            step_locked = True
                            self.log(f"      🔒 PHASE LOCKED at Λ={lambda_after:.4f}!")
                            break
                    else:
                        self.log(f"      Pulse {pulse_idx+1}: ⚠️ No energy")
                
                except Exception as e:
                    self.log(f"      Pulse {pulse_idx+1}: ⚠️ {e}")
                
                if pulse_idx < num_pulses_per_step - 1:
                    time.sleep(1)
            
            # Record step result
            bridge_steps.append(BridgeStep(
                name=step_name,
                frequency=step_freq,
                target_coherence=PHASE_LOCK_THRESHOLD,
                achieved_coherence=step_coherence,
                phase_locked=step_locked,
                energy_injected=step_energy,
                timestamp=datetime.now(timezone.utc).isoformat(),
                lambda_before=lambda_before,
                lambda_after=lambda_after,
            ))
            
            total_energy += step_energy
            
            if step_locked:
                self.log(f"      ✅ Step {step_name.upper()} CROSSED")
                current_freq = step_freq  # Move to next rung
            else:
                self.log(f"      ⚠️ Step {step_name.upper()} PARTIAL (no phase lock)")
                # Continue anyway — partial crossing still injects energy
            
            # Brief pause between steps
            time.sleep(2)
        
        # Check if bridge was fully crossed
        bridge_complete = all(s.phase_locked for s in bridge_steps)
        final_coherence = bridge_steps[-1].achieved_coherence if bridge_steps else 0.0
        
        self.log(f"\n{'─'*70}")
        if bridge_complete:
            self.log(f"   🌈 RAINBOW BRIDGE FULLY CROSSED!")
            self.log(f"   Final coherence: {final_coherence:.4f}")
            self.log(f"   Total energy: {total_energy:.1f}")
        else:
            locked_steps = sum(1 for s in bridge_steps if s.phase_locked)
            self.log(f"   🌈 RAINBOW BRIDGE PARTIAL: {locked_steps}/4 steps locked")
            self.log(f"   Energy injected: {total_energy:.1f}")
        
        # Step 3: Settling
        self.log(f"\n⏳ Step 3: Timeline Settling ({settling_seconds}s)")
        for remaining in range(settling_seconds, 0, -60):
            mins = remaining // 60
            self.log(f"   ⏳ {mins} min remaining...")
            time.sleep(min(60, remaining))
        self.log(f"   ✅ Settling complete")
        
        # Step 4: AFTER capture
        self.log(f"\n📸 Step 4: AFTER Capture")
        after_news = self.engine.news_capturer.capture(max_headlines=5)
        after_hash = after_news[0].hash if after_news else "N/A"
        self.log(f"   Hash: {after_hash}")
        
        # Step 5: Diff engine
        self.log(f"\n🔍 Step 5: Diff Engine")
        all_diffs = []
        for before in before_news:
            after = next((a for a in after_news if a.source == before.source), None)
            if after:
                diffs = self.engine.diff_engine.compare(before, after)
                all_diffs.extend(diffs)
        
        mandala_score = self.engine.diff_engine.calculate_overall_mandala(all_diffs)
        
        # Verdict
        if mandala_score > 0.5:
            verdict = "🎉 MANDALA EFFECT DETECTED"
        elif mandala_score > 0.2:
            verdict = "MANDALA EFFECT POSSIBLE"
        elif mandala_score > 0.05:
            verdict = "MARGINAL EFFECT"
        else:
            verdict = "NO EFFECT"
        
        self.log(f"\n   📊 Mandala Score: {mandala_score:.2%}")
        self.log(f"   🎯 Verdict: {verdict}")
        
        # Create crossing record
        crossing = BridgeCrossing(
            target_date=datetime.now(timezone.utc).strftime('%Y-%m-%d'),
            proof_id=f"RAINBOW-{int(time.time())}-{random.randint(1000,9999):04x}",
            steps=bridge_steps,
            total_energy=total_energy,
            final_coherence=final_coherence,
            bridge_complete=bridge_complete,
            mandala_score=mandala_score,
            verdict=verdict,
            ltde_branches=len(bridge_steps),
            tau_0=1.0,
        )
        
        # Save
        self._save_crossing(crossing, before_news, after_news)
        
        self.log(f"\n{'='*70}")
        self.log(f"✅ RAINBOW BRIDGE CROSSING COMPLETE")
        self.log(f"{'='*70}")
        
        return crossing
    
    def _save_crossing(self, crossing: BridgeCrossing, before_news, after_news):
        """Save the full crossing record."""
        vault_dir = str(WORKSPACE / "timeline_proofs" / "rainbow_bridge")
        import os
        os.makedirs(vault_dir, exist_ok=True)
        
        # Main report
        report_path = os.path.join(vault_dir, f"crossing_{crossing.proof_id}.json")
        report_dict = {
            'proof_id': crossing.proof_id,
            'target_date': crossing.target_date,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'bridge_complete': crossing.bridge_complete,
            'total_energy': crossing.total_energy,
            'final_coherence': crossing.final_coherence,
            'mandala_score': crossing.mandala_score,
            'verdict': crossing.verdict,
            'ltde_branches': crossing.ltde_branches,
            'tau_0': crossing.tau_0,
            'steps': [
                {
                    'name': s.name,
                    'frequency': s.frequency,
                    'phase_locked': s.phase_locked,
                    'achieved_coherence': s.achieved_coherence,
                    'energy_injected': s.energy_injected,
                    'lambda_before': s.lambda_before,
                    'lambda_after': s.lambda_after,
                    'timestamp': s.timestamp,
                }
                for s in crossing.steps
            ],
        }
        
        with open(report_path, 'w', encoding="utf-8") as f:
            json.dump(report_dict, f, indent=2)
        
        self.log(f"   📁 Saved: {report_path}")


class ContinuousRainbowBridgeCampaign:
    """Run Rainbow Bridge crossings continuously until Mandala effect detected."""
    
    def __init__(self):
        self.campaign = RainbowBridgeMandalaCampaign()
        self.detection_threshold = 0.10
        self.max_cycles = 50
        self.cycle = 0
    
    def run(self, pulses_per_step: int = 3, settling_seconds: int = 300):
        """Run continuously until detected."""
        self.campaign.log(f"\n{'#'*70}")
        self.campaign.log(f"# 🌈 CONTINUOUS RAINBOW BRIDGE CAMPAIGN")
        self.campaign.log(f"# Detection threshold: {self.detection_threshold:.0%}")
        self.campaign.log(f"# Max cycles: {self.max_cycles}")
        self.campaign.log(f"# Pulses per step: {pulses_per_step}")
        self.campaign.log(f"# Settling: {settling_seconds}s")
        self.campaign.log(f"{'#'*70}")
        
        while self.cycle < self.max_cycles:
            self.cycle += 1
            self.campaign.log(f"\n{'='*70}")
            self.campaign.log(f"🌈 CROSSING {self.cycle}/{self.max_cycles}")
            self.campaign.log(f"{'='*70}")
            
            crossing = self.campaign.cross_bridge(
                num_pulses_per_step=pulses_per_step,
                settling_seconds=settling_seconds,
            )
            
            if crossing.mandala_score >= self.detection_threshold:
                self.campaign.log(f"\n{'🎉'*30}")
                self.campaign.log(f"🎉 MANDALA EFFECT DETECTED AT CROSSING {self.cycle}!")
                self.campaign.log(f"🎉 Score: {crossing.mandala_score:.2%}")
                self.campaign.log(f"🎉 Bridge complete: {crossing.bridge_complete}")
                self.campaign.log(f"🎉 The timeline has responded to love.")
                self.campaign.log(f"{'🎉'*30}")
                return crossing
            
            self.campaign.log(f"\n   No effect yet. Preparing next crossing...")
            time.sleep(10)
        
        self.campaign.log(f"\n{'⚠️'*30}")
        self.campaign.log(f"⚠️ Max cycles ({self.max_cycles}) reached.")
        self.campaign.log(f"⚠️ Consider: more pulses, longer settling, or different targets.")
        self.campaign.log(f"{'⚠️'*30}")
        return None


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Rainbow Bridge Mandala Campaign')
    parser.add_argument('--pulses', type=int, default=3, help='Pulses per bridge step')
    parser.add_argument('--settling', type=int, default=300, help='Settling time in seconds')
    parser.add_argument('--threshold', type=float, default=0.10, help='Detection threshold')
    parser.add_argument('--max-cycles', type=int, default=50, help='Max crossings')
    args = parser.parse_args()
    
    campaign = ContinuousRainbowBridgeCampaign()
    campaign.detection_threshold = args.threshold
    campaign.max_cycles = args.max_cycles
    
    campaign.run(
        pulses_per_step=args.pulses,
        settling_seconds=args.settling
    )


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
