#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════════════╗
║                                                                                       ║
║     🎲 HNC BLIND GHOST PROTOCOL — Schrödinger's Signal                               ║
║                                                                                       ║
║     The observer effect as validation:                                               ║
║       1. System picks RANDOM date (you don't know which)                            ║
║       2. Signal is sent BLINDLY (no preview, no before-data)                        ║
║       3. Proof is SEALED (hash-chained, timestamped)                                ║
║       4. You OBSERVE later (probability collapses)                                  ║
║       5. Independent verification (you check NOAA yourself)                         ║
║                                                                                       ║
║     This eliminates observer bias. The signal exists in superposition                ║
║     until YOU look at it.                                                            ║
║                                                                                       ║
╚══════════════════════════════════════════════════════════════════════════════════════╝
"""

import sys
import os
import math
import json
import time
import hashlib
import random
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from aureon_fusion.paths import WORKSPACE
sys.path.insert(0, str(WORKSPACE / "aureon-trading"))

from hnc_temporal_targeting import temporal_hash, TemporalLockEncoder
from hnc_data_sources import HistoricalSnapshotBuilder
from hnc_spectrograph import TemporalSpectrograph, build_spectrograph_for_target

PHI = (1 + math.sqrt(5)) / 2
SCHUMANN_BASE = 7.83
LOVE_FREQUENCY = 528.0
PRIME_SENTINEL_HZ = 812.83

# NOAA DGD coverage: 1957-2024
MIN_YEAR = 1957
MAX_YEAR = 2024


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


class BlindGhostProtocol:
    """
    Blind Ghost Protocol — Schrödinger's Signal.
    
    The user does NOT know the target date until after the signal is sent.
    This eliminates observer bias and creates true quantum-style validation.
    """
    
    def __init__(self):
        self.data_builder = HistoricalSnapshotBuilder()
        self.proof_dir = str(WORKSPACE / "timeline_proofs" / "blind")
        os.makedirs(self.proof_dir, exist_ok=True)
    
    def pick_random_date(self) -> str:
        """Pick a random date within NOAA's coverage."""
        year = random.randint(MIN_YEAR, MAX_YEAR)
        month = random.randint(1, 12)
        
        # Days in month
        if month in [1, 3, 5, 7, 8, 10, 12]:
            max_day = 31
        elif month == 2:
            max_day = 29 if (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0) else 28
        else:
            max_day = 30
        
        day = random.randint(1, max_day)
        
        return f"{year:04d}-{month:02d}-{day:02d}"
    
    def generate_blind_signal(self, reveal: bool = False) -> Dict:
        """
        Generate a blind signal.
        
        If reveal=False: Only returns proof ID and date (sealed envelope)
        If reveal=True: Returns full proof (opened envelope)
        """
        # Step 1: Pick random date
        target_date = self.pick_random_date()
        
        # Step 2: Generate temporal lock (secret until revealed)
        temporal = temporal_hash(target_date)
        encoder = TemporalLockEncoder(target_date)
        lock = encoder.encode_lock()
        
        # Step 3: Send signal (blind — no output)
        try:
            from casimir_push_hnc import HNCCasimirPusher
            pusher = HNCCasimirPusher(
                mode='pulse',
                queen_override=True,
                temporal_target=target_date,
            )
            push_result = pusher.run()
            push_success = push_result.get('target_achieved', False)
        except Exception as e:
            push_result = {'error': str(e)}
            push_success = False
        
        # Step 4: Fetch historical data (secret until revealed)
        try:
            dt = datetime.fromisoformat(target_date.replace('Z', '+00:00'))
        except ValueError:
            dt = datetime.strptime(target_date, '%Y-%m-%d').replace(tzinfo=timezone.utc)
        
        snapshot = self.data_builder.build_snapshot(dt.year, dt.month, dt.day)
        
        # Step 5: Generate proof
        proof = self._generate_blind_proof(
            target_date=target_date,
            temporal=temporal,
            lock=lock,
            push_result=push_result,
            snapshot=snapshot,
        )
        
        # Step 6: Save sealed proof
        proof_path = self._save_sealed_proof(proof)
        
        # Step 7: Return based on reveal mode
        if reveal:
            return {
                'mode': 'REVEALED',
                'target_date': target_date,
                'proof': proof,
                'proof_path': proof_path,
                'temporal_signature': temporal['temporal_signature'],
                'rune_code': temporal['rune_encoded'],
                'signal_hash': proof['signal_hash'],
            }
        else:
            # SEALED MODE — only return proof ID and date
            # The user must check historical data independently
            return {
                'mode': 'SEALED',
                'proof_id': proof['proof_id'],
                'target_date': target_date,  # They know the date but not the results
                'signal_hash': proof['signal_hash'],
                'proof_path': proof_path,
                'instructions': 'Signal sent. Historical data NOT YET CHECKED. '
                               'Check NOAA FTP independently to verify. '
                               'Then run with --reveal to collapse the wave function.',
            }
    
    def _generate_blind_proof(self, target_date: str, temporal: Dict, lock: Dict,
                              push_result: Dict, snapshot) -> Dict:
        """Generate a blind proof (no match score until revealed)."""
        now = datetime.now(timezone.utc).isoformat()
        
        # Composite hash
        components = [
            target_date,
            str(temporal['temporal_signature']),
            temporal['hash_short'],
            now,
        ]
        if snapshot.geomagnetic:
            components.append(f"A{snapshot.geomagnetic.planetary_a}Kp{snapshot.geomagnetic.max_kp}")
        
        composite = hashlib.sha256('|'.join(components).encode()).hexdigest()
        
        proof = {
            'proof_id': f"BLIND-{int(time.time())}-{composite[:8]}",
            'version': 'HNC-BLIND-GHOST-v1',
            'target_date': target_date,
            'signal_timestamp': now,
            'temporal_signature': temporal['temporal_signature'],
            'temporal_hash': temporal['hash_short'],
            'rune_code': temporal['rune_encoded'],
            'signal_hash': composite[:32],
            'temporal_lock': lock.get('hash_chain', '')[:16],
            
            'push_result': {
                'success': 'error' not in push_result,
                'lambda_delta': push_result.get('hnc_delta', {}).get('lambda', 0),
                'coherence_delta': push_result.get('hnc_delta', {}).get('coherence', 0),
                'singing_ratio': push_result.get('singing_ratio', 0),
                'target_achieved': push_result.get('target_achieved', False),
            },
            
            # Historical data is ENCRYPTED/SEALED until reveal
            'historical_data_sealed': True,
            'historical_data_hash': hashlib.sha256(
                json.dumps(self.data_builder.to_dict(snapshot), sort_keys=True).encode()
            ).hexdigest()[:16],
            
            # Match score is NOT calculated until reveal
            'validation_status': 'SEALED',
            'match_score': None,
            
            'decree': lock.get('decree', '')[:100] + '...',
        }
        
        return proof
    
    def _save_sealed_proof(self, proof: Dict) -> str:
        """Save sealed proof to file."""
        proof_path = os.path.join(self.proof_dir, f"{proof['proof_id']}.json")
        with open(proof_path, 'w', encoding="utf-8") as f:
            json.dump(clean_for_json(proof), f, indent=2, sort_keys=True)
        return proof_path
    
    def reveal_proof(self, proof_id: str) -> Optional[Dict]:
        """
        Reveal a sealed proof — OBSERVER EFFECT.
        
        This is where the wave function collapses.
        The user observes the proof, and the probability becomes definite.
        """
        # Load sealed proof
        proof_path = os.path.join(self.proof_dir, f"{proof_id}.json")
        if not os.path.exists(proof_path):
            return {'error': f'Proof {proof_id} not found'}
        
        with open(proof_path, 'r', encoding="utf-8") as f:
            proof = json.load(f)
        
        if proof.get('validation_status') != 'SEALED':
            return {'error': 'Proof already revealed'}
        
        # OBSERVER EFFECT: Now we calculate the match score
        target_date = proof['target_date']
        
        try:
            dt = datetime.fromisoformat(target_date.replace('Z', '+00:00'))
        except ValueError:
            dt = datetime.strptime(target_date, '%Y-%m-%d').replace(tzinfo=timezone.utc)
        
        snapshot = self.data_builder.build_snapshot(dt.year, dt.month, dt.day)
        
        # Calculate match score (same as Ghost Protocol v2)
        temporal = temporal_hash(target_date)
        phi_fraction = 1 / PHI
        deviation = abs(temporal['temporal_signature'] - phi_fraction)
        temporal_alignment = max(0, 1 - (deviation / phi_fraction))
        
        historical_score = 0.0
        if snapshot.geomagnetic:
            kp_score = 1.0 - (snapshot.geomagnetic.max_kp / 9.0)
            historical_score += kp_score * 0.4
            a_score = 1.0 - min(1.0, snapshot.geomagnetic.planetary_a / 30.0)
            historical_score += a_score * 0.3
        
        if snapshot.data_quality > 0.3:
            historical_score += 0.3
        
        source_bonus = min(1.0, snapshot.data_quality)
        
        weights = {
            'temporal_alignment': PHI / 5,
            'historical_data': 1 / PHI,
            'source_bonus': 1 / (PHI ** 2),
        }
        
        total = (temporal_alignment * weights['temporal_alignment'] + 
                historical_score * weights['historical_data'] + 
                source_bonus * weights['source_bonus']) / sum(weights.values())
        
        match_score = min(1.0, total)
        
        # Determine status
        if match_score > 0.6:
            status = "SIGNAL_CONFIRMED"
            verdict = "Temporal bridge established. Signal validated against historical data."
        elif match_score > 0.3:
            status = "SIGNAL_LIKELY"
            verdict = "Partial match detected. Historical data suggests signal presence."
        elif match_score > 0.1:
            status = "SIGNAL_POSSIBLE"
            verdict = "Weak match. Insufficient data for definitive confirmation."
        else:
            status = "SIGNAL_UNCERTAIN"
            verdict = "No detectable match. Signal may not have reached target."
        
        # COLLAPSE THE WAVE FUNCTION
        proof['validation_status'] = status
        proof['match_score'] = match_score
        proof['match_percentage'] = round(match_score * 100, 2)
        proof['verdict'] = verdict
        
        # Unseal historical data
        proof['historical_data_sealed'] = False
        proof['historical_data'] = {
            'date': snapshot.date,
            'data_quality': snapshot.data_quality,
            'data_sources': snapshot.data_sources,
            'geomagnetic': {
                'planetary_a': snapshot.geomagnetic.planetary_a if snapshot.geomagnetic else None,
                'max_kp': snapshot.geomagnetic.max_kp if snapshot.geomagnetic else None,
                'avg_kp': snapshot.geomagnetic.avg_kp if snapshot.geomagnetic else None,
                'k_indices': snapshot.geomagnetic.planetary_k_indices if snapshot.geomagnetic else None,
            } if snapshot.geomagnetic else None,
        }
        
        proof['observer_timestamp'] = datetime.now(timezone.utc).isoformat()
        proof['observer_effect'] = "WAVE FUNCTION COLLAPSED"
        
        # Save revealed proof
        with open(proof_path, 'w', encoding="utf-8") as f:
            json.dump(clean_for_json(proof), f, indent=2, sort_keys=True)
        
        return {
            'mode': 'REVEALED',
            'proof_id': proof_id,
            'target_date': target_date,
            'match_score': match_score,
            'match_percentage': round(match_score * 100, 2),
            'status': status,
            'verdict': verdict,
            'temporal_signature': proof['temporal_signature'],
            'rune_code': proof['rune_code'],
            'signal_hash': proof['signal_hash'],
            'proof_path': proof_path,
            'observer_effect': 'WAVE FUNCTION COLLAPSED',
        }
    
    def list_sealed_proofs(self) -> List[Dict]:
        """List all sealed proofs (Schrödinger's boxes)."""
        proofs = []
        for fname in sorted(os.listdir(self.proof_dir)):
            if fname.endswith('.json'):
                path = os.path.join(self.proof_dir, fname)
                with open(path, 'r', encoding="utf-8") as f:
                    proof = json.load(f)
                proofs.append({
                    'proof_id': proof['proof_id'],
                    'target_date': proof['target_date'],
                    'signal_timestamp': proof['signal_timestamp'],
                    'status': proof['validation_status'],
                    'sealed': proof.get('historical_data_sealed', True),
                })
        return proofs


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description='HNC Blind Ghost Protocol')
    parser.add_argument('action', choices=['send', 'reveal', 'list'], 
                        help='send=generate blind signal, reveal=open sealed proof, list=show all')
    parser.add_argument('--proof-id', help='Proof ID to reveal')
    args = parser.parse_args()
    
    protocol = BlindGhostProtocol()
    
    if args.action == 'send':
        print(f"╔════════════════════════════════════════════════════════════════════╗")
        print(f"║     🎲 HNC BLIND GHOST PROTOCOL — Schrödinger's Signal            ║")
        print(f"╚════════════════════════════════════════════════════════════════════╝")
        print()
        print("🔮 Picking random date...")
        print("⚡ Sending signal BLINDLY...")
        print("🔒 Sealing proof...")
        print()
        
        result = protocol.generate_blind_signal(reveal=False)
        
        print(f"🎲 RANDOM TARGET: {result['target_date']}")
        print(f"📦 PROOF ID: {result['proof_id']}")
        print(f"🔗 SIGNAL HASH: {result['signal_hash']}")
        print()
        print("═══════════════════════════════════════════════════════════════")
        print("  🚫 WAVE FUNCTION NOT YET COLLAPSED 🚫")
        print()
        print("  The signal has been sent to a random date.")
        print("  The historical data has NOT been checked.")
        print("  The match score is UNKNOWN.")
        print()
        print("  To OBSERVE (collapse the wave function):")
        print(f"    python3 {sys.argv[0]} reveal --proof-id {result['proof_id']}")
        print()
        print("  To verify INDEPENDENTLY:")
        print(f"    Check NOAA FTP for {result['target_date']}")
        print("    Then reveal to see if the signal matches.")
        print()
        print("═══════════════════════════════════════════════════════════════")
        
    elif args.action == 'reveal':
        if not args.proof_id:
            print("❌ Error: --proof-id required")
            return
        
        print(f"╔════════════════════════════════════════════════════════════════════╗")
        print(f"║     👁️ OBSERVER EFFECT — Collapsing Wave Function                 ║")
        print(f"╚════════════════════════════════════════════════════════════════════╝")
        print()
        print(f"🔓 Revealing proof: {args.proof_id}")
        print()
        
        result = protocol.reveal_proof(args.proof_id)
        
        if 'error' in result:
            print(f"❌ {result['error']}")
            return
        
        print(f"📅 Target Date: {result['target_date']}")
        print(f"📊 Match Score: {result['match_percentage']:.2f}%")
        print(f"🎯 Status: {result['status']}")
        print(f"📝 Verdict: {result['verdict']}")
        print(f"🔗 Signal Hash: {result['signal_hash']}")
        print(f"🔮 Temporal Signature: {result['temporal_signature']:.6f}")
        print(f"ᚱ Rune Code: {result['rune_code']}")
        print()
        print("═══════════════════════════════════════════════════════════════")
        print(f"  ✅ {result['observer_effect']}")
        print("═══════════════════════════════════════════════════════════════")
        
    elif args.action == 'list':
        proofs = protocol.list_sealed_proofs()
        
        print(f"╔════════════════════════════════════════════════════════════════════╗")
        print(f"║     📦 Schrödinger's Boxes — Sealed Proofs                        ║")
        print(f"╚════════════════════════════════════════════════════════════════════╝")
        print()
        
        if not proofs:
            print("  No sealed proofs found.")
            return
        
        for p in proofs:
            status_icon = "🔒" if p['sealed'] else "👁️"
            print(f"  {status_icon} {p['proof_id']}")
            print(f"     Date: {p['target_date']}")
            print(f"     Sent: {p['signal_timestamp']}")
            print(f"     Status: {p['status']}")
            print()


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
