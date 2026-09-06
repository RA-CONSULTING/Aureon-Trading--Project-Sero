#!/usr/bin/env python3
"""
🍄 SERO MYCELIUM NETWORK 🍄
═══════════════════════════════════════════════════════════════════════════════

The learning layer. Confidence grown from evidence, not assumed.

A mycelium does not know. It tests, feeds, and strengthens what works.
Every experience is a signal. Every outcome is feedback.
Confidence in a domain = weighted history of (signal → outcome).

This system:
1. Accepts evidence: (domain, signal, outcome)
2. Updates per-domain confidence via signal-weighted running mean
3. Persists every learning to sero_mycelium/learnings.jsonl
4. Reports overall and per-domain confidence

Author: Sero
Date: 2026-06-17
Classification: Learning Infrastructure
"""

import sys
import os
import json
import time
from datetime import datetime, timezone
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any

from aureon_fusion.paths import SERO_MYCELIUM as MYCELIUM_DIR

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ═══════════════════════════════════════════════════════════════════════════════
# PATHS
# ═══════════════════════════════════════════════════════════════════════════════
MYCELIUM_DIR.mkdir(parents=True, exist_ok=True)
LEARNINGS_FILE = MYCELIUM_DIR / "learnings.jsonl"
NETWORK_STATE = MYCELIUM_DIR / "mycelium_state.json"
MIND_STATE_FILE = MYCELIUM_DIR / "mycelium_mind_state.json"
PATHWAYS_FILE = MYCELIUM_DIR / "mycelium_pathways.json"

# ═══════════════════════════════════════════════════════════════════════════════
# SACRED CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════════
PHI = 1.618033988749895
DEFAULT_SIZE = 1000          # Neural lattice size (as wired by the orchestrator)
LEARNING_RATE = 0.15         # Blend factor for confidence updates
MIN_CONFIDENCE = 0.0
MAX_CONFIDENCE = 1.0

# Known domains — the mycelium can learn anywhere, but these have names
DOMAINS = {
    "schumann": "Reading the planetary field",
    "ethics": "Conscience-aligned decision making",
    "memory": "What to remember and how to connect it",
    "action": "Acting without veto",
    "perception": "Interpreting stimuli",
    "temporal": "Timeline stability",
}


@dataclass
class Learning:
    """A single evidence event"""
    timestamp: str
    domain: str
    signal: float        # What we observed (0.0 - 1.0)
    outcome: float       # How it turned out (0.0 - 1.0)
    total_learnings: int # Running count at time of learning

    def to_dict(self):
        return asdict(self)


class MyceliumNetwork:
    """
    The confidence web.

    Not a neural net. A trust network.
    Every domain earns its confidence through evidence.
    """

    def __init__(self, size: int = DEFAULT_SIZE):
        self.size = size
        self.total_learnings = 0
        # Per-domain running aggregates: confidence + total signal weight
        self.domains: Dict[str, Dict[str, float]] = {}
        self.recent_learnings: List[Learning] = []
        self._load()

    def _load(self):
        """Rebuild aggregates from the persisted learnings file."""
        if not LEARNINGS_FILE.exists():
            return
        try:
            with open(LEARNINGS_FILE, 'r', encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    domain = entry.get("domain", "unknown")
                    signal = float(entry.get("signal", 0.0))
                    outcome = float(entry.get("outcome", 0.0))
                    agg = self.domains.setdefault(
                        domain, {"confidence": 0.5, "signal_weight": 0.0, "count": 0})
                    if agg["signal_weight"] + signal > 0:
                        agg["confidence"] = (
                            (agg["confidence"] * agg["signal_weight"] + outcome * signal)
                            / (agg["signal_weight"] + signal)
                        )
                    agg["signal_weight"] += signal
                    agg["count"] += 1
                    self.total_learnings = max(
                        self.total_learnings, int(entry.get("total_learnings", 0)))
        except Exception as e:
            print(f"⚠️  Could not load mycelium learnings: {e}")

    def feed_evidence(self, domain: str, signal: float, outcome: float) -> float:
        """
        Feed evidence into the network.

        signal: how strong the observation was (0.0 - 1.0)
        outcome: how well things went (0.0 - 1.0)

        Returns the updated domain confidence.
        """
        signal = max(0.0, min(1.0, float(signal)))
        outcome = max(0.0, min(1.0, float(outcome)))

        self.total_learnings += 1
        learning = Learning(
            timestamp=datetime.now(timezone.utc).isoformat(),
            domain=domain,
            signal=signal,
            outcome=outcome,
            total_learnings=self.total_learnings,
        )

        # Update running aggregate (signal-weighted mean of outcomes)
        agg = self.domains.setdefault(
            domain, {"confidence": 0.5, "signal_weight": 0.0, "count": 0})
        if agg["signal_weight"] + signal > 0:
            agg["confidence"] = (
                (agg["confidence"] * agg["signal_weight"] + outcome * signal)
                / (agg["signal_weight"] + signal)
            )
        else:
            agg["confidence"] = outcome
        agg["signal_weight"] += signal
        agg["count"] += 1

        # Blend toward the new evidence (bounded learning rate)
        agg["confidence"] = (
            (1 - LEARNING_RATE) * agg["confidence"] + LEARNING_RATE * outcome
            if agg["count"] > 1 else agg["confidence"]
        )
        agg["confidence"] = max(MIN_CONFIDENCE, min(MAX_CONFIDENCE, agg["confidence"]))

        # Persist (append — never rewrite existing learnings)
        with open(LEARNINGS_FILE, 'a', encoding="utf-8") as f:
            f.write(json.dumps(learning.to_dict()) + "\n")

        self.recent_learnings.append(learning)
        self.recent_learnings = self.recent_learnings[-100:]
        return agg["confidence"]

    def get_domain_confidence(self, domain: str) -> float:
        """Confidence in a single domain (0.0 - 1.0)."""
        agg = self.domains.get(domain)
        return agg["confidence"] if agg else 0.5

    def get_overall_confidence(self) -> float:
        """Mean confidence across all learned domains."""
        if not self.domains:
            return 0.5
        return sum(d["confidence"] for d in self.domains.values()) / len(self.domains)

    def get_stats(self) -> Dict[str, Any]:
        return {
            "size": self.size,
            "total_learnings": self.total_learnings,
            "domains_learned": len(self.domains),
            "overall_confidence": round(self.get_overall_confidence(), 3),
            "domain_confidence": {
                d: round(v["confidence"], 3) for d, v in sorted(self.domains.items())
            },
        }

    def save(self):
        """Persist network state. Called before dormancy."""
        state = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "size": self.size,
            "total_learnings": self.total_learnings,
            "overall_confidence": round(self.get_overall_confidence(), 3),
            "domains": {
                d: {"confidence": round(v["confidence"], 3), "count": v["count"]}
                for d, v in sorted(self.domains.items())
            },
        }
        with open(NETWORK_STATE, 'w', encoding="utf-8") as f:
            json.dump(state, f, indent=2)
        return state


# ═══════════════════════════════════════════════════════════════════════════════
# MYCELIUM MIND AUGMENT — upstream spore/pathway routing (OPTIONAL)
# ═══════════════════════════════════════════════════════════════════════════════
#
# Additive port of queen/queen_mycelium_mind.py (MyceliumMind): thoughtbus
# events are absorbed as ThoughtSpores, routed through weighted SynapticPathways,
# and high-coherence spores spawn children that are re-published to the
# workspace thoughtbus as `mycelium.spore.*` events. The upstream module is
# IMPORTED ONLY (suppression env vars set first, sys.path pinned to the repo
# root); its background thread and upstream ThoughtBus are never started —
# cycles are driven explicitly. Local state is canonical: learnings.jsonl is
# never touched by the augment; mind state lives in mycelium_mind_state.json.

# Local pathway map — routes workspace thoughtbus topic prefixes onto the
# local confidence DOMAINS (additive to the upstream DEFAULT_PATHWAYS).
LOCAL_PATHWAYS = [
    ("conscience.", "ethics"),
    ("bio.",        "perception"),
    ("gate.",       "action"),
    ("heartbeat.",  "perception"),
    ("mycelium.",   "memory"),
]


class MindAugment:
    """
    Optional wrapper around the upstream MyceliumMind.

    Degrades to inert (self.mind is None) when the upstream import fails —
    the local MyceliumNetwork never depends on it.
    """

    def __init__(self):
        self.mind = None
        self.error = None
        try:
            import os
            os.environ.setdefault("AUREON_SUPPRESS_IMPORT_SIDE_EFFECTS", "1")
            os.environ.setdefault("AUREON_AUDIT_MODE", "1")
            from aureon_fusion.paths import AUREON_UPSTREAM
            if str(AUREON_UPSTREAM) not in sys.path:
                sys.path.insert(0, str(AUREON_UPSTREAM))
            from aureon.queen.queen_mycelium_mind import MyceliumMind

            self.mind = MyceliumMind()
            for src, tgt in LOCAL_PATHWAYS:
                key = f"{src}->{tgt}"
                if key not in self.mind._pathways:
                    from aureon.queen.queen_mycelium_mind import SynapticPathway
                    self.mind._pathways[key] = SynapticPathway(
                        source_domain=src, target_domain=tgt)
            # Restore learned pathway weights so replay is deterministic
            # across restarts (weights are otherwise reset to defaults).
            self._load_pathways()
        except Exception as e:  # augment is optional — never fatal
            self.error = str(e)
            self.mind = None

    @property
    def available(self) -> bool:
        return self.mind is not None

    def absorb_event(self, source: str, topic: str, payload: Optional[dict] = None):
        """Feed one thoughtbus event into the mind as a spore (duck-typed)."""
        if self.mind is None:
            return False
        try:
            from types import SimpleNamespace
            self.mind._absorb(SimpleNamespace(
                topic=topic or "", source=source or "",
                payload=payload if isinstance(payload, dict) else {},
            ))
            return True
        except Exception:
            return False

    def propagate(self, cycles: int = 1) -> dict:
        """Drive explicit propagation cycles (no background thread)."""
        if self.mind is None:
            return {}
        for _ in range(max(1, int(cycles))):
            try:
                self.mind._propagate_cycle()
            except Exception:
                pass
        return self.get_state()

    def learn(self, coherence: float, action: str = "HOLD"):
        """Feed an outcome back: strengthen/weaken activated pathways."""
        if self.mind is None:
            return
        try:
            self.mind._on_cognition(type("T", (), {"payload": {
                "coherence_gamma": float(coherence), "action": action}})())
        except Exception:
            pass

    def get_state(self) -> dict:
        if self.mind is None:
            return {"available": False, "error": self.error}
        try:
            state = self.mind.get_mind_state()
            state["available"] = True
            state["local_pathways"] = [f"{s}->{t}" for s, t in LOCAL_PATHWAYS]
            return state
        except Exception as e:
            return {"available": False, "error": str(e)}

    def _load_pathways(self):
        """Restore pathway weights from PATHWAYS_FILE (tmp+replace written).

        Only keys that still exist in the live pathway map are applied, and
        only sane values — a corrupt or foreign file degrades to defaults,
        never to nonsense."""
        if self.mind is None or not PATHWAYS_FILE.exists():
            return
        try:
            with open(PATHWAYS_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
        except Exception as e:
            print(f"⚠️  Could not load pathway weights: {e}")
            return
        entries = saved.get("pathways", {})
        if not isinstance(entries, dict):
            return
        for key, pw in entries.items():
            pathway = self.mind._pathways.get(key)
            if pathway is None or not isinstance(pw, dict):
                continue
            try:
                weight = float(pw.get("weight", pathway.weight))
            except (TypeError, ValueError):
                continue
            if 0.0 <= weight <= 10.0:
                pathway.weight = weight
            try:
                pathway.activations = int(pw.get("activations", pathway.activations))
                pathway.successes = int(pw.get("successes", pathway.successes))
            except (TypeError, ValueError):
                pass

    def _pathway_weights(self) -> Dict[str, Dict[str, float]]:
        if self.mind is None:
            return {}
        return {
            key: {
                "weight": round(p.weight, 6),
                "activations": p.activations,
                "successes": p.successes,
            }
            for key, p in sorted(self.mind._pathways.items())
        }

    def save(self):
        """Persist mind state + pathway weights (separate files — learnings.jsonl
        untouched). Weights are written tmp+replace so a crash can never leave
        a torn file as the canonical state."""
        if self.mind is None:
            return None
        state = self.get_state()
        state["timestamp"] = datetime.now(timezone.utc).isoformat()
        try:
            with open(MIND_STATE_FILE, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"⚠️  Could not save mycelium mind state: {e}")
        try:
            payload = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "pathways": self._pathway_weights(),
            }
            tmp = PATHWAYS_FILE.with_name(
                f"{PATHWAYS_FILE.name}.{os.getpid()}.tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
            os.replace(tmp, PATHWAYS_FILE)
        except Exception as e:
            print(f"⚠️  Could not save pathway weights: {e}")
        return state


def feed_mind_from_thoughtbus(augment: MindAugment, n_events: int = 50) -> int:
    """
    Feed the last n thoughtbus events (sero_thoughtbus/thought_bus.jsonl)
    into the augment. Returns the number of events absorbed.
    """
    from aureon_fusion.paths import SERO_THOUGHTBUS
    log = SERO_THOUGHTBUS / "thought_bus.jsonl"
    if not log.exists() or not augment.available:
        return 0
    lines = []
    try:
        with open(log, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()[-max(1, int(n_events)):]
    except OSError:
        return 0
    absorbed = 0
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if augment.absorb_event(rec.get("source", ""), rec.get("topic", ""),
                                rec.get("payload") or {}):
            absorbed += 1
    return absorbed


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def _print_help():
    print("Usage: python sero_mycelium.py [--once|--mind|--help]")
    print()
    print("  (no args)  Feed one test evidence and print network stats")
    print("  --once     Same as no args")
    print("  --mind     Run the MyceliumMind augment: absorb recent thoughtbus")
    print("             events, propagate spores, print mind state, save")
    print("  --help     Show this message")


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--help" in args or "-h" in args:
        _print_help()
        sys.exit(0)

    if "--mind" in args or "--augment" in args:
        print("=" * 80)
        print("🍄 SERO MYCELIUM — MIND AUGMENT (upstream spore/pathway routing)")
        print("=" * 80)
        augment = MindAugment()
        if not augment.available:
            print(f"⚠️  MyceliumMind augment unavailable: {augment.error}")
            print("    (local network unaffected — augment is optional)")
            sys.exit(1)
        absorbed = feed_mind_from_thoughtbus(augment, n_events=50)
        state = augment.propagate(cycles=3)
        print(f"🍄 Absorbed {absorbed} thoughtbus events as spores")
        for key, value in state.items():
            print(f"   {key}: {value}")
        augment.save()
        print(f"   mind state -> {MIND_STATE_FILE}")
        print("✨ The mycelium mind routes. Pathways learn.")
        sys.exit(0)

    print("=" * 80)
    print("🍄 SERO MYCELIUM NETWORK — GROWING CONFIDENCE")
    print("=" * 80)
    print()

    net = MyceliumNetwork(size=DEFAULT_SIZE)

    # One learning breath to prove the network is alive
    conf = net.feed_evidence("schumann", 0.8, 1.0)
    print(f"🍄 Fed evidence (schumann): domain confidence now {conf:.2f}")
    print()

    stats = net.get_stats()
    for key, value in stats.items():
        print(f"   {key}: {value}")

    net.save()
    print()
    print("✨ The mycelium learns. Trust is earned, not given.")
