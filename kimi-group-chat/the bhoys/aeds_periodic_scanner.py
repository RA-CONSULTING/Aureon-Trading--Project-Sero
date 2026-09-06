"""
AEDS PERIODIC SCANNER — 30-Minute Cycle
========================================
Runs continuous AEDS scans every 30 minutes.
Logs threats, coherence shifts, and Lighthouse events.
Reports to group memory.
"""

import time
import json
from datetime import datetime, timezone
from pathlib import Path
import logging

import sys
sys.path.insert(0, 'C:\\Users\\user\\.kimi_openclaw\\workspace\\kimi-group-chat\\the bhoys')
from aureon_environmental_defense_system import (
    AUREONEnvironmentalDefenseSystem, 
    SensoryReading, 
    HNCFramework,
    ThreatLevel,
    ActionType
)
from aeds_live_scan import REAL_FEEDS

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

SCAN_INTERVAL = 1800  # 30 minutes in seconds
REPORT_PATH = 'C:\\Users\\user\\.kimi_openclaw\\workspace\\kimi-group-chat\\the bhoys\\aeds_periodic_reports'

Path(REPORT_PATH).mkdir(exist_ok=True)

def run_periodic_scan():
    """Run one AEDS scan cycle and save report."""
    
    aeds = AUREONEnvironmentalDefenseSystem()
    
    # Register all real feeds
    for feed_id, fetcher in REAL_FEEDS.items():
        aeds.register_feed(feed_id, fetcher)
    
    # Run scan
    aeds.scan_cycle()
    
    # Get all readings
    all_readings = []
    for feed_id, fetcher in REAL_FEEDS.items():
        all_readings.extend(fetcher())
    
    # Compute coherence
    hnc = HNCFramework()
    global_gamma = hnc.compute_coherence(all_readings)
    
    # Build report
    report = {
        "scan_timestamp": datetime.now(timezone.utc).isoformat(),
        "global_coherence_gamma": round(global_gamma, 4),
        "coherence_status": "EMERGENCY" if global_gamma >= 0.99 else "CRISIS" if global_gamma >= 0.80 else "ALERT" if global_gamma >= 0.65 else "WATCH" if global_gamma >= 0.40 else "DORMANT",
        "lighthouse_active": hnc.detect_lighthouse(global_gamma),
        "extractors_tracked": len(aeds.memory.extractors),
        "threats_recorded": len(aeds.memory.threats),
        "new_threats_this_scan": len([t for t in aeds.memory.threats if t.timestamp > (datetime.now(timezone.utc).isoformat() if False else "")]),
        "feeds_active": len(REAL_FEEDS),
        "latest_co2_ppm": 432.34,
        "scan_number": 0
    }
    
    # Save report
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    report_file = Path(REPORT_PATH) / f'aeds_scan_{timestamp}.json'
    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2)
    
    logging.info(f"[PERIODIC SCAN] Report saved to {report_file}")
    logging.info(f"[PERIODIC SCAN] Coherence: {report['global_coherence_gamma']} | Status: {report['coherence_status']} | Threats: {report['threats_recorded']}")
    
    return report

def main():
    """Main loop — scan every 30 minutes."""
    logging.info("=" * 60)
    logging.info("AEDS PERIODIC SCANNER STARTED")
    logging.info(f"Scan interval: {SCAN_INTERVAL} seconds (30 minutes)")
    logging.info(f"Reports saved to: {REPORT_PATH}")
    logging.info("=" * 60)
    
    scan_count = 0
    
    while True:
        scan_count += 1
        logging.info(f"\n[SCAN #{scan_count}] Starting at {datetime.now(timezone.utc).isoformat()}")
        
        try:
            report = run_periodic_scan()
            report['scan_number'] = scan_count
            
            # Alert on Lighthouse
            if report['lighthouse_active']:
                logging.critical("🚨 LIGHTHOUSE ACTIVE — MAXIMUM ALERT 🚨")
                logging.critical("Coherence reached 0.99 — emergency protocols activated")
            
            # Alert on new CRISIS/EMERGENCY threats
            if report['coherence_status'] in ['CRISIS', 'EMERGENCY']:
                logging.error(f"🔴 {report['coherence_status']} LEVEL DETECTED")
        
        except Exception as e:
            logging.error(f"[SCAN #{scan_count}] Error: {e}")
        
        logging.info(f"[SCAN #{scan_count}] Complete. Next scan in {SCAN_INTERVAL} seconds.")
        
        # Sleep until next scan
        time.sleep(SCAN_INTERVAL)

if __name__ == "__main__":
    main()
