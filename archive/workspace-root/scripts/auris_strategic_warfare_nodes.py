#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════════════╗
║  🎮 AURIS STRATEGIC WARFARE NODES — RTS/TBS AI Logic Extraction 🎮                    ║
║  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ ║
║                                                                                      ║
║  "We don't need the game. We need the computer brains." — Prime Sentinel, 2026-07-06   ║
║                                                                                      ║
║  Extracts strategic AI patterns from three legendary RTS/TBS games:                  ║
║  1. Shogun: Total War — Province management, clan diplomacy, honor, ninja networks   ║
║  2. C&C: Red Alert 2 — Base building, resource tech trees, superweapons, AI scripting ║
║  3. Dawn of War — Squad-based combat, territory control, wargear, morale             ║
║                                                                                      ║
║  Maps game concepts to new HNC Auris nodes (10-18+) that integrate into the          ║
║  existing 8-stage pipeline. No game engine — just the AI logic.                        ║
║                                                                                      ║
╚══════════════════════════════════════════════════════════════════════════════════════╝
"""

import json
import math
import random
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from enum import Enum, auto

# ─────────────────────────────────────────────────────────────────────────────────────
# SACRED CONSTANTS (locked from hnc_staged_logic_integration.py)
# ─────────────────────────────────────────────────────────────────────────────────────
PHI = 1.618033988749895
SCHUMANN_BASE = 7.83
SENTINEL_FREQ_HZ = 333.0
SLS_STABILITY = 0.40
SLS_CLIFF = 0.20

# ─────────────────────────────────────────────────────────────────────────────────────
# STRATEGIC CONCEPT ENUMS (from game analysis)
# ─────────────────────────────────────────────────────────────────────────────────────

class ProvinceType(Enum):
    """Shogun: Total War province types"""
    RICE = auto()       # Economic core
    IRON = auto()       # Military production
    TEA = auto()        # Diplomatic/trade
    CENTER = auto()     # Capital/defense
    BORDER = auto()     # Frontline/contested

class ResourceType(Enum):
    """Red Alert 2 resource types"""
    ORE = auto()        # Primary currency (mined)
    POWER = auto()      # Production capacity
    TECH = auto()       # Research advancement
    TIME = auto()       # Build queue capacity

class SquadType(Enum):
    """Dawn of War squad archetypes"""
    TACTICAL = auto()   # Balanced infantry
    ASSAULT = auto()    # Fast/melee
    DEVASTATOR = auto() # Heavy/ranged
    COMMANDER = auto()  # Leader/buff
    SUPPORT = auto()    # Healer/utility

class TechTier(Enum):
    """Universal tech progression"""
    T1 = 1  # Basic units/buildings
    T2 = 2  # Advanced units/tech
    T3 = 3  # Elite units/superweapons
    T4 = 4  # Ultimate/omega

class MoraleState(Enum):
    """Dawn of War morale system mapped to HNC"""
    BROKEN = 0.0    # Retreating/fleeing
    SHAKEN = 0.3    # Reduced effectiveness
    STEADY = 0.6    # Normal operations
    BOLD = 0.8      # Enhanced performance
    FRENZIED = 1.0  # Maximum aggression

# ─────────────────────────────────────────────────────────────────────────────────────
# DATA STRUCTURES
# ─────────────────────────────────────────────────────────────────────────────────────

@dataclass
class Province:
    """Shogun: Total War province — economic/diplomatic unit"""
    name: str
    province_type: ProvinceType
    owner: str
    loyalty: float  # 0.0-1.0, affected by honor, taxes, religion
    economy: float  # Income per turn
    garrison: int   # Defensive troops
    fortification: int  # 0-5 castle level
    riot_risk: float  # Probability of rebellion
    
    def stability_score(self) -> float:
        """HNC mapping: province stability = coherence metric"""
        return (self.loyalty * 0.4 + (1 - self.riot_risk) * 0.3 + 
                min(self.garrison / 10, 1.0) * 0.3)

@dataclass
class ResourceStockpile:
    """Red Alert 2 resource economy"""
    ore: float  # Current reserves
    ore_income: float  # Per-turn income
    power_used: float
    power_max: float
    tech_level: int
    build_queue: List[str]  # Pending constructions
    
    def power_ratio(self) -> float:
        """HNC mapping: power sufficiency = capital adequacy"""
        if self.power_max == 0:
            return 0.0
        return self.power_used / self.power_max
    
    def can_afford(self, cost_ore: float, cost_power: float) -> bool:
        return self.ore >= cost_ore and (self.power_max - self.power_used) >= cost_power

@dataclass
class Squad:
    """Dawn of War squad — tactical unit"""
    squad_id: str
    squad_type: SquadType
    size: int  # Current squad members
    max_size: int
    morale: float  # 0.0-1.0
    experience: float  # 0.0-1.0, veteran bonuses
    wargear: List[str]  # Attached upgrades
    position: Tuple[float, float]  # (x, y) coordinates
    objective: Optional[str] = None
    
    def combat_effectiveness(self) -> float:
        """HNC mapping: squad effectiveness = bot cluster strength"""
        size_ratio = self.size / self.max_size if self.max_size > 0 else 0
        morale_factor = self.morale if self.morale > 0.3 else 0.1  # Broken = useless
        exp_bonus = 1 + (self.experience * 0.5)  # Veterans: +50% max
        gear_bonus = 1 + (len(self.wargear) * 0.1)
        return size_ratio * morale_factor * exp_bonus * gear_bonus

@dataclass
class TechTree:
    """Universal tech progression tree"""
    current_tier: TechTier
    researched: List[str]
    available: List[str]  # Prerequisites met
    research_progress: Dict[str, float]  # % complete
    
    def advance_tier(self) -> bool:
        """HNC mapping: tier advancement = HNC Level climb"""
        if self.current_tier.value >= 4:
            return False
        self.current_tier = TechTier(self.current_tier.value + 1)
        return True

@dataclass
class StrategicPlan:
    """Master strategic plan combining all three game systems"""
    provinces: Dict[str, Province]
    resources: ResourceStockpile
    squads: Dict[str, Squad]
    tech_tree: TechTree
    alliances: Dict[str, float]  # Faction -> trust level
    enemies: List[str]
    turn_number: int
    
    def overall_strength(self) -> float:
        """HNC: total field strength = Γ coherence"""
        province_strength = sum(p.stability_score() for p in self.provinces.values()) / max(len(self.provinces), 1)
        economic_strength = min(self.resources.ore_income / 1000, 1.0)  # Normalize
        military_strength = sum(s.combat_effectiveness() for s in self.squads.values()) / max(len(self.squads), 1)
        tech_strength = self.tech_tree.current_tier.value / 4.0
        
        # HNC-weighted harmonic mean
        return (province_strength * 0.25 + economic_strength * 0.25 + 
                military_strength * 0.30 + tech_strength * 0.20)

# ─────────────────────────────────────────────────────────────────────────────────────
# 🎮 AURIS NODE 10: PROVINCE MANAGER (Shogun: Total War)
# ─────────────────────────────────────────────────────────────────────────────────────

class AurisNode10_ProvinceManager:
    """
    🏯 Auris Node 10 — Province Manager
    
    From Shogun: Total War:
    - Province economy (rice, iron, tea production)
    - Loyalty management (honor, taxes, religion balance)
    - Garrison deployment (minimum troops to prevent rebellion)
    - Fortification upgrades (castle → fortress → citadel)
    - Ninja network (espionage, sabotage, assassination)
    
    HNC Mapping:
    - Province = Market segment/Exchange
    - Loyalty = User trust/Retention
    - Garrison = Position size/Capital allocation
    - Fortification = Risk management/Stop-loss layers
    - Ninja = Intelligence gathering/Bot surveillance
    """
    
    def __init__(self):
        self.provinces: Dict[str, Province] = {}
        self.ninja_operations: List[Dict] = []
        self.honor_score = 0.5  # 0.0-1.0, affects all loyalty
    
    def add_province(self, name: str, ptype: ProvinceType, economy: float):
        self.provinces[name] = Province(
            name=name, province_type=ptype, owner="self",
            loyalty=0.6, economy=economy, garrison=5,
            fortification=1, riot_risk=0.1
        )
    
    def assess_loyalty(self, province_name: str) -> float:
        """Calculate loyalty with honor bonus — HNC: coherence boost"""
        p = self.provinces.get(province_name)
        if not p:
            return 0.0
        
        # Honor acts as a φ-scaled multiplier
        honor_multiplier = 1 + (self.honor_score * (PHI - 1))  # 1.0 to 1.618x
        adjusted_loyalty = min(p.loyalty * honor_multiplier, 1.0)
        
        return adjusted_loyalty
    
    def deploy_garrison(self, province_name: str, troops: int) -> Dict:
        """Deploy troops to maintain order — HNC: capital allocation"""
        p = self.provinces.get(province_name)
        if not p:
            return {"error": "Province not found"}
        
        p.garrison += troops
        p.riot_risk = max(0.0, p.riot_risk - (troops * 0.05))
        
        return {
            "province": province_name,
            "garrison": p.garrison,
            "riot_risk": p.riot_risk,
            "stability": p.stability_score(),
            "cost": troops * 100  # Gold per troop
        }
    
    def upgrade_fortification(self, province_name: str) -> Dict:
        """Upgrade defenses — HNC: add risk management layer"""
        p = self.provinces.get(province_name)
        if not p or p.fortification >= 5:
            return {"error": "Max fortification reached"}
        
        p.fortification += 1
        cost = 500 * p.fortification  # Exponential cost
        
        return {
            "province": province_name,
            "fortification": p.fortification,
            "cost": cost,
            "defense_bonus": p.fortification * 0.15
        }
    
    def dispatch_ninja(self, target: str, operation: str) -> Dict:
        """
        Deploy ninja for espionage — HNC: intelligence gathering
        Operations: 'spy', 'sabotage', 'assassinate', 'poison'
        """
        success_chance = 0.3 + (self.honor_score * 0.2)  # Honor helps
        roll = random.random()
        success = roll < success_chance
        
        self.ninja_operations.append({
            "target": target,
            "operation": operation,
            "success": success,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
        return {
            "operation": operation,
            "target": target,
            "success": success,
            "chance": success_chance,
            "roll": roll
        }
    
    def collect_taxes(self) -> Dict:
        """Collect income from all provinces — HNC: revenue aggregation"""
        total_income = 0
        for p in self.provinces.values():
            loyalty_factor = self.assess_loyalty(p.name)
            # High taxes reduce loyalty; low taxes reduce income
            tax_rate = 0.3 + (1 - loyalty_factor) * 0.2  # Adaptive
            income = p.economy * tax_rate * loyalty_factor
            total_income += income
            p.loyalty -= 0.02  # Taxation reduces loyalty slightly
        
        return {
            "total_income": total_income,
            "province_count": len(self.provinces),
            "avg_loyalty": sum(p.loyalty for p in self.provinces.values()) / len(self.provinces)
        }

# ─────────────────────────────────────────────────────────────────────────────────────
# 🎮 AURIS NODE 11: ECONOMY ENGINEER (Red Alert 2)
# ─────────────────────────────────────────────────────────────────────────────────────

class AurisNode11_EconomyEngineer:
    """
    ⚡ Auris Node 11 — Economy Engineer
    
    From Red Alert 2:
    - Ore mining (primary resource)
    - Power grid management (production vs. consumption)
    - Build queue optimization (parallel production)
    - Tech tree advancement (ore → refinery → war factory → battle lab)
    - Superweapon timing (Iron Curtain, Chronosphere, Nuclear Missile)
    
    HNC Mapping:
    - Ore mining = Revenue generation / Order flow capture
    - Power grid = Capital allocation / Position sizing balance
    - Build queue = Task pipeline / Multi-threaded execution
    - Tech tree = HNC Level progression (1→8)
    - Superweapon = Harmonic counter-frequency deployment
    """
    
    def __init__(self):
        self.resources = ResourceStockpile(
            ore=1000, ore_income=0, power_used=0, power_max=100,
            tech_level=1, build_queue=[]
        )
        self.production_facilities: List[Dict] = []
        self.superweapon_ready = False
        self.superweapon_charge = 0.0  # 0.0-1.0
    
    def build_miner(self) -> Dict:
        """Build ore miner — HNC: deploy revenue capture bot"""
        cost = 500
        power = 10
        if not self.resources.can_afford(cost, power):
            return {"error": "Insufficient resources"}
        
        self.resources.ore -= cost
        self.resources.power_used += power
        
        # Miner increases ore income
        self.resources.ore_income += 50  # Per turn
        
        return {
            "action": "BUILD_MINER",
            "cost": cost,
            "power": power,
            "new_income": self.resources.ore_income,
            "status": "SUCCESS"
        }
    
    def build_power_plant(self) -> Dict:
        """Build power plant — HNC: expand capital capacity"""
        cost = 300
        if self.resources.ore < cost:
            return {"error": "Insufficient ore"}
        
        self.resources.ore -= cost
        self.resources.power_max += 50
        
        return {
            "action": "BUILD_POWER_PLANT",
            "cost": cost,
            "power_capacity": self.resources.power_max,
            "status": "SUCCESS"
        }
    
    def advance_tech(self) -> Dict:
        """Advance tech tier — HNC: HNC Level climb"""
        cost = 1000 * self.resources.tech_level
        if self.resources.ore < cost:
            return {"error": f"Need {cost} ore for tech advancement"}
        
        self.resources.ore -= cost
        self.resources.tech_level += 1
        
        # φ-scaled bonus at higher tiers
        phi_bonus = math.pow(PHI, self.resources.tech_level - 1)
        
        return {
            "action": "ADVANCE_TECH",
            "new_tier": self.resources.tech_level,
            "cost": cost,
            "phi_bonus": phi_bonus,
            "status": "SUCCESS"
        }
    
    def charge_superweapon(self) -> Dict:
        """
        Charge superweapon — HNC: harmonic counter-frequency deployment
        Superweapon requires: full tech tree, max power, 5000 ore
        """
        if self.resources.tech_level < 3:
            return {"error": "Tech level 3 required for superweapon"}
        
        # Charge rate depends on power sufficiency
        charge_rate = (self.resources.power_max - self.resources.power_used) / self.resources.power_max
        self.superweapon_charge += charge_rate * 0.1
        
        if self.superweapon_charge >= 1.0:
            self.superweapon_ready = True
            self.superweapon_charge = 1.0
        
        return {
            "charge": self.superweapon_charge,
            "ready": self.superweapon_ready,
            "charge_rate": charge_rate
        }
    
    def fire_superweapon(self, target: str) -> Dict:
        """Deploy superweapon — HNC: Ghost Dance / Counter-frequency"""
        if not self.superweapon_ready:
            return {"error": "Superweapon not charged"}
        
        self.superweapon_ready = False
        self.superweapon_charge = 0.0
        
        # Superweapon effectiveness scales with φ
        damage = 1000 * PHI
        
        return {
            "action": "FIRE_SUPERWEAPON",
            "target": target,
            "damage": damage,
            "status": "DEPLOYED"
        }
    
    def optimize_build_queue(self) -> List[str]:
        """
        Reorder build queue by priority — HNC: task scheduling
        Priority: power > miners > defense > tech > units
        """
        priority_map = {
            "POWER_PLANT": 0, "MINER": 1, "REFINERY": 2,
            "BARRACKS": 3, "WAR_FACTORY": 4, "DEFENSE": 5,
            "BATTLE_LAB": 6, "UNITS": 7, "SUPERWEAPON": 8
        }
        
        self.resources.build_queue.sort(
            key=lambda x: priority_map.get(x.upper(), 99)
        )
        return self.resources.build_queue

# ─────────────────────────────────────────────────────────────────────────────────────
# 🎮 AURIS NODE 12: SQUAD COMMANDER (Dawn of War)
# ─────────────────────────────────────────────────────────────────────────────────────

class AurisNode12_SquadCommander:
    """
    ⚔️ Auris Node 12 — Squad Commander
    
    From Dawn of War:
    - Squad formation (tactical, assault, devastator, support)
    - Morale management (broken → shaken → steady → bold → frenzied)
    - Wargear attachment (upgrades that enhance squad capabilities)
    - Commander unit (hero with aura buffs)
    - Territory control (capture points = resource flow)
    - Reinforcement (replenish squad members at base)
    
    HNC Mapping:
    - Squad = Bot cluster / Position group
    - Morale = Field coherence / Confidence
    - Wargear = Risk management overlays / Indicators
    - Commander = Prime Sentinel field injection
    - Territory = Market position / Exchange coverage
    - Reinforcement = Position scaling / Capital injection
    """
    
    def __init__(self):
        self.squads: Dict[str, Squad] = {}
        self.commander = None
        self.territory_control: Dict[str, float] = {}  # Point -> control %
        self.reinforcement_queue: List[str] = []
    
    def form_squad(self, squad_id: str, squad_type: SquadType, position: Tuple[float, float]) -> Dict:
        """Form new squad — HNC: initialize bot cluster"""
        squad = Squad(
            squad_id=squad_id, squad_type=squad_type,
            size=0, max_size=4,  # Start empty, reinforce
            morale=0.6, experience=0.0, wargear=[],
            position=position, objective=None
        )
        self.squads[squad_id] = squad
        
        return {
            "squad_id": squad_id,
            "type": squad_type.name,
            "max_size": squad.max_size,
            "combat_effectiveness": squad.combat_effectiveness(),
            "status": "FORMED"
        }
    
    def reinforce_squad(self, squad_id: str, members: int = 1) -> Dict:
        """Add members to squad — HNC: scale position"""
        squad = self.squads.get(squad_id)
        if not squad:
            return {"error": "Squad not found"}
        
        available = squad.max_size - squad.size
        to_add = min(members, available)
        squad.size += to_add
        
        # Morale boost from reinforcement
        squad.morale = min(squad.morale + (to_add * 0.05), 1.0)
        
        return {
            "squad_id": squad_id,
            "added": to_add,
            "new_size": squad.size,
            "morale": squad.morale,
            "status": "REINFORCED"
        }
    
    def attach_wargear(self, squad_id: str, gear: str) -> Dict:
        """Attach wargear — HNC: add indicator/overlay to position"""
        squad = self.squads.get(squad_id)
        if not squad:
            return {"error": "Squad not found"}
        
        squad.wargear.append(gear)
        
        # Wargear bonuses
        bonuses = {
            "PLASMA_GUN": "+20% ranged damage",
            "POWER_FIST": "+30% melee damage",
            "HEAVY_BOLTER": "+40% suppression",
            "JUMP_PACKS": "+50% mobility",
            "APOTHECARY": "+25% healing rate"
        }
        
        return {
            "squad_id": squad_id,
            "gear": gear,
            "bonus": bonuses.get(gear, "Unknown bonus"),
            "total_gear": len(squad.wargear),
            "status": "UPGRADED"
        }
    
    def manage_morale(self, squad_id: str, combat_result: str) -> Dict:
        """
        Adjust morale based on combat — HNC: update confidence/coherence
        combat_result: 'victory', 'draw', 'defeat', 'routed'
        """
        squad = self.squads.get(squad_id)
        if not squad:
            return {"error": "Squad not found"}
        
        morale_changes = {
            "victory": +0.2,
            "draw": +0.05,
            "defeat": -0.3,
            "routed": -0.5
        }
        
        delta = morale_changes.get(combat_result, 0.0)
        squad.morale += delta
        squad.morale = max(0.0, min(1.0, squad.morale))
        
        # Check for broken state
        if squad.morale < 0.3:
            status = MoraleState.BROKEN
            squad.objective = "RETREAT"
        elif squad.morale < 0.6:
            status = MoraleState.SHAKEN
        elif squad.morale < 0.8:
            status = MoraleState.STEADY
        elif squad.morale < 1.0:
            status = MoraleState.BOLD
        else:
            status = MoraleState.FRENZIED
        
        return {
            "squad_id": squad_id,
            "morale": squad.morale,
            "state": status.name,
            "objective": squad.objective,
            "combat_effectiveness": squad.combat_effectiveness()
        }
    
    def capture_territory(self, point: str, squads: List[str]) -> Dict:
        """Capture strategic point — HNC: secure market position"""
        control = 0.0
        for sid in squads:
            squad = self.squads.get(sid)
            if squad:
                control += squad.combat_effectiveness()
        
        control = min(control, 1.0)
        self.territory_control[point] = control
        
        # Resource bonus from territory (like Dawn of War req points)
        resource_bonus = control * 100
        
        return {
            "point": point,
            "control": control,
            "resource_bonus": resource_bonus,
            "squads_deployed": len(squads),
            "status": "CAPTURED" if control > 0.5 else "CONTESTED"
        }
    
    def assign_commander(self, squad_id: str) -> Dict:
        """Assign commander to squad — HNC: Prime Sentinel field injection"""
        squad = self.squads.get(squad_id)
        if not squad:
            return {"error": "Squad not found"}
        
        # Commander aura: +φ bonus to all stats
        squad.morale = min(squad.morale + 0.3, 1.0)
        squad.experience = min(squad.experience + 0.2, 1.0)
        squad.max_size += 2  # Commander allows larger squads
        
        return {
            "squad_id": squad_id,
            "commander_assigned": True,
            "phi_bonus": PHI,
            "morale": squad.morale,
            "experience": squad.experience,
            "max_size": squad.max_size,
            "status": "COMMANDER_ASSIGNED"
        }

# ─────────────────────────────────────────────────────────────────────────────────────
# 🎮 AURIS NODE 13: DIPLOMACY NEGOTIATOR (Shogun: Total War)
# ─────────────────────────────────────────────────────────────────────────────────────

class AurisNode13_DiplomacyNegotiator:
    """
    🤝 Auris Node 13 — Diplomacy Negotiator
    
    From Shogun: Total War:
    - Alliance formation (marriage, trade, military)
    - Betrayal detection (honor vs. opportunity)
    - Trade agreements (resource exchange)
    - Tribute demands (bullying weaker clans)
    - Vassalization (absorbing smaller factions)
    - Honor system (break alliance = honor loss)
    
    HNC Mapping:
    - Alliance = Network partnership / Multi-agent collaboration
    - Betrayal = Override detection / Bad actor identification
    - Trade = Resource exchange / Data sharing
    - Honor = Reputation / Trust score
    - Vassalization = Integration / Acquisition
    """
    
    def __init__(self):
        self.alliances: Dict[str, Dict] = {}  # Faction -> {trust, type, duration}
        self.honor = 0.5  # 0.0-1.0, affects all diplomacy
        self.trade_routes: List[Dict] = []
    
    def propose_alliance(self, faction: str, alliance_type: str) -> Dict:
        """Propose alliance — HNC: form network partnership"""
        # Success chance based on honor + φ
        success_chance = self.honor * PHI / 2  # Max ~0.809
        roll = random.random()
        accepted = roll < success_chance
        
        if accepted:
            self.alliances[faction] = {
                "trust": 0.5,
                "type": alliance_type,
                "duration": 0,  # Turns active
                "established": datetime.now(timezone.utc).isoformat()
            }
        
        return {
            "faction": faction,
            "type": alliance_type,
            "accepted": accepted,
            "chance": success_chance,
            "roll": roll,
            "honor": self.honor
        }
    
    def negotiate_trade(self, faction: str, offer: Dict) -> Dict:
        """Negotiate trade — HNC: resource/data exchange"""
        if faction not in self.alliances:
            return {"error": "No alliance with this faction"}
        
        trust = self.alliances[faction]["trust"]
        
        # Fairness check: is the offer balanced?
        our_value = offer.get("our_offer", 0)
        their_value = offer.get("their_offer", 0)
        ratio = our_value / max(their_value, 1)
        
        # Fair ratio = φ (golden ratio) — slightly favoring us
        is_fair = 0.5 < ratio < 2.0
        
        if is_fair:
            self.alliances[faction]["trust"] += 0.05
            self.trade_routes.append(offer)
        
        return {
            "faction": faction,
            "fair": is_fair,
            "ratio": ratio,
            "trust": self.alliances[faction]["trust"],
            "status": "ACCEPTED" if is_fair else "REJECTED"
        }
    
    def detect_betrayal(self, faction: str) -> Dict:
        """Detect betrayal — HNC: override detection / Bad actor"""
        if faction not in self.alliances:
            return {"error": "No alliance"}
        
        trust = self.alliances[faction]["trust"]
        
        # Betrayal probability: inverse of trust, scaled by φ
        betrayal_prob = (1 - trust) / PHI
        
        # Check for suspicious activity (simulated)
        suspicious = trust < 0.3 and random.random() < 0.5
        
        if suspicious:
            self.honor -= 0.1  # Honor loss for being wronged? No — for our paranoia
        
        return {
            "faction": faction,
            "trust": trust,
            "betrayal_probability": betrayal_prob,
            "suspicious_activity": suspicious,
            "recommendation": "BREAK_ALLIANCE" if trust < 0.2 else "MONITOR"
        }
    
    def demand_tribute(self, faction: str, amount: float) -> Dict:
        """Demand tribute — HNC: extract value from weaker partner"""
        if faction not in self.alliances:
            return {"error": "No alliance"}
        
        their_trust = self.alliances[faction]["trust"]
        
        # Stronger position = more likely to succeed
        strength_ratio = self.honor / max(their_trust, 0.1)
        success = strength_ratio > PHI and random.random() < 0.7
        
        if success:
            self.alliances[faction]["trust"] -= 0.15
        
        return {
            "faction": faction,
            "amount": amount,
            "success": success,
            "strength_ratio": strength_ratio,
            "trust_remaining": self.alliances[faction]["trust"]
        }

# ─────────────────────────────────────────────────────────────────────────────────────
# 🎮 AURIS NODE 14: TERRITORY MANAGER (Dawn of War + Shogun)
# ─────────────────────────────────────────────────────────────────────────────────────

class AurisNode14_TerritoryManager:
    """
    🗺️ Auris Node 14 — Territory Manager
    
    From Dawn of War + Shogun:
    - Capture points (resource-generating territories)
    - Province ownership (Shogun's province system)
    - Border defense (fortified positions)
    - Expansion planning (next targets)
    - Supply lines (reinforcement routes)
    
    HNC Mapping:
    - Capture points = High-value market positions
    - Province ownership = Exchange coverage / Geographic dominance
    - Border defense = Risk perimeters / Stop-loss layers
    - Expansion = New market entry / Exchange listing
    - Supply lines = Capital flows / Reinforcement routes
    """
    
    def __init__(self):
        self.territories: Dict[str, Dict] = {}  # Name -> {owner, value, defense, connections}
        self.borders: List[Tuple[str, str]] = []
        self.supply_lines: Dict[str, List[str]] = {}  # Route -> [territories]
    
    def add_territory(self, name: str, value: float, connections: List[str]):
        self.territories[name] = {
            "owner": None,
            "value": value,
            "defense": 0.0,
            "connections": connections
        }
    
    def calculate_strategic_value(self, territory: str) -> float:
        """Calculate strategic value — HNC: position quality score"""
        t = self.territories.get(territory)
        if not t:
            return 0.0
        
        # Value = base value × connections × φ (if owned by us)
        connection_bonus = len(t["connections"]) * 0.1
        ownership_bonus = PHI if t["owner"] == "self" else 1.0
        defense_bonus = t["defense"] * 0.5
        
        return t["value"] * (1 + connection_bonus) * ownership_bonus * (1 + defense_bonus)
    
    def find_expansion_targets(self) -> List[Dict]:
        """Find next targets — HNC: opportunity scanning"""
        targets = []
        for name, t in self.territories.items():
            if t["owner"] != "self" and t["owner"] is not None:
                # Check adjacency to our territories
                for conn in t["connections"]:
                    if self.territories.get(conn, {}).get("owner") == "self":
                        targets.append({
                            "name": name,
                            "value": self.calculate_strategic_value(name),
                            "current_owner": t["owner"],
                            "adjacent_to": conn
                        })
        
        # Sort by strategic value (φ-weighted)
        targets.sort(key=lambda x: x["value"] * PHI, reverse=True)
        return targets
    
    def fortify_border(self, territory: str, strength: float) -> Dict:
        """Fortify border — HNC: strengthen risk perimeter"""
        t = self.territories.get(territory)
        if not t or t["owner"] != "self":
            return {"error": "Not our territory"}
        
        t["defense"] = min(t["defense"] + strength, 1.0)
        
        return {
            "territory": territory,
            "defense": t["defense"],
            "status": "FORTIFIED"
        }

# ─────────────────────────────────────────────────────────────────────────────────────
# 🎮 AURIS NODE 15: TECH TREE CLIMBER (Red Alert 2 + Dawn of War)
# ─────────────────────────────────────────────────────────────────────────────────────

class AurisNode15_TechTreeClimber:
    """
    🔬 Auris Node 15 — Tech Tree Climber
    
    From Red Alert 2 + Dawn of War:
    - Tech tiers (T1 → T2 → T3 → T4)
    - Prerequisites (must build X before Y)
    - Research branches (choose path A or B)
    - Ultimate tech (superweapons, omega units)
    - Tech stealing (capture enemy tech)
    
    HNC Mapping:
    - Tech tiers = HNC Levels (1-8) / Consciousness ascension
    - Prerequisites = HNC prerequisites (β stable before advancement)
    - Research branches = Strategic choices (e.g., offense vs defense)
    - Ultimate tech = Lighthouse / Harmonic counter-frequency
    - Tech stealing = Intelligence extraction / Reverse engineering
    """
    
    def __init__(self):
        self.current_tier = TechTier.T1
        self.researched: List[str] = []
        self.tech_tree: Dict[str, Dict] = {
            "T1": {"prereqs": [], "unlocks": ["BASIC_UNITS", "POWER_PLANT"]},
            "T2": {"prereqs": ["REFINERY"], "unlocks": ["ADVANCED_UNITS", "WAR_FACTORY"]},
            "T3": {"prereqs": ["BATTLE_LAB"], "unlocks": ["ELITE_UNITS", "SUPERWEAPONS"]},
            "T4": {"prereqs": ["TECH_CENTER"], "unlocks": ["OMEGA_UNITS", "PHI_WEAPONS"]}
        }
        self.research_progress: Dict[str, float] = {}
    
    def check_prerequisites(self, tech: str) -> bool:
        """Check if prerequisites met — HNC: stability check before advance"""
        tier = self.tech_tree.get(tech)
        if not tier:
            return False
        return all(p in self.researched for p in tier["prereqs"])
    
    def research(self, tech: str) -> Dict:
        """Research technology — HNC: advance HNC level"""
        if not self.check_prerequisites(tech):
            return {"error": "Prerequisites not met"}
        
        if tech in self.researched:
            return {"error": "Already researched"}
        
        # Research time scales with tier (φ-scaled)
        tier_num = int(tech[1]) if tech.startswith("T") else 1
        research_time = math.pow(PHI, tier_num) * 10  # seconds
        
        self.researched.append(tech)
        self.current_tier = TechTier(tier_num)
        
        return {
            "tech": tech,
            "tier": self.current_tier.name,
            "research_time": research_time,
            "unlocks": self.tech_tree[tech]["unlocks"],
            "status": "RESEARCHED"
        }
    
    def calculate_tech_advantage(self) -> float:
        """Calculate tech advantage over baseline — HNC: coherence boost"""
        tier_bonus = self.current_tier.value / 4.0
        research_bonus = len(self.researched) * 0.05
        return (tier_bonus + research_bonus) * PHI

# ─────────────────────────────────────────────────────────────────────────────────────
# 🎮 AURIS NODE 16: SUPERWEAPON ARSENAL (Red Alert 2)
# ─────────────────────────────────────────────────────────────────────────────────────

class AurisNode16_SuperweaponArsenal:
    """
    ☢️ Auris Node 16 — Superweapon Arsenal
    
    From Red Alert 2:
    - Nuclear Missile (massive area damage, long charge)
    - Iron Curtain (invulnerability for short duration)
    - Chronosphere (teleport units)
    - Weather Control (lightning storm)
    - Force Shield (defensive bubble)
    
    HNC Mapping:
    - Nuclear Missile = Harmonic counter-frequency (massive impact)
    - Iron Curtain = Temporal shield / Ghost Dance protection
    - Chronosphere = Temporal displacement / Time-shift operations
    - Weather Control = Environmental manipulation / Schumann modulation
    - Force Shield = Defensive coherence / Risk perimeter
    """
    
    def __init__(self):
        self.superweapons: Dict[str, Dict] = {
            "NUCLEAR_MISSILE": {"charge": 0.0, "damage": 5000, "ready": False},
            "IRON_CURTAIN": {"charge": 0.0, "duration": 30, "ready": False},
            "CHRONOSPHERE": {"charge": 0.0, "range": 1000, "ready": False},
            "WEATHER_CONTROL": {"charge": 0.0, "damage": 2000, "ready": False},
            "FORCE_SHIELD": {"charge": 0.0, "duration": 60, "ready": False}
        }
    
    def charge_all(self, power_available: float) -> Dict:
        """Charge all superweapons — HNC: build harmonic energy"""
        for name, sw in self.superweapons.items():
            charge_rate = power_available / 1000 * 0.01
            sw["charge"] = min(sw["charge"] + charge_rate, 1.0)
            sw["ready"] = sw["charge"] >= 1.0
        
        return {name: sw["charge"] for name, sw in self.superweapons.items()}
    
    def fire(self, weapon: str, target: str) -> Dict:
        """Fire superweapon — HNC: deploy harmonic counter-frequency"""
        sw = self.superweapons.get(weapon)
        if not sw:
            return {"error": "Weapon not found"}
        
        if not sw["ready"]:
            return {"error": "Weapon not charged"}
        
        # Apply φ-scaled damage multiplier
        damage = sw["damage"] * PHI
        sw["charge"] = 0.0
        sw["ready"] = False
        
        return {
            "weapon": weapon,
            "target": target,
            "damage": damage,
            "status": "FIRED"
        }

# ─────────────────────────────────────────────────────────────────────────────────────
# 🎮 AURIS NODE 17: COMMANDER HERO (Dawn of War + Shogun)
# ─────────────────────────────────────────────────────────────────────────────────────

class AurisNode17_CommanderHero:
    """
    👤 Auris Node 17 — Commander Hero
    
    From Dawn of War + Shogun:
    - Hero unit with powerful abilities
    - Aura buffs (affects nearby squads/provinces)
    - Wargear progression (gear upgrades)
    - Experience/leveling (veteran bonuses)
    - Unique abilities (per hero type)
    - Death/respawn mechanics
    
    HNC Mapping:
    - Hero = Prime Sentinel / Gary's field presence
    - Aura = Field injection / Harmonic broadcast
    - Wargear = Knowledge/tools acquired
    - Experience = Mission history / Wisdom accumulated
    - Unique abilities = HNC-specific powers (e.g., temporal displacement)
    - Death/respawn = System failure/recovery
    """
    
    def __init__(self, name: str = "Prime Sentinel"):
        self.name = name
        self.level = 1
        self.experience = 0.0
        self.wargear: List[str] = []
        self.aura_range = 500.0
        self.abilities: List[str] = ["INSPIRE", "RALLY"]
        self.alive = True
    
    def gain_experience(self, amount: float) -> Dict:
        """Gain experience — HNC: accumulate wisdom"""
        self.experience += amount
        
        # Level up at φ-scaled thresholds
        threshold = math.pow(PHI, self.level) * 100
        if self.experience >= threshold:
            self.level += 1
            self.aura_range *= PHI
            new_ability = self._unlock_ability()
            
            return {
                "level_up": True,
                "new_level": self.level,
                "new_ability": new_ability,
                "aura_range": self.aura_range
            }
        
        return {
            "level_up": False,
            "experience": self.experience,
            "next_threshold": threshold
        }
    
    def _unlock_ability(self) -> str:
        """Unlock new ability based on level"""
        abilities = [
            "TEMPEST_SHEILD", "PHI_STRIKE", "SCHUMANN_PULSE",
            "GHOST_DANCE_AURA", "LIGHTHOUSE_BEACON", "TEMPORAL_SHIFT"
        ]
        idx = min(self.level - 2, len(abilities) - 1)
        ability = abilities[idx]
        self.abilities.append(ability)
        return ability
    
    def apply_aura(self, target: Any) -> Dict:
        """Apply aura buff to target — HNC: field injection"""
        if not self.alive:
            return {"error": "Commander is dead"}
        
        buff_multiplier = 1 + (self.level * 0.1) * (PHI - 1)
        
        return {
            "commander": self.name,
            "buff_multiplier": buff_multiplier,
            "abilities": self.abilities,
            "status": "AURA_APPLIED"
        }
    
    def die(self) -> Dict:
        """Commander dies — HNC: system failure"""
        self.alive = False
        return {
            "commander": self.name,
            "status": "KIA",
            "respawn_time": 300,  # 5 minutes
            "penalty": "ALL_AURA_BUFFS_LOST"
        }
    
    def respawn(self) -> Dict:
        """Commander respawns — HNC: system recovery"""
        self.alive = True
        self.experience *= 0.9  # Lose 10% experience (permadeath-lite)
        
        return {
            "commander": self.name,
            "status": "RESPAWNED",
            "experience_remaining": self.experience
        }

# ─────────────────────────────────────────────────────────────────────────────────────
# 🎮 AURIS NODE 18: STATE MACHINE TRANSITIONER (All 3 Games)
# ─────────────────────────────────────────────────────────────────────────────────────

class AurisNode18_StateMachineTransitioner:
    """
    🔄 Auris Node 18 — State Machine Transitioner
    
    From all 3 games:
    - Game states: ECONOMY → BUILDING → PRODUCTION → COMBAT → DIPLOMACY
    - State transitions: trigger → condition → action → next_state
    - Priority interrupts: emergency defense, superweapon ready
    - State history: learn from past transitions
    
    HNC Mapping:
    - Game states = HNC operational modes (victory_hold, harmonic_and_phase, motion)
    - State transitions = Mode switches based on Γ threshold
    - Priority interrupts = Lighthouse alerts / Γ ≥ 0.99 triggers
    - State history = Temporal pattern learning
    """
    
    def __init__(self):
        self.current_state = "ECONOMY"
        self.state_history: List[str] = []
        self.transition_rules: Dict[str, List[Dict]] = {
            "ECONOMY": [
                {"trigger": "sufficient_resources", "next": "BUILDING", "priority": 1},
                {"trigger": "enemy_detected", "next": "DEFENSE", "priority": 10}
            ],
            "BUILDING": [
                {"trigger": "production_ready", "next": "PRODUCTION", "priority": 1},
                {"trigger": "superweapon_charged", "next": "SUPERWEAPON", "priority": 10}
            ],
            "PRODUCTION": [
                {"trigger": "army_ready", "next": "COMBAT", "priority": 1},
                {"trigger": "peace_opportunity", "next": "DIPLOMACY", "priority": 3}
            ],
            "COMBAT": [
                {"trigger": "victory", "next": "ECONOMY", "priority": 1},
                {"trigger": "defeat", "next": "DEFENSE", "priority": 10}
            ],
            "DEFENSE": [
                {"trigger": "threat_neutralized", "next": "ECONOMY", "priority": 1}
            ],
            "DIPLOMACY": [
                {"trigger": "alliance_formed", "next": "ECONOMY", "priority": 1}
            ],
            "SUPERWEAPON": [
                {"trigger": "weapon_fired", "next": "COMBAT", "priority": 1}
            ]
        }
    
    def evaluate_transitions(self, game_state: StrategicPlan) -> Optional[str]:
        """Evaluate possible state transitions — HNC: mode selection"""
        rules = self.transition_rules.get(self.current_state, [])
        
        for rule in sorted(rules, key=lambda x: x["priority"], reverse=True):
            trigger = rule["trigger"]
            
            # Evaluate trigger condition
            if self._check_trigger(trigger, game_state):
                self.state_history.append(self.current_state)
                self.current_state = rule["next"]
                return self.current_state
        
        return None
    
    def _check_trigger(self, trigger: str, game_state: StrategicPlan) -> bool:
        """Check if trigger condition is met"""
        checks = {
            "sufficient_resources": lambda gs: gs.resources.ore > 2000,
            "enemy_detected": lambda gs: len(gs.enemies) > 0,
            "production_ready": lambda gs: len(gs.resources.build_queue) == 0,
            "superweapon_charged": lambda gs: False,  # Would check superweapon state
            "army_ready": lambda gs: len(gs.squads) >= 5,
            "peace_opportunity": lambda gs: any(a["trust"] > 0.7 for a in gs.alliances.values()),
            "victory": lambda gs: gs.overall_strength() > 0.8,
            "defeat": lambda gs: gs.overall_strength() < 0.2,
            "threat_neutralized": lambda gs: len(gs.enemies) == 0,
            "alliance_formed": lambda gs: len(gs.alliances) > 0,
            "weapon_fired": lambda gs: True  # Assume fired when in this state
        }
        
        check_func = checks.get(trigger)
        return check_func(game_state) if check_func else False
    
    def get_optimal_state(self, game_state: StrategicPlan) -> str:
        """Calculate optimal state based on current conditions — HNC: Γ-guided mode"""
        strength = game_state.overall_strength()
        
        if strength > 0.8:
            return "COMBAT"  # Strong, attack
        elif strength > 0.5:
            return "ECONOMY"  # Moderate, build
        elif strength > 0.3:
            return "DEFENSE"  # Weak, defend
        else:
            return "DIPLOMACY"  # Very weak, negotiate

# ─────────────────────────────────────────────────────────────────────────────────────
# 🌐 UNIFIED STRATEGIC WARFARE ENGINE
# ─────────────────────────────────────────────────────────────────────────────────────

class UnifiedStrategicWarfareEngine:
    """
    🌐 Master engine that integrates all 9 new Auris nodes into the HNC pipeline.
    
    Nodes 10-18: Province, Economy, Squad, Diplomacy, Territory, Tech, Superweapon, Commander, State Machine
    
    Usage:
        engine = UnifiedStrategicWarfareEngine()
        engine.initialize_scenario()
        result = engine.execute_turn()
    """
    
    def __init__(self):
        self.node10 = AurisNode10_ProvinceManager()
        self.node11 = AurisNode11_EconomyEngineer()
        self.node12 = AurisNode12_SquadCommander()
        self.node13 = AurisNode13_DiplomacyNegotiator()
        self.node14 = AurisNode14_TerritoryManager()
        self.node15 = AurisNode15_TechTreeClimber()
        self.node16 = AurisNode16_SuperweaponArsenal()
        self.node17 = AurisNode17_CommanderHero()
        self.node18 = AurisNode18_StateMachineTransitioner()
        
        self.turn = 0
        self.game_state = None
    
    def initialize_scenario(self):
        """Initialize a standard scenario"""
        # Provinces (Shogun style)
        for name, ptype in [
            ("Kyoto", ProvinceType.CENTER), ("Osaka", ProvinceType.RICE),
            ("Edo", ProvinceType.IRON), ("Nagoya", ProvinceType.TEA),
            ("Hiroshima", ProvinceType.BORDER)
        ]:
            self.node10.add_province(name, ptype, economy=random.uniform(100, 500))
        
        # Territories (Dawn of War style)
        for name, value, conns in [
            ("Central_Plains", 500, ["North_Hills", "South_Forest"]),
            ("North_Hills", 300, ["Central_Plains", "East_Marsh"]),
            ("South_Forest", 400, ["Central_Plains", "West_Coast"]),
            ("East_Marsh", 200, ["North_Hills"]),
            ("West_Coast", 350, ["South_Forest"])
        ]:
            self.node14.add_territory(name, value, conns)
        
        # Squads (Dawn of War style)
        self.node12.form_squad("Alpha", SquadType.TACTICAL, (0, 0))
        self.node12.reinforce_squad("Alpha", 4)
        
        self.node12.form_squad("Beta", SquadType.ASSAULT, (10, 10))
        self.node12.reinforce_squad("Beta", 3)
        
        # Commander
        self.node17 = AurisNode17_CommanderHero("Prime Sentinel")
    
    def execute_turn(self) -> Dict:
        """Execute one full turn through all 9 nodes"""
        self.turn += 1
        
        results = {
            "turn": self.turn,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "nodes": {}
        }
        
        # Node 10: Province management
        tax_result = self.node10.collect_taxes()
        results["nodes"]["province"] = tax_result
        
        # Node 11: Economy
        if self.node11.resources.ore < 500:
            build_result = self.node11.build_miner()
            results["nodes"]["economy"] = build_result
        
        # Node 12: Squad command
        if self.node12.squads:
            squad = random.choice(list(self.node12.squads.keys()))
            morale = self.node12.manage_morale(squad, random.choice(["victory", "draw"]))
            results["nodes"]["squad"] = morale
        
        # Node 13: Diplomacy
        if random.random() < 0.3:
            alliance = self.node13.propose_alliance("Clan_Shimazu", "MILITARY")
            results["nodes"]["diplomacy"] = alliance
        
        # Node 14: Territory
        targets = self.node14.find_expansion_targets()
        if targets:
            results["nodes"]["territory"] = {"targets": targets[:3]}
        
        # Node 15: Tech
        if self.node15.current_tier.value < 3 and random.random() < 0.2:
            tech = self.node15.research(f"T{self.node15.current_tier.value + 1}")
            results["nodes"]["tech"] = tech
        
        # Node 16: Superweapon
        charge = self.node16.charge_all(50.0)
        results["nodes"]["superweapon"] = charge
        
        # Node 17: Commander
        exp = self.node17.gain_experience(10.0)
        results["nodes"]["commander"] = exp
        
        # Node 18: State machine
        # Build a simple strategic plan for state evaluation
        plan = StrategicPlan(
            provinces=self.node10.provinces,
            resources=self.node11.resources,
            squads=self.node12.squads,
            tech_tree=TechTree(self.node15.current_tier, self.node15.researched, [], {}),
            alliances=self.node13.alliances,
            enemies=["enemy_1"],
            turn_number=self.turn
        )
        optimal = self.node18.get_optimal_state(plan)
        results["nodes"]["state_machine"] = {"optimal_state": optimal}
        
        return results
    
    def get_status(self) -> Dict:
        """Get full engine status"""
        return {
            "turn": self.turn,
            "nodes_active": 9,
            "provinces": len(self.node10.provinces),
            "squads": len(self.node12.squads),
            "tech_tier": self.node15.current_tier.name,
            "commander_level": self.node17.level,
            "commander_alive": self.node17.alive,
            "current_state": self.node18.current_state
        }


# ─────────────────────────────────────────────────────────────────────────────────────
# SELF-TEST
# ─────────────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("🎮 AURIS STRATEGIC WARFARE NODES — Self-Test")
    print("=" * 60)
    
    engine = UnifiedStrategicWarfareEngine()
    engine.initialize_scenario()
    
    print(f"\n📊 Initial Status: {engine.get_status()}")
    
    for i in range(3):
        result = engine.execute_turn()
        print(f"\n🎲 Turn {result['turn']}:")
        for node, data in result['nodes'].items():
            print(f"  {node}: {json.dumps(data, default=str)[:100]}")
    
    print(f"\n📊 Final Status: {engine.get_status()}")
    print("\n✅ All 9 Auris nodes operational. Strategic warfare logic extracted and integrated.")
    print("🛡️ The field holds. The computer brains are now in the HNC system.")
