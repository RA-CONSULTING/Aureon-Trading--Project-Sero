"""Offline tests for exact zero-traffic Cloud Run staging."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

import pytest


CONTROL = Path(__file__).resolve().parents[1] / "trading-control"
sys.path.insert(0, str(CONTROL))
spec = importlib.util.spec_from_file_location(
    "cloud_run_stage", CONTROL / "cloud_run_stage.py"
)
assert spec and spec.loader
stage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stage)
commission = sys.modules["authority_commission"]

REVISION = "a" * 40
AUTHORITY = (
    "europe-west1-docker.pkg.dev/aureon-trading/aureon-web/"
    "aureon-trading-authority@sha256:" + "b" * 64
)
PUBLIC = (
    "europe-west1-docker.pkg.dev/aureon-trading/aureon-web/"
    "aureon-public-entry@sha256:" + "c" * 64
)


def contract():
    return commission.resolve_contract(
        commission.load_contract(),
        source_revision=REVISION,
        authority_image=AUTHORITY,
        public_entry_image=PUBLIC,
        supabase_project_ref="fixtureprojectref123",
        supabase_owner_subject="12345678-1234-4123-8123-123456789abc",
        supabase_owner_email_sha256="d" * 64,
        iap_admin_email_sha256="e" * 64,
    )


def test_plan_renders_all_services_with_no_traffic_and_exact_networking():
    plan = stage.build_plan(contract(), "f" * 64)
    assert len(plan["services"]) == 7
    rows = {row["service"]: row for row in plan["services"]}
    for row in rows.values():
        assert "--no-traffic" in row["argv"]
        assert not any(arg.startswith("--to-") for arg in row["argv"])
        assert row["revision"].endswith("-r" + REVISION[:12])
    operator = rows["aureon-fusion-operator"]["argv"]
    assert "--iap" in operator
    assert "--network=aureon-sero-network" in operator
    assert "--subnet=aureon-web-entry-europe-west1" in operator
    assert "--network-tags=aureon-web-entry" in operator
    assert "--vpc-egress=private-ranges-only" in operator
    assert "--min-instances=0" in operator
    assert "--max-instances=20" in operator
    assert not any(arg.startswith("--min=") for arg in operator)
    assert not any(arg.startswith("--max=") for arg in operator)
    controller = rows["aureon-trade-controller"]["argv"]
    assert "--no-iap" in controller
    assert "--clear-network" in controller
    assert "--timeout=120s" in controller


def test_exact_plan_acknowledgement_and_execution(tmp_path):
    plan = stage.build_plan(contract(), "f" * 64)
    path = (tmp_path / "plan.json").resolve()
    path.write_text(json.dumps(plan), encoding="utf-8")
    plan_hash = commission.sha256(commission.canonical(plan))
    assert stage.load_exact_plan(path, plan, plan_hash) == plan_hash
    calls = []

    def runner(executable, project, args):
        calls.append((executable, project, args))

    completed = stage.execute_plan(plan, executable="fixture-gcloud", runner=runner)
    assert completed == [row["service"] for row in plan["services"]]
    assert len(calls) == 7
    assert all("--no-traffic" in args for _, _, args in calls)

    tampered = dict(plan)
    tampered["source_revision"] = "f" * 40
    path.write_text(json.dumps(tampered), encoding="utf-8")
    with pytest.raises(stage.StageError, match="binding_invalid"):
        stage.load_exact_plan(path, plan, plan_hash)


def test_resumable_stage_records_failure_and_skips_provider_exact_revision():
    plan = stage.build_plan(contract(), "f" * 64)
    completed = []
    progress = []
    calls = []

    def runner(_executable, _project, args):
        name = args[2]
        calls.append(name)
        if name == plan["services"][1]["service"]:
            raise stage.StageError("cloud_run_stage_command_failed")
        completed.append(name)

    def is_complete(name):
        return name in completed

    def record(status, done, in_flight, error):
        progress.append((status, list(done), in_flight, error))

    with pytest.raises(stage.StageError, match="command_failed"):
        stage.execute_resumable(
            plan,
            completed=[],
            executable="fixture-gcloud",
            is_complete=is_complete,
            progress=record,
            runner=runner,
        )
    assert progress[-1] == (
        "recovery_required",
        [plan["services"][0]["service"]],
        plan["services"][1]["service"],
        "cloud_run_stage_command_failed",
    )

    completed.append(plan["services"][1]["service"])
    resumed = stage.execute_resumable(
        plan,
        completed=[plan["services"][0]["service"]],
        executable="fixture-gcloud",
        is_complete=is_complete,
        progress=record,
        runner=runner,
    )
    assert resumed == [row["service"] for row in plan["services"]]
    assert calls.count(plan["services"][1]["service"]) == 1


def test_recovery_revalidates_completed_prefix_before_any_new_deploy():
    plan = stage.build_plan(contract(), "f" * 64)
    first = plan["services"][0]["service"]
    progress = []
    calls = []
    with pytest.raises(stage.StageError, match="prior_readback_not_exact"):
        stage.execute_resumable(
            plan,
            completed=[first],
            executable="fixture-gcloud",
            is_complete=lambda _name: False,
            progress=lambda *row: progress.append(row),
            runner=lambda *_args: calls.append(_args),
        )
    assert calls == []
    assert progress[-1] == (
        "recovery_required",
        [],
        first,
        "cloud_run_stage_prior_readback_not_exact",
    )


def test_recovery_receipt_rejects_tampered_plan_binding(tmp_path):
    plan = stage.build_plan(contract(), "f" * 64)
    progress = stage._progress_receipt(
        plan,
        status="recovery_required",
        completed=[],
        in_flight_service=plan["services"][0]["service"],
        error_code="cloud_run_stage_command_failed",
    )
    path = (tmp_path / "progress.json").resolve()
    path.write_text(json.dumps(progress), encoding="utf-8")
    assert stage._load_recovery(path, plan) == []
    progress["immutable_image_build_receipt_sha256"] = "0" * 64
    path.write_text(json.dumps(progress), encoding="utf-8")
    with pytest.raises(stage.StageError, match="recovery_receipt_invalid"):
        stage._load_recovery(path, plan)
