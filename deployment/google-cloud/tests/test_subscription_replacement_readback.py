"""Offline tests for safe immutable-subscription replacement readback."""

from __future__ import annotations

from datetime import UTC, datetime
import importlib.util
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit
import sys

import pytest


CONTROL = Path(__file__).resolve().parents[1] / "trading-control"
sys.path.insert(0, str(CONTROL))
MODULE = CONTROL / "subscription_replacement_readback.py"
spec = importlib.util.spec_from_file_location(
    "subscription_replacement_readback", MODULE
)
assert spec and spec.loader
readback = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = readback
spec.loader.exec_module(readback)


def provider_reader(url, *, token):
    assert token == "offline_token_" + "x" * 32
    query = parse_qs(urlsplit(url).query)
    expression = query["filter"][0]
    assert readback.SUBSCRIPTION in expression
    metric = next(name for name in readback.METRICS if name in expression)
    return {
        "timeSeries": [
            {
                "metric": {"type": metric},
                "resource": {
                    "type": "pubsub_subscription",
                    "labels": {
                        "project_id": readback.PROJECT,
                        "subscription_id": readback.SUBSCRIPTION,
                    },
                },
                "points": [
                    {
                        "interval": {"endTime": f"2026-09-13T17:0{x}:00Z"},
                        "value": {"int64Value": "0"},
                    }
                    for x in (1, 2, 3)
                ],
            }
        ]
    }


def test_collect_binds_frozen_publisher_and_explicit_zero_series():
    receipt = readback.collect(
        contract_sha256="a" * 64,
        source_revision="b" * 40,
        token="offline_token_" + "x" * 32,
        state={
            "active_state": "inactive",
            "sub_state": "dead",
            "unit_file_state": "disabled",
            "frozen_since": "2026-09-13T16:59:00+00:00",
        },
        end=datetime(2026, 9, 13, 17, 4, tzinfo=UTC),
        reader=provider_reader,
    )
    row = receipt["subscriptions"][0]
    assert row["resource_name"].endswith("/" + readback.SUBSCRIPTION)
    assert row["topic_resource_name"].endswith("/" + readback.TOPIC)
    assert row["publisher_freeze"]["member"] == readback.PUBLISHER_MEMBER
    assert row["publisher_freeze"]["active_state"] == "inactive"
    assert len(row["publisher_freeze"]["readback_sha256"]) == 64
    assert {item["metric_type"] for item in row["metrics"]} == set(
        readback.METRICS
    )


def test_publisher_state_reads_only_fixed_systemd_state(monkeypatch):
    calls = []

    def run(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(
            returncode=0,
            stdout=(
                "ActiveState=inactive\nSubState=dead\nUnitFileState=disabled\n"
                "FrozenSince=2026-09-13T16:59:00+00:00\n"
            ),
        )

    monkeypatch.setattr(readback.subprocess, "run", run)
    assert readback.publisher_state("gcloud-fixture") == {
        "active_state": "inactive",
        "sub_state": "dead",
        "unit_file_state": "disabled",
        "frozen_since": "2026-09-13T16:59:00+00:00",
    }
    command = calls[0][0]
    assert command[:4] == [
        "gcloud-fixture", "compute", "ssh", readback.INSTANCE,
    ]
    assert "Environment" not in " ".join(command)
    remote = next(
        item.removeprefix("--command=")
        for item in command
        if item.startswith("--command=")
    )
    assert "ActiveEnterTimestampMonotonic" in remote
    assert "InactiveExitTimestampMonotonic" in remote
    assert "ExecMainStartTimestampMonotonic" in remote
    assert "InvocationID" in remote
    assert 'awk \'$1 == "btime" {print $2}\' /proc/stat' in remote


def test_publisher_state_rejects_missing_freeze_timestamp(monkeypatch):
    def run(_command, **_kwargs):
        return SimpleNamespace(
            returncode=0,
            stdout=(
                "ActiveState=inactive\nSubState=dead\nUnitFileState=disabled\n"
                "FrozenSince=\n"
            ),
        )

    monkeypatch.setattr(readback.subprocess, "run", run)
    with pytest.raises(
        readback.ReplacementReadbackError,
        match="publisher_readback_invalid",
    ):
        readback.publisher_state("gcloud-fixture")


def test_readback_source_never_outputs_token_or_environment():
    source = MODULE.read_text(encoding="utf-8")
    assert "print(token" not in source
    assert '"access_token"' not in source
    assert "--property=Environment" not in source
    assert "subscriptions delete" not in source
