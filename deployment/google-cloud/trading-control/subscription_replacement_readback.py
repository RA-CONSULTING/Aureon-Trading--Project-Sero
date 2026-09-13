"""Capture the redacted precondition receipt for immutable subscription replacement.

This command is read-only. It proves the exact publisher unit is stopped and
queries explicit Cloud Monitoring backlog series. It never changes Pub/Sub,
starts or stops a service, or emits a token or environment value.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime, timedelta
import json
from pathlib import Path
import re
import subprocess
from typing import Any, Callable, Mapping

from authority_commission import CommissionError, canonical, sha256, write_receipt
from legacy_backlog_readback import METRICS, gcloud_token, metric_points, read_json


PROJECT = "aureon-trading"
ZONE = "europe-west1-b"
INSTANCE = "aureon-sero-20260906"
SUBSCRIPTION = "aureon-trade-release-controller-push-v1"
TOPIC = "aureon-trade-release-requests-v1"
PUBLISHER_MEMBER = (
    "serviceAccount:aureon-vm-operator@aureon-trading.iam.gserviceaccount.com"
)
PUBLISHER_UNIT = "aureon-cloud-operator.service"
SCHEMA = "aureon.gcp.subscription-replacement-readback.v1"
PROVIDER = "cloud_monitoring_and_gce_systemd"
_HEX64 = re.compile(r"[0-9a-f]{64}")
_REVISION = re.compile(r"[0-9a-f]{40}")


class ReplacementReadbackError(RuntimeError):
    """Stable failure without provider output or credential content."""


def publisher_state(executable: str) -> dict[str, str]:
    command = (
        "set -eu; systemctl show " + PUBLISHER_UNIT
        + " --property=ActiveState --property=SubState "
        + "--property=UnitFileState --no-pager; "
        + "stamp=$(systemctl show " + PUBLISHER_UNIT
        + " --property=InactiveEnterTimestamp --value); "
        + "printf 'FrozenSince='; date --date=\"$stamp\" --iso-8601=seconds"
    )
    try:
        result = subprocess.run(
            [
                executable,
                "compute",
                "ssh",
                INSTANCE,
                "--project=" + PROJECT,
                "--zone=" + ZONE,
                "--tunnel-through-iap",
                "--command=" + command,
                "--quiet",
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=45,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ReplacementReadbackError("publisher_readback_failed") from exc
    if result.returncode or len(result.stdout) > 1024:
        raise ReplacementReadbackError("publisher_readback_failed")
    values: dict[str, str] = {}
    for line in result.stdout.splitlines():
        if not line or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key not in {
            "ActiveState", "SubState", "UnitFileState", "FrozenSince"
        } or key in values:
            raise ReplacementReadbackError("publisher_readback_invalid")
        values[key] = value
    if set(values) != {
        "ActiveState", "SubState", "UnitFileState", "FrozenSince"
    }:
        raise ReplacementReadbackError("publisher_readback_invalid")
    try:
        frozen_since = datetime.fromisoformat(values["FrozenSince"])
        if frozen_since.tzinfo is None:
            raise ValueError("timezone_required")
    except (ValueError, TypeError, OverflowError) as exc:
        raise ReplacementReadbackError("publisher_readback_invalid") from exc
    return {
        "active_state": values["ActiveState"],
        "sub_state": values["SubState"],
        "unit_file_state": values["UnitFileState"],
        "frozen_since": values["FrozenSince"],
    }


def collect(
    *,
    contract_sha256: str,
    source_revision: str,
    token: str,
    state: Mapping[str, str],
    end: datetime | None = None,
    window_seconds: int = 300,
    reader: Callable[..., Any] = read_json,
) -> dict[str, Any]:
    if _HEX64.fullmatch(contract_sha256 or "") is None:
        raise ReplacementReadbackError("contract_sha256_invalid")
    if _REVISION.fullmatch(source_revision or "") is None:
        raise ReplacementReadbackError("source_revision_invalid")
    if window_seconds < 120 or window_seconds > 300:
        raise ReplacementReadbackError("monitoring_window_invalid")
    if (
        set(state) != {
            "active_state", "sub_state", "unit_file_state", "frozen_since"
        }
        or any(
            not isinstance(state[key], str)
            or not re.fullmatch(r"[a-z-]{2,32}", state[key])
            for key in ("active_state", "sub_state", "unit_file_state")
        )
    ):
        raise ReplacementReadbackError("publisher_readback_invalid")
    try:
        frozen_since = datetime.fromisoformat(state["frozen_since"]).astimezone(UTC)
    except (ValueError, TypeError, OverflowError) as exc:
        raise ReplacementReadbackError("publisher_readback_invalid") from exc
    finished = datetime.now(UTC) if end is None else end.astimezone(UTC)
    started = finished - timedelta(seconds=window_seconds)
    observed_at = datetime.now(UTC)
    evidence = {
        "project": PROJECT,
        "zone": ZONE,
        "instance": INSTANCE,
        "unit": PUBLISHER_UNIT,
        "active_state": state["active_state"],
        "sub_state": state["sub_state"],
        "unit_file_state": state["unit_file_state"],
        "frozen_since": frozen_since.isoformat(),
        "observed_at": observed_at.isoformat(),
    }
    return {
        "schema": SCHEMA,
        "provider": PROVIDER,
        "project": PROJECT,
        "contract_sha256": contract_sha256,
        "source_revision": source_revision,
        "recorded_at": observed_at.isoformat(),
        "window_start": started.isoformat(),
        "window_end": finished.isoformat(),
        "subscriptions": [
            {
                "resource_name": f"projects/{PROJECT}/subscriptions/{SUBSCRIPTION}",
                "topic_resource_name": f"projects/{PROJECT}/topics/{TOPIC}",
                "publisher_freeze": {
                    "member": PUBLISHER_MEMBER,
                    "runtime": "gce_systemd",
                    "unit": PUBLISHER_UNIT,
                    "active_state": state["active_state"],
                    "sub_state": state["sub_state"],
                    "unit_file_state": state["unit_file_state"],
                    "frozen_since": frozen_since.isoformat(),
                    "observed_at": observed_at.isoformat(),
                    "readback_sha256": sha256(canonical(evidence)),
                },
                "metrics": [
                    {
                        "metric_type": metric,
                        "points": metric_points(
                            SUBSCRIPTION,
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
        ],
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
            state=publisher_state(args.gcloud),
            window_seconds=args.window_seconds,
        )
        write_receipt(args.receipt, value)
        freeze = value["subscriptions"][0]["publisher_freeze"]
        maximum = max(
            float(point["value"])
            for metric in value["subscriptions"][0]["metrics"]
            for point in metric["points"]
        )
        ready = (
            freeze["active_state"] == "inactive"
            and freeze["sub_state"] == "dead"
            and freeze["unit_file_state"] == "disabled"
            and datetime.fromisoformat(freeze["frozen_since"])
            <= datetime.fromisoformat(value["window_start"])
            and maximum == 0.0
        )
        print(
            json.dumps(
                {
                    "schema": SCHEMA,
                    "receipt": str(args.receipt),
                    "receipt_sha256": sha256(canonical(value)),
                    "publisher_frozen": freeze["active_state"] == "inactive"
                    and freeze["sub_state"] == "dead",
                    "all_measurements_zero": maximum == 0.0,
                },
                sort_keys=True,
            )
        )
        return 0 if ready else 1
    except (ReplacementReadbackError, CommissionError) as exc:
        print(str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
