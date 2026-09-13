"""Create a redacted Supabase Auth owner provider-readback receipt.

The administrator secret is read once from standard input, kept in memory, and
never printed or written. Only the exact user UUID, role, confirmation state,
domain-separated email commitment, revision, and contract hash reach disk.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, BinaryIO, Callable, Mapping
from urllib.error import HTTPError
from urllib.request import (
    HTTPRedirectHandler,
    ProxyHandler,
    Request,
    build_opener,
)

from authority_commission import CommissionError, canonical, sha256, write_receipt

SCHEMA = "aureon.supabase-owner-provider-readback.v1"
PROVIDER = "supabase_auth_admin"
EMAIL_COMMITMENT_DOMAIN = b"aureon-supabase-owner-email-v1\x00"
_PROJECT_REF = re.compile(r"[a-z0-9]{20}")
_UUID = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-"
    r"[89ab][0-9a-f]{3}-[0-9a-f]{12}"
)
_REVISION = re.compile(r"[0-9a-f]{40}")
_HEX64 = re.compile(r"[0-9a-f]{64}")
_SECRET = re.compile(r"[A-Za-z0-9._~-]{20,8192}")


class OwnerReadbackError(RuntimeError):
    """Stable provider-readback error without response or credential text."""


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise OwnerReadbackError("supabase_owner_redirect_denied")


def read_admin_secret(stream: BinaryIO) -> str:
    raw = stream.read(8193)
    if len(raw) > 8192:
        raise OwnerReadbackError("supabase_admin_secret_invalid")
    try:
        value = raw.decode("ascii").strip()
    except UnicodeError as exc:
        raise OwnerReadbackError("supabase_admin_secret_invalid") from exc
    if _SECRET.fullmatch(value) is None:
        raise OwnerReadbackError("supabase_admin_secret_invalid")
    return value


def provider_user(
    project_ref: str,
    subject: str,
    admin_secret: str,
) -> Mapping[str, Any]:
    if (
        _PROJECT_REF.fullmatch(project_ref) is None
        or _UUID.fullmatch(subject) is None
        or _SECRET.fullmatch(admin_secret) is None
    ):
        raise OwnerReadbackError("supabase_owner_request_invalid")
    url = (
        f"https://{project_ref}.supabase.co/auth/v1/admin/users/{subject}"
    )
    opener = build_opener(ProxyHandler({}), NoRedirects())
    request = Request(
        url,
        headers={
            "Authorization": "Bearer " + admin_secret,
            "apikey": admin_secret,
            "Accept": "application/json",
        },
        method="GET",
    )
    try:
        with opener.open(request, timeout=20) as response:
            if response.status != 200 or response.geturl() != url:
                raise OwnerReadbackError("supabase_owner_readback_failed")
            raw = response.read(131_073)
    except OwnerReadbackError:
        raise
    except (HTTPError, OSError) as exc:
        raise OwnerReadbackError("supabase_owner_readback_failed") from exc
    if len(raw) > 131_072:
        raise OwnerReadbackError("supabase_owner_response_too_large")
    try:
        value = json.loads(raw)
    except (ValueError, TypeError, UnicodeError) as exc:
        raise OwnerReadbackError("supabase_owner_response_invalid") from exc
    if not isinstance(value, Mapping):
        raise OwnerReadbackError("supabase_owner_response_invalid")
    return value


def email_commitment(value: str) -> str:
    if not isinstance(value, str) or len(value) > 320:
        raise OwnerReadbackError("supabase_owner_response_invalid")
    normalized = value.strip().casefold()
    if re.fullmatch(
        r"[a-z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-z0-9.-]+", normalized
    ) is None:
        raise OwnerReadbackError("supabase_owner_response_invalid")
    return hashlib.sha256(
        EMAIL_COMMITMENT_DOMAIN + normalized.encode("utf-8")
    ).hexdigest()


def make_receipt(
    *,
    project_ref: str,
    subject: str,
    source_revision: str,
    contract_sha256: str,
    admin_secret: str,
    reader: Callable[[str, str, str], Mapping[str, Any]] = provider_user,
    now: datetime | None = None,
) -> dict[str, Any]:
    if (
        _PROJECT_REF.fullmatch(project_ref or "") is None
        or _UUID.fullmatch(subject or "") is None
        or _REVISION.fullmatch(source_revision or "") is None
        or _HEX64.fullmatch(contract_sha256 or "") is None
    ):
        raise OwnerReadbackError("supabase_owner_request_invalid")
    value = reader(project_ref, subject, admin_secret)
    app_metadata = value.get("app_metadata")
    email = value.get("email")
    confirmed = value.get("email_confirmed_at")
    if (
        value.get("id") != subject
        or not isinstance(app_metadata, Mapping)
        or app_metadata.get("aureon_role") != "owner"
        or not isinstance(confirmed, str)
        or not confirmed
    ):
        raise OwnerReadbackError("supabase_owner_binding_invalid")
    try:
        confirmed_at = datetime.fromisoformat(
            confirmed.replace("Z", "+00:00")
        )
        if confirmed_at.tzinfo is None:
            raise ValueError("timezone_required")
    except (ValueError, TypeError, OverflowError) as exc:
        raise OwnerReadbackError("supabase_owner_binding_invalid") from exc
    observed = (now or datetime.now(UTC)).astimezone(UTC)
    if confirmed_at.astimezone(UTC) > observed:
        raise OwnerReadbackError("supabase_owner_binding_invalid")
    return {
        "schema": SCHEMA,
        "provider": PROVIDER,
        "project_ref": project_ref,
        "subject": subject,
        "app_metadata_role": "owner",
        "email_confirmed": True,
        "email_sha256": email_commitment(email),
        "recorded_at": observed.isoformat(),
        "source_revision": source_revision,
        "contract_sha256": contract_sha256,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-ref", required=True)
    parser.add_argument("--subject", required=True)
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--contract-sha256", required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        value = make_receipt(
            project_ref=args.project_ref,
            subject=args.subject,
            source_revision=args.source_revision,
            contract_sha256=args.contract_sha256,
            admin_secret=read_admin_secret(sys.stdin.buffer),
        )
        write_receipt(args.receipt, value)
        print(
            json.dumps(
                {
                    "schema": SCHEMA,
                    "receipt": str(args.receipt),
                    "receipt_sha256": sha256(canonical(value)),
                    "provider_readback_ok": True,
                    "secret_value_recorded": False,
                },
                sort_keys=True,
            )
        )
        return 0
    except (OwnerReadbackError, CommissionError) as exc:
        print(str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
