import asyncio
import json
import threading
import urllib.error
import urllib.request
from unittest.mock import patch

import aureon.data_feeds.ws_market_data_feeder as feeder_mod
from aureon.data_feeds.ws_market_data_feeder import (
    CAPITAL_DEFAULT_SYMBOLS,
    MarketSnapshotStore,
    LatestSnapshotPublisher,
    _acquire_single_writer_lock,
    _build_generic_ticker_cache,
    _cached_last_good_snapshot,
    _extract_kraken_prices_and_tickers,
    _extract_prices_and_tickers,
    _merge_market_snapshots,
    _release_single_writer_lock,
    _snapshots_from_merged_cache,
    _ticker_cache_to_waveform_bars,
)


_STREAM_TEST_EPOCH = 1_700_000_000


def _incremental_binance(symbol, price, timestamp):
    return feeder_mod._build_binance_snapshot(
        [{"s": symbol, "c": str(price), "o": str(price), "v": "1", "E": (_STREAM_TEST_EPOCH + timestamp) * 1000}],
        binance_uk_mode=False, source="binance_ws", mode="websocket_all_market_ticker_stream",
    )


def test_blocked_store_write_keeps_loop_responsive_and_coalesces_latest_per_symbol(tmp_path, monkeypatch):
    out_path = tmp_path / "cache.json"
    store = MarketSnapshotStore(out_path)
    started, release = threading.Event(), threading.Event()
    original_write = feeder_mod._atomic_write_json
    writes = []
    active = 0
    maximum_active = 0
    loop_thread = threading.get_ident()
    writer_threads = []
    def blocked_write(path, payload):
        nonlocal active, maximum_active
        writer_threads.append(threading.get_ident())
        active += 1
        maximum_active = max(maximum_active, active)
        try:
            if not started.is_set():
                started.set()
                release.wait(3)
            original_write(path, payload)
            writes.append(payload)
        finally:
            active -= 1
    monkeypatch.setattr(feeder_mod, "_atomic_write_json", blocked_write)
    async def scenario():
        publisher = LatestSnapshotPublisher(store, "binance")
        publisher.submit(_incremental_binance("BTCUSDT", 100, 1000))
        try:
            assert await asyncio.to_thread(started.wait, 2)
            await asyncio.sleep(0)
            assert writes == [], "disk work blocked the event loop"
            publisher.submit(_incremental_binance("ETHUSDT", 20, 1002))
            publisher.submit(_incremental_binance("ADAUSDT", 3, 1003))
            publisher.submit(_incremental_binance("ETHUSDT", 999, 1001))
            other = asyncio.create_task(store.update("kraken", feeder_mod._disabled_snapshot("kraken", "test_no_data")))
            await asyncio.sleep(0)
            assert writes == []
        finally:
            release.set()
        await publisher.flush()
        await other
        assert publisher.last_error == ""
    asyncio.run(scenario())
    assert maximum_active == 1
    assert all(thread != loop_thread for thread in writer_threads)
    assert len(writes) == 3  # In-flight Binance, coalesced Binance, one Kraken.
    written = json.loads(out_path.read_text(encoding="utf-8"))
    cache = written["ticker_cache"]
    assert {cache[key]["base"] for key in cache} == {"BTC", "ETH", "ADA"}
    assert cache["ETHUSDT"]["price"] == 20
    assert cache["ETHUSDT"]["timestamp"] == _STREAM_TEST_EPOCH + 1002
    assert cache["BTCUSDT"]["timestamp"] == _STREAM_TEST_EPOCH + 1000
    assert cache["ADAUSDT"]["timestamp"] == _STREAM_TEST_EPOCH + 1003
    assert written["prices"]["ETH"] == 20
    assert written["source_health"]["binance"]["fresh"] is False


def test_cancelled_store_update_retains_writer_lock_until_disk_job_finishes(tmp_path, monkeypatch):
    store = MarketSnapshotStore(tmp_path / "cache.json")
    started, release = threading.Event(), threading.Event()
    writes = []
    active = 0
    maximum_active = 0
    def blocked_write(path, payload):
        nonlocal active, maximum_active
        active += 1
        maximum_active = max(maximum_active, active)
        try:
            if not started.is_set():
                started.set()
                release.wait(3)
            writes.append(payload)
        finally:
            active -= 1
    monkeypatch.setattr(feeder_mod, "_atomic_write_json", blocked_write)
    async def scenario():
        first = asyncio.create_task(store.update("binance", _incremental_binance("BTCUSDT", 100, 1000)))
        try:
            assert await asyncio.to_thread(started.wait, 2)
            first.cancel()
            await asyncio.sleep(0)
            second = asyncio.create_task(store.update("kraken", feeder_mod._disabled_snapshot("kraken", "test_no_data")))
            await asyncio.sleep(0)
            assert not first.done()
            assert writes == []
        finally:
            release.set()
        results = await asyncio.gather(first, second, return_exceptions=True)
        assert isinstance(results[0], asyncio.CancelledError)
        assert isinstance(results[1], dict)
    asyncio.run(scenario())
    assert maximum_active == 1
    assert len(writes) == 2


def _get_public_quotes(server):
    with urllib.request.urlopen(f"http://127.0.0.1:{server.server_port}/api/quotes", timeout=2) as response:
        return json.loads(response.read().decode("utf-8"))


def test_memory_quote_endpoint_serves_latest_source_clocks_during_blocked_disk(tmp_path, monkeypatch):
    clock = [_STREAM_TEST_EPOCH + 1000.0]
    monkeypatch.setattr(feeder_mod.time, "time", lambda: clock[0])
    store = MarketSnapshotStore(tmp_path / "cache.json")
    started, release = threading.Event(), threading.Event()
    writes = []
    def blocked_write(path, payload):
        if not started.is_set():
            started.set()
            release.wait(3)
        writes.append(payload)
    monkeypatch.setattr(feeder_mod, "_atomic_write_json", blocked_write)
    server = feeder_mod.start_public_snapshot_server(store, port=0)
    assert server.server_address[0] == "127.0.0.1"
    async def scenario():
        publisher = LatestSnapshotPublisher(store, "binance")
        publisher.submit(_incremental_binance("BTCUSDT", 100, 1000))
        try:
            assert await asyncio.to_thread(started.wait, 2)
            clock[0] += 1
            publisher.submit(_incremental_binance("ETHUSDT", 20, 1001))
            fresh = await asyncio.to_thread(_get_public_quotes, server)
            assert writes == []
            assert fresh["fresh"] is True
            assert fresh["transport"] == "loopback_memory"
            assert fresh["producer_pid"] == feeder_mod.os.getpid()
            assert fresh["ticker_cache"]["binance:ETHUSDT"]["timestamp"] == clock[0]
            assert fresh["ticker_cache"]["binance:BTCUSDT"]["timestamp"] == clock[0] - 1
            original_generated_at = fresh["generated_at"]
            original_rows = fresh["ticker_cache"]
            clock[0] += 6
            expired = await asyncio.to_thread(_get_public_quotes, server)
            assert expired["fresh"] is False
            assert expired["data_status"] == "stale"
            assert expired["source_health"]["binance"]["freshness_limit_sec"] == 5
            assert expired["ticker_cache"] == original_rows
            assert expired["generated_at"] == original_generated_at
            assert writes == []
        finally:
            release.set()
            await publisher.flush()
    try:
        asyncio.run(scenario())
    finally:
        server.shutdown()
        server.server_close()


def test_public_quote_endpoint_is_get_only_and_excludes_account_fields(tmp_path):
    store = MarketSnapshotStore(tmp_path / "cache.json")
    payload = _incremental_binance("BTCUSDT", 100, 1000)
    payload.update(api_key="not-public", accounts=[{"balance": 500}], raw={"token": "not-public"})
    payload["ticker_cache"]["BTCUSDT"].update(api_secret="not-public", account_id="not-public", raw={"token": "not-public"})
    store.publish_memory("binance", payload)
    server = feeder_mod.start_public_snapshot_server(store, port=0)
    try:
        snapshot = _get_public_quotes(server)
        encoded = json.dumps(snapshot)
        assert "not-public" not in encoded
        assert "api_key" not in encoded and "accounts" not in encoded and "raw" not in encoded
        assert len(snapshot["ticker_cache"]) == 1  # Provider aliases are deduplicated.
        for method, path, status in (("POST", "/api/quotes", 405), ("GET", "/accounts", 404)):
            request = urllib.request.Request(f"http://127.0.0.1:{server.server_port}{path}", method=method)
            try:
                urllib.request.urlopen(request, timeout=2)
                assert False, "unsupported route or method accepted"
            except urllib.error.HTTPError as error:
                assert error.code == status
        assert not store.out_path.exists()
    finally:
        server.shutdown()
        server.server_close()


def test_public_quote_projection_bounds_rows_and_rejects_invalid_clocks(tmp_path, monkeypatch):
    monkeypatch.setattr(feeder_mod, "PUBLIC_SNAPSHOT_MAX_ROWS", 2)
    store = MarketSnapshotStore(tmp_path / "cache.json")
    for symbol, timestamp in (("BTCUSDT", 1000), ("ETHUSDT", 1001), ("ADAUSDT", 1002)):
        store.publish_memory("binance", _incremental_binance(symbol, 10, timestamp))
    bad = _incremental_binance("BADUSDT", 10, 1003)
    for row in bad["ticker_cache"].values():
        row["timestamp"] = None
        row["provider_timestamp"] = None
    store.publish_memory("binance", bad)
    projected = store.public_quote_snapshot()
    assert set(projected["ticker_cache"]) == {"binance:ADAUSDT", "binance:ETHUSDT"}
    assert projected["truncated"] is True
    assert len(json.dumps(projected).encode("utf-8")) < feeder_mod.PUBLIC_SNAPSHOT_MAX_BYTES


def test_extract_prices_accepts_binance_websocket_payload():
    prices, ticker_cache = _extract_prices_and_tickers(
        [{"s": "BTCUSDT", "c": "50000.0", "P": "1.5", "v": "12.0"}],
        binance_uk_mode=False,
    )

    assert prices["BTC"] == 50000.0
    assert ticker_cache["BTCUSDT"]["change24h"] == 1.5
    assert ticker_cache["binance:BTCUSDT"]["volume"] == 12.0


def test_extract_prices_accepts_binance_rest_24hr_payload():
    prices, ticker_cache = _extract_prices_and_tickers(
        [
            {
                "symbol": "ETHUSDT",
                "lastPrice": "3200.0",
                "priceChangePercent": "2.25",
                "quoteVolume": "987654321.0",
            }
        ],
        binance_uk_mode=False,
    )

    assert prices["ETH"] == 3200.0
    assert ticker_cache["ETHUSDT"]["change24h"] == 2.25
    assert ticker_cache["ETHUSDT"]["volume"] == 987654321.0


def test_extract_kraken_prices_accepts_public_ticker_payload():
    prices, ticker_cache = _extract_kraken_prices_and_tickers(
        {
            "XXBTZUSD": {
                "a": ["50100.0"],
                "b": ["50000.0"],
                "c": ["50050.0"],
                "o": "49000.0",
                "v": ["1.0", "2.0"],
            }
        }
    )

    assert prices["BTC"] == 50050.0
    assert ticker_cache["BTCUSD"]["exchange"] == "kraken"
    assert ticker_cache["kraken:BTCUSD"]["quote"] == "USD"
    assert ticker_cache["BTCUSD"]["change24h"] > 2.0


def test_generic_authenticated_snapshots_build_equity_cache():
    prices, ticker_cache = _build_generic_ticker_cache(
        [{"symbol": "AAPL", "price": 215.5, "bid": 215.4, "ask": 215.6, "change_pct": 0.8, "volume": 12345}],
        exchange="alpaca",
        source="alpaca_rest_snapshot",
    )

    assert prices["AAPL"] == 215.5
    assert ticker_cache["AAPLUSD"]["exchange"] == "alpaca"
    assert ticker_cache["alpaca:AAPLUSD"]["change24h"] == 0.8


def test_capital_default_watchlist_prioritizes_gold_target_lane():
    assert CAPITAL_DEFAULT_SYMBOLS[:4] == ["GOLD", "GCM2026", "GLD", "GDX"]


def test_merge_market_snapshots_preserves_source_health_and_tickers():
    merged = _merge_market_snapshots(
        {
            "binance": {
                "generated_at": 100.0,
                "source": "binance_ws",
                "prices": {"BTC": 50000.0},
                "ticker_cache": {"BTCUSDT": {"price": 50000.0, "base": "BTC", "exchange": "binance"}},
                "source_health": {"binance": {"source": "binance_ws", "active": True, "generated_at": 100.0}},
            },
            "kraken": {
                "generated_at": 101.0,
                "source": "kraken_public_rest",
                "prices": {"ETH": 3000.0},
                "ticker_cache": {"ETHUSD": {"price": 3000.0, "base": "ETH", "exchange": "kraken"}},
                "source_health": {"kraken": {"source": "kraken_public_rest", "active": True, "generated_at": 101.0}},
            },
        }
    )

    assert merged["source"] == "multi_exchange_stream_cache"
    assert merged["prices"]["BTC"] == 50000.0
    assert merged["prices"]["ETH"] == 3000.0
    assert set(merged["source_health"]) == {"binance", "kraken"}
    assert "ETHUSD" in merged["ticker_cache"]


def test_live_cache_tickers_convert_to_global_waveform_bars():
    bars = _ticker_cache_to_waveform_bars(
        {
            "generated_at": 100.0,
            "source": "multi_exchange_stream_cache",
            "ticker_cache": {
                "binance:BTCUSDT": {
                    "price": 50000.0,
                    "bid": 49990.0,
                    "ask": 50010.0,
                    "volume": 1000000.0,
                    "base": "BTC",
                    "quote": "USDT",
                    "exchange": "binance",
                    "pair": "BTCUSDT",
                },
                "kraken:ETHUSD": {
                    "price": 3000.0,
                    "volume": 2000000.0,
                    "base": "ETH",
                    "quote": "USD",
                    "exchange": "kraken",
                    "pair": "ETHUSD",
                },
            },
        },
        now_ms=1_800_000_123_456,
        bucket_ms=60_000,
        max_symbols=2,
    )

    assert len(bars) == 2
    assert bars[0]["provider"] == "aureon_live_stream_cache"
    assert bars[0]["period_id"] == "LIVE_60S"
    assert bars[0]["symbol"] in {"BTCUSD", "ETHUSD"}
    assert any(bar["venue"] == "KRAKEN" for bar in bars)


def test_single_writer_lock_replaces_stale_lock(tmp_path):
    lock_path = tmp_path / "state" / "feeder.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text('{"pid": 999999999, "out_path": "old"}', encoding="utf-8")

    acquired = _acquire_single_writer_lock(lock_path, out_path=tmp_path / "ws_cache" / "ws_prices.json")

    assert acquired == lock_path
    assert "999999999" not in lock_path.read_text(encoding="utf-8")
    _release_single_writer_lock(acquired)
    assert not lock_path.exists()


def test_windows_pid_check_uses_tasklist_before_openprocess():
    with patch.object(feeder_mod.sys, "platform", "win32"), patch.object(feeder_mod.subprocess, "run") as run:
        run.return_value.stdout = "INFO: No tasks are running which match the specified criteria."

        assert feeder_mod._pid_is_running(14524) is False

    run.assert_called_once()


def test_cached_last_good_snapshot_preserves_mapping_during_provider_backoff():
    cached = _cached_last_good_snapshot(
        "capital",
        {
            "generated_at": 100.0,
            "source": "capital_rest_snapshot",
            "ticker_cache": {"capital:AAPLUSD": {"exchange": "capital", "price": 100.0}},
            "source_health": {"capital": {"active": True, "fresh": True, "ticker_count": 1, "generated_at": 100.0}},
        },
        "rate_limited",
    )

    assert cached["ticker_cache"]
    assert cached["source_health"]["capital"]["active"] is True
    assert cached["source_health"]["capital"]["fresh"] is False
    assert cached["ticker_cache"]["capital:AAPLUSD"]["timestamp"] == 100.0
    assert cached["source_health"]["capital"]["reason"] == "cached_last_good_due_to:rate_limited"
    assert cached["source_health"]["capital"]["data_age_sec"] >= 0


def test_market_snapshot_store_hydrates_existing_merged_cache_before_fast_source_write(tmp_path):
    out_path = tmp_path / "ws_cache" / "ws_prices.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(
            _merge_market_snapshots(
                {
                    "binance": {
                        "generated_at": 100.0,
                        "source": "binance_rest",
                        "prices": {"BTC": 100.0},
                        "ticker_cache": {"binance:BTCUSDT": {"exchange": "binance", "base": "BTC", "price": 100.0}},
                        "source_health": {"binance": {"active": True, "fresh": True, "ticker_count": 1, "generated_at": 100.0}},
                    },
                    "kraken": {
                        "generated_at": 101.0,
                        "source": "kraken_rest",
                        "prices": {"ETH": 10.0},
                        "ticker_cache": {"kraken:ETHUSD": {"exchange": "kraken", "base": "ETH", "price": 10.0}},
                        "source_health": {"kraken": {"active": True, "fresh": True, "ticker_count": 1, "generated_at": 101.0}},
                    },
                }
            )
        ),
        encoding="utf-8",
    )
    store = MarketSnapshotStore(out_path)

    merged = asyncio.run(
        store.update(
            "binance",
            {
                "generated_at": 102.0,
                "source": "binance_rest",
                "prices": {"BTC": 101.0},
                "ticker_cache": {"binance:BTCUSDT": {"exchange": "binance", "base": "BTC", "price": 101.0}},
                "source_health": {"binance": {"active": True, "fresh": True, "ticker_count": 1, "generated_at": 102.0}},
            },
        )
    )

    assert set(merged["source_health"]) == {"binance", "kraken"}
    assert "kraken:ETHUSD" in merged["ticker_cache"]
    assert _snapshots_from_merged_cache(merged)["kraken"]["ticker_cache"]


def test_binance_rest_writer_preserves_existing_slower_source_snapshots(tmp_path, monkeypatch):
    out_path = tmp_path / "ws_cache" / "ws_prices.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(
            _merge_market_snapshots(
                {
                    "binance": {
                        "generated_at": 100.0,
                        "source": "binance_rest",
                        "prices": {"BTC": 100.0},
                        "ticker_cache": {"binance:BTCUSDT": {"exchange": "binance", "base": "BTC", "price": 100.0}},
                        "source_health": {"binance": {"active": True, "fresh": True, "ticker_count": 1, "generated_at": 100.0}},
                    },
                    "capital": {
                        "generated_at": 101.0,
                        "source": "capital_rest",
                        "prices": {"AAPL": 10.0},
                        "ticker_cache": {"capital:AAPLUSD": {"exchange": "capital", "base": "AAPL", "price": 10.0}},
                        "source_health": {"capital": {"active": True, "fresh": True, "ticker_count": 1, "generated_at": 101.0}},
                    },
                }
            )
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        feeder_mod,
        "_fetch_binance_all_tickers_rest",
        lambda: [{"symbol": "BTCUSDT", "lastPrice": "101.0", "priceChangePercent": "1", "quoteVolume": "1000"}],
    )
    store = MarketSnapshotStore(out_path)

    asyncio.run(
        feeder_mod._write_binance_rest_snapshot(
            out_path=out_path,
            binance_uk_mode=False,
            source="binance_rest_gap_fill",
            store=store,
        )
    )
    written = json.loads(out_path.read_text(encoding="utf-8"))

    assert set(written["source_health"]) == {"binance", "capital"}
    assert "capital:AAPLUSD" in written["ticker_cache"]


def test_binance_timestamp_uses_provider_event_not_parse_time(monkeypatch):
    monkeypatch.setattr(feeder_mod.time, "time", lambda: 1_800_000_100.0)
    payload = feeder_mod._build_binance_snapshot(
        [{"s": "BTCUSDT", "c": "50000", "P": "1", "b": "49999", "a": "50001", "E": 1_800_000_000_000}],
        binance_uk_mode=False, source="binance_ws", mode="websocket_all_market_ticker_stream",
    )
    ticker = payload["ticker_cache"]["BTCUSDT"]
    assert ticker["timestamp"] == 1_800_000_000.0
    assert ticker["provider_timestamp"] == ticker["timestamp"]
    assert ticker["received_at"] == 1_800_000_100.0
    assert ticker["timestamp_kind"] == "provider_event"
    assert ticker["bid"] == 49999
    assert ticker["ask"] == 50001
    assert payload["source_health"]["binance"]["fresh"] is False


def test_binance_rest_preserves_window_close_and_missing_timestamp_fails_freshness(monkeypatch):
    monkeypatch.setattr(feeder_mod.time, "time", lambda: 1_800_000_001.0)
    for close_time, expected_fresh in [(1_800_000_000_000, True), (None, False)]:
        payload = feeder_mod._build_binance_snapshot(
            [{"symbol": "BTCUSDT", "lastPrice": "50000", "priceChangePercent": "1", "closeTime": close_time}],
            binance_uk_mode=False, source="binance_rest_preflight", mode="rest_snapshot_for_stream_continuity",
        )
        ticker = payload["ticker_cache"]["BTCUSDT"]
        assert ticker["timestamp"] == (1_800_000_000.0 if close_time else 0.0)
        assert payload["source_health"]["binance"]["fresh"] is expected_fresh


def test_merge_new_source_does_not_rejuvenate_old_source(monkeypatch):
    monkeypatch.setattr(feeder_mod.time, "time", lambda: 1_800_000_100.0)
    merged = _merge_market_snapshots({"kraken": {
        "generated_at": 1_800_000_000.0,
        "source_health": {"kraken": {"active": True, "fresh": True, "generated_at": 1_800_000_000.0}},
    }})
    assert merged["generated_at"] == 1_800_000_100.0
    assert merged["source_health"]["kraken"]["fresh"] is False
    assert merged["source_health"]["kraken"]["data_age_sec"] == 100.0


def test_generic_snapshot_preserves_provider_timestamp_and_labels_receipt_only(monkeypatch):
    monkeypatch.setattr(feeder_mod.time, "time", lambda: 1_800_000_100.0)
    _, cache = _build_generic_ticker_cache(
        [{"symbol": "AAPL", "price": 200, "provider_timestamp": 1_800_000_000.0},
         {"symbol": "MSFT", "price": 400}],
        exchange="alpaca", source="alpaca_rest_snapshot",
    )
    assert cache["AAPLUSD"]["timestamp"] == 1_800_000_000.0
    assert cache["AAPLUSD"]["timestamp_kind"] == "provider_event"
    assert cache["MSFTUSD"]["provider_timestamp"] is None
    assert cache["MSFTUSD"]["timestamp_kind"] == "received_at"
    assert cache["MSFTUSD"]["bid"] == cache["MSFTUSD"]["ask"] == 0


def test_binance_supported_mini_ticker_derives_change_from_provider_open():
    _, cache = _extract_prices_and_tickers(
        [{"e": "24hrMiniTicker", "E": 1_800_000_000_000, "s": "BTCUSDT", "c": "55000", "o": "50000", "v": "3", "q": "160000"}],
        binance_uk_mode=False,
    )
    assert cache["BTCUSDT"]["change24h"] == 10.0
    assert cache["BTCUSDT"]["volume"] == 160000.0
    assert cache["BTCUSDT"]["timestamp"] == 1_800_000_000.0
    assert cache["BTCUSDT"]["bid"] == cache["BTCUSDT"]["ask"] == 0
