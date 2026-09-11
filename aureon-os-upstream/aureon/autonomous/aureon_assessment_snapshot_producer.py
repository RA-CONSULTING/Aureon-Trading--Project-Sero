"""Persist read-only cognitive assessment snapshots for the UI gateway.

The SaaS gateway must stay passive: GET routes read persisted evidence and never
construct live monitors. This producer is the active read-only side of that
contract. It calls assess() methods only, never reflect(), deliberate(), direct(),
or any execution path.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional, Sequence

SCHEMA_VERSION = "aureon-assessment-snapshots-v1"
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_JSON = REPO_ROOT / "docs" / "audits" / "aureon_assessment_snapshots.json"
DEFAULT_PUBLIC_JSON = REPO_ROOT / "frontend" / "public" / "aureon_assessment_snapshots.json"

Builder = Callable[[], dict[str, Any]]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _as_dict(value: Any) -> dict[str, Any]:
    if hasattr(value, "to_dict"):
        value = value.to_dict()
    return value if isinstance(value, dict) else {"available": False, "truth_status": "no_data"}


def _metacognition() -> dict[str, Any]:
    from aureon.core.metacognition_monitor import get_metacognition_monitor

    return _as_dict(get_metacognition_monitor().assess())


def _soul() -> dict[str, Any]:
    from aureon.core.soul import get_soul

    return _as_dict(get_soul().assess())


def _inner_work() -> dict[str, Any]:
    from aureon.core.inner_work import get_inner_work

    return _as_dict(get_inner_work().assess())


def _pursuit() -> dict[str, Any]:
    from aureon.core.pursuit import get_pursuit

    return _as_dict(get_pursuit().assess())


ASSESSMENT_BUILDERS: dict[str, Builder] = {
    "metacognition": _metacognition,
    "soul": _soul,
    "inner_work": _inner_work,
    "pursuit": _pursuit,
}


def _capture(name: str, build: Builder) -> dict[str, Any]:
    try:
        row = _as_dict(build())
        row.setdefault("available", False)
        row.setdefault("truth_status", "no_data")
        row.setdefault("ts", time.time())
        row["producer_surface"] = name
        return row
    except Exception as exc:  # noqa: BLE001 - a producer failure is data, not a crash
        return {
            "available": False,
            "truth_status": "no_data",
            "ts": time.time(),
            "producer_surface": name,
            "producer_error": type(exc).__name__,
        }


def build_assessment_snapshots(
    root: Optional[Path] = None,
    builders: dict[str, Builder] | None = None,
) -> dict[str, Any]:
    """Build a bounded snapshot using read-only assessment methods.

    The deterministic self-authoring fallback is forced for this producer so a
    Soul assessment cannot open a model call while preparing a UI status row.
    """
    os.environ.setdefault("AUREON_LLM_OFFLINE", "1")
    selected = builders or ASSESSMENT_BUILDERS
    captured = {name: _capture(name, build) for name, build in selected.items()}
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_now(),
        "status": "assessment_snapshots_ready",
        "repo_root": str((root or REPO_ROOT).resolve()),
        "assessment_count": len(captured),
        "assessments": captured,
        "producer_contract": {
            "passive_gateway": "GET routes read this file and do not construct assessment monitors.",
            "read_only_methods": "Only assess() methods are called; reflect(), deliberate(), direct(), execution, payment, filing and exchange mutation paths are not called.",
            "offline_self_authoring": "AUREON_LLM_OFFLINE defaults to 1 inside this producer to prevent model calls during status refresh.",
        },
    }


def write_assessment_snapshots(
    snapshot: dict[str, Any],
    output_json: Path = DEFAULT_OUTPUT_JSON,
    public_json: Path = DEFAULT_PUBLIC_JSON,
) -> tuple[Path, Path]:
    output_json.parent.mkdir(parents=True, exist_ok=True)
    public_json.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(snapshot, indent=2, sort_keys=True, default=str)
    output_json.write_text(data, encoding="utf-8")
    public_json.write_text(data, encoding="utf-8")
    return output_json, public_json


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Aureon read-only assessment snapshots for the UI gateway.")
    parser.add_argument("--repo-root", default="", help="Repo root recorded in the snapshot; defaults to current Aureon repo.")
    parser.add_argument("--json", default=str(DEFAULT_OUTPUT_JSON), help="Audit JSON path.")
    parser.add_argument("--public-json", default=str(DEFAULT_PUBLIC_JSON), help="Frontend public JSON path.")
    parser.add_argument("--daemon", action="store_true", help="Continuously refresh the assessment snapshot.")
    parser.add_argument("--interval", type=float, default=5.0, help="Refresh interval in seconds when --daemon is set.")
    parser.add_argument("--quiet", action="store_true", help="Suppress per-cycle JSON output when running as a daemon.")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    root = Path(args.repo_root).resolve() if args.repo_root else REPO_ROOT
    interval = max(1.0, float(args.interval))
    while True:
        snapshot = build_assessment_snapshots(root)
        output, public = write_assessment_snapshots(snapshot, Path(args.json), Path(args.public_json))
        if not args.quiet:
            print(json.dumps({
                "json": str(output),
                "public_json": str(public),
                "assessment_count": snapshot["assessment_count"],
                "available": {key: value.get("available") for key, value in snapshot["assessments"].items()},
            }, indent=2, sort_keys=True), flush=True)
        if not args.daemon:
            return 0
        time.sleep(interval)


if __name__ == "__main__":
    raise SystemExit(main())
