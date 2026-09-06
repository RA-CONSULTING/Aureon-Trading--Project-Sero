/**
 * 💰 TREND FOLLOWER - NEVER FIGHT THE TREND 💰
 * 
 * "The trend is your friend until it ends"
 * 
 *   ╔═══════════════════════════════════════════════════════════════════════════╗
 *   ║   RULES:                                                                  ║
 *   ║   1. Only LONG when price is RISING (last 3 ticks up)                    ║
 *   ║   2. Only SHORT when price is FALLING (last 3 ticks down)               ║
 *   ║   3. Exit IMMEDIATELY when trend reverses                                ║
 *   ║   4. Trail stops to lock in profits                                      ║
 *   ║                                                                           ║
 *   ╚═══════════════════════════════════════════════════════════════════════════╝
 * 
 * Author: Gary Leckey - R&A Consulting
 */

import * as dotenv from 'dotenv';
import * as path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

dotenv.config({ path: path.join(__dirname, '..', '.env') });

// ═══════════════════════════════════════════════════════════════════════════
// BROKER FEES (Low-fee brokers only)
// ═══════════════════════════════════════════════════════════════════════════

const BROKER_FEES: Record<string, { fee: number; taxFree: boolean }> = {
  'Binance':  { fee: 0.10, taxFree: false },  // 0.10% per trade
  'OKX':      { fee: 0.10, taxFree: false },  // 0.10%
  'Kraken':   { fee: 0.26, taxFree: false },  // 0.26%
  'OANDA':    { fee: 0.01, taxFree: false },  // Spread only
  'FXCM':     { fee: 0.015, taxFree: false }, // Spread only
  'IG':       { fee: 0.03, taxFree: true },   // 🎁 TAX FREE
  'CMC':      { fee: 0.03, taxFree: true },   // 🎁 TAX FREE
  'Capital':  { fee: 0.02, taxFree: false },
};

// ═══════════════════════════════════════════════════════════════════════════
// Configuration
// ═══════════════════════════════════════════════════════════════════════════

const CONFIG = {
  BALANCE_PER_BROKER: 20,
  POSITION_SIZE_PCT: 0.20,   // 20% = £4 per trade (bigger to make profits meaningful)
  
  STOP_LOSS_PCT: 0.01,       // 1% stop loss - cut losers fast!
  TAKE_PROFIT_PCT: 0.03,     // 3% take profit
  TRAILING_STOP_PCT: 0.005,  // 0.5% trailing stop once in profit
  
  MAX_POSITIONS_PER_BROKER: 3,
  SCAN_INTERVAL_MS: 3000,    // 3 seconds - faster reaction
  
  // Trend confirmation
  MIN_TICKS_FOR_TREND: 3,    // Need 3 consecutive moves to confirm trend
  MIN_MOVE_PCT: 0.001,       // 0.001% minimum move to count as "up" or "down"
};

// ═══════════════════════════════════════════════════════════════════════════
// Types
// ═══════════════════════════════════════════════════════════════════════════

interface LivePrice {
  symbol: string;
  bid: number;
  ask: number;
  mid: number;
}

interface Position {
  broker: string;
  symbol: string;
  direction: 'LONG' | 'SHORT';
  size: number;
  entryPrice: number;
  currentPrice: number;
  highestPrice: number;   // For trailing stop
  lowestPrice: number;    // For trailing stop
  grossPnl: number;
  fees: number;
  netPnl: number;
  pnlPercent: number;
  taxFree: boolean;
}

interface BrokerState {
  name: string;
  emoji: string;
  balance: number;
  positions: number;
  wins: number;
  losses: number;
  netPnl: number;
  taxFree: boolean;
}

// ═══════════════════════════════════════════════════════════════════════════
// Trend Tracker
// ═══════════════════════════════════════════════════════════════════════════

class TrendTracker {
  private priceHistory: Map<string, number[]> = new Map();

  addPrice(key: string, price: number): void {
    if (!this.priceHistory.has(key)) {
      this.priceHistory.set(key, []);
    }
    const history = this.priceHistory.get(key)!;
    history.push(price);
    if (history.length > 20) history.shift();
  }

  // Returns 'UP', 'DOWN', or 'FLAT'
  getTrend(key: string): 'UP' | 'DOWN' | 'FLAT' {
    const history = this.priceHistory.get(key);
    if (!history || history.length < CONFIG.MIN_TICKS_FOR_TREND + 1) {
      return 'FLAT';
    }

    // Check last N moves
    const recent = history.slice(-CONFIG.MIN_TICKS_FOR_TREND - 1);
    let upCount = 0;
    let downCount = 0;

    for (let i = 1; i < recent.length; i++) {
      const change = (recent[i] - recent[i - 1]) / recent[i - 1];
      if (change > CONFIG.MIN_MOVE_PCT / 100) upCount++;
      else if (change < -CONFIG.MIN_MOVE_PCT / 100) downCount++;
    }

    if (upCount >= CONFIG.MIN_TICKS_FOR_TREND) return 'UP';
    if (downCount >= CONFIG.MIN_TICKS_FOR_TREND) return 'DOWN';
    return 'FLAT';
  }

  // Get momentum strength (0-100)
  getMomentum(key: string): number {
    const history = this.priceHistory.get(key);
    if (!history || history.length < 5) return 0;

    const recent = history.slice(-5);
    const oldest = recent[0];
    const newest = recent[recent.length - 1];
    const change = Math.abs((newest - oldest) / oldest) * 100;
    return Math.min(100, change * 10); // Scale to 0-100
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// Price Feeds (Simplified - Focus on fast, reliable feeds)
// ═══════════════════════════════════════════════════════════════════════════

async function fetchBinancePrices(): Promise<LivePrice[]> {
  const symbols = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'XRPUSDT', 'DOGEUSDT', 'BNBUSDT', 'ADAUSDT', 'AVAXUSDT'];
  
  try {
    const response = await fetch('https://api.binance.com/api/v3/ticker/bookTicker');
    if (!response.ok) return [];
    
    const data = await response.json();
    return symbols.map(sym => {
      const ticker = data.find((t: any) => t.symbol === sym);
      if (!ticker) return null;
      const bid = parseFloat(ticker.bidPrice);
      const ask = parseFloat(ticker.askPrice);
      return { symbol: sym, bid, ask, mid: (bid + ask) / 2 };
    }).filter(p => p !== null) as LivePrice[];
  } catch { return []; }
}

async function fetchOKXPrices(): Promise<LivePrice[]> {
  const symbols = ['BTC-USDT', 'ETH-USDT', 'SOL-USDT', 'XRP-USDT', 'DOGE-USDT'];
  
  try {
    const response = await fetch('https://www.okx.com/api/v5/market/tickers?instType=SPOT');
    if (!response.ok) return [];
    
    const data = await response.json();
    if (!data.data) return [];
    
    return symbols.map(sym => {
      const ticker = data.data.find((t: any) => t.instId === sym);
      if (!ticker) return null;
      const bid = parseFloat(ticker.bidPx);
      const ask = parseFloat(ticker.askPx);
      return { symbol: sym, bid, ask, mid: (bid + ask) / 2 };
    }).filter(p => p !== null) as LivePrice[];
  } catch { return []; }
}

async function fetchKrakenPrices(): Promise<LivePrice[]> {
  try {
    const response = await fetch('https://api.kraken.com/0/public/Ticker?pair=XBTUSD,ETHUSD,SOLUSD');
    if (!response.ok) return [];
    
    const data = await response.json();
    if (data.error?.length > 0) return [];
    
    const prices: LivePrice[] = [];
    for (const [key, ticker] of Object.entries(data.result) as any) {
      const bid = parseFloat(ticker.b[0]);
      const ask = parseFloat(ticker.a[0]);
      prices.push({ symbol: key, bid, ask, mid: (bid + ask) / 2 });
    }
    return prices;
  } catch { return []; }
}

// ═══════════════════════════════════════════════════════════════════════════
// Trend Follower Engine
// ═══════════════════════════════════════════════════════════════════════════

class TrendFollower {
  private tracker = new TrendTracker();
  private positions: Map<string, Position> = new Map();
  private brokers: Map<string, BrokerState> = new Map();
  private scans = 0;
  private startTime = new Date();
  private totalNetPnL = 0;
  private wins = 0;
  private losses = 0;

  constructor() {
    this.initBrokers();
  }

  private initBrokers() {
    const list = [
      { name: 'Binance', emoji: '🪙' },
      { name: 'OKX', emoji: '⭕' },
      { name: 'Kraken', emoji: '🦑' },
      { name: 'OANDA', emoji: '💱' },
      { name: 'FXCM', emoji: '💹' },
      { name: 'IG', emoji: '📈' },
      { name: 'CMC', emoji: '📉' },
      { name: 'Capital', emoji: '📊' },
    ];

    for (const b of list) {
      const fees = BROKER_FEES[b.name];
      this.brokers.set(b.name, {
        name: b.name,
        emoji: b.emoji,
        balance: CONFIG.BALANCE_PER_BROKER,
        positions: 0,
        wins: 0,
        losses: 0,
        netPnl: 0,
        taxFree: fees?.taxFree || false
      });
    }
  }

  async start(): Promise<void> {
    this.printHeader();
    
    console.log('\n  📡 Building price history (need 4+ ticks before trading)...\n');
    
    while (true) {
      this.scans++;
      await this.executeScan();
      
      if (this.scans % 2 === 0) { // Display every 2 scans to reduce spam
        this.displayStatus();
      }
      
      await new Promise(r => setTimeout(r, CONFIG.SCAN_INTERVAL_MS));
    }
  }

  private async executeScan(): Promise<void> {
    const [binance, okx, kraken] = await Promise.all([
      fetchBinancePrices(),
      fetchOKXPrices(),
      fetchKrakenPrices()
    ]);

    this.processPrices('Binance', binance);
    this.processPrices('OKX', okx);
    this.processPrices('Kraken', kraken);
    
    // Mirror prices to forex/CFD brokers (they trade similar instruments)
    this.processPrices('OANDA', binance.slice(0, 3));
    this.processPrices('FXCM', binance.slice(0, 3));
    this.processPrices('IG', binance.slice(0, 3));
    this.processPrices('CMC', binance.slice(0, 3));
    this.processPrices('Capital', binance.slice(0, 3));
  }

  private processPrices(broker: string, prices: LivePrice[]): void {
    const brokerState = this.brokers.get(broker);
    if (!brokerState || prices.length === 0) return;

    for (const price of prices) {
      const key = `${broker}:${price.symbol}`;
      
      // Track price
      this.tracker.addPrice(key, price.mid);
      
      // Update existing position
      if (this.positions.has(key)) {
        this.updatePosition(key, price);
        continue;
      }
      
      // Check if we can open new position
      if (brokerState.positions >= CONFIG.MAX_POSITIONS_PER_BROKER) continue;
      
      // Get trend
      const trend = this.tracker.getTrend(key);
      const momentum = this.tracker.getMomentum(key);
      
      // Only enter on CONFIRMED trend with momentum
      if (trend === 'UP' && momentum > 10) {
        this.openPosition(broker, price, 'LONG', momentum);
      } else if (trend === 'DOWN' && momentum > 10) {
        this.openPosition(broker, price, 'SHORT', momentum);
      }
    }
  }

  private openPosition(broker: string, price: LivePrice, direction: 'LONG' | 'SHORT', momentum: number): void {
    const brokerState = this.brokers.get(broker);
    if (!brokerState) return;
    
    const key = `${broker}:${price.symbol}`;
    const entryPrice = direction === 'LONG' ? price.ask : price.bid;
    const tradeValue = brokerState.balance * CONFIG.POSITION_SIZE_PCT;
    const size = tradeValue / entryPrice;
    
    const fee = BROKER_FEES[broker]?.fee || 0.1;
    const entryFee = tradeValue * (fee / 100);
    
    this.positions.set(key, {
      broker,
      symbol: price.symbol,
      direction,
      size,
      entryPrice,
      currentPrice: price.mid,
      highestPrice: price.mid,
      lowestPrice: price.mid,
      grossPnl: 0,
      fees: entryFee,
      netPnl: -entryFee,
      pnlPercent: 0,
      taxFree: brokerState.taxFree
    });
    
    brokerState.positions++;
    
    const dirEmoji = direction === 'LONG' ? '🟢⬆️' : '🔴⬇️';
    const taxLabel = brokerState.taxFree ? ' 🎁' : '';
    const priceStr = price.mid > 100 ? price.mid.toFixed(2) : price.mid.toFixed(4);
    console.log(`  ${brokerState.emoji} ${dirEmoji} ENTER ${price.symbol} @ ${priceStr} (momentum: ${momentum.toFixed(0)}%)${taxLabel}`);
  }

  private updatePosition(key: string, price: LivePrice): void {
    const pos = this.positions.get(key);
    if (!pos) return;
    
    const brokerState = this.brokers.get(pos.broker);
    if (!brokerState) return;
    
    pos.currentPrice = price.mid;
    
    // Track high/low for trailing stop
    if (price.mid > pos.highestPrice) pos.highestPrice = price.mid;
    if (price.mid < pos.lowestPrice) pos.lowestPrice = price.mid;
    
    // Calculate P&L
    const priceDiff = price.mid - pos.entryPrice;
    const multiplier = pos.direction === 'LONG' ? 1 : -1;
    pos.grossPnl = priceDiff * pos.size * multiplier;
    pos.pnlPercent = (priceDiff / pos.entryPrice) * 100 * multiplier;
    
    // Exit fee
    const tradeValue = pos.size * pos.entryPrice;
    const fee = BROKER_FEES[pos.broker]?.fee || 0.1;
    const totalFees = tradeValue * (fee / 100) * 2; // Entry + Exit
    pos.fees = totalFees;
    pos.netPnl = pos.grossPnl - totalFees;
    
    const netPnlPercent = (pos.netPnl / tradeValue) * 100;
    
    // Check current trend - EXIT if trend reverses!
    const trend = this.tracker.getTrend(key);
    const trendReversed = (pos.direction === 'LONG' && trend === 'DOWN') ||
                          (pos.direction === 'SHORT' && trend === 'UP');
    
    // EXIT CONDITIONS:
    
    // 1. Stop Loss hit
    if (netPnlPercent <= -CONFIG.STOP_LOSS_PCT * 100) {
      this.closePosition(key, 'STOP');
      return;
    }
    
    // 2. Take Profit hit
    if (netPnlPercent >= CONFIG.TAKE_PROFIT_PCT * 100) {
      this.closePosition(key, 'TP');
      return;
    }
    
    // 3. Trend reversed - exit immediately!
    if (trendReversed && pos.grossPnl > 0) {
      this.closePosition(key, 'TREND');
      return;
    }
    
    // 4. Trailing stop (once in profit)
    if (pos.netPnl > 0) {
      if (pos.direction === 'LONG') {
        const trailStop = pos.highestPrice * (1 - CONFIG.TRAILING_STOP_PCT);
        if (price.mid < trailStop) {
          this.closePosition(key, 'TRAIL');
          return;
        }
      } else {
        const trailStop = pos.lowestPrice * (1 + CONFIG.TRAILING_STOP_PCT);
        if (price.mid > trailStop) {
          this.closePosition(key, 'TRAIL');
          return;
        }
      }
    }
  }

  private closePosition(key: string, reason: string): void {
    const pos = this.positions.get(key);
    if (!pos) return;
    
    const brokerState = this.brokers.get(pos.broker);
    if (!brokerState) return;
    
    brokerState.balance += pos.netPnl;
    brokerState.netPnl += pos.netPnl;
    this.totalNetPnL += pos.netPnl;
    
    if (pos.netPnl >= 0) {
      brokerState.wins++;
      this.wins++;
    } else {
      brokerState.losses++;
      this.losses++;
    }
    
    brokerState.positions--;
    
    const emoji = pos.netPnl >= 0 ? '✅' : '❌';
    const taxLabel = pos.taxFree && pos.netPnl > 0 ? ' 🎁TAX FREE!' : '';
    const netStr = pos.netPnl >= 0 ? `+£${pos.netPnl.toFixed(4)}` : `-£${Math.abs(pos.netPnl).toFixed(4)}`;
    console.log(`  ${brokerState.emoji} ${emoji} ${reason}: ${pos.symbol} | NET: ${netStr}${taxLabel}`);
    
    this.positions.delete(key);
  }

  private printHeader(): void {
    console.log('\n');
    console.log('  ╔═══════════════════════════════════════════════════════════════════════════════╗');
    console.log('  ║                                                                               ║');
    console.log('  ║   💰 TREND FOLLOWER - "Never Fight The Trend" 💰                              ║');
    console.log('  ║                                                                               ║');
    console.log('  ╠═══════════════════════════════════════════════════════════════════════════════╣');
    console.log('  ║                                                                               ║');
    console.log('  ║   RULES:                                                                      ║');
    console.log('  ║   ✅ Only LONG when price is RISING                                          ║');
    console.log('  ║   ✅ Only SHORT when price is FALLING                                        ║');
    console.log('  ║   ✅ Exit when trend REVERSES                                                ║');
    console.log('  ║   ✅ Trail stops to lock in profits                                          ║');
    console.log('  ║                                                                               ║');
    console.log('  ║   🎁 TAX FREE: 📈 IG  📉 CMC (UK Spread Betting)                             ║');
    console.log('  ║                                                                               ║');
    console.log('  ╚═══════════════════════════════════════════════════════════════════════════════╝');
    console.log('');
    console.log(`  ⚙️  SL: ${CONFIG.STOP_LOSS_PCT * 100}% | TP: ${CONFIG.TAKE_PROFIT_PCT * 100}% | Trail: ${CONFIG.TRAILING_STOP_PCT * 100}% | Size: ${CONFIG.POSITION_SIZE_PCT * 100}%`);
    console.log('  ────────────────────────────────────────────────────────────────────────────────');
  }

  private displayStatus(): void {
    const elapsed = Math.floor((Date.now() - this.startTime.getTime()) / 1000);
    const minutes = Math.floor(elapsed / 60);
    const seconds = elapsed % 60;
    
    let totalBalance = 0;
    let totalPositions = 0;
    let taxFreePnL = 0;
    
    for (const [, state] of this.brokers) {
      totalBalance += state.balance;
      totalPositions += state.positions;
      if (state.taxFree) taxFreePnL += state.netPnl;
    }
    
    const winRate = this.wins + this.losses > 0
      ? ((this.wins / (this.wins + this.losses)) * 100).toFixed(1)
      : '0.0';
    
    const totalEmoji = this.totalNetPnL >= 0 ? '🟢' : '🔴';
    const totalStr = this.totalNetPnL >= 0 
      ? `+£${this.totalNetPnL.toFixed(4)}` 
      : `-£${Math.abs(this.totalNetPnL).toFixed(4)}`;
    
    console.log('');
    console.log('  ┌──────────────────────────────────────────────────────────────────────────────┐');
    console.log(`  │  SCAN #${this.scans.toString().padStart(4)} │ Time: ${minutes}m ${seconds}s │ Pos: ${totalPositions}/${8 * CONFIG.MAX_POSITIONS_PER_BROKER} │ W/L: ${this.wins}/${this.losses} (${winRate}%)  │`);
    console.log('  ├──────────────────────────────────────────────────────────────────────────────┤');
    
    for (const [, state] of this.brokers) {
      const pnlStr = state.netPnl >= 0 ? `+£${state.netPnl.toFixed(2)}` : `-£${Math.abs(state.netPnl).toFixed(2)}`;
      const emoji = state.netPnl >= 0 ? '🟢' : '🔴';
      const tax = state.taxFree ? '🎁' : '  ';
      console.log(`  │ ${state.emoji} ${state.name.padEnd(8)} │ £${state.balance.toFixed(2).padStart(6)} │ ${state.positions}/${CONFIG.MAX_POSITIONS_PER_BROKER} │ ${emoji} ${pnlStr.padStart(9)} │ ${tax} │`);
    }
    
    console.log('  ├──────────────────────────────────────────────────────────────────────────────┤');
    console.log(`  │ 💰 TOTAL    │ £${totalBalance.toFixed(2).padStart(6)} │    │ ${totalEmoji} ${totalStr.padStart(9)} │    │`);
    console.log('  └──────────────────────────────────────────────────────────────────────────────┘');
    
    if (taxFreePnL !== 0) {
      const taxStr = taxFreePnL >= 0 ? `+£${taxFreePnL.toFixed(4)}` : `-£${Math.abs(taxFreePnL).toFixed(4)}`;
      console.log(`  🎁 Tax-Free P&L (IG+CMC): ${taxStr}`);
    }
    
    // Show positions
    const allPos = Array.from(this.positions.values());
    if (allPos.length > 0) {
      console.log('');
      console.log('  📊 Active Positions:');
      for (const pos of allPos.sort((a, b) => b.netPnl - a.netPnl).slice(0, 8)) {
        const emoji = pos.netPnl >= 0 ? '🟢' : '🔴';
        const dir = pos.direction === 'LONG' ? '⬆' : '⬇';
        const trend = this.tracker.getTrend(`${pos.broker}:${pos.symbol}`);
        const trendEmoji = trend === 'UP' ? '📈' : trend === 'DOWN' ? '📉' : '➡️';
        const netStr = pos.netPnl >= 0 ? `+£${pos.netPnl.toFixed(4)}` : `-£${Math.abs(pos.netPnl).toFixed(4)}`;
        const state = this.brokers.get(pos.broker);
        console.log(`     ${state?.emoji} ${emoji} ${pos.symbol.padEnd(10)} ${dir} ${trendEmoji} NET: ${netStr}`);
      }
    } else {
      console.log('');
      console.log('  ⏳ Waiting for trend confirmation...');
    }
    
    console.log('');
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// Main
// ═══════════════════════════════════════════════════════════════════════════

async function main() {
  console.log(`
  ╔═══════════════════════════════════════════════════════════════════════════════╗
  ║                                                                               ║
  ║   💰 TREND FOLLOWER - FOLLOW THE MONEY 💰                                     ║
  ║                                                                               ║
  ║   "The trend is your friend until it ends"                                   ║
  ║                                                                               ║
  ║   • LONG only when price RISING                                              ║
  ║   • SHORT only when price FALLING                                            ║
  ║   • Exit when trend reverses                                                 ║
  ║   • Trail stops to lock profits                                              ║
  ║                                                                               ║
  ║   Low-fee brokers only:                                                      ║
  ║   🪙 Binance (0.1%) ⭕ OKX (0.1%) 🦑 Kraken (0.26%)                           ║
  ║   📈 IG 🎁 📉 CMC 🎁 (TAX FREE spread betting)                                ║
  ║                                                                               ║
  ╚═══════════════════════════════════════════════════════════════════════════════╝
  `);

  const follower = new TrendFollower();
  
  process.on('SIGINT', () => {
    console.log('\n  💰 Trend Follower stopped.\n');
    process.exit(0);
  });

  await follower.start();
}

main().catch(console.error);
