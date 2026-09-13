"""Render or execute Aureon's exact zero-traffic Cloud Run revision plan.

The default ``plan`` command is offline and deterministic. ``stage`` requires
the exact plan file and its SHA-256 acknowledgement. It can create revisions,
but every deploy contains ``--no-traffic`` and this tool has no promotion
operation.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
import re
import subprocess
from typing import Any, Callable, Mapping

from authority_commission import (
    CommissionError,
    Gcloud as AuditGcloud,
    audit_snapshot,
    canonical,
    capture_cloud_run_service,
    load_contract,
    resolve_contract,
    sha256,
    validate_immutable_image_build_receipt,
    write_receipt,
)


SCHEMA = "aureon.gcp.cloud-run-no-traffic-plan.v1"
STAGE_SCHEMA = "aureon.gcp.cloud-run-no-traffic-stage-receipt.v1"
_HEX64 = re.compile(r"[0-9a-f]{64}")


class StageError(RuntimeError):
    """Stable stage failure without provider output."""


def _environment_flag(environment: Mapping[str, str]) -> str:
    if not environment or any(
        not isinstance(key, str)
        or not isinstance(value, str)
        or re.fullmatch(r"[A-Z_][A-Z0-9_]*", key) is None
        or any(character in key + value for character in "\r\n\x00")
        for key, value in environment.items()
    ):
        raise StageError("cloud_run_environment_invalid")
    joined_values = "".join(key + environment[key] for key in sorted(environment))
    delimiter = "__AUREON_ENV_BOUNDARY__"
    if delimiter in joined_values:
        delimiter += sha256(canonical(dict(environment)))[:16]
    return f"--set-env-vars=^{delimiter}^" + delimiter.join(
        f"{key}={environment[key]}" for key in sorted(environment)
    )


def _probe_flag(probe: Mapping[str, Any]) -> str:
    if probe.get("kind") != "tcp":
        raise StageError("cloud_run_startup_probe_invalid")
    return "--startup-probe=" + ",".join(
        (
            f"tcpSocket.port={probe['port']}",
            f"initialDelaySeconds={probe['initial_delay_seconds']}",
            f"timeoutSeconds={probe['timeout_seconds']}",
            f"periodSeconds={probe['period_seconds']}",
            f"failureThreshold={probe['failure_threshold']}",
        )
    )


def service_command(
    contract: Mapping[str, Any], service: Mapping[str, Any]
) -> tuple[str, ...]:
    """Return one complete, no-traffic ``gcloud run deploy`` argument list."""

    revision_suffix = "r" + contract["release"]["source_revision"][:12]
    args = [
        "run",
        "deploy",
        service["name"],
        "--region=" + contract["region"],
        "--image=" + contract["release"][service["image_parameter"]],
        "--service-account=" + service["service_account"],
        "--ingress=" + service["ingress"],
        "--port=8080",
        "--timeout=" + str(service["timeout_seconds"]) + "s",
        "--concurrency=" + str(service["container_concurrency"]),
        "--cpu=" + service["resources"]["cpu"],
        "--memory=" + service["resources"]["memory"],
        "--min-instances=" + str(service["scaling"]["min_instances"]),
        "--max-instances=" + str(service["scaling"]["max_instances"]),
        "--cpu-boost" if service["startup_cpu_boost"] else "--no-cpu-boost",
        "--cpu-throttling" if service["cpu_idle"] else "--no-cpu-throttling",
        _probe_flag(service["startup_probe"]),
        _environment_flag(service["environment"]),
        "--iap" if service["iap_enabled"] else "--no-iap",
        "--no-traffic",
        "--revision-suffix=" + revision_suffix,
    ]
    direct_vpc = service["direct_vpc"]
    if direct_vpc is None:
        args.extend(("--clear-network", "--clear-vpc-connector"))
    else:
        args.extend(
            (
                "--network=" + direct_vpc["network"],
                "--subnet=" + direct_vpc["subnetwork"],
                "--vpc-egress=" + direct_vpc["egress"],
                "--clear-vpc-connector",
            )
        )
        if direct_vpc["tags"]:
            args.append("--network-tags=" + ",".join(direct_vpc["tags"]))
        else:
            args.append("--clear-network-tags")
    return tuple(args)


def build_plan(
    contract: Mapping[str, Any], image_build_receipt_sha256: str
) -> dict[str, Any]:
    rows = []
    for service in contract["cloud_run"]["services"]:
        args = service_command(contract, service)
        if "--no-traffic" not in args or any(
            item.startswith("--to-") for item in args
        ):
            raise StageError("traffic_mutation_flag_forbidden")
        rows.append(
            {
                "service": service["name"],
                "revision": service["name"]
                + "-r"
                + contract["release"]["source_revision"][:12],
                "image": contract["release"][service["image_parameter"]],
                "argv": list(args),
                "argv_sha256": sha256(canonical(list(args))),
            }
        )
    return {
        "schema": SCHEMA,
        "project": contract["project"],
        "region": contract["region"],
        "source_revision": contract["release"]["source_revision"],
        "contract_sha256": sha256(canonical(contract)),
        "immutable_image_build_receipt_sha256": image_build_receipt_sha256,
        "services": rows,
        "all_revisions_no_traffic": True,
        "traffic_mutation_available": False,
        "release_authority": False,
        "mutation_authority": False,
    }


def _progress_receipt(
    plan: Mapping[str, Any],
    *,
    status: str,
    completed: list[str],
    in_flight_service: str | None,
    error_code: str | None,
) -> dict[str, Any]:
    return {
        "schema": STAGE_SCHEMA,
        "status": status,
        "recorded_at": datetime.now(UTC).isoformat(),
        "project": plan["project"],
        "source_revision": plan["source_revision"],
        "contract_sha256": plan["contract_sha256"],
        "plan_sha256": sha256(canonical(plan)),
        "immutable_image_build_receipt_sha256": plan[
            "immutable_image_build_receipt_sha256"
        ],
        "services": list(completed),
        "in_flight_service": in_flight_service,
        "error_code": error_code,
        "all_revisions_requested_no_traffic": True,
        "provider_attestation_required": True,
        "cloud_run_traffic_changed": False,
        "secret_values_recorded": False,
        "release_authority": False,
        "mutation_authority": False,
    }


def _load_recovery(path: Path, plan: Mapping[str, Any]) -> list[str]:
    """Load a durable prefix of provider-attested work from an earlier attempt."""

    if not path.exists():
        return []
    if not path.is_absolute() or path.is_symlink() or not path.is_file():
        raise StageError("stage_recovery_receipt_invalid")
    try:
        value = json.loads(path.read_bytes())
    except (OSError, ValueError, TypeError, UnicodeError) as exc:
        raise StageError("stage_recovery_receipt_invalid") from exc
    required = _progress_receipt(
        plan,
        status="staging",
        completed=[],
        in_flight_service=None,
        error_code=None,
    )
    volatile = {"status", "recorded_at", "services", "in_flight_service", "error_code"}
    if (
        not isinstance(value, Mapping)
        or set(value) != set(required)
        or any(value.get(key) != expected for key, expected in required.items() if key not in volatile)
        or value.get("status")
        not in {
            "staging",
            "recovery_required",
            "commands_completed_pending_provider_attestation",
        }
    ):
        raise StageError("stage_recovery_receipt_invalid")
    names = [row["service"] for row in plan["services"]]
    completed = value.get("services")
    in_flight = value.get("in_flight_service")
    error_code = value.get("error_code")
    if (
        not isinstance(completed, list)
        or completed != names[: len(completed)]
        or any(not isinstance(name, str) for name in completed)
        or (
            in_flight is not None
            and (
                len(completed) >= len(names)
                or in_flight != names[len(completed)]
            )
        )
    ):
        raise StageError("stage_recovery_receipt_invalid")
    status = value["status"]
    if (
        (status == "recovery_required" and (
            in_flight is None
            or error_code
            not in {
                "cloud_run_stage_command_failed",
                "cloud_run_stage_provider_readback_failed",
                "cloud_run_stage_provider_readback_not_exact",
                "cloud_run_stage_prior_readback_not_exact",
            }
        ))
        or (status == "staging" and error_code is not None)
        or (
            status == "commands_completed_pending_provider_attestation"
            and (
                completed != names
                or in_flight is not None
                or error_code is not None
            )
        )
    ):
        raise StageError("stage_recovery_receipt_invalid")
    return list(completed)


def _service_staged_exact(
    contract: Mapping[str, Any], snapshot: Mapping[str, Any], name: str
) -> bool:
    actual = snapshot.get("cloud_run", {}).get(name)
    target_revision = name + "-r" + contract["release"]["source_revision"][:12]
    if (
        not isinstance(actual, Mapping)
        or actual.get("latest_created_revision") != target_revision
        or actual.get("latest_ready_revision") != target_revision
        or any(
            isinstance(row, Mapping) and row.get("revision") == target_revision
            for row in actual.get("traffic", [])
        )
    ):
        return False
    audit = audit_snapshot(
        contract,
        snapshot,
        allow_iam_extras=False,
        allow_vm_pending=True,
        cloud_run_mode="staged",
        allow_legacy_pending=True,
        allow_immutable_subscription_pending=True,
    )
    prefix = f"cloud_run.{name}."
    return not any(code.startswith(prefix) for code in audit["errors"])


def provider_service_staged_exact(
    contract: Mapping[str, Any], provider: AuditGcloud, name: str
) -> bool:
    expected = next(
        (
            row
            for row in contract["cloud_run"]["services"]
            if row["name"] == name
        ),
        None,
    )
    if expected is None:
        raise StageError("cloud_run_stage_service_not_in_contract")
    observed = capture_cloud_run_service(contract, provider, expected)
    snapshot: dict[str, Any] = {"cloud_run": {}}
    if observed is not None:
        snapshot["cloud_run"][name] = observed
    return _service_staged_exact(contract, snapshot, name)


def load_exact_plan(
    path: Path | None, expected: Mapping[str, Any], acknowledgement: str | None
) -> str:
    if (
        path is None
        or not path.is_absolute()
        or not path.is_file()
        or path.is_symlink()
    ):
        raise StageError("absolute_stage_plan_required")
    try:
        value = json.loads(path.read_bytes())
    except (OSError, ValueError, TypeError, UnicodeError) as exc:
        raise StageError("stage_plan_invalid") from exc
    if value != expected:
        raise StageError("stage_plan_binding_invalid")
    plan_hash = sha256(canonical(value))
    if acknowledgement != plan_hash:
        raise StageError("exact_stage_plan_acknowledgement_required")
    return plan_hash


def gcloud_apply(executable: str, project: str, args: tuple[str, ...]) -> None:
    try:
        result = subprocess.run(
            [executable, *args, "--project=" + project, "--quiet"],
            check=False,
            capture_output=True,
            text=True,
            timeout=1800,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise StageError("cloud_run_stage_command_failed") from exc
    if result.returncode:
        raise StageError("cloud_run_stage_command_failed")


def execute_plan(
    plan: Mapping[str, Any],
    *,
    executable: str,
    runner: Callable[[str, str, tuple[str, ...]], None] = gcloud_apply,
) -> list[str]:
    completed = []
    for row in plan["services"]:
        args = tuple(row["argv"])
        if "--no-traffic" not in args:
            raise StageError("traffic_mutation_flag_forbidden")
        runner(executable, plan["project"], args)
        completed.append(row["service"])
    return completed


def execute_resumable(
    plan: Mapping[str, Any],
    *,
    completed: list[str],
    executable: str,
    is_complete: Callable[[str], bool],
    progress: Callable[[str, list[str], str | None, str | None], None],
    runner: Callable[[str, str, tuple[str, ...]], None] = gcloud_apply,
) -> list[str]:
    """Resume an immutable stage using provider state after uncertain failures."""

    names = [row["service"] for row in plan["services"]]
    if completed != names[: len(completed)]:
        raise StageError("stage_recovery_receipt_invalid")
    done = list(completed)
    for name in done:
        try:
            still_exact = is_complete(name)
        except (CommissionError, StageError):
            still_exact = False
        if not still_exact:
            progress(
                "recovery_required",
                names[: names.index(name)],
                name,
                "cloud_run_stage_prior_readback_not_exact",
            )
            raise StageError("cloud_run_stage_prior_readback_not_exact")
    for row in plan["services"][len(done) :]:
        name = row["service"]
        args = tuple(row["argv"])
        if "--no-traffic" not in args:
            raise StageError("traffic_mutation_flag_forbidden")
        if is_complete(name):
            done.append(name)
            progress("staging", done, None, None)
            continue
        progress("staging", done, name, None)
        try:
            runner(executable, plan["project"], args)
        except (CommissionError, StageError):
            try:
                completed_at_provider = is_complete(name)
            except (CommissionError, StageError):
                completed_at_provider = False
            if completed_at_provider:
                done.append(name)
                progress("staging", done, None, None)
                continue
            progress("recovery_required", done, name, "cloud_run_stage_command_failed")
            raise StageError("cloud_run_stage_command_failed")
        try:
            completed_at_provider = is_complete(name)
        except (CommissionError, StageError):
            progress(
                "recovery_required",
                done,
                name,
                "cloud_run_stage_provider_readback_failed",
            )
            raise StageError("cloud_run_stage_provider_readback_failed")
        if not completed_at_provider:
            progress(
                "recovery_required",
                done,
                name,
                "cloud_run_stage_provider_readback_not_exact",
            )
            raise StageError("cloud_run_stage_provider_readback_not_exact")
        done.append(name)
        progress("staging", done, None, None)
    progress(
        "commands_completed_pending_provider_attestation", done, None, None
    )
    return done


def _resolved(args: argparse.Namespace) -> dict[str, Any]:
    return resolve_contract(
        load_contract(args.contract),
        source_revision=args.source_revision,
        authority_image=args.authority_image,
        public_entry_image=args.public_entry_image,
        supabase_project_ref=args.supabase_project_ref,
        supabase_owner_subject=args.supabase_owner_subject,
        supabase_owner_email_sha256=args.supabase_owner_email_sha256,
        iap_admin_email_sha256=args.iap_admin_email_sha256,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("plan", "stage"), nargs="?", default="plan")
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--authority-image", required=True)
    parser.add_argument("--public-entry-image", required=True)
    parser.add_argument("--supabase-project-ref", required=True)
    parser.add_argument("--supabase-owner-subject", required=True)
    parser.add_argument("--supabase-owner-email-sha256", required=True)
    parser.add_argument("--iap-admin-email-sha256", required=True)
    parser.add_argument("--plan", type=Path)
    parser.add_argument("--acknowledge-plan-sha256")
    parser.add_argument("--immutable-image-build-receipt", type=Path, required=True)
    parser.add_argument(
        "--acknowledge-immutable-image-build-receipt-sha256", required=True
    )
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--gcloud", default="gcloud")
    args = parser.parse_args(argv)
    try:
        contract = _resolved(args)
        image_receipt_hash, _, _ = validate_immutable_image_build_receipt(
            contract,
            args.immutable_image_build_receipt,
            args.acknowledge_immutable_image_build_receipt_sha256,
        )
        plan = build_plan(contract, image_receipt_hash)
        if args.command == "plan":
            write_receipt(args.receipt, plan)
            print(
                json.dumps(
                    {
                        "schema": SCHEMA,
                        "services": len(plan["services"]),
                        "plan_sha256": sha256(canonical(plan)),
                        "all_revisions_no_traffic": True,
                    },
                    sort_keys=True,
                )
            )
            return 0
        plan_hash = load_exact_plan(
            args.plan, plan, args.acknowledge_plan_sha256
        )
        if plan_hash != sha256(canonical(plan)):
            raise StageError("stage_plan_binding_invalid")
        completed = _load_recovery(args.receipt, plan)
        provider = AuditGcloud(args.gcloud, contract["project"])

        def is_complete(name: str) -> bool:
            return provider_service_staged_exact(contract, provider, name)

        def progress(
            status: str,
            done: list[str],
            in_flight: str | None,
            error_code: str | None,
        ) -> None:
            write_receipt(
                args.receipt,
                _progress_receipt(
                    plan,
                    status=status,
                    completed=done,
                    in_flight_service=in_flight,
                    error_code=error_code,
                ),
            )

        completed = execute_resumable(
            plan,
            completed=completed,
            executable=args.gcloud,
            is_complete=is_complete,
            progress=progress,
        )
        receipt = _progress_receipt(
            plan,
            status="commands_completed_pending_provider_attestation",
            completed=completed,
            in_flight_service=None,
            error_code=None,
        )
        write_receipt(args.receipt, receipt)
        print(
            json.dumps(
                {"schema": STAGE_SCHEMA, "status": receipt["status"]},
                sort_keys=True,
            )
        )
        return 0
    except (CommissionError, StageError) as exc:
        print(str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
