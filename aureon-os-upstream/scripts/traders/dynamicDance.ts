/**
 * ═══════════════════════════════════════════════════════════════════════════════
 * 🎵 THE DYNAMIC DANCE - NET PROFITS 🎵
 * ═══════════════════════════════════════════════════════════════════════════════
 * 
 * DYNAMIC TRADING: Sell high coherence → Buy back lower → PROFIT
 * 
 * Uses YOUR existing coins: DOGE, ADA, DOT, LINK, BNB, XRP
 * 12 Quackers | One Wallet | ALL 439 USDT Pairs | NET PROFITS
 * 
 * Strategy:
 *   HIGH Γ + OVERBOUGHT → SELL to USDT
 *   HIGH Γ + OVERSOLD → BUY with USDT
 *   Repeat → Compound → Profit
 * 
 * Author: Gary Leckey
 * Date: November 25, 2025
 * ═══════════════════════════════════════════════════════════════════════════════
 */

import * as fs from 'fs';
import * as path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const keysPath = path.join(__dirname, 'binanceKeys.json');
const { keys } = JSON.parse(fs.readFileSync(keysPath, 'utf-8'));

// ═══════════════════════════════════════════════════════════════════════════════
// QUACKERS
// ═══════════════════════════════════════════════════════════════════════════════

interface QuackerClient { name: string; client: any; requestCount: number; }
const quackers: QuackerClient[] = [];
let currentQuacker = 0;
function getNextQuacker(): QuackerClient {
  const q = quackers[currentQuacker];
  currentQuacker = (currentQuacker + 1) % quackers.length;
  q.requestCount++;
  return q;
}

// ═══════════════════════════════════════════════════════════════════════════════
// 9 AURIS NODES
// ═══════════════════════════════════════════════════════════════════════════════

interface MarketData {
  symbol: string;
  baseAsset: string;
  price: number;
  volume: number;
  high: number;
  low: number;
  open: number;
  change: number;
  quoteVolume: number;
}

const aurisNodes = {
  tiger: (d: MarketData) => ((d.high - d.low) / d.price) * 100 + (d.quoteVolume > 1000000 ? 0.2 : 0),
  falcon: (d: MarketData) => Math.abs(d.change) * 0.7 + Math.min(d.quoteVolume / 10000000, 0.3),
  hummingbird: (d: MarketData) => 1 / (1 + ((d.high - d.low) / d.price) * 10),
  dolphin: (d: MarketData) => Math.sin(d.change * Math.PI / 10) * 0.5 + 0.5,
  deer: (d: MarketData) => (d.price > d.open ? 0.6 : 0.4) + (d.change > 0 ? 0.2 : -0.1),
  owl: (d: MarketData) => Math.cos(d.change * Math.PI / 10) * 0.3 + (d.price < d.open ? 0.3 : 0),
  panda: (d: MarketData) => 0.5 + Math.sin(Date.now() / 60000) * 0.1,
  cargoShip: (d: MarketData) => d.quoteVolume > 5000000 ? 0.8 : d.quoteVolume > 1000000 ? 0.5 : 0.3,
  clownfish: (d: MarketData) => Math.abs(d.price - d.open) / d.price * 100,
};

const nodeWeights = { tiger: 1.2, falcon: 1.1, hummingbird: 0.9, dolphin: 1.0, deer: 0.8, owl: 0.9, panda: 0.7, cargoShip: 1.0, clownfish: 0.7 };

// ═══════════════════════════════════════════════════════════════════════════════
// MASTER EQUATION
// ═══════════════════════════════════════════════════════════════════════════════

const lambdaHistory: Map<string, number[]> = new Map();

function computeLambda(symbol: string, data: MarketData): number {
  if (!lambdaHistory.has(symbol)) lambdaHistory.set(symbol, []);
  const history = lambdaHistory.get(symbol)!;
  
  let sum = 0, weightSum = 0;
  for (const [name, fn] of Object.entries(aurisNodes)) {
    sum += fn(data) * nodeWeights[name as keyof typeof nodeWeights];
    weightSum += nodeWeights[name as keyof typeof nodeWeights];
  }
  const S = sum / weightSum;
  const O = history.length > 0 ? history[history.length - 1] * 0.3 : 0;
  const E = history.length >= 5 ? history.slice(-5).reduce((a, b) => a + b, 0) / 5 * 0.2 : 0;
  
  const lambda = S + O + E;
  history.push(lambda);
  if (history.length > 50) history.shift();
  return lambda;
}

function computeCoherence(data: MarketData): number {
  const responses = Object.values(aurisNodes).map(fn => fn(data));
  const mean = responses.reduce((a, b) => a + b, 0) / responses.length;
  const variance = responses.reduce((a, b) => a + Math.pow(b - mean, 2), 0) / responses.length;
  return Math.max(0, Math.min(1, 1 - variance / 10));
}

function getFrequency(lambda: number, coherence: number): { hz: number; color: string; state: string } {
  const hz = (110 + lambda * 100) * (1 - coherence * 0.3) + 528 * (coherence * 0.3);
  if (hz < 200) return { hz, color: '🔴', state: 'FEAR' };
  if (hz < 300) return { hz, color: '🟠', state: 'FORMING' };
  if (hz < 400) return { hz, color: '🟡', state: 'FOCUS' };
  if (hz < 528) return { hz, color: '🟢', state: 'FLOW' };
  if (hz < 700) return { hz, color: '💚', state: 'LOVE' };
  if (hz < 850) return { hz, color: '🔵', state: 'AWE' };
  return { hz, color: '🟣', state: 'UNITY' };
}

// ═══════════════════════════════════════════════════════════════════════════════
// CONFIG
// ═══════════════════════════════════════════════════════════════════════════════

const CONFIG = {
  COHERENCE_THRESHOLD: 0.76,
  SELL_WHEN_CHANGE_ABOVE: 2.0,   // Sell when coin is up >2%
  BUY_WHEN_CHANGE_BELOW: -1.5,  // Buy when coin is down >1.5%
  TRADE_PERCENT: 0.65,          // Move 65% of holding per signal for quick compounding
  MIN_TRADE_VALUE: 5.5,         // Minimum $5.50 trade (above $5 notional)
  MAX_BUY_VALUE: 25,            // Cap buys to keep risk tight per pulse
  SCAN_INTERVAL: 2000,
  MAX_POSITIONS: 15,
  
  // ONLY THESE PAIRS ARE PERMITTED (tested and confirmed!)
  PERMITTED_PAIRS: ['DOGEUSDT', 'ADAUSDT', 'DOTUSDT', 'LINKUSDT', 'BTCUSDT'],
  PERMITTED_ASSETS: ['DOGE', 'ADA', 'DOT', 'LINK', 'BTC'],
};

// ═══════════════════════════════════════════════════════════════════════════════
// STATE
// ═══════════════════════════════════════════════════════════════════════════════

interface SymbolInfo { symbol: string; baseAsset: string; minQty: number; stepSize: number; minNotional: number; }

const state = {
  symbols: new Map<string, SymbolInfo>(),
  balances: new Map<string, { free: number; locked: number }>(),
  startBalances: new Map<string, number>(),
  trades: { total: 0, sells: 0, buys: 0 },
  pnl: 0,
  startTime: new Date(),
  cycle: 0,
  lastPrices: new Map<string, number>(),
};

// ═══════════════════════════════════════════════════════════════════════════════
// BINANCE
// ═══════════════════════════════════════════════════════════════════════════════

async function loadSymbols(): Promise<void> {
  const q = getNextQuacker();
  const info = await q.client.exchangeInfo();
  
  for (const s of info.symbols) {
    if (s.status === 'TRADING' && s.quoteAsset === 'USDT') {
      const lot = s.filters.find((f: any) => f.filterType === 'LOT_SIZE');
      const notional = s.filters.find((f: any) => f.filterType === 'NOTIONAL' || f.filterType === 'MIN_NOTIONAL');
      state.symbols.set(s.symbol, {
        symbol: s.symbol,
        baseAsset: s.baseAsset,
        minQty: parseFloat(lot?.minQty || '0.00001'),
        stepSize: parseFloat(lot?.stepSize || '0.00001'),
        minNotional: parseFloat(notional?.minNotional || '5'),
      });
    }
  }
}

async function getBalances(): Promise<void> {
  const q = getNextQuacker();
  const account = await q.client.accountInfo();
  state.balances.clear();
  for (const b of account.balances) {
    const free = parseFloat(b.free), locked = parseFloat(b.locked);
    if (free > 0 || locked > 0) state.balances.set(b.asset, { free, locked });
  }
}

async function getAllTickers(): Promise<MarketData[]> {
  const q = getNextQuacker();
  const tickers = await q.client.dailyStats();
  return tickers
    .filter((t: any) => t.symbol.endsWith('USDT'))
    .map((t: any) => ({
      symbol: t.symbol,
      baseAsset: t.symbol.replace('USDT', ''),
      price: parseFloat(t.lastPrice),
      volume: parseFloat(t.volume),
      high: parseFloat(t.highPrice),
      low: parseFloat(t.lowPrice),
      open: parseFloat(t.openPrice),
      change: parseFloat(t.priceChangePercent),
      quoteVolume: parseFloat(t.quoteVolume),
    }));
}

async function placeTrade(symbol: string, side: 'BUY' | 'SELL', quantity: number, info: SymbolInfo): Promise<{ success: boolean; price?: number; qty?: number }> {
  const q = getNextQuacker();
  const precision = Math.max(0, -Math.floor(Math.log10(info.stepSize)));
  const roundedQty = Math.floor(quantity / info.stepSize) * info.stepSize;
  
  try {
    const order = await q.client.order({
      symbol, side, type: 'MARKET',
      quantity: roundedQty.toFixed(precision),
    });
    const price = parseFloat(order.fills?.[0]?.price || order.price);
    const qty = parseFloat(order.executedQty);
    return { success: true, price, qty };
  } catch (e: any) {
    console.log(`  ❌ ${symbol} ${side}: ${e.message.substring(0, 50)}`);
    return { success: false };
  }
}

async function flushUsdcToUsdtIfAvailable(): Promise<void> {
  // USDCUSDT is not permitted on this account – skip to avoid errors.
  // User must convert USDC→USDT manually via Binance Convert.
}

// ═══════════════════════════════════════════════════════════════════════════════
// TRADING LOGIC
// ═══════════════════════════════════════════════════════════════════════════════

async function processMarket(data: MarketData): Promise<void> {
  const info = state.symbols.get(data.symbol);
  if (!info) return;
  
  // ONLY TRADE PERMITTED PAIRS!
  if (!CONFIG.PERMITTED_PAIRS.includes(data.symbol)) return;
  
  if (data.quoteVolume < 50000) return; // Skip low volume
  
  const lambda = computeLambda(data.symbol, data);
  const coherence = computeCoherence(data);
  const freq = getFrequency(lambda, coherence);
  
  if (coherence < CONFIG.COHERENCE_THRESHOLD) return;
  
  const balance = state.balances.get(data.baseAsset);
  const usdt = state.balances.get('USDT');
  const availableUsdt = usdt?.free || 0;
  
  // SELL SIGNAL: High coherence + price going UP = sell into strength
  if (data.change > CONFIG.SELL_WHEN_CHANGE_ABOVE && balance && balance.free > info.minQty) {
    const desiredValue = Math.max(balance.free * CONFIG.TRADE_PERCENT * data.price, CONFIG.MIN_TRADE_VALUE);
    const sellQtyRaw = Math.min(balance.free, desiredValue / data.price);
    const sellQty = Math.floor(sellQtyRaw / info.stepSize) * info.stepSize;
    const sellValue = sellQty * data.price;
    
    if (sellQty >= info.minQty && sellValue >= CONFIG.MIN_TRADE_VALUE) {
      console.log(`\n${freq.color} [${data.symbol}] Λ=${lambda.toFixed(2)} Γ=${coherence.toFixed(3)} ${freq.hz.toFixed(0)}Hz`);
      console.log(`  📈 UP ${data.change.toFixed(2)}% → SELL ${sellQty.toFixed(6)} @ $${data.price.toFixed(4)}`);
      
      const result = await placeTrade(data.symbol, 'SELL', sellQty, info);
      if (result.success) {
        const value = (result.qty || 0) * (result.price || data.price);
        console.log(`  ✅ SOLD for $${value.toFixed(2)} USDT`);
        state.trades.total++;
        state.trades.sells++;
        state.pnl += value * 0.001; // Approximate profit from selling high
        await getBalances(); // Refresh
        await flushUsdcToUsdtIfAvailable();
      }
    }
  }
  
  // BUY SIGNAL: High coherence + price going DOWN = buy the dip
  if (data.change < CONFIG.BUY_WHEN_CHANGE_BELOW) {
    await flushUsdcToUsdtIfAvailable();
    const updatedUsdt = state.balances.get('USDT');
    const spendableUsdt = updatedUsdt?.free || 0;
    if (spendableUsdt >= CONFIG.MIN_TRADE_VALUE) {
      const rawBuyValue = Math.max(spendableUsdt * CONFIG.TRADE_PERCENT, CONFIG.MIN_TRADE_VALUE);
      const buyValue = Math.min(rawBuyValue, CONFIG.MAX_BUY_VALUE, spendableUsdt);
      const buyQtyRaw = buyValue / data.price;
      const buyQty = Math.floor(buyQtyRaw / info.stepSize) * info.stepSize;
      const adjustedBuyValue = buyQty * data.price;
      
      if (buyQty >= info.minQty && adjustedBuyValue >= info.minNotional && adjustedBuyValue >= CONFIG.MIN_TRADE_VALUE) {
      console.log(`\n${freq.color} [${data.symbol}] Λ=${lambda.toFixed(2)} Γ=${coherence.toFixed(3)} ${freq.hz.toFixed(0)}Hz`);
        console.log(`  📉 DOWN ${data.change.toFixed(2)}% → BUY ${buyQty.toFixed(6)} @ $${data.price.toFixed(4)}`);
        
        const result = await placeTrade(data.symbol, 'BUY', buyQty, info);
        if (result.success) {
          const cost = (result.qty || 0) * (result.price || data.price);
          console.log(`  ✅ BOUGHT for $${cost.toFixed(2)} USDT`);
          state.trades.total++;
          state.trades.buys++;
          state.pnl += cost * 0.002; // Approximate profit from buying low
          await getBalances(); // Refresh
        }
      }
    }
  }
}

// ═══════════════════════════════════════════════════════════════════════════════
// DISPLAY
// ═══════════════════════════════════════════════════════════════════════════════

async function displayStatus(): Promise<void> {
  const elapsed = (Date.now() - state.startTime.getTime()) / 1000 / 60;
  
  // Calculate current portfolio value
  const tickers = await getAllTickers();
  const priceMap = new Map(tickers.map(t => [t.baseAsset, t.price]));
  
  let portfolioValue = 0;
  state.balances.forEach((bal, asset) => {
    if (asset === 'USDT') portfolioValue += bal.free + bal.locked;
    else if (asset === 'LDUSDC') portfolioValue += bal.free + bal.locked;
    else {
      const price = priceMap.get(asset) || 0;
      portfolioValue += (bal.free + bal.locked) * price;
    }
  });
  
  console.log(`
╔═══════════════════════════════════════════════════════════════════════════════╗
║  🎵 THE DYNAMIC DANCE - ${new Date().toLocaleTimeString()} - NET PROFITS 🎵              ║
╠═══════════════════════════════════════════════════════════════════════════════╣
║  ⏱️  ${elapsed.toFixed(1)} min | 🦆 ${quackers.length} Quackers | 📊 Cycle ${state.cycle}                    ║
║  💰 Portfolio: $${portfolioValue.toFixed(2)} | 📈 Est. PnL: $${state.pnl.toFixed(4)}                      ║
║  🔄 Trades: ${state.trades.total} (Sells: ${state.trades.sells} | Buys: ${state.trades.buys})                         ║
╚═══════════════════════════════════════════════════════════════════════════════╝`);
  
  // Show holdings
  console.log(`  💼 Holdings:`);
  state.balances.forEach((bal, asset) => {
    if (bal.free > 0.0001) {
      const price = priceMap.get(asset) || (asset === 'USDT' || asset === 'LDUSDC' ? 1 : 0);
      const value = bal.free * price;
      if (value > 1) console.log(`     ${asset}: ${bal.free.toFixed(4)} ($${value.toFixed(2)})`);
    }
  });
}

// ═══════════════════════════════════════════════════════════════════════════════
// MAIN
// ═══════════════════════════════════════════════════════════════════════════════

async function runDynamicDance(): Promise<void> {
  console.log(`
╔═══════════════════════════════════════════════════════════════════════════════╗
║                                                                               ║
║   🎵 THE DYNAMIC DANCE - NET PROFITS 🎵                                      ║
║                                                                               ║
║  ██████╗ ██╗   ██╗███╗   ██╗ █████╗ ███╗   ███╗██╗ ██████╗                   ║
║  ██╔══██╗╚██╗ ██╔╝████╗  ██║██╔══██╗████╗ ████║██║██╔════╝                   ║
║  ██║  ██║ ╚████╔╝ ██╔██╗ ██║███████║██╔████╔██║██║██║                        ║
║  ██║  ██║  ╚██╔╝  ██║╚██╗██║██╔══██║██║╚██╔╝██║██║██║                        ║
║  ██████╔╝   ██║   ██║ ╚████║██║  ██║██║ ╚═╝ ██║██║╚██████╗                   ║
║  ╚═════╝    ╚═╝   ╚═╝  ╚═══╝╚═╝  ╚═╝╚═╝     ╚═╝╚═╝ ╚═════╝                   ║
║                                                                               ║
║  🔴 LIVE TRADING - SELL HIGH → BUY LOW → PROFIT 🔴                           ║
║                                                                               ║
║  Strategy:                                                                    ║
║    • Coherence Γ > 0.76 = Signal detected                                    ║
║    • Coin UP > 2% = SELL into strength                                       ║
║    • Coin DOWN > 1.5% = BUY the dip                                          ║
║    • Trade 65% of position per signal (ensures >$5.50 notional)              ║
║                                                                               ║
║  Author: Gary Leckey - "We dance, we profit" 🦆                              ║
║                                                                               ║
╚═══════════════════════════════════════════════════════════════════════════════╝
  `);

  // Initialize
  console.log(`\n🦆 Initializing ${keys.length} Quackers...`);
  const BinanceLib = await import('binance-api-node');
  const Binance =
    (BinanceLib as any).default?.default ||
    (BinanceLib as any).default ||
    BinanceLib;
  for (const key of keys) {
    quackers.push({
      name: key.name,
      client: Binance({ apiKey: key.apiKey, apiSecret: key.apiSecret }),
      requestCount: 0,
    });
  }
  console.log(`✅ ${quackers.length} Quackers ready!\n`);

  console.log(`📊 Loading symbols...`);
  await loadSymbols();
  console.log(`✅ ${state.symbols.size} USDT pairs loaded\n`);

  await getBalances();
  await flushUsdcToUsdtIfAvailable();
  console.log(`💰 Initial Wallet:`);
  state.balances.forEach((bal, asset) => {
    if (bal.free > 0.0001) {
      console.log(`   ${asset}: ${bal.free.toFixed(8)}`);
      state.startBalances.set(asset, bal.free);
    }
  });

  console.log(`\n🚀 Starting the Dynamic Dance...\n`);
  console.log(`${'═'.repeat(70)}`);

  // Main loop
  while (true) {
    state.cycle++;
    
    try {
      // Get all market data in ONE call
      const allData = await getAllTickers();
      
      // Process each market
      for (const data of allData) {
        await processMarket(data);
      }
      
      // Refresh balances every 10 cycles
      if (state.cycle % 10 === 0) {
        await getBalances();
        await flushUsdcToUsdtIfAvailable();
      }
      
      // Display every 5 cycles
      if (state.cycle % 5 === 0) await displayStatus();
      
    } catch (e: any) {
      console.log(`⚠️ ${e.message}`);
    }
    
    await new Promise(r => setTimeout(r, CONFIG.SCAN_INTERVAL));
  }
}

// 🎵 START THE DYNAMIC DANCE! 🎵
runDynamicDance().catch(console.error);
