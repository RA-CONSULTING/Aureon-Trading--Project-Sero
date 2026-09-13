"""Offline tests for the root-only VM token broker contract."""

from __future__ import annotations

from datetime import UTC, datetime
import importlib.util
import json
from pathlib import Path
import sys

import pytest


GOOGLE_CLOUD = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(GOOGLE_CLOUD))


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    value = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = value
    spec.loader.exec_module(value)
    return value


identity = load(
    "vm_workload_identity_tested",
    GOOGLE_CLOUD / "vm_workload_identity.py",
)
broker = load("vm_token_broker_tested", GOOGLE_CLOUD / "vm_token_broker.py")

NOW = 1_800_000_000.0
SOURCE_TOKEN = "source_token_" + "s" * 32
WORKLOAD_TOKEN = "workload_token_" + "w" * 32


def expiry(seconds=1_800):
    return (
        datetime.fromtimestamp(NOW + seconds, UTC)
        .isoformat()
        .replace("+00:00", "Z")
    )


def test_attached_identity_and_token_are_both_provider_bound():
    calls = []

    def reader(url, **kwargs):
        calls.append((url, kwargs))
        if url == broker.METADATA_EMAIL:
            return broker.BROKER_SERVICE_ACCOUNT.encode("ascii")
        if url == broker.METADATA_TOKEN:
            return json.dumps(
                {"access_token": SOURCE_TOKEN, "expires_in": 3_600}
            ).encode("ascii")
        raise AssertionError(url)

    assert broker._attached_token(reader) == SOURCE_TOKEN
    assert [row[0] for row in calls] == [
        broker.METADATA_EMAIL,
        broker.METADATA_TOKEN,
    ]
    assert all(
        row[1]["headers"] == {"Metadata-Flavor": "Google"}
        for row in calls
    )


def test_wrong_attached_identity_fails_before_impersonation():
    def reader(url, **_kwargs):
        if url == broker.METADATA_EMAIL:
            return b"wrong@aureon-trading.iam.gserviceaccount.com"
        return json.dumps(
            {"access_token": SOURCE_TOKEN, "expires_in": 3_600}
        ).encode("ascii")

    with pytest.raises(broker.BrokerError, match="metadata_identity_invalid"):
        broker._attached_token(reader)


def test_mint_is_fixed_to_one_reviewed_workload_and_short_lifetime():
    workload = broker.WORKLOADS[1]
    captured = {}

    def reader(url, **kwargs):
        captured.update(url=url, **kwargs)
        return json.dumps(
            {"accessToken": WORKLOAD_TOKEN, "expireTime": expiry()}
        ).encode("ascii")

    value = broker.mint(
        workload, SOURCE_TOKEN, reader=reader, now=NOW
    )
    assert captured["url"] == (
        broker.IAM_ROOT + workload.service_account + ":generateAccessToken"
    )
    assert captured["method"] == "POST"
    assert captured["headers"]["Authorization"] == "Bearer " + SOURCE_TOKEN
    assert json.loads(captured["body"]) == {
        "lifetime": "1800s",
        "scope": ["https://www.googleapis.com/auth/cloud-platform"],
    }
    assert value == {
        "schema": identity.TOKEN_SCHEMA,
        "service_account": workload.service_account,
        "access_token": WORKLOAD_TOKEN,
        "token_type": "Bearer",
        "expires_at_epoch": NOW + 1_800,
    }


def test_rotate_mints_every_identity_before_installing_any_file():
    installed = []
    iam_calls = 0

    def reader(url, **_kwargs):
        nonlocal iam_calls
        if url == broker.METADATA_EMAIL:
            return broker.BROKER_SERVICE_ACCOUNT.encode("ascii")
        if url == broker.METADATA_TOKEN:
            return json.dumps(
                {"access_token": SOURCE_TOKEN, "expires_in": 3_600}
            ).encode("ascii")
        iam_calls += 1
        if iam_calls == 3:
            raise broker.BrokerError("offline_iam_failure")
        return json.dumps(
            {"accessToken": WORKLOAD_TOKEN, "expireTime": expiry()}
        ).encode("ascii")

    with pytest.raises(broker.BrokerError, match="offline_iam_failure"):
        broker.rotate_once(
            reader=reader,
            installer=lambda workload, value: installed.append(
                (workload, value)
            ),
            now=NOW,
        )
    assert installed == []


def token_payload(
    *,
    expires=NOW + 1_800,
    service_account=(
        "aureon-vm-operator@aureon-trading.iam.gserviceaccount.com"
    ),
    **extra,
):
    return json.dumps(
        {
            "schema": identity.TOKEN_SCHEMA,
            "service_account": service_account,
            "access_token": WORKLOAD_TOKEN,
            "token_type": "Bearer",
            "expires_at_epoch": expires,
            **extra,
        },
        sort_keys=True,
    ).encode("ascii")


def test_workload_token_file_contract_is_exact_and_expiring(monkeypatch):
    path = "/run/aureon-cloud-identity/operator/token.json"
    monkeypatch.setattr(
        identity, "_trusted_file", lambda _path: token_payload()
    )
    assert (
        identity.broker_token(
            {
                identity.BROKER_REQUIRED_ENV: "1",
                identity.TOKEN_FILE_ENV: path,
            },
            now=NOW,
        )
        == WORKLOAD_TOKEN
    )
    with pytest.raises(
        identity.WorkloadIdentityError, match="token_file_invalid"
    ):
        identity._decode_token(
            token_payload(extra="forbidden"),
            now=NOW,
            expected_service_account=identity.TOKEN_FILE_IDENTITIES[path],
        )
    with pytest.raises(
        identity.WorkloadIdentityError, match="token_file_invalid"
    ):
        identity._decode_token(
            token_payload(expires=NOW + 20),
            now=NOW,
            expected_service_account=identity.TOKEN_FILE_IDENTITIES[path],
        )
    with pytest.raises(
        identity.WorkloadIdentityError, match="token_file_invalid"
    ):
        identity._decode_token(
            token_payload(
                service_account=(
                    "aureon-vm-ui@aureon-trading.iam.gserviceaccount.com"
                )
            ),
            now=NOW,
            expected_service_account=identity.TOKEN_FILE_IDENTITIES[path],
        )


def test_broker_mode_never_falls_back_to_metadata():
    with pytest.raises(
        identity.WorkloadIdentityError, match="token_file_required"
    ):
        identity.broker_token(
            {identity.BROKER_REQUIRED_ENV: "1"}, now=NOW
        )
    with pytest.raises(
        identity.WorkloadIdentityError, match="token_file_path_invalid"
    ):
        identity.broker_token(
            {
                identity.BROKER_REQUIRED_ENV: "1",
                identity.TOKEN_FILE_ENV: "/tmp/attacker-token.json",
            },
            now=NOW,
        )
    assert identity.broker_token({}, now=NOW) is None


def test_broker_source_has_no_token_output_path():
    source = (GOOGLE_CLOUD / "vm_token_broker.py").read_text(
        encoding="utf-8"
    )
    assert "print(token" not in source
    assert "print(value" not in source
    assert "never prints token material" in source
