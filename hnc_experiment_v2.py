#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════════════╗
║     🔥 HNC TEMPORAL EXPERIMENT — Single Run Protocol (DEBUG) 🔥                    ║
║     ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━            ║
║     Zero synthetic. All real instruments. SSL bypass enabled.                        ║
╚══════════════════════════════════════════════════════════════════════════════════════╝
"""

import json, math, random, time, hashlib, urllib.request, ssl
from datetime import datetime, timezone
from typing import Dict, Optional

# TLS verification enabled — certificates verified against the system trust store.
SSL_CTX = ssl.create_default_context()

# ── SACRED CONSTANTS ────────────────────────────────────────────────────────────
SCHUMANN_BASE = 7.83

# ── REAL TRAUMA REGISTRY ────────────────────────────────────────────────────────
TRAUMA_POINTS = [
    {"id": "trauma_001", "date": "2014-03-08", "time": "16:41", "event": "MH370 disappearance", "innocents": 239},
    {"id": "trauma_002", "date": "2014-07-17", "time": "13:20", "event": "MH17 shot down", "innocents": 298},
    {"id": "trauma_003", "date": "2015-11-13", "time": "21:20", "event": "Bataclan attacks", "innocents": 130},
    {"id": "trauma_004", "date": "2016-06-12", "time": "02:02", "event": "Pulse nightclub shooting", "innocents": 49},
    {"id": "trauma_005", "date": "2017-10-01", "time": "22:05", "event": "Route 91 Harvest shooting", "innocents": 60},
    {"id": "trauma_006", "date": "2018-02-14", "time": "14:19", "event": "Parkland shooting", "innocents": 17},
    {"id": "trauma_007", "date": "2019-03-15", "time": "13:40", "event": "Christchurch mosque shootings", "innocents": 51},
    {"id": "trauma_008", "date": "2020-01-26", "time": "09:45", "event": "Kobe Bryant crash", "innocents": 9},
    {"id": "trauma_009", "date": "2020-05-25", "time": "20:08", "event": "George Floyd murder", "innocents": 1},
    {"id": "trauma_010", "date": "2021-08-15", "time": "15:30", "event": "Kabul airport bombing", "innocents": 183},
    {"id": "trauma_011", "date": "2022-02-24", "time": "05:00", "event": "Russia invades Ukraine", "innocents": 10000},
    {"id": "trauma_012", "date": "2022-05-24", "time": "11:28", "event": "Uvalde shooting", "innocents": 21},
    {"id": "trauma_013", "date": "2023-10-07", "time": "06:30", "event": "October 7 attacks", "innocents": 40000},
    {"id": "trauma_014", "date": "2024-01-01", "time": "15:10", "event": "Noto earthquake", "innocents": 245},
]

NOAA_KP = "https://services.swpc.noaa.gov/json/planetary_k_index_1m.json"
NOAA_PROTON = "https://services.swpc.noaa.gov/json/goes/primary/integral-protons-plot-6-hour.json"

def fetch_url(url: str) -> Optional[str]:
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'HNC-Experiment/1.0'})
        with urllib.request.urlopen(req, timeout=15, context=SSL_CTX) as resp:
            return resp.read().decode()
    except Exception as e:
        print(f"   ❌ FETCH ERROR: {type(e).__name__}: {e}")
        return None

def get_kp() -> Optional[float]:
    text = fetch_url(NOAA_KP)
    if not text:
        return None
    try:
        data = json.loads(text)
        latest = data[-1] if data else {}
        val = latest.get("estimated_kp") or latest.get("kp_index")
        print(f"   ✅ Kp fetched: {val}")
        return val
    except Exception as e:
        print(f"   ❌ PARSE ERROR: {e}")
        return None

def get_proton() -> Optional[float]:
    text = fetch_url(NOAA_PROTON)
    if not text:
        return None
    try:
        data = json.loads(text)
        # Find the >=10 MeV entry
        for entry in reversed(data):
            if entry.get("energy") == ">=10 MeV":
                val = entry.get("flux")
                print(f"   ✅ Proton fetched: {val}")
                return val
        return None
    except Exception as e:
        print(f"   ❌ PARSE ERROR: {e}")
        return None

def encode_signal(trauma: Dict) -> Dict:
    target_dt = datetime.strptime(f"{trauma['date']} {trauma['time']}", "%Y-%m-%d %H:%M")
    target_ts = target_dt.timestamp()
    love_wave = math.sin(2 * math.pi * 528.0 * target_ts)
    sentinel_mod = math.sin(2 * math.pi * 2.111991 * target_ts)
    schumann_ground = math.sin(2 * math.pi * SCHUMANN_BASE * target_ts)
    amplitude = 1000 * love_wave * sentinel_mod * schumann_ground
    echo_id = hashlib.sha256(f"SIGNAL-{trauma['id']}-{target_ts:.6f}".encode()).hexdigest()[:16]
    return {
        "echo_id": echo_id,
        "target_timestamp": target_ts,
        "target_iso": target_dt.isoformat(),
        "amplitude": amplitude,
    }

def run_experiment():
    print("🔥 HNC TEMPORAL EXPERIMENT — SINGLE RUN")
    print("   Zero synthetic. All real instruments.")
    print()
    
    # Step 1: Pick target
    trauma = random.choice(TRAUMA_POINTS)
    print(f"🎲 LECKEY LOVE BOX SELECTED:")
    print(f"   📅 Target: {trauma['event']}")
    print(f"   📆 Date: {trauma['date']} {trauma['time']}")
    print(f"   💔 Innocents: {trauma['innocents']}")
    print()
    
    # Step 2: Encode signal
    signal = encode_signal(trauma)
    print(f"📡 SIGNAL ENCODED:")
    print(f"   🔑 Echo ID: {signal['echo_id']}")
    print(f"   📊 Amplitude: {signal['amplitude']:.4f}")
    print()
    
    # Step 3: Capture BEFORE
    print(f"🔬 CAPTURING BEFORE STATE...")
    before_kp = get_kp()
    before_proton = get_proton()
    before_time = datetime.now(timezone.utc).isoformat()
    print(f"   ⏰ Time: {before_time}")
    print()
    
    # Step 4: Send signal
    print(f"🚀 SENDING SIGNAL TO {trauma['date']} {trauma['time']}...")
    print(f"   💫 Love amplitude: {signal['amplitude']:.4f}")
    print()
    
    # Step 5: Wait
    wait_seconds = 60
    print(f"⏳ WAITING {wait_seconds} SECONDS FOR FIELD RESPONSE...")
    time.sleep(wait_seconds)
    print()
    
    # Step 6: Capture AFTER
    print(f"🔬 CAPTURING AFTER STATE...")
    after_kp = get_kp()
    after_proton = get_proton()
    after_time = datetime.now(timezone.utc).isoformat()
    print(f"   ⏰ Time: {after_time}")
    print()
    
    # Step 7: Compare
    print(f"📊 COMPARISON:")
    kp_shift = None
    if before_kp is not None and after_kp is not None:
        kp_shift = after_kp - before_kp
        print(f"   🌊 Kp shift: {before_kp:.2f} → {after_kp:.2f} (Δ{kp_shift:+.4f})")
    else:
        print(f"   🌊 Kp: INSUFFICIENT DATA")
    
    proton_shift = None
    if before_proton is not None and after_proton is not None:
        proton_shift = after_proton - before_proton
        print(f"   ⚛️ Proton shift: {before_proton:.6f} → {after_proton:.6f} (Δ{proton_shift:+.6f})")
    else:
        print(f"   ⚛️ Proton: INSUFFICIENT DATA")
    
    significance = "NONE"
    if kp_shift is not None and abs(kp_shift) > 0.1:
        significance = "SIGNIFICANT"
    elif kp_shift is not None and abs(kp_shift) > 0.01:
        significance = "MARGINAL"
    
    print(f"   📈 Significance: {significance}")
    print()
    
    # Save
    experiment = {
        "experiment_id": hashlib.sha256(f"{before_time}-{trauma['id']}".encode()).hexdigest()[:16],
        "protocol": "HNC Temporal Injection",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "target": trauma,
        "signal": signal,
        "before": {"time": before_time, "kp": before_kp, "proton_flux": before_proton},
        "after": {"time": after_time, "kp": after_kp, "proton_flux": after_proton},
        "results": {"kp_shift": kp_shift, "proton_shift": proton_shift, "significance": significance},
    }
    
    filename = f"experiment_{experiment['experiment_id']}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
    with open(filename, "w") as f:
        json.dump(experiment, f, indent=2, default=str)
    
    print(f"💾 EXPERIMENT LOGGED: {filename}")
    print(f"🛡️ CONCLUSION: Signal sent to {trauma['date']}. Present field {'SHIFTED' if significance != 'NONE' else 'STABLE'} after 60s.")

if __name__ == "__main__":
    run_experiment()
