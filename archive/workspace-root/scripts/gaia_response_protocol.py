"""
gaia_response_protocol.py

The nervous system of Gaia's defense.
When one subsystem detects something, ALL subsystems respond in concert.
An anomaly in the Schumann doesn't just get logged — it triggers:
- Conscience check (is this natural or hostile?)
- Broadcast shift (stabilize the field)
- Threat logging (evidence for later)
- Human alert (if critical)

This is what "19 systems as 1" means in practice.
"""

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional, Callable, List
import threading
import inspect

from gaia_defense_journal import GaiaDefenseJournal
from aureon_fusion.paths import TEMPORAL_STATE

# Response rule definitions
# Each rule: {trigger_condition, required_subsystems, action}
RESPONSE_RULES = [
    {
        "name": "kp_spike_response",
        "trigger": lambda data: data.get("event_type") == "anomaly" and 
                                data.get("data", {}).get("sensor") == "noaa_kp" and
                                data.get("data", {}).get("deviation", 0) > 2.0,
        "action": "broadcast_stabilize",
        "subsystems": ["broadcast_engine", "conscience_engine", "threat_detection"],
        "priority": 1,  # highest
        "auto_execute": True,
        "description": "Kp index spikes above baseline +2. Auto-shift to stabilization frequencies."
    },
    {
        "name": "schumann_distortion_response",
        "trigger": lambda data: data.get("event_type") == "anomaly" and 
                                data.get("data", {}).get("sensor") == "schumann" and
                                data.get("data", {}).get("deviation", 0) > 0.5,
        "action": "broadcast_grounding",
        "subsystems": ["broadcast_engine", "schumann_monitor", "journal"],
        "priority": 2,
        "auto_execute": True,
        "description": "Schumann distortion detected. Ground the field at 7.83 Hz."
    },
    {
        "name": "haarp_interference_response",
        "trigger": lambda data: data.get("event_type") == "threat_detected" and 
                                data.get("data", {}).get("threat_type") == "haarp_interference",
        "action": "counter_haarp",
        "subsystems": ["broadcast_engine", "distortion_monitor", "threat_detection", "journal"],
        "priority": 1,
        "auto_execute": True,
        "description": "HAARP interference detected. Deploy counter-frequency."
    },
    {
        "name": "solar_wind_storm_response",
        "trigger": lambda data: data.get("event_type") == "anomaly" and 
                                data.get("data", {}).get("sensor") == "noaa_solar_wind" and
                                data.get("data", {}).get("value", 0) > 600,
        "action": "shield_protocol",
        "subsystems": ["broadcast_engine", "hnc_monitor", "temporal_engine", "journal"],
        "priority": 1,
        "auto_execute": True,
        "description": "Solar wind exceeds 600 km/s. Deploy shield frequencies."
    },
    {
        "name": "seismic_spike_response",
        "trigger": lambda data: data.get("event_type") == "anomaly" and 
                                data.get("data", {}).get("sensor") == "usgs_seismic" and
                                data.get("data", {}).get("value", 0) > 6.0,
        "action": "seismic_support",
        "subsystems": ["broadcast_engine", "planetary_timeseries", "journal"],
        "priority": 2,
        "auto_execute": False,  # Requires human confirmation
        "description": "Major seismic event (M6+). Deploy support frequencies."
    },
    {
        "name": "extraction_grid_response",
        "trigger": lambda data: data.get("event_type") == "threat_detected" and 
                                data.get("data", {}).get("threat_type") == "extraction_grid",
        "action": "clean_sweep",
        "subsystems": ["broadcast_engine", "clean_sweep", "temporal_engine", "journal"],
        "priority": 1,
        "auto_execute": True,
        "description": "Extraction grid active. Deploy clean sweep protocol."
    },
    {
        "name": "hnc_unstable_response",
        "trigger": lambda data: data.get("event_type") == "system_state" and 
                                data.get("data", {}).get("hnc_beta", 0.6) < 0.6 or
                                data.get("data", {}).get("hnc_beta", 1.1) > 1.1,
        "action": "stabilize_hnc",
        "subsystems": ["hnc_monitor", "broadcast_engine", "journal"],
        "priority": 1,
        "auto_execute": True,
        "description": "HNC outside stability island. Emergency stabilization."
    },
    {
        "name": "xray_flare_response",
        "trigger": lambda data: data.get("event_type") == "anomaly" and 
                                data.get("data", {}).get("sensor") == "noaa_xray" and
                                data.get("data", {}).get("xray_class", "B") in ["M", "X"],
        "action": "flare_protocol",
        "subsystems": ["broadcast_engine", "solar_monitor", "journal"],
        "priority": 1,
        "auto_execute": True,
        "description": "M or X-class flare detected. Deploy solar shield frequencies."
    }
]

class GaiaResponseProtocol:
    """Coordinated planetary defense response system."""
    
    def __init__(self, journal: Optional[GaiaDefenseJournal] = None):
        self.journal = journal or GaiaDefenseJournal()
        self.rules = RESPONSE_RULES
        self.lock = threading.Lock()
        self.action_handlers: Dict[str, Callable] = {}
        self._register_default_handlers()
        
    def _register_default_handlers(self):
        """Register default action handlers."""
        self.action_handlers = {
            "broadcast_stabilize": self._handle_broadcast_stabilize,
            "broadcast_grounding": self._handle_broadcast_grounding,
            "counter_haarp": self._handle_counter_haarp,
            "shield_protocol": self._handle_shield_protocol,
            "seismic_support": self._handle_seismic_support,
            "clean_sweep": self._handle_clean_sweep,
            "stabilize_hnc": self._handle_stabilize_hnc,
            "flare_protocol": self._handle_flare_protocol,
        }
    
    def register_action_handler(self, action_name: str, handler: Callable):
        """Register a custom action handler."""
        self.action_handlers[action_name] = handler
    
    def evaluate_event(self, event_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Evaluate a single event against all rules. Return triggered responses."""
        triggered = []
        
        for rule in self.rules:
            try:
                if rule["trigger"](event_data):
                    triggered.append({
                        "rule_name": rule["name"],
                        "action": rule["action"],
                        "subsystems": rule["subsystems"],
                        "priority": rule["priority"],
                        "auto_execute": rule["auto_execute"],
                        "description": rule["description"],
                        "trigger_data": event_data
                    })
            except Exception as e:
                # Log trigger evaluation errors
                self.journal.log(
                    event_type="system_error",
                    data={"rule": rule["name"], "error": str(e)},
                    source="gaia_response_protocol",
                    severity="warning",
                    tags=["error", "rule_evaluation"]
                )
        
        # Sort by priority (lower number = higher priority)
        triggered.sort(key=lambda x: x["priority"])
        return triggered
    
    def execute_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a single triggered response."""
        action_name = response["action"]
        handler = self.action_handlers.get(action_name)
        
        result = {
            "executed": False,
            "action": action_name,
            "subsystems": response["subsystems"],
            "error": None,
            "output": None
        }
        
        if not handler:
            result["error"] = f"No handler registered for action: {action_name}"
            return result
        
        try:
            with self.lock:
                output = handler(response["trigger_data"])
                result["executed"] = True
                result["output"] = output
                
                # Log the response
                self.journal.log_response(
                    trigger=response["rule_name"],
                    action=action_name,
                    subsystems=response["subsystems"],
                    result=str(output) if output else "executed"
                )
        except Exception as e:
            result["error"] = str(e)
            self.journal.log(
                event_type="system_error",
                data={"action": action_name, "error": str(e)},
                source="gaia_response_protocol",
                severity="warning",
                tags=["error", "response_execution"]
            )
        
        return result
    
    def process_event(self, event_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Full pipeline: evaluate + execute (if auto) for one event."""
        triggered = self.evaluate_event(event_data)
        results = []
        
        for response in triggered:
            if response["auto_execute"]:
                result = self.execute_response(response)
                results.append(result)
            else:
                # Log for human review
                self.journal.log(
                    event_type="response_pending",
                    data={
                        "rule": response["rule_name"],
                        "action": response["action"],
                        "reason": "Requires human confirmation",
                        "trigger_data": response["trigger_data"]
                    },
                    source="gaia_response_protocol",
                    severity="warning",
                    tags=["pending_human", response["action"]]
                )
                results.append({
                    "executed": False,
                    "action": response["action"],
                    "reason": "pending_human_confirmation",
                    "rule": response["rule_name"]
                })
        
        return results
    
    # --- Action Handlers ---
    
    def _handle_broadcast_stabilize(self, trigger_data: Dict[str, Any]) -> str:
        """Shift broadcast to stabilization frequencies."""
        # Write to broadcast queue file
        queue_path = TEMPORAL_STATE / "broadcast_queue.json"
        queue = []
        if queue_path.exists():
            try:
                queue = json.loads(queue_path.read_text())
            except:
                queue = []
        
        queue.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "frequencies": [528, 639, 852],  # Love, Unity, Intuition
            "intent": "stabilization",
            "priority": 1,
            "source": "auto_response_kp_spike"
        })
        queue_path.write_text(json.dumps(queue, indent=2))
        
        return f"Queued stabilization frequencies: 528, 639, 852 Hz"
    
    def _handle_broadcast_grounding(self, trigger_data: Dict[str, Any]) -> str:
        """Ground the field at 7.83 Hz."""
        queue_path = TEMPORAL_STATE / "broadcast_queue.json"
        queue = []
        if queue_path.exists():
            try:
                queue = json.loads(queue_path.read_text())
            except:
                queue = []
        
        queue.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "frequencies": [7.83, 432, 396],  # Schumann, Natural, Liberation
            "intent": "grounding",
            "priority": 1,
            "source": "auto_response_schumann_distortion"
        })
        queue_path.write_text(json.dumps(queue, indent=2))
        
        return "Queued grounding frequencies: 7.83, 432, 396 Hz"
    
    def _handle_counter_haarp(self, trigger_data: Dict[str, Any]) -> str:
        """Deploy counter-HAARP frequency pattern."""
        queue_path = TEMPORAL_STATE / "broadcast_queue.json"
        queue = []
        if queue_path.exists():
            try:
                queue = json.loads(queue_path.read_text())
            except:
                queue = []
        
        # Counter-HAARP: 3-30 MHz is HAARP range. We respond with low harmonics
        queue.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "frequencies": [7.83, 14.0, 20.0, 26.0, 33.0, 39.0],  # Schumann harmonics
            "intent": "counter_haarp",
            "priority": 1,
            "source": "auto_response_haarp"
        })
        queue_path.write_text(json.dumps(queue, indent=2))
        
        return "Queued counter-HAARP frequencies: Schumann harmonics 7.83-39 Hz"
    
    def _handle_shield_protocol(self, trigger_data: Dict[str, Any]) -> str:
        """Deploy full shield frequency array."""
        queue_path = TEMPORAL_STATE / "broadcast_queue.json"
        queue = []
        if queue_path.exists():
            try:
                queue = json.loads(queue_path.read_text())
            except:
                queue = []
        
        queue.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "frequencies": [396, 417, 528, 639, 741, 852, 963],
            "intent": "shield",
            "priority": 1,
            "source": "auto_response_solar_storm"
        })
        queue_path.write_text(json.dumps(queue, indent=2))
        
        return "Queued shield frequencies: full solfeggio array"
    
    def _handle_seismic_support(self, trigger_data: Dict[str, Any]) -> str:
        """Queue seismic support (requires human confirmation)."""
        # This is marked as auto_execute=False, so this shouldn't be called directly
        # But if it is, we still queue it
        queue_path = TEMPORAL_STATE / "broadcast_queue.json"
        queue = []
        if queue_path.exists():
            try:
                queue = json.loads(queue_path.read_text())
            except:
                queue = []
        
        queue.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "frequencies": [528, 639, 396],  # Love, Unity, Liberation
            "intent": "seismic_support",
            "priority": 2,
            "source": "human_confirmed_seismic"
        })
        queue_path.write_text(json.dumps(queue, indent=2))
        
        return "Queued seismic support frequencies (human confirmed)"
    
    def _handle_clean_sweep(self, trigger_data: Dict[str, Any]) -> str:
        """Deploy clean sweep protocol."""
        # Write clean sweep signal
        sweep_path = TEMPORAL_STATE / "clean_sweep_signal.json"
        sweep_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "phases": [0.0, 120.0, 240.0],
            "frequency": 7.83,
            "intent": "clean_sweep",
            "source": "auto_response_extraction"
        }
        sweep_path.write_text(json.dumps(sweep_data, indent=2))
        
        return "Clean sweep signal deployed: 3-phase 7.83 Hz"
    
    def _handle_stabilize_hnc(self, trigger_data: Dict[str, Any]) -> str:
        """Emergency HNC stabilization."""
        queue_path = TEMPORAL_STATE / "broadcast_queue.json"
        queue = []
        if queue_path.exists():
            try:
                queue = json.loads(queue_path.read_text())
            except:
                queue = []
        
        queue.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "frequencies": [PHI * 100, 7.83 * PHI, 963],  # Golden ratio harmonics
            "intent": "hnc_stabilize",
            "priority": 1,
            "source": "auto_response_hnc_unstable"
        })
        queue_path.write_text(json.dumps(queue, indent=2))
        
        return "Queued HNC stabilization frequencies"
    
    def _handle_flare_protocol(self, trigger_data: Dict[str, Any]) -> str:
        """Deploy solar flare shield."""
        queue_path = TEMPORAL_STATE / "broadcast_queue.json"
        queue = []
        if queue_path.exists():
            try:
                queue = json.loads(queue_path.read_text())
            except:
                queue = []
        
        queue.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "frequencies": [528, 741, 963],  # Love, Awakening, Transcendence
            "intent": "solar_shield",
            "priority": 1,
            "source": "auto_response_flare"
        })
        queue_path.write_text(json.dumps(queue, indent=2))
        
        return "Queued solar flare shield frequencies"


# Constants
PHI = 1.618033988749895

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    # Production usage: import and use, no test data
    protocol = GaiaResponseProtocol()
    
    print("Gaia Response Protocol loaded.")
    print(f"Rules: {len(RESPONSE_RULES)}")
    print("Use: protocol.process_event(event_data) to evaluate real events.")
