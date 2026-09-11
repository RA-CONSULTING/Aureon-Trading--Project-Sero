"""Status probes preserve coordinator results without constructing live bus services.

Production classes/functions are compiled from AST; no runtime modules, provider
clients, credentials, or background services are imported by these tests.
"""
import ast
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Dict, List, Optional, Set
from unittest.mock import Mock


ROOT = Path(__file__).resolve().parents[1]


class FixedDatetime(datetime):
    @classmethod
    def now(cls, tz=None):
        return cls(2026, 9, 8, 10, 0, 0, tzinfo=tz)


def coordinator_class(bus_factory):
    path = ROOT / "aureon/core/aureon_system_coordinator.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = {"SystemState", "SystemCategory", "SystemDependency", "SystemState_Data", "SystemCoordinator"}
    classes = [node for node in tree.body if isinstance(node, ast.ClassDef) and node.name in names]
    namespace = {"Enum": Enum, "dataclass": dataclass, "field": field, "asdict": asdict,
                 "Dict": Dict, "List": List, "Optional": Optional, "Set": Set,
                 "Path": Path, "json": json, "datetime": FixedDatetime,
                 "time": SimpleNamespace(time=lambda: 1_800_000_000.0),
                 "logger": Mock(), "ThoughtBus": bus_factory}
    exec(compile(ast.Module(body=classes, type_ignores=[]), str(path), "exec"), namespace)
    return namespace["SystemCoordinator"]


def status_probe(factory):
    path = ROOT / "aureon/saas/status.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    node = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "_coordinator_state")
    # Replace only the import with the isolated class fixture; retain the actual
    # request probe call, result shaping, and error handling.
    class IsolateImport(ast.NodeTransformer):
        def visit_ImportFrom(self, node):
            return None if node.module == "aureon.core.aureon_system_coordinator" else node
    node = IsolateImport().visit(node)
    namespace = {"Dict": Dict, "Any": object, "logger": Mock(), "SystemCoordinator": factory}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])), str(path), "exec"), namespace)
    return namespace["_coordinator_state"]


def registry(tmp_path):
    path = tmp_path / "coordinator.json"
    path.write_text(json.dumps({"categories": {"Execution Engines": {"systems": [
        {"name": "orca_complete_kill_cycle", "filepath": "test-only.py", "loc": 10,
         "is_dashboard": False, "has_thought_bus": True, "has_queen_integration": True},
    ]}}}), encoding="utf-8")
    return path


def test_default_coordinator_bus_behavior_remains_enabled(tmp_path):
    bus = Mock(return_value=SimpleNamespace(live_bus_marker=True))
    Coordinator = coordinator_class(bus)
    coordinator = Coordinator(str(registry(tmp_path)))
    bus.assert_called_once_with()
    assert coordinator.thought_bus is bus.return_value


def test_read_only_coordinator_retains_identical_snapshot_and_execution_blockers(tmp_path):
    bus = Mock(return_value=SimpleNamespace(live_bus_marker=True))
    Coordinator = coordinator_class(bus)
    path = str(registry(tmp_path))
    operational = Coordinator(path)
    observed = Coordinator(path, connect_bus=False)
    assert observed.thought_bus is None
    assert observed.get_coordination_state() == operational.get_coordination_state()
    assert observed.can_execute_orca() == operational.can_execute_orca()
    assert observed.systems == operational.systems
    assert observed.dependencies == operational.dependencies
    bus.assert_called_once_with()


def test_repeated_status_probes_never_create_coordinator_or_legacy_background_work():
    factory = Mock(side_effect=AssertionError("constructed a private coordinator"))
    probe = status_probe(factory)
    for _ in range(100):
        assert probe() == {"available": False, "truth_status": "no_data",
                           "reason": "no_published_coordinator_runtime_snapshot"}
    factory.assert_not_called()
