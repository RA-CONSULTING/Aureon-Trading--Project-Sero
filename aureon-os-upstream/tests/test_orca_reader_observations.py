"""Offline contract tests: never import Orca actors or call a provider."""
import ast
import asyncio
import copy
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("orca_passive_projection", ROOT / "aureon/exchanges/orca_reader_observations.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
NOW = 1788886800.0


def receipt():
    return {"provider": "alpaca", "kind": "positions", "source": "alpaca:GET /v2/positions",
            "source_timestamp": NOW - 2, "received_at": NOW - 1,
            "source_timestamp_kind": "provider_http_date", "max_age_seconds": 300,
            "generated_values": False, "status": "observed", "inventory_complete": True,
            "observed_count": 1, "rows": [{"reference": "a" * 16, "symbol": "EXAMPLE",
                "quantity": 2.5, "entry_price": 12.25, "currency": None, "side": "BUY",
                "source_timestamp": NOW - 2, "received_at": NOW - 1}]}


class NoProviderCalls:
    def __init__(self, value):
        self.last_ui_positions_observation = value

    def get_positions(self):
        raise AssertionError("passive handler must not call a provider")

    def get_open_positions(self):
        raise AssertionError("passive handler must not call a provider")


class OrcaReaderTests(unittest.TestCase):
    def project(self, value, now=NOW):
        return module.build_orca_reader_observations(NoProviderCalls(value), NoProviderCalls(value),
                                                     {"Example": True, "unknown": "yes"}, now=now)

    def test_native_receipt_preserved_without_calls_or_mutating_the_original(self):
        value = receipt()
        value["account_secret"] = "must not project"
        value["rows"][0]["raw"] = {"private": "must not project"}
        original = copy.deepcopy(value)
        result = self.project(value)
        snapshot = result["provider_positions"]["alpaca"]
        self.assertEqual(snapshot["status"], "observed")
        self.assertEqual(snapshot["source_timestamp"], NOW - 2)
        self.assertEqual(snapshot["received_at"], NOW - 1)
        self.assertIsNone(snapshot["rows"][0]["currency"])
        self.assertNotIn("account_secret", snapshot)
        self.assertNotIn("raw", snapshot["rows"][0])
        self.assertNotIn("timestamp", result)
        self.assertNotIn("generated_at", result)
        self.assertEqual(value, original)
        snapshot["rows"][0]["quantity"] = 99
        self.assertEqual(value, original)

    def test_pending_cache_does_not_renew_clock_and_failure_suppresses_rows(self):
        value = receipt()
        value["refresh_status"] = "pending"
        self.assertEqual(self.project(value)["provider_positions"]["alpaca"]["status"], "observed")
        expired = self.project(value, NOW + 299)["provider_positions"]["alpaca"]
        self.assertEqual(expired["status"], "unavailable")
        self.assertEqual(expired["source_timestamp"], NOW - 2)
        self.assertIsNone(expired["observed_count"])
        value.update(status="unavailable", refresh_status="failed")
        self.assertEqual(self.project(value)["provider_positions"]["alpaca"]["rows"], [])

    def test_only_successfully_attested_empty_inventory_can_display_zero(self):
        value = receipt()
        value.update(rows=[], observed_count=0)
        self.assertEqual(self.project(value)["provider_positions"]["alpaca"]["observed_count"], 0)
        value["inventory_complete"] = False
        self.assertIsNone(self.project(value)["provider_positions"]["alpaca"]["observed_count"])
        self.assertIsNone(self.project({})["provider_positions"]["alpaca"]["observed_count"])

    def test_partial_inventory_is_preserved_as_partial_not_a_global_total(self):
        value = receipt()
        value["inventory_complete"] = False
        result = self.project(value)["provider_positions"]["alpaca"]
        self.assertEqual(result["observed_count"], 1)
        self.assertFalse(result["inventory_complete"])

    def test_malformed_generated_future_and_row_clock_mismatch_fail_closed(self):
        mutations = [("generated_values", True), ("source_timestamp", NOW + 6),
                     ("source_timestamp", None), ("source", "registry"), ("observed_count", True),
                     ("source_timestamp_kind", "assembly_time")]
        for key, replacement in mutations:
            value = receipt()
            value[key] = replacement
            with self.subTest(key=key):
                self.assertEqual(self.project(value)["provider_positions"]["alpaca"]["rows"], [])
        for key, replacement in [("quantity", None), ("entry_price", float("nan")),
                                  ("source_timestamp", NOW), ("quantity", "2")]:
            value = receipt()
            value["rows"][0][key] = replacement
            with self.subTest(row_key=key):
                self.assertEqual(self.project(value)["provider_positions"]["alpaca"]["rows"], [])

    def test_import_availability_and_attached_kraken_cannot_create_observations(self):
        result = self.project(receipt())
        self.assertEqual(result["component_imports"], {"Example": True})
        self.assertEqual(result["provider_positions"]["kraken"]["status"], "unavailable")
        self.assertIsNone(result["provider_positions"]["kraken"]["observed_count"])
        self.assertIn("closed_fills", result["unsupported_sources"])
        self.assertIn("realized_performance", result["unsupported_sources"])

    def test_actual_handler_uses_only_saved_sidecars(self):
        source = ROOT.parent / "aureon_radar/bots/orca_command_center.py"
        tree = ast.parse(source.read_text(encoding="utf-8-sig"))
        cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "OrcaCommandCenter")
        handler = next(node for node in cls.body if isinstance(node, ast.AsyncFunctionDef) and node.name == "_handle_api_observations")
        compiled = compile(ast.Module(body=[handler], type_ignores=[]), str(source), "exec")
        namespace = {"web": SimpleNamespace(json_response=lambda data, **kwargs: (data, kwargs)),
                     "build_orca_reader_observations": lambda a, k, c: module.build_orca_reader_observations(a, k, c, now=NOW),
                     "SYSTEMS_STATUS": {"Example": True}}
        exec(compiled, namespace)
        client = NoProviderCalls(receipt())
        data, kwargs = asyncio.run(namespace["_handle_api_observations"](SimpleNamespace(alpaca=client, kraken=client), None))
        self.assertEqual(data["provider_positions"]["alpaca"]["observed_count"], 1)
        self.assertEqual(kwargs["headers"]["Cache-Control"], "no-store")


if __name__ == "__main__":
    unittest.main()
