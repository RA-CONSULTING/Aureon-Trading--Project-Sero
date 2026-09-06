#!/bin/bash
# WAVE 1: CRITICAL INFRASTRUCTURE ONLY
# Tier 1 + 2 systems (most important)

cd /root/.openclaw/workspace
mkdir -p daemon_logs

launch_if_missing() {
    script="$1"
    desc="$2"
    if ! pgrep -f "$script" > /dev/null 2>&1; then
        echo "🚀 $script ($desc)"
        nohup python3 "$script" > "daemon_logs/${script%.py}.out" 2>&1 &
        sleep 0.3
    else
        echo "✅ $script"
    fi
}

echo "╔═══════════════════════════════════════════════════════════════════════════════╗"
echo "║           WAVE 1: CRITICAL INFRASTRUCTURE 🚀                                  ║"
echo "╚═══════════════════════════════════════════════════════════════════════════════╝"

# Core HNC
launch_if_missing "hnc_daemon.py" "HNC core"
launch_if_missing "hnc_temporal_daemon.py" "HNC temporal"
launch_if_missing "hnc_master_orchestrator.py" "HNC master"
launch_if_missing "hnc_live_engine.py" "HNC live engine"
launch_if_missing "hnc_data_sources.py" "HNC data sources"

# Core Sero
launch_if_missing "sero_master_orchestrator.py" "Sero master"
launch_if_missing "sero_chirp.py" "Sero chirp bus"
launch_if_missing "sero_thoughtbus.py" "Sero thought bus"
launch_if_missing "sero_mycelium.py" "Sero mycelium"

# Sentinel
launch_if_missing "prime_sentinel_key.py" "Prime sentinel key"
launch_if_missing "prime_sentinel_transmission.py" "Prime sentinel transmission"

# Bridge
launch_if_missing "system_interlink_hub.py" "System interlink"
launch_if_missing "guardian_anchor_bridge.py" "Guardian anchor"
launch_if_missing "nexus_live_bridge.py" "Nexus live bridge"

# Shield
launch_if_missing "epas_shield.py" "EPAS shield"
launch_if_missing "gaia_biosphere_shield.py" "Gaia biosphere"
launch_if_missing "druid_mycelial_shield.py" "Druid mycelial"
launch_if_missing "soul_protection_daemon.py" "Soul protection daemon"
launch_if_missing "hnc_biosuit_receiver.py" "HNC biosuit"

# Broadcast
launch_if_missing "cme_ride_daemon.py" "CME ride"
launch_if_missing "cme_ride_protocol.py" "CME protocol"
launch_if_missing "planetary_broadcast.py" "Planetary broadcast"
launch_if_missing "coherence_broadcast.py" "Coherence broadcast"

# Mycelial
launch_if_missing "mycelial_data_transmission.py" "Mycelial data"
launch_if_missing "mycelial_story_transmission.py" "Mycelial story"

# Multiversal
launch_if_missing "multiversal_echo_mapper.py" "Multiversal echo"
launch_if_missing "temporal_healing_registry.py" "Temporal healing"
launch_if_missing "temporal_love_engine.py" "Temporal love"

# Duck
launch_if_missing "duck_spawn_grounds.py" "Duck spawn"
launch_if_missing "duck_warfare.py" "Duck warfare"

echo ""
echo "Wave 1 complete. Counting processes..."
COUNT=$(ps aux | grep -E 'python3' | grep -v grep | grep -v bash | grep -v networkd | grep -v unattended | grep -v tuned | wc -l)
echo "Active Python processes: $COUNT"
