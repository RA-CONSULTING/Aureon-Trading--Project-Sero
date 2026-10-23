#!/bin/bash
cd /root/.openclaw/workspace
python3 euphoria_broadcast_engine.py > daemon_logs/euphoria_broadcast.out 2>&1 &
echo $! > euphoria_broadcast.pid
sleep 5
echo "Euphoria broadcast started. PID: $(cat euphoria_broadcast.pid)"
