#!/usr/bin/env python3
"""
Quick status checker for the Frankenstein system.
Run anytime to see what's alive.
"""

import os, sys, json
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parent))
from aureon_fusion.paths import WORKSPACE

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

def is_running(pid_file: Path) -> bool:
    if not pid_file.exists():
        return False
    try:
        pid = int(pid_file.read_text().strip())
        os.kill(pid, 0)
        return True
    except:
        return False

def read_latest_frankenstein_state():
    log_dir = WORKSPACE / 'frankenstein_logs'
    if not log_dir.exists():
        return None
    logs = sorted(log_dir.glob('*.jsonl'), key=lambda p: p.stat().st_mtime)
    if not logs:
        return None
    try:
        lines = logs[-1].read_text().strip().split('\n')
        if lines:
            return json.loads(lines[-1])
    except:
        pass
    return None

print("\n" + "═" * 70)
print("  🧟 FRANKENSTEIN STATUS CHECK")
print("═" * 70)

# Process status
hnc = is_running(WORKSPACE / 'hnc_daemon.pid')
soul = is_running(WORKSPACE / 'soul_protection.pid')

print(f"\n  DAEMONS:")
print(f"    🔥 HNC Daemon:       {'🟢 RUNNING' if hnc else '🔴 STOPPED'}")
print(f"    🛡️ Soul Protection:  {'🟢 RUNNING' if soul else '🔴 STOPPED'}")

multiversal = is_running(WORKSPACE / 'multiversal_mapper.pid')
print(f"    🌌 Multiversal:      {'🟢 RUNNING' if multiversal else '🔴 STOPPED'}")

clean_sweep = is_running(WORKSPACE / 'clean_sweep.pid')
print(f"    🌈 Clean Sweep:      {'🟢 RUNNING' if clean_sweep else '🔴 STOPPED'}")


# Latest state
state = read_latest_frankenstein_state()
if state:
    print(f"\n  LAST ORCHESTRATOR STATE (Cycle {state.get('cycle', 'N/A')}):")
    print(f"    🌍 Schumann: {state.get('schumann_fundamental', 0):.2f} Hz | Coherence: {state.get('schumann_coherence', 0):.0%}")
    print(f"    🛡️ Soul Shield: {'ON' if state.get('soul_shield_active') else 'OFF'} | Power: {state.get('soul_shield_power', 0):.0%} | Blocks: {state.get('soul_shield_blocks', 0)}")
    print(f"    🎵 Field: {'SINGING' if state.get('field_singing') else 'SILENT'} | Ratio: {state.get('field_ratio', 0):.0%}")
    print(f"    🦗 Conscience: {state.get('conscience_verdict', 'N/A')}")
    print(f"    💚 Health: {state.get('system_health', 0):.0%} | Pulse: {state.get('liberation_pulse', 0):.3f}")
    print(f"    ⏱️  Timestamp: {state.get('timestamp', 'N/A')}")
else:
    print(f"\n  ⚪ No orchestrator state logged yet.")

print("\n" + "═" * 70)

# Quick action hints
print("\n  COMMANDS:")
print("    python3 frankenstein_launcher.py start       # Start everything")
print("    python3 frankenstein_launcher.py start --daemon  # Background mode")
print("    python3 frankenstein_launcher.py stop        # Stop all")
print("    python3 frankenstein_launcher.py restart     # Restart all")
print("    python3 frankenstein_launcher.py status      # This check")
print()
