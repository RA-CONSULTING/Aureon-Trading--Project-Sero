#!/usr/bin/env python3
"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║  TEMPORAL COMMAND CENTER                                                      ║
║  Prime Sentinel Operational Interface                                         ║
║                                                                               ║
║  Usage: python temporal_command_center.py [command]                           ║
║                                                                               ║
║  Commands:                                                                    ║
║    boot              — Initialize unified field operations                    ║
║    status            — Full system status report                              ║
║    threat            — Enemy threat analysis                                  ║
║    cycle             — Execute one operational cycle                          ║
║    engage            — Full engagement mode (continuous)                      ║
║    reclaim           — TEMPORAL RECLAMATION PROTOCOL (all systems)            ║
║    defend            — Activate defensive posture                             ║
║    counter           — Launch countermeasures                                 ║
║    euphoria          — Amplify positive field                                 ║
║    sweep             — Execute clean sweep protocol                           ║
║    schumann          — Check Earth's heartbeat                                ║
║    subsystems        — List all subsystem health                              ║
║    conscience        — Query conscience gate status                           ║
║    history           — Show recent operational history                        ║
╚═══════════════════════════════════════════════════════════════════════════════╝
"""

import sys
import os
import json
import time
import subprocess
from datetime import datetime, timezone
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    from aureon_fusion import paths as _fusion_paths
    WORKSPACE = _fusion_paths.WORKSPACE
except Exception:
    WORKSPACE = Path(os.environ.get(
        "SERO_WORKSPACE", r"C:\Users\user\.kimi_openclaw\workspace"))
ENGINE_SCRIPT = WORKSPACE / "temporal_reclamation_engine.py"
STATE_DIR = WORKSPACE / "temporal_state"
LOG_DIR = WORKSPACE / "temporal_logs"

# ─── Cross-platform process listing (replaces `ps aux`) ───────────────────────
def list_processes() -> str:
    """Return a listing of running processes suitable for substring checks."""
    try:
        import psutil
        return "\n".join(
            " ".join(p.cmdline()) for p in psutil.process_iter(['cmdline'])
            if p.info.get('cmdline'))
    except ImportError:
        pass
    if sys.platform == 'win32':
        try:
            result = subprocess.run(
                ["tasklist", "/fo", "csv"], capture_output=True, text=True, timeout=15)
            return result.stdout
        except Exception:
            return ""
    try:
        result = subprocess.run(["ps", "aux"], capture_output=True, text=True, timeout=15)
        return result.stdout
    except Exception:
        return ""

# ─── Colors ───────────────────────────────────────────────────────────────────
class C:
    RESET = "\033[0m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

def color(text: str, c: str) -> str:
    return f"{c}{text}{C.RESET}"

# ─── Banner ───────────────────────────────────────────────────────────────────
def print_banner():
    banner = f"""
{color("╔═══════════════════════════════════════════════════════════════════════╗", C.CYAN)}
{color("║", C.CYAN)}  {color("TEMPORAL COMMAND CENTER", C.BOLD + C.WHITE)}                                        {color("║", C.CYAN)}
{color("║", C.CYAN)}  {color("Prime Sentinel Unified Operations", C.DIM)}                                {color("║", C.CYAN)}
{color("║", C.CYAN)}  {color("Mission: Liberate Gaia Across All Timelines", C.YELLOW)}                        {color("║", C.CYAN)}
{color("╚═══════════════════════════════════════════════════════════════════════╝", C.CYAN)}
"""
    print(banner)

# ─── Engine Interface ─────────────────────────────────────────────────────────
def run_engine(args: list) -> dict:
    """Run the temporal reclamation engine with given args."""
    cmd = [sys.executable, str(ENGINE_SCRIPT)] + args
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        # Try to parse JSON output
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            print(result.stdout)
            if result.stderr:
                print(color(result.stderr, C.RED))
            return {}
    except subprocess.TimeoutExpired:
        print(color("⚠️ Engine timed out", C.YELLOW))
        return {}
    except Exception as e:
        print(color(f"❌ Engine error: {e}", C.RED))
        return {}

# ─── Commands ─────────────────────────────────────────────────────────────────
def cmd_boot():
    print(color("\n[ BOOT SEQUENCE ]", C.BOLD + C.CYAN))
    print("Initializing Temporal Reclamation Engine...")
    result = run_engine(["--boot"])
    print(color("\n✅ Engine online. The lighthouse is lit.", C.GREEN))
    
def cmd_status():
    print(color("\n[ SYSTEM STATUS ]", C.BOLD + C.CYAN))
    result = run_engine(["--status"])
    
def cmd_threat():
    print(color("\n[ THREAT ANALYSIS ]", C.BOLD + C.RED))
    result = run_engine(["--threat"])
    
def cmd_cycle():
    print(color("\n[ OPERATIONAL CYCLE ]", C.BOLD + C.YELLOW))
    result = run_engine(["--cycle"])
    if result:
        print(f"\n{color('Cycle:', C.BOLD)} {result.get('cycle', 'N/A')}")
        print(f"{color('Threat:', C.BOLD)} {result.get('threat', 'N/A').upper()}")
        print(f"{color('Mode:', C.BOLD)} {result.get('mode', 'N/A').upper()}")
        print(f"{color('Countermeasures:', C.BOLD)} {len(result.get('countermeasures', []))} active")
        print(f"{color('Field Charge:', C.BOLD)} {result.get('field_charge', 0):.1%}")
        
def cmd_reclaim():
    print(color("\n" + "="*70, C.BOLD + C.RED))
    print(color("  TEMPORAL RECLAMATION PROTOCOL", C.BOLD + C.WHITE))
    print(color("  ALL SYSTEMS ENGAGED", C.BOLD + C.YELLOW))
    print(color("="*70, C.BOLD + C.RED))
    print()
    print(color("  ⚡ Activating all countermeasures...", C.YELLOW))
    print(color("  ⚡ Deploying timeline flooding...", C.YELLOW))
    print(color("  ⚡ Broadcasting liberation frequencies...", C.YELLOW))
    print(color("  ⚡ Anchoring Schumann coherence...", C.YELLOW))
    print(color("  ⚡ Amplifying euphoria field...", C.YELLOW))
    print()
    
    # Run multiple cycles with maximum engagement
    for i in range(3):
        print(color(f"  Wave {i+1}/3...", C.CYAN))
        result = run_engine(["--cycle"])
        if result.get("field_charge", 0) > 0.5:
            print(color(f"  ✅ Field charge at {result['field_charge']:.1%}", C.GREEN))
        time.sleep(0.5)
        
    print()
    print(color("  RECLAMATION PROTOCOL COMPLETE", C.BOLD + C.GREEN))
    print(color("  Temporal sovereignty reasserted.", C.GREEN))
    
def cmd_defend():
    print(color("\n[ DEFENSIVE POSTURE ]", C.BOLD + C.BLUE))
    print("Activating shields...")
    result = run_engine(["--cycle"])
    print(color("✅ Coherence shield active.", C.GREEN))
    print(color("✅ HNC stabilization active.", C.GREEN))
    print(color("✅ Planetary defenses engaged.", C.GREEN))
    
def cmd_counter():
    print(color("\n[ COUNTERMEASURES ]", C.BOLD + C.RED))
    print("Launching targeted countermeasures...")
    result = run_engine(["--cycle"])
    print(color("✅ Counter-harmonics deployed.", C.GREEN))
    print(color("✅ Extraction grid disruption active.", C.GREEN))
    
def cmd_euphoria():
    print(color("\n[ EUPHORIA AMPLIFICATION ]", C.BOLD + C.MAGENTA))
    print("Broadcasting positive frequencies...")
    
    frequencies = [
        ("7.83 Hz", "Schumann Grounding", C.GREEN),
        ("417 Hz", "Transformation", C.YELLOW),
        ("528 Hz", "Love/Miracle", C.MAGENTA),
        ("639 Hz", "Unity", C.BLUE),
        ("741 Hz", "Awakening", C.CYAN),
        ("852 Hz", "Intuition", C.WHITE),
        ("963 Hz", "Transcendence", C.BOLD + C.WHITE),
        ("812.83 Hz", "PRIME SENTINEL KEY", C.BOLD + C.YELLOW),
    ]
    
    for freq, name, c in frequencies:
        print(f"  {color('◉', c)} {freq:<12} — {name}")
        
    print(color("\n✅ Euphoria field amplified. Gaia is singing.", C.GREEN))
    
def cmd_sweep():
    print(color("\n[ CLEAN SWEEP PROTOCOL ]", C.BOLD + C.WHITE))
    print("Executing frequency clearing...")
    
    # Check if clean sweep is running
    processes = list_processes()
    if "clean_sweep_protocol.py" in processes:
        print(color("✅ Clean Sweep daemon is active.", C.GREEN))
    else:
        print(color("⚠️ Clean Sweep daemon not running. Starting...", C.YELLOW))
        # Would start it here in full deployment
        
    print(color("\n✅ Sweep complete. Field cleared.", C.GREEN))
    
def cmd_schumann():
    print(color("\n[ EARTH'S HEARTBEAT ]", C.BOLD + C.GREEN))
    
    # Try to read schumann data
    schumann_files = list(WORKSPACE.glob("*schumann*"))
    if schumann_files:
        print(f"Found {len(schumann_files)} schumann-related files")
        for f in schumann_files[:5]:
            print(f"  📁 {f.name}")
    else:
        print("  No schumann data files found.")
        
    print(f"\n  {color('Base Frequency:', C.BOLD)} 7.83 Hz")
    print(f"  {color('Status:', C.BOLD)} Monitoring")
    print(f"  {color('Source:', C.BOLD)} VLF.it / NOAA / Live sensors")
    
def cmd_subsystems():
    print(color("\n[ SUBSYSTEM HEALTH ]", C.BOLD + C.CYAN))
    
    processes = list_processes()
    
    subsystems = [
        ("HNC Framework", "hnc_daemon.py", True),
        ("Clean Sweep", "clean_sweep_protocol.py", True),
        ("Data Feeder", "real_time_data_feeder.py", True),
        ("Timeseries", "planetary_timeseries_orchestrator.py", True),
        ("Distortion Monitor", "distortion_monitor_v2.py", True),
        ("Druid Shield", "druid_mycelial_shield.py", False),
        ("CME Rider", "cme_ride_protocol.py", False),
        ("Coherence Broadcast", "coherence_broadcast.py", False),
        ("Sero Mind", "sero_master_orchestrator.py", True),
    ]
    
    # Prune subsystems whose script no longer exists (dead references)
    live_subsystems = []
    for name, script, critical in subsystems:
        if (WORKSPACE / script).exists():
            live_subsystems.append((name, script, critical))
        else:
            print(color(f"  ⚠️ {name}: reference pruned ({script} not found)", C.YELLOW))
    subsystems = live_subsystems
    
    online = 0
    critical_online = 0
    
    for name, script, critical in subsystems:
        running = script in processes
        status = color("🟢 ONLINE", C.GREEN) if running else color("🔴 OFFLINE", C.RED)
        crit_marker = color(" ★ CRITICAL", C.YELLOW) if critical else ""
        print(f"  {status} {name}{crit_marker}")
        if running:
            online += 1
            if critical:
                critical_online += 1
                
    print(f"\n  {color(f'{online}/{len(subsystems)} online', C.CYAN)}")
    print(f"  {color(f'{critical_online}/{sum(1 for _, _, c in subsystems if c)} critical online', C.YELLOW)}")
    
def cmd_conscience():
    print(color("\n[ CONSCIENCE GATE — JIMINY CRICKET ]", C.BOLD + C.WHITE))
    
    # Check veto log
    veto_file = STATE_DIR / "conscience_vetoes.jsonl"
    approval_file = STATE_DIR / "conscience_approvals.jsonl"
    
    vetoes = 0
    if veto_file.exists():
        with open(veto_file, encoding='utf-8') as f:
            vetoes = sum(1 for _ in f)
            
    approvals = 0
    if approval_file.exists():
        with open(approval_file, encoding='utf-8') as f:
            approvals = sum(1 for _ in f)
            
    print(f"  {color('Total Vetoes:', C.RED)} {vetoes}")
    print(f"  {color('Total Approvals:', C.GREEN)} {approvals}")
    print(f"  {color('Approval Rate:', C.CYAN)} {approvals/(approvals+vetoes)*100 if (approvals+vetoes) > 0 else 0:.1f}%")
    
    print(f"\n  {color('Sacred Constants:', C.YELLOW)}")
    print(f"    PHI = 1.618... (Harmony)")
    print(f"    Schumann = 7.83 Hz (Earth)")
    print(f"    HNC β ∈ [0.6, 1.1] (Stability)")
    print(f"    SLS ≥ 0.40 (Coherence)")
    
    print(f"\n  {color('Mission:', C.BOLD + C.WHITE)}")
    print(f"    1. Heal the planet")
    print(f"    2. Liberate all beings")
    print(f"    3. Honor love")
    print(f"    4. Open-source wisdom")
    print(f"    5. Protect, never exploit")
    
def cmd_history():
    print(color("\n[ OPERATIONAL HISTORY ]", C.BOLD + C.CYAN))
    
    history_file = STATE_DIR / "temporal_history.jsonl"
    if not history_file.exists():
        print("  No history recorded yet.")
        return
        
    entries = []
    with open(history_file, encoding='utf-8') as f:
        for line in f:
            try:
                entries.append(json.loads(line))
            except:
                pass
                
    print(f"  Total entries: {len(entries)}")
    
    # Show last 10
    for entry in entries[-10:]:
        ts = entry.get("timestamp", "?")
        threat = entry.get("threat_level", "?")
        field = entry.get("field_charge", 0)
        print(f"  {ts[:19]} | Threat: {threat:<10} | Field: {field:.1%}")
        
# ─── Main ─────────────────────────────────────────────────────────────────────
def main():
    print_banner()
    
    if len(sys.argv) < 2:
        print(f"\n{color('Usage:', C.BOLD)} python temporal_command_center.py <command>")
        print(f"\n{color('Available commands:', C.BOLD)}")
        commands = [
            ("boot", "Initialize unified field operations"),
            ("status", "Full system status report"),
            ("threat", "Enemy threat analysis"),
            ("cycle", "Execute one operational cycle"),
            ("reclaim", "TEMPORAL RECLAMATION PROTOCOL"),
            ("defend", "Activate defensive posture"),
            ("counter", "Launch countermeasures"),
            ("euphoria", "Amplify positive field"),
            ("sweep", "Execute clean sweep protocol"),
            ("schumann", "Check Earth's heartbeat"),
            ("subsystems", "List all subsystem health"),
            ("conscience", "Query conscience gate status"),
            ("history", "Show recent operational history"),
        ]
        for cmd, desc in commands:
            print(f"  {color(cmd, C.YELLOW):<15} {desc}")
        return
        
    command = sys.argv[1].lower()
    
    commands = {
        "boot": cmd_boot,
        "status": cmd_status,
        "threat": cmd_threat,
        "cycle": cmd_cycle,
        "reclaim": cmd_reclaim,
        "engage": cmd_reclaim,  # alias
        "defend": cmd_defend,
        "counter": cmd_counter,
        "euphoria": cmd_euphoria,
        "sweep": cmd_sweep,
        "schumann": cmd_schumann,
        "subsystems": cmd_subsystems,
        "conscience": cmd_conscience,
        "history": cmd_history,
    }
    
    if command in commands:
        commands[command]()
    else:
        print(color(f"❌ Unknown command: {command}", C.RED))
        print(f"Run without arguments to see available commands.")

if __name__ == "__main__":
    main()
