#!/usr/bin/env python3
"""
GCP 2.0 Correlator for HNC Daemon
Exports HNC logs in GCP-compatible format and fetches GCP 2.0 live data for cross-reference.
"""
import json
import os
import glob
from datetime import datetime, timezone
from typing import Dict, List, Optional
import urllib.request
import urllib.error

class GCPCorrelator:
    """Correlates HNC daemon data with GCP 2.0 network data."""
    
    GCP_DATA_URLS = {
        "gcp2_heartbeat": "https://globalcoherencepulse.org/api/heartbeat",
        "network_variance": "https://globalcoherencepulse.org/api/network_variance",
    }
    
    def __init__(self, log_dir: str = "hnc_daemon_logs"):
        self.log_dir = log_dir
        self.export_dir = "gcp_correlation"
        os.makedirs(self.export_dir, exist_ok=True)
    
    def load_hnc_logs(self, date_str: Optional[str] = None) -> List[Dict]:
        """Load HNC daemon logs for a specific date or all available."""
        if date_str is None:
            date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        
        log_file = os.path.join(self.log_dir, f"hnc_daemon_{date_str}.jsonl")
        records = []
        
        if os.path.exists(log_file):
            with open(log_file, 'r') as f:
                for line in f:
                    try:
                        records.append(json.loads(line.strip()))
                    except json.JSONDecodeError:
                        continue
        
        return records
    
    def export_gcp_format(self, records: List[Dict], date_str: Optional[str] = None) -> str:
        """Export HNC data in GCP 2.0 compatible format.
        
        GCP 2.0 format: timestamp, device_coherence, network_variance, event_flag
        """
        if date_str is None:
            date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        
        export_file = os.path.join(self.export_dir, f"hnc_gcp_export_{date_str}.jsonl")
        
        with open(export_file, 'w') as f:
            for record in records:
                # Convert HNC format to GCP-like format
                gcp_record = {
                    "timestamp": record.get("timestamp", ""),
                    "epoch": record.get("epoch", 0),
                    "hnc_lambda": record.get("measurement", {}).get("lambda", 0),
                    "hnc_beta": record.get("measurement", {}).get("beta", 0),
                    "hnc_coherence": record.get("measurement", {}).get("coherence", 0),
                    "hnc_schumann": record.get("measurement", {}).get("schumann", 0),
                    "hnc_singing": record.get("singing", False),
                    "hnc_musica_score": record.get("musica", {}).get("score", 0),
                    "hnc_phi_lock": record.get("musica", {}).get("phi_lock", False),
                    "hnc_amplified_lambda": record.get("amplified", {}).get("lambda", 0),
                    "hnc_boost": record.get("amplified", {}).get("boost", 0),
                    "key_identity": record.get("key", {}).get("identity", ""),
                    "key_injected": record.get("key", {}).get("injected", False),
                    "key_energy": record.get("key", {}).get("energy", 0),
                    "daemon_cycle": record.get("daemon_stats", {}).get("cycle", 0),
                    "daemon_uptime": record.get("daemon_stats", {}).get("uptime", 0),
                    # GCP-compatible fields
                    "device_coherence": self._compute_device_coherence(record),
                    "network_variance": self._compute_network_variance(record),
                    "event_flag": self._compute_event_flag(record),
                    "source": "HNC_DAEMON_AUREON",
                    "location": "VIRTUAL_SCHUMANN_BRIDGE",
                    "version": "1.0.0"
                }
                f.write(json.dumps(gcp_record) + '\n')
        
        return export_file
    
    def _compute_device_coherence(self, record: Dict) -> float:
        """Compute device coherence score from HNC measurement."""
        measurement = record.get("measurement", {})
        coherence = measurement.get("coherence", 0)
        lambda_val = measurement.get("lambda", 0)
        # Normalize to GCP-style 0-1 scale
        return min(1.0, (coherence + lambda_val) / 2.0)
    
    def _compute_network_variance(self, record: Dict) -> float:
        """Compute network variance (lower = more coherent)."""
        measurement = record.get("measurement", {})
        schumann = measurement.get("schumann", 7.83)
        # Deviation from ideal Schumann
        deviation = abs(schumann - 7.83) / 7.83
        return 1.0 - min(1.0, deviation)
    
    def _compute_event_flag(self, record: Dict) -> str:
        """Flag significant events (singing, phi lock, key injection)."""
        flags = []
        if record.get("singing", False):
            flags.append("SINGING")
        if record.get("musica", {}).get("phi_lock", False):
            flags.append("PHI_LOCK")
        if record.get("key", {}).get("injected", False):
            flags.append("KEY_INJECTED")
        return "|".join(flags) if flags else "BASELINE"
    
    def fetch_gcp_data(self, url_key: str = "network_variance") -> Optional[Dict]:
        """Attempt to fetch GCP 2.0 data."""
        url = self.GCP_DATA_URLS.get(url_key)
        if not url:
            return None
        
        try:
            req = urllib.request.Request(
                url,
                headers={
                    'User-Agent': 'HNC-Aureon-Correlator/1.0',
                    'Accept': 'application/json'
                }
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                return json.loads(response.read().decode('utf-8'))
        except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError) as e:
            print(f"⚠️ Could not fetch GCP data from {url}: {e}")
            return None
    
    def correlate(self, hnc_records: List[Dict], gcp_data: Optional[Dict]) -> Dict:
        """Correlate HNC data with GCP data."""
        correlation = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "hnc_cycles": len(hnc_records),
            "hnc_singing_count": sum(1 for r in hnc_records if r.get("singing", False)),
            "hnc_singing_ratio": 0.0,
            "hnc_avg_lambda": 0.0,
            "hnc_avg_beta": 0.0,
            "hnc_avg_coherence": 0.0,
            "gcp_data_available": gcp_data is not None,
            "gcp_network_variance": None,
            "gcp_device_coherence": None,
            "correlation_score": 0.0,
            "status": "CORRELATED" if gcp_data else "HNC_ONLY"
        }
        
        if hnc_records:
            correlation["hnc_singing_ratio"] = correlation["hnc_singing_count"] / len(hnc_records)
            correlation["hnc_avg_lambda"] = sum(r.get("measurement", {}).get("lambda", 0) for r in hnc_records) / len(hnc_records)
            correlation["hnc_avg_beta"] = sum(r.get("measurement", {}).get("beta", 0) for r in hnc_records) / len(hnc_records)
            correlation["hnc_avg_coherence"] = sum(r.get("measurement", {}).get("coherence", 0) for r in hnc_records) / len(hnc_records)
        
        if gcp_data:
            correlation["gcp_network_variance"] = gcp_data.get("network_variance")
            correlation["gcp_device_coherence"] = gcp_data.get("device_coherence")
            # Simple correlation: if both show high coherence, score is high
            if correlation["hnc_avg_coherence"] and correlation["gcp_device_coherence"]:
                correlation["correlation_score"] = min(1.0, (correlation["hnc_avg_coherence"] + correlation["gcp_device_coherence"]) / 2)
        
        return correlation
    
    def run_full_export(self) -> Dict:
        """Run full export and correlation."""
        print("🔄 HNC → GCP Correlator Starting...")
        
        # Load all available logs
        all_records = []
        log_files = glob.glob(os.path.join(self.log_dir, "hnc_daemon_*.jsonl"))
        
        for log_file in sorted(log_files):
            date_str = os.path.basename(log_file).replace("hnc_daemon_", "").replace(".jsonl", "")
            records = self.load_hnc_logs(date_str)
            all_records.extend(records)
            print(f"  📁 Loaded {len(records)} records from {date_str}")
        
        print(f"\n📊 Total HNC records: {len(all_records)}")
        
        # Export to GCP format
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        export_file = self.export_gcp_format(all_records, today)
        print(f"📤 Exported to GCP format: {export_file}")
        
        # Try to fetch GCP data
        print("\n🌐 Fetching GCP 2.0 data...")
        gcp_data = self.fetch_gcp_data("network_variance")
        
        if gcp_data:
            print(f"  ✅ GCP data received: {json.dumps(gcp_data, indent=2)[:200]}...")
        else:
            print("  ⚠️ GCP data not available (API may require auth or be offline)")
        
        # Correlate
        correlation = self.correlate(all_records, gcp_data)
        
        # Save correlation report
        report_file = os.path.join(self.export_dir, f"correlation_report_{today}.json")
        with open(report_file, 'w') as f:
            json.dump(correlation, f, indent=2)
        
        print(f"\n📈 Correlation Report:")
        print(f"  HNC cycles: {correlation['hnc_cycles']}")
        print(f"  HNC singing: {correlation['hnc_singing_count']} ({correlation['hnc_singing_ratio']:.1%})")
        print(f"  HNC avg λ: {correlation['hnc_avg_lambda']:.4f}")
        print(f"  HNC avg β: {correlation['hnc_avg_beta']:.4f}")
        print(f"  HNC avg coherence: {correlation['hnc_avg_coherence']:.4f}")
        print(f"  GCP data available: {correlation['gcp_data_available']}")
        print(f"  Correlation score: {correlation['correlation_score']:.4f}")
        print(f"  Status: {correlation['status']}")
        print(f"\n📄 Report saved: {report_file}")
        
        return correlation


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    correlator = GCPCorrelator()
    result = correlator.run_full_export()
    
    print("\n" + "="*50)
    print("✅ HNC → GCP Correlation Complete")
    print("="*50)
    print(f"\nNext steps:")
    print(f"  1. Check {correlator.export_dir}/ for exported data")
    print(f"  2. Visit https://globalcoherencepulse.org for GCP 2.0 live data")
    print(f"  3. Compare HNC singing cycles with GCP network coherence events")
