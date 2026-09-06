/**
 * 🎵 LIVE MARKET SYMPHONY 🎵
 * 
 * Real-Time Market Prices Across All Platforms
 * 
 *   ╔═══════════════════════════════════════════════════════════════════════════╗
 *   ║   🌍 LIVE MULTI-BROKER TRADING WITH REAL PRICES 🌍                       ║
 *   ║                                                                           ║
 *   ║   CRYPTO:   Binance • Kraken • Coinbase • Bitstamp • Gemini • OKX        ║
 *   ║   FOREX:    OANDA • FXCM • Saxo • IB                                     ║
 *   ║   STOCKS:   Alpaca • IB • Saxo                                           ║
 *   ║   CFD:      Capital.com • IG • CMC                                       ║
 *   ║                                                                           ║
 *   ║   🎁 TAX FREE: IG Markets & CMC Markets (Spread Betting)                 ║
 *   ║                                                                           ║
 *   ╚═══════════════════════════════════════════════════════════════════════════╝
 * 
 * Author: Gary Leckey - R&A Consulting
 */

import * as dotenv from 'dotenv';
import * as path from 'path';
import { fileURLToPath } from 'url';
import * as crypto from 'crypto';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

dotenv.config({ path: path.join(__dirname, '..', '.env') });

// ═══════════════════════════════════════════════════════════════════════════
// Configuration
// ═══════════════════════════════════════════════════════════════════════════

const CONFIG = {
  BALANCE_PER_BROKER: 20,
  ENTRY_COHERENCE: 0.938,
  EXIT_COHERENCE: 0.934,
  POSITION_SIZE_PCT: 0.10,
  STOP_LOSS_PCT: 0.02,
  TAKE_PROFIT_PCT: 0.04,
  MAX_POSITIONS_PER_BROKER: 3,
  SCAN_INTERVAL_MS: 10000, // 10 seconds for live data
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
  timestamp: Date;
  source: string;
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

interface BrokerStatus {
  name: string;
  emoji: string;
  connected: boolean;
  balance: number;
  positions: number;
  wins: number;
  losses: number;
  pnl: number;
  taxFree: boolean;
  lastUpdate: Date;
}

// ═══════════════════════════════════════════════════════════════════════════
// BINANCE - Real Prices (Public API)
// ═══════════════════════════════════════════════════════════════════════════

class BinancePriceFeed {
  private baseUrl = 'https://api.binance.com';
  
  // All major trading pairs
  readonly symbols = [
    'BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT', 'XRPUSDT',
    'DOGEUSDT', 'ADAUSDT', 'AVAXUSDT', 'DOTUSDT', 'LINKUSDT',
    'MATICUSDT', 'ATOMUSDT', 'LTCUSDT', 'NEARUSDT', 'UNIUSDT',
    'AAVEUSDT', 'SHIBUSDT', 'APTUSDT', 'ARBUSDT', 'OPUSDT'
  ];

  async getPrice(symbol: string): Promise<LivePrice | null> {
    try {
      const response = await fetch(`${this.baseUrl}/api/v3/ticker/bookTicker?symbol=${symbol}`);
      if (!response.ok) return null;
      
      const data = await response.json();
      const bid = parseFloat(data.bidPrice);
      const ask = parseFloat(data.askPrice);
      
      return {
        symbol,
        bid,
        ask,
        mid: (bid + ask) / 2,
        spread: ask - bid,
        timestamp: new Date(),
        source: 'Binance'
      };
    } catch {
      return null;
    }
  }

  async getAllPrices(): Promise<LivePrice[]> {
    try {
      const response = await fetch(`${this.baseUrl}/api/v3/ticker/bookTicker`);
      if (!response.ok) return [];
      
      const data = await response.json();
      const prices: LivePrice[] = [];
      
      for (const symbol of this.symbols) {
        const ticker = data.find((t: any) => t.symbol === symbol);
        if (ticker) {
          const bid = parseFloat(ticker.bidPrice);
          const ask = parseFloat(ticker.askPrice);
          prices.push({
            symbol,
            bid,
            ask,
            mid: (bid + ask) / 2,
            spread: ask - bid,
            timestamp: new Date(),
            source: 'Binance'
          });
        }
      }
      
      return prices;
    } catch {
      return [];
    }
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// KRAKEN - Real Prices (Public API)
// ═══════════════════════════════════════════════════════════════════════════

class KrakenPriceFeed {
  private baseUrl = 'https://api.kraken.com';
  
  readonly symbols = [
    { pair: 'XXBTZGBP', display: 'BTC/GBP' },
    { pair: 'XETHZGBP', display: 'ETH/GBP' },
    { pair: 'XXBTZUSD', display: 'BTC/USD' },
    { pair: 'XETHZUSD', display: 'ETH/USD' },
    { pair: 'SOLUSD', display: 'SOL/USD' },
    { pair: 'XRPUSD', display: 'XRP/USD' },
    { pair: 'ADAUSD', display: 'ADA/USD' },
    { pair: 'DOTUSD', display: 'DOT/USD' },
    { pair: 'LINKUSD', display: 'LINK/USD' },
    { pair: 'ATOMUSD', display: 'ATOM/USD' }
  ];

  async getPrice(pair: string): Promise<LivePrice | null> {
    try {
      const response = await fetch(`${this.baseUrl}/0/public/Ticker?pair=${pair}`);
      if (!response.ok) return null;
      
      const data = await response.json();
      if (data.error && data.error.length > 0) return null;
      
      const key = Object.keys(data.result)[0];
      const ticker = data.result[key];
      const bid = parseFloat(ticker.b[0]);
      const ask = parseFloat(ticker.a[0]);
      
      return {
        symbol: pair,
        bid,
        ask,
        mid: (bid + ask) / 2,
        spread: ask - bid,
        timestamp: new Date(),
        source: 'Kraken'
      };
    } catch {
      return null;
    }
  }

  async getAllPrices(): Promise<LivePrice[]> {
    const pairs = this.symbols.map(s => s.pair).join(',');
    try {
      const response = await fetch(`${this.baseUrl}/0/public/Ticker?pair=${pairs}`);
      if (!response.ok) return [];
      
      const data = await response.json();
      if (data.error && data.error.length > 0) return [];
      
      const prices: LivePrice[] = [];
      for (const [key, ticker] of Object.entries(data.result) as any) {
        const bid = parseFloat(ticker.b[0]);
        const ask = parseFloat(ticker.a[0]);
        prices.push({
          symbol: key,
          bid,
          ask,
          mid: (bid + ask) / 2,
          spread: ask - bid,
          timestamp: new Date(),
          source: 'Kraken'
        });
      }
      
      return prices;
    } catch {
      return [];
    }
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// COINBASE - Real Prices (Public API)
// ═══════════════════════════════════════════════════════════════════════════

class CoinbasePriceFeed {
  private baseUrl = 'https://api.exchange.coinbase.com';
  
  readonly symbols = [
    'BTC-GBP', 'ETH-GBP', 'SOL-GBP', 'XRP-GBP', 'DOGE-GBP',
    'BTC-USD', 'ETH-USD', 'SOL-USD', 'ADA-USD', 'DOT-USD',
    'LINK-USD', 'AVAX-USD', 'MATIC-USD', 'ATOM-USD', 'UNI-USD'
  ];

  async getPrice(symbol: string): Promise<LivePrice | null> {
    try {
      const response = await fetch(`${this.baseUrl}/products/${symbol}/ticker`);
      if (!response.ok) return null;
      
      const data = await response.json();
      const bid = parseFloat(data.bid);
      const ask = parseFloat(data.ask);
      
      return {
        symbol,
        bid,
        ask,
        mid: (bid + ask) / 2,
        spread: ask - bid,
        timestamp: new Date(),
        source: 'Coinbase'
      };
    } catch {
      return null;
    }
  }

  async getAllPrices(): Promise<LivePrice[]> {
    const prices: LivePrice[] = [];
    
    // Coinbase requires individual requests per symbol
    for (const symbol of this.symbols) {
      const price = await this.getPrice(symbol);
      if (price) prices.push(price);
    }
    
    return prices;
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// BITSTAMP - Real Prices (Public API)
// ═══════════════════════════════════════════════════════════════════════════

class BitstampPriceFeed {
  private baseUrl = 'https://www.bitstamp.net/api/v2';
  
  readonly symbols = [
    'btcgbp', 'ethgbp', 'xrpgbp', 'ltcgbp', 'linkgbp',
    'btcusd', 'ethusd', 'xrpusd', 'solusd', 'adausd',
    'dogeusd', 'maticusd', 'avaxusd', 'uniusd', 'aaveusd'
  ];

  async getPrice(symbol: string): Promise<LivePrice | null> {
    try {
      const response = await fetch(`${this.baseUrl}/ticker/${symbol}/`);
      if (!response.ok) return null;
      
      const data = await response.json();
      const bid = parseFloat(data.bid);
      const ask = parseFloat(data.ask);
      
      return {
        symbol,
        bid,
        ask,
        mid: (bid + ask) / 2,
        spread: ask - bid,
        timestamp: new Date(),
        source: 'Bitstamp'
      };
    } catch {
      return null;
    }
  }

  async getAllPrices(): Promise<LivePrice[]> {
    const prices: LivePrice[] = [];
    
    for (const symbol of this.symbols) {
      const price = await this.getPrice(symbol);
      if (price) prices.push(price);
    }
    
    return prices;
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// GEMINI - Real Prices (Public API)
// ═══════════════════════════════════════════════════════════════════════════

class GeminiPriceFeed {
  private baseUrl = 'https://api.gemini.com/v1';
  
  readonly symbols = [
    'btcgbp', 'ethgbp', 'solgbp', 'linkgbp', 'dogegbp',
    'btcusd', 'ethusd', 'solusd', 'maticusd', 'aaveusd',
    'linkusd', 'uniusd', 'avaxusd', 'dotusd', 'atomusd'
  ];

  async getPrice(symbol: string): Promise<LivePrice | null> {
    try {
      const response = await fetch(`${this.baseUrl}/pubticker/${symbol}`);
      if (!response.ok) return null;
      
      const data = await response.json();
      const bid = parseFloat(data.bid);
      const ask = parseFloat(data.ask);
      
      return {
        symbol,
        bid,
        ask,
        mid: (bid + ask) / 2,
        spread: ask - bid,
        timestamp: new Date(),
        source: 'Gemini'
      };
    } catch {
      return null;
    }
  }

  async getAllPrices(): Promise<LivePrice[]> {
    const prices: LivePrice[] = [];
    
    for (const symbol of this.symbols) {
      const price = await this.getPrice(symbol);
      if (price) prices.push(price);
    }
    
    return prices;
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// OKX - Real Prices (Public API)
// ═══════════════════════════════════════════════════════════════════════════

class OKXPriceFeed {
  private baseUrl = 'https://www.okx.com';
  
  readonly symbols = [
    'BTC-USDT', 'ETH-USDT', 'SOL-USDT', 'XRP-USDT', 'DOGE-USDT',
    'ADA-USDT', 'DOT-USDT', 'AVAX-USDT', 'LINK-USDT', 'NEAR-USDT',
    'ATOM-USDT', 'UNI-USDT', 'AAVE-USDT', 'LTC-USDT', 'MATIC-USDT',
    'ARB-USDT', 'OP-USDT', 'APT-USDT', 'INJ-USDT', 'SUI-USDT'
  ];

  async getPrice(symbol: string): Promise<LivePrice | null> {
    try {
      const response = await fetch(`${this.baseUrl}/api/v5/market/ticker?instId=${symbol}`);
      if (!response.ok) return null;
      
      const data = await response.json();
      if (!data.data || data.data.length === 0) return null;
      
      const ticker = data.data[0];
      const bid = parseFloat(ticker.bidPx);
      const ask = parseFloat(ticker.askPx);
      
      return {
        symbol,
        bid,
        ask,
        mid: (bid + ask) / 2,
        spread: ask - bid,
        timestamp: new Date(),
        source: 'OKX'
      };
    } catch {
      return null;
    }
  }

  async getAllPrices(): Promise<LivePrice[]> {
    try {
      const response = await fetch(`${this.baseUrl}/api/v5/market/tickers?instType=SPOT`);
      if (!response.ok) return [];
      
      const data = await response.json();
      if (!data.data) return [];
      
      const prices: LivePrice[] = [];
      for (const symbol of this.symbols) {
        const ticker = data.data.find((t: any) => t.instId === symbol);
        if (ticker) {
          const bid = parseFloat(ticker.bidPx);
          const ask = parseFloat(ticker.askPx);
          prices.push({
            symbol,
            bid,
            ask,
            mid: (bid + ask) / 2,
            spread: ask - bid,
            timestamp: new Date(),
            source: 'OKX'
          });
        }
      }
      
      return prices;
    } catch {
      return [];
    }
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// FOREX PRICES - Via Free APIs (ExchangeRate-API & Forex)
// ═══════════════════════════════════════════════════════════════════════════

class ForexPriceFeed {
  // Using free forex API for indicative prices
  private baseUrl = 'https://api.exchangerate-api.com/v4/latest';
  
  readonly pairs = [
    { base: 'EUR', quote: 'USD', symbol: 'EUR/USD' },
    { base: 'GBP', quote: 'USD', symbol: 'GBP/USD' },
    { base: 'USD', quote: 'JPY', symbol: 'USD/JPY' },
    { base: 'USD', quote: 'CHF', symbol: 'USD/CHF' },
    { base: 'AUD', quote: 'USD', symbol: 'AUD/USD' },
    { base: 'USD', quote: 'CAD', symbol: 'USD/CAD' },
    { base: 'NZD', quote: 'USD', symbol: 'NZD/USD' },
    { base: 'EUR', quote: 'GBP', symbol: 'EUR/GBP' },
    { base: 'GBP', quote: 'JPY', symbol: 'GBP/JPY' },
    { base: 'EUR', quote: 'JPY', symbol: 'EUR/JPY' }
  ];

  private cachedRates: Map<string, number> = new Map();
  private lastUpdate: Date | null = null;

  async refreshRates(): Promise<void> {
    try {
      // Get USD rates
      const usdResponse = await fetch(`${this.baseUrl}/USD`);
      if (usdResponse.ok) {
        const usdData = await usdResponse.json();
        for (const [currency, rate] of Object.entries(usdData.rates)) {
          this.cachedRates.set(`USD/${currency}`, rate as number);
          this.cachedRates.set(`${currency}/USD`, 1 / (rate as number));
        }
      }
      
      // Get EUR rates
      const eurResponse = await fetch(`${this.baseUrl}/EUR`);
      if (eurResponse.ok) {
        const eurData = await eurResponse.json();
        for (const [currency, rate] of Object.entries(eurData.rates)) {
          this.cachedRates.set(`EUR/${currency}`, rate as number);
        }
      }
      
      // Get GBP rates
      const gbpResponse = await fetch(`${this.baseUrl}/GBP`);
      if (gbpResponse.ok) {
        const gbpData = await gbpResponse.json();
        for (const [currency, rate] of Object.entries(gbpData.rates)) {
          this.cachedRates.set(`GBP/${currency}`, rate as number);
        }
      }
      
      this.lastUpdate = new Date();
    } catch (error) {
      console.error('Forex rate refresh failed:', error);
    }
  }

  async getAllPrices(): Promise<LivePrice[]> {
    // Refresh rates if stale (> 1 minute)
    if (!this.lastUpdate || Date.now() - this.lastUpdate.getTime() > 60000) {
      await this.refreshRates();
    }

    const prices: LivePrice[] = [];
    
    for (const pair of this.pairs) {
      let mid: number | undefined;
      
      // Try direct rate
      const directKey = `${pair.base}/${pair.quote}`;
      const inverseKey = `${pair.quote}/${pair.base}`;
      
      if (this.cachedRates.has(directKey)) {
        mid = this.cachedRates.get(directKey);
      } else if (this.cachedRates.has(inverseKey)) {
        mid = 1 / this.cachedRates.get(inverseKey)!;
      }
      
      if (mid) {
        // Simulate spread (typical forex spread)
        const spreadPct = 0.0002; // 2 pips
        const spread = mid * spreadPct;
        
        prices.push({
          symbol: pair.symbol,
          bid: mid - spread / 2,
          ask: mid + spread / 2,
          mid,
          spread,
          timestamp: new Date(),
          source: 'Forex'
        });
      }
    }
    
    return prices;
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// COMMODITIES & INDICES - Via Free APIs
// ═══════════════════════════════════════════════════════════════════════════

class CommoditiesPriceFeed {
  // Using Alpha Vantage or similar for commodities
  private goldSilverUrl = 'https://api.metals.live/v1/spot';
  
  async getGoldSilver(): Promise<LivePrice[]> {
    try {
      const response = await fetch(this.goldSilverUrl);
      if (!response.ok) return [];
      
      const data = await response.json();
      const prices: LivePrice[] = [];
      
      // Gold
      if (data.gold) {
        const goldMid = data.gold;
        const goldSpread = goldMid * 0.0005;
        prices.push({
          symbol: 'XAU/USD',
          bid: goldMid - goldSpread / 2,
          ask: goldMid + goldSpread / 2,
          mid: goldMid,
          spread: goldSpread,
          timestamp: new Date(),
          source: 'Metals'
        });
      }
      
      // Silver
      if (data.silver) {
        const silverMid = data.silver;
        const silverSpread = silverMid * 0.001;
        prices.push({
          symbol: 'XAG/USD',
          bid: silverMid - silverSpread / 2,
          ask: silverMid + silverSpread / 2,
          mid: silverMid,
          spread: silverSpread,
          timestamp: new Date(),
          source: 'Metals'
        });
      }
      
      return prices;
    } catch {
      return [];
    }
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// Coherence Engine
// ═══════════════════════════════════════════════════════════════════════════

class CoherenceEngine {
  private priceHistory: Map<string, number[]> = new Map();
  private PHI = 1.618033988749895;

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

    const phiLevel = 1 / this.PHI;
    const phiDist = Math.abs(normalized - phiLevel);
    const phiScore = 1 - phiDist;

    const momentum = (current - recent[0]) / recent[0];
    const momentumScore = Math.tanh(momentum * 50) * 0.5 + 0.5;

    const wavePosition = Math.sin(normalized * Math.PI) ** 2;

    return phiScore * 0.4 + momentumScore * 0.3 + wavePosition * 0.3;
  }

  getSignal(key: string): 'BUY' | 'SELL' | 'HOLD' {
    const coherence = this.calculateCoherence(key);
    const history = this.priceHistory.get(key);

    if (!history || history.length < 5) return 'HOLD';

    const trend = history[history.length - 1] > history[history.length - 5] ? 1 : -1;

    if (coherence >= CONFIG.ENTRY_COHERENCE && trend > 0) return 'BUY';
    if (coherence >= CONFIG.ENTRY_COHERENCE && trend < 0) return 'SELL';

    return 'HOLD';
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// Live Symphony Controller
// ═══════════════════════════════════════════════════════════════════════════

class LiveMarketSymphony {
  private binance = new BinancePriceFeed();
  private kraken = new KrakenPriceFeed();
  private coinbase = new CoinbasePriceFeed();
  private bitstamp = new BitstampPriceFeed();
  private gemini = new GeminiPriceFeed();
  private okx = new OKXPriceFeed();
  private forex = new ForexPriceFeed();
  private commodities = new CommoditiesPriceFeed();
  private coherence = new CoherenceEngine();
  
  private positions: Map<string, Position> = new Map();
  private brokerStats: Map<string, BrokerStatus> = new Map();
  private scans = 0;
  private startTime = new Date();
  private totalPnL = 0;
  private wins = 0;
  private losses = 0;

  constructor() {
    this.initBrokers();
  }

  private initBrokers() {
    const brokers = [
      { name: 'Binance', emoji: '🪙', taxFree: false },
      { name: 'Kraken', emoji: '🦑', taxFree: false },
      { name: 'Coinbase', emoji: '🟠', taxFree: false },
      { name: 'Bitstamp', emoji: '💎', taxFree: false },
      { name: 'Gemini', emoji: '💠', taxFree: false },
      { name: 'OKX', emoji: '⭕', taxFree: false },
      { name: 'OANDA', emoji: '💱', taxFree: false },
      { name: 'FXCM', emoji: '💹', taxFree: false },
      { name: 'IG', emoji: '📈', taxFree: true },
      { name: 'CMC', emoji: '📉', taxFree: true },
      { name: 'Capital', emoji: '📊', taxFree: false },
      { name: 'Saxo', emoji: '🏦', taxFree: false },
      { name: 'IB', emoji: '🏛️', taxFree: false },
      { name: 'Alpaca', emoji: '🦙', taxFree: false },
    ];

    for (const b of brokers) {
      this.brokerStats.set(b.name, {
        name: b.name,
        emoji: b.emoji,
        connected: true,
        balance: CONFIG.BALANCE_PER_BROKER,
        positions: 0,
        wins: 0,
        losses: 0,
        pnl: 0,
        taxFree: b.taxFree,
        lastUpdate: new Date()
      });
    }
  }

  async start(): Promise<void> {
    this.printHeader();
    
    console.log('\n  📡 Fetching initial market data...\n');
    
    // Initial data fetch
    await this.fetchAllPrices();
    
    // Main loop
    while (true) {
      this.scans++;
      await this.scanMarkets();
      this.displayStatus();
      await this.sleep(CONFIG.SCAN_INTERVAL_MS);
    }
  }

  private async fetchAllPrices(): Promise<Map<string, LivePrice[]>> {
    const allPrices = new Map<string, LivePrice[]>();
    
    console.log('  🪙 Fetching Binance prices...');
    allPrices.set('Binance', await this.binance.getAllPrices());
    
    console.log('  🦑 Fetching Kraken prices...');
    allPrices.set('Kraken', await this.kraken.getAllPrices());
    
    console.log('  🟠 Fetching Coinbase prices...');
    allPrices.set('Coinbase', await this.coinbase.getAllPrices());
    
    console.log('  💎 Fetching Bitstamp prices...');
    allPrices.set('Bitstamp', await this.bitstamp.getAllPrices());
    
    console.log('  💠 Fetching Gemini prices...');
    allPrices.set('Gemini', await this.gemini.getAllPrices());
    
    console.log('  ⭕ Fetching OKX prices...');
    allPrices.set('OKX', await this.okx.getAllPrices());
    
    console.log('  💱 Fetching Forex rates...');
    allPrices.set('Forex', await this.forex.getAllPrices());
    
    console.log('  🥇 Fetching Gold/Silver prices...');
    allPrices.set('Commodities', await this.commodities.getGoldSilver());
    
    return allPrices;
  }

  private async scanMarkets(): Promise<void> {
    const allPrices = await this.fetchAllPrices();
    
    // Process Binance
    const binancePrices = allPrices.get('Binance') || [];
    for (const price of binancePrices) {
      this.processPrice('Binance', price);
    }
    
    // Process Kraken
    const krakenPrices = allPrices.get('Kraken') || [];
    for (const price of krakenPrices) {
      this.processPrice('Kraken', price);
    }
    
    // Process Coinbase
    const coinbasePrices = allPrices.get('Coinbase') || [];
    for (const price of coinbasePrices) {
      this.processPrice('Coinbase', price);
    }
    
    // Process Bitstamp
    const bitstampPrices = allPrices.get('Bitstamp') || [];
    for (const price of bitstampPrices) {
      this.processPrice('Bitstamp', price);
    }
    
    // Process Gemini
    const geminiPrices = allPrices.get('Gemini') || [];
    for (const price of geminiPrices) {
      this.processPrice('Gemini', price);
    }
    
    // Process OKX
    const okxPrices = allPrices.get('OKX') || [];
    for (const price of okxPrices) {
      this.processPrice('OKX', price);
    }
    
    // Process Forex (distribute to OANDA, FXCM, IG, CMC)
    const forexPrices = allPrices.get('Forex') || [];
    for (const price of forexPrices) {
      this.processPrice('OANDA', price);
      this.processPrice('FXCM', price);
      this.processPrice('IG', price);
      this.processPrice('CMC', price);
    }
    
    // Process Commodities (distribute to Capital, Saxo, IG, CMC)
    const commodityPrices = allPrices.get('Commodities') || [];
    for (const price of commodityPrices) {
      this.processPrice('Capital', price);
      this.processPrice('Saxo', price);
      this.processPrice('IG', price);
      this.processPrice('CMC', price);
    }
  }

  private processPrice(broker: string, price: LivePrice): void {
    const key = `${broker}:${price.symbol}`;
    const brokerStat = this.brokerStats.get(broker);
    if (!brokerStat) return;

    this.coherence.addPrice(key, price.mid);
    
    const posKey = key;
    const existingPos = this.positions.get(posKey);
    
    if (existingPos) {
      // Update existing position
      const oldPrice = existingPos.currentPrice;
      existingPos.currentPrice = price.mid;
      const priceDiff = price.mid - existingPos.entryPrice;
      const multiplier = existingPos.direction === 'LONG' ? 1 : -1;
      existingPos.pnl = priceDiff * existingPos.size * multiplier;
      existingPos.pnlPercent = (priceDiff / existingPos.entryPrice) * 100 * multiplier;
      
      // Check stop loss / take profit
      if (existingPos.pnlPercent <= -CONFIG.STOP_LOSS_PCT * 100) {
        this.closePosition(posKey, 'STOP');
      } else if (existingPos.pnlPercent >= CONFIG.TAKE_PROFIT_PCT * 100) {
        this.closePosition(posKey, 'PROFIT');
      }
    } else {
      // Check for new position
      const posCount = Array.from(this.positions.values()).filter(p => p.broker === broker).length;
      if (posCount >= CONFIG.MAX_POSITIONS_PER_BROKER) return;
      
      const signal = this.coherence.getSignal(key);
      if (signal !== 'HOLD') {
        const direction = signal === 'BUY' ? 'LONG' : 'SHORT';
        const size = (brokerStat.balance * CONFIG.POSITION_SIZE_PCT) / price.mid;
        
        this.positions.set(posKey, {
          broker,
          symbol: price.symbol,
          direction,
          size,
          entryPrice: price.mid,
          currentPrice: price.mid,
          pnl: 0,
          pnlPercent: 0,
          taxFree: brokerStat.taxFree
        });
        
        brokerStat.positions++;
        const taxLabel = brokerStat.taxFree ? ' 🎁' : '';
        console.log(`  ${brokerStat.emoji} ⚡ ${signal}: ${price.symbol} @ ${price.mid.toFixed(price.mid < 10 ? 5 : 2)}${taxLabel}`);
      }
    }
    
    brokerStat.lastUpdate = new Date();
  }

  private closePosition(posKey: string, reason: 'STOP' | 'PROFIT'): void {
    const pos = this.positions.get(posKey);
    if (!pos) return;
    
    const brokerStat = this.brokerStats.get(pos.broker);
    if (!brokerStat) return;
    
    brokerStat.balance += pos.pnl;
    brokerStat.pnl += pos.pnl;
    this.totalPnL += pos.pnl;
    
    if (pos.pnl >= 0) {
      brokerStat.wins++;
      this.wins++;
    } else {
      brokerStat.losses++;
      this.losses++;
    }
    
    brokerStat.positions--;
    
    const emoji = pos.pnl >= 0 ? '✅' : '❌';
    const taxLabel = pos.taxFree ? ' 🎁TAX FREE!' : '';
    console.log(`  ${brokerStat.emoji} ${emoji} ${reason}: ${pos.symbol} | P&L: £${pos.pnl.toFixed(2)}${taxLabel}`);
    
    this.positions.delete(posKey);
  }

  private printHeader(): void {
    console.log('\n');
    console.log('  ╔═══════════════════════════════════════════════════════════════════════════════╗');
    console.log('  ║                                                                               ║');
    console.log('  ║   🎵 LIVE MARKET SYMPHONY - REAL PRICES ACROSS ALL PLATFORMS 🎵              ║');
    console.log('  ║                                                                               ║');
    console.log('  ║   Northern Ireland / UK Multi-Platform Trading                                ║');
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
    console.log(`  ║   Total Starting Capital: £${CONFIG.BALANCE_PER_BROKER * 14} (£${CONFIG.BALANCE_PER_BROKER} × 14 brokers)                         ║`);
    console.log('  ║   Coherence Φ: Entry 0.938 | Exit 0.934                                       ║');
    console.log('  ║   Risk: 2% SL | 4% TP | 10% Position Size                                     ║');
    console.log('  ╚═══════════════════════════════════════════════════════════════════════════════╝');
    console.log('');
    console.log('  🎵 Live Market Symphony starting with REAL prices...');
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
    
    for (const [name, stat] of this.brokerStats) {
      totalBalance += stat.balance;
      totalPositions += stat.positions;
      if (stat.taxFree) taxFreePnL += stat.pnl;
      
      const hitRate = stat.wins + stat.losses > 0
        ? ((stat.wins / (stat.wins + stat.losses)) * 100).toFixed(0)
        : '-';
      
      const pnlStr = stat.pnl >= 0 ? `+£${stat.pnl.toFixed(2)}` : `-£${Math.abs(stat.pnl).toFixed(2)}`;
      const pnlEmoji = stat.pnl >= 0 ? '🟢' : '🔴';
      const taxLabel = stat.taxFree ? '🎁' : '  ';
      
      lines.push(
        `  │ ${stat.emoji} ${stat.name.padEnd(8)} │ £${stat.balance.toFixed(0).padStart(5)} │ ${stat.positions.toString().padStart(1)}/${CONFIG.MAX_POSITIONS_PER_BROKER} │ ${hitRate.padStart(3)}% │ ${pnlEmoji} ${pnlStr.padStart(8)} │ ${taxLabel} │`
      );
    }
    
    const totalHitRate = this.wins + this.losses > 0
      ? ((this.wins / (this.wins + this.losses)) * 100).toFixed(1)
      : '0.0';
    
    const totalPnLStr = this.totalPnL >= 0 ? `+£${this.totalPnL.toFixed(2)}` : `-£${Math.abs(this.totalPnL).toFixed(2)}`;
    const totalEmoji = this.totalPnL >= 0 ? '🟢' : '🔴';
    
    console.log('');
    console.log('  ┌───────────────────────────────────────────────────────────────────────────┐');
    console.log(`  │  SCAN #${this.scans.toString().padStart(5)} [LIVE]  │  Time: ${minutes}m ${seconds}s  │  Positions: ${totalPositions}/${14 * CONFIG.MAX_POSITIONS_PER_BROKER}  │`);
    console.log('  ├───────────────────────────────────────────────────────────────────────────┤');
    console.log('  │  Broker    │ Balance │ Pos │  HR  │     P&L    │ 🎁 │');
    console.log('  ├────────────┼─────────┼─────┼──────┼────────────┼────┤');
    
    for (const line of lines) {
      console.log(line);
    }
    
    console.log('  ├────────────┼─────────┼─────┼──────┼────────────┼────┤');
    console.log(`  │ 🎵 TOTAL   │ £${totalBalance.toFixed(0).padStart(5)} │ ${totalPositions.toString().padStart(2)}  │${totalHitRate.padStart(5)}% │ ${totalEmoji} ${totalPnLStr.padStart(8)} │    │`);
    console.log('  └───────────────────────────────────────────────────────────────────────────┘');
    
    if (taxFreePnL !== 0) {
      const taxFreeStr = taxFreePnL >= 0 ? `+£${taxFreePnL.toFixed(2)}` : `-£${Math.abs(taxFreePnL).toFixed(2)}`;
      console.log(`  🎁 Tax-Free P&L (IG + CMC Spread Betting): ${taxFreeStr}`);
    }
    
    this.displayPositions();
  }

  private displayPositions(): void {
    const allPositions = Array.from(this.positions.values());
    
    if (allPositions.length === 0) {
      console.log('');
      console.log('  🌊 Waiting for coherence signals on LIVE prices...');
      console.log('');
      return;
    }
    
    allPositions.sort((a, b) => b.pnl - a.pnl);
    
    console.log('');
    console.log('  🌊 Active Positions with LIVE Market Prices:');
    console.log('');
    
    for (const pos of allPositions.slice(0, 15)) {
      const emoji = pos.pnl >= 0 ? '🟢' : '🔴';
      const dir = pos.direction === 'LONG' ? '⬆' : '⬇';
      const brokerStat = this.brokerStats.get(pos.broker);
      const brokerEmoji = brokerStat?.emoji || '📈';
      const taxLabel = pos.taxFree ? ' 🎁' : '';
      
      const pnlStr = pos.pnl >= 0 ? `+£${pos.pnl.toFixed(2)}` : `-£${Math.abs(pos.pnl).toFixed(2)}`;
      const priceStr = pos.currentPrice < 10 ? pos.currentPrice.toFixed(5) : pos.currentPrice.toFixed(2);
      
      console.log(`     ${brokerEmoji} ${emoji} ${pos.symbol.padEnd(12)} ${dir} @ ${priceStr} → ${pnlStr} (${pos.pnlPercent.toFixed(1)}%)${taxLabel}`);
    }
    
    if (allPositions.length > 15) {
      console.log(`     ... and ${allPositions.length - 15} more positions`);
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
  console.log(`
  ╔═══════════════════════════════════════════════════════════════════════════════╗
  ║                                                                               ║
  ║   🎵 AUREON LIVE MARKET SYMPHONY 🎵                                           ║
  ║                                                                               ║
  ║   REAL-TIME PRICES FROM ALL EXCHANGES                                        ║
  ║                                                                               ║
  ║   Crypto Exchanges (Live Public APIs):                                        ║
  ║   • Binance    - 20 major pairs                                               ║
  ║   • Kraken     - 10 pairs (GBP + USD)                                         ║
  ║   • Coinbase   - 15 pairs (GBP + USD)                                         ║
  ║   • Bitstamp   - 15 pairs                                                     ║
  ║   • Gemini     - 15 pairs                                                     ║
  ║   • OKX        - 20 pairs                                                     ║
  ║                                                                               ║
  ║   Forex (ExchangeRate API):                                                   ║
  ║   • EUR/USD, GBP/USD, USD/JPY, EUR/GBP, GBP/JPY, etc.                        ║
  ║                                                                               ║
  ║   Commodities (Metals.Live API):                                              ║
  ║   • Gold (XAU/USD), Silver (XAG/USD)                                          ║
  ║                                                                               ║
  ║   🎁 TAX FREE: IG Markets & CMC Markets (Spread Betting)                      ║
  ║                                                                               ║
  ║   Author: Gary Leckey - R&A Consulting                                       ║
  ║                                                                               ║
  ╚═══════════════════════════════════════════════════════════════════════════════╝
  `);

  const symphony = new LiveMarketSymphony();
  
  process.on('SIGINT', () => {
    console.log('\n');
    console.log('  ────────────────────────────────────────────────────────────────────────────');
    console.log('  🎵 Live Market Symphony concludes...');
    console.log('  ────────────────────────────────────────────────────────────────────────────');
    console.log('');
    console.log('  "Real prices, real signals, the wave rides eternal"');
    console.log('');
    process.exit(0);
  });

  await symphony.start();
}

main().catch(console.error);
