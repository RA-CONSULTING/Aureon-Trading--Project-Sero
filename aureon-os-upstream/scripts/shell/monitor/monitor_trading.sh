#!/bin/bash
clear
echo "👑 AUREON TRADING SYSTEM MONITOR 👑"
echo "==================================="
echo "📊 Dashboard Status:"
if ps -p $(cat /tmp/dash_pid) > /dev/null; then
    echo "✅ Dashboard Running (PID: $(cat /tmp/dash_pid))"
else
    echo "❌ Dashboard STOPPED"
fi

echo "🦈 Orca Status:"
if ps -p $(cat /tmp/orca_pid) > /dev/null; then
    echo "✅ Orca Running (PID: $(cat /tmp/orca_pid))"
else
    echo "❌ Orca STOPPED"
fi

echo ""
echo "📈 Latest Dashboard Output:"
echo "---------------------------"
tail -n 30 /tmp/dashboard_live.log

echo ""
echo "📜 Latest Orca Activity:"
echo "------------------------"
tail -n 10 /tmp/orca_live.log
