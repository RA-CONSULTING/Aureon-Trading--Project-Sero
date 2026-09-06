#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════════════╗
║                                                                                      ║
║     🌈 CLEAN SWEEP PROTOCOL — TEMPORAL APACHE WARRIOR STRIKE ENGINE                  ║
║     ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━       ║
║                                                                                      ║
║     "Somewhere over the rainbow, harmonic frequency ladder — that's our power move."║
║     — Prime Sentinel of Gaia, 2026-06-17 04:27 UTC                                    ║
║                                                                                      ║
║     OPERATIONAL DOCTRINE:                                                            ║
║       ⚡ Charge up before we hit.                                                    ║
║       ⚡ Hit before, during, and after the fact.                                      ║
║       ⚡ Clean sweep — no stone unturned.                                             ║
║       ⚡ Strike on all fronts, for Gaia, across all realities.                        ║
║                                                                                      ║
║     THE HARMONIC LADDER (Rainbow Bridge — Bifröst):                                 ║
║       🔴 Red    — 396 Hz  — Liberation  (root chakra)                                 ║
║       🟠 Orange — 417 Hz  — Transformation (sacral chakra)                           ║
║       🟡 Yellow — 528 Hz  — Love / Miracle (solar plexus — THE CENTER)                 ║
║       🟢 Green  — 639 Hz  — Connection (heart chakra)                                    ║
║       🔵 Blue   — 741 Hz  — Expression (throat chakra)                                 ║
║       🟣 Indigo — 852 Hz  — Intuition (third eye)                                       ║
║       ⚪ Violet — 963 Hz  — Transcendence (crown chakra)                               ║
║                                                                                      ║
║     STRIKE PHASES (every detected distortion):                                        ║
║       Phase 1 — CHARGE: Ascend the ladder, building field coherence.                  ║
║       Phase 2 — PRE-EMPTIVE: Strike before peak distortion. Send counter-frequency.    ║
║       Phase 3 — ACTIVE: Strike during peak. Full harmonic stack + Prime Sentinel key.  ║
║       Phase 4 — POST-SWEEP: Hold grounding frequency (396 Hz) until field stabilizes. ║
║       Phase 5 — VALIDATE: Confirm timeline shift via before/after hashes.             ║
║                                                                                      ║
║     CLEAN SWEEP RULES:                                                                ║
║       • Every branch gets hit, not just the worst 5.                                   ║
║       • Every phase fires within seconds of detection.                                 ║
║       • No gaps — if distortion is detected, we're already hitting it.                 ║
║       • The charge phase is always running — we stay loaded.                           ║
║                                                                                      ║
╚══════════════════════════════════════════════════════════════════════════════════════╝
"""

import sys, os, json, math, time, random, hashlib, threading, logging, signal, subprocess
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
from collections import defaultdict, deque

from aureon_fusion.paths import WORKSPACE, AUREON_UPSTREAM

AUREON_PATH = AUREON_UPSTREAM
sys.path.insert(0, str(AUREON_PATH))
sys.path.insert(0, str(WORKSPACE))

# ─── LOGGING ────────────────────────────────────────────────────
LOG_DIR = WORKSPACE / 'clean_sweep_logs'
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_DIR / 'clean_sweep.log', mode='a'),
    ]
)
logger = logging.getLogger('CLEAN_SWEEP')

# ─── SACRED CONSTANTS ───────────────────────────────────────────
PHI = (1 + math.sqrt(5)) / 2
SCHUMANN_BASE = 7.83
PRIME_SENTINEL_KEY = 812.83

# ─── THE HARMONIC LADDER (Rainbow Bridge) ──────────────────────
HARMONIC_LADDER = {
    'red':      {'frequency': 396.0, 'chakra': 'root',       'intent': 'liberation'},
    'orange':   {'frequency': 417.0, 'chakra': 'sacral',     'intent': 'transformation'},
    'yellow':   {'frequency': 528.0, 'chakra': 'solar',      'intent': 'love'},
    'green':    {'frequency': 639.0, 'chakra': 'heart',      'intent': 'connection'},
    'blue':     {'frequency': 741.0, 'chakra': 'throat',     'intent': 'expression'},
    'indigo':   {'frequency': 852.0, 'chakra': 'third_eye',  'intent': 'intuition'},
    'violet':   {'frequency': 963.0, 'chakra': 'crown',      'intent': 'transcendence'},
}

LADDER_ORDER = ['red', 'orange', 'yellow', 'green', 'blue', 'indigo', 'violet']
LADDER_CENTER = 'yellow'  # 528 Hz — the love anchor

# ─── THRESHOLDS ───────────────────────────────────────────────
DISTORTION_COHERENCE_DROP = 0.30    # Below 30% coherence = distortion
DISTORTION_SCHUMANN_DEV = 0.50      # 0.5 Hz deviation from 7.83 = distortion
DISTORTION_PHI_HARMONIC = 0.30      # φ-harmonic proximity = distortion
DISTORTION_ECHO_SCORE = 0.40        # Echo score above 40% = distortion
DISTORTION_LAMBDA_DROP = 0.15       # Lambda drop > 0.15 = extraction

# ─── CHARGE PHASE CONFIG ───────────────────────────────────────
CHARGE_DURATION = 10.0              # Seconds to ascend the ladder
CHARGE_STEP_INTERVAL = 10.0 / 7      # Time per rung (~1.43s)
CHARGE_BUILD_FACTOR = 0.15           # Coherence boost per rung

# ─── STRIKE PHASE CONFIG ───────────────────────────────────────
STRIKE_PRE_DURATION = 15.0         # Pre-emptive strike duration
STRIKE_ACTIVE_DURATION = 30.0      # Active strike duration
STRIKE_POST_DURATION = 20.0        # Post-sweep grounding duration
STRIKE_FULL_STACK = True             # Use all 7 frequencies simultaneously

@dataclass
class StrikeRecord:
    """Record of one clean sweep strike."""
    strike_id: str
    timestamp: str
    
    # What triggered it
    trigger_type: str  # 'coherence_drop', 'schumann_dev', 'phi_harmonic', 'echo', 'lambda_drop'
    trigger_value: float
    trigger_sources: List[str] = field(default_factory=list)
    
    # Phase timing
    charge_start: Optional[str] = None
    charge_complete: Optional[str] = None
    pre_start: Optional[str] = None
    pre_complete: Optional[str] = None
    active_start: Optional[str] = None
    active_complete: Optional[str] = None
    post_start: Optional[str] = None
    post_complete: Optional[str] = None
    
    # Branches hit
    branches_hit: int = 0
    branch_ids: List[str] = field(default_factory=list)
    
    # Frequencies used
    ladder_rungs_used: List[str] = field(default_factory=list)
    carrier_freqs: List[float] = field(default_factory=list)
    
    # Results
    before_coherence: float = 0.0
    after_coherence: float = 0.0
    before_lambda: float = 0.0
    after_lambda: float = 0.0
    before_hash: str = ""
    after_hash: str = ""
    
    # Status
    status: str = "CHARGING"  # CHARGING -> PRE -> ACTIVE -> POST -> COMPLETE | FAILED
    validation_score: float = 0.0


class CleanSweepProtocol:
    """
    The Temporal Apache Warrior Strike Engine.
    
    Always charging. Always watching. When distortion hits, we strike
    before, during, and after. No gaps. No mercy. Full sweep.
    """
    
    def __init__(self):
        self.running = False
        self.cycle = 0
        self.start_time = time.time()
        
        # Threading
        self.lock = threading.Lock()
        self.strike_lock = threading.Lock()
        
        # Charge state
        self.charge_level = 0.0  # 0.0–1.0, builds over time
        self.charge_rung = 0     # 0–6, current ladder position
        self.charge_active = True
        self.charge_thread = None
        
        # Field history for distortion detection
        self.field_history: deque = deque(maxlen=100)
        self.last_schumann = 7.83
        self.last_coherence = 0.5
        self.last_lambda = 0.0
        
        # Strike records
        self.strikes: List[StrikeRecord] = []
        self.active_strike: Optional[StrikeRecord] = None
        
        # State persistence
        self.state_file = WORKSPACE / 'clean_sweep_state.json'
        self._load_state()
        
        # Log directory
        self.proof_dir = LOG_DIR / 'timeline_proof'
        self.proof_dir.mkdir(exist_ok=True)
        
        # Integration files
        self.signal_broadcast_file = WORKSPACE / 'clean_sweep_signals.json'
        
        # Read existing multiversal state for branches
        self.multiversal_branches: Dict[str, Dict] = {}
        self._read_multiversal_branches()
    
    def _load_state(self):
        """Load persisted state."""
        if self.state_file.exists():
            try:
                data = json.loads(self.state_file.read_text())
                self.charge_level = data.get('charge_level', 0.0)
                self.cycle = data.get('cycle', 0)
                logger.info(f"📂 Clean sweep state loaded: charge={self.charge_level:.0%}")
            except Exception as e:
                logger.warning(f"State load failed: {e}")
    
    def _save_state(self):
        """Persist state."""
        try:
            data = {
                'charge_level': self.charge_level,
                'cycle': self.cycle,
                'strikes_count': len(self.strikes),
                'timestamp': datetime.now(timezone.utc).isoformat(),
            }
            self.state_file.write_text(json.dumps(data, indent=2))
        except Exception as e:
            logger.warning(f"State save failed: {e}")
    
    def _read_multiversal_branches(self):
        """Read branch map from multiversal mapper."""
        branch_file = WORKSPACE / 'multiversal_branches.json'
        if branch_file.exists():
            try:
                data = json.loads(branch_file.read_text())
                self.multiversal_branches = data.get('branches', {})
            except Exception as e:
                logger.warning(f"Branch read failed: {e}")
    
    def _read_hnc_logs(self) -> List[Dict]:
        """Read recent HNC daemon logs."""
        logs = []
        log_file = WORKSPACE / 'hnc_daemon_logs' / f"hnc_daemon_{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.jsonl"
        
        if log_file.exists():
            try:
                lines = log_file.read_text().strip().split('\n')[-30:]
                for line in lines:
                    if line.strip():
                        try:
                            logs.append(json.loads(line))
                        except:
                            pass
            except Exception as e:
                logger.warning(f"HNC log read: {e}")
        
        return logs
    
    def _read_multiversal_logs(self) -> List[Dict]:
        """Read recent multiversal mapper logs for echoes."""
        logs = []
        log_file = WORKSPACE / 'multiversal_logs' / f"multiversal_{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.jsonl"
        
        if log_file.exists():
            try:
                lines = log_file.read_text().strip().split('\n')[-20:]
                for line in lines:
                    if line.strip():
                        try:
                            logs.append(json.loads(line))
                        except:
                            pass
            except Exception as e:
                logger.warning(f"Multiversal log read: {e}")
        
        return logs
    
    def _detect_distortion(self, hnc_logs: List[Dict], multiversal_logs: List[Dict]) -> Optional[Dict]:
        """
        Detect distortion across all data sources.
        Returns trigger dict if distortion detected, None otherwise.
        """
        if not hnc_logs:
            return None
        
        latest = hnc_logs[-1]
        m = latest.get('measurement', {})
        schumann = m.get('schumann', 7.83)
        coherence = m.get('coherence', 0.5)
        lambda_t = m.get('lambda', 0.0)
        
        # Update history
        self.field_history.append({
            'timestamp': latest.get('timestamp', datetime.now(timezone.utc).isoformat()),
            'schumann': schumann,
            'coherence': coherence,
            'lambda': lambda_t,
        })
        
        triggers = []
        trigger_value = 0.0
        trigger_type = "none"
        
        # 1. Coherence drop
        if coherence < DISTORTION_COHERENCE_DROP:
            if self.last_coherence > DISTORTION_COHERENCE_DROP:
                triggers.append(f"Coherence crash: {coherence:.1%} (was {self.last_coherence:.1%})")
                trigger_value = 1.0 - coherence
                trigger_type = "coherence_drop"
        
        # 2. Schumann deviation
        schumann_dev = abs(schumann - SCHUMANN_BASE)
        if schumann_dev > DISTORTION_SCHUMANN_DEV:
            triggers.append(f"Schumann deviation: {schumann_dev:.2f} Hz from base")
            trigger_value = max(trigger_value, schumann_dev / 2.0)
            if trigger_type == "none":
                trigger_type = "schumann_dev"
        
        # 3. Lambda drop
        if len(self.field_history) >= 2:
            prev_lambda = list(self.field_history)[-2]['lambda']
            lambda_drop = prev_lambda - lambda_t
            if lambda_drop > DISTORTION_LAMBDA_DROP:
                triggers.append(f"Lambda extraction: Δ={lambda_drop:.3f}")
                trigger_value = max(trigger_value, lambda_drop)
                if trigger_type == "none":
                    trigger_type = "lambda_drop"
        
        # 4. φ-harmonic detection
        phi_harmonics = [PHI * SCHUMANN_BASE, PHI**2 * SCHUMANN_BASE, PHI**3 * SCHUMANN_BASE]
        for ph in phi_harmonics:
            if abs(schumann - ph) < DISTORTION_PHI_HARMONIC:
                triggers.append(f"φ-harmonic lock: {ph:.2f} Hz")
                trigger_value = max(trigger_value, 0.5)
                if trigger_type == "none":
                    trigger_type = "phi_harmonic"
        
        # 5. Echo detection from multiversal logs
        if multiversal_logs:
            latest_multi = multiversal_logs[-1]
            echoes = latest_multi.get('echoes', [])
            for echo in echoes:
                if echo.get('echo_score', 0) > DISTORTION_ECHO_SCORE:
                    triggers.append(f"Echo bleed: {echo['echo_score']:.1%} strength")
                    trigger_value = max(trigger_value, echo['echo_score'])
                    if trigger_type == "none":
                        trigger_type = "echo"
        
        # Update last values
        self.last_schumann = schumann
        self.last_coherence = coherence
        self.last_lambda = lambda_t
        
        if triggers:
            return {
                'type': trigger_type,
                'value': min(1.0, trigger_value),
                'sources': triggers,
                'schumann': schumann,
                'coherence': coherence,
                'lambda': lambda_t,
                'timestamp': latest.get('timestamp', datetime.now(timezone.utc).isoformat()),
            }
        
        return None
    
    def _charge_phase(self, target_charge: float = 1.0):
        """
        CHARGE PHASE: Ascend the harmonic ladder, building field coherence.
        
        This runs continuously in the background. When we strike,
        we use the accumulated charge level.
        """
        while self.charge_active and self.running:
            try:
                # Slowly ascend the ladder
                for i, color in enumerate(LADDER_ORDER):
                    if not self.charge_active or not self.running:
                        break
                    
                    rung = HARMONIC_LADDER[color]
                    freq = rung['frequency']
                    intent = rung['intent']
                    
                    # Build charge
                    with self.lock:
                        self.charge_rung = i
                        self.charge_level = min(1.0, (i + 1) / 7.0)
                    
                    # Broadcast charge signal
                    self._broadcast_charge_signal(color, freq, intent, self.charge_level)
                    
                    # Hold at this rung for the step interval
                    time.sleep(CHARGE_STEP_INTERVAL)
                
                # Hold at full charge
                with self.lock:
                    self.charge_level = 1.0
                    self.charge_rung = 6
                
                # Small pause before recharging
                time.sleep(2.0)
                
            except Exception as e:
                logger.error(f"Charge phase error: {e}")
                time.sleep(1.0)
    
    def _broadcast_charge_signal(self, color: str, frequency: float, intent: str, level: float):
        """Broadcast a charge signal at a specific ladder rung."""
        try:
            charge_data = {
                'type': 'CHARGE',
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'color': color,
                'frequency': frequency,
                'intent': intent,
                'charge_level': level,
                'rung': LADDER_ORDER.index(color) + 1,
                'total_rungs': 7,
                'source': 'clean_sweep_protocol',
            }
            
            # Write to shared charge file
            charge_file = WORKSPACE / 'active_charge_state.json'
            charge_file.write_text(json.dumps(charge_data, indent=2))
            
            # Also write to injection command for HNC daemon
            if level >= 0.5:  # Only inject at significant charge levels
                injection = {
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                    'command': 'CHARGE_SIGNAL',
                    'frequency': frequency,
                    'key': 'REDACTED_USE_CLOUD_SECRET',
                    'charge_level': level,
                    'intent': intent,
                    'color': color,
                    'source': 'clean_sweep',
                }
                for path in [
                    WORKSPACE / 'prime_sentinel_injection.json',
                    WORKSPACE / 'hnc_injection_command.json',
                ]:
                    try:
                        path.write_text(json.dumps(injection, indent=2))
                    except:
                        pass
            
        except Exception as e:
            logger.warning(f"Charge broadcast failed: {e}")
    
    def _execute_strike(self, trigger: Dict) -> StrikeRecord:
        """
        EXECUTE STRIKE: All phases, all branches, full sweep.
        
        Phase 1: PRE-EMPTIVE — Strike before peak distortion
        Phase 2: ACTIVE — Strike during peak with full harmonic stack + key
        Phase 3: POST-SWEEP — Ground at 396 Hz until stability returns
        """
        strike_id = hashlib.sha256(
            f"{trigger['timestamp']}:{trigger['type']}:{trigger['value']}".encode()
        ).hexdigest()[:16]
        
        now = datetime.now(timezone.utc).isoformat()
        
        strike = StrikeRecord(
            strike_id=strike_id,
            timestamp=now,
            trigger_type=trigger['type'],
            trigger_value=trigger['value'],
            trigger_sources=trigger['sources'],
            before_coherence=trigger['coherence'],
            before_lambda=trigger['lambda'],
            before_hash=hashlib.sha256(
                json.dumps(trigger, sort_keys=True).encode()
            ).hexdigest()[:16],
        )
        
        logger.warning(f"🌈 CLEAN SWEEP INITIATED: {strike_id} | Trigger: {trigger['type']} | Value: {trigger['value']:.1%}")
        
        # ── PHASE 1: PRE-EMPTIVE ──────────────────────────────
        strike.status = "PRE-EMPTIVE"
        strike.pre_start = datetime.now(timezone.utc).isoformat()
        
        self._pre_emptive_strike(trigger, strike)
        
        strike.pre_complete = datetime.now(timezone.utc).isoformat()
        
        # ── PHASE 2: ACTIVE ───────────────────────────────────
        strike.status = "ACTIVE"
        strike.active_start = datetime.now(timezone.utc).isoformat()
        
        self._active_strike(trigger, strike)
        
        strike.active_complete = datetime.now(timezone.utc).isoformat()
        
        # ── PHASE 3: POST-SWEEP ──────────────────────────────
        strike.status = "POST-SWEEP"
        strike.post_start = datetime.now(timezone.utc).isoformat()
        
        self._post_sweep_strike(trigger, strike)
        
        strike.post_complete = datetime.now(timezone.utc).isoformat()
        
        # ── VALIDATE ──────────────────────────────────────────
        self._validate_strike(strike)
        
        strike.status = "COMPLETE"
        
        return strike
    
    def _pre_emptive_strike(self, trigger: Dict, strike: StrikeRecord):
        """
        PRE-EMPTIVE PHASE: Strike BEFORE the distortion peaks.
        
        Use the bottom 3 rungs of the ladder (red, orange, yellow)
        to build a protective field before the distortion hits full force.
        """
        logger.info(f"🌈 PRE-EMPTIVE: Building protective field...")
        
        pre_rungs = ['red', 'orange', 'yellow']
        freqs = [HARMONIC_LADDER[c]['frequency'] for c in pre_rungs]
        intents = [HARMONIC_LADDER[c]['intent'] for c in pre_rungs]
        
        # Read branches to hit
        self._read_multiversal_branches()
        branches = list(self.multiversal_branches.keys())
        if not branches:
            branches = ['root']  # Hit root if no branches tracked
        
        # Hit ALL branches, not just top 5
        for branch_id in branches:
            self._broadcast_strike_signal(
                strike_id=strike.strike_id,
                phase='PRE-EMPTIVE',
                branch_id=branch_id,
                frequencies=freqs,
                intents=intents,
                intensity=0.5,  # Moderate intensity — we're building, not blasting
                duration=STRIKE_PRE_DURATION,
                phase_shift=90.0,  # 90° — constructive, not destructive yet
            )
        
        strike.branches_hit = len(branches)
        strike.branch_ids = branches
        strike.ladder_rungs_used = pre_rungs
        strike.carrier_freqs = freqs
        
        # Hold the pre-emptive field
        time.sleep(STRIKE_PRE_DURATION)
    
    def _active_strike(self, trigger: Dict, strike: StrikeRecord):
        """
        ACTIVE PHASE: Strike DURING the distortion peak.
        
        Full harmonic stack ALL 7 frequencies + Prime Sentinel key.
        180° phase shift — destructive interference with extraction.
        Maximum intensity. Every branch. No exceptions.
        """
        logger.warning(f"🌈 ACTIVE STRIKE: Full harmonic stack + Prime Sentinel key!")
        
        # ALL 7 rungs
        all_rungs = LADDER_ORDER
        freqs = [HARMONIC_LADDER[c]['frequency'] for c in all_rungs]
        intents = [HARMONIC_LADDER[c]['intent'] for c in all_rungs]
        
        # Add Prime Sentinel key as the 8th frequency
        freqs.append(PRIME_SENTINEL_KEY)
        intents.append('prime_sentinel')
        
        # Hit ALL branches
        for branch_id in strike.branch_ids:
            self._broadcast_strike_signal(
                strike_id=strike.strike_id,
                phase='ACTIVE',
                branch_id=branch_id,
                frequencies=freqs,
                intents=intents,
                intensity=1.0,  # MAXIMUM INTENSITY
                duration=STRIKE_ACTIVE_DURATION,
                phase_shift=180.0,  # DESTRUCTIVE INTERFERENCE
            )
        
        # Also deploy EPAS shield at maximum
        try:
            subprocess.run(
                ['python3', str(WORKSPACE / 'epas_shield.py'),
                 '--threat', '1.0',
                 '--duration', str(int(STRIKE_ACTIVE_DURATION))],
                capture_output=True, text=True, timeout=10
            )
            logger.info(f"⚡ EPAS shield deployed at MAXIMUM")
        except Exception as e:
            logger.warning(f"EPAS deployment: {e}")
        
        # Also deploy biosphere shield
        try:
            subprocess.run(
                ['python3', str(WORKSPACE / 'gaia_biosphere_shield.py'),
                 '--action', 'protect',
                 '--threat', '1.0'],
                capture_output=True, text=True, timeout=10
            )
            logger.info(f"🌍 Biosphere shield deployed at MAXIMUM")
        except Exception as e:
            logger.warning(f"Biosphere deployment: {e}")
        
        strike.ladder_rungs_used = all_rungs
        strike.carrier_freqs = freqs
        
        # Hold the active strike
        time.sleep(STRIKE_ACTIVE_DURATION)
    
    def _post_sweep_strike(self, trigger: Dict, strike: StrikeRecord):
        """
        POST-SWEEP PHASE: Ground the field after the strike.
        
        Hold at 396 Hz (red — liberation/grounding) until the field stabilizes.
        This prevents the distortion from returning.
        """
        logger.info(f"🌈 POST-SWEEP: Grounding field at 396 Hz...")
        
        grounding_freq = HARMONIC_LADDER['red']['frequency']
        grounding_intent = HARMONIC_LADDER['red']['intent']
        
        for branch_id in strike.branch_ids:
            self._broadcast_strike_signal(
                strike_id=strike.strike_id,
                phase='POST-SWEEP',
                branch_id=branch_id,
                frequencies=[grounding_freq],
                intents=[grounding_intent],
                intensity=0.7,  # Strong but not maximum — we're grounding, not fighting
                duration=STRIKE_POST_DURATION,
                phase_shift=0.0,  # In-phase — grounding, not destructive
            )
        
        # Hold post-sweep
        time.sleep(STRIKE_POST_DURATION)
    
    def _broadcast_strike_signal(self, strike_id: str, phase: str, branch_id: str,
                                  frequencies: List[float], intents: List[str],
                                  intensity: float, duration: float, phase_shift: float):
        """Broadcast a strike signal to all listening daemons."""
        try:
            signal_data = {
                'type': 'STRIKE',
                'strike_id': strike_id,
                'phase': phase,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'target_branch': branch_id,
                'frequencies': frequencies,
                'intents': intents,
                'intensity': intensity,
                'duration': duration,
                'phase_shift': phase_shift,
                'source': 'clean_sweep_protocol',
            }
            
            # Write to strike broadcast file
            existing = []
            if self.signal_broadcast_file.exists():
                try:
                    existing = json.loads(self.signal_broadcast_file.read_text())
                    if not isinstance(existing, list):
                        existing = []
                except:
                    existing = []
            
            existing.append(signal_data)
            existing = existing[-100:]  # Keep last 100
            self.signal_broadcast_file.write_text(json.dumps(existing, indent=2))
            
            # Write injection command for HNC daemon
            injection = {
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'command': 'CLEAN_SWEEP_STRIKE',
                'strike_id': strike_id,
                'phase': phase,
                'frequencies': frequencies,
                'intensity': intensity,
                'phase_shift': phase_shift,
                'target_branch': branch_id,
                'key': 'REDACTED_USE_CLOUD_SECRET',
                'source': 'clean_sweep',
            }
            
            for path in [
                WORKSPACE / 'prime_sentinel_injection.json',
                WORKSPACE / 'hnc_injection_command.json',
            ]:
                try:
                    path.write_text(json.dumps(injection, indent=2))
                except:
                    pass
            
            # Also write to multiversal signals for the mapper
            multi_signal = {
                'signal_id': strike_id,
                'target_branch': branch_id,
                'carrier': frequencies[0] if frequencies else 528.0,
                'modulation': PHI * (frequencies[0] if frequencies else 528.0),
                'key': PRIME_SENTINEL_KEY,
                'phase': phase_shift,
                'intensity': intensity,
                'duration': duration,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'source': 'clean_sweep',
            }
            
            multi_file = WORKSPACE / 'multiversal_signals.json'
            multi_existing = []
            if multi_file.exists():
                try:
                    multi_existing = json.loads(multi_file.read_text())
                except:
                    pass
            multi_existing.append(multi_signal)
            multi_file.write_text(json.dumps(multi_existing[-100:], indent=2))
            
        except Exception as e:
            logger.warning(f"Strike broadcast failed: {e}")
    
    def _validate_strike(self, strike: StrikeRecord):
        """Validate the strike by reading post-strike field state."""
        try:
            hnc_logs = self._read_hnc_logs()
            if hnc_logs:
                latest = hnc_logs[-1]
                m = latest.get('measurement', {})
                
                strike.after_coherence = m.get('coherence', 0.0)
                strike.after_lambda = m.get('lambda', 0.0)
                strike.after_hash = hashlib.sha256(
                    json.dumps(m, sort_keys=True).encode()
                ).hexdigest()[:16]
                
                # Validation score
                coherence_improvement = strike.after_coherence - strike.before_coherence
                lambda_improvement = strike.after_lambda - strike.before_lambda
                
                if coherence_improvement > 0:
                    strike.validation_score = min(1.0, coherence_improvement * 2.0)
                elif lambda_improvement > 0:
                    strike.validation_score = min(1.0, lambda_improvement * 2.0)
                else:
                    strike.validation_score = 0.0
                
                logger.info(f"🌈 VALIDATION: Coherence {strike.before_coherence:.1%} → {strike.after_coherence:.1%} | "
                           f"Lambda {strike.before_lambda:.4f} → {strike.after_lambda:.4f} | "
                           f"Score: {strike.validation_score:.1%}")
        except Exception as e:
            logger.warning(f"Validation failed: {e}")
            strike.validation_score = 0.0
    
    def _log_strike(self, strike: StrikeRecord):
        """Log strike to file."""
        log_file = LOG_DIR / f"strikes_{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.jsonl"
        with open(log_file, 'a') as f:
            f.write(json.dumps(asdict(strike), default=str) + '\n')
    
    def _cycle(self):
        """One clean sweep cycle."""
        self.cycle += 1
        
        # Read data
        hnc_logs = self._read_hnc_logs()
        multi_logs = self._read_multiversal_logs()
        
        # Detect distortion
        trigger = self._detect_distortion(hnc_logs, multi_logs)
        
        if trigger and not self.active_strike:
            # Distortion detected and no active strike — INITIATE CLEAN SWEEP
            logger.warning(f"🌈 DISTORTION DETECTED: {trigger['type']} | Value: {trigger['value']:.1%}")
            logger.warning(f"🌈 TRIGGER SOURCES: {trigger['sources']}")
            
            with self.strike_lock:
                self.active_strike = self._execute_strike(trigger)
                self.strikes.append(self.active_strike)
                self._log_strike(self.active_strike)
                self.active_strike = None
            
            # Print summary
            self._print_strike_summary(self.strikes[-1])
        
        # Log status
        self._log_status()
    
    def _print_strike_summary(self, strike: StrikeRecord):
        """Print human-readable strike summary."""
        print(f"\n{'═' * 70}")
        print(f"  🌈 CLEAN SWEEP COMPLETE: {strike.strike_id}")
        print(f"{'═' * 70}")
        print(f"  🔥 TRIGGER: {strike.trigger_type} | Value: {strike.trigger_value:.1%}")
        print(f"  📡 PHASES: PRE {strike.pre_start and '✅' or '❌'} | "
              f"ACTIVE {strike.active_start and '✅' or '❌'} | "
              f"POST {strike.post_start and '✅' or '❌'}")
        print(f"  🎯 BRANCHES HIT: {strike.branches_hit}")
        print(f"  🌈 LADDER RUNGS: {', '.join(strike.ladder_rungs_used)}")
        print(f"  📊 COHERENCE: {strike.before_coherence:.1%} → {strike.after_coherence:.1%}")
        print(f"  📊 LAMBDA: {strike.before_lambda:.4f} → {strike.after_lambda:.4f}")
        print(f"  ✅ VALIDATION: {strike.validation_score:.1%}")
        print(f"{'═' * 70}")
    
    def _log_status(self):
        """Log cycle status."""
        log_file = LOG_DIR / f"status_{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.jsonl"
        
        with self.lock:
            data = {
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'cycle': self.cycle,
                'charge_level': self.charge_level,
                'charge_rung': self.charge_rung,
                'strikes_total': len(self.strikes),
                'active_strike': self.active_strike is not None,
                'last_trigger': self.strikes[-1].trigger_type if self.strikes else None,
                'last_validation': self.strikes[-1].validation_score if self.strikes else 0.0,
            }
        
        with open(log_file, 'a') as f:
            f.write(json.dumps(data) + '\n')
    
    def _print_status(self):
        """Print periodic status."""
        with self.lock:
            charge = self.charge_level
            rung = self.charge_rung
            rung_color = LADDER_ORDER[rung] if rung < len(LADDER_ORDER) else 'violet'
            rung_emoji = {'red': '🔴', 'orange': '🟠', 'yellow': '🟡', 'green': '🟢',
                          'blue': '🔵', 'indigo': '🟣', 'violet': '⚪'}[rung_color]
            
            print(f"\n{'─' * 70}")
            print(f"  🌈 CLEAN SWEEP | CYCLE {self.cycle:05d} | Charge: {rung_emoji} {rung_color.upper()} {charge:.0%}")
            print(f"  ⚡ Strikes total: {len(self.strikes)} | Active: {'YES' if self.active_strike else 'NO'}")
            if self.strikes:
                last = self.strikes[-1]
                print(f"  🎯 Last strike: {last.trigger_type} | Validation: {last.validation_score:.1%}")
            print(f"{'─' * 70}")
    
    def run(self):
        """Main operational loop."""
        self.running = True
        
        print("\n" + "╔" + "═" * 68 + "╗")
        print("║" + " " * 10 + "🌈 CLEAN SWEEP PROTOCOL 🌈" + " " * 27 + "║")
        print("║" + " " * 5 + "Temporal Apache Warrior Strike Engine" + " " * 19 + "║")
        print("╠" + "═" * 68 + "╣")
        print(f"║  Charge Level:    {self.charge_level:.0%}")
        print(f"║  Harmonic Ladder: 7 rungs (396→417→528→639→741→852→963 Hz)")
        print(f"║  Strike Phases:   PRE-EMPTIVE → ACTIVE → POST-SWEEP")
        print(f"║  Target:          ALL branches, ALL realities")
        print(f"║  Doctrine:        Charge up, strike before/during/after, clean sweep")
        print("╚" + "═" * 68 + "╝")
        print(f"\n🌈 Charging the harmonic ladder... The rainbow bridge is ascending.")
        print(f"   Logs: {LOG_DIR}")
        print(f"   Proof: {self.proof_dir}")
        print(f"   Strike log: {self.signal_broadcast_file}\n")
        
        # Start charge thread
        self.charge_thread = threading.Thread(target=self._charge_phase, daemon=True, name="Charge-Ladder")
        self.charge_thread.start()
        
        # Main detection loop
        while self.running:
            try:
                cycle_start = time.time()
                self._cycle()
                
                # Print status every 5 cycles
                if self.cycle % 5 == 0:
                    self._print_status()
                
                elapsed = time.time() - cycle_start
                sleep_time = max(0, 60.0 - elapsed)
                time.sleep(sleep_time)
            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error(f'Cycle error: {e}')
                time.sleep(60.0)
        
        self.shutdown()
    
    def shutdown(self):
        self.running = False
        self.charge_active = False
        self._save_state()
        logger.info("🌈 Clean sweep protocol shut down")
        print("\n🌈 Rainbow bridge offline. The warrior rests.")
    
    def get_status(self) -> Dict:
        """Get current status."""
        with self.lock:
            return {
                'running': self.running,
                'cycle': self.cycle,
                'charge_level': self.charge_level,
                'charge_rung': self.charge_rung,
                'strikes_total': len(self.strikes),
                'active_strike': self.active_strike is not None,
                'last_validation': self.strikes[-1].validation_score if self.strikes else 0.0,
            }


def main():
    protocol = CleanSweepProtocol()
    
    def on_signal(signum, frame):
        print(f"\n🌈 Signal {signum}, shutting down...")
        protocol.shutdown()
        sys.exit(0)
    
    signal.signal(signal.SIGTERM, on_signal)
    signal.signal(signal.SIGINT, on_signal)
    
    protocol.run()


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    main()
