#!/usr/bin/env python3
"""
🌌 SOLAR SYSTEM - TEMPORAL STATE INTEGRATION
═══════════════════════════════════════════════════════════════════════

Reads solar system collector output and merges into unified temporal state.
"""

import json
import sys
from pathlib import Path
from datetime import datetime, timezone

# Paths
from aureon_fusion.paths import WORKSPACE, TEMPORAL_STATE

SOLAR_STATE_FILE = WORKSPACE / "solar_system_data" / "solar_system_state.json"
TEMPORAL_STATE_FILE = TEMPORAL_STATE / "temporal_state.json"

def merge_solar_into_temporal():
    """Merge solar system metrics into temporal state"""
    
    # Load solar system state
    if not SOLAR_STATE_FILE.exists():
        print("❌ No solar system state found")
        sys.exit(1)
    
    with open(SOLAR_STATE_FILE) as f:
        solar = json.load(f)
    
    # Load temporal state
    temporal = {}
    if TEMPORAL_STATE_FILE.exists():
        with open(TEMPORAL_STATE_FILE) as f:
            temporal = json.load(f)
    
    # Merge solar system data
    temporal['solar_system'] = {
        'timestamp': solar.get('timestamp'),
        'health': solar.get('solar_system_health', {}),
        'solar_activity': solar.get('solar_activity', {}),
        'solar_wind': solar.get('solar_wind', {}),
        'magnetic_field': solar.get('magnetic_field', {}),
        'particle_environment': solar.get('particle_environment', {}),
        'alerts': solar.get('alerts', {}),
        'aurora': solar.get('aurora', {}),
        'collection_status': solar.get('collection_status', {})
    }
    
    # Update timestamp
    temporal['last_updated'] = datetime.now(timezone.utc).isoformat()
    
    # Save
    TEMPORAL_STATE_FILE.parent.mkdir(exist_ok=True)
    with open(TEMPORAL_STATE_FILE, 'w') as f:
        json.dump(temporal, f, indent=2, default=str)
    
    print("✅ Solar system data merged into temporal state")
    
    # Print summary
    health = solar.get('solar_system_health', {})
    solar_act = solar.get('solar_activity', {})
    sw = solar.get('solar_wind', {})
    
    print(f"\n🌌 SOLAR SYSTEM SUMMARY")
    print(f"   Health: {health.get('score', 0):.2f} ({health.get('threat_level', 'unknown')})")
    print(f"   SSN: {solar_act.get('sunspot_number', 'N/A')}")
    print(f"   F10.7: {solar_act.get('f10.7_flux', 'N/A')} sfu")
    print(f"   Solar Wind: {sw.get('speed', 0):.1f} km/s, {sw.get('density', 0):.2f} cm⁻³")
    print(f"   Sources: {solar.get('collection_status', {}).get('successful_sources', 0)}/8")

if __name__ == '__main__':
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    merge_solar_into_temporal()
