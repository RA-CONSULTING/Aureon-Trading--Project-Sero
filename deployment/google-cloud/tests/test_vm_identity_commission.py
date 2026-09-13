"""Offline tests for controlled existing-VM identity commissioning."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


MODULE = Path(__file__).resolve().parents[1] / "vm_identity_commission.py"
CONTRACT = Path(__file__).resolve().parents[1] / "trading-control/resource_contract.json"
spec = importlib.util.spec_from_file_location("vm_identity_commission", MODULE)
assert spec and spec.loader
identity = importlib.util.module_from_spec(spec)
spec.loader.exec_module(identity)


def contract():
    return json.loads(CONTRACT.read_text(encoding="utf-8"))


def current(service_account="old@aureon-trading.iam.gserviceaccount.com"):
    return {
        "name": "aureon-sero-20260906",
        "zone": "europe-west1-b",
        "status": "RUNNING",
        "machine_type": "n2-standard-8",
        "service_account": service_account,
        "scopes": ["https://www.googleapis.com/auth/cloud-platform"],
    }


def provider(value):
    return {
        "name": value["name"],
        "zone": "projects/1/zones/" + value["zone"],
        "status": value["status"],
        "machineType": "zones/europe-west1-b/machineTypes/"
        + value["machine_type"],
        "serviceAccounts": [
            {"email": value["service_account"], "scopes": value["scopes"]}
        ],
    }


class StatefulRunner:
    def __init__(self, resolved, *, fail_after=(), fail_before=()):
        self.resolved = resolved
        self.state = current()
        self.calls = []
        self.fail_after = list(fail_after)
        self.fail_before = list(fail_before)

    def describe(self, _instance, _zone):
        return provider(self.state)

    def apply(self, *args):
        operation = args[2]
        self.calls.append(operation)
        if operation in self.fail_before:
            self.fail_before.remove(operation)
            raise identity.IdentityCommissionError("gcloud_identity_operation_failed")
        if operation == "stop":
            self.state["status"] = "TERMINATED"
        elif operation == "set-service-account":
            vm = self.resolved["vm_workload_identity"]
            self.state["service_account"] = vm["attached_service_account"]
            self.state["scopes"] = sorted(vm["attached_oauth_scopes"])
        elif operation == "start":
            self.state["status"] = "RUNNING"
        if operation in self.fail_after:
            self.fail_after.remove(operation)
            raise identity.IdentityCommissionError("gcloud_identity_operation_failed")


def test_plan_and_apply_use_only_controlled_stop_attach_start(tmp_path):
    resolved = contract()
    plan = identity.build_plan(resolved, current())
    assert plan["identity_change_required"] is True
    assert plan["data_plane_roles_granted"] is False
    runner = StatefulRunner(resolved)
    operations, _observed = identity.apply_identity_resumable(
        resolved,
        runner,
        plan,
        identity.sha256(identity.canonical(plan)),
        (tmp_path / "receipt.json").resolve(),
        sleeper=lambda _seconds: None,
    )
    assert operations == ["stop", "set-service-account", "start"]
    assert runner.calls == ["stop", "set-service-account", "start"]


def test_exact_desired_identity_is_noop(tmp_path):
    resolved = contract()
    desired = resolved["vm_workload_identity"]["attached_service_account"]
    plan = identity.build_plan(resolved, current(desired))
    runner = StatefulRunner(resolved)
    runner.state = current(desired)
    assert plan["identity_change_required"] is False
    operations, _observed = identity.apply_identity_resumable(
        resolved,
        runner,
        plan,
        identity.sha256(identity.canonical(plan)),
        (tmp_path / "receipt.json").resolve(),
        sleeper=lambda _seconds: None,
    )
    assert operations == []
    assert runner.calls == []


@pytest.mark.parametrize("operation", ["stop", "set-service-account", "start"])
def test_uncertain_operation_resumes_from_provider_state(
    tmp_path, operation
):
    resolved = contract()
    plan = identity.build_plan(resolved, current())
    plan_hash = identity.sha256(identity.canonical(plan))
    receipt = (tmp_path / "identity-receipt.json").resolve()
    runner = StatefulRunner(resolved, fail_after=[operation])

    operations, observed = identity.apply_identity_resumable(
        resolved,
        runner,
        plan,
        plan_hash,
        receipt,
        sleeper=lambda _seconds: None,
    )

    assert operations == ["stop", "set-service-account", "start"]
    assert observed["status"] == "RUNNING"
    assert observed["service_account"] == resolved["vm_workload_identity"][
        "attached_service_account"
    ]
    progress = json.loads(identity.progress_path(receipt).read_text())
    assert progress["status"] == "passed"
    assert progress["phase"] == "complete"
    assert operation in progress["uncertain_operations"]
    assert progress["provider_readback"]["status"] == "RUNNING"
    assert progress["secret_values_recorded"] is False


def test_failed_identity_change_recovers_original_vm_then_resumes(
    tmp_path,
):
    resolved = contract()
    plan = identity.build_plan(resolved, current())
    plan_hash = identity.sha256(identity.canonical(plan))
    receipt = (tmp_path / "identity-receipt.json").resolve()
    runner = StatefulRunner(
        resolved,
        fail_before=["set-service-account", "set-service-account"],
    )

    with pytest.raises(
        identity.IdentityCommissionError,
        match="vm_identity_set_service_account_failed_vm_recovered_running",
    ):
        identity.apply_identity_resumable(
            resolved,
            runner,
            plan,
            plan_hash,
            receipt,
            sleeper=lambda _seconds: None,
        )
    failed = json.loads(identity.progress_path(receipt).read_text())
    assert failed["status"] == "recovered_running"
    assert failed["provider_readback"]["status"] == "RUNNING"
    assert failed["provider_readback"]["service_account"] == plan["current"][
        "service_account"
    ]
    assert failed["recovery_operations"] == ["start"]

    operations, observed = identity.apply_identity_resumable(
        resolved,
        runner,
        plan,
        plan_hash,
        receipt,
        sleeper=lambda _seconds: None,
    )
    assert operations == ["stop", "set-service-account", "start"]
    assert observed["status"] == "RUNNING"
    recovered = json.loads(identity.progress_path(receipt).read_text())
    assert recovered["status"] == "passed"
    assert recovered["resume_count"] == 1
    assert recovered["recovery_operations"] == ["start"]


def test_resume_after_process_interruption_continues_from_stopped_vm(tmp_path):
    resolved = contract()
    plan = identity.build_plan(resolved, current())
    plan_hash = identity.sha256(identity.canonical(plan))
    receipt = (tmp_path / "identity-receipt.json").resolve()
    progress = identity.progress_path(receipt)
    runner = StatefulRunner(resolved)
    runner.state["status"] = "TERMINATED"
    history = {
        "attempted_operations": ["stop"],
        "uncertain_operations": [],
        "recovery_operations": [],
        "resume_count": 0,
    }
    identity._write_progress(
        progress,
        resolved,
        plan_hash,
        history,
        status="in_progress",
        phase="stop_requested",
        completed=[],
        observed=current(),
    )

    operations, observed = identity.apply_identity_resumable(
        resolved,
        runner,
        plan,
        plan_hash,
        receipt,
        sleeper=lambda _seconds: None,
    )
    assert operations == ["stop", "set-service-account", "start"]
    assert runner.calls == ["set-service-account", "start"]
    assert observed["status"] == "RUNNING"
    completed = json.loads(progress.read_text())
    assert completed["status"] == "passed"
    assert completed["resume_count"] == 1


def test_unrecoverable_start_failure_records_stopped_provider_state(tmp_path):
    resolved = contract()
    plan = identity.build_plan(resolved, current())
    plan_hash = identity.sha256(identity.canonical(plan))
    receipt = (tmp_path / "identity-receipt.json").resolve()
    runner = StatefulRunner(
        resolved,
        fail_before=["start", "start", "start"],
    )

    with pytest.raises(
        identity.IdentityCommissionError,
        match="vm_identity_start_failed_recovery_required",
    ):
        identity.apply_identity_resumable(
            resolved,
            runner,
            plan,
            plan_hash,
            receipt,
            sleeper=lambda _seconds: None,
        )
    progress = json.loads(identity.progress_path(receipt).read_text())
    assert progress["status"] == "recovery_required"
    assert progress["provider_state_known"] is True
    assert progress["vm_running"] is False
    assert progress["provider_readback"]["status"] == "TERMINATED"
    assert progress["last_error_code"] == "vm_identity_start_failed"


def test_acknowledged_plan_can_be_loaded_after_provider_state_changes(tmp_path):
    resolved = contract()
    plan = identity.build_plan(resolved, current())
    path = (tmp_path / "plan.json").resolve()
    plan_hash = identity.write_json(path, plan)
    observed, observed_hash = identity.load_commission_plan(
        path, resolved, plan_hash
    )
    assert observed == plan
    assert observed_hash == plan_hash


def test_apply_cli_writes_final_and_durable_progress_receipts(
    tmp_path, monkeypatch, capsys
):
    resolved = contract()
    plan = identity.build_plan(resolved, current())
    plan_path = (tmp_path / "plan.json").resolve()
    plan_hash = identity.write_json(plan_path, plan)
    receipt = (tmp_path / "receipt.json").resolve()
    runner = StatefulRunner(resolved, fail_after=["stop"])
    monkeypatch.setattr(identity, "Gcloud", lambda *_args: runner)

    assert identity.main(
        [
            "apply",
            "--contract=" + str(CONTRACT.resolve()),
            "--plan=" + str(plan_path),
            "--acknowledge-plan-sha256=" + plan_hash,
            "--acknowledge-interruption=stop-set-service-account-start:"
            "aureon-sero-20260906",
            "--receipt=" + str(receipt),
        ]
    ) == 0
    assert json.loads(receipt.read_text())["status"] == "passed"
    progress = json.loads(identity.progress_path(receipt).read_text())
    assert progress["status"] == "passed"
    assert progress["uncertain_operations"] == ["stop"]
    assert json.loads(capsys.readouterr().out)["status"] == "passed"
