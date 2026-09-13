"""Offline regression fixtures are labeled arithmetic examples, never market observations."""
from __future__ import annotations

import json
import math
import socketserver
import sys
import threading
import time
from dataclasses import replace
from datetime import UTC, datetime, timezone
from pathlib import Path

import pytest
from flask import Flask, g

from aureon.operator.historical_backtest import (
    CAPABILITY_PATH,
    REPLAY_PATH,
    BacktestError,
    Candle,
    Dataset,
    _run_source_worker,
    account_scope,
    fetch_kraken_dataset,
    historical_source_worker_ready,
    parse_kraken_dataset,
    register_historical_backtest_routes,
    run_replay,
    validate_config,
)

NOW = datetime(2026, 9, 11, tzinfo=UTC).timestamp()
START = int(datetime(2026, 9, 1, tzinfo=UTC).timestamp())


def configuration(**changes):
    return {"symbol": "BTCUSD", "startDate": "2026-09-01", "endDate": "2026-09-02", "initialCapital": 10000,
            "tradeSize": 1, "stopLoss": 50, "takeProfit": 100, "strategy": "momentum_next_open_v1",
            "intervalMinutes": 1440, "lookbackPeriods": 2, "feeBps": 0, "slippageBps": 0, **changes}


def arithmetic_dataset(closes=(90, 95, 100, 110, 121)):
    """Five invented arithmetic fixture bars, explicitly confined to offline tests."""
    bars = []
    for index, close in enumerate(closes):
        opening = closes[index - 1] if index else close
        bars.append(Candle(START + (index - 3) * 86400, opening, max(opening, close) * 1.001,
                           min(opening, close) * 0.999, close, 10))
    return Dataset("BTCUSD", 1440, tuple(bars), "https://example.invalid/offline-arithmetic-fixture", NOW - 3600, "0" * 64)


def provider_response(dataset=None):
    data = dataset or arithmetic_dataset()
    rows = [[c.ts, str(c.open), str(c.high), str(c.low), str(c.close), str(c.close), str(c.volume), 2] for c in data.candles]
    last = data.candles[-1]
    rows.append([last.ts + 86400, str(last.close), str(last.close), str(last.close), str(last.close), str(last.close), "1", 1])
    return {"error": [], "result": {"XXBTZUSD": rows, "last": rows[-1][0]}}


def parse(payload):
    return parse_kraken_dataset(json.dumps(payload).encode(), symbol="BTCUSD", interval_minutes=1440,
                                fetched_at=NOW, source_url="https://api.kraken.com/0/public/OHLC?pair=XBTUSD&interval=1440")


def test_configuration_is_bounded_and_unsupported_hnc_fields_never_silently_apply():
    assert validate_config(configuration(), now=NOW) == configuration()
    for updates in ({"initialCapital": True}, {"feeBps": float("nan")}, {"slippageBps": -1}, {"intervalMinutes": 5},
                    {"lookbackPeriods": 2.5}, {"endDate": "2026-09-11"}, {"symbol": "../../secret"},
                    {"strategy": "live_hnc"}, {"coherenceThreshold": 0.9}, {"endDate": "2026-02-31"}):
        with pytest.raises(BacktestError):
            validate_config(configuration(**updates), now=NOW)
    with pytest.raises(BacktestError, match="window"):
        validate_config(configuration(startDate="2026-01-01", endDate="2026-09-01", intervalMinutes=60), now=NOW)


def test_provider_parser_validates_pair_prices_time_and_drops_uncommitted_last_bar():
    data = parse(provider_response())
    assert len(data.candles) == 5
    assert data.candles[-1].ts == START + 86400
    assert len(data.sha256) == 64
    malformed = provider_response()
    malformed["result"]["ETHUSD"] = malformed["result"].pop("XXBTZUSD")
    with pytest.raises(BacktestError, match="pair identity"):
        parse(malformed)
    for mutate in (
        lambda rows: rows[1].__setitem__(0, rows[0][0]),
        lambda rows: rows[1].__setitem__(0, rows[1][0] + 1),
        lambda rows: rows[1].__setitem__(2, "1"),
        lambda rows: rows[1].__setitem__(6, "-1"),
        lambda rows: rows[1].__setitem__(4, "NaN"),
        lambda rows: rows[-1].__setitem__(0, NOW + 86400),
    ):
        broken = provider_response()
        mutate(broken["result"]["XXBTZUSD"])
        with pytest.raises(BacktestError):
            parse(broken)


def test_missing_history_and_gaps_are_refused_instead_of_interpolated():
    data = arithmetic_dataset()
    for bars in (data.candles[1:], data.candles[:-1], data.candles[:2] + data.candles[3:]):
        with pytest.raises(BacktestError, match="completely covered"):
            run_replay(replace(data, candles=bars), configuration(), now=NOW)
    with pytest.raises(BacktestError, match="identity"):
        run_replay(replace(data, symbol="ETHUSD"), configuration(), now=NOW)


def test_known_cash_accounting_and_allocation_match_hand_calculation():
    report = run_replay(arithmetic_dataset(), configuration(tradeSize=0.5), now=NOW)
    results = report["results"]
    assert results["totalTrades"] == 1
    trade = results["trades"][0]
    assert trade["entryPrice"] == 100
    assert trade["exitPrice"] == 121
    assert trade["quantity"] == 50
    assert trade["pnl"] == 1050
    assert results["equityCurve"][-1]["equity"] == 11050
    assert results["totalReturn"] == pytest.approx(10.5)
    assert results["winRate"] == 100
    assert results["profitFactor"] is None  # no loss denominator
    assert report["config"] == configuration(tradeSize=0.5)
    assert report["provenance"]["provider_fills"] is False


def test_fee_and_slippage_costs_conserve_cash_and_both_fee_legs_are_charged():
    result = run_replay(arithmetic_dataset(), configuration(feeBps=10, slippageBps=20), now=NOW)["results"]
    quantity = 10000 / (100 * 1.002 * 1.001)
    final = quantity * (121 * 0.998) * 0.999
    assert result["equityCurve"][-1]["equity"] == pytest.approx(final)
    trade = result["trades"][0]
    assert trade["entryFee"] > 0 and trade["exitFee"] > 0
    assert sum(t["pnl"] for t in result["trades"]) == pytest.approx(final - 10000)


def test_no_lookahead_current_close_cannot_create_an_entry_at_its_own_open():
    data = arithmetic_dataset((100, 100, 100, 110, 121))
    trades = run_replay(data, configuration(), now=NOW)["results"]["trades"]
    assert len(trades) == 1
    assert trades[0]["openedAt"] == "2026-09-02T00:00:00Z"
    assert trades[0]["entryPrice"] == 110


def test_no_lookahead_current_period_volume_cannot_change_its_opening_entry():
    data = arithmetic_dataset()
    baseline = run_replay(data, configuration(), now=NOW)["results"]["trades"][0]
    for future_volume in (0, 1, 1_000_000):
        bars = list(data.candles)
        bars[3] = replace(bars[3], volume=future_volume)
        first = run_replay(replace(data, candles=tuple(bars)), configuration(), now=NOW)["results"]["trades"][0]
        assert (first["openedAt"], first["entryPrice"], first["quantity"]) == (
            baseline["openedAt"], baseline["entryPrice"], baseline["quantity"])
    bars = list(data.candles)
    bars[2] = replace(bars[2], volume=0)
    trades = run_replay(replace(data, candles=tuple(bars)), configuration(), now=NOW)["results"]["trades"]
    assert trades[0]["openedAt"] == "2026-09-02T00:00:00Z"  # prior-period eligibility is known at that open


@pytest.mark.parametrize("framing", ["headers", "chunk_size", "chunk_trailer"])
def test_actual_slow_http_framing_is_killed_by_the_process_deadline(framing):
    """Local test server deliberately defeats idle timeouts; no market fixture is published."""
    received = threading.Event()
    stop = threading.Event()

    class Handler(socketserver.StreamRequestHandler):
        def handle(self):
            self.connection.settimeout(3)
            try:
                self.rfile.readline()
                while self.rfile.readline() not in (b"\r\n", b"\n", b""):
                    pass
                received.set()
                if framing == "headers":
                    prefix = b"HTTP/1.1 200 OK\r\nX-Slow: "
                elif framing == "chunk_size":
                    prefix = b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n1;extension="
                else:
                    prefix = b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n1\r\nx\r\n0\r\nX-Trailer: "
                self.wfile.write(prefix)
                self.wfile.flush()
                for _ in range(150):
                    if stop.wait(0.05):
                        return
                    self.wfile.write(b"a")
                    self.wfile.flush()
            except OSError:
                pass  # parent killed the intentionally stalled test connection

    class Server(socketserver.ThreadingTCPServer):
        daemon_threads = True
        block_on_close = False

    worker = Path(__file__).resolve().parents[1] / "aureon" / "operator" / "historical_source_worker.py"
    with Server(("127.0.0.1", 0), Handler) as server:
        thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True)
        thread.start()
        # Explicit offline seam: production argv never accepts or constructs this loopback URL.
        url = f"http://127.0.0.1:{server.server_address[1]}/offline-framing-fixture"
        code = ("import importlib.util,sys;"
                f"spec=importlib.util.spec_from_file_location('isolated_source',{str(worker)!r});"
                "m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);"
                "assert not any(n=='aureon' or n.startswith('aureon.') for n in sys.modules);"
                f"sys.stdout.buffer.write(m._read_source({url!r}))")
        started = time.monotonic()
        try:
            with pytest.raises(BacktestError) as error:
                _run_source_worker([sys.executable, "-I", "-S", "-B", "-c", code], timeout_seconds=2)
            elapsed = time.monotonic() - started
            assert received.is_set(), "the fixture must actually reach the slow framing phase"
            assert error.value.code == "source_timeout"  # also proves kill/reap did not fail
            assert elapsed < 4.5, "two-second request budget plus bounded process cleanup"
        finally:
            stop.set()
            server.shutdown()
            thread.join(timeout=1)
            assert not thread.is_alive()


def test_source_worker_has_no_inherited_provider_secrets(monkeypatch):
    monkeypatch.setenv("TEST_PROVIDER_SECRET", "offline-test-value")
    raw = _run_source_worker([sys.executable, "-I", "-S", "-B", "-c", "import os,json;print(json.dumps(sorted(os.environ)))"])
    assert "TEST_PROVIDER_SECRET" not in json.loads(raw)


def test_packaged_source_worker_has_concrete_local_readiness():
    assert historical_source_worker_ready() is True


def test_source_worker_rejects_oversized_output():
    with pytest.raises(BacktestError) as error:
        _run_source_worker([sys.executable, "-I", "-S", "-B", "-c", "import sys;sys.stdout.buffer.write(b'x'*(512*1024+1))"])
    assert error.value.code == "source_too_large"


def test_both_intrabar_bounds_use_stop_first_and_stop_gaps_use_open():
    data = arithmetic_dataset()
    bars = list(data.candles)
    bars[3] = replace(bars[3], high=150, low=50)
    result = run_replay(replace(data, candles=tuple(bars)), configuration(stopLoss=10, takeProfit=10), now=NOW)
    assert result["results"]["trades"][0]["exitPrice"] == 90
    assert result["results"]["trades"][0]["closeReason"] == "stop_loss_ohlc_assumption"
    bars = list(data.candles)
    bars[-1] = replace(bars[-1], open=80, low=79, high=122)
    result = run_replay(replace(data, candles=tuple(bars)), configuration(stopLoss=10), now=NOW)
    assert result["results"]["trades"][0]["exitPrice"] == 80
    assert result["results"]["trades"][0]["closeReason"] == "stop_gap"


def test_no_trades_has_real_zero_return_and_undefined_ratios():
    result = run_replay(arithmetic_dataset((100, 100, 100, 100, 100)), configuration(), now=NOW)["results"]
    assert result["totalTrades"] == 0 and result["trades"] == []
    assert result["totalReturn"] == 0 and result["maxDrawdown"] == 0
    for key in ("winRate", "sharpeRatio", "profitFactor", "avgWin", "avgLoss"):
        assert result[key] is None
    assert all(math.isfinite(point["equity"]) for point in result["equityCurve"])


def test_original_source_time_is_not_replaced_with_request_time_and_replay_is_deterministic():
    first = run_replay(arithmetic_dataset(), configuration(), now=NOW)
    second = run_replay(arithmetic_dataset(), configuration(), now=NOW + 3600)
    assert first == second
    assert first["provenance"]["source_at"] == "2026-09-03T00:00:00Z"
    assert first["provenance"]["fetched_at"] != first["provenance"]["source_at"]


def test_network_hold_is_respected_before_any_public_request(monkeypatch):
    monkeypatch.setenv("AUREON_NO_EXTERNAL_API_CALLS", "1")
    with pytest.raises(BacktestError, match="held"):
        fetch_kraken_dataset(configuration())


def app_client(kind="admin", tenant=None, admitted=False):
    """Test-only Flask admission stub; not evidence of production HNC release."""
    app = Flask(__name__)
    calls = []

    @app.before_request
    def test_identity():
        g.identity_kind, g.tenant = kind, tenant

    def reader(config):
        calls.append(dict(config))
        return arithmetic_dataset()

    register_historical_backtest_routes(app, dispatch_available=lambda: admitted, source_reader=reader)
    return app.test_client(), calls


def request_body(kind="admin", tenant=None):
    return {"config": configuration(), "request_id": "offline-test-request-001", "account_scope": account_scope(kind, tenant)}


def test_default_dispatch_is_held_and_open_mode_never_becomes_authenticated(monkeypatch):
    monkeypatch.delenv("AUREON_NO_EXTERNAL_API_CALLS", raising=False)
    client, calls = app_client()
    capability = client.get(CAPABILITY_PATH).get_json()
    assert capability["available"] is False and capability["ingress_status"] == "held"
    assert capability["source_observed"] is False
    assert client.post(REPLAY_PATH, json=request_body()).status_code == 503
    client, calls = app_client(kind="open", admitted=True)
    assert client.get(CAPABILITY_PATH).get_json()["available"] is False
    assert client.post(REPLAY_PATH, json=request_body()).status_code == 401
    assert calls == []


def test_route_binds_account_request_and_exact_config_without_cross_account_fallback(monkeypatch):
    monkeypatch.delenv("AUREON_NO_EXTERNAL_API_CALLS", raising=False)
    client, calls = app_client(kind="tenant", tenant="tenant-a", admitted=True)
    wrong = request_body("tenant", "tenant-b")
    assert client.post(REPLAY_PATH, json=wrong).status_code == 409
    assert calls == []
    body = request_body("tenant", "tenant-a")
    response = client.post(REPLAY_PATH, json=body)
    assert response.status_code == 200
    report = response.get_json()
    assert report["account_scope"] == body["account_scope"]
    assert report["request_id"] == body["request_id"]
    assert report["config"] == body["config"]
    assert report["execution"] == {"orders_submitted": 0, "credentials_used": False, "state_written": False}
    assert len(calls) == 1


def test_unknown_body_fields_or_unsupported_strategy_fail_before_provider_read():
    client, calls = app_client(admitted=True)
    body = request_body()
    body["source_url"] = "http://127.0.0.1/private"
    assert client.post(REPLAY_PATH, json=body).status_code == 400
    body = request_body()
    body["config"]["strategy"] = "live"
    assert client.post(REPLAY_PATH, json=body).status_code == 400
    assert calls == []
