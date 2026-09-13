"""Create the redacted owner receipt without exposing a Supabase admin key.

The Supabase Management API token is read from Windows Credential Manager. The
project's single legacy ``service_role`` key is fetched into memory and passed
to the reviewed owner-readback program over an anonymous stdin pipe. Neither
credential is placed in argv, the environment, a temporary file, or stdout.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Mapping
from urllib.error import HTTPError
from urllib.request import (
    HTTPRedirectHandler,
    ProxyHandler,
    Request,
    build_opener,
)

PROJECT_REF = "siihxcwetdjdsrfdexmb"
CREDENTIAL_TARGET = "Supabase CLI:supabase"
_PROJECT_REF = re.compile(r"[a-z0-9]{20}")
_REVISION = re.compile(r"[0-9a-f]{40}")
_HEX64 = re.compile(r"[0-9a-f]{64}")
_SECRET = re.compile(r"[A-Za-z0-9._~-]{20,8192}")


class ReadbackBootstrapError(RuntimeError):
    """Stable error that never contains a credential or provider body."""


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ReadbackBootstrapError("supabase_management_redirect_denied")


def _decode_credential_blob(blob: object) -> str:
    if isinstance(blob, str):
        value = blob
    elif isinstance(blob, bytes):
        try:
            if blob.startswith((b"\xff\xfe", b"\xfe\xff")):
                value = blob.decode("utf-16").lstrip("\ufeff")
            else:
                value = blob.decode("utf-8")
        except UnicodeError as exc:
            raise ReadbackBootstrapError(
                "supabase_management_credential_invalid"
            ) from exc
    else:
        raise ReadbackBootstrapError("supabase_management_credential_invalid")
    value = value.rstrip("\x00\r\n")
    if _SECRET.fullmatch(value) is None:
        raise ReadbackBootstrapError("supabase_management_credential_invalid")
    return value


def read_windows_credential(target: str) -> str:
    if not isinstance(target, str) or not target or len(target) > 256:
        raise ReadbackBootstrapError("windows_credential_target_invalid")
    try:
        import win32cred  # type: ignore[import-not-found]

        row = win32cred.CredRead(target, win32cred.CRED_TYPE_GENERIC, 0)
    except (ImportError, OSError) as exc:
        raise ReadbackBootstrapError(
            "supabase_management_credential_unavailable"
        ) from exc
    if not isinstance(row, Mapping) or "CredentialBlob" not in row:
        raise ReadbackBootstrapError(
            "supabase_management_credential_unavailable"
        )
    return _decode_credential_blob(row["CredentialBlob"])


def fetch_service_role_key(
    project_ref: str,
    management_token: str,
    *,
    opener_factory: Callable[..., Any] = build_opener,
) -> str:
    if (
        _PROJECT_REF.fullmatch(project_ref or "") is None
        or _SECRET.fullmatch(management_token or "") is None
    ):
        raise ReadbackBootstrapError("supabase_management_request_invalid")
    url = (
        "https://api.supabase.com/v1/projects/"
        f"{project_ref}/api-keys?reveal=true"
    )
    request = Request(
        url,
        headers={
            "Authorization": "Bearer " + management_token,
            "Accept": "application/json",
        },
        method="GET",
    )
    opener = opener_factory(ProxyHandler({}), NoRedirects())
    try:
        with opener.open(request, timeout=20) as response:
            if response.status != 200 or response.geturl() != url:
                raise ReadbackBootstrapError(
                    "supabase_management_key_readback_failed"
                )
            raw = response.read(262_145)
    except ReadbackBootstrapError:
        raise
    except (HTTPError, OSError) as exc:
        raise ReadbackBootstrapError(
            "supabase_management_key_readback_failed"
        ) from exc
    if len(raw) > 262_144:
        raise ReadbackBootstrapError("supabase_management_response_too_large")
    try:
        value = json.loads(raw)
    except (ValueError, TypeError, UnicodeError) as exc:
        raise ReadbackBootstrapError(
            "supabase_management_response_invalid"
        ) from exc
    if not isinstance(value, list) or len(value) > 32:
        raise ReadbackBootstrapError("supabase_management_response_invalid")
    matches: list[str] = []
    for item in value:
        if not isinstance(item, Mapping):
            raise ReadbackBootstrapError(
                "supabase_management_response_invalid"
            )
        if item.get("name") == "service_role" and item.get("type") == "legacy":
            key = item.get("api_key")
            if not isinstance(key, str) or _SECRET.fullmatch(key) is None:
                raise ReadbackBootstrapError(
                    "supabase_service_role_key_invalid"
                )
            matches.append(key)
    if len(matches) != 1:
        raise ReadbackBootstrapError(
            "supabase_service_role_key_not_exactly_one"
        )
    return matches[0]


def _git_output(repo: Path, *args: str) -> bytes:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), *args],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=20,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise ReadbackBootstrapError("trusted_source_revision_invalid") from exc
    return result.stdout


def verify_committed_program(
    repo: Path,
    program: Path,
    source_revision: str,
) -> None:
    if _REVISION.fullmatch(source_revision or "") is None:
        raise ReadbackBootstrapError("trusted_source_revision_invalid")
    try:
        repo = repo.resolve(strict=True)
        program = program.resolve(strict=True)
        relative = program.relative_to(repo).as_posix()
    except (OSError, ValueError) as exc:
        raise ReadbackBootstrapError("owner_readback_program_invalid") from exc
    if program.is_symlink() or not program.is_file():
        raise ReadbackBootstrapError("owner_readback_program_invalid")
    head = _git_output(repo, "rev-parse", "HEAD").decode("ascii").strip()
    if head != source_revision:
        raise ReadbackBootstrapError("trusted_source_revision_mismatch")
    committed = _git_output(repo, "show", f"{source_revision}:{relative}")
    try:
        local = program.read_bytes()
    except OSError as exc:
        raise ReadbackBootstrapError("owner_readback_program_invalid") from exc
    if committed != local:
        raise ReadbackBootstrapError("owner_readback_program_not_committed")


def _minimal_child_environment() -> dict[str, str]:
    allowed = ("SystemRoot", "WINDIR", "PATH", "PATHEXT", "TEMP", "TMP")
    return {name: os.environ[name] for name in allowed if name in os.environ}


def invoke_owner_readback(
    *,
    program: Path,
    project_ref: str,
    subject: str,
    source_revision: str,
    contract_sha256: str,
    receipt: Path,
    admin_secret: str,
) -> int:
    if (
        _PROJECT_REF.fullmatch(project_ref or "") is None
        or _REVISION.fullmatch(source_revision or "") is None
        or _HEX64.fullmatch(contract_sha256 or "") is None
        or _SECRET.fullmatch(admin_secret or "") is None
        or not receipt.is_absolute()
    ):
        raise ReadbackBootstrapError("owner_readback_invocation_invalid")
    argv = [
        sys.executable,
        "-E",
        "-s",
        "-S",
        str(program),
        "--project-ref",
        project_ref,
        "--subject",
        subject,
        "--source-revision",
        source_revision,
        "--contract-sha256",
        contract_sha256,
        "--receipt",
        str(receipt),
    ]
    try:
        completed = subprocess.run(
            argv,
            input=(admin_secret + "\n").encode("ascii"),
            stdout=None,
            stderr=None,
            cwd=program.parent,
            env=_minimal_child_environment(),
            close_fds=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise ReadbackBootstrapError("owner_readback_invocation_failed") from exc
    return completed.returncode


def main(argv: list[str] | None = None) -> int:
    root = Path(__file__).resolve().parents[3]
    default_program = (
        root
        / "deployment"
        / "google-cloud"
        / "trading-control"
        / "supabase_owner_readback.py"
    )
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-ref", default=PROJECT_REF)
    parser.add_argument("--subject", required=True)
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--contract-sha256", required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument(
        "--windows-credential-target", default=CREDENTIAL_TARGET
    )
    parser.add_argument("--owner-readback-program", type=Path, default=default_program)
    args = parser.parse_args(argv)
    try:
        program = args.owner_readback_program.resolve(strict=True)
        verify_committed_program(root, program, args.source_revision)
        management_token = read_windows_credential(
            args.windows_credential_target
        )
        admin_secret = fetch_service_role_key(
            args.project_ref, management_token
        )
        return invoke_owner_readback(
            program=program,
            project_ref=args.project_ref,
            subject=args.subject,
            source_revision=args.source_revision,
            contract_sha256=args.contract_sha256,
            receipt=args.receipt,
            admin_secret=admin_secret,
        )
    except ReadbackBootstrapError as exc:
        print(str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
