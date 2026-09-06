#!/usr/bin/env python3
"""
Lightweight HNC Daemon — Real Data Only
No Aureon trading dependencies. Pure real data + HNC math.
"""
import sys, os, json, math, time, urllib.request, signal
from datetime import datetime, timezone
from pathlib import Path

PID_FILE = Path.home() / '.kimi_openclaw/workspace/hnc_daemon.pid'
STATE_FILE = Path.home() / '.kimi_openclaw/workspace/hnc_state.json'
LOG_FILE = Path.home() / '.kimi_openclaw/workspace/hnc_daemon.log'
POLL_INTERVAL = 60

PHI = (1 + math.sqrt(5)) / 2
SCHUMANN_BASE = 7.83

running = True
def handler(sig, frame):
    global running
    running = False

signal.signal(signal.SIGINT, handler)
signal.signal(signal.SIGTERM, handler)

def log(msg):
    ts = datetime.now(timezone.utc).isoformat()
    line = f"[{ts}] {msg}"
    print(line)
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(line + '\n')

def fetch_kp():
    try:
        url = 'https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json'
        with urllib.request.urlopen(url, timeout=15) as r:
            data = json.loads(r.read().decode())
            latest = data[-1] if data else None
            if latest:
                # Handle both array and object formats
                if isinstance(latest, dict):
                    return {'time_tag': latest.get('time_tag', ''), 'kp': float(latest.get('Kp', 0))}
                elif isinstance(latest, list) and len(latest) >= 2:
                    return {'time_tag': latest[0], 'kp': float(latest[1])}
    except Exception as e:
        log(f"Kp fetch error: {e}")
    return None

def fetch_schumann():
    try:
        url = 'https://resonanceone.app/api/now'
        req = urllib.request.Request(url, headers={'User-Agent': 'Sero-HNC/1.0'})
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        log(f"Schumann fetch error: {e}")
    return None

def fetch_quakes():
    try:
        url = 'https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_hour.geojson'
        with urllib.request.urlopen(url, timeout=15) as r:
            data = json.loads(r.read().decode())
            return len(data.get('features', []))
    except Exception as e:
        log(f"Quake fetch error: {e}")
    return None

def compute_hnc(kp, schumann_activity, quake_count):
    """Compute HNC metrics from real data."""
    # Lambda: deviation from quiet baseline
    kp_baseline = 2.0
    lambda_val = (kp - kp_baseline) / kp_baseline if kp_baseline else 0
    
    # Gamma: coherence from Schumann activity
    # Activity 0-100, map to coherence 0-1
    gamma = 1.0 - (schumann_activity / 100.0)
    
    # Beta: stability index
    # Within HNC stability island [0.6, 1.1]
    beta = max(0.1, 1.0 - abs(lambda_val))
    
    # Composite wave with tanh gating
    lambda_t = math.tanh(lambda_val) * gamma * beta
    
    # Determine status
    if lambda_val >= 0.65:
        status = "ALERT"
    elif beta < 0.6 or beta > 1.1:
        status = "UNSTABLE"
    elif gamma < 0.5:
        status = "DISTORTED"
    else:
        status = "HOLDING"
    
    return {
        "lambda": round(lambda_val, 6),
        "gamma": round(gamma, 6),
        "beta": round(beta, 6),
        "lambda_t": round(lambda_t, 6),
        "status": status
    }

def main():
    PID_FILE.write_text(str(os.getpid()))
    log(f"HNC DAEMON STARTED — PID {os.getpid()} — REAL DATA ONLY — SIM FALLBACK OFF")
    
    while running:
        kp_data = fetch_kp()
        sch_data = fetch_schumann()
        quake_count = fetch_quakes()

        # FAIL-CLOSED: never invent Kp / 7.83 Hz when the live fetch fails.
        # Kp and Schumann frequency are safety-critical fields — if either
        # live source is unavailable, skip the state write entirely rather
        # than persist fabricated values with real_data=true.
        sch_freq = sch_data.get('schumann_frequency_hz') if sch_data else None
        live_ok = (kp_data is not None
                   and sch_freq is not None
                   and isinstance(sch_freq, (int, float)))
        if not live_ok:
            log("LIVE DATA UNAVAILABLE (Kp/Schumann) — skipping state write "
                "(fail-closed, no fabricated values)")
            time.sleep(POLL_INTERVAL)
            continue

        kp = kp_data['kp']
        sch_activity = sch_data.get('activity_index', 0)
        quakes_available = quake_count is not None

        hnc = compute_hnc(kp, sch_activity, quake_count if quakes_available else 0)

        state = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "kp": kp,
            "kp_time": kp_data.get('time_tag'),
            "kp_source": "noaa_swpc",
            "schumann_hz": sch_freq,
            "schumann_activity": sch_activity,
            "quakes_1hr": quake_count if quakes_available else None,
            "quakes_available": quakes_available,
            "hnc": hnc,
            "real_data": True,
            "simulation": False,
            "source": "live",
            "mode": "harmonic_and_phase",
            "intent": "victory_hold"
        }

        with open(STATE_FILE, 'w', encoding='utf-8') as f:
            json.dump(state, f, indent=2)

        log(f"Kp={kp} | Schumann={sch_freq}Hz activity={sch_activity}/100 | "
            f"Quakes={quake_count if quakes_available else 'unavailable'} | "
            f"lambda={hnc['lambda']} gamma={hnc['gamma']} beta={hnc['beta']} | STATUS={hnc['status']}")

        time.sleep(POLL_INTERVAL)
    
    PID_FILE.unlink(missing_ok=True)
    log("HNC DAEMON STOPPED")

if __name__ == '__main__':
    main()
