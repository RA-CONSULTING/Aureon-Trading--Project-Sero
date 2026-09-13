"""Archive and acknowledge Aureon's four retired Pub/Sub subscriptions.

The command is deliberately narrow.  It first proves that both VM publishers
are stopped and disabled, then pulls only the four legacy subscriptions named
below.  Acknowledgement happens only after each message and its batch manifest
have been written with a create-only precondition to a locked, uniform-access,
CMEK Cloud Storage bucket and read back at the exact provider generation.

The tool never invokes an Aureon runtime, processes an order, changes traffic,
or deletes a subscription.  A later, independent Cloud Monitoring receipt is
still required before the subscriptions may be retired.
"""

from __future__ import annotations

import argparse
import base64
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import re
import shlex
import subprocess
import time
from typing import Any, Callable, Mapping, Protocol
from urllib.error import HTTPError
from urllib.parse import quote, urlencode
from urllib.request import (
    HTTPRedirectHandler,
    ProxyHandler,
    Request,
    build_opener,
)

from authority_commission import CommissionError, canonical, sha256, write_receipt


PROJECT = "aureon-trading"
ZONE = "europe-west1-b"
INSTANCE = "aureon-sero-20260906"
SUBSCRIPTIONS = (
    "aureon-trade-review-v1",
    "aureon-trade-dispatch-v1",
    "aureon-trade-executor-v1",
    "aureon-trade-receipt-v1",
)
PUBLISHER_UNITS = (
    "aureon-cloud-operator.service",
    "aureon-cloud-trade-receipt.service",
)
ARCHIVE_SCHEMA = "aureon.gcp.pubsub-legacy-message-archive.v1"
BATCH_SCHEMA = "aureon.gcp.pubsub-legacy-archive-batch.v1"
ROOT_SCHEMA = "aureon.gcp.pubsub-legacy-archive-root.v1"
RECEIPT_SCHEMA = "aureon.gcp.pubsub-legacy-archive-receipt.v1"
SCOPE_SCHEMA = "aureon.gcp.pubsub-legacy-archive-scope.v1"
DEFAULT_PREFIX = "aureon-trade-legacy-archive"
ARCHIVE_IO_MAX_WORKERS = 4

_HEX40 = re.compile(r"[0-9a-f]{40}")
_HEX64 = re.compile(r"[0-9a-f]{64}")
_TOKEN = re.compile(r"[A-Za-z0-9._~-]{20,8192}")
_BUCKET = re.compile(r"[a-z0-9][a-z0-9._-]{1,61}[a-z0-9]")
_MESSAGE_ID = re.compile(r"[A-Za-z0-9_-]{1,256}")
_PREFIX = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,255}")
_KMS_KEY = re.compile(
    r"projects/([a-z][a-z0-9-]{4,28}[a-z0-9])/locations/"
    r"([a-z0-9-]+)/keyRings/([A-Za-z0-9_-]{1,63})/"
    r"cryptoKeys/([A-Za-z0-9_-]{1,63})"
)
_RFC3339 = re.compile(
    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,9})?Z"
)


class ArchiveError(RuntimeError):
    """A stable failure that never contains message, token, or provider text."""


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ArchiveError("provider_redirect_denied")


@dataclass(frozen=True)
class ObjectState:
    bucket: str
    name: str
    generation: str
    size: int
    kms_key_name: str
    event_based_hold: bool
    metadata: dict[str, str]
    crc32c: str | None = None


@dataclass(frozen=True)
class PulledMessage:
    ack_id: str
    message_id: str
    publish_time: str
    data_base64: str
    attributes: dict[str, str]
    ordering_key: str
    delivery_attempt: int | None


class Provider(Protocol):
    def publisher_freeze_readback(self) -> Mapping[str, Any]: ...

    def bucket_metadata(self, bucket: str) -> Mapping[str, Any]: ...

    def pull(self, subscription: str, maximum: int) -> list[Mapping[str, Any]]: ...

    def put_if_absent(
        self,
        bucket: str,
        name: str,
        value: bytes,
        *,
        kms_key: str,
        metadata: Mapping[str, str],
    ) -> ObjectState: ...

    def read_object(
        self,
        bucket: str,
        name: str,
        generation: str,
        *,
        maximum_bytes: int,
    ) -> tuple[ObjectState, bytes]: ...

    def list_objects(self, bucket: str, prefix: str) -> list[ObjectState]: ...

    def acknowledge(self, subscription: str, ack_ids: list[str]) -> None: ...


def _crc32c(value: bytes) -> str:
    """Return the RFC 4960 CRC32C checksum in Cloud Storage wire format."""

    crc = 0xFFFFFFFF
    for byte in value:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ (0x82F63B78 if crc & 1 else 0)
    raw = ((crc ^ 0xFFFFFFFF) & 0xFFFFFFFF).to_bytes(4, "big")
    return base64.b64encode(raw).decode("ascii")


def _state(value: Mapping[str, Any]) -> ObjectState:
    try:
        bucket = value["bucket"]
        name = value["name"]
        generation = str(value["generation"])
        size = int(value["size"])
        kms = value["kmsKeyName"]
        hold = value["eventBasedHold"]
        metadata = value["metadata"]
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        raise ArchiveError("storage_object_metadata_invalid") from exc
    if (
        not isinstance(bucket, str)
        or not isinstance(name, str)
        or not generation.isdigit()
        or size < 0
        or not isinstance(kms, str)
        or hold is not True
        or not isinstance(metadata, Mapping)
        or any(
            not isinstance(key, str) or not isinstance(item, str)
            for key, item in metadata.items()
        )
    ):
        raise ArchiveError("storage_object_metadata_invalid")
    crc = value.get("crc32c")
    if crc is not None and not isinstance(crc, str):
        raise ArchiveError("storage_object_metadata_invalid")
    return ObjectState(
        bucket=bucket,
        name=name,
        generation=generation,
        size=size,
        kms_key_name=kms,
        event_based_hold=True,
        metadata=dict(metadata),
        crc32c=crc,
    )


def _kms_matches(actual: str, expected: str) -> bool:
    return actual == expected or actual.startswith(expected + "/cryptoKeyVersions/")


def _object_metadata(
    *, schema: str, contract_sha256: str, source_revision: str, payload: bytes,
) -> dict[str, str]:
    return {
        "aureon_schema": schema,
        "aureon_contract_sha256": contract_sha256,
        "aureon_source_revision": source_revision,
        "aureon_payload_sha256": sha256(payload),
    }


def _validate_object(
    state: ObjectState,
    value: bytes,
    *,
    bucket: str,
    name: str,
    expected: bytes,
    kms_key: str,
    metadata: Mapping[str, str],
) -> None:
    if (
        state.bucket != bucket
        or state.name != name
        or state.size != len(expected)
        or not _kms_matches(state.kms_key_name, kms_key)
        or state.event_based_hold is not True
        or state.metadata != dict(metadata)
        or value != expected
        or sha256(value) != metadata.get("aureon_payload_sha256")
        or state.crc32c != _crc32c(expected)
    ):
        raise ArchiveError("storage_object_readback_mismatch")


def ensure_object(
    provider: Provider,
    *,
    bucket: str,
    name: str,
    value: bytes,
    kms_key: str,
    metadata: Mapping[str, str],
) -> ObjectState:
    uploaded = provider.put_if_absent(
        bucket, name, value, kms_key=kms_key, metadata=metadata
    )
    observed, body = provider.read_object(
        bucket,
        name,
        uploaded.generation,
        maximum_bytes=len(value) + 1,
    )
    if uploaded.generation != observed.generation:
        raise ArchiveError("storage_generation_mismatch")
    _validate_object(
        observed,
        body,
        bucket=bucket,
        name=name,
        expected=value,
        kms_key=kms_key,
        metadata=metadata,
    )
    return observed


def validate_bucket(
    value: Mapping[str, Any],
    *,
    bucket: str,
    kms_key: str,
    minimum_retention_seconds: int,
) -> None:
    retention = value.get("retentionPolicy")
    iam = value.get("iamConfiguration")
    encryption = value.get("encryption")
    try:
        retention_seconds = int(retention.get("retentionPeriod", 0)) \
            if isinstance(retention, Mapping) else 0
    except (TypeError, ValueError, OverflowError) as exc:
        raise ArchiveError("archive_bucket_contract_invalid") from exc
    key_match = _KMS_KEY.fullmatch(kms_key)
    key_location = key_match.group(2).lower() if key_match else ""
    bucket_location = value.get("location")
    if (
        value.get("name") != bucket
        or not isinstance(bucket_location, str)
        or bucket_location.lower() != key_location
        or not isinstance(retention, Mapping)
        or retention.get("isLocked") is not True
        or retention_seconds < minimum_retention_seconds
        or not isinstance(iam, Mapping)
        or not isinstance(iam.get("uniformBucketLevelAccess"), Mapping)
        or iam["uniformBucketLevelAccess"].get("enabled") is not True
        or iam.get("publicAccessPrevention") != "enforced"
        or not isinstance(encryption, Mapping)
        or encryption.get("defaultKmsKeyName") != kms_key
    ):
        raise ArchiveError("archive_bucket_contract_invalid")


def validate_freeze(value: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ArchiveError("publisher_freeze_readback_invalid")
    rows = value.get("units")
    if (
        value.get("instance") != INSTANCE
        or not isinstance(rows, list)
        or len(rows) != len(PUBLISHER_UNITS)
    ):
        raise ArchiveError("publisher_freeze_readback_invalid")
    observed: dict[str, dict[str, str]] = {}
    for row in rows:
        if not isinstance(row, Mapping) or set(row) != {
            "unit", "active_state", "unit_file_state"
        }:
            raise ArchiveError("publisher_freeze_readback_invalid")
        unit = row.get("unit")
        active = row.get("active_state")
        enabled = row.get("unit_file_state")
        if (
            unit not in PUBLISHER_UNITS
            or unit in observed
            or active != "inactive"
            or enabled not in {"disabled", "masked"}
        ):
            raise ArchiveError("publishers_not_frozen")
        observed[str(unit)] = {
            "active_state": str(active),
            "unit_file_state": str(enabled),
        }
    return {
        "instance": INSTANCE,
        "units": [
            {"unit": unit, **observed[unit]}
            for unit in PUBLISHER_UNITS
        ],
    }


def parse_message(value: Mapping[str, Any], *, maximum_bytes: int) -> PulledMessage:
    if not isinstance(value, Mapping) or not set(value) <= {
        "ackId", "message", "deliveryAttempt"
    }:
        raise ArchiveError("pubsub_message_invalid")
    ack_id = value.get("ackId")
    message = value.get("message")
    attempt = value.get("deliveryAttempt")
    if (
        not isinstance(ack_id, str)
        or not 1 <= len(ack_id) <= 8192
        or not isinstance(message, Mapping)
        or not set(message) <= {
            "data", "attributes", "messageId", "publishTime", "orderingKey"
        }
    ):
        raise ArchiveError("pubsub_message_invalid")
    message_id = message.get("messageId")
    publish_time = message.get("publishTime")
    data_text = message.get("data", "")
    attributes = message.get("attributes", {})
    ordering_key = message.get("orderingKey", "")
    if (
        not isinstance(message_id, str)
        or _MESSAGE_ID.fullmatch(message_id) is None
        or not isinstance(publish_time, str)
        or _RFC3339.fullmatch(publish_time) is None
        or not isinstance(data_text, str)
        or not isinstance(attributes, Mapping)
        or len(attributes) > 100
        or any(
            not isinstance(key, str)
            or not isinstance(item, str)
            or not 1 <= len(key) <= 1024
            or len(item) > 4096
            for key, item in attributes.items()
        )
        or not isinstance(ordering_key, str)
        or len(ordering_key) > 1024
        or (
            attempt is not None
            and (isinstance(attempt, bool) or not isinstance(attempt, int) or attempt < 1)
        )
    ):
        raise ArchiveError("pubsub_message_invalid")
    try:
        raw = base64.b64decode(data_text, validate=True)
    except (ValueError, TypeError) as exc:
        raise ArchiveError("pubsub_message_invalid") from exc
    if len(raw) > maximum_bytes:
        raise ArchiveError("pubsub_message_too_large")
    # Canonicalize the base64 spelling while preserving the exact decoded bytes.
    return PulledMessage(
        ack_id=ack_id,
        message_id=message_id,
        publish_time=publish_time,
        data_base64=base64.b64encode(raw).decode("ascii"),
        attributes={str(key): str(attributes[key]) for key in sorted(attributes)},
        ordering_key=ordering_key,
        delivery_attempt=attempt,
    )


def archive_payload(
    message: PulledMessage,
    *,
    subscription: str,
    contract_sha256: str,
    source_revision: str,
) -> dict[str, Any]:
    raw = base64.b64decode(message.data_base64, validate=True)
    return {
        "schema": ARCHIVE_SCHEMA,
        "project": PROJECT,
        "contract_sha256": contract_sha256,
        "source_revision": source_revision,
        "subscription": f"projects/{PROJECT}/subscriptions/{subscription}",
        "message": {
            "message_id": message.message_id,
            "publish_time": message.publish_time,
            "ordering_key": message.ordering_key,
            "attributes": message.attributes,
            "data_base64": message.data_base64,
            "data_sha256": sha256(raw),
            "delivery_attempt": message.delivery_attempt,
        },
    }


def archive_scope(
    *,
    contract_sha256: str,
    source_revision: str,
    bucket: str,
    kms_key: str,
    prefix: str,
    batch_size: int,
    max_total_messages: int,
    max_total_bytes: int,
    max_runtime_seconds: int,
    empty_polls: int,
    minimum_retention_seconds: int,
) -> dict[str, Any]:
    if (
        _HEX64.fullmatch(contract_sha256 or "") is None
        or _HEX40.fullmatch(source_revision or "") is None
        or _BUCKET.fullmatch(bucket or "") is None
        or _KMS_KEY.fullmatch(kms_key or "") is None
        or not kms_key.startswith(f"projects/{PROJECT}/")
        or _PREFIX.fullmatch(prefix or "") is None
        or prefix.startswith("/")
        or prefix.endswith("/")
        or ".." in prefix.split("/")
        or not 1 <= batch_size <= 100
        or not 1 <= max_total_messages <= 100_000
        or not 1 <= max_total_bytes <= 100 * 1024 * 1024 * 1024
        or not 30 <= max_runtime_seconds <= 86_400
        or not 2 <= empty_polls <= 20
        or not 86_400 <= minimum_retention_seconds <= 315_576_000
    ):
        raise ArchiveError("archive_scope_invalid")
    return {
        "schema": SCOPE_SCHEMA,
        "project": PROJECT,
        "zone": ZONE,
        "instance": INSTANCE,
        "publisher_units": list(PUBLISHER_UNITS),
        "subscriptions": [
            f"projects/{PROJECT}/subscriptions/{name}" for name in SUBSCRIPTIONS
        ],
        "contract_sha256": contract_sha256,
        "source_revision": source_revision,
        "bucket": bucket,
        "kms_key": kms_key,
        "prefix": prefix,
        "batch_size": batch_size,
        "max_total_messages": max_total_messages,
        "max_total_bytes": max_total_bytes,
        "max_runtime_seconds": max_runtime_seconds,
        "empty_polls": empty_polls,
        "minimum_retention_seconds": minimum_retention_seconds,
        "subscription_deletion": False,
        "order_execution": False,
    }


def _message_object_name(
    prefix: str, source_revision: str, contract_sha256: str,
    subscription: str, message_id: str,
) -> str:
    return (
        f"{prefix}/v1/{source_revision}/{contract_sha256}/messages/"
        f"{subscription}/{message_id}.json"
    )


def _batch_prefix(
    prefix: str, source_revision: str, contract_sha256: str,
) -> str:
    return f"{prefix}/v1/{source_revision}/{contract_sha256}/batches/"


def _ensure_message(
    provider: Provider,
    message: PulledMessage,
    *,
    subscription: str,
    scope: Mapping[str, Any],
) -> dict[str, Any]:
    payload = archive_payload(
        message,
        subscription=subscription,
        contract_sha256=scope["contract_sha256"],
        source_revision=scope["source_revision"],
    )
    raw = canonical(payload)
    name = _message_object_name(
        scope["prefix"],
        scope["source_revision"],
        scope["contract_sha256"],
        subscription,
        message.message_id,
    )
    metadata = _object_metadata(
        schema=ARCHIVE_SCHEMA,
        contract_sha256=scope["contract_sha256"],
        source_revision=scope["source_revision"],
        payload=raw,
    )
    state = ensure_object(
        provider,
        bucket=scope["bucket"],
        name=name,
        value=raw,
        kms_key=scope["kms_key"],
        metadata=metadata,
    )
    return {
        "message_id": message.message_id,
        "publish_time": message.publish_time,
        "data_sha256": payload["message"]["data_sha256"],
        "object_name": name,
        "generation": state.generation,
        "payload_sha256": sha256(raw),
    }


def _parallel_ordered(
    items: list[Any],
    operation: Callable[[Any], Any],
    *,
    max_workers: int,
) -> list[Any]:
    """Run independent archive proofs concurrently with deterministic errors."""

    if not 1 <= max_workers <= ARCHIVE_IO_MAX_WORKERS:
        raise ArchiveError("archive_parallelism_invalid")
    if not items:
        return []
    with ThreadPoolExecutor(max_workers=min(max_workers, len(items))) as pool:
        futures = [pool.submit(operation, item) for item in items]
        # Resolve in input order so any surfaced failure is deterministic. No
        # caller writes a batch manifest or acknowledges before this returns.
        return [future.result() for future in futures]


def _ensure_batch(
    provider: Provider,
    entries: list[dict[str, Any]],
    *,
    subscription: str,
    scope: Mapping[str, Any],
) -> dict[str, Any]:
    payload = {
        "schema": BATCH_SCHEMA,
        "project": PROJECT,
        "contract_sha256": scope["contract_sha256"],
        "source_revision": scope["source_revision"],
        "subscription": f"projects/{PROJECT}/subscriptions/{subscription}",
        "messages": sorted(entries, key=lambda row: row["message_id"]),
    }
    raw = canonical(payload)
    digest = sha256(raw)
    name = (
        _batch_prefix(scope["prefix"], scope["source_revision"], scope["contract_sha256"])
        + subscription
        + "/"
        + digest
        + ".json"
    )
    metadata = _object_metadata(
        schema=BATCH_SCHEMA,
        contract_sha256=scope["contract_sha256"],
        source_revision=scope["source_revision"],
        payload=raw,
    )
    state = ensure_object(
        provider,
        bucket=scope["bucket"],
        name=name,
        value=raw,
        kms_key=scope["kms_key"],
        metadata=metadata,
    )
    return {
        "object_name": name,
        "generation": state.generation,
        "payload_sha256": digest,
        "message_count": len(entries),
    }


def _validate_message_reference(
    provider: Provider,
    entry: Mapping[str, Any],
    *,
    subscription: str,
    scope: Mapping[str, Any],
) -> None:
    """Re-read an archived message at the manifest's exact generation."""

    name = str(entry["object_name"])
    generation = str(entry["generation"])
    observed, raw = provider.read_object(
        scope["bucket"],
        name,
        generation,
        maximum_bytes=16 * 1024 * 1024,
    )
    if observed.generation != generation:
        raise ArchiveError("storage_generation_mismatch")
    expected_meta = _object_metadata(
        schema=ARCHIVE_SCHEMA,
        contract_sha256=scope["contract_sha256"],
        source_revision=scope["source_revision"],
        payload=raw,
    )
    _validate_object(
        observed,
        raw,
        bucket=scope["bucket"],
        name=name,
        expected=raw,
        kms_key=scope["kms_key"],
        metadata=expected_meta,
    )
    try:
        payload = json.loads(raw)
    except (ValueError, TypeError, UnicodeError) as exc:
        raise ArchiveError("archive_message_object_invalid") from exc
    if (
        not isinstance(payload, Mapping)
        or set(payload) != {
            "schema", "project", "contract_sha256", "source_revision",
            "subscription", "message",
        }
        or payload.get("schema") != ARCHIVE_SCHEMA
        or payload.get("project") != PROJECT
        or payload.get("contract_sha256") != scope["contract_sha256"]
        or payload.get("source_revision") != scope["source_revision"]
        or payload.get("subscription") != subscription
        or not isinstance(payload.get("message"), Mapping)
        or canonical(payload) != raw
    ):
        raise ArchiveError("archive_message_object_invalid")
    message_value = payload["message"]
    if set(message_value) != {
        "message_id", "publish_time", "ordering_key", "attributes",
        "data_base64", "data_sha256", "delivery_attempt",
    }:
        raise ArchiveError("archive_message_object_invalid")
    try:
        parsed = parse_message(
            {
                "ackId": "archive-readback",
                "deliveryAttempt": message_value.get("delivery_attempt"),
                "message": {
                    "messageId": message_value.get("message_id"),
                    "publishTime": message_value.get("publish_time"),
                    "orderingKey": message_value.get("ordering_key"),
                    "attributes": message_value.get("attributes"),
                    "data": message_value.get("data_base64"),
                },
            },
            maximum_bytes=10_000_000,
        )
        data = base64.b64decode(parsed.data_base64, validate=True)
    except ArchiveError as exc:
        raise ArchiveError("archive_message_object_invalid") from exc
    if (
        payload != archive_payload(
            parsed,
            subscription=subscription.rsplit("/", 1)[-1],
            contract_sha256=scope["contract_sha256"],
            source_revision=scope["source_revision"],
        )
        or message_value.get("message_id") != entry["message_id"]
        or message_value.get("publish_time") != entry["publish_time"]
        or message_value.get("data_sha256") != entry["data_sha256"]
        or sha256(data) != entry["data_sha256"]
        or sha256(raw) != entry["payload_sha256"]
    ):
        raise ArchiveError("archive_message_object_invalid")


def _read_existing_batches(
    provider: Provider,
    *,
    scope: Mapping[str, Any],
    io_workers: int = ARCHIVE_IO_MAX_WORKERS,
) -> tuple[list[dict[str, Any]], dict[tuple[str, str], dict[str, Any]]]:
    prefix = _batch_prefix(
        scope["prefix"], scope["source_revision"], scope["contract_sha256"]
    )
    states = provider.list_objects(scope["bucket"], prefix)
    if len(states) > scope["max_total_messages"] * 2 + 100:
        raise ArchiveError("archive_manifest_inventory_too_large")
    batches: list[dict[str, Any]] = []
    messages: dict[tuple[str, str], dict[str, Any]] = {}
    for listed in sorted(states, key=lambda item: item.name):
        observed, raw = provider.read_object(
            scope["bucket"],
            listed.name,
            listed.generation,
            maximum_bytes=16 * 1024 * 1024,
        )
        if observed.generation != listed.generation:
            raise ArchiveError("storage_generation_mismatch")
        expected_meta = _object_metadata(
            schema=BATCH_SCHEMA,
            contract_sha256=scope["contract_sha256"],
            source_revision=scope["source_revision"],
            payload=raw,
        )
        _validate_object(
            observed,
            raw,
            bucket=scope["bucket"],
            name=listed.name,
            expected=raw,
            kms_key=scope["kms_key"],
            metadata=expected_meta,
        )
        try:
            payload = json.loads(raw)
        except (ValueError, TypeError, UnicodeError) as exc:
            raise ArchiveError("archive_batch_manifest_invalid") from exc
        if (
            not isinstance(payload, Mapping)
            or set(payload) != {
                "schema", "project", "contract_sha256", "source_revision",
                "subscription", "messages",
            }
            or payload.get("schema") != BATCH_SCHEMA
            or payload.get("project") != PROJECT
            or payload.get("contract_sha256") != scope["contract_sha256"]
            or payload.get("source_revision") != scope["source_revision"]
            or payload.get("subscription") not in scope["subscriptions"]
            or not isinstance(payload.get("messages"), list)
            or not payload["messages"]
        ):
            raise ArchiveError("archive_batch_manifest_invalid")
        subscription = payload["subscription"]
        short = subscription.rsplit("/", 1)[-1]
        expected_path = prefix + short + "/" + sha256(raw) + ".json"
        if listed.name != expected_path:
            raise ArchiveError("archive_batch_manifest_invalid")
        for entry in payload["messages"]:
            if not isinstance(entry, Mapping) or set(entry) != {
                "message_id", "publish_time", "data_sha256", "object_name",
                "generation", "payload_sha256",
            }:
                raise ArchiveError("archive_batch_manifest_invalid")
            message_id = entry.get("message_id")
            if (
                not isinstance(message_id, str)
                or _MESSAGE_ID.fullmatch(message_id) is None
                or _HEX64.fullmatch(str(entry.get("data_sha256") or "")) is None
                or _HEX64.fullmatch(str(entry.get("payload_sha256") or "")) is None
                or not str(entry.get("generation") or "").isdigit()
                or entry.get("object_name") != _message_object_name(
                    scope["prefix"], scope["source_revision"],
                    scope["contract_sha256"], short, message_id,
                )
            ):
                raise ArchiveError("archive_batch_manifest_invalid")
            key = (subscription, message_id)
            normalized = dict(entry)
            if key in messages and messages[key] != normalized:
                raise ArchiveError("archive_message_identity_collision")
            messages[key] = normalized
        batches.append({
            "object_name": listed.name,
            "generation": listed.generation,
            "payload_sha256": sha256(raw),
            "message_count": len(payload["messages"]),
        })
    references = [
        (subscription, entry)
        for (subscription, _message_id), entry in sorted(messages.items())
    ]

    def validate_reference(item: tuple[str, dict[str, Any]]) -> None:
        subscription, entry = item
        _validate_message_reference(
            provider,
            entry,
            subscription=subscription,
            scope=scope,
        )

    _parallel_ordered(
        references,
        validate_reference,
        max_workers=io_workers,
    )
    return batches, messages


def _ensure_root(
    provider: Provider,
    *,
    scope: Mapping[str, Any],
    freeze: Mapping[str, Any],
    batch_rows: list[dict[str, Any]],
    messages: Mapping[tuple[str, str], Mapping[str, Any]],
) -> dict[str, Any]:
    counts = {
        resource: sum(1 for (subscription, _message_id) in messages if subscription == resource)
        for resource in scope["subscriptions"]
    }
    payload = {
        "schema": ROOT_SCHEMA,
        "project": PROJECT,
        "contract_sha256": scope["contract_sha256"],
        "source_revision": scope["source_revision"],
        "publisher_freeze": freeze,
        "subscriptions": [
            {"resource_name": resource, "archived_message_count": counts[resource]}
            for resource in scope["subscriptions"]
        ],
        "batch_manifests": sorted(batch_rows, key=lambda row: row["object_name"]),
    }
    raw = canonical(payload)
    digest = sha256(raw)
    name = (
        f"{scope['prefix']}/v1/{scope['source_revision']}/"
        f"{scope['contract_sha256']}/roots/{digest}.json"
    )
    metadata = _object_metadata(
        schema=ROOT_SCHEMA,
        contract_sha256=scope["contract_sha256"],
        source_revision=scope["source_revision"],
        payload=raw,
    )
    state = ensure_object(
        provider,
        bucket=scope["bucket"],
        name=name,
        value=raw,
        kms_key=scope["kms_key"],
        metadata=metadata,
    )
    return {
        "object_name": name,
        "generation": state.generation,
        "payload_sha256": digest,
        "message_count": sum(counts.values()),
    }


def archive_backlogs(
    provider: Provider,
    *,
    scope: Mapping[str, Any],
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
    io_workers: int = ARCHIVE_IO_MAX_WORKERS,
) -> dict[str, Any]:
    """Archive and acknowledge a bounded backlog, returning a redacted receipt."""

    if not 1 <= io_workers <= ARCHIVE_IO_MAX_WORKERS:
        raise ArchiveError("archive_parallelism_invalid")

    freeze = validate_freeze(provider.publisher_freeze_readback())
    validate_bucket(
        provider.bucket_metadata(scope["bucket"]),
        bucket=scope["bucket"],
        kms_key=scope["kms_key"],
        minimum_retention_seconds=scope["minimum_retention_seconds"],
    )
    started = clock()
    acknowledged = 0
    archived_bytes = 0
    empty_counts: dict[str, int] = {}
    batches_this_run = 0
    for subscription in SUBSCRIPTIONS:
        empties = 0
        while empties < scope["empty_polls"]:
            if clock() - started > scope["max_runtime_seconds"]:
                raise ArchiveError("archive_runtime_bound_reached_before_drain")
            if acknowledged >= scope["max_total_messages"]:
                raise ArchiveError("archive_message_bound_reached_before_drain")
            pulled = provider.pull(subscription, scope["batch_size"])
            if not pulled:
                empties += 1
                if empties < scope["empty_polls"]:
                    sleep(1.0)
                continue
            empties = 0
            parsed = [
                parse_message(row, maximum_bytes=min(10_000_000, scope["max_total_bytes"]))
                for row in pulled
            ]
            if len(parsed) > scope["batch_size"]:
                raise ArchiveError("pubsub_pull_batch_invalid")
            projected = archived_bytes + sum(
                len(base64.b64decode(row.data_base64, validate=True)) for row in parsed
            )
            if projected > scope["max_total_bytes"]:
                raise ArchiveError("archive_byte_bound_reached_before_drain")
            if acknowledged + len(parsed) > scope["max_total_messages"]:
                raise ArchiveError("archive_message_bound_reached_before_drain")
            ordered_messages = sorted(parsed, key=lambda row: row.message_id)
            entries = _parallel_ordered(
                ordered_messages,
                lambda message: _ensure_message(
                    provider,
                    message,
                    subscription=subscription,
                    scope=scope,
                ),
                max_workers=io_workers,
            )
            entries_by_id: dict[str, dict[str, Any]] = {}
            ack_ids: list[str] = []
            for message, entry in zip(ordered_messages, entries, strict=True):
                prior = entries_by_id.get(message.message_id)
                if prior is not None and prior != entry:
                    raise ArchiveError("archive_message_identity_collision")
                entries_by_id[message.message_id] = entry
                ack_ids.append(message.ack_id)
            _ensure_batch(
                provider,
                list(entries_by_id.values()),
                subscription=subscription,
                scope=scope,
            )
            batches_this_run += 1
            provider.acknowledge(subscription, ack_ids)
            acknowledged += len(parsed)
            archived_bytes = projected
        empty_counts[subscription] = empties

    final_freeze = validate_freeze(provider.publisher_freeze_readback())
    if final_freeze != freeze:
        raise ArchiveError("publisher_freeze_changed_during_archive")
    validate_bucket(
        provider.bucket_metadata(scope["bucket"]),
        bucket=scope["bucket"],
        kms_key=scope["kms_key"],
        minimum_retention_seconds=scope["minimum_retention_seconds"],
    )
    batches, messages = _read_existing_batches(
        provider,
        scope=scope,
        io_workers=io_workers,
    )
    root = _ensure_root(
        provider,
        scope=scope,
        freeze=freeze,
        batch_rows=batches,
        messages=messages,
    )
    return {
        "schema": RECEIPT_SCHEMA,
        "status": "archived_and_acknowledged",
        "provider": "google_cloud_storage_and_pubsub",
        "project": PROJECT,
        "contract_sha256": scope["contract_sha256"],
        "source_revision": scope["source_revision"],
        "recorded_at": datetime.now(UTC).isoformat(),
        "scope_sha256": sha256(canonical(scope)),
        "publisher_freeze": freeze,
        "publisher_freeze_reverified_after_drain": True,
        "archive_bucket_reverified_after_drain": True,
        "archive_bucket": scope["bucket"],
        "archive_kms_key_sha256": sha256(scope["kms_key"].encode("utf-8")),
        "root_manifest": root,
        "acknowledged_this_run": acknowledged,
        "archived_bytes_this_run": archived_bytes,
        "batch_manifests_this_run": batches_this_run,
        "empty_poll_confirmations": [
            {
                "resource_name": f"projects/{PROJECT}/subscriptions/{name}",
                "count": empty_counts[name],
            }
            for name in SUBSCRIPTIONS
        ],
        "subscription_deleted": False,
        "order_execution": False,
        "cloud_run_traffic_changed": False,
        "release_authority": False,
    }


class GcpProvider:
    """Minimal fixed-host Pub/Sub, Storage, and VM readback client."""

    def __init__(self, *, gcloud: str, token: str | None = None):
        self.gcloud = gcloud
        self.token = token or self._token()

    def _token(self) -> str:
        try:
            result = subprocess.run(
                [self.gcloud, "auth", "print-access-token", "--quiet"],
                check=False,
                capture_output=True,
                text=True,
                timeout=30,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ArchiveError("gcloud_token_failed") from exc
        token = result.stdout.strip()
        if result.returncode or _TOKEN.fullmatch(token) is None:
            raise ArchiveError("gcloud_token_failed")
        return token

    def _request(
        self,
        method: str,
        url: str,
        *,
        body: bytes | None = None,
        content_type: str = "application/json",
        maximum_bytes: int = 16 * 1024 * 1024,
        allow_precondition: bool = False,
    ) -> tuple[int, bytes]:
        if (
            _TOKEN.fullmatch(self.token) is None
            or not (
                url.startswith("https://pubsub.googleapis.com/v1/")
                or url.startswith("https://storage.googleapis.com/storage/v1/")
                or url.startswith("https://storage.googleapis.com/upload/storage/v1/")
            )
        ):
            raise ArchiveError("provider_request_invalid")
        headers = {"Authorization": "Bearer " + self.token, "Accept": "application/json"}
        if body is not None:
            headers["Content-Type"] = content_type
            headers["Content-Length"] = str(len(body))
        try:
            with build_opener(ProxyHandler({}), NoRedirects()).open(
                Request(url, data=body, headers=headers, method=method), timeout=30
            ) as response:
                raw = response.read(maximum_bytes + 1)
                status = response.status
        except HTTPError as exc:
            if allow_precondition and exc.code == 412:
                return 412, b""
            raise ArchiveError("provider_request_failed") from exc
        except OSError as exc:
            raise ArchiveError("provider_request_failed") from exc
        if len(raw) > maximum_bytes:
            raise ArchiveError("provider_response_too_large")
        return status, raw

    @staticmethod
    def _json(raw: bytes, reason: str) -> Any:
        try:
            return json.loads(raw or b"{}")
        except (ValueError, TypeError, UnicodeError) as exc:
            raise ArchiveError(reason) from exc

    def publisher_freeze_readback(self) -> Mapping[str, Any]:
        units = " ".join(shlex.quote(unit) for unit in PUBLISHER_UNITS)
        remote = (
            f"for u in {units}; do echo @@UNIT=$u; "
            "systemctl show --property=ActiveState --property=UnitFileState \"$u\"; "
            "done"
        )
        try:
            result = subprocess.run(
                [
                    self.gcloud, "compute", "ssh", INSTANCE,
                    "--project=" + PROJECT,
                    "--zone=" + ZONE,
                    "--tunnel-through-iap",
                    "--command=" + remote,
                    "--quiet",
                ],
                check=False,
                capture_output=True,
                text=True,
                timeout=60,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ArchiveError("publisher_freeze_readback_failed") from exc
        if result.returncode:
            raise ArchiveError("publisher_freeze_readback_failed")
        if len(result.stdout) > 4096:
            raise ArchiveError("publisher_freeze_readback_failed")
        rows: list[dict[str, str]] = []
        current: dict[str, str] | None = None
        for line in result.stdout.splitlines():
            if line.startswith("@@UNIT="):
                current = {"unit": line.removeprefix("@@UNIT=").strip()}
                rows.append(current)
            elif not line.strip():
                continue
            elif current is not None and "=" in line:
                key, item = line.split("=", 1)
                if key == "ActiveState" and "active_state" not in current:
                    current["active_state"] = item.strip()
                elif key == "UnitFileState" and "unit_file_state" not in current:
                    current["unit_file_state"] = item.strip()
                else:
                    raise ArchiveError("publisher_freeze_readback_invalid")
            else:
                raise ArchiveError("publisher_freeze_readback_invalid")
        return {"instance": INSTANCE, "units": rows}

    def bucket_metadata(self, bucket: str) -> Mapping[str, Any]:
        url = "https://storage.googleapis.com/storage/v1/b/" + quote(bucket, safe="")
        status, raw = self._request("GET", url, maximum_bytes=1_048_576)
        if status != 200:
            raise ArchiveError("archive_bucket_readback_failed")
        value = self._json(raw, "archive_bucket_readback_invalid")
        if not isinstance(value, Mapping):
            raise ArchiveError("archive_bucket_readback_invalid")
        return value

    def pull(self, subscription: str, maximum: int) -> list[Mapping[str, Any]]:
        if subscription not in SUBSCRIPTIONS or not 1 <= maximum <= 100:
            raise ArchiveError("pubsub_pull_scope_invalid")
        url = (
            f"https://pubsub.googleapis.com/v1/projects/{PROJECT}/subscriptions/"
            + quote(subscription, safe="")
            + ":pull"
        )
        body = canonical({"maxMessages": maximum, "returnImmediately": True})
        status, raw = self._request("POST", url, body=body, maximum_bytes=128 * 1024 * 1024)
        if status != 200:
            raise ArchiveError("pubsub_pull_failed")
        value = self._json(raw, "pubsub_pull_response_invalid")
        rows = value.get("receivedMessages", []) if isinstance(value, Mapping) else None
        if not isinstance(rows, list) or any(not isinstance(row, Mapping) for row in rows):
            raise ArchiveError("pubsub_pull_response_invalid")
        return list(rows)

    def put_if_absent(
        self,
        bucket: str,
        name: str,
        value: bytes,
        *,
        kms_key: str,
        metadata: Mapping[str, str],
    ) -> ObjectState:
        boundary = "aureon-" + hashlib.sha256(name.encode("utf-8")).hexdigest()
        object_meta = canonical({
            "name": name,
            "contentType": "application/json",
            "cacheControl": "no-store",
            "eventBasedHold": True,
            "crc32c": _crc32c(value),
            "metadata": dict(metadata),
        })
        body = (
            ("--" + boundary + "\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n").encode()
            + object_meta
            + ("\r\n--" + boundary + "\r\nContent-Type: application/json\r\n\r\n").encode()
            + value
            + ("\r\n--" + boundary + "--\r\n").encode()
        )
        query = urlencode({
            "uploadType": "multipart",
            "name": name,
            "ifGenerationMatch": "0",
            "kmsKeyName": kms_key,
        })
        url = (
            "https://storage.googleapis.com/upload/storage/v1/b/"
            + quote(bucket, safe="")
            + "/o?"
            + query
        )
        status, raw = self._request(
            "POST",
            url,
            body=body,
            content_type="multipart/related; boundary=" + boundary,
            maximum_bytes=1_048_576,
            allow_precondition=True,
        )
        if status == 412:
            current, _ = self._get_object(bucket, name, generation=None, maximum_bytes=0)
            return current
        if status != 200:
            raise ArchiveError("storage_upload_failed")
        value_meta = self._json(raw, "storage_upload_response_invalid")
        if not isinstance(value_meta, Mapping):
            raise ArchiveError("storage_upload_response_invalid")
        return _state(value_meta)

    def _get_object(
        self,
        bucket: str,
        name: str,
        *,
        generation: str | None,
        maximum_bytes: int,
    ) -> tuple[ObjectState, bytes]:
        base = (
            "https://storage.googleapis.com/storage/v1/b/"
            + quote(bucket, safe="")
            + "/o/"
            + quote(name, safe="")
        )
        generation_query = {"generation": generation} if generation else {}
        meta_url = base + ("?" + urlencode(generation_query) if generation_query else "")
        status, raw = self._request("GET", meta_url, maximum_bytes=1_048_576)
        if status != 200:
            raise ArchiveError("storage_readback_failed")
        meta = self._json(raw, "storage_object_metadata_invalid")
        if not isinstance(meta, Mapping):
            raise ArchiveError("storage_object_metadata_invalid")
        state = _state(meta)
        if maximum_bytes <= 0:
            return state, b""
        media_query = {"alt": "media", "generation": state.generation}
        status, body = self._request(
            "GET", base + "?" + urlencode(media_query), maximum_bytes=maximum_bytes
        )
        if status != 200:
            raise ArchiveError("storage_readback_failed")
        return state, body

    def read_object(
        self,
        bucket: str,
        name: str,
        generation: str,
        *,
        maximum_bytes: int,
    ) -> tuple[ObjectState, bytes]:
        if not generation.isdigit():
            raise ArchiveError("storage_generation_invalid")
        return self._get_object(
            bucket,
            name,
            generation=generation,
            maximum_bytes=maximum_bytes,
        )

    def list_objects(self, bucket: str, prefix: str) -> list[ObjectState]:
        result: list[ObjectState] = []
        token: str | None = None
        while True:
            params = {
                "prefix": prefix,
                "maxResults": "1000",
                "fields": (
                    "items(bucket,name,generation,size,kmsKeyName,eventBasedHold,"
                    "metadata,crc32c),nextPageToken"
                ),
            }
            if token:
                params["pageToken"] = token
            url = (
                "https://storage.googleapis.com/storage/v1/b/"
                + quote(bucket, safe="")
                + "/o?"
                + urlencode(params)
            )
            status, raw = self._request("GET", url, maximum_bytes=16 * 1024 * 1024)
            if status != 200:
                raise ArchiveError("storage_list_failed")
            value = self._json(raw, "storage_list_response_invalid")
            rows = value.get("items", []) if isinstance(value, Mapping) else None
            if (
                not isinstance(rows, list)
                or any(not isinstance(row, Mapping) for row in rows)
            ):
                raise ArchiveError("storage_list_response_invalid")
            result.extend(_state(row) for row in rows)
            if len(result) > 200_000:
                raise ArchiveError("storage_list_response_too_large")
            token = value.get("nextPageToken") if isinstance(value, Mapping) else None
            if token is None:
                break
            if not isinstance(token, str) or not token:
                raise ArchiveError("storage_list_response_invalid")
        return result

    def acknowledge(self, subscription: str, ack_ids: list[str]) -> None:
        if (
            subscription not in SUBSCRIPTIONS
            or not ack_ids
            or len(ack_ids) > 100
            or any(not isinstance(item, str) or not 1 <= len(item) <= 8192 for item in ack_ids)
        ):
            raise ArchiveError("pubsub_ack_scope_invalid")
        url = (
            f"https://pubsub.googleapis.com/v1/projects/{PROJECT}/subscriptions/"
            + quote(subscription, safe="")
            + ":acknowledge"
        )
        status, raw = self._request(
            "POST", url, body=canonical({"ackIds": ack_ids}), maximum_bytes=4096
        )
        if status != 200 or self._json(raw, "pubsub_ack_response_invalid") != {}:
            raise ArchiveError("pubsub_ack_failed")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", nargs="?", choices=("plan", "archive"), default="plan")
    parser.add_argument("--gcloud", default="gcloud")
    parser.add_argument("--contract-sha256", required=True)
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--bucket", required=True)
    parser.add_argument("--cmek-key", required=True)
    parser.add_argument("--prefix", default=DEFAULT_PREFIX)
    parser.add_argument("--batch-size", type=int, default=10)
    parser.add_argument("--max-total-messages", type=int, default=10_000)
    parser.add_argument("--max-total-bytes", type=int, default=1024 * 1024 * 1024)
    parser.add_argument("--max-runtime-seconds", type=int, default=3600)
    parser.add_argument("--empty-polls", type=int, default=3)
    parser.add_argument("--minimum-retention-seconds", type=int, default=604_800)
    parser.add_argument("--acknowledge-scope-sha256")
    parser.add_argument("--receipt", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        scope = archive_scope(
            contract_sha256=args.contract_sha256,
            source_revision=args.source_revision,
            bucket=args.bucket,
            kms_key=args.cmek_key,
            prefix=args.prefix,
            batch_size=args.batch_size,
            max_total_messages=args.max_total_messages,
            max_total_bytes=args.max_total_bytes,
            max_runtime_seconds=args.max_runtime_seconds,
            empty_polls=args.empty_polls,
            minimum_retention_seconds=args.minimum_retention_seconds,
        )
        scope_hash = sha256(canonical(scope))
        if args.command == "plan":
            print(json.dumps({
                "schema": SCOPE_SCHEMA,
                "scope_sha256": scope_hash,
                "project": PROJECT,
                "subscription_count": len(SUBSCRIPTIONS),
                "subscription_deletion": False,
                "order_execution": False,
            }, sort_keys=True))
            return 0
        if args.acknowledge_scope_sha256 != scope_hash:
            raise ArchiveError("exact_archive_scope_acknowledgement_required")
        if args.receipt is None or not args.receipt.is_absolute():
            raise ArchiveError("absolute_receipt_path_required")
        receipt = archive_backlogs(GcpProvider(gcloud=args.gcloud), scope=scope)
        write_receipt(args.receipt, receipt)
        print(json.dumps({
            "schema": RECEIPT_SCHEMA,
            "status": receipt["status"],
            "receipt_sha256": sha256(canonical(receipt)),
            "root_manifest_sha256": receipt["root_manifest"]["payload_sha256"],
            "acknowledged_this_run": receipt["acknowledged_this_run"],
            "subscription_deleted": False,
            "order_execution": False,
        }, sort_keys=True))
        return 0
    except (ArchiveError, CommissionError) as exc:
        print(str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
