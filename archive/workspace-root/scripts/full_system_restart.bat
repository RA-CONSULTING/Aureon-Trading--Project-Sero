@echo off
REM ============================================================
REM AUREON FULL SYSTEM RESTART — All Compartments Fresh
REM Timestamp: 2026-09-04
REM Prime Sentinel: Gary Leckey
REM ============================================================

setlocal
set PYTHONIOENCODING=utf-8
set PYTHONUNBUFFERED=1
set WORKSPACE=C:\Users\user\.kimi_openclaw\workspace
set PYTHON_EXE=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe
if not exist "%PYTHON_EXE%" set PYTHON_EXE=python

REM Ensure log directories exist
if not exist "%WORKSPACE%\logs" mkdir "%WORKSPACE%\logs"

echo ============================================================
echo  AUREON FULL SYSTEM RESTART
echo  Time: %date% %time%
echo ============================================================
echo.

REM === LAYER 0: DATA FEEDERS ===
echo [L0] Starting Real-Time Data Feeder...
start /B /MIN "" "%PYTHON_EXE%" -u "%WORKSPACE%\real_time_data_feeder.py" > "%WORKSPACE%\logs\real_time_data_feeder_restart.log" 2>&1
timeout /t 1 /nobreak >nul

REM === LAYER 1: LEGACY DAEMONS ===
echo [L1] Starting Legacy Daemon Layer...
start /B /MIN "" "%PYTHON_EXE%" -u "%WORKSPACE%\hnc_daemon.py" > "%WORKSPACE%\logs\hnc_daemon_restart.log" 2>&1
start /B /MIN "" "%PYTHON_EXE%" -u "%WORKSPACE%\schumann_real_daemon.py" > "%WORKSPACE%\logs\schumann_daemon_restart.log" 2>&1
start /B /MIN "" "%PYTHON_EXE%" -u "%WORKSPACE%\planetary_monitor_daemon.py" > "%WORKSPACE%\logs\planetary_monitor_restart.log" 2>&1
start /B /MIN "" "%PYTHON_EXE%" -u "%WORKSPACE%\soul_protection_daemon.py" > "%WORKSPACE%\logs\soul_protection_restart.log" 2>&1
start /B /MIN "" "%PYTHON_EXE%" -u "%WORKSPACE%\temporal_reclamation_engine.py" > "%WORKSPACE%\logs\temporal_engine_restart.log" 2>&1
timeout /t 2 /nobreak >nul

REM === LAYER 2: RADAR COMPARTMENT ===
echo [L2] Starting Radar Compartment...
cd /d "%WORKSPACE%\aureon_radar"
start /B /MIN "" "%PYTHON_EXE%" -u "planetary_switchboard.py" > "planetary_meta_restart.log" 2>&1
start /B /MIN "" "%PYTHON_EXE%" -u "ollama_switchboard.py" > "ollama_switchboard_restart.log" 2>&1
start /B /MIN "" "%PYTHON_EXE%" -u "alpaca_switchboard.py" > "stock_meta_restart.log" 2>&1
start /B /MIN "" "%PYTHON_EXE%" -u "binance_switchboard.py" > "correlation_meta_restart.log" 2>&1
timeout /t 2 /nobreak >nul

REM === LAYER 3: BRIDGE + RADAR ===
echo [L3] Starting Bridge and Phi-Radar...
start /B /MIN "" "%PYTHON_EXE%" -u "aureon_bridge.py" > "aureon_bridge_restart.log" 2>&1
start /B /MIN "" "%PYTHON_EXE%" -u "aureon_phi_radar.py" > "radar_restart.log" 2>&1

echo.
echo ============================================================
echo  ALL SYSTEMS LAUNCHED
echo ============================================================
echo.
echo Active logs:
echo   - %WORKSPACE%\logs\*_restart.log
echo   - %WORKSPACE%\aureon_radar\*_restart.log
echo.
