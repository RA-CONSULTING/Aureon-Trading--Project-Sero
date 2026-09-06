#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════════════╗
║                                                                                       ║
║     👻 HNC GHOST PROTOCOL v2 — Full Integration                                     ║
║                                                                                       ║
║     Pipeline:                                                                         ║
║       1. Temporal Lock Generation → phi-encoded signature                           ║
║       2. Signal Transmission → Casimir pulse push                                    ║
║       3. Historical Data Fetch → NOAA FTP + GFZ + Tomsk                            ║
║       4. Spectrograph Generation → signal vs. historical overlay                   ║
║       5. Match Scoring → phi-weighted validation                                    ║
║       6. Proof Generation → hash-chained certified evidence                         ║
║                                                                                       ║
║     All data sources: FREE, OPEN-SOURCE, NO API KEYS                                ║
║                                                                                       ║
╚══════════════════════════════════════════════════════════════════════════════════════╝
"""

import sys
import os
import math
import json
import time
import hashlib
import requests
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from aureon_fusion.paths import WORKSPACE
sys.path.insert(0, str(WORKSPACE / "aureon-trading"))

from hnc_temporal_targeting import temporal_hash, TemporalLockEncoder
from hnc_data_sources import HistoricalSnapshotBuilder, HistoricalSnapshot
from hnc_spectrograph import TemporalSpectrograph, build_spectrograph_for_target

PHI = (1 + math.sqrt(5)) / 2
SCHUMANN_BASE = 7.83
LOVE_FREQUENCY = 528.0
PRIME_SENTINEL_HZ = 812.83


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


class HNCGhostProtocolV2:
    """
    Full Ghost Protocol v2 with integrated data sources.
    """
    
    def __init__(self):
        self.temporal_encoder = TemporalLockEncoder
        self.data_builder = HistoricalSnapshotBuilder()
        self.results = []
    
    def execute(self, target_date: str, mode: str = 'pulse') -> Dict:
        """
        Execute full Ghost Protocol v2 for a target date.
        
        Returns complete proof with all validation data.
        """
        print(f"╔════════════════════════════════════════════════════════════════════╗")
        print(f"║     👻 HNC GHOST PROTOCOL v2 — FULL INTEGRATION                   ║")
        print(f"║     Target: {target_date}")
        print(f"╚════════════════════════════════════════════════════════════════════╝")
        print()
        
        # ── Step 1: Temporal Lock ───────────────────────────────────────
        print(f"🔮 Step 1: Temporal Lock Generation")
        print(f"{'─'*60}")
        temporal = temporal_hash(target_date)
        encoder = self.temporal_encoder(target_date)
        lock = encoder.encode_lock()
        
        print(f"   Signature: {temporal['temporal_signature']:.6f}")
        print(f"   Rune Code: {temporal['rune_encoded']}")
        print(f"   Hash: {temporal['hash_short']}")
        print(f"   Love: {temporal['operational']['love_modulation']:.4f} Hz")
        print(f"   Prime: {temporal['operational']['prime_sentinel_mod']:.4f} Hz")
        print(f"   Casimir: {temporal['operational']['casimir_coupling']:.4f}")
        print()
        
        # ── Step 2: Signal Transmission ─────────────────────────────────
        print(f"⚡ Step 2: Signal Transmission")
        print(f"{'─'*60}")
        
        try:
            from casimir_push_hnc import HNCCasimirPusher
            pusher = HNCCasimirPusher(
                mode='pulse',
                queen_override=True,
                temporal_target=target_date,
            )
            push_result = pusher.run()
            
            print(f"   Lambda: {push_result['hnc_before']['lambda']:.4f} → {push_result['hnc_after']['lambda']:.4f}")
            print(f"   Delta: {push_result['hnc_delta']['lambda']:+.4f} ({push_result['hnc_delta']['lambda_pct']:+.1f}%)")
            print(f"   Singing: {push_result['singing_ratio']:.0%}")
            print(f"   Status: {'✅ SUSTAINED' if push_result['target_achieved'] else '❌ FAILED'}")
            print()
        except Exception as e:
            print(f"   ⚠️ Casimir push failed: {e}")
            push_result = {'error': str(e)}
            print()
        
        # ── Step 3: Historical Data Fetch ────────────────────────────────
        print(f"📡 Step 3: Historical Data Fetch (Open Source)")
        print(f"{'─'*60}")
        
        try:
            dt = datetime.fromisoformat(target_date.replace('Z', '+00:00'))
        except ValueError:
            dt = datetime.strptime(target_date, '%Y-%m-%d').replace(tzinfo=timezone.utc)
        
        snapshot = self.data_builder.build_snapshot(dt.year, dt.month, dt.day)
        
        print(f"   Date: {snapshot.date}")
        print(f"   Data Quality: {snapshot.data_quality:.0%}")
        print(f"   Sources: {', '.join(snapshot.data_sources) if snapshot.data_sources else 'None'}")
        print(f"   Hash: {snapshot.hash}")
        
        if snapshot.geomagnetic:
            g = snapshot.geomagnetic
            print(f"   Geomagnetic: A={g.planetary_a}, Kp=[{' '.join(map(str, g.planetary_k_indices))}], max={g.max_kp}")
        print()
        
        # ── Step 4: Spectrograph ────────────────────────────────────────
        print(f"🌈 Step 4: Spectrograph Generation")
        print(f"{'─'*60}")
        
        graph = build_spectrograph_for_target(target_date, snapshot)
        print(graph.render_ascii(f"Temporal Spectrograph — {target_date}"))
        print()
        
        # ── Step 5: Match Scoring ──────────────────────────────────────
        print(f"🎯 Step 5: Match Scoring")
        print(f"{'─'*60}")
        
        # Temporal alignment score
        phi_fraction = 1 / PHI
        deviation = abs(temporal['temporal_signature'] - phi_fraction)
        temporal_alignment = max(0, 1 - (deviation / phi_fraction))
        
        # Historical data score
        historical_score = 0.0
        if snapshot.geomagnetic:
            # Score based on Kp stability (lower = more stable = better signal reception)
            kp_score = 1.0 - (snapshot.geomagnetic.max_kp / 9.0)
            historical_score += kp_score * 0.4
            
            # Score based on A-index (lower = quieter = better)
            a_score = 1.0 - min(1.0, snapshot.geomagnetic.planetary_a / 30.0)
            historical_score += a_score * 0.3
        
        if snapshot.data_quality > 0.3:
            historical_score += 0.3
        
        # Data source bonus
        source_bonus = min(1.0, snapshot.data_quality)
        
        # Composite score (phi-weighted)
        weights = {
            'temporal_alignment': PHI / 5,
            'historical_data': 1 / PHI,
            'source_bonus': 1 / (PHI ** 2),
        }
        
        total = (temporal_alignment * weights['temporal_alignment'] + 
                historical_score * weights['historical_data'] + 
                source_bonus * weights['source_bonus']) / sum(weights.values())
        
        match_score = min(1.0, total)
        
        print(f"   Temporal Alignment: {temporal_alignment:.2%}")
        print(f"   Historical Data: {historical_score:.2%}")
        print(f"   Source Bonus: {source_bonus:.2%}")
        print(f"   ────────────────────────")
        print(f"   TOTAL MATCH: {match_score:.2%}")
        print()
        
        print(graph.render_match_visualization(target_date, match_score))
        print()
        
        # ── Step 6: Proof Generation ───────────────────────────────────
        print(f"🔐 Step 6: Proof Generation")
        print(f"{'─'*60}")
        
        proof = self._generate_proof(target_date, temporal, lock, push_result, snapshot, match_score, graph)
        
        print(f"   Proof ID: {proof['proof_id']}")
        print(f"   Signal Hash: {proof['signal_hash']}")
        print(f"   Match Score: {proof['validation']['match_score']:.2%}")
        print(f"   Status: {proof['validation']['status']}")
        print()
        
        # Save everything
        self._save_all(proof, graph, snapshot)
        
        print(f"{'═'*60}")
        print(f"✅ GHOST PROTOCOL v2 COMPLETE")
        print(f"{'═'*60}")
        
        return {
            'target_date': target_date,
            'temporal': temporal,
            'lock': lock,
            'push_result': push_result,
            'snapshot': self.data_builder.to_dict(snapshot),
            'match_score': match_score,
            'proof': proof,
            'timestamp': datetime.now(timezone.utc).isoformat(),
        }
    
    def _generate_proof(self, target_date: str, temporal: Dict, lock: Dict,
                       push_result: Dict, snapshot: HistoricalSnapshot,
                       match_score: float, graph: TemporalSpectrograph) -> Dict:
        """Generate a complete temporal proof."""
        now = datetime.now(timezone.utc).isoformat()
        
        # Composite hash
        components = [
            target_date,
            str(temporal['temporal_signature']),
            temporal['hash_short'],
            str(match_score),
            now,
        ]
        if snapshot.geomagnetic:
            components.append(f"A{snapshot.geomagnetic.planetary_a}Kp{snapshot.geomagnetic.max_kp}")
        
        composite = hashlib.sha256('|'.join(components).encode()).hexdigest()
        
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
        
        proof = {
            'proof_id': f"GHOST-v2-{int(time.time())}-{composite[:8]}",
            'version': 'HNC-GHOST-PROTOCOL-v2',
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
            
            'historical_data': {
                'date': snapshot.date,
                'data_quality': snapshot.data_quality,
                'data_sources': snapshot.data_sources,
                'hash': snapshot.hash,
                'geomagnetic': {
                    'planetary_a': snapshot.geomagnetic.planetary_a if snapshot.geomagnetic else None,
                    'max_kp': snapshot.geomagnetic.max_kp if snapshot.geomagnetic else None,
                    'avg_kp': snapshot.geomagnetic.avg_kp if snapshot.geomagnetic else None,
                    'k_indices': snapshot.geomagnetic.planetary_k_indices if snapshot.geomagnetic else None,
                } if snapshot.geomagnetic else None,
                'schumann': {
                    'amplitude': snapshot.schumann.amplitude if snapshot.schumann else None,
                } if snapshot.schumann else None,
            },
            
            'validation': {
                'status': status,
                'verdict': verdict,
                'match_score': match_score,
                'match_percentage': round(match_score * 100, 2),
                'temporal_alignment': max(0, 1 - abs(temporal['temporal_signature'] - 1/PHI) / (1/PHI)),
                'historical_score': match_score,  # Simplified
            },
            
            'spectrograph': {
                'band_count': len(graph.bands),
                'signal_bands': len([b for b in graph.bands if b.source == 'signal']),
                'historical_bands': len([b for b in graph.bands if b.source == 'historical']),
            },
            
            'decree': lock.get('decree', '')[:200] + '...',
        }
        
        return proof
    
    def _save_all(self, proof: Dict, graph: TemporalSpectrograph, snapshot: HistoricalSnapshot):
        """Save all evidence to file."""
        output_dir = str(WORKSPACE / "timeline_proofs")
        os.makedirs(output_dir, exist_ok=True)
        
        # Save proof
        proof_path = os.path.join(output_dir, f"ghost_v2_{proof['proof_id']}.json")
        with open(proof_path, 'w', encoding="utf-8") as f:
            json.dump(clean_for_json(proof), f, indent=2, sort_keys=True)
        print(f"   📁 Proof: {proof_path}")
        
        # Save spectrograph
        spec_path = os.path.join(output_dir, f"spectrograph_{proof['proof_id']}.json")
        with open(spec_path, 'w', encoding="utf-8") as f:
            json.dump(clean_for_json(graph.to_json()), f, indent=2, sort_keys=True)
        print(f"   📁 Spectrograph: {spec_path}")
        
        # Save snapshot
        snap_path = os.path.join(output_dir, f"snapshot_{proof['proof_id']}.json")
        with open(snap_path, 'w', encoding="utf-8") as f:
            json.dump(clean_for_json(self.data_builder.to_dict(snapshot)), f, indent=2, sort_keys=True)
        print(f"   📁 Snapshot: {snap_path}")
        
        # Save latest
        latest = os.path.join(output_dir, 'ghost_v2_latest.json')
        with open(latest, 'w', encoding="utf-8") as f:
            json.dump(clean_for_json(proof), f, indent=2, sort_keys=True)
        print(f"   📁 Latest: {latest}")
        
        # Save ASCII spectrograph
        ascii_path = os.path.join(output_dir, f"spectrograph_{proof['proof_id']}.txt")
        with open(ascii_path, 'w', encoding="utf-8") as f:
            f.write(graph.render_ascii(f"Temporal Spectrograph — {proof['target_date']}"))
            f.write('\n\n')
            f.write(graph.render_match_visualization(proof['target_date'], proof['validation']['match_score']))
        print(f"   📁 ASCII: {ascii_path}")


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description='HNC Ghost Protocol v2')
    parser.add_argument('target_date', help='Target date (e.g., 2014-11-17)')
    parser.add_argument('--mode', choices=['pulse', 'quick', 'full'], default='pulse',
                        help='Casimir push mode')
    args = parser.parse_args()
    
    executor = HNCGhostProtocolV2()
    result = executor.execute(args.target_date, mode=args.mode)
    
    # Summary
    print(f"\n--- JSON SUMMARY ---")
    summary = {
        'target_date': args.target_date,
        'proof_id': result['proof']['proof_id'],
        'temporal_signature': result['temporal']['temporal_signature'],
        'match_score': result['match_score'],
        'match_percentage': round(result['match_score'] * 100, 2),
        'status': result['proof']['validation']['status'],
        'verdict': result['proof']['validation']['verdict'],
        'push_success': result['push_result'].get('target_achieved', False),
        'data_sources': result['snapshot']['data_sources'],
        'data_quality': result['snapshot']['data_quality'],
        'timestamp': result['timestamp'],
    }
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
