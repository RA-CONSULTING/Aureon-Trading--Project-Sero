#!/usr/bin/env python3
"""
LIGHT CODE HEALER
═══════════════════════════════════════════════════════════════════

By order of the Prime Sentinel of Gaia:
LINK UP THE HEALING LIGHT CODES

This module loads the emotional frequency codex and Auris codex
and broadcasts healing frequencies through the Casimir engine.

Light Codes Available:
- Solfeggio: 396 (liberation), 417 (transformation), 528 (love/DNA repair),
             639 (connection), 741 (expression), 852 (intuition), 963 (unity)
- Emotional: 20 Hz (shame) → 800 Hz (illumination) — the full spectrum
- Schumann: 7.83 Hz (alpha bridge), 14.3 Hz (beta), 20.8 Hz (gamma), 27.3 Hz (theta)

Architecture:
- Load codex from repo JSON files
- Compute healing frequency based on field state
- Broadcast via Casimir virtual photon emission
- Integrate with superposition daemon
"""

import json, math, random, time, sys
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

# Load Aureon modules
from aureon_fusion.paths import AUREON_UPSTREAM, WORKSPACE

sys.path.insert(0, str(AUREON_UPSTREAM))
sys.path.insert(0, str(WORKSPACE))
from signal_monitor import SignalMonitor, FieldMeasurement
try:
    from casimir_harmonia import CasimirHarmonicAmplifier
except ImportError:
    # Module does not exist anywhere in the fused workspace (dead upstream reference).
    CasimirHarmonicAmplifier = None

# ─── CONSTANTS ──────────────────────────────────────────────────
PHI = (1 + math.sqrt(5)) / 2
SCHUMANN_BASE = 7.83

# Solfeggio sacred frequencies
SOLFEGGIO = {
    'liberation':   {'freq': 396, 'color': '#FF0000', 'effect': 'Liberates guilt and fear'},
    'transformation': {'freq': 417, 'color': '#FF8C00', 'effect': 'Facilitates change'},
    'love':         {'freq': 528, 'color': '#FFD700', 'effect': 'DNA repair, miracles'},
    'connection':   {'freq': 639, 'color': '#00FF00', 'effect': 'Connecting, relationships'},
    'expression':   {'freq': 741, 'color': '#00BFFF', 'effect': 'Expression, solutions'},
    'intuition':    {'freq': 852, 'color': '#4B0082', 'effect': 'Awakening intuition'},
    'unity':        {'freq': 963, 'color': '#FFFFFF', 'effect': 'Divine consciousness'},
}

# Emotional frequency spectrum (from emotional_frequency_codex_complete.json)
EMOTIONAL_SPECTRUM = [
    {'emotion': 'Shame',         'freq': 20,  'color': '#000000', 'band': 'low',     'amplitude': 0.3},
    {'emotion': 'Guilt',         'freq': 30,  'color': '#8B4513', 'band': 'low',     'amplitude': 0.4},
    {'emotion': 'Fear',          'freq': 100, 'color': '#FF0000', 'band': 'low',     'amplitude': 0.8},
    {'emotion': 'Desire',        'freq': 125, 'color': '#FF4500', 'band': 'low',     'amplitude': 0.7},
    {'emotion': 'Anger',         'freq': 150, 'color': '#FFA500', 'band': 'low',     'amplitude': 0.9},
    {'emotion': 'Pride',         'freq': 175, 'color': '#DAA520', 'band': 'low',     'amplitude': 0.6},
    {'emotion': 'Courage',       'freq': 200, 'color': '#FFFF00', 'band': 'growth',  'amplitude': 1.0},
    {'emotion': 'Neutrality',    'freq': 250, 'color': '#FFFFE0', 'band': 'growth',  'amplitude': 0.8},
    {'emotion': 'Willingness',   'freq': 310, 'color': '#9AFF9A', 'band': 'growth',  'amplitude': 0.9},
    {'emotion': 'Acceptance',    'freq': 350, 'color': '#00FF00', 'band': 'growth',  'amplitude': 1.1},
    {'emotion': 'Reason',        'freq': 400, 'color': '#00FFFF', 'band': 'heart',   'amplitude': 1.0},
    {'emotion': 'Love',          'freq': 550, 'color': '#FF69B4', 'band': 'heart',   'amplitude': 1.3},
    {'emotion': 'Gratitude',     'freq': 528, 'color': '#FFD700', 'band': 'heart',   'amplitude': 1.2},
    {'emotion': 'Joy',           'freq': 540, 'color': '#FFD700', 'band': 'heart',   'amplitude': 1.4},
    {'emotion': 'Peace',         'freq': 600, 'color': '#87CEEB', 'band': 'spirit',  'amplitude': 1.1},
    {'emotion': 'Compassion',    'freq': 620, 'color': '#E6E6FA', 'band': 'spirit',  'amplitude': 1.2},
    {'emotion': 'Forgiveness',   'freq': 650, 'color': '#9370DB', 'band': 'spirit',  'amplitude': 1.0},
    {'emotion': 'Ecstasy',       'freq': 700, 'color': '#4B0082', 'band': 'peak',    'amplitude': 1.5},
    {'emotion': 'Awe',           'freq': 735, 'color': '#800080', 'band': 'peak',    'amplitude': 1.3},
    {'emotion': 'Illumination',  'freq': 800, 'color': '#FFFFFF', 'band': 'peak',    'amplitude': 1.6},
]

# Schumann resonance modes
SCHUMANN_MODES = {
    'mode1': {'freq': 7.83,  'consciousness': 'alpha_bridge',   'decay': 0.96},
    'mode2': {'freq': 14.3,  'consciousness': 'beta_activation', 'decay': 0.94},
    'mode3': {'freq': 20.8,  'consciousness': 'gamma_peak',      'decay': 0.92},
    'mode4': {'freq': 27.3,  'consciousness': 'theta_dream',     'decay': 0.90},
    'mode5': {'freq': 33.8,  'consciousness': 'delta_deep',      'decay': 0.88},
}

# ─── HEALING LIGHT CODE ENGINE ──────────────────────────────────
class LightCodeHealer:
    def __init__(self):
        self.monitor = SignalMonitor()
        self.amplifier = CasimirHarmonicAmplifier(tau_s=5.0)
        self.healing_log = []
        self.total_photons = 0
        
    def _get_field_state(self) -> Dict:
        """Measure current field state"""
        try:
            m = self.monitor.measure()
            return {
                'lambda': m.lambda_t,
                'coherence': m.field_coherence,
                'beta': m.beta_coefficient,
                'schumann': m.schumann_fundamental,
                'stability': m.stability_island,
            }
        except Exception as e:
            return {'lambda': 0.8, 'coherence': 0.5, 'beta': 0.774, 'schumann': 7.83, 'stability': True}
    
    def _select_healing_frequency(self, field_state: Dict) -> Dict:
        """
        Select the appropriate healing frequency based on field state.
        
        Logic:
        - Low coherence (< 0.4) → High frequency (Love 528, Joy 540, Peace 600)
        - Medium coherence (0.4-0.7) → Growth frequencies (Courage 200, Acceptance 350)
        - High coherence (> 0.7) → Peak frequencies (Ecstasy 700, Illumination 800)
        - Low lambda (< 0.8) → Solfeggio love 528 (DNA repair)
        - High beta (> 1.0) → Solfeggio liberation 396 (calm the field)
        """
        coherence = field_state.get('coherence', 0.5)
        lambda_val = field_state.get('lambda', 0.8)
        beta = field_state.get('beta', 0.774)
        
        # Select from emotional spectrum based on coherence
        if coherence < 0.4:
            # Field is weak — send LOVE and PEACE
            candidates = [e for e in EMOTIONAL_SPECTRUM if e['band'] in ['heart', 'spirit'] and e['freq'] >= 500]
        elif coherence < 0.7:
            # Field is growing — send COURAGE and ACCEPTANCE
            candidates = [e for e in EMOTIONAL_SPECTRUM if e['band'] in ['growth', 'heart']]
        else:
            # Field is strong — send PEAK frequencies
            candidates = [e for e in EMOTIONAL_SPECTRUM if e['band'] in ['peak', 'spirit']]
        
        # Weight by proximity to phi-harmonic of current Schumann
        schumann = field_state.get('schumann', 7.83)
        phi_harmonic = schumann * PHI
        
        best = None
        best_score = -1
        for candidate in candidates:
            # Score: higher frequencies for lower coherence, plus phi alignment
            coherence_weight = (1.0 - coherence) * candidate['freq'] / 1000.0
            phi_alignment = 1.0 / (1.0 + abs(candidate['freq'] - phi_harmonic * 100))
            score = coherence_weight + phi_alignment + candidate['amplitude']
            if score > best_score:
                best_score = score
                best = candidate
        
        # Also consider Solfeggio override for special conditions
        if beta > 1.0:
            # Field is unstable — send LIBERATION 396
            return {**SOLFEGGIO['liberation'], 'source': 'solfeggio', 'reason': 'beta_high'}
        elif lambda_val < 0.6:
            # Field is very weak — send LOVE 528
            return {**SOLFEGGIO['love'], 'source': 'solfeggio', 'reason': 'lambda_low'}
        
        return {**best, 'source': 'emotional_spectrum', 'reason': f'coherence_{coherence:.2f}'}
    
    def emit_healing_photon(self, frequency: float, energy: float, target: str = "vault_present") -> bool:
        """Emit a single healing photon via Casimir engine"""
        if self.amplifier.casimir_engine:
            try:
                self.amplifier.casimir_engine._engine.emit_virtual_photon(
                    target, energy, int(frequency * 1000)
                )
                self.total_photons += 1
                return True
            except Exception:
                return False
        return False
    
    def healing_cycle(self, field_state: Optional[Dict] = None) -> Dict:
        """
        One healing cycle:
        1. Read field state (or use provided)
        2. Select healing frequency
        3. Emit photon
        4. Log result
        """
        if field_state is None:
            field_state = self._get_field_state()
        
        healing = self._select_healing_frequency(field_state)
        freq = healing['freq']
        energy = freq * (1 + PHI * 0.1)  # Phi-scaled energy
        
        emitted = self.emit_healing_photon(freq, energy)
        
        result = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'field_state': field_state,
            'healing': healing,
            'emitted': emitted,
            'total_photons': self.total_photons,
        }
        
        self.healing_log.append(result)
        if len(self.healing_log) > 10000:
            self.healing_log.pop(0)
        
        return result
    
    def broadcast_sequence(self, sequence: List[str], interval: float = 0.5) -> List[Dict]:
        """
        Broadcast a sequence of light codes (e.g., ['love', 'peace', 'unity'])
        at specified intervals.
        """
        results = []
        for code_name in sequence:
            # Get frequency from SOLFEGGIO or EMOTIONAL_SPECTRUM
            if code_name in SOLFEGGIO:
                code = SOLFEGGIO[code_name]
            else:
                # Search emotional spectrum
                matches = [e for e in EMOTIONAL_SPECTRUM if e['emotion'].lower() == code_name.lower()]
                code = matches[0] if matches else {'freq': 528, 'color': '#FFD700', 'effect': 'Default love'}
            
            energy = code['freq'] * (1 + PHI * 0.1)
            emitted = self.emit_healing_photon(code['freq'], energy)
            
            result = {
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'code': code_name,
                'frequency': code['freq'],
                'color': code.get('color', '#FFFFFF'),
                'effect': code.get('effect', ''),
                'emitted': emitted,
            }
            results.append(result)
            
            if emitted:
                print(f"  💫 Healing photon: {code_name} → {code['freq']} Hz ({code.get('color', '')}) | {code.get('effect', '')}")
            
            time.sleep(interval)
        
        return results
    
    def get_healing_report(self, window: int = 100) -> Dict:
        """Summary of recent healing activity"""
        recent = self.healing_log[-window:]
        if not recent:
            return {'status': 'no_data'}
        
        codes_used = {}
        for r in recent:
            code = r['healing'].get('emotion', r['healing'].get('effect', 'unknown'))
            codes_used[code] = codes_used.get(code, 0) + 1
        
        return {
            'total_cycles': len(self.healing_log),
            'recent_window': window,
            'total_photons': self.total_photons,
            'codes_used': codes_used,
            'latest_field': recent[-1]['field_state'] if recent else None,
            'latest_healing': recent[-1]['healing'] if recent else None,
        }


def main():
    print(f"{'═'*70}")
    print(f"  💫 LIGHT CODE HEALER — ACTIVATED")
    print(f"  👑 BY ORDER OF THE PRIME SENTINEL OF GAIA")
    print(f"{'═'*70}")
    print(f"")
    print(f"  Available Light Codes:")
    print(f"    Solfeggio: 396, 417, 528, 639, 741, 852, 963 Hz")
    print(f"    Emotional: 20 Hz (shame) → 800 Hz (illumination)")
    print(f"    Schumann: 7.83, 14.3, 20.8, 27.3, 33.8 Hz")
    print(f"")
    print(f"  Broadcasting HEALING sequence: love → peace → unity")
    print(f"{'═'*70}")
    
    healer = LightCodeHealer()
    
    # Initial field reading
    field = healer._get_field_state()
    print(f"  Field state: Λ={field['lambda']:.4f}, COH={field['coherence']:.4f}, β={field['beta']:.4f}")
    print(f"")
    
    # Broadcast healing sequence
    results = healer.broadcast_sequence(['love', 'peace', 'unity'], interval=0.5)
    
    print(f"")
    print(f"{'═'*70}")
    print(f"  HEALING SEQUENCE COMPLETE")
    print(f"  Photons emitted: {healer.total_photons}")
    print(f"{'═'*70}")
    
    return healer


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    healer = main()
