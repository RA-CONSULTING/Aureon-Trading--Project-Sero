"""Offline tests for the reviewed VM identity contract."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import pytest


MODULE = Path(__file__).resolve().parents[1] / "provision_vm.py"
spec = importlib.util.spec_from_file_location("provision_vm", MODULE)
provision_vm = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = provision_vm
spec.loader.exec_module(provision_vm)


def instance(**overrides):
    value = {
        "machineType": "projects/p/zones/z/machineTypes/e2-standard-8",
        "networkInterfaces": [
            {
                "network": "projects/p/global/networks/aureon-sero-network",
                "subnetwork": (
                    "projects/p/regions/europe-west1/subnetworks/"
                    "aureon-sero-europe-west1"
                ),
            }
        ],
        "disks": [{"autoDelete": False, "diskSizeGb": "50"}],
        "serviceAccounts": [
            {
                "email": provision_vm.SERVICE_ACCOUNT,
                "scopes": [provision_vm.CLOUD_PLATFORM_SCOPE],
            }
        ],
    }
    value.update(overrides)
    return value


def test_exact_runtime_identity_and_instance_are_accepted():
    provision_vm.validate_instance(instance())


@pytest.mark.parametrize(
    "accounts,reason",
    [
        ([], "exactly_one_service_account"),
        ([{"email": "wrong@example.invalid", "scopes": [provision_vm.CLOUD_PLATFORM_SCOPE]}], "service_account_mismatch"),
        ([{"email": provision_vm.SERVICE_ACCOUNT, "scopes": []}], "cloud_platform_scope_mismatch"),
        ([{"email": provision_vm.SERVICE_ACCOUNT, "scopes": [provision_vm.CLOUD_PLATFORM_SCOPE, "extra"]}], "cloud_platform_scope_mismatch"),
    ],
)
def test_missing_wrong_or_overbroad_runtime_identity_is_rejected(accounts, reason):
    with pytest.raises(provision_vm.ProvisionError, match=reason):
        provision_vm.validate_runtime_identity({"serviceAccounts": accounts})


def test_script_is_import_safe_and_no_longer_provisions_an_identityless_vm():
    source = MODULE.read_text(encoding="utf-8")
    assert 'if __name__ == "__main__"' in source
    assert "--no-service-account" not in source
    assert "--no-scopes" not in source
    assert '"--service-account=" + SERVICE_ACCOUNT' in source
    assert '"--scopes=" + CLOUD_PLATFORM_SCOPE' in source
