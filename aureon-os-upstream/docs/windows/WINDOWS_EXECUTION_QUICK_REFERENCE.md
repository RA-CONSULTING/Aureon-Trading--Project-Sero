# 🪟 WINDOWS EXECUTION GUIDE - Aureon Trading System

## Quick Start (Windows PowerShell)

### 1️⃣ Navigate to Project
```powershell
cd C:\Users\<YourUsername>\aureon-trading
```

### 2️⃣ Activate Virtual Environment
```powershell
.\.venv\Scripts\Activate.ps1
```

### 3️⃣ Run the System (Safe Launcher)
```powershell
# Dry-run mode (RECOMMENDED FIRST)
python run_aureon_windows.py --dry-run

# Snowball mode (slow & safe)
python run_aureon_windows.py --snowball

# Multi-exchange mode (fastest)
python run_aureon_windows.py --multi-exchange

# Winners only mode (clean console)
python run_aureon_windows.py --winners-only
```

### 4️⃣ Direct Execution (if launcher fails)
```powershell
python micro_profit_labyrinth.py --dry-run
```

---

## Understanding the Startup Output

✅ **Good Signs** (System initializing):
```
🔐 Environment variables loaded
🔑 Kraken API: ✅ Loaded
🌍 Global Financial Feed LOADED!
💎 Mycelium: Ultimate Intelligence WIRED!
🏆🌀 LABYRINTH SNOWBALL ENGINE LOADING...
```

✅ **System Ready** (Final messages before trading):
```
🏆🌀 Labyrinth Snowball Engine LOADED!
🐙 Kraken Client LOADED!
🟡 Binance Client LOADED!
🦙 Alpaca Client LOADED!
```

❌ **Error - Fixed by Launcher**:
```
ValueError('I/O operation on closed file.')
lost sys.stderr
```
→ **Solution**: Use `python run_aureon_windows.py` instead of direct execution

---

## Configuration

### 1️⃣ Check Environment File
```powershell
# View current configuration
Get-Content .env

# Edit with Notepad
notepad .env
```

### 2️⃣ Required API Keys in `.env`
```
KRAKEN_API_KEY=your_key_here
KRAKEN_PRIVATE_KEY=your_secret_here
BINANCE_API_KEY=your_key_here
BINANCE_API_SECRET=your_secret_here
ALPACA_API_KEY=your_key_here
ALPACA_SECRET_KEY=your_secret_here
CAPITAL_API_KEY=your_key_here
CAPITAL_LOGIN=your_login_here
CAPITAL_PASSWORD=your_password_here
```

### 3️⃣ Optional Environment Variables
```powershell
# Set mode to live trading
[Environment]::SetEnvironmentVariable("LIVE", "true", "User")

# Enable snowball mode
[Environment]::SetEnvironmentVariable("SNOWBALL_MODE", "true", "User")

# Force multi-exchange
[Environment]::SetEnvironmentVariable("MULTI_EXCHANGE", "true", "User")
```

---

## Troubleshooting

### Issue: "ValueError: I/O operation on closed file"

**Cause**: Windows stream closure issue on exit  
**Fix**: 
```powershell
# Use the safe launcher
python run_aureon_windows.py --dry-run

# If still occurring, add delay before exit
# (This is handled automatically by the launcher)
```

### Issue: "ModuleNotFoundError: No module named 'X'"

**Cause**: Virtual environment not activated  
**Fix**:
```powershell
# Activate venv
.\.venv\Scripts\Activate.ps1

# Then run again
python run_aureon_windows.py --dry-run
```

### Issue: "Permission denied" or "Access denied"

**Cause**: Windows execution policy  
**Fix**:
```powershell
# Check current policy
Get-ExecutionPolicy

# Temporarily allow for this session
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process

# Then activate venv
.\.venv\Scripts\Activate.ps1
```

### Issue: "PYTHONIOENCODING is not recognized"

**Cause**: Command prompt UTF-8 handling  
**Fix**: The launcher handles this automatically. Use:
```powershell
python run_aureon_windows.py --dry-run
```

---

## Performance Monitoring

### 1️⃣ Watch Logs in Real-Time
```powershell
# Monitor trades as they happen
Get-Content -Path $env:TEMP\aureon_trade_logs\trades_*.jsonl -Wait

# Alternative: Follow latest log
Get-ChildItem $env:TEMP\aureon_trade_logs -Recurse -File | 
  Sort-Object LastWriteTime -Desc | 
  Select-Object -First 1 | 
  ForEach-Object { Get-Content -Path $_.FullName -Wait }
```

### 2️⃣ Check Resource Usage
```powershell
# Monitor process while running
Get-Process python* | Select-Object ProcessName, @{
    Name = "CPU%";
    Expression = {[math]::Round($_.CPU, 2)}
}, @{
    Name = "RAM MB";
    Expression = {[math]::Round($_.WorkingSet / 1MB, 2)}
} | Sort-Object "CPU%" -Descending
```

### 3️⃣ Verify Exchange Connectivity
```powershell
# Check all exchange balances
python check_all_balances.py

# Verify WebSocket connections
python verify_platform_connectivity.py
```

---

## Safe Trading Workflow

### ✅ Phase 1: Dry-Run (15+ minutes)
```powershell
python run_aureon_windows.py --dry-run
# Monitor: No real money moved, but all systems tested
```

### ✅ Phase 2: Snowball Mode ($1-5 trades)
```powershell
python run_aureon_windows.py --snowball
# Monitor: One trade at a time, very safe
# Expected: 1-3 trades over first hour
```

### ✅ Phase 3: Winners-Only Mode (production)
```powershell
python run_aureon_windows.py --winners-only
# Monitor: Clean console, only winning trades shown
# Expected: 5-20 trades per hour depending on markets
```

### ⚠️ Phase 4: Multi-Exchange (when confident)
```powershell
python run_aureon_windows.py --multi-exchange
# Monitor: Fastest execution, highest frequency
# Expected: 20-50 opportunities per hour
```

---

## Stop the System

### ✅ Graceful Shutdown
```powershell
# Press Ctrl+C in the console
# System will:
#   1. Close all open positions
#   2. Cancel pending orders
#   3. Save state to JSON files
#   4. Exit cleanly
```

### 🚨 Force Stop (if hung)
```powershell
# List all Python processes
Get-Process python* | Format-Table Id, ProcessName, CPU, WorkingSet

# Kill specific process (careful!)
Stop-Process -Id <process_id> -Force

# Kill all Python processes (RISKY)
Stop-Process -Name python -Force
```

---

## Next Steps

1. **Test connectivity first**:
   ```powershell
   python check_all_balances.py
   ```

2. **Run dry-mode for confidence**:
   ```powershell
   python run_aureon_windows.py --dry-run
   ```

3. **Start with snowball mode**:
   ```powershell
   python run_aureon_windows.py --snowball
   ```

4. **Monitor performance**:
   ```powershell
   # Watch realtime logs
   Get-ChildItem $env:TEMP\aureon_trade_logs -Recurse -File | 
     Sort-Object LastWriteTime -Desc | 
     Select-Object -First 1 | 
     ForEach-Object { Get-Content -Path $_.FullName -Wait }
   ```

---

## Windows-Specific Features

✅ **UTF-8 Support**: Handled automatically by launcher  
✅ **Stream Cleanup**: Fixed in `run_aureon_windows.py`  
✅ **Asyncio Event Loop**: ProactorEventLoop on Windows (recommended)  
✅ **Path Handling**: Fully compatible with Windows paths (C:\...)  
✅ **File Permissions**: No special admin required (except 2FA on exchanges)  

---

**Version**: 2.0 (January 16, 2026)  
**Platform**: Windows 10/11  
**Python**: 3.9+  
**Status**: ✅ Production Ready
