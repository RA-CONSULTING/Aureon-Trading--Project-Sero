/**
 * 🌊 AGGRESSIVE WAVE RIDER - LIVE MARKETS 🌊
 * 
 * A→Z  ↔  Z→A  "They Can't Stop Them All!"
 * 
 *   ╔═══════════════════════════════════════════════════════════════════════════╗
 *   ║   THE WAVE RIDER STRATEGY - REAL PRICES, REAL TRADES                     ║
 *   ║                                                                           ║
 *   ║   • Scan A→Z on odd cycles, Z→A on even cycles                           ║
 *   ║   • Enter on momentum + trend alignment                                   ║
 *   ║   • Ride the wave until stop loss or take profit                         ║
 *   ║   • Survive = preserve capital with tight risk management                ║
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
// Configuration - AGGRESSIVE MODE
// ═══════════════════════════════════════════════════════════════════════════

const CONFIG = {
  BALANCE_PER_BROKER: 20,
  
  // Lower threshold for more entries with live data
  ENTRY_THRESHOLD: 0.60,   // Much lower - enter on any momentum
  MIN_HISTORY: 3,          // Only need 3 ticks to start trading
  
  // Position sizing
  POSITION_SIZE_PCT: 0.15, // 15% per trade = £3 per position
  STOP_LOSS_PCT: 0.015,    // 1.5% stop loss (tighter)
  TAKE_PROFIT_PCT: 0.03,   // 3% take profit
  
  // Max positions per broker
  MAX_POSITIONS_PER_BROKER: 5,
  
  // Faster scanning
  SCAN_INTERVAL_MS: 5000,  // 5 seconds
};

// ═══════════════════════════════════════════════════════════════════════════
// Types
// ═══════════════════════════════════════════════════════════════════════════

interface LivePrice {
  symbol: string;
  bid: number;
  ask: number;
  mid: number;
  spread: number;
  change24h?: number;
}

interface Position {
  broker: string;
  symbol: string;
  direction: 'LONG' | 'SHORT';
  size: number;
  entryPrice: number;
  currentPrice: number;
  pnl: number;
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
  pnl: number;
  taxFree: boolean;
}

// ═══════════════════════════════════════════════════════════════════════════
// Real Price Feeds
// ═══════════════════════════════════════════════════════════════════════════

// BINANCE
async function fetchBinancePrices(): Promise<LivePrice[]> {
  const symbols = [
    'BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT', 'XRPUSDT',
    'DOGEUSDT', 'ADAUSDT', 'AVAXUSDT', 'DOTUSDT', 'LINKUSDT',
    'MATICUSDT', 'LTCUSDT', 'NEARUSDT', 'UNIUSDT', 'AAVEUSDT',
    'APTUSDT', 'ARBUSDT', 'OPUSDT', 'ATOMUSDT', 'SHIBUSDT'
  ];
  
  try {
    const response = await fetch('https://api.binance.com/api/v3/ticker/24hr');
    if (!response.ok) return [];
    
    const data = await response.json();
    const prices: LivePrice[] = [];
    
    for (const sym of symbols) {
      const ticker = data.find((t: any) => t.symbol === sym);
      if (ticker) {
        const bid = parseFloat(ticker.bidPrice);
        const ask = parseFloat(ticker.askPrice);
        prices.push({
          symbol: sym,
          bid,
          ask,
          mid: (bid + ask) / 2,
          spread: ask - bid,
          change24h: parseFloat(ticker.priceChangePercent)
        });
      }
    }
    return prices;
  } catch { return []; }
}

// KRAKEN
async function fetchKrakenPrices(): Promise<LivePrice[]> {
  const pairs = 'XXBTZGBP,XETHZGBP,XXBTZUSD,XETHZUSD,SOLUSD,XRPUSD,ADAUSD,DOTUSD,LINKUSD,ATOMUSD';
  
  try {
    const response = await fetch(`https://api.kraken.com/0/public/Ticker?pair=${pairs}`);
    if (!response.ok) return [];
    
    const data = await response.json();
    if (data.error?.length > 0) return [];
    
    const prices: LivePrice[] = [];
    for (const [key, ticker] of Object.entries(data.result) as any) {
      const bid = parseFloat(ticker.b[0]);
      const ask = parseFloat(ticker.a[0]);
      const open = parseFloat(ticker.o);
      const last = parseFloat(ticker.c[0]);
      prices.push({
        symbol: key,
        bid,
        ask,
        mid: (bid + ask) / 2,
        spread: ask - bid,
        change24h: ((last - open) / open) * 100
      });
    }
    return prices;
  } catch { return []; }
}

// OKX
async function fetchOKXPrices(): Promise<LivePrice[]> {
  const symbols = [
    'BTC-USDT', 'ETH-USDT', 'SOL-USDT', 'XRP-USDT', 'DOGE-USDT',
    'ADA-USDT', 'DOT-USDT', 'AVAX-USDT', 'LINK-USDT', 'NEAR-USDT',
    'ATOM-USDT', 'UNI-USDT', 'AAVE-USDT', 'LTC-USDT', 'ARB-USDT'
  ];
  
  try {
    const response = await fetch('https://www.okx.com/api/v5/market/tickers?instType=SPOT');
    if (!response.ok) return [];
    
    const data = await response.json();
    if (!data.data) return [];
    
    const prices: LivePrice[] = [];
    for (const sym of symbols) {
      const ticker = data.data.find((t: any) => t.instId === sym);
      if (ticker) {
        const bid = parseFloat(ticker.bidPx);
        const ask = parseFloat(ticker.askPx);
        const open = parseFloat(ticker.open24h);
        const last = parseFloat(ticker.last);
        prices.push({
          symbol: sym,
          bid,
          ask,
          mid: (bid + ask) / 2,
          spread: ask - bid,
          change24h: ((last - open) / open) * 100
        });
      }
    }
    return prices;
  } catch { return []; }
}

// COINBASE
async function fetchCoinbasePrices(): Promise<LivePrice[]> {
  const symbols = ['BTC-GBP', 'ETH-GBP', 'SOL-GBP', 'BTC-USD', 'ETH-USD', 'SOL-USD', 'DOGE-USD', 'ADA-USD'];
  const prices: LivePrice[] = [];
  
  for (const sym of symbols) {
    try {
      const response = await fetch(`https://api.exchange.coinbase.com/products/${sym}/ticker`);
      if (response.ok) {
        const data = await response.json();
        const bid = parseFloat(data.bid);
        const ask = parseFloat(data.ask);
        prices.push({
          symbol: sym,
          bid,
          ask,
          mid: (bid + ask) / 2,
          spread: ask - bid
        });
      }
    } catch {}
  }
  return prices;
}

// BITSTAMP
async function fetchBitstampPrices(): Promise<LivePrice[]> {
  const symbols = ['btcgbp', 'ethgbp', 'btcusd', 'ethusd', 'xrpusd', 'ltcusd', 'solusd'];
  const prices: LivePrice[] = [];
  
  for (const sym of symbols) {
    try {
      const response = await fetch(`https://www.bitstamp.net/api/v2/ticker/${sym}/`);
      if (response.ok) {
        const data = await response.json();
        const bid = parseFloat(data.bid);
        const ask = parseFloat(data.ask);
        const open = parseFloat(data.open);
        const last = parseFloat(data.last);
        prices.push({
          symbol: sym.toUpperCase(),
          bid,
          ask,
          mid: (bid + ask) / 2,
          spread: ask - bid,
          change24h: ((last - open) / open) * 100
        });
      }
    } catch {}
  }
  return prices;
}

// FOREX (Free API)
async function fetchForexPrices(): Promise<LivePrice[]> {
  try {
    const response = await fetch('https://api.exchangerate-api.com/v4/latest/USD');
    if (!response.ok) return [];
    
    const data = await response.json();
    const prices: LivePrice[] = [];
    
    // Major pairs
    const pairs = [
      { base: 'EUR', symbol: 'EUR/USD' },
      { base: 'GBP', symbol: 'GBP/USD' },
      { base: 'JPY', symbol: 'USD/JPY' },
      { base: 'CHF', symbol: 'USD/CHF' },
      { base: 'AUD', symbol: 'AUD/USD' },
      { base: 'CAD', symbol: 'USD/CAD' },
    ];
    
    for (const pair of pairs) {
      const rate = data.rates[pair.base];
      if (rate) {
        let mid: number;
        if (pair.symbol.startsWith('USD/')) {
          mid = rate;
        } else {
          mid = 1 / rate;
        }
        const spread = mid * 0.0002;
        prices.push({
          symbol: pair.symbol,
          bid: mid - spread / 2,
          ask: mid + spread / 2,
          mid,
          spread
        });
      }
    }
    return prices;
  } catch { return []; }
}

// ═══════════════════════════════════════════════════════════════════════════
// Wave Rider Engine
// ═══════════════════════════════════════════════════════════════════════════

class WaveRiderEngine {
  private priceHistory: Map<string, number[]> = new Map();
  private PHI = 1.618033988749895;

  addPrice(key: string, price: number): void {
    if (!this.priceHistory.has(key)) {
      this.priceHistory.set(key, []);
    }
    const history = this.priceHistory.get(key)!;
    history.push(price);
    if (history.length > 50) history.shift();
  }

  getHistoryLength(key: string): number {
    return this.priceHistory.get(key)?.length || 0;
  }

  // Wave analysis - detect momentum and trend
  analyzeWave(key: string): { signal: 'BUY' | 'SELL' | 'HOLD'; strength: number; trend: string } {
    const history = this.priceHistory.get(key);
    if (!history || history.length < CONFIG.MIN_HISTORY) {
      return { signal: 'HOLD', strength: 0, trend: 'building' };
    }

    const recent = history.slice(-10);
    const current = recent[recent.length - 1];
    const previous = recent[recent.length - 2] || current;
    const oldest = recent[0];
    
    // Immediate momentum (last tick)
    const tickMomentum = (current - previous) / previous;
    
    // Short-term trend (last few ticks)
    const shortTrend = (current - oldest) / oldest;
    
    // Volatility check
    const min = Math.min(...recent);
    const max = Math.max(...recent);
    const range = max - min;
    const volatility = range / ((max + min) / 2);
    
    // Wave position (PHI levels)
    const normalized = range > 0 ? (current - min) / range : 0.5;
    const phiLevel = 1 / this.PHI; // 0.618
    const atPhiSupport = normalized < 0.4;  // Near bottom
    const atPhiResistance = normalized > 0.7;  // Near top
    
    // Signal logic based on wave position and momentum
    let signal: 'BUY' | 'SELL' | 'HOLD' = 'HOLD';
    let strength = 0;
    let trend = 'neutral';
    
    // BUY: At support with upward momentum
    if (atPhiSupport && tickMomentum > 0 && shortTrend > -0.01) {
      signal = 'BUY';
      strength = Math.min(1, Math.abs(tickMomentum) * 100 + 0.5);
      trend = 'reversal-up';
    }
    // BUY: Strong uptrend continuation
    else if (shortTrend > 0.002 && tickMomentum > 0) {
      signal = 'BUY';
      strength = Math.min(1, shortTrend * 50 + 0.3);
      trend = 'uptrend';
    }
    // SELL: At resistance with downward momentum
    else if (atPhiResistance && tickMomentum < 0 && shortTrend < 0.01) {
      signal = 'SELL';
      strength = Math.min(1, Math.abs(tickMomentum) * 100 + 0.5);
      trend = 'reversal-down';
    }
    // SELL: Strong downtrend continuation
    else if (shortTrend < -0.002 && tickMomentum < 0) {
      signal = 'SELL';
      strength = Math.min(1, Math.abs(shortTrend) * 50 + 0.3);
      trend = 'downtrend';
    }
    
    // Volatility boost
    if (volatility > 0.005 && signal !== 'HOLD') {
      strength = Math.min(1, strength + 0.2);
    }
    
    return { signal, strength, trend };
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// Aggressive Wave Rider
// ═══════════════════════════════════════════════════════════════════════════

class AggressiveWaveRider {
  private engine = new WaveRiderEngine();
  private positions: Map<string, Position> = new Map();
  private brokers: Map<string, BrokerState> = new Map();
  private scanDirection: 'A→Z' | 'Z→A' = 'A→Z';
  private scans = 0;
  private startTime = new Date();
  private totalPnL = 0;
  private wins = 0;
  private losses = 0;

  constructor() {
    this.initBrokers();
  }

  private initBrokers() {
    const brokerList = [
      { name: 'Binance', emoji: '🪙', taxFree: false },
      { name: 'Kraken', emoji: '🦑', taxFree: false },
      { name: 'Coinbase', emoji: '🟠', taxFree: false },
      { name: 'Bitstamp', emoji: '💎', taxFree: false },
      { name: 'OKX', emoji: '⭕', taxFree: false },
      { name: 'OANDA', emoji: '💱', taxFree: false },
      { name: 'FXCM', emoji: '💹', taxFree: false },
      { name: 'IG', emoji: '📈', taxFree: true },
      { name: 'CMC', emoji: '📉', taxFree: true },
      { name: 'Capital', emoji: '📊', taxFree: false },
      { name: 'Saxo', emoji: '🏦', taxFree: false },
      { name: 'IB', emoji: '🏛️', taxFree: false },
      { name: 'Alpaca', emoji: '🦙', taxFree: false },
      { name: 'Gemini', emoji: '💠', taxFree: false },
    ];

    for (const b of brokerList) {
      this.brokers.set(b.name, {
        name: b.name,
        emoji: b.emoji,
        balance: CONFIG.BALANCE_PER_BROKER,
        positions: 0,
        wins: 0,
        losses: 0,
        pnl: 0,
        taxFree: b.taxFree
      });
    }
  }

  async start(): Promise<void> {
    this.printHeader();
    
    console.log('\n  📡 Connecting to live markets...\n');
    
    while (true) {
      this.scans++;
      this.scanDirection = this.scanDirection === 'A→Z' ? 'Z→A' : 'A→Z';
      
      await this.executeScan();
      this.displayStatus();
      
      await new Promise(r => setTimeout(r, CONFIG.SCAN_INTERVAL_MS));
    }
  }

  private async executeScan(): Promise<void> {
    // Fetch all prices in parallel
    const [binance, kraken, okx, coinbase, bitstamp, forex] = await Promise.all([
      fetchBinancePrices(),
      fetchKrakenPrices(),
      fetchOKXPrices(),
      fetchCoinbasePrices(),
      fetchBitstampPrices(),
      fetchForexPrices()
    ]);

    // Sort by direction
    const sortFn = (a: LivePrice, b: LivePrice) => {
      const cmp = a.symbol.localeCompare(b.symbol);
      return this.scanDirection === 'A→Z' ? cmp : -cmp;
    };

    // Process each exchange
    this.processPrices('Binance', binance.sort(sortFn));
    this.processPrices('Kraken', kraken.sort(sortFn));
    this.processPrices('OKX', okx.sort(sortFn));
    this.processPrices('Coinbase', coinbase.sort(sortFn));
    this.processPrices('Bitstamp', bitstamp.sort(sortFn));
    
    // Forex goes to multiple brokers
    const sortedForex = forex.sort(sortFn);
    this.processPrices('OANDA', sortedForex);
    this.processPrices('FXCM', sortedForex);
    this.processPrices('IG', sortedForex);
    this.processPrices('CMC', sortedForex);
    this.processPrices('Saxo', sortedForex);
  }

  private processPrices(broker: string, prices: LivePrice[]): void {
    const brokerState = this.brokers.get(broker);
    if (!brokerState) return;

    for (const price of prices) {
      const key = `${broker}:${price.symbol}`;
      
      // Add to history
      this.engine.addPrice(key, price.mid);
      
      // Check existing position
      const existingPos = this.positions.get(key);
      if (existingPos) {
        this.updatePosition(key, price.mid);
        continue;
      }
      
      // Check if we can open new position
      if (brokerState.positions >= CONFIG.MAX_POSITIONS_PER_BROKER) continue;
      
      // Analyze wave
      const analysis = this.engine.analyzeWave(key);
      
      // Enter on signal with sufficient strength
      if (analysis.signal !== 'HOLD' && analysis.strength >= CONFIG.ENTRY_THRESHOLD) {
        this.openPosition(broker, price, analysis.signal, analysis.strength, analysis.trend);
      }
    }
  }

  private openPosition(broker: string, price: LivePrice, signal: 'BUY' | 'SELL', strength: number, trend: string): void {
    const brokerState = this.brokers.get(broker);
    if (!brokerState) return;
    
    const key = `${broker}:${price.symbol}`;
    const direction = signal === 'BUY' ? 'LONG' : 'SHORT';
    const entryPrice = signal === 'BUY' ? price.ask : price.bid;
    const size = (brokerState.balance * CONFIG.POSITION_SIZE_PCT) / entryPrice;
    
    this.positions.set(key, {
      broker,
      symbol: price.symbol,
      direction,
      size,
      entryPrice,
      currentPrice: price.mid,
      pnl: 0,
      pnlPercent: 0,
      taxFree: brokerState.taxFree
    });
    
    brokerState.positions++;
    
    const dir = this.scanDirection;
    const taxLabel = brokerState.taxFree ? ' 🎁' : '';
    const priceStr = price.mid < 10 ? price.mid.toFixed(5) : price.mid.toFixed(2);
    console.log(`  ${brokerState.emoji} [${dir}] ⚡ ${signal}: ${price.symbol} @ ${priceStr} (${trend}, ${(strength*100).toFixed(0)}%)${taxLabel}`);
  }

  private updatePosition(key: string, currentPrice: number): void {
    const pos = this.positions.get(key);
    if (!pos) return;
    
    const brokerState = this.brokers.get(pos.broker);
    if (!brokerState) return;
    
    pos.currentPrice = currentPrice;
    const priceDiff = currentPrice - pos.entryPrice;
    const multiplier = pos.direction === 'LONG' ? 1 : -1;
    pos.pnl = priceDiff * pos.size * multiplier;
    pos.pnlPercent = (priceDiff / pos.entryPrice) * 100 * multiplier;
    
    // Check stop loss
    if (pos.pnlPercent <= -CONFIG.STOP_LOSS_PCT * 100) {
      this.closePosition(key, 'STOP');
    }
    // Check take profit
    else if (pos.pnlPercent >= CONFIG.TAKE_PROFIT_PCT * 100) {
      this.closePosition(key, 'PROFIT');
    }
  }

  private closePosition(key: string, reason: 'STOP' | 'PROFIT'): void {
    const pos = this.positions.get(key);
    if (!pos) return;
    
    const brokerState = this.brokers.get(pos.broker);
    if (!brokerState) return;
    
    brokerState.balance += pos.pnl;
    brokerState.pnl += pos.pnl;
    this.totalPnL += pos.pnl;
    
    if (pos.pnl >= 0) {
      brokerState.wins++;
      this.wins++;
    } else {
      brokerState.losses++;
      this.losses++;
    }
    
    brokerState.positions--;
    
    const emoji = pos.pnl >= 0 ? '✅' : '❌';
    const taxLabel = pos.taxFree ? ' 🎁TAX FREE!' : '';
    const pnlStr = pos.pnl >= 0 ? `+£${pos.pnl.toFixed(4)}` : `-£${Math.abs(pos.pnl).toFixed(4)}`;
    console.log(`  ${brokerState.emoji} ${emoji} ${reason}: ${pos.symbol} | P&L: ${pnlStr}${taxLabel}`);
    
    this.positions.delete(key);
  }

  private printHeader(): void {
    console.log('\n');
    console.log('  ╔═══════════════════════════════════════════════════════════════════════════════╗');
    console.log('  ║                                                                               ║');
    console.log('  ║   🌊 AGGRESSIVE WAVE RIDER - LIVE MARKETS 🌊                                  ║');
    console.log('  ║                                                                               ║');
    console.log('  ║   A→Z  ↔  Z→A  "They Can\'t Stop Them All!"                                   ║');
    console.log('  ║                                                                               ║');
    console.log('  ╠═══════════════════════════════════════════════════════════════════════════════╣');
    console.log('  ║                                                                               ║');
    console.log('  ║   CRYPTO:  🪙 Binance  🦑 Kraken  🟠 Coinbase  💎 Bitstamp  💠 Gemini  ⭕ OKX  ║');
    console.log('  ║   FOREX:   💱 OANDA  💹 FXCM  🏦 Saxo  🏛️ IB                                   ║');
    console.log('  ║   CFD:     📊 Capital  📈 IG  📉 CMC  🦙 Alpaca                               ║');
    console.log('  ║                                                                               ║');
    console.log('  ║   🎁 TAX FREE (Spread Betting): 📈 IG  📉 CMC                                 ║');
    console.log('  ║                                                                               ║');
    console.log('  ╠═══════════════════════════════════════════════════════════════════════════════╣');
    console.log(`  ║   Capital: £${CONFIG.BALANCE_PER_BROKER} × 14 = £${CONFIG.BALANCE_PER_BROKER * 14} | Entry: ${CONFIG.ENTRY_THRESHOLD*100}% | SL: ${CONFIG.STOP_LOSS_PCT*100}% | TP: ${CONFIG.TAKE_PROFIT_PCT*100}%       ║`);
    console.log('  ╚═══════════════════════════════════════════════════════════════════════════════╝');
    console.log('');
    console.log('  🌊 Wave Rider activated - riding A→Z ↔ Z→A on live markets...');
    console.log('  ────────────────────────────────────────────────────────────────────────────────');
  }

  private displayStatus(): void {
    const elapsed = Math.floor((Date.now() - this.startTime.getTime()) / 1000);
    const minutes = Math.floor(elapsed / 60);
    const seconds = elapsed % 60;
    
    let totalBalance = 0;
    let totalPositions = 0;
    let taxFreePnL = 0;
    
    const lines: string[] = [];
    
    for (const [name, state] of this.brokers) {
      totalBalance += state.balance;
      totalPositions += state.positions;
      if (state.taxFree) taxFreePnL += state.pnl;
      
      const hitRate = state.wins + state.losses > 0
        ? ((state.wins / (state.wins + state.losses)) * 100).toFixed(0)
        : '-';
      
      const pnlStr = state.pnl >= 0 ? `+£${state.pnl.toFixed(2)}` : `-£${Math.abs(state.pnl).toFixed(2)}`;
      const pnlEmoji = state.pnl >= 0 ? '🟢' : '🔴';
      const taxLabel = state.taxFree ? '🎁' : '  ';
      
      lines.push(
        `  │ ${state.emoji} ${state.name.padEnd(8)} │ £${state.balance.toFixed(2).padStart(6)} │ ${state.positions}/${CONFIG.MAX_POSITIONS_PER_BROKER} │ ${hitRate.padStart(3)}% │ ${pnlEmoji} ${pnlStr.padStart(8)} │ ${taxLabel} │`
      );
    }
    
    const totalHitRate = this.wins + this.losses > 0
      ? ((this.wins / (this.wins + this.losses)) * 100).toFixed(1)
      : '0.0';
    
    const totalPnLStr = this.totalPnL >= 0 ? `+£${this.totalPnL.toFixed(2)}` : `-£${Math.abs(this.totalPnL).toFixed(2)}`;
    const totalEmoji = this.totalPnL >= 0 ? '🟢' : '🔴';
    
    console.log('');
    console.log('  ┌────────────────────────────────────────────────────────────────────────────┐');
    console.log(`  │  SCAN #${this.scans.toString().padStart(5)} [${this.scanDirection}]  │  Time: ${minutes}m ${seconds}s  │  Positions: ${totalPositions}/${14 * CONFIG.MAX_POSITIONS_PER_BROKER}  │`);
    console.log('  ├────────────────────────────────────────────────────────────────────────────┤');
    console.log('  │  Broker    │ Balance  │ Pos │  HR  │     P&L    │ 🎁 │');
    console.log('  ├────────────┼──────────┼─────┼──────┼────────────┼────┤');
    
    for (const line of lines) {
      console.log(line);
    }
    
    console.log('  ├────────────┼──────────┼─────┼──────┼────────────┼────┤');
    console.log(`  │ 🌊 TOTAL   │ £${totalBalance.toFixed(2).padStart(6)} │ ${totalPositions.toString().padStart(2)}  │${totalHitRate.padStart(5)}% │ ${totalEmoji} ${totalPnLStr.padStart(8)} │    │`);
    console.log('  └────────────────────────────────────────────────────────────────────────────┘');
    
    if (taxFreePnL !== 0) {
      const taxFreeStr = taxFreePnL >= 0 ? `+£${taxFreePnL.toFixed(4)}` : `-£${Math.abs(taxFreePnL).toFixed(4)}`;
      console.log(`  🎁 Tax-Free P&L (IG + CMC): ${taxFreeStr}`);
    }
    
    this.displayPositions();
  }

  private displayPositions(): void {
    const allPositions = Array.from(this.positions.values());
    
    if (allPositions.length === 0) {
      console.log('');
      console.log(`  🌊 [${this.scanDirection}] Scanning markets for wave entry points...`);
      console.log('');
      return;
    }
    
    allPositions.sort((a, b) => b.pnl - a.pnl);
    
    console.log('');
    console.log(`  🌊 Active Positions [${this.scanDirection}]:`);
    console.log('');
    
    for (const pos of allPositions.slice(0, 12)) {
      const emoji = pos.pnl >= 0 ? '🟢' : '🔴';
      const dir = pos.direction === 'LONG' ? '⬆' : '⬇';
      const brokerState = this.brokers.get(pos.broker);
      const brokerEmoji = brokerState?.emoji || '📈';
      const taxLabel = pos.taxFree ? ' 🎁' : '';
      
      const pnlStr = pos.pnl >= 0 ? `+£${pos.pnl.toFixed(4)}` : `-£${Math.abs(pos.pnl).toFixed(4)}`;
      const priceStr = pos.currentPrice < 10 ? pos.currentPrice.toFixed(5) : pos.currentPrice.toFixed(2);
      
      console.log(`     ${brokerEmoji} ${emoji} ${pos.symbol.padEnd(12)} ${dir} → ${pnlStr} (${pos.pnlPercent.toFixed(2)}%)${taxLabel}`);
    }
    
    if (allPositions.length > 12) {
      console.log(`     ... and ${allPositions.length - 12} more positions`);
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
  ║   🌊 WAVE RIDER - AGGRESSIVE LIVE TRADING 🌊                                  ║
  ║                                                                               ║
  ║   Strategy:                                                                   ║
  ║   • A→Z on odd scans, Z→A on even scans                                      ║
  ║   • Enter on momentum + PHI wave analysis                                     ║
  ║   • Ride the wave with 1.5% SL / 3% TP                                       ║
  ║   • "They can't stop them all!"                                              ║
  ║                                                                               ║
  ║   Live Data Sources:                                                          ║
  ║   • Binance API (20 pairs)                                                    ║
  ║   • Kraken API (10 pairs)                                                     ║
  ║   • OKX API (15 pairs)                                                        ║
  ║   • Coinbase API (8 pairs)                                                    ║
  ║   • Bitstamp API (7 pairs)                                                    ║
  ║   • Forex API (6 major pairs)                                                 ║
  ║                                                                               ║
  ║   Author: Gary Leckey - R&A Consulting                                       ║
  ║                                                                               ║
  ╚═══════════════════════════════════════════════════════════════════════════════╝
  `);

  const rider = new AggressiveWaveRider();
  
  process.on('SIGINT', () => {
    console.log('\n');
    console.log('  ────────────────────────────────────────────────────────────────────────────');
    console.log('  🌊 Wave Rider concludes...');
    console.log('  ────────────────────────────────────────────────────────────────────────────');
    console.log('');
    console.log('  "A→Z ↔ Z→A - The wave rides eternal"');
    console.log('');
    process.exit(0);
  });

  await rider.start();
}

main().catch(console.error);
