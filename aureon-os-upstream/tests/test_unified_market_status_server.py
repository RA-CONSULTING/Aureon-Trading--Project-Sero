import base64
import json
import os
import sys
import tempfile
import unittest
from unittest import mock
import time
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
EXCHANGES_DIR = REPO_ROOT / "aureon" / "exchanges"
if str(EXCHANGES_DIR) not in sys.path:
    sys.path.insert(0, str(EXCHANGES_DIR))

import unified_market_status_server as status_server
READ_LIVE_MARKET_CACHE = status_server._read_live_market_cache


class UnifiedMarketStatusServerFlightTestTests(unittest.TestCase):
    def setUp(self):
        self.memory_patch = mock.patch.object(status_server, "_read_live_market_cache", return_value=None)
        self.memory_patch.start()
        self.tmp = tempfile.TemporaryDirectory()
        self.state_root = Path(self.tmp.name)
        self.old_status_path = status_server.STATUS_PATH
        self.old_intent_path = status_server.MARKET_INTENT_PATH
        self.old_env_path = status_server.ENV_PATH
        self.old_env_update_intent_path = status_server.ENV_UPDATE_INTENT_PATH
        self.old_hnc_packet_evidence_path = status_server.HNC_PACKET_EVIDENCE_PATH
        status_server.STATUS_PATH = self.state_root / "unified_runtime_status.json"
        status_server.MARKET_INTENT_PATH = self.state_root / "aureon_market_reboot_intent.json"
        status_server.ENV_PATH = self.state_root / ".env"
        status_server.ENV_UPDATE_INTENT_PATH = self.state_root / "aureon_env_update_intent.json"
        status_server.HNC_PACKET_EVIDENCE_PATH = self.state_root / "aureon_hnc_quantum_packet_last_run.json"
        self.old_secret_env = {
            key: os.environ.get(key)
            for key in (
                "KRAKEN_API_KEY",
                "KRAKEN_API_SECRET",
                "BINANCE_API_KEY",
                "BINANCE_API_SECRET",
                "ALPACA_API_KEY",
                "ALPACA_SECRET_KEY",
                "CAPITAL_API_KEY",
                "CAPITAL_IDENTIFIER",
                "CAPITAL_PASSWORD",
                "AUREON_HNC_PACKET_MASTER_KEY",
                "HNC_PACKET_MASTER_KEY",
            )
        }
        self.old_env = {
            key: os.environ.get(key)
            for key in (
                "AUREON_MARKET_DOWNTIME_DAYS",
                "AUREON_MARKET_DOWNTIME_START_LOCAL",
                "AUREON_MARKET_DOWNTIME_END_LOCAL",
            )
        }
        os.environ["AUREON_MARKET_DOWNTIME_DAYS"] = "*"
        os.environ["AUREON_MARKET_DOWNTIME_START_LOCAL"] = "00:00"
        os.environ["AUREON_MARKET_DOWNTIME_END_LOCAL"] = "23:59"

    def tearDown(self):
        self.memory_patch.stop()
        status_server.STATUS_PATH = self.old_status_path
        status_server.MARKET_INTENT_PATH = self.old_intent_path
        status_server.ENV_PATH = self.old_env_path
        status_server.ENV_UPDATE_INTENT_PATH = self.old_env_update_intent_path
        status_server.HNC_PACKET_EVIDENCE_PATH = self.old_hnc_packet_evidence_path
        for key, value in self.old_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        for key, value in self.old_secret_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        self.tmp.cleanup()

    def _write_status(self, open_positions: int, stale: bool = False):
        payload = {
            "ok": not stale,
            "trading_ready": True,
            "data_ready": True,
            "stale": stale,
            "last_tick_completed_at": datetime.fromtimestamp(time.time() - (90 if stale else 1)).isoformat(),
            "last_tick_age_sec": 90 if stale else 1,
            "combined": {"open_positions": open_positions},
            "exchanges": {"kraken_ready": True, "capital_ready": True},
        }
        status_server.STATUS_PATH.write_text(json.dumps(payload), encoding="utf-8")

    def _write_pending_intent(self):
        payload = {"status": "pending", "surface": "market", "reason": "test"}
        status_server.MARKET_INTENT_PATH.write_text(json.dumps(payload), encoding="utf-8")

    def test_status_recalculates_old_tick_despite_fresh_file_and_stored_age(self):
        self._write_status(open_positions=0)
        payload = json.loads(status_server.STATUS_PATH.read_text(encoding="utf-8"))
        payload["last_tick_completed_at"] = datetime.fromtimestamp(time.time() - 120).isoformat()
        payload["last_tick_started_at"] = datetime.now().isoformat()
        payload["last_tick_age_sec"] = 1
        status_server.STATUS_PATH.write_text(json.dumps(payload), encoding="utf-8")
        observed = status_server._read_status()
        self.assertTrue(observed["stale"])
        self.assertFalse(observed["ok"])
        self.assertGreaterEqual(observed["last_tick_age_sec"], 119)

    def test_active_tick_within_long_running_threshold_is_not_stale(self):
        """A progressing tick may legitimately take longer than the normal
        freshness window.  Do not mark the endpoint stale while the cycle is
        actively running and has not exceeded the long-running stall threshold.
        """
        self._write_status(open_positions=0)
        now = time.time()
        payload = json.loads(status_server.STATUS_PATH.read_text(encoding="utf-8"))
        payload["last_tick_completed_at"] = datetime.fromtimestamp(now - 60).isoformat()
        payload["last_tick_started_at"] = datetime.fromtimestamp(now - 30).isoformat()
        payload["last_tick_age_sec"] = 60
        payload["tick_phase"] = "build_combined_payload:early_gate_status_write"
        status_server.STATUS_PATH.write_text(json.dumps(payload), encoding="utf-8")
        observed = status_server._read_status()
        self.assertFalse(observed["stale"])
        self.assertTrue(observed["ok"])
        self.assertEqual(observed["stale_reason"], "")
        self.assertTrue(observed["runtime_watchdog"]["tick_active"])
        self.assertGreater(observed["runtime_watchdog"]["last_tick_running_sec"], 0)

    def test_market_stream_rejects_old_quotes_even_in_new_cache_file(self):
        original = status_server.STREAM_CACHE_PATH
        status_server.STREAM_CACHE_PATH = self.state_root / "quotes.json"
        try:
            cache = {"generated_at": time.time(), "ticker_cache": {
                "old": {"price": 100, "timestamp": time.time() - 90},
                "missing": {"price": 100},
                "future": {"price": 100, "timestamp": time.time() + 90},
                "current": {"symbol": "BTCUSDT", "base": "BTC", "quote": "USDT", "price": 100,
                            "timestamp": time.time() - 1, "timestamp_kind": "provider_event", "source": "binance_ws"},
            }}
            status_server.STREAM_CACHE_PATH.write_text(json.dumps(cache), encoding="utf-8")
            observed = status_server._read_market_stream()
            self.assertTrue(observed["fresh"])
            self.assertEqual(observed["symbol_count"], 1)
            self.assertEqual(observed["quotes"][0]["symbol"], "BTCUSDT")
            self.assertEqual(observed["quotes"][0]["timestamp_kind"], "provider_event")
        finally:
            status_server.STREAM_CACHE_PATH = original

    def test_status_serializes_local_clock_as_same_explicit_utc_instant(self):
        self._write_status(open_positions=0)
        original = json.loads(status_server.STATUS_PATH.read_text(encoding="utf-8"))["last_tick_completed_at"]
        observed = status_server._read_status()["last_tick_completed_at"]
        self.assertTrue(observed.endswith("+00:00"))
        self.assertAlmostEqual(datetime.fromisoformat(original).timestamp(), datetime.fromisoformat(observed).timestamp(), places=5)

    def test_stream_read_retries_transient_windows_permission_without_redating(self):
        timestamp = time.time() - 1
        encoded = json.dumps({"ticker_cache": {"btc": {"symbol": "BTCUSDT", "source": "binance_ws", "price": 1, "timestamp": timestamp}}})
        cached = self.state_root / "retry_quotes.json"
        cached.write_text(encoded, encoding="utf-8")
        handle = cached.open("r", encoding="utf-8")
        with mock.patch.object(Path, "open", side_effect=[PermissionError(), handle]), \
                mock.patch.object(status_server.time, "sleep"):
            observed = status_server._read_market_stream()
        self.assertTrue(observed["fresh"])
        self.assertEqual(observed["quotes"][0]["timestamp"], timestamp)

    def test_memory_quotes_are_preferred_without_disk_and_original_rows_expire_at_five_seconds(self):
        now = time.time()
        quotes = {"ticker_cache": {
            "fresh": {"symbol": "BTCUSDT", "price": 1, "timestamp": now - 1, "source": "binance_ws", "timestamp_kind": "provider_event"},
            "old": {"symbol": "ETHUSDT", "price": 1, "timestamp": now - 5.01, "source": "binance_ws"},
        }, "generated_at": now, "producer_pid": 123}
        with mock.patch.object(status_server, "_read_live_market_cache", return_value=quotes), \
                mock.patch.object(status_server, "_load_json_file_snapshot", side_effect=AssertionError("request read a file")), \
                mock.patch.object(status_server.time, "time", return_value=now):
            observed = status_server._read_market_stream()
        self.assertEqual(observed["transport"], "loopback_memory")
        self.assertTrue(observed["fresh"])
        self.assertEqual(observed["symbol_count"], 1)
        self.assertEqual(observed["quotes"][0]["timestamp"], now - 1)
        self.assertEqual(observed["quotes"][0]["timestamp_kind"], "provider_event")

    def test_loopback_snapshot_has_fixed_target_timeout_and_bounded_body(self):
        raw = json.dumps({"ticker_cache": {}}).encode()
        with mock.patch.object(status_server, "HTTPConnection") as connection:
            response = connection.return_value.getresponse.return_value
            response.status = 200
            response.getheader.return_value = str(len(raw))
            response.read.return_value = raw
            self.assertEqual(READ_LIVE_MARKET_CACHE(), {"ticker_cache": {}})
            connection.assert_called_once_with("127.0.0.1", 8794, timeout=0.25)
            connection.return_value.request.assert_called_once_with("GET", "/api/quotes", headers={"Accept": "application/json"})
            response.read.assert_called_once_with(len(raw))
            connection.return_value.close.assert_called_once()

    def test_loopback_snapshot_rejects_redirect_oversize_and_timeout_without_reading_body(self):
        for mode in ("redirect", "oversize", "timeout"):
            with self.subTest(mode=mode), mock.patch.object(status_server, "HTTPConnection") as connection:
                response = connection.return_value.getresponse.return_value
                response.status = 302 if mode == "redirect" else 200
                response.getheader.return_value = str(status_server.STREAM_MEMORY_MAX_BYTES + 1)
                if mode == "timeout":
                    connection.return_value.getresponse.side_effect = TimeoutError("test-only timeout")
                self.assertIsNone(READ_LIVE_MARKET_CACHE())
                response.read.assert_not_called()
                connection.return_value.close.assert_called_once()

    def test_live_request_uses_background_files_only_and_recalculates_original_tick_and_quote_ages(self):
        now = time.time()
        self._write_status(open_positions=0)
        payload = json.loads(status_server.STATUS_PATH.read_text(encoding="utf-8"))
        payload["last_tick_completed_at"] = datetime.fromtimestamp(now).isoformat()
        payload["provider_observations"] = {"binance": {"accounts": {"source_timestamp": now - 10, "received_at": now - 9}}}
        status_server.STATUS_PATH.write_text(json.dumps(payload), encoding="utf-8")
        runtime_cache = status_server._BackgroundFileSnapshot(status_server.STATUS_PATH)
        runtime_cache.refresh()
        quotes_path = self.state_root / "background_quotes.json"
        quotes_path.write_text(json.dumps({"ticker_cache": {"btc": {"symbol": "BTCUSDT", "source": "binance_ws", "price": 1, "timestamp": now}}}), encoding="utf-8")
        stream_cache = status_server._BackgroundFileSnapshot(quotes_path)
        stream_cache.refresh()
        original_snapshot = json.loads(json.dumps(runtime_cache.snapshot()))
        with mock.patch.object(status_server, "_runtime_file_cache", runtime_cache), \
                mock.patch.object(status_server, "_stream_file_cache", stream_cache), \
                mock.patch.object(Path, "exists", side_effect=AssertionError("request exists")), \
                mock.patch.object(Path, "open", side_effect=AssertionError("request open")), \
                mock.patch.object(Path, "stat", side_effect=AssertionError("request stat")), \
                mock.patch.object(status_server.time, "time", return_value=now + 2):
            first = status_server._read_status()
            self.assertFalse(first["stale"])
            self.assertTrue(first["live_stream_cache"]["fresh"])
            self.assertEqual(first["live_stream_cache"]["transport"], "file_snapshot")
            with mock.patch.object(status_server.time, "time", return_value=now + 46):
                expired = status_server._read_status()
                self.assertTrue(expired["stale"])
                self.assertFalse(expired["live_stream_cache"]["fresh"])
                with mock.patch.object(status_server, "_read_live_market_cache", return_value={"ticker_cache": {"btc": {"symbol": "BTCUSDT", "source": "binance_ws", "price": 1, "timestamp": now + 45}}}):
                    independent = status_server._read_status()
                    self.assertTrue(independent["stale"])
                    self.assertTrue(independent["live_stream_cache"]["fresh"])
        self.assertEqual(runtime_cache.snapshot(), original_snapshot)
        self.assertEqual(expired["provider_observations"], payload["provider_observations"])
        self.assertEqual(first["status_file_mtime"], expired["status_file_mtime"])
        self.assertEqual(first["last_tick_completed_at"], expired["last_tick_completed_at"])

    def test_background_read_failure_or_missing_file_drops_previous_payload(self):
        for state in ("failed", "missing"):
            with self.subTest(state=state):
                self._write_status(open_positions=0)
                cache = status_server._BackgroundFileSnapshot(status_server.STATUS_PATH)
                cache.refresh()
                with mock.patch.object(status_server, "_load_json_file_snapshot", return_value={"payload": None, "mtime": None, "read_at": time.time(), "state": state, "error": "PermissionError"}):
                    cache.refresh()
                with mock.patch.object(status_server, "_runtime_file_cache", cache):
                    observed = status_server._read_runtime_status()
                self.assertTrue(observed["stale"])
                self.assertFalse(observed.get("trading_ready", False))
                self.assertEqual(observed["status_file_read_state"], state)
                self.assertIsNone(cache._thread)

    def test_flight_test_holds_restart_when_open_positions_exist(self):
        self._write_status(open_positions=2)
        self._write_pending_intent()

        flight = status_server._flight_test()

        self.assertTrue(flight["checks"]["pending_restart"])
        self.assertTrue(flight["checks"]["open_positions"])
        self.assertFalse(flight["reboot_advice"]["can_reboot_now"])
        self.assertEqual(flight["reboot_advice"]["reason"], "open_positions_reported")

    def test_flight_test_reports_stale_tick_with_open_positions_as_position_monitor_hold(self):
        self._write_status(open_positions=2, stale=True)

        flight = status_server._flight_test()

        self.assertFalse(flight["checks"]["tick_fresh"])
        self.assertTrue(flight["checks"]["heartbeat_fresh_but_tick_stale"])
        self.assertFalse(flight["reboot_advice"]["can_reboot_now"])
        self.assertEqual(flight["reboot_advice"]["decision"], "hold_monitor_positions")
        self.assertEqual(flight["reboot_advice"]["reason"], "runtime_tick_stale_with_open_positions")
        self.assertEqual(
            flight["reboot_advice"]["recovery_action"],
            "preserve_position_monitoring_and_defer_restart_until_flat_downtime",
        )

    def test_flight_test_allows_pending_restart_when_flat_in_window(self):
        self._write_status(open_positions=0)
        self._write_pending_intent()

        flight = status_server._flight_test()

        self.assertTrue(flight["checks"]["downtime_window"])
        self.assertFalse(flight["checks"]["open_positions"])
        self.assertTrue(flight["reboot_advice"]["can_reboot_now"])

    def test_env_credentials_status_reports_presence_without_secret_values(self):
        status_server.ENV_PATH.write_text(
            "KRAKEN_API_KEY=kraken-key\nKRAKEN_API_SECRET=kraken-secret-value\n",
            encoding="utf-8",
        )

        status = status_server._env_credentials_status()

        self.assertTrue(status["exchanges"]["kraken"]["present"])
        self.assertEqual(status["exchanges"]["kraken"]["keys"]["KRAKEN_API_SECRET"]["length"], len("kraken-secret-value"))
        self.assertNotIn("kraken-secret-value", json.dumps(status))
        self.assertEqual(status["secret_policy"], "metadata_only_no_values_returned")

    def test_env_credential_writer_holds_before_plaintext_or_intent_write(self):
        os.environ.pop("AUREON_HNC_PACKET_MASTER_KEY", None)
        os.environ.pop("HNC_PACKET_MASTER_KEY", None)
        updates = status_server._extract_env_updates(
            "kraken",
            {"krakenApiKey": "new-kraken-key", "krakenApiSecret": "new-kraken-secret"},
        )

        with self.assertRaisesRegex(
            status_server.HNCPacketError,
            status_server.CREDENTIAL_UPDATE_FILESYSTEM_HOLD,
        ):
            status_server._write_env_updates(updates)

        self.assertFalse(status_server.ENV_PATH.exists())
        self.assertFalse(status_server.ENV_UPDATE_INTENT_PATH.exists())
        self.assertFalse(status_server.MARKET_INTENT_PATH.exists())
        self.assertFalse(status_server.HNC_PACKET_EVIDENCE_PATH.exists())

    def test_public_credential_status_holds_before_reading_sources(self):
        captured = {}

        class FakeHandler:
            path = "/api/env-credentials"

            def _json(self, status, payload):
                captured.update({"status": status, "payload": payload})

        original = status_server._env_credentials_status
        status_server._env_credentials_status = lambda: self.fail(
            "public credential status inspected a credential source"
        )
        try:
            status_server.StatusHandler.do_GET(FakeHandler())
        finally:
            status_server._env_credentials_status = original

        self.assertEqual(captured["status"], 403)
        self.assertEqual(
            captured["payload"],
            {"ok": False, "error": status_server.CREDENTIAL_STATUS_READ_HOLD},
        )

    def test_cors_never_grants_nonlocal_or_prefix_confusion_origin(self):
        class FakeHandler:
            def __init__(self, origin):
                self.headers = {"Origin": origin}
                self.emitted = []

            def send_header(self, key, value):
                self.emitted.append((key, value))

        for origin in (
            "https://attacker.invalid",
            "http://localhost.attacker.invalid",
            "http://127.0.0.1.attacker.invalid",
        ):
            handler = FakeHandler(origin)
            status_server.StatusHandler._cors(handler)

            self.assertNotIn(
                "Access-Control-Allow-Origin",
                {key for key, _ in handler.emitted},
            )

    def test_env_credential_writer_holds_before_encrypted_or_evidence_write(self):
        os.environ["AUREON_HNC_PACKET_MASTER_KEY"] = (
            base64.urlsafe_b64encode(b"U" * 32).decode("ascii").rstrip("=")
        )
        updates = status_server._extract_env_updates(
            "kraken",
            {"krakenApiKey": "packet-kraken-key", "krakenApiSecret": "packet-kraken-secret"},
        )

        with self.assertRaisesRegex(
            status_server.HNCPacketError,
            status_server.CREDENTIAL_UPDATE_FILESYSTEM_HOLD,
        ):
            status_server._write_env_updates(updates)

        self.assertFalse(status_server.ENV_PATH.exists())
        self.assertFalse(status_server.HNC_PACKET_EVIDENCE_PATH.exists())

    def test_packetize_env_updates_is_pure_and_metadata_only(self):
        os.environ["AUREON_HNC_PACKET_MASTER_KEY"] = (
            base64.urlsafe_b64encode(b"U" * 32).decode("ascii").rstrip("=")
        )
        updates = {
            "KRAKEN_API_KEY": "packet-kraken-key",
            "KRAKEN_API_SECRET": "packet-kraken-secret",
        }

        stored, encrypted_keys, evidence = status_server._packetize_env_updates(updates)
        rendered = json.dumps(evidence, sort_keys=True)

        self.assertEqual(encrypted_keys, ["KRAKEN_API_KEY", "KRAKEN_API_SECRET"])
        self.assertTrue(all(status_server.is_env_packet(token) for token in stored.values()))
        self.assertNotIn("packet-kraken-key", json.dumps(stored))
        self.assertNotIn("packet-kraken-secret", json.dumps(stored))
        self.assertNotIn("packet-kraken-key", rendered)
        self.assertNotIn("packet-kraken-secret", rendered)
        self.assertTrue(all(token not in rendered for token in stored.values()))
        self.assertFalse(status_server.ENV_PATH.exists())
        self.assertFalse(status_server.HNC_PACKET_EVIDENCE_PATH.exists())
        encryption = status_server._env_credentials_status()["hnc_packet_encryption"]
        self.assertFalse(encryption["enabled"])
        self.assertTrue(encryption["packetization_available"])
        self.assertFalse(encryption["filesystem_write_released"])
        self.assertEqual(
            encryption["release_hold"],
            status_server.CREDENTIAL_UPDATE_FILESYSTEM_HOLD,
        )

    def test_packetize_env_updates_requires_valid_hnc_key_without_raw_fallback(self):
        os.environ.pop("AUREON_HNC_PACKET_MASTER_KEY", None)
        os.environ.pop("HNC_PACKET_MASTER_KEY", None)

        with self.assertRaisesRegex(
            status_server.HNCPacketError,
            "credential_update_requires_valid_hnc_master_key",
        ):
            status_server._packetize_env_updates(
                {"KRAKEN_API_SECRET": "must-not-return-raw"}
            )

        self.assertFalse(status_server.ENV_PATH.exists())
        self.assertFalse(status_server.HNC_PACKET_EVIDENCE_PATH.exists())

    def test_env_status_does_not_report_malformed_hnc_key_as_enabled(self):
        os.environ["AUREON_HNC_PACKET_MASTER_KEY"] = "not a canonical base64url key"

        status = status_server._env_credentials_status()
        encryption = status["hnc_packet_encryption"]

        self.assertTrue(encryption["master_key_present"])
        self.assertFalse(encryption["master_key_valid"])
        self.assertFalse(encryption["enabled"])
        self.assertEqual(encryption["configuration_error"], "hnc_master_key_invalid")
        self.assertNotIn(os.environ["AUREON_HNC_PACKET_MASTER_KEY"], json.dumps(status))

    def test_flight_test_treats_env_update_as_pending_restart(self):
        self._write_status(open_positions=0)
        status_server._record_env_update_intent("binance", ["BINANCE_API_KEY"])

        flight = status_server._flight_test()

        self.assertTrue(flight["checks"]["pending_restart"])
        self.assertTrue(flight["reboot_advice"]["can_reboot_now"])
        self.assertEqual(flight["env_update_intent"]["exchange"], "binance")


if __name__ == "__main__":
    unittest.main()
