"""Exercise actual history writers without importing or starting the Miner Brain."""
from __future__ import annotations

import ast
import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from aureon.saas.observed_runtime import historical_file_observation, source_epoch


SOURCE = Path(__file__).resolve().parents[1] / "aureon/utils/aureon_miner_brain.py"


def writer_method(class_name: str, method_name: str):
    """Compile the original method and its datetime import, excluding active boot code."""
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    datetime_import = next(
        node for node in tree.body
        if isinstance(node, ast.ImportFrom) and node.module == "datetime"
    )
    owner = next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == class_name
    )
    method = next(
        node for node in owner.body
        if isinstance(node, ast.FunctionDef) and node.name == method_name
    )
    namespace = {"json": json, "os": os, "logger": Mock(), "Dict": dict}
    isolated = ast.Module(body=[datetime_import, method], type_ignores=[])
    exec(compile(isolated, str(SOURCE), "exec"), namespace)
    return namespace[method_name]


def assert_original_utc_clock(value: str, before: float, after: float):
    parsed = datetime.fromisoformat(value)
    assert parsed.utcoffset() == timedelta(0)
    stamp = source_epoch(value)
    assert stamp is not None and before <= stamp <= after
    return stamp


def test_prediction_writer_clock_reaches_strict_history_reader(tmp_path):
    path = tmp_path / "brain_predictions_history.json"
    predictions = [
        {"id": index, "validated": index % 2 == 0, "was_correct": True}
        for index in range(103)
    ]
    owner = SimpleNamespace(
        predictions_file=str(path), predictions=predictions,
        bias_tracker={"bullish_calls": 3},
    )
    before = time.time()
    writer_method("CognitiveCircle", "_save_predictions")(owner)
    after = time.time()
    saved = json.loads(path.read_text(encoding="utf-8"))
    stamp = assert_original_utc_clock(saved["last_updated"], before, after)
    assert saved["predictions"] == predictions[-100:]
    assert saved["bias_tracker"] == owner.bias_tracker
    observed = historical_file_observation(path, "brain_predictions", now=after)
    assert observed["historical_available"] is True
    assert observed["source_timestamp"] == stamp
    assert observed["total_predictions"] == 100
    assert observed["validated"] == 50 and observed["accuracy_pct"] == 100


def test_knowledge_writer_clock_preserves_history_and_reaches_strict_reader(tmp_path):
    path = tmp_path / "miner_brain_knowledge.json"
    existing = [{"timestamp": "2026-01-01T00:00:00", "talk": str(index)} for index in range(100)]
    path.write_text(json.dumps(existing), encoding="utf-8")
    owner = SimpleNamespace(MEMORY_FILE=str(path))
    before = time.time()
    writer_method("MemoryCore", "remember")(
        owner, "isolated fixture", {"processed": {"fixture": True}},
        {"skeptic": {"fixture": True}, "council": {"fixture": True}, "speculations": []},
    )
    after = time.time()
    saved = json.loads(path.read_text(encoding="utf-8"))
    stamp = assert_original_utc_clock(saved[-1]["timestamp"], before, after)
    assert len(saved) == 100 and saved[:-1] == existing[1:]
    assert saved[-1] == {
        "timestamp": saved[-1]["timestamp"], "talk": "isolated fixture",
        "processed_data": {"fixture": True}, "skeptic_analysis": {"fixture": True},
        "council_verdict": {"fixture": True}, "speculations": [],
    }
    observed = historical_file_observation(path, "brain_knowledge", now=after)
    assert observed["historical_available"] is True
    assert observed["source_timestamp"] == stamp and observed["entries"] == 100
