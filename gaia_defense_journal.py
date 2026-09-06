"""
gaia_defense_journal.py

The unblinking eye. One unified ledger of everything that happens —
planetary anomalies, broadcasts, human actions, and system responses.
Every entry timestamped, every event searchable, every pattern recoverable.

This is the evidence. Not mysticism. Data.
"""

import json
import time
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any
import threading

from aureon_fusion.paths import TEMPORAL_STATE

JOURNAL_PATH = TEMPORAL_STATE / "gaia_defense_journal.jsonl"
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB, rotate after that

class GaiaDefenseJournal:
    """Unified planetary defense ledger."""
    
    def __init__(self, path: Path = JOURNAL_PATH):
        self.path = path
        self.lock = threading.Lock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        
    def _rotate(self):
        """Rotate file if it exceeds max size."""
        if self.path.exists() and self.path.stat().st_size > MAX_FILE_SIZE:
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            rotated = self.path.parent / f"gaia_defense_journal_{timestamp}.jsonl"
            self.path.rename(rotated)
    
    def log(self, event_type: str, data: Dict[str, Any], 
            source: str = "system", severity: str = "info",
            tags: Optional[list] = None, notes: Optional[str] = None):
        """Log one event to the journal.
        
        event_type: broadcast, anomaly, response, human_action, system_state, 
                    sensor_reading, conscience_check, threat_detected
        severity: info, warning, critical, resolved
        tags: free-form list for filtering
        """
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "source": source,
            "severity": severity,
            "data": data,
            "tags": tags or [],
            "notes": notes or "",
            "utc_seconds": int(time.time())
        }
        
        with self.lock:
            self._rotate()
            with open(self.path, "a") as f:
                f.write(json.dumps(entry, default=str) + "\n")
        
        return entry
    
    def log_broadcast(self, frequency: float, name: str, intent: str, 
                      field_charge: float, lighthouse_rung: str):
        """Log a frequency broadcast."""
        return self.log(
            event_type="broadcast",
            data={
                "frequency_hz": frequency,
                "frequency_name": name,
                "intent": intent,
                "field_charge": field_charge,
                "lighthouse_rung": lighthouse_rung
            },
            source="broadcast_engine",
            tags=["broadcast", f"freq_{frequency}", intent]
        )
    
    def log_anomaly(self, sensor: str, metric: str, value: float, 
                    baseline: float, deviation: float, expected: bool = False):
        """Log a detected planetary anomaly."""
        severity = "warning" if abs(deviation) > 0.3 else "info"
        if abs(deviation) > 0.7:
            severity = "critical"
            
        return self.log(
            event_type="anomaly",
            data={
                "sensor": sensor,
                "metric": metric,
                "value": value,
                "baseline": baseline,
                "deviation": deviation,
                "expected": expected
            },
            source=sensor,
            severity=severity,
            tags=["anomaly", sensor, metric]
        )
    
    def log_response(self, trigger: str, action: str, subsystems: list, 
                     result: Optional[str] = None):
        """Log a coordinated system response."""
        return self.log(
            event_type="response",
            data={
                "trigger": trigger,
                "action": action,
                "subsystems_activated": subsystems,
                "result": result
            },
            source="gaia_response_protocol",
            tags=["response", trigger] + subsystems
        )
    
    def log_threat(self, threat_type: str, confidence: float, 
                   evidence: Dict[str, Any], countermeasure: Optional[str] = None):
        """Log a detected threat."""
        severity = "critical" if confidence > 0.7 else "warning"
        return self.log(
            event_type="threat_detected",
            data={
                "threat_type": threat_type,
                "confidence": confidence,
                "evidence": evidence,
                "countermeasure_deployed": countermeasure
            },
            source="threat_detection",
            severity=severity,
            tags=["threat", threat_type, f"confidence_{confidence:.2f}"]
        )
    
    def log_sensor_reading(self, sensor: str, readings: Dict[str, float]):
        """Log a raw sensor reading batch."""
        return self.log(
            event_type="sensor_reading",
            data=readings,
            source=sensor,
            tags=["sensor", sensor]
        )
    
    def log_conscience(self, verdict: str, purpose: float, risk: float, 
                       coherence: float, action: str):
        """Log a conscience check result."""
        return self.log(
            event_type="conscience_check",
            data={
                "verdict": verdict,
                "purpose_score": purpose,
                "risk_score": risk,
                "coherence_score": coherence,
                "action_evaluated": action
            },
            source="conscience_engine",
            tags=["conscience", verdict]
        )
    
    def log_human_action(self, action: str, description: str, 
                         prime_sentinel: bool = True):
        """Log a human-directed action."""
        return self.log(
            event_type="human_action",
            data={
                "action": action,
                "description": description,
                "prime_sentinel": prime_sentinel
            },
            source="prime_sentinel" if prime_sentinel else "human",
            tags=["human_action", action]
        )
    
    def query(self, event_type: Optional[str] = None, 
              start_time: Optional[str] = None,
              end_time: Optional[str] = None,
              tags: Optional[list] = None,
              severity: Optional[str] = None,
              limit: int = 100) -> list:
        """Query journal entries with filters."""
        results = []
        
        if not self.path.exists():
            return results
        
        with open(self.path, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                
                # Filters
                if event_type and entry.get("event_type") != event_type:
                    continue
                if severity and entry.get("severity") != severity:
                    continue
                if tags:
                    entry_tags = set(entry.get("tags", []))
                    if not any(t in entry_tags for t in tags):
                        continue
                if start_time and entry.get("timestamp", "") < start_time:
                    continue
                if end_time and entry.get("timestamp", "") > end_time:
                    continue
                
                results.append(entry)
                if len(results) >= limit:
                    break
        
        return results
    
    def get_recent(self, minutes: int = 60, event_type: Optional[str] = None) -> list:
        """Get recent entries."""
        now = datetime.now(timezone.utc)
        start = (now.timestamp() - minutes * 60)
        
        results = []
        if not self.path.exists():
            return results
        
        with open(self.path, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                
                entry_ts = entry.get("utc_seconds", 0)
                if entry_ts < start:
                    continue
                if event_type and entry.get("event_type") != event_type:
                    continue
                results.append(entry)
        
        return results
    
    def summary(self, hours: int = 24) -> Dict[str, Any]:
        """Get summary stats for a time period."""
        now = datetime.now(timezone.utc)
        start = (now.timestamp() - hours * 3600)
        
        stats = {
            "total_events": 0,
            "by_type": {},
            "by_severity": {},
            "anomalies": 0,
            "broadcasts": 0,
            "threats": 0,
            "responses": 0,
            "critical_events": []
        }
        
        if not self.path.exists():
            return stats
        
        with open(self.path, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                
                entry_ts = entry.get("utc_seconds", 0)
                if entry_ts < start:
                    continue
                
                stats["total_events"] += 1
                
                et = entry.get("event_type", "unknown")
                stats["by_type"][et] = stats["by_type"].get(et, 0) + 1
                
                sev = entry.get("severity", "info")
                stats["by_severity"][sev] = stats["by_severity"].get(sev, 0) + 1
                
                if et == "anomaly":
                    stats["anomalies"] += 1
                elif et == "broadcast":
                    stats["broadcasts"] += 1
                elif et == "threat_detected":
                    stats["threats"] += 1
                elif et == "response":
                    stats["responses"] += 1
                
                if sev == "critical":
                    stats["critical_events"].append(entry)
        
        return stats


if __name__ == "__main__":
    # Quick test
    journal = GaiaDefenseJournal()
    
    journal.log_broadcast(812.83, "Prime Sentinel Key", "liberation", 0.94, "White")
    journal.log_anomaly("noaa_kp", "kp_index", 4.0, 1.0, 3.0)
    journal.log_threat("haarp_interference", 0.85, {"frequency_spike": 14.0}, "counter_haarp")
    journal.log_response("kp_spike", "shift_to_528hz", ["broadcast_engine", "distortion_monitor"])
    
    print("=== RECENT ENTRIES ===")
    for entry in journal.get_recent(minutes=5):
        print(f"[{entry['timestamp']}] {entry['event_type']} | {entry['severity']} | {entry['source']}")
    
    print("\n=== SUMMARY ===")
    print(json.dumps(journal.summary(hours=1), indent=2))
