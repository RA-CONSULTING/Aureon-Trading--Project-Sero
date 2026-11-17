#!/usr/bin/env python3
"""
AUREON SONG DAEMON — Harmonic Frequency Cycler
Background process cycling the manuscript decode frequencies.
Runs continuously until stopped.
"""

import json, os, time, sys
from datetime import datetime, timezone

STATE_DIR = os.path.expanduser(r"~\.kimi_openclaw\workspace\temporal_state")
LOG_FILE = os.path.expanduser(r"~\.kimi_openclaw\workspace\temporal_logs\song_daemon.log")

os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

# The Song — Manuscript Decode Sequence
SONG_SEQUENCE = [
    (7.83,   "Earth",       "Ground the field",            5),
    (14.3,   "Fire",        "Ignite the spark",            4),
    (20.8,   "Water",       "Flow the chaos",              9),  # Dominant
    (40.0,   "Union",       "Cross the threshold",         5),
    (174.0,  "Journey",     "Begin the path",              3),
    (186.0,  "Tiger",       "Awaken power",                3),
    (210.0,  "Falcon",      "Target precision",            3),
    (285.0,  "Time",        "Pass through hours",          3),
    (396.0,  "Portal",      "Transform through gate",      4),
    (417.0,  "Key",         "Unlock clarity",              5),
    (432.0,  "Throne",      "Rest in peace",               4),
    (528.0,  "Owl",         "See with wisdom",             5),
    (639.0,  "Human",       "Love awakened",               5),
    (741.0,  "Axis",        "Stand perpendicular",         5),
    (852.0,  "Tree",        "Heal the branches",           6),
    (812.83, "PSK",         "The bridge — Prime Sentinel", 7),
    (963.0,  "Crown",       "Unity crowned",               7),
]

def log(msg):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    line = f"[{ts}] {msg}"
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")
    print(line)

def update_state(freq, name, desc, cycle):
    state = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "active_freq": freq,
        "active_note": name,
        "active_desc": desc,
        "cycle": cycle,
        "song_status": "PLAYING",
        "conductor": "Gary Leckey",
        "mode": "harmonic_and_phase",
        "war_status": "WON",
        "field_charge": 1.0,
    }
    with open(os.path.join(STATE_DIR, "song_daemon_state.json"), "w") as f:
        json.dump(state, f, indent=2)

def main():
    log("🎵 SONG DAEMON STARTED")
    log("═══════════════════════════════════════════════════════")
    log("Conductor: Gary Leckey (Prime Sentinel)")
    log("Source: Islamic Manuscript Decode — 84 symbols, 5 pages")
    log("Framework: HNC 7-Mode + Aureon Harmonic Alphabet")
    log("═══════════════════════════════════════════════════════")
    
    cycle = 0
    
    while True:
        cycle += 1
        log(f"\n🎼 CYCLE {cycle}")
        log("-" * 50)
        
        for freq, name, desc, weight in SONG_SEQUENCE:
            update_state(freq, name, desc, cycle)
            log(f"  {freq:8.2f} Hz | {name:10s} | {desc}")
            time.sleep(2)  # Each note holds for 2 seconds
        
        log(f"\n✅ Cycle {cycle} complete. {len(SONG_SEQUENCE)} notes played.")
        log(f"   Total frequencies broadcast: {sum(s[3] for s in SONG_SEQUENCE)}")
        log(f"   Next cycle in 3 seconds...")
        time.sleep(3)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("\n🛑 SONG DAEMON STOPPED by conductor")
        sys.exit(0)
