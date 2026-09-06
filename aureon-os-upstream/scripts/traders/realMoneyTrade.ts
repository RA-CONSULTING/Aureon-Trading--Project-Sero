/**
 * 🔥 REAL MONEY TRADING ENGINE 🔥
 * 
 * THE SONG OF SPACE AND TIME - LIVE EDITION
 * 
 * ⚠️ WARNING: THIS USES REAL MONEY! ⚠️
 * 
 * Safety Features:
 * - Maximum position limits
 * - Daily loss limits
 * - Kill switch
 * - Confirmation prompts
 * - Audit logging
 * 
 * Setup:
 * 1. Set your Binance API keys:
 *    export BINANCE_API_KEY="your_real_api_key"
 *    export BINANCE_API_SECRET="your_real_api_secret"
 * 
 * 2. Run with safety confirmations:
 *    npm run trade:real
 */

import crypto from 'node:crypto';
import fs from 'node:fs';
import readline from 'node:readline';

// ═══════════════════════════════════════════════════════════════════════════
// SAFETY CONFIGURATION - MODIFY THESE CAREFULLY!
// ═══════════════════════════════════════════════════════════════════════════

// Auto-detect testnet vs live based on environment
const USE_TESTNET = process.env.BINANCE_TESTNET === 'true' || process.env.USE_TESTNET === '1';
const BINANCE_URL = USE_TESTNET 
  ? 'https://testnet.binance.vision'
  : 'https://api.binance.com';

// ⚠️ SAFETY LIMITS ⚠️
const MAX_POSITION_SIZE_USD = Number(process.env.MAX_POSITION_USD || '10');     // Max $10 per position
const MAX_TOTAL_EXPOSURE_USD = Number(process.env.MAX_EXPOSURE_USD || '100');   // Max $100 total
const MAX_DAILY_LOSS_USD = Number(process.env.MAX_DAILY_LOSS_USD || '20');      // Stop if lose $20
const MAX_POSITIONS = Number(process.env.MAX_POSITIONS || '5');                  // Max 5 positions
const REQUIRE_CONFIRMATION = process.env.SKIP_CONFIRM !== '1';                   // Require user confirmation

// API Keys (from environment)
const API_KEY = process.env.BINANCE_API_KEY || '';
const API_SECRET = process.env.BINANCE_API_SECRET || '';

// Trading parameters
const ENTRY_COHERENCE = 0.95;  // Higher threshold for real money
const EXIT_COHERENCE = 0.93;
const TAKE_PROFIT_PCT = 0.012; // 1.2% take profit
const STOP_LOSS_PCT = 0.005;   // 0.5% stop loss - TIGHT!
const TRAILING_STOP_PCT = 0.003;

// Scan configuration
const SCAN_INTERVAL_MS = 3000;
const QUOTE_ASSET = 'USDT';

// Audit log
const AUDIT_LOG_PATH = './trade_audit.log';

// ═══════════════════════════════════════════════════════════════════════════
// Types
// ═══════════════════════════════════════════════════════════════════════════

interface Position {
  id: string;
  symbol: string;
  orderId: number;
  entryPrice: number;
  quantity: number;
  entryTime: Date;
  peakPrice: number;
  notionalValue: number;
}

interface Trade {
  id: string;
  symbol: string;
  side: 'BUY' | 'SELL';
  entryPrice: number;
  exitPrice: number;
  quantity: number;
  pnl: number;
  pnlPercent: number;
  timestamp: Date;
  reason: string;
}

// ═══════════════════════════════════════════════════════════════════════════
// Binance API (REAL)
// ═══════════════════════════════════════════════════════════════════════════

function createSignature(queryString: string): string {
  return crypto.createHmac('sha256', API_SECRET).update(queryString).digest('hex');
}

async function binanceRequest(
  endpoint: string,
  method: 'GET' | 'POST' | 'DELETE' = 'GET',
  params: Record<string, string | number> = {},
  signed = false
): Promise<any> {
  const url = new URL(endpoint, BINANCE_URL);
  
  if (signed) {
    params.timestamp = Date.now();
    params.recvWindow = 10000;
  }
  
  const queryString = Object.entries(params)
    .map(([k, v]) => `${k}=${encodeURIComponent(v)}`)
    .join('&');
  
  if (signed) {
    const signature = createSignature(queryString);
    url.search = `${queryString}&signature=${signature}`;
  } else if (queryString) {
    url.search = queryString;
  }
  
  const headers: Record<string, string> = {
    'X-MBX-APIKEY': API_KEY
  };
  
  const response = await fetch(url.toString(), { method, headers });
  const data = await response.json();
  
  if (!response.ok) {
    throw new Error(`Binance API error: ${JSON.stringify(data)}`);
  }
  
  return data;
}

// ═══════════════════════════════════════════════════════════════════════════
// Audit Logging
// ═══════════════════════════════════════════════════════════════════════════

function auditLog(message: string, data?: any) {
  const timestamp = new Date().toISOString();
  const logLine = `[${timestamp}] ${message}${data ? ' | ' + JSON.stringify(data) : ''}\n`;
  
  console.log(`  📝 ${message}`);
  
  try {
    fs.appendFileSync(AUDIT_LOG_PATH, logLine);
  } catch (e) {
    // Ignore file errors
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// User Confirmation
// ═══════════════════════════════════════════════════════════════════════════

async function confirm(message: string): Promise<boolean> {
  if (!REQUIRE_CONFIRMATION) return true;
  
  const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout
  });
  
  return new Promise((resolve) => {
    rl.question(`  ⚠️  ${message} (yes/no): `, (answer) => {
      rl.close();
      resolve(answer.toLowerCase() === 'yes' || answer.toLowerCase() === 'y');
    });
  });
}

// ═══════════════════════════════════════════════════════════════════════════
// Coherence Calculator
// ═══════════════════════════════════════════════════════════════════════════

class CoherenceEngine {
  private priceHistory: Map<string, number[]> = new Map();
  
  update(symbol: string, price: number): { coherence: number; velocity: number } {
    if (!this.priceHistory.has(symbol)) {
      this.priceHistory.set(symbol, []);
    }
    
    const history = this.priceHistory.get(symbol)!;
    history.push(price);
    if (history.length > 20) history.shift();
    
    if (history.length < 5) return { coherence: 0.5, velocity: 0 };
    
    const returns = history.slice(1).map((p, i) => (p - history[i]) / history[i]);
    const positiveReturns = returns.filter(r => r > 0).length;
    const trendStrength = Math.abs(positiveReturns / returns.length - 0.5) * 2;
    
    const recentReturns = returns.slice(-3);
    const recentAvg = recentReturns.reduce((a, b) => a + b, 0) / recentReturns.length;
    const overallAvg = returns.reduce((a, b) => a + b, 0) / returns.length;
    const momentumAlign = (recentAvg > 0 && overallAvg > 0) ? 1 : 0;
    
    const variance = returns.reduce((s, r) => s + r * r, 0) / returns.length;
    const volFactor = Math.max(0.5, 1 - Math.sqrt(variance) * 10);
    
    const coherence = 0.5 + (trendStrength * 0.3 + momentumAlign * 0.2) * volFactor;
    
    return { 
      coherence: Math.min(1, Math.max(0.5, coherence)), 
      velocity: recentAvg 
    };
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// REAL MONEY TRADING ENGINE
// ═══════════════════════════════════════════════════════════════════════════

class RealMoneyEngine {
  private positions: Map<string, Position> = new Map();
  private trades: Trade[] = [];
  private coherenceEngine = new CoherenceEngine();
  private balance: number = 0;
  private dailyPnL: number = 0;
  private isRunning: boolean = false;
  private killSwitch: boolean = false;
  
  async start() {
    this.printBanner();
    
    // Check for API keys
    if (!API_KEY || !API_SECRET) {
      console.log('');
      console.log('  ❌ NO API KEYS FOUND!');
      console.log('');
      console.log('  To trade with real money, set your Binance API keys:');
      console.log('');
      console.log('  export BINANCE_API_KEY="your_api_key"');
      console.log('  export BINANCE_API_SECRET="your_api_secret"');
      console.log('');
      console.log('  Then run: npm run trade:real');
      console.log('');
      return;
    }
    
    try {
      // Test connection
      console.log(`  🔗 Connecting to Binance ${USE_TESTNET ? 'TESTNET' : 'LIVE'}...`);
      await binanceRequest('/api/v3/ping');
      console.log(`  ✅ Connected to Binance ${USE_TESTNET ? 'TESTNET' : 'LIVE'}`);
      console.log(`  🌐 URL: ${BINANCE_URL}`);
      
      // Get account info
      const account = await binanceRequest('/api/v3/account', 'GET', {}, true);
      const usdtBalance = account.balances.find((b: any) => b.asset === 'USDT');
      this.balance = parseFloat(usdtBalance?.free || '0');
      
      console.log('');
      console.log('  ═══════════════════════════════════════════════════════════');
      console.log(`  💰 USDT Balance: $${this.balance.toFixed(2)}`);
      console.log(`  📊 Max Position Size: $${MAX_POSITION_SIZE_USD}`);
      console.log(`  🛡️  Max Total Exposure: $${MAX_TOTAL_EXPOSURE_USD}`);
      console.log(`  🚨 Daily Loss Limit: $${MAX_DAILY_LOSS_USD}`);
      console.log(`  🤖 Max Positions: ${MAX_POSITIONS}`);
      console.log('  ═══════════════════════════════════════════════════════════');
      console.log('');
      
      // Safety check
      if (this.balance < MAX_POSITION_SIZE_USD) {
        console.log(`  ⚠️  Insufficient balance. Need at least $${MAX_POSITION_SIZE_USD}`);
        return;
      }
      
      // Confirm with user
      const confirmed = await confirm('START REAL MONEY TRADING?');
      if (!confirmed) {
        console.log('  ❌ Cancelled by user');
        return;
      }
      
      auditLog('TRADING SESSION STARTED', { balance: this.balance });
      
      this.isRunning = true;
      await this.tradingLoop();
      
    } catch (error) {
      console.error('  ❌ Error:', error);
      auditLog('ERROR', { error: String(error) });
    }
  }
  
  private printBanner() {
    console.log('\n');
    if (USE_TESTNET) {
      console.log('  ╔═══════════════════════════════════════════════════════════╗');
      console.log('  ║  🎮 T E S T N E T   T R A D I N G   E N G I N E        🎮  ║');
      console.log('  ║                                                           ║');
      console.log('  ║         💚 PAPER MODE - NO REAL FUNDS AT RISK 💚         ║');
      console.log('  ║                                                           ║');
      console.log('  ║    "We practice our dance before the real stakes begin,  ║');
      console.log('  ║     Every trade a rehearsal, preparing to win."          ║');
      console.log('  ╚═══════════════════════════════════════════════════════════╝');
    } else {
      console.log('  ╔═══════════════════════════════════════════════════════════╗');
      console.log('  ║  🔥 R E A L   M O N E Y   T R A D I N G   E N G I N E 🔥  ║');
      console.log('  ║                                                           ║');
      console.log('  ║         ⚠️  WARNING: USING REAL FUNDS! ⚠️                ║');
      console.log('  ║                                                           ║');
      console.log('  ║    "We dance through space and time, with real stakes,   ║');
      console.log('  ║     Every trade a note, every profit we take."           ║');
      console.log('  ╚═══════════════════════════════════════════════════════════╝');
    }
    console.log('');
  }
  
  private async tradingLoop() {
    const symbols = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT', 'XRPUSDT']; // Start with majors
    
    console.log(`  🎵 Trading: ${symbols.join(', ')}`);
    console.log('  ─────────────────────────────────────────────────────────');
    console.log('');
    
    while (this.isRunning && !this.killSwitch) {
      // Check daily loss limit
      if (this.dailyPnL <= -MAX_DAILY_LOSS_USD) {
        console.log('');
        console.log('  🚨 DAILY LOSS LIMIT HIT! Stopping trading.');
        auditLog('DAILY LOSS LIMIT HIT', { dailyPnL: this.dailyPnL });
        break;
      }
      
      try {
        // Fetch prices
        const tickers = await binanceRequest('/api/v3/ticker/price');
        const priceMap = new Map<string, number>(tickers.map((t: any) => [t.symbol, parseFloat(t.price)]));
        
        // Check exits first
        for (const [id, position] of this.positions) {
          const price = priceMap.get(position.symbol);
          if (price === undefined) continue;
          
          position.peakPrice = Math.max(position.peakPrice, price);
          const pnlPercent = (price - position.entryPrice) / position.entryPrice;
          const drawdown = (position.peakPrice - price) / position.peakPrice;
          
          let exitReason = '';
          
          if (pnlPercent >= TAKE_PROFIT_PCT) exitReason = '🎯 TAKE PROFIT';
          else if (pnlPercent <= -STOP_LOSS_PCT) exitReason = '🛡️ STOP LOSS';
          else if (pnlPercent > 0.003 && drawdown > TRAILING_STOP_PCT) exitReason = '📉 TRAILING';
          
          if (exitReason) {
            await this.closePosition(position, price, exitReason);
          }
        }
        
        // Check entries
        for (const symbol of symbols) {
          const price = priceMap.get(symbol);
          if (price === undefined) continue;
          
          const { coherence, velocity } = this.coherenceEngine.update(symbol, price);
          
          // Check if we can enter
          const currentExposure = this.getTotalExposure();
          const canEnter = 
            coherence >= ENTRY_COHERENCE &&
            velocity > 0 &&
            this.positions.size < MAX_POSITIONS &&
            currentExposure + MAX_POSITION_SIZE_USD <= MAX_TOTAL_EXPOSURE_USD &&
            !this.hasPositionFor(symbol);
          
          if (canEnter) {
            await this.openPosition(symbol, price, coherence);
          }
        }
        
        // Status update
        this.printStatus();
        
        await this.sleep(SCAN_INTERVAL_MS);
        
      } catch (error) {
        console.error('  ⚠️ Error:', error);
        auditLog('LOOP ERROR', { error: String(error) });
        await this.sleep(SCAN_INTERVAL_MS * 2);
      }
    }
    
    // Close all positions on shutdown
    await this.closeAllPositions('SHUTDOWN');
    this.printFinalReport();
  }
  
  private async openPosition(symbol: string, price: number, coherence: number) {
    try {
      // Calculate quantity
      const quantity = MAX_POSITION_SIZE_USD / price;
      
      // Get symbol info for precision
      const exchangeInfo = await binanceRequest('/api/v3/exchangeInfo', 'GET', { symbol });
      const symbolInfo = exchangeInfo.symbols[0];
      const lotSize = symbolInfo.filters.find((f: any) => f.filterType === 'LOT_SIZE');
      const stepSize = parseFloat(lotSize.stepSize);
      const precision = Math.max(0, Math.round(-Math.log10(stepSize)));
      const adjustedQty = Math.floor(quantity / stepSize) * stepSize;
      
      if (adjustedQty <= 0) {
        console.log(`  ⚠️ Quantity too small for ${symbol}`);
        return;
      }
      
      // Place REAL order
      auditLog('PLACING BUY ORDER', { symbol, quantity: adjustedQty, price });
      
      const order = await binanceRequest('/api/v3/order', 'POST', {
        symbol,
        side: 'BUY',
        type: 'MARKET',
        quantity: adjustedQty.toFixed(precision)
      }, true);
      
      const fillPrice = parseFloat(order.fills?.[0]?.price || price);
      const fillQty = parseFloat(order.executedQty);
      const notional = fillPrice * fillQty;
      
      const position: Position = {
        id: `POS-${Date.now()}`,
        symbol,
        orderId: order.orderId,
        entryPrice: fillPrice,
        quantity: fillQty,
        entryTime: new Date(),
        peakPrice: fillPrice,
        notionalValue: notional
      };
      
      this.positions.set(position.id, position);
      
      console.log(`  🟢 BOUGHT ${symbol} @ $${fillPrice.toFixed(2)} | Qty: ${fillQty} | Value: $${notional.toFixed(2)}`);
      auditLog('BUY EXECUTED', { symbol, price: fillPrice, quantity: fillQty, orderId: order.orderId });
      
    } catch (error) {
      console.error(`  ❌ Failed to buy ${symbol}:`, error);
      auditLog('BUY FAILED', { symbol, error: String(error) });
    }
  }
  
  private async closePosition(position: Position, price: number, reason: string) {
    try {
      auditLog('PLACING SELL ORDER', { symbol: position.symbol, quantity: position.quantity, reason });
      
      const order = await binanceRequest('/api/v3/order', 'POST', {
        symbol: position.symbol,
        side: 'SELL',
        type: 'MARKET',
        quantity: position.quantity
      }, true);
      
      const fillPrice = parseFloat(order.fills?.[0]?.price || price);
      const pnl = (fillPrice - position.entryPrice) * position.quantity;
      const pnlPercent = (fillPrice - position.entryPrice) / position.entryPrice;
      
      this.dailyPnL += pnl;
      
      this.trades.push({
        id: position.id,
        symbol: position.symbol,
        side: 'SELL',
        entryPrice: position.entryPrice,
        exitPrice: fillPrice,
        quantity: position.quantity,
        pnl,
        pnlPercent,
        timestamp: new Date(),
        reason
      });
      
      this.positions.delete(position.id);
      
      const emoji = pnl >= 0 ? '🟢' : '🔴';
      console.log(`  ${emoji} SOLD ${position.symbol} @ $${fillPrice.toFixed(2)} | PnL: $${pnl.toFixed(2)} (${(pnlPercent * 100).toFixed(2)}%) | ${reason}`);
      auditLog('SELL EXECUTED', { symbol: position.symbol, price: fillPrice, pnl, reason });
      
    } catch (error) {
      console.error(`  ❌ Failed to sell ${position.symbol}:`, error);
      auditLog('SELL FAILED', { symbol: position.symbol, error: String(error) });
    }
  }
  
  private async closeAllPositions(reason: string) {
    console.log('');
    console.log(`  📤 Closing all positions (${reason})...`);
    
    for (const [id, position] of this.positions) {
      try {
        const ticker = await binanceRequest('/api/v3/ticker/price', 'GET', { symbol: position.symbol });
        const price = parseFloat(ticker.price);
        await this.closePosition(position, price, reason);
      } catch (error) {
        console.error(`  ❌ Failed to close ${position.symbol}`);
      }
    }
  }
  
  private getTotalExposure(): number {
    let total = 0;
    for (const position of this.positions.values()) {
      total += position.notionalValue;
    }
    return total;
  }
  
  private hasPositionFor(symbol: string): boolean {
    for (const position of this.positions.values()) {
      if (position.symbol === symbol) return true;
    }
    return false;
  }
  
  private printStatus() {
    const exposure = this.getTotalExposure();
    const winners = this.trades.filter(t => t.pnl > 0).length;
    const hitRate = this.trades.length > 0 ? (winners / this.trades.length * 100).toFixed(1) : '0.0';
    
    console.log(`  📊 ${new Date().toISOString().slice(11, 19)} | Pos: ${this.positions.size}/${MAX_POSITIONS} | Exposure: $${exposure.toFixed(2)} | Daily PnL: $${this.dailyPnL.toFixed(2)} | Trades: ${this.trades.length} (${hitRate}%)`);
  }
  
  private printFinalReport() {
    const winners = this.trades.filter(t => t.pnl > 0);
    const totalPnl = this.trades.reduce((s, t) => s + t.pnl, 0);
    const hitRate = this.trades.length > 0 ? winners.length / this.trades.length : 0;
    
    console.log('\n');
    console.log('  ═══════════════════════════════════════════════════════════');
    console.log('  ✧  S E S S I O N   C O M P L E T E  ✧');
    console.log('  ═══════════════════════════════════════════════════════════');
    console.log('');
    console.log(`  📊 Total Trades: ${this.trades.length}`);
    console.log(`  🏆 Winners: ${winners.length} | Losers: ${this.trades.length - winners.length}`);
    console.log(`  🎯 Hit Rate: ${(hitRate * 100).toFixed(2)}%`);
    console.log(`  💰 Session PnL: $${totalPnl.toFixed(2)}`);
    console.log('');
    
    if (this.trades.length > 0) {
      console.log('  📜 Trade Log:');
      this.trades.forEach(t => {
        const emoji = t.pnl >= 0 ? '🟢' : '🔴';
        console.log(`     ${emoji} ${t.symbol}: $${t.pnl.toFixed(2)} (${(t.pnlPercent * 100).toFixed(2)}%) - ${t.reason}`);
      });
    }
    
    console.log('');
    console.log('  ─────────────────────────────────────────────────────────');
    console.log('  🎵 "Through real stakes we danced, our profits enhanced." 🎵');
    console.log('  ─────────────────────────────────────────────────────────');
    console.log('');
    
    auditLog('SESSION ENDED', { trades: this.trades.length, pnl: totalPnl });
  }
  
  private sleep(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
  
  stop() {
    this.isRunning = false;
  }
  
  emergencyStop() {
    this.killSwitch = true;
    this.isRunning = false;
    console.log('\n  🚨 EMERGENCY STOP ACTIVATED!');
    auditLog('EMERGENCY STOP');
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// Main Entry
// ═══════════════════════════════════════════════════════════════════════════

const engine = new RealMoneyEngine();

process.on('SIGINT', () => {
  console.log('\n  ⏹️  Stopping trading...');
  engine.stop();
});

process.on('SIGTERM', () => {
  engine.emergencyStop();
});

engine.start().catch(console.error);
