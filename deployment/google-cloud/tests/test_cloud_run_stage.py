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
    serving_revision = expected["name"] + "-00001-old"
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
                "latestReadyRevisionName": serving_revision,
                "conditions": [{"type": "Ready", "status": "True"}],
                "traffic": [
                    {
                        "revisionName": serving_revision,
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
            "metadata": {
                "name": revision_name,
                "annotations": revision_annotations,
            },
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
                "conditions": [
                    {"type": "Ready", "status": "True", "reason": "Retired"},
                    {"type": "Active", "status": "False", "reason": "Retired"},
                ],
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


def test_cloud_run_capture_rejects_unknown_revision_mode_before_provider_read():
    resolved = contract()
    expected = resolved["cloud_run"]["services"][0]
    runner = TargetServiceRunner(
        expected, staged_provider_fixture(resolved, expected)
    )

    with pytest.raises(
        commission.CommissionError, match="cloud_run_capture_mode_invalid"
    ):
        commission.capture_cloud_run_service(
            resolved, runner, expected, "unknown"
        )
    assert runner.calls == []


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
    assert runner.calls[2][0][3] == (
        expected["name"] + "-r" + REVISION[:12]
    )


def test_serving_capture_still_inspects_latest_ready_revision():
    resolved = contract()
    expected = next(
        row
        for row in resolved["cloud_run"]["services"]
        if row["name"] == "aureon-trade-controller"
    )
    provider = staged_provider_fixture(resolved, expected)
    latest_created = provider["service"]["status"]["latestCreatedRevisionName"]
    latest_ready = provider["service"]["status"]["latestReadyRevisionName"]
    provider["revision"]["metadata"]["name"] = latest_ready
    runner = TargetServiceRunner(expected, provider)

    observed = commission.capture_cloud_run_service(resolved, runner, expected)

    assert observed is not None
    assert observed["latest_created_revision"] == latest_created
    assert observed["latest_ready_revision"] == latest_ready
    assert observed["inspected_revision"] == latest_ready
    assert runner.calls[2][0][3] == latest_ready
    snapshot = {"cloud_run": {expected["name"]: observed}}
    audit = commission.audit_snapshot(
        resolved,
        snapshot,
        allow_vm_pending=True,
        allow_legacy_pending=True,
        allow_immutable_subscription_pending=True,
    )
    assert (
        f"cloud_run.{expected['name']}.latest_ready_revision"
        in audit["errors"]
    )


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
        lambda provider, revision: provider["revision"]["metadata"].update(
            name=revision + "-wrong"
        ),
        lambda provider, revision: provider["revision"]["status"].update(
            conditions=[
                {"type": "Ready", "status": "False", "reason": "Retired"},
                {"type": "Active", "status": "False", "reason": "Retired"},
            ]
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


def test_direct_vpc_command_omits_only_provider_proven_clear_connector_noop():
    resolved = contract()
    plan = stage.build_plan(resolved, "f" * 64)
    row = next(
        item for item in plan["services"]
        if item["service"] == "aureon-trade-executor"
    )
    expected = next(
        item for item in resolved["cloud_run"]["services"]
        if item["name"] == row["service"]
    )
    provider = staged_provider_fixture(resolved, expected)
    latest_created = provider["service"]["status"]["latestCreatedRevisionName"]
    runner = TargetServiceRunner(expected, provider)

    command, omission = stage.provider_safe_service_command(
        resolved, runner, row
    )

    original = tuple(row["argv"])
    assert stage._CLEAR_VPC_CONNECTOR in original
    assert stage._CLEAR_VPC_CONNECTOR not in command
    assert command == tuple(
        arg for arg in original if arg != stage._CLEAR_VPC_CONNECTOR
    )
    assert "--no-traffic" in command
    assert "--revision-suffix=r" + REVISION[:12] in command
    assert omission == {
        "service": row["service"],
        "omitted_argument": stage._CLEAR_VPC_CONNECTOR,
        "provider_connector_absent": True,
        "provider_direct_vpc_exact": True,
    }
    assert runner.calls[2][0][3] == latest_created


def test_direct_vpc_command_requires_explicit_connector_migration():
    resolved = contract()
    plan = stage.build_plan(resolved, "f" * 64)
    row = next(
        item for item in plan["services"]
        if item["service"] == "aureon-trade-executor"
    )
    expected = next(
        item for item in resolved["cloud_run"]["services"]
        if item["name"] == row["service"]
    )
    provider = staged_provider_fixture(resolved, expected)
    provider["revision"]["metadata"]["annotations"][
        "run.googleapis.com/vpc-access-connector"
    ] = "legacy-connector"
    runner = TargetServiceRunner(expected, provider)

    with pytest.raises(
        stage.StageError,
        match="cloud_run_stage_vpc_connector_migration_required",
    ):
        stage.provider_safe_service_command(resolved, runner, row)


def test_direct_vpc_command_rejects_unbound_latest_created_revision():
    resolved = contract()
    plan = stage.build_plan(resolved, "f" * 64)
    row = next(
        item for item in plan["services"]
        if item["service"] == "aureon-trade-executor"
    )
    expected = next(
        item for item in resolved["cloud_run"]["services"]
        if item["name"] == row["service"]
    )
    provider = staged_provider_fixture(resolved, expected)
    provider["revision"]["metadata"]["name"] = provider["service"]["status"][
        "latestReadyRevisionName"
    ]
    runner = TargetServiceRunner(expected, provider)

    with pytest.raises(
        stage.StageError, match="cloud_run_stage_network_readback_not_exact"
    ):
        stage.provider_safe_service_command(resolved, runner, row)


def test_direct_vpc_command_fails_closed_on_network_drift_or_provider_error():
    resolved = contract()
    plan = stage.build_plan(resolved, "f" * 64)
    row = next(
        item for item in plan["services"]
        if item["service"] == "aureon-trade-executor"
    )
    expected = next(
        item for item in resolved["cloud_run"]["services"]
        if item["name"] == row["service"]
    )
    provider = staged_provider_fixture(resolved, expected)
    interfaces = json.loads(
        provider["revision"]["metadata"]["annotations"][
            "run.googleapis.com/network-interfaces"
        ]
    )
    interfaces[0]["network"] = "wrong-network"
    provider["revision"]["metadata"]["annotations"][
        "run.googleapis.com/network-interfaces"
    ] = json.dumps(interfaces)
    runner = TargetServiceRunner(expected, provider)
    with pytest.raises(
        stage.StageError, match="cloud_run_stage_network_readback_not_exact"
    ):
        stage.provider_safe_service_command(resolved, runner, row)

    class ErrorRunner:
        def json(self, *_args, **_kwargs):
            raise commission.CommissionError("gcloud_command_failed")

    with pytest.raises(
        stage.StageError, match="cloud_run_stage_network_readback_not_exact"
    ):
        stage.provider_safe_service_command(resolved, ErrorRunner(), row)


def test_private_ranges_direct_vpc_command_bypasses_workaround():
    resolved = contract()
    plan = stage.build_plan(resolved, "f" * 64)
    row = next(
        item for item in plan["services"]
        if item["service"] == "aureon-fusion-web"
    )

    class NoReadRunner:
        def json(self, *_args, **_kwargs):
            raise AssertionError("provider read was not required")

    command, omission = stage.provider_safe_service_command(
        resolved, NoReadRunner(), row
    )
    assert command == tuple(row["argv"])
    assert stage._CLEAR_VPC_CONNECTOR in command
    assert "--vpc-egress=private-ranges-only" in command
    assert omission is None


def test_absent_all_traffic_service_creation_keeps_original_command():
    resolved = contract()
    plan = stage.build_plan(resolved, "f" * 64)
    row = next(
        item for item in plan["services"]
        if item["service"] == "aureon-trade-executor"
    )
    expected = next(
        item for item in resolved["cloud_run"]["services"]
        if item["name"] == row["service"]
    )
    provider = staged_provider_fixture(resolved, expected)
    provider["service"] = None
    runner = TargetServiceRunner(expected, provider)

    command, omission = stage.provider_safe_service_command(
        resolved, runner, row
    )
    assert command == tuple(row["argv"])
    assert stage._CLEAR_VPC_CONNECTOR in command
    assert "--vpc-egress=all-traffic" in command
    assert omission is None
    assert len(runner.calls) == 1


def test_service_without_direct_vpc_keeps_reviewed_clear_flags_without_readback():
    resolved = contract()
    plan = stage.build_plan(resolved, "f" * 64)
    row = next(
        item for item in plan["services"]
        if item["service"] == "aureon-trade-controller"
    )

    class NoReadRunner:
        def json(self, *_args, **_kwargs):
            raise AssertionError("provider read was not required")

    command, omission = stage.provider_safe_service_command(
        resolved, NoReadRunner(), row
    )
    assert command == tuple(row["argv"])
    assert stage._CLEAR_VPC_CONNECTOR in command
    assert "--clear-network" in command
    assert omission is None


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
    assert stage._load_recovery(path, plan) == ([], [])
    progress["immutable_image_build_receipt_sha256"] = "0" * 64
    path.write_text(json.dumps(progress), encoding="utf-8")
    with pytest.raises(stage.StageError, match="recovery_receipt_invalid"):
        stage._load_recovery(path, plan)


def test_recovery_receipt_preserves_safe_noop_omission_and_accepts_legacy_shape(
    tmp_path,
):
    plan = stage.build_plan(contract(), "f" * 64)
    names = [row["service"] for row in plan["services"]]
    target = "aureon-trade-executor"
    completed = names[: names.index(target)]
    omission = {
        "service": target,
        "omitted_argument": stage._CLEAR_VPC_CONNECTOR,
        "provider_connector_absent": True,
        "provider_direct_vpc_exact": True,
    }
    progress = stage._progress_receipt(
        plan,
        status="recovery_required",
        completed=completed,
        in_flight_service=target,
        error_code="cloud_run_stage_command_failed",
        provider_proven_noop_omissions=[omission],
    )
    path = (tmp_path / "noop-progress.json").resolve()
    path.write_text(json.dumps(progress), encoding="utf-8")

    assert stage._load_recovery(path, plan) == (completed, [omission])

    progress.pop("provider_proven_noop_omissions")
    path.write_text(json.dumps(progress), encoding="utf-8")
    assert stage._load_recovery(path, plan) == (completed, [])
