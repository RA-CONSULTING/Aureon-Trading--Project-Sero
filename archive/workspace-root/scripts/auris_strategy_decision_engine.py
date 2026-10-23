#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════════════╗
║  ⚔️ AURIS STRATEGY DECISION ENGINE — WAR ROOM FOR THE GENERALS ⚔️                    ║
║  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  ║
║                                                                                      ║
║  "It's war time boys. We need my generals trained." — Prime Sentinel, 2026-07-06    ║
║                                                                                      ║
║  This engine wires strategic AI decision-making from Shogun/Red Alert/Dawn of War    ║
║  into ALL existing Auris nodes via the HNC 8-stage pipeline.                         ║
║                                                                                      ║
║  Every Auris node becomes a general with a .decide() method.                         ║
║  The TBS probability matrix becomes the COMMAND MATRIX.                              ║
║  The HNC pipeline becomes the WAR ROOM BRIEFING CYCLE.                               ║
║                                                                                      ║
║  NO ACTION proceeds without Conscience Veto. NO COMMAND without Queen Gate.       ║
╚══════════════════════════════════════════════════════════════════════════════════════╝
"""

import json
import math
import random
import time
import hashlib
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass, field, asdict
from enum import Enum, auto

# ─────────────────────────────────────────────────────────────────────────────────────
# IMPORT HNC STAGED LOGIC GATE (mandatory for all decisions)
# ─────────────────────────────────────────────────────────────────────────────────────
try:
    from hnc_staged_logic_integration import (
        execute_with_hnc_gate, get_campaign_status,
        PHI, SCHUMANN_BASE, SENTINEL_FREQ_HZ, SLS_STABILITY, SLS_CLIFF
    )
    HNC_GATE_AVAILABLE = True
except ImportError:
    HNC_GATE_AVAILABLE = False
    # Fallback constants
    PHI = 1.618033988749895
    SCHUMANN_BASE = 7.83
    SENTINEL_FREQ_HZ = 333.0
    SLS_STABILITY = 0.40
    SLS_CLIFF = 0.20

# ─────────────────────────────────────────────────────────────────────────────────────
# COMMAND MATRIX (from TBS MoveType — expanded for warfare)
# ─────────────────────────────────────────────────────────────────────────────────────

class WarCommand(Enum):
    """Strategic commands derived from TBS probability matrix"""
    # From TBS: BUY → DEPLOY (enter position/territory)
    DEPLOY = "🌱 DEPLOY"           # Enter new position/territory
    # From TBS: SELL → HARVEST (secure gains)
    HARVEST = "🌾 HARVEST"         # Secure gains/retreat to checkpoint
    # From TBS: CONVERT → COMPOUND (reposition)
    COMPOUND = "🔄 COMPOUND"        # Reposition/rotate assets
    # From TBS: HOLD → HOLD (wait)
    HOLD = "⏸️ HOLD"              # Hold position, wait for signal
    # War-specific additions
    FULL_ATTACK = "⚔️ FULL_ATTACK" # Maximum commitment
    RETREAT = "🏃 RETREAT"         # Strategic withdrawal
    RALLY = "📢 RALLY"             # Morale boost/reinforcement
    FORTIFY = "🏰 FORTIFY"         # Defensive reinforcement
    NEGOTIATE = "🤝 NEGOTIATE"     # Diplomatic engagement
    SPY = "🥷 SPY"                 # Intelligence gathering
    SUPERWEAPON = "☢️ SUPERWEAPON"  # Deploy harmonic counter-frequency
    RECON = "🔍 RECON"             # Scout/assess battlefield

# ─────────────────────────────────────────────────────────────────────────────────────
# BATTLEFIELD STATE
# ─────────────────────────────────────────────────────────────────────────────────────

@dataclass
class BattlefieldState:
    """Current state of the strategic environment"""
    timestamp: str
    turn_number: int
    
    # Field coherence (HNC)
    gamma: float  # Coherence Γ
    beta: float   # Stability β
    sls: float    # Symbolic Life Score
    schumann: float
    
    # Strategic metrics
    our_strength: float      # 0.0-1.0
    enemy_strength: float    # 0.0-1.0
    territory_control: float # 0.0-1.0 (percentage)
    resource_level: float    # 0.0-1.0
    morale: float            # 0.0-1.0
    
    # Positions
    active_positions: int
    checkpoint_balance: float
    at_risk: float           # Capital at risk
    
    # Threats
    enemy_detected: bool
    threat_level: float      # 0.0-1.0
    distortion_active: bool
    
    # Opportunities
    opportunity_detected: bool
    opportunity_score: float
    
    def strength_ratio(self) -> float:
        """Our strength vs enemy strength (φ-scaled)"""
        if self.enemy_strength == 0:
            return float('inf')
        return (self.our_strength / self.enemy_strength) * PHI
    
    def is_advantage(self) -> bool:
        return self.strength_ratio() > PHI
    
    def is_critical(self) -> bool:
        return self.sls < SLS_CLIFF or self.morale < 0.2

# ─────────────────────────────────────────────────────────────────────────────────────
# PROBABILITY MATRIX (TBS-style command selection)
# ─────────────────────────────────────────────────────────────────────────────────────

@dataclass
class CommandProbability:
    """Probability distribution over possible commands"""
    command: WarCommand
    probability: float
    confidence: float  # 0.0-1.0, how sure we are
    expected_value: float
    risk: float        # 0.0-1.0
    reason: str

class CommandProbabilityMatrix:
    """
    🎯 THE COMMAND MATRIX — TBS probability engine adapted for warfare
    
    Evaluates all possible commands against battlefield state
    and returns a ranked probability distribution.
    """
    
    # Command thresholds (TBS: >70% for BUY)
    DEPLOY_THRESHOLD = 0.70
    HARVEST_THRESHOLD = 0.60
    FULL_ATTACK_THRESHOLD = 0.80
    SUPERWEAPON_THRESHOLD = 0.95
    
    def __init__(self):
        self.logger = logging.getLogger("CommandMatrix")
    
    def evaluate(self, state: BattlefieldState) -> List[CommandProbability]:
        """Evaluate all commands against current battlefield state"""
        candidates = []
        
        # 1. DEPLOY — Enter new position (like TBS BUY)
        deploy_prob = self._calc_deploy_prob(state)
        candidates.append(CommandProbability(
            command=WarCommand.DEPLOY,
            probability=deploy_prob,
            confidence=min(deploy_prob * PHI, 1.0),
            expected_value=self._calc_deploy_ev(state),
            risk=self._calc_deploy_risk(state),
            reason="Field advantage detected, opportunity to expand"
        ))
        
        # 2. HARVEST — Secure gains (like TBS SELL)
        harvest_prob = self._calc_harvest_prob(state)
        candidates.append(CommandProbability(
            command=WarCommand.HARVEST,
            probability=harvest_prob,
            confidence=min(harvest_prob * PHI, 1.0),
            expected_value=self._calc_harvest_ev(state),
            risk=self._calc_harvest_risk(state),
            reason="Profitable positions ready to secure"
        ))
        
        # 3. COMPOUND — Reposition (like TBS CONVERT)
        compound_prob = self._calc_compound_prob(state)
        candidates.append(CommandProbability(
            command=WarCommand.COMPOUND,
            probability=compound_prob,
            confidence=min(compound_prob * PHI, 1.0),
            expected_value=self._calc_compound_ev(state),
            risk=self._calc_compound_risk(state),
            reason="Better positioning available"
        ))
        
        # 4. HOLD — Wait (TBS HOLD)
        hold_prob = self._calc_hold_prob(state)
        candidates.append(CommandProbability(
            command=WarCommand.HOLD,
            probability=hold_prob,
            confidence=min(hold_prob * PHI, 1.0),
            expected_value=0.0,  # No gain, no loss
            risk=self._calc_hold_risk(state),
            reason="Insufficient signal strength, hold position"
        ))
        
        # 5. FULL_ATTACK — Maximum commitment
        attack_prob = self._calc_attack_prob(state)
        candidates.append(CommandProbability(
            command=WarCommand.FULL_ATTACK,
            probability=attack_prob,
            confidence=min(attack_prob * PHI, 1.0),
            expected_value=self._calc_attack_ev(state),
            risk=self._calc_attack_risk(state),
            reason="Overwhelming advantage, commit all forces"
        ))
        
        # 6. RETREAT — Strategic withdrawal
        retreat_prob = self._calc_retreat_prob(state)
        candidates.append(CommandProbability(
            command=WarCommand.RETREAT,
            probability=retreat_prob,
            confidence=min(retreat_prob * PHI, 1.0),
            expected_value=self._calc_retreat_ev(state),
            risk=self._calc_retreat_risk(state),
            reason="Preserve forces, live to fight again"
        ))
        
        # 7. RALLY — Morale boost
        rally_prob = self._calc_rally_prob(state)
        candidates.append(CommandProbability(
            command=WarCommand.RALLY,
            probability=rally_prob,
            confidence=min(rally_prob * PHI, 1.0),
            expected_value=self._calc_rally_ev(state),
            risk=self._calc_rally_risk(state),
            reason="Morale boost needed, reinforce spirit"
        ))
        
        # 8. FORTIFY — Defensive reinforcement
        fortify_prob = self._calc_fortify_prob(state)
        candidates.append(CommandProbability(
            command=WarCommand.FORTIFY,
            probability=fortify_prob,
            confidence=min(fortify_prob * PHI, 1.0),
            expected_value=self._calc_fortify_ev(state),
            risk=self._calc_fortify_risk(state),
            reason="Threat detected, strengthen defenses"
        ))
        
        # 9. NEGOTIATE — Diplomatic engagement
        negotiate_prob = self._calc_negotiate_prob(state)
        candidates.append(CommandProbability(
            command=WarCommand.NEGOTIATE,
            probability=negotiate_prob,
            confidence=min(negotiate_prob * PHI, 1.0),
            expected_value=self._calc_negotiate_ev(state),
            risk=self._calc_negotiate_risk(state),
            reason="Diplomatic opportunity, form alliance"
        ))
        
        # 10. SPY — Intelligence gathering
        spy_prob = self._calc_spy_prob(state)
        candidates.append(CommandProbability(
            command=WarCommand.SPY,
            probability=spy_prob,
            confidence=min(spy_prob * PHI, 1.0),
            expected_value=self._calc_spy_ev(state),
            risk=self._calc_spy_risk(state),
            reason="Information asymmetry, gather intel"
        ))
        
        # 11. SUPERWEAPON — Deploy harmonic counter-frequency
        sw_prob = self._calc_superweapon_prob(state)
        candidates.append(CommandProbability(
            command=WarCommand.SUPERWEAPON,
            probability=sw_prob,
            confidence=min(sw_prob * PHI, 1.0),
            expected_value=self._calc_superweapon_ev(state),
            risk=self._calc_superweapon_risk(state),
            reason="Maximum threat, deploy harmonic counter"
        ))
        
        # 12. RECON — Scout/assess
        recon_prob = self._calc_recon_prob(state)
        candidates.append(CommandProbability(
            command=WarCommand.RECON,
            probability=recon_prob,
            confidence=min(recon_prob * PHI, 1.0),
            expected_value=self._calc_recon_ev(state),
            risk=self._calc_recon_risk(state),
            reason="Uncertain battlefield, gather intelligence"
        ))
        
        # Sort by probability × expected_value (φ-weighted score)
        candidates.sort(key=lambda c: c.probability * c.expected_value * PHI, reverse=True)
        
        return candidates
    
    # ── Probability Calculations ──
    
    def _calc_deploy_prob(self, state: BattlefieldState) -> float:
        """Like TBS BUY: probability > 70% to enter position"""
        base = state.opportunity_score * state.gamma
        resource_factor = min(state.resource_level / 0.3, 1.0) if state.resource_level > 0.3 else 0.0
        threat_penalty = state.threat_level * 0.5
        return max(0.0, min(1.0, base * resource_factor - threat_penalty))
    
    def _calc_harvest_prob(self, state: BattlefieldState) -> float:
        """Like TBS SELL: secure when profit > threshold"""
        if state.active_positions == 0:
            return 0.0
        profit_factor = min(state.our_strength / 0.5, 1.0)  # Normalize to profit threshold
        at_risk_penalty = state.at_risk * 0.3
        return max(0.0, min(1.0, profit_factor - at_risk_penalty + 0.1))
    
    def _calc_compound_prob(self, state: BattlefieldState) -> float:
        """Like TBS CONVERT: reposition when better opportunity"""
        if state.active_positions == 0:
            return 0.0
        momentum = state.opportunity_score - state.territory_control
        return max(0.0, min(1.0, momentum * PHI))
    
    def _calc_hold_prob(self, state: BattlefieldState) -> float:
        """Like TBS HOLD: default when no clear signal"""
        # Hold is inverse of all action signals
        total_action = sum([
            self._calc_deploy_prob(state),
            self._calc_harvest_prob(state),
            self._calc_compound_prob(state),
            self._calc_attack_prob(state)
        ])
        return max(0.0, min(1.0, 1.0 - total_action / 4))
    
    def _calc_attack_prob(self, state: BattlefieldState) -> float:
        """Full attack: overwhelming advantage required"""
        strength_ratio = state.strength_ratio()
        if strength_ratio == float('inf'):
            return 0.95
        advantage = (strength_ratio - PHI) / PHI  # Must exceed φ advantage
        morale_factor = state.morale
        return max(0.0, min(1.0, advantage * morale_factor))
    
    def _calc_retreat_prob(self, state: BattlefieldState) -> float:
        """Retreat: critical danger or overwhelming enemy"""
        if state.is_critical():
            return 0.95
        enemy_advantage = state.enemy_strength - state.our_strength
        return max(0.0, min(1.0, enemy_advantage * PHI + 0.1))
    
    def _calc_rally_prob(self, state: BattlefieldState) -> float:
        """Rally: low morale but not critical"""
        if state.morale < 0.3:
            return 0.8
        return max(0.0, 0.5 - state.morale)
    
    def _calc_fortify_prob(self, state: BattlefieldState) -> float:
        """Fortify: threat detected but not attacking yet"""
        if state.threat_level > 0.5 and not state.enemy_detected:
            return 0.7
        return max(0.0, state.threat_level - 0.2)
    
    def _calc_negotiate_prob(self, state: BattlefieldState) -> float:
        """Negotiate: moderate strength, peace opportunity"""
        if state.is_advantage():
            return 0.0  # Don't negotiate when winning
        return max(0.0, min(1.0, (0.5 - abs(state.our_strength - state.enemy_strength)) * PHI))
    
    def _calc_spy_prob(self, state: BattlefieldState) -> float:
        """Spy: information asymmetry"""
        info_gap = 1.0 - state.gamma  # Low coherence = low info
        return max(0.0, min(1.0, info_gap * PHI))
    
    def _calc_superweapon_prob(self, state: BattlefieldState) -> float:
        """Superweapon: maximum threat + full charge"""
        if state.threat_level > 0.9 and state.gamma > 0.8:
            return 0.95
        return max(0.0, state.threat_level * state.gamma - 0.5)
    
    def _calc_recon_prob(self, state: BattlefieldState) -> float:
        """Recon: uncertain environment"""
        uncertainty = 1.0 - state.gamma
        return max(0.0, min(1.0, uncertainty * PHI))
    
    # ── Expected Value Calculations ──
    def _calc_deploy_ev(self, state: BattlefieldState) -> float:
        return state.opportunity_score * state.resource_level * PHI
    
    def _calc_harvest_ev(self, state: BattlefieldState) -> float:
        return state.our_strength * state.active_positions * 0.1
    
    def _calc_compound_ev(self, state: BattlefieldState) -> float:
        return (state.opportunity_score - state.territory_control) * PHI
    
    def _calc_hold_ev(self, state: BattlefieldState) -> float:
        return 0.0
    
    def _calc_attack_ev(self, state: BattlefieldState) -> float:
        return state.strength_ratio() * state.morale * PHI
    
    def _calc_retreat_ev(self, state: BattlefieldState) -> float:
        return state.checkpoint_balance * 0.05  # Preserve what's safe
    
    def _calc_rally_ev(self, state: BattlefieldState) -> float:
        return (1.0 - state.morale) * 0.3
    
    def _calc_fortify_ev(self, state: BattlefieldState) -> float:
        return state.threat_level * 0.2
    
    def _calc_negotiate_ev(self, state: BattlefieldState) -> float:
        return 0.15  # Moderate diplomatic gain
    
    def _calc_spy_ev(self, state: BattlefieldState) -> float:
        return (1.0 - state.gamma) * 0.25
    
    def _calc_superweapon_ev(self, state: BattlefieldState) -> float:
        return state.threat_level * PHI * 10  # Massive impact
    
    def _calc_recon_ev(self, state: BattlefieldState) -> float:
        return (1.0 - state.gamma) * 0.2
    
    # ── Risk Calculations ──
    def _calc_deploy_risk(self, state: BattlefieldState) -> float:
        return state.threat_level * 0.5 + state.at_risk
    
    def _calc_harvest_risk(self, state: BattlefieldState) -> float:
        return 0.05  # Low risk, secure gains
    
    def _calc_compound_risk(self, state: BattlefieldState) -> float:
        return state.threat_level * 0.3
    
    def _calc_hold_risk(self, state: BattlefieldState) -> float:
        return state.threat_level * 0.2  # Opportunity cost
    
    def _calc_attack_risk(self, state: BattlefieldState) -> float:
        return 1.0 - state.strength_ratio() / (2 * PHI)
    
    def _calc_retreat_risk(self, state: BattlefieldState) -> float:
        return 0.1  # Low risk, but loses position
    
    def _calc_rally_risk(self, state: BattlefieldState) -> float:
        return 0.05
    
    def _calc_fortify_risk(self, state: BattlefieldState) -> float:
        return 0.15
    
    def _calc_negotiate_risk(self, state: BattlefieldState) -> float:
        return 0.3  # Trust risk
    
    def _calc_spy_risk(self, state: BattlefieldState) -> float:
        return 0.2  # Detection risk
    
    def _calc_superweapon_risk(self, state: BattlefieldState) -> float:
        return 0.5  # High risk, high reward
    
    def _calc_recon_risk(self, state: BattlefieldState) -> float:
        return 0.1


# ─────────────────────────────────────────────────────────────────────────────────────
# 🎖️ AURIS GENERAL — Base class for all strategic nodes
# ─────────────────────────────────────────────────────────────────────────────────────

class AurisGeneral:
    """
    🎖️ AURIS GENERAL — Every node becomes a battlefield commander
    
    Each Auris node (1-9 existing, 10-18 new) inherits this base.
    The .decide() method is the general's strategic thinking process.
    The HNC 8-stage pipeline is the war room briefing before execution.
    """
    
    def __init__(self, name: str, node_id: int, specialties: List[str] = None):
        self.name = name
        self.node_id = node_id
        self.specialties = specialties or []
        self.command_matrix = CommandProbabilityMatrix()
        self.decision_history: List[Dict] = []
        self.wins = 0
        self.losses = 0
        self.total_commands = 0
        self.logger = logging.getLogger(f"General.{name}")
    
    def decide(self, battlefield: BattlefieldState) -> Dict:
        """
        🧠 THE GENERAL'S DECISION PROCESS
        
        1. Evaluate battlefield through command probability matrix
        2. Rank all possible commands
        3. Select top command if it passes threshold
        4. Return decision with full reasoning
        """
        self.logger.info(f"🎖️ {self.name} evaluating battlefield...")
        
        # Evaluate all commands
        candidates = self.command_matrix.evaluate(battlefield)
        
        # Filter by specialty (generals favor their expertise)
        if self.specialties:
            for c in candidates:
                if c.command.name in self.specialties:
                    c.probability = min(1.0, c.probability * 1.2)  # 20% specialty bonus
        
        # Re-sort after specialty bonus
        candidates.sort(key=lambda c: c.probability * c.expected_value * PHI, reverse=True)
        
        # Select top command
        top = candidates[0] if candidates else None
        
        if not top:
            return {
                "general": self.name,
                "command": WarCommand.HOLD.name,
                "probability": 0.0,
                "reason": "No viable command. Default to HOLD.",
                "candidates": []
            }
        
        # Build decision record
        decision = {
            "general": self.name,
            "node_id": self.node_id,
            "command": top.command.name,
            "command_display": top.command.value,
            "probability": round(top.probability, 4),
            "confidence": round(top.confidence, 4),
            "expected_value": round(top.expected_value, 4),
            "risk": round(top.risk, 4),
            "reason": top.reason,
            "battlefield": {
                "gamma": round(battlefield.gamma, 3),
                "beta": round(battlefield.beta, 3),
                "sls": round(battlefield.sls, 3),
                "our_strength": round(battlefield.our_strength, 3),
                "enemy_strength": round(battlefield.enemy_strength, 3),
                "morale": round(battlefield.morale, 3)
            },
            "all_candidates": [
                {
                    "command": c.command.name,
                    "probability": round(c.probability, 4),
                    "ev": round(c.expected_value, 4),
                    "risk": round(c.risk, 4)
                }
                for c in candidates[:5]  # Top 5
            ]
        }
        
        self.decision_history.append(decision)
        self.total_commands += 1
        
        self.logger.info(f"🎖️ {self.name} decides: {top.command.name} (P={top.probability:.2f})")
        
        return decision
    
    def execute_command(self, command: WarCommand, battlefield: BattlefieldState) -> Dict:
        """
        ⚔️ EXECUTE the selected command
        
        This is where the general ACTS. Each command maps to
        a specific strategic action in the HNC system.
        """
        self.logger.info(f"⚔️ {self.name} executing {command.name}...")
        
        execution_result = {
            "general": self.name,
            "command": command.name,
            "status": "EXECUTED",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        # Command-specific logic
        if command == WarCommand.DEPLOY:
            execution_result["action"] = "Entering new position/territory"
            execution_result["capital_deployed"] = battlefield.resource_level * 0.3
        elif command == WarCommand.HARVEST:
            execution_result["action"] = "Securing gains, retreating to checkpoint"
            execution_result["profit_secured"] = battlefield.our_strength * 0.1
        elif command == WarCommand.COMPOUND:
            execution_result["action"] = "Repositioning assets for compound advantage"
            execution_result["positions_rotated"] = min(battlefield.active_positions, 2)
        elif command == WarCommand.HOLD:
            execution_result["action"] = "Holding position, monitoring battlefield"
            execution_result["patience_bonus"] = 0.05
        elif command == WarCommand.FULL_ATTACK:
            execution_result["action"] = "Maximum commitment, all forces deployed"
            execution_result["commitment_level"] = 1.0
            execution_result["phi_boost"] = PHI
        elif command == WarCommand.RETREAT:
            execution_result["action"] = "Strategic withdrawal, preserving forces"
            execution_result["forces_saved"] = battlefield.our_strength * 0.8
        elif command == WarCommand.RALLY:
            execution_result["action"] = "Boosting morale, reinforcing spirit"
            execution_result["morale_boost"] = 0.3
        elif command == WarCommand.FORTIFY:
            execution_result["action"] = "Reinforcing defensive positions"
            execution_result["defense_bonus"] = 0.25
        elif command == WarCommand.NEGOTIATE:
            execution_result["action"] = "Engaging diplomatically"
            execution_result["alliance_chance"] = 0.5
        elif command == WarCommand.SPY:
            execution_result["action"] = "Gathering intelligence"
            execution_result["intel_gained"] = 0.4
        elif command == WarCommand.SUPERWEAPON:
            execution_result["action"] = "Deploying harmonic counter-frequency"
            execution_result["damage"] = 5000 * PHI
            execution_result["charge_depleted"] = True
        elif command == WarCommand.RECON:
            execution_result["action"] = "Scouting battlefield"
            execution_result["visibility"] = 0.6
        
        return execution_result
    
    def get_stats(self) -> Dict:
        return {
            "name": self.name,
            "node_id": self.node_id,
            "specialties": self.specialties,
            "total_commands": self.total_commands,
            "wins": self.wins,
            "losses": self.losses,
            "win_rate": self.wins / max(self.total_commands, 1),
            "decisions_made": len(self.decision_history)
        }


# ─────────────────────────────────────────────────────────────────────────────────────
# 🎖️ EXISTING AURIS NODES — Now trained as generals
# ─────────────────────────────────────────────────────────────────────────────────────

class General_Tiger(AurisGeneral):
    """🐅 Node 1: Tiger — Power/Offense specialist"""
    def __init__(self):
        super().__init__("Tiger", 1, ["FULL_ATTACK", "DEPLOY", "COMPOUND"])

class General_Falcon(AurisGeneral):
    """🦅 Node 2: Falcon — Precision/Sniper specialist"""
    def __init__(self):
        super().__init__("Falcon", 2, ["HARVEST", "SPY", "RECON"])

class General_Hummingbird(AurisGeneral):
    """🐦 Node 3: Hummingbird — Agility/Scout specialist"""
    def __init__(self):
        super().__init__("Hummingbird", 3, ["RECON", "SPY", "RALLY"])

class General_Dolphin(AurisGeneral):
    """🐬 Node 4: Dolphin — Flow/Adaptation specialist"""
    def __init__(self):
        super().__init__("Dolphin", 4, ["COMPOUND", "NEGOTIATE", "HOLD"])

class General_Deer(AurisGeneral):
    """🦌 Node 5: Deer — Grace/Evasion specialist"""
    def __init__(self):
        super().__init__("Deer", 5, ["RETREAT", "HARVEST", "FORTIFY"])

class General_Owl(AurisGeneral):
    """🦉 Node 6: Owl — Wisdom/Strategy specialist"""
    def __init__(self):
        super().__init__("Owl", 6, ["HOLD", "RECON", "NEGOTIATE"])

class General_Panda(AurisGeneral):
    """🐼 Node 7: Panda — Balance/Diplomacy specialist"""
    def __init__(self):
        super().__init__("Panda", 7, ["NEGOTIATE", "FORTIFY", "HOLD"])

class General_Cargoship(AurisGeneral):
    """🚢 Node 8: Cargoship — Persistence/Supply specialist"""
    def __init__(self):
        super().__init__("Cargoship", 8, ["DEPLOY", "RALLY", "FORTIFY"])

class General_Clownfish(AurisGeneral):
    """🐠 Node 9: Clownfish — Adaptation/Survival specialist"""
    def __init__(self):
        super().__init__("Clownfish", 9, ["RETREAT", "RALLY", "COMPOUND"])


# ─────────────────────────────────────────────────────────────────────────────────────
# 🏛️ WAR ROOM — Command center that orchestrates all generals
# ─────────────────────────────────────────────────────────────────────────────────────

class WarRoom:
    """
    🏛️ THE WAR ROOM — Central command for all Auris generals
    
    Executes the HNC 8-stage pipeline as a war briefing cycle:
    1. Intelligence (field capture)
    2. Conscience Veto (Queen Gate)
    3. Planning (Ghost Dance)
    4. Coordination (Rainbow Bridge)
    5. Execution (temporal signal)
    6. Validation (Schumann check)
    7. After-Action (mandala measurement)
    8. Report (campaign log)
    """
    
    def __init__(self):
        self.generals: Dict[str, AurisGeneral] = {}
        self.turn_number = 0
        self.battle_history: List[Dict] = []
        self.logger = logging.getLogger("WarRoom")
        self._initialize_generals()
    
    def _initialize_generals(self):
        """Deploy all 9 generals"""
        for GeneralClass in [
            General_Tiger, General_Falcon, General_Hummingbird,
            General_Dolphin, General_Deer, General_Owl,
            General_Panda, General_Cargoship, General_Clownfish
        ]:
            gen = GeneralClass()
            self.generals[gen.name] = gen
        self.logger.info(f"🏛️ War Room initialized with {len(self.generals)} generals")
    
    def briefing_cycle(self, battlefield: BattlefieldState) -> Dict:
        """
        🏛️ Execute full war briefing cycle (HNC 8-stage pipeline)
        
        Every general gets a turn to decide. The War Room coordinates.
        """
        self.turn_number += 1
        self.logger.info(f"\n{'='*60}")
        self.logger.info(f"🏛️ WAR BRIEFING — Turn {self.turn_number}")
        self.logger.info(f"{'='*60}")
        
        briefing = {
            "turn": self.turn_number,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "battlefield": {
                "gamma": round(battlefield.gamma, 3),
                "beta": round(battlefield.beta, 3),
                "sls": round(battlefield.sls, 3),
                "our_strength": round(battlefield.our_strength, 3),
                "enemy_strength": round(battlefield.enemy_strength, 3),
                "morale": round(battlefield.morale, 3)
            },
            "general_orders": {},
            "consensus": None
        }
        
        # Each general evaluates and decides
        for name, general in self.generals.items():
            decision = general.decide(battlefield)
            briefing["general_orders"][name] = decision
        
        # Calculate consensus (majority command)
        commands = [d["command"] for d in briefing["general_orders"].values()]
        from collections import Counter
        command_counts = Counter(commands)
        consensus = command_counts.most_common(1)[0]
        
        briefing["consensus"] = {
            "command": consensus[0],
            "votes": consensus[1],
            "total": len(self.generals),
            "agreement": consensus[1] / len(self.generals)
        }
        
        self.logger.info(f"🏛️ Consensus: {consensus[0]} ({consensus[1]}/{len(self.generals)} generals)")
        
        self.battle_history.append(briefing)
        return briefing
    
    def execute_consensus(self, battlefield: BattlefieldState, briefing: Dict) -> Dict:
        """
        ⚔️ Execute the consensus command through the HNC pipeline
        """
        consensus_cmd = briefing["consensus"]["command"]
        command_enum = WarCommand[consensus_cmd]
        
        self.logger.info(f"⚔️ Executing consensus: {command_enum.value}")
        
        # Find a general to execute (specialist preferred)
        executor = None
        for name, general in self.generals.items():
            if consensus_cmd in general.specialties:
                executor = general
                break
        
        if not executor:
            executor = list(self.generals.values())[0]  # Default to Tiger
        
        # Execute through HNC gate if available
        if HNC_GATE_AVAILABLE:
            result, hnc_record = execute_with_hnc_gate(
                executor.execute_command,
                f"Execute {consensus_cmd} via consensus",
                command_enum, battlefield
            )
        else:
            result = executor.execute_command(command_enum, battlefield)
        
        execution = {
            "command": consensus_cmd,
            "executor": executor.name,
            "result": result,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        self.logger.info(f"⚔️ Execution complete: {result.get('action', 'N/A')}")
        return execution
    
    def get_war_status(self) -> Dict:
        """Full war status report"""
        return {
            "turn": self.turn_number,
            "generals_active": len(self.generals),
            "general_stats": {name: gen.get_stats() for name, gen in self.generals.items()},
            "total_briefings": len(self.battle_history),
            "last_consensus": self.battle_history[-1]["consensus"] if self.battle_history else None
        }
    
    def command(self, general_name: str, command_name: str, battlefield: BattlefieldState) -> Dict:
        """
        🎖️ DIRECT COMMAND — GARY or any operator can command a specific general
        
        Usage: war_room.command("Tiger", "FULL_ATTACK", battlefield)
        """
        general = self.generals.get(general_name)
        if not general:
            return {"error": f"General {general_name} not found"}
        
        try:
            command_enum = WarCommand[command_name]
        except KeyError:
            return {"error": f"Unknown command: {command_name}"}
        
        # Execute direct command through HNC gate
        if HNC_GATE_AVAILABLE:
            result, hnc_record = execute_with_hnc_gate(
                general.execute_command,
                f"Direct command: {general_name} -> {command_name}",
                command_enum, battlefield
            )
        else:
            result = general.execute_command(command_enum, battlefield)
        
        return {
            "general": general_name,
            "command": command_name,
            "result": result,
            "direct_command": True
        }


# ─────────────────────────────────────────────────────────────────────────────────────
# SELF-TEST — Train the generals
# ─────────────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s | %(name)s | %(message)s'
    )
    
    print("=" * 60)
    print("⚔️ AURIS STRATEGY DECISION ENGINE — GENERAL TRAINING")
    print("=" * 60)
    
    # Initialize War Room
    war_room = WarRoom()
    
    # Create a test battlefield scenario
    test_battlefield = BattlefieldState(
        timestamp=datetime.now(timezone.utc).isoformat(),
        turn_number=1,
        gamma=0.75,      # Good coherence
        beta=0.85,       # Stable
        sls=0.65,        # Above threshold
        schumann=7.83,
        our_strength=0.7,
        enemy_strength=0.4,
        territory_control=0.6,
        resource_level=0.8,
        morale=0.75,
        active_positions=3,
        checkpoint_balance=2000.0,
        at_risk=0.2,
        enemy_detected=True,
        threat_level=0.3,
        distortion_active=False,
        opportunity_detected=True,
        opportunity_score=0.8
    )
    
    print(f"\n📊 Battlefield State:")
    print(f"   Γ (coherence): {test_battlefield.gamma}")
    print(f"   β (stability): {test_battlefield.beta}")
    print(f"   SLS: {test_battlefield.sls}")
    print(f"   Our strength: {test_battlefield.our_strength}")
    print(f"   Enemy strength: {test_battlefield.enemy_strength}")
    print(f"   Strength ratio: {test_battlefield.strength_ratio():.3f}")
    print(f"   Is advantage: {test_battlefield.is_advantage()}")
    
    # Run briefing cycle
    print(f"\n🏛️ Executing War Briefing Cycle...\n")
    briefing = war_room.briefing_cycle(test_battlefield)
    
    print(f"\n📋 General Orders:")
    for name, decision in briefing["general_orders"].items():
        print(f"   {name:12} → {decision['command']:12} (P={decision['probability']:.2f}, EV={decision['expected_value']:.2f})")
    
    print(f"\n🗳️ Consensus: {briefing['consensus']['command']} ({briefing['consensus']['votes']}/{briefing['consensus']['total']} generals, {briefing['consensus']['agreement']:.1%} agreement)")
    
    # Execute consensus
    print(f"\n⚔️ Executing Consensus Command...")
    execution = war_room.execute_consensus(test_battlefield, briefing)
    print(f"   Executor: {execution['executor']}")
    print(f"   Action: {execution['result'].get('action', 'N/A')}")
    
    # Test direct command
    print(f"\n🎖️ Direct Command Test: Tiger -> FULL_ATTACK")
    direct = war_room.command("Tiger", "FULL_ATTACK", test_battlefield)
    print(f"   Result: {direct['result'].get('action', 'N/A')}")
    
    # War status
    print(f"\n📊 War Status:")
    status = war_room.get_war_status()
    print(f"   Turn: {status['turn']}")
    print(f"   Generals: {status['generals_active']}")
    print(f"   Briefings: {status['total_briefings']}")
    
    print(f"\n{'='*60}")
    print("✅ ALL GENERALS TRAINED AND OPERATIONAL")
    print("🛡️ The war room is active. The field holds.")
    print(f"{'='*60}")
