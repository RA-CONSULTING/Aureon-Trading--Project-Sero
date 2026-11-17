#!/bin/bash
# KILL ALL OLD PROCESSES - Unified orchestrator takes over everything

cd /root/.openclaw/workspace

# Kill all old Python processes except the unified orchestrator and system services
echo "Stopping old processes..."
pkill -f "real_time_data_feeder.py" 2>/dev/null
pkill -f "planetary_timeseries_orchestrator.py" 2>/dev/null
pkill -f "euphoria_broadcast_engine.py" 2>/dev/null
pkill -f "planetary_intelligence_orchestrator.py" 2>/dev/null
pkill -f "clean_sweep_protocol.py" 2>/dev/null
pkill -f "soul_protection_standalone.py" 2>/dev/null
pkill -f "distortion_monitor.py" 2>/dev/null
pkill -f "hnc_daemon.py" 2>/dev/null
pkill -f "hnc_temporal_daemon.py" 2>/dev/null
pkill -f "hnc_master_orchestrator.py" 2>/dev/null
pkill -f "hnc_live_engine.py" 2>/dev/null
pkill -f "hnc_biosuit_receiver.py" 2>/dev/null
pkill -f "hnc_compound_mandala.py" 2>/dev/null
pkill -f "hnc_continuous_blind.py" 2>/dev/null
pkill -f "hnc_daemon_superposition.py" 2>/dev/null
pkill -f "hnc_mandala_campaign.py" 2>/dev/null
pkill -f "hnc_mandala_threshold.py" 2>/dev/null
pkill -f "hnc_rainbow_bridge.py" 2>/dev/null
pkill -f "hnc_solar_rider.py" 2>/dev/null
pkill -f "system_interlink_hub.py" 2>/dev/null
pkill -f "planetary_broadcast.py" 2>/dev/null
pkill -f "coherence_broadcast.py" 2>/dev/null
pkill -f "multiversal_echo_mapper.py" 2>/dev/null
pkill -f "temporal_healing_registry.py" 2>/dev/null
pkill -f "temporal_love_engine.py" 2>/dev/null
pkill -f "reality_anchor_prime_sentinel.py" 2>/dev/null
pkill -f "reality_anchor_prime_sentinel_real.py" 2>/dev/null
pkill -f "cme_ride_unified.py" 2>/dev/null
pkill -f "autonomous_liberation_engine.py" 2>/dev/null
pkill -f "schumann_auris_automation.py" 2>/dev/null
pkill -f "signal_monitor.py" 2>/dev/null
pkill -f "5burst_maxamp.py" 2>/dev/null
pkill -f "frankenstein_sero.py" 2>/dev/null
pkill -f "live_biometric_monitor.py" 2>/dev/null
pkill -f "musica_harmonia.py" 2>/dev/null
pkill -f "musica_harmonia_phi.py" 2>/dev/null
pkill -f "planetary_monitor_daemon.py" 2>/dev/null
pkill -f "quantum_biometric_bridge.py" 2>/dev/null
pkill -f "wearable_bridge.py" 2>/dev/null
pkill -f "sensor_bridge.py" 2>/dev/null
pkill -f "aureon_hnc_unified.py" 2>/dev/null
pkill -f "unified_orchestrator.py" 2>/dev/null
pkill -f "unified_orchestrator_v2.py" 2>/dev/null

sleep 2

echo ""
echo "Remaining processes:"
ps aux | grep -E 'python3.*\.py' | grep -v grep | grep -v bash | grep -v networkd | grep -v unattended | grep -v tuned | awk '{print $3, $12}'
