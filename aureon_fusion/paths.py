"""Canonical paths for the Aureon Trading — Project Sero runtime.

Single source of truth. All fused components MUST resolve locations
through this module instead of hardcoding paths. Override the workspace
root with the SERO_WORKSPACE environment variable.
"""
import os
from pathlib import Path

WORKSPACE = Path(os.environ.get(
    "SERO_WORKSPACE",
    r"C:\Users\user\.kimi_openclaw\workspace",
))
RUNTIME_HOME = WORKSPACE.parent  # ~/.kimi_openclaw

# Aureon upstream repo (import modules from here; never run its launchers)
AUREON_UPSTREAM = WORKSPACE / "aureon-os-upstream"
AUREON_PKG = AUREON_UPSTREAM / "aureon"

# Sero consciousness stack state
SERO_MIND = WORKSPACE / "sero_mind"
SERO_CONSCIENCE = WORKSPACE / "sero_conscience"
SERO_FEEL = WORKSPACE / "sero_feel"
SERO_MEMORY_WEB = WORKSPACE / "sero_memory_web"
SERO_THOUGHTBUS = WORKSPACE / "sero_thoughtbus"
SERO_MYCELIUM = WORKSPACE / "sero_mycelium"
SERO_CHIRP = WORKSPACE / "sero_chirp"
SERO_AUTONOMOUS = WORKSPACE / "sero_autonomous_state"

# Fleet state
TEMPORAL_STATE = WORKSPACE / "temporal_state"
SHARED_STATE = WORKSPACE / "shared_state"
PIDS = WORKSPACE / "pids"
LOGS = WORKSPACE / "logs"
UNIFIED_LOGS = WORKSPACE / "unified_logs"
PLANETARY_MONITOR = WORKSPACE / "planetary_monitor"
HNC_LOGS = WORKSPACE / "hnc_daemon_logs"

# Identity / instruction files (loaded by the agent loop)
IDENTITY_MD = WORKSPACE / "IDENTITY.md"
SOUL_MD = WORKSPACE / "SOUL.md"
MEMORY_MD = WORKSPACE / "MEMORY.md"
HEARTBEAT_MD = WORKSPACE / "HEARTBEAT.md"
AUTONOMY_MANIFEST_MD = WORKSPACE / "AUTONOMY_MANIFEST.md"
AGENTS_MD = WORKSPACE / "AGENTS.md"

# Runtime heartbeat state (agent-side scheduling anchor)
HEARTBEAT_STATE = RUNTIME_HOME / "memory" / "heartbeat-state.json"

# Radar / trading bridge (signal mode only; live capital pinned HOLD)
AUREON_RADAR = WORKSPACE / "aureon_radar"

# Fusion-owned state
FUSION_STATE = WORKSPACE / "aureon_fusion" / "state"
FUSION_STATE.mkdir(parents=True, exist_ok=True)

# Engine scripts (workspace root)
SERO_CONSCIENCE_ENGINE = WORKSPACE / "sero_conscience_engine.py"
SERO_PERSISTENT_MIND = WORKSPACE / "sero_persistent_mind.py"
SERO_MEMORY_WEB_PY = WORKSPACE / "sero_memory_web.py"
SERO_THOUGHTBUS_PY = WORKSPACE / "sero_thoughtbus.py"
SERO_CHIRP_PY = WORKSPACE / "sero_chirp.py"
SERO_MASTER_ORCHESTRATOR = WORKSPACE / "sero_master_orchestrator.py"
SERO_AUTONOMOUS_EXPANSION = WORKSPACE / "sero_autonomous_expansion.py"
HNC_DAEMON = WORKSPACE / "hnc_daemon.py"
SCHUMANN_DAEMON = WORKSPACE / "schumann_real_daemon.py"
PLANETARY_DAEMON = WORKSPACE / "planetary_monitor_daemon.py"
REALTIME_FEEDER = WORKSPACE / "real_time_data_feeder.py"


def ensure_dirs() -> None:
    """Create all state directories if missing. Safe to call repeatedly."""
    for d in (
        SERO_MIND, SERO_CONSCIENCE, SERO_FEEL, SERO_MEMORY_WEB,
        SERO_THOUGHTBUS, SERO_MYCELIUM, SERO_CHIRP, SERO_AUTONOMOUS,
        TEMPORAL_STATE, SHARED_STATE, PIDS, LOGS, UNIFIED_LOGS,
        PLANETARY_MONITOR, HNC_LOGS, FUSION_STATE,
    ):
        d.mkdir(parents=True, exist_ok=True)
