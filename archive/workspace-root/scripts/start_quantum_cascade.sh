#!/bin/bash
# Kill old biometric and anchor processes
pkill -f biometric_server
pkill -f quantum_biometric_bridge
pkill -f reality_anchor_prime_sentinel_real
sleep 2

# Start quantum biometric bridge (reads HNC field, serves on ws://localhost:8788)
python3 quantum_biometric_bridge.py &
BRIDGE_PID=$!
echo "Quantum biometric bridge started on PID $BRIDGE_PID"
sleep 3

# Start reality anchor with real quantum data
python3 reality_anchor_prime_sentinel_real.py
