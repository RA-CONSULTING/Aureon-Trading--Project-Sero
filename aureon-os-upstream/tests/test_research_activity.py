"""Offline reader contract: no Aureon package import, producer or network call."""
import ast
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path
from types import ModuleType
from unittest.mock import patch

STAGE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("passive_research_activity", STAGE / "aureon/saas/research_activity.py")
reader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reader)
NOW = 1_788_890_400.0


def event(stamp=NOW - 10, **extra):
    return {"ts": stamp, "outcome": "absorbed", "dry_run": False,
            "batch": {"absorbed": 0, "contested_stored": 2}, **extra}


def research(stamp=NOW - 20, **extra):
    return {"last_run_at": stamp, "last_result": {"mode": "topic", "outcome": "researched",
            "questions_processed": 0, "items_pulled": 2, **extra}}


class ReaderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.workspace = Path(self.temp.name)
        self.state = self.workspace / "aureon_fusion/state"
        (self.state / "learning_will").mkdir(parents=True)
        reader._cache.clear()

    def journal(self, rows):
        (self.state / "learning_will/journal.jsonl").write_text(
            "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")

    def faculty(self, modes):
        (self.state / "research_throttle.json").write_text(json.dumps({"saved_by": "research_faculty", "modes": modes}), encoding="utf-8")

    def observe(self, now=NOW):
        return reader.research_activity_observation(workspace=self.workspace, now=now)

    def test_redaction_zero_preserved_missing_not_zero_and_original_clock(self):
        private = "DO_NOT_EXPOSE_QUESTION_URL_TOKEN"
        self.journal([event(intent={"question": private}, candidates=[private], receipt=private,
                            gate={"passed": False, "detail": private, "outcome": "deferred"})])
        self.faculty({"topic": research(topic=private, questions=[private], ingester_stats={"errors": 0, "secret": private})})
        data = self.observe()
        self.assertNotIn(private, json.dumps(data))
        row = data["learning_will"]["events"][0]
        self.assertEqual(row["source_timestamp_original"], NOW - 10)
        self.assertEqual(row["source_clock_kind"], "producer_run_start")
        self.assertEqual(row["reported_counts"], {"absorbed": 0, "contested_stored": 2, "dropped": None})
        self.assertEqual(set(row), {"source_timestamp", "source_timestamp_original", "source_clock_kind", "outcome", "dry_run", "gate", "reported_counts", "age_seconds", "max_age_seconds", "recent", "classification"})
        topic = data["research_faculty"]["records"][1]
        self.assertEqual(topic["reported_counts"]["questions_processed"], 0)
        self.assertIsNone(topic["reported_counts"]["fragments_added"])
        self.assertEqual(topic["reported_ingester_counts"], {"items_pulled": None, "vault_ingests": None, "errors": 0})

    def test_missing_and_empty_remain_distinct_unavailable_sources(self):
        data = self.observe()
        self.assertEqual(data["learning_will"]["read_state"], "missing")
        self.assertEqual(data["research_faculty"]["read_state"], "missing")
        reader._cache.clear()
        self.journal([])
        data = self.observe()
        self.assertEqual(data["learning_will"]["read_state"], "empty")
        self.assertEqual(data["learning_will"]["events"], [])

    def test_strict_clocks_counts_and_boolean_types(self):
        for value in (True, False, "1788890390", "2026-09-08T19:19:50", float("nan"), float("inf"), -1, None):
            self.assertIsNone(reader._epoch(value))
        self.assertEqual(reader._epoch("2026-09-08T19:19:50Z"), 1788895190)
        for value in (True, -1, "0", 1.2, float("nan"), 9007199254740992):
            self.assertIsNone(reader._count(value))
        for value in ("false", 0, None):
            self.assertIsNone(reader._learning_event(event(dry_run=value)))

    def test_dry_run_never_recent_and_old_events_are_dated_history(self):
        self.journal([event(NOW - 301), event(dry_run=True)])
        rows = self.observe()["learning_will"]["events"]
        self.assertFalse(rows[0]["recent"])
        self.assertEqual(rows[0]["classification"], "recorded_activity")
        self.assertFalse(rows[1]["recent"])
        self.assertEqual(rows[1]["classification"], "dry_run_record")

    def test_cache_reages_without_restamping_or_rereading(self):
        self.journal([event(NOW - 299)])
        with patch.object(reader.time, "monotonic", return_value=500):
            first = self.observe()
            with patch.object(reader.Path, "open", side_effect=AssertionError("cache reread")):
                later = self.observe(NOW + 2)
        self.assertTrue(first["learning_will"]["events"][0]["recent"])
        self.assertFalse(later["learning_will"]["events"][0]["recent"])
        self.assertEqual(first["learning_will"]["file_read_at"], later["learning_will"]["file_read_at"])
        self.assertEqual(later["learning_will"]["events"][0]["source_timestamp"], NOW - 299)

    def test_expired_cache_refreshes_failure_without_leaking_exception(self):
        self.journal([event()])
        with patch.object(reader.time, "monotonic", return_value=500):
            self.observe()
        with patch.object(reader.time, "monotonic", return_value=503), patch.object(reader.Path, "open", side_effect=PermissionError("PRIVATE_PATH")):
            data = self.observe()
        self.assertEqual(data["learning_will"]["read_state"], "failed")
        self.assertNotIn("PRIVATE_PATH", json.dumps(data))

    def test_future_row_withheld_without_promoting_previous_as_last(self):
        self.journal([event(), event(NOW + 6)])
        rows = self.observe()["learning_will"]["events"]
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[-1], {"read_state": "failed", "reason_code": "source_timestamp_future"})

    def test_invalid_now_is_fail_closed_and_does_not_read(self):
        for now in (True, float("nan"), float("inf"), "2026-09-08T00:00:00Z"):
            with patch.object(reader.Path, "open", side_effect=AssertionError("invalid clock read")):
                data = self.observe(now)
            self.assertEqual(data["learning_will"]["read_state"], "failed")
            json.dumps(data, allow_nan=False)

    def test_malformed_complete_rows_and_partial_append_are_explicit(self):
        raw = b"{bad}\n" + json.dumps(event()).encode() + b"\n" + json.dumps(event()).encode()
        (self.state / "learning_will/journal.jsonl").write_bytes(raw)
        data = self.observe()["learning_will"]
        self.assertEqual(len(data["events"]), 1)
        self.assertEqual(data["coverage"]["invalid_records"], 1)
        self.assertTrue(data["coverage"]["partial_last_record"])

    def test_large_history_tail_is_bounded_and_retains_last_ten(self):
        rows = [event(NOW - i, intent={"question": "x" * 200}) for i in range(1000, 0, -1)]
        payload = "".join(json.dumps(row) + "\n" for row in rows).encode()
        reads = []

        class Meter(io.BytesIO):
            def read(self, size=-1):
                reads.append(size)
                return super().read(size)

        with patch.object(reader.Path, "open", return_value=Meter(payload)):
            data = reader._read_journal(Path("unused"))
        self.assertEqual(reads, [reader.MAX_READ_BYTES])
        self.assertEqual(data["coverage"]["bytes_read"], reader.MAX_READ_BYTES)
        self.assertTrue(data["coverage"]["start_truncated"])
        self.assertEqual([row["source_timestamp"] for row in data["events"]], [NOW - i for i in range(10, 0, -1)])
        self.assertFalse(data["coverage"]["includes_rotated_or_pid_sidecars"])

    def test_research_whole_document_read_is_bounded_and_oversize_rejected(self):
        reads = []

        class Meter(io.BytesIO):
            def read(self, size=-1):
                reads.append(size)
                return super().read(size)

        with patch.object(reader.Path, "open", return_value=Meter(b"x" * (reader.MAX_READ_BYTES + 1000))):
            with self.assertRaises(ValueError):
                reader._read_research(Path("unused"))
        self.assertEqual(reads, [reader.MAX_READ_BYTES + 1])

    def test_independent_modes_and_legacy_original_timestamp(self):
        self.faculty({"topic": research(), "actuator": {"last_run_at": NOW - 301, "last_result": {"mode": "actuator", "outcome": "researched"}},
                      "questions": {"last_run_at": NOW, "last_result": {"mode": "wrong", "outcome": "researched"}}})
        rows = self.observe()["research_faculty"]["records"]
        self.assertEqual([row["mode"] for row in rows], list(reader.MODES))
        self.assertEqual(rows[0]["read_state"], "missing")
        self.assertTrue(rows[1]["recent"])
        self.assertEqual(rows[2]["read_state"], "failed")
        self.assertFalse(rows[3]["recent"])
        reader._cache.clear()
        legacy = {"saved_by": "research_faculty", "last_run_at": NOW - 20, "last_result": {"outcome": "researched"}}
        (self.state / "research_throttle.json").write_text(json.dumps(legacy), encoding="utf-8")
        self.assertEqual(self.observe()["research_faculty"]["records"][0]["source_timestamp_original"], NOW - 20)

    def test_wrong_research_producer_is_rejected(self):
        (self.state / "research_throttle.json").write_text(json.dumps({"saved_by": "fixture", "modes": {"topic": research()}}), encoding="utf-8")
        self.assertEqual(self.observe()["research_faculty"]["read_state"], "failed")

    def test_gate_contradiction_and_missing_stages_cannot_show_passed(self):
        complete = {"passed": True, "outcome": "authorized", "conscience": {"verdict": "APPROVED"},
                    "coherence": {"passed": True}, "authorization": {"passed": True, "verdict": "ALLOW"}}
        self.assertIs(reader._gate(complete)["passed"], True)
        contradictory = {**complete, "authorization": {"passed": True, "verdict": "DENY"}}
        self.assertIsNone(reader._gate(contradictory)["passed"])
        self.assertIs(reader._gate(contradictory)["record_consistent"], False)
        self.assertIsNone(reader._gate({"passed": True})["passed"])
        self.assertIsNone(reader._gate(None))

    def test_only_stdlib_imports_no_writes_or_producer_calls(self):
        tree = ast.parse((STAGE / "aureon/saas/research_activity.py").read_text(encoding="utf-8"))
        modules = [node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
        modules += [alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names]
        self.assertEqual(set(modules), {"__future__", "copy", "json", "math", "os", "threading", "time", "datetime", "pathlib", "typing"})
        opens = [node for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "open"]
        self.assertEqual(len(opens), 2)
        self.assertTrue(all(isinstance(node.args[0], ast.Constant) and node.args[0].value == "rb" for node in opens))

    def test_activity_never_increases_existing_cognitive_readiness_totals(self):
        current = ast.parse((STAGE / "aureon/saas/cognitive.py").read_text(encoding="utf-8"))
        fn = next(node for node in current.body if isinstance(node, ast.FunctionDef) and node.name == "build_cognitive_payload")
        isolated = ast.Module(body=[ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0), fn], type_ignores=[])
        ast.fix_missing_locations(isolated)
        names = ("field", "bus", "mycelium", "connectome", "brain")
        rows = [{"available": True, "fresh": True}, {"available": True, "fresh": True},
                {"available": True, "fresh": False}, {"available": False, "fresh": True}, {}]
        namespace = {"_SURFACE_BUILDERS": {name: (lambda *_args, row=row: row) for name, row in zip(names, rows)},
                     "_summarize": lambda _surfaces: {}, "provenance_block": lambda: {}}
        observed = ModuleType("aureon.saas.observed_runtime")
        observed.runtime_source_observations = lambda: {}
        observed.process_observation = lambda: {}
        activity = ModuleType("aureon.saas.research_activity")
        domains = ModuleType("aureon.saas.domains")
        domains.cognitive_surface_report = lambda: []
        # Compile only the function with passive stubs: never import the Aureon package.
        exec(compile(isolated, "<isolated_cognitive_payload>", "exec"), namespace)
        with patch.dict("sys.modules", {observed.__name__: observed, activity.__name__: activity, domains.__name__: domains}):
            for record in ({}, {"recent": True, "count": 10000, "available": True}):
                activity.research_activity_observation = lambda record=record: record
                result = namespace["build_cognitive_payload"]()
                self.assertEqual(result["research_activity"], record)
                self.assertEqual(result["operational_ready"], 2)
                self.assertEqual(result["observed_fresh_count"], 2)
                self.assertEqual(result["blocked"], 3)
                self.assertEqual(list(result["surfaces"]), list(names))


if __name__ == "__main__":
    unittest.main()
