"""Offline tests for exact zero-traffic Cloud Run staging."""

from __future__ import annotations

import importlib.util
import json
from copy import deepcopy
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


def staged_provider_fixture(resolved, expected):
    revision_name = expected["name"] + "-r" + REVISION[:12]
    revision_annotations = {
        "autoscaling.knative.dev/minScale": str(expected["scaling"]["min_instances"]),
        "autoscaling.knative.dev/maxScale": str(expected["scaling"]["max_instances"]),
        "run.googleapis.com/startup-cpu-boost": str(
            expected["startup_cpu_boost"]
        ).lower(),
        "run.googleapis.com/cpu-throttling": str(expected["cpu_idle"]).lower(),
    }
    if expected["direct_vpc"] is not None:
        direct_vpc = expected["direct_vpc"]
        revision_annotations.update(
            {
                "run.googleapis.com/network-interfaces": json.dumps(
                    [
                        {
                            "network": direct_vpc["network"],
                            "subnetwork": direct_vpc["subnetwork"],
                            "tags": direct_vpc["tags"],
                        }
                    ]
                ),
                "run.googleapis.com/vpc-access-egress": direct_vpc["egress"],
            }
        )
    service_annotations = {
        "run.googleapis.com/ingress": expected["ingress"],
        "run.googleapis.com/iap-enabled": str(expected["iap_enabled"]).lower(),
    }
    return {
        "service": {
            "metadata": {"annotations": service_annotations},
            "status": {
                "url": expected["url"],
                "latestCreatedRevisionName": revision_name,
                "latestReadyRevisionName": revision_name,
                "conditions": [{"type": "Ready", "status": "True"}],
                "traffic": [
                    {
                        "revisionName": expected["name"] + "-00001-old",
                        "percent": 100,
                    }
                ],
            },
        },
        "policy": {
            "bindings": [
                {"role": "roles/run.invoker", "members": expected["invokers"]}
            ]
        },
        "revision": {
            "metadata": {"annotations": revision_annotations},
            "spec": {
                "serviceAccountName": expected["service_account"],
                "timeoutSeconds": expected["timeout_seconds"],
                "containerConcurrency": expected["container_concurrency"],
                "containers": [
                    {
                        "image": resolved["release"][expected["image_parameter"]],
                        "resources": {"limits": expected["resources"]},
                        "env": [
                            {"name": name, "value": value}
                            for name, value in expected["environment"].items()
                        ],
                        "startupProbe": {
                            "tcpSocket": {
                                "port": expected["startup_probe"]["port"]
                            },
                            "initialDelaySeconds": expected["startup_probe"][
                                "initial_delay_seconds"
                            ],
                            "timeoutSeconds": expected["startup_probe"][
                                "timeout_seconds"
                            ],
                            "periodSeconds": expected["startup_probe"][
                                "period_seconds"
                            ],
                            "failureThreshold": expected["startup_probe"][
                                "failure_threshold"
                            ],
                        },
                    }
                ],
            },
            "status": {
                "imageDigest": resolved["release"][expected["image_parameter"]],
                "conditions": [{"type": "Ready", "status": "True"}],
            },
        },
    }


class TargetServiceRunner:
    def __init__(self, expected, provider):
        self.expected = expected
        self.provider = provider
        self.calls = []

    def json(self, *args, optional=False):
        self.calls.append((args, optional))
        if args[:3] == ("run", "services", "describe"):
            return self.provider["service"]
        if args[:3] == ("run", "services", "get-iam-policy"):
            return self.provider["policy"]
        if args[:3] == ("run", "revisions", "describe"):
            return self.provider["revision"]
        raise AssertionError(args)


def test_staged_service_readback_uses_only_three_targeted_provider_reads():
    resolved = contract()
    expected = next(
        row
        for row in resolved["cloud_run"]["services"]
        if row["name"] == "aureon-trade-controller"
    )
    runner = TargetServiceRunner(
        expected, staged_provider_fixture(resolved, expected)
    )

    assert stage.provider_service_staged_exact(
        resolved, runner, expected["name"]
    ) is True
    assert len(runner.calls) == 3
    assert [call[0][:3] for call in runner.calls] == [
        ("run", "services", "describe"),
        ("run", "services", "get-iam-policy"),
        ("run", "revisions", "describe"),
    ]
    assert all(call[1] is True for call in runner.calls)


@pytest.mark.parametrize(
    "mutate",
    (
        lambda provider, revision: provider["revision"]["status"].update(
            imageDigest="wrong-image"
        ),
        lambda provider, revision: provider["revision"]["spec"]["containers"][
            0
        ]["env"].append({"name": "UNREVIEWED", "value": "1"}),
        lambda provider, revision: provider["policy"]["bindings"][0][
            "members"
        ].append("allUsers"),
        lambda provider, revision: provider["service"]["status"].update(
            traffic=[{"revisionName": revision, "percent": 100}]
        ),
    ),
)
def test_staged_service_readback_fails_closed_on_execution_surface_drift(mutate):
    resolved = contract()
    expected = next(
        row
        for row in resolved["cloud_run"]["services"]
        if row["name"] == "aureon-trade-controller"
    )
    revision = expected["name"] + "-r" + REVISION[:12]
    provider = deepcopy(staged_provider_fixture(resolved, expected))
    mutate(provider, revision)
    runner = TargetServiceRunner(expected, provider)

    assert stage.provider_service_staged_exact(
        resolved, runner, expected["name"]
    ) is False
    assert len(runner.calls) == 3


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
