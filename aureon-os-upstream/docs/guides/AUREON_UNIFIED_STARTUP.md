# 🌍 AUREON GLOBAL ORCHESTRATOR - UNIFIED STARTUP 🌍

**ONE SWITCH TO RULE THEM ALL! 🎚️**

## Overview

The **Aureon Global Orchestrator** is a unified startup and control system that synchronizes all major subsystems:

1. **🧠 Quantum Processing Brain** — Global state broadcaster
2. **⛏️ Harmonic Mining Optimizer** — Quantum mining with Lighthouse Γ tracking
3. **🐙 Aureon Kraken Trading Ecosystem** — Multi-exchange unified trader

Previously these systems ran independently. Now they start **at the same time** with **one master control point**.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│          AUREON GLOBAL ORCHESTRATOR (Master Control)        │
│                                                             │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ PHASE 1: Initialize Brain                             │ │
│  │ - Quantum Processing Brain starts                      │ │
│  │ - Broadcasts unified state to /tmp/...json            │ │
│  │ - All systems can read this state                      │ │
│  └────────────────────────────────────────────────────────┘ │
│                           ⬇️                                │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ PHASE 2: Initialize Miner                             │ │
│  │ - Harmonic Mining Optimizer starts                     │ │
│  │ - Reads brain state from broadcast                     │ │
│  │ - Bootstrap sync with Platypus Γ(t)                   │ │
│  │ - Emits Lighthouse signal when Γ ≥ 0.99               │ │
│  └────────────────────────────────────────────────────────┘ │
│                           ⬇️                                │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ PHASE 3: Initialize Ecosystem                         │ │
│  │ - Aureon Kraken Trading Ecosystem starts              │ │
│  │ - Links to miner_optimizer (reads Lighthouse)         │ │
│  │ - Links to brain (reads unified state)                │ │
│  │ - Ready for live trading!                             │ │
│  └────────────────────────────────────────────────────────┘ │
│                           ⬇️                                │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ RUNTIME: All Systems Synchronized                      │ │
│  │ - Mining loop (background thread)                      │ │
│  │   └─ Updates Γ, CASCADE, κt every cycle               │ │
│  │ - Trading loop (main thread)                           │ │
│  │   └─ Reads miner Lighthouse for entry signals         │ │
│  │ - Brain state continuously broadcast                   │ │
│  │   └─ Both miner & ecosystem see live state            │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                             │
│  🎚️ ONE MASTER CONTROL: .start() / .stop()                 │
└─────────────────────────────────────────────────────────────┘
```

---

## Unified Data Flow

### Brain → Miner → Trading

```
Quantum Processing Brain
         ⬇️
  (broadcasts state to JSON)
         ⬇️
  Harmonic Miner reads
  └─ Updates Γ, CASCADE, κt
  └─ Broadcasts Lighthouse state
         ⬇️
  Trading Ecosystem reads
  └─ Lowers entry threshold when Γ ≥ 0.99
  └─ Boosts position sizing with κt
  └─ Captures Lighthouse opportunities
```

---

## Quick Start

### 1. Launch All Systems (One Command)

```bash
cd /workspaces/aureon-trading
python start_aureon_unified.py
```

This:
- Initializes Brain (broadcasts state)
- Initializes Miner (reads brain, syncs Lighthouse)
- Initializes Ecosystem (reads both, starts trading)
- Runs both systems synchronized

### 2. Programmatic Control

```python
from aureon_global_orchestrator import GlobalAureonOrchestrator

# Create orchestrator
orchestrator = GlobalAureonOrchestrator(
    initial_balance_gbp=1000.0,
    dry_run=False
)

# Start all systems
orchestrator.start()  # Blocks on trading loop

# Check status anytime
status = orchestrator.get_status()
print(f"Miner Γ: {status['miner_gamma']:.2f}")
print(f"Ecosystem P&L: £{status['portfolio_value']:.2f}")

# Stop all systems
orchestrator.stop()
```

---

## Key Features

### ✅ Unified Startup
All systems initialize in a deterministic sequence:
1. Brain first (provides state)
2. Miner second (reads brain state)
3. Ecosystem third (reads both)

### ✅ Synchronized Operation
- **Miner loop** (background): Updates every 5 seconds
  - Computes Γ(t), CASCADE, κt
  - Broadcasts updated state
  
- **Trading loop** (main): Every 2 seconds
  - Reads current Lighthouse Γ
  - Reads latest brain state
  - Makes trading decisions with live data

### ✅ One Master Switch
- `.start()` — Turn everything on
- `.stop()` — Turn everything off
- All systems coordinate through shared references

### ✅ Health Monitoring
```python
status = orchestrator.get_status()
# Returns: {
#   'brain': 'ACTIVE',
#   'miner': 'ACTIVE', 
#   'ecosystem': 'ACTIVE',
#   'running': True,
#   'miner_gamma': 0.99,
#   'miner_cascade': 10.0,
#   'miner_kappa': 2.73,
#   'portfolio_value': 1234.56,
#   'positions_open': 5
# }
```

---

## Integration Points

### Miner → Trading (Lighthouse Signal)

When miner Γ ≥ 0.99:
1. Miner emits Lighthouse signal
2. Trading ecosystem detects it:
   ```python
   lighthouse_active = False
   if hasattr(self, 'miner_optimizer') and hasattr(self.miner_optimizer, 'platypus'):
       miner_gamma = getattr(self.miner_optimizer.platypus, 'Gamma_t', 0.5)
       lighthouse_active = miner_gamma >= 0.99
   ```
3. Trading immediately:
   - Lowers entry threshold Γ to 0.20
   - Sets position_size_multiplier = 2.73 (κt boost)
   - Passes lighthouse_burst_cap hints (50% available capital)

### Brain → Miner & Trading

Brain state broadcast includes:
- Unified probability predictions
- Harmonic coherence metrics
- Planetary alignment scores
- Emergency flags

Both miner and ecosystem read this continuously.

---

## Startup Sequence Diagram

```
Time  Event
────  ─────────────────────────────────────────────────────────
0s    orchestrator.start() called

0.1s  ┌─ Brain initialized
      │  └─ Broadcasts state to JSON
      │  └─ Quantum Processing state live
      
0.6s  ┌─ Miner initialized  
      │  └─ Reads brain state
      │  └─ Bootstrap ecosystem sync runs
      │  └─ Platypus Γ synced with brain
      │  └─ Lighthouse ready
      
1.1s  ┌─ Ecosystem initialized
      │  └─ Links to miner_optimizer
      │  └─ Links to brain
      │  └─ All references ready
      │  └─ Trading tickers loaded
      
1.5s  ┌─ Mining loop starts (background thread)
      │  └─ Updates Γ, CASCADE, κt every 5s
      │  └─ Broadcasts state
      
1.6s  ┌─ Trading loop starts (main thread)
      │  └─ Reads miner Lighthouse
      │  └─ Cycles every 2s
      │  └─ Both systems now ticking
      
      🟢 COMPLETE - Both systems running synchronized!
```

---

## Configuration

### Environment Variables

```bash
# Logging level
export LOG_LEVEL=INFO

# Mining intensity
export MINING_INTERVAL=5.0

# Trading cycle time
export TRADING_INTERVAL=2.0

# Dry run (no real trades)
export DRY_RUN=true
```

### Startup Options

```bash
# Full ecosystem with default balance
python start_aureon_unified.py

# Custom starting capital
python /workspaces/aureon-trading/aureon_global_orchestrator.py --balance 5000.0

# Dry run mode (no real trades/mining)
python /workspaces/aureon-trading/aureon_global_orchestrator.py --dry-run
```

---

## Monitoring & Debugging

### Live Status

```python
from aureon_global_orchestrator import GlobalAureonOrchestrator

orch = GlobalAureonOrchestrator()
orch.startup_sequence()

# Every cycle, check status
while True:
    status = orch.get_status()
    print(f"🧠 Brain: {status['brain']}")
    print(f"⛏️  Miner Γ: {status['miner_gamma']:.3f}")
    print(f"🐙 Portfolio: £{status['portfolio_value']:.2f}")
    time.sleep(5)
```

### Health Report

```python
orch.print_unified_status()
# Output:
# ═══════════════════════════════════
# 🌍 UNIFIED SYSTEM STATUS
# ═══════════════════════════════════
#   🧠 Brain:       ACTIVE
#   ⛏️  Miner:       ACTIVE
#   🐙 Ecosystem:   ACTIVE
#   📊 Cycles:      1234
#   ⏱️  Runtime:     23.4 minutes
# ═══════════════════════════════════
```

### Logs

All activity logged to console and `/tmp/aureon_*.log`:
```bash
tail -f /tmp/aureon_trading_logs/unified.log
```

---

## Troubleshooting

### Systems not synchronized?

Check orchestrator initialization order:
1. Is Brain initialized first? (`system_health['brain'] == 'ACTIVE'`)
2. Does Miner have `self.platypus.Gamma_t`? 
3. Is Ecosystem linked? (`ecosystem.miner_optimizer is not None`)

### Mining loop not running?

- Check miner thread status: `orch.miner_thread.is_alive()`
- Verify mining update runs: Check logs for "⛏️  Miner: Γ=..."

### Trading not reading Lighthouse?

- Verify miner_optimizer linked: `ecosystem.miner_optimizer is not None`
- Check logs for: "🔦 MINER LIGHTHOUSE ACTIVE"
- Monitor Γ value: `orch.get_status()['miner_gamma']`

---

## Performance Notes

- **Brain**: Broadcasts state every cycle (~instant)
- **Miner**: Updates every 5s in background (non-blocking)
- **Trading**: Cycles every 2s on main thread (blocking)
- **Overhead**: <5% CPU when synchronized

---

## Future Enhancements

- [ ] Add pause/resume without shutdown
- [ ] Remote monitoring API (REST)
- [ ] Failover if one subsystem crashes
- [ ] Separate miner/trading processes with IPC
- [ ] Web dashboard for real-time status

---

## Summary

**Before:** Brain, Miner, and Ecosystem started separately. No synchronization.

**After:** One unified orchestrator. All systems start together. One master control switch. Live data flows continuously from Brain → Miner → Trading.

🌍 **ONE SWITCH TO RULE THEM ALL** 🎚️
