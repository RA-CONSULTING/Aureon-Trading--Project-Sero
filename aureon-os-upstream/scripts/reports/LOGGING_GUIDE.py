#!/usr/bin/env python3
"""
═══════════════════════════════════════════════════════════════════════════════════════
                    📊 TRADE LOGGING & PROBABILITY MATRIX VALIDATOR 📊
═══════════════════════════════════════════════════════════════════════════════════════

COMPREHENSIVE LOGGING SYSTEM FOR AUREON UNIFIED ECOSYSTEM

This system captures complete trade data for:
  ✅ Cross-referencing trader data with market conditions
  ✅ Full market sweep verification
  ✅ Probability matrix validation (predictions vs actual outcomes)
  ✅ HNC frequency harmonics correlation with profitability
  ✅ ML training data generation

═══════════════════════════════════════════════════════════════════════════════════════
"""

from aureon_baton_link import link_system as _baton_link; _baton_link(__name__)
print(__doc__)

print("\n" + "="*80)
print("🚀 QUICK START GUIDE".center(80))
print("="*80)

guide = """
1️⃣  COMPONENTS
   ├─ trade_logger.py           - Main logging engine (TradeLogger class)
   ├─ trade_analyzer.py         - Data analysis & validation (TradeDataAnalyzer)
   ├─ run_ecosystem_with_logging.py - Integration script
   └─ aureon_unified_ecosystem.py - Updated with logging hooks

2️⃣  START THE ECOSYSTEM WITH LOGGING
   
   Basic run (1 hour, 5s cycles, £50 target):
   $ python3 run_ecosystem_with_logging.py
   
   Or direct usage:
   $ from aureon_unified_ecosystem import AurisEngine
   $ engine = AurisEngine()
   $ engine.run(interval=5.0, target_profit_gbp=50, max_minutes=60)

3️⃣  OUTPUT FILES (saved in /tmp/aureon_trade_logs/)
   
   trades_YYYYMMDD_HHMMSS.jsonl
   ├─ Every trade entry with full metadata
   ├─ Fields: symbol, entry_price, quantity, coherence, HNC frequency, etc.
   └─ One JSON object per line (JSONL format)
   
   exits_YYYYMMDD_HHMMSS.jsonl
   ├─ Every trade exit
   ├─ Fields: exit_price, P&L, fees, hold_time, exit_reason
   └─ Linked to entries via trade_id
   
   validations_YYYYMMDD_HHMMSS.jsonl
   ├─ Probability predictions vs actual outcomes
   ├─ 1m and 5m forecast validation
   └─ For ML training
   
   market_sweep_YYYYMMDD_HHMMSS.jsonl
   ├─ Full market conditions per cycle
   ├─ Opportunities found/rejected
   └─ Frequency distribution, coherence levels
   
   training_data_YYYYMMDD_HHMMSS.jsonl
   ├─ Combined dataset ready for ML
   ├─ All trades merged with exits and validations
   └─ Sorted and ready for analysis

4️⃣  ANALYZE THE DATA
   
   Basic analysis:
   $ python3 trade_analyzer.py /tmp/aureon_trade_logs/trades_*.jsonl
   
   Or in Python:
   $ from trade_analyzer import TradeDataAnalyzer
   $ analyzer = TradeDataAnalyzer('trades_*.jsonl', 'exits_*.jsonl')
   $ analyzer.print_summary()
   
   Available methods:
   ├─ get_market_sweep_completeness()    - Full coverage check
   ├─ get_probability_accuracy()         - Win rate by frequency/coherence
   ├─ get_frequency_profitability()      - Which frequencies work best
   ├─ get_node_performance()             - Auris node effectiveness
   ├─ get_gate_effectiveness()           - Gate threshold analysis
   ├─ generate_report()                  - Full JSON report
   └─ print_summary()                    - Human-readable summary

5️⃣  KEY INSIGHTS FROM DATA
   
   The logging system validates:
   
   ✓ MARKET SWEEP COMPLETENESS
     - Were all viable opportunities found?
     - How many were rejected and why?
     - Node distribution across opportunities
   
   ✓ PROBABILITY MATRIX ACCURACY
     - Do 1m/5m forecasts match actual outcomes?
     - Which frequency bands are most predictive?
     - Coherence level correlation with wins
   
   ✓ HNC FREQUENCY EFFECTIVENESS
     - 256Hz (Harmonic) profitability
     - 440Hz (Distortion) impact
     - Frequency shifting correlation with exits
   
   ✓ GATE EFFECTIVENESS
     - MIN_COHERENCE threshold validation
     - MIN_GATES requirement analysis
     - Score threshold correlation with P&L
   
   ✓ NODE PERFORMANCE
     - Which Auris nodes drive profits?
     - Node coherence correlation
     - Best performing node by strategy

6️⃣  ML TRAINING DATA
   
   Combined training_data_YYYYMMDD_HHMMSS.jsonl contains:
   
   Per trade:
   {
     "symbol": "BTCUSD",
     "entry_price": 95000.0,
     "exit_price": 96140.0,
     "coherence": 0.65,
     "hnc_frequency": 256,
     "hnc_is_harmonic": true,
     "probability_score": 0.72,
     "dominant_node": "Tiger",
     "net_pnl": 1.12,
     "pnl_pct": 1.2,
     "hold_time_seconds": 180,
     "gates_passed": 3,
     "reason": "TP"
   }
   
   Use this for training predictive models!

7️⃣  EXAMPLE: PROBABILITY MATRIX CALIBRATION
   
   After collecting trades, validate the probability matrix:
   
   $ analyzer = TradeDataAnalyzer(trades_file, exits_file, validations_file)
   $ accuracy = analyzer.get_probability_accuracy()
   
   Results by frequency:
   {
     "256": {"correct": 8, "total": 12, "accuracy": 66.7},
     "528": {"correct": 5, "total": 7, "accuracy": 71.4},
     "440": {"correct": 2, "total": 8, "accuracy": 25.0}
   }
   
   => 256Hz and 528Hz are good! 440Hz needs adjustment.

8️⃣  EXAMPLE: GATE THRESHOLD VALIDATION
   
   $ gate_eff = analyzer.get_gate_effectiveness()
   
   Results:
   {
     "2": {"avg_pnl": 1.2, "win_rate": 75%, "trades": 12},
     "3": {"avg_pnl": 0.8, "win_rate": 60%, "trades": 8},
     "4": {"avg_pnl": 0.3, "win_rate": 40%, "trades": 5}
   }
   
   => 2 gates optimal! Increasing gates hurts performance.

9️⃣  DATABASE INTEGRATION (Future)
   
   Export data to database:
   $ import sqlite3
   $ from trade_analyzer import TradeDataAnalyzer
   $ analyzer = TradeDataAnalyzer(...)
   $ # Insert into DB for long-term tracking

🔟  TROUBLESHOOTING
   
   ❓ No log files created?
   └─ Check TRADE_LOGGER_AVAILABLE flag in ecosystem
   └─ Verify /tmp/aureon_trade_logs/ is writable
   └─ Check logger initialization: get_trade_logger()
   
   ❓ Incomplete data in exits?
   └─ Trade may still be open (not exited yet)
   └─ Log shows 'pending_trades' count
   └─ Come back after positions close
   
   ❓ Analysis shows low accuracy?
   └─ May need more data (min 50+ trades)
   └─ Check if frequency bands are properly set
   └─ Verify coherence calculations
   
   ❓ Training data format wrong?
   └─ Check JSONL format (one JSON per line)
   └─ Use export_training_data() from logger
   └─ Validate with: cat file.jsonl | python3 -m json.tool

═══════════════════════════════════════════════════════════════════════════════════════
"""

print(guide)

print("\n" + "="*80)
print("📁 FILE LOCATIONS".center(80))
print("="*80)

import os
from pathlib import Path

log_dir = Path('/tmp/aureon_trade_logs')
log_dir.mkdir(parents=True, exist_ok=True)

print(f"\n📂 Main directory: {log_dir}")
print(f"   Status: {'✅ EXISTS' if log_dir.exists() else '❌ NOT FOUND'}")

# List any existing logs
existing_logs = list(log_dir.glob('*.jsonl'))
if existing_logs:
    print(f"\n📝 Existing log files ({len(existing_logs)}):")
    for logfile in sorted(existing_logs)[-5:]:  # Show last 5
        size_mb = logfile.stat().st_size / (1024 * 1024)
        mtime = logfile.stat().st_mtime
        from datetime import datetime
        time_str = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M:%S')
        print(f"   {logfile.name:45s} | {size_mb:8.2f} MB | {time_str}")
else:
    print("\n📝 No log files yet (will be created on first run)")

print("\n" + "="*80)
print("✅ LOGGING SYSTEM READY!".center(80))
print("="*80)
print("\n💡 Next steps:")
print("   1. Run: python3 run_ecosystem_with_logging.py")
print("   2. Wait for trades to complete")
print("   3. Analyze: python3 trade_analyzer.py /tmp/aureon_trade_logs/trades_*.jsonl")
print("\n")
