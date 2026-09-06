# 🇮🇪 AUREON WINDOWS COMMAND CHEAT SHEET

Save this somewhere handy.

> Assumptions:
> - You’re using **Windows Terminal → PowerShell**
> - Repo folder is `C:\Users\<YOU>\aureon-trading` (change as needed)

---

## 📂 Navigation

```powershell
cd C:\Users\<YOU>\aureon-trading
ls          # or: dir
cls
```

---

## 🐍 Python + venv (first-time setup)

### Create + activate venv

```powershell
cd C:\Users\<YOU>\aureon-trading
py -3 -m venv .venv

# If activation is blocked:
# Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### Quick “is venv active?” check

```powershell
python -c "import sys; print(sys.executable)"
```

---

## 🔄 Git (pull updates)

```powershell
git pull origin main

git status

git log --oneline -5
```

### If you get: “local changes would be overwritten”

```powershell
git stash

git pull origin main

git stash pop  # optional (only if you want your local edits back)
```

---

## 🚀 Run the system (most common)

### 🏆 RECOMMENDED: Multi-Window Setup (Best Experience)

Open **2 PowerShell windows** and run these:

**Window 1 - Trading Engine (Orca + War Room):**
```powershell
cd C:\Users\<YOU>\aureon-trading
.\.venv\Scripts\Activate.ps1
python orca_complete_kill_cycle.py --autonomous
```

**Window 2 - Game Launcher (All Dashboards):**
```powershell
cd C:\Users\<YOU>\aureon-trading
.\.venv\Scripts\Activate.ps1
python aureon_game_launcher.py
```

This gives you the full system with all dashboards accessible!

---

### 1) War Room Dashboard (AUTO-START)

```powershell
# Auto-starts the dashboard by default
python orca_complete_kill_cycle.py
```

Optional explicit mode:

```powershell
python orca_complete_kill_cycle.py --autonomous
```

### 2) Safe first run (dry-run trading engine)

```powershell
python micro_profit_labyrinth.py --dry-run
```

### 3) Windows-safe launcher (recommended if console/encoding gets weird)

```powershell
python run_aureon_windows.py --dry-run
```

### 4) Launch the “Game Launcher” (starts dashboards/services)

```powershell
python aureon_game_launcher.py
```

### 5) Command Center (Full Dashboard with ALL systems)

```powershell
# Full Command Center - all intelligence systems loaded
python aureon_command_center.py
# Then open: http://localhost:8888
# Systems will load in background on Windows (0/0 → 25/25 within seconds)
```
---

## 🛑 Stop the system

```text
Ctrl + C
```

---

## 🧪 Testing & diagnostics

```powershell
python test_system_health.py
python comprehensive_diagnostic.py
python verify_platform_connectivity.py
```

---

## 💰 Checking balances (quick CLI)

> These require your API keys configured in `.env`.

```powershell
python -c "from binance_client import BinanceClient; b=BinanceClient(); print(b.get_balance('USDT'))"
python -c "from kraken_client import KrakenClient; k=KrakenClient(); print(k.get_balance())"
```

---

## 📋 Common workflows

### Daily update + run

```powershell
cd C:\Users\<YOU>\aureon-trading
.\.venv\Scripts\Activate.ps1

git pull origin main

# Safe validation pass
python micro_profit_labyrinth.py --dry-run

# Then War Room
python orca_complete_kill_cycle.py
```

### “Things are stuck” reset path (careful)

```powershell
cd C:\Users\<YOU>\aureon-trading
.\.venv\Scripts\Activate.ps1

git stash

git pull origin main

python reset_for_beta.py
```

### Check version

```powershell
python -c "from version import __version__; print(f'Aureon v{__version__}')"
```

---

## 📁 Important files

- `.env` (API keys — don’t share)
- `orca_complete_kill_cycle.py` (War Room / Orca engine)
- `micro_profit_labyrinth.py` (main execution engine)
- `run_aureon_windows.py` (Windows-safe runner)
- `CHANGELOG.md` (what changed)

---

## 🏷️ Git tags (versions)

```powershell
git tag

git checkout v0.9.0-beta

git checkout main
```

---

## ⚠️ Troubleshooting

### “Activate.ps1 is not recognized”

- You’re likely **not in the repo folder**, or `.venv` doesn’t exist.

```powershell
cd C:\Users\<YOU>\aureon-trading
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### “running scripts is disabled”

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### “ModuleNotFoundError”

```powershell
pip install -r requirements.txt
```

### Emoji/Unicode looks broken

```powershell
$env:PYTHONIOENCODING = "utf-8"
python run_aureon_windows.py --dry-run
```
