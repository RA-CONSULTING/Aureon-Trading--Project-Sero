# 🎵 THE TEMPO OF SPACE AND TIME - BROKER API SPECIFICATIONS 🎵

## Real Trading Rate Limits, Fees & Transaction Specs

> *"Every broker has its own rhythm - know the tempo to dance in harmony"*

---

## 🪙 BINANCE (Crypto)

### Rate Limits (The Beat)
```
┌─────────────────────────────────────────────────────────────────┐
│  REQUEST TYPE          │  LIMIT                                │
├─────────────────────────────────────────────────────────────────┤
│  API Weight            │  1,200 per minute (rolling)           │
│  Orders                │  10 orders/second, 100,000/day        │
│  WebSocket Streams     │  5 messages/second per connection     │
│  Connections           │  300 per 5 minutes per IP             │
└─────────────────────────────────────────────────────────────────┘
```

### Trading Fees 💰
```
┌─────────────────────────────────────────────────────────────────┐
│  TIER       │  30d Volume    │  MAKER      │  TAKER           │
├─────────────────────────────────────────────────────────────────┤
│  VIP 0      │  < $1M         │  0.1000%    │  0.1000%         │
│  VIP 1      │  ≥ $1M         │  0.0900%    │  0.1000%         │
│  VIP 2      │  ≥ $5M         │  0.0800%    │  0.1000%         │
│  VIP 3      │  ≥ $10M        │  0.0420%    │  0.0600%         │
│  VIP 9      │  ≥ $4B         │  0.0100%    │  0.0200%         │
│                                                                 │
│  💡 With BNB: -25% discount → VIP0 = 0.075% maker/taker        │
└─────────────────────────────────────────────────────────────────┘
```

### Minimum Order Sizes
```
Notional Minimum: $5 per order (most pairs)
LOT_SIZE: Varies by pair (e.g., BTC = 0.00001, DOGE = 1)
```

### Our Strategy Impact
```
At £100 with 5% position = £5 per trade
Fee per trade: £5 × 0.1% = £0.005 (half a penny!)
500 trades: £2.50 total fees ✅ Very low impact
```

---

## 📊 CAPITAL.COM (CFDs)

### Rate Limits (The Beat)
```
┌─────────────────────────────────────────────────────────────────┐
│  REQUEST TYPE          │  LIMIT                                │
├─────────────────────────────────────────────────────────────────┤
│  All API Calls         │  10 requests/second (REST)            │
│  WebSocket Updates     │  50 price updates/second              │
│  Sessions              │  1 active session per API key         │
│  Positions             │  200 open positions max               │
└─────────────────────────────────────────────────────────────────┘
```

### Trading Fees 💰
```
┌─────────────────────────────────────────────────────────────────┐
│  ASSET TYPE      │  FEE MODEL                                  │
├─────────────────────────────────────────────────────────────────┤
│  All CFDs        │  SPREAD ONLY (no commission)               │
│                                                                 │
│  Typical Spreads:                                               │
│  ─────────────────                                              │
│  EUR/USD         │  0.6 pips                                   │
│  Gold            │  0.3 points                                 │
│  Bitcoin         │  $30-50 (varies with volatility)           │
│  S&P 500         │  0.4 points                                 │
│  Apple           │  0.08% of price                             │
│                                                                 │
│  Overnight Fees:                                                │
│  ─────────────────                                              │
│  Swap Rate       │  ~0.008% daily (positions held overnight)  │
│  Weekend Fee     │  3x Friday (for Sat/Sun)                    │
└─────────────────────────────────────────────────────────────────┘
```

### Minimum Order Sizes
```
Forex: 0.01 lot (1,000 units)
Stocks: 0.1 share equivalent
Crypto: $10 notional
Indices: 0.1 lot
```

### Leverage (UK/EU Retail)
```
Forex Majors: 30:1
Forex Minor: 20:1
Indices: 20:1
Gold: 20:1
Crypto: 2:1
Stocks: 5:1
```

### Our Strategy Impact
```
At £100 with 5% position = £5 per trade
Spread cost: ~0.1-0.2% depending on asset
500 trades: £5-10 total spread costs ✅ Reasonable
⚠️ Overnight fees add up - day trade for efficiency!
```

---

## 🦙 ALPACA (US Stocks & Crypto)

### Rate Limits (The Beat)
```
┌─────────────────────────────────────────────────────────────────┐
│  REQUEST TYPE          │  LIMIT                                │
├─────────────────────────────────────────────────────────────────┤
│  Trading API           │  200 requests/minute                  │
│  Data API              │  200 requests/minute (separate)       │
│  WebSocket Streams     │  Unlimited real-time                  │
│  Concurrent Streams    │  1 per subscription tier              │
│  Orders Per Day        │  No limit (but PDT rules apply)       │
└─────────────────────────────────────────────────────────────────┘
```

### Trading Fees 💰
```
┌─────────────────────────────────────────────────────────────────┐
│  ASSET TYPE      │  COMMISSION     │  NOTES                    │
├─────────────────────────────────────────────────────────────────┤
│  US Stocks       │  $0.00          │  Commission-free! 🎉      │
│  ETFs            │  $0.00          │  Commission-free! 🎉      │
│  Options         │  $0.00          │  Commission-free! 🎉      │
│  Crypto          │  0.15%          │  Taker fee                │
│  Crypto Maker    │  0.12%          │  Limit orders             │
│                                                                 │
│  Hidden Costs:                                                  │
│  ─────────────────                                              │
│  Payment for     │  Included in    │  Typical 0.001-0.002%    │
│  Order Flow      │  execution      │  price improvement        │
│                                                                 │
│  Margin Interest:                                               │
│  ─────────────────                                              │
│  Basic           │  9.75% APR      │  Under $100k              │
│  Premium         │  8.75% APR      │  Over $100k               │
└─────────────────────────────────────────────────────────────────┘
```

### Minimum Order Sizes
```
Stocks: $1 minimum (fractional shares allowed!)
Crypto: $1 minimum
```

### Pattern Day Trader (PDT) Rules ⚠️
```
If account < $25,000:
  - Max 3 day trades per rolling 5 days
  - Day trade = buy + sell same security same day
  
Our workaround:
  - Use different securities each day
  - Or hold overnight (swing trade)
  - Or fund account to $25,000+
```

### Our Strategy Impact
```
At £100 with 5% position = £5 per trade
Stock fee: £0.00 (FREE!) 🎉
Crypto fee: £5 × 0.15% = £0.0075
500 stock trades: £0 total fees ✅ AMAZING
500 crypto trades: £3.75 total fees ✅ Very low
⚠️ Watch PDT rule with < $25k account!
```

---

## 💱 OANDA (Forex)

### Rate Limits (The Beat)
```
┌─────────────────────────────────────────────────────────────────┐
│  REQUEST TYPE          │  LIMIT                                │
├─────────────────────────────────────────────────────────────────┤
│  REST API              │  120 requests/second (!)              │
│  Streaming API         │  20 connections max                   │
│  Price Polls           │  1 per second recommended             │
│  Historical Data       │  500 candles per request              │
│  Orders                │  No explicit limit                    │
└─────────────────────────────────────────────────────────────────┘
```

### Trading Fees 💰
```
┌─────────────────────────────────────────────────────────────────┐
│  PAIR           │  TYPICAL SPREAD  │  COMMISSION              │
├─────────────────────────────────────────────────────────────────┤
│  EUR/USD        │  1.0-1.4 pips    │  $0 (spread only)        │
│  GBP/USD        │  1.4-1.8 pips    │  $0 (spread only)        │
│  USD/JPY        │  1.0-1.4 pips    │  $0 (spread only)        │
│  Gold (XAU/USD) │  0.33 points     │  $0 (spread only)        │
│  Oil (BCO/USD)  │  0.03 points     │  $0 (spread only)        │
│                                                                 │
│  Premium Account:                                               │
│  ─────────────────                                              │
│  All pairs      │  -20% tighter    │  Still $0                 │
│                                                                 │
│  Overnight Financing:                                           │
│  ─────────────────                                              │
│  Rate           │  Based on pair   │  Daily @ 5pm EST          │
│  Example        │  EUR/USD long    │  ~-0.005% per day         │
└─────────────────────────────────────────────────────────────────┘
```

### Minimum Order Sizes
```
Minimum: 1 unit of base currency
Standard lot: 100,000 units
Mini lot: 10,000 units
Micro lot: 1,000 units
Nano lot: 1 unit (OANDA specialty!)
```

### Leverage (UK/EU Retail)
```
Major Pairs: 30:1
Minor Pairs: 20:1
Exotics: 10:1
Gold: 20:1
```

### Our Strategy Impact
```
At £100 with 5% position = £5 per trade
Spread cost: ~1.2 pips on EUR/USD
   = 1.2 × $0.0001 × 1000 units = $0.12 per trade
500 trades: ~$60 (£48) total spread costs 
⚠️ Higher than stocks! Forex spreads matter.
💡 Trade major pairs only for tightest spreads
```

---

## 🎼 THE UNIFIED TEMPO COMPARISON

```
╔═══════════════════════════════════════════════════════════════════════════╗
║                    THE RHYTHM OF EACH INSTRUMENT                          ║
╠═══════════════════════════════════════════════════════════════════════════╣
║                                                                           ║
║  BROKER      │ TEMPO        │ COST/TRADE  │ MIN SIZE  │ BEST FOR         ║
║  ───────────────────────────────────────────────────────────────────────  ║
║  🪙 Binance   │ ♩=600/min    │ 0.075%      │ $5        │ Crypto           ║
║  📊 Capital   │ ♩=10/sec     │ 0.1% spread │ £10       │ CFDs             ║
║  🦙 Alpaca    │ ♩=200/min    │ FREE stocks │ $1        │ US Stocks        ║
║  💱 OANDA     │ ♩=120/sec    │ 1.2 pips    │ 1 unit    │ Forex            ║
║                                                                           ║
╚═══════════════════════════════════════════════════════════════════════════╝
```

---

## 📊 COST ANALYSIS FOR 500 TRADES (£100 EACH BROKER)

```
┌─────────────────────────────────────────────────────────────────────────┐
│  BROKER        │  TRADES  │  EST. FEES    │  AS % OF CAPITAL          │
├─────────────────────────────────────────────────────────────────────────┤
│  🪙 Binance     │  500     │  ~£2.50       │  2.5%                     │
│  📊 Capital.com │  500     │  ~£8.00       │  8.0%                     │
│  🦙 Alpaca      │  500     │  ~£0.00       │  0.0% 🎉                  │
│  💱 OANDA       │  500     │  ~£48.00      │  48.0% ⚠️                 │
├─────────────────────────────────────────────────────────────────────────┤
│  TOTAL         │  2000    │  ~£58.50      │  14.6% of £400            │
└─────────────────────────────────────────────────────────────────────────┘

Our simulation profit: +£71.89
Estimated real fees:   -£58.50
Net after fees:        +£13.39 ✅ Still profitable!

💡 OPTIMIZATION TIPS:
───────────────────────
1. Use BNB for Binance fees (-25%)
2. Trade major forex pairs only on OANDA
3. Focus on stocks over crypto on Alpaca
4. Day trade on Capital.com to avoid overnight fees
```

---

## ⚡ OPTIMAL TRADE FREQUENCY (THE TEMPO)

### Per-Minute Sustainable Rate
```
┌─────────────────────────────────────────────────────────────────┐
│  BROKER        │  SAFE RATE      │  BURST RATE    │  COOLDOWN  │
├─────────────────────────────────────────────────────────────────┤
│  🪙 Binance     │  30 trades/min  │  10/second     │  Auto      │
│  📊 Capital.com │  5 trades/min   │  10/second     │  100ms     │
│  🦙 Alpaca      │  60 trades/min  │  3/second      │  100ms     │
│  💱 OANDA       │  60 trades/min  │  120/second    │  None      │
└─────────────────────────────────────────────────────────────────┘

RECOMMENDED UNIFIED TEMPO: 🎵 30 trades/minute per broker
  = 2 trades per broker every 4 seconds
  = 120 trades/minute total across all 4
  = 7,200 trades/hour maximum sustainable
```

---

## 🎯 POSITION LIMITS

```
┌─────────────────────────────────────────────────────────────────┐
│  BROKER        │  MAX POSITIONS  │  MAX LEVERAGE  │  MARGIN    │
├─────────────────────────────────────────────────────────────────┤
│  🪙 Binance     │  Unlimited      │  20x (futures) │  5%        │
│  📊 Capital.com │  200            │  30x (forex)   │  3.33%     │
│  🦙 Alpaca      │  Unlimited      │  4x (margin)   │  25%       │
│  💱 OANDA       │  Unlimited      │  30x (forex)   │  3.33%     │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🌙 MARKET HOURS (THE SCHEDULE)

```
┌─────────────────────────────────────────────────────────────────┐
│  MARKET          │  HOURS (UTC)              │  BEST LIQUIDITY │
├─────────────────────────────────────────────────────────────────┤
│  🪙 Crypto        │  24/7/365                 │  Always         │
│  💱 Forex         │  Sun 21:00 - Fri 21:00   │  London session │
│  🦙 US Stocks     │  Mon-Fri 14:30-21:00     │  First 2 hours  │
│  📊 CFDs          │  Varies by underlying    │  Match asset    │
│                                                                 │
│  🎯 OVERLAP WINDOWS (Best for unified symphony):               │
│  ─────────────────────────────────────────────────────────────  │
│  14:30-17:00 UTC │  US + London + Crypto    │  MAXIMUM 🔥     │
│  08:00-09:00 UTC │  London open + Asia end  │  Forex peak     │
│  21:00-22:00 UTC │  US close + Asia open    │  Transition     │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🎵 THE SYMPHONY'S RECOMMENDED TEMPO

```
╔═══════════════════════════════════════════════════════════════════════════╗
║                                                                           ║
║   🎼 OPTIMAL TRADING RHYTHM FOR THE DANCE OF SPACE AND TIME 🎼           ║
║                                                                           ║
║   ┌─────────────────────────────────────────────────────────────────┐    ║
║   │                                                                 │    ║
║   │   TEMPO:      ♩ = 30 BPM (trades per minute, per broker)       │    ║
║   │   MEASURE:    4/4 time (4 brokers, 4 beats per measure)        │    ║
║   │   DYNAMICS:   mf (moderate position sizing)                    │    ║
║   │   ARTICULATION: staccato (quick in/out trades)                 │    ║
║   │                                                                 │    ║
║   │   🪙 Beat 1: Binance  →  Place crypto order                    │    ║
║   │   📊 Beat 2: Capital  →  Place CFD order                       │    ║
║   │   🦙 Beat 3: Alpaca   →  Place stock order                     │    ║
║   │   💱 Beat 4: OANDA    →  Place forex order                     │    ║
║   │   🔄 Repeat...                                                  │    ║
║   │                                                                 │    ║
║   │   Total Harmony: 120 trades/minute unified                     │    ║
║   │   Daily Capacity: 172,800 trades (24h operation)               │    ║
║   │                                                                 │    ║
║   └─────────────────────────────────────────────────────────────────┘    ║
║                                                                           ║
║   🎵 "One tempo, four instruments, infinite possibilities" 🎵           ║
║                                                                           ║
╚═══════════════════════════════════════════════════════════════════════════╝
```

---

## 📋 QUICK REFERENCE CARD

| Metric | Binance | Capital.com | Alpaca | OANDA |
|--------|---------|-------------|--------|-------|
| **API Speed** | 1200/min | 600/min | 200/min | 7200/min |
| **Trade Fee** | 0.1% | Spread | FREE | Spread |
| **Min Order** | $5 | £10 | $1 | 1 unit |
| **Max Positions** | ∞ | 200 | ∞ | ∞ |
| **Best Asset** | Crypto | CFDs | Stocks | Forex |
| **24/7** | ✅ | Partial | ❌ | Partial |
| **Demo Mode** | Testnet | Demo | Paper | Practice |

---

## 🚀 GOING LIVE CHECKLIST

```
□ Binance: Fund account, enable spot trading
□ Capital.com: Verify identity, switch to LIVE environment
□ Alpaca: Fund $25k+ to avoid PDT (or trade carefully)
□ OANDA: Create live account, fund minimum £100

□ Set environment variables:
  - Remove DEMO/PAPER/TESTNET flags
  - Use production API endpoints
  - Enable 2FA on all accounts

□ Start small: £100 each (£400 total)
□ Monitor first 100 trades manually
□ Scale up after 500+ profitable trades
```

---

*"The tempo is set, the instruments tuned, the symphony awaits its conductor."* 🎵

**YOU have built something beautiful. The dance of space and time is ready.** 🙏

