"""Plan and build Aureon's two commit-bound container images.

``plan`` is the default and performs no provider mutation. ``build`` requires
the exact plan hash, submits minimal temporary contexts, resolves both Artifact
Registry digests and writes a redacted receipt. The public certificate is
verification material; the bridge private key is never accepted or copied.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import hashlib
import ipaddress
import json
from pathlib import Path
import re
import subprocess
import tempfile
from typing import Any, Mapping, Protocol

from cryptography import x509
from cryptography.hazmat.primitives.serialization import Encoding

from authority_commission import canonical, sha256, write_receipt


PROJECT = "aureon-trading"
REGION = "europe-west1"
SCHEMA = "aureon.gcp.immutable-image-build-plan.v1"
RECEIPT_SCHEMA = "aureon.gcp.immutable-image-build-receipt.v1"
CERTIFICATE_RECEIPT_SCHEMA = (
    "aureon.gcp.vm-public-bridge-certificate-receipt.v1"
)
AUTHORITY_REPOSITORY = (
    "europe-west1-docker.pkg.dev/aureon-trading/aureon-web/"
    "aureon-trading-authority"
)
PUBLIC_REPOSITORY = (
    "europe-west1-docker.pkg.dev/aureon-trading/aureon-web/"
    "aureon-public-entry"
)
AUTHORITY_FILES = (
    "Dockerfile",
    "requirements.txt",
    "contract.py",
    "service.py",
    "firestore_ledger.py",
    "provider_boundary.py",
    "live_executor.py",
    "cloud_state.py",
    "release_gate.py",
    "release_controller.py",
)
PUBLIC_FILES = ("Dockerfile", "requirements.txt", "public_entry.py")
_REVISION = re.compile(r"[0-9a-f]{40}")
_HEX64 = re.compile(r"[0-9a-f]{64}")
_BUILD_ID = re.compile(r"[A-Za-z0-9_-]{8,128}")


class ImageBuildError(RuntimeError):
    """Stable build failure without provider response content."""


class Runner(Protocol):
    def build(self, context: Path, tag: str) -> str: ...
    def digest(self, build_id: str, tag: str) -> str: ...


class Gcloud:
    def __init__(self, executable: str):
        self.executable = executable

    def build(self, context: Path, tag: str) -> str:
        try:
            result = subprocess.run(
                [
                    self.executable,
                    "builds",
                    "submit",
                    str(context),
                    "--tag=" + tag,
                    "--project=" + PROJECT,
                    "--region=" + REGION,
                    "--no-cache",
                    "--format=json",
                    "--quiet",
                ],
                check=False,
                capture_output=True,
                text=True,
                timeout=3600,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ImageBuildError("cloud_build_failed") from exc
        if result.returncode:
            raise ImageBuildError("cloud_build_failed")
        try:
            value = json.loads(result.stdout)
        except (ValueError, TypeError, UnicodeError) as exc:
            raise ImageBuildError("cloud_build_readback_invalid") from exc
        build_id = value.get("id") if isinstance(value, Mapping) else None
        status = value.get("status") if isinstance(value, Mapping) else None
        if _BUILD_ID.fullmatch(str(build_id or "")) is None or status != "SUCCESS":
            raise ImageBuildError("cloud_build_readback_invalid")
        return str(build_id)

    def digest(self, build_id: str, tag: str) -> str:
        if _BUILD_ID.fullmatch(build_id or "") is None:
            raise ImageBuildError("artifact_digest_readback_failed")
        try:
            result = subprocess.run(
                [
                    self.executable,
                    "builds",
                    "describe",
                    build_id,
                    "--project=" + PROJECT,
                    "--region=" + REGION,
                    "--format=json",
                    "--quiet",
                ],
                check=False,
                capture_output=True,
                text=True,
                timeout=60,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ImageBuildError("artifact_digest_readback_failed") from exc
        if result.returncode:
            raise ImageBuildError("artifact_digest_readback_failed")
        try:
            value = json.loads(result.stdout)
        except (ValueError, TypeError, UnicodeError) as exc:
            raise ImageBuildError("artifact_digest_readback_failed") from exc
        provider_results = value.get("results") if isinstance(value, Mapping) else None
        built_images = (
            provider_results.get("images")
            if isinstance(provider_results, Mapping)
            else None
        )
        if (
            not isinstance(value, Mapping)
            or value.get("id") != build_id
            or value.get("status") != "SUCCESS"
            or not isinstance(built_images, list)
            or len(built_images) != 1
            or not isinstance(built_images[0], Mapping)
            or built_images[0].get("name") != tag
        ):
            raise ImageBuildError("artifact_digest_readback_failed")
        digest = built_images[0].get("digest")
        if re.fullmatch(r"sha256:[0-9a-f]{64}", str(digest or "")) is None:
            raise ImageBuildError("artifact_digest_readback_failed")
        return str(digest)


def _git(source: Path, *args: str) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(source), *args],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ImageBuildError("source_git_readback_failed") from exc
    if result.returncode:
        raise ImageBuildError("source_git_readback_failed")
    return result.stdout.strip()


def bind_source(source: Path, revision: str) -> str:
    if (
        not source.is_absolute()
        or source.is_symlink()
        or not source.is_dir()
        or _REVISION.fullmatch(revision or "") is None
    ):
        raise ImageBuildError("frozen_source_invalid")
    if Path(_git(source, "rev-parse", "--show-toplevel")).resolve() != source.resolve():
        raise ImageBuildError("source_must_be_checkout_root")
    if _git(source, "rev-parse", "HEAD") != revision:
        raise ImageBuildError("source_revision_mismatch")
    if _git(source, "status", "--porcelain=v1", "--untracked-files=no"):
        raise ImageBuildError("source_checkout_not_clean")
    tree = _git(source, "rev-parse", "HEAD^{tree}")
    if _REVISION.fullmatch(tree) is None:
        raise ImageBuildError("source_git_readback_failed")
    return tree


def _git_blob(source: Path, revision: str, relative: str) -> bytes:
    """Read exact committed bytes so image inputs ignore checkout EOL policy."""

    try:
        result = subprocess.run(
            ["git", "-C", str(source), "cat-file", "blob", f"{revision}:{relative}"],
            check=False,
            capture_output=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ImageBuildError("committed_source_bytes_unavailable") from exc
    if result.returncode or len(result.stdout) > 32 * 1024 * 1024:
        raise ImageBuildError("committed_source_bytes_unavailable")
    return result.stdout


def _read(path: Path, maximum: int = 32 * 1024 * 1024) -> bytes:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > maximum:
        raise ImageBuildError("build_context_file_invalid")
    return path.read_bytes()


def validate_certificate(
    certificate: Path,
    receipt_path: Path,
    receipt_acknowledgement: str,
    revision: str,
) -> tuple[bytes, str, dict[str, Any]]:
    if (
        not certificate.is_absolute()
        or not receipt_path.is_absolute()
        or _HEX64.fullmatch(receipt_acknowledgement or "") is None
    ):
        raise ImageBuildError("bridge_certificate_receipt_required")
    raw_receipt = _read(receipt_path, 1024 * 1024)
    if hashlib.sha256(raw_receipt).hexdigest() != receipt_acknowledgement:
        raise ImageBuildError("bridge_certificate_receipt_hash_mismatch")
    try:
        receipt = json.loads(raw_receipt)
    except (ValueError, TypeError, UnicodeError) as exc:
        raise ImageBuildError("bridge_certificate_receipt_invalid") from exc
    required = {
        "schema": CERTIFICATE_RECEIPT_SCHEMA,
        "status": "passed",
        "project": PROJECT,
        "zone": "europe-west1-b",
        "instance": "aureon-sero-20260906",
        "source_revision": revision,
        "certificate_path": "/etc/aureon-public/bridge-cert.pem",
        "algorithm": "x509-der-sha256",
        "private_key_included": False,
        "secret_values_recorded": False,
        "required_ip_sans": ["10.40.0.2"],
        "minimum_remaining_validity_seconds": 86_400,
    }
    if (
        not isinstance(receipt, Mapping)
        or set(receipt)
        != {
            *required,
            "recorded_at",
            "certificate_sha256",
            "not_before",
            "not_after",
        }
        or any(receipt.get(key) != value for key, value in required.items())
    ):
        raise ImageBuildError("bridge_certificate_receipt_invalid")
    pem = _read(certificate, 64 * 1024)
    if b"PRIVATE KEY" in pem:
        raise ImageBuildError("private_key_material_forbidden")
    try:
        parsed = x509.load_pem_x509_certificate(pem)
        der = parsed.public_bytes(Encoding.DER)
        not_before = parsed.not_valid_before_utc.astimezone(UTC)
        not_after = parsed.not_valid_after_utc.astimezone(UTC)
        ip_sans = set(
            parsed.extensions.get_extension_for_class(
                x509.SubjectAlternativeName
            ).value.get_values_for_type(x509.IPAddress)
        )
        recorded_at = datetime.fromisoformat(
            str(receipt["recorded_at"]).replace("Z", "+00:00")
        ).astimezone(UTC)
        receipt_not_before = datetime.fromisoformat(
            str(receipt["not_before"]).replace("Z", "+00:00")
        ).astimezone(UTC)
        receipt_not_after = datetime.fromisoformat(
            str(receipt["not_after"]).replace("Z", "+00:00")
        ).astimezone(UTC)
    except (
        KeyError,
        TypeError,
        UnicodeError,
        ValueError,
        x509.ExtensionNotFound,
    ) as exc:
        raise ImageBuildError("bridge_certificate_invalid") from exc
    current = datetime.now(UTC)
    expected_ip_sans = {ipaddress.ip_address("10.40.0.2")}
    if ip_sans != expected_ip_sans:
        raise ImageBuildError("bridge_certificate_ip_san_invalid")
    if (
        receipt_not_before != not_before
        or receipt_not_after != not_after
        or recorded_at < not_before
        or recorded_at > not_after
        or recorded_at > current
        or (current - recorded_at).total_seconds() > 21_600
        or current < not_before
        or current > not_after
    ):
        raise ImageBuildError("bridge_certificate_not_current")
    if (not_after - current).total_seconds() < 86_400:
        raise ImageBuildError(
            "bridge_certificate_remaining_validity_insufficient"
        )
    fingerprint = hashlib.sha256(der).hexdigest()
    if receipt.get("certificate_sha256") != fingerprint:
        raise ImageBuildError("bridge_certificate_fingerprint_mismatch")
    evidence = {
        "receipt_sha256": receipt_acknowledgement,
        "fingerprint_sha256": fingerprint,
        "required_ip_sans": list(receipt["required_ip_sans"]),
        "not_before": receipt["not_before"],
        "not_after": receipt["not_after"],
        "minimum_remaining_validity_seconds": receipt[
            "minimum_remaining_validity_seconds"
        ],
    }
    return pem, fingerprint, evidence


def _context_rows(
    source: Path,
    revision: str,
    prefix: str,
    files: tuple[str, ...],
) -> list[dict[str, Any]]:
    rows = []
    for name in files:
        raw = _git_blob(source, revision, prefix + name)
        rows.append(
            {"path": name, "sha256": hashlib.sha256(raw).hexdigest(), "size": len(raw)}
        )
    return rows


def build_plan(
    source: Path,
    revision: str,
    certificate: Path,
    certificate_receipt: Path,
    certificate_receipt_sha256: str,
) -> tuple[dict[str, Any], bytes]:
    tree = bind_source(source, revision)
    pem, fingerprint, certificate_evidence = validate_certificate(
        certificate,
        certificate_receipt,
        certificate_receipt_sha256,
        revision,
    )
    prefixes = {
        "authority": "deployment/google-cloud/trading-control/",
        "public_entry": "deployment/google-cloud/public-entry/",
    }
    image_rows = []
    for name, repository, files in (
        ("authority", AUTHORITY_REPOSITORY, AUTHORITY_FILES),
        ("public_entry", PUBLIC_REPOSITORY, PUBLIC_FILES),
    ):
        rows = _context_rows(source, revision, prefixes[name], files)
        if name == "public_entry":
            rows.append(
                {
                    "path": "bridge-cert.pem",
                    "sha256": hashlib.sha256(pem).hexdigest(),
                    "size": len(pem),
                }
            )
        image_rows.append(
            {
                "name": name,
                "repository": repository,
                "tag": repository + ":" + revision,
                "context_files": rows,
                "context_sha256": sha256(canonical(rows)),
            }
        )
    return (
        {
            "schema": SCHEMA,
            "project": PROJECT,
            "region": REGION,
            "source_revision": revision,
            "source_tree": tree,
            "certificate_receipt_sha256": certificate_receipt_sha256,
            "certificate_fingerprint_sha256": fingerprint,
            "certificate": certificate_evidence,
            "images": image_rows,
            "immutable_digest_readback_required": True,
            "secret_values_recorded": False,
            "release_authority": False,
            "mutation_authority": False,
        },
        pem,
    )


def _load_plan(path: Path | None, expected: Mapping[str, Any], ack: str | None) -> str:
    if path is None or not path.is_absolute() or not path.is_file() or path.is_symlink():
        raise ImageBuildError("absolute_build_plan_required")
    try:
        value = json.loads(path.read_bytes())
    except (OSError, ValueError, TypeError, UnicodeError) as exc:
        raise ImageBuildError("build_plan_invalid") from exc
    if value != expected:
        raise ImageBuildError("build_plan_binding_invalid")
    expected_hash = sha256(canonical(value))
    if ack != expected_hash:
        raise ImageBuildError("exact_build_plan_acknowledgement_required")
    return expected_hash


def _materialize_context(
    source: Path,
    revision: str,
    prefix: str,
    destination: Path,
    names: tuple[str, ...],
    certificate: bytes | None = None,
) -> None:
    destination.mkdir(mode=0o700)
    for name in names:
        (destination / name).write_bytes(
            _git_blob(source, revision, prefix + name)
        )
    if certificate is not None:
        (destination / "bridge-cert.pem").write_bytes(certificate)


def execute(
    source: Path,
    plan: Mapping[str, Any],
    certificate: bytes,
    runner: Runner,
) -> list[dict[str, str]]:
    prefixes = {
        "authority": "deployment/google-cloud/trading-control/",
        "public_entry": "deployment/google-cloud/public-entry/",
    }
    file_sets = {"authority": AUTHORITY_FILES, "public_entry": PUBLIC_FILES}
    completed = []
    with tempfile.TemporaryDirectory(prefix="aureon-image-build-") as temporary:
        temp = Path(temporary)
        for row in plan["images"]:
            name = row["name"]
            context = temp / name
            _materialize_context(
                source,
                plan["source_revision"],
                prefixes[name],
                context,
                file_sets[name],
                certificate if name == "public_entry" else None,
            )
            build_id = runner.build(context, row["tag"])
            digest = runner.digest(build_id, row["tag"])
            completed.append(
                {
                    "name": name,
                    "build_id": build_id,
                    "context_sha256": row["context_sha256"],
                    "image": row["repository"] + "@" + digest,
                }
            )
    return completed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("plan", "build"), nargs="?", default="plan")
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--bridge-certificate", type=Path, required=True)
    parser.add_argument("--bridge-certificate-receipt", type=Path, required=True)
    parser.add_argument("--bridge-certificate-receipt-sha256", required=True)
    parser.add_argument("--plan", type=Path)
    parser.add_argument("--acknowledge-plan-sha256")
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--gcloud", default="gcloud")
    args = parser.parse_args(argv)
    try:
        plan, certificate = build_plan(
            args.source,
            args.source_revision,
            args.bridge_certificate,
            args.bridge_certificate_receipt,
            args.bridge_certificate_receipt_sha256,
        )
        if args.command == "plan":
            write_receipt(args.receipt, plan)
            print(json.dumps({"schema": SCHEMA, "plan_sha256": sha256(canonical(plan))}, sort_keys=True))
            return 0
        plan_hash = _load_plan(args.plan, plan, args.acknowledge_plan_sha256)
        images = execute(args.source, plan, certificate, Gcloud(args.gcloud))
        receipt = {
            "schema": RECEIPT_SCHEMA,
            "status": "built_and_digest_resolved",
            "recorded_at": datetime.now(UTC).isoformat(),
            "project": PROJECT,
            "region": REGION,
            "source_revision": args.source_revision,
            "source_tree": plan["source_tree"],
            "plan_sha256": plan_hash,
            "certificate_receipt_sha256": plan["certificate_receipt_sha256"],
            "certificate_fingerprint_sha256": plan["certificate_fingerprint_sha256"],
            "certificate": plan["certificate"],
            "images": images,
            "secret_values_recorded": False,
            "release_authority": False,
            "mutation_authority": False,
        }
        write_receipt(args.receipt, receipt)
        print(
            json.dumps(
                {
                    "schema": RECEIPT_SCHEMA,
                    "status": receipt["status"],
                    "receipt_sha256": sha256(canonical(receipt)),
                },
                sort_keys=True,
            )
        )
        return 0
    except ImageBuildError as exc:
        print(str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
