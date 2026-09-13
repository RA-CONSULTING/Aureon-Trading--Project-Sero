"""Offline tests for the fail-closed legacy Pub/Sub archive transaction."""

from __future__ import annotations

import base64
from collections import Counter
from dataclasses import replace
import importlib.util
import json
from pathlib import Path
import sys
import threading
import time
from typing import Any, Mapping

import pytest


CONTROL = Path(__file__).resolve().parents[1] / "trading-control"
sys.path.insert(0, str(CONTROL))
MODULE = CONTROL / "legacy_backlog_archive.py"
spec = importlib.util.spec_from_file_location("legacy_backlog_archive", MODULE)
assert spec and spec.loader
archive = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = archive
spec.loader.exec_module(archive)


BUCKET = "aureon-legacy-archive-test"
KMS_KEY = (
    "projects/aureon-trading/locations/europe-west1/"
    "keyRings/archive/cryptoKeys/pubsub-archive"
)
CONTRACT_SHA256 = "a" * 64
SOURCE_REVISION = "1" * 40


def message(
    message_id: str,
    payload: bytes,
    *,
    ack_id: str | None = None,
    attributes: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    return {
        "ackId": ack_id or "ack-" + message_id,
        "deliveryAttempt": 2,
        "message": {
            "messageId": message_id,
            "publishTime": "2026-09-13T16:40:00.123456Z",
            "orderingKey": "legacy-order",
            "attributes": dict(attributes or {"kind": "receipt", "version": "1"}),
            "data": base64.b64encode(payload).decode("ascii"),
        },
    }


def scope(**updates: Any) -> dict[str, Any]:
    values = {
        "contract_sha256": CONTRACT_SHA256,
        "source_revision": SOURCE_REVISION,
        "bucket": BUCKET,
        "kms_key": KMS_KEY,
        "prefix": archive.DEFAULT_PREFIX,
        "batch_size": 10,
        "max_total_messages": 100,
        "max_total_bytes": 10_000_000,
        "max_runtime_seconds": 300,
        "empty_polls": 2,
        "minimum_retention_seconds": 604_800,
    }
    values.update(updates)
    return archive.archive_scope(**values)


class FakeProvider:
    def __init__(self, queues: Mapping[str, list[Mapping[str, Any]]] | None = None):
        self.queues = {
            name: [dict(row) for row in (queues or {}).get(name, [])]
            for name in archive.SUBSCRIPTIONS
        }
        self.objects: dict[str, tuple[archive.ObjectState, bytes]] = {}
        self.operations: list[tuple[str, str]] = []
        self.created = Counter()
        self.successful_acknowledgements: list[tuple[str, tuple[str, ...]]] = []
        self.fail_upload = False
        self.mismatch_generation_once = False
        self.fail_acknowledgements = 0
        self.fail_pull_once: set[str] = set()
        self.frozen = True
        self.valid_bucket = True

    def publisher_freeze_readback(self) -> Mapping[str, Any]:
        state = "inactive" if self.frozen else "active"
        unit_file_state = "disabled" if self.frozen else "enabled"
        return {
            "instance": archive.INSTANCE,
            "units": [
                {
                    "unit": unit,
                    "active_state": state,
                    "unit_file_state": unit_file_state,
                }
                for unit in archive.PUBLISHER_UNITS
            ],
        }

    def bucket_metadata(self, bucket: str) -> Mapping[str, Any]:
        retention = 604_800 if self.valid_bucket else "invalid"
        return {
            "name": bucket,
            "location": "EUROPE-WEST1",
            "retentionPolicy": {
                "isLocked": True,
                "retentionPeriod": retention,
            },
            "iamConfiguration": {
                "uniformBucketLevelAccess": {"enabled": True},
                "publicAccessPrevention": "enforced",
            },
            "encryption": {"defaultKmsKeyName": KMS_KEY},
        }

    def pull(self, subscription: str, maximum: int) -> list[Mapping[str, Any]]:
        self.operations.append(("pull", subscription))
        if subscription in self.fail_pull_once:
            self.fail_pull_once.remove(subscription)
            raise archive.ArchiveError("synthetic_pull_failure")
        return self.queues[subscription][:maximum]

    def put_if_absent(
        self,
        bucket: str,
        name: str,
        value: bytes,
        *,
        kms_key: str,
        metadata: Mapping[str, str],
    ) -> archive.ObjectState:
        self.operations.append(("put", name))
        if self.fail_upload:
            raise archive.ArchiveError("synthetic_upload_failure")
        if name in self.objects:
            return self.objects[name][0]
        state = archive.ObjectState(
            bucket=bucket,
            name=name,
            generation="1",
            size=len(value),
            kms_key_name=kms_key + "/cryptoKeyVersions/7",
            event_based_hold=True,
            metadata=dict(metadata),
            crc32c=archive._crc32c(value),
        )
        self.objects[name] = (state, value)
        self.created[name] += 1
        return state

    def read_object(
        self,
        bucket: str,
        name: str,
        generation: str,
        *,
        maximum_bytes: int,
    ) -> tuple[archive.ObjectState, bytes]:
        self.operations.append(("read", name))
        state, value = self.objects[name]
        assert bucket == state.bucket
        assert maximum_bytes > len(value)
        if self.mismatch_generation_once:
            self.mismatch_generation_once = False
            return replace(state, generation=str(int(generation) + 1)), value
        assert generation == state.generation
        return state, value

    def list_objects(self, bucket: str, prefix: str) -> list[archive.ObjectState]:
        self.operations.append(("list", prefix))
        assert bucket == BUCKET
        return [
            state for name, (state, _value) in self.objects.items()
            if name.startswith(prefix)
        ]

    def acknowledge(self, subscription: str, ack_ids: list[str]) -> None:
        self.operations.append(("ack", subscription))
        if self.fail_acknowledgements:
            self.fail_acknowledgements -= 1
            raise archive.ArchiveError("synthetic_ack_failure")
        wanted = set(ack_ids)
        self.queues[subscription] = [
            row for row in self.queues[subscription]
            if row.get("ackId") not in wanted
        ]
        self.successful_acknowledgements.append((subscription, tuple(ack_ids)))


def run(
    provider: FakeProvider,
    *,
    io_workers: int = archive.ARCHIVE_IO_MAX_WORKERS,
    **scope_updates: Any,
) -> dict[str, Any]:
    return archive.archive_backlogs(
        provider,
        scope=scope(**scope_updates),
        sleep=lambda _seconds: None,
        clock=lambda: 0.0,
        io_workers=io_workers,
    )


def test_empty_backlogs_emit_bound_redacted_receipt_without_acknowledgement():
    provider = FakeProvider()

    receipt = run(provider)

    assert receipt["status"] == "archived_and_acknowledged"
    assert receipt["contract_sha256"] == CONTRACT_SHA256
    assert receipt["source_revision"] == SOURCE_REVISION
    assert receipt["root_manifest"]["message_count"] == 0
    assert receipt["acknowledged_this_run"] == 0
    assert len([op for op in provider.operations if op[0] == "pull"]) == 8
    assert not any(op[0] == "ack" for op in provider.operations)
    assert receipt["subscription_deleted"] is False
    assert receipt["order_execution"] is False
    assert KMS_KEY not in json.dumps(receipt)
    assert receipt["archive_kms_key_sha256"] == archive.sha256(KMS_KEY.encode())


def test_nonempty_payload_and_manifest_are_read_back_before_acknowledgement():
    payload = b"\x00raw-message-bytes\xff"
    subscription = archive.SUBSCRIPTIONS[0]
    provider = FakeProvider({
        subscription: [message("m-100", payload, attributes={"z": "last", "a": "first"})]
    })

    receipt = run(provider)

    message_name = next(name for name in provider.objects if "/messages/" in name)
    batch_name = next(name for name in provider.objects if "/batches/" in name)
    body = json.loads(provider.objects[message_name][1])
    assert base64.b64decode(body["message"]["data_base64"]) == payload
    assert body["message"]["attributes"] == {"a": "first", "z": "last"}
    assert body["message"]["message_id"] == "m-100"
    assert body["message"]["publish_time"] == "2026-09-13T16:40:00.123456Z"
    assert body["message"]["data_sha256"] == archive.sha256(payload)

    positions = {
        marker: provider.operations.index(marker)
        for marker in (
            ("put", message_name),
            ("read", message_name),
            ("put", batch_name),
            ("read", batch_name),
            ("ack", subscription),
        )
    }
    assert positions[("put", message_name)] < positions[("read", message_name)]
    assert positions[("read", message_name)] < positions[("put", batch_name)]
    assert positions[("put", batch_name)] < positions[("read", batch_name)]
    assert positions[("read", batch_name)] < positions[("ack", subscription)]
    assert provider.operations.count(("read", message_name)) >= 2
    assert receipt["root_manifest"]["message_count"] == 1
    assert receipt["acknowledged_this_run"] == 1


def test_parallel_message_and_final_proofs_are_bounded_before_acknowledgement():
    subscription = archive.SUBSCRIPTIONS[0]

    class ConcurrentProvider(FakeProvider):
        def __init__(self):
            super().__init__({
                subscription: [
                    message(f"m-parallel-{index}", str(index).encode())
                    for index in range(8)
                ]
            })
            self.lock = threading.Lock()
            self.active_message_puts = 0
            self.max_message_puts = 0
            self.final_validation = False
            self.active_final_reads = 0
            self.max_final_reads = 0

        def put_if_absent(self, bucket, name, value, *, kms_key, metadata):
            is_message = "/messages/" in name
            if is_message:
                with self.lock:
                    self.active_message_puts += 1
                    self.max_message_puts = max(
                        self.max_message_puts, self.active_message_puts
                    )
                time.sleep(0.01)
            try:
                return super().put_if_absent(
                    bucket,
                    name,
                    value,
                    kms_key=kms_key,
                    metadata=metadata,
                )
            finally:
                if is_message:
                    with self.lock:
                        self.active_message_puts -= 1

        def list_objects(self, bucket, prefix):
            result = super().list_objects(bucket, prefix)
            self.final_validation = True
            return result

        def read_object(self, bucket, name, generation, *, maximum_bytes):
            track = self.final_validation and "/messages/" in name
            if track:
                with self.lock:
                    self.active_final_reads += 1
                    self.max_final_reads = max(
                        self.max_final_reads, self.active_final_reads
                    )
                time.sleep(0.01)
            try:
                return super().read_object(
                    bucket,
                    name,
                    generation,
                    maximum_bytes=maximum_bytes,
                )
            finally:
                if track:
                    with self.lock:
                        self.active_final_reads -= 1

    provider = ConcurrentProvider()
    receipt = run(provider)

    assert 2 <= provider.max_message_puts <= archive.ARCHIVE_IO_MAX_WORKERS
    assert 2 <= provider.max_final_reads <= archive.ARCHIVE_IO_MAX_WORKERS
    ack_position = provider.operations.index(("ack", subscription))
    batch_name = next(name for name in provider.objects if "/batches/" in name)
    assert provider.operations.index(("read", batch_name)) < ack_position
    message_names = [name for name in provider.objects if "/messages/" in name]
    assert all(
        provider.operations.index(("read", name)) < ack_position
        for name in message_names
    )
    assert receipt["acknowledged_this_run"] == 8


def test_parallel_and_serial_archive_outputs_are_equivalent():
    subscription = archive.SUBSCRIPTIONS[0]
    queues = {
        subscription: [
            message(f"m-equivalent-{index}", f"payload-{index}".encode())
            for index in range(6)
        ]
    }
    serial_provider = FakeProvider(queues)
    parallel_provider = FakeProvider(queues)

    serial_receipt = run(serial_provider, io_workers=1)
    parallel_receipt = run(
        parallel_provider,
        io_workers=archive.ARCHIVE_IO_MAX_WORKERS,
    )

    serial_receipt.pop("recorded_at")
    parallel_receipt.pop("recorded_at")
    assert serial_receipt == parallel_receipt
    assert serial_provider.objects == parallel_provider.objects


def test_parallel_failure_creates_no_batch_and_acknowledges_nothing():
    subscription = archive.SUBSCRIPTIONS[0]

    class OneMessageFails(FakeProvider):
        def put_if_absent(self, bucket, name, value, *, kms_key, metadata):
            if name.endswith("/m-fail.json"):
                raise archive.ArchiveError("synthetic_one_message_failure")
            return super().put_if_absent(
                bucket,
                name,
                value,
                kms_key=kms_key,
                metadata=metadata,
            )

    provider = OneMessageFails({
        subscription: [
            message("m-good-a", b"a"),
            message("m-fail", b"failure"),
            message("m-good-b", b"b"),
        ]
    })

    with pytest.raises(
        archive.ArchiveError,
        match="synthetic_one_message_failure",
    ):
        run(provider)

    assert not any("/batches/" in name for name in provider.objects)
    assert not provider.successful_acknowledgements
    assert len(provider.queues[subscription]) == 3


def test_upload_failure_fails_before_any_acknowledgement():
    provider = FakeProvider({archive.SUBSCRIPTIONS[0]: [message("m-upload", b"x")]})
    provider.fail_upload = True

    with pytest.raises(archive.ArchiveError, match="synthetic_upload_failure"):
        run(provider)

    assert not any(op[0] == "ack" for op in provider.operations)
    assert provider.queues[archive.SUBSCRIPTIONS[0]]


def test_generation_mismatch_fails_before_any_acknowledgement():
    provider = FakeProvider({archive.SUBSCRIPTIONS[0]: [message("m-generation", b"x")]})
    provider.mismatch_generation_once = True

    with pytest.raises(archive.ArchiveError, match="storage_generation_mismatch"):
        run(provider)

    assert not any(op[0] == "ack" for op in provider.operations)
    assert provider.queues[archive.SUBSCRIPTIONS[0]]


def test_ack_failure_leaves_durable_objects_and_restart_is_idempotent():
    subscription = archive.SUBSCRIPTIONS[0]
    provider = FakeProvider({subscription: [message("m-restart", b"restart-safe")]})
    provider.fail_acknowledgements = 1

    with pytest.raises(archive.ArchiveError, match="synthetic_ack_failure"):
        run(provider)

    durable_names = set(provider.objects)
    assert len(durable_names) == 2
    assert any("/messages/" in name for name in durable_names)
    assert any("/batches/" in name for name in durable_names)
    assert provider.queues[subscription]

    receipt = run(provider)
    after_restart = set(provider.objects)
    assert durable_names < after_restart
    assert receipt["acknowledged_this_run"] == 1
    assert not provider.queues[subscription]
    assert all(count == 1 for count in provider.created.values())

    stable_names = set(provider.objects)
    stable_values = dict(provider.objects)
    third = run(provider)
    assert set(provider.objects) == stable_names
    assert provider.objects == stable_values
    assert third["acknowledged_this_run"] == 0
    assert all(count == 1 for count in provider.created.values())


def test_partial_run_restart_preserves_first_ack_and_finishes_remaining_queue():
    first, second = archive.SUBSCRIPTIONS[:2]
    provider = FakeProvider({
        first: [message("m-first", b"first")],
        second: [message("m-second", b"second")],
    })
    provider.fail_pull_once.add(second)

    with pytest.raises(archive.ArchiveError, match="synthetic_pull_failure"):
        run(provider)

    assert not provider.queues[first]
    assert provider.queues[second]
    first_message_name = next(
        name for name in provider.objects if name.endswith("/m-first.json")
    )
    first_generation = provider.objects[first_message_name][0].generation

    receipt = run(provider)
    assert not provider.queues[first]
    assert not provider.queues[second]
    assert provider.objects[first_message_name][0].generation == first_generation
    assert receipt["root_manifest"]["message_count"] == 2
    assert receipt["acknowledged_this_run"] == 1
    assert all(count == 1 for count in provider.created.values())


def test_publishers_and_bucket_must_pass_provider_readback():
    provider = FakeProvider()
    provider.frozen = False
    with pytest.raises(archive.ArchiveError, match="publishers_not_frozen"):
        run(provider)
    assert not any(op[0] == "pull" for op in provider.operations)

    provider = FakeProvider()
    provider.valid_bucket = False
    with pytest.raises(archive.ArchiveError, match="archive_bucket_contract_invalid"):
        run(provider)
    assert not any(op[0] == "pull" for op in provider.operations)


def test_source_contains_no_subscription_delete_or_mutation_route():
    source = MODULE.read_text(encoding="utf-8").lower()
    assert "subscriptions delete" not in source
    assert "subscriptions.delete" not in source
    assert "delete_subscription" not in source
    assert ":publish" not in source
    assert "run services update-traffic" not in source


def test_crc32c_matches_standard_check_vector_and_batch_bound_fails_before_write():
    assert archive._crc32c(b"123456789") == "4waSgw=="
    subscription = archive.SUBSCRIPTIONS[0]
    provider = FakeProvider({
        subscription: [message("m-bound-1", b"1"), message("m-bound-2", b"2")]
    })

    with pytest.raises(
        archive.ArchiveError, match="archive_message_bound_reached_before_drain"
    ):
        run(provider, max_total_messages=1)

    assert not provider.objects
    assert not any(op[0] == "ack" for op in provider.operations)


def test_archive_cli_requires_exact_reviewed_scope_hash_before_provider_use(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
):
    result = archive.main([
        "archive",
        "--contract-sha256", CONTRACT_SHA256,
        "--source-revision", SOURCE_REVISION,
        "--bucket", BUCKET,
        "--cmek-key", KMS_KEY,
        "--acknowledge-scope-sha256", "f" * 64,
        "--receipt", str((tmp_path / "receipt.json").resolve()),
    ])

    assert result == 1
    assert capsys.readouterr().out.strip() == (
        "exact_archive_scope_acknowledgement_required"
    )
