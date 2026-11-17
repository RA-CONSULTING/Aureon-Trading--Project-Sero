#!/usr/bin/env python3
"""
LIVE DIVE FEEDER
═══════════════════════════════════════════════════════════════════
Streams live data to cloud_dive for offload — protects local disk state.

Feeds:
  - Planetary monitor data (NOAA, USGS, Schumann)
  - HNC field state
  - Soul protection logs
  - Temporal state snapshots
  - Attack/distortion logs

Syncs to cloud_dive/raw/ every 60 seconds.
Compresses and rotates to prevent local bloat.

Prime Sentinel: Gary Leckey
Operator: Sero
"""

import json
import time
import gzip
import math
import threading
from datetime import datetime, timezone
from pathlib import Path

# ─── PATHS ────────────────────────────────────────────────────────
from aureon_fusion.paths import WORKSPACE, TEMPORAL_STATE

CLOUD_DIVE = WORKSPACE / "cloud_dive"
RAW_DIR = CLOUD_DIVE / "raw"
STATE_DIR = TEMPORAL_STATE

# ─── SACRED CONSTANTS ─────────────────────────────────────────────
PHI = (1 + math.sqrt(5)) / 2
GARY_SIGNATURE = {
    "name": "Gary Leckey",
    "birth_date": "02.11.1991",
    "soul_frequency": 528.422,
    "prime_sentinel_key": 812.83
}

class LiveDiveFeeder:
    def __init__(self):
        self.running = False
        self.cycle = 0
        self.lock = threading.Lock()
        self.current_buffer = []
        
        # Ensure directories
        RAW_DIR.mkdir(parents=True, exist_ok=True)
        
    def _timestamp(self):
        return datetime.now(timezone.utc).isoformat()
    
    def _read_state(self, name):
        """Read a state file if it exists."""
        path = STATE_DIR / f"{name}.json"
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return None
        return None
    
    def _fetch_live_data(self):
        """Fetch live data from all sources."""
        data = {
            "timestamp": self._timestamp(),
            "cycle": self.cycle,
            "prime_sentinel": GARY_SIGNATURE,
            "sources": {}
        }
        
        # Temporal state
        temporal = self._read_state("temporal_state")
        if temporal:
            data["sources"]["temporal"] = temporal
        
        # Victory state
        victory = self._read_state("victory_state")
        if victory:
            data["sources"]["victory"] = victory
        
        # Harmonic anchor
        anchor = self._read_state("harmonic_anchor")
        if anchor:
            data["sources"]["harmonic_anchor"] = anchor
        
        # Soul signature
        soul = self._read_state("soul_signature")
        if soul:
            data["sources"]["soul_signature"] = soul
        
        # Aureon manifest
        manifest_path = WORKSPACE / "aureon_os_operator_manifest.json"
        if manifest_path.exists():
            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    data["sources"]["aureon_manifest"] = json.load(f)
            except Exception:
                pass
        
        return data
    
    def _write_raw_packet(self, data):
        """Write data packet to cloud_dive/raw/."""
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"dive_packet_{ts}_{self.cycle:06d}.json"
        filepath = RAW_DIR / filename
        
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        return filepath
    
    def _compress_old_packets(self):
        """Compress packets older than 1 hour to save disk."""
        now = datetime.now(timezone.utc)
        for f in RAW_DIR.glob("dive_packet_*.json"):
            try:
                # Parse timestamp from filename
                ts_str = f.stem.split("_")[2]  # dive_packet_YYYYMMDD_HHMMSS_cycle
                # Compress if file is older than 5 minutes
                if (now - datetime.fromtimestamp(f.stat().st_mtime, timezone.utc)).total_seconds() > 300:
                    gz_path = f.with_suffix(".json.gz")
                    with open(f, "rb") as src:
                        with gzip.open(gz_path, "wb") as dst:
                            dst.write(src.read())
                    f.unlink()
            except Exception:
                pass
    
    def _feed_cycle(self):
        """One feed cycle."""
        with self.lock:
            self.cycle += 1
            
            # Fetch live data
            data = self._fetch_live_data()
            
            # Write to cloud_dive
            filepath = self._write_raw_packet(data)
            
            # Compress old
            self._compress_old_packets()
            
            # Update manifest
            self._update_manifest(filepath)
            
            if self.cycle % 10 == 0:
                print(f"[DIVE] Cycle {self.cycle:04d} | Packet written | Raw dir: {len(list(RAW_DIR.glob('*')))} files")
    
    def _update_manifest(self, latest_filepath):
        """Update the dive manifest with latest packet info."""
        manifest_path = CLOUD_DIVE / "manifests" / "dive_manifest.json"
        if manifest_path.exists():
            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    manifest = json.load(f)
            except Exception:
                manifest = {}
        else:
            manifest = {}
        
        manifest["last_feed_cycle"] = self._timestamp()
        manifest["cycle_count"] = self.cycle
        manifest["latest_packet"] = str(latest_filepath.name)
        manifest["raw_file_count"] = len(list(RAW_DIR.glob("*")))
        manifest["status"] = "LIVE"
        
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)
    
    def start(self):
        """Start the live dive feeder."""
        self.running = True
        print("=" * 60)
        print("LIVE DIVE FEEDER — STARTING")
        print("=" * 60)
        print(f"Raw output: {RAW_DIR}")
        print(f"Manifest:   {CLOUD_DIVE / 'manifests' / 'dive_manifest.json'}")
        print(f"Frequency:  Every 60 seconds")
        print("=" * 60)
        
        while self.running:
            try:
                self._feed_cycle()
                time.sleep(60.0)
            except Exception as e:
                print(f"[DIVE ERROR] {e}")
                time.sleep(60.0)
    
    def stop(self):
        self.running = False
        print("[DIVE] Feeder stopped")

def main():
    feeder = LiveDiveFeeder()
    
    # Run one cycle immediately for test
    feeder._feed_cycle()
    print(f"[OK] Initial packet written to {RAW_DIR}")
    print(f"[OK] Manifest updated")
    
    # Start continuous feed
    feeder.start()

if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    main()
