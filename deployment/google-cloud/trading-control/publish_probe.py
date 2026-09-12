"""Publish one validated no-mutation probe to the fixed Aureon intent topic."""
from __future__ import annotations

import argparse
import base64
import subprocess
from pathlib import Path

import requests

from contract import canonical_bytes
from make_probe import build_probe


TOPIC_URL = (
    "https://pubsub.googleapis.com/v1/projects/aureon-trading/"
    "topics/aureon-trade-intents-v1:publish"
)


def _access_token(gcloud: Path) -> str:
    resolved = gcloud.resolve(strict=True)
    if resolved.name.lower() not in {"gcloud", "gcloud.cmd", "gcloud.exe"} or not resolved.is_file():
        raise RuntimeError("gcloud_executable_invalid")
    result = subprocess.run(
        [str(resolved), "auth", "print-access-token"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
        timeout=15,
        text=True,
        encoding="ascii",
    )
    token = result.stdout.strip()
    if result.returncode != 0 or not 20 <= len(token) <= 8192 or any(char.isspace() for char in token):
        raise RuntimeError("gcloud_access_token_unavailable")
    return token


def publish_probe(*, gcloud: Path, event_sha256: str,
                  lease_expires_at_ms: int, revision: str) -> str:
    probe = build_probe(
        event_sha256=event_sha256,
        lease_expires_at_ms=lease_expires_at_ms,
        revision=revision,
    )
    wire = canonical_bytes(probe)
    token = _access_token(gcloud)
    response = requests.post(
        TOPIC_URL,
        headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
        json={"messages": [{
            "data": base64.b64encode(wire).decode("ascii"),
            "attributes": {"schema": probe["schema"]},
            "orderingKey": probe["intent_id"],
        }]},
        timeout=15,
    )
    token = ""
    if response.status_code != 200:
        raise RuntimeError("probe_publish_failed")
    try:
        value = response.json()
        ids = value["messageIds"]
    except (ValueError, KeyError, TypeError) as exc:
        raise RuntimeError("probe_publish_response_invalid") from exc
    if not isinstance(ids, list) or len(ids) != 1 or not isinstance(ids[0], str) or not ids[0]:
        raise RuntimeError("probe_publish_response_invalid")
    return ids[0]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gcloud", required=True, type=Path)
    parser.add_argument("--event-sha256", required=True)
    parser.add_argument("--lease-expires-at-ms", required=True, type=int)
    parser.add_argument("--revision", required=True)
    args = parser.parse_args()
    print(publish_probe(
        gcloud=args.gcloud,
        event_sha256=args.event_sha256,
        lease_expires_at_ms=args.lease_expires_at_ms,
        revision=args.revision,
    ))


if __name__ == "__main__":
    main()
