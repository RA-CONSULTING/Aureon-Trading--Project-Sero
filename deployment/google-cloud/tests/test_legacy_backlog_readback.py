"""Offline Cloud Monitoring legacy-backlog receipt tests."""

from __future__ import annotations

from datetime import UTC, datetime
import importlib.util
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
import sys

import pytest


CONTROL = Path(__file__).resolve().parents[1] / "trading-control"
sys.path.insert(0, str(CONTROL))
MODULE = CONTROL / "legacy_backlog_readback.py"
spec = importlib.util.spec_from_file_location(
    "legacy_backlog_readback", MODULE
)
assert spec and spec.loader
readback = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = readback
spec.loader.exec_module(readback)


def provider_reader(url, *, token):
    assert token == "offline_token_" + "x" * 32
    query = parse_qs(urlsplit(url).query)
    expression = query["filter"][0]
    subscription = next(
        name for name in readback.SUBSCRIPTIONS if name in expression
    )
    metric = next(
        name for name in readback.METRICS if name in expression
    )
    return {
        "timeSeries": [
            {
                "metric": {"type": metric},
                "resource": {
                    "type": "pubsub_subscription",
                    "labels": {
                        "project_id": readback.PROJECT,
                        "subscription_id": subscription,
                    },
                },
                "points": [
                    {
                        "interval": {
                            "endTime": f"2026-09-13T17:0{minute}:00Z"
                        },
                        "value": {"int64Value": "0"},
                    }
                    for minute in (1, 2, 3)
                ],
            }
        ]
    }


def test_collect_binds_every_subscription_metric_and_point():
    receipt = readback.collect(
        contract_sha256="a" * 64,
        source_revision="b" * 40,
        token="offline_token_" + "x" * 32,
        end=datetime(2026, 9, 13, 17, 4, tzinfo=UTC),
        reader=provider_reader,
    )
    assert receipt["contract_sha256"] == "a" * 64
    assert receipt["source_revision"] == "b" * 40
    assert {
        row["resource_name"] for row in receipt["subscriptions"]
    } == {
        f"projects/{readback.PROJECT}/subscriptions/{name}"
        for name in readback.SUBSCRIPTIONS
    }
    for row in receipt["subscriptions"]:
        assert {metric["metric_type"] for metric in row["metrics"]} == set(
            readback.METRICS
        )
        assert all(
            len(metric["points"]) == 3 for metric in row["metrics"]
        )


def test_missing_provider_time_series_fails_closed():
    with pytest.raises(
        readback.ReadbackError, match="time_series_missing"
    ):
        readback.metric_points(
            readback.SUBSCRIPTIONS[0],
            readback.METRICS[0],
            token="offline_token_" + "x" * 32,
            start=datetime(2026, 9, 13, 17, 0, tzinfo=UTC),
            end=datetime(2026, 9, 13, 17, 5, tzinfo=UTC),
            reader=lambda *_args, **_kwargs: {"timeSeries": []},
        )


def test_readback_source_never_prints_or_persists_access_token():
    source = MODULE.read_text(encoding="utf-8")
    assert "print(token" not in source
    assert '"access_token"' not in source
    assert '"Authorization": "Bearer " + token' in source
