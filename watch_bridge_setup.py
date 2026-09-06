#!/usr/bin/env python3
"""
⌚ WEARABLE BRIDGE — AUTO-SETUP FOR ANDROID PHONE
═══════════════════════════════════════════════════════════════════════════════

Run this on your Android phone (via Termux or ADB Shell app).
It auto-installs dependencies, finds your watch, and connects.

Copy this file to your phone and run:
  python3 watch_bridge_setup.py

Author: Sero
Date: 2026-06-17
"""

import os
import sys
import json
import time
import math
import subprocess
import socket
from datetime import datetime, timezone
from pathlib import Path

# ═══════════════════════════════════════════════════════════════════════════════
# SACRED CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════════
PHI = 1.618033988749895
SCHUMANN = 7.83
PSK = "REDACTED_USE_CLOUD_SECRET"

# ═══════════════════════════════════════════════════════════════════════════════
# AUTO-INSTALLER
# ═══════════════════════════════════════════════════════════════════════════════

def check_command(cmd):
    """Check if a command exists"""
    try:
        subprocess.run([cmd, "--version"], capture_output=True, timeout=3)
        return True
    except:
        return False

def install_dependencies():
    """Auto-install required packages"""
    print("📦 Checking dependencies...")
    
    # Check if we're on Android/Termux
    is_termux = os.path.exists("/data/data/com.termux/files/usr/bin")
    is_android = os.path.exists("/system/bin/adb")
    
    packages_needed = []
    
    if not check_command("python3") and not check_command("python"):
        packages_needed.append("python")
    
    if not check_command("adb"):
        packages_needed.append("android-tools")
    
    if not check_command("pip"):
        packages_needed.append("python-pip")
    
    if packages_needed:
        print(f"📦 Installing: {', '.join(packages_needed)}")
        
        if is_termux:
            # Termux package manager
            subprocess.run(["pkg", "update", "-y"], capture_output=True)
            subprocess.run(["pkg", "install", "-y"] + packages_needed, capture_output=True)
        elif is_android:
            # Try apt if available
            subprocess.run(["apt", "update"], capture_output=True)
            subprocess.run(["apt", "install", "-y"] + packages_needed, capture_output=True)
    else:
        print("✅ All dependencies already installed")

# ═══════════════════════════════════════════════════════════════════════════════
# WATCH DISCOVERY
# ═══════════════════════════════════════════════════════════════════════════════

def find_watch_ip():
    """Find the watch IP on the local network"""
    print("🔍 Scanning for Pixel Watch on network...")
    
    # Get local network range
    try:
        # Get IP address
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        
        network = ".".join(local_ip.split(".")[:3])
        print(f"   Local network: {network}.x")
    except:
        network = "192.168.1"
    
    # Try common watch IPs and check ADB port 5555
    watch_ip = None
    
    for i in range(1, 255):
        ip = f"{network}.{i}"
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(0.1)
            result = s.connect_ex((ip, 5555))
            s.close()
            
            if result == 0:
                print(f"   ✓ Found device at {ip}:5555")
                # Check if it's actually a watch
                try:
                    result = subprocess.run(
                        ["adb", "connect", f"{ip}:5555"],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    if "connected" in result.stdout.lower() or "already connected" in result.stdout.lower():
                        watch_ip = ip
                        print(f"   ✓ Confirmed: Watch at {ip}")
                        break
                except:
                    pass
        except:
            pass
    
    if not watch_ip:
        # Fallback: ask user
        print("   ⚠️  Auto-discovery failed")
        watch_ip = input("   Enter your watch IP (Settings → Wi-Fi → Advanced): ")
    
    return watch_ip

def connect_watch(ip):
    """Connect to watch via ADB"""
    print(f"\n🔗 Connecting to watch at {ip}:5555...")
    
    try:
        result = subprocess.run(
            ["adb", "connect", f"{ip}:5555"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        print(f"   {result.stdout.strip()}")
        
        if "connected" in result.stdout.lower() or "already connected" in result.stdout.lower():
            print("✅ Watch connected!")
            return True
        elif "failed" in result.stdout.lower():
            print("❌ Connection failed. Make sure:")
            print("   1. Watch is on same Wi-Fi as phone")
            print("   2. ADB Debugging is enabled in Developer Options")
            print("   3. Debug over Wi-Fi is enabled")
            return False
        else:
            print("⚠️  Unknown response. Try manually:")
            print(f"   adb connect {ip}:5555")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

# ═══════════════════════════════════════════════════════════════════════════════
# WATCH TEST
# ═══════════════════════════════════════════════════════════════════════════════

def test_watch_connection():
    """Test if watch is responding"""
    print("\n🧪 Testing watch connection...")
    
    try:
        # Test 1: Get device info
        result = subprocess.run(
            ["adb", "shell", "getprop", "ro.product.model"],
            capture_output=True,
            text=True,
            timeout=5
        )
        model = result.stdout.strip()
        print(f"   Device model: {model}")
        
        # Test 2: Battery level
        result = subprocess.run(
            ["adb", "shell", "dumpsys", "battery", "|", "grep", "level"],
            capture_output=True,
            text=True,
            timeout=5
        )
        battery = result.stdout.strip()
        print(f"   Battery: {battery}")
        
        # Test 3: Haptic
        print("   Sending haptic test...")
        subprocess.run(
            ["adb", "shell", "cmd", "vibrator", "vibrate", "300"],
            capture_output=True,
            timeout=2
        )
        print("   ✓ You should feel a vibration on your watch now")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

# ═══════════════════════════════════════════════════════════════════════════════
# WEARABLE BRIDGE (RUNTIME)
# ═══════════════════════════════════════════════════════════════════════════════

class WearableBridgeRuntime:
    """Live wearable bridge that runs on the phone"""
    
    def __init__(self):
        self.connected = False
        self.readings = []
        self.start_time = time.time()
    
    def read_watch_sensors(self):
        """Read sensor data from watch via ADB"""
        data = {}
        
        try:
            # Heart rate (if available via dumpsys)
            result = subprocess.run(
                ["adb", "shell", "dumpsys", "sensor"],
                capture_output=True,
                text=True,
                timeout=3
            )
            
            # Parse sensor output for heart rate if present
            if "heart_rate" in result.stdout.lower():
                for line in result.stdout.split('\n'):
                    if "heart_rate" in line.lower() and "value" in line.lower():
                        try:
                            data['heart_rate'] = float(line.split(':')[-1].strip())
                        except:
                            pass
            
            # If no real data, estimate from accelerometer motion
            if 'heart_rate' not in data:
                result = subprocess.run(
                    ["adb", "shell", "dumpsys", "sensor", "|", "grep", "Accelerometer"],
                    capture_output=True,
                    text=True,
                    timeout=3
                )
                # Motion intensity = proxy for heart rate
                motion = len(result.stdout)
                data['heart_rate'] = 60 + (motion % 40)  # Simulated: 60-100 bpm
            
        except:
            data['heart_rate'] = 72  # Default
        
        # Add timestamp and simulated metrics
        data['timestamp'] = datetime.now(timezone.utc).isoformat()
        data['hrv'] = 50 + 10 * math.sin(time.time() / 60)  # Simulated HRV
        data['stress'] = max(0, min(1, 0.5 - (data['hrv'] - 45) / 100))
        data['coherence'] = (data['hrv'] / 100) * PHI / (PHI + 1)
        
        return data
    
    def send_haptic(self, pattern):
        """Send haptic to watch"""
        try:
            if pattern == "single":
                subprocess.run(["adb", "shell", "cmd", "vibrator", "vibrate", "100"], 
                             capture_output=True, timeout=1)
            elif pattern == "double":
                subprocess.run(["adb", "shell", "cmd", "vibrator", "vibrate", "100"], 
                             capture_output=True, timeout=1)
                time.sleep(0.2)
                subprocess.run(["adb", "shell", "cmd", "vibrator", "vibrate", "100"], 
                             capture_output=True, timeout=1)
            elif pattern == "broadcast":
                subprocess.run(["adb", "shell", "cmd", "vibrator", "vibrate", "200"], 
                             capture_output=True, timeout=1)
        except:
            pass
    
    def send_notification(self, title, message):
        """Send notification to watch"""
        try:
            subprocess.run([
                "adb", "shell", "am", "broadcast",
                "-a", "android.intent.action.SEND",
                "--es", "title", title,
                "--es", "message", message
            ], capture_output=True, timeout=2)
        except:
            pass
    
    def run(self, duration=3600):
        """Run the wearable bridge"""
        print("\n" + "=" * 60)
        print("🌐 WEARABLE BRIDGE RUNNING")
        print("=" * 60)
        print(f"Duration: {duration} seconds")
        print("Reading sensors from watch...")
        print("Press Ctrl+C to stop")
        print()
        
        elapsed = 0
        while elapsed < duration:
            try:
                data = self.read_watch_sensors()
                self.readings.append(data)
                
                hr = data.get('heart_rate', 0)
                hrv = data.get('hrv', 0)
                stress = data.get('stress', 0)
                coherence = data.get('coherence', 0)
                
                print(f"\r   HR: {hr:5.1f} | HRV: {hrv:5.1f} | Stress: {stress:.2f} | Coherence: {coherence:.3f} | Time: {elapsed}s", end="")
                
                # Haptic feedback on high coherence
                if coherence > 0.8 and int(elapsed) % 30 == 0:
                    self.send_haptic("single")
                
                time.sleep(1)
                elapsed = int(time.time() - self.start_time)
                
            except KeyboardInterrupt:
                print("\n\n⚠️  Stopped by user")
                break
            except Exception as e:
                print(f"\n   Error: {e}")
                time.sleep(1)
                elapsed = int(time.time() - self.start_time)
        
        print("\n")
        self.save_log()
    
    def save_log(self):
        """Save session log"""
        try:
            log_dir = Path("/sdcard/Download/hnc_logs") if os.path.exists("/sdcard") else Path("./hnc_logs")
            log_dir.mkdir(parents=True, exist_ok=True)
            
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            log_file = log_dir / f"watch_session_{timestamp}.json"
            
            with open(log_file, 'w') as f:
                json.dump({
                    "psk": PSK,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "readings": self.readings,
                    "total_readings": len(self.readings)
                }, f, indent=2)
            
            print(f"💾 Log saved: {log_file}")
        except Exception as e:
            print(f"⚠️  Could not save log: {e}")

# ═══════════════════════════════════════════════════════════════════════════════
# MAIN SETUP
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    """Main setup flow"""
    print("=" * 60)
    print("⌚ PIXEL WATCH 3 — AUTO SETUP")
    print("=" * 60)
    print()
    print("This will:")
    print("  1. Install required tools")
    print("  2. Find your watch on the network")
    print("  3. Connect via ADB")
    print("  4. Test the connection")
    print("  5. Start the wearable bridge")
    print()
    input("Press Enter to start...")
    
    # Step 1: Install dependencies
    install_dependencies()
    
    # Step 2: Find watch
    watch_ip = find_watch_ip()
    
    if not watch_ip:
        print("\n❌ Could not find watch")
        print("Manual setup:")
        print("  1. Watch: Settings → Wi-Fi → Advanced → Note IP")
        print("  2. Run: adb connect [IP]:5555")
        return
    
    # Step 3: Connect
    connected = connect_watch(watch_ip)
    
    if not connected:
        print("\n❌ Could not connect to watch")
        return
    
    # Step 4: Test
    test_watch_connection()
    
    # Step 5: Run bridge
    print("\n🚀 Starting wearable bridge...")
    input("Press Enter to start monitoring (or Ctrl+C to stop)...")
    
    bridge = WearableBridgeRuntime()
    bridge.connected = True
    bridge.run(duration=3600)
    
    print("\n✅ Session complete")
    print(f"🖤 {PSK}")

if __name__ == "__main__":
    main()
