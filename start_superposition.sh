#!/bin/bash
# Start HNC Daemon in SUPERPOSITION MODE — 1000x power output

echo "🌟 PRIME SENTINEL COMMAND: ACTIVATE SUPERPOSITION"
echo "⚡ Power output: 1000x"
echo ""

# Kill old daemon
OLD_PID=$(cat /root/.openclaw/workspace/hnc_daemon.pid 2>/dev/null)
if [ -n "$OLD_PID" ]; then
    echo "🛑 Stopping old daemon (PID $OLD_PID)..."
    kill $OLD_PID 2>/dev/null
    sleep 2
fi

# Kill any remaining hnc_daemon processes
pkill -f "hnc_daemon.py" 2>/dev/null
sleep 1

# Start superposition daemon
cd /root/.openclaw/workspace
nohup python3 hnc_daemon_superposition.py > /root/.openclaw/workspace/hnc_superposition.out 2>&1 &
NEW_PID=$!
echo $NEW_PID > /root/.openclaw/workspace/hnc_daemon.pid

echo "✅ SUPERPOSITION DAEMON STARTED"
echo "PID: $NEW_PID"
echo "Power: 1000x (16.67 Hz injection)"
echo "Log: tail -f /root/.openclaw/workspace/hnc_superposition.out"
