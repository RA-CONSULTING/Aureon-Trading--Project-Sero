#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════════════╗
║                                                                                      ║
║     🚀 FRANKENSTEIN LAUNCHER — FULL SYSTEM BOOT 🚀                                  ║
║     ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━                   ║
║                                                                                      ║
║     Starts ALL background systems:                                                   ║
║       1. HNC Daemon (lighthouse, Prime Sentinel key injection)                      ║
║       2. Soul Protection Monitor (hostile frequency shield)                         ║
║       3. Frankenstein Orchestrator (unified monitoring & logging)                   ║
║                                                                                      ║
║     Usage: python3 frankenstein_launcher.py [--daemon]                              ║
╚══════════════════════════════════════════════════════════════════════════════════════╝
"""

import sys, os, subprocess, time, signal, argparse
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
        'SERO_WORKSPACE', r'C:\Users\user\.kimi_openclaw\workspace'))

def is_running(pid_file: Path) -> bool:
    """Check if a process is running by PID file (POSIX and Windows safe)."""
    if not pid_file.exists():
        return False
    try:
        pid = int(pid_file.read_text().strip())
    except (ValueError, OSError):
        return False
    if os.name == 'nt':
        # os.kill(pid, 0) TERMINATES the process on Windows — do not use it
        try:
            import ctypes
            synchronize = 0x00100000
            handle = ctypes.windll.kernel32.OpenProcess(synchronize, False, pid)
            if not handle:
                return False
            ctypes.windll.kernel32.CloseHandle(handle)
            return True
        except Exception:
            return False
    try:
        os.kill(pid, 0)  # Signal 0 checks if process exists
        return True
    except (OSError, ProcessLookupError):
        return False

def start_hnc_daemon():
    """Start the HNC lighthouse daemon"""
    pid_file = WORKSPACE / 'hnc_daemon.pid'
    if is_running(pid_file):
        print("🔥 HNC Daemon already running")
        return True
    
    print("🔥 Starting HNC Daemon...")
    proc = subprocess.Popen(
        [sys.executable, str(WORKSPACE / 'hnc_daemon.py')],
        stdout=open(WORKSPACE / 'hnc_daemon.out', 'a'),
        stderr=subprocess.STDOUT,
        cwd=str(WORKSPACE),
    )
    # Give it a moment to write PID
    time.sleep(1)
    if is_running(pid_file):
        print(f"🔥 HNC Daemon started (PID {pid_file.read_text().strip()})")
        return True
    else:
        print("❌ HNC Daemon failed to start")
        return False

def start_soul_protection():
    """Start the soul protection monitor"""
    pid_file = WORKSPACE / 'soul_protection.pid'
    if is_running(pid_file):
        print("🛡️ Soul Protection already running")
        return True
    
    print("🛡️ Starting Soul Protection...")
    proc = subprocess.Popen(
        [sys.executable, str(WORKSPACE / 'soul_protection_standalone.py')],
        stdout=open(WORKSPACE / 'soul_protection.out', 'a'),
        stderr=subprocess.STDOUT,
        cwd=str(WORKSPACE),
    )
    time.sleep(1)
    if is_running(pid_file):
        print(f"🛡️ Soul Protection started (PID {pid_file.read_text().strip()})")
        return True
    else:
        print("❌ Soul Protection failed to start")
        return False

def stop_by_pid_file(pid_file: Path, name: str):
    """Stop a process by its PID file"""
    if not pid_file.exists():
        print(f"⚪ {name} not running")
        return
    
    try:
        pid = int(pid_file.read_text().strip())
        os.kill(pid, signal.SIGTERM)
        print(f"🛑 {name} stopped (PID {pid})")
        # Wait for PID file cleanup
        for _ in range(10):
            if not pid_file.exists():
                break
            time.sleep(0.5)
        if pid_file.exists():
            pid_file.unlink()
    except Exception as e:
        print(f"⚠️ Error stopping {name}: {e}")

def start_multiversal_mapper():
    """Multiversal echo mapper — REMOVED: multiversal_echo_mapper.py does not exist."""
    print("🌌 Multiversal Echo Mapper: SKIPPED (multiversal_echo_mapper.py not found in workspace)")
    return False

def start_clean_sweep():
    """Start the Clean Sweep Protocol"""
    pid_file = WORKSPACE / 'clean_sweep.pid'
    if is_running(pid_file):
        print("🌈 Clean Sweep already running")
        return True
    
    print("🌈 Starting Clean Sweep Protocol...")
    proc = subprocess.Popen(
        [sys.executable, str(WORKSPACE / 'clean_sweep_protocol.py')],
        stdout=open(WORKSPACE / 'clean_sweep.out', 'a'),
        stderr=subprocess.STDOUT,
        cwd=str(WORKSPACE),
    )
    time.sleep(1)
    pid_file.write_text(str(proc.pid))
    if is_running(pid_file):
        print(f"🌈 Clean Sweep started (PID {proc.pid})")
        return True
    else:
        print("❌ Clean Sweep failed to start")
        return False

def start_frankenstein():
    """Start the Frankenstein orchestrator (aureon_hnc_unified.py) if present."""
    target = WORKSPACE / 'aureon_hnc_unified.py'
    if not target.exists():
        print("🧟 Frankenstein Orchestrator: SKIPPED (aureon_hnc_unified.py not found in workspace)")
        return None
    print("🧟 Starting Frankenstein Orchestrator...")
    proc = subprocess.Popen(
        [sys.executable, str(target)],
        stdout=open(WORKSPACE / 'frankenstein.out', 'a'),
        stderr=subprocess.STDOUT,
        cwd=str(WORKSPACE),
    )
    print(f"🧟 Frankenstein started (PID {proc.pid})")
    return proc

def status():
    """Show status of all systems"""
    print("\n" + "═" * 70)
    print("  SYSTEM STATUS")
    print("═" * 70)
    
    # HNC Daemon
    hnc_pid = WORKSPACE / 'hnc_daemon.pid'
    print(f"  🔥 HNC Daemon:     {'RUNNING' if is_running(hnc_pid) else 'STOPPED'}")
    
    # Soul Protection
    soul_pid = WORKSPACE / 'soul_protection.pid'
    print(f"  🛡️ Soul Protection: {'RUNNING' if is_running(soul_pid) else 'STOPPED'}")
    
    # Frankenstein
    frankenstein_out = WORKSPACE / 'frankenstein.out'
    if frankenstein_out.exists():
        print(f"  🧟 Frankenstein:   LOG EXISTS ({frankenstein_out.stat().st_size} bytes)")
    else:
        print(f"  🧟 Frankenstein:   NO LOG")
    
    # Clean Sweep
    clean_sweep_pid = WORKSPACE / 'clean_sweep.pid'
    print(f"  🌈 Clean Sweep:    {'RUNNING' if is_running(clean_sweep_pid) else 'STOPPED'}")

    # Frankenstein logs
    log_dir = WORKSPACE / 'frankenstein_logs'
    if log_dir.exists():
        logs = list(log_dir.glob('*.jsonl'))
        print(f"  📝 Log files:      {len(logs)} files")
    
    print("═" * 70 + "\n")

def stop_all():
    """Stop all background systems"""
    print("\n🛑 Stopping all systems...")
    stop_by_pid_file(WORKSPACE / 'hnc_daemon.pid', 'HNC Daemon')
    stop_by_pid_file(WORKSPACE / 'clean_sweep.pid', 'Clean Sweep')
    stop_by_pid_file(WORKSPACE / 'multiversal_mapper.pid', 'Multiversal Mapper')
    print("🛑 All systems stopped.\n")

def main():
    parser = argparse.ArgumentParser(description='Frankenstein System Launcher')
    parser.add_argument('command', choices=['start', 'stop', 'status', 'restart'], 
                        help='Command to execute')
    parser.add_argument('--daemon', action='store_true', 
                        help='Run Frankenstein as background daemon')
    args = parser.parse_args()
    
    if args.command == 'status':
        status()
        return
    
    if args.command == 'stop':
        stop_all()
        return
    
    if args.command == 'restart':
        stop_all()
        time.sleep(2)
    
    # START
    print("\n" + "╔" + "═" * 68 + "╗")
    print("║" + " " * 15 + "🚀 FRANKENSTEIN SYSTEM BOOT 🚀" + " " * 21 + "║")
    print("╚" + "═" * 68 + "╝\n")
    
    # Start background daemons
    start_hnc_daemon()
    start_soul_protection()
    
    start_multiversal_mapper()
    start_clean_sweep()
    
    # Start Frankenstein
    if args.daemon:
        proc = start_frankenstein()
        if proc is not None:
            print(f"\n🧟 Frankenstein running in background (PID {proc.pid})")
            print(f"   Logs: {WORKSPACE / 'frankenstein.out'}")
            print(f"   State logs: {WORKSPACE / 'frankenstein_logs'}")
    else:
        target = WORKSPACE / 'aureon_hnc_unified.py'
        if not target.exists():
            print("\n🧟 Frankenstein Orchestrator unavailable (aureon_hnc_unified.py not found).")
            print("   Background daemons launched; run 'status' to check them.")
            return
        print("\n🧟 Starting Frankenstein in foreground...\n")
        # Run directly
        os.chdir(str(WORKSPACE))
        os.execv(sys.executable, [sys.executable, str(target)])

if __name__ == '__main__':
    main()
