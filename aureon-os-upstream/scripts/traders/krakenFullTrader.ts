/**
 * 🐙 KRAKEN FULL TRADER 🐙
 * 
 * Trade ALL crypto pairs on Kraken - Just like Binance!
 * Dynamically loads ALL USD/EUR pairs | Full market coverage
 * 
 * Strategy: Mean Reversion + Momentum
 * - BUY when down > 1.5% (oversold)
 * - SELL when up > 1.5% (overbought)
 * - Uses coherence from 9 Auris nodes
 * 
 * Author: Gary Leckey
 */

import * as crypto from 'crypto';
import * as dotenv from 'dotenv';
import * as path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

dotenv.config({ path: path.join(__dirname, '..', '.env') });

const CONFIG = {
  API_KEY: process.env.KRAKEN_API_KEY || '',
  API_SECRET: process.env.KRAKEN_API_SECRET || '',
  
  BASE_URL: 'https://api.kraken.com',
  
  // Trading settings
  COHERENCE_THRESHOLD: 0.76,
  RISK_PERCENT: 2,
  ENTRY_THRESHOLD: 1.5,
  TAKE_PROFIT: 2.0,
  STOP_LOSS: 1.0,
  MIN_VOLUME_USD: 100000,   // Min 24h volume
  SCAN_INTERVAL: 3000,
  MAX_POSITIONS: 5,
  QUOTE_ASSETS: ['USD', 'ZUSD', 'EUR', 'ZEUR'], // Trade against these
};

// ═══════════════════════════════════════════════════════════════════════════════
// TYPES
// ═══════════════════════════════════════════════════════════════════════════════

interface TradingPair {
  pair: string;           // API pair name (e.g., XXBTZUSD)
  altname: string;        // Alternative name (e.g., XBTUSD)
  base: string;           // Base asset
  quote: string;          // Quote asset
  lotDecimals: number;    // Lot size decimals
  pairDecimals: number;   // Price decimals
  orderMin: number;       // Minimum order size
}

interface Position {
  pair: string;
  side: 'buy' | 'sell';
  price: number;
  volume: number;
  orderId: string;
  entryTime: Date;
}

interface MarketData {
  pair: string;
  altname: string;
  price: number;
  open: number;
  high: number;
  low: number;
  volume: number;
  volumeUSD: number;
  change: number;
  bid: number;
  ask: number;
}

const state = {
  allPairs: new Map<string, TradingPair>(),
  tradablePairs: [] as TradingPair[],
  positions: new Map<string, Position>(),
  balances: new Map<string, number>(),
  trades: { total: 0, wins: 0, losses: 0 },
  pnl: 0,
  nonce: Date.now(),
  cycle: 0,
  startTime: new Date(),
};

// ═══════════════════════════════════════════════════════════════════════════════
// 9 AURIS NODES (Same as Binance for consistency)
// ═══════════════════════════════════════════════════════════════════════════════

const aurisNodes = {
  tiger: (d: MarketData) => ((d.high - d.low) / d.price) * 100 + (d.volumeUSD > 1000000 ? 0.2 : 0),
  falcon: (d: MarketData) => Math.abs(d.change) * 0.7 + Math.min(d.volumeUSD / 10000000, 0.3),
  hummingbird: (d: MarketData) => 1 / (1 + ((d.high - d.low) / d.price) * 10),
  dolphin: (d: MarketData) => Math.sin(d.change * Math.PI / 10) * 0.5 + 0.5,
  deer: (d: MarketData) => (d.price > d.open ? 0.6 : 0.4) + (d.change > 0 ? 0.2 : -0.1),
  owl: (d: MarketData) => Math.cos(d.change * Math.PI / 10) * 0.3 + (d.price < d.open ? 0.3 : 0),
  panda: (d: MarketData) => 0.5 + Math.sin(Date.now() / 60000) * 0.1,
  cargoShip: (d: MarketData) => d.volumeUSD > 5000000 ? 0.8 : d.volumeUSD > 1000000 ? 0.5 : 0.3,
  clownfish: (d: MarketData) => Math.abs(d.price - d.open) / d.price * 100,
};

const nodeWeights = {
  tiger: 1.2, falcon: 1.1, hummingbird: 0.9, dolphin: 1.0,
  deer: 0.8, owl: 0.9, panda: 0.7, cargoShip: 1.0, clownfish: 0.7
};

const lambdaHistory: Map<string, number[]> = new Map();

function computeLambda(pair: string, data: MarketData): number {
  if (!lambdaHistory.has(pair)) lambdaHistory.set(pair, []);
  const history = lambdaHistory.get(pair)!;
  
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
// KRAKEN API
// ═══════════════════════════════════════════════════════════════════════════════

function getSignature(path: string, postData: string, nonce: number): string {
  const message = nonce + postData;
  const hash = crypto.createHash('sha256').update(message).digest();
  const secretBuffer = Buffer.from(CONFIG.API_SECRET, 'base64');
  const hmac = crypto.createHmac('sha512', secretBuffer);
  hmac.update(path);
  hmac.update(hash);
  return hmac.digest('base64');
}

async function publicRequest(endpoint: string): Promise<any> {
  const response = await fetch(`${CONFIG.BASE_URL}/0/public/${endpoint}`);
  const data = await response.json();
  
  if (data.error && data.error.length > 0) {
    throw new Error(data.error.join(', '));
  }
  
  return data.result;
}

async function privateRequest(endpoint: string, params: Record<string, any> = {}): Promise<any> {
  const nonce = ++state.nonce;
  const postData = new URLSearchParams({ nonce: nonce.toString(), ...params }).toString();
  const path = `/0/private/${endpoint}`;
  const signature = getSignature(path, postData, nonce);
  
  const response = await fetch(`${CONFIG.BASE_URL}${path}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
      'API-Key': CONFIG.API_KEY,
      'API-Sign': signature,
    },
    body: postData,
  });
  
  const data = await response.json();
  
  if (data.error && data.error.length > 0) {
    throw new Error(data.error.join(', '));
  }
  
  return data.result;
}

// ═══════════════════════════════════════════════════════════════════════════════
// LOAD ALL TRADING PAIRS (Like Binance exchangeInfo)
// ═══════════════════════════════════════════════════════════════════════════════

async function loadAllPairs(): Promise<void> {
  console.log('📊 Loading all Kraken trading pairs...');
  
  const assetPairs = await publicRequest('AssetPairs');
  
  state.allPairs.clear();
  state.tradablePairs = [];
  
  for (const [pairName, info] of Object.entries(assetPairs) as [string, any][]) {
    // Skip darkpool pairs and .d pairs
    if (pairName.includes('.d') || info.status !== 'online') continue;
    
    const quote = info.quote;
    
    // Only trade against USD/EUR
    if (!CONFIG.QUOTE_ASSETS.some(q => quote.includes(q) || quote === q)) continue;
    
    const pair: TradingPair = {
      pair: pairName,
      altname: info.altname || pairName,
      base: info.base,
      quote: info.quote,
      lotDecimals: info.lot_decimals || 8,
      pairDecimals: info.pair_decimals || 5,
      orderMin: parseFloat(info.ordermin || '0.0001'),
    };
    
    state.allPairs.set(pairName, pair);
    state.tradablePairs.push(pair);
  }
  
  console.log(`✅ Loaded ${state.tradablePairs.length} USD/EUR trading pairs`);
}

// ═══════════════════════════════════════════════════════════════════════════════
// GET ALL TICKERS (Like Binance dailyStats)
// ═══════════════════════════════════════════════════════════════════════════════

async function getAllTickers(): Promise<Map<string, MarketData>> {
  // Get all tickers in one call
  const pairList = state.tradablePairs.map(p => p.pair).join(',');
  const tickers = await publicRequest(`Ticker?pair=${pairList}`);
  
  const result = new Map<string, MarketData>();
  
  for (const [pairName, ticker] of Object.entries(tickers) as [string, any][]) {
    const pairInfo = state.allPairs.get(pairName);
    if (!pairInfo) continue;
    
    const price = parseFloat(ticker.c[0]);    // Last trade price
    const open = parseFloat(ticker.o);         // Today's open
    const high = parseFloat(ticker.h[1]);      // 24h high
    const low = parseFloat(ticker.l[1]);       // 24h low
    const volume = parseFloat(ticker.v[1]);    // 24h volume
    const bid = parseFloat(ticker.b[0]);       // Best bid
    const ask = parseFloat(ticker.a[0]);       // Best ask
    const volumeUSD = volume * price;          // Volume in USD
    const change = open > 0 ? ((price - open) / open) * 100 : 0;
    
    result.set(pairName, {
      pair: pairName,
      altname: pairInfo.altname,
      price,
      open,
      high,
      low,
      volume,
      volumeUSD,
      change,
      bid,
      ask,
    });
  }
  
  return result;
}

// ═══════════════════════════════════════════════════════════════════════════════
// BALANCE & ORDERS
// ═══════════════════════════════════════════════════════════════════════════════

async function getBalances(): Promise<void> {
  const balances = await privateRequest('Balance');
  state.balances.clear();
  
  for (const [asset, amount] of Object.entries(balances)) {
    const bal = parseFloat(amount as string);
    if (bal > 0) {
      state.balances.set(asset, bal);
    }
  }
}

async function getOpenPositions(): Promise<void> {
  try {
    const orders = await privateRequest('OpenOrders');
    // Could update positions from open orders here
  } catch (e) {
    // Ignore
  }
}

async function placeOrder(pair: string, side: 'buy' | 'sell', volume: number): Promise<string | null> {
  const pairInfo = state.allPairs.get(pair);
  if (!pairInfo) return null;
  
  const volumeStr = volume.toFixed(pairInfo.lotDecimals);
  console.log(`\n🎯 ${side.toUpperCase()} ${volumeStr} ${pairInfo.altname}`);
  
  try {
    const result = await privateRequest('AddOrder', {
      pair,
      type: side,
      ordertype: 'market',
      volume: volumeStr,
    });
    
    const orderId = result.txid?.[0] || 'unknown';
    console.log(`✅ Order filled! ID: ${orderId}`);
    state.trades.total++;
    return orderId;
  } catch (e: any) {
    console.log(`❌ Order failed: ${e.message}`);
    return null;
  }
}

// ═══════════════════════════════════════════════════════════════════════════════
// TRADING LOGIC
// ═══════════════════════════════════════════════════════════════════════════════

async function processMarket(pairInfo: TradingPair, data: MarketData): Promise<void> {
  // Skip low volume
  if (data.volumeUSD < CONFIG.MIN_VOLUME_USD) return;
  
  const lambda = computeLambda(data.pair, data);
  const coherence = computeCoherence(data);
  const freq = getFrequency(lambda, coherence);
  
  // Check existing position
  const existingPos = state.positions.get(data.pair);
  
  if (existingPos) {
    // Check exit conditions
    const pnlPct = existingPos.side === 'buy'
      ? ((data.price - existingPos.price) / existingPos.price) * 100
      : ((existingPos.price - data.price) / existingPos.price) * 100;
    
    if (pnlPct >= CONFIG.TAKE_PROFIT || pnlPct <= -CONFIG.STOP_LOSS) {
      const reason = pnlPct >= CONFIG.TAKE_PROFIT ? '🎯 TP' : '🛑 SL';
      console.log(`\n${reason} ${data.altname} ${pnlPct >= 0 ? '+' : ''}${pnlPct.toFixed(2)}%`);
      
      const closeSide = existingPos.side === 'buy' ? 'sell' : 'buy';
      if (await placeOrder(data.pair, closeSide, existingPos.volume)) {
        state.positions.delete(data.pair);
        state.pnl += existingPos.volume * existingPos.price * (pnlPct / 100);
        if (pnlPct > 0) state.trades.wins++;
        else state.trades.losses++;
        await getBalances();
      }
    }
    return;
  }
  
  // Skip if no signal or max positions reached
  if (coherence < CONFIG.COHERENCE_THRESHOLD) return;
  if (state.positions.size >= CONFIG.MAX_POSITIONS) return;
  
  // Determine direction
  let signal: 'BUY' | 'SELL' | 'HOLD' = 'HOLD';
  if (data.change <= -CONFIG.ENTRY_THRESHOLD) signal = 'BUY';
  else if (data.change >= CONFIG.ENTRY_THRESHOLD) signal = 'SELL';
  
  if (signal === 'HOLD') return;
  
  // Get available balance
  const usdBalance = state.balances.get('ZUSD') || state.balances.get('USD') || 0;
  const baseBalance = state.balances.get(pairInfo.base) || 0;
  
  let volume = 0;
  let side: 'buy' | 'sell' = 'buy';
  
  if (signal === 'BUY' && usdBalance > 10) {
    const tradeAmount = Math.min(usdBalance * (CONFIG.RISK_PERCENT / 100), 50);
    volume = tradeAmount / data.ask;
    side = 'buy';
  } else if (signal === 'SELL' && baseBalance * data.bid > 10) {
    volume = baseBalance * (CONFIG.RISK_PERCENT / 100);
    side = 'sell';
  } else {
    return;
  }
  
  if (volume < pairInfo.orderMin) return;
  
  console.log(`\n${freq.color} [${data.altname}] Λ=${lambda.toFixed(2)} Γ=${coherence.toFixed(3)} ${freq.hz.toFixed(0)}Hz`);
  console.log(`   ${signal} @ $${data.price.toFixed(pairInfo.pairDecimals)} (${data.change >= 0 ? '+' : ''}${data.change.toFixed(2)}%)`);
  
  const orderId = await placeOrder(data.pair, side, volume);
  if (orderId) {
    state.positions.set(data.pair, {
      pair: data.pair,
      side,
      price: side === 'buy' ? data.ask : data.bid,
      volume,
      orderId,
      entryTime: new Date(),
    });
    await getBalances();
  }
}

// ═══════════════════════════════════════════════════════════════════════════════
// DISPLAY
// ═══════════════════════════════════════════════════════════════════════════════

function displayStatus(markets: Map<string, MarketData>): void {
  const elapsed = (Date.now() - state.startTime.getTime()) / 1000 / 60;
  const winRate = state.trades.total > 0 ? (state.trades.wins / state.trades.total * 100) : 0;
  
  // Find top movers
  const sorted = [...markets.values()]
    .filter(m => m.volumeUSD > CONFIG.MIN_VOLUME_USD)
    .sort((a, b) => Math.abs(b.change) - Math.abs(a.change))
    .slice(0, 5);
  
  console.log(`
╔═══════════════════════════════════════════════════════════════════════════════╗
║  🐙 KRAKEN FULL TRADER - ${new Date().toLocaleTimeString()} - ALL PAIRS 🐙                 ║
╠═══════════════════════════════════════════════════════════════════════════════╣
║  ⏱️  ${elapsed.toFixed(1)}min | 📊 Pairs: ${state.tradablePairs.length} | 🔄 Cycle: ${state.cycle}                          ║
║  💰 Positions: ${state.positions.size}/${CONFIG.MAX_POSITIONS} | Trades: ${state.trades.total} (W:${state.trades.wins} L:${state.trades.losses}) | WR: ${winRate.toFixed(0)}%    ║
║  📈 Realized PnL: $${state.pnl.toFixed(2)}                                                  ║
╚═══════════════════════════════════════════════════════════════════════════════╝`);

  // Show top movers
  console.log(`  📊 Top Movers:`);
  for (const m of sorted) {
    const arrow = m.change >= 0 ? '📈' : '📉';
    console.log(`     ${arrow} ${m.altname}: $${m.price.toFixed(4)} (${m.change >= 0 ? '+' : ''}${m.change.toFixed(2)}%) Vol: $${(m.volumeUSD/1000000).toFixed(1)}M`);
  }
  
  // Show balances
  console.log(`  💰 Balances:`);
  state.balances.forEach((bal, asset) => {
    if (bal > 0.0001) {
      console.log(`     ${asset}: ${bal.toFixed(8)}`);
    }
  });
  
  // Show positions
  if (state.positions.size > 0) {
    console.log(`  📍 Open Positions:`);
    state.positions.forEach((pos, pair) => {
      const market = markets.get(pair);
      if (market) {
        const pnlPct = pos.side === 'buy'
          ? ((market.price - pos.price) / pos.price) * 100
          : ((pos.price - market.price) / pos.price) * 100;
        console.log(`     ${pos.side.toUpperCase()} ${market.altname}: ${pnlPct >= 0 ? '+' : ''}${pnlPct.toFixed(2)}%`);
      }
    });
  }
}

// ═══════════════════════════════════════════════════════════════════════════════
// MAIN TRADING LOOP
// ═══════════════════════════════════════════════════════════════════════════════

async function tradingCycle(): Promise<void> {
  state.cycle++;
  
  try {
    // Get all market data in ONE call
    const markets = await getAllTickers();
    
    // Process each market
    for (const [pair, data] of markets) {
      const pairInfo = state.allPairs.get(pair);
      if (!pairInfo) continue;
      
      await processMarket(pairInfo, data);
    }
    
    // Refresh balances every 10 cycles
    if (state.cycle % 10 === 0) {
      await getBalances();
    }
    
    // Display status every 5 cycles
    if (state.cycle % 5 === 0) {
      displayStatus(markets);
    }
    
  } catch (e: any) {
    console.log(`⚠️ ${e.message}`);
  }
}

// ═══════════════════════════════════════════════════════════════════════════════
// MAIN
// ═══════════════════════════════════════════════════════════════════════════════

async function run(): Promise<void> {
  console.log(`
╔═══════════════════════════════════════════════════════════════════════════════╗
║                                                                               ║
║   🐙 KRAKEN FULL TRADER - ALL PAIRS 🐙                                       ║
║                                                                               ║
║   ██╗  ██╗██████╗  █████╗ ██╗  ██╗███████╗███╗   ██╗                         ║
║   ██║ ██╔╝██╔══██╗██╔══██╗██║ ██╔╝██╔════╝████╗  ██║                         ║
║   █████╔╝ ██████╔╝███████║█████╔╝ █████╗  ██╔██╗ ██║                         ║
║   ██╔═██╗ ██╔══██╗██╔══██║██╔═██╗ ██╔══╝  ██║╚██╗██║                         ║
║   ██║  ██╗██║  ██║██║  ██║██║  ██╗███████╗██║ ╚████║                         ║
║   ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝╚══════╝╚═╝  ╚═══╝                         ║
║                                                                               ║
║   🔴 TRADES ALL USD/EUR PAIRS - FULL MARKET COVERAGE 🔴                      ║
║                                                                               ║
║   Features:                                                                   ║
║     • Dynamically loads ALL trading pairs (like Binance)                     ║
║     • 9 Auris Nodes coherence analysis                                       ║
║     • Mean reversion + momentum strategy                                     ║
║     • Automatic position management                                          ║
║                                                                               ║
║   Strategy:                                                                   ║
║     • Coherence Γ > 0.76 = Valid signal                                      ║
║     • BUY when down ≥ 1.5%                                                   ║
║     • SELL when up ≥ 1.5%                                                    ║
║     • Take Profit: 2% | Stop Loss: 1%                                        ║
║                                                                               ║
║   Author: Gary Leckey - "Release the Kraken!" 🦆                             ║
║                                                                               ║
╚═══════════════════════════════════════════════════════════════════════════════╝
`);

  if (!CONFIG.API_KEY || !CONFIG.API_SECRET) {
    console.log('❌ Missing Kraken API credentials!');
    console.log('');
    console.log('To set up Kraken:');
    console.log('1. Go to https://www.kraken.com/u/security/api');
    console.log('2. Create a new API key with these permissions:');
    console.log('   ✅ Query Funds');
    console.log('   ✅ Query Open Orders & Trades');
    console.log('   ✅ Query Closed Orders & Trades');
    console.log('   ✅ Create & Modify Orders');
    console.log('');
    console.log('3. Add to your .env file:');
    console.log('   KRAKEN_API_KEY=your_api_key');
    console.log('   KRAKEN_API_SECRET=your_api_secret');
    console.log('');
    return;
  }
  
  console.log('🔐 Connecting to Kraken...');
  
  try {
    // Load all trading pairs
    await loadAllPairs();
    
    // Get balances
    await getBalances();
    
    console.log('\n💰 Your Balances:');
    if (state.balances.size === 0) {
      console.log('   (No balances - deposit funds to trade)');
    } else {
      state.balances.forEach((bal, asset) => {
        console.log(`   ${asset}: ${bal.toFixed(8)}`);
      });
    }
    
    console.log(`\n🚀 Starting Kraken Full Trader on ${state.tradablePairs.length} pairs...`);
    console.log(`${'═'.repeat(70)}`);
    
    // Main loop
    while (true) {
      await tradingCycle();
      await new Promise(r => setTimeout(r, CONFIG.SCAN_INTERVAL));
    }
    
  } catch (e: any) {
    console.log(`❌ Connection failed: ${e.message}`);
    console.log('');
    console.log('Check your API key and secret are correct.');
  }
}

run().catch(console.error);
