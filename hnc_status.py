#!/usr/bin/env python3
"""Quick status check for HNC daemon"""
import sys, os, json
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent))
from aureon_fusion.paths import WORKSPACE, HNC_LOGS
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PID_FILE = WORKSPACE / "hnc_daemon.pid"
LOG_DIR = HNC_LOGS

def _pid_running(pid: int) -> bool:
    """Check if a PID is alive, portable across Windows and POSIX."""
    if sys.platform == "win32":
        import ctypes
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return False
        try:
            exit_code = ctypes.c_ulong()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                return False
            return exit_code.value == 259  # STILL_ACTIVE
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True

if PID_FILE.exists():
    pid = PID_FILE.read_text(encoding="utf-8").strip()
    # Check if process is actually running
    try:
        if _pid_running(int(pid)):
            print(f"🟢 HNC Daemon is RUNNING (PID {pid})")
        else:
            print(f"🔴 HNC Daemon is NOT RUNNING (stale PID {pid})")
            PID_FILE.unlink()
    except (ValueError, OSError):
        print(f"🔴 HNC Daemon is NOT RUNNING (invalid PID file)")
        try:
            PID_FILE.unlink()
        except OSError:
            pass
else:
    print("🔴 HNC Daemon is NOT RUNNING")

# Show today's log
import glob
logs = sorted(LOG_DIR.glob('hnc_daemon_*.jsonl'))
if logs:
    latest = logs[-1]
    lines = latest.read_text(encoding="utf-8").strip().split('\n')
    if lines:
        last = json.loads(lines[-1])
        print(f"📊 Latest from {latest.name}:")
        if 'error' in last:
            print(f"   ⚠️  Error: {last['error']}")
        else:
            m = last['measurement']
            a = last['amplified']
            s = last['singing']
            print(f"   Λ: {m['lambda']:.4f} → {a['lambda']:.4f}")
            print(f"   Singing: {'🎵 YES' if s else '🔇 NO'}")
            print(f"   Cycle: {last['cycle']}")
            if 'daemon_stats' in last:
                ds = last['daemon_stats']
                print(f"   Total: {ds['total_singing']}/{ds['total_cycles']} ({ds['singing_ratio']:.1%})")
                print(f"   Uptime: {ds['uptime_seconds']:.0f}s")
