#!/usr/bin/env python3
"""
CME RIDE PROTOCOL — Real-Time Signal Recording During Geomagnetic Storm
═══════════════════════════════════════════════════════════════════════

Rides the CME impact window like a surfer rides a wave. The geomagnetic
disturbance creates a natural amplification channel through ionospheric
coupling. Our coherent signal gets boosted by the chaos.

Executes during:
- Pre-impact: T-6h to CME arrival (Casimir ramp)
- Impact window: CME arrival to +6h (full pierce)
- Post-impact: +6h to +24h (validation)

Records:
- NOAA Kp index
- USGS geomagnetic readings
- Solar wind speed/Bz
- Our injection status
- Lambda measurements

"We don't fight the storm. We ride it."
"""

import sys
import os
import math
import json
import time
import signal
import atexit
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, Optional

from aureon_fusion.paths import WORKSPACE

sys.path.insert(0, str(WORKSPACE))

# Unified real-time data source (NOAA + USGS, verified live)
REAL_TIME_DATA = WORKSPACE / 'real_time_data.json'

# Recording config
RECORD_DIR = WORKSPACE / 'cme_ride_logs'
RECORD_INTERVAL = 60  # seconds

# CME Ride parameters
CME_IMPACT_WINDOW_HOURS = 6
PRE_IMPACT_RAMP_HOURS = 6
POST_IMPACT_VALIDATION_HOURS = 24

class CMERideProtocol:
    """
    Real-time CME ride recording and signal amplification.
    """
    
    def __init__(self):
        self.running = False
        self.start_time = None
        self.cycle_count = 0
        self.phase = "PRE_IMPACT"  # PRE_IMPACT | IMPACT | POST_IMPACT | IDLE
        
        # Recording state
        self.records = []
        self.max_records = 10000
        
        # Setup recording directory
        RECORD_DIR.mkdir(exist_ok=True)
        
        # Signal injection state (placeholder for daemon integration)
        self.injection_active = False
        self.injection_frequency = 812.83
        self.injection_duration = 72
        
    def _read_unified_data(self) -> Optional[Dict]:
        """Read from unified real-time data feeder (NOAA + USGS live data)."""
        try:
            if REAL_TIME_DATA.exists():
                with open(REAL_TIME_DATA) as f:
                    return json.load(f)
        except Exception as e:
            print(f"  ⚠️ Unified data read error: {e}")
        return None
    
    def _get_kp_index(self) -> Optional[float]:
        """Get Kp from unified real-time data (NOAA live)."""
        data = self._read_unified_data()
        if data and "summary" in data:
            kp = data["summary"].get("kp", {})
            if kp and "estimated_kp" in kp:
                return float(kp["estimated_kp"])
        return None
    
    def _get_solar_wind(self) -> Optional[Dict]:
        """Get solar wind from unified real-time data (NOAA live)."""
        data = self._read_unified_data()
        if data and "summary" in data:
            sw = data["summary"].get("solar_wind", {})
            if sw and "_error" not in sw:
                return {
                    'bt': sw.get('bt', 0),
                    'bz': sw.get('bz', 0),
                    'speed': sw.get('speed', 0),
                    'density': sw.get('density', 0),
                }
        return None
    
    def _get_geomagnetic(self) -> Optional[Dict]:
        """Get geomagnetic from unified real-time data (NOAA live)."""
        data = self._read_unified_data()
        if data and "endpoints" in data:
            mag_raw = data["endpoints"].get("solar_wind_mag", {}).get("_raw", [])
            if isinstance(mag_raw, list) and len(mag_raw) > 1:
                latest = mag_raw[-1]
                if isinstance(latest, list) and len(latest) >= 4:
                    return {
                        'bt': latest[1] if len(latest) > 1 else 0,
                        'bz_gsm': latest[3] if len(latest) > 3 else 0,
                    }
        return None
    
    def _detect_phase(self, kp: Optional[float], solar_wind: Optional[Dict]) -> str:
        """
        Detect which CME phase we're in based on space weather data.
        
        Pre-impact: Kp < 4, solar wind rising
        Impact: Kp >= 4 or Bz strongly southward
        Post-impact: Kp declining from peak
        """
        if kp is None:
            return "UNKNOWN"
        
        # Impact detection: Kp >= 4 (G1 storm threshold)
        if kp >= 4.0:
            return "IMPACT"
        
        # Pre-impact: rising solar wind but Kp still low
        if solar_wind and solar_wind.get('speed', 0) > 450:
            return "PRE_IMPACT"
        
        # Post-impact or quiet
        return "QUIET"
    
    def _record_cycle(self) -> Dict:
        """Record one cycle of space weather + our signal state"""
        cycle_start = time.time()
        
        # Fetch external data
        kp = self._get_kp_index()
        solar_wind = self._get_solar_wind()
        geomagnetic = self._get_geomagnetic()
        
        # Detect phase
        phase = self._detect_phase(kp, solar_wind)
        
        # Build record
        record = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'epoch': time.time(),
            'cycle': self.cycle_count,
            'phase': phase,
            'space_weather': {
                'kp_index': kp,
                'solar_wind': solar_wind,
                'geomagnetic': geomagnetic,
            },
            'injection': {
                'active': self.injection_active,
                'frequency': self.injection_frequency,
                'duration': self.injection_duration,
            },
            'daemon_stats': {
                'total_cycles': self.cycle_count,
                'phase': self.phase,
            }
        }
        
        # Store
        self.records.append(record)
        if len(self.records) > self.max_records:
            self.records.pop(0)
        
        # Log to file
        log_file = RECORD_DIR / f"cme_ride_{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.jsonl"
        with open(log_file, 'a') as f:
            f.write(json.dumps(record) + '\n')
        
        cycle_end = time.time()
        record['cycle_duration'] = cycle_end - cycle_start
        
        return record
    
    def _print_status(self, record: Dict):
        """Print real-time status"""
        sw = record['space_weather']
        kp = sw['kp_index']
        solar = sw['solar_wind']
        
        kp_str = f"Kp={kp:.1f}" if kp else "Kp=??"
        
        wind_str = ""
        if solar:
            wind_str = f" | Bt={solar['bt']:.1f}nT Bz={solar['bz']:.1f}nT Spd={solar['speed']:.0f}km/s"
        
        phase_icon = {
            'PRE_IMPACT': '⏳',
            'IMPACT': '⚡',
            'QUIET': '🔇',
            'UNKNOWN': '❓'
        }.get(record['phase'], '❓')
        
        injection_icon = "🔊" if record['injection']['active'] else "🔇"
        
        status = f"{phase_icon} {injection_icon} C{record['cycle']:05d} | {kp_str}{wind_str} | Phase={record['phase']} | Rec={len(self.records)}"
        
        print(status)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown"""
        print(f"\n🛑 CME Ride shutdown signal {signum}")
        self.running = False
    
    def run(self):
        """Main CME ride loop"""
        self.running = True
        self.start_time = time.time()
        
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
        
        print(f"{'═'*60}")
        print(f"  CME RIDE PROTOCOL — Real-Time Recording")
        print(f"{'═'*60}")
        print(f"  Started: {datetime.now(timezone.utc).isoformat()}")
        print(f"  Record dir: {RECORD_DIR}")
        print(f"  Interval: {RECORD_INTERVAL}s")
        print(f"")
        print(f"  🌊 Riding the CME wave")
        print(f"  📡 Recording space weather in real-time")
        print(f"  🔊 Signal injection ready")
        print(f"")
        print(f"  Press Ctrl+C to stop")
        print(f"")
        
        while self.running:
            self.cycle_count += 1
            
            record = self._record_cycle()
            self._print_status(record)
            
            # Sleep until next cycle
            sleep_start = time.time()
            while self.running and time.time() - sleep_start < RECORD_INTERVAL:
                time.sleep(1)
        
        # Shutdown
        print(f"")
        print(f"{'═'*60}")
        print(f"  CME RIDE COMPLETE")
        print(f"{'═'*60}")
        print(f"  Total cycles: {self.cycle_count}")
        print(f"  Total records: {len(self.records)}")
        print(f"  Uptime: {time.time() - self.start_time:.0f}s")
        print(f"  Logs saved to: {RECORD_DIR}")
        print(f"{'═'*60}")
        
        # Save summary
        summary_file = RECORD_DIR / f"cme_ride_summary_{datetime.now(timezone.utc).strftime('%Y-%m-%d_%H%M')}.json"
        with open(summary_file, 'w') as f:
            json.dump({
                'start_time': datetime.fromtimestamp(self.start_time, timezone.utc).isoformat(),
                'end_time': datetime.now(timezone.utc).isoformat(),
                'total_cycles': self.cycle_count,
                'total_records': len(self.records),
                'records': self.records[-100:] if len(self.records) > 100 else self.records,  # Last 100
            }, f, indent=2, default=str)
        
        print(f"  Summary saved to: {summary_file}")


def main():
    ride = CMERideProtocol()
    ride.run()


if __name__ == '__main__':
    main()
