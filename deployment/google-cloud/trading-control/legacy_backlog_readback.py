"""Write a redacted Cloud Monitoring receipt for legacy Pub/Sub retirement.

This command is read-only. It captures a gcloud access token in memory, queries
two fixed metrics for four fixed subscriptions, and writes only resource names,
timestamps, and numeric measurements. Missing time series fail closed.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime, timedelta
import json
from pathlib import Path
import re
import subprocess
from typing import Any, Callable, Mapping
from urllib.parse import urlencode
from urllib.request import (
    HTTPRedirectHandler,
    ProxyHandler,
    Request,
    build_opener,
)

from authority_commission import (
    CommissionError,
    canonical,
    sha256,
    write_receipt,
)


PROJECT = "aureon-trading"
SCHEMA = "aureon.gcp.pubsub-legacy-retirement-readback.v1"
SUBSCRIPTIONS = (
    "aureon-trade-review-v1",
    "aureon-trade-dispatch-v1",
    "aureon-trade-executor-v1",
    "aureon-trade-receipt-v1",
)
REPLACEMENT_SUBSCRIPTIONS = (
    "aureon-trade-release-controller-push-v1",
)
MONITORED_SUBSCRIPTIONS = frozenset(
    (*SUBSCRIPTIONS, *REPLACEMENT_SUBSCRIPTIONS)
)
METRICS = (
    "pubsub.googleapis.com/subscription/num_undelivered_messages",
    "pubsub.googleapis.com/subscription/oldest_unacked_message_age",
)
API_ROOT = (
    "https://monitoring.googleapis.com/v3/projects/"
    + PROJECT
    + "/timeSeries"
)
_TOKEN = re.compile(r"[A-Za-z0-9._~-]{20,8192}")
_HEX64 = re.compile(r"[0-9a-f]{64}")
_REVISION = re.compile(r"[0-9a-f]{40}")


class ReadbackError(RuntimeError):
    """Stable failure without provider response or credential content."""


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ReadbackError("monitoring_redirect_denied")


def gcloud_token(executable: str) -> str:
    try:
        result = subprocess.run(
            [executable, "auth", "print-access-token", "--quiet"],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ReadbackError("gcloud_token_failed") from exc
    token = result.stdout.strip()
    if result.returncode or _TOKEN.fullmatch(token) is None:
        raise ReadbackError("gcloud_token_failed")
    return token


def read_json(url: str, *, token: str) -> Any:
    if not url.startswith(API_ROOT + "?") or _TOKEN.fullmatch(token) is None:
        raise ReadbackError("monitoring_request_invalid")
    opener = build_opener(ProxyHandler({}), NoRedirects())
    try:
        with opener.open(
            Request(
                url,
                headers={
                    "Authorization": "Bearer " + token,
                    "Accept": "application/json",
                },
                method="GET",
            ),
            timeout=20,
        ) as response:
            if response.status != 200:
                raise ReadbackError("monitoring_request_failed")
            raw = response.read(1_048_577)
    except ReadbackError:
        raise
    except OSError as exc:
        raise ReadbackError("monitoring_request_failed") from exc
    if len(raw) > 1_048_576:
        raise ReadbackError("monitoring_response_too_large")
    try:
        return json.loads(raw)
    except (ValueError, TypeError, UnicodeError) as exc:
        raise ReadbackError("monitoring_response_invalid") from exc


def _number(value: Mapping[str, Any]) -> int | float:
    if set(value) == {"int64Value"}:
        raw = value["int64Value"]
        if not isinstance(raw, str) or not raw.isdigit():
            raise ReadbackError("monitoring_point_invalid")
        return int(raw)
    if set(value) == {"doubleValue"}:
        raw = value["doubleValue"]
        if isinstance(raw, bool) or not isinstance(raw, (int, float)):
            raise ReadbackError("monitoring_point_invalid")
        return float(raw)
    raise ReadbackError("monitoring_point_invalid")


def metric_points(
    subscription: str,
    metric: str,
    *,
    token: str,
    start: datetime,
    end: datetime,
    reader: Callable[..., Any] = read_json,
) -> list[dict[str, Any]]:
    if subscription not in MONITORED_SUBSCRIPTIONS or metric not in METRICS:
        raise ReadbackError("monitoring_resource_invalid")
    query = urlencode(
        {
            "filter": (
                f'metric.type="{metric}" AND '
                'resource.type="pubsub_subscription" AND '
                f'resource.labels.subscription_id="{subscription}"'
            ),
            "interval.startTime": start.isoformat().replace("+00:00", "Z"),
            "interval.endTime": end.isoformat().replace("+00:00", "Z"),
            "aggregation.alignmentPeriod": "60s",
            "aggregation.perSeriesAligner": "ALIGN_MAX",
            "view": "FULL",
            "pageSize": "1000",
        }
    )
    value = reader(API_ROOT + "?" + query, token=token)
    rows = value.get("timeSeries") if isinstance(value, Mapping) else None
    if not isinstance(rows, list) or not rows:
        raise ReadbackError("monitoring_time_series_missing")
    points: dict[str, int | float] = {}
    for row in rows:
        resource = row.get("resource", {}) if isinstance(row, Mapping) else {}
        labels = resource.get("labels", {}) if isinstance(resource, Mapping) else {}
        metric_value = row.get("metric", {}) if isinstance(row, Mapping) else {}
        if (
            resource.get("type") != "pubsub_subscription"
            or labels.get("project_id") != PROJECT
            or labels.get("subscription_id") != subscription
            or metric_value.get("type") != metric
        ):
            raise ReadbackError("monitoring_series_binding_invalid")
        for point in row.get("points", []):
            interval = point.get("interval", {}) if isinstance(point, Mapping) else {}
            observed = interval.get("endTime")
            point_value = point.get("value") if isinstance(point, Mapping) else None
            if (
                not isinstance(observed, str)
                or not isinstance(point_value, Mapping)
                or observed in points
            ):
                raise ReadbackError("monitoring_point_invalid")
            points[observed] = _number(point_value)
    if len(points) < 3:
        raise ReadbackError("monitoring_time_series_missing")
    return [
        {"observed_at": stamp, "value": points[stamp]}
        for stamp in sorted(points)
    ]


def collect(
    *,
    contract_sha256: str,
    source_revision: str,
    token: str,
    end: datetime | None = None,
    window_seconds: int = 300,
    reader: Callable[..., Any] = read_json,
) -> dict[str, Any]:
    if _HEX64.fullmatch(contract_sha256 or "") is None:
        raise ReadbackError("contract_sha256_invalid")
    if _REVISION.fullmatch(source_revision or "") is None:
        raise ReadbackError("source_revision_invalid")
    if window_seconds < 120 or window_seconds > 900:
        raise ReadbackError("monitoring_window_invalid")
    finished = datetime.now(UTC) if end is None else end.astimezone(UTC)
    started = finished - timedelta(seconds=window_seconds)
    rows = []
    for subscription in SUBSCRIPTIONS:
        rows.append(
            {
                "resource_name": (
                    f"projects/{PROJECT}/subscriptions/{subscription}"
                ),
                "metrics": [
                    {
                        "metric_type": metric,
                        "points": metric_points(
                            subscription,
                            metric,
                            token=token,
                            start=started,
                            end=finished,
                            reader=reader,
                        ),
                    }
                    for metric in METRICS
                ],
            }
        )
    return {
        "schema": SCHEMA,
        "provider": "cloud_monitoring",
        "project": PROJECT,
        "contract_sha256": contract_sha256,
        "source_revision": source_revision,
        "recorded_at": datetime.now(UTC).isoformat(),
        "window_start": started.isoformat(),
        "window_end": finished.isoformat(),
        "subscriptions": rows,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gcloud", default="gcloud")
    parser.add_argument("--contract-sha256", required=True)
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--window-seconds", type=int, default=300)
    args = parser.parse_args(argv)
    try:
        value = collect(
            contract_sha256=args.contract_sha256,
            source_revision=args.source_revision,
            token=gcloud_token(args.gcloud),
            window_seconds=args.window_seconds,
        )
        write_receipt(args.receipt, value)
        maximum = max(
            float(point["value"])
            for row in value["subscriptions"]
            for metric in row["metrics"]
            for point in metric["points"]
        )
        print(
            json.dumps(
                {
                    "schema": SCHEMA,
                    "receipt": str(args.receipt),
                    "receipt_sha256": sha256(canonical(value)),
                    "all_measurements_zero": maximum == 0.0,
                },
                sort_keys=True,
            )
        )
        return 0 if maximum == 0.0 else 1
    except (ReadbackError, CommissionError) as exc:
        print(str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
