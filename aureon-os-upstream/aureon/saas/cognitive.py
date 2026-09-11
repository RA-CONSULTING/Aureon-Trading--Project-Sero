"""
Aureon SaaS — the cognitive substrate as verified read APIs.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

The organism is connected end-to-end — the HNC field, the connectome body-map,
the mycelium mesh, the thought bus, and the miner brain all breathe together.
This module *productizes* that substrate: it turns each cognitive and
meta-cognitive system into a first-class SaaS surface that anyone can read over
HTTP (``GET /api/cognition/...``), and it stamps every response with honest
**data provenance** so a consumer knows whether they are reading live truth,
a cached real value, or nothing at all.

Two invariants make this safe to expose:

  1. **Never cold-boot a heavy organ from a GET.** ``get_miner_brain()``,
     ``get_mycelium()`` and ``Connectome.sense()`` all have heavy / side-effectful
     init. So the brain surface reads the persisted prediction/knowledge files
     directly (never constructs the brain), and the mycelium surface reports only
     when the singleton already exists (``no_data`` / dormant otherwise) — the
     same posture ``build_organism_payload`` takes for the Queen.

  2. **Never fabricate.** Each surface carries a ``truth_status`` drawn from the
     repo's real-data contract vocabulary (``live`` / ``real_derived`` /
     ``cached_real`` / ``no_data``). When a signal is not flowing the surface
     says ``no_data`` with a blocker — it does not invent a plausible number.

Every builder is guarded and never raises: a dead organ degrades to an
unavailable surface, not a 500.

Gary Leckey · Aureon Institute
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Callable, Dict, List

logger = logging.getLogger("aureon.saas.cognitive")

_REPO_ROOT = Path(
    os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))
)

# Key topic families that carry the organism's cognition — surfaced by the bus
# view so a consumer sees the living links, not just an anonymous topic count.
_COGNITIVE_TOPIC_FAMILIES = (
    "symbolic.life.pulse", "symbolic.life.subfield", "organism.field.consensus",
    "organism.connectome.pulse", "baton.link", "cognition.complete",
    "auris.throne.cosmic_state", "lighthouse.event", "operator.action.verdict",
)


# ── provenance — reuse the repo's real-data contract vocabulary ───────────────

def provenance_block() -> Dict[str, Any]:
    """A response-level provenance header, mirroring the connections layer's
    ``_real_data_policy_summary`` shape but self-contained (reuses the same
    ``real_data_contract`` / ``live_data_policy`` primitives, no private import).
    Shared by every SaaS surface so each response carries honest provenance.
    Never raises."""
    block: Dict[str, Any] = {
        "simulation_fallback_allowed": False,
        "truth_statuses": [],
        "source_registry_count": 0,
        "policy": "no fabricated values — a dormant organ reports no_data, never a guess",
    }
    try:
        from aureon.observer.live_data_policy import simulation_fallback_allowed
        from aureon.observer.real_data_contract import TRUTH_STATUSES, load_source_registry

        block["simulation_fallback_allowed"] = bool(simulation_fallback_allowed())
        block["truth_statuses"] = sorted(TRUTH_STATUSES)
        try:
            sources = load_source_registry(_REPO_ROOT).get("sources", {})
            block["source_registry_count"] = len(sources) if isinstance(sources, dict) else 0
        except Exception:  # noqa: BLE001 — registry optional
            pass
    except Exception as exc:  # noqa: BLE001 — contract module optional
        block["provenance_error"] = str(exc)[:160]
    return block


def _summarize(surfaces: Dict[str, Dict[str, Any]]) -> Dict[str, int]:
    """Roll the per-surface ``truth_status`` up via the contract's summarizer."""
    try:
        from aureon.observer.real_data_contract import summarize_truth_status

        return summarize_truth_status(
            [{"truth_status": s.get("truth_status", "no_data")} for s in surfaces.values()]
        )
    except Exception:  # noqa: BLE001
        return {}


# ── the field's producers — an honest live-vs-intended map ────────────────────

# The whole-body HNC field (``blend_field``) fuses whatever ``symbolic.life.subfield``
# producers are *present*. This is the documented set of every producer *intended* to
# feed it, each marked ``live`` iff its ``source`` string is currently in
# ``read_subfields()`` — so the map shows exactly who is feeding the field right now
# and names the dark ones truthfully, rather than papering over the gap. The exact
# ``source`` strings match each ``publish_subfield(...)`` caller in the repo.
_INTENDED_PRODUCERS: tuple[Dict[str, str], ...] = (
    # live-in-daemon — booted by organism_daemon.breathe() / boot(), publishing each breath
    {"source": "metacognition_monitor", "host": "organism_daemon",
     "note": "the organism reads its own signals and loops self-coherence back each breath"},
    {"source": "affect_monitor", "host": "organism_daemon",
     "note": "victory/defeat/fear/resolve, felt from real signals and folded in each breath"},
    {"source": "inner_work", "host": "organism_daemon",
     "note": "the seven-chakra ascent state, folded in each breath"},
    {"source": "pursuit", "host": "organism_daemon",
     "note": "the pursuit-of-happiness compass, folded in each breath"},
    {"source": "consciousness_module", "host": "organism_daemon",
     "note": "the metacognitive Λ field, published on each heartbeat when the engine is live"},
    {"source": "dr_auris_throne", "host": "organism_daemon",
     "note": "the cosmic/harmonic throne loop, autostarted in boot()"},
    {"source": "mycelium_mesh", "host": "organism_daemon",
     "note": "the mesh's network coherence — live once the connectome sweep first weaves the mesh singleton"},
    # ICS-hosted (dark) — publish only inside integrated_cognitive_system, which the
    # minimal daemon does not boot. Booting ICS is a deployment decision, not a
    # fabricated bridge, so these are named honestly rather than overclaimed as live.
    {"source": "queen_cortex", "host": "integrated_cognitive_system",
     "note": "Queen Λ engine; host not booted in the minimal daemon"},
    {"source": "queen_source_law", "host": "integrated_cognitive_system",
     "note": "Queen Λ engine; host not booted, and event-driven (publishes per decision)"},
    {"source": "queen_metacognition", "host": "integrated_cognitive_system",
     "note": "Queen Λ engine; host not booted in the minimal daemon"},
    {"source": "queen_sentient_loop", "host": "integrated_cognitive_system",
     "note": "Queen Λ engine; host not booted in the minimal daemon"},
    {"source": "queen_mycelium_mind", "host": "queen_layer / integrated_cognitive_system",
     "note": "thought-propagation spore engine; live on the Queen/ignition boot path, dark only in the minimal organism daemon"},
    {"source": "hnc_human_loop", "host": "integrated_cognitive_system",
     "note": "human-in-the-loop Λ producer; host not booted, and event-driven (publishes per message)"},
    {"source": "harmonic_observer", "host": "hnc_live_daemon",
     "note": "FFT-of-Λ spectral observer; publishes its local field each daemon compute step (throttled 30 s), dark until the observer has data"},
)


def field_producers(subs: Dict[str, Any]) -> Dict[str, Any]:
    """An honest live-vs-intended map of who feeds the whole-body field.

    ``subs`` is the live ``read_subfields()`` mapping (source → field). Each intended
    producer is marked ``live`` iff its ``source`` is a present key — a real signal,
    nothing fabricated. Dark producers are named truthfully (host not booted /
    event-driven), so the map never overclaims a dark producer as connected.
    Never raises.
    """
    try:
        present = set(subs.keys()) if isinstance(subs, dict) else set()
        producers = [{**p, "live": p["source"] in present} for p in _INTENDED_PRODUCERS]
        return {
            "producers": producers,
            "live_count": sum(1 for p in producers if p["live"]),
            "intended_count": len(producers),
        }
    except Exception as exc:  # noqa: BLE001
        return {"producers": [], "live_count": 0, "intended_count": 0,
                "blocker": f"producer map failed: {str(exc)[:120]}"}


# ── the five cognitive surfaces ───────────────────────────────────────────────

def field_surface(bus: Any = None) -> Dict[str, Any]:
    from aureon.saas.observed_runtime import canonical_surface
    return canonical_surface(bus)

def _consensus_event(bus: Any = None) -> Dict[str, Any] | None:
    try:
        from aureon.core.aureon_thought_bus import get_thought_bus, payload_of

        b = bus if bus is not None else get_thought_bus()
        events = b.recall("organism.field.consensus", limit=1) or []
        if events:
            ev = events[-1]
            ts = ev.get("ts") if isinstance(ev, dict) else getattr(ev, "ts", None)
            return {
                "age_s": round(time.time() - float(ts), 1) if ts else None,
                "payload": payload_of(ev),
                "source": "bus",
            }
    except Exception:  # noqa: BLE001
        pass
    # Cross-process fallback: the organism daemon breathes consensus in another
    # process; read the dedicated trace it writes so the heartbeat still shows.
    try:
        from aureon.core.bus_trace import read_trace_latest

        row = read_trace_latest("organism_consensus")
        if not row:
            return None
        ts = row.get("ts")
        return {
            "age_s": round(time.time() - float(ts), 1) if ts else None,
            "payload": {k: v for k, v in row.items() if k != "ts"},
            "source": "consensus_trace_file",
        }
    except Exception:  # noqa: BLE001
        return None


def bus_surface(bus: Any = None) -> Dict[str, Any]:
    from aureon.saas.observed_runtime import bus_observation
    return bus_observation(bus)

def mycelium_surface() -> Dict[str, Any]:
    from aureon.saas.observed_runtime import observed_organism
    return observed_organism()["mycelium"]

def connectome_surface() -> Dict[str, Any]:
    from aureon.saas.observed_runtime import observed_organism
    row = observed_organism()["connectome"]
    historical = row.get("source_timestamp") is not None and row.get("read_state") in {"observed", "stale"}
    return {**row, "body_map": dict(row), "classification": "recorded_history",
            "historical_available": historical, "truth_status": "cached_real" if historical else "no_data"}

def _brain_path(env_key: str, default_name: str) -> Path:
    return Path(os.environ.get(env_key) or (_REPO_ROOT / default_name))


def brain_surface() -> Dict[str, Any]:
    from aureon.saas.observed_runtime import brain_observation
    return brain_observation()

# ── the umbrella ──────────────────────────────────────────────────────────────

_SURFACE_BUILDERS: Dict[str, Callable[[], Dict[str, Any]]] = {
    "field": field_surface,
    "bus": bus_surface,
    "mycelium": mycelium_surface,
    "connectome": connectome_surface,
    "brain": brain_surface,
}


def build_cognitive_payload() -> Dict[str, Any]:
    """The whole cognitive substrate as one verified SaaS payload: every surface
    plus a provenance header and a truth-status roll-up. Never raises — a dead
    organ shows as a ``no_data`` surface, and the roll-up counts it as blocked."""
    surfaces: Dict[str, Dict[str, Any]] = {}
    import sys
    from aureon.saas.observed_runtime import runtime_source_observations, process_observation
    from aureon.saas.research_activity import research_activity_observation
    bus = getattr(sys.modules.get("aureon.core.aureon_thought_bus"), "_thought_bus_instance", None)

    for name, builder in _SURFACE_BUILDERS.items():
        try:
            surfaces[name] = builder(bus) if name in ("field", "bus") else builder()  # type: ignore[call-arg]
        except Exception as exc:  # noqa: BLE001 — one dead organ never sinks the payload
            surfaces[name] = {"truth_status": "no_data", "blocker": f"{name} failed: {str(exc)[:120]}"}

    roll = _summarize(surfaces)
    observed_fresh = sum(surface.get("available") is True and surface.get("fresh") is True for surface in surfaces.values())
    # A retained history is useful evidence, but not a currently operating organ.
    roll["operational_ready"] = observed_fresh
    roll["blocked"] = len(surfaces) - observed_fresh
    registry: List[Dict[str, Any]] = []
    try:
        from aureon.saas.domains import cognitive_surface_report

        registry = cognitive_surface_report()
    except Exception:  # noqa: BLE001 — catalog view optional
        registry = []
    return {
        "available": any(surface.get("available") for surface in surfaces.values()),
        "product_domain": "cognition",
        "research_activity": research_activity_observation(),
        "runtime_sources": runtime_source_observations(),
        "process_observation": process_observation(),
        "surfaces": surfaces,
        "registry": registry,
        "provenance": provenance_block(),
        "truth_summary": roll,
        "operational_ready": roll.get("operational_ready", 0),
        "observed_fresh_count": observed_fresh,
        "count_scope": "fresh_source_observations_not_functional_health",
        "blocked": roll.get("blocked", 0),
    }


__all__ = [
    "build_cognitive_payload",
    "provenance_block",
    "field_surface",
    "bus_surface",
    "mycelium_surface",
    "connectome_surface",
    "brain_surface",
]
