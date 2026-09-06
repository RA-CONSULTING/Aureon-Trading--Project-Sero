/**
 * 🌍 GLOBAL FINANCIAL ECOSYSTEM TRADER 🌍
 * 
 * Complete market hours, sessions, and trading windows for the entire financial system
 * 
 * ┌─────────────────────────────────────────────────────────────────────────────┐
 * │  MARKET SESSION      │  OPEN (UTC)      │  CLOSE (UTC)    │  PEAK HOURS    │
 * ├─────────────────────────────────────────────────────────────────────────────┤
 * │  🇦🇺 Sydney           │  22:00 (Sun)     │  07:00          │  00:00-02:00   │
 * │  🇯🇵 Tokyo            │  00:00           │  09:00          │  00:00-03:00   │
 * │  🇭🇰 Hong Kong        │  01:00           │  09:00          │  01:00-04:00   │
 * │  🇸🇬 Singapore        │  01:00           │  09:00          │  01:00-04:00   │
 * │  🇩🇪 Frankfurt        │  07:00           │  16:00          │  07:00-09:00   │
 * │  🇬🇧 London           │  08:00           │  17:00          │  08:00-11:00   │
 * │  🇺🇸 New York         │  13:00           │  22:00          │  13:30-16:00   │
 * │  🪙 Crypto            │  00:00           │  24:00          │  Always        │
 * └─────────────────────────────────────────────────────────────────────────────┘
 * 
 * Run: npx tsx scripts/globalEcosystemTrader.ts
 */

// ═══════════════════════════════════════════════════════════════════════════
// GLOBAL MARKET SESSIONS
// ═══════════════════════════════════════════════════════════════════════════

interface MarketSession {
  name: string;
  emoji: string;
  region: string;
  openUTC: number;      // Hour (0-23)
  closeUTC: number;     // Hour (0-23)
  peakStart: number;    // Best liquidity start
  peakEnd: number;      // Best liquidity end
  timezone: string;
  dstOffset: number;    // Daylight saving adjustment
  tradingDays: number[]; // 0=Sun, 1=Mon...6=Sat
}

const MARKET_SESSIONS: MarketSession[] = [
  // ASIA-PACIFIC
  {
    name: 'Sydney',
    emoji: '🇦🇺',
    region: 'APAC',
    openUTC: 22,        // 9am Sydney = 22:00 UTC (prev day)
    closeUTC: 7,        // 4pm Sydney = 07:00 UTC
    peakStart: 0,
    peakEnd: 2,
    timezone: 'Australia/Sydney',
    dstOffset: 1,       // +1 hour in summer
    tradingDays: [1, 2, 3, 4, 5], // Mon-Fri
  },
  {
    name: 'Tokyo',
    emoji: '🇯🇵',
    region: 'APAC',
    openUTC: 0,         // 9am Tokyo = 00:00 UTC
    closeUTC: 9,        // 6pm Tokyo = 09:00 UTC
    peakStart: 0,
    peakEnd: 3,
    timezone: 'Asia/Tokyo',
    dstOffset: 0,       // No DST
    tradingDays: [1, 2, 3, 4, 5],
  },
  {
    name: 'Hong Kong',
    emoji: '🇭🇰',
    region: 'APAC',
    openUTC: 1,         // 9am HK = 01:00 UTC
    closeUTC: 8,        // 4pm HK = 08:00 UTC
    peakStart: 1,
    peakEnd: 4,
    timezone: 'Asia/Hong_Kong',
    dstOffset: 0,
    tradingDays: [1, 2, 3, 4, 5],
  },
  {
    name: 'Singapore',
    emoji: '🇸🇬',
    region: 'APAC',
    openUTC: 1,
    closeUTC: 9,
    peakStart: 1,
    peakEnd: 4,
    timezone: 'Asia/Singapore',
    dstOffset: 0,
    tradingDays: [1, 2, 3, 4, 5],
  },
  {
    name: 'Shanghai',
    emoji: '🇨🇳',
    region: 'APAC',
    openUTC: 1,         // 9:30am Shanghai = 01:30 UTC
    closeUTC: 7,        // 3pm Shanghai = 07:00 UTC
    peakStart: 1,
    peakEnd: 4,
    timezone: 'Asia/Shanghai',
    dstOffset: 0,
    tradingDays: [1, 2, 3, 4, 5],
  },
  
  // EUROPE
  {
    name: 'Frankfurt',
    emoji: '🇩🇪',
    region: 'EMEA',
    openUTC: 7,         // 8am Frankfurt = 07:00 UTC (winter)
    closeUTC: 16,       // 5pm Frankfurt = 16:00 UTC
    peakStart: 7,
    peakEnd: 9,
    timezone: 'Europe/Berlin',
    dstOffset: 1,
    tradingDays: [1, 2, 3, 4, 5],
  },
  {
    name: 'London',
    emoji: '🇬🇧',
    region: 'EMEA',
    openUTC: 8,         // 8am London = 08:00 UTC (winter)
    closeUTC: 17,       // 5pm London = 17:00 UTC
    peakStart: 8,
    peakEnd: 11,
    timezone: 'Europe/London',
    dstOffset: 1,
    tradingDays: [1, 2, 3, 4, 5],
  },
  {
    name: 'Zurich',
    emoji: '🇨🇭',
    region: 'EMEA',
    openUTC: 7,
    closeUTC: 16,
    peakStart: 8,
    peakEnd: 10,
    timezone: 'Europe/Zurich',
    dstOffset: 1,
    tradingDays: [1, 2, 3, 4, 5],
  },
  
  // AMERICAS
  {
    name: 'New York',
    emoji: '🇺🇸',
    region: 'AMER',
    openUTC: 14,        // 9:30am NY = 14:30 UTC (winter)
    closeUTC: 21,       // 4pm NY = 21:00 UTC
    peakStart: 14,
    peakEnd: 16,
    timezone: 'America/New_York',
    dstOffset: 1,
    tradingDays: [1, 2, 3, 4, 5],
  },
  {
    name: 'Chicago',
    emoji: '🏛️',
    region: 'AMER',
    openUTC: 14,        // CME hours
    closeUTC: 21,
    peakStart: 14,
    peakEnd: 17,
    timezone: 'America/Chicago',
    dstOffset: 1,
    tradingDays: [1, 2, 3, 4, 5],
  },
  {
    name: 'Toronto',
    emoji: '🇨🇦',
    region: 'AMER',
    openUTC: 14,
    closeUTC: 21,
    peakStart: 14,
    peakEnd: 16,
    timezone: 'America/Toronto',
    dstOffset: 1,
    tradingDays: [1, 2, 3, 4, 5],
  },
];

// ═══════════════════════════════════════════════════════════════════════════
// ASSET CLASSES & TRADING HOURS
// ═══════════════════════════════════════════════════════════════════════════

interface AssetClass {
  name: string;
  emoji: string;
  marketHours: 'always' | 'session' | 'extended';
  openUTC?: number;
  closeUTC?: number;
  weekendTrading: boolean;
  examples: string[];
}

const ASSET_CLASSES: AssetClass[] = [
  {
    name: 'Cryptocurrency',
    emoji: '🪙',
    marketHours: 'always',
    weekendTrading: true,
    examples: ['BTC', 'ETH', 'BNB', 'SOL', 'XRP', 'ADA', 'DOGE', 'AVAX'],
  },
  {
    name: 'Forex',
    emoji: '💱',
    marketHours: 'extended',
    openUTC: 21,    // Sunday 9pm UTC
    closeUTC: 21,   // Friday 9pm UTC
    weekendTrading: false,
    examples: ['EUR/USD', 'GBP/USD', 'USD/JPY', 'AUD/USD', 'USD/CHF', 'EUR/GBP'],
  },
  {
    name: 'US Stocks',
    emoji: '🇺🇸',
    marketHours: 'session',
    openUTC: 14,    // 9:30am ET
    closeUTC: 21,   // 4pm ET
    weekendTrading: false,
    examples: ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA', 'NVDA', 'META'],
  },
  {
    name: 'UK Stocks',
    emoji: '🇬🇧',
    marketHours: 'session',
    openUTC: 8,     // 8am GMT
    closeUTC: 17,   // 4:30pm GMT
    weekendTrading: false,
    examples: ['FTSE100', 'BP', 'HSBC', 'AZN', 'ULVR', 'RIO', 'SHEL'],
  },
  {
    name: 'European Stocks',
    emoji: '🇪🇺',
    marketHours: 'session',
    openUTC: 7,
    closeUTC: 16,
    weekendTrading: false,
    examples: ['DAX40', 'CAC40', 'SAP', 'ASML', 'LVMH', 'NESN'],
  },
  {
    name: 'Asian Stocks',
    emoji: '🌏',
    marketHours: 'session',
    openUTC: 0,
    closeUTC: 8,
    weekendTrading: false,
    examples: ['Nikkei225', 'HangSeng', 'SSE', 'SONY', 'BABA', 'TSM'],
  },
  {
    name: 'Commodities',
    emoji: '🛢️',
    marketHours: 'extended',
    openUTC: 22,
    closeUTC: 21,
    weekendTrading: false,
    examples: ['Gold', 'Silver', 'Oil', 'NatGas', 'Copper', 'Wheat'],
  },
  {
    name: 'Indices',
    emoji: '📊',
    marketHours: 'extended',
    openUTC: 22,
    closeUTC: 21,
    weekendTrading: false,
    examples: ['S&P500', 'NASDAQ', 'DOW', 'FTSE', 'DAX', 'Nikkei'],
  },
  {
    name: 'Bonds',
    emoji: '📜',
    marketHours: 'session',
    openUTC: 12,
    closeUTC: 21,
    weekendTrading: false,
    examples: ['US10Y', 'US30Y', 'UK10Y', 'DE10Y', 'T-Bills'],
  },
];

// ═══════════════════════════════════════════════════════════════════════════
// BROKER CONFIGURATIONS WITH FULL DETAILS
// ═══════════════════════════════════════════════════════════════════════════

interface BrokerConfig {
  name: string;
  emoji: string;
  type: 'crypto' | 'forex' | 'stocks' | 'cfd' | 'multi';
  
  // API Limits
  tradesPerMinute: number;
  tradesPerDay: number;
  maxConcurrentPositions: number;
  
  // Fee Structure
  makerFee: number;
  takerFee: number;
  spreadCost: number;
  overnightFee: number;       // Daily %
  withdrawalFee: number;
  
  // Order Constraints
  minOrderSize: number;       // In £
  maxOrderSize: number;
  minLotSize: number;
  
  // Market Hours
  tradingHours: 'always' | 'forex' | 'stocks' | 'extended';
  supportedAssets: string[];
  
  // Regulatory
  regulated: boolean;
  taxFree: boolean;           // UK spread betting
  leverageMax: number;
  marginRequired: number;     // As decimal
  
  // Region
  region: 'UK' | 'EU' | 'US' | 'Global';
  ukAvailable: boolean;
}

const BROKERS: BrokerConfig[] = [
  // ═══════════════════════════════════════════════════════════════════════
  // CRYPTO EXCHANGES
  // ═══════════════════════════════════════════════════════════════════════
  {
    name: 'Binance',
    emoji: '🪙',
    type: 'crypto',
    tradesPerMinute: 30,
    tradesPerDay: 100000,
    maxConcurrentPositions: 500,
    makerFee: 0.001,
    takerFee: 0.001,
    spreadCost: 0.0001,
    overnightFee: 0,
    withdrawalFee: 0.0005,
    minOrderSize: 5,
    maxOrderSize: 1000000,
    minLotSize: 0.00001,
    tradingHours: 'always',
    supportedAssets: ['BTC', 'ETH', 'BNB', 'SOL', 'XRP', 'ADA', 'DOGE', 'AVAX', 'DOT', 'MATIC'],
    regulated: true,
    taxFree: false,
    leverageMax: 20,
    marginRequired: 0.05,
    region: 'Global',
    ukAvailable: true,
  },
  {
    name: 'OKX',
    emoji: '⭕',
    type: 'crypto',
    tradesPerMinute: 30,
    tradesPerDay: 100000,
    maxConcurrentPositions: 500,
    makerFee: 0.0008,
    takerFee: 0.001,
    spreadCost: 0.0001,
    overnightFee: 0,
    withdrawalFee: 0.0004,
    minOrderSize: 5,
    maxOrderSize: 1000000,
    minLotSize: 0.00001,
    tradingHours: 'always',
    supportedAssets: ['BTC', 'ETH', 'SOL', 'XRP', 'OKB', 'AVAX', 'NEAR'],
    regulated: true,
    taxFree: false,
    leverageMax: 20,
    marginRequired: 0.05,
    region: 'Global',
    ukAvailable: true,
  },
  {
    name: 'Kraken',
    emoji: '🦑',
    type: 'crypto',
    tradesPerMinute: 15,
    tradesPerDay: 50000,
    maxConcurrentPositions: 200,
    makerFee: 0.0016,
    takerFee: 0.0026,
    spreadCost: 0.0002,
    overnightFee: 0,
    withdrawalFee: 0.0003,
    minOrderSize: 5,
    maxOrderSize: 500000,
    minLotSize: 0.0001,
    tradingHours: 'always',
    supportedAssets: ['BTC', 'ETH', 'SOL', 'XRP', 'ADA', 'DOT', 'ATOM'],
    regulated: true,
    taxFree: false,
    leverageMax: 5,
    marginRequired: 0.2,
    region: 'US',
    ukAvailable: true,
  },
  {
    name: 'Coinbase',
    emoji: '🟠',
    type: 'crypto',
    tradesPerMinute: 10,
    tradesPerDay: 10000,
    maxConcurrentPositions: 100,
    makerFee: 0.004,
    takerFee: 0.006,
    spreadCost: 0.005,
    overnightFee: 0,
    withdrawalFee: 0.001,
    minOrderSize: 2,
    maxOrderSize: 100000,
    minLotSize: 0.00001,
    tradingHours: 'always',
    supportedAssets: ['BTC', 'ETH', 'SOL', 'XRP', 'AVAX', 'LINK'],
    regulated: true,
    taxFree: false,
    leverageMax: 1,
    marginRequired: 1,
    region: 'US',
    ukAvailable: true,
  },
  {
    name: 'Bitstamp',
    emoji: '💎',
    type: 'crypto',
    tradesPerMinute: 20,
    tradesPerDay: 30000,
    maxConcurrentPositions: 100,
    makerFee: 0.003,
    takerFee: 0.004,
    spreadCost: 0.0003,
    overnightFee: 0,
    withdrawalFee: 0.0005,
    minOrderSize: 10,
    maxOrderSize: 200000,
    minLotSize: 0.0001,
    tradingHours: 'always',
    supportedAssets: ['BTC', 'ETH', 'XRP', 'LTC', 'BCH'],
    regulated: true,
    taxFree: false,
    leverageMax: 1,
    marginRequired: 1,
    region: 'EU',
    ukAvailable: true,
  },
  {
    name: 'Gemini',
    emoji: '♊',
    type: 'crypto',
    tradesPerMinute: 10,
    tradesPerDay: 10000,
    maxConcurrentPositions: 50,
    makerFee: 0.002,
    takerFee: 0.004,
    spreadCost: 0.003,
    overnightFee: 0,
    withdrawalFee: 0,
    minOrderSize: 1,
    maxOrderSize: 100000,
    minLotSize: 0.00001,
    tradingHours: 'always',
    supportedAssets: ['BTC', 'ETH', 'SOL', 'MATIC', 'LINK'],
    regulated: true,
    taxFree: false,
    leverageMax: 1,
    marginRequired: 1,
    region: 'US',
    ukAvailable: true,
  },

  // ═══════════════════════════════════════════════════════════════════════
  // FOREX BROKERS
  // ═══════════════════════════════════════════════════════════════════════
  {
    name: 'OANDA',
    emoji: '💱',
    type: 'forex',
    tradesPerMinute: 60,
    tradesPerDay: 100000,
    maxConcurrentPositions: 500,
    makerFee: 0,
    takerFee: 0,
    spreadCost: 0.00012,        // 1.2 pips
    overnightFee: 0.00005,
    withdrawalFee: 0,
    minOrderSize: 1,
    maxOrderSize: 10000000,
    minLotSize: 1,              // 1 unit (nano lots!)
    tradingHours: 'forex',
    supportedAssets: ['EUR/USD', 'GBP/USD', 'USD/JPY', 'AUD/USD', 'USD/CHF', 'EUR/GBP', 'XAU/USD'],
    regulated: true,
    taxFree: false,
    leverageMax: 30,
    marginRequired: 0.0333,
    region: 'UK',
    ukAvailable: true,
  },
  {
    name: 'FXCM',
    emoji: '💹',
    type: 'forex',
    tradesPerMinute: 30,
    tradesPerDay: 50000,
    maxConcurrentPositions: 200,
    makerFee: 0,
    takerFee: 0,
    spreadCost: 0.00015,
    overnightFee: 0.00006,
    withdrawalFee: 0,
    minOrderSize: 10,
    maxOrderSize: 5000000,
    minLotSize: 1000,
    tradingHours: 'forex',
    supportedAssets: ['EUR/USD', 'GBP/USD', 'USD/JPY', 'EUR/GBP', 'GBP/JPY'],
    regulated: true,
    taxFree: false,
    leverageMax: 30,
    marginRequired: 0.0333,
    region: 'UK',
    ukAvailable: true,
  },
  {
    name: 'Saxo Bank',
    emoji: '🏦',
    type: 'multi',
    tradesPerMinute: 20,
    tradesPerDay: 10000,
    maxConcurrentPositions: 100,
    makerFee: 0.0003,
    takerFee: 0.0005,
    spreadCost: 0.0001,
    overnightFee: 0.00008,
    withdrawalFee: 0,
    minOrderSize: 100,          // High minimum
    maxOrderSize: 10000000,
    minLotSize: 1000,
    tradingHours: 'extended',
    supportedAssets: ['Forex', 'Stocks', 'Bonds', 'Options', 'Futures'],
    regulated: true,
    taxFree: false,
    leverageMax: 30,
    marginRequired: 0.0333,
    region: 'EU',
    ukAvailable: true,
  },

  // ═══════════════════════════════════════════════════════════════════════
  // STOCK BROKERS
  // ═══════════════════════════════════════════════════════════════════════
  {
    name: 'Alpaca',
    emoji: '🦙',
    type: 'stocks',
    tradesPerMinute: 60,
    tradesPerDay: 100000,
    maxConcurrentPositions: 500,
    makerFee: 0,
    takerFee: 0,                // Commission-free stocks!
    spreadCost: 0.0001,
    overnightFee: 0.0001,       // Margin interest
    withdrawalFee: 0,
    minOrderSize: 1,
    maxOrderSize: 1000000,
    minLotSize: 0.001,          // Fractional shares
    tradingHours: 'stocks',
    supportedAssets: ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA', 'NVDA', 'META', 'BRK.B'],
    regulated: true,
    taxFree: false,
    leverageMax: 4,
    marginRequired: 0.25,
    region: 'US',
    ukAvailable: true,
  },
  {
    name: 'Interactive Brokers',
    emoji: '🏛️',
    type: 'multi',
    tradesPerMinute: 50,
    tradesPerDay: 100000,
    maxConcurrentPositions: 1000,
    makerFee: 0.00005,
    takerFee: 0.0001,
    spreadCost: 0.00005,
    overnightFee: 0.00015,
    withdrawalFee: 0,
    minOrderSize: 1,
    maxOrderSize: 10000000,
    minLotSize: 1,
    tradingHours: 'extended',
    supportedAssets: ['Global Stocks', 'Options', 'Futures', 'Forex', 'Bonds', 'ETFs'],
    regulated: true,
    taxFree: false,
    leverageMax: 4,
    marginRequired: 0.25,
    region: 'US',
    ukAvailable: true,
  },

  // ═══════════════════════════════════════════════════════════════════════
  // CFD & SPREAD BETTING (UK)
  // ═══════════════════════════════════════════════════════════════════════
  {
    name: 'IG Markets',
    emoji: '📈',
    type: 'cfd',
    tradesPerMinute: 10,
    tradesPerDay: 10000,
    maxConcurrentPositions: 200,
    makerFee: 0,
    takerFee: 0,
    spreadCost: 0.0003,         // Spread betting spread
    overnightFee: 0.00025,
    withdrawalFee: 0,
    minOrderSize: 1,
    maxOrderSize: 1000000,
    minLotSize: 0.1,
    tradingHours: 'extended',
    supportedAssets: ['Forex', 'Indices', 'Stocks', 'Crypto', 'Commodities'],
    regulated: true,
    taxFree: true,              // 🎁 SPREAD BETTING = TAX FREE!
    leverageMax: 30,
    marginRequired: 0.0333,
    region: 'UK',
    ukAvailable: true,
  },
  {
    name: 'CMC Markets',
    emoji: '📉',
    type: 'cfd',
    tradesPerMinute: 10,
    tradesPerDay: 10000,
    maxConcurrentPositions: 200,
    makerFee: 0,
    takerFee: 0,
    spreadCost: 0.0003,
    overnightFee: 0.00025,
    withdrawalFee: 0,
    minOrderSize: 1,
    maxOrderSize: 500000,
    minLotSize: 0.1,
    tradingHours: 'extended',
    supportedAssets: ['Forex', 'Indices', 'Stocks', 'Crypto', 'Commodities'],
    regulated: true,
    taxFree: true,              // 🎁 SPREAD BETTING = TAX FREE!
    leverageMax: 30,
    marginRequired: 0.0333,
    region: 'UK',
    ukAvailable: true,
  },
  {
    name: 'Capital.com',
    emoji: '📊',
    type: 'cfd',
    tradesPerMinute: 5,
    tradesPerDay: 5000,
    maxConcurrentPositions: 200,
    makerFee: 0,
    takerFee: 0,
    spreadCost: 0.0006,
    overnightFee: 0.0003,
    withdrawalFee: 0,
    minOrderSize: 10,
    maxOrderSize: 500000,
    minLotSize: 0.01,
    tradingHours: 'extended',
    supportedAssets: ['Forex', 'Indices', 'Stocks', 'Crypto', 'Commodities'],
    regulated: true,
    taxFree: false,
    leverageMax: 30,
    marginRequired: 0.0333,
    region: 'UK',
    ukAvailable: true,
  },
  {
    name: 'Plus500',
    emoji: '➕',
    type: 'cfd',
    tradesPerMinute: 10,
    tradesPerDay: 10000,
    maxConcurrentPositions: 100,
    makerFee: 0,
    takerFee: 0,
    spreadCost: 0.0008,
    overnightFee: 0.00035,
    withdrawalFee: 0,
    minOrderSize: 10,
    maxOrderSize: 300000,
    minLotSize: 0.1,
    tradingHours: 'extended',
    supportedAssets: ['Forex', 'Indices', 'Stocks', 'Crypto', 'Commodities', 'ETFs'],
    regulated: true,
    taxFree: false,
    leverageMax: 30,
    marginRequired: 0.0333,
    region: 'UK',
    ukAvailable: true,
  },
  {
    name: 'eToro',
    emoji: '🐂',
    type: 'multi',
    tradesPerMinute: 10,
    tradesPerDay: 5000,
    maxConcurrentPositions: 100,
    makerFee: 0,
    takerFee: 0,
    spreadCost: 0.001,          // Higher spreads
    overnightFee: 0.0003,
    withdrawalFee: 5,           // $5 withdrawal
    minOrderSize: 10,
    maxOrderSize: 100000,
    minLotSize: 0.1,
    tradingHours: 'extended',
    supportedAssets: ['Stocks', 'Crypto', 'ETFs', 'Forex', 'Commodities'],
    regulated: true,
    taxFree: false,
    leverageMax: 30,
    marginRequired: 0.0333,
    region: 'EU',
    ukAvailable: true,
  },
];

// ═══════════════════════════════════════════════════════════════════════════
// MARKET CALENDAR & HOLIDAYS
// ═══════════════════════════════════════════════════════════════════════════

const MAJOR_HOLIDAYS_2025 = [
  { date: '2025-01-01', name: "New Year's Day", markets: ['ALL'] },
  { date: '2025-01-20', name: 'MLK Day', markets: ['US'] },
  { date: '2025-02-17', name: "Presidents' Day", markets: ['US'] },
  { date: '2025-04-18', name: 'Good Friday', markets: ['US', 'UK', 'EU'] },
  { date: '2025-04-21', name: 'Easter Monday', markets: ['UK', 'EU'] },
  { date: '2025-05-05', name: 'May Day', markets: ['UK'] },
  { date: '2025-05-26', name: 'Spring Bank Holiday', markets: ['UK'] },
  { date: '2025-05-26', name: 'Memorial Day', markets: ['US'] },
  { date: '2025-07-04', name: 'Independence Day', markets: ['US'] },
  { date: '2025-08-25', name: 'Summer Bank Holiday', markets: ['UK'] },
  { date: '2025-09-01', name: 'Labor Day', markets: ['US'] },
  { date: '2025-11-27', name: 'Thanksgiving', markets: ['US'] },
  { date: '2025-12-25', name: 'Christmas Day', markets: ['ALL'] },
  { date: '2025-12-26', name: 'Boxing Day', markets: ['UK'] },
];

// ═══════════════════════════════════════════════════════════════════════════
// GLOBAL ECOSYSTEM TRADER
// ═══════════════════════════════════════════════════════════════════════════

class GlobalEcosystemTrader {
  private capital: number = 400;
  private startTime: Date;
  private currentTime: Date;
  
  constructor() {
    this.startTime = new Date();
    this.currentTime = new Date();
  }
  
  private getCurrentUTCHour(): number {
    return this.currentTime.getUTCHours();
  }
  
  private getDayOfWeek(): number {
    return this.currentTime.getUTCDay();
  }
  
  private isMarketOpen(session: MarketSession): boolean {
    const hour = this.getCurrentUTCHour();
    const day = this.getDayOfWeek();
    
    // Check if trading day
    if (!session.tradingDays.includes(day)) return false;
    
    // Handle sessions that span midnight
    if (session.openUTC > session.closeUTC) {
      return hour >= session.openUTC || hour < session.closeUTC;
    }
    
    return hour >= session.openUTC && hour < session.closeUTC;
  }
  
  private getOpenSessions(): MarketSession[] {
    return MARKET_SESSIONS.filter(s => this.isMarketOpen(s));
  }
  
  private getActiveBrokers(): BrokerConfig[] {
    const hour = this.getCurrentUTCHour();
    const day = this.getDayOfWeek();
    
    return BROKERS.filter(broker => {
      if (broker.tradingHours === 'always') return true;
      if (broker.tradingHours === 'forex') {
        // Forex: Sun 21:00 - Fri 21:00 UTC
        if (day === 0) return hour >= 21;
        if (day === 6) return false;
        if (day === 5) return hour < 21;
        return true;
      }
      if (broker.tradingHours === 'stocks') {
        // US Stocks: Mon-Fri 14:00-21:00 UTC
        if (day === 0 || day === 6) return false;
        return hour >= 14 && hour < 21;
      }
      if (broker.tradingHours === 'extended') {
        // Extended: Most of the week except weekends
        if (day === 0) return hour >= 22;
        if (day === 6) return hour < 22;
        return true;
      }
      return false;
    });
  }
  
  private formatTime(date: Date): string {
    return date.toISOString().substring(11, 16) + ' UTC';
  }
  
  printCurrentStatus(): void {
    const openSessions = this.getOpenSessions();
    const activeBrokers = this.getActiveBrokers();
    const hour = this.getCurrentUTCHour();
    const day = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'][this.getDayOfWeek()];
    
    console.clear();
    console.log(`
╔═══════════════════════════════════════════════════════════════════════════════╗
║                                                                               ║
║   🌍 GLOBAL FINANCIAL ECOSYSTEM - LIVE STATUS 🌍                             ║
║                                                                               ║
║   Current Time: ${this.formatTime(this.currentTime)} (${day})                                         ║
║   Capital: £${this.capital.toFixed(2)}                                                        ║
║                                                                               ║
╠═══════════════════════════════════════════════════════════════════════════════╣
║                                                                               ║
║   📊 MARKET SESSIONS:                                                         ║
║   ─────────────────────────────────────────────────────────────────           ║`);
    
    MARKET_SESSIONS.forEach(session => {
      const isOpen = this.isMarketOpen(session);
      const status = isOpen ? '🟢 OPEN' : '🔴 CLOSED';
      const peak = (hour >= session.peakStart && hour < session.peakEnd && isOpen) ? '⚡ PEAK' : '';
      console.log(`║   ${session.emoji} ${session.name.padEnd(12)} │ ${status.padEnd(12)} │ ${session.openUTC.toString().padStart(2, '0')}:00-${session.closeUTC.toString().padStart(2, '0')}:00 UTC │ ${peak.padEnd(8)} ║`);
    });

    console.log(`║                                                                               ║
║   💼 ACTIVE BROKERS (${activeBrokers.length}/${BROKERS.length}):                                                     ║
║   ─────────────────────────────────────────────────────────────────           ║`);
    
    activeBrokers.slice(0, 8).forEach(broker => {
      const taxNote = broker.taxFree ? '🎁 TAX FREE' : '';
      console.log(`║   ${broker.emoji} ${broker.name.padEnd(12)} │ ${broker.tradesPerMinute.toString().padStart(3)} trades/min │ ${(broker.spreadCost * 100).toFixed(2)}% spread │ ${taxNote.padEnd(12)} ║`);
    });
    
    if (activeBrokers.length > 8) {
      console.log(`║   ... and ${activeBrokers.length - 8} more brokers active                                         ║`);
    }

    const totalTradesPerMin = activeBrokers.reduce((sum, b) => sum + b.tradesPerMinute, 0);
    const totalTradesPerHour = totalTradesPerMin * 60;
    
    console.log(`║                                                                               ║
║   ⚡ CURRENT CAPACITY:                                                        ║
║   ─────────────────────────────────────────────────────────────────           ║
║   Trades/Minute:  ${totalTradesPerMin.toString().padStart(4)}                                                       ║
║   Trades/Hour:    ${totalTradesPerHour.toLocaleString().padStart(6)}                                                     ║
║   Trades/Day:     ${(totalTradesPerHour * 24).toLocaleString().padStart(8)}                                                   ║
║                                                                               ║
╠═══════════════════════════════════════════════════════════════════════════════╣
║                                                                               ║
║   🌐 SESSION OVERLAPS (Best Liquidity):                                       ║
║   ─────────────────────────────────────────────────────────────────           ║
║   🔥 08:00-09:00 UTC │ London + Asia overlap                                  ║
║   🔥 13:00-17:00 UTC │ London + New York overlap  ← MAXIMUM LIQUIDITY        ║
║   🔥 00:00-03:00 UTC │ Tokyo + Sydney overlap                                 ║
║                                                                               ║
║   🪙 Crypto trades 24/7/365 - No restrictions!                               ║
║                                                                               ║
╚═══════════════════════════════════════════════════════════════════════════════╝
`);
  }
  
  async run(): Promise<void> {
    // Simulate a 24-hour period
    console.log('\n🚀 Simulating 24-hour trading window...\n');
    
    const results: Array<{hour: number; sessions: number; brokers: number; capacity: number}> = [];
    
    for (let hour = 0; hour < 24; hour++) {
      this.currentTime = new Date();
      this.currentTime.setUTCHours(hour, 0, 0, 0);
      // Set to a weekday (Wednesday)
      const daysToWed = (3 - this.currentTime.getUTCDay() + 7) % 7;
      this.currentTime.setUTCDate(this.currentTime.getUTCDate() + daysToWed);
      
      const openSessions = this.getOpenSessions();
      const activeBrokers = this.getActiveBrokers();
      const capacity = activeBrokers.reduce((sum, b) => sum + b.tradesPerMinute, 0);
      
      results.push({
        hour,
        sessions: openSessions.length,
        brokers: activeBrokers.length,
        capacity,
      });
    }
    
    console.log(`
╔═══════════════════════════════════════════════════════════════════════════════╗
║                                                                               ║
║   📊 24-HOUR TRADING CAPACITY ANALYSIS                                        ║
║                                                                               ║
╠═══════════════════════════════════════════════════════════════════════════════╣
║                                                                               ║
║   HOUR │ SESSIONS │ BROKERS │ TRADES/MIN │ BAR                               ║
║   ─────────────────────────────────────────────────────────────────           ║`);
    
    results.forEach(r => {
      const bar = '█'.repeat(Math.floor(r.capacity / 20));
      const sessionEmojis = r.sessions >= 4 ? '🔥🔥' : r.sessions >= 2 ? '🔥' : '';
      console.log(`║   ${r.hour.toString().padStart(2, '0')}:00 │    ${r.sessions.toString().padStart(2)}    │   ${r.brokers.toString().padStart(2)}    │    ${r.capacity.toString().padStart(3)}     │ ${bar.padEnd(15)} ${sessionEmojis.padEnd(4)} ║`);
    });
    
    const totalCapacity = results.reduce((sum, r) => sum + r.capacity, 0);
    const avgCapacity = totalCapacity / 24;
    const peakCapacity = Math.max(...results.map(r => r.capacity));
    const peakHour = results.find(r => r.capacity === peakCapacity)?.hour;
    
    console.log(`║   ─────────────────────────────────────────────────────────────────           ║
║                                                                               ║
║   📈 SUMMARY:                                                                 ║
║   Average Capacity:  ${avgCapacity.toFixed(0)} trades/min                                          ║
║   Peak Capacity:     ${peakCapacity} trades/min (at ${peakHour?.toString().padStart(2, '0')}:00 UTC)                            ║
║   Daily Capacity:    ${(avgCapacity * 60 * 24).toLocaleString()} trades                                         ║
║                                                                               ║
╚═══════════════════════════════════════════════════════════════════════════════╝
`);

    // Print broker summary
    console.log(`
╔═══════════════════════════════════════════════════════════════════════════════╗
║                                                                               ║
║   💼 COMPLETE BROKER ECOSYSTEM                                                ║
║                                                                               ║
╠═══════════════════════════════════════════════════════════════════════════════╣
`);
    
    const types = ['crypto', 'forex', 'stocks', 'cfd', 'multi'];
    types.forEach(type => {
      const typeBrokers = BROKERS.filter(b => b.type === type);
      if (typeBrokers.length === 0) return;
      
      const typeName = type.toUpperCase().padEnd(8);
      console.log(`║   ${typeName}                                                                  ║`);
      console.log(`║   ─────────────────────────────────────────────────────────────────           ║`);
      
      typeBrokers.forEach(b => {
        const taxNote = b.taxFree ? '🎁' : '';
        const totalFee = ((b.makerFee + b.takerFee + b.spreadCost) * 100).toFixed(2);
        console.log(`║   ${b.emoji} ${b.name.padEnd(15)} │ ${b.tradesPerMinute.toString().padStart(3)}/min │ ${totalFee}% fee │ ${b.tradingHours.padEnd(8)} │ ${taxNote} ║`);
      });
      console.log(`║                                                                               ║`);
    });
    
    console.log(`╚═══════════════════════════════════════════════════════════════════════════════╝`);
    
    // Now show current live status
    this.currentTime = new Date();
    console.log('\n\n📍 CURRENT LIVE STATUS:\n');
    this.printCurrentStatus();
  }
}

// Run
const trader = new GlobalEcosystemTrader();
trader.run();
