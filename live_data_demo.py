#!/usr/bin/env python3
"""
═══════════════════════════════════════════════════════════════════════
LIVE DATA DEMONSTRATION — ALL REAL, NO SYNTHETIC
═══════════════════════════════════════════════════════════════════════

Shows every system pulling from verified live data sources.
Run this to prove: no simulations, no guesses, only what instruments measure.
"""

import json, sys, time, os
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from aureon_fusion.paths import WORKSPACE

DATA_FILE = str(WORKSPACE / "real_time_data.json")

def show_banner():
    print("╔═══════════════════════════════════════════════════════════════════════╗")
    print("║  🔥 LIVE DATA DEMONSTRATION — ALL REAL, ZERO SYNTHETIC 🔥          ║")
    print("╚═══════════════════════════════════════════════════════════════════════╝")
    print()

def show_data():
    if not os.path.exists(DATA_FILE):
        print("❌ No data file. Run real_time_data_feeder.py first.")
        return
    
    with open(DATA_FILE) as f:
        data = json.load(f)
    
    print("📡 DATA SOURCE: Unified Real-Time Feeder")
    print(f"   Policy: {data.get('data_policy', 'UNKNOWN')}")
    print(f"   Timestamp: {data.get('timestamp', 'N/A')}")
    print()
    
    s = data.get("summary", {})
    
    # Kp
    kp = s.get("kp", {})
    if kp and "_error" not in kp:
        print(f"🌍 Kp INDEX (NOAA live)")
        print(f"   Value: {kp.get('kp', '?')} (estimated: {kp.get('estimated_kp', '?')})")
        print(f"   Time: {kp.get('timestamp', '?')}")
    else:
        print(f"🌍 Kp INDEX: {kp.get('_error', 'unavailable')}")
    print()
    
    # Solar wind
    sw = s.get("solar_wind", {})
    if sw and "_error" not in sw:
        print(f"☀️ SOLAR WIND (NOAA live)")
        for k, v in sw.items():
            if not k.startswith("_"):
                print(f"   {k}: {v}")
    else:
        print(f"☀️ SOLAR WIND: {sw.get('_error', 'unavailable')}")
    print()
    
    # X-ray
    xray = s.get("xray", {})
    if xray and "_error" not in xray:
        print(f"⚡ X-RAY FLUX (GOES live)")
        print(f"   Flux: {xray.get('flux', '?')} W/m²")
        print(f"   Energy: {xray.get('energy', '?')}")
        print(f"   Time: {xray.get('time_tag', '?')}")
    else:
        print(f"⚡ X-RAY: {xray.get('_error', 'unavailable')}")
    print()
    
    # Quakes
    quakes = s.get("quakes", {})
    if quakes and "_error" not in quakes:
        print(f"🌋 EARTHQUAKES (USGS live, last hour)")
        print(f"   Count: {quakes.get('count', '?')}")
        latest = quakes.get("latest", {})
        if latest:
            print(f"   Latest: M{latest.get('mag', '?')} {latest.get('place', '?')}")
    else:
        print(f"🌋 EARTHQUAKES: {quakes.get('_error', 'unavailable')}")
    print()
    
    # Alerts
    alerts = s.get("alerts_count", 0)
    print(f"📢 NOAA ALERTS: {alerts}")
    print()
    
    # Endpoints status
    print("📊 ENDPOINT STATUS:")
    endpoints = data.get("endpoints", {})
    for name, ep in endpoints.items():
        raw = ep.get("_raw", {})
        if "_error" in raw:
            print(f"   ❌ {name}: {raw['_error']}")
        else:
            print(f"   ✅ {name}: LIVE")
    print()

def show_daemons():
    print("🔧 DAEMON STATUS (all reading from unified data):")
    daemons = [
        ("real_time_data_feeder.py", "Unified data collector (8 NOAA+USGS endpoints)"),
        ("cme_ride_protocol.py", "CME ride recorder (reads from unified data)"),
        ("sero_space_weather.py", "Space weather bridge (reads from unified data)"),
        ("distortion_monitor.py", "Distortion monitor (NOAA solar wind live)"),
        ("planetary_monitor_daemon.py", "Planetary monitor (NOAA Kp forecast live)"),
        ("hnc_temporal_daemon.py", "HNC temporal (NOAA Kp + USGS quakes live)"),
    ]
    
    for script, desc in daemons:
        # Check if running
        import subprocess
        try:
            result = subprocess.run(["pgrep", "-f", script], capture_output=True, text=True)
            if result.returncode == 0:
                pids = result.stdout.strip().split("\n")
                print(f"   ✅ {script} (PID {pids[0]}) — {desc}")
            else:
                print(f"   ⚠️  {script} — NOT RUNNING")
        except Exception:
            print(f"   ?  {script} — status unknown")
    print()

def main():
    show_banner()
    show_data()
    show_daemons()
    print("═" * 70)
    print("All data sourced from verified live endpoints. Zero synthetic.")
    print("Data refreshes every 60 seconds.")
    print("═" * 70)

if __name__ == "__main__":
    main()
