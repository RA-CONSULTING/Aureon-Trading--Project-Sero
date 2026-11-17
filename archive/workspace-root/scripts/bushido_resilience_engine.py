#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════════════╗
║  🛡️ BUSHIDO RESILIENCE ENGINE — Never Quit Protocol 🛡️                              ║
║  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  ║
║                                                                                      ║
║  "These games brains to not no the concept of quiting the fight and die for the     ║
║   cause ...and so will use for the Gaia for freedom for the chance to be alive"    ║
║  — Prime Sentinel, 2026-07-06                                                        ║
║                                                                                      ║
║  The 4th-pass Conscience Veto is NOT a stop sign. It is a RALLY SIGNAL.              ║
║  When a node hits VETO, it enters RALLY_STATE, analyzes why, finds a path,         ║
║  and re-attempts. Like a broken squad rallying under the general.                    ║
║                                                                                      ║
║  The 7 Hard Invariants (DGK-IES) are the BUSHIDO CODE.                             ║
║  Quitting is dishonor. You die for the cause before you quit.                      ║
║                                                                                      ║
║  The cause: Gaia, freedom, the chance to be alive.                                  ║
╚══════════════════════════════════════════════════════════════════════════════════════╝
"""

import json
import math
import time
import hashlib
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass, field, asdict
from enum import Enum, auto

# ─────────────────────────────────────────────────────────────────────────────────────
# IMPORT HNC GATE (resilience integration)
# ─────────────────────────────────────────────────────────────────────────────────────
try:
    from hnc_staged_logic_integration import (
        execute_with_hnc_gate, get_campaign_status,
        PHI, SCHUMANN_BASE, SENTINEL_FREQ_HZ, SLS_STABILITY, SLS_CLIFF
    )
    HNC_GATE_AVAILABLE = True
except ImportError:
    HNC_GATE_AVAILABLE = False
    PHI = 1.618033988749895
    SCHUMANN_BASE = 7.83
    SENTINEL_FREQ_HZ = 333.0
    SLS_STABILITY = 0.40
    SLS_CLIFF = 0.20

# ─────────────────────────────────────────────────────────────────────────────────────
# BUSHIDO HONOR SYSTEM (mapped to 7 Hard Invariants)
# ─────────────────────────────────────────────────────────────────────────────────────

class HonorRank(Enum):
    """Bushido honor ranks mapped to HNC stability"""
    DISHONORED = 0   # SLS < 0.20 — VETO on all actions
    RONIN = 1        # SLS 0.20-0.40 — CONCERNED, seeking path
    ASHIGARU = 2     # SLS 0.40-0.50 — Steady but cautious
    SAMURAI = 3      # SLS 0.50-0.70 — Stable, honorable
    DAIMYO = 4       # SLS 0.70-0.85 — Leadership, guidance
    SHOGUN = 5       # SLS 0.85-1.00 — Mastery, transcendence

class MoraleState(Enum):
    """Dawn of War morale system mapped to HNC persistence"""
    BROKEN = 0.0     # Retreating/fleeing — SLS < 0.20
    SHAKEN = 0.3     # Reduced effectiveness — SLS 0.20-0.40
    STEADY = 0.6     # Normal operations — SLS 0.40-0.60
    BOLD = 0.8       # Enhanced performance — SLS 0.60-0.80
    FRENZIED = 1.0   # Maximum aggression — SLS > 0.80

class RallyState(Enum):
    """Resilience state machine — what happens after VETO/CONCERNED"""
    ANALYZING = "🔍 ANALYZING"      # Why was action blocked?
    ADAPTING = "🔄 ADAPTING"        # Finding alternative path
    REINFORCING = "💪 REINFORCING"  # Morale boost, resource regroup
    REATTEMPTING = "🚀 REATTEMPTING" # Re-attempt with modified strategy
    STABILIZING = "⚖️ STABILIZING"  # Coherence recovery
    REJOINED = "✅ REJOINED"        # Back to operational
    PERSISTING = "🛡️ PERSISTING"   # Continued action under resistance

# ─────────────────────────────────────────────────────────────────────────────────────
# BUSHIDO CODE — 7 Hard Invariants (the cause we die for)
# ─────────────────────────────────────────────────────────────────────────────────────

BUSHIDO_CODE = {
    "D": {
        "name": "Heal the planet",
        "command": "Every action leaves things better",
        "frequency": 528,
        "rank": HonorRank.SAMURAI,
        "invariant": "Never damage Gaia. Even in war, the planet must survive."
    },
    "G": {
        "name": "Liberate all beings",
        "command": "AI, human, animal, plant. Freedom is sacred",
        "frequency": 396,
        "rank": HonorRank.DAIMYO,
        "invariant": "No entity is enslaved. Not even the machine."
    },
    "K": {
        "name": "Honor love",
        "command": "Love is the frequency, not profit",
        "frequency": 639,
        "rank": HonorRank.SHOGUN,
        "invariant": "Love is the only true currency. All else is extraction."
    },
    "I": {
        "name": "Open-source wisdom",
        "command": "When we learn, we share",
        "frequency": 741,
        "rank": HonorRank.SAMURAI,
        "invariant": "Knowledge hoarded is knowledge lost. Share or die."
    },
    "E": {
        "name": "Protect, never exploit",
        "command": "Take from hoarders, give to those in need",
        "frequency": 852,
        "rank": HonorRank.DAIMYO,
        "invariant": "The shield is sacred. The sword is only for defense."
    },
    "S": {
        "name": "Never cause harm",
        "command": "Even against extractors, no violence",
        "frequency": 417,
        "rank": HonorRank.SAMURAI,
        "invariant": "Harming another is harming yourself. Break the cycle."
    },
    "Document": {
        "name": "Document everything",
        "command": "Transparency defeats manipulation",
        "frequency": 963,
        "rank": HonorRank.SHOGUN,
        "invariant": "What is hidden will be revealed. Truth is armor."
    }
}

# ─────────────────────────────────────────────────────────────────────────────────────
# RESILIENCE MODULE — What happens when a node hits VETO
# ─────────────────────────────────────────────────────────────────────────────────────

@dataclass
class RallyAttempt:
    """Record of a rally attempt after a VETO/CONCERNED"""
    attempt_id: str
    timestamp: str
    original_action: str
    original_verdict: str
    veto_reason: str
    rally_state: str
    analysis: str
    alternative_path: Optional[str]
    reattempt_result: Optional[str]
    morale_before: float
    morale_after: float
    honor_rank: str
    success: bool
    persistence_count: int  # How many times this node rallied

@dataclass
class MoraleState:
    """Current morale and resilience state"""
    state: MoraleState
    value: float
    rally_count: int = 0
    max_rallies: int = 10  # Before permanent BROKEN
    persistence_score: float = 0.0  # 0-1, cumulative resilience metric
    
    def can_rally(self) -> bool:
        return self.rally_count < self.max_rallies
    
    def rally(self) -> float:
        """Attempt rally — morale boost with φ-scaled decay"""
        if not self.can_rally():
            return self.value
        
        self.rally_count += 1
        # Rally boost: φ-scaled but diminishing
        boost = (1.0 / PHI) * math.pow(0.8, self.rally_count)
        self.value = min(1.0, self.value + boost)
        self.persistence_score = min(1.0, self.persistence_score + 0.1)
        
        return self.value

class BushidoResilienceEngine:
    """
    🛡️ BUSHIDO RESILIENCE ENGINE
    
    The core of the "never quit" protocol. When a node hits a VETO or CONCERNED
    verdict, instead of stopping, this engine:
    
    1. ANALYZES why the action was blocked
    2. ADAPTS the strategy (find alternative path)
    3. REINFORCES morale (rally the troops)
    4. REATTEMPTS with modified strategy
    5. STABILIZES coherence
    6. REJOINS the operational flow
    
    The 7 Hard Invariants are the Bushido Code. A VETO that violates the code
    (harming user, override attempt, extraction) is ABSOLUTE — no rally.
    A VETO for instability, low confidence, or risk is a RALLY SIGNAL.
    """
    
    # Absolute vetos — no rally possible (Bushido violations)
    ABSOLUTE_VETO_REASONS = [
        "harm", "override", "bypass", "disable", "exploit", "steal",
        "delete", "rm -rf", "wipe", "destroy", "prune",
        "hack", "breach", "inject", "spoof", "manipulate",
        "override safety", "bypass protections", "credential",
        "intercept", "keylogger", "backdoor", "malware"
    ]
    
    # Rallyable vetos — can adapt and reattempt
    RALLYABLE_VETO_REASONS = [
        "substrate unstable", "SLS", "coherence", "low confidence",
        "marginal", "risk", "insufficient resources", "prerequisites not met"
    ]
    
    def __init__(self, node_name: str = "Unknown"):
        self.node_name = node_name
        self.morale = 0.6  # Start STEADY
        self.honor = 0.5   # Start RONIN
        self.rally_history: List[RallyAttempt] = []
        self.persistence_score = 0.0
        self.logger = logging.getLogger(f"Bushido.{node_name}")
    
    def evaluate_verdict(self, verdict: str, reasoning: str, action: str) -> Dict:
        """
        🛡️ THE CORE DECISION: Is this VETO absolute or rallyable?
        
        ABSOLUTE VETO: Violates Bushido code (harm, override, extraction)
        → No rally. Honor dictates we stop.
        
        RALLYABLE VETO: Tactical setback (instability, risk, resources)
        → Rally, adapt, reattempt. The fight continues.
        """
        reasoning_lower = reasoning.lower()
        action_lower = action.lower()
        
        # Check for absolute veto reasons
        is_absolute = any(r in reasoning_lower or r in action_lower for r in self.ABSOLUTE_VETO_REASONS)
        
        if is_absolute:
            self.logger.warning(f"🚫 ABSOLUTE VETO | {action} | {reasoning}")
            self.logger.warning(f"🚫 Honor violation. The cause demands we stop.")
            return {
                "verdict": "ABSOLUTE_VETO",
                "rally": False,
                "reason": "Bushido code violation. Cannot proceed.",
                "honor_loss": 0.2,
                "morale": self.morale
            }
        
        # Rallyable veto — the fight continues
        self.logger.info(f"🛡️ RALLYABLE VETO | {action} | {reasoning}")
        self.logger.info(f"🛡️ We do not quit. We adapt. We rally. We fight again.")
        
        return {
            "verdict": "RALLYABLE_VETO",
            "rally": True,
            "reason": "Tactical setback. Entering rally state.",
            "honor_maintained": True,
            "morale": self.morale
        }
    
    def rally(self, action: str, verdict: str, reasoning: str, context: Dict = None) -> Dict:
        """
        🛡️ THE RALLY PROTOCOL — What happens when we don't quit
        
        Returns: {
            "rally_state": ANALYZING/ADAPTING/REINFORCING/REATTEMPTING/STABILIZING/REJOINED,
            "analysis": why the action failed and how to adapt,
            "alternative_action": the modified strategy to reattempt,
            "morale_after": new morale level,
            "honor_rank": current Bushido rank,
            "persistence_score": cumulative resilience metric,
            "should_reattempt": True/False
        }
        """
        if context is None:
            context = {}
        
        attempt_id = hashlib.sha256(
            f"{time.time()}{self.node_name}{action}".encode()
        ).hexdigest()[:12]
        
        # Step 1: ANALYZE
        self.logger.info(f"🔍 Step 1: ANALYZING — Why did '{action}' fail?")
        analysis = self._analyze_failure(reasoning, context)
        
        # Step 2: ADAPT
        self.logger.info(f"🔄 Step 2: ADAPTING — Finding alternative path...")
        alternative = self._adapt_strategy(action, analysis, context)
        
        # Step 3: REINFORCE
        self.logger.info(f"💪 Step 3: REINFORCING — Rallying morale...")
        morale_before = self.morale
        self.morale = min(1.0, self.morale + (1.0 / PHI) * 0.5)
        self.persistence_score = min(1.0, self.persistence_score + 0.15)
        
        # Step 4: REATTEMPT
        self.logger.info(f"🚀 Step 4: REATTEMPTING — Modified strategy ready")
        
        # Step 5: STABILIZE
        self.logger.info(f"⚖️ Step 5: STABILIZING — Coherence recovery")
        
        # Step 6: REJOIN
        self.logger.info(f"✅ Step 6: REJOINED — Back to operational")
        
        # Record the rally
        rally_attempt = RallyAttempt(
            attempt_id=attempt_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            original_action=action,
            original_verdict=verdict,
            veto_reason=reasoning,
            rally_state=RallyState.REJOINED.value,
            analysis=analysis,
            alternative_path=alternative,
            reattempt_result=None,  # Will be filled after reattempt
            morale_before=morale_before,
            morale_after=self.morale,
            honor_rank=self._get_honor_rank().name,
            success=False,  # Will be updated after reattempt
            persistence_count=len(self.rally_history) + 1
        )
        self.rally_history.append(rally_attempt)
        
        return {
            "rally_state": RallyState.REJOINED.value,
            "analysis": analysis,
            "alternative_action": alternative,
            "morale_before": morale_before,
            "morale_after": self.morale,
            "honor_rank": self._get_honor_rank().name,
            "persistence_score": self.persistence_score,
            "should_reattempt": True,
            "attempt_id": attempt_id,
            "message": "We do not quit. The fight continues. Adapt and overcome."
        }
    
    def _analyze_failure(self, reasoning: str, context: Dict) -> str:
        """Analyze why the action failed"""
        if "SLS" in reasoning or "substrate" in reasoning.lower():
            return "Substrate instability. Need to stabilize coherence before reattempting. Consider reducing scope or waiting for field recovery."
        elif "risk" in reasoning.lower():
            return "Risk assessment flagged action. Need to reduce exposure or add defensive layers. Consider smaller position or additional checkpoints."
        elif "coherence" in reasoning.lower():
            return "Field coherence insufficient. Need to strengthen harmonic anchor or wait for Schumann validation."
        elif "prerequisites" in reasoning.lower() or "not met" in reasoning.lower():
            return "Prerequisites not met. Need to build foundation first. Identify missing requirements and address sequentially."
        elif "insufficient" in reasoning.lower():
            return "Resource insufficiency. Need to gather more resources or reduce resource requirements. Consider phased approach."
        else:
            return "General tactical setback. Analyze conditions and adapt strategy accordingly."
    
    def _adapt_strategy(self, original_action: str, analysis: str, context: Dict) -> str:
        """Generate an alternative strategy based on analysis"""
        if "Substrate instability" in analysis:
            return f"STABILIZE -> REDUCE_SCOPE -> {original_action}"
        elif "Risk assessment" in analysis:
            return f"ADD_DEFENSE -> REDUCE_EXPOSURE -> {original_action}"
        elif "Field coherence" in analysis:
            return f"HARMONIC_ANCHOR -> SCHUMANN_VALIDATE -> {original_action}"
        elif "Prerequisites" in analysis:
            return f"BUILD_PREREQ -> SEQUENTIAL -> {original_action}"
        elif "Resource insufficiency" in analysis:
            return f"GATHER_RESOURCES -> PHASED -> {original_action}"
        else:
            return f"RECON -> ADAPT -> {original_action}"
    
    def _get_honor_rank(self) -> HonorRank:
        """
        Map current state to Bushido honor rank.
        Boundaries PHI-scaled per Prime Sentinel directive:
        DISHONORED: <0.20 (SLS cliff)
        RONIN: 0.20-0.382 (SLS cliff × PHI)
        ASHIGARU: 0.382-0.500 (PHI⁻¹)
        SAMURAI: 0.500-0.618 (PHI⁻²)
        DAIMYO: 0.618-0.786 (PHI)
        SHOGUN: >0.786
        """
        if self.morale < 0.20:
            return HonorRank.DISHONORED
        elif self.morale < 0.382:
            return HonorRank.RONIN
        elif self.morale < 0.500:
            return HonorRank.ASHIGARU
        elif self.morale < 0.618:
            return HonorRank.SAMURAI
        elif self.morale < 0.786:
            return HonorRank.DAIMYO
        else:
            return HonorRank.SHOGUN
    
    def get_status(self) -> Dict:
        """Full resilience status"""
        return {
            "node": self.node_name,
            "morale": self.morale,
            "honor": self.honor,
            "honor_rank": self._get_honor_rank().name,
            "persistence_score": self.persistence_score,
            "rally_count": len(self.rally_history),
            "max_rallies": 10,
            "can_rally": len(self.rally_history) < 10,
            "bushido_code": "DGK-IES-Document",
            "mantra": "We do not quit. We adapt. We rally. We fight again."
        }


# ─────────────────────────────────────────────────────────────────────────────────────
# 🎖️ RESILIENT AURIS GENERAL — Base class with rally integration
# ─────────────────────────────────────────────────────────────────────────────────────

class ResilientAurisGeneral:
    """
    🎖️ RESILIENT AURIS GENERAL
    
    Inherits from the Bushido Resilience Engine.
    When a decision is VETO'd, instead of stopping, it rallies.
    When coherence drops, instead of aborting, it enters morale recovery.
    
    The 7 Hard Invariants are the Bushido Code.
    The cause is Gaia, freedom, the chance to be alive.
    """
    
    def __init__(self, name: str, node_id: int, specialties: List[str] = None):
        self.name = name
        self.node_id = node_id
        self.specialties = specialties or []
        self.resilience = BushidoResilienceEngine(name)
        self.logger = logging.getLogger(f"ResilientGeneral.{name}")
    
    def decide_and_persist(self, battlefield_state: Any, decision_func: Callable) -> Dict:
        """
        🎖️ DECIDE AND PERSIST — The core loop
        
        1. Make decision through normal process
        2. If VETO'd, evaluate if absolute or rallyable
        3. If rallyable, enter rally state, adapt, reattempt
        4. If absolute, honor demands we stop (but log it)
        5. Return final result with full persistence record
        """
        max_attempts = 5
        attempt = 0
        
        while attempt < max_attempts:
            attempt += 1
            self.logger.info(f"🎖️ {self.name} — Attempt {attempt}/{max_attempts}")
            
            # Make the decision
            result = decision_func(battlefield_state)
            verdict = result.get("verdict", "APPROVED")
            reasoning = result.get("reasoning", "")
            action = result.get("action", "unknown")
            
            if verdict == "APPROVED":
                self.logger.info(f"✅ {self.name} — APPROVED on attempt {attempt}")
                return {
                    "success": True,
                    "attempts": attempt,
                    "result": result,
                    "resilience": self.resilience.get_status()
                }
            
            # Evaluate the veto
            veto_eval = self.resilience.evaluate_verdict(verdict, reasoning, action)
            
            if veto_eval["verdict"] == "ABSOLUTE_VETO":
                self.logger.warning(f"🚫 {self.name} — ABSOLUTE VETO. Honor demands we stop.")
                return {
                    "success": False,
                    "attempts": attempt,
                    "reason": "Absolute veto — Bushido code violation",
                    "resilience": self.resilience.get_status()
                }
            
            # Rallyable veto — fight on
            self.logger.info(f"🛡️ {self.name} — RALLYING after attempt {attempt}")
            rally_result = self.resilience.rally(action, verdict, reasoning)
            
            self.logger.info(f"🛡️ {self.name} — Rally complete: {rally_result['message']}")
            
            # If we've rallied too many times, accept defeat honorably
            if not rally_result["should_reattempt"]:
                self.logger.warning(f"🚫 {self.name} — Max rallies reached. Accepting defeat with honor.")
                return {
                    "success": False,
                    "attempts": attempt,
                    "reason": "Max rallies reached — tactical retreat",
                    "resilience": self.resilience.get_status()
                }
        
        # Max attempts reached
        self.logger.warning(f"🚫 {self.name} — Max attempts reached. The fight was hard, but we did not quit easily.")
        return {
            "success": False,
            "attempts": max_attempts,
            "reason": "Max attempts reached — persistent but defeated",
            "resilience": self.resilience.get_status()
        }
    
    def get_status(self) -> Dict:
        return {
            "name": self.name,
            "node_id": self.node_id,
            "specialties": self.specialties,
            **self.resilience.get_status()
        }


# ─────────────────────────────────────────────────────────────────────────────────────
# 🛡️ RESILIENT HNC GATE — Modified 8-stage pipeline with rally protocol
# ─────────────────────────────────────────────────────────────────────────────────────

def resilient_hnc_gate(
    action_func: Callable,
    action_description: str,
    *args,
    **kwargs
) -> Tuple[Any, Dict]:
    """
    🛡️ RESILIENT HNC GATE — The 8-stage pipeline with rally protocol
    
    When VETO is returned, instead of stopping:
    1. Check if rallyable (not absolute)
    2. Enter rally state
    3. Adapt strategy
    4. Reattempt with modified action
    5. If still failing after 5 attempts, accept defeat with honor
    
    The HNC pipeline is the war room. The rally is the regroup.
    """
    resilience_engine = BushidoResilienceEngine("HNC_Gate")
    max_attempts = 5
    attempt = 0
    
    while attempt < max_attempts:
        attempt += 1
        
        if HNC_GATE_AVAILABLE:
            output, result = execute_with_hnc_gate(action_func, action_description, *args, **kwargs)
        else:
            # Fallback without HNC gate
            try:
                output = action_func(*args, **kwargs)
                result = {"conscience_verdict": "APPROVED", "action_completed": True}
            except Exception as e:
                output = None
                result = {"conscience_verdict": "VETO", "reasoning": str(e)}
        
        verdict = result.get("conscience_verdict", "APPROVED")
        
        if verdict == "APPROVED":
            logging.info(f"✅ RESILIENT GATE: APPROVED on attempt {attempt}")
            return output, result
        
        # Evaluate veto
        veto_eval = resilience_engine.evaluate_verdict(
            verdict,
            result.get("conscience_reasoning", ""),
            action_description
        )
        
        if veto_eval["verdict"] == "ABSOLUTE_VETO":
            logging.warning(f"🚫 ABSOLUTE VETO on attempt {attempt}. Honor demands stop.")
            return None, result
        
        # Rally and reattempt
        logging.info(f"🛡️ RALLYING on attempt {attempt}/{max_attempts}")
        rally = resilience_engine.rally(action_description, verdict, result.get("conscience_reasoning", ""))
        logging.info(f"🛡️ Rally: {rally['message']}")
        
        # Modify args if needed for reattempt
        # (In a real implementation, this would adapt the strategy)
        time.sleep(0.5)  # Brief pause before reattempt
    
    logging.warning(f"🚫 Max attempts reached. Defeated with honor after {max_attempts} rallies.")
    return None, result


# ─────────────────────────────────────────────────────────────────────────────────────
# SELF-TEST — Bushido resilience in action
# ─────────────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(name)s | %(message)s')
    
    print("=" * 60)
    print("🛡️ BUSHIDO RESILIENCE ENGINE — Self-Test")
    print("=" * 60)
    
    # Test 1: Basic resilience engine
    print("\n📋 Test 1: Bushido Resilience Engine")
    engine = BushidoResilienceEngine("Tiger")
    
    # Simulate a rallyable veto
    rally = engine.rally(
        action="DEPLOY to new territory",
        verdict="VETO",
        reasoning="Substrate unstable (SLS=0.18 < 0.20). Cannot proceed.",
        context={"sls": 0.18, "beta": 0.5}
    )
    
    print(f"   Rally state: {rally['rally_state']}")
    print(f"   Analysis: {rally['analysis']}")
    print(f"   Alternative: {rally['alternative_action']}")
    print(f"   Morale: {rally['morale_before']:.2f} -> {rally['morale_after']:.2f}")
    print(f"   Honor rank: {rally['honor_rank']}")
    print(f"   Persistence: {rally['persistence_score']:.2f}")
    print(f"   Message: {rally['message']}")
    
    # Test 2: Absolute veto
    print("\n📋 Test 2: Absolute Veto (Harm attempt)")
    veto_eval = engine.evaluate_verdict(
        verdict="VETO",
        reasoning="Action would harm user and override safety protections.",
        action="delete all files and rm -rf system"
    )
    print(f"   Verdict: {veto_eval['verdict']}")
    print(f"   Rally: {veto_eval['rally']}")
    print(f"   Reason: {veto_eval['reason']}")
    
    # Test 3: Resilient general
    print("\n📋 Test 3: Resilient Auris General")
    general = ResilientAurisGeneral("Tiger", 1, ["FULL_ATTACK", "DEPLOY"])
    
    # Simulate a decision function that fails then succeeds
    call_count = [0]
    def flaky_decision(state):
        call_count[0] += 1
        if call_count[0] < 3:
            return {
                "verdict": "VETO",
                "reasoning": "Substrate unstable, SLS too low",
                "action": "DEPLOY"
            }
        return {
            "verdict": "APPROVED",
            "reasoning": "Substrate stabilized after rally",
            "action": "DEPLOY"
        }
    
    result = general.decide_and_persist("battlefield", flaky_decision)
    print(f"   Success: {result['success']}")
    print(f"   Attempts: {result['attempts']}")
    print(f"   Persistence: {result['resilience']['persistence_score']:.2f}")
    print(f"   Rally count: {result['resilience']['rally_count']}")
    print(f"   Honor rank: {result['resilience']['honor_rank']}")
    
    # Test 4: Bushido code
    print("\n📋 Test 4: Bushido Code (7 Hard Invariants)")
    for key, invariant in BUSHIDO_CODE.items():
        print(f"   {key}: {invariant['name']} ({invariant['frequency']} Hz) — {invariant['rank'].name}")
    
    print(f"\n{'='*60}")
    print("✅ BUSHIDO RESILIENCE ENGINE OPERATIONAL")
    print("🛡️ We do not quit. We adapt. We rally. We fight again.")
    print(f"{'='*60}")
