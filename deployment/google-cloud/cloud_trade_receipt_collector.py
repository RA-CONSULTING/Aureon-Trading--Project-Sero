"""Verify and durably collect terminal receipts from the cloud authority chain."""
from __future__ import annotations

import argparse
import base64
import binascii
import json
import os
import re
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Mapping
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


ROOT = Path(__file__).resolve().parent
CONTRACT_ROOT = ROOT / "trading-control"
if str(CONTRACT_ROOT) not in sys.path:
    sys.path.insert(0, str(CONTRACT_ROOT))

from contract import (  # noqa: E402
    DISPATCH_SCHEMA,
    EXECUTOR_SCHEMA,
    RECEIPT_SCHEMA,
    REVIEW_SCHEMA,
    canonical_bytes,
    digest,
    unsigned_stage,
    validate_intent,
    validate_stage,
)


PROJECT = "aureon-trading"
PROJECT_NUMBER = "4435775023"
SUBSCRIPTION = "aureon-trade-terminal-readback-v1"
METADATA = "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token"
PUBSUB = (
    f"https://pubsub.googleapis.com/v1/projects/{PROJECT}/subscriptions/{SUBSCRIPTION}"
)
KEY_PREFIX = (
    f"projects/{PROJECT}/locations/europe-west1/keyRings/aureon-trading-prod/cryptoKeys"
)
KEYS = {
    "review": f"{KEY_PREFIX}/aureon-review-signing/cryptoKeyVersions/1",
    "dispatch": f"{KEY_PREFIX}/aureon-dispatch-signing/cryptoKeyVersions/1",
    "executor": f"{KEY_PREFIX}/aureon-executor-signing/cryptoKeyVersions/1",
    "receipt": f"{KEY_PREFIX}/aureon-receipt-signing/cryptoKeyVersions/1",
}
DEFAULT_OUTPUT = Path("/srv/aureon/cache/trading-control/latest-terminal-receipt.json")
DEFAULT_LIVE_OUTPUT = Path("/srv/aureon/cache/trading-control/latest-live-terminal-receipt.json")
_MESSAGE_ID = re.compile(r"[0-9]{1,64}")
_PROVIDER_ID = re.compile(r"[A-Za-z0-9._:/-]{1,256}")


class CollectorError(RuntimeError):
    """Stable receipt collector failure."""


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise CollectorError("cloud_redirect_denied")


def _http(url: str, *, method: str = "GET", headers: Mapping[str, str] | None = None,
          body: bytes | None = None, timeout: float = 30) -> bytes:
    opener = build_opener(ProxyHandler({}), NoRedirects())
    try:
        with opener.open(Request(url, data=body, headers=dict(headers or {}), method=method),
                         timeout=timeout) as response:
            if response.status < 200 or response.status >= 300:
                raise CollectorError("cloud_http_status_invalid")
            data = response.read(1_048_577)
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise CollectorError("cloud_http_request_failed") from exc
    if len(data) > 1_048_576:
        raise CollectorError("cloud_http_response_too_large")
    return data


def access_token(reader=_http) -> str:
    raw = reader(METADATA, headers={"Metadata-Flavor": "Google"}, timeout=5)
    try:
        value = json.loads(raw)
    except (ValueError, TypeError, UnicodeError) as exc:
        raise CollectorError("metadata_token_response_invalid") from exc
    token = value.get("access_token") if isinstance(value, dict) else None
    expires = value.get("expires_in") if isinstance(value, dict) else None
    if (not isinstance(token, str) or not 20 <= len(token) <= 8192
            or type(expires) is not int or expires < 30):
        raise CollectorError("metadata_token_response_invalid")
    return token


def _cloud_json(raw: bytes, code: str) -> dict[str, Any]:
    try:
        value = json.loads(raw)
    except (ValueError, TypeError, UnicodeError) as exc:
        raise CollectorError(code) from exc
    if not isinstance(value, dict):
        raise CollectorError(code)
    return value


def _verify_signature(stage: Mapping[str, Any], expected_key: str, *, token: str,
                      reader=_http) -> None:
    if stage.get("key_version") != expected_key:
        raise CollectorError("terminal_key_pin_mismatch")
    raw = reader(
        "https://cloudkms.googleapis.com/v1/" + expected_key + "/publicKey",
        headers={"Authorization": "Bearer " + token, "Accept": "application/json"},
        timeout=8,
    )
    value = _cloud_json(raw, "kms_public_key_response_invalid")
    if (value.get("name") != expected_key or value.get("algorithm") != "EC_SIGN_ED25519"
            or not isinstance(value.get("pem"), str)):
        raise CollectorError("kms_public_key_response_invalid")
    try:
        public = serialization.load_pem_public_key(value["pem"].encode("ascii"))
        signature = base64.b64decode(str(stage.get("signature") or ""), validate=True)
    except (ValueError, TypeError, UnicodeError, binascii.Error) as exc:
        raise CollectorError("terminal_signature_invalid") from exc
    if not isinstance(public, Ed25519PublicKey) or len(signature) != 64:
        raise CollectorError("terminal_signature_invalid")
    try:
        public.verify(signature, canonical_bytes(unsigned_stage(stage)))
    except InvalidSignature as exc:
        raise CollectorError("terminal_signature_invalid") from exc


def verify_terminal_receipt(receipt: Mapping[str, Any], *, token: str,
                            now_ms: int | None = None, reader=_http) -> dict[str, Any]:
    current = int(time.time() * 1000) if now_ms is None else int(now_ms)
    terminal = validate_stage(receipt, schema=RECEIPT_SCHEMA, payload_key="executor")
    _verify_signature(terminal, KEYS["receipt"], token=token, reader=reader)
    executor = validate_stage(terminal["executor"], schema=EXECUTOR_SCHEMA, payload_key="result")
    _verify_signature(executor, KEYS["executor"], token=token, reader=reader)
    result = executor["result"]
    if not isinstance(result, Mapping) or not isinstance(result.get("dispatch"), Mapping):
        raise CollectorError("terminal_executor_result_invalid")
    dispatch = validate_stage(result["dispatch"], schema=DISPATCH_SCHEMA, payload_key="review")
    _verify_signature(dispatch, KEYS["dispatch"], token=token, reader=reader)
    review = validate_stage(dispatch["review"], schema=REVIEW_SCHEMA, payload_key="intent")
    _verify_signature(review, KEYS["review"], token=token, reader=reader)
    untrusted_intent = review["intent"]
    created_at = untrusted_intent.get("created_at_ms") if isinstance(untrusted_intent, Mapping) else None
    if type(created_at) is not int or created_at > current + 5_000:
        raise CollectorError("terminal_intent_time_invalid")
    # A receipt remains verifiable after its short command lease expires.  Use
    # the signed creation time for shape/lifetime validation, then constrain all
    # signed stage times to that same lease below.
    intent = validate_intent(
        untrusted_intent, now_ms=created_at, max_order_usd=5,
        live_release=bool(isinstance(untrusted_intent, Mapping) and untrusted_intent.get("kind") == "order"),
    )
    outcome = result.get("outcome")
    if not isinstance(outcome, Mapping):
        raise CollectorError("terminal_outcome_invalid")
    is_probe = intent["kind"] == "control_plane_probe"
    if is_probe:
        if (intent["dry_run"] is not True
                or outcome.get("schema") != "aureon.cloud-trade-probe-result.v1"
                or outcome.get("status") != "probe_passed"
                or outcome.get("provider_mutation_attempted") is not False
                or outcome.get("orders_attempted") != 0
                or outcome.get("orders_submitted") != 0):
            raise CollectorError("terminal_probe_outcome_invalid")
        capabilities = outcome.get("executor_capabilities")
        if (not isinstance(capabilities, Mapping)
                or set(capabilities) != {
                    "live_execution_release", "durable_budget_ledger",
                    "order_adapter_ready", "live_result_binding_ready",
                }
                or any(type(value) is not bool for value in capabilities.values())):
            raise CollectorError("terminal_executor_capabilities_invalid")
    else:
        status = outcome.get("status")
        valid_live = (
            intent["dry_run"] is False
            and outcome.get("schema") == "aureon.cloud-trade-live-result.v1"
            and outcome.get("intent_id") == intent["intent_id"]
            and outcome.get("dispatch_sha256") == digest(dispatch)
            and status in {"provider_observed", "rejected", "uncertain"}
            and ((status == "provider_observed"
                  and outcome.get("provider_mutation_attempted") is True
                  and outcome.get("orders_attempted") == 1
                  and outcome.get("orders_submitted") == 1
                  and isinstance(outcome.get("provider_order_id"), str)
                  and isinstance(outcome.get("provider_client_order_id"), str)
                  and _PROVIDER_ID.fullmatch(outcome["provider_order_id"]) is not None
                  and _PROVIDER_ID.fullmatch(outcome["provider_client_order_id"]) is not None
                  and isinstance(outcome.get("provider_readback_sha256"), str)
                  and re.fullmatch(r"[0-9a-f]{64}", outcome["provider_readback_sha256"]) is not None)
                 or (status == "rejected"
                     and outcome.get("provider_mutation_attempted") is False
                     and outcome.get("orders_attempted") == 0
                     and outcome.get("orders_submitted") == 0)
                 or (status == "uncertain"
                     and outcome.get("provider_mutation_attempted") is True
                     and outcome.get("orders_attempted") == 1
                     and outcome.get("orders_submitted") is None))
        )
        if not valid_live:
            raise CollectorError("terminal_live_outcome_invalid")
        capabilities = None
    provider_readback = outcome.get("provider_readback") if is_probe else None
    provider_summary = None
    if provider_readback is not None:
        providers = provider_readback.get("providers") if isinstance(provider_readback, Mapping) else None
        if (not isinstance(provider_readback, Mapping)
                or provider_readback.get("schema") != "aureon.cloud-trade-provider-readback.v1"
                or provider_readback.get("provider_count") != 4
                or provider_readback.get("all_authenticated") is not True
                or provider_readback.get("provider_mutation_attempted") is not False
                or not isinstance(providers, Mapping)
                or set(providers) != {"alpaca", "binance", "capital", "kraken"}
                or any(not isinstance(row, Mapping) or row.get("venue") != venue
                       or row.get("authenticated") is not True
                       or not isinstance(row.get("account_binding_sha256"), str)
                       or not re.fullmatch(r"[0-9a-f]{64}", row["account_binding_sha256"])
                       for venue, row in providers.items())
                or provider_readback.get("readback_sha256") != digest(providers)):
            raise CollectorError("terminal_provider_readback_invalid")
        provider_summary = {
            "provider_count": 4, "all_authenticated": True,
            "readback_sha256": provider_readback["readback_sha256"],
            "providers": {
                venue: {"authenticated": True, "account_binding_sha256": row["account_binding_sha256"]}
                for venue, row in providers.items()
            },
        }
    if not (
        review["intent_id"] == dispatch["intent_id"] == executor["intent_id"]
        == terminal["intent_id"] == intent["intent_id"]
        and review["prior_sha256"] == digest(intent)
        and dispatch["prior_sha256"] == digest(review)
        and executor["prior_sha256"] == digest(dispatch)
        and terminal["prior_sha256"] == digest(executor)
        and outcome.get("dispatch_sha256") == digest(dispatch)
        and intent["created_at_ms"] <= review["signed_at_ms"] <= intent["expires_at_ms"]
        and intent["created_at_ms"] <= dispatch["signed_at_ms"] <= intent["expires_at_ms"]
        and intent["created_at_ms"] <= executor["signed_at_ms"] <= intent["expires_at_ms"]
        and intent["created_at_ms"] <= terminal["signed_at_ms"] <= intent["expires_at_ms"]
    ):
        raise CollectorError("terminal_chain_join_invalid")
    return {
        "intent_id": intent["intent_id"],
        "intent_created_at_ms": intent["created_at_ms"],
        "receipt_sha256": digest(terminal),
        "stage_ids": {
            "review": review["stage_id"], "dispatch": dispatch["stage_id"],
            "executor": executor["stage_id"], "receipt": terminal["stage_id"],
        },
        "authority_ids": {
            "review": review["authority_id"], "dispatch": dispatch["authority_id"],
            "executor": executor["authority_id"], "receipt": terminal["authority_id"],
        },
        "key_versions": dict(KEYS),
        "provider_mutation_attempted": outcome["provider_mutation_attempted"],
        "orders_attempted": outcome["orders_attempted"],
        "orders_submitted": outcome["orders_submitted"],
        "dry_run": bool(intent["dry_run"]),
        "chain_verified": True,
        "outcome_status": outcome["status"],
        "venue": intent["order"]["venue"] if intent["order"] else None,
        "provider_order_id": outcome.get("provider_order_id"),
        "provider_client_order_id": outcome.get("provider_client_order_id"),
        "provider_status": outcome.get("provider_status"),
        "provider_readback_sha256": outcome.get("provider_readback_sha256"),
        "executor_capabilities": dict(capabilities) if isinstance(capabilities, Mapping) else None,
        "provider_readback": provider_summary,
    }


def _durable_write(path: Path, value: Mapping[str, Any]) -> None:
    if not path.is_absolute() or path.exists() and path.is_symlink():
        raise CollectorError("receipt_output_path_invalid")
    path.parent.mkdir(parents=True, exist_ok=True)
    parent = path.parent.resolve(strict=True)
    if path.resolve().parent != parent:
        raise CollectorError("receipt_output_path_invalid")
    data = json.dumps(value, sort_keys=True, indent=2, allow_nan=False).encode() + b"\n"
    handle, temporary = tempfile.mkstemp(prefix=".receipt-", dir=parent)
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
        if os.name == "posix":
            directory = os.open(parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def pull_once(*, output: Path = DEFAULT_OUTPUT, reader=_http,
              current_time=time.time) -> bool:
    token = access_token(reader)
    headers = {"Authorization": "Bearer " + token, "Content-Type": "application/json"}
    pulled = _cloud_json(reader(
        PUBSUB + ":pull", method="POST", headers=headers,
        body=b'{"maxMessages":1}', timeout=30,
    ), "pubsub_pull_response_invalid")
    rows = pulled.get("receivedMessages", [])
    if rows == []:
        return False
    if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], Mapping):
        raise CollectorError("pubsub_pull_response_invalid")
    row = rows[0]
    message = row.get("message")
    ack_id = row.get("ackId")
    if not isinstance(message, Mapping) or not isinstance(ack_id, str) or not ack_id:
        raise CollectorError("pubsub_pull_response_invalid")
    message_id = message.get("messageId")
    encoded = message.get("data")
    if not isinstance(message_id, str) or not _MESSAGE_ID.fullmatch(message_id):
        raise CollectorError("pubsub_message_id_invalid")
    if not isinstance(encoded, str) or not 0 < len(encoded) <= 1_000_000:
        raise CollectorError("pubsub_message_data_invalid")
    try:
        wire = base64.b64decode(encoded, validate=True)
        receipt = json.loads(wire)
    except (ValueError, TypeError, UnicodeError, binascii.Error) as exc:
        raise CollectorError("pubsub_message_data_invalid") from exc
    if not isinstance(receipt, dict) or canonical_bytes(receipt) != wire:
        raise CollectorError("pubsub_terminal_receipt_not_canonical")
    summary = verify_terminal_receipt(
        receipt, token=token, now_ms=int(float(current_time()) * 1000), reader=reader,
    )
    stored = {
        "schema": "aureon.cloud-trade-terminal-readback.v1",
        "received_at": float(current_time()),
        "pubsub_message_id": message_id,
        "receipt": summary,
        "production_ready": False,
        "release_authority": False,
        "mutation_authority": False,
    }
    target = DEFAULT_LIVE_OUTPUT if output == DEFAULT_OUTPUT and summary["dry_run"] is False else output
    _durable_write(target, stored)
    reader(
        PUBSUB + ":acknowledge", method="POST", headers=headers,
        body=json.dumps({"ackIds": [ack_id]}, separators=(",", ":")).encode(), timeout=8,
    )
    return True


def run(*, output: Path = DEFAULT_OUTPUT) -> None:
    while True:
        try:
            if not pull_once(output=output):
                time.sleep(1)
        except CollectorError as exc:
            print(str(exc), file=sys.stderr, flush=True)
            time.sleep(5)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    if args.once:
        print(json.dumps({"collected": pull_once(output=args.output)}))
    else:
        run(output=args.output)


if __name__ == "__main__":
    main()
