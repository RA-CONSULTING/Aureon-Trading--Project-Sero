# 🌌 AUREON SYSTEM HUB

**Centralized mind map and categorization for all 90+ Aureon Trading systems.**

---

## 🚀 Quick Start

### 1. Scan Workspace
```bash
python aureon_system_hub.py
```
This will:
- Auto-discover all Python modules
- Categorize into 12 system groups
- Generate `aureon_system_registry.json`
- Display statistics

### 2. Launch Web Dashboard
```bash
python aureon_system_hub_dashboard.py
```
Then open: **http://localhost:13001**

### 3. Use CLI Interface
```bash
# List all systems
python aureon_system_hub_cli.py list

# Search for systems
python aureon_system_hub_cli.py search whale

# Show statistics
python aureon_system_hub_cli.py stats

# View system details
python aureon_system_hub_cli.py info aureon_queen_hive_mind

# Generate ASCII mind map
python aureon_system_hub_cli.py map

# Launch dashboard from CLI
python aureon_system_hub_cli.py launch
```

---

## 📊 System Categories

| Icon | Category | Description |
|------|----------|-------------|
| 🕵️ | **Intelligence Gatherers** | Bot, Firm, Whale intelligence systems |
| 📊 | **Market Scanners** | Wave analysis, momentum detection, market sweeps |
| 🤖 | **Bot Tracking** | Bot detection, classification, mapping |
| ⚡ | **Momentum Systems** | Movement detection >0.34%, animal-themed hunters |
| 🎯 | **Probability & Prediction** | 95% accuracy ML, coherence validation |
| 🧠 | **Neural Networks** | Queen Hive Mind, Mycelium, Elephant Memory |
| 🔐 | **Codebreaking & Harmonics** | Enigma rotors, harmonic signals, frequency analysis |
| 🌌 | **Stargate & Quantum** | Planetary nodes, quantum telescopes, timeline anchoring |
| 📈 | **Dashboards** | Web interfaces, visualizations, monitoring |
| 🔗 | **Communication** | Thought Bus, Chirp Bus, integration hubs |
| ⚙️ | **Execution Engines** | Trading execution, profit gates, order routing |
| 🌍 | **Exchange Clients** | Kraken, Binance, Alpaca, Capital.com APIs |

---

## 🎨 Features

### Interactive Mind Map
- **Force-directed graph** visualization
- **Color-coded** by category
- **Click nodes** to see details
- **Double-click** to zoom
- **Search** and filter
- **Auto-discovery** of dependencies

### System Registry
- **Auto-categorization** by pattern matching
- **Import analysis** for dependency mapping
- **LOC counting** and statistics
- **ThoughtBus detection**
- **Queen integration** tracking
- **Sacred frequency** extraction

### Dashboard Links
Direct access to all active dashboards:
- 👑 Queen Web (5000)
- 🤖 Bot Hunter (9999)
- 📊 Queen Unified (13000)
- 🗺️ Global Bot Map (8888)
- 👁️ Surveillance (8080)

---

## 🔍 What Gets Tracked

For each system, the hub tracks:
- **Name** and **filepath**
- **Category** (auto-detected)
- **Description** (from docstring)
- **Lines of code**
- **Dependencies** and imports
- **ThoughtBus integration** (yes/no)
- **Queen integration** (yes/no)
- **Dashboard status** and port
- **Sacred frequencies** (528Hz, 7.83Hz, PHI, etc.)
- **Last modified** timestamp

---

## 📁 Output Files

- `aureon_system_registry.json` - Full system catalog with metadata
- Saved automatically after scan

---

## 🎯 Use Cases

1. **Onboarding** - New developers can visualize the entire system
2. **Documentation** - Auto-generated system catalog
3. **Dependency Analysis** - See which systems connect
4. **Dashboard Discovery** - Find all web interfaces
5. **Integration Tracking** - Which systems use ThoughtBus/Queen
6. **Code Statistics** - LOC counts per category
7. **Architecture Visualization** - Interactive mind map

---

## 🧠 How Categorization Works

The system uses **pattern matching** on filenames and content:

```python
# Examples
aureon_bot_intelligence_profiler.py     → Intelligence Gatherers
aureon_global_wave_scanner.py           → Market Scanners
aureon_momentum_snowball.py             → Momentum Systems
aureon_queen_hive_mind.py               → Neural Networks
aureon_enigma.py                        → Codebreaking & Harmonics
aureon_stargate_protocol.py             → Stargate & Quantum
```

Manual override available in future versions.

---

## 🌐 Web Dashboard Features

- **Interactive graph** with physics simulation
- **Category filtering** (12 filters)
- **Real-time search**
- **Node details sidebar**
- **Dashboard launcher** (click star nodes)
- **Color-coded legend**
- **Quick links** to all dashboards
- **Responsive design**

---

## 📈 Statistics Tracked

- Total systems count
- Systems per category
- Total lines of code
- Dashboard count
- ThoughtBus integration count
- Queen integration count
- Sacred frequency usage

---

## 🔮 Future Enhancements

- [ ] Real-time system health monitoring
- [ ] Live process detection (running/stopped)
- [ ] Auto-refresh on file changes
- [ ] Export to PNG/SVG
- [ ] Integration with `aureon_live_systems_monitor.py`
- [ ] Performance metrics per system
- [ ] Code complexity analysis
- [ ] Test coverage integration
- [ ] Git history tracking

---

## 🤝 Integration Points

### With ThoughtBus
```python
from aureon_thought_bus import ThoughtBus

bus = ThoughtBus()
bus.emit(Thought(
    source="SystemHub",
    type="system_registered",
    data={"system": "aureon_whale_profiler", "category": "Intelligence"}
))
```

### With Queen Hive
```python
# Queen receives hub events for decision-making
queen.on_system_registered(system_info)
```

---

## 📖 CLI Commands Reference

| Command | Description | Example |
|---------|-------------|---------|
| `scan` | Scan workspace | `python aureon_system_hub_cli.py scan` |
| `list [category]` | List systems | `python aureon_system_hub_cli.py list "Intelligence"` |
| `search <term>` | Search systems | `python aureon_system_hub_cli.py search whale` |
| `stats` | Show statistics | `python aureon_system_hub_cli.py stats` |
| `info <system>` | System details | `python aureon_system_hub_cli.py info aureon_brain` |
| `map` | ASCII mind map | `python aureon_system_hub_cli.py map` |
| `launch` | Web dashboard | `python aureon_system_hub_cli.py launch` |

---

## 🎨 Color Scheme

Each category has a unique color in the mind map:
- 🕵️ Intelligence: `#FF6B6B` (Red)
- 📊 Scanners: `#4ECDC4` (Teal)
- 🤖 Bot Tracking: `#45B7D1` (Blue)
- ⚡ Momentum: `#FFA07A` (Orange)
- 🎯 Probability: `#98D8C8` (Mint)
- 🧠 Neural: `#F7B731` (Gold)
- 🔐 Harmonics: `#A29BFE` (Purple)
- 🌌 Quantum: `#6C5CE7` (Deep Purple)
- 📈 Dashboards: `#FD79A8` (Pink)
- 🔗 Communication: `#FDCB6E` (Yellow)
- ⚙️ Execution: `#00B894` (Green)
- 🌍 Exchanges: `#74B9FF` (Light Blue)

---

**Created by:** Aureon Trading System  
**Date:** January 2026  
**Version:** 1.0.0
