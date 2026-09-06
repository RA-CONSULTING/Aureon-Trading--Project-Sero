"""Live market momentum scanner — REAL market data (Binance public REST).

Reference implementation for the real-signal layer. Every other real-signal
module must follow these binding conventions:

  * expose a module-level ``scan(symbol, price)`` — the hub probes this name
    first and coerces the result (see SignalFusionEngine._coerce_score).
  * return either a float in [-1, 1] or a dict
    {"direction": "LONG"|"SHORT"|"NEUTRAL", "confidence": 0..1}.
    A NEUTRAL/low-conviction result returns None upstream and is omitted
    from fusion — never force a direction to fake participation.
  * map hub symbols via SYMBOL_MAP; anything unmapped returns None.
  * REAL data only. On any network failure, rate limit, stale (>60s) or
    unprovable timestamp: return None. Never synthesise a price or score.
  * cache responses ~45s per symbol; hard timeout <=5s per call. A scanner
    must never stall the hub's 5s extraction deadline.
"""

from __future__ import annotations

import math
import time
from typing import Optional

import requests

# ── symbol mapping (hub symbol -> Binance public symbol) ────────────────────
SYMBOL_MAP = {
    "BTCUSD": "BTCUSDT", "BTCUSDT": "BTCUSDT", "BTC": "BTCUSDT", "XBTUSD": "BTCUSDT",
    "ETHUSD": "ETHUSDT", "ETHUSDT": "ETHUSDT", "ETH": "ETHUSDT",
}

_BASE = "https://api.binance.com/api/v3"
_TIMEOUT = 4.0
_CACHE_TTL = 45.0
_cache: dict = {}


def _fetch(symbol: str) -> Optional[dict]:
    now = time.time()
    hit = _cache.get(symbol)
    if hit and now - hit[0] < _CACHE_TTL:
        return hit[1]
    try:
        r = requests.get(f"{_BASE}/ticker/24hr", params={"symbol": symbol},
                         timeout=_TIMEOUT)
        if r.status_code != 200:
            return None
        t = r.json()
        k = requests.get(f"{_BASE}/klines", params={"symbol": symbol,
                         "interval": "15m", "limit": 48}, timeout=_TIMEOUT)
        klines = k.json() if k.status_code == 200 else []
        close = [float(c[4]) for c in klines] if isinstance(klines, list) else []
        vol = [float(c[5]) for c in klines] if isinstance(klines, list) else []
        data = {
            "change_pct": float(t.get("priceChangePercent", 0.0)),
            "quote_vol": float(t.get("quoteVolume", 0.0)),
            "last": float(t.get("lastPrice", 0.0)),
            "closes": close,
            "vols": vol,
        }
        _cache[symbol] = (now, data)
        return data
    except Exception:
        return None


def _ema(values, period: int) -> float:
    if len(values) < period:
        return values[-1] if values else 0.0
    k = 2.0 / (period + 1)
    e = sum(values[:period]) / period
    for v in values[period:]:
        e = v * k + e * (1 - k)
    return e


def scan(symbol: str, price: float = 0.0):
    """Hub probe entry — returns dict(direction, confidence) or None."""
    bsym = SYMBOL_MAP.get(str(symbol).upper())
    if bsym is None:
        return None
    d = _fetch(bsym)
    if not d or not d["closes"]:
        return None

    # 1) 24h momentum, saturating: ±3% -> ±0.55
    m_mom = math.tanh(d["change_pct"] / 3.0) * 0.55

    # 2) 15m trend: EMA12 vs EMA36 cross, bounded ±0.30
    ema_fast = _ema(d["closes"], 12)
    ema_slow = _ema(d["closes"], 36)
    denom = ema_slow if ema_slow else 1.0
    cross = (ema_fast - ema_slow) / denom
    m_trend = max(-0.30, min(0.30, cross * 25.0))

    # 3) volume confirmation: recent 8-bar vol vs 48-bar avg, bounded ±0.15
    if d["vols"] and len(d["vols"]) >= 16:
        recent = sum(d["vols"][-8:]) / 8.0
        base = sum(d["vols"]) / len(d["vols"]) or 1.0
        vr = recent / base
        sign = 1.0 if (m_mom + m_trend) >= 0 else -1.0
        m_vol = sign * min(0.15, max(0.0, (vr - 1.0) * 0.15))
    else:
        m_vol = 0.0

    score = max(-1.0, min(1.0, m_mom + m_trend + m_vol))
    conf = abs(score)
    if conf < 0.35:
        return None  # no real conviction — omit, don't dilute fusion
    return {
        "direction": "LONG" if score > 0 else "SHORT",
        "confidence": round(conf, 4),
        "source": "binance_public_24h+15m",
    }


if __name__ == "__main__":
    for s in ("BTCUSD", "ETHUSD", "EURUSD"):
        print(s, scan(s))
