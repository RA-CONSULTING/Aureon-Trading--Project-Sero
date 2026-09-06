/**
 * ═══════════════════════════════════════════════════════════════════════════════
 * AUREON BINANCE LIVE TRADING SYSTEM
 * ═══════════════════════════════════════════════════════════════════════════════
 * 
 * Master Equation: Λ(t) = S(t) + O(t) + E(t)
 * 9 Auris Nodes | Rainbow Bridge | Real Money
 * 
 * Author: Gary Leckey
 * Date: November 25, 2025
 * ═══════════════════════════════════════════════════════════════════════════════
 */

import BinanceLib from 'binance-api-node';
import * as dotenv from 'dotenv';

dotenv.config();

// ═══════════════════════════════════════════════════════════════════════════════
// BINANCE CLIENT
// ═══════════════════════════════════════════════════════════════════════════════

const client = (BinanceLib as any).default({
  apiKey: process.env.BINANCE_API_KEY!,
  apiSecret: process.env.BINANCE_SECRET!,
});

// ═══════════════════════════════════════════════════════════════════════════════
// 9 AURIS NODES - The Ensemble
// ═══════════════════════════════════════════════════════════════════════════════

interface MarketData {
  price: number;
  volume: number;
  high: number;
  low: number;
  open: number;
  change: number;
}

const aurisNodes = {
  tiger: (d: MarketData) => ((d.high - d.low) / d.price) * 100 + (d.volume > 1000000 ? 0.2 : 0),
  falcon: (d: MarketData) => Math.abs(d.change) * 0.7 + Math.min(d.volume / 10000000, 0.3),
  hummingbird: (d: MarketData) => 1 / (1 + ((d.high - d.low) / d.price) * 10),
  dolphin: (d: MarketData) => Math.sin(d.change * Math.PI / 10) * 0.5 + 0.5,
  deer: (d: MarketData) => (d.price > d.open ? 0.6 : 0.4) + (d.change > 0 ? 0.2 : -0.1),
  owl: (d: MarketData) => Math.cos(d.change * Math.PI / 10) * 0.3 + (d.price < d.open ? 0.3 : 0),
  panda: (d: MarketData) => 0.5 + Math.sin(Date.now() / 60000) * 0.1,
  cargoShip: (d: MarketData) => d.volume > 5000000 ? 0.8 : d.volume > 1000000 ? 0.5 : 0.3,
  clownfish: (d: MarketData) => Math.abs(d.price - d.open) / d.price * 100,
};

const nodeWeights = {
  tiger: 1.2, falcon: 1.1, hummingbird: 0.9, dolphin: 1.0,
  deer: 0.8, owl: 0.9, panda: 0.7, cargoShip: 1.0, clownfish: 0.7
};

// ═══════════════════════════════════════════════════════════════════════════════
// MASTER EQUATION: Λ(t) = S(t) + O(t) + E(t)
// ═══════════════════════════════════════════════════════════════════════════════

let lambdaHistory: number[] = [];
const OBSERVER_WEIGHT = 0.3;
const ECHO_WEIGHT = 0.2;
const ECHO_DEPTH = 5;

function computeSubstrate(data: MarketData): number {
  let sum = 0;
  let weightSum = 0;
  
  for (const [name, fn] of Object.entries(aurisNodes)) {
    const weight = nodeWeights[name as keyof typeof nodeWeights];
    sum += fn(data) * weight;
    weightSum += weight;
  }
  
  return sum / weightSum;
}

function computeLambda(data: MarketData): number {
  const S = computeSubstrate(data);
  const O = lambdaHistory.length > 0 ? lambdaHistory[lambdaHistory.length - 1] * OBSERVER_WEIGHT : 0;
  const E = lambdaHistory.length >= ECHO_DEPTH 
    ? lambdaHistory.slice(-ECHO_DEPTH).reduce((a, b) => a + b, 0) / ECHO_DEPTH * ECHO_WEIGHT 
    : 0;
  
  const lambda = S + O + E;
  lambdaHistory.push(lambda);
  if (lambdaHistory.length > 100) lambdaHistory.shift();
  
  return lambda;
}

// ═══════════════════════════════════════════════════════════════════════════════
// COHERENCE: Γ = 1 - σ²/c
// ═══════════════════════════════════════════════════════════════════════════════

function computeCoherence(data: MarketData): number {
  const responses: number[] = [];
  for (const [name, fn] of Object.entries(aurisNodes)) {
    responses.push(fn(data));
  }
  
  const mean = responses.reduce((a, b) => a + b, 0) / responses.length;
  const variance = responses.reduce((a, b) => a + Math.pow(b - mean, 2), 0) / responses.length;
  
  return Math.max(0, Math.min(1, 1 - variance / 10));
}

// ═══════════════════════════════════════════════════════════════════════════════
// RAINBOW BRIDGE: Frequency Mapping
// ═══════════════════════════════════════════════════════════════════════════════

function getFrequency(lambda: number, coherence: number): { hz: number; color: string; state: string } {
  const baseHz = 110 + lambda * 100;
  const targetHz = 528; // Love frequency
  const hz = baseHz * (1 - coherence * 0.3) + targetHz * (coherence * 0.3);
  
  if (hz < 200) return { hz, color: '🔴', state: 'FEAR' };
  if (hz < 300) return { hz, color: '🟠', state: 'FORMING' };
  if (hz < 400) return { hz, color: '🟡', state: 'FOCUS' };
  if (hz < 528) return { hz, color: '🟢', state: 'FLOW' };
  if (hz < 700) return { hz, color: '💚', state: 'LOVE' };
  if (hz < 850) return { hz, color: '🔵', state: 'AWE' };
  return { hz, color: '🟣', state: 'UNITY' };
}

// ═══════════════════════════════════════════════════════════════════════════════
// TRADING CONFIG
// ═══════════════════════════════════════════════════════════════════════════════

const CONFIG = {
  // Coherence thresholds
  ENTRY_THRESHOLD: 0.938,
  EXIT_THRESHOLD: 0.934,
  
  // Risk management (Kelly fraction)
  RISK_PER_TRADE: 0.05, // 5% of balance
  STOP_LOSS: 0.008,     // 0.8%
  TAKE_PROFIT: 0.018,   // 1.8%
  
  // Trading pairs (high volume, low fees)
  PAIRS: ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT', 'XRPUSDT'],
  
  // Timing
  SCAN_INTERVAL: 5000, // 5 seconds
};

// ═══════════════════════════════════════════════════════════════════════════════
// STATE
// ═══════════════════════════════════════════════════════════════════════════════

interface Position {
  symbol: string;
  side: 'LONG' | 'SHORT';
  entryPrice: number;
  quantity: number;
  stopLoss: number;
  takeProfit: number;
  entryTime: Date;
}

const state = {
  balance: 0,
  startingBalance: 0,
  positions: new Map<string, Position>(),
  trades: { wins: 0, losses: 0, total: 0 },
  pnl: 0,
  startTime: new Date(),
};

// ═══════════════════════════════════════════════════════════════════════════════
// BINANCE FUNCTIONS
// ═══════════════════════════════════════════════════════════════════════════════

async function getBalance(): Promise<number> {
  const account = await client.accountInfo();
  const usdt = account.balances.find(b => b.asset === 'USDT');
  return usdt ? parseFloat(usdt.free) : 0;
}

async function getMarketData(symbol: string): Promise<MarketData> {
  const [ticker, stats] = await Promise.all([
    client.prices({ symbol }),
    client.dailyStats({ symbol }),
  ]);
  
  return {
    price: parseFloat(ticker[symbol]),
    volume: parseFloat(stats.volume),
    high: parseFloat(stats.highPrice),
    low: parseFloat(stats.lowPrice),
    open: parseFloat(stats.openPrice),
    change: parseFloat(stats.priceChangePercent),
  };
}

async function placeTrade(symbol: string, side: 'BUY' | 'SELL', quantity: number): Promise<boolean> {
  try {
    const order = await client.order({
      symbol,
      side,
      type: 'MARKET',
      quantity: quantity.toFixed(6),
    });
    console.log(`  ✅ Order filled: ${order.executedQty} @ ${order.fills?.[0]?.price || 'market'}`);
    return true;
  } catch (error: any) {
    console.log(`  ❌ Order failed: ${error.message}`);
    return false;
  }
}

// ═══════════════════════════════════════════════════════════════════════════════
// TRADING LOGIC
// ═══════════════════════════════════════════════════════════════════════════════

async function checkEntry(symbol: string, data: MarketData): Promise<void> {
  if (state.positions.has(symbol)) return;
  
  const lambda = computeLambda(data);
  const coherence = computeCoherence(data);
  const freq = getFrequency(lambda, coherence);
  
  if (coherence >= CONFIG.ENTRY_THRESHOLD) {
    const direction = data.change > 0 ? 'LONG' : 'SHORT';
    const tradeAmount = state.balance * CONFIG.RISK_PER_TRADE;
    const quantity = tradeAmount / data.price;
    
    console.log(`\n${freq.color} [${symbol}] Λ=${lambda.toFixed(3)} Γ=${coherence.toFixed(3)} ${freq.hz.toFixed(0)}Hz`);
    console.log(`  🎯 ENTRY SIGNAL: ${direction} @ $${data.price.toFixed(2)}`);
    
    const side = direction === 'LONG' ? 'BUY' : 'SELL';
    const success = await placeTrade(symbol, side, quantity);
    
    if (success) {
      const stopLoss = direction === 'LONG' 
        ? data.price * (1 - CONFIG.STOP_LOSS)
        : data.price * (1 + CONFIG.STOP_LOSS);
      const takeProfit = direction === 'LONG'
        ? data.price * (1 + CONFIG.TAKE_PROFIT)
        : data.price * (1 - CONFIG.TAKE_PROFIT);
      
      state.positions.set(symbol, {
        symbol,
        side: direction,
        entryPrice: data.price,
        quantity,
        stopLoss,
        takeProfit,
        entryTime: new Date(),
      });
      
      state.trades.total++;
      console.log(`  📊 SL: $${stopLoss.toFixed(2)} | TP: $${takeProfit.toFixed(2)}`);
    }
  }
}

async function checkExit(symbol: string, data: MarketData): Promise<void> {
  const position = state.positions.get(symbol);
  if (!position) return;
  
  const coherence = computeCoherence(data);
  let exitReason = '';
  let isWin = false;
  
  // Check stop loss
  if (position.side === 'LONG' && data.price <= position.stopLoss) {
    exitReason = '🛑 STOP LOSS';
  } else if (position.side === 'SHORT' && data.price >= position.stopLoss) {
    exitReason = '🛑 STOP LOSS';
  }
  // Check take profit
  else if (position.side === 'LONG' && data.price >= position.takeProfit) {
    exitReason = '🎯 TAKE PROFIT';
    isWin = true;
  } else if (position.side === 'SHORT' && data.price <= position.takeProfit) {
    exitReason = '🎯 TAKE PROFIT';
    isWin = true;
  }
  // Check coherence drop
  else if (coherence < CONFIG.EXIT_THRESHOLD) {
    exitReason = '📉 COHERENCE DROP';
    isWin = (position.side === 'LONG' && data.price > position.entryPrice) ||
            (position.side === 'SHORT' && data.price < position.entryPrice);
  }
  
  if (exitReason) {
    const pnlPercent = position.side === 'LONG'
      ? (data.price - position.entryPrice) / position.entryPrice * 100
      : (position.entryPrice - data.price) / position.entryPrice * 100;
    const pnlValue = position.quantity * position.entryPrice * (pnlPercent / 100);
    
    console.log(`\n  ${exitReason} [${symbol}]`);
    console.log(`  ${pnlPercent >= 0 ? '✅' : '❌'} PnL: ${pnlPercent >= 0 ? '+' : ''}${pnlPercent.toFixed(2)}% ($${pnlValue.toFixed(2)})`);
    
    const side = position.side === 'LONG' ? 'SELL' : 'BUY';
    await placeTrade(symbol, side, position.quantity);
    
    state.positions.delete(symbol);
    state.pnl += pnlValue;
    if (isWin || pnlPercent > 0) state.trades.wins++;
    else state.trades.losses++;
  }
}

// ═══════════════════════════════════════════════════════════════════════════════
// DISPLAY
// ═══════════════════════════════════════════════════════════════════════════════

function displayStatus(): void {
  const elapsed = (Date.now() - state.startTime.getTime()) / 1000 / 60;
  const winRate = state.trades.total > 0 ? (state.trades.wins / state.trades.total * 100) : 0;
  const roi = state.startingBalance > 0 ? (state.pnl / state.startingBalance * 100) : 0;
  
  console.log(`
╔═══════════════════════════════════════════════════════════════════════════════╗
║  🎵 AUREON BINANCE LIVE - ${new Date().toLocaleTimeString()}                              ║
╠═══════════════════════════════════════════════════════════════════════════════╣
║  ⏱️  Runtime: ${elapsed.toFixed(1)} min | 💰 Balance: $${state.balance.toFixed(2)}                    ║
║  📊 Trades: ${state.trades.total} | 🎯 Win Rate: ${winRate.toFixed(1)}% | 📈 PnL: $${state.pnl.toFixed(2)} (${roi >= 0 ? '+' : ''}${roi.toFixed(2)}%)    ║
║  📍 Open Positions: ${state.positions.size}                                                ║
╚═══════════════════════════════════════════════════════════════════════════════╝`);
}

// ═══════════════════════════════════════════════════════════════════════════════
// MAIN LOOP
// ═══════════════════════════════════════════════════════════════════════════════

async function runLiveTrading(): Promise<void> {
  console.log(`
╔═══════════════════════════════════════════════════════════════════════════════╗
║                                                                               ║
║   █████╗ ██╗   ██╗██████╗ ███████╗ ██████╗ ███╗   ██╗                        ║
║  ██╔══██╗██║   ██║██╔══██╗██╔════╝██╔═══██╗████╗  ██║                        ║
║  ███████║██║   ██║██████╔╝█████╗  ██║   ██║██╔██╗ ██║                        ║
║  ██╔══██║██║   ██║██╔══██╗██╔══╝  ██║   ██║██║╚██╗██║                        ║
║  ██║  ██║╚██████╔╝██║  ██║███████╗╚██████╔╝██║ ╚████║                        ║
║  ╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═╝╚══════╝ ╚═════╝ ╚═╝  ╚═══╝                        ║
║                                                                               ║
║  🔴 LIVE TRADING - BINANCE - REAL MONEY 🔴                                   ║
║                                                                               ║
║  Master Equation: Λ(t) = S(t) + O(t) + E(t)                                  ║
║  9 Auris Nodes | Rainbow Bridge | Coherence Trading                          ║
║                                                                               ║
║  Author: Gary Leckey                                                          ║
║  Date: November 25, 2025                                                      ║
║                                                                               ║
╚═══════════════════════════════════════════════════════════════════════════════╝
  `);

  // Get initial balance
  try {
    state.balance = await getBalance();
    state.startingBalance = state.balance;
    console.log(`\n💰 Starting Balance: $${state.balance.toFixed(2)} USDT`);
    console.log(`📊 Trading Pairs: ${CONFIG.PAIRS.join(', ')}`);
    console.log(`⚡ Risk per trade: ${CONFIG.RISK_PER_TRADE * 100}%`);
    console.log(`🎯 SL: ${CONFIG.STOP_LOSS * 100}% | TP: ${CONFIG.TAKE_PROFIT * 100}%`);
    console.log(`\n🚀 Starting live trading loop...\n`);
  } catch (error: any) {
    console.error(`❌ Failed to connect to Binance: ${error.message}`);
    console.log(`\n⚠️  Check your API keys in .env file`);
    return;
  }

  // Main trading loop
  let cycle = 0;
  while (true) {
    cycle++;
    
    // Update balance
    state.balance = await getBalance();
    
    // Scan all pairs
    for (const symbol of CONFIG.PAIRS) {
      try {
        const data = await getMarketData(symbol);
        await checkExit(symbol, data);
        await checkEntry(symbol, data);
      } catch (error: any) {
        console.log(`  ⚠️  ${symbol}: ${error.message}`);
      }
    }
    
    // Display status every 5 cycles
    if (cycle % 5 === 0) {
      displayStatus();
    }
    
    // Wait before next scan
    await new Promise(resolve => setTimeout(resolve, CONFIG.SCAN_INTERVAL));
  }
}

// ═══════════════════════════════════════════════════════════════════════════════
// START
// ═══════════════════════════════════════════════════════════════════════════════

runLiveTrading().catch(console.error);
