"""
Aureon Price Feed Router v3

Priority: Free APIs first, Capital.com ONLY for execution.

1. Yahoo Finance (free, no auth) — stocks, forex, commodities, indices
2. Binance (free, no auth) — crypto
3. CoinGecko (free, no auth) — crypto fallback
4. Capital.com — RATE LIMITED, execution only

Gary Leckey | 2026 | Free data, paid execution
"""

import json
import logging
import sys
import time
from pathlib import Path
from typing import Dict, Optional
from urllib.request import urlopen, Request
from urllib.parse import quote

try:
    from aureon_fusion.api_communion import get_json as _communion_get_json
except ImportError:  # radar runs with aureon_radar/ as sys.path[0]
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from aureon_fusion.api_communion import get_json as _communion_get_json

logger = logging.getLogger(__name__)

# Communion TTLs per upstream source (seconds)
YAHOO_TTL_S = 90
BINANCE_TTL_S = 30
COINGECKO_TTL_S = 60

# Cache
_price_cache: Dict[str, dict] = {}
_CACHE_TTL = 5  # 5 second cache

# ── YAHOO FINANCE SYMBOL MAP ──
# Covers: stocks, indices, forex, commodities, crypto
YAHOO_MAP = {
    # Forex
    "USDJPY": "USDJPY=X", "EURUSD": "EURUSD=X", "GBPUSD": "GBPUSD=X",
    # Indices
    "US100": "^NDX",
    # Stocks  
    "AAPL": "AAPL", "TSLA": "TSLA", "NVDA": "NVDA",
    # Commodities (futures)
    "GOLD": "GC=F", "SILVER": "SI=F", "OIL_CRUDE": "CL=F", "NATURALGAS": "NG=F",
    # Crypto (Yahoo has these too)
    "BTCUSD": "BTC-USD", "ETHUSD": "ETH-USD",
}

# ── BINANCE MAP ──
BINANCE_MAP = {
    "BTCUSD": "BTCUSDT", "ETHUSD": "ETHUSDT",
}

# ── COINGECKO MAP ──
COINGECKO_MAP = {
    "BTCUSD": "bitcoin", "ETHUSD": "ethereum",
}

# ── CAPITAL SCALING FIX ──
# Capital.com returns forex in "pip" format (×100 or ×10000)
# Other assets may also be scaled
CAPITAL_SCALE = {
    "USDJPY": 0.01,      # 15843 → 158.43
    "EURUSD": 0.0001,    # 11579 → 1.1579
    "GBPUSD": 0.0001,    # 13485 → 1.3485
}


def _fetch_yahoo(symbol: str) -> Optional[float]:
    """Fetch from Yahoo Finance (free, no auth needed)."""
    yahoo_sym = YAHOO_MAP.get(symbol)
    if not yahoo_sym:
        return None
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{quote(yahoo_sym)}?interval=1d&range=1d"
        # Browser-like UA — Yahoo rejects obvious bot agents
        data = _communion_get_json(
            url, ttl_s=YAHOO_TTL_S, timeout=5,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
        )
        if not data:
            logger.debug(f"Yahoo failed for {symbol}")
            return None
        result = data.get("chart", {}).get("result", [{}])[0]
        meta = result.get("meta", {})
        # Try current price first, then previous close
        price = meta.get("regularMarketPrice")
        if price is None:
            price = meta.get("previousClose")
        if price and price > 0:
            logger.debug(f"[PRICE] Yahoo {symbol} = {price}")
            return float(price)
    except Exception as e:
        logger.debug(f"Yahoo failed for {symbol}: {e}")
    return None


def _fetch_binance(symbol: str) -> Optional[float]:
    """Fetch from Binance (free, no auth)."""
    bin_sym = BINANCE_MAP.get(symbol)
    if not bin_sym:
        return None
    try:
        url = f"https://api.binance.com/api/v3/ticker/price?symbol={bin_sym}"
        data = _communion_get_json(url, ttl_s=BINANCE_TTL_S, timeout=3)
        if not data:
            logger.debug(f"Binance failed for {symbol}")
            return None
        price = float(data.get("price", 0))
        if price > 0:
            logger.debug(f"[PRICE] Binance {symbol} = {price}")
            return price
    except Exception as e:
        logger.debug(f"Binance failed for {symbol}: {e}")
    return None


def _fetch_coingecko(symbol: str) -> Optional[float]:
    """Fetch from CoinGecko (free tier, no auth)."""
    cg_id = COINGECKO_MAP.get(symbol)
    if not cg_id:
        return None
    try:
        url = f"https://api.coingecko.com/api/v3/simple/price?ids={cg_id}&vs_currencies=usd"
        data = _communion_get_json(url, ttl_s=COINGECKO_TTL_S, timeout=5)
        if not data:
            logger.debug(f"CoinGecko failed for {symbol}")
            return None
        price = data.get(cg_id, {}).get("usd", 0)
        if price > 0:
            logger.debug(f"[PRICE] CoinGecko {symbol} = {price}")
            return float(price)
    except Exception as e:
        logger.debug(f"CoinGecko failed for {symbol}: {e}")
    return None


def _fetch_capital(capital_connector, symbol: str) -> Optional[float]:
    """LAST RESORT: Capital.com with forex scaling fix."""
    if not capital_connector:
        return None
    try:
        price = capital_connector.get_price(symbol)
        if price and price > 0:
            # Apply forex scaling if known
            scale = CAPITAL_SCALE.get(symbol, 1.0)
            if scale != 1.0:
                fixed = price * scale
                logger.info(f"[PRICE] Capital {symbol} raw={price} scaled={fixed}")
                return fixed
            logger.debug(f"[PRICE] Capital {symbol} = {price}")
            return float(price)
    except Exception as e:
        logger.debug(f"Capital failed for {symbol}: {e}")
    return None


def get_price(symbol: str, capital_connector=None) -> Optional[float]:
    """
    Get price. Priority:
    1. Yahoo Finance (covers everything)
    2. Binance (crypto)
    3. CoinGecko (crypto)
    4. Capital.com (forex scaling fix)
    """
    # Check cache
    if symbol in _price_cache:
        cached = _price_cache[symbol]
        if time.time() - cached["time"] < _CACHE_TTL:
            return cached["price"]
    
    price = None
    source = None
    
    # 1. Yahoo Finance first (covers stocks, forex, commodities, indices, crypto)
    price = _fetch_yahoo(symbol)
    if price:
        source = "yahoo"
    
    # 2. Binance for crypto
    if not price:
        price = _fetch_binance(symbol)
        if price:
            source = "binance"
    
    # 3. CoinGecko for crypto fallback
    if not price:
        price = _fetch_coingecko(symbol)
        if price:
            source = "coingecko"
    
    # 4. Capital.com last resort
    if not price:
        price = _fetch_capital(capital_connector, symbol)
        if price:
            source = "capital"
    
    if price:
        _price_cache[symbol] = {"price": price, "time": time.time()}
        if source:
            logger.info(f"[PRICE] {symbol} = {price} (via {source})")
    else:
        logger.warning(f"[PRICE] Could not fetch {symbol}")
    
    return price


def get_all_prices(symbols: list, capital_connector=None) -> Dict[str, float]:
    """Batch fetch prices."""
    results = {}
    
    # Batch Binance first for crypto
    crypto_syms = [s for s in symbols if BINANCE_MAP.get(s)]
    if crypto_syms:
        try:
            url = "https://api.binance.com/api/v3/ticker/price"
            with urlopen(url, timeout=5) as resp:
                data = json.loads(resp.read().decode())
                for item in data:
                    sym = item.get("symbol", "")
                    for our_sym, bin_sym in BINANCE_MAP.items():
                        if bin_sym == sym:
                            results[our_sym] = float(item.get("price", 0))
                            break
        except Exception as e:
            logger.debug(f"Binance batch failed: {e}")
    
    # Fill gaps individually
    for sym in symbols:
        if sym not in results:
            price = get_price(sym, capital_connector)
            if price:
                results[sym] = price
    
    return results
