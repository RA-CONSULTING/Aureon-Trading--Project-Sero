"""Offline tests for the exact Google Cloud authority commissioning contract."""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime, timedelta
import importlib.util
import json
from pathlib import Path
import shlex
import subprocess
import sys

import pytest


MODULE = (
    Path(__file__).resolve().parents[1]
    / "trading-control"
    / "authority_commission.py"
)
spec = importlib.util.spec_from_file_location("authority_commission", MODULE)
assert spec and spec.loader
commission = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = commission
spec.loader.exec_module(commission)

REVISION = "a" * 40
AUTHORITY_IMAGE = (
    "europe-west1-docker.pkg.dev/aureon-trading/aureon-web/"
    "aureon-trading-authority@sha256:" + "b" * 64
)
PUBLIC_IMAGE = (
    "europe-west1-docker.pkg.dev/aureon-trading/aureon-web/"
    "aureon-public-entry@sha256:" + "c" * 64
)
OWNER_SUBJECT = "12345678-1234-4123-8123-123456789abc"
OWNER_EMAIL_SHA256 = "d" * 64
IAP_ADMIN_EMAIL_SHA256 = "e" * 64
SUPABASE_PROJECT_REF = "fixtureprojectref123"


def resolved_contract():
    return commission.resolve_contract(
        commission.load_contract(),
        source_revision=REVISION,
        authority_image=AUTHORITY_IMAGE,
        public_entry_image=PUBLIC_IMAGE,
        supabase_project_ref=SUPABASE_PROJECT_REF,
        supabase_owner_subject=OWNER_SUBJECT,
        supabase_owner_email_sha256=OWNER_EMAIL_SHA256,
        iap_admin_email_sha256=IAP_ADMIN_EMAIL_SHA256,
    )


def policy(role=None, members=()):
    bindings = []
    if role is not None:
        bindings.append({"role": role, "members": list(members)})
    return {"bindings": bindings}


def exact_snapshot(contract):
    project_bindings = []
    for row in contract["iam"]["firestore"]["custom_roles"]:
        project_bindings.append(
            {
                "role": f"projects/{contract['project']}/roles/{row['id']}",
                "members": list(row["members"]),
            }
        )
    snapshot = {
        "cloud_run": {},
        "topics": {},
        "subscriptions": {},
        "legacy_subscriptions": {},
        "service_accounts": {},
        "service_account_iam": {},
        "kms": {},
        "secrets": {},
        "custom_roles": {},
        "project_iam": {"bindings": project_bindings},
        "firestore": {
            "name": contract["iam"]["firestore"]["database"],
            "location": contract["iam"]["firestore"]["location"],
            "delete_protection": True,
        },
        "enabled_apis": list(contract["required_apis"]),
    }
    for row in contract["cloud_run"]["services"]:
        serving_revision = row["name"] + "-00001-test"
        snapshot["cloud_run"][row["name"]] = {
            "url": row["url"],
            "serving_revision": serving_revision,
            "latest_created_revision": serving_revision,
            "latest_ready_revision": serving_revision,
            "inspected_revision": serving_revision,
            "ready": True,
            "traffic": [
                {
                    "revision": serving_revision,
                    "percent": 100,
                    "tag": None,
                }
            ],
            "service_account": row["service_account"],
            "image": contract["release"][row["image_parameter"]],
            "ingress": row["ingress"],
            "iap_enabled": row["iap_enabled"],
            "timeout_seconds": row["timeout_seconds"],
            "container_concurrency": row["container_concurrency"],
            "container_count": 1,
            "resources": deepcopy(row["resources"]),
            "scaling": deepcopy(row["scaling"]),
            "startup_cpu_boost": row["startup_cpu_boost"],
            "cpu_idle": row["cpu_idle"],
            "startup_probe": deepcopy(row["startup_probe"]),
            "direct_vpc": deepcopy(row["direct_vpc"]),
            "legacy_vpc_connector": None,
            "environment": deepcopy(row["environment"]),
            "secret_environment": [],
            "invokers": list(row["invokers"]),
        }
    for row in contract["pubsub"]["topics"]:
        snapshot["topics"][row["name"]] = {
            "publishers": list(row["publishers"])
        }
    for row in contract["pubsub"]["push_subscriptions"]:
        snapshot["subscriptions"][row["name"]] = {
            **{
                key: deepcopy(row[key])
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
    snapshot["subscriptions"][terminal["name"]] = {
        **{
            key: deepcopy(terminal[key])
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
    for account in commission.service_account_emails(contract):
        snapshot["service_accounts"][account] = {
            "email": account,
            "disabled": False,
        }
        snapshot["service_account_iam"][account] = policy()
    service_agent = "serviceAccount:" + contract["pubsub"]["service_agent"]
    for account in contract["iam"]["pubsub_oidc_token_creators"]:
        snapshot["service_account_iam"][account] = policy(
            "roles/iam.serviceAccountTokenCreator", [service_agent]
        )
    broker = (
        "serviceAccount:"
        + contract["vm_workload_identity"]["attached_service_account"]
    )
    for row in contract["vm_workload_identity"]["workloads"]:
        snapshot["service_account_iam"][row["service_account"]] = policy(
            "roles/iam.serviceAccountTokenCreator", [broker]
        )
    for row in contract["iam"]["kms_keys"]:
        snapshot["kms"][row["name"]] = {
            "signers": list(row["signers"]),
            "public_key_viewers": list(row["public_key_viewers"]),
            "purpose": row["purpose"],
            "configured_algorithm": row["algorithm"],
            "version": row["version"],
            "version_state": "ENABLED",
            "version_algorithm": row["algorithm"],
        }
    for row in contract["iam"]["secrets"]:
        snapshot["secrets"][row["id"]] = {
            "readers": list(row["readers"]),
            "version": row["version"],
            "version_state": "ENABLED",
        }
    for row in contract["iam"]["firestore"]["custom_roles"]:
        snapshot["custom_roles"][row["id"]] = {
            "permissions": list(row["permissions"]),
            "stage": row["stage"],
            "title": row["title"],
        }
    vm = contract["vm_workload_identity"]
    units = {
        name: {
            "user": "aureon",
            "group": "aureon",
            "supplementary_groups": [],
            "exec_start": "/bin/true",
            "ip_address_deny": (
                vm["metadata_ipv4"] + " " + vm["metadata_ipv6"]
            ),
            "ip_address_allow": "",
            "environment": {},
            "active_state": "active",
            "sub_state": "running",
            "unit_file_state": "enabled",
            "result": "success",
            "exec_main_status": "0",
            "environment_parse_error": False,
            "sensitive_environment_name_hashes": [],
        }
        for name in vm["all_aureon_units"]
    }
    units[vm["broker_unit"]] = {
        "user": "root",
        "group": "root",
        "supplementary_groups": [],
        "exec_start": vm["broker_exec"],
        "ip_address_deny": "",
        "ip_address_allow": "",
        "environment": {},
        "active_state": "active",
        "sub_state": "running",
        "unit_file_state": "enabled",
        "result": "success",
        "exec_main_status": "0",
        "environment_parse_error": False,
        "sensitive_environment_name_hashes": [],
    }
    for row in vm["workloads"]:
        for unit in row["units"]:
            units[unit].update(
                {
                    "user": row["user"],
                    "supplementary_groups": row["supplementary_groups"],
                    "environment": {
                        "AUREON_GOOGLE_TOKEN_FILE": row["token_file"],
                        "AUREON_VM_TOKEN_BROKER_REQUIRED": "1",
                        "AUREON_GCP_PROJECT_NUMBER": contract[
                            "project_number"
                        ],
                        **row.get("required_environment", {}),
                    },
                }
            )
    bridge = vm["public_bridge"]
    units[bridge["unit"]].update(
        {
            "environment_file_bound": True,
            "effective_environment": deepcopy(bridge["required_environment"]),
            "effective_environment_parse_error": False,
            "effective_sensitive_environment_name_hashes": [],
        }
    )
    snapshot["vm"] = {
        "name": vm["instance"],
        "status": "RUNNING",
        "service_accounts": [
            {
                "email": vm["attached_service_account"],
                "scopes": vm["attached_oauth_scopes"],
            }
        ],
        "systemd_readback_ok": True,
        "units": units,
        "paths": {
            row["path"]: {
                key: row[key] for key in ("kind", "owner", "group", "mode")
            }
            for row in [*vm["token_storage"], *vm["shared_state_exchange"]]
        },
    }
    return snapshot


def freeze_legacy_publishers(contract, snapshot):
    for unit in contract["pubsub"]["legacy_archive_receipt"][
        "publisher_units"
    ]:
        snapshot["vm"]["units"][unit].update(
            active_state="inactive",
            sub_state="dead",
            unit_file_state="disabled",
        )
    return snapshot


def cli_args(command=None):
    result = []
    if command:
        result.append(command)
    return [
        *result,
        "--source-revision",
        REVISION,
        "--authority-image",
        AUTHORITY_IMAGE,
        "--public-entry-image",
        PUBLIC_IMAGE,
        "--supabase-project-ref",
        SUPABASE_PROJECT_REF,
        "--supabase-owner-subject",
        OWNER_SUBJECT,
        "--supabase-owner-email-sha256",
        OWNER_EMAIL_SHA256,
        "--iap-admin-email-sha256",
        IAP_ADMIN_EMAIL_SHA256,
    ]


def stub_valid_finalize_evidence(monkeypatch):
    monkeypatch.setattr(
        commission,
        "validate_supabase_owner_receipt",
        lambda *_args, **_kwargs: "1" * 64,
    )
    monkeypatch.setattr(
        commission,
        "validate_immutable_image_build_receipt",
        lambda *_args, **_kwargs: (
            "2" * 64,
            {},
            {"fingerprint_sha256": "3" * 64},
        ),
    )
    monkeypatch.setattr(
        commission,
        "validate_vm_release_receipt",
        lambda *_args, **_kwargs: "4" * 64,
    )
    monkeypatch.setattr(
        commission,
        "validate_vm_reboot_continuity_receipt",
        lambda *_args, **_kwargs: "5" * 64,
    )
    monkeypatch.setattr(
        commission,
        "validate_legacy_retirement_phase_receipt",
        lambda *_args, **_kwargs: (
            "6" * 64,
            "7" * 64,
            "8" * 64,
            "9" * 64,
        ),
    )


def owner_readback_receipt(contract, now):
    return {
        "schema": "aureon.supabase-owner-provider-readback.v1",
        "provider": "supabase_auth_admin",
        "project_ref": SUPABASE_PROJECT_REF,
        "subject": OWNER_SUBJECT,
        "app_metadata_role": "owner",
        "email_confirmed": True,
        "email_sha256": OWNER_EMAIL_SHA256,
        "recorded_at": now.isoformat(),
        "source_revision": REVISION,
        "contract_sha256": commission.sha256(commission.canonical(contract)),
    }


def certificate_evidence(contract, now):
    return {
        "receipt_sha256": "2" * 64,
        "fingerprint_sha256": "3" * 64,
        "required_ip_sans": list(
            contract["vm_workload_identity"]["public_bridge"][
                "required_ip_sans"
            ]
        ),
        "not_before": (now - timedelta(days=1)).isoformat(),
        "not_after": (now + timedelta(days=30)).isoformat(),
        "minimum_remaining_validity_seconds": contract[
            "vm_workload_identity"
        ]["public_bridge"]["minimum_remaining_validity_seconds"],
    }


def immutable_image_receipt(contract, now):
    certificate = certificate_evidence(contract, now)
    return {
        "schema": contract["commissioning"][
            "immutable_image_build_receipt_schema"
        ],
        "status": "built_and_digest_resolved",
        "recorded_at": now.isoformat(),
        "project": contract["project"],
        "region": contract["region"],
        "source_revision": REVISION,
        "source_tree": "9" * 40,
        "plan_sha256": "1" * 64,
        "certificate_receipt_sha256": "2" * 64,
        "certificate_fingerprint_sha256": "3" * 64,
        "certificate": certificate,
        "images": [
            {
                "name": "authority",
                "build_id": "fixture-build-authority",
                "context_sha256": "4" * 64,
                "image": contract["release"]["authority_image"],
            },
            {
                "name": "public_entry",
                "build_id": "fixture-build-public",
                "context_sha256": "5" * 64,
                "image": contract["release"]["public_entry_image"],
            },
        ],
        "secret_values_recorded": False,
        "release_authority": False,
        "mutation_authority": False,
    }


def legacy_retirement_phase_receipt(
    contract, now, *, owner, archive, zero, snapshot=None
):
    provider_snapshot = snapshot or exact_snapshot(contract)
    subscriptions = commission.exact_subscription_configuration(
        contract, provider_snapshot
    )
    subscription_hash = commission.sha256(
        commission.canonical(subscriptions)
    )
    targets = sorted(contract["pubsub"]["retire_after_zero_backlog"])
    publisher_freeze = {
        "instance": contract["vm_workload_identity"]["instance"],
        "units": [
            {
                "unit": unit,
                "active_state": "inactive",
                "sub_state": "dead",
                "unit_file_state": "disabled",
            }
            for unit in contract["pubsub"]["legacy_archive_receipt"][
                "publisher_units"
            ]
        ],
    }
    provider = {
        "schema": "aureon.gcp.pubsub-legacy-retirement-provider-readback.v1",
        "project": contract["project"],
        "contract_sha256": commission.sha256(commission.canonical(contract)),
        "source_revision": REVISION,
        "legacy_subscriptions_absent": targets,
        "subscription_configuration_sha256": subscription_hash,
        "cloud_run_configuration_sha256": commission.sha256(
            commission.canonical(provider_snapshot["cloud_run"])
        ),
        "subscription_configuration": subscriptions,
        "publisher_freeze_readback": publisher_freeze,
        "publisher_freeze_readback_sha256": commission.sha256(
            commission.canonical(publisher_freeze)
        ),
        "secret_values_recorded": False,
        "release_authority": False,
        "mutation_authority": False,
    }
    return {
        "schema": contract["commissioning"][
            "legacy_retirement_phase_receipt_schema"
        ],
        "status": "legacy_retired",
        "phase": "legacy-retirement",
        "retirement_started_at": now.isoformat(),
        "recorded_at": now.isoformat(),
        "project": contract["project"],
        "contract_sha256": commission.sha256(commission.canonical(contract)),
        "source_revision": REVISION,
        "retired_subscription_names": targets,
        "applied_action_ids": [
            f"subscription.{name}.retire" for name in targets
        ],
        "provider_readback_ok": True,
        "provider_readback": provider,
        "provider_readback_sha256": commission.sha256(
            commission.canonical(provider)
        ),
        "subscription_configuration_sha256": subscription_hash,
        "legacy_archive_receipt_sha256": commission.sha256(
            commission.canonical(archive)
        ),
        "legacy_retirement_receipt_sha256": commission.sha256(
            commission.canonical(zero)
        ),
        "supabase_owner_readback_receipt_sha256": commission.sha256(
            commission.canonical(owner)
        ),
        "cloud_run_traffic_changed": False,
        "order_execution_requested": False,
        "secret_payloads_requested": False,
        "sensitive_environment_values_returned": False,
        "release_authority": False,
        "mutation_authority": False,
    }


def subscription_replacement_receipt(contract, now, *, value=0):
    required = contract["pubsub"]["immutable_subscription_replacement"]
    target = required["targets"][0]
    start = now - timedelta(minutes=3)
    stamps = [
        start + timedelta(seconds=30),
        start + timedelta(seconds=90),
        start + timedelta(seconds=150),
    ]
    return {
        "schema": required["schema"],
        "provider": required["provider"],
        "project": contract["project"],
        "contract_sha256": commission.sha256(commission.canonical(contract)),
        "source_revision": REVISION,
        "recorded_at": now.isoformat(),
        "window_start": start.isoformat(),
        "window_end": now.isoformat(),
        "subscriptions": [
            {
                "resource_name": (
                    f"projects/{contract['project']}/subscriptions/"
                    + target["subscription"]
                ),
                "topic_resource_name": (
                    f"projects/{contract['project']}/topics/" + target["topic"]
                ),
                "publisher_freeze": {
                    "member": target["publisher_member"],
                    "runtime": target["publisher_runtime"],
                    "unit": target["publisher_unit"],
                    "active_state": target["required_active_state"],
                    "sub_state": target["required_sub_state"],
                    "unit_file_state": target["required_unit_file_state"],
                    "frozen_since": (start - timedelta(minutes=1)).isoformat(),
                    "observed_at": now.isoformat(),
                    "readback_sha256": "f" * 64,
                },
                "metrics": [
                    {
                        "metric_type": metric,
                        "points": [
                            {"observed_at": stamp.isoformat(), "value": value}
                            for stamp in stamps
                        ],
                    }
                    for metric in required["required_metrics"]
                ],
            }
        ],
    }


def legacy_archive_receipt(contract, now):
    required = contract["pubsub"]["legacy_archive_receipt"]
    contract_hash = commission.sha256(commission.canonical(contract))
    root_hash = "8" * 64
    return {
        "schema": required["schema"],
        "status": required["required_status"],
        "provider": required["provider"],
        "project": contract["project"],
        "contract_sha256": contract_hash,
        "source_revision": REVISION,
        "recorded_at": (now - timedelta(minutes=4)).isoformat(),
        "scope_sha256": "7" * 64,
        "publisher_freeze": {
            "instance": contract["vm_workload_identity"]["instance"],
            "units": [
                {
                    "unit": unit,
                    "active_state": "inactive",
                    "unit_file_state": "disabled",
                }
                for unit in required["publisher_units"]
            ],
        },
        "publisher_freeze_reverified_after_drain": True,
        "archive_bucket_reverified_after_drain": True,
        "archive_bucket": "aureon-legacy-archive-fixture",
        "archive_kms_key_sha256": "9" * 64,
        "root_manifest": {
            "object_name": (
                f"fixture/v1/{REVISION}/{contract_hash}/roots/{root_hash}.json"
            ),
            "generation": "1234567890",
            "payload_sha256": root_hash,
            "message_count": 12,
        },
        "acknowledged_this_run": 12,
        "archived_bytes_this_run": 4096,
        "batch_manifests_this_run": 4,
        "empty_poll_confirmations": [
            {
                "resource_name": (
                    f"projects/{contract['project']}/subscriptions/{name}"
                ),
                "count": required["minimum_empty_poll_confirmations"],
            }
            for name in contract["pubsub"]["retire_after_zero_backlog"]
        ],
        "subscription_deleted": False,
        "order_execution": False,
        "cloud_run_traffic_changed": False,
        "release_authority": False,
    }


def retirement_receipt(contract, now, *, value=0):
    start = now - timedelta(minutes=3)
    point_times = [
        start + timedelta(seconds=30),
        start + timedelta(seconds=90),
        start + timedelta(seconds=150),
    ]
    metrics = contract["pubsub"]["legacy_retirement_receipt"][
        "required_metrics"
    ]
    return {
        "schema": contract["pubsub"]["legacy_retirement_receipt"]["schema"],
        "provider": "cloud_monitoring",
        "project": contract["project"],
        "contract_sha256": commission.sha256(
            commission.canonical(contract)
        ),
        "source_revision": contract["release"]["source_revision"],
        "recorded_at": now.isoformat(),
        "window_start": start.isoformat(),
        "window_end": now.isoformat(),
        "subscriptions": [
            {
                "resource_name": (
                    f"projects/{contract['project']}/subscriptions/{name}"
                ),
                "metrics": [
                    {
                        "metric_type": metric,
                        "points": [
                            {
                                "observed_at": stamp.isoformat(),
                                "value": value,
                            }
                            for stamp in point_times
                        ],
                    }
                    for metric in metrics
                ],
            }
            for name in contract["pubsub"]["retire_after_zero_backlog"]
        ],
    }


def vm_release_receipt(contract, now, *, certificate=None):
    vm = contract["vm_workload_identity"]
    revision = contract["release"]["source_revision"]
    units = []
    restart_readback = []
    for unit in vm["all_aureon_units"]:
        units.append(
            {
                "unit": unit,
                "user": commission._vm_expected_unit_user(contract, unit),
                "active": True,
                "enabled": True,
                "result": "success",
                "exec_main_status": 0,
                "fragment_path": f"/etc/systemd/system/{unit}",
                "fragment_sha256": "1" * 64,
                "executable_path": commission._vm_expected_executable(unit),
                "executable_sha256": "2" * 64,
                "started_at": (now - timedelta(seconds=20)).isoformat(),
            }
        )
        if unit == vm["broker_unit"]:
            readback = {"ready": True, "tokens_fresh": True}
        elif unit == vm["public_bridge"]["unit"]:
            readback = {
                "tls": True,
                "http_status": 200,
                "certificate_pinned": True,
                "response_sha256": "3" * 64,
            }
        else:
            matched_role = next(
                (
                    role
                    for role, candidate in vm["release_readback_receipt"][
                        "required_loopback_roles"
                    ].items()
                    if candidate == unit
                ),
                None,
            )
            readback = (
                {
                    "schema": "aureon.cloud-http-health.v1",
                    "revision": revision,
                    "role": matched_role,
                    "ready": True,
                    "deployment_hold": True,
                    "release_authority": False,
                    "tenant_auth_ready": True,
                    "response_sha256": "4" * 64,
                }
                if matched_role is not None
                else {}
            )
        restart_readback.append(
            {
                "unit": unit,
                "revision": revision,
                "passed": True,
                "readback": readback,
            }
        )
    loopback = {}
    for role, unit in vm["release_readback_receipt"][
        "required_loopback_roles"
    ].items():
        loopback[role] = {
            "unit": unit,
            "schema": "aureon.cloud-http-health.v1",
            "revision": revision,
            "role": role,
            "ready": True,
            "deployment_hold": True,
            "release_authority": False,
            "tenant_auth_ready": True,
            "response_sha256": "4" * 64,
        }
    tokens = []
    for index, workload in enumerate(vm["workloads"], start=1):
        tokens.append(
            {
                "workload": workload["name"],
                "target_service_account": workload["service_account"],
                "token_path": workload["token_file"],
                "schema": vm["token_schema"],
                "owner_uid": 0,
                "owner_gid": 2000 + index,
                "reader_uid": 1000 + index,
                "reader_gid": 2000 + index,
                "mode": "0640",
                "expires_at": (now + timedelta(minutes=20)).isoformat(),
                "observed_at": (now - timedelta(seconds=5)).isoformat(),
                "readback_sha256": "5" * 64,
                "secret_value_recorded": False,
            }
        )
    unit_order = [row["unit"] for row in units]
    return {
        "schema": vm["release_readback_receipt"]["schema"],
        "project": contract["project"],
        "zone": contract["zone"],
        "instance": vm["instance"],
        "status": "passed",
        "attached_service_account": vm["attached_service_account"],
        "attached_scopes": vm["attached_oauth_scopes"],
        "contract_sha256": commission.sha256(commission.canonical(contract)),
        "source_revision": revision,
        "recorded_at": now.isoformat(),
        "bundle_manifest_sha256": "6" * 64,
        "source_tree_sha256": "7" * 64,
        "public_bridge_source_sha256": "8" * 64,
        "public_bridge_certificate_sha256": (
            certificate or certificate_evidence(contract, now)
        )["fingerprint_sha256"],
        "public_bridge_certificate": deepcopy(
            certificate or certificate_evidence(contract, now)
        ),
        "units": units,
        "broker_tokens": tokens,
        "loopback_health": loopback,
        "restart_continuity": {
            "controlled_restart": "passed",
            "boot_id_before_sha256": "a" * 64,
            "boot_id_after_sha256": "a" * 64,
            "boot_id_unchanged": True,
            "broker_before_workloads": True,
            "start_order": unit_order,
            "restart_order": unit_order,
            "readback": restart_readback,
            "reboot_validation": "pending_separate_cutover_evidence",
        },
        "deployment_hold": True,
        "release_authority": False,
        "secret_values_recorded": False,
    }


def vm_reboot_receipt(contract, release, release_hash, now):
    vm = contract["vm_workload_identity"]
    revision = contract["release"]["source_revision"]
    units = [
        {
            "unit": row["unit"],
            "user": row["user"],
            "active": True,
            "enabled": True,
            "result": "success",
            "exec_main_status": 0,
            "fragment_sha256": row["fragment_sha256"],
            "executable_sha256": row["executable_sha256"],
            "observed_at": (now - timedelta(seconds=5)).isoformat(),
        }
        for row in release["units"]
    ]
    tokens = deepcopy(release["broker_tokens"])
    for token in tokens:
        token["observed_at"] = (now - timedelta(seconds=5)).isoformat()
        token["expires_at"] = (now + timedelta(minutes=20)).isoformat()
        token["readback_sha256"] = "b" * 64
    loopback = deepcopy(release["loopback_health"])
    loopback["public-bridge"] = {
        "unit": vm["public_bridge"]["unit"],
        "revision": revision,
        "passed": True,
        "readback": {
            "tls": True,
            "http_status": 200,
            "certificate_pinned": True,
            "response_sha256": "c" * 64,
        },
    }
    return {
        "schema": vm["reboot_continuity_receipt"]["schema"],
        "status": "passed",
        "recorded_at": now.isoformat(),
        "vm_release_receipt_sha256": release_hash,
        "contract_sha256": release["contract_sha256"],
        "source_revision": release["source_revision"],
        "bundle_manifest_sha256": release["bundle_manifest_sha256"],
        "source_tree_sha256": release["source_tree_sha256"],
        "project": release["project"],
        "zone": release["zone"],
        "instance": release["instance"],
        "attached_service_account": release["attached_service_account"],
        "attached_scopes": release["attached_scopes"],
        "boot_id_before_sha256": release["restart_continuity"][
            "boot_id_after_sha256"
        ],
        "boot_id_after_sha256": "d" * 64,
        "boot_id_changed": True,
        "vm_status": "RUNNING",
        "units": units,
        "broker_tokens": tokens,
        "loopback_health": loopback,
        "public_bridge_source_sha256": release[
            "public_bridge_source_sha256"
        ],
        "public_bridge_certificate_sha256": release[
            "public_bridge_certificate_sha256"
        ],
        "public_bridge_certificate": deepcopy(
            release["public_bridge_certificate"]
        ),
        "deployment_hold": True,
        "release_authority": False,
        "secret_values_recorded": False,
    }


def test_contract_is_resolved_only_from_exact_immutable_inputs():
    contract = commission.load_contract()
    resolved = resolved_contract()
    assert resolved["periodic_readiness"] == contract["periodic_readiness"]
    assert resolved["release"]["source_revision"] == REVISION
    assert "${" not in json.dumps(resolved)
    with pytest.raises(commission.CommissionError, match="digest_invalid"):
        commission.resolve_contract(
            contract,
            source_revision=REVISION,
            authority_image=AUTHORITY_IMAGE.split("@", 1)[0] + ":latest",
            public_entry_image=PUBLIC_IMAGE,
            supabase_project_ref=SUPABASE_PROJECT_REF,
            supabase_owner_subject=OWNER_SUBJECT,
            supabase_owner_email_sha256=OWNER_EMAIL_SHA256,
            iap_admin_email_sha256=IAP_ADMIN_EMAIL_SHA256,
        )


def test_contract_contains_commitments_and_no_plaintext_owner_identity():
    contract = commission.load_contract()
    raw = commission.DEFAULT_CONTRACT.read_text(encoding="utf-8")
    assert "AUREON_ALLOWED_USER_EMAILS" not in raw
    services = {
        row["name"]: row for row in contract["cloud_run"]["services"]
    }
    assert (
        "AUREON_IAP_ADMIN_EMAIL_SHA256"
        not in services["aureon-fusion-web"]["environment"]
    )
    assert services["aureon-fusion-operator"]["environment"][
        "AUREON_IAP_ADMIN_EMAIL_SHA256"
    ] == "${IAP_ADMIN_EMAIL_SHA256}"
    with pytest.raises(
        commission.CommissionError, match="repository_mismatch"
    ):
        commission.resolve_contract(
            contract,
            source_revision=REVISION,
            authority_image=PUBLIC_IMAGE,
            public_entry_image=PUBLIC_IMAGE,
            supabase_project_ref=SUPABASE_PROJECT_REF,
            supabase_owner_subject=OWNER_SUBJECT,
            supabase_owner_email_sha256=OWNER_EMAIL_SHA256,
            iap_admin_email_sha256=IAP_ADMIN_EMAIL_SHA256,
        )


def test_exact_provider_snapshot_passes():
    contract = resolved_contract()
    audit = commission.audit_snapshot(contract, exact_snapshot(contract))
    assert audit["ok"] is True
    assert audit["errors"] == []
    assert audit["vm_readback_deferred_to_release_receipt"] is False
    assert audit["release_authority"] is False
    assert audit["mutation_authority"] is False


def test_prepare_audit_defers_only_vm_readback():
    contract = resolved_contract()
    snapshot = exact_snapshot(contract)
    snapshot["vm"] = {}

    strict = commission.audit_snapshot(contract, snapshot)
    assert strict["ok"] is False
    assert "vm.name" in strict["errors"]
    assert strict["vm_readback_deferred_to_release_receipt"] is False

    prepared = commission.audit_snapshot(
        contract,
        snapshot,
        allow_iam_extras=True,
        allow_vm_pending=True,
    )
    assert prepared["ok"] is True
    assert prepared["errors"] == []
    assert prepared["vm_readback_deferred_to_release_receipt"] is True

    iam_strict_prepare = commission.audit_snapshot(
        contract,
        snapshot,
        allow_vm_pending=True,
    )
    assert iam_strict_prepare["ok"] is True
    assert iam_strict_prepare["errors"] == []

    snapshot["cloud_run"]["aureon-trade-controller"][
        "timeout_seconds"
    ] = 30
    still_blocked = commission.audit_snapshot(
        contract,
        snapshot,
        allow_iam_extras=True,
        allow_vm_pending=True,
    )
    assert still_blocked["ok"] is False
    assert "cloud_run.aureon-trade-controller.timeout" in still_blocked[
        "errors"
    ]


@pytest.mark.parametrize(
    ("mutate", "error"),
    [
        (
            lambda c, s: s["cloud_run"]["aureon-trade-controller"].update(
                timeout_seconds=30
            ),
            "cloud_run.aureon-trade-controller.timeout",
        ),
        (
            lambda c, s: s["cloud_run"]["aureon-trade-review"].update(
                ingress="all"
            ),
            "cloud_run.aureon-trade-review.ingress",
        ),
        (
            lambda c, s: s["cloud_run"]["aureon-fusion-operator"].update(
                iap_enabled=False
            ),
            "cloud_run.aureon-fusion-operator.iap_enabled",
        ),
        (
            lambda c, s: s["cloud_run"]["aureon-trade-review"].update(
                traffic=[
                    {
                        "revision": "aureon-trade-review-00000-old",
                        "percent": 100,
                        "tag": None,
                    }
                ]
            ),
            "cloud_run.aureon-trade-review.traffic",
        ),
        (
            lambda c, s: s["cloud_run"]["aureon-fusion-web"][
                "direct_vpc"
            ].update(egress="all-traffic"),
            "cloud_run.aureon-fusion-web.direct_vpc",
        ),
        (
            lambda c, s: s["subscriptions"][
                "aureon-trade-release-controller-push-v1"
            ].update(oidc_audience=""),
            "subscription.aureon-trade-release-controller-push-v1.oidc_audience",
        ),
        (
            lambda c, s: s["subscriptions"][
                "aureon-trade-terminal-readback-v1"
            ].update(enable_exactly_once_delivery=False),
            "subscription.terminal.enable_exactly_once_delivery",
        ),
        (
            lambda c, s: s["cloud_run"]["aureon-trade-executor"][
                "invokers"
            ].append("allUsers"),
            "cloud_run.aureon-trade-executor.anonymous",
        ),
        (
            lambda c, s: s["topics"]["aureon-trade-intents-v1"][
                "publishers"
            ].append("serviceAccount:wrong@example.invalid"),
            "topic.aureon-trade-intents-v1.publishers",
        ),
        (
            lambda c, s: s["project_iam"]["bindings"].append(
                {
                    "role": "roles/pubsub.publisher",
                    "members": [
                        "serviceAccount:"
                        + c["vm_workload_identity"]["old_union_identity"]
                    ],
                }
            ),
            "project_iam.roles/pubsub.publisher.forbidden",
        ),
        (
            lambda c, s: s["vm"].update(status="TERMINATED"),
            "vm.status",
        ),
        (
            lambda c, s: s["vm"]["units"][
                "aureon-cloud-operator.service"
            ]["sensitive_environment_name_hashes"].append("f" * 64),
            "vm.unit.aureon-cloud-operator.service.inline_secret_environment",
        ),
        (
            lambda c, s: s["vm"]["units"][
                c["vm_workload_identity"]["public_bridge"]["unit"]
            ].update(environment_file_bound=False),
            "vm.unit.aureon-public-bridge.service.environment_file",
        ),
        (
            lambda c, s: s["vm"]["units"][
                c["vm_workload_identity"]["public_bridge"]["unit"]
            ].update(effective_environment_parse_error=True),
            "vm.unit.aureon-public-bridge.service.effective_environment_parse",
        ),
        (
            lambda c, s: s["vm"]["units"][
                c["vm_workload_identity"]["public_bridge"]["unit"]
            ]["effective_sensitive_environment_name_hashes"].append("f" * 64),
            "vm.unit.aureon-public-bridge.service.effective_secret_environment",
        ),
        (
            lambda c, s: s["vm"].update(service_accounts=[]),
            "vm.attached_identity",
        ),
        (
            lambda c, s: s["vm"]["units"][
                "aureon-organ@queen_mind.service"
            ].update(ip_address_deny=""),
            "vm.unit.aureon-organ@queen_mind.service.metadata_not_denied",
        ),
        (
            lambda c, s: s["vm"]["units"][
                "aureon-cloud-operator.service"
            ]["environment"].update(
                AUREON_GOOGLE_TOKEN_FILE=(
                    "/run/aureon-cloud-identity/provider/token.json"
                )
            ),
            "vm.unit.aureon-cloud-operator.service.token_file",
        ),
        (
            lambda c, s: s["secrets"][
                "aureon-owner-exchange-credentials-20260912"
            ]["readers"].append(
                "serviceAccount:aureon-vm-operator@aureon-trading."
                "iam.gserviceaccount.com"
            ),
            "secret.aureon-owner-exchange-credentials-20260912.readers",
        ),
        (
            lambda c, s: s["kms"]["aureon-executor-signing"][
                "signers"
            ].append(
                "serviceAccount:aureon-vm-trade-bridge@aureon-trading."
                "iam.gserviceaccount.com"
            ),
            "kms.aureon-executor-signing.signers",
        ),
        (
            lambda c, s: s["kms"]["aureon-executor-signing"].update(
                purpose="ENCRYPT_DECRYPT"
            ),
            "kms.aureon-executor-signing.purpose",
        ),
        (
            lambda c, s: s["kms"]["aureon-executor-signing"].update(
                version_algorithm="EC_SIGN_P256_SHA256"
            ),
            "kms.aureon-executor-signing.algorithm",
        ),
        (
            lambda c, s: s["kms"]["aureon-executor-signing"].update(
                version="2"
            ),
            "kms.aureon-executor-signing.version",
        ),
        (
            lambda c, s: s["kms"]["aureon-executor-signing"].update(
                version_state="DISABLED"
            ),
            "kms.aureon-executor-signing.version_state",
        ),
    ],
)
def test_provider_drift_fails_closed(mutate, error):
    contract = resolved_contract()
    snapshot = exact_snapshot(contract)
    mutate(contract, snapshot)
    audit = commission.audit_snapshot(contract, snapshot)
    assert audit["ok"] is False
    assert error in audit["errors"]


def test_finalize_preflight_allows_only_iam_extras():
    contract = resolved_contract()
    snapshot = exact_snapshot(contract)
    snapshot["cloud_run"]["aureon-trade-review"]["invokers"].append(
        "allUsers"
    )
    snapshot["topics"]["aureon-trade-intents-v1"]["publishers"].append(
        "serviceAccount:wrong@example.invalid"
    )
    snapshot["project_iam"]["bindings"].append(
        {
            "role": "roles/pubsub.publisher",
            "members": [
                "serviceAccount:"
                + contract["vm_workload_identity"]["old_union_identity"]
            ],
        }
    )
    assert commission.audit_snapshot(contract, snapshot)["ok"] is False
    assert commission.audit_snapshot(
        contract, snapshot, allow_iam_extras=True
    )["ok"] is True


def test_action_plan_creates_resources_updates_oidc_and_marks_removals():
    contract = resolved_contract()
    snapshot = exact_snapshot(contract)
    missing_topic = "aureon-trade-release-requests-v1"
    del snapshot["topics"][missing_topic]
    missing_account = (
        "aureon-vm-provider@aureon-trading.iam.gserviceaccount.com"
    )
    del snapshot["service_accounts"][missing_account]
    snapshot["subscriptions"][
        "aureon-trade-release-controller-push-v1"
    ]["oidc_audience"] = ""
    del snapshot["subscriptions"]["aureon-trade-terminal-readback-v1"]
    broad_member = (
        "serviceAccount:"
        + contract["vm_workload_identity"]["old_union_identity"]
    )
    snapshot["project_iam"]["bindings"].append(
        {"role": "roles/pubsub.publisher", "members": [broad_member]}
    )
    actions = commission.build_iam_actions(contract, snapshot)
    by_id = {row.action_id: row for row in actions}
    assert by_id[f"topic.{missing_topic}.create"].args == (
        "pubsub",
        "topics",
        "create",
        missing_topic,
    )
    assert (
        by_id["service-account.aureon-vm-provider.create"].args[:4]
        == ("iam", "service-accounts", "create", "aureon-vm-provider")
    )
    update = by_id[
        "subscription.aureon-trade-release-controller-push-v1.update"
    ]
    assert (
        "--push-auth-token-audience="
        "https://aureon-trade-controller-25xhneniva-ew.a.run.app"
        in update.args
    )
    terminal_create = by_id["subscription.terminal.create"]
    assert "--enable-exactly-once-delivery" in terminal_create.args
    removals = [row for row in actions if row.destructive]
    assert any(
        row.args[:3]
        == (
            "projects",
            "remove-iam-policy-binding",
            contract["project"],
        )
        and "--role=roles/pubsub.publisher" in row.args
        for row in removals
    )
    assert all("--condition=None" in row.args for row in removals)


@pytest.mark.parametrize(
    ("command_template", "supports_condition"),
    [
        (("pubsub", "topics", "{operation}", "topic"), False),
        (("pubsub", "subscriptions", "{operation}", "subscription"), False),
        (("kms", "keys", "{operation}", "key"), True),
        (("iam", "service-accounts", "{operation}", "account"), True),
        (("secrets", "{operation}", "secret"), True),
        (("run", "services", "{operation}", "service"), True),
        (("projects", "{operation}", "project"), True),
    ],
)
def test_binding_actions_match_provider_condition_flag_support(
    command_template, supports_condition
):
    actions = commission._binding_actions(
        "test", command_template, "roles/viewer",
        {"serviceAccount:old@example.invalid"},
        {"serviceAccount:new@example.invalid"},
    )
    assert len(actions) == 2
    addition, removal = actions
    assert "add-iam-policy-binding" in addition.args
    assert "remove-iam-policy-binding" in removal.args
    assert addition.destructive is False and removal.destructive is True
    for action in actions:
        assert ("--condition=None" in action.args) is supports_condition
        assert "--role=roles/viewer" in action.args


def test_missing_resources_produce_audit_codes_instead_of_capture_abort():
    contract = resolved_contract()

    class MissingRunner:
        def json(self, *args, optional=False):
            if args[:2] == ("projects", "get-iam-policy"):
                return {"bindings": []}
            if args[:2] == ("services", "list"):
                return []
            if optional:
                return None
            raise AssertionError(args)

        def text(self, *args):
            raise AssertionError(args)

        def apply(self, *args):
            raise AssertionError(args)

    snapshot = commission.capture_snapshot(contract, MissingRunner())
    audit = commission.audit_snapshot(contract, snapshot)
    assert audit["ok"] is False
    assert "cloud_run.aureon-trade-controller.missing" in audit["errors"]
    assert (
        "service_account.aureon-vm-token-broker@aureon-trading."
        "iam.gserviceaccount.com.missing"
        in audit["errors"]
    )


def test_capture_snapshot_binds_explicit_enabled_asymmetric_kms_versions():
    contract = resolved_contract()

    class KmsRunner:
        def __init__(self):
            self.calls = []

        def json(self, *args, optional=False):
            self.calls.append((args, optional))
            if args[:3] == ("kms", "keys", "describe"):
                return {
                    "purpose": "ASYMMETRIC_SIGN",
                    "versionTemplate": {"algorithm": "EC_SIGN_ED25519"},
                }
            if args[:4] == ("kms", "keys", "versions", "describe"):
                key = next(
                    item.removeprefix("--key=")
                    for item in args
                    if item.startswith("--key=")
                )
                return {
                    "name": (
                        f"projects/{contract['project']}/locations/"
                        f"{contract['region']}/keyRings/{contract['keyring']}/"
                        f"cryptoKeys/{key}/cryptoKeyVersions/{args[4]}"
                    ),
                    "state": "ENABLED",
                    "algorithm": "EC_SIGN_ED25519",
                }
            if args[:3] == ("kms", "keys", "get-iam-policy"):
                return {"bindings": []}
            if args[:2] == ("projects", "get-iam-policy"):
                return {"bindings": []}
            if args[:2] == ("services", "list"):
                return []
            if optional:
                return None
            raise AssertionError(args)

        def text(self, *args):
            raise AssertionError(args)

    runner = KmsRunner()
    snapshot = commission.capture_snapshot(contract, runner)

    for expected in contract["iam"]["kms_keys"]:
        assert snapshot["kms"][expected["name"]] == {
            "signers": [],
            "public_key_viewers": [],
            "purpose": expected["purpose"],
            "configured_algorithm": expected["algorithm"],
            "version": expected["version"],
            "version_state": "ENABLED",
            "version_algorithm": expected["algorithm"],
        }
        assert (
            (
                "kms",
                "keys",
                "versions",
                "describe",
                expected["version"],
                "--key=" + expected["name"],
                "--location=" + contract["region"],
                "--keyring=" + contract["keyring"],
            ),
            True,
        ) in runner.calls


def test_vm_snapshot_uses_privileged_redacted_metadata_readback():
    contract = resolved_contract()

    class VmRunner:
        def __init__(self):
            self.text_args = None

        def json(self, *args, optional=False):
            assert args[:3] == ("compute", "instances", "describe")
            assert optional is True
            return {
                "name": contract["vm_workload_identity"]["instance"],
                "status": "RUNNING",
                "serviceAccounts": [],
            }

        def text(self, *args):
            self.text_args = args
            path = contract["vm_workload_identity"]["token_storage"][0]["path"]
            bridge = contract["vm_workload_identity"]["public_bridge"]
            commitment = bridge["required_environment"][
                "AUREON_IAP_ADMIN_EMAIL_SHA256"
            ]
            return (
                f"@@UNIT={bridge['unit']}\n"
                "EnvironmentFileBinding=1\n"
                "EffectiveEnvironmentAllowed."
                f"AUREON_IAP_ADMIN_EMAIL_SHA256={commitment}\n"
                f"@@PATH={path}\n"
                "Kind=directory\n"
                "Owner=root\n"
                "Group=root\n"
                "Mode=750\n"
            )

    runner = VmRunner()
    snapshot = commission._capture_vm(contract, runner)

    assert snapshot["systemd_readback_ok"] is True
    bridge = contract["vm_workload_identity"]["public_bridge"]
    bridge_readback = snapshot["units"][bridge["unit"]]
    assert bridge_readback["environment_file_bound"] is True
    assert bridge_readback["effective_environment"] == (
        bridge["required_environment"]
    )
    assert bridge_readback["effective_environment_parse_error"] is False
    assert bridge_readback["effective_sensitive_environment_name_hashes"] == []
    path = contract["vm_workload_identity"]["token_storage"][0]["path"]
    assert snapshot["paths"][path] == {
        "kind": "directory",
        "owner": "root",
        "group": "root",
        "mode": "750",
    }
    command = next(
        item.removeprefix("--command=")
        for item in runner.text_args
        if item.startswith("--command=")
    )
    words = shlex.split(command)
    assert words[:5] == ["sudo", "-n", "--", "sh", "-c"]
    redacted_script = words[5]
    assert "systemctl show" in redacted_script
    assert "--property=EnvironmentFiles" in redacted_script
    assert commission.PUBLIC_BRIDGE_ENVIRONMENT_FILE in redacted_script
    assert '"/proc/$pid/environ"' in redacted_script
    assert "SensitiveEnvironmentNameHash" in redacted_script
    assert "EffectiveSensitiveEnvironmentNameHash" in redacted_script
    assert "EnvironmentAllowed." in redacted_script
    assert "stat --format=" in redacted_script
    assert "ActiveEnterTimestampMonotonic" in redacted_script
    assert "InactiveExitTimestampMonotonic" in redacted_script
    assert "ExecMainStartTimestampMonotonic" in redacted_script
    assert "InvocationID" in redacted_script
    assert 'awk \'$1 == "btime" {print $2}\' /proc/stat' in redacted_script
    assert "cat " not in redacted_script


def test_effective_environment_filter_returns_only_commitment_and_name_hashes(
    tmp_path,
):
    contract = resolved_contract()
    bridge = contract["vm_workload_identity"]["public_bridge"]
    commitment = bridge["required_environment"][
        "AUREON_IAP_ADMIN_EMAIL_SHA256"
    ]
    plaintext_email = "owner@example.invalid"
    secret_value = "never-print-this-provider-key"
    unrelated_value = "also-never-print-this"
    environment = (tmp_path / "environ").resolve()
    environment.write_bytes(
        b"AUREON_IAP_ADMIN_EMAIL_SHA256="
        + commitment.encode("ascii")
        + b"\0AUREON_IAP_ADMIN_EMAIL="
        + plaintext_email.encode("ascii")
        + b"\0AUREON_API_KEY="
        + secret_value.encode("ascii")
        + b"\0UNRELATED="
        + unrelated_value.encode("ascii")
        + b"\0"
    )

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            commission._effective_environment_filter_source(
                bridge["required_environment"]
            ),
            str(environment),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert result.stderr == ""
    assert result.stdout.splitlines() == [
        "EffectiveEnvironmentAllowed.AUREON_IAP_ADMIN_EMAIL_SHA256="
        + commitment,
        "EffectiveSensitiveEnvironmentNameHash="
        + commission.sha256(b"AUREON_IAP_ADMIN_EMAIL"),
        "EffectiveSensitiveEnvironmentNameHash="
        + commission.sha256(b"AUREON_API_KEY"),
    ]
    assert plaintext_email not in result.stdout
    assert secret_value not in result.stdout
    assert unrelated_value not in result.stdout


@pytest.mark.parametrize(
    ("provider_value", "expected"),
    [
        (
            "/etc/aureon-public/bridge.env (ignore_errors=no)\n",
            "EnvironmentFileBinding=1\n",
        ),
        (
            "/etc/aureon-public/bridge.env (ignore_errors=yes)\n",
            "EnvironmentFileBinding=0\n",
        ),
        (
            "/etc/aureon-public/bridge.env (ignore_errors=no) "
            "/etc/aureon-public/other.env (ignore_errors=no)\n",
            "EnvironmentFileBinding=0\n",
        ),
        ("", "EnvironmentFileBinding=0\n"),
    ],
)
def test_environment_file_binding_filter_requires_one_nonoptional_exact_path(
    provider_value, expected
):
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            commission._environment_file_binding_filter_source(
                commission.PUBLIC_BRIDGE_ENVIRONMENT_FILE
            ),
        ],
        input=provider_value,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert result.stderr == ""
    assert result.stdout == expected


def test_legacy_archive_receipt_binds_scope_root_freeze_and_no_effects(
    tmp_path,
):
    contract = resolved_contract()
    now = datetime.now(UTC)
    value = legacy_archive_receipt(contract, now)
    path = (tmp_path / "legacy-archive.json").resolve()
    path.write_text(json.dumps(value), encoding="utf-8")
    receipt_hash = commission.sha256(commission.canonical(value))
    assert commission.validate_legacy_archive_receipt(
        contract,
        path,
        receipt_hash,
        value["scope_sha256"],
        now=now,
    ) == receipt_hash

    value["root_manifest"]["generation"] = ""
    path.write_text(json.dumps(value), encoding="utf-8")
    changed_hash = commission.sha256(commission.canonical(value))
    with pytest.raises(commission.CommissionError, match="root_invalid"):
        commission.validate_legacy_archive_receipt(
            contract,
            path,
            changed_hash,
            value["scope_sha256"],
            now=now,
        )


def test_legacy_retirement_requires_fresh_explicit_zero_time_series(
    tmp_path,
):
    contract = resolved_contract()
    now = datetime(2026, 9, 13, 18, 0, tzinfo=UTC)
    value = retirement_receipt(contract, now)
    path = (tmp_path / "legacy.json").resolve()
    path.write_text(json.dumps(value), encoding="utf-8")
    receipt_hash = commission.sha256(commission.canonical(value))
    assert (
        commission.validate_legacy_retirement_receipt(
            contract, path, receipt_hash, now=now
        )
        == receipt_hash
    )
    value["subscriptions"][0]["metrics"][0]["points"][1]["value"] = 1
    path.write_text(json.dumps(value), encoding="utf-8")
    changed_hash = commission.sha256(commission.canonical(value))
    with pytest.raises(
        commission.CommissionError, match="backlog_not_zero"
    ):
        commission.validate_legacy_retirement_receipt(
            contract, path, changed_hash, now=now
        )
    value = retirement_receipt(contract, now)
    value["subscriptions"][0]["metrics"].pop()
    path.write_text(json.dumps(value), encoding="utf-8")
    changed_hash = commission.sha256(commission.canonical(value))
    with pytest.raises(
        commission.CommissionError, match="time_series_missing"
    ):
        commission.validate_legacy_retirement_receipt(
            contract, path, changed_hash, now=now
        )


def test_default_command_is_read_only_audit(monkeypatch):
    contract = resolved_contract()
    snapshot = exact_snapshot(contract)

    class Runner:
        def __init__(self):
            self.applied = []

        def apply(self, *args):
            self.applied.append(args)

    runner = Runner()
    monkeypatch.setattr(commission, "Gcloud", lambda *_args: runner)
    monkeypatch.setattr(
        commission, "capture_snapshot", lambda *_args: snapshot
    )
    assert commission.main(cli_args()) == 0
    assert runner.applied == []


def test_resource_prepare_receipt_explicitly_defers_runtime_boundaries(
    monkeypatch, tmp_path
):
    contract = resolved_contract()
    snapshot = exact_snapshot(contract)
    snapshot["vm"] = {}

    class Runner:
        def __init__(self):
            self.applied = []

        def apply(self, *args):
            self.applied.append(args)

    runner = Runner()
    monkeypatch.setattr(commission, "Gcloud", lambda *_args: runner)
    monkeypatch.setattr(
        commission, "capture_snapshot", lambda *_args: snapshot
    )
    now = datetime.now(UTC)
    owner = owner_readback_receipt(contract, now)
    owner_path = (tmp_path / "owner.json").resolve()
    owner_path.write_text(json.dumps(owner), encoding="utf-8")
    owner_hash = commission.sha256(commission.canonical(owner))
    output = (tmp_path / "prepare.json").resolve()
    contract_hash = commission.sha256(commission.canonical(contract))

    result = commission.main(
        [
            *cli_args("apply"),
            "--phase=resource-prepare",
            "--acknowledge-contract-sha256=" + contract_hash,
            "--supabase-owner-readback-receipt=" + str(owner_path),
            "--acknowledge-supabase-owner-readback-sha256=" + owner_hash,
            "--receipt=" + str(output),
        ]
    )

    assert result == 0
    assert runner.applied == []
    receipt = json.loads(output.read_text(encoding="utf-8"))
    assert receipt["status"] == "resources_prepared"
    assert receipt["phase"] == "resource-prepare"
    assert receipt["provider_readback_ok"] is True
    assert receipt["provider_error_codes"] == []
    assert receipt["vm_readback_deferred_to_release_receipt"] is True
    assert receipt["cloud_run_readback_mode"] == "deferred"
    assert receipt["legacy_retirement_deferred"] is True
    assert receipt["broker_identity_readback_ok"] is False
    assert receipt["destructive_iam_cleanup_deferred"] is False
    assert receipt["release_authority"] is False
    assert receipt["mutation_authority"] is False


def test_resource_prepare_never_revokes_old_union_before_broker_attachment(
    monkeypatch, tmp_path
):
    contract = resolved_contract()
    snapshot = exact_snapshot(contract)
    snapshot["vm"] = {}
    old_member = (
        "serviceAccount:" + contract["vm_workload_identity"]["old_union_identity"]
    )
    snapshot["project_iam"]["bindings"].append(
        {
            "role": "roles/secretmanager.secretAccessor",
            "members": [old_member],
        }
    )

    class Runner:
        def __init__(self):
            self.applied = []

        def apply(self, *args):
            self.applied.append(args)

    runner = Runner()
    monkeypatch.setattr(commission, "Gcloud", lambda *_args: runner)
    monkeypatch.setattr(commission, "capture_snapshot", lambda *_args: snapshot)
    owner = owner_readback_receipt(contract, datetime.now(UTC))
    owner_path = (tmp_path / "owner.json").resolve()
    owner_path.write_text(json.dumps(owner), encoding="utf-8")
    owner_hash = commission.sha256(commission.canonical(owner))
    output = (tmp_path / "prepare.json").resolve()
    result = commission.main(
        [
            *cli_args("apply"),
            "--phase=resource-prepare",
            "--acknowledge-contract-sha256="
            + commission.sha256(commission.canonical(contract)),
            "--supabase-owner-readback-receipt=" + str(owner_path),
            "--acknowledge-supabase-owner-readback-sha256=" + owner_hash,
            "--receipt=" + str(output),
        ]
    )
    assert result == 0
    assert runner.applied == []
    receipt = json.loads(output.read_text(encoding="utf-8"))
    assert receipt["broker_identity_readback_ok"] is False
    assert receipt["destructive_iam_cleanup_deferred"] is True


def test_resource_prepare_never_removes_rollback_anonymous_invoker(
    monkeypatch, tmp_path
):
    contract = resolved_contract()
    snapshot = exact_snapshot(contract)
    rollback_name = contract["cloud_run"][
        "rollback_service_without_anonymous_invoker"
    ]
    snapshot["cloud_run"][rollback_name] = {"invokers": ["allUsers"]}

    class Runner:
        def __init__(self):
            self.applied = []

        def apply(self, *args):
            self.applied.append(args)

    runner = Runner()
    monkeypatch.setattr(commission, "Gcloud", lambda *_args: runner)
    monkeypatch.setattr(commission, "capture_snapshot", lambda *_args: snapshot)
    monkeypatch.setattr(
        commission,
        "validate_supabase_owner_receipt",
        lambda *_args, **_kwargs: "1" * 64,
    )
    output = (tmp_path / "prepare.json").resolve()

    result = commission.main(
        [
            *cli_args("apply"),
            "--phase=resource-prepare",
            "--acknowledge-contract-sha256="
            + commission.sha256(commission.canonical(contract)),
            "--receipt=" + str(output),
        ]
    )

    assert result == 0
    assert runner.applied == []
    receipt = json.loads(output.read_text(encoding="utf-8"))
    assert receipt["status"] == "resources_prepared"
    assert receipt["provider_readback_ok"] is True
    assert receipt["destructive_iam_cleanup_deferred"] is False
    assert receipt["rollback_anonymous_invoker_removal_deferred"] is True


def test_supabase_owner_provider_readback_receipt_is_exact_and_redacted(tmp_path):
    contract = resolved_contract()
    now = datetime.now(UTC)
    value = owner_readback_receipt(contract, now)
    path = (tmp_path / "owner-readback.json").resolve()
    path.write_text(json.dumps(value), encoding="utf-8")
    receipt_hash = commission.sha256(commission.canonical(value))
    assert commission.validate_supabase_owner_receipt(
        contract, path, receipt_hash, now=now
    ) == receipt_hash
    raw = path.read_text(encoding="utf-8")
    assert "@" not in raw
    assert "access_token" not in raw


@pytest.mark.parametrize(
    ("field", "value", "reason"),
    [
        ("project_ref", "otherprojectfixture1", "binding_invalid"),
        ("subject", "00000000-0000-4000-8000-000000000099", "binding_invalid"),
        ("app_metadata_role", "authenticated", "binding_invalid"),
        ("email_confirmed", False, "binding_invalid"),
        ("email_sha256", "f" * 64, "binding_invalid"),
    ],
)
def test_supabase_owner_provider_readback_rejects_wrong_binding(
    tmp_path, field, value, reason
):
    contract = resolved_contract()
    observed = owner_readback_receipt(contract, datetime.now(UTC))
    observed[field] = value
    path = (tmp_path / f"owner-{field}.json").resolve()
    path.write_text(json.dumps(observed), encoding="utf-8")
    receipt_hash = commission.sha256(commission.canonical(observed))
    with pytest.raises(commission.CommissionError, match=reason):
        commission.validate_supabase_owner_receipt(
            contract, path, receipt_hash
        )


def test_supabase_owner_provider_readback_rejects_stale_and_tampered(tmp_path):
    contract = resolved_contract()
    now = datetime.now(UTC)
    observed = owner_readback_receipt(contract, now - timedelta(hours=1))
    path = (tmp_path / "owner-stale.json").resolve()
    path.write_text(json.dumps(observed), encoding="utf-8")
    receipt_hash = commission.sha256(commission.canonical(observed))
    with pytest.raises(commission.CommissionError, match="receipt_stale"):
        commission.validate_supabase_owner_receipt(
            contract, path, receipt_hash, now=now
        )

    observed = owner_readback_receipt(contract, now)
    acknowledged = commission.sha256(commission.canonical(observed))
    observed["email_confirmed"] = False
    path.write_text(json.dumps(observed), encoding="utf-8")
    with pytest.raises(
        commission.CommissionError, match="acknowledgement_invalid"
    ):
        commission.validate_supabase_owner_receipt(
            contract, path, acknowledged, now=now
        )


def test_vm_release_readback_binds_exact_runtime_and_raw_receipt_hash(tmp_path):
    contract = resolved_contract()
    now = datetime.now(UTC)
    observed = vm_release_receipt(contract, now)
    path = (tmp_path / "vm-release.json").resolve()
    path.write_text(
        json.dumps(observed, sort_keys=True, indent=2) + "\n",
        encoding="ascii",
    )
    receipt_hash = commission.sha256(path.read_bytes())
    assert commission.validate_vm_release_receipt(
        contract,
        path,
        receipt_hash,
        expected_certificate=observed["public_bridge_certificate"],
        now=now,
    ) == receipt_hash
    raw = path.read_text(encoding="ascii")
    assert "access_token" not in raw
    assert "private_key" not in raw


@pytest.mark.parametrize(
    ("mutation", "reason"),
    [
        (
            lambda value: value.update(source_revision="b" * 40),
            "binding_invalid",
        ),
        (
            lambda value: value.update(contract_sha256="b" * 64),
            "binding_invalid",
        ),
        (
            lambda value: value.update(
                attached_service_account="other@example.test"
            ),
            "binding_invalid",
        ),
        (
            lambda value: value["units"][0].update(
                executable_sha256="invalid"
            ),
            "unit_readback_invalid",
        ),
        (
            lambda value: value["broker_tokens"][0].update(
                target_service_account="other@example.test"
            ),
            "token_readback_invalid",
        ),
        (
            lambda value: value["restart_continuity"].update(
                controlled_restart="failed"
            ),
            "continuity_invalid",
        ),
    ],
)
def test_vm_release_readback_rejects_wrong_binding(
    tmp_path, mutation, reason
):
    contract = resolved_contract()
    now = datetime.now(UTC)
    observed = vm_release_receipt(contract, now)
    mutation(observed)
    path = (tmp_path / f"vm-release-{reason}.json").resolve()
    path.write_text(json.dumps(observed), encoding="ascii")
    receipt_hash = commission.sha256(path.read_bytes())
    with pytest.raises(commission.CommissionError, match=reason):
        commission.validate_vm_release_receipt(
            contract,
            path,
            receipt_hash,
            expected_certificate=observed["public_bridge_certificate"],
            now=now,
        )


def test_vm_release_readback_rejects_stale_and_tampered(tmp_path):
    contract = resolved_contract()
    now = datetime.now(UTC)
    observed = vm_release_receipt(contract, now - timedelta(minutes=30))
    path = (tmp_path / "vm-release-stale.json").resolve()
    path.write_text(json.dumps(observed), encoding="ascii")
    receipt_hash = commission.sha256(path.read_bytes())
    with pytest.raises(commission.CommissionError, match="receipt_stale"):
        commission.validate_vm_release_receipt(
            contract,
            path,
            receipt_hash,
            expected_certificate=observed["public_bridge_certificate"],
            now=now,
        )


def test_vm_release_rejects_different_immutable_certificate_identity(tmp_path):
    contract = resolved_contract()
    now = datetime.now(UTC)
    expected = certificate_evidence(contract, now)
    observed = vm_release_receipt(contract, now, certificate=expected)
    path = (tmp_path / "vm-release-certificate.json").resolve()
    path.write_text(json.dumps(observed), encoding="ascii")
    receipt_hash = commission.sha256(path.read_bytes())
    different = {**expected, "fingerprint_sha256": "e" * 64}
    with pytest.raises(
        commission.CommissionError,
        match="vm_release_receipt_certificate_binding_invalid",
    ):
        commission.validate_vm_release_receipt(
            contract,
            path,
            receipt_hash,
            expected_certificate=different,
            now=now,
        )

    observed = vm_release_receipt(contract, now)
    path.write_text(json.dumps(observed), encoding="ascii")
    acknowledged = commission.sha256(path.read_bytes())
    observed["units"][0]["fragment_sha256"] = "f" * 64
    path.write_text(json.dumps(observed), encoding="ascii")
    with pytest.raises(
        commission.CommissionError, match="acknowledgement_invalid"
    ):
        commission.validate_vm_release_receipt(
            contract,
            path,
            acknowledged,
            expected_certificate=observed["public_bridge_certificate"],
            now=now,
        )


def _write_vm_receipt(path, value):
    path.write_text(
        json.dumps(value, sort_keys=True, indent=2) + "\n",
        encoding="ascii",
    )
    return commission.sha256(path.read_bytes())


def test_vm_reboot_continuity_binds_release_and_changed_boot(tmp_path):
    contract = resolved_contract()
    now = datetime.now(UTC)
    release = vm_release_receipt(contract, now - timedelta(minutes=1))
    release_path = (tmp_path / "vm-release.json").resolve()
    release_hash = _write_vm_receipt(release_path, release)
    reboot = vm_reboot_receipt(contract, release, release_hash, now)
    reboot_path = (tmp_path / "vm-reboot.json").resolve()
    reboot_hash = _write_vm_receipt(reboot_path, reboot)
    assert commission.validate_vm_reboot_continuity_receipt(
        contract,
        reboot_path,
        reboot_hash,
        release_path,
        release_hash,
        expected_certificate=release["public_bridge_certificate"],
        now=now,
    ) == reboot_hash


@pytest.mark.parametrize(
    ("mutation", "reason"),
    [
        (
            lambda value: value.update(vm_release_receipt_sha256="e" * 64),
            "binding_invalid",
        ),
        (
            lambda value: value.update(source_tree_sha256="e" * 64),
            "binding_invalid",
        ),
        (
            lambda value: value.update(
                boot_id_after_sha256=value["boot_id_before_sha256"]
            ),
            "boot_invalid",
        ),
        (
            lambda value: value["units"][0].update(
                fragment_sha256="e" * 64
            ),
            "unit_readback_invalid",
        ),
        (
            lambda value: value["broker_tokens"][0].update(
                target_service_account="other@example.test"
            ),
            "token_readback_invalid",
        ),
    ],
)
def test_vm_reboot_continuity_rejects_wrong_binding(
    tmp_path, mutation, reason
):
    contract = resolved_contract()
    now = datetime.now(UTC)
    release = vm_release_receipt(contract, now - timedelta(minutes=1))
    release_path = (tmp_path / "vm-release.json").resolve()
    release_hash = _write_vm_receipt(release_path, release)
    reboot = vm_reboot_receipt(contract, release, release_hash, now)
    mutation(reboot)
    reboot_path = (tmp_path / f"vm-reboot-{reason}.json").resolve()
    reboot_hash = _write_vm_receipt(reboot_path, reboot)
    with pytest.raises(commission.CommissionError, match=reason):
        commission.validate_vm_reboot_continuity_receipt(
            contract,
            reboot_path,
            reboot_hash,
            release_path,
            release_hash,
            expected_certificate=release["public_bridge_certificate"],
            now=now,
        )


def test_vm_reboot_continuity_rejects_stale_and_tampered(tmp_path):
    contract = resolved_contract()
    now = datetime.now(UTC)
    old = now - timedelta(minutes=30)
    release = vm_release_receipt(contract, old - timedelta(minutes=1))
    release_path = (tmp_path / "vm-release.json").resolve()
    release_hash = _write_vm_receipt(release_path, release)
    reboot = vm_reboot_receipt(contract, release, release_hash, old)
    reboot_path = (tmp_path / "vm-reboot.json").resolve()
    reboot_hash = _write_vm_receipt(reboot_path, reboot)
    with pytest.raises(commission.CommissionError, match="receipt_stale"):
        commission.validate_vm_reboot_continuity_receipt(
            contract,
            reboot_path,
            reboot_hash,
            release_path,
            release_hash,
            expected_certificate=release["public_bridge_certificate"],
            now=now,
        )

    release = vm_release_receipt(contract, now - timedelta(minutes=1))
    release_hash = _write_vm_receipt(release_path, release)
    reboot = vm_reboot_receipt(contract, release, release_hash, now)
    acknowledged = _write_vm_receipt(reboot_path, reboot)
    reboot["boot_id_changed"] = False
    _write_vm_receipt(reboot_path, reboot)
    with pytest.raises(
        commission.CommissionError, match="acknowledgement_invalid"
    ):
        commission.validate_vm_reboot_continuity_receipt(
            contract,
            reboot_path,
            acknowledged,
            release_path,
            release_hash,
            expected_certificate=release["public_bridge_certificate"],
            now=now,
        )


def test_immutable_subscription_drift_is_an_explicit_blocker():
    contract = resolved_contract()
    snapshot = exact_snapshot(contract)
    name = "aureon-trade-release-controller-push-v1"
    snapshot["subscriptions"][name]["enable_message_ordering"] = False
    actions = commission.build_iam_actions(contract, snapshot)
    blockers = [row for row in actions if row.blocked]
    assert [row.action_id for row in blockers] == [
        f"subscription.{name}.manual-replacement-required"
    ]
    assert commission.immutable_subscription_mismatches(
        contract, snapshot
    ) == [name]


def test_subscription_replacement_receipt_requires_frozen_zero_publisher(
    tmp_path,
):
    contract = resolved_contract()
    now = datetime.now(UTC)
    name = "aureon-trade-release-controller-push-v1"
    value = subscription_replacement_receipt(contract, now)
    path = (tmp_path / "replace.json").resolve()
    path.write_text(json.dumps(value), encoding="utf-8")
    receipt_hash = commission.sha256(commission.canonical(value))
    assert commission.validate_subscription_replacement_receipt(
        contract, path, receipt_hash, [name], now=now
    ) == receipt_hash

    value["subscriptions"][0]["publisher_freeze"]["active_state"] = "active"
    path.write_text(json.dumps(value), encoding="utf-8")
    changed_hash = commission.sha256(commission.canonical(value))
    with pytest.raises(commission.CommissionError, match="publisher_not_frozen"):
        commission.validate_subscription_replacement_receipt(
            contract, path, changed_hash, [name], now=now
        )

    value = subscription_replacement_receipt(contract, now, value=1)
    path.write_text(json.dumps(value), encoding="utf-8")
    changed_hash = commission.sha256(commission.canonical(value))
    with pytest.raises(commission.CommissionError, match="backlog_not_zero"):
        commission.validate_subscription_replacement_receipt(
            contract, path, changed_hash, [name], now=now
        )

    value = subscription_replacement_receipt(contract, now)
    path.write_text(json.dumps(value), encoding="utf-8")
    changed_hash = commission.sha256(commission.canonical(value))
    live = exact_snapshot(contract)
    with pytest.raises(
        commission.CommissionError, match="publisher_not_frozen"
    ):
        commission.validate_subscription_replacement_receipt(
            contract,
            path,
            changed_hash,
            [name],
            provider_snapshot=live,
            now=now,
        )


def test_subscription_replacement_phase_deletes_only_after_receipts(
    monkeypatch, tmp_path
):
    contract = resolved_contract()
    now = datetime.now(UTC)
    initial = exact_snapshot(contract)
    name = "aureon-trade-release-controller-push-v1"
    initial["subscriptions"][name]["enable_message_ordering"] = False
    publisher = initial["vm"]["units"]["aureon-cloud-operator.service"]
    publisher.update(
        active_state="inactive",
        sub_state="dead",
        unit_file_state="disabled",
        inactive_enter_timestamp=(now - timedelta(minutes=4)).isoformat(),
    )
    final = exact_snapshot(contract)
    final["vm"]["units"]["aureon-cloud-operator.service"].update(
        active_state="inactive",
        sub_state="dead",
        unit_file_state="disabled",
        inactive_enter_timestamp=(now - timedelta(minutes=4)).isoformat(),
    )

    class Runner:
        def __init__(self):
            self.applied = []

        def apply(self, *args):
            self.applied.append(args)

    runner = Runner()
    snapshots = iter((initial, final))
    monkeypatch.setattr(commission, "Gcloud", lambda *_args: runner)
    monkeypatch.setattr(
        commission, "capture_snapshot", lambda *_args: next(snapshots)
    )
    owner = owner_readback_receipt(contract, now)
    owner_path = (tmp_path / "owner.json").resolve()
    owner_path.write_text(json.dumps(owner), encoding="utf-8")
    owner_hash = commission.sha256(commission.canonical(owner))
    replacement = subscription_replacement_receipt(contract, now)
    replacement_path = (tmp_path / "replacement.json").resolve()
    replacement_path.write_text(json.dumps(replacement), encoding="utf-8")
    replacement_hash = commission.sha256(commission.canonical(replacement))
    output = (tmp_path / "result.json").resolve()
    contract_hash = commission.sha256(commission.canonical(contract))
    result = commission.main(
        [
            *cli_args("apply"),
            "--phase=subscription-replacement",
            "--acknowledge-contract-sha256=" + contract_hash,
            "--supabase-owner-readback-receipt=" + str(owner_path),
            "--acknowledge-supabase-owner-readback-sha256=" + owner_hash,
            "--subscription-replacement-receipt=" + str(replacement_path),
            "--acknowledge-subscription-replacement-sha256="
            + replacement_hash,
            "--receipt=" + str(output),
        ]
    )
    assert result == 0
    assert runner.applied[0] == (
        "pubsub", "subscriptions", "delete", name, "--quiet"
    )
    assert runner.applied[1][:4] == (
        "pubsub", "subscriptions", "create", name
    )
    assert "--enable-message-ordering" in runner.applied[1]
    assert (
        "--push-auth-token-audience="
        "https://aureon-trade-controller-25xhneniva-ew.a.run.app"
        in runner.applied[1]
    )


def test_finalize_preflight_blocks_all_mutation_and_redacts_receipt(
    monkeypatch, tmp_path
):
    contract = resolved_contract()
    snapshot = exact_snapshot(contract)
    snapshot["cloud_run"]["aureon-trade-controller"][
        "timeout_seconds"
    ] = 30

    class Runner:
        def __init__(self):
            self.applied = []

        def apply(self, *args):
            self.applied.append(args)

    runner = Runner()
    monkeypatch.setattr(commission, "Gcloud", lambda *_args: runner)
    monkeypatch.setattr(
        commission, "capture_snapshot", lambda *_args: snapshot
    )
    receipt = (tmp_path / "receipt.json").resolve()
    ack = commission.sha256(commission.canonical(contract))
    evidence_now = datetime.now(UTC)
    observed = retirement_receipt(contract, evidence_now)
    observed_path = (tmp_path / "legacy.json").resolve()
    observed_path.write_text(json.dumps(observed), encoding="utf-8")
    observed_hash = commission.sha256(commission.canonical(observed))
    owner_observed = owner_readback_receipt(contract, evidence_now)
    owner_path = (tmp_path / "owner.json").resolve()
    owner_path.write_text(json.dumps(owner_observed), encoding="utf-8")
    owner_hash = commission.sha256(commission.canonical(owner_observed))
    archive_observed = legacy_archive_receipt(contract, evidence_now)
    archive_path = (tmp_path / "archive.json").resolve()
    archive_path.write_text(json.dumps(archive_observed), encoding="utf-8")
    archive_hash = commission.sha256(
        commission.canonical(archive_observed)
    )
    phase_observed = legacy_retirement_phase_receipt(
        contract,
        evidence_now,
        owner=owner_observed,
        archive=archive_observed,
        zero=observed,
    )
    phase_path = (tmp_path / "legacy-phase.json").resolve()
    phase_path.write_text(json.dumps(phase_observed), encoding="utf-8")
    phase_hash = commission.sha256(commission.canonical(phase_observed))
    image_observed = immutable_image_receipt(contract, evidence_now)
    image_path = (tmp_path / "images.json").resolve()
    image_path.write_text(json.dumps(image_observed), encoding="utf-8")
    image_hash = commission.sha256(commission.canonical(image_observed))
    vm_observed = vm_release_receipt(
        contract,
        evidence_now,
        certificate=image_observed["certificate"],
    )
    vm_path = (tmp_path / "vm-release.json").resolve()
    vm_path.write_text(
        json.dumps(vm_observed, sort_keys=True, indent=2) + "\n",
        encoding="ascii",
    )
    vm_hash = commission.sha256(vm_path.read_bytes())
    reboot_observed = vm_reboot_receipt(
        contract, vm_observed, vm_hash, evidence_now
    )
    reboot_path = (tmp_path / "vm-reboot.json").resolve()
    reboot_hash = _write_vm_receipt(reboot_path, reboot_observed)
    result = commission.main(
        [
            *cli_args("apply"),
            "--phase=finalize",
            "--acknowledge-contract-sha256=" + ack,
            "--receipt=" + str(receipt),
            "--legacy-retirement-receipt=" + str(observed_path),
            "--acknowledge-legacy-retirement-sha256=" + observed_hash,
            "--legacy-retirement-phase-receipt=" + str(phase_path),
            "--acknowledge-legacy-retirement-phase-sha256=" + phase_hash,
            "--supabase-owner-readback-receipt=" + str(owner_path),
            "--acknowledge-supabase-owner-readback-sha256=" + owner_hash,
            "--legacy-retirement-owner-readback-receipt=" + str(owner_path),
            "--acknowledge-legacy-retirement-owner-readback-sha256="
            + owner_hash,
            "--legacy-archive-receipt=" + str(archive_path),
            "--acknowledge-legacy-archive-receipt-sha256=" + archive_hash,
            "--acknowledge-legacy-archive-scope-sha256="
            + archive_observed["scope_sha256"],
            "--vm-release-readback-receipt=" + str(vm_path),
            "--acknowledge-vm-release-readback-sha256=" + vm_hash,
            "--vm-reboot-continuity-receipt=" + str(reboot_path),
            "--acknowledge-vm-reboot-continuity-sha256=" + reboot_hash,
            "--immutable-image-build-receipt=" + str(image_path),
            "--acknowledge-immutable-image-build-receipt-sha256="
            + image_hash,
        ]
    )
    assert result == 1
    assert runner.applied == []
    raw = receipt.read_text(encoding="utf-8")
    value = json.loads(raw)
    assert value["status"] == "failed_closed"
    assert value["error_code"] == "finalize_prerequisites_not_exact"
    assert value["vm_release_readback_receipt_sha256"] == vm_hash
    assert value["vm_reboot_continuity_receipt_sha256"] == reboot_hash
    assert value["legacy_retirement_phase_receipt_sha256"] == phase_hash
    assert OWNER_SUBJECT not in raw
    assert OWNER_EMAIL_SHA256 not in raw
    assert "access_token" not in raw


def test_finalize_requires_vm_release_readback_before_any_mutation(
    monkeypatch, tmp_path
):
    contract = resolved_contract()
    snapshot = exact_snapshot(contract)

    class Runner:
        def __init__(self):
            self.applied = []

        def apply(self, *args):
            self.applied.append(args)

    runner = Runner()
    monkeypatch.setattr(commission, "Gcloud", lambda *_args: runner)
    monkeypatch.setattr(
        commission, "capture_snapshot", lambda *_args: snapshot
    )
    owner = owner_readback_receipt(contract, datetime.now(UTC))
    owner_path = (tmp_path / "owner.json").resolve()
    owner_path.write_text(json.dumps(owner), encoding="utf-8")
    owner_hash = commission.sha256(commission.canonical(owner))
    image = immutable_image_receipt(contract, datetime.now(UTC))
    image_path = (tmp_path / "finalize-images.json").resolve()
    image_path.write_text(json.dumps(image), encoding="utf-8")
    image_hash = commission.sha256(commission.canonical(image))
    output = (tmp_path / "failed.json").resolve()
    result = commission.main(
        [
            *cli_args("apply"),
            "--phase=finalize",
            "--acknowledge-contract-sha256="
            + commission.sha256(commission.canonical(contract)),
            "--supabase-owner-readback-receipt=" + str(owner_path),
            "--acknowledge-supabase-owner-readback-sha256=" + owner_hash,
            "--immutable-image-build-receipt=" + str(image_path),
            "--acknowledge-immutable-image-build-receipt-sha256="
            + image_hash,
            "--receipt=" + str(output),
        ]
    )
    assert result == 1
    assert runner.applied == []
    assert json.loads(output.read_text(encoding="utf-8"))["error_code"] == (
        "vm_release_receipt_required"
    )


def test_finalize_keeps_rollback_public_when_marketed_web_is_not_green(
    monkeypatch, tmp_path
):
    contract = resolved_contract()
    snapshot = exact_snapshot(contract)
    rollback_name = contract["cloud_run"][
        "rollback_service_without_anonymous_invoker"
    ]
    snapshot["cloud_run"][rollback_name] = {"invokers": ["allUsers"]}
    web = snapshot["cloud_run"]["aureon-fusion-web"]
    old_revision = "aureon-fusion-web-00000-old"
    web["serving_revision"] = old_revision
    web["traffic"] = [
        {"revision": old_revision, "percent": 100, "tag": None}
    ]

    class Runner:
        def __init__(self):
            self.applied = []

        def apply(self, *args):
            self.applied.append(args)

    runner = Runner()
    monkeypatch.setattr(commission, "Gcloud", lambda *_args: runner)
    monkeypatch.setattr(commission, "capture_snapshot", lambda *_args: snapshot)
    stub_valid_finalize_evidence(monkeypatch)
    output = (tmp_path / "finalize-not-green.json").resolve()

    result = commission.main(
        [
            *cli_args("apply"),
            "--phase=finalize",
            "--acknowledge-contract-sha256="
            + commission.sha256(commission.canonical(contract)),
            "--receipt=" + str(output),
        ]
    )

    assert result == 1
    assert runner.applied == []
    receipt = json.loads(output.read_text(encoding="utf-8"))
    assert receipt["status"] == "failed_closed"
    assert receipt["error_code"] == "finalize_prerequisites_not_exact"


def test_finalize_removes_rollback_anonymous_only_after_marketed_web_is_green(
    monkeypatch, tmp_path
):
    contract = resolved_contract()
    snapshot = exact_snapshot(contract)
    rollback_name = contract["cloud_run"][
        "rollback_service_without_anonymous_invoker"
    ]
    snapshot["cloud_run"][rollback_name] = {"invokers": ["allUsers"]}
    expected_call = (
        "run",
        "services",
        "remove-iam-policy-binding",
        rollback_name,
        "--region=" + contract["region"],
        "--member=allUsers",
        "--role=roles/run.invoker",
        "--condition=None",
    )

    class Runner:
        def __init__(self):
            self.applied = []

        def apply(self, *args):
            self.applied.append(args)
            if args == expected_call:
                snapshot["cloud_run"][rollback_name]["invokers"] = []

    runner = Runner()
    monkeypatch.setattr(commission, "Gcloud", lambda *_args: runner)
    monkeypatch.setattr(commission, "capture_snapshot", lambda *_args: snapshot)
    stub_valid_finalize_evidence(monkeypatch)
    output = (tmp_path / "finalize-green.json").resolve()

    result = commission.main(
        [
            *cli_args("apply"),
            "--phase=finalize",
            "--acknowledge-contract-sha256="
            + commission.sha256(commission.canonical(contract)),
            "--receipt=" + str(output),
        ]
    )

    assert result == 0
    assert runner.applied == [expected_call]
    receipt = json.loads(output.read_text(encoding="utf-8"))
    assert receipt["status"] == "applied"
    assert receipt["provider_readback_ok"] is True
    assert receipt["applied_action_ids"] == [
        "run.rollback.remove-anonymous."
        + commission.sha256(b"allUsers")[:12]
    ]
    assert receipt["rollback_anonymous_invoker_removal_deferred"] is False


def _staged_snapshot(contract):
    snapshot = exact_snapshot(contract)
    for row in snapshot["cloud_run"].values():
        staged_revision = row["latest_created_revision"]
        old_revision = staged_revision.replace("-00001-test", "-00000-old")
        row["serving_revision"] = old_revision
        row["latest_ready_revision"] = old_revision
        row["traffic"] = [
            {"revision": old_revision, "percent": 100, "tag": None}
        ]
    return snapshot


def test_staged_revision_audit_requires_latest_created_ready_with_zero_traffic():
    contract = resolved_contract()
    snapshot = _staged_snapshot(contract)
    audit = commission.audit_snapshot(
        contract,
        snapshot,
        allow_iam_extras=True,
        allow_vm_pending=True,
        cloud_run_mode="staged",
    )
    assert audit["ok"] is True
    assert audit["cloud_run_staged_without_traffic"] is True
    name = "aureon-trade-controller"
    snapshot["cloud_run"][name]["traffic"] = [
        {
            "revision": snapshot["cloud_run"][name]["latest_created_revision"],
            "percent": 100,
            "tag": None,
        }
    ]
    blocked = commission.audit_snapshot(
        contract,
        snapshot,
        allow_iam_extras=True,
        allow_vm_pending=True,
        cloud_run_mode="staged",
    )
    assert f"cloud_run.{name}.staged_revision_has_traffic" in blocked["errors"]

    snapshot = _staged_snapshot(contract)
    snapshot["cloud_run"]["aureon-trade-controller"]["invokers"].append(
        "allUsers"
    )
    strict_iam = commission.audit_snapshot(
        contract,
        snapshot,
        allow_iam_extras=False,
        allow_vm_pending=True,
        cloud_run_mode="staged",
    )
    assert strict_iam["ok"] is False
    assert "cloud_run.aureon-trade-controller.invokers" in strict_iam["errors"]


def test_immutable_image_receipt_rejects_wrong_digest_and_stale_time(tmp_path):
    contract = resolved_contract()
    receipt = immutable_image_receipt(contract, datetime.now(UTC))
    path = (tmp_path / "images.json").resolve()
    path.write_text(json.dumps(receipt), encoding="utf-8")
    receipt_hash = commission.sha256(commission.canonical(receipt))
    validated_hash, images, certificate = (
        commission.validate_immutable_image_build_receipt(
        contract, path, receipt_hash
        )
    )
    assert validated_hash == receipt_hash
    assert images["authority"] == contract["release"]["authority_image"]
    assert certificate["fingerprint_sha256"] == "3" * 64

    receipt["images"][0]["image"] = receipt["images"][0]["image"].replace(
        "b" * 64, "f" * 64
    )
    path.write_text(json.dumps(receipt), encoding="utf-8")
    wrong_hash = commission.sha256(commission.canonical(receipt))
    with pytest.raises(commission.CommissionError, match="binding_invalid"):
        commission.validate_immutable_image_build_receipt(
            contract, path, wrong_hash
        )

    receipt = immutable_image_receipt(
        contract, datetime.now(UTC) - timedelta(hours=7)
    )
    path.write_text(json.dumps(receipt), encoding="utf-8")
    stale_hash = commission.sha256(commission.canonical(receipt))
    with pytest.raises(commission.CommissionError, match="time_invalid"):
        commission.validate_immutable_image_build_receipt(
            contract, path, stale_hash
        )


def test_staged_attestation_is_read_only_and_release_consumable(monkeypatch, tmp_path):
    contract = resolved_contract()
    snapshot = _staged_snapshot(contract)
    capture_modes = []

    class Runner:
        def __init__(self):
            self.applied = []

        def apply(self, *args):
            self.applied.append(args)

    runner = Runner()
    monkeypatch.setattr(commission, "Gcloud", lambda *_args: runner)

    def capture(_contract, _runner, cloud_run_mode="serving"):
        capture_modes.append(cloud_run_mode)
        return snapshot

    monkeypatch.setattr(commission, "capture_snapshot", capture)
    owner = owner_readback_receipt(contract, datetime.now(UTC))
    owner_path = (tmp_path / "owner.json").resolve()
    owner_path.write_text(json.dumps(owner), encoding="utf-8")
    owner_hash = commission.sha256(commission.canonical(owner))
    image = immutable_image_receipt(contract, datetime.now(UTC))
    image_path = (tmp_path / "image.json").resolve()
    image_path.write_text(json.dumps(image), encoding="utf-8")
    image_hash = commission.sha256(commission.canonical(image))
    output = (tmp_path / "staged.json").resolve()
    result = commission.main(
        [
            *cli_args("apply"),
            "--phase=staged-revision-attestation",
            "--acknowledge-contract-sha256="
            + commission.sha256(commission.canonical(contract)),
            "--supabase-owner-readback-receipt=" + str(owner_path),
            "--acknowledge-supabase-owner-readback-sha256=" + owner_hash,
            "--immutable-image-build-receipt=" + str(image_path),
            "--acknowledge-immutable-image-build-receipt-sha256="
            + image_hash,
            "--receipt=" + str(output),
        ]
    )
    assert result == 0
    assert runner.applied == []
    assert capture_modes == ["staged"]
    receipt = json.loads(output.read_text(encoding="utf-8"))
    assert receipt["status"] == "staged_attested"
    assert receipt["phase"] == "staged-revision-attestation"
    assert receipt["cloud_run_staged_without_traffic"] is True
    assert receipt["cloud_run_traffic_changed"] is False
    assert receipt["immutable_image_build_receipt_sha256"] == image_hash
    assert receipt["provider_readback_sha256"] == commission.sha256(
        commission.canonical(receipt["provider_readback"])
    )


def test_legacy_retirement_deletes_exact_names_only_after_both_receipts(
    monkeypatch, tmp_path
):
    contract = resolved_contract()
    initial = freeze_legacy_publishers(contract, exact_snapshot(contract))
    targets = sorted(contract["pubsub"]["retire_after_zero_backlog"])
    initial["legacy_subscriptions"] = {
        name: {"name": name} for name in targets
    }
    state = deepcopy(initial)

    class Runner:
        def __init__(self):
            self.applied = []

        def apply(self, *args):
            self.applied.append(args)
            state["legacy_subscriptions"].pop(args[3])

    runner = Runner()
    monkeypatch.setattr(commission, "Gcloud", lambda *_args: runner)
    monkeypatch.setattr(
        commission, "capture_snapshot", lambda *_args: deepcopy(state)
    )
    now = datetime.now(UTC)
    owner = owner_readback_receipt(contract, now)
    archive = legacy_archive_receipt(contract, now)
    zero = retirement_receipt(contract, now)
    paths = {}
    for name, value in (("owner", owner), ("archive", archive), ("zero", zero)):
        path = (tmp_path / f"{name}.json").resolve()
        path.write_text(json.dumps(value), encoding="utf-8")
        paths[name] = (path, commission.sha256(commission.canonical(value)))
    output = (tmp_path / "legacy-retired.json").resolve()
    result = commission.main(
        [
            *cli_args("apply"),
            "--phase=legacy-retirement",
            "--acknowledge-contract-sha256="
            + commission.sha256(commission.canonical(contract)),
            "--supabase-owner-readback-receipt=" + str(paths["owner"][0]),
            "--acknowledge-supabase-owner-readback-sha256=" + paths["owner"][1],
            "--legacy-archive-receipt=" + str(paths["archive"][0]),
            "--acknowledge-legacy-archive-receipt-sha256="
            + paths["archive"][1],
            "--acknowledge-legacy-archive-scope-sha256="
            + archive["scope_sha256"],
            "--legacy-retirement-receipt=" + str(paths["zero"][0]),
            "--acknowledge-legacy-retirement-sha256=" + paths["zero"][1],
            "--receipt=" + str(output),
        ]
    )
    assert result == 0
    assert [call[3] for call in runner.applied] == targets
    assert all(call[:3] == ("pubsub", "subscriptions", "delete") for call in runner.applied)
    progress = json.loads(
        commission.legacy_retirement_progress_path(output).read_text(
            encoding="utf-8"
        )
    )
    assert progress["status"] == (
        "commands_completed_pending_provider_readback"
    )
    assert progress["completed_subscription_names"] == targets
    phase = json.loads(output.read_text(encoding="utf-8"))
    assert phase["status"] == "legacy_retired"
    assert phase["provider_readback"]["subscription_configuration"][
        "subscriptions"
    ] == commission.exact_subscription_configuration(
        contract, initial
    )["subscriptions"]
    phase_hash = commission.sha256(commission.canonical(phase))
    validated = commission.validate_legacy_retirement_phase_receipt(
        contract,
        output,
        phase_hash,
        archive_path=paths["archive"][0],
        archive_receipt_acknowledgement=paths["archive"][1],
        archive_scope_acknowledgement=archive["scope_sha256"],
        zero_path=paths["zero"][0],
        zero_acknowledgement=paths["zero"][1],
        retirement_owner_path=paths["owner"][0],
        retirement_owner_acknowledgement=paths["owner"][1],
    )
    assert validated == (
        phase_hash,
        paths["archive"][1],
        paths["zero"][1],
        paths["owner"][1],
    )


def test_legacy_retirement_stops_when_publisher_restarts_between_deletes(
    monkeypatch, tmp_path
):
    contract = resolved_contract()
    state = freeze_legacy_publishers(contract, exact_snapshot(contract))
    targets = sorted(contract["pubsub"]["retire_after_zero_backlog"])
    state["legacy_subscriptions"] = {
        name: {"name": name} for name in targets
    }

    class Runner:
        def __init__(self):
            self.applied = []

        def apply(self, *args):
            self.applied.append(args)
            state["legacy_subscriptions"].pop(args[3])
            state["vm"]["units"][
                "aureon-cloud-operator.service"
            ].update(
                active_state="active",
                sub_state="running",
                unit_file_state="enabled",
            )

    runner = Runner()
    monkeypatch.setattr(commission, "Gcloud", lambda *_args: runner)
    monkeypatch.setattr(
        commission, "capture_snapshot", lambda *_args: deepcopy(state)
    )
    now = datetime.now(UTC)
    values = {
        "owner": owner_readback_receipt(contract, now),
        "archive": legacy_archive_receipt(contract, now),
        "zero": retirement_receipt(contract, now),
    }
    paths = {}
    for label, value in values.items():
        path = (tmp_path / f"freeze-{label}.json").resolve()
        path.write_text(json.dumps(value), encoding="utf-8")
        paths[label] = (
            path,
            commission.sha256(commission.canonical(value)),
        )
    output = (tmp_path / "freeze-failed.json").resolve()
    result = commission.main(
        [
            *cli_args("apply"),
            "--phase=legacy-retirement",
            "--acknowledge-contract-sha256="
            + commission.sha256(commission.canonical(contract)),
            "--supabase-owner-readback-receipt=" + str(paths["owner"][0]),
            "--acknowledge-supabase-owner-readback-sha256="
            + paths["owner"][1],
            "--legacy-archive-receipt=" + str(paths["archive"][0]),
            "--acknowledge-legacy-archive-receipt-sha256="
            + paths["archive"][1],
            "--acknowledge-legacy-archive-scope-sha256="
            + values["archive"]["scope_sha256"],
            "--legacy-retirement-receipt=" + str(paths["zero"][0]),
            "--acknowledge-legacy-retirement-sha256=" + paths["zero"][1],
            "--receipt=" + str(output),
        ]
    )
    assert result == 1
    assert [call[3] for call in runner.applied] == targets[:1]
    failure = json.loads(output.read_text(encoding="utf-8"))
    assert failure["error_code"] == (
        "legacy_retirement_publisher_freeze_not_current"
    )


def test_legacy_retirement_requires_archive_before_zero_window(tmp_path):
    contract = resolved_contract()
    now = datetime.now(UTC)
    archive = legacy_archive_receipt(contract, now)
    zero = retirement_receipt(contract, now)
    archive["recorded_at"] = (
        now - timedelta(minutes=1)
    ).isoformat()
    archive_path = (tmp_path / "late-archive.json").resolve()
    zero_path = (tmp_path / "zero.json").resolve()
    archive_path.write_text(json.dumps(archive), encoding="utf-8")
    zero_path.write_text(json.dumps(zero), encoding="utf-8")
    with pytest.raises(
        commission.CommissionError,
        match="legacy_retirement_evidence_order_invalid",
    ):
        commission.validate_legacy_retirement_evidence_order(
            archive_path,
            zero_path,
            retirement_started_at=now,
        )


def test_legacy_phase_revalidates_exact_deletion_time_owner_receipt(tmp_path):
    contract = resolved_contract()
    now = datetime.now(UTC)
    original_owner = owner_readback_receipt(contract, now)
    different_owner_receipt = owner_readback_receipt(
        contract, now - timedelta(seconds=10)
    )
    archive = legacy_archive_receipt(contract, now)
    zero = retirement_receipt(contract, now)
    phase = legacy_retirement_phase_receipt(
        contract,
        now,
        owner=original_owner,
        archive=archive,
        zero=zero,
    )
    values = {
        "phase": phase,
        "archive": archive,
        "zero": zero,
        "owner": different_owner_receipt,
    }
    paths = {}
    for label, value in values.items():
        path = (tmp_path / f"owner-chain-{label}.json").resolve()
        path.write_text(json.dumps(value), encoding="utf-8")
        paths[label] = (
            path,
            commission.sha256(commission.canonical(value)),
        )
    with pytest.raises(
        commission.CommissionError,
        match="legacy_retirement_phase_receipt_chain_invalid",
    ):
        commission.validate_legacy_retirement_phase_receipt(
            contract,
            paths["phase"][0],
            paths["phase"][1],
            archive_path=paths["archive"][0],
            archive_receipt_acknowledgement=paths["archive"][1],
            archive_scope_acknowledgement=archive["scope_sha256"],
            zero_path=paths["zero"][0],
            zero_acknowledgement=paths["zero"][1],
            retirement_owner_path=paths["owner"][0],
            retirement_owner_acknowledgement=paths["owner"][1],
            now=now,
        )


def test_legacy_retirement_resumes_uncertain_partial_delete(
    monkeypatch, tmp_path
):
    contract = resolved_contract()
    state = freeze_legacy_publishers(contract, exact_snapshot(contract))
    targets = sorted(contract["pubsub"]["retire_after_zero_backlog"])
    state["legacy_subscriptions"] = {
        name: {"name": name} for name in targets
    }

    class Runner:
        def __init__(self):
            self.applied = []
            self.fail_once = True

        def apply(self, *args):
            name = args[3]
            self.applied.append(args)
            state["legacy_subscriptions"].pop(name)
            if name == targets[1] and self.fail_once:
                self.fail_once = False
                raise commission.CommissionError("fixture_uncertain_delete")

    runner = Runner()
    monkeypatch.setattr(commission, "Gcloud", lambda *_args: runner)
    monkeypatch.setattr(
        commission, "capture_snapshot", lambda *_args: deepcopy(state)
    )
    now = datetime.now(UTC)
    values = {
        "owner": owner_readback_receipt(contract, now),
        "archive": legacy_archive_receipt(contract, now),
        "zero": retirement_receipt(contract, now),
    }
    paths = {}
    for label, value in values.items():
        path = (tmp_path / f"resume-{label}.json").resolve()
        path.write_text(json.dumps(value), encoding="utf-8")
        paths[label] = (
            path,
            commission.sha256(commission.canonical(value)),
        )
    retirement_owner_path = (tmp_path / "retirement-owner.json").resolve()
    retirement_owner_path.write_text(
        json.dumps(values["owner"]), encoding="utf-8"
    )
    retirement_owner_hash = paths["owner"][1]
    output = (tmp_path / "legacy-resume.json").resolve()
    command = [
        *cli_args("apply"),
        "--phase=legacy-retirement",
        "--acknowledge-contract-sha256="
        + commission.sha256(commission.canonical(contract)),
        "--supabase-owner-readback-receipt=" + str(paths["owner"][0]),
        "--acknowledge-supabase-owner-readback-sha256="
        + paths["owner"][1],
        "--legacy-retirement-owner-readback-receipt="
        + str(retirement_owner_path),
        "--acknowledge-legacy-retirement-owner-readback-sha256="
        + retirement_owner_hash,
        "--legacy-archive-receipt=" + str(paths["archive"][0]),
        "--acknowledge-legacy-archive-receipt-sha256="
        + paths["archive"][1],
        "--acknowledge-legacy-archive-scope-sha256="
        + values["archive"]["scope_sha256"],
        "--legacy-retirement-receipt=" + str(paths["zero"][0]),
        "--acknowledge-legacy-retirement-sha256=" + paths["zero"][1],
        "--receipt=" + str(output),
    ]

    assert commission.main(command) == 1
    progress_path = commission.legacy_retirement_progress_path(output)
    failed_progress = json.loads(progress_path.read_text(encoding="utf-8"))
    assert failed_progress["status"] == "recovery_required"
    assert failed_progress["completed_subscription_names"] == targets[:1]
    assert failed_progress["in_flight_subscription_name"] == targets[1]
    assert sorted(state["legacy_subscriptions"]) == targets[2:]

    resume_now = now + timedelta(minutes=20)
    refreshed_owner = owner_readback_receipt(contract, resume_now)
    paths["owner"][0].write_text(
        json.dumps(refreshed_owner), encoding="utf-8"
    )
    refreshed_owner_hash = commission.sha256(
        commission.canonical(refreshed_owner)
    )
    command = [
        (
            "--acknowledge-supabase-owner-readback-sha256="
            + refreshed_owner_hash
            if item.startswith(
                "--acknowledge-supabase-owner-readback-sha256="
            )
            else item
        )
        for item in command
    ]

    class ResumeDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return resume_now if tz is not None else resume_now.replace(
                tzinfo=None
            )

    monkeypatch.setattr(commission, "datetime", ResumeDateTime)
    assert commission.main(command) == 0
    assert [call[3] for call in runner.applied] == targets
    completed_progress = json.loads(
        progress_path.read_text(encoding="utf-8")
    )
    assert completed_progress["status"] == (
        "commands_completed_pending_provider_readback"
    )
    assert completed_progress["completed_subscription_names"] == targets
    phase = json.loads(output.read_text(encoding="utf-8"))
    assert phase["status"] == "legacy_retired"
    assert phase["supabase_owner_readback_receipt_sha256"] == (
        retirement_owner_hash
    )
    assert phase["retirement_started_at"] == failed_progress["started_at"]
    assert phase["applied_action_ids"] == [
        f"subscription.{name}.retire" for name in targets
    ]


def test_legacy_retirement_refuses_subscription_drift_before_delete(
    monkeypatch, tmp_path
):
    contract = resolved_contract()
    snapshot = freeze_legacy_publishers(contract, exact_snapshot(contract))
    targets = sorted(contract["pubsub"]["retire_after_zero_backlog"])
    snapshot["legacy_subscriptions"] = {
        name: {"name": name} for name in targets
    }
    controller = contract["pubsub"]["push_subscriptions"][0]["name"]
    snapshot["subscriptions"][controller]["enable_message_ordering"] = False

    class Runner:
        def __init__(self):
            self.applied = []

        def apply(self, *args):
            self.applied.append(args)

    runner = Runner()
    monkeypatch.setattr(commission, "Gcloud", lambda *_args: runner)
    monkeypatch.setattr(commission, "capture_snapshot", lambda *_args: snapshot)
    now = datetime.now(UTC)
    values = {
        "owner": owner_readback_receipt(contract, now),
        "archive": legacy_archive_receipt(contract, now),
        "zero": retirement_receipt(contract, now),
    }
    paths = {}
    for name, value in values.items():
        path = (tmp_path / f"{name}.json").resolve()
        path.write_text(json.dumps(value), encoding="utf-8")
        paths[name] = (path, commission.sha256(commission.canonical(value)))
    output = (tmp_path / "failed.json").resolve()
    result = commission.main(
        [
            *cli_args("apply"),
            "--phase=legacy-retirement",
            "--acknowledge-contract-sha256="
            + commission.sha256(commission.canonical(contract)),
            "--supabase-owner-readback-receipt=" + str(paths["owner"][0]),
            "--acknowledge-supabase-owner-readback-sha256=" + paths["owner"][1],
            "--legacy-archive-receipt=" + str(paths["archive"][0]),
            "--acknowledge-legacy-archive-receipt-sha256=" + paths["archive"][1],
            "--acknowledge-legacy-archive-scope-sha256="
            + values["archive"]["scope_sha256"],
            "--legacy-retirement-receipt=" + str(paths["zero"][0]),
            "--acknowledge-legacy-retirement-sha256=" + paths["zero"][1],
            "--receipt=" + str(output),
        ]
    )
    assert result == 1
    assert runner.applied == []
    assert json.loads(output.read_text(encoding="utf-8"))["error_code"] == (
        "replacement_subscriptions_not_exact_before_legacy_retirement"
    )
