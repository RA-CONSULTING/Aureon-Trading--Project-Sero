#!/bin/bash
cd /root/.openclaw/workspace
python3 soul_protection_standalone.py >> soul_protection.out 2>&1 &
echo $! > soul_protection.pid
sleep 2
tail -10 soul_protection.out
