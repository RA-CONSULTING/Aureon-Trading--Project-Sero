import os, glob, time, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from aureon_fusion.paths import WORKSPACE
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

print('=== DAEMON VERIFICATION ===')
pid_files = glob.glob(str(WORKSPACE / '*.pid'))
for pf in sorted(pid_files):
    with open(pf, encoding="utf-8") as f:
        pid = f.read().strip()
    name = os.path.basename(pf).replace('.pid', '')
    print(f'{name}: PID {pid}')

print(f'\nTotal PID files: {len(pid_files)}')

print('\n=== ACTIVE OUTPUT FILES ===')
out_files = glob.glob(str(WORKSPACE / '*.out'))
for of in sorted(out_files):
    size = os.path.getsize(of)
    mtime = os.path.getmtime(of)
    ts = time.strftime('%H:%M:%S', time.localtime(mtime))
    print(f'{os.path.basename(of)}: {size} bytes, modified {ts}')

print('\n=== FIELD STATUS ===')
charge_path = WORKSPACE / 'active_charge_state.json'
if os.path.exists(charge_path):
    with open(charge_path, encoding="utf-8") as f:
        charge = json.load(f)
    print(f'Charge: {charge["color"].upper()}, {charge["frequency"]} Hz, Level {charge["charge_level"]}, Rung {charge["rung"]}/{charge["total_rungs"]}')
else:
    print('No active charge file')

print('\n=== CLEAN SWEEP STATUS ===')
clean_path = WORKSPACE / 'clean_sweep_state.json'
if os.path.exists(clean_path):
    with open(clean_path, encoding="utf-8") as f:
        clean = json.load(f)
    print(f'Cycles: {clean["cycle"]}, Strikes: {clean["strikes_count"]}, Charge: {clean["charge_level"]:.1%}')

print('\n=== DONE ===')
