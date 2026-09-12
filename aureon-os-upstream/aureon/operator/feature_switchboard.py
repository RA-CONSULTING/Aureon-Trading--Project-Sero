"""
Aureon Operator — the feature switchboard.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Turn every system feature on/off at human discretion. Instance-owned, admin-managed
via the operator bearer gate — one global flag set, encrypted at rest at
``~/.aureon/feature_flags.json.enc`` (key file ``~/.aureon/feature_flags.key``,
mode 0600), applied to ``os.environ`` at each daemon's boot via
``bootstrap_credentials()`` (aureon.core.aureon_env). Never committed.

Two tiers:

* **safe / reversible** — organism & connectome, cognition routing, notifications.
* **hard boundary** — live trading, cloud execution holds, armed local actions,
  soul-act autonomy, billing charge, sovereign mode. Entering each flag's risky
  value requires an explicit typed-confirm ceremony (see the route layer).

The load-bearing invariant: this module is a **human control plane**. Flipping a
flag either sets that flag's own env var or records a cloud handoff request.
``apply_to_env()`` imports nothing from
the trading/conscience/runtime layer and calls no executor. Arming a hard-boundary
flag records the human's intent — it does **not** remove any downstream
gate: the conscience veto, the approval queue (records, never executes), and the
runtime dry-run gates all stay in force, and no internal score self-arms anything.
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger("aureon.operator.feature_switchboard")

CONFIG_DIR = Path.home() / ".aureon"
KEY_PATH = CONFIG_DIR / "feature_flags.key"
STORE_PATH = CONFIG_DIR / "feature_flags.json.enc"

_TRUTHY = {"1", "true", "yes", "on", "t", "y"}


@dataclass(frozen=True)
class FeatureFlag:
    """One boolean capability gate, surfaced honestly."""

    id: str  # the env var — the single identifier (also the typed-confirm token)
    label: str
    group: str
    kind: str  # "safe" | "hard_boundary"
    effect: str  # "live" | "restart" | "handoff" (cloud supervisor must apply)
    effect_note: str
    description: str
    default: bool = False  # the consuming process's own default when the flag is unset
    risk_value: bool = True  # value which requires the typed-confirm ceremony

    @property
    def env_var(self) -> str:
        return self.id

    def to_public_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "env_var": self.env_var,
            "label": self.label,
            "group": self.group,
            "kind": self.kind,
            "effect": self.effect,
            "effect_note": self.effect_note,
            "description": self.description,
            "default": self.default,
            "risk_value": self.risk_value,
        }


# ── The registry — the single source of truth for every switchable feature ─────
# Ordered by group; group order below is the display order.
FLAGS: List[FeatureFlag] = [
    # ── Organism & Connectome (the self-wiring nervous system) ──
    FeatureFlag(
        "AUREON_CONNECTOME_SWEEP", "Connectome sweep", "Organism & Connectome",
        "safe", "restart", "Organism daemon re-reads on restart.",
        "Progressively touch the whole module tree so the organism senses its own body.",
        default=True,
    ),
    FeatureFlag(
        "AUREON_CONNECTOME_WEAVE", "Connectome weave", "Organism & Connectome",
        "safe", "restart", "Organism daemon re-reads on restart.",
        "Graduate touched modules onto the mycelium mesh + Queen (integration climbs).",
        default=True,
    ),
    FeatureFlag(
        "AUREON_AURIS_AUTOSTART", "Dr Auris throne", "Organism & Connectome",
        "safe", "restart", "Organism daemon re-reads on restart.",
        "Start the Dr Auris cosmic-state loop so the cosmic gate reads a live signal.",
        default=True,
    ),
    FeatureFlag(
        "AUREON_TRACE_PUMP", "Trace pump", "Organism & Connectome",
        "safe", "restart", "Organism daemon re-reads on restart.",
        "Republish cross-process bus traces (auris/lighthouse) onto the local bus.",
        default=True,
    ),
    # ── Cognition routing (which brain answers) ──
    FeatureFlag(
        "AUREON_COGNITION_PREFER_LOCAL", "Prefer local LLM", "Cognition Routing",
        "safe", "live", "Applied to the operator immediately; daemons on restart.",
        "Route cognition to the local/Ollama model first, cloud as fallback.",
    ),
    FeatureFlag(
        "AUREON_LLM_OFFLINE", "LLM offline mode", "Cognition Routing",
        "safe", "live", "Applied to the operator immediately; daemons on restart.",
        "Disable all outbound LLM/network calls — deterministic, offline-safe reasoning.",
    ),
    FeatureFlag(
        "AUREON_AFFECT_MODULATION", "Affect modulation", "Cognition Routing",
        "safe", "restart", "Consuming process re-reads on restart (call-time, fail-safe).",
        "Let felt fear/defeat tighten the grounded-action risk gate (only ever tightens).",
    ),
    # ── Notifications (recording only) ──
    FeatureFlag(
        "AUREON_APPROVAL_EMAIL", "Approval email loop", "Notifications",
        "safe", "restart", "The approval-email loop reads at boot.",
        "Email the owner each prepared big play and read replies as decisions (records, never executes).",
    ),
    # ── Hard boundary (risky value needs exact typed confirmation) ──
    FeatureFlag(
        "AUREON_DEPLOYMENT_HOLD", "Deployment hold", "Hard Boundary",
        "hard_boundary", "handoff", "Saved for a governed cloud runtime handoff; running services remain unchanged.",
        "Keep the production deployment held. Turning this OFF requests release, but does not bypass release evidence or authority checks.",
        default=True, risk_value=False,
    ),
    FeatureFlag(
        "AUREON_DISABLE_REAL_ORDERS", "Disable real orders", "Hard Boundary",
        "hard_boundary", "handoff", "Saved for a governed cloud runtime handoff; running services remain unchanged.",
        "Keep real orders disabled. Turning this OFF requests order permission, subject to every downstream execution gate.",
        default=True, risk_value=False,
    ),
    FeatureFlag(
        "AUREON_DISABLE_EXCHANGE_MUTATIONS", "Disable exchange mutations", "Hard Boundary",
        "hard_boundary", "handoff", "Saved for a governed cloud runtime handoff; running services remain unchanged.",
        "Keep exchange mutations disabled. Turning this OFF requests mutation permission, subject to provider and runtime authority.",
        default=True, risk_value=False,
    ),
    FeatureFlag(
        "AUREON_LIVE_TRADING", "Live trading", "Hard Boundary",
        "hard_boundary", "handoff", "Saved for a governed cloud runtime handoff; running services remain unchanged.",
        "Request live order execution. The conscience veto, release evidence and runtime gates remain in force.",
    ),
    FeatureFlag(
        "AUREON_ORDER_INTENT_PUBLISH", "Publish order intents", "Hard Boundary",
        "hard_boundary", "handoff", "Saved for a governed cloud runtime handoff; running services remain unchanged.",
        "Request publication of governed order intents to the execution boundary.",
    ),
    FeatureFlag(
        "AUREON_UNIFIED_ORDER_EXECUTOR", "Unified order executor", "Hard Boundary",
        "hard_boundary", "handoff", "Saved for a governed cloud runtime handoff; running services remain unchanged.",
        "Request the unified execution consumer. Credentials, provider health and production authority remain mandatory.",
    ),
    FeatureFlag(
        "AUREON_LOCAL_ACTIONS_ARMED", "Local actions armed", "Hard Boundary",
        "hard_boundary", "restart", "The local-action bridge re-reads at boot.",
        "Let grounded local-machine actions execute (else dry-run). Grounding gate stays in force.",
    ),
    FeatureFlag(
        "AUREON_SOUL_ACT", "Soul act", "Hard Boundary",
        "hard_boundary", "restart", "The soul reads it call-time in the daemon; restart to change there.",
        "Let a resolved soul deliberation carry out its move (still through the guarded, gated bridge).",
    ),
    FeatureFlag(
        "AUREON_BILLING_CHARGE_ENABLED", "Billing charge", "Hard Boundary",
        "hard_boundary", "restart", "The billing route re-reads at boot; 403 by default.",
        "Enable the charge-fee route to move money. Off → the route stays 403.",
    ),
    FeatureFlag(
        "AUREON_SOVEREIGN_MODE", "Sovereign mode", "Hard Boundary",
        "hard_boundary", "restart", "The agent core re-reads at boot.",
        "Widen autonomous agent-core execution. Hard authority boundaries stay deterministically blocked.",
    ),
    FeatureFlag(
        "AUREON_ACCEPT_LIVE_RISK", "Accept live risk", "Hard Boundary",
        "hard_boundary", "restart", "The consuming process re-reads at boot.",
        "Acknowledge live-risk operation. A human acknowledgement only — no gate is removed.",
    ),
    FeatureFlag(
        "AUREON_GROUND_LOCAL_ACTIONS", "Ground sovereign actions", "Hard Boundary",
        "hard_boundary", "restart", "The agent core re-reads at boot.",
        "Route the sovereign path through the conscience/Λ(t) grounding gate (safety-increasing).",
    ),
]

# Group display order.
_GROUP_ORDER = [
    "Organism & Connectome",
    "Cognition Routing",
    "Notifications",
    "Hard Boundary",
]

_BY_ID: Dict[str, FeatureFlag] = {f.id: f for f in FLAGS}

# Flags whose consumer is the operator's own cognition engine → a save can hot-rebuild.
LIVE_FLAG_IDS = {f.id for f in FLAGS if f.effect == "live"}


def get_flag(flag_id: str) -> FeatureFlag | None:
    return _BY_ID.get(flag_id)


def is_hard_boundary(flag_id: str) -> bool:
    f = _BY_ID.get(flag_id)
    return bool(f and f.kind == "hard_boundary")


def _env_holds_safe(flag: FeatureFlag) -> bool:
    """True when the runtime environment explicitly keeps a boundary safe.

    Hard boundaries are armed only by a human decision. The risky value can be
    true (live trading) or false (disabling a deployment hold). Safe flags keep
    their normal precedence so launcher/.env defaults do not silently override
    a human decision.
    """
    if flag.kind != "hard_boundary":
        return False
    value = os.environ.get(flag.env_var)
    return value is not None and _env_truthy(value) != flag.risk_value


# ── Encrypted store (mirrors keystore.py) ──────────────────────────────────────
def _fernet():
    from cryptography.fernet import Fernet

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if not KEY_PATH.exists():
        KEY_PATH.write_bytes(Fernet.generate_key())
        try:
            KEY_PATH.chmod(0o600)
        except OSError:  # pragma: no cover - best effort on odd filesystems
            pass
    return Fernet(KEY_PATH.read_bytes())


def load() -> Dict[str, Dict[str, Any]]:
    """Decrypt and return the stored flags, or ``{}`` if missing/unreadable."""
    if not STORE_PATH.exists():
        return {}
    try:
        raw = _fernet().decrypt(STORE_PATH.read_bytes())
        data = json.loads(raw.decode("utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception as exc:  # noqa: BLE001 — a corrupt store must not sink the operator
        logger.warning("feature switchboard store unreadable: %s", type(exc).__name__)
        return {}


def _persist(data: Dict[str, Dict[str, Any]]) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    token = _fernet().encrypt(json.dumps(data).encode("utf-8"))
    STORE_PATH.write_bytes(token)
    try:
        STORE_PATH.chmod(0o600)
    except OSError:  # pragma: no cover
        pass


def save_flag(flag_id: str, enabled: bool) -> Dict[str, Any]:
    """Record a human's on/off decision for a flag and persist. Returns the entry.

    This ONLY records intent + writes the flag's own env var (via apply_to_env).
    It removes no downstream gate and invokes no executor.
    """
    if flag_id not in _BY_ID:
        raise KeyError(f"unknown feature flag: {flag_id}")
    data = load()
    entry = {"enabled": bool(enabled), "decided_at": time.time()}
    data[flag_id] = entry
    _persist(data)
    apply_to_env()
    return entry


def _last_awakened_at() -> float | None:
    """The organism's last boot time (epoch), guarded — the anchor for pending-restart.

    The organism daemon applies the flags (``bootstrap_credentials`` →
    ``apply_to_env``) and then ``awaken()`` stamps ``last_awakened_at``. So a
    decision made after this timestamp has not yet been picked up. Never raises;
    ``None`` when the genome is absent/unreadable (honest no_data).
    """
    try:
        from aureon.core.awakening import read_genome

        ts = read_genome().get("last_awakened_at")
        return float(ts) if isinstance(ts, (int, float)) else None
    except Exception:  # noqa: BLE001 — an unreadable genome is unknown, never a crash
        return None


def _pending_restart(flag: FeatureFlag, source: str, decided_at: float | None) -> bool | None:
    """Has a human decision NOT yet reached the consuming process?

    ``None`` (no_data) when it cannot be known honestly; never a fabricated
    "applied". ``live`` flags are applied in-process immediately, and a flag with
    no stored human decision is nothing the human is waiting on → ``False``.
    """
    if flag.effect in {"live", "handoff"} or source != "store":
        return False
    if decided_at is None:  # legacy entry with no recorded decision time
        return None
    booted = _last_awakened_at()
    if booted is None:  # the organism has never awoken / genome unknown
        return None
    return decided_at > booted


def apply_to_env() -> None:
    """Inject stored flag decisions into ``os.environ`` (``"1"``/``"0"``).

    Only touches ``os.environ`` for flags the human has decided on. Flags with no
    stored decision are left untouched, so ``.env`` / launcher values still win
    where no UI choice was made. Never imports the trading/conscience/runtime
    layer; calls no executor.
    """
    data = load()
    for flag_id, entry in data.items():
        flag = _BY_ID.get(flag_id)
        if flag is None or flag.effect == "handoff":
            continue
        os.environ[flag.env_var] = "1" if bool(entry.get("enabled")) else "0"


def _env_truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in _TRUTHY


def flag_view(flag: FeatureFlag) -> Dict[str, Any]:
    """Honest per-flag view: effective value, where it came from, and its tier.

    Cloud-handoff flags keep the operator's requested value separate from the
    running environment. The request is never painted as effective and is never
    destroyed merely because the supervised runtime remains held safe.
    """
    stored = load().get(flag.id)
    env_present = flag.env_var in os.environ
    env_value = os.environ.get(flag.env_var)
    env_enabled = _env_truthy(env_value) if env_present else None

    # Non-handoff flags historically apply inside this process. Reconcile an
    # unsafe stored choice when the launcher explicitly holds the runtime safe.
    if flag.effect != "handoff" and flag.kind == "hard_boundary" and stored is not None and _env_holds_safe(flag):
        if bool(stored.get("enabled")) == flag.risk_value:
            data = load()
            data[flag.id] = {"enabled": not flag.risk_value, "decided_at": time.time(),
                             "reconciled_by_env_hold": True}
            _persist(data)
            stored = data[flag.id]

    if flag.effect == "handoff":
        enabled = env_enabled if env_present else flag.default
        source = "env" if env_present else "default"
    elif stored is not None and not (flag.kind == "hard_boundary" and _env_holds_safe(flag)):
        enabled = bool(stored.get("enabled"))
        source = "store"
    elif env_present:
        enabled = env_enabled
        source = "env"
    else:
        enabled = flag.default
        source = "default"

    decided_at = stored.get("decided_at") if isinstance(stored, dict) else None
    if not isinstance(decided_at, (int, float)):
        decided_at = None
    stored_enabled = bool(stored.get("enabled")) if stored is not None else None
    requested_enabled = stored_enabled if stored_enabled is not None else bool(enabled)
    return {
        **flag.to_public_dict(),
        "enabled": enabled,
        "stored": stored_enabled,
        "source": source,
        "armed": bool(flag.kind == "hard_boundary" and enabled == flag.risk_value),
        "requested_armed": bool(flag.kind == "hard_boundary" and requested_enabled == flag.risk_value),
        "decided_at": decided_at,
        "pending_restart": _pending_restart(flag, source, decided_at),
        "pending_handoff": bool(flag.effect == "handoff" and stored_enabled is not None and stored_enabled != enabled),
        "env_hold": _env_holds_safe(flag),
    }


def grouped_view() -> List[Dict[str, Any]]:
    """All flags grouped for the UI, in display order."""
    groups: List[Dict[str, Any]] = []
    for label in _GROUP_ORDER:
        flags = [flag_view(f) for f in FLAGS if f.group == label]
        if flags:
            groups.append({"label": label, "flags": flags})
    return groups


def summary() -> Dict[str, Any]:
    """The switchboard's safety posture at a glance — honest counts only.

    ``armed`` counts hard boundaries currently at their risky value. Requested
    state and cloud handoff counts remain separate from effective runtime state.
    ``pending_restart`` counts decisions not yet picked up by their consuming
    process. Cheap and read-only — suitable for the composed vitals.
    """
    views = [flag_view(f) for f in FLAGS]
    return {
        "total": len(views),
        "enabled": sum(1 for v in views if v["enabled"]),
        "requested_enabled": sum(1 for v in views if (v["stored"] if v["stored"] is not None else v["enabled"])),
        "armed": sum(1 for v in views if v["armed"]),
        "requested_armed": sum(1 for v in views if v["requested_armed"]),
        "pending_restart": sum(1 for v in views if v["pending_restart"] is True),
        "pending_handoff": sum(1 for v in views if v["pending_handoff"]),
        "hard_boundary_total": sum(1 for f in FLAGS if f.kind == "hard_boundary"),
    }


__all__ = [
    "FeatureFlag",
    "FLAGS",
    "LIVE_FLAG_IDS",
    "get_flag",
    "is_hard_boundary",
    "load",
    "save_flag",
    "apply_to_env",
    "flag_view",
    "grouped_view",
    "summary",
    "STORE_PATH",
    "KEY_PATH",
]
