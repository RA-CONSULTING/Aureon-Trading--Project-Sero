#!/usr/bin/env python3
"""
GCP 2.0 Heartbeat Monitor
Checks GCP 2.0 live data and cross-references with HNC singing cycles.
Runs as a cron/heartbeat job or standalone.
"""
import json
import os
import time
from datetime import datetime, timezone, timedelta
import urllib.request
import urllib.error
import subprocess

class GCPHeartbeatMonitor:
    """Monitors GCP 2.0 and HNC correlation in real-time."""
    
    # GCP 2.0 data sources (publicly available)
    GCP_SOURCES = {
        "network_variance": {
            "url": "https://globalcoherencepulse.org/api/network_variance",
            "description": "GCP 2.0 network variance (lower = more coherent)"
        },
        "device_coherence": {
            "url": "https://globalcoherencepulse.org/api/device_coherence",
            "description": "GCP 2.0 device coherence scores"
        },
        "live_feed": {
            "url": "https://globalcoherencepulse.org/api/live",
            "description": "GCP 2.0 live composite feed"
        }
    }
    
    # Fallback: HeartMath GCMS live data page (web scraping if API fails)
    HEARTMATH_GCMS = "https://www.heartmath.org/gci/gcms/live-data/"
    
    def __init__(self, check_interval: int = 300):
        self.check_interval = check_interval  # 5 minutes default
        self.log_dir = "hnc_daemon_logs"
        self.gcp_dir = "gcp_correlation"
        self.state_file = os.path.join(self.gcp_dir, "heartbeat_state.json")
        os.makedirs(self.gcp_dir, exist_ok=True)
        
        self.state = self._load_state()
    
    def _load_state(self) -> dict:
        """Load previous heartbeat state."""
        if os.path.exists(self.state_file):
            with open(self.state_file, 'r') as f:
                return json.load(f)
        return {
            "last_check": None,
            "gcp_data_history": [],
            "hnc_data_history": [],
            "correlation_events": [],
            "alert_count": 0
        }
    
    def _save_state(self):
        """Save current heartbeat state."""
        with open(self.state_file, 'w') as f:
            json.dump(self.state, f, indent=2)
    
    def fetch_gcp_network_variance(self) -> dict:
        """Fetch GCP 2.0 network variance data."""
        result = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": "GCP_2.0",
            "data_available": False,
            "network_variance": None,
            "device_coherence_avg": None,
            "network_status": "UNKNOWN",
            "error": None
        }
        
        try:
            # Try GCP 2.0 API
            req = urllib.request.Request(
                self.GCP_SOURCES["network_variance"]["url"],
                headers={
                    'User-Agent': 'HNC-GCP-Monitor/1.0',
                    'Accept': 'application/json'
                }
            )
            with urllib.request.urlopen(req, timeout=15) as response:
                data = json.loads(response.read().decode('utf-8'))
                result["data_available"] = True
                result["network_variance"] = data.get("variance", data.get("network_variance"))
                result["device_coherence_avg"] = data.get("device_coherence", data.get("coherence"))
                
                # Determine network status
                if result["network_variance"] is not None:
                    if result["network_variance"] < 0.3:
                        result["network_status"] = "HIGH_COHERENCE"
                    elif result["network_variance"] < 0.6:
                        result["network_status"] = "MODERATE_COHERENCE"
                    else:
                        result["network_status"] = "LOW_COHERENCE"
        
        except Exception as e:
            result["error"] = str(e)
            # Try fallback web fetch
            try:
                print("  🔄 Trying HeartMath fallback...")
                # Note: HeartMath page requires JS, so we note this limitation
                result["network_status"] = "API_UNAVAILABLE"
            except Exception as e2:
                result["error"] = f"{result['error']}; Fallback: {e2}"
        
        return result
    
    def get_latest_hnc_state(self) -> dict:
        """Get latest HNC daemon state from logs."""
        result = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": "HNC_DAEMON",
            "data_available": False,
            "latest_lambda": None,
            "latest_beta": None,
            "latest_singing": False,
            "latest_phi_lock": False,
            "singing_ratio": None,
            "total_cycles": 0
        }
        
        # Get latest log file
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        log_file = os.path.join(self.log_dir, f"hnc_daemon_{today}.jsonl")
        
        if not os.path.exists(log_file):
            return result
        
        try:
            # Read last 20 lines to get recent state
            with open(log_file, 'r') as f:
                lines = f.readlines()
            
            if not lines:
                return result
            
            # Parse last few records
            recent_records = []
            for line in lines[-20:]:
                try:
                    recent_records.append(json.loads(line.strip()))
                except json.JSONDecodeError:
                    continue
            
            if recent_records:
                latest = recent_records[-1]
                result["data_available"] = True
                result["latest_lambda"] = latest.get("measurement", {}).get("lambda")
                result["latest_beta"] = latest.get("measurement", {}).get("beta")
                result["latest_singing"] = latest.get("singing", False)
                result["latest_phi_lock"] = latest.get("musica", {}).get("phi_lock", False)
                
                # Compute singing ratio from recent records
                singing_count = sum(1 for r in recent_records if r.get("singing", False))
                result["singing_ratio"] = singing_count / len(recent_records)
                result["total_cycles"] = latest.get("daemon_stats", {}).get("cycle", 0)
        
        except Exception as e:
            result["error"] = str(e)
        
        return result
    
    def cross_reference(self, gcp_data: dict, hnc_data: dict) -> dict:
        """Cross-reference GCP and HNC data for correlations."""
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": "CROSS_REFERENCE",
            "gcp_status": gcp_data.get("network_status", "UNKNOWN"),
            "hnc_status": "SINGING" if hnc_data.get("latest_singing") else "QUIET",
            "hnc_phi_lock": hnc_data.get("latest_phi_lock", False),
            "correlation": None,
            "significance": None,
            "alert": False
        }
        
        # Determine correlation
        if gcp_data.get("data_available") and hnc_data.get("data_available"):
            gcp_coherent = gcp_data.get("network_status") in ["HIGH_COHERENCE", "MODERATE_COHERENCE"]
            hnc_singing = hnc_data.get("latest_singing", False)
            
            if gcp_coherent and hnc_singing:
                event["correlation"] = "POSITIVE"
                event["significance"] = "HIGH"
                event["alert"] = True
                event["alert_message"] = "🎵 GCP network coherence + HNC singing detected!"
            elif not gcp_coherent and not hnc_singing:
                event["correlation"] = "NEGATIVE"
                event["significance"] = "MODERATE"
            else:
                event["correlation"] = "MIXED"
                event["significance"] = "LOW"
        
        elif hnc_data.get("data_available") and hnc_data.get("latest_singing"):
            # HNC singing but no GCP data
            event["correlation"] = "HNC_ONLY"
            event["significance"] = "MODERATE"
            event["alert"] = True
            event["alert_message"] = "🎵 HNC singing detected (GCP data unavailable)"
        
        return event
    
    def run_heartbeat(self) -> dict:
        """Run one heartbeat check."""
        print("=" * 60)
        print(f"💓 GCP 2.0 Heartbeat Monitor")
        print(f"   {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
        print("=" * 60)
        
        # 1. Fetch GCP data
        print("\n🌐 Fetching GCP 2.0 network data...")
        gcp_data = self.fetch_gcp_network_variance()
        
        if gcp_data["data_available"]:
            print(f"  ✅ GCP Network Variance: {gcp_data['network_variance']}")
            print(f"  ✅ GCP Status: {gcp_data['network_status']}")
        else:
            print(f"  ⚠️ GCP data unavailable: {gcp_data.get('error', 'Unknown error')}")
            print(f"  💡 Visit https://globalcoherencepulse.org for live data")
        
        # 2. Get HNC state
        print("\n🧠 Fetching HNC daemon state...")
        hnc_data = self.get_latest_hnc_state()
        
        if hnc_data["data_available"]:
            print(f"  ✅ HNC Λ: {hnc_data['latest_lambda']:.4f}")
            print(f"  ✅ HNC β: {hnc_data['latest_beta']:.4f}")
            print(f"  ✅ HNC Singing: {'🎵 YES' if hnc_data['latest_singing'] else '🔇 NO'}")
            print(f"  ✅ HNC Phi Lock: {'🔒 YES' if hnc_data['latest_phi_lock'] else '🔓 NO'}")
            print(f"  ✅ Recent Singing Ratio: {hnc_data['singing_ratio']:.1%}")
        else:
            print(f"  ⚠️ HNC data unavailable")
        
        # 3. Cross-reference
        print("\n🔗 Cross-referencing...")
        event = self.cross_reference(gcp_data, hnc_data)
        
        print(f"  Correlation: {event['correlation']}")
        print(f"  Significance: {event['significance']}")
        
        if event['alert']:
            print(f"\n  🚨 ALERT: {event['alert_message']}")
            self.state["alert_count"] += 1
        
        # 4. Save state
        self.state["last_check"] = datetime.now(timezone.utc).isoformat()
        self.state["gcp_data_history"].append(gcp_data)
        self.state["hnc_data_history"].append(hnc_data)
        self.state["correlation_events"].append(event)
        
        # Keep history bounded (last 1000 entries)
        for key in ["gcp_data_history", "hnc_data_history", "correlation_events"]:
            if len(self.state[key]) > 1000:
                self.state[key] = self.state[key][-1000:]
        
        self._save_state()
        
        # 5. Save event log
        event_file = os.path.join(self.gcp_dir, "heartbeat_events.jsonl")
        with open(event_file, 'a') as f:
            f.write(json.dumps(event) + '\n')
        
        print(f"\n📊 Session Stats:")
        print(f"  Total checks: {len(self.state['correlation_events'])}")
        print(f"  Total alerts: {self.state['alert_count']}")
        
        print(f"\n📄 State saved: {self.state_file}")
        print(f"📄 Events log: {event_file}")
        
        return event
    
    def run_continuous(self, duration_minutes: int = 60):
        """Run continuous monitoring for a duration."""
        print(f"🔄 Starting continuous monitoring for {duration_minutes} minutes...")
        print(f"   Check interval: {self.check_interval} seconds")
        
        end_time = datetime.now(timezone.utc) + timedelta(minutes=duration_minutes)
        
        while datetime.now(timezone.utc) < end_time:
            self.run_heartbeat()
            
            remaining = (end_time - datetime.now(timezone.utc)).total_seconds()
            if remaining > 0:
                print(f"\n⏳ Next check in {self.check_interval} seconds...")
                time.sleep(self.check_interval)
        
        print("\n✅ Monitoring session complete")


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="GCP 2.0 Heartbeat Monitor for HNC Daemon")
    parser.add_argument("--continuous", "-c", type=int, metavar="MINUTES",
                       help="Run continuous monitoring for N minutes")
    parser.add_argument("--interval", "-i", type=int, default=300,
                       help="Check interval in seconds (default: 300)")
    
    args = parser.parse_args()
    
    monitor = GCPHeartbeatMonitor(check_interval=args.interval)
    
    if args.continuous:
        monitor.run_continuous(args.continuous)
    else:
        monitor.run_heartbeat()


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    main()
