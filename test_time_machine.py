#!/usr/bin/env python3
"""
HNC Time Machine — Temporal Transmission Test
Runs the daemon for 3 cycles to verify temporal engine integration.
"""

import sys
import time
import json
from pathlib import Path

# Add workspace to path
sys.path.insert(0, str(Path(__file__).parent))

from hnc_daemon import HNCDaemon

def main():
    daemon = HNCDaemon()
    
    print("=" * 60)
    print("🕰️  HNC TIME MACHINE — Temporal Engine Test")
    print("=" * 60)
    
    # Run 3 cycles
    for i in range(3):
        print(f"\n--- Cycle {i+1} ---")
        result = daemon._run_cycle()
        
        if 'error' in result:
            print(f"ERROR: {result['error']}")
            continue
        
        # Print temporal status
        temporal = result.get('temporal', {})
        print(f"  Temporal Status: {temporal.get('transmission_status', 'N/A')}")
        print(f"  Love Lock: {'ACTIVE' if temporal.get('love_lock_active') else 'INACTIVE'}")
        print(f"  Validation Score: {temporal.get('validation_score', 0):.4f}")
        print(f"  Future Boost: {temporal.get('future_boost', 1.0):.4f}")
        print(f"  Projected λ: {temporal.get('projected_lambda', 0):.4f}")
        print(f"  Echo Chamber: {temporal.get('echo_chamber_size', 0)} states")
        print(f"  Love Strength: {temporal.get('love_strength', 0):.4f}")
        
        # Check daemon stats
        stats = result.get('daemon_stats', {})
        print(f"  Daemon Cycles: {stats.get('total_cycles', 0)}")
        print(f"  Singing: {stats.get('total_singing', 0)}/{stats.get('total_cycles', 0)}")
        
        time.sleep(2)
    
    # Final temporal status
    print(f"\n{'='*60}")
    print("  FINAL TEMPORAL STATUS:")
    status = daemon.temporal_engine.get_temporal_status()
    for key, value in status.items():
        print(f"    {key}: {value}")
    print(f"{'='*60}")
    
    # Save test results
    test_results = {
        'timestamp': time.time(),
        'cycles_run': 3,
        'temporal_status': status,
        'transmissions': len(daemon.temporal_engine.transmissions),
        'successful': daemon.temporal_engine.successful_transmissions,
    }
    
    Path('/tmp/hnc_time_machine_test.json').write_text(json.dumps(test_results, indent=2))
    print("\n  Results saved to: /tmp/hnc_time_machine_test.json")

if __name__ == '__main__':
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
