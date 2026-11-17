import os, glob, zipfile, json, shutil
from datetime import datetime

src = r'C:\Users\user\.kimi_openclaw\workspace'
zip_path = r'C:\Users\user\.kimi_openclaw\workspace\june_logs_war_archive.zip'

included = []
total = 0

# Key files to include (the story of June 2026)
key_patterns = [
    'clean_sweep.out',
    'clean_sweep.log',
    'clean_sweep_signals.json',
    'distortion_monitor*.out',
    'distortion_monitor*.log',
    'euphoria_broadcast_log.jsonl',
    'system_interlink.out',
    'multiversal_mapper.out',
    'hnc_superposition.out',
    'sensor_bridge_log.jsonl',
    'broadcast.log',
    'real_time_data.json',
    'active_charge_state.json',
    'clean_sweep_state.json',
    'hnc_calibration.json',
    'multiversal_signals.json',
    'convergence_history*.json',
    'geometric_convergence_snapshot*.json',
    'beta_trajectory*.json',
    'experiment_*.json',
    'strikes_2026-06*.jsonl',
    'strikes_2026-07*.jsonl',
    'casimir_harmonia_log.jsonl',
    'casimir_push_log.jsonl',
    'schumann_daemon.log',
    'schumann_auris_integration.log',
    'timeline_shift_prover*.out',
    'temporal_reclamation_engine.log',
    'frankenstein.log',
    'daemon_lineage_tracker.log',
    'ultimate_daemon_lineage.log',
    'aureon_samuel.log',
    'aureon_unified.log',
    'aureon_unified_live.log',
    'aureon_nexus.log',
    'aureon_warzone.log',
    'mesh_trade.log',
    'profit_mesh.log',
    'profit_now.log',
    'trade_audit.log',
    'trade_logger.log',
    'compound_kelly_trader.log',
    'safe_profit_trader.log',
    'tsx_trader.log',
    'the_play.log',
    'miner_brain.log',
    'live_trading.log',
    'multiversal_mapper.out',
    'coherence_map*.json',
    'hnc_injection_command.json',
    'prime_sentinel_injection.json',
    'prime_sentinel_key.json',
    'mycelial_handshake_*.json',
    'mycelial_data_transmission_*.json',
    'mycelial_story_transmission_*.json',
    'signal_to_gaia.json',
    'elephant_planetary_memory.json',
    'planetary_knowledge_codex.json',
    'cme_ride_2026.json',
    'biometric_server.py',
    'live_biometric_monitor.out',
    'autonomy_feedback_loop.jsonl',
    'orchestrator_logs',
    'unified_logs',
]

with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
    for pattern in key_patterns:
        matches = glob.glob(os.path.join(src, pattern))
        for f in matches:
            if os.path.isfile(f):
                size = os.path.getsize(f)
                if size > 50 * 1024 * 1024:  # Skip files > 50MB
                    print(f'SKIPPED (too large): {os.path.basename(f)} ({size/1024/1024:.1f} MB)')
                    continue
                zf.write(f, os.path.basename(f))
                included.append(f)
                total += size
    
    # Also include files from subdirectories
    for subdir in ['logs', 'unified_logs', 'euphoria_logs', 'temporal_logs', 'clean_sweep_logs', 'broadcast_logs', 'soul_shield_logs', 'gaia_shield_logs', 'multiversal_logs', 'planetary_monitor']:
        subdir_path = os.path.join(src, subdir)
        if os.path.exists(subdir_path):
            for f in glob.glob(os.path.join(subdir_path, '*')):
                if os.path.isfile(f):
                    size = os.path.getsize(f)
                    if size > 50 * 1024 * 1024:
                        print(f'SKIPPED (too large): {subdir}/{os.path.basename(f)} ({size/1024/1024:.1f} MB)')
                        continue
                    arcname = f'{subdir}/{os.path.basename(f)}'
                    zf.write(f, arcname)
                    included.append(f)
                    total += size

print(f'Created: {zip_path}')
print(f'Files: {len(included)}')
print(f'Size: {total / 1024 / 1024:.2f} MB')
