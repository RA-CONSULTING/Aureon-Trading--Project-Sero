#!/usr/bin/env python3
"""
🌌 AUREON SYSTEM HUB - INTEGRATION GUIDE
========================================
How to integrate your new systems with the hub.

Author: Aureon Trading System
Date: January 2026
"""

from aureon_baton_link import link_system as _baton_link; _baton_link(__name__)
# =============================================================================
# AUTOMATIC CATEGORIZATION RULES
# =============================================================================

"""
The System Hub automatically categorizes files based on naming patterns:

INTELLIGENCE GATHERERS
├── Files matching: *intelligence*, *profiler*, *bot_*, *firm*, *whale*, *counter*
├── Examples: aureon_bot_intelligence_profiler.py, aureon_whale_profiler.py
└── Purpose: Bot/Firm/Whale detection and tracking

MARKET SCANNERS
├── Files matching: *scanner*, *wave*, *ocean*, *mega*, *sweep*
├── Examples: aureon_global_wave_scanner.py, aureon_ocean_scanner.py
└── Purpose: Market analysis and opportunity detection

BOT TRACKING
├── Files matching: *bot_hunter*, *bot_shape*, *bot_map*, *bot_entity*
├── Examples: aureon_bot_hunter_dashboard.py, aureon_bot_shape_scanner.py
└── Purpose: Bot tracking and visualization

MOMENTUM SYSTEMS
├── Files matching: *momentum*, *animal*, *compound*, *kelly*
├── Examples: aureon_momentum_snowball.py, aureon_animal_momentum_scanners.py
└── Purpose: Momentum detection and compounding strategies

PROBABILITY & PREDICTION
├── Files matching: *probability*, *nexus*, *prediction*, *validation*
├── Examples: aureon_probability_nexus.py, aureon_nexus.py
└── Purpose: Prediction and validation systems

NEURAL NETWORKS
├── Files matching: *queen*, *neuron*, *mycelium*, *elephant*, *brain*, *learning*
├── Examples: aureon_queen_hive_mind.py, aureon_elephant_learning.py
└── Purpose: AI/ML systems and learning mechanisms

CODEBREAKING & HARMONICS
├── Files matching: *enigma*, *harmonic*, *signal*, *cipher*
├── Examples: aureon_enigma.py, aureon_harmonic_chain_master.py
└── Purpose: Signal processing and frequency analysis

STARGATE & QUANTUM
├── Files matching: *stargate*, *quantum*, *timeline*, *mirror*
├── Examples: aureon_stargate_protocol.py, aureon_quantum_telescope.py
└── Purpose: Quantum systems and timeline anchoring

DASHBOARDS
├── Files matching: *dashboard* or contains Flask/app.run
├── Examples: aureon_command_center.py, aureon_bot_hunter_dashboard.py
└── Purpose: Web interfaces and visualizations

COMMUNICATION
├── Files matching: *bus*, *bridge*, *hub*, *orchestrator*
├── Examples: aureon_thought_bus.py, aureon_frontend_bridge.py
└── Purpose: Inter-system communication

EXECUTION ENGINES
├── Files matching: *execution*, *labyrinth*, *profit*, *gate*, *trader*
├── Examples: micro_profit_labyrinth.py, adaptive_prime_profit_gate.py
└── Purpose: Trading execution and profit management

EXCHANGE CLIENTS
├── Files matching: *client*
├── Examples: kraken_client.py, binance_client.py, alpaca_client.py
└── Purpose: Exchange API integrations
"""


# =============================================================================
# HOW TO ENSURE YOUR SYSTEM IS DISCOVERED
# =============================================================================

def example_system_template():
    """
    Template for creating a new system that will be auto-discovered.
    """
    
    # Step 1: Use proper naming convention
    # - Start with 'aureon_' prefix
    # - Include category keyword (see patterns above)
    # - Use underscores, not hyphens
    
    # GOOD EXAMPLES:
    # ✅ aureon_stellar_intelligence.py → Intelligence Gatherers
    # ✅ aureon_momentum_hunter.py → Momentum Systems
    # ✅ aureon_quantum_gate.py → Stargate & Quantum
    
    # BAD EXAMPLES:
    # ❌ my_script.py → Will be categorized as Communication (default)
    # ❌ test_something.py → Will be IGNORED (test prefix)
    
    pass


# =============================================================================
# INTEGRATIONS TO MAXIMIZE HUB BENEFITS
# =============================================================================

def integration_checklist():
    """
    Checklist for integrating with System Hub features:
    
    1. ADD DOCSTRING (Module-level)
       ✓ First line becomes description in registry
       ✓ Keep it concise (< 200 chars)
       
    2. THOUGHT BUS INTEGRATION (Optional but recommended)
       ✓ Import: from aureon_thought_bus import ThoughtBus
       ✓ Emit events: bus.emit(Thought(...))
       ✓ Hub will detect and mark as "ThoughtBus Integrated"
       
    3. QUEEN INTEGRATION (For decision systems)
       ✓ Reference: queen, hive, sero in your code
       ✓ Hub will mark as "Queen Integrated"
       
    4. DASHBOARD PORT (For Flask apps)
       ✓ Add: app.run(port=XXXX)
       ✓ Hub will extract port number automatically
       
    5. SACRED FREQUENCIES (For harmonic systems)
       ✓ Use constants: 528 (Love), 7.83 (Schumann), 432, 396, PHI (1.618)
       ✓ Hub tracks frequency usage across systems
       
    6. IMPORTS (Clean dependencies)
       ✓ Import other aureon_* modules
       ✓ Hub will map dependency graph
    """
    pass


# =============================================================================
# EXAMPLE: WELL-INTEGRATED SYSTEM
# =============================================================================

"""
#!/usr/bin/env python3
\"\"\"
🔥 AUREON PLASMA MOMENTUM SCANNER 🔥
====================================
Detects plasma-level momentum spikes using sacred harmonics.

Author: Aureon Trading System
Date: January 2026
\"\"\"

import sys, os
if sys.platform == 'win32':
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    # ... UTF-8 wrapper code

from dataclasses import dataclass
import math

# Import other Aureon systems (creates dependency edges in hub)
from aureon_thought_bus import ThoughtBus, Thought
from aureon_queen_hive_mind import QueenHiveMind

# Sacred constants (tracked by hub)
LOVE_FREQUENCY = 528
SCHUMANN_RESONANCE = 7.83
PHI = 1.618033988749895

@dataclass
class PlasmaSpike:
    symbol: str
    momentum: float
    frequency: float
    timestamp: float

class PlasmaScanner:
    def __init__(self):
        # ThoughtBus integration (hub detects this)
        self.bus = ThoughtBus()
        
        # Queen integration (hub detects this)
        self.queen = QueenHiveMind()
    
    def scan(self):
        # Your scanning logic here
        pass
    
    def emit_signal(self, spike: PlasmaSpike):
        # Emit to ThoughtBus
        self.bus.emit(Thought(
            source="PlasmaScanner",
            type="momentum_spike",
            data={"symbol": spike.symbol, "momentum": spike.momentum}
        ))
        
        # Ask Queen
        guidance = self.queen.evaluate_opportunity(spike)
        return guidance

if __name__ == "__main__":
    scanner = PlasmaScanner()
    scanner.scan()
\"\"\"

THIS FILE WOULD BE CATEGORIZED AS:
✅ Category: Momentum Systems (has 'momentum' in name)
✅ ThoughtBus: Yes (imports and uses ThoughtBus)
✅ Queen: Yes (imports and uses QueenHiveMind)
✅ Sacred Frequencies: [528, 7.83, 1.618]
✅ Dependencies: aureon_thought_bus, aureon_queen_hive_mind
"""


# =============================================================================
# DASHBOARD INTEGRATION
# =============================================================================

"""
For Flask dashboards, hub will detect port and create clickable links:

from flask import Flask, render_template

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

if __name__ == "__main__":
    # Hub extracts port automatically
    app.run(host='0.0.0.0', port=13002, debug=False)

THIS CREATES:
✅ is_dashboard: True
✅ dashboard_port: 13002
✅ Clickable link in mind map
✅ Listed in dashboard links panel
"""


# =============================================================================
# MANUAL OVERRIDE (IF NEEDED)
# =============================================================================

"""
If automatic categorization is wrong, you can manually override by creating:

aureon_system_hub_config.json:
{
  "overrides": {
    "my_weird_system": "Neural Networks",
    "another_system": "Intelligence Gatherers"
  }
}

(Not yet implemented - future enhancement)
"""


# =============================================================================
# BEST PRACTICES
# =============================================================================

"""
DO:
✅ Use descriptive docstrings
✅ Follow naming conventions
✅ Import other aureon_* modules where appropriate
✅ Integrate with ThoughtBus for events
✅ Integrate with Queen for decisions
✅ Use sacred constants (528, 7.83, PHI, etc.)
✅ Keep LOC reasonable (< 5000 lines per file)
✅ Add your dashboard to game launcher if it's user-facing

DON'T:
❌ Use test_ prefix (will be ignored)
❌ Use hyphens in filenames (use underscores)
❌ Hardcode values that should be constants
❌ Create circular imports
❌ Skip the UTF-8 wrapper on Windows
❌ Forget to document port numbers for dashboards
"""


# =============================================================================
# TESTING YOUR INTEGRATION
# =============================================================================

"""
After creating your new system:

1. Scan workspace:
   python aureon_system_hub.py

2. Verify categorization:
   python aureon_system_hub_cli.py search your_system_name

3. Check details:
   python aureon_system_hub_cli.py info your_system_name

4. View in mind map:
   python aureon_system_hub_dashboard.py
   (Open http://localhost:13001)

5. Launch with game launcher:
   python aureon_game_launcher.py --system-hub
"""


# =============================================================================
# UPDATING THE HUB
# =============================================================================

"""
The hub registry is regenerated every time you run:
- python aureon_system_hub.py
- python aureon_system_hub_cli.py [any command]
- python aureon_system_hub_dashboard.py

Changes to files are auto-detected.
No manual updates needed!

To force refresh while dashboard is running:
- Stop dashboard (Ctrl+C)
- Run: python aureon_system_hub.py
- Restart: python aureon_system_hub_dashboard.py
"""


# =============================================================================
# METRICS TRACKED
# =============================================================================

"""
For each system, the hub tracks:

BASIC INFO:
- Name (filename without .py)
- Filepath (relative to workspace)
- Category (auto-detected)
- Description (first line of docstring)

CODE METRICS:
- Lines of code (excluding comments/blanks)
- Last modified timestamp
- Import count

INTEGRATION STATUS:
- ThoughtBus: Yes/No
- Queen: Yes/No
- Dashboard: Yes/No
- Dashboard port: Number or None

ADVANCED:
- Sacred frequencies used
- Dependencies (imported aureon modules)
- Import graph edges
"""


# =============================================================================
# CONTRIBUTING NEW CATEGORIES
# =============================================================================

"""
To add a new category:

1. Edit aureon_system_hub.py
2. Add to _initialize_categories():

{
    "name": "Your New Category",
    "description": "What this category does",
    "color": "#HEX_COLOR",  # Choose from color palette
    "icon": "🔥"  # Pick an emoji
}

3. Update _categorize_system() with detection logic:

if any(x in name for x in ['your_pattern', 'another_pattern']):
    return "Your New Category"

4. Re-scan workspace:
   python aureon_system_hub.py
"""


# =============================================================================
# TROUBLESHOOTING
# =============================================================================

"""
ISSUE: My system isn't showing up
FIX: Check filename - must end in .py and not start with test_ or __

ISSUE: Wrong category
FIX: Rename file to include category keyword, or add manual override

ISSUE: ThoughtBus not detected
FIX: Ensure you import aureon_thought_bus or use 'ThoughtBus' in code

ISSUE: Queen not detected
FIX: Must have both 'queen' AND ('hive' OR 'sero') in code

ISSUE: Dashboard port not detected
FIX: Use format: port=XXXX or app.run(..., port=XXXX)

ISSUE: Sacred frequencies not showing
FIX: Use exact patterns: 528, 7.83, 432, 396, 1.618, PHI

ISSUE: Dashboard won't start
FIX: Check if port is already in use, try different port
"""


# =============================================================================
# REFERENCE: FULL SYSTEM ARCHITECTURE
# =============================================================================

"""
Aureon Trading System (197 systems, 162,893 LOC)
│
├── Intelligence Gatherers (31 systems) 🕵️
│   ├── Bot Intelligence
│   ├── Firm Intelligence
│   ├── Whale Tracking
│   └── Counter-Intelligence
│
├── Market Scanners (14 systems) 📊
│   ├── Wave Scanners
│   ├── Ocean Scanners
│   └── Mega Scanners
│
├── Bot Tracking (0 systems) 🤖
│   └── (Pattern reserved for future use)
│
├── Momentum Systems (3 systems) ⚡
│   ├── Animal-themed hunters
│   └── Compounding systems
│
├── Probability & Prediction (2 systems) 🎯
│   ├── Probability Nexus
│   └── Validation systems
│
├── Neural Networks (14 systems) 🧠
│   ├── Queen Hive Mind
│   ├── Mycelium Network
│   ├── Elephant Memory
│   └── Brain Systems
│
├── Codebreaking & Harmonics (12 systems) 🔐
│   ├── Enigma System
│   ├── Harmonic Chains
│   └── Signal Processing
│
├── Stargate & Quantum (10 systems) 🌌
│   ├── Stargate Protocol
│   ├── Quantum Telescopes
│   └── Timeline Anchoring
│
├── Dashboards (4 systems) 📈
│   ├── Command Center
│   ├── Bot Hunter
│   ├── Surveillance
│   └── System Hub (this!)
│
├── Communication (91 systems) 🔗
│   ├── ThoughtBus
│   ├── Bridges
│   ├── Hubs
│   └── Orchestrators
│
├── Execution Engines (9 systems) ⚙️
│   ├── Trading Engines
│   ├── Profit Gates
│   └── Order Routing
│
└── Exchange Clients (7 systems) 🌍
    ├── Kraken
    ├── Binance
    ├── Alpaca
    └── Capital.com
"""


if __name__ == "__main__":
    print(__doc__)
    print("\nFor more information, see:")
    print("  - SYSTEM_HUB_README.md")
    print("  - aureon_system_hub.py")
    print("  - aureon_system_hub_dashboard.py")
    print("  - aureon_system_hub_cli.py")
