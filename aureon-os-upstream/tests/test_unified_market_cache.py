import json
import time

from aureon.data_feeds import unified_market_cache as cache_mod


def test_unified_market_cache_reads_ws_prices_default_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(cache_mod, "CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(cache_mod, "WS_PRICE_CACHE_PATH", str(tmp_path / "ws_prices.json"))
    monkeypatch.setattr(cache_mod, "BINANCE_CACHE_PATH", str(tmp_path / "binance_ws_prices.json"))
    monkeypatch.setattr(cache_mod, "BINANCE_CACHE_PATHS", [str(tmp_path / "ws_prices.json"), str(tmp_path / "binance_ws_prices.json")])
    monkeypatch.setattr(cache_mod, "UNIFIED_CACHE_PATH", str(tmp_path / "unified_prices.json"))
    monkeypatch.setattr(cache_mod, "KRAKEN_CACHE_PATH", str(tmp_path / "kraken_prices.json"))
    cache_mod.UnifiedMarketCache._instance = None
    cache_mod._cache_instance = None

    now = time.time()
    (tmp_path / "ws_prices.json").write_text(
        json.dumps(
            {
                "generated_at": now,
                "source": "binance_ws",
                "prices": {"BTC": 50123.45},
                "source_health": {
                    "binance": {
                        "source": "binance_ws",
                        "active": True,
                        "fresh": True,
                        "ticker_count": 1,
                        "generated_at": now,
                    }
                },
                "ticker_cache": {
                    "BTCUSDT": {
                        "price": 50123.45,
                        "change24h": 1.8,
                        "volume": 2000.0,
                        "base": "BTC",
                        "quote": "USDT",
                        "exchange": "binance",
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    ticker = cache_mod.get_ticker("BTC", max_age=5.0)

    assert ticker is not None
    assert ticker.price == 50123.45
    assert ticker.source == "binance_ws"
    source_health = cache_mod.get_market_cache().get_source_health()
    assert source_health["binance"]["active"] is True
    assert source_health["binance"]["ticker_count"] == 1
    cache_mod.UnifiedMarketCache._instance = None
    cache_mod._cache_instance = None


def test_cached_ticker_rejects_future_and_missing_observations(monkeypatch):
    monkeypatch.setattr(cache_mod.time, "time", lambda: 1_800_000_000.0)
    for timestamp in (0.0, 1_800_000_100.0, float("nan"), float("inf")):
        ticker = cache_mod.CachedTicker("BTC", 50000, 50000, 50000, 0, 0, "binance_ws", timestamp, "BTCUSDT")
        assert ticker.is_fresh(30) is False


def test_cache_preserves_provider_age_and_provenance_when_file_is_republished(tmp_path, monkeypatch):
    monkeypatch.setattr(cache_mod, "CACHE_DIR", str(tmp_path))
    path = tmp_path / "ws_prices.json"
    monkeypatch.setattr(cache_mod, "BINANCE_CACHE_PATHS", [str(path)])
    monkeypatch.setattr(cache_mod, "UNIFIED_CACHE_PATH", str(tmp_path / "unused.json"))
    monkeypatch.setattr(cache_mod, "KRAKEN_CACHE_PATH", str(tmp_path / "unused-kraken.json"))
    monkeypatch.setattr(cache_mod.UnifiedMarketCache, "_instance", None)
    monkeypatch.setattr(cache_mod, "_cache_instance", None)
    now = 1_800_000_100.0
    monkeypatch.setattr(cache_mod.time, "time", lambda: now)
    path.write_text(json.dumps({
        "generated_at": now,
        "source_health": {"binance": {"active": True, "fresh": True, "last_success_at": now - 100, "generated_at": now}},
        "ticker_cache": {
            "BTCUSDT": {"base": "BTC", "price": 50000, "exchange": "binance", "timestamp": now - 100, "provider_timestamp": now - 100, "timestamp_kind": "provider_event"},
            "ETHUSDT": {"base": "ETH", "price": 3000, "exchange": "binance"},
            "SOLUSDT": {"base": "SOL", "price": 100, "exchange": "binance", "timestamp": now - 1, "provider_timestamp": now - 1, "received_at": now, "timestamp_kind": "provider_event"},
        },
    }), encoding="utf-8")
    cache = cache_mod.get_market_cache()
    assert set(cache.get_all_tickers(max_age=30)) == {"SOL"}
    ticker = cache.get_ticker("SOL")
    assert ticker.provider_timestamp == now - 1
    assert ticker.timestamp_kind == "provider_event"
    assert ticker.received_at == now
    assert cache.get_source_health()["binance"]["fresh"] is False
