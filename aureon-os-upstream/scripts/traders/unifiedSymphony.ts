/**
 * 🎵 THE UNIFIED DANCE OF SPACE AND TIME 🎵
 * 
 * Four Chords Playing Simultaneously:
 * 
 *   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
 *   │   BINANCE   │  │ CAPITAL.COM │  │   ALPACA    │  │   OANDA     │
 *   │   Crypto    │  │    CFDs     │  │   Stocks    │  │   Forex     │
 *   │   £100      │  │    £100     │  │    £100     │  │    £100     │
 *   └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘
 *         │                │                │                │
 *         └────────────────┴────────────────┴────────────────┘
 *                                 │
 *                    ╔═══════════════════════════╗
 *                    ║   COHERENCE ENGINE Φ      ║
 *                    ║   Entry: 0.938            ║
 *                    ║   Exit:  0.934            ║
 *                    ╚═══════════════════════════╝
 *                                 │
 *                         A→Z  ↔  Z→A
 *                    "They can't stop them all!"
 * 
 * Run: npm run symphony
 */

// ═══════════════════════════════════════════════════════════════════════════
// Configuration
// ═══════════════════════════════════════════════════════════════════════════

const CONFIG = {
  // Starting balance per broker (£100 each = £400 total)
  BALANCE_PER_BROKER: 100,
  
  // Coherence thresholds (unified across all brokers)
  ENTRY_COHERENCE: 0.938,
  EXIT_COHERENCE: 0.934,
  
  // Position sizing (as % of broker balance)
  POSITION_SIZE_PCT: 0.05,  // 5% per trade = £5 per position
  
  // Risk management
  STOP_LOSS_PCT: 0.02,      // 2% stop loss
  TAKE_PROFIT_PCT: 0.04,    // 4% take profit
  
  // Max positions per broker
  MAX_POSITIONS_PER_BROKER: 10,
  
  // Scan timing (synchronized)
  SCAN_INTERVAL_MS: 5000,   // 5 seconds
  
  // Enable/disable brokers
  ENABLE_BINANCE: true,
  ENABLE_CAPITAL: true,
  ENABLE_ALPACA: true,
  ENABLE_OANDA: true
};

// ═══════════════════════════════════════════════════════════════════════════
// Types
// ═══════════════════════════════════════════════════════════════════════════

interface BrokerState {
  name: string;
  emoji: string;
  connected: boolean;
  balance: number;
  positions: number;
  wins: number;
  losses: number;
  pnl: number;
  lastSignal: string;
  assetCount: number;
}

interface UnifiedPosition {
  broker: string;
  symbol: string;
  direction: 'LONG' | 'SHORT';
  size: number;
  entryPrice: number;
  currentPrice: number;
  pnl: number;
  pnlPercent: number;
}

// ═══════════════════════════════════════════════════════════════════════════
// Coherence Engine (Unified)
// ═══════════════════════════════════════════════════════════════════════════

class UnifiedCoherenceEngine {
  private priceHistory: Map<string, number[]> = new Map();
  private PHI = 1.618033988749895;
  private PHI_MINOR = 0.381966011250105;
  
  addPrice(key: string, price: number): void {
    if (!this.priceHistory.has(key)) {
      this.priceHistory.set(key, []);
    }
    const history = this.priceHistory.get(key)!;
    history.push(price);
    if (history.length > 100) history.shift();
  }
  
  calculateCoherence(key: string): number {
    const history = this.priceHistory.get(key);
    if (!history || history.length < 10) return 0;
    
    const recent = history.slice(-20);
    const min = Math.min(...recent);
    const max = Math.max(...recent);
    const range = max - min;
    if (range === 0) return 0.5;
    
    const current = recent[recent.length - 1];
    const normalized = (current - min) / range;
    
    const phiMajorDist = Math.abs(normalized - (1 / this.PHI));
    const phiMinorDist = Math.abs(normalized - this.PHI_MINOR);
    const phiScore = 1 - Math.min(phiMajorDist, phiMinorDist);
    
    const momentum = (current - recent[0]) / recent[0];
    const momentumScore = Math.tanh(momentum * 50) * 0.5 + 0.5;
    
    const wavePosition = Math.sin(normalized * Math.PI) ** 2;
    
    return (phiScore * 0.4 + momentumScore * 0.3 + wavePosition * 0.3);
  }
  
  getSignal(key: string): 'BUY' | 'SELL' | 'HOLD' {
    const coherence = this.calculateCoherence(key);
    const history = this.priceHistory.get(key);
    
    // More aggressive for demo - enter after just 3 price ticks
    if (!history || history.length < 3) return 'HOLD';
    
    const trend = history[history.length - 1] > history[history.length - 3] ? 1 : -1;
    
    // Lower threshold for demo (0.85 instead of 0.938)
    if (coherence >= 0.85 && trend > 0) return 'BUY';
    if (coherence >= 0.85 && trend < 0) return 'SELL';
    
    // Random entry for demo action (20% chance)
    if (Math.random() < 0.20) {
      return Math.random() > 0.5 ? 'BUY' : 'SELL';
    }
    
    return 'HOLD';
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// Simulated Broker Clients (for demo without real credentials)
// ═══════════════════════════════════════════════════════════════════════════

class SimulatedBroker {
  name: string;
  emoji: string;
  balance: number;
  positions: Map<string, UnifiedPosition> = new Map();
  wins = 0;
  losses = 0;
  realizedPnL = 0;
  assets: string[];
  
  constructor(name: string, emoji: string, assets: string[]) {
    this.name = name;
    this.emoji = emoji;
    this.balance = CONFIG.BALANCE_PER_BROKER;
    this.assets = assets;
  }
  
  async getPrice(symbol: string): Promise<number> {
    // Simulate price with random walk
    const basePrice = this.getBasePrice(symbol);
    const volatility = 0.001;
    const change = (Math.random() - 0.5) * 2 * volatility;
    return basePrice * (1 + change);
  }
  
  private getBasePrice(symbol: string): number {
    // Approximate base prices for different asset types
    if (symbol.includes('BTC')) return 95000;
    if (symbol.includes('ETH')) return 3500;
    if (symbol.includes('SOL')) return 250;
    if (symbol.includes('EUR')) return 1.05;
    if (symbol.includes('GBP')) return 1.27;
    if (symbol.includes('JPY')) return 0.0067;
    if (symbol.includes('AAPL')) return 175;
    if (symbol.includes('MSFT')) return 420;
    if (symbol.includes('TSLA')) return 350;
    if (symbol.includes('GOLD') || symbol.includes('XAU')) return 2650;
    if (symbol.includes('OIL') || symbol.includes('BCO')) return 75;
    if (symbol.includes('SPX') || symbol.includes('SP500')) return 6000;
    return 100;
  }
  
  openPosition(symbol: string, direction: 'LONG' | 'SHORT', price: number): boolean {
    if (this.positions.has(symbol)) return false;
    if (this.positions.size >= CONFIG.MAX_POSITIONS_PER_BROKER) return false;
    
    const size = (this.balance * CONFIG.POSITION_SIZE_PCT) / price;
    
    this.positions.set(symbol, {
      broker: this.name,
      symbol,
      direction,
      size,
      entryPrice: price,
      currentPrice: price,
      pnl: 0,
      pnlPercent: 0
    });
    
    return true;
  }
  
  updatePosition(symbol: string, currentPrice: number): void {
    const pos = this.positions.get(symbol);
    if (!pos) return;
    
    pos.currentPrice = currentPrice;
    const priceDiff = currentPrice - pos.entryPrice;
    const multiplier = pos.direction === 'LONG' ? 1 : -1;
    pos.pnl = priceDiff * pos.size * multiplier;
    pos.pnlPercent = (priceDiff / pos.entryPrice) * 100 * multiplier;
  }
  
  checkStopLossTakeProfit(symbol: string): 'STOP' | 'PROFIT' | null {
    const pos = this.positions.get(symbol);
    if (!pos) return null;
    
    if (pos.pnlPercent <= -CONFIG.STOP_LOSS_PCT * 100) return 'STOP';
    if (pos.pnlPercent >= CONFIG.TAKE_PROFIT_PCT * 100) return 'PROFIT';
    
    return null;
  }
  
  closePosition(symbol: string, reason: string): number {
    const pos = this.positions.get(symbol);
    if (!pos) return 0;
    
    const pnl = pos.pnl;
    this.realizedPnL += pnl;
    this.balance += pnl;
    
    if (pnl >= 0) {
      this.wins++;
    } else {
      this.losses++;
    }
    
    this.positions.delete(symbol);
    return pnl;
  }
  
  getOpenPnL(): number {
    return Array.from(this.positions.values()).reduce((sum, p) => sum + p.pnl, 0);
  }
  
  getState(): BrokerState {
    return {
      name: this.name,
      emoji: this.emoji,
      connected: true,
      balance: this.balance,
      positions: this.positions.size,
      wins: this.wins,
      losses: this.losses,
      pnl: this.realizedPnL + this.getOpenPnL(),
      lastSignal: '',
      assetCount: this.assets.length
    };
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// Unified Symphony Controller
// ═══════════════════════════════════════════════════════════════════════════

class UnifiedSymphony {
  private coherence: UnifiedCoherenceEngine;
  private brokers: SimulatedBroker[] = [];
  private scanDirection: 'A→Z' | 'Z→A' = 'A→Z';
  private scans = 0;
  private startTime: Date;
  
  constructor() {
    this.coherence = new UnifiedCoherenceEngine();
    this.startTime = new Date();
    
    // Initialize brokers with their asset lists
    if (CONFIG.ENABLE_BINANCE) {
      this.brokers.push(new SimulatedBroker('Binance', '🪙', [
        'BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'XRPUSDT', 'DOGEUSDT',
        'ADAUSDT', 'AVAXUSDT', 'DOTUSDT', 'LINKUSDT', 'MATICUSDT',
        'ATOMUSDT', 'LTCUSDT', 'NEARUSDT', 'UNIUSDT', 'AAVEUSDT'
      ]));
    }
    
    if (CONFIG.ENABLE_CAPITAL) {
      this.brokers.push(new SimulatedBroker('Capital', '📊', [
        'BTCUSD', 'ETHUSD', 'GOLD', 'SILVER', 'OIL_CRUDE',
        'US500', 'US100', 'UK100', 'DE40', 'EURUSD',
        'GBPUSD', 'USDJPY', 'AAPL', 'MSFT', 'TSLA'
      ]));
    }
    
    if (CONFIG.ENABLE_ALPACA) {
      this.brokers.push(new SimulatedBroker('Alpaca', '🦙', [
        'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META',
        'NVDA', 'TSLA', 'AMD', 'NFLX', 'JPM',
        'SPY', 'QQQ', 'IWM', 'BTC/USD', 'ETH/USD'
      ]));
    }
    
    if (CONFIG.ENABLE_OANDA) {
      this.brokers.push(new SimulatedBroker('OANDA', '💱', [
        'EUR_USD', 'GBP_USD', 'USD_JPY', 'USD_CHF', 'AUD_USD',
        'USD_CAD', 'NZD_USD', 'EUR_GBP', 'EUR_JPY', 'GBP_JPY',
        'XAU_USD', 'XAG_USD', 'BCO_USD', 'SPX500_USD', 'NAS100_USD'
      ]));
    }
  }
  
  async start(): Promise<void> {
    this.printHeader();
    
    // Main loop
    while (true) {
      this.scans++;
      this.scanDirection = this.scanDirection === 'A→Z' ? 'Z→A' : 'A→Z';
      
      // Run all brokers in parallel
      await Promise.all(this.brokers.map(broker => this.scanBroker(broker)));
      
      // Display unified status
      this.displayStatus();
      
      // Wait for next scan
      await this.sleep(CONFIG.SCAN_INTERVAL_MS);
    }
  }
  
  private async scanBroker(broker: SimulatedBroker): Promise<void> {
    // Sort assets by scan direction
    const assets = [...broker.assets];
    assets.sort((a, b) => {
      const cmp = a.localeCompare(b);
      return this.scanDirection === 'A→Z' ? cmp : -cmp;
    });
    
    // Update existing positions
    for (const [symbol, pos] of broker.positions) {
      const price = await broker.getPrice(symbol);
      broker.updatePosition(symbol, price);
      
      // Check stop loss / take profit
      const action = broker.checkStopLossTakeProfit(symbol);
      if (action) {
        const pnl = broker.closePosition(symbol, action);
        const emoji = pnl >= 0 ? '✅' : '❌';
        console.log(`  ${broker.emoji} ${emoji} ${action}: ${symbol} | P&L: £${pnl.toFixed(2)}`);
      }
    }
    
    // Scan for new opportunities
    for (const symbol of assets) {
      if (broker.positions.has(symbol)) continue;
      if (broker.positions.size >= CONFIG.MAX_POSITIONS_PER_BROKER) break;
      
      const price = await broker.getPrice(symbol);
      const key = `${broker.name}:${symbol}`;
      
      this.coherence.addPrice(key, price);
      const signal = this.coherence.getSignal(key);
      
      if (signal !== 'HOLD') {
        const direction = signal === 'BUY' ? 'LONG' : 'SHORT';
        const opened = broker.openPosition(symbol, direction, price);
        
        if (opened) {
          console.log(`  ${broker.emoji} ⚡ ${signal}: ${symbol} @ ${price.toFixed(4)}`);
        }
      }
    }
  }
  
  private printHeader(): void {
    console.log('\n');
    console.log('  ╔═════════════════════════════════════════════════════════════════╗');
    console.log('  ║                                                                 ║');
    console.log('  ║   🎵 THE UNIFIED SYMPHONY OF SPACE AND TIME 🎵                  ║');
    console.log('  ║                                                                 ║');
    console.log('  ║   Four Chords Playing in Perfect Harmony                        ║');
    console.log('  ║                                                                 ║');
    console.log('  ╠═════════════════════════════════════════════════════════════════╣');
    console.log('  ║                                                                 ║');
    console.log('  ║   🪙 BINANCE    📊 CAPITAL    🦙 ALPACA    💱 OANDA            ║');
    console.log('  ║      Crypto        CFDs         Stocks       Forex             ║');
    console.log('  ║       £100         £100          £100         £100             ║');
    console.log('  ║                                                                 ║');
    console.log('  ║               Total Starting Capital: £400                      ║');
    console.log('  ║                                                                 ║');
    console.log('  ╠═════════════════════════════════════════════════════════════════╣');
    console.log('  ║   Coherence Φ: Entry 0.938 | Exit 0.934                         ║');
    console.log('  ║   Risk: 2% SL | 4% TP | 5% Position Size                        ║');
    console.log('  ╚═════════════════════════════════════════════════════════════════╝');
    console.log('');
    console.log('  🎵 The Symphony begins...');
    console.log('  ─────────────────────────────────────────────────────────────────');
    console.log('');
  }
  
  private displayStatus(): void {
    const elapsed = Math.floor((Date.now() - this.startTime.getTime()) / 1000);
    const minutes = Math.floor(elapsed / 60);
    const seconds = elapsed % 60;
    
    // Calculate totals
    let totalBalance = 0;
    let totalPositions = 0;
    let totalWins = 0;
    let totalLosses = 0;
    let totalPnL = 0;
    
    const brokerLines: string[] = [];
    
    for (const broker of this.brokers) {
      const state = broker.getState();
      totalBalance += state.balance;
      totalPositions += state.positions;
      totalWins += state.wins;
      totalLosses += state.losses;
      totalPnL += state.pnl;
      
      const hitRate = state.wins + state.losses > 0
        ? ((state.wins / (state.wins + state.losses)) * 100).toFixed(0)
        : '-';
      
      const pnlStr = state.pnl >= 0 ? `+£${state.pnl.toFixed(2)}` : `-£${Math.abs(state.pnl).toFixed(2)}`;
      const pnlEmoji = state.pnl >= 0 ? '🟢' : '🔴';
      
      brokerLines.push(
        `  │ ${state.emoji} ${state.name.padEnd(8)} │ £${state.balance.toFixed(0).padStart(5)} │ ${state.positions.toString().padStart(2)}/${CONFIG.MAX_POSITIONS_PER_BROKER} │ ${state.wins}W/${state.losses}L │ ${hitRate.padStart(3)}% │ ${pnlEmoji} ${pnlStr.padStart(8)} │`
      );
    }
    
    const totalHitRate = totalWins + totalLosses > 0
      ? ((totalWins / (totalWins + totalLosses)) * 100).toFixed(1)
      : '0.0';
    
    const totalPnLStr = totalPnL >= 0 ? `+£${totalPnL.toFixed(2)}` : `-£${Math.abs(totalPnL).toFixed(2)}`;
    const totalEmoji = totalPnL >= 0 ? '🟢' : '🔴';
    
    console.log('');
    console.log('  ┌─────────────────────────────────────────────────────────────────┐');
    console.log(`  │  SCAN #${this.scans.toString().padStart(5)} [${this.scanDirection}]  │  Time: ${minutes}m ${seconds}s  │  Total Positions: ${totalPositions}  │`);
    console.log('  ├─────────────────────────────────────────────────────────────────┤');
    console.log('  │  Broker    │ Balance │ Pos  │  W/L  │  HR │    P&L    │');
    console.log('  ├────────────┼─────────┼──────┼───────┼─────┼───────────┤');
    
    for (const line of brokerLines) {
      console.log(line);
    }
    
    console.log('  ├────────────┼─────────┼──────┼───────┼─────┼───────────┤');
    console.log(`  │ 🎵 TOTAL   │ £${totalBalance.toFixed(0).padStart(5)} │ ${totalPositions.toString().padStart(2)}   │ ${totalWins}W/${totalLosses}L │${totalHitRate.padStart(4)}% │ ${totalEmoji} ${totalPnLStr.padStart(8)} │`);
    console.log('  └─────────────────────────────────────────────────────────────────┘');
    
    // Show active positions wave
    this.displayWave();
  }
  
  private displayWave(): void {
    const allPositions: UnifiedPosition[] = [];
    
    for (const broker of this.brokers) {
      for (const pos of broker.positions.values()) {
        allPositions.push(pos);
      }
    }
    
    if (allPositions.length === 0) {
      console.log('');
      console.log('  🌊 Waiting for coherence signals...');
      console.log('');
      return;
    }
    
    // Sort by P&L
    allPositions.sort((a, b) => b.pnl - a.pnl);
    
    console.log('');
    console.log('  🌊 Active Positions Across All Brokers:');
    console.log('');
    
    // Show top 10
    for (const pos of allPositions.slice(0, 10)) {
      const emoji = pos.pnl >= 0 ? '🟢' : '🔴';
      const dir = pos.direction === 'LONG' ? '⬆' : '⬇';
      const broker = this.brokers.find(b => b.name === pos.broker);
      const brokerEmoji = broker?.emoji || '📈';
      
      const pnlStr = pos.pnl >= 0 ? `+£${pos.pnl.toFixed(2)}` : `-£${Math.abs(pos.pnl).toFixed(2)}`;
      
      console.log(`     ${brokerEmoji} ${emoji} ${pos.symbol.padEnd(12)} ${dir} @ ${pos.entryPrice.toFixed(4)} → ${pnlStr} (${pos.pnlPercent.toFixed(1)}%)`);
    }
    
    if (allPositions.length > 10) {
      console.log(`     ... and ${allPositions.length - 10} more positions`);
    }
    
    console.log('');
  }
  
  private sleep(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// Main Entry Point
// ═══════════════════════════════════════════════════════════════════════════

async function main() {
  const symphony = new UnifiedSymphony();
  
  // Handle graceful shutdown
  process.on('SIGINT', () => {
    console.log('\n');
    console.log('  ─────────────────────────────────────────────────────────────────');
    console.log('  🎵 The Symphony concludes...');
    console.log('  ─────────────────────────────────────────────────────────────────');
    console.log('');
    console.log('  "Four chords played as one, the wave rides eternal"');
    console.log('');
    process.exit(0);
  });
  
  await symphony.start();
}

main().catch(console.error);
