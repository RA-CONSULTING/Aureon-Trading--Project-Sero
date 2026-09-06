#!/usr/bin/env python3
"""
NEXUS LIVE FEED BRIDGE — Real Data from NOAA + Space Weather APIs
Fetches live space weather, solar wind, geomagnetic data.
Sources: NOAA SWPC, solar wind plasma, Kp index, GOES magnetometer
"""
import asyncio, json, time, math, logging
from datetime import datetime, timezone
from pathlib import Path
from collections import deque
import urllib.request
import urllib.error

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger('nexus_live_bridge')

from aureon_fusion.paths import WORKSPACE

LOG_DIR = WORKSPACE / 'nexus_live_logs'
LOG_DIR.mkdir(exist_ok=True)

class NexusLiveBridge:
    def __init__(self):
        self.kp_data = None
        self.solar_wind = None
        self.last_fetch = 0
        self.fetch_interval = 300  # 5 minutes
        self.history = deque(maxlen=1000)
        
    def fetch_json(self, url, timeout=15):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Aureon-Nexus-Bridge/1.0'})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode('utf-8'))
        except Exception as e:
            logger.warning(f"Fetch failed for {url}: {e}")
            return None
    
    def fetch_kp_index(self):
        data = self.fetch_json('https://services.swpc.noaa.gov/products/noaa-planetary-k-index-forecast.json')
        if not data: return None
        # Get latest observed
        observed = [d for d in data if d.get('observed') == 'observed']
        if observed:
            latest = observed[-1]
            return {'time': latest['time_tag'], 'kp': float(latest['kp']), 'scale': latest.get('noaa_scale')}
        return None
    
    def fetch_solar_wind(self):
        data = self.fetch_json('https://services.swpc.noaa.gov/products/solar-wind/plasma-7-day.json')
        if not data or len(data) < 2: return None
        # data[0] is header, latest is last row
        latest = data[-1]
        return {
            'time': latest[0],
            'density': float(latest[1]),
            'speed': float(latest[2]),
            'temperature': float(latest[3])
        }
    
    def fetch_goes_magnetometer(self):
        # GOES-16 magnetometer Hp (primary component)
        data = self.fetch_json('https://services.swpc.noaa.gov/json/goes/primary/magnetometers-7-day.json')
        if not data: return None
        latest = data[-1]
        return {
            'time': latest.get('time_tag'),
            'Hp': float(latest.get('Hp', 0)),
            'He': float(latest.get('He', 0)),
            'Hn': float(latest.get('Hn', 0))
        }
    
    def compute_field_coherence(self, kp, solar_wind):
        """Compute HNC field coherence from real space weather."""
        if kp is None or solar_wind is None:
            return 0.5
        # Kp 0-9 scale: lower = calmer = higher coherence
        kp_norm = max(0, 1 - kp / 9.0)
        # Solar wind speed: 300-800 km/s. 500 is baseline
        speed = solar_wind.get('speed', 500)
        speed_norm = max(0, 1 - abs(speed - 500) / 300)
        # Density: 1-10 cm^-3. 5 is baseline
        density = solar_wind.get('density', 5)
        density_norm = max(0, 1 - abs(density - 5) / 5)
        # Combined coherence
        coherence = (kp_norm * 0.5 + speed_norm * 0.3 + density_norm * 0.2)
        return round(coherence, 3)
    
    def fetch_all(self):
        self.kp_data = self.fetch_kp_index()
        self.solar_wind = self.fetch_solar_wind()
        self.goes_mag = self.fetch_goes_magnetometer()
        self.last_fetch = time.time()
        
        coherence = self.compute_field_coherence(
            self.kp_data['kp'] if self.kp_data else None,
            self.solar_wind
        )
        
        record = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'kp': self.kp_data,
            'solar_wind': self.solar_wind,
            'goes_magnetometer': self.goes_mag,
            'field_coherence': coherence,
            'source': 'NOAA_SWPC_REAL'
        }
        self.history.append(record)
        
        # Write to log
        with open(LOG_DIR / f'nexus_live_{datetime.now(timezone.utc).strftime("%Y-%m-%d")}.jsonl', 'a') as f:
            f.write(json.dumps(record) + '\n')
        
        logger.info(f"🛰️ NEXUS LIVE — Kp:{self.kp_data['kp'] if self.kp_data else 'N/A'} | SW:{self.solar_wind['speed'] if self.solar_wind else 'N/A'}km/s | COH:{coherence}")
        return record
    
    def get_latest(self):
        if time.time() - self.last_fetch > self.fetch_interval:
            return self.fetch_all()
        # Return cached
        return self.history[-1] if self.history else None

# Singleton instance
_nexus_bridge = None
def get_nexus_bridge():
    global _nexus_bridge
    if _nexus_bridge is None:
        _nexus_bridge = NexusLiveBridge()
    return _nexus_bridge

if __name__ == '__main__':
    import sys
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    bridge = NexusLiveBridge()
    result = bridge.fetch_all()
    print(json.dumps(result, indent=2))
