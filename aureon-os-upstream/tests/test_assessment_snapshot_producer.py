import json
from pathlib import Path

from aureon.autonomous.aureon_assessment_snapshot_producer import (
    build_assessment_snapshots,
    write_assessment_snapshots,
)


def test_assessment_snapshot_producer_writes_only_read_only_surfaces(tmp_path, monkeypatch):
    monkeypatch.delenv("AUREON_LLM_OFFLINE", raising=False)
    snapshot = build_assessment_snapshots(
        tmp_path,
        builders={
            "metacognition": lambda: {"available": True, "truth_status": "real_derived", "contributors": 1, "signals": {}, "ts": 10.0},
            "soul": lambda: {"available": False, "truth_status": "no_data", "ts": 10.0},
        },
    )
    assert snapshot["schema_version"] == "aureon-assessment-snapshots-v1"
    assert snapshot["assessment_count"] == 2
    assert snapshot["assessments"]["metacognition"]["contributors"] == 1
    assert snapshot["producer_contract"]["read_only_methods"].startswith("Only assess()")
    assert "direct()" in snapshot["producer_contract"]["read_only_methods"]
    assert snapshot["assessments"]["soul"]["available"] is False
    import os
    assert os.environ["AUREON_LLM_OFFLINE"] == "1"

    audit, public = write_assessment_snapshots(snapshot, tmp_path / "audit.json", tmp_path / "public.json")
    assert audit.exists() and public.exists()
    assert json.loads(public.read_text(encoding="utf-8"))["assessment_count"] == 2
