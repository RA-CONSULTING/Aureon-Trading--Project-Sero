#!/usr/bin/env python3
"""
🌍 SCHUMANN DAEMON LAUNCHER
═══════════════════════════════════════════════════════════════════════

Starts/stops the calibrated Schumann-Auris integration as a background daemon.
"""

import subprocess
import sys
import os
import signal
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

PID_FILE = WORKSPACE / "schumann_daemon.pid"
LOG_FILE = WORKSPACE / "schumann_daemon.log"
TARGET_SCRIPT = WORKSPACE / "schumann_auris_integration.py"

def pid_alive(pid: int) -> bool:
    """Cross-platform liveness check.

    WARNING: os.kill(pid, 0) TERMINATES the process on Windows —
    never use signal 0 there.
    """
    if os.name == 'nt':
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
        os.kill(pid, 0)
        return True
    except OSError:
        return False

def start():
    """Start the Schumann daemon in background"""
    if not TARGET_SCRIPT.exists():
        print(f"❌ Cannot start: {TARGET_SCRIPT.name} not found in workspace (dead reference).")
        print("   The Schumann-Auris integration module does not exist.")
        return

    if PID_FILE.exists():
        try:
            with open(PID_FILE, encoding='utf-8') as f:
                old_pid = int(f.read().strip())
            if pid_alive(old_pid):
                print(f"🛑 Schumann daemon already running (PID {old_pid})")
                print("   Run 'python schumann_daemon_launcher.py stop' first to restart")
                return
            PID_FILE.unlink()
        except (OSError, ValueError):
            PID_FILE.unlink()
    
    print("🌍 Starting Schumann daemon...")
    
    # Start in background
    kwargs = {}
    if os.name != 'nt':
        kwargs['start_new_session'] = True
    else:
        kwargs['creationflags'] = subprocess.CREATE_NEW_PROCESS_GROUP
    proc = subprocess.Popen(
        [sys.executable, str(TARGET_SCRIPT), "--interval", "300"],
        stdout=open(LOG_FILE, "a", encoding='utf-8', errors='replace'),
        stderr=subprocess.STDOUT,
        cwd=str(WORKSPACE),
        **kwargs,
    )
    
    with open(PID_FILE, "w", encoding='utf-8') as f:
        f.write(str(proc.pid))
    
    print(f"✅ Schumann daemon started (PID {proc.pid})")
    print(f"   Log: {LOG_FILE}")
    print(f"   Interval: 300s (5 minutes)")

def stop():
    """Stop the Schumann daemon"""
    if not PID_FILE.exists():
        print("❌ Schumann daemon not running")
        return
    
    try:
        with open(PID_FILE, encoding='utf-8') as f:
            pid = int(f.read().strip())
        os.kill(pid, signal.SIGTERM)
        PID_FILE.unlink()
        print(f"🛑 Schumann daemon stopped (PID {pid})")
    except (OSError, ValueError) as e:
        print(f"⚠️ Error stopping daemon: {e}")
        if PID_FILE.exists():
            PID_FILE.unlink()

def status():
    """Show daemon status"""
    if PID_FILE.exists():
        try:
            with open(PID_FILE, encoding='utf-8') as f:
                pid = int(f.read().strip())
            if pid_alive(pid):
                print(f"🌍 Schumann daemon RUNNING (PID {pid})")
            else:
                print("❌ Schumann daemon PID file exists but process dead")
                PID_FILE.unlink()
        except (OSError, ValueError):
            print("❌ Schumann daemon PID file unreadable")
    else:
        print("❌ Schumann daemon NOT running")
    
    if not TARGET_SCRIPT.exists():
        print(f"⚠️ Note: {TARGET_SCRIPT.name} not found — 'start' will refuse to launch.")
    
    # Show latest calibrated reading
    try:
        import json
        from schumann_calibrator import SchumannCalibrator
        calibrator = SchumannCalibrator()
        reading = calibrator.get_latest()
        if reading:
            print(f"\n📡 Latest Calibrated Schumann:")
            print(f"   Time: {reading.get('timestamp', 'N/A')}")
            print(f"   Freq: {reading.get('fundamental_hz', 'N/A'):.4f} Hz")
            print(f"   Amp:  {reading.get('amplitude', 'N/A'):.3f}")
            print(f"   Q:    {reading.get('quality', 'N/A'):.3f}")
            print(f"   Dist: {reading.get('disturbance', 'N/A'):.3f}")
            print(f"   Conf: {reading.get('confidence', 'N/A'):.2f}")
            print(f"   Src:  {reading.get('source_count', 0)}/5")
            print(f"   Src:  {', '.join(reading.get('active_sources', []))}")
    except ImportError:
        print("\n⚠️ schumann_calibrator module not available.")
    except Exception as e:
        print(f"\n⚠️ Could not read latest data: {e}")

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description="Schumann daemon launcher")
    parser.add_argument('command', choices=['start', 'stop', 'status', 'restart'])
    args = parser.parse_args()
    
    if args.command == 'start':
        start()
    elif args.command == 'stop':
        stop()
    elif args.command == 'status':
        status()
    elif args.command == 'restart':
        stop()
        start()
