"""Audit and explicitly commission Aureon's Google Cloud authority boundary.

``audit`` is read-only. ``apply`` changes only declared identities, Pub/Sub
resources and IAM. It never deploys an image, changes traffic, activates a
release, reads a secret payload or places an order. Resource preparation,
zero-traffic revision attestation, subscription replacement, legacy retirement
and strict finalization are separate fail-closed phases. Every mutation is
followed by provider readback and receipts contain names and hashes, never
credentials or tokens.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shlex
import subprocess
import tempfile
from typing import Any, Iterable, Mapping, Protocol


HERE = Path(__file__).resolve().parent
DEFAULT_CONTRACT = HERE / "resource_contract.json"
CONTRACT_SCHEMA = "aureon.cloud-trading-authority-resources.v3"
RECEIPT_SCHEMA = "aureon.cloud-trading-authority-commission-receipt.v1"
LEGACY_RETIREMENT_PROGRESS_SCHEMA = (
    "aureon.gcp.pubsub-legacy-retirement-progress.v1"
)
_REVISION = re.compile(r"[0-9a-f]{40}")
_DIGEST_IMAGE = re.compile(
    r"[a-z0-9-]+-docker\.pkg\.dev/[a-z0-9-]+/[A-Za-z0-9._-]+/"
    r"[A-Za-z0-9._-]+@sha256:[0-9a-f]{64}"
)
_UUID = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-"
    r"[89ab][0-9a-f]{3}-[0-9a-f]{12}"
)
_HEX64 = re.compile(r"[0-9a-f]{64}")
_SUPABASE_PROJECT_REF = re.compile(r"[a-z0-9]{20}")
_BUCKET = re.compile(r"[a-z0-9][a-z0-9._-]{1,61}[a-z0-9]")
VM_READBACK_ENVIRONMENT_KEYS = frozenset(
    {
        "AUREON_GOOGLE_TOKEN_FILE",
        "AUREON_VM_TOKEN_BROKER_REQUIRED",
        "AUREON_GCP_PROJECT_NUMBER",
        "AUREON_SUPABASE_OWNER_SUBJECT",
        "AUREON_SUPABASE_OWNER_EMAIL_SHA256",
        "AUREON_IAP_ADMIN_EMAIL_SHA256",
    }
)
DATA_ROLES = frozenset(
    {
        "roles/pubsub.publisher",
        "roles/pubsub.subscriber",
        "roles/secretmanager.secretAccessor",
        "roles/cloudkms.signerVerifier",
        "roles/cloudkms.publicKeyViewer",
        "roles/datastore.user",
        "roles/datastore.viewer",
        "roles/datastore.owner",
    }
)


class CommissionError(RuntimeError):
    """A stable commissioning failure without provider response text."""


class Runner(Protocol):
    def json(self, *args: str, optional: bool = False) -> Any: ...
    def text(self, *args: str) -> str: ...
    def apply(self, *args: str) -> None: ...


def canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
    ).encode("ascii")


def sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def load_contract(path: Path = DEFAULT_CONTRACT) -> dict[str, Any]:
    try:
        value = json.loads(path.read_bytes())
    except (OSError, ValueError, TypeError, UnicodeError) as exc:
        raise CommissionError("resource_contract_invalid") from exc
    if not isinstance(value, dict) or value.get("schema") != CONTRACT_SCHEMA:
        raise CommissionError("resource_contract_invalid")
    periodic = value.get("periodic_readiness")
    if not isinstance(periodic, dict) or periodic != {
        "activation_document": "aureon_trade_attestations/current_probe",
        "refresh_document": "aureon_trade_attestations/current_readiness",
        "interval_seconds": 120,
        "maximum_age_seconds": 300,
        "provider_deadline_seconds": 18,
        "worker_timeout_seconds": 120,
        "maximum_allowance_usd": 5,
        "executor_signing_key": "aureon-executor-signing",
        "receipt_signing_key": "aureon-receipt-signing",
        "release_binding": (
            "exact_controller_generation_request_event_expiry_revision_"
            "and_signed_state_digest"
        ),
        "release_authority": False,
        "mutation_authority": False,
    }:
        raise CommissionError("periodic_readiness_contract_changed")
    _validate_contract_topology(value)
    return value


def _validate_contract_topology(value: Mapping[str, Any]) -> None:
    if (
        value.get("project") != "aureon-trading"
        or value.get("project_number") != "4435775023"
        or value.get("region") != "europe-west1"
        or value.get("zone") != "europe-west1-b"
        or value.get("release_authority") != "controller_signed_state"
    ):
        raise CommissionError("resource_contract_identity_invalid")
    commissioning = value.get("commissioning")
    if (
        not isinstance(commissioning, Mapping)
        or commissioning.get("phase_order")
        != [
            "immutable-image-build",
            "vm-release-prepare-and-broker-bootstrap",
            "vm-broker-identity-attachment",
            "resource-prepare",
            "zero-traffic-revision-stage",
            "subscription-replacement",
            "legacy-retirement",
            "staged-revision-attestation",
            "vm-release-and-reboot-readback",
            "external-reviewed-traffic-promotion",
            "finalize",
        ]
        or commissioning.get(
            "old_union_cleanup_requires_broker_identity_readback"
        )
        is not True
        or commissioning.get("traffic_promotion_is_external_reviewed_operation")
        is not True
        or commissioning.get("resource_prepare_deferrals")
        != [
            "cloud_run_revision",
            "vm_release_readback",
            "immutable_subscription_replacement",
            "legacy_subscription_retirement",
            "destructive_iam_cleanup_until_broker_identity_attached",
        ]
        or commissioning.get("legacy_retirement_phase_receipt_schema")
        != "aureon.gcp.pubsub-legacy-retirement-phase-receipt.v1"
        or commissioning.get("legacy_retirement_progress_receipt_schema")
        != LEGACY_RETIREMENT_PROGRESS_SCHEMA
        or commissioning.get("release_authority") is not False
        or commissioning.get("mutation_authority") is not False
    ):
        raise CommissionError("commissioning_phase_contract_invalid")
    services = value.get("cloud_run", {}).get("services")
    expected_names = {
        "aureon-fusion-web", "aureon-fusion-operator",
        "aureon-trade-controller", "aureon-trade-review",
        "aureon-trade-dispatch", "aureon-trade-executor",
        "aureon-trade-receipt",
    }
    if (
        not isinstance(services, list)
        or {row.get("name") for row in services if isinstance(row, dict)} != expected_names
        or any(row.get("timeout_seconds") != (90 if row["name"].startswith("aureon-fusion-") else 120) for row in services)
    ):
        raise CommissionError("cloud_run_contract_invalid")
    by_name = {row["name"]: row for row in services}
    web_environment = by_name["aureon-fusion-web"].get("environment", {})
    recovery_environment = by_name["aureon-fusion-operator"].get(
        "environment", {}
    )
    if (
        "AUREON_ALLOWED_USER_EMAILS" in json.dumps(value)
        or "AUREON_IAP_ADMIN_EMAIL_SHA256" in web_environment
        or recovery_environment.get("AUREON_IAP_ADMIN_EMAIL_SHA256")
        != "${IAP_ADMIN_EMAIL_SHA256}"
        or value.get("release", {}).get("supabase_owner_provider_receipt", {}).get(
            "plaintext_email_forbidden"
        )
        is not True
    ):
        raise CommissionError("plaintext_owner_identity_contract_invalid")
    pushes = value.get("pubsub", {}).get("push_subscriptions")
    if not isinstance(pushes, list) or len(pushes) != 5:
        raise CommissionError("pubsub_contract_invalid")
    for row in pushes:
        if (
            row.get("push_endpoint") != row.get("oidc_audience", "") + "/process"
            or row.get("ack_deadline_seconds") != 120
            or not row.get("oidc_service_account")
        ):
            raise CommissionError("pubsub_push_contract_invalid")
    vm = value.get("vm_workload_identity")
    vm_receipt = vm.get("release_readback_receipt", {}) if isinstance(vm, dict) else {}
    reboot_receipt = (
        vm.get("reboot_continuity_receipt", {})
        if isinstance(vm, dict)
        else {}
    )
    if (
        not isinstance(vm, dict)
        or vm.get("only_metadata_unit") != "aureon-cloud-token-broker.service"
        or vm.get("attached_service_account")
        != "aureon-vm-token-broker@aureon-trading.iam.gserviceaccount.com"
        or vm.get("direct_metadata_workload_access_is_production_blocker") is not True
        or vm.get("public_bridge", {}).get("plaintext_identity_forbidden")
        is not True
        or vm.get("public_bridge", {}).get("certificate_path")
        != "/etc/aureon-public/bridge-cert.pem"
        or vm.get("public_bridge", {}).get("certificate_receipt_schema")
        != "aureon.gcp.vm-public-bridge-certificate-receipt.v1"
        or vm.get("public_bridge", {}).get("required_ip_sans")
        != ["10.40.0.2"]
        or vm.get("public_bridge", {}).get(
            "minimum_remaining_validity_seconds"
        )
        != 86_400
        or vm.get("public_bridge", {}).get("private_key_export_forbidden")
        is not True
        or vm_receipt
        != {
            "schema": "aureon.gcp.vm-release-readback.v1",
            "maximum_age_seconds": 900,
            "exact_raw_sha256_acknowledgement_required": True,
            "required_status": "passed",
            "required_attached_oauth_scopes": [
                "https://www.googleapis.com/auth/cloud-platform"
            ],
            "required_loopback_roles": {
                "operator": "aureon-cloud-operator.service",
                "ui-gateway": "aureon-cloud-ui.service",
            },
            "required_controlled_restart": "passed",
            "required_reboot_validation": (
                "pending_separate_cutover_evidence"
            ),
            "minimum_token_validity_seconds": 120,
            "maximum_token_lifetime_seconds": 1860,
            "secret_values_forbidden": True,
        }
        or reboot_receipt
        != {
            "schema": "aureon.gcp.vm-reboot-continuity.v1",
            "maximum_age_seconds": 900,
            "exact_raw_sha256_acknowledgement_required": True,
            "must_bind_vm_release_receipt": True,
            "required_status": "passed",
            "required_vm_status": "RUNNING",
            "required_loopback_roles": {
                "operator": "aureon-cloud-operator.service",
                "ui-gateway": "aureon-cloud-ui.service",
                "public-bridge": "aureon-public-bridge.service",
            },
            "boot_id_must_change": True,
            "secret_values_forbidden": True,
        }
    ):
        raise CommissionError("vm_broker_contract_invalid")


def resolve_contract(
    value: Mapping[str, Any],
    *,
    source_revision: str,
    authority_image: str,
    public_entry_image: str,
    supabase_project_ref: str,
    supabase_owner_subject: str,
    supabase_owner_email_sha256: str,
    iap_admin_email_sha256: str,
) -> dict[str, Any]:
    if _REVISION.fullmatch(source_revision or "") is None:
        raise CommissionError("source_revision_invalid")
    if _DIGEST_IMAGE.fullmatch(authority_image or "") is None:
        raise CommissionError("authority_image_digest_invalid")
    if _DIGEST_IMAGE.fullmatch(public_entry_image or "") is None:
        raise CommissionError("public_entry_image_digest_invalid")
    release = value["release"]
    for supplied, repository, reason in (
        (authority_image, release["authority_image_repository"], "authority_image_repository_mismatch"),
        (public_entry_image, release["public_entry_image_repository"], "public_entry_image_repository_mismatch"),
    ):
        if supplied.split("@", 1)[0] != repository:
            raise CommissionError(reason)
    project_ref = str(supabase_project_ref or "").strip().lower()
    subject = str(supabase_owner_subject or "").strip().lower()
    email_hash = str(supabase_owner_email_sha256 or "").strip().lower()
    iap_email_hash = str(iap_admin_email_sha256 or "").strip().lower()
    if (
        _SUPABASE_PROJECT_REF.fullmatch(project_ref) is None
        or _UUID.fullmatch(subject) is None
        or _HEX64.fullmatch(email_hash) is None
        or _HEX64.fullmatch(iap_email_hash) is None
    ):
        raise CommissionError("supabase_owner_provider_binding_invalid")
    replacements = {
        "${SOURCE_REVISION}": source_revision,
        "${AUTHORITY_IMAGE}": authority_image,
        "${PUBLIC_ENTRY_IMAGE}": public_entry_image,
        "${SUPABASE_PROJECT_REF}": project_ref,
        "${SUPABASE_OWNER_SUBJECT}": subject,
        "${SUPABASE_OWNER_EMAIL_SHA256}": email_hash,
        "${IAP_ADMIN_EMAIL_SHA256}": iap_email_hash,
    }

    def walk(item: Any) -> Any:
        if isinstance(item, dict):
            return {key: walk(child) for key, child in item.items()}
        if isinstance(item, list):
            return [walk(child) for child in item]
        return replacements.get(item, item)

    resolved = walk(dict(value))
    if "${" in json.dumps(resolved):
        raise CommissionError("resource_contract_parameter_unresolved")
    return resolved


def policy_members(policy: Any, role: str) -> set[str]:
    if not isinstance(policy, Mapping):
        return set()
    result: set[str] = set()
    for row in policy.get("bindings", []):
        if isinstance(row, Mapping) and row.get("role") == role:
            result.update(str(member) for member in row.get("members", []))
    return result


def _short_resource(value: object) -> str:
    return str(value or "").rsplit("/", 1)[-1]


def _env_map(container: Mapping[str, Any]) -> tuple[dict[str, str], set[str]]:
    values: dict[str, str] = {}
    secrets: set[str] = set()
    for row in container.get("env", []) if isinstance(container, Mapping) else []:
        if not isinstance(row, Mapping) or not isinstance(row.get("name"), str):
            continue
        if "valueFrom" in row:
            secrets.add(row["name"])
        else:
            values[row["name"]] = str(row.get("value") or "")
    return values, secrets


def _provider_int(value: object, *, default: int = -1) -> int:
    try:
        if isinstance(value, bool) or value is None:
            return default
        return int(value)
    except (TypeError, ValueError, OverflowError):
        return default


def _startup_probe(container: Mapping[str, Any]) -> dict[str, Any]:
    value = container.get("startupProbe")
    if not isinstance(value, Mapping):
        return {}
    tcp = value.get("tcpSocket")
    if not isinstance(tcp, Mapping):
        return {"kind": "unsupported"}
    return {
        "kind": "tcp",
        "port": _provider_int(tcp.get("port")),
        "initial_delay_seconds": _provider_int(
            value.get("initialDelaySeconds"), default=0,
        ),
        "timeout_seconds": _provider_int(value.get("timeoutSeconds")),
        "period_seconds": _provider_int(value.get("periodSeconds")),
        "failure_threshold": _provider_int(value.get("failureThreshold")),
    }


def _direct_vpc(
    annotations: Mapping[str, Any],
) -> dict[str, Any] | None:
    raw = annotations.get("run.googleapis.com/network-interfaces")
    egress = annotations.get("run.googleapis.com/vpc-access-egress")
    if raw is None and egress is None:
        return None
    try:
        rows = json.loads(str(raw))
    except (ValueError, TypeError, UnicodeError):
        return {"invalid": True}
    if (
        not isinstance(rows, list)
        or len(rows) != 1
        or not isinstance(rows[0], Mapping)
        or not isinstance(rows[0].get("tags", []), list)
    ):
        return {"invalid": True}
    row = rows[0]
    return {
        "network": _short_resource(row.get("network")),
        "subnetwork": _short_resource(row.get("subnetwork")),
        "tags": sorted(str(tag) for tag in row.get("tags", [])),
        "egress": egress,
    }


def _errors() -> tuple[list[str], Any]:
    errors: list[str] = []

    def check(condition: bool, code: str) -> None:
        if not condition:
            errors.append(code)

    return errors, check


def _members_match(
    actual: Iterable[str],
    expected: Iterable[str],
    *,
    allow_extras: bool,
) -> bool:
    actual_set = set(actual)
    expected_set = set(expected)
    return expected_set <= actual_set if allow_extras else expected_set == actual_set


def audit_snapshot(
    contract: Mapping[str, Any],
    snapshot: Mapping[str, Any],
    *,
    allow_iam_extras: bool = False,
    allow_vm_pending: bool = False,
    cloud_run_mode: str = "serving",
    allow_legacy_pending: bool = False,
    allow_immutable_subscription_pending: bool = False,
) -> dict[str, Any]:
    """Compare a redacted provider snapshot with the exact resolved contract.

    ``allow_vm_pending`` exists only for the prepare phase.  The VM release
    cannot consume the prepare receipt until that receipt exists, so prepare
    proves every provider resource outside the VM and records the one deferred
    boundary explicitly.  Audit, plan, subscription replacement and finalize
    always use the strict default.
    """

    if cloud_run_mode not in {"serving", "staged", "deferred"}:
        raise CommissionError("cloud_run_audit_mode_invalid")
    errors, check = _errors()
    services = snapshot.get("cloud_run", {})
    for expected in contract["cloud_run"]["services"]:
        name = expected["name"]
        actual = services.get(name)
        check(isinstance(actual, Mapping), f"cloud_run.{name}.missing")
        if not isinstance(actual, Mapping):
            continue
        serving_revision = actual.get("serving_revision")
        check(
            isinstance(serving_revision, str) and bool(serving_revision),
            f"cloud_run.{name}.serving_revision",
        )
        check(
            actual.get("latest_created_revision") == serving_revision
            and actual.get("latest_ready_revision") == serving_revision,
            f"cloud_run.{name}.latest_ready_revision",
        )
        check(actual.get("ready") is True, f"cloud_run.{name}.ready")
        check(
            actual.get("traffic")
            == [
                {
                    "revision": serving_revision,
                    "percent": 100,
                    "tag": None,
                }
            ],
            f"cloud_run.{name}.traffic",
        )
        check(actual.get("url") == expected["url"], f"cloud_run.{name}.url")
        check(actual.get("service_account") == expected["service_account"], f"cloud_run.{name}.service_account")
        check(actual.get("image") == contract["release"][expected["image_parameter"]], f"cloud_run.{name}.image")
        check(actual.get("ingress") == expected["ingress"], f"cloud_run.{name}.ingress")
        check(
            actual.get("iap_enabled") is expected["iap_enabled"],
            f"cloud_run.{name}.iap_enabled",
        )
        check(actual.get("timeout_seconds") == expected["timeout_seconds"], f"cloud_run.{name}.timeout")
        check(actual.get("container_concurrency") == expected["container_concurrency"], f"cloud_run.{name}.concurrency")
        check(actual.get("container_count") == 1, f"cloud_run.{name}.container_count")
        check(actual.get("resources") == expected["resources"], f"cloud_run.{name}.resources")
        check(actual.get("scaling") == expected["scaling"], f"cloud_run.{name}.scaling")
        check(
            actual.get("startup_cpu_boost")
            is expected["startup_cpu_boost"],
            f"cloud_run.{name}.startup_cpu_boost",
        )
        check(
            actual.get("cpu_idle") is expected["cpu_idle"],
            f"cloud_run.{name}.cpu_idle",
        )
        check(
            actual.get("startup_probe") == expected["startup_probe"],
            f"cloud_run.{name}.startup_probe",
        )
        check(
            actual.get("direct_vpc") == expected["direct_vpc"],
            f"cloud_run.{name}.direct_vpc",
        )
        check(
            actual.get("legacy_vpc_connector") is None,
            f"cloud_run.{name}.legacy_vpc_connector",
        )
        check(actual.get("environment") == expected["environment"], f"cloud_run.{name}.environment")
        check(actual.get("secret_environment") == [], f"cloud_run.{name}.secret_environment")
        check(
            _members_match(
                actual.get("invokers", []),
                expected["invokers"],
                allow_extras=allow_iam_extras,
            ),
            f"cloud_run.{name}.invokers",
        )
        if (
            not allow_iam_extras
            and name
            in contract["cloud_run"][
                "private_services_without_anonymous_invoker"
            ]
        ):
            check(not {"allUsers", "allAuthenticatedUsers"} & set(actual.get("invokers", [])), f"cloud_run.{name}.anonymous")
    rollback = snapshot.get("cloud_run", {}).get(contract["cloud_run"]["rollback_service_without_anonymous_invoker"])
    if isinstance(rollback, Mapping) and not allow_iam_extras:
        check(not {"allUsers", "allAuthenticatedUsers"} & set(rollback.get("invokers", [])), "cloud_run.rollback.anonymous")

    topics = snapshot.get("topics", {})
    for expected in contract["pubsub"]["topics"]:
        actual = topics.get(expected["name"])
        check(isinstance(actual, Mapping), f"topic.{expected['name']}.missing")
        if isinstance(actual, Mapping):
            check(
                _members_match(
                    actual.get("publishers", []),
                    expected["publishers"],
                    allow_extras=allow_iam_extras,
                ),
                f"topic.{expected['name']}.publishers",
            )
    subscriptions = snapshot.get("subscriptions", {})
    for expected in contract["pubsub"]["push_subscriptions"]:
        actual = subscriptions.get(expected["name"])
        check(isinstance(actual, Mapping), f"subscription.{expected['name']}.missing")
        if not isinstance(actual, Mapping):
            continue
        for field in (
            "topic", "push_endpoint", "oidc_service_account", "oidc_audience",
            "ack_deadline_seconds", "message_retention_duration",
            "expiration_period", "minimum_backoff", "maximum_backoff",
            "enable_message_ordering", "push_no_wrapper",
        ):
            check(actual.get(field) == expected[field], f"subscription.{expected['name']}.{field}")
    terminal = contract["pubsub"]["terminal_readback_subscription"]
    actual_terminal = subscriptions.get(terminal["name"])
    check(isinstance(actual_terminal, Mapping), "subscription.terminal.missing")
    if isinstance(actual_terminal, Mapping):
        for field in (
            "topic", "ack_deadline_seconds", "message_retention_duration",
            "expiration_period", "enable_message_ordering",
            "enable_exactly_once_delivery",
        ):
            check(actual_terminal.get(field) == terminal[field], f"subscription.terminal.{field}")
        check(not actual_terminal.get("push_endpoint"), "subscription.terminal.push_forbidden")
        check(
            _members_match(
                actual_terminal.get("subscribers", []),
                terminal["subscribers"],
                allow_extras=allow_iam_extras,
            ),
            "subscription.terminal.subscribers",
        )

    for name in contract["pubsub"]["retire_after_zero_backlog"]:
        check(
            name not in snapshot.get("legacy_subscriptions", {}),
            f"subscription.{name}.retirement_pending",
        )

    project_policy = snapshot.get("project_iam", {})
    protected = protected_members(contract)
    if not allow_iam_extras:
        for role in DATA_ROLES:
            check(
                not (policy_members(project_policy, role) & protected),
                f"project_iam.{role}.forbidden",
            )
    old = "serviceAccount:" + contract["vm_workload_identity"]["old_union_identity"]
    broker = (
        "serviceAccount:"
        + contract["vm_workload_identity"]["attached_service_account"]
    )
    if not allow_iam_extras:
        for role in DATA_ROLES:
            check(
                old not in policy_members(project_policy, role),
                f"old_vm_union.{role}.forbidden",
            )
            check(
                broker not in policy_members(project_policy, role),
                f"vm_broker.{role}.forbidden",
            )

    service_accounts = snapshot.get("service_accounts", {})
    for account in service_account_emails(contract):
        actual_account = service_accounts.get(account)
        check(
            isinstance(actual_account, Mapping),
            f"service_account.{account}.missing",
        )
        if isinstance(actual_account, Mapping):
            check(
                actual_account.get("email") == account
                and actual_account.get("disabled") is False,
                f"service_account.{account}.invalid",
            )

    custom_roles = snapshot.get("custom_roles", {})
    for expected in contract["iam"]["firestore"]["custom_roles"]:
        role_name = f"projects/{contract['project']}/roles/{expected['id']}"
        actual = custom_roles.get(expected["id"])
        check(isinstance(actual, Mapping), f"custom_role.{expected['id']}.missing")
        if isinstance(actual, Mapping):
            check(set(actual.get("permissions", [])) == set(expected["permissions"]), f"custom_role.{expected['id']}.permissions")
            check(actual.get("stage") == expected["stage"], f"custom_role.{expected['id']}.stage")
            check(
                actual.get("title") == expected["title"],
                f"custom_role.{expected['id']}.title",
            )
        check(
            _members_match(
                policy_members(project_policy, role_name),
                expected["members"],
                allow_extras=allow_iam_extras,
            ),
            f"custom_role.{expected['id']}.members",
        )

    service_account_policies = snapshot.get("service_account_iam", {})
    service_agent = "serviceAccount:" + contract["pubsub"]["service_agent"]
    for account in contract["iam"]["pubsub_oidc_token_creators"]:
        actual = service_account_policies.get(account)
        check(
            _members_match(
                policy_members(actual, "roles/iam.serviceAccountTokenCreator"),
                {service_agent},
                allow_extras=allow_iam_extras,
            ),
            f"oidc_token_creator.{account}",
        )
    broker_member = "serviceAccount:" + contract["vm_workload_identity"]["attached_service_account"]
    for workload in contract["vm_workload_identity"]["workloads"]:
        actual = service_account_policies.get(workload["service_account"])
        check(
            _members_match(
                policy_members(actual, "roles/iam.serviceAccountTokenCreator"),
                {broker_member},
                allow_extras=allow_iam_extras,
            ),
            f"broker_token_creator.{workload['name']}",
        )

    kms = snapshot.get("kms", {})
    for expected in contract["iam"]["kms_keys"]:
        actual = kms.get(expected["name"])
        check(isinstance(actual, Mapping), f"kms.{expected['name']}.missing")
        if isinstance(actual, Mapping):
            check(
                _members_match(
                    actual.get("signers", []),
                    expected["signers"],
                    allow_extras=allow_iam_extras,
                ),
                f"kms.{expected['name']}.signers",
            )
            check(
                _members_match(
                    actual.get("public_key_viewers", []),
                    expected["public_key_viewers"],
                    allow_extras=allow_iam_extras,
                ),
                f"kms.{expected['name']}.viewers",
            )
            check(str(actual.get("primary_version")) == expected["version"], f"kms.{expected['name']}.primary_version")

    secrets = snapshot.get("secrets", {})
    for expected in contract["iam"]["secrets"]:
        actual = secrets.get(expected["id"])
        check(isinstance(actual, Mapping), f"secret.{expected['id']}.missing")
        if isinstance(actual, Mapping):
            check(
                _members_match(
                    actual.get("readers", []),
                    expected["readers"],
                    allow_extras=allow_iam_extras,
                ),
                f"secret.{expected['id']}.readers",
            )
            check(actual.get("version") == expected["version"] and actual.get("version_state") == "ENABLED", f"secret.{expected['id']}.version")

    database = snapshot.get("firestore", {})
    check(database.get("name") == contract["iam"]["firestore"]["database"], "firestore.database")
    check(database.get("location") == contract["iam"]["firestore"]["location"], "firestore.location")
    check(database.get("delete_protection") is True, "firestore.delete_protection")

    enabled = set(snapshot.get("enabled_apis", []))
    for api in contract["required_apis"]:
        check(api in enabled, f"api.{api}.disabled")

    if not allow_vm_pending:
        _audit_vm(contract, snapshot.get("vm", {}), check)

    # Resource preparation deliberately precedes revision deployment.  It
    # therefore proves only the provider resources it owns and records the
    # Cloud Run boundary as deferred.  Staged attestation verifies the latest
    # created/ready revision and its exact template while requiring that the
    # revision receive no traffic.  Strict serving audit remains the default.
    if cloud_run_mode == "deferred":
        errors[:] = [
            code for code in errors if not code.startswith("cloud_run.")
        ]
    elif cloud_run_mode == "staged":
        ignored_suffixes = (
            ".serving_revision",
            ".latest_ready_revision",
            ".traffic",
        )
        errors[:] = [
            code
            for code in errors
            if not (
                code.startswith("cloud_run.")
                and code.endswith(ignored_suffixes)
            )
        ]
        for expected in contract["cloud_run"]["services"]:
            name = expected["name"]
            actual = services.get(name)
            if not isinstance(actual, Mapping):
                continue
            staged_revision = actual.get("latest_created_revision")
            check(
                isinstance(staged_revision, str)
                and bool(staged_revision)
                and actual.get("latest_ready_revision") == staged_revision,
                f"cloud_run.{name}.staged_revision_ready",
            )
            traffic = actual.get("traffic")
            check(
                isinstance(traffic, list)
                and bool(traffic)
                and all(
                    not isinstance(row, Mapping)
                    or row.get("revision") != staged_revision
                    or (
                        isinstance(row.get("percent"), (int, float))
                        and not isinstance(row.get("percent"), bool)
                        and row.get("percent") == 0
                    )
                    for row in traffic
                ),
                f"cloud_run.{name}.staged_revision_has_traffic",
            )

    if allow_legacy_pending:
        legacy_prefixes = tuple(
            f"subscription.{name}.retirement_pending"
            for name in contract["pubsub"]["retire_after_zero_backlog"]
        )
        errors[:] = [code for code in errors if code not in legacy_prefixes]

    deferred_subscriptions: list[str] = []
    if allow_immutable_subscription_pending:
        deferred_subscriptions = immutable_subscription_mismatches(
            contract, snapshot
        )
        prefixes = tuple(
            f"subscription.{name}." for name in deferred_subscriptions
        )
        errors[:] = [
            code for code in errors if not code.startswith(prefixes)
        ]
    return {
        "schema": "aureon.cloud-trading-authority-audit.v1",
        "ok": not errors,
        "errors": sorted(set(errors)),
        "error_count": len(set(errors)),
        "vm_readback_deferred_to_release_receipt": allow_vm_pending,
        "cloud_run_readback_mode": cloud_run_mode,
        "cloud_run_staged_without_traffic": cloud_run_mode == "staged",
        "legacy_retirement_deferred": allow_legacy_pending,
        "immutable_subscription_replacement_deferred": sorted(
            deferred_subscriptions
        ),
        "release_authority": False,
        "mutation_authority": False,
    }


def broker_identity_attached(
    contract: Mapping[str, Any], snapshot: Mapping[str, Any]
) -> bool:
    """Prove the broker identity is attached before revoking the old VM union."""

    expected = contract["vm_workload_identity"]
    vm = snapshot.get("vm")
    return bool(
        isinstance(vm, Mapping)
        and vm.get("name") == expected["instance"]
        and vm.get("status") == "RUNNING"
        and vm.get("service_accounts")
        == [
            {
                "email": expected["attached_service_account"],
                "scopes": expected["attached_oauth_scopes"],
            }
        ]
    )


def _audit_vm(contract: Mapping[str, Any], vm: Any, check: Any) -> None:
    expected = contract["vm_workload_identity"]
    check(isinstance(vm, Mapping), "vm.missing")
    if not isinstance(vm, Mapping):
        return
    check(vm.get("name") == expected["instance"], "vm.name")
    check(vm.get("status") == "RUNNING", "vm.status")
    check(vm.get("service_accounts") == [{
        "email": expected["attached_service_account"],
        "scopes": expected["attached_oauth_scopes"],
    }], "vm.attached_identity")
    check(vm.get("systemd_readback_ok") is True, "vm.systemd_readback")
    units = vm.get("units", {})
    check(set(units) == set(expected["all_aureon_units"]), "vm.aureon_unit_inventory")
    broker = units.get(expected["broker_unit"], {}) if isinstance(units, Mapping) else {}
    check(broker.get("user") == "root", "vm.broker.user")
    check(broker.get("group") == "root", "vm.broker.group")
    check(not broker.get("supplementary_groups"), "vm.broker.supplementary_groups")
    check(expected["broker_exec"] in str(broker.get("exec_start") or ""), "vm.broker.exec")
    for unit, actual in units.items() if isinstance(units, Mapping) else []:
        check(actual.get("active_state") == "active", f"vm.unit.{unit}.active")
        check(actual.get("unit_file_state") == "enabled", f"vm.unit.{unit}.enabled")
        check(actual.get("result") == "success", f"vm.unit.{unit}.result")
        check(actual.get("exec_main_status") == "0", f"vm.unit.{unit}.exit_status")
        check(
            actual.get("environment_parse_error") is False,
            f"vm.unit.{unit}.environment_parse",
        )
        check(
            actual.get("sensitive_environment_name_hashes") == [],
            f"vm.unit.{unit}.inline_secret_environment",
        )
        if unit == expected["only_metadata_unit"]:
            continue
        deny = str(actual.get("ip_address_deny") or "")
        allow = str(actual.get("ip_address_allow") or "")
        ipv4_denied = expected["metadata_ipv4"] in deny or "0.0.0.0/0" in deny or "any" in deny
        ipv6_denied = expected["metadata_ipv6"] in deny or "::/0" in deny or "any" in deny
        check(ipv4_denied and ipv6_denied, f"vm.unit.{unit}.metadata_not_denied")
        check("169.254.169.254" not in allow and "fd20:ce::254" not in allow, f"vm.unit.{unit}.metadata_allowed")
    for workload in expected["workloads"]:
        for unit in workload["units"]:
            actual = units.get(unit, {}) if isinstance(units, Mapping) else {}
            environment = actual.get("environment", {})
            check(actual.get("user") == workload["user"], f"vm.unit.{unit}.user")
            check(
                set(actual.get("supplementary_groups", []))
                == set(workload["supplementary_groups"]),
                f"vm.unit.{unit}.supplementary_groups",
            )
            check(environment.get("AUREON_GOOGLE_TOKEN_FILE") == workload["token_file"], f"vm.unit.{unit}.token_file")
            check(environment.get("AUREON_VM_TOKEN_BROKER_REQUIRED") == "1", f"vm.unit.{unit}.broker_required")
            check(environment.get("AUREON_GCP_PROJECT_NUMBER") == contract["project_number"], f"vm.unit.{unit}.project_number")
            for key, value in workload.get("required_environment", {}).items():
                check(environment.get(key) == value, f"vm.unit.{unit}.{key}")
    bridge = expected["public_bridge"]
    bridge_environment = units.get(bridge["unit"], {}).get("environment", {})
    for key, value in bridge["required_environment"].items():
        check(
            bridge_environment.get(key) == value,
            f"vm.unit.{bridge['unit']}.{key}",
        )
    owner_keys = {
        "AUREON_SUPABASE_OWNER_SUBJECT",
        "AUREON_SUPABASE_OWNER_EMAIL_SHA256",
    }
    operator_units = set(
        next(
            row["units"]
            for row in expected["workloads"]
            if row["name"] == "operator"
        )
    )
    for unit, actual in units.items() if isinstance(units, Mapping) else []:
        if unit not in operator_units:
            check(
                not owner_keys & set(actual.get("environment", {})),
                f"vm.unit.{unit}.owner_binding_forbidden",
            )
    paths = vm.get("paths", {})
    for row in [
        *expected["token_storage"],
        *expected["shared_state_exchange"],
    ]:
        actual = paths.get(row["path"])
        prefix = "vm.path." + sha256(row["path"].encode("utf-8"))[:12]
        check(isinstance(actual, Mapping), prefix + ".missing")
        if isinstance(actual, Mapping):
            for field in ("kind", "owner", "group", "mode"):
                check(actual.get(field) == row[field], prefix + "." + field)


def protected_members(contract: Mapping[str, Any]) -> set[str]:
    emails = {
        row["service_account"] for row in contract["cloud_run"]["services"]
        if row["service_account"].endswith(".iam.gserviceaccount.com")
    }
    vm = contract["vm_workload_identity"]
    emails.update(row["service_account"] for row in vm["workloads"])
    emails.update({vm["attached_service_account"], vm["old_union_identity"]})
    return {"serviceAccount:" + email for email in emails}


def service_account_emails(contract: Mapping[str, Any]) -> set[str]:
    emails = {
        row["service_account"] for row in contract["cloud_run"]["services"]
    }
    vm = contract["vm_workload_identity"]
    emails.add(vm["attached_service_account"])
    emails.update(row["service_account"] for row in vm["workloads"])
    return emails


class Gcloud:
    def __init__(self, executable: str, project: str):
        self.executable = executable
        self.project = project

    def _run(self, args: Iterable[str], *, optional: bool = False) -> subprocess.CompletedProcess[str] | None:
        command = [self.executable, *args, "--project=" + self.project]
        try:
            result = subprocess.run(
                command, check=False, capture_output=True, text=True, timeout=60,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise CommissionError("gcloud_execution_failed") from exc
        if result.returncode:
            if optional and any(
                text in result.stderr.lower()
                for text in (
                    "not found",
                    "not_found",
                    "was not found",
                    "does not exist",
                )
            ):
                return None
            raise CommissionError("gcloud_command_failed")
        if len(result.stdout) > 16 * 1024 * 1024:
            raise CommissionError("gcloud_response_too_large")
        return result

    def json(self, *args: str, optional: bool = False) -> Any:
        result = self._run([*args, "--format=json"], optional=optional)
        if result is None:
            return None
        try:
            return json.loads(result.stdout or "null")
        except (ValueError, TypeError, UnicodeError) as exc:
            raise CommissionError("gcloud_json_invalid") from exc

    def text(self, *args: str) -> str:
        result = self._run(args)
        assert result is not None
        return result.stdout

    def apply(self, *args: str) -> None:
        result = self._run([*args, "--quiet"])
        if result is None:
            raise CommissionError("gcloud_apply_failed")


def capture_snapshot(contract: Mapping[str, Any], runner: Runner) -> dict[str, Any]:
    """Collect only configuration and IAM metadata; never access secret data."""

    project = contract["project"]
    region = contract["region"]
    result: dict[str, Any] = {
        "cloud_run": {}, "topics": {}, "subscriptions": {},
        "legacy_subscriptions": {}, "service_accounts": {},
        "service_account_iam": {}, "kms": {}, "secrets": {},
        "custom_roles": {},
    }
    for expected in contract["cloud_run"]["services"]:
        name = expected["name"]
        value = runner.json(
            "run", "services", "describe", name, "--region=" + region,
            optional=True,
        )
        if not isinstance(value, Mapping):
            continue
        policy = runner.json(
            "run", "services", "get-iam-policy", name, "--region=" + region,
            optional=True,
        ) or {}
        status = value.get("status", {})
        serving_revision = status.get("latestReadyRevisionName")
        revision = None
        if isinstance(serving_revision, str) and serving_revision:
            revision = runner.json(
                "run", "revisions", "describe", serving_revision,
                "--region=" + region, optional=True,
            )
        revision = revision if isinstance(revision, Mapping) else {}
        spec = revision.get("spec", {})
        containers = (
            spec.get("containers", [])
            if isinstance(spec, Mapping)
            else []
        )
        container = (
            containers[0]
            if isinstance(containers, list)
            and len(containers) == 1
            and isinstance(containers[0], Mapping)
            else {}
        )
        env, secret_env = _env_map(container)
        service_annotations = value.get("metadata", {}).get(
            "annotations", {}
        )
        revision_annotations = revision.get("metadata", {}).get(
            "annotations", {}
        )
        revision_status = revision.get("status", {})
        service_ready = any(
            row.get("type") == "Ready" and row.get("status") == "True"
            for row in status.get("conditions", [])
            if isinstance(row, Mapping)
        )
        revision_ready = any(
            row.get("type") == "Ready" and row.get("status") == "True"
            for row in revision_status.get("conditions", [])
            if isinstance(row, Mapping)
        )
        traffic = [
            {
                "revision": row.get("revisionName"),
                "percent": int(row.get("percent", 0)),
                "tag": row.get("tag"),
            }
            for row in status.get("traffic", [])
            if isinstance(row, Mapping)
        ]
        limits = container.get("resources", {}).get("limits", {})
        limits = dict(limits) if isinstance(limits, Mapping) else {}
        result["cloud_run"][name] = {
            "url": status.get("url"),
            "serving_revision": serving_revision,
            "latest_created_revision": status.get(
                "latestCreatedRevisionName"
            ),
            "latest_ready_revision": status.get("latestReadyRevisionName"),
            "ready": service_ready and revision_ready,
            "traffic": traffic,
            "service_account": spec.get("serviceAccountName"),
            "image": revision_status.get("imageDigest")
            or container.get("image"),
            "ingress": service_annotations.get(
                "run.googleapis.com/ingress", "all",
            ),
            "iap_enabled": (
                service_annotations.get("run.googleapis.com/iap-enabled")
                == "true"
            ),
            "timeout_seconds": _provider_int(spec.get("timeoutSeconds")),
            "container_concurrency": _provider_int(
                spec.get("containerConcurrency")
            ),
            "container_count": len(containers),
            "resources": limits,
            "scaling": {
                "min_instances": _provider_int(
                    revision_annotations.get(
                        "autoscaling.knative.dev/minScale"
                    ),
                    default=0,
                ),
                "max_instances": _provider_int(
                    revision_annotations.get(
                        "autoscaling.knative.dev/maxScale"
                    )
                ),
            },
            "startup_cpu_boost": (
                revision_annotations.get(
                    "run.googleapis.com/startup-cpu-boost"
                )
                == "true"
            ),
            "cpu_idle": (
                revision_annotations.get(
                    "run.googleapis.com/cpu-throttling", "true"
                )
                == "true"
            ),
            "startup_probe": _startup_probe(container),
            "direct_vpc": _direct_vpc(revision_annotations),
            "legacy_vpc_connector": revision_annotations.get(
                "run.googleapis.com/vpc-access-connector"
            ),
            "environment": env,
            "secret_environment": sorted(secret_env),
            "invokers": sorted(policy_members(policy, "roles/run.invoker")),
        }
    rollback_name = contract["cloud_run"]["rollback_service_without_anonymous_invoker"]
    rollback = runner.json("run", "services", "describe", rollback_name, "--region=" + region, optional=True)
    if rollback is not None:
        policy = runner.json(
            "run", "services", "get-iam-policy", rollback_name,
            "--region=" + region, optional=True,
        ) or {}
        result["cloud_run"][rollback_name] = {"invokers": sorted(policy_members(policy, "roles/run.invoker"))}

    for expected in contract["pubsub"]["topics"]:
        name = expected["name"]
        value = runner.json(
            "pubsub", "topics", "describe", name, optional=True,
        )
        if not isinstance(value, Mapping):
            continue
        policy = runner.json(
            "pubsub", "topics", "get-iam-policy", name, optional=True,
        ) or {}
        result["topics"][name] = {"publishers": sorted(policy_members(policy, "roles/pubsub.publisher"))}
    subscription_rows = [
        *contract["pubsub"]["push_subscriptions"],
        contract["pubsub"]["terminal_readback_subscription"],
    ]
    for expected in subscription_rows:
        name = expected["name"]
        value = runner.json(
            "pubsub", "subscriptions", "describe", name, optional=True,
        )
        if not isinstance(value, Mapping):
            continue
        policy = runner.json(
            "pubsub", "subscriptions", "get-iam-policy", name, optional=True,
        ) or {}
        push = value.get("pushConfig") or {}
        oidc = push.get("oidcToken") or {}
        retry = value.get("retryPolicy") or {}
        expiration = value.get("expirationPolicy") or {}
        result["subscriptions"][name] = {
            "topic": _short_resource(value.get("topic")),
            "push_endpoint": push.get("pushEndpoint"),
            "oidc_service_account": oidc.get("serviceAccountEmail"),
            "oidc_audience": oidc.get("audience"),
            "ack_deadline_seconds": int(value.get("ackDeadlineSeconds", 0)),
            "message_retention_duration": value.get("messageRetentionDuration"),
            "expiration_period": expiration.get("ttl") or "never",
            "minimum_backoff": retry.get("minimumBackoff"),
            "maximum_backoff": retry.get("maximumBackoff"),
            "enable_message_ordering": bool(value.get("enableMessageOrdering", False)),
            "enable_exactly_once_delivery": bool(
                value.get("enableExactlyOnceDelivery", False)
            ),
            "push_no_wrapper": bool(push.get("noWrapper")),
            "subscribers": sorted(policy_members(policy, "roles/pubsub.subscriber")),
        }

    for name in contract["pubsub"]["retire_after_zero_backlog"]:
        value = runner.json(
            "pubsub", "subscriptions", "describe", name, optional=True,
        )
        if isinstance(value, Mapping):
            result["legacy_subscriptions"][name] = {
                "topic": _short_resource(value.get("topic")),
            }

    for account in sorted(service_account_emails(contract)):
        value = runner.json(
            "iam", "service-accounts", "describe", account, optional=True,
        )
        if not isinstance(value, Mapping):
            continue
        result["service_accounts"][account] = {
            "email": value.get("email"),
            "disabled": bool(value.get("disabled", False)),
        }
        result["service_account_iam"][account] = runner.json(
            "iam", "service-accounts", "get-iam-policy", account,
            optional=True,
        ) or {}
    for expected in contract["iam"]["kms_keys"]:
        name = expected["name"]
        value = runner.json(
            "kms", "keys", "describe", name,
            "--location=" + region, "--keyring=" + contract["keyring"],
            optional=True,
        )
        if not isinstance(value, Mapping):
            continue
        policy = runner.json(
            "kms", "keys", "get-iam-policy", name,
            "--location=" + region, "--keyring=" + contract["keyring"],
            optional=True,
        ) or {}
        result["kms"][name] = {
            "signers": sorted(policy_members(policy, "roles/cloudkms.signerVerifier")),
            "public_key_viewers": sorted(policy_members(policy, "roles/cloudkms.publicKeyViewer")),
            "primary_version": _short_resource(value.get("primary", {}).get("name")),
        }
    for expected in contract["iam"]["secrets"]:
        name = expected["id"]
        policy = runner.json(
            "secrets", "get-iam-policy", name, optional=True,
        )
        version = runner.json(
            "secrets", "versions", "describe", expected["version"],
            "--secret=" + name, optional=True,
        )
        if not isinstance(policy, Mapping) or not isinstance(version, Mapping):
            continue
        result["secrets"][name] = {
            "readers": sorted(policy_members(policy, "roles/secretmanager.secretAccessor")),
            "version": _short_resource(version.get("name")),
            "version_state": version.get("state"),
        }
    result["project_iam"] = runner.json("projects", "get-iam-policy", project)
    for expected in contract["iam"]["firestore"]["custom_roles"]:
        value = runner.json(
            "iam", "roles", "describe", expected["id"], optional=True,
        )
        if value is not None:
            result["custom_roles"][expected["id"]] = {
                "permissions": sorted(value.get("includedPermissions", [])),
                "stage": value.get("stage"),
                "title": value.get("title"),
            }
    database = runner.json(
        "firestore", "databases", "describe", "--database=(default)",
        optional=True,
    )
    if isinstance(database, Mapping):
        result["firestore"] = {
            "name": database.get("name"),
            "location": database.get("locationId"),
            "delete_protection": (
                database.get("deleteProtectionState")
                == "DELETE_PROTECTION_ENABLED"
            ),
        }
    apis = runner.json("services", "list", "--enabled")
    result["enabled_apis"] = sorted(
        row.get("config", {}).get("name") for row in apis
        if isinstance(row, Mapping) and row.get("config", {}).get("name")
    )
    result["vm"] = _capture_vm(contract, runner)
    return result


def _capture_vm(contract: Mapping[str, Any], runner: Runner) -> dict[str, Any]:
    vm = contract["vm_workload_identity"]
    value = runner.json(
        "compute", "instances", "describe", vm["instance"],
        "--zone=" + contract["zone"],
        optional=True,
    )
    if not isinstance(value, Mapping):
        return {}
    paths = [
        row["path"]
        for row in [*vm["token_storage"], *vm["shared_state_exchange"]]
    ]
    quoted_paths = " ".join(shlex.quote(path) for path in paths)
    environment_filter = (
        "import hashlib,re,shlex,sys\n"
        f"allowed={sorted(VM_READBACK_ENVIRONMENT_KEYS)!r}\n"
        "plaintext_identity={'AUREON_ALLOWED_USER_EMAILS','AUREON_OWNER_EMAIL','AUREON_IAP_ADMIN_EMAIL'}\n"
        "sensitive=re.compile(r'(?:^|_)(?:API_KEY|SECRET|PASSWORD|TOKEN|PRIVATE_KEY|CREDENTIALS?)(?:$|_)')\n"
        "try:\n pieces=shlex.split(sys.stdin.read())\n"
        "except ValueError:\n print('EnvironmentParseError=1'); raise SystemExit(0)\n"
        "for piece in pieces:\n"
        " if '=' not in piece:\n  print('EnvironmentParseError=1'); continue\n"
        " name,value=piece.split('=',1)\n"
        " if name in allowed and re.fullmatch(r'[A-Za-z0-9_./@:-]{1,512}',value):\n"
        "  print('EnvironmentAllowed.'+name+'='+value)\n"
        " elif name in allowed:\n  print('EnvironmentParseError=1')\n"
        " elif name in plaintext_identity or sensitive.search(name):\n"
        "  print('SensitiveEnvironmentNameHash='+hashlib.sha256(name.encode()).hexdigest())\n"
    )
    remote = (
        "for u in $(systemctl list-unit-files 'aureon-*' --no-legend --no-pager "
        "| awk '{print $1}' | grep -v '@.service$'); do echo @@UNIT=$u; "
        "systemctl show \"$u\" --property=User --property=Group --property=ExecStart "
        "--property=SupplementaryGroups --property=IPAddressDeny "
        "--property=IPAddressAllow --property=ActiveState --property=SubState "
        "--property=UnitFileState --property=Result --property=ExecMainStatus; "
        "stamp=$(systemctl show \"$u\" --property=InactiveEnterTimestamp "
        "--value); if test -n \"$stamp\" && test \"$stamp\" != n/a; then "
        "printf 'InactiveEnterTimestamp='; "
        "date --date=\"$stamp\" --iso-8601=seconds; fi; "
        "systemctl show \"$u\" --property=Environment --value | python3 -c "
        + shlex.quote(environment_filter)
        + "; done; "
        f"for p in {quoted_paths}; do echo @@PATH=$p; "
        "if test -e \"$p\" && test ! -L \"$p\"; then "
        "stat --format='Kind=%F%nOwner=%U%nGroup=%G%nMode=%a' -- \"$p\"; "
        "else echo Missing=1; fi; done"
    )
    try:
        raw = runner.text(
            "compute", "ssh", vm["instance"], "--zone=" + contract["zone"],
            "--tunnel-through-iap", "--command=" + remote, "--quiet",
        )
        readback_ok = True
    except CommissionError:
        raw = ""
        readback_ok = False
    units: dict[str, dict[str, Any]] = {}
    path_state: dict[str, dict[str, Any]] = {}
    current: dict[str, Any] | None = None
    current_path: dict[str, Any] | None = None
    for line in raw.splitlines():
        if line.startswith("@@UNIT="):
            name = line.removeprefix("@@UNIT=").strip()
            current = {
                "environment": {},
                "environment_parse_error": False,
                "sensitive_environment_name_hashes": [],
            }
            units[name] = current
            current_path = None
        elif line.startswith("@@PATH="):
            name = line.removeprefix("@@PATH=").strip()
            current_path = {}
            path_state[name] = current_path
            current = None
        elif current is not None and "=" in line:
            key, item = line.split("=", 1)
            mapped = {
                "User": "user", "Group": "group", "ExecStart": "exec_start",
                "IPAddressDeny": "ip_address_deny", "IPAddressAllow": "ip_address_allow",
                "ActiveState": "active_state", "SubState": "sub_state",
                "UnitFileState": "unit_file_state", "Result": "result",
                "ExecMainStatus": "exec_main_status",
                "InactiveEnterTimestamp": "inactive_enter_timestamp",
            }.get(key)
            if mapped:
                current[mapped] = item
            elif key == "SupplementaryGroups":
                current["supplementary_groups"] = item.split()
            elif key.startswith("EnvironmentAllowed."):
                current["environment"][key.removeprefix("EnvironmentAllowed.")] = item
            elif key == "EnvironmentParseError":
                current["environment_parse_error"] = True
            elif key == "SensitiveEnvironmentNameHash":
                current["sensitive_environment_name_hashes"].append(item)
        elif current_path is not None and "=" in line:
            key, item = line.split("=", 1)
            mapped = {
                "Kind": "kind",
                "Owner": "owner",
                "Group": "group",
                "Mode": "mode",
            }.get(key)
            if mapped:
                current_path[mapped] = item
            elif key == "Missing":
                current_path["missing"] = item == "1"
    accounts = []
    for account in value.get("serviceAccounts", []):
        accounts.append({
            "email": account.get("email"),
            "scopes": account.get("scopes", []),
        })
    return {
        "name": value.get("name"),
        "status": value.get("status"),
        "service_accounts": accounts,
        "systemd_readback_ok": readback_ok,
        "units": units,
        "paths": path_state,
    }


@dataclass(frozen=True)
class Action:
    action_id: str
    args: tuple[str, ...]
    destructive: bool = False
    blocked: bool = False


def _binding_actions(
    prefix: str,
    command_template: tuple[str, ...],
    role: str,
    actual: set[str],
    expected: set[str],
) -> list[Action]:
    actions: list[Action] = []
    for member in sorted(expected - actual):
        command = tuple(
            "add-iam-policy-binding" if item == "{operation}" else item
            for item in command_template
        )
        actions.append(
            Action(
                f"{prefix}.add.{sha256(member.encode())[:12]}",
                (
                    *command,
                    "--member=" + member,
                    "--role=" + role,
                    "--condition=None",
                ),
            )
        )
    for member in sorted(actual - expected):
        command = tuple(
            "remove-iam-policy-binding" if item == "{operation}" else item
            for item in command_template
        )
        actions.append(
            Action(
                f"{prefix}.remove.{sha256(member.encode())[:12]}",
                (
                    *command,
                    "--member=" + member,
                    "--role=" + role,
                    "--condition=None",
                ),
                destructive=True,
            )
        )
    return actions


def _subscription_actions(
    contract: Mapping[str, Any],
    snapshot: Mapping[str, Any],
) -> list[Action]:
    actions: list[Action] = []
    actual_subscriptions = snapshot.get("subscriptions", {})
    for row in contract["pubsub"]["push_subscriptions"]:
        actual = actual_subscriptions.get(row["name"])
        common = (
            "--ack-deadline=" + str(row["ack_deadline_seconds"]),
            "--message-retention-duration=" + row["message_retention_duration"],
            "--expiration-period=" + row["expiration_period"],
            "--min-retry-delay=" + row["minimum_backoff"],
            "--max-retry-delay=" + row["maximum_backoff"],
            "--push-endpoint=" + row["push_endpoint"],
            "--push-auth-service-account=" + row["oidc_service_account"],
            "--push-auth-token-audience=" + row["oidc_audience"],
        )
        if not isinstance(actual, Mapping):
            actions.append(
                Action(
                    f"subscription.{row['name']}.create",
                    (
                        "pubsub", "subscriptions", "create", row["name"],
                        "--topic=" + row["topic"],
                        *common,
                        "--enable-message-ordering",
                    ),
                )
            )
            continue
        immutable_matches = (
            actual.get("topic") == row["topic"]
            and actual.get("enable_message_ordering")
            == row["enable_message_ordering"]
        )
        mutable_fields = (
            "push_endpoint", "oidc_service_account", "oidc_audience",
            "ack_deadline_seconds", "message_retention_duration",
            "expiration_period", "minimum_backoff", "maximum_backoff",
            "push_no_wrapper",
        )
        if immutable_matches and any(
            actual.get(field) != row[field] for field in mutable_fields
        ):
            actions.append(
                Action(
                    f"subscription.{row['name']}.update",
                    (
                        "pubsub", "subscriptions", "update", row["name"],
                        *common,
                        "--clear-push-no-wrapper-config",
                    ),
                )
            )
        elif not immutable_matches:
            actions.append(
                Action(
                    f"subscription.{row['name']}.manual-replacement-required",
                    (),
                    blocked=True,
                )
            )

    terminal = contract["pubsub"]["terminal_readback_subscription"]
    actual = actual_subscriptions.get(terminal["name"])
    common = (
        "--ack-deadline=" + str(terminal["ack_deadline_seconds"]),
        "--message-retention-duration=" + terminal["message_retention_duration"],
        "--expiration-period=" + terminal["expiration_period"],
    )
    if not isinstance(actual, Mapping):
        actions.append(
            Action(
                "subscription.terminal.create",
                (
                    "pubsub", "subscriptions", "create", terminal["name"],
                    "--topic=" + terminal["topic"],
                    *common,
                    "--enable-message-ordering",
                    "--enable-exactly-once-delivery",
                ),
            )
        )
    elif (
        actual.get("topic") == terminal["topic"]
        and actual.get("enable_message_ordering")
        == terminal["enable_message_ordering"]
        and not actual.get("push_endpoint")
        and any(
            actual.get(field) != terminal[field]
            for field in (
                "ack_deadline_seconds",
                "message_retention_duration",
                "expiration_period",
                "enable_exactly_once_delivery",
            )
        )
    ):
        actions.append(
            Action(
                "subscription.terminal.update",
                (
                    "pubsub", "subscriptions", "update", terminal["name"],
                    *common,
                    "--enable-exactly-once-delivery",
                ),
            )
        )
    elif (
        actual.get("topic") != terminal["topic"]
        or actual.get("enable_message_ordering")
        != terminal["enable_message_ordering"]
        or actual.get("push_endpoint")
    ):
        actions.append(
            Action(
                "subscription.terminal.manual-replacement-required",
                (),
                blocked=True,
            )
        )
    return actions


def _resource_actions(
    contract: Mapping[str, Any],
    snapshot: Mapping[str, Any],
) -> list[Action]:
    actions: list[Action] = []
    enabled = set(snapshot.get("enabled_apis", []))
    for api in contract["required_apis"]:
        if api not in enabled:
            actions.append(
                Action(f"api.{api}.enable", ("services", "enable", api))
            )
    existing_accounts = snapshot.get("service_accounts", {})
    for account in sorted(service_account_emails(contract)):
        if account not in existing_accounts:
            account_id = account.split("@", 1)[0]
            actions.append(
                Action(
                    f"service-account.{account_id}.create",
                    (
                        "iam", "service-accounts", "create", account_id,
                        "--display-name=" + account_id,
                        "--description=Aureon commissioned keyless runtime identity",
                    ),
                )
            )
    topics = snapshot.get("topics", {})
    for row in contract["pubsub"]["topics"]:
        if row["name"] not in topics:
            actions.append(
                Action(
                    f"topic.{row['name']}.create",
                    ("pubsub", "topics", "create", row["name"]),
                )
            )
    actions.extend(_subscription_actions(contract, snapshot))
    roles = snapshot.get("custom_roles", {})
    for row in contract["iam"]["firestore"]["custom_roles"]:
        actual = roles.get(row["id"])
        common = (
            "--title=" + row["title"],
            "--permissions=" + ",".join(sorted(row["permissions"])),
            "--stage=" + row["stage"],
        )
        if not isinstance(actual, Mapping):
            actions.append(
                Action(
                    f"custom-role.{row['id']}.create",
                    ("iam", "roles", "create", row["id"], *common),
                )
            )
        elif (
            set(actual.get("permissions", [])) != set(row["permissions"])
            or actual.get("stage") != row["stage"]
            or actual.get("title") != row["title"]
        ):
            actions.append(
                Action(
                    f"custom-role.{row['id']}.update",
                    ("iam", "roles", "update", row["id"], *common),
                )
            )
    return actions


def build_iam_actions(
    contract: Mapping[str, Any],
    snapshot: Mapping[str, Any],
) -> list[Action]:
    """Return exact provisioning and resource-level IAM changes.

    Cloud Run deployment, VM identity cutover, KMS key creation, secret version
    creation and legacy-subscription retirement remain explicit prerequisites.
    """

    actions = _resource_actions(contract, snapshot)
    region, keyring = contract["region"], contract["keyring"]
    for row in contract["cloud_run"]["services"]:
        if row["name"] not in snapshot.get("cloud_run", {}):
            continue
        actual = set(snapshot.get("cloud_run", {}).get(row["name"], {}).get("invokers", []))
        actions += _binding_actions(
            f"run.{row['name']}.invoker",
            ("run", "services", "{operation}", row["name"], "--region=" + region),
            "roles/run.invoker", actual, set(row["invokers"]),
        )
    rollback_name = contract["cloud_run"][
        "rollback_service_without_anonymous_invoker"
    ]
    rollback = snapshot.get("cloud_run", {}).get(rollback_name)
    if isinstance(rollback, Mapping):
        for member in sorted(
            {"allUsers", "allAuthenticatedUsers"}
            & set(rollback.get("invokers", []))
        ):
            actions.append(
                Action(
                    "run.rollback.remove-anonymous."
                    + sha256(member.encode())[:12],
                    (
                        "run", "services", "remove-iam-policy-binding",
                        rollback_name, "--region=" + region,
                        "--member=" + member,
                        "--role=roles/run.invoker",
                        "--condition=None",
                    ),
                    destructive=True,
                )
            )
    for row in contract["pubsub"]["topics"]:
        actual = set(snapshot.get("topics", {}).get(row["name"], {}).get("publishers", []))
        actions += _binding_actions(
            f"topic.{row['name']}.publisher", ("pubsub", "topics", "{operation}", row["name"]),
            "roles/pubsub.publisher", actual, set(row["publishers"]),
        )
    terminal = contract["pubsub"]["terminal_readback_subscription"]
    actual = set(snapshot.get("subscriptions", {}).get(terminal["name"], {}).get("subscribers", []))
    actions += _binding_actions(
        "subscription.terminal.subscriber", ("pubsub", "subscriptions", "{operation}", terminal["name"]),
        "roles/pubsub.subscriber", actual, set(terminal["subscribers"]),
    )
    service_agent = "serviceAccount:" + contract["pubsub"]["service_agent"]
    for account in contract["iam"]["pubsub_oidc_token_creators"]:
        policy = snapshot.get("service_account_iam", {}).get(account, {})
        actions += _binding_actions(
            f"sa.{account}.pubsub-token", ("iam", "service-accounts", "{operation}", account),
            "roles/iam.serviceAccountTokenCreator",
            policy_members(policy, "roles/iam.serviceAccountTokenCreator"), {service_agent},
        )
    broker = "serviceAccount:" + contract["vm_workload_identity"]["attached_service_account"]
    for workload in contract["vm_workload_identity"]["workloads"]:
        account = workload["service_account"]
        policy = snapshot.get("service_account_iam", {}).get(account, {})
        actions += _binding_actions(
            f"sa.{account}.broker-token", ("iam", "service-accounts", "{operation}", account),
            "roles/iam.serviceAccountTokenCreator",
            policy_members(policy, "roles/iam.serviceAccountTokenCreator"), {broker},
        )
    for row in contract["iam"]["kms_keys"]:
        if row["name"] not in snapshot.get("kms", {}):
            continue
        actual = snapshot.get("kms", {}).get(row["name"], {})
        base = ("kms", "keys", "{operation}", row["name"], "--location=" + region, "--keyring=" + keyring)
        actions += _binding_actions(f"kms.{row['name']}.signer", base, "roles/cloudkms.signerVerifier", set(actual.get("signers", [])), set(row["signers"]))
        actions += _binding_actions(f"kms.{row['name']}.viewer", base, "roles/cloudkms.publicKeyViewer", set(actual.get("public_key_viewers", [])), set(row["public_key_viewers"]))
    for row in contract["iam"]["secrets"]:
        if row["id"] not in snapshot.get("secrets", {}):
            continue
        actual = set(snapshot.get("secrets", {}).get(row["id"], {}).get("readers", []))
        actions += _binding_actions(f"secret.{row['id']}.reader", ("secrets", "{operation}", row["id"]), "roles/secretmanager.secretAccessor", actual, set(row["readers"]))
    project_policy = snapshot.get("project_iam", {})
    for row in contract["iam"]["firestore"]["custom_roles"]:
        role = f"projects/{contract['project']}/roles/{row['id']}"
        actions += _binding_actions(
            f"project.{row['id']}", ("projects", "{operation}", contract["project"]), role,
            policy_members(project_policy, role), set(row["members"]),
        )
    protected = protected_members(contract)
    for role in sorted(DATA_ROLES):
        for member in sorted(policy_members(project_policy, role) & protected):
            actions.append(Action(
                f"project.remove-broad.{role}.{sha256(member.encode())[:12]}",
                (
                    "projects", "remove-iam-policy-binding",
                    contract["project"], "--member=" + member,
                    "--role=" + role, "--condition=None",
                ),
                destructive=True,
            ))
    return actions


def _parse_timestamp(value: object, reason: str) -> datetime:
    if not isinstance(value, str) or len(value) > 64:
        raise CommissionError(reason)
    try:
        parsed_value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed_value.tzinfo is None:
            raise ValueError("timezone_required")
        parsed = parsed_value.astimezone(UTC)
    except (ValueError, TypeError, OverflowError) as exc:
        raise CommissionError(reason) from exc
    return parsed


def validate_public_bridge_certificate_evidence(
    contract: Mapping[str, Any],
    value: object,
    *,
    now: datetime,
    reason: str,
) -> dict[str, Any]:
    """Validate one redacted identity for the certificate in every release layer."""

    bridge = contract["vm_workload_identity"]["public_bridge"]
    if (
        not isinstance(value, Mapping)
        or set(value)
        != {
            "receipt_sha256",
            "fingerprint_sha256",
            "required_ip_sans",
            "not_before",
            "not_after",
            "minimum_remaining_validity_seconds",
        }
        or _HEX64.fullmatch(str(value.get("receipt_sha256") or "")) is None
        or _HEX64.fullmatch(str(value.get("fingerprint_sha256") or ""))
        is None
        or value.get("required_ip_sans") != bridge["required_ip_sans"]
        or value.get("minimum_remaining_validity_seconds")
        != bridge["minimum_remaining_validity_seconds"]
    ):
        raise CommissionError(reason)
    not_before = _parse_timestamp(value.get("not_before"), reason)
    not_after = _parse_timestamp(value.get("not_after"), reason)
    current = now.astimezone(UTC)
    if (
        not_before > current
        or not_after <= current
        or (not_after - current).total_seconds()
        < bridge["minimum_remaining_validity_seconds"]
    ):
        raise CommissionError(reason)
    return dict(value)


def validate_supabase_owner_receipt(
    contract: Mapping[str, Any],
    path: Path | None,
    acknowledgement: str | None,
    *,
    now: datetime | None = None,
) -> str:
    """Bind commissioning to a fresh, redacted Supabase Auth readback."""

    if (
        path is None
        or not path.is_absolute()
        or not path.is_file()
        or path.is_symlink()
    ):
        raise CommissionError("supabase_owner_receipt_required")
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise CommissionError("supabase_owner_receipt_invalid") from exc
    if not 0 < len(raw) <= 16 * 1024:
        raise CommissionError("supabase_owner_receipt_invalid")
    try:
        value = json.loads(raw)
    except (ValueError, TypeError, UnicodeError) as exc:
        raise CommissionError("supabase_owner_receipt_invalid") from exc
    if not isinstance(value, Mapping) or set(value) != {
        "schema",
        "provider",
        "project_ref",
        "subject",
        "app_metadata_role",
        "email_confirmed",
        "email_sha256",
        "recorded_at",
        "source_revision",
        "contract_sha256",
    }:
        raise CommissionError("supabase_owner_receipt_invalid")
    required = contract["release"]["supabase_owner_provider_receipt"]
    receipt_hash = sha256(canonical(value))
    if (
        _HEX64.fullmatch(str(acknowledgement or "")) is None
        or not secrets.compare_digest(acknowledgement, receipt_hash)
    ):
        raise CommissionError("supabase_owner_receipt_acknowledgement_invalid")
    expected_contract_hash = sha256(canonical(contract))
    if (
        value.get("schema") != required["schema"]
        or value.get("provider") != required["provider"]
        or value.get("project_ref") != contract["release"]["supabase_project_ref"]
        or value.get("subject") != contract["release"]["supabase_owner_subject"]
        or value.get("app_metadata_role")
        != required["required_app_metadata_role"]
        or value.get("email_confirmed") is not True
        or value.get("email_sha256")
        != contract["release"]["supabase_owner_email_sha256"]
        or value.get("source_revision") != contract["release"]["source_revision"]
        or value.get("contract_sha256") != expected_contract_hash
    ):
        raise CommissionError("supabase_owner_receipt_binding_invalid")
    recorded_at = _parse_timestamp(
        value.get("recorded_at"), "supabase_owner_receipt_time_invalid"
    )
    observed_now = (now or datetime.now(UTC)).astimezone(UTC)
    age = (observed_now - recorded_at).total_seconds()
    if age < -30 or age > required["maximum_age_seconds"]:
        raise CommissionError("supabase_owner_receipt_stale")
    return receipt_hash


def _vm_expected_unit_user(
    contract: Mapping[str, Any], unit: str,
) -> str:
    vm = contract["vm_workload_identity"]
    if unit == vm["broker_unit"]:
        return "root"
    if unit == vm["public_bridge"]["unit"]:
        return "aureon-public"
    for workload in vm["workloads"]:
        if unit in workload["units"]:
            return workload["user"]
    return "aureon-organ-" + sha256(unit.encode("ascii"))[:12]


def _vm_expected_executable(unit: str) -> str:
    root = "/srv/aureon/runtime/workspace/deployment/google-cloud/"
    if unit == "aureon-cloud-token-broker.service":
        return root + "vm_token_broker.py"
    if unit == "aureon-cloud-operator.service":
        return root + "cloud_operator.py"
    if unit == "aureon-cloud-ui.service":
        return root + "cloud_ui_gateway.py"
    if unit == "aureon-cloud-trade-receipt.service":
        return root + "cloud_trade_receipt_collector.py"
    if unit == "aureon-public-bridge.service":
        return "/srv/aureon/public-entry/public_entry.py"
    return root + "cloud_read_organ.py"


def _validate_vm_http_health(
    value: object,
    *,
    role: str,
    unit: str,
    revision: str,
) -> None:
    expected_keys = {
        "unit", "schema", "revision", "role", "ready",
        "deployment_hold", "release_authority", "tenant_auth_ready",
        "response_sha256",
    }
    if (
        not isinstance(value, Mapping)
        or set(value) != expected_keys
        or value.get("unit") != unit
        or value.get("schema") != "aureon.cloud-http-health.v1"
        or value.get("revision") != revision
        or value.get("role") != role
        or value.get("ready") is not True
        or value.get("deployment_hold") is not True
        or value.get("release_authority") is not False
        or value.get("tenant_auth_ready") is not True
        or _HEX64.fullmatch(str(value.get("response_sha256") or "")) is None
    ):
        raise CommissionError("vm_release_receipt_loopback_invalid")


def validate_vm_release_receipt(
    contract: Mapping[str, Any],
    path: Path | None,
    acknowledgement: str | None,
    *,
    expected_certificate: Mapping[str, Any],
    now: datetime | None = None,
) -> str:
    """Validate a fresh, redacted receipt produced on the commissioned VM."""

    if (
        path is None
        or not path.is_absolute()
        or not path.is_file()
        or path.is_symlink()
    ):
        raise CommissionError("vm_release_receipt_required")
    try:
        raw = path.read_bytes()
        value = json.loads(raw)
    except (OSError, ValueError, TypeError, UnicodeError) as exc:
        raise CommissionError("vm_release_receipt_invalid") from exc
    if not 0 < len(raw) <= 4 * 1024 * 1024 or not isinstance(value, Mapping):
        raise CommissionError("vm_release_receipt_invalid")
    receipt_hash = sha256(raw)
    if (
        _HEX64.fullmatch(str(acknowledgement or "")) is None
        or not secrets.compare_digest(acknowledgement, receipt_hash)
    ):
        raise CommissionError("vm_release_receipt_acknowledgement_invalid")
    if set(value) != {
        "schema", "project", "zone", "instance", "status",
        "attached_service_account", "attached_scopes", "contract_sha256",
        "source_revision", "recorded_at", "bundle_manifest_sha256",
        "source_tree_sha256", "public_bridge_source_sha256",
        "public_bridge_certificate_sha256", "public_bridge_certificate",
        "units", "broker_tokens",
        "loopback_health", "restart_continuity", "deployment_hold",
        "release_authority", "secret_values_recorded",
    }:
        raise CommissionError("vm_release_receipt_invalid")
    vm = contract["vm_workload_identity"]
    required = vm["release_readback_receipt"]
    if (
        value.get("schema") != required["schema"]
        or value.get("project") != contract["project"]
        or value.get("zone") != contract["zone"]
        or value.get("instance") != vm["instance"]
        or value.get("status") != required["required_status"]
        or value.get("attached_service_account")
        != vm["attached_service_account"]
        or value.get("attached_scopes")
        != required["required_attached_oauth_scopes"]
        or value.get("contract_sha256") != sha256(canonical(contract))
        or value.get("source_revision")
        != contract["release"]["source_revision"]
        or value.get("deployment_hold") is not True
        or value.get("release_authority") is not False
        or value.get("secret_values_recorded") is not False
        or any(
            _HEX64.fullmatch(str(value.get(key) or "")) is None
            for key in (
                "bundle_manifest_sha256", "source_tree_sha256",
                "public_bridge_source_sha256",
                "public_bridge_certificate_sha256",
            )
        )
    ):
        raise CommissionError("vm_release_receipt_binding_invalid")
    observed_now = (now or datetime.now(UTC)).astimezone(UTC)
    certificate = validate_public_bridge_certificate_evidence(
        contract,
        value.get("public_bridge_certificate"),
        now=observed_now,
        reason="vm_release_receipt_certificate_invalid",
    )
    expected_certificate_value = validate_public_bridge_certificate_evidence(
        contract,
        expected_certificate,
        now=observed_now,
        reason="vm_release_receipt_certificate_invalid",
    )
    if (
        not secrets.compare_digest(
            sha256(canonical(certificate)),
            sha256(canonical(expected_certificate_value)),
        )
        or value.get("public_bridge_certificate_sha256")
        != expected_certificate_value["fingerprint_sha256"]
    ):
        raise CommissionError("vm_release_receipt_certificate_binding_invalid")
    recorded_at = _parse_timestamp(
        value.get("recorded_at"), "vm_release_receipt_time_invalid"
    )
    receipt_age = (observed_now - recorded_at).total_seconds()
    if receipt_age < -30 or receipt_age > required["maximum_age_seconds"]:
        raise CommissionError("vm_release_receipt_stale")

    units = value.get("units")
    expected_units = vm["all_aureon_units"]
    if not isinstance(units, list) or len(units) != len(expected_units):
        raise CommissionError("vm_release_receipt_unit_inventory_invalid")
    unit_order: list[str] = []
    for row in units:
        if not isinstance(row, Mapping) or set(row) != {
            "unit", "user", "active", "enabled", "result",
            "exec_main_status", "fragment_path", "fragment_sha256",
            "executable_path", "executable_sha256", "started_at",
        }:
            raise CommissionError("vm_release_receipt_unit_inventory_invalid")
        unit = row.get("unit")
        if not isinstance(unit, str) or unit not in expected_units:
            raise CommissionError("vm_release_receipt_unit_inventory_invalid")
        unit_order.append(unit)
        started_at = _parse_timestamp(
            row.get("started_at"), "vm_release_receipt_unit_time_invalid"
        )
        start_age = (recorded_at - started_at).total_seconds()
        if (
            row.get("user") != _vm_expected_unit_user(contract, unit)
            or row.get("active") is not True
            or row.get("enabled") is not True
            or row.get("result") != "success"
            or row.get("exec_main_status") != 0
            or isinstance(row.get("exec_main_status"), bool)
            or row.get("fragment_path") != f"/etc/systemd/system/{unit}"
            or row.get("executable_path") != _vm_expected_executable(unit)
            or _HEX64.fullmatch(str(row.get("fragment_sha256") or ""))
            is None
            or _HEX64.fullmatch(str(row.get("executable_sha256") or ""))
            is None
            or start_age < -30
            or start_age > required["maximum_age_seconds"]
        ):
            raise CommissionError("vm_release_receipt_unit_readback_invalid")
    if len(set(unit_order)) != len(expected_units) or set(unit_order) != set(
        expected_units
    ):
        raise CommissionError("vm_release_receipt_unit_inventory_invalid")

    token_rows = value.get("broker_tokens")
    token_targets = {row["name"]: row for row in vm["workloads"]}
    if not isinstance(token_rows, list) or len(token_rows) != len(token_targets):
        raise CommissionError("vm_release_receipt_token_readback_invalid")
    token_names: set[str] = set()
    for row in token_rows:
        if not isinstance(row, Mapping) or set(row) != {
            "workload", "target_service_account", "token_path", "schema",
            "owner_uid", "owner_gid", "reader_uid", "reader_gid", "mode",
            "expires_at", "observed_at", "readback_sha256",
            "secret_value_recorded",
        }:
            raise CommissionError("vm_release_receipt_token_readback_invalid")
        name = row.get("workload")
        target = token_targets.get(name) if isinstance(name, str) else None
        if target is None or name in token_names:
            raise CommissionError("vm_release_receipt_token_readback_invalid")
        token_names.add(name)
        observed_at = _parse_timestamp(
            row.get("observed_at"), "vm_release_receipt_token_time_invalid"
        )
        expires_at = _parse_timestamp(
            row.get("expires_at"), "vm_release_receipt_token_time_invalid"
        )
        token_age = (observed_now - observed_at).total_seconds()
        remaining = (expires_at - observed_now).total_seconds()
        lifetime = (expires_at - observed_at).total_seconds()
        integer_fields = (
            row.get("owner_uid"), row.get("owner_gid"),
            row.get("reader_uid"), row.get("reader_gid"),
        )
        if (
            row.get("target_service_account") != target["service_account"]
            or row.get("token_path") != target["token_file"]
            or row.get("schema") != vm["token_schema"]
            or any(
                not isinstance(item, int) or isinstance(item, bool)
                for item in integer_fields
            )
            or row.get("owner_uid") != 0
            or row.get("reader_uid", 0) <= 0
            or row.get("owner_gid", 0) <= 0
            or row.get("owner_gid") != row.get("reader_gid")
            or row.get("mode") != "0640"
            or row.get("secret_value_recorded") is not False
            or _HEX64.fullmatch(str(row.get("readback_sha256") or ""))
            is None
            or token_age < -30
            or token_age > required["maximum_age_seconds"]
            or observed_at > recorded_at + timedelta(seconds=30)
            or remaining <= required["minimum_token_validity_seconds"]
            or lifetime > required["maximum_token_lifetime_seconds"]
            or lifetime <= required["minimum_token_validity_seconds"]
        ):
            raise CommissionError("vm_release_receipt_token_readback_invalid")
    if token_names != set(token_targets):
        raise CommissionError("vm_release_receipt_token_readback_invalid")

    loopback = value.get("loopback_health")
    expected_loopbacks = required["required_loopback_roles"]
    if not isinstance(loopback, Mapping) or set(loopback) != set(
        expected_loopbacks
    ):
        raise CommissionError("vm_release_receipt_loopback_invalid")
    for role, unit in expected_loopbacks.items():
        _validate_vm_http_health(
            loopback[role], role=role, unit=unit,
            revision=contract["release"]["source_revision"],
        )

    continuity = value.get("restart_continuity")
    if not isinstance(continuity, Mapping) or set(continuity) != {
        "controlled_restart", "boot_id_before_sha256",
        "boot_id_after_sha256", "boot_id_unchanged",
        "broker_before_workloads", "start_order", "restart_order",
        "readback", "reboot_validation",
    }:
        raise CommissionError("vm_release_receipt_continuity_invalid")
    boot_before = str(continuity.get("boot_id_before_sha256") or "")
    if (
        continuity.get("controlled_restart")
        != required["required_controlled_restart"]
        or _HEX64.fullmatch(boot_before) is None
        or continuity.get("boot_id_after_sha256") != boot_before
        or continuity.get("boot_id_unchanged") is not True
        or continuity.get("broker_before_workloads") is not True
        or continuity.get("start_order") != unit_order
        or continuity.get("restart_order") != unit_order
        or not unit_order
        or unit_order[0] != vm["broker_unit"]
        or continuity.get("reboot_validation")
        != required["required_reboot_validation"]
    ):
        raise CommissionError("vm_release_receipt_continuity_invalid")
    restart_rows = continuity.get("readback")
    if not isinstance(restart_rows, list) or len(restart_rows) != len(unit_order):
        raise CommissionError("vm_release_receipt_continuity_invalid")
    for expected_unit, row in zip(unit_order, restart_rows, strict=True):
        if (
            not isinstance(row, Mapping)
            or set(row) != {"unit", "revision", "passed", "readback"}
            or row.get("unit") != expected_unit
            or row.get("revision") != contract["release"]["source_revision"]
            or row.get("passed") is not True
            or not isinstance(row.get("readback"), Mapping)
        ):
            raise CommissionError("vm_release_receipt_continuity_invalid")
        readback = row["readback"]
        role = next(
            (
                candidate
                for candidate, candidate_unit in expected_loopbacks.items()
                if candidate_unit == expected_unit
            ),
            None,
        )
        if role is not None:
            _validate_vm_http_health(
                {"unit": expected_unit, **readback},
                role=role,
                unit=expected_unit,
                revision=contract["release"]["source_revision"],
            )
        elif expected_unit == vm["broker_unit"]:
            if readback != {"ready": True, "tokens_fresh": True}:
                raise CommissionError("vm_release_receipt_continuity_invalid")
        elif expected_unit == vm["public_bridge"]["unit"]:
            if (
                set(readback)
                != {"tls", "http_status", "certificate_pinned", "response_sha256"}
                or readback.get("tls") is not True
                or readback.get("certificate_pinned") is not True
                or readback.get("http_status") not in {200, 400, 401, 403, 503}
                or _HEX64.fullmatch(
                    str(readback.get("response_sha256") or "")
                )
                is None
            ):
                raise CommissionError("vm_release_receipt_continuity_invalid")
        elif readback != {}:
            raise CommissionError("vm_release_receipt_continuity_invalid")
    return receipt_hash


def validate_vm_reboot_continuity_receipt(
    contract: Mapping[str, Any],
    path: Path | None,
    acknowledgement: str | None,
    vm_release_path: Path | None,
    vm_release_sha256: str | None,
    *,
    expected_certificate: Mapping[str, Any],
    now: datetime | None = None,
) -> str:
    """Validate post-reboot VM state and its exact pre-reboot receipt link."""

    if (
        path is None
        or not path.is_absolute()
        or not path.is_file()
        or path.is_symlink()
        or vm_release_path is None
        or not vm_release_path.is_absolute()
        or not vm_release_path.is_file()
        or vm_release_path.is_symlink()
    ):
        raise CommissionError("vm_reboot_continuity_receipt_required")
    try:
        raw = path.read_bytes()
        value = json.loads(raw)
        release_raw = vm_release_path.read_bytes()
        release_value = json.loads(release_raw)
    except (OSError, ValueError, TypeError, UnicodeError) as exc:
        raise CommissionError("vm_reboot_continuity_receipt_invalid") from exc
    if (
        not 0 < len(raw) <= 4 * 1024 * 1024
        or not isinstance(value, Mapping)
        or not isinstance(release_value, Mapping)
        or _HEX64.fullmatch(str(vm_release_sha256 or "")) is None
        or sha256(release_raw) != vm_release_sha256
    ):
        raise CommissionError("vm_reboot_continuity_receipt_invalid")
    receipt_hash = sha256(raw)
    if (
        _HEX64.fullmatch(str(acknowledgement or "")) is None
        or not secrets.compare_digest(acknowledgement, receipt_hash)
    ):
        raise CommissionError(
            "vm_reboot_continuity_receipt_acknowledgement_invalid"
        )
    if set(value) != {
        "schema", "status", "recorded_at", "vm_release_receipt_sha256",
        "contract_sha256", "source_revision", "bundle_manifest_sha256",
        "source_tree_sha256", "project", "zone", "instance",
        "attached_service_account", "attached_scopes",
        "boot_id_before_sha256", "boot_id_after_sha256", "boot_id_changed",
        "vm_status", "units", "broker_tokens", "loopback_health",
        "public_bridge_source_sha256", "public_bridge_certificate_sha256",
        "public_bridge_certificate",
        "deployment_hold", "release_authority", "secret_values_recorded",
    }:
        raise CommissionError("vm_reboot_continuity_receipt_invalid")
    vm = contract["vm_workload_identity"]
    required = vm["reboot_continuity_receipt"]
    linked_fields = (
        "contract_sha256", "source_revision", "bundle_manifest_sha256",
        "source_tree_sha256", "project", "zone", "instance",
        "attached_service_account", "attached_scopes",
        "public_bridge_source_sha256",
        "public_bridge_certificate_sha256",
        "public_bridge_certificate",
    )
    if (
        value.get("schema") != required["schema"]
        or value.get("status") != required["required_status"]
        or value.get("vm_status") != required["required_vm_status"]
        or value.get("vm_release_receipt_sha256") != vm_release_sha256
        or any(value.get(key) != release_value.get(key) for key in linked_fields)
        or value.get("contract_sha256") != sha256(canonical(contract))
        or value.get("source_revision")
        != contract["release"]["source_revision"]
        or value.get("project") != contract["project"]
        or value.get("zone") != contract["zone"]
        or value.get("instance") != vm["instance"]
        or value.get("attached_service_account")
        != vm["attached_service_account"]
        or value.get("attached_scopes") != vm["attached_oauth_scopes"]
        or value.get("deployment_hold") is not True
        or value.get("release_authority") is not False
        or value.get("secret_values_recorded") is not False
    ):
        raise CommissionError("vm_reboot_continuity_binding_invalid")
    observed_now = (now or datetime.now(UTC)).astimezone(UTC)
    certificate = validate_public_bridge_certificate_evidence(
        contract,
        value.get("public_bridge_certificate"),
        now=observed_now,
        reason="vm_reboot_continuity_certificate_invalid",
    )
    expected_certificate_value = validate_public_bridge_certificate_evidence(
        contract,
        expected_certificate,
        now=observed_now,
        reason="vm_reboot_continuity_certificate_invalid",
    )
    if (
        not secrets.compare_digest(
            sha256(canonical(certificate)),
            sha256(canonical(expected_certificate_value)),
        )
        or value.get("public_bridge_certificate_sha256")
        != expected_certificate_value["fingerprint_sha256"]
    ):
        raise CommissionError(
            "vm_reboot_continuity_certificate_binding_invalid"
        )
    recorded_at = _parse_timestamp(
        value.get("recorded_at"), "vm_reboot_continuity_time_invalid"
    )
    age = (observed_now - recorded_at).total_seconds()
    if age < -30 or age > required["maximum_age_seconds"]:
        raise CommissionError("vm_reboot_continuity_receipt_stale")
    before_boot = str(value.get("boot_id_before_sha256") or "")
    after_boot = str(value.get("boot_id_after_sha256") or "")
    release_boot = release_value.get("restart_continuity", {}).get(
        "boot_id_after_sha256"
    )
    if (
        _HEX64.fullmatch(before_boot) is None
        or _HEX64.fullmatch(after_boot) is None
        or before_boot != release_boot
        or after_boot == before_boot
        or value.get("boot_id_changed") is not True
    ):
        raise CommissionError("vm_reboot_continuity_boot_invalid")

    release_units = {
        row.get("unit"): row
        for row in release_value.get("units", [])
        if isinstance(row, Mapping)
    }
    units = value.get("units")
    expected_units = set(vm["all_aureon_units"])
    if not isinstance(units, list) or len(units) != len(expected_units):
        raise CommissionError("vm_reboot_continuity_unit_inventory_invalid")
    seen_units: set[str] = set()
    for row in units:
        if not isinstance(row, Mapping) or set(row) != {
            "unit", "user", "active", "enabled", "result",
            "exec_main_status", "fragment_sha256", "executable_sha256",
            "observed_at",
        }:
            raise CommissionError("vm_reboot_continuity_unit_inventory_invalid")
        unit = row.get("unit")
        prior = release_units.get(unit)
        if (
            not isinstance(unit, str)
            or unit not in expected_units
            or unit in seen_units
            or not isinstance(prior, Mapping)
        ):
            raise CommissionError("vm_reboot_continuity_unit_inventory_invalid")
        seen_units.add(unit)
        observed_at = _parse_timestamp(
            row.get("observed_at"), "vm_reboot_continuity_time_invalid"
        )
        unit_age = (observed_now - observed_at).total_seconds()
        if (
            row.get("user") != _vm_expected_unit_user(contract, unit)
            or row.get("active") is not True
            or row.get("enabled") is not True
            or row.get("result") != "success"
            or row.get("exec_main_status") != 0
            or isinstance(row.get("exec_main_status"), bool)
            or row.get("fragment_sha256") != prior.get("fragment_sha256")
            or row.get("executable_sha256")
            != prior.get("executable_sha256")
            or unit_age < -30
            or unit_age > required["maximum_age_seconds"]
            or observed_at > recorded_at + timedelta(seconds=30)
        ):
            raise CommissionError("vm_reboot_continuity_unit_readback_invalid")
    if seen_units != expected_units:
        raise CommissionError("vm_reboot_continuity_unit_inventory_invalid")

    tokens = value.get("broker_tokens")
    token_targets = {row["name"]: row for row in vm["workloads"]}
    if not isinstance(tokens, list) or len(tokens) != len(token_targets):
        raise CommissionError("vm_reboot_continuity_token_readback_invalid")
    seen_tokens: set[str] = set()
    release_token_names = {
        row.get("workload")
        for row in release_value.get("broker_tokens", [])
        if isinstance(row, Mapping)
    }
    release_token_rules = vm["release_readback_receipt"]
    for row in tokens:
        if not isinstance(row, Mapping) or set(row) != {
            "workload", "target_service_account", "token_path", "schema",
            "owner_uid", "owner_gid", "reader_uid", "reader_gid", "mode",
            "expires_at", "observed_at", "readback_sha256",
            "secret_value_recorded",
        }:
            raise CommissionError("vm_reboot_continuity_token_readback_invalid")
        name = row.get("workload")
        target = token_targets.get(name) if isinstance(name, str) else None
        if (
            target is None
            or name in seen_tokens
            or name not in release_token_names
        ):
            raise CommissionError("vm_reboot_continuity_token_readback_invalid")
        seen_tokens.add(name)
        token_observed = _parse_timestamp(
            row.get("observed_at"), "vm_reboot_continuity_time_invalid"
        )
        expires = _parse_timestamp(
            row.get("expires_at"), "vm_reboot_continuity_time_invalid"
        )
        integer_fields = (
            row.get("owner_uid"), row.get("owner_gid"),
            row.get("reader_uid"), row.get("reader_gid"),
        )
        if (
            row.get("target_service_account") != target["service_account"]
            or row.get("token_path") != target["token_file"]
            or row.get("schema") != vm["token_schema"]
            or any(
                not isinstance(item, int) or isinstance(item, bool)
                for item in integer_fields
            )
            or row.get("owner_uid") != 0
            or row.get("reader_uid", 0) <= 0
            or row.get("owner_gid", 0) <= 0
            or row.get("owner_gid") != row.get("reader_gid")
            or row.get("mode") != "0640"
            or row.get("secret_value_recorded") is not False
            or _HEX64.fullmatch(str(row.get("readback_sha256") or ""))
            is None
            or (observed_now - token_observed).total_seconds() < -30
            or (observed_now - token_observed).total_seconds()
            > required["maximum_age_seconds"]
            or token_observed > recorded_at + timedelta(seconds=30)
            or (expires - observed_now).total_seconds()
            <= release_token_rules["minimum_token_validity_seconds"]
            or (expires - token_observed).total_seconds()
            > release_token_rules["maximum_token_lifetime_seconds"]
        ):
            raise CommissionError("vm_reboot_continuity_token_readback_invalid")
    if seen_tokens != set(token_targets):
        raise CommissionError("vm_reboot_continuity_token_readback_invalid")

    loopback = value.get("loopback_health")
    roles = required["required_loopback_roles"]
    if not isinstance(loopback, Mapping) or set(loopback) != set(roles):
        raise CommissionError("vm_reboot_continuity_loopback_invalid")
    for role in ("operator", "ui-gateway"):
        _validate_vm_http_health(
            loopback[role],
            role=role,
            unit=roles[role],
            revision=contract["release"]["source_revision"],
        )
    public = loopback["public-bridge"]
    if (
        not isinstance(public, Mapping)
        or set(public) != {"unit", "revision", "passed", "readback"}
        or public.get("unit") != roles["public-bridge"]
        or public.get("revision") != contract["release"]["source_revision"]
        or public.get("passed") is not True
        or not isinstance(public.get("readback"), Mapping)
    ):
        raise CommissionError("vm_reboot_continuity_loopback_invalid")
    public_readback = public["readback"]
    if (
        set(public_readback)
        != {"tls", "http_status", "certificate_pinned", "response_sha256"}
        or public_readback.get("tls") is not True
        or public_readback.get("certificate_pinned") is not True
        or public_readback.get("http_status") not in {200, 400, 401, 403, 503}
        or _HEX64.fullmatch(
            str(public_readback.get("response_sha256") or "")
        )
        is None
    ):
        raise CommissionError("vm_reboot_continuity_loopback_invalid")
    return receipt_hash


def validate_immutable_image_build_receipt(
    contract: Mapping[str, Any],
    path: Path | None,
    acknowledgement: str | None,
    *,
    now: datetime | None = None,
) -> tuple[str, dict[str, str], dict[str, Any]]:
    """Bind both resolved image digests to one fresh commit-bound build receipt."""

    if (
        path is None
        or not path.is_absolute()
        or not path.is_file()
        or path.is_symlink()
    ):
        raise CommissionError("immutable_image_build_receipt_required")
    try:
        raw = path.read_bytes()
        value = json.loads(raw)
    except (OSError, ValueError, TypeError, UnicodeError) as exc:
        raise CommissionError("immutable_image_build_receipt_invalid") from exc
    if (
        not 0 < len(raw) <= 256 * 1024
        or not isinstance(value, Mapping)
        or set(value)
        != {
            "schema",
            "status",
            "recorded_at",
            "project",
            "region",
            "source_revision",
            "source_tree",
            "plan_sha256",
            "certificate_receipt_sha256",
            "certificate_fingerprint_sha256",
            "certificate",
            "images",
            "secret_values_recorded",
            "release_authority",
            "mutation_authority",
        }
    ):
        raise CommissionError("immutable_image_build_receipt_invalid")
    receipt_hash = sha256(canonical(value))
    if (
        _HEX64.fullmatch(str(acknowledgement or "")) is None
        or not secrets.compare_digest(str(acknowledgement), receipt_hash)
    ):
        raise CommissionError(
            "immutable_image_build_receipt_acknowledgement_invalid"
        )
    recorded = _parse_timestamp(
        value.get("recorded_at"), "immutable_image_build_receipt_time_invalid"
    )
    current = (now or datetime.now(UTC)).astimezone(UTC)
    age = (current - recorded).total_seconds()
    if age < -30 or age > 21_600:
        raise CommissionError("immutable_image_build_receipt_time_invalid")
    expected_schema = contract["commissioning"][
        "immutable_image_build_receipt_schema"
    ]
    if (
        value.get("schema") != expected_schema
        or value.get("status") != "built_and_digest_resolved"
        or value.get("project") != contract["project"]
        or value.get("region") != contract["region"]
        or value.get("source_revision")
        != contract["release"]["source_revision"]
        or _REVISION.fullmatch(str(value.get("source_tree") or "")) is None
        or _HEX64.fullmatch(str(value.get("plan_sha256") or "")) is None
        or _HEX64.fullmatch(
            str(value.get("certificate_receipt_sha256") or "")
        )
        is None
        or _HEX64.fullmatch(
            str(value.get("certificate_fingerprint_sha256") or "")
        )
        is None
        or value.get("secret_values_recorded") is not False
        or value.get("release_authority") is not False
        or value.get("mutation_authority") is not False
    ):
        raise CommissionError("immutable_image_build_receipt_binding_invalid")
    certificate = value.get("certificate")
    bridge = contract["vm_workload_identity"]["public_bridge"]
    if (
        not isinstance(certificate, Mapping)
        or set(certificate)
        != {
            "receipt_sha256",
            "fingerprint_sha256",
            "required_ip_sans",
            "not_before",
            "not_after",
            "minimum_remaining_validity_seconds",
        }
        or certificate.get("receipt_sha256")
        != value.get("certificate_receipt_sha256")
        or certificate.get("fingerprint_sha256")
        != value.get("certificate_fingerprint_sha256")
        or certificate.get("required_ip_sans") != bridge["required_ip_sans"]
        or certificate.get("minimum_remaining_validity_seconds")
        != bridge["minimum_remaining_validity_seconds"]
    ):
        raise CommissionError("immutable_image_build_certificate_invalid")
    not_before = _parse_timestamp(
        certificate.get("not_before"),
        "immutable_image_build_certificate_invalid",
    )
    not_after = _parse_timestamp(
        certificate.get("not_after"),
        "immutable_image_build_certificate_invalid",
    )
    if (
        not_before > recorded
        or recorded > not_after
        or current < not_before
        or (not_after - current).total_seconds()
        < bridge["minimum_remaining_validity_seconds"]
    ):
        raise CommissionError("immutable_image_build_certificate_invalid")
    images = value.get("images")
    expected = {
        "authority": contract["release"]["authority_image"],
        "public_entry": contract["release"]["public_entry_image"],
    }
    observed: dict[str, str] = {}
    if not isinstance(images, list) or len(images) != len(expected):
        raise CommissionError("immutable_image_build_receipt_invalid")
    for row in images:
        if (
            not isinstance(row, Mapping)
            or set(row)
            != {"name", "build_id", "context_sha256", "image"}
        ):
            raise CommissionError("immutable_image_build_receipt_invalid")
        name = row.get("name")
        image = row.get("image")
        if (
            name not in expected
            or name in observed
            or image != expected[name]
            or re.fullmatch(r"[A-Za-z0-9_-]{8,128}", str(row.get("build_id") or ""))
            is None
            or _HEX64.fullmatch(str(row.get("context_sha256") or "")) is None
        ):
            raise CommissionError("immutable_image_build_receipt_binding_invalid")
        observed[str(name)] = str(image)
    if observed != expected:
        raise CommissionError("immutable_image_build_receipt_binding_invalid")
    return receipt_hash, observed, dict(certificate)


def staged_provider_readback(
    contract: Mapping[str, Any],
    snapshot: Mapping[str, Any],
    image_build_receipt_sha256: str,
    certificate: Mapping[str, Any],
) -> dict[str, Any]:
    """Return exact redacted Cloud Run evidence, rather than a generic pass hash."""

    services = []
    observed = snapshot.get("cloud_run", {})
    for expected in contract["cloud_run"]["services"]:
        actual = observed.get(expected["name"])
        if not isinstance(actual, Mapping):
            raise CommissionError("staged_revision_provider_readback_not_exact")
        services.append(
            {
                "name": expected["name"],
                "revision": actual.get("latest_created_revision"),
                "latest_ready_revision": actual.get("latest_ready_revision"),
                "traffic": actual.get("traffic"),
                "image": actual.get("image"),
                "configuration_sha256": sha256(canonical(dict(actual))),
            }
        )
    return {
        "schema": "aureon.gcp.cloud-run-staged-provider-readback.v1",
        "project": contract["project"],
        "region": contract["region"],
        "contract_sha256": sha256(canonical(contract)),
        "source_revision": contract["release"]["source_revision"],
        "image_build_receipt_sha256": image_build_receipt_sha256,
        "public_bridge_certificate": dict(certificate),
        "services": services,
        "secret_values_recorded": False,
        "release_authority": False,
        "mutation_authority": False,
    }


def immutable_subscription_mismatches(
    contract: Mapping[str, Any], snapshot: Mapping[str, Any]
) -> list[str]:
    """Return subscriptions whose immutable provider fields require replacement."""

    actual_subscriptions = snapshot.get("subscriptions", {})
    result: list[str] = []
    for row in contract["pubsub"]["push_subscriptions"]:
        actual = actual_subscriptions.get(row["name"])
        if isinstance(actual, Mapping) and (
            actual.get("topic") != row["topic"]
            or actual.get("enable_message_ordering")
            != row["enable_message_ordering"]
        ):
            result.append(row["name"])
    terminal = contract["pubsub"]["terminal_readback_subscription"]
    actual = actual_subscriptions.get(terminal["name"])
    if isinstance(actual, Mapping) and (
        actual.get("topic") != terminal["topic"]
        or actual.get("enable_message_ordering")
        != terminal["enable_message_ordering"]
        or actual.get("push_endpoint")
    ):
        result.append(terminal["name"])
    return sorted(result)


def _expected_subscription_configuration(
    contract: Mapping[str, Any], subscriptions: Mapping[str, Any]
) -> dict[str, Any]:
    names = [
        *(row["name"] for row in contract["pubsub"]["push_subscriptions"]),
        contract["pubsub"]["terminal_readback_subscription"]["name"],
    ]
    return {
        "schema": "aureon.gcp.pubsub-exact-subscription-readback.v1",
        "project": contract["project"],
        "contract_sha256": sha256(canonical(contract)),
        "source_revision": contract["release"]["source_revision"],
        "subscriptions": {
            name: dict(subscriptions[name]) for name in sorted(names)
        },
        "secret_values_recorded": False,
        "release_authority": False,
        "mutation_authority": False,
    }


def _validate_exact_subscription_configuration(
    contract: Mapping[str, Any], value: object
) -> None:
    if not isinstance(value, Mapping):
        raise CommissionError("exact_subscription_readback_invalid")
    expected_subscriptions: dict[str, dict[str, Any]] = {}
    for row in contract["pubsub"]["push_subscriptions"]:
        expected_subscriptions[row["name"]] = {
            **{
                key: row[key]
                for key in (
                    "topic",
                    "push_endpoint",
                    "oidc_service_account",
                    "oidc_audience",
                    "ack_deadline_seconds",
                    "message_retention_duration",
                    "expiration_period",
                    "minimum_backoff",
                    "maximum_backoff",
                    "enable_message_ordering",
                    "push_no_wrapper",
                )
            },
            "subscribers": [],
        }
    terminal = contract["pubsub"]["terminal_readback_subscription"]
    expected_subscriptions[terminal["name"]] = {
        **{
            key: terminal[key]
            for key in (
                "topic",
                "ack_deadline_seconds",
                "message_retention_duration",
                "expiration_period",
                "enable_message_ordering",
                "enable_exactly_once_delivery",
            )
        },
        "push_endpoint": None,
        "subscribers": list(terminal["subscribers"]),
    }
    if dict(value) != _expected_subscription_configuration(
        contract, expected_subscriptions
    ):
        raise CommissionError("exact_subscription_readback_invalid")


def exact_subscription_configuration(
    contract: Mapping[str, Any], snapshot: Mapping[str, Any]
) -> dict[str, Any]:
    """Return exact redacted subscription state or fail on any field drift."""

    audit = audit_snapshot(contract, snapshot)
    errors = [
        code
        for code in audit["errors"]
        if code.startswith("subscription.")
        and not code.endswith(".retirement_pending")
    ]
    if errors:
        raise CommissionError(
            "replacement_subscriptions_not_exact_before_legacy_retirement"
        )
    subscriptions = snapshot.get("subscriptions", {})
    result = _expected_subscription_configuration(contract, subscriptions)
    _validate_exact_subscription_configuration(contract, result)
    return result


def validate_subscription_replacement_receipt(
    contract: Mapping[str, Any],
    path: Path | None,
    acknowledgement: str | None,
    mismatches: Iterable[str],
    *,
    provider_snapshot: Mapping[str, Any] | None = None,
    now: datetime | None = None,
) -> str:
    """Require publisher freeze and explicit zero backlog before replacement."""

    if (
        path is None
        or not path.is_absolute()
        or not path.is_file()
        or path.is_symlink()
    ):
        raise CommissionError("subscription_replacement_receipt_required")
    try:
        raw = path.read_bytes()
        value = json.loads(raw)
    except (OSError, ValueError, TypeError, UnicodeError) as exc:
        raise CommissionError("subscription_replacement_receipt_invalid") from exc
    if not 0 < len(raw) <= 128 * 1024 or not isinstance(value, Mapping):
        raise CommissionError("subscription_replacement_receipt_invalid")
    if set(value) != {
        "schema", "provider", "project", "contract_sha256",
        "source_revision", "recorded_at", "window_start", "window_end",
        "subscriptions",
    }:
        raise CommissionError("subscription_replacement_receipt_invalid")
    required = contract["pubsub"]["immutable_subscription_replacement"]
    receipt_hash = sha256(canonical(value))
    if (
        _HEX64.fullmatch(str(acknowledgement or "")) is None
        or not secrets.compare_digest(acknowledgement, receipt_hash)
    ):
        raise CommissionError(
            "subscription_replacement_receipt_acknowledgement_invalid"
        )
    if (
        value.get("schema") != required["schema"]
        or value.get("provider") != required["provider"]
        or value.get("project") != contract["project"]
        or value.get("contract_sha256") != sha256(canonical(contract))
        or value.get("source_revision") != contract["release"]["source_revision"]
    ):
        raise CommissionError("subscription_replacement_receipt_binding_invalid")
    observed_now = (now or datetime.now(UTC)).astimezone(UTC)
    recorded_at = _parse_timestamp(
        value.get("recorded_at"), "subscription_replacement_receipt_time_invalid"
    )
    window_start = _parse_timestamp(
        value.get("window_start"), "subscription_replacement_receipt_time_invalid"
    )
    window_end = _parse_timestamp(
        value.get("window_end"), "subscription_replacement_receipt_time_invalid"
    )
    age = (observed_now - recorded_at).total_seconds()
    if (
        age < -30
        or age > required["maximum_age_seconds"]
        or window_end > recorded_at
        or window_end > observed_now + timedelta(seconds=30)
        or (window_end - window_start).total_seconds()
        < required["minimum_window_seconds"]
    ):
        raise CommissionError("subscription_replacement_receipt_time_invalid")
    expected_names = set(mismatches)
    targets = {row["subscription"]: row for row in required["targets"]}
    if not expected_names or not expected_names <= set(targets):
        raise CommissionError("subscription_replacement_target_unsupported")
    subscriptions = value.get("subscriptions")
    if not isinstance(subscriptions, list) or len(subscriptions) != len(expected_names):
        raise CommissionError("subscription_replacement_receipt_invalid")
    seen: set[str] = set()
    expected_metrics = set(required["required_metrics"])
    for row in subscriptions:
        if not isinstance(row, Mapping) or set(row) != {
            "resource_name", "topic_resource_name", "publisher_freeze", "metrics",
        }:
            raise CommissionError("subscription_replacement_receipt_invalid")
        resource = row.get("resource_name")
        prefix = f"projects/{contract['project']}/subscriptions/"
        if not isinstance(resource, str) or not resource.startswith(prefix):
            raise CommissionError("subscription_replacement_receipt_binding_invalid")
        name = resource.removeprefix(prefix)
        if name not in expected_names or name in seen:
            raise CommissionError("subscription_replacement_receipt_binding_invalid")
        seen.add(name)
        target = targets[name]
        if row.get("topic_resource_name") != (
            f"projects/{contract['project']}/topics/{target['topic']}"
        ):
            raise CommissionError("subscription_replacement_receipt_binding_invalid")
        freeze = row.get("publisher_freeze")
        if not isinstance(freeze, Mapping) or set(freeze) != {
            "member", "runtime", "unit", "active_state", "sub_state",
            "unit_file_state", "frozen_since", "observed_at",
            "readback_sha256",
        }:
            raise CommissionError("subscription_replacement_publisher_not_frozen")
        if (
            freeze.get("member") != target["publisher_member"]
            or freeze.get("runtime") != target["publisher_runtime"]
            or freeze.get("unit") != target["publisher_unit"]
            or freeze.get("active_state") != target["required_active_state"]
            or freeze.get("sub_state") != target["required_sub_state"]
            or freeze.get("unit_file_state")
            != target["required_unit_file_state"]
            or _HEX64.fullmatch(str(freeze.get("readback_sha256") or "")) is None
        ):
            raise CommissionError("subscription_replacement_publisher_not_frozen")
        freeze_time = _parse_timestamp(
            freeze.get("observed_at"),
            "subscription_replacement_receipt_time_invalid",
        )
        frozen_since = _parse_timestamp(
            freeze.get("frozen_since"),
            "subscription_replacement_receipt_time_invalid",
        )
        if (
            frozen_since > window_start
            or freeze_time < window_end
            or freeze_time > recorded_at
        ):
            raise CommissionError("subscription_replacement_receipt_time_invalid")
        if provider_snapshot is not None:
            vm_snapshot = provider_snapshot.get("vm", {})
            live_unit = vm_snapshot.get("units", {}).get(
                target["publisher_unit"], {}
            )
            if (
                vm_snapshot.get("systemd_readback_ok") is not True
                or live_unit.get("active_state")
                != target["required_active_state"]
                or live_unit.get("sub_state") != target["required_sub_state"]
                or live_unit.get("unit_file_state")
                != target["required_unit_file_state"]
            ):
                raise CommissionError(
                    "subscription_replacement_publisher_not_frozen"
                )
            live_frozen_since = _parse_timestamp(
                live_unit.get("inactive_enter_timestamp"),
                "subscription_replacement_live_freeze_invalid",
            )
            if abs((live_frozen_since - frozen_since).total_seconds()) > 1:
                raise CommissionError(
                    "subscription_replacement_live_freeze_changed"
                )
        metrics = row.get("metrics")
        if not isinstance(metrics, list):
            raise CommissionError("subscription_replacement_time_series_missing")
        seen_metrics: set[str] = set()
        for metric in metrics:
            if not isinstance(metric, Mapping) or set(metric) != {
                "metric_type", "points",
            }:
                raise CommissionError("subscription_replacement_receipt_invalid")
            metric_type = metric.get("metric_type")
            points = metric.get("points")
            if (
                metric_type not in expected_metrics
                or metric_type in seen_metrics
                or not isinstance(points, list)
                or len(points) < required["minimum_sample_count"]
            ):
                raise CommissionError("subscription_replacement_time_series_missing")
            seen_metrics.add(metric_type)
            point_stamps: set[datetime] = set()
            for point in points:
                if not isinstance(point, Mapping) or set(point) != {
                    "observed_at", "value",
                }:
                    raise CommissionError("subscription_replacement_receipt_invalid")
                stamp = _parse_timestamp(
                    point.get("observed_at"),
                    "subscription_replacement_receipt_time_invalid",
                )
                point_value = point.get("value")
                if (
                    stamp < window_start
                    or stamp > window_end
                    or stamp < frozen_since
                    or stamp in point_stamps
                    or isinstance(point_value, bool)
                    or not isinstance(point_value, (int, float))
                    or float(point_value) != 0.0
                ):
                    raise CommissionError("subscription_replacement_backlog_not_zero")
                point_stamps.add(stamp)
            if (
                max(point_stamps) - min(point_stamps)
            ).total_seconds() < required["minimum_window_seconds"]:
                raise CommissionError("subscription_replacement_time_series_missing")
        if seen_metrics != expected_metrics:
            raise CommissionError("subscription_replacement_time_series_missing")
    if seen != expected_names:
        raise CommissionError("subscription_replacement_time_series_missing")
    return receipt_hash


def validate_legacy_archive_receipt(
    contract: Mapping[str, Any],
    path: Path | None,
    receipt_acknowledgement: str | None,
    scope_acknowledgement: str | None,
    *,
    now: datetime | None = None,
) -> str:
    """Validate the redacted, generation-bound archive completion receipt."""

    if (
        path is None
        or not path.is_absolute()
        or not path.is_file()
        or path.is_symlink()
    ):
        raise CommissionError("legacy_archive_receipt_required")
    try:
        raw = path.read_bytes()
        value = json.loads(raw)
    except (OSError, ValueError, TypeError, UnicodeError) as exc:
        raise CommissionError("legacy_archive_receipt_invalid") from exc
    if (
        not 0 < len(raw) <= 256 * 1024
        or not isinstance(value, Mapping)
        or set(value) != {
            "schema", "status", "provider", "project", "contract_sha256",
            "source_revision", "recorded_at", "scope_sha256",
            "publisher_freeze", "publisher_freeze_reverified_after_drain",
            "archive_bucket_reverified_after_drain", "archive_bucket",
            "archive_kms_key_sha256", "root_manifest",
            "acknowledged_this_run", "archived_bytes_this_run",
            "batch_manifests_this_run", "empty_poll_confirmations",
            "subscription_deleted", "order_execution",
            "cloud_run_traffic_changed", "release_authority",
        }
    ):
        raise CommissionError("legacy_archive_receipt_invalid")
    required = contract["pubsub"]["legacy_archive_receipt"]
    receipt_hash = sha256(canonical(value))
    if (
        _HEX64.fullmatch(str(receipt_acknowledgement or "")) is None
        or not secrets.compare_digest(receipt_acknowledgement, receipt_hash)
    ):
        raise CommissionError("legacy_archive_receipt_acknowledgement_invalid")
    scope_hash = str(value.get("scope_sha256") or "")
    if (
        _HEX64.fullmatch(scope_hash) is None
        or _HEX64.fullmatch(str(scope_acknowledgement or "")) is None
        or not secrets.compare_digest(scope_acknowledgement, scope_hash)
    ):
        raise CommissionError("legacy_archive_scope_acknowledgement_invalid")
    if (
        value.get("schema") != required["schema"]
        or value.get("status") != required["required_status"]
        or value.get("provider") != required["provider"]
        or value.get("project") != contract["project"]
        or value.get("contract_sha256") != sha256(canonical(contract))
        or value.get("source_revision") != contract["release"]["source_revision"]
        or value.get("publisher_freeze_reverified_after_drain") is not True
        or value.get("archive_bucket_reverified_after_drain") is not True
        or value.get("subscription_deleted") is not False
        or value.get("order_execution") is not False
        or value.get("cloud_run_traffic_changed") is not False
        or value.get("release_authority") is not False
        or _BUCKET.fullmatch(str(value.get("archive_bucket") or "")) is None
        or _HEX64.fullmatch(
            str(value.get("archive_kms_key_sha256") or "")
        )
        is None
    ):
        raise CommissionError("legacy_archive_receipt_binding_invalid")
    recorded_at = _parse_timestamp(
        value.get("recorded_at"), "legacy_archive_receipt_time_invalid"
    )
    observed_now = (now or datetime.now(UTC)).astimezone(UTC)
    if recorded_at > observed_now + timedelta(seconds=30):
        raise CommissionError("legacy_archive_receipt_time_invalid")
    freeze = value.get("publisher_freeze")
    if not isinstance(freeze, Mapping) or set(freeze) != {"instance", "units"}:
        raise CommissionError("legacy_archive_publisher_freeze_invalid")
    freeze_units = freeze.get("units")
    expected_units = set(required["publisher_units"])
    if (
        freeze.get("instance") != contract["vm_workload_identity"]["instance"]
        or not isinstance(freeze_units, list)
        or len(freeze_units) != len(expected_units)
    ):
        raise CommissionError("legacy_archive_publisher_freeze_invalid")
    seen_units: set[str] = set()
    for unit in freeze_units:
        if not isinstance(unit, Mapping) or set(unit) != {
            "unit", "active_state", "unit_file_state",
        }:
            raise CommissionError("legacy_archive_publisher_freeze_invalid")
        name = unit.get("unit")
        if (
            name not in expected_units
            or name in seen_units
            or unit.get("active_state") != "inactive"
            or unit.get("unit_file_state") not in {"disabled", "masked"}
        ):
            raise CommissionError("legacy_archive_publisher_freeze_invalid")
        seen_units.add(str(name))
    root = value.get("root_manifest")
    if not isinstance(root, Mapping) or set(root) != {
        "object_name", "generation", "payload_sha256", "message_count",
    }:
        raise CommissionError("legacy_archive_root_invalid")
    root_hash = str(root.get("payload_sha256") or "")
    root_name = str(root.get("object_name") or "")
    message_count = root.get("message_count")
    if (
        _HEX64.fullmatch(root_hash) is None
        or not str(root.get("generation") or "").isdigit()
        or not root_name.endswith(
            f"/v1/{contract['release']['source_revision']}/"
            f"{sha256(canonical(contract))}/roots/{root_hash}.json"
        )
        or root_name.startswith("/")
        or ".." in root_name.split("/")
        or isinstance(message_count, bool)
        or not isinstance(message_count, int)
        or message_count < 0
    ):
        raise CommissionError("legacy_archive_root_invalid")
    for key in (
        "acknowledged_this_run", "archived_bytes_this_run",
        "batch_manifests_this_run",
    ):
        item = value.get(key)
        if isinstance(item, bool) or not isinstance(item, int) or item < 0:
            raise CommissionError("legacy_archive_receipt_invalid")
    empty = value.get("empty_poll_confirmations")
    expected_subscriptions = {
        f"projects/{contract['project']}/subscriptions/{name}"
        for name in contract["pubsub"]["retire_after_zero_backlog"]
    }
    if not isinstance(empty, list) or len(empty) != len(expected_subscriptions):
        raise CommissionError("legacy_archive_empty_poll_invalid")
    seen_subscriptions: set[str] = set()
    for row in empty:
        if not isinstance(row, Mapping) or set(row) != {"resource_name", "count"}:
            raise CommissionError("legacy_archive_empty_poll_invalid")
        resource = row.get("resource_name")
        count = row.get("count")
        if (
            resource not in expected_subscriptions
            or resource in seen_subscriptions
            or isinstance(count, bool)
            or not isinstance(count, int)
            or count < required["minimum_empty_poll_confirmations"]
        ):
            raise CommissionError("legacy_archive_empty_poll_invalid")
        seen_subscriptions.add(str(resource))
    return receipt_hash


def validate_legacy_retirement_receipt(
    contract: Mapping[str, Any],
    path: Path | None,
    acknowledgement: str | None,
    *,
    now: datetime | None = None,
) -> str:
    """Validate fresh, explicit zero Cloud Monitoring time series.

    The receipt is collected before any manual legacy-subscription deletion.
    It contains only resource names, zero measurements and timestamps.  A
    missing metric or point is a blocker rather than an inferred zero.
    """

    if (
        path is None
        or not path.is_absolute()
        or not path.is_file()
        or path.is_symlink()
    ):
        raise CommissionError("legacy_retirement_receipt_required")
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise CommissionError("legacy_retirement_receipt_invalid") from exc
    if not 0 < len(raw) <= 256 * 1024:
        raise CommissionError("legacy_retirement_receipt_invalid")
    try:
        value = json.loads(raw)
    except (ValueError, TypeError, UnicodeError) as exc:
        raise CommissionError("legacy_retirement_receipt_invalid") from exc
    required = contract["pubsub"]["legacy_retirement_receipt"]
    if not isinstance(value, Mapping) or set(value) != {
        "schema",
        "provider",
        "project",
        "contract_sha256",
        "source_revision",
        "recorded_at",
        "window_start",
        "window_end",
        "subscriptions",
    }:
        raise CommissionError("legacy_retirement_receipt_invalid")
    contract_hash = sha256(canonical(contract))
    receipt_hash = sha256(canonical(value))
    if (
        value.get("schema") != required["schema"]
        or value.get("provider") != required["provider"]
        or value.get("project") != contract["project"]
        or value.get("contract_sha256") != contract_hash
        or value.get("source_revision")
        != contract["release"]["source_revision"]
        or _HEX64.fullmatch(str(acknowledgement or "")) is None
        or acknowledgement != receipt_hash
    ):
        raise CommissionError("legacy_retirement_receipt_binding_invalid")
    current = datetime.now(UTC) if now is None else now.astimezone(UTC)
    recorded = _parse_timestamp(
        value.get("recorded_at"), "legacy_retirement_receipt_time_invalid"
    )
    window_start = _parse_timestamp(
        value.get("window_start"), "legacy_retirement_receipt_time_invalid"
    )
    window_end = _parse_timestamp(
        value.get("window_end"), "legacy_retirement_receipt_time_invalid"
    )
    window_seconds = (window_end - window_start).total_seconds()
    if (
        window_seconds < required["minimum_window_seconds"]
        or window_seconds > required["maximum_age_seconds"]
        or window_end > recorded
        or (recorded - window_end).total_seconds() > 120
        or recorded > current
        or (current - recorded).total_seconds()
        > required["maximum_age_seconds"]
    ):
        raise CommissionError("legacy_retirement_receipt_time_invalid")
    rows = value.get("subscriptions")
    if not isinstance(rows, list):
        raise CommissionError("legacy_retirement_receipt_invalid")
    expected_names = {
        (
            f"projects/{contract['project']}/subscriptions/{name}"
        )
        for name in contract["pubsub"]["retire_after_zero_backlog"]
    }
    seen_names: set[str] = set()
    expected_metrics = set(required["required_metrics"])
    for row in rows:
        if not isinstance(row, Mapping) or set(row) != {
            "resource_name",
            "metrics",
        }:
            raise CommissionError("legacy_retirement_receipt_invalid")
        resource_name = row.get("resource_name")
        if (
            not isinstance(resource_name, str)
            or resource_name in seen_names
            or resource_name not in expected_names
        ):
            raise CommissionError(
                "legacy_retirement_receipt_binding_invalid"
            )
        seen_names.add(resource_name)
        metrics = row.get("metrics")
        if not isinstance(metrics, list):
            raise CommissionError("legacy_retirement_receipt_invalid")
        seen_metrics: set[str] = set()
        for metric in metrics:
            if not isinstance(metric, Mapping) or set(metric) != {
                "metric_type",
                "points",
            }:
                raise CommissionError("legacy_retirement_receipt_invalid")
            metric_type = metric.get("metric_type")
            if (
                not isinstance(metric_type, str)
                or metric_type in seen_metrics
                or metric_type not in expected_metrics
            ):
                raise CommissionError(
                    "legacy_retirement_receipt_binding_invalid"
                )
            seen_metrics.add(metric_type)
            points = metric.get("points")
            if (
                not isinstance(points, list)
                or len(points) < required["minimum_sample_count"]
            ):
                raise CommissionError(
                    "legacy_retirement_time_series_missing"
                )
            observed: set[str] = set()
            for point in points:
                if not isinstance(point, Mapping) or set(point) != {
                    "observed_at",
                    "value",
                }:
                    raise CommissionError(
                        "legacy_retirement_receipt_invalid"
                    )
                stamp_text = point.get("observed_at")
                stamp = _parse_timestamp(
                    stamp_text,
                    "legacy_retirement_receipt_time_invalid",
                )
                point_value = point.get("value")
                if (
                    stamp_text in observed
                    or stamp < window_start
                    or stamp > window_end
                    or isinstance(point_value, bool)
                    or not isinstance(point_value, (int, float))
                    or float(point_value) != 0.0
                ):
                    raise CommissionError(
                        "legacy_retirement_backlog_not_zero"
                    )
                observed.add(stamp_text)
        if seen_metrics != expected_metrics:
            raise CommissionError(
                "legacy_retirement_time_series_missing"
            )
    if seen_names != expected_names:
        raise CommissionError("legacy_retirement_time_series_missing")
    return receipt_hash


def validate_legacy_retirement_evidence_order(
    archive_path: Path | None,
    zero_path: Path | None,
    *,
    retirement_started_at: datetime,
) -> None:
    """Require the archive to precede the zero-backlog observation window."""

    if archive_path is None or zero_path is None:
        raise CommissionError("legacy_retirement_evidence_order_invalid")
    try:
        archive = json.loads(archive_path.read_bytes())
        zero = json.loads(zero_path.read_bytes())
    except (OSError, ValueError, TypeError, UnicodeError) as exc:
        raise CommissionError("legacy_retirement_evidence_order_invalid") from exc
    if not isinstance(archive, Mapping) or not isinstance(zero, Mapping):
        raise CommissionError("legacy_retirement_evidence_order_invalid")
    archive_recorded = _parse_timestamp(
        archive.get("recorded_at"), "legacy_retirement_evidence_order_invalid"
    )
    zero_start = _parse_timestamp(
        zero.get("window_start"), "legacy_retirement_evidence_order_invalid"
    )
    zero_end = _parse_timestamp(
        zero.get("window_end"), "legacy_retirement_evidence_order_invalid"
    )
    zero_recorded = _parse_timestamp(
        zero.get("recorded_at"), "legacy_retirement_evidence_order_invalid"
    )
    started = retirement_started_at.astimezone(UTC)
    if not (
        archive_recorded <= zero_start
        and zero_start <= zero_end
        and zero_end <= zero_recorded
        and zero_recorded <= started
    ):
        raise CommissionError("legacy_retirement_evidence_order_invalid")


def validate_legacy_retirement_phase_receipt(
    contract: Mapping[str, Any],
    path: Path | None,
    acknowledgement: str | None,
    *,
    archive_path: Path | None,
    archive_receipt_acknowledgement: str | None,
    archive_scope_acknowledgement: str | None,
    zero_path: Path | None,
    zero_acknowledgement: str | None,
    retirement_owner_path: Path | None,
    retirement_owner_acknowledgement: str | None,
    now: datetime | None = None,
) -> tuple[str, str, str, str]:
    """Validate the post-deletion receipt and its receipts as of deletion time."""

    if (
        path is None
        or not path.is_absolute()
        or not path.is_file()
        or path.is_symlink()
    ):
        raise CommissionError("legacy_retirement_phase_receipt_required")
    try:
        raw = path.read_bytes()
        value = json.loads(raw)
    except (OSError, ValueError, TypeError, UnicodeError) as exc:
        raise CommissionError("legacy_retirement_phase_receipt_invalid") from exc
    required_keys = {
        "schema",
        "status",
        "phase",
        "retirement_started_at",
        "recorded_at",
        "project",
        "contract_sha256",
        "source_revision",
        "retired_subscription_names",
        "applied_action_ids",
        "provider_readback_ok",
        "provider_readback",
        "provider_readback_sha256",
        "subscription_configuration_sha256",
        "legacy_archive_receipt_sha256",
        "legacy_retirement_receipt_sha256",
        "supabase_owner_readback_receipt_sha256",
        "cloud_run_traffic_changed",
        "order_execution_requested",
        "secret_payloads_requested",
        "sensitive_environment_values_returned",
        "release_authority",
        "mutation_authority",
    }
    if (
        not 0 < len(raw) <= 256 * 1024
        or not isinstance(value, Mapping)
        or set(value) != required_keys
    ):
        raise CommissionError("legacy_retirement_phase_receipt_invalid")
    receipt_hash = sha256(canonical(value))
    if (
        _HEX64.fullmatch(str(acknowledgement or "")) is None
        or not secrets.compare_digest(str(acknowledgement), receipt_hash)
    ):
        raise CommissionError(
            "legacy_retirement_phase_receipt_acknowledgement_invalid"
        )
    recorded = _parse_timestamp(
        value.get("recorded_at"), "legacy_retirement_phase_receipt_time_invalid"
    )
    started = _parse_timestamp(
        value.get("retirement_started_at"),
        "legacy_retirement_phase_receipt_time_invalid",
    )
    current = (now or datetime.now(UTC)).astimezone(UTC)
    if (
        started > recorded
        or (recorded - started).total_seconds() > 86_400
        or (current - started).total_seconds() > 86_400
        or (current - recorded).total_seconds() < -30
        or (current - recorded).total_seconds() > 86_400
    ):
        raise CommissionError("legacy_retirement_phase_receipt_time_invalid")
    targets = sorted(contract["pubsub"]["retire_after_zero_backlog"])
    actions = [f"subscription.{name}.retire" for name in targets]
    readback = value.get("provider_readback")
    if (
        value.get("schema")
        != contract["commissioning"]["legacy_retirement_phase_receipt_schema"]
        or value.get("status") != "legacy_retired"
        or value.get("phase") != "legacy-retirement"
        or value.get("project") != contract["project"]
        or value.get("contract_sha256") != sha256(canonical(contract))
        or value.get("source_revision")
        != contract["release"]["source_revision"]
        or value.get("retired_subscription_names") != targets
        or value.get("applied_action_ids") != actions
        or value.get("provider_readback_ok") is not True
        or not isinstance(readback, Mapping)
        or sha256(canonical(readback))
        != value.get("provider_readback_sha256")
        or _HEX64.fullmatch(
            str(value.get("subscription_configuration_sha256") or "")
        )
        is None
        or value.get("cloud_run_traffic_changed") is not False
        or value.get("order_execution_requested") is not False
        or value.get("secret_payloads_requested") is not False
        or value.get("sensitive_environment_values_returned") is not False
        or value.get("release_authority") is not False
        or value.get("mutation_authority") is not False
    ):
        raise CommissionError("legacy_retirement_phase_receipt_binding_invalid")
    expected_readback = {
        "schema": "aureon.gcp.pubsub-legacy-retirement-provider-readback.v1",
        "project": contract["project"],
        "contract_sha256": sha256(canonical(contract)),
        "source_revision": contract["release"]["source_revision"],
        "legacy_subscriptions_absent": targets,
        "subscription_configuration_sha256": value[
            "subscription_configuration_sha256"
        ],
        "cloud_run_configuration_sha256": readback.get(
            "cloud_run_configuration_sha256"
        ),
        "subscription_configuration": readback.get(
            "subscription_configuration"
        ),
        "publisher_freeze_readback": readback.get(
            "publisher_freeze_readback"
        ),
        "publisher_freeze_readback_sha256": readback.get(
            "publisher_freeze_readback_sha256"
        ),
        "secret_values_recorded": False,
        "release_authority": False,
        "mutation_authority": False,
    }
    if (
        dict(readback) != expected_readback
        or _HEX64.fullmatch(
            str(readback.get("cloud_run_configuration_sha256") or "")
        )
        is None
        or _HEX64.fullmatch(
            str(readback.get("publisher_freeze_readback_sha256") or "")
        )
        is None
        or not isinstance(readback.get("publisher_freeze_readback"), Mapping)
        or sha256(canonical(readback["publisher_freeze_readback"]))
        != readback.get("publisher_freeze_readback_sha256")
    ):
        raise CommissionError("legacy_retirement_phase_receipt_binding_invalid")
    validate_legacy_publisher_freeze_readback(
        contract, readback["publisher_freeze_readback"]
    )
    archive_hash = validate_legacy_archive_receipt(
        contract,
        archive_path,
        archive_receipt_acknowledgement,
        archive_scope_acknowledgement,
        now=started,
    )
    zero_hash = validate_legacy_retirement_receipt(
        contract, zero_path, zero_acknowledgement, now=started
    )
    validate_legacy_retirement_evidence_order(
        archive_path,
        zero_path,
        retirement_started_at=started,
    )
    retirement_owner_hash = validate_supabase_owner_receipt(
        contract,
        retirement_owner_path,
        retirement_owner_acknowledgement,
        now=started,
    )
    if (
        value.get("legacy_archive_receipt_sha256") != archive_hash
        or value.get("legacy_retirement_receipt_sha256") != zero_hash
        or not secrets.compare_digest(
            str(value.get("supabase_owner_readback_receipt_sha256") or ""),
            retirement_owner_hash,
        )
    ):
        raise CommissionError("legacy_retirement_phase_receipt_chain_invalid")
    configuration = readback.get("subscription_configuration")
    _validate_exact_subscription_configuration(contract, configuration)
    if (
        sha256(canonical(configuration))
        != value.get("subscription_configuration_sha256")
    ):
        raise CommissionError("legacy_retirement_phase_receipt_binding_invalid")
    return receipt_hash, archive_hash, zero_hash, retirement_owner_hash


def write_receipt(path: Path, value: Mapping[str, Any]) -> None:
    if not path.is_absolute() or path.exists() and path.is_symlink():
        raise CommissionError("receipt_path_invalid")
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(dict(value), sort_keys=True, indent=2).encode("ascii") + b"\n"
    fd, temporary = tempfile.mkstemp(prefix=".authority-receipt-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
        if os.name == "posix":
            directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def legacy_retirement_progress_path(receipt: Path) -> Path:
    """Return a separate durable journal path for legacy deletion recovery."""

    if not receipt.is_absolute() or receipt.is_symlink():
        raise CommissionError("legacy_retirement_progress_path_invalid")
    suffix = receipt.suffix or ".json"
    progress = receipt.with_name(receipt.stem + ".progress" + suffix)
    if progress == receipt or progress.is_symlink():
        raise CommissionError("legacy_retirement_progress_path_invalid")
    return progress


def _legacy_retirement_progress_receipt(
    contract: Mapping[str, Any],
    *,
    started_at: datetime,
    status: str,
    targets: list[str],
    completed: list[str],
    in_flight: str | None,
    error_code: str | None,
    subscription_configuration_sha256: str,
    cloud_run_configuration_sha256: str,
    archive_receipt_sha256: str,
    zero_receipt_sha256: str,
    owner_receipt_sha256: str,
) -> dict[str, Any]:
    return {
        "schema": LEGACY_RETIREMENT_PROGRESS_SCHEMA,
        "status": status,
        "started_at": started_at.astimezone(UTC).isoformat(),
        "recorded_at": datetime.now(UTC).isoformat(),
        "project": contract["project"],
        "contract_sha256": sha256(canonical(contract)),
        "source_revision": contract["release"]["source_revision"],
        "target_subscription_names": list(targets),
        "completed_subscription_names": list(completed),
        "in_flight_subscription_name": in_flight,
        "error_code": error_code,
        "subscription_configuration_sha256": (
            subscription_configuration_sha256
        ),
        "cloud_run_configuration_sha256": cloud_run_configuration_sha256,
        "legacy_archive_receipt_sha256": archive_receipt_sha256,
        "legacy_retirement_receipt_sha256": zero_receipt_sha256,
        "supabase_owner_readback_receipt_sha256": owner_receipt_sha256,
        "secret_values_recorded": False,
        "release_authority": False,
        "mutation_authority": False,
    }


def _load_legacy_retirement_progress(
    path: Path,
    contract: Mapping[str, Any],
    *,
    targets: list[str],
    subscription_configuration_sha256: str,
    cloud_run_configuration_sha256: str,
    archive_receipt_sha256: str,
    zero_receipt_sha256: str,
    owner_receipt_sha256: str,
) -> dict[str, Any] | None:
    if not path.exists():
        return None
    if not path.is_absolute() or path.is_symlink() or not path.is_file():
        raise CommissionError("legacy_retirement_progress_receipt_invalid")
    try:
        raw = path.read_bytes()
        value = json.loads(raw)
    except (OSError, ValueError, TypeError, UnicodeError) as exc:
        raise CommissionError(
            "legacy_retirement_progress_receipt_invalid"
        ) from exc
    required = _legacy_retirement_progress_receipt(
        contract,
        started_at=datetime.now(UTC),
        status="in_progress",
        targets=targets,
        completed=[],
        in_flight=None,
        error_code=None,
        subscription_configuration_sha256=(
            subscription_configuration_sha256
        ),
        cloud_run_configuration_sha256=cloud_run_configuration_sha256,
        archive_receipt_sha256=archive_receipt_sha256,
        zero_receipt_sha256=zero_receipt_sha256,
        owner_receipt_sha256=owner_receipt_sha256,
    )
    volatile = {
        "status",
        "started_at",
        "recorded_at",
        "completed_subscription_names",
        "in_flight_subscription_name",
        "error_code",
    }
    if (
        not 0 < len(raw) <= 256 * 1024
        or not isinstance(value, Mapping)
        or set(value) != set(required)
        or any(
            value.get(key) != expected
            for key, expected in required.items()
            if key not in volatile
        )
    ):
        raise CommissionError("legacy_retirement_progress_receipt_invalid")
    started_at = _parse_timestamp(
        value.get("started_at"),
        "legacy_retirement_progress_receipt_invalid",
    )
    recorded_at = _parse_timestamp(
        value.get("recorded_at"),
        "legacy_retirement_progress_receipt_invalid",
    )
    completed = value.get("completed_subscription_names")
    in_flight = value.get("in_flight_subscription_name")
    error_code = value.get("error_code")
    status = value.get("status")
    current = datetime.now(UTC)
    if (
        not isinstance(completed, list)
        or any(not isinstance(name, str) for name in completed)
        or completed != targets[: len(completed)]
        or (
            in_flight is not None
            and (
                not isinstance(in_flight, str)
                or len(completed) >= len(targets)
                or in_flight != targets[len(completed)]
            )
        )
        or status
        not in {
            "in_progress",
            "recovery_required",
            "commands_completed_pending_provider_readback",
        }
        or (
            status == "in_progress"
            and error_code is not None
        )
        or (
            status == "recovery_required"
            and (
                in_flight is None
                or error_code
                not in {
                    "legacy_subscription_delete_failed",
                    "legacy_retirement_provider_readback_failed",
                }
            )
        )
        or (
            status == "commands_completed_pending_provider_readback"
            and (
                completed != targets
                or in_flight is not None
                or error_code is not None
            )
        )
        or started_at > recorded_at
        or (current - started_at).total_seconds() < -300
        or (current - started_at).total_seconds() > 86_400
        or (recorded_at - current).total_seconds() > 300
        or _HEX64.fullmatch(
            str(
                value.get(
                    "supabase_owner_readback_receipt_sha256"
                )
                or ""
            )
        )
        is None
    ):
        raise CommissionError("legacy_retirement_progress_receipt_invalid")
    return dict(value)


def _legacy_absent_prefix(
    snapshot: Mapping[str, Any], targets: list[str]
) -> list[str]:
    observed = snapshot.get("legacy_subscriptions")
    if (
        not isinstance(observed, Mapping)
        or any(name not in targets for name in observed)
    ):
        raise CommissionError("legacy_subscription_inventory_not_exact")
    absent = [name for name in targets if name not in observed]
    if absent != targets[: len(absent)]:
        raise CommissionError("legacy_subscription_inventory_not_exact")
    return absent


def validate_legacy_publisher_freeze(
    contract: Mapping[str, Any], snapshot: Mapping[str, Any]
) -> dict[str, Any]:
    """Read back the legacy publishers as stopped and unable to auto-start."""

    vm = snapshot.get("vm")
    required_units = contract["pubsub"]["legacy_archive_receipt"][
        "publisher_units"
    ]
    if (
        not isinstance(vm, Mapping)
        or vm.get("name") != contract["vm_workload_identity"]["instance"]
        or vm.get("status") != "RUNNING"
        or vm.get("systemd_readback_ok") is not True
        or not isinstance(vm.get("units"), Mapping)
    ):
        raise CommissionError("legacy_retirement_publisher_freeze_not_current")
    rows = []
    for unit in required_units:
        value = vm["units"].get(unit)
        if (
            not isinstance(value, Mapping)
            or value.get("active_state") != "inactive"
            or value.get("sub_state") != "dead"
            or value.get("unit_file_state") not in {"disabled", "masked"}
        ):
            raise CommissionError(
                "legacy_retirement_publisher_freeze_not_current"
            )
        rows.append(
            {
                "unit": unit,
                "active_state": "inactive",
                "sub_state": "dead",
                "unit_file_state": value["unit_file_state"],
            }
        )
    readback = {"instance": vm["name"], "units": rows}
    validate_legacy_publisher_freeze_readback(contract, readback)
    return readback


def validate_legacy_publisher_freeze_readback(
    contract: Mapping[str, Any], value: object
) -> None:
    """Validate the redacted systemd evidence embedded in a receipt."""

    required_units = contract["pubsub"]["legacy_archive_receipt"][
        "publisher_units"
    ]
    if (
        not isinstance(value, Mapping)
        or set(value) != {"instance", "units"}
        or value.get("instance")
        != contract["vm_workload_identity"]["instance"]
        or not isinstance(value.get("units"), list)
        or len(value["units"]) != len(required_units)
    ):
        raise CommissionError("legacy_retirement_publisher_freeze_invalid")
    observed = []
    for row in value["units"]:
        if (
            not isinstance(row, Mapping)
            or set(row)
            != {"unit", "active_state", "sub_state", "unit_file_state"}
            or row.get("active_state") != "inactive"
            or row.get("sub_state") != "dead"
            or row.get("unit_file_state") not in {"disabled", "masked"}
        ):
            raise CommissionError(
                "legacy_retirement_publisher_freeze_invalid"
            )
        observed.append(row.get("unit"))
    if observed != required_units:
        raise CommissionError("legacy_retirement_publisher_freeze_invalid")


def validate_legacy_retirement_live_state(
    contract: Mapping[str, Any],
    snapshot: Mapping[str, Any],
    *,
    targets: list[str],
    expected_completed: list[str],
    subscription_configuration_sha256: str,
    cloud_run_configuration_sha256: str,
) -> dict[str, Any]:
    """Re-read every state whose drift would make a deletion unsafe."""

    freeze = validate_legacy_publisher_freeze(contract, snapshot)
    if _legacy_absent_prefix(snapshot, targets) != expected_completed:
        raise CommissionError("legacy_retirement_provider_state_conflict")
    if (
        sha256(canonical(snapshot.get("cloud_run", {})))
        != cloud_run_configuration_sha256
    ):
        raise CommissionError("legacy_retirement_cloud_run_state_changed")
    configuration = exact_subscription_configuration(contract, snapshot)
    if sha256(canonical(configuration)) != subscription_configuration_sha256:
        raise CommissionError(
            "replacement_subscription_state_changed_during_retirement"
        )
    return freeze


def _redacted_summary(contract: Mapping[str, Any], audit: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema": audit["schema"],
        "ok": audit["ok"],
        "error_count": audit["error_count"],
        "errors": audit["errors"],
        "audit_sha256": sha256(canonical(audit)),
        "contract_sha256": sha256(canonical(contract)),
        "source_revision": contract["release"]["source_revision"],
        "authority_image_sha256": contract["release"]["authority_image"].rsplit(":", 1)[-1],
        "public_entry_image_sha256": contract["release"]["public_entry_image"].rsplit(":", 1)[-1],
        "release_authority": False,
        "mutation_authority": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command", nargs="?", choices=("audit", "plan", "apply"),
        default="audit",
    )
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--authority-image", required=True)
    parser.add_argument("--public-entry-image", required=True)
    parser.add_argument("--supabase-project-ref", required=True)
    parser.add_argument("--supabase-owner-subject", required=True)
    parser.add_argument("--supabase-owner-email-sha256", required=True)
    parser.add_argument("--iap-admin-email-sha256", required=True)
    parser.add_argument("--gcloud", default="gcloud")
    parser.add_argument("--receipt", type=Path)
    parser.add_argument(
        "--phase",
        choices=(
            "prepare",
            "resource-prepare",
            "staged-revision-attestation",
            "subscription-replacement",
            "legacy-retirement",
            "finalize",
        ),
        default="resource-prepare",
    )
    parser.add_argument("--acknowledge-contract-sha256")
    parser.add_argument("--legacy-retirement-receipt", type=Path)
    parser.add_argument(
        "--acknowledge-legacy-retirement-sha256"
    )
    parser.add_argument("--legacy-retirement-phase-receipt", type=Path)
    parser.add_argument(
        "--acknowledge-legacy-retirement-phase-sha256"
    )
    parser.add_argument("--legacy-archive-receipt", type=Path)
    parser.add_argument("--acknowledge-legacy-archive-receipt-sha256")
    parser.add_argument("--acknowledge-legacy-archive-scope-sha256")
    parser.add_argument("--supabase-owner-readback-receipt", type=Path)
    parser.add_argument(
        "--acknowledge-supabase-owner-readback-sha256"
    )
    parser.add_argument(
        "--legacy-retirement-owner-readback-receipt", type=Path
    )
    parser.add_argument(
        "--acknowledge-legacy-retirement-owner-readback-sha256"
    )
    parser.add_argument("--subscription-replacement-receipt", type=Path)
    parser.add_argument(
        "--acknowledge-subscription-replacement-sha256"
    )
    parser.add_argument("--vm-release-readback-receipt", type=Path)
    parser.add_argument("--acknowledge-vm-release-readback-sha256")
    parser.add_argument("--vm-reboot-continuity-receipt", type=Path)
    parser.add_argument("--acknowledge-vm-reboot-continuity-sha256")
    parser.add_argument("--immutable-image-build-receipt", type=Path)
    parser.add_argument("--acknowledge-immutable-image-build-receipt-sha256")
    args = parser.parse_args(argv)
    # ``prepare`` remains a compatibility spelling, but receipts use the
    # unambiguous phase name required by the release transaction.
    phase = "resource-prepare" if args.phase == "prepare" else args.phase
    try:
        contract = resolve_contract(
            load_contract(args.contract), source_revision=args.source_revision,
            authority_image=args.authority_image,
            public_entry_image=args.public_entry_image,
            supabase_project_ref=args.supabase_project_ref,
            supabase_owner_subject=args.supabase_owner_subject,
            supabase_owner_email_sha256=args.supabase_owner_email_sha256,
            iap_admin_email_sha256=args.iap_admin_email_sha256,
        )
        runner = Gcloud(args.gcloud, contract["project"])
        snapshot = capture_snapshot(contract, runner)
        audit = audit_snapshot(contract, snapshot)
        summary = _redacted_summary(contract, audit)
        actions = build_iam_actions(contract, snapshot)
        if args.command == "audit":
            if args.receipt is not None:
                write_receipt(
                    args.receipt,
                    {
                        **summary,
                        "schema": RECEIPT_SCHEMA,
                        "status": "audited",
                        "recorded_at": datetime.now(UTC).isoformat(),
                        "secret_payloads_requested": False,
                        "sensitive_environment_values_returned": False,
                    },
                )
            print(json.dumps(summary, sort_keys=True))
            return 0 if audit["ok"] else 1
        if args.command == "plan":
            plan = {
                **summary,
                "planned_prepare_action_ids": [
                    row.action_id
                    for row in actions
                    if not row.destructive and not row.blocked
                ],
                "planned_finalize_action_ids": [
                    row.action_id for row in actions if row.destructive
                ],
                "blocked_action_ids": [
                    row.action_id for row in actions if row.blocked
                ],
            }
            if args.receipt is not None:
                write_receipt(
                    args.receipt,
                    {
                        **plan,
                        "schema": RECEIPT_SCHEMA,
                        "status": "planned",
                        "recorded_at": datetime.now(UTC).isoformat(),
                        "secret_payloads_requested": False,
                        "sensitive_environment_values_returned": False,
                    },
                )
            print(json.dumps(plan, sort_keys=True))
            return 0
        expected_ack = sha256(canonical(contract))
        if args.acknowledge_contract_sha256 != expected_ack:
            raise CommissionError("exact_contract_acknowledgement_required")
        if args.receipt is None:
            raise CommissionError("absolute_receipt_path_required")
        applied: list[str] = []
        legacy_receipt_hash: str | None = None
        legacy_archive_receipt_hash: str | None = None
        legacy_phase_receipt_hash: str | None = None
        owner_receipt_hash: str | None = None
        replacement_receipt_hash: str | None = None
        vm_release_receipt_hash: str | None = None
        vm_reboot_receipt_hash: str | None = None
        image_build_receipt_hash: str | None = None
        image_build_certificate: dict[str, Any] | None = None
        retirement_owner_receipt_hash: str | None = None
        destructive_iam_cleanup_deferred = False
        deferred_destructive_action_ids: set[str] = set()
        broker_identity_readback_ok = broker_identity_attached(
            contract, snapshot
        )
        try:
            owner_receipt_hash = validate_supabase_owner_receipt(
                contract,
                args.supabase_owner_readback_receipt,
                args.acknowledge_supabase_owner_readback_sha256,
            )
            blocked = [row for row in actions if row.blocked]
            if phase == "subscription-replacement":
                mismatches = immutable_subscription_mismatches(
                    contract, snapshot
                )
                replacement_receipt_hash = (
                    validate_subscription_replacement_receipt(
                        contract,
                        args.subscription_replacement_receipt,
                        args.acknowledge_subscription_replacement_sha256,
                        mismatches,
                        provider_snapshot=snapshot,
                    )
                )
                rows = {
                    row["name"]: row
                    for row in contract["pubsub"]["push_subscriptions"]
                }
                for name in mismatches:
                    row = rows.get(name)
                    if row is None:
                        raise CommissionError(
                            "subscription_replacement_target_unsupported"
                        )
                    runner.apply(
                        "pubsub", "subscriptions", "delete", name, "--quiet"
                    )
                    applied.append(f"subscription.{name}.delete-for-replacement")
                    runner.apply(
                        "pubsub", "subscriptions", "create", name,
                        "--topic=" + row["topic"],
                        "--ack-deadline=" + str(row["ack_deadline_seconds"]),
                        "--message-retention-duration="
                        + row["message_retention_duration"],
                        "--expiration-period=" + row["expiration_period"],
                        "--min-retry-delay=" + row["minimum_backoff"],
                        "--max-retry-delay=" + row["maximum_backoff"],
                        "--push-endpoint=" + row["push_endpoint"],
                        "--push-auth-service-account="
                        + row["oidc_service_account"],
                        "--push-auth-token-audience=" + row["oidc_audience"],
                        "--enable-message-ordering",
                    )
                    applied.append(f"subscription.{name}.recreate")
                final_snapshot = capture_snapshot(contract, runner)
                if immutable_subscription_mismatches(contract, final_snapshot):
                    raise CommissionError(
                        "subscription_replacement_provider_readback_not_exact"
                    )
                validate_subscription_replacement_receipt(
                    contract,
                    args.subscription_replacement_receipt,
                    args.acknowledge_subscription_replacement_sha256,
                    mismatches,
                    provider_snapshot=final_snapshot,
                )
                final_audit = audit_snapshot(contract, final_snapshot)
                target_errors = [
                    error
                    for error in final_audit["errors"]
                    if any(
                        error.startswith(f"subscription.{name}.")
                        for name in mismatches
                    )
                ]
                if target_errors:
                    raise CommissionError(
                        "subscription_replacement_provider_readback_not_exact"
                    )
                receipt = {
                    "schema": RECEIPT_SCHEMA,
                    "status": "subscription_replaced",
                    "phase": phase,
                    "recorded_at": datetime.now(UTC).isoformat(),
                    "contract_sha256": expected_ack,
                    "source_revision": contract["release"]["source_revision"],
                    "applied_action_ids": applied,
                    "provider_readback_ok": True,
                    "subscription_replacement_receipt_sha256": (
                        replacement_receipt_hash
                    ),
                    "supabase_owner_readback_receipt_sha256": (
                        owner_receipt_hash
                    ),
                    "secret_payloads_requested": False,
                    "sensitive_environment_values_returned": False,
                    "release_authority": False,
                    "mutation_authority": False,
                }
                write_receipt(args.receipt, receipt)
                print(
                    json.dumps(
                        {
                            "receipt_sha256": sha256(canonical(receipt)),
                            **{
                                key: receipt[key]
                                for key in (
                                    "schema", "status", "phase",
                                    "contract_sha256", "provider_readback_ok",
                                    "release_authority", "mutation_authority",
                                )
                            },
                        },
                        sort_keys=True,
                    )
                )
                return 0

            if phase == "legacy-retirement":
                subscription_readback = exact_subscription_configuration(
                    contract, snapshot
                )
                subscription_configuration_sha256 = sha256(
                    canonical(subscription_readback)
                )
                targets = sorted(
                    contract["pubsub"]["retire_after_zero_backlog"]
                )
                cloud_run_configuration_sha256 = sha256(
                    canonical(snapshot.get("cloud_run", {}))
                )
                validate_legacy_publisher_freeze(contract, snapshot)
                retirement_owner_path = (
                    args.legacy_retirement_owner_readback_receipt
                    or args.supabase_owner_readback_receipt
                )
                retirement_owner_acknowledgement = (
                    args.acknowledge_legacy_retirement_owner_readback_sha256
                    or args.acknowledge_supabase_owner_readback_sha256
                )
                progress_path = legacy_retirement_progress_path(args.receipt)
                progress_value = _load_legacy_retirement_progress(
                    progress_path,
                    contract,
                    targets=targets,
                    subscription_configuration_sha256=(
                        subscription_configuration_sha256
                    ),
                    cloud_run_configuration_sha256=(
                        cloud_run_configuration_sha256
                    ),
                    archive_receipt_sha256=(
                        args.acknowledge_legacy_archive_receipt_sha256
                    ),
                    zero_receipt_sha256=(
                        args.acknowledge_legacy_retirement_sha256
                    ),
                    owner_receipt_sha256=(
                        retirement_owner_acknowledgement or ""
                    ),
                )
                retirement_started_at = (
                    _parse_timestamp(
                        progress_value["started_at"],
                        "legacy_retirement_progress_receipt_invalid",
                    )
                    if progress_value is not None
                    else datetime.now(UTC)
                )
                legacy_archive_receipt_hash = validate_legacy_archive_receipt(
                    contract,
                    args.legacy_archive_receipt,
                    (
                        args.acknowledge_legacy_archive_receipt_sha256
                    ),
                    (
                        args.acknowledge_legacy_archive_scope_sha256
                    ),
                    now=retirement_started_at,
                )
                legacy_receipt_hash = validate_legacy_retirement_receipt(
                    contract,
                    args.legacy_retirement_receipt,
                    (
                        args.acknowledge_legacy_retirement_sha256
                    ),
                    now=retirement_started_at,
                )
                validate_legacy_retirement_evidence_order(
                    args.legacy_archive_receipt,
                    args.legacy_retirement_receipt,
                    retirement_started_at=retirement_started_at,
                )
                retirement_owner_receipt_hash = (
                    validate_supabase_owner_receipt(
                        contract,
                        retirement_owner_path,
                        retirement_owner_acknowledgement,
                        now=retirement_started_at,
                    )
                )
                provider_completed = _legacy_absent_prefix(snapshot, targets)
                if progress_value is None:
                    if provider_completed:
                        raise CommissionError(
                            "legacy_subscription_inventory_not_exact"
                        )
                    completed: list[str] = []
                    in_flight = None
                else:
                    completed = list(
                        progress_value["completed_subscription_names"]
                    )
                    in_flight = progress_value[
                        "in_flight_subscription_name"
                    ]
                    if provider_completed == completed:
                        pass
                    elif (
                        in_flight is not None
                        and provider_completed == [*completed, in_flight]
                    ):
                        completed.append(in_flight)
                        in_flight = None
                    else:
                        raise CommissionError(
                            "legacy_retirement_provider_state_conflict"
                        )
                validate_legacy_retirement_live_state(
                    contract,
                    snapshot,
                    targets=targets,
                    expected_completed=provider_completed,
                    subscription_configuration_sha256=(
                        subscription_configuration_sha256
                    ),
                    cloud_run_configuration_sha256=(
                        cloud_run_configuration_sha256
                    ),
                )

                def persist_legacy_progress(
                    status: str,
                    completed_names: list[str],
                    in_flight_name: str | None,
                    error_code: str | None = None,
                ) -> None:
                    write_receipt(
                        progress_path,
                        _legacy_retirement_progress_receipt(
                            contract,
                            started_at=retirement_started_at,
                            status=status,
                            targets=targets,
                            completed=completed_names,
                            in_flight=in_flight_name,
                            error_code=error_code,
                            subscription_configuration_sha256=(
                                subscription_configuration_sha256
                            ),
                            cloud_run_configuration_sha256=(
                                cloud_run_configuration_sha256
                            ),
                            archive_receipt_sha256=(
                                legacy_archive_receipt_hash
                            ),
                            zero_receipt_sha256=legacy_receipt_hash,
                            owner_receipt_sha256=(
                                retirement_owner_receipt_hash
                            ),
                        ),
                    )

                persist_legacy_progress(
                    "in_progress", completed, None
                )
                applied.extend(
                    f"subscription.{name}.retire" for name in completed
                )
                for name in targets[len(completed) :]:
                    pre_delete_snapshot = capture_snapshot(contract, runner)
                    validate_legacy_retirement_live_state(
                        contract,
                        pre_delete_snapshot,
                        targets=targets,
                        expected_completed=completed,
                        subscription_configuration_sha256=(
                            subscription_configuration_sha256
                        ),
                        cloud_run_configuration_sha256=(
                            cloud_run_configuration_sha256
                        ),
                    )
                    persist_legacy_progress(
                        "in_progress", completed, name
                    )
                    try:
                        runner.apply(
                            "pubsub",
                            "subscriptions",
                            "delete",
                            name,
                            "--quiet",
                        )
                    except CommissionError:
                        persist_legacy_progress(
                            "recovery_required",
                            completed,
                            name,
                            "legacy_subscription_delete_failed",
                        )
                        raise
                    try:
                        step_snapshot = capture_snapshot(contract, runner)
                        expected_completed = [*completed, name]
                        validate_legacy_retirement_live_state(
                            contract,
                            step_snapshot,
                            targets=targets,
                            expected_completed=expected_completed,
                            subscription_configuration_sha256=(
                                subscription_configuration_sha256
                            ),
                            cloud_run_configuration_sha256=(
                                cloud_run_configuration_sha256
                            ),
                        )
                    except CommissionError:
                        persist_legacy_progress(
                            "recovery_required",
                            completed,
                            name,
                            "legacy_retirement_provider_readback_failed",
                        )
                        raise
                    completed.append(name)
                    applied.append(f"subscription.{name}.retire")
                    persist_legacy_progress(
                        "in_progress", completed, None
                    )
                persist_legacy_progress(
                    "commands_completed_pending_provider_readback",
                    completed,
                    None,
                )
                final_snapshot = capture_snapshot(contract, runner)
                final_freeze_readback = validate_legacy_retirement_live_state(
                    contract,
                    final_snapshot,
                    targets=targets,
                    expected_completed=targets,
                    subscription_configuration_sha256=(
                        subscription_configuration_sha256
                    ),
                    cloud_run_configuration_sha256=(
                        cloud_run_configuration_sha256
                    ),
                )
                final_subscription_readback = exact_subscription_configuration(
                    contract, final_snapshot
                )
                if (
                    sha256(canonical(final_subscription_readback))
                    != subscription_configuration_sha256
                ):
                    raise CommissionError(
                        "replacement_subscription_state_changed_during_retirement"
                    )
                provider_readback = {
                    "schema": (
                        "aureon.gcp.pubsub-legacy-retirement-provider-readback.v1"
                    ),
                    "project": contract["project"],
                    "contract_sha256": expected_ack,
                    "source_revision": contract["release"]["source_revision"],
                    "legacy_subscriptions_absent": targets,
                    "subscription_configuration_sha256": (
                        subscription_configuration_sha256
                    ),
                    "cloud_run_configuration_sha256": (
                        cloud_run_configuration_sha256
                    ),
                    "subscription_configuration": subscription_readback,
                    "publisher_freeze_readback": final_freeze_readback,
                    "publisher_freeze_readback_sha256": sha256(
                        canonical(final_freeze_readback)
                    ),
                    "secret_values_recorded": False,
                    "release_authority": False,
                    "mutation_authority": False,
                }
                receipt = {
                    "schema": contract["commissioning"][
                        "legacy_retirement_phase_receipt_schema"
                    ],
                    "status": "legacy_retired",
                    "phase": phase,
                    "retirement_started_at": (
                        retirement_started_at.isoformat()
                    ),
                    "recorded_at": datetime.now(UTC).isoformat(),
                    "project": contract["project"],
                    "contract_sha256": expected_ack,
                    "source_revision": contract["release"]["source_revision"],
                    "retired_subscription_names": targets,
                    "applied_action_ids": applied,
                    "provider_readback_ok": True,
                    "provider_readback": provider_readback,
                    "provider_readback_sha256": sha256(
                        canonical(provider_readback)
                    ),
                    "subscription_configuration_sha256": (
                        subscription_configuration_sha256
                    ),
                    "legacy_archive_receipt_sha256": (
                        legacy_archive_receipt_hash
                    ),
                    "legacy_retirement_receipt_sha256": legacy_receipt_hash,
                    "supabase_owner_readback_receipt_sha256": (
                        retirement_owner_receipt_hash
                    ),
                    "cloud_run_traffic_changed": False,
                    "order_execution_requested": False,
                    "secret_payloads_requested": False,
                    "sensitive_environment_values_returned": False,
                    "release_authority": False,
                    "mutation_authority": False,
                }
                write_receipt(args.receipt, receipt)
                print(
                    json.dumps(
                        {
                            "receipt_sha256": sha256(canonical(receipt)),
                            **{
                                key: receipt[key]
                                for key in (
                                    "schema",
                                    "status",
                                    "phase",
                                    "contract_sha256",
                                    "provider_readback_ok",
                                    "release_authority",
                                    "mutation_authority",
                                )
                            },
                        },
                        sort_keys=True,
                    )
                )
                return 0

            if phase == "staged-revision-attestation":
                if blocked:
                    raise CommissionError(
                        "subscription_replacement_required_before_staged_attestation"
                    )
                (
                    image_build_receipt_hash,
                    _,
                    image_build_certificate,
                ) = (
                    validate_immutable_image_build_receipt(
                        contract,
                        args.immutable_image_build_receipt,
                        args.acknowledge_immutable_image_build_receipt_sha256,
                    )
                )
                staged_audit = audit_snapshot(
                    contract,
                    snapshot,
                    allow_iam_extras=False,
                    allow_vm_pending=True,
                    cloud_run_mode="staged",
                )
                remaining_non_destructive = [
                    row.action_id
                    for row in actions
                    if not row.destructive and not row.blocked
                ]
                if not staged_audit["ok"] or remaining_non_destructive:
                    raise CommissionError(
                        "staged_revision_provider_readback_not_exact"
                    )
                provider_readback = staged_provider_readback(
                    contract,
                    snapshot,
                    image_build_receipt_hash,
                    image_build_certificate,
                )
                receipt = {
                    "schema": RECEIPT_SCHEMA,
                    "status": "staged_attested",
                    "phase": phase,
                    "recorded_at": datetime.now(UTC).isoformat(),
                    "contract_sha256": expected_ack,
                    "source_revision": contract["release"]["source_revision"],
                    "applied_action_ids": [],
                    "provider_readback_ok": True,
                    "provider_readback": provider_readback,
                    "provider_readback_sha256": sha256(
                        canonical(provider_readback)
                    ),
                    "provider_error_codes": [],
                    "cloud_run_staged_without_traffic": True,
                    "cloud_run_traffic_changed": False,
                    "vm_readback_deferred_to_release_receipt": True,
                    "supabase_owner_readback_receipt_sha256": (
                        owner_receipt_hash
                    ),
                    "immutable_image_build_receipt_sha256": (
                        image_build_receipt_hash
                    ),
                    "public_bridge_certificate": image_build_certificate,
                    "secret_payloads_requested": False,
                    "sensitive_environment_values_returned": False,
                    "release_authority": False,
                    "mutation_authority": False,
                }
                write_receipt(args.receipt, receipt)
                print(
                    json.dumps(
                        {
                            key: receipt[key]
                            for key in (
                                "schema",
                                "status",
                                "phase",
                                "contract_sha256",
                                "provider_readback_ok",
                                "release_authority",
                                "mutation_authority",
                            )
                        },
                        sort_keys=True,
                    )
                )
                return 0

            if blocked and phase != "resource-prepare":
                raise CommissionError(
                    "manual_subscription_replacement_required"
                )
            # Finalization may remove the old VM union and other broad grants.
            # Do not make a single destructive change until every non-removal
            # property already reads back exactly.
            if phase == "finalize":
                (
                    image_build_receipt_hash,
                    _,
                    image_build_certificate,
                ) = validate_immutable_image_build_receipt(
                    contract,
                    args.immutable_image_build_receipt,
                    args.acknowledge_immutable_image_build_receipt_sha256,
                )
                vm_release_receipt_hash = validate_vm_release_receipt(
                    contract,
                    args.vm_release_readback_receipt,
                    args.acknowledge_vm_release_readback_sha256,
                    expected_certificate=image_build_certificate,
                )
                vm_reboot_receipt_hash = (
                    validate_vm_reboot_continuity_receipt(
                        contract,
                        args.vm_reboot_continuity_receipt,
                        args.acknowledge_vm_reboot_continuity_sha256,
                        args.vm_release_readback_receipt,
                        vm_release_receipt_hash,
                        expected_certificate=image_build_certificate,
                    )
                )
                (
                    legacy_phase_receipt_hash,
                    legacy_archive_receipt_hash,
                    legacy_receipt_hash,
                    retirement_owner_receipt_hash,
                ) = validate_legacy_retirement_phase_receipt(
                    contract,
                    args.legacy_retirement_phase_receipt,
                    args.acknowledge_legacy_retirement_phase_sha256,
                    archive_path=args.legacy_archive_receipt,
                    archive_receipt_acknowledgement=(
                        args.acknowledge_legacy_archive_receipt_sha256
                    ),
                    archive_scope_acknowledgement=(
                        args.acknowledge_legacy_archive_scope_sha256
                    ),
                    zero_path=args.legacy_retirement_receipt,
                    zero_acknowledgement=(
                        args.acknowledge_legacy_retirement_sha256
                    ),
                    retirement_owner_path=(
                        args.legacy_retirement_owner_readback_receipt
                    ),
                    retirement_owner_acknowledgement=(
                        args.acknowledge_legacy_retirement_owner_readback_sha256
                    ),
                )
                prerequisite = audit_snapshot(
                    contract, snapshot, allow_iam_extras=True,
                )
                if not prerequisite["ok"]:
                    raise CommissionError(
                        "finalize_prerequisites_not_exact"
                    )
                selected = actions
            elif phase == "resource-prepare":
                selected = [
                    row
                    for row in actions
                    if not row.destructive and not row.blocked
                ]
                for action in selected:
                    runner.apply(*action.args)
                    applied.append(action.action_id)
                prepared_snapshot = capture_snapshot(contract, runner)
                prepared_audit = audit_snapshot(
                    contract,
                    prepared_snapshot,
                    allow_iam_extras=True,
                    allow_vm_pending=True,
                    cloud_run_mode="deferred",
                    allow_legacy_pending=True,
                    allow_immutable_subscription_pending=True,
                )
                prepared_actions = build_iam_actions(
                    contract, prepared_snapshot
                )
                broker_identity_readback_ok = broker_identity_attached(
                    contract, prepared_snapshot
                )
                if (
                    not prepared_audit["ok"]
                    or any(
                        not row.destructive and not row.blocked
                        for row in prepared_actions
                    )
                ):
                    raise CommissionError("prepare_provider_readback_not_exact")
                # Exact narrow grants now exist. Remove broad/extraneous grants
                # before any revision can be attested or promoted.
                destructive_actions = [
                    action for action in prepared_actions if action.destructive
                ]
                old_union_member_argument = (
                    "--member=serviceAccount:"
                    + contract["vm_workload_identity"]["old_union_identity"]
                )
                broker_gated_actions = [
                    action
                    for action in destructive_actions
                    if old_union_member_argument in action.args
                ]
                deferred_destructive_action_ids = {
                    action.action_id for action in broker_gated_actions
                }
                destructive_iam_cleanup_deferred = bool(
                    broker_gated_actions
                ) and not broker_identity_readback_ok
                for action in destructive_actions:
                    if (
                        action not in broker_gated_actions
                        or broker_identity_readback_ok
                    ):
                        runner.apply(*action.args)
                        applied.append(action.action_id)
                selected = []
            else:
                selected = []
            for action in selected:
                runner.apply(*action.args)
                applied.append(action.action_id)
            final_snapshot = capture_snapshot(contract, runner)
            final_broker_identity_readback_ok = broker_identity_attached(
                contract, final_snapshot
            )
            if (
                phase == "resource-prepare"
                and broker_identity_readback_ok
                and deferred_destructive_action_ids
                and not final_broker_identity_readback_ok
            ):
                raise CommissionError("broker_identity_readback_changed")
            broker_identity_readback_ok = final_broker_identity_readback_ok
            final_audit = audit_snapshot(
                contract,
                final_snapshot,
                allow_iam_extras=(
                    phase == "resource-prepare"
                    and destructive_iam_cleanup_deferred
                ),
                allow_vm_pending=phase == "resource-prepare",
                cloud_run_mode=(
                    "deferred"
                    if phase == "resource-prepare"
                    else "serving"
                ),
                allow_legacy_pending=phase == "resource-prepare",
                allow_immutable_subscription_pending=(
                    phase == "resource-prepare"
                ),
            )
            remaining = build_iam_actions(contract, final_snapshot)
            if phase == "resource-prepare" and any(
                not row.blocked
                and not (
                    destructive_iam_cleanup_deferred
                    and row.action_id in deferred_destructive_action_ids
                )
                for row in remaining
            ):
                raise CommissionError("prepare_provider_readback_not_exact")
            if phase == "resource-prepare" and not final_audit["ok"]:
                raise CommissionError("prepare_provider_readback_not_exact")
            if phase == "finalize" and not final_audit["ok"]:
                raise CommissionError("provider_readback_not_exact")
            receipt = {
                "schema": RECEIPT_SCHEMA,
                "status": (
                    "applied" if phase == "finalize" else "resources_prepared"
                ),
                "phase": phase,
                "recorded_at": datetime.now(UTC).isoformat(),
                "contract_sha256": expected_ack,
                "source_revision": contract["release"]["source_revision"],
                "applied_action_ids": applied,
                "provider_readback_ok": final_audit["ok"],
                "provider_readback_sha256": sha256(
                    canonical(final_audit)
                ),
                "legacy_retirement_receipt_sha256": (
                    legacy_receipt_hash
                ),
                "legacy_archive_receipt_sha256": (
                    legacy_archive_receipt_hash
                ),
                "legacy_retirement_phase_receipt_sha256": (
                    legacy_phase_receipt_hash
                ),
                "supabase_owner_readback_receipt_sha256": owner_receipt_hash,
                "legacy_retirement_owner_readback_receipt_sha256": (
                    retirement_owner_receipt_hash
                ),
                "vm_release_readback_receipt_sha256": vm_release_receipt_hash,
                "vm_reboot_continuity_receipt_sha256": vm_reboot_receipt_hash,
                "immutable_image_build_receipt_sha256": (
                    image_build_receipt_hash
                ),
                "public_bridge_certificate": image_build_certificate,
                "provider_error_codes": final_audit["errors"],
                "vm_readback_deferred_to_release_receipt": (
                    final_audit[
                        "vm_readback_deferred_to_release_receipt"
                    ]
                ),
                "cloud_run_readback_mode": final_audit[
                    "cloud_run_readback_mode"
                ],
                "cloud_run_staged_without_traffic": final_audit[
                    "cloud_run_staged_without_traffic"
                ],
                "legacy_retirement_deferred": final_audit[
                    "legacy_retirement_deferred"
                ],
                "immutable_subscription_replacement_deferred": final_audit[
                    "immutable_subscription_replacement_deferred"
                ],
                "broker_identity_readback_ok": broker_identity_readback_ok,
                "destructive_iam_cleanup_deferred": (
                    destructive_iam_cleanup_deferred
                ),
                "secret_payloads_requested": False,
                "sensitive_environment_values_returned": False,
                "release_authority": False,
                "mutation_authority": False,
            }
            write_receipt(args.receipt, receipt)
            print(json.dumps({key: receipt[key] for key in ("schema", "status", "phase", "contract_sha256", "provider_readback_ok", "release_authority", "mutation_authority")}, sort_keys=True))
            return 0
        except Exception as exc:
            failure = {
                "schema": RECEIPT_SCHEMA,
                "status": "failed_closed",
                "phase": phase,
                "recorded_at": datetime.now(UTC).isoformat(),
                "contract_sha256": expected_ack,
                "source_revision": contract["release"]["source_revision"],
                "applied_action_ids": applied,
                "provider_readback_ok": False,
                "supabase_owner_readback_receipt_sha256": owner_receipt_hash,
                "legacy_retirement_owner_readback_receipt_sha256": (
                    retirement_owner_receipt_hash
                ),
                "subscription_replacement_receipt_sha256": (
                    replacement_receipt_hash
                ),
                "legacy_archive_receipt_sha256": (
                    legacy_archive_receipt_hash
                ),
                "legacy_retirement_phase_receipt_sha256": (
                    legacy_phase_receipt_hash
                ),
                "vm_release_readback_receipt_sha256": (
                    vm_release_receipt_hash
                ),
                "vm_reboot_continuity_receipt_sha256": (
                    vm_reboot_receipt_hash
                ),
                "immutable_image_build_receipt_sha256": (
                    image_build_receipt_hash
                ),
                "error_code": (
                    str(exc)
                    if isinstance(exc, CommissionError)
                    else "commission_apply_failed"
                ),
                "secret_payloads_requested": False,
                "sensitive_environment_values_returned": False,
                "release_authority": False,
                "mutation_authority": False,
            }
            write_receipt(args.receipt, failure)
            raise CommissionError("commission_apply_failed_closed") from exc
    except CommissionError as exc:
        print(str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
