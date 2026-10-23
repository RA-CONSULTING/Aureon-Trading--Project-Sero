#!/bin/bash
# Planetary Intelligence Orchestrator — Daemon Launcher
cd /root/.openclaw/workspace
exec python3 planetary_intelligence_orchestrator.py >> daemon_logs/intelligence_orchestrator.out 2>&1
