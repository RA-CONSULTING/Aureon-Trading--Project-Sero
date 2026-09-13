"""Create a redacted VM readback receipt for the public bridge certificate.

Run this on the VM. It reads public certificate bytes and non-token metadata;
it never opens, copies, or hashes the private key.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Callable
from urllib.request import ProxyHandler, Request, build_opener

from cryptography import x509
from cryptography.hazmat.primitives.serialization import Encoding


SCHEMA = "aureon.gcp.vm-public-bridge-certificate-receipt.v1"
PROJECT = "aureon-trading"
ZONE = "europe-west1-b"
INSTANCE = "aureon-sero-20260906"
CERTIFICATE = Path("/etc/aureon-public/bridge-cert.pem")
METADATA = "http://metadata.google.internal/computeMetadata/v1/"
_REVISION = re.compile(r"[0-9a-f]{40}")
REQUIRED_IP_SANS = ("10.40.0.2",)
MINIMUM_REMAINING_VALIDITY_SECONDS = 86_400


class CertificateReceiptError(RuntimeError):
    """Stable receipt failure without certificate or provider content."""


def metadata_text(path: str) -> str:
    if path not in {"project/project-id", "instance/name", "instance/zone"}:
        raise CertificateReceiptError("metadata_path_invalid")
    request = Request(
        METADATA + path,
        headers={"Metadata-Flavor": "Google"},
        method="GET",
    )
    try:
        with build_opener(ProxyHandler({})).open(request, timeout=5) as response:
            raw = response.read(4097)
    except OSError as exc:
        raise CertificateReceiptError("vm_metadata_readback_failed") from exc
    if len(raw) > 4096:
        raise CertificateReceiptError("vm_metadata_readback_failed")
    try:
        return raw.decode("ascii").strip()
    except UnicodeError as exc:
        raise CertificateReceiptError("vm_metadata_readback_failed") from exc


def vm_identity(reader: Callable[[str], str] = metadata_text) -> dict[str, str]:
    value = {
        "project": reader("project/project-id"),
        "zone": reader("instance/zone").rsplit("/", 1)[-1],
        "instance": reader("instance/name"),
    }
    if value != {"project": PROJECT, "zone": ZONE, "instance": INSTANCE}:
        raise CertificateReceiptError("vm_identity_binding_invalid")
    return value


def certificate_der(path: Path) -> bytes:
    if (
        path != CERTIFICATE
        or path.is_symlink()
        or not path.is_file()
        or path.stat().st_size > 64 * 1024
    ):
        raise CertificateReceiptError("public_bridge_certificate_invalid")
    try:
        pem = path.read_bytes()
        if b"PRIVATE KEY" in pem:
            raise CertificateReceiptError("private_key_material_forbidden")
        certificate = x509.load_pem_x509_certificate(pem)
        return certificate.public_bytes(Encoding.DER)
    except CertificateReceiptError:
        raise
    except (OSError, ValueError) as exc:
        raise CertificateReceiptError("public_bridge_certificate_invalid") from exc


def certificate_evidence(
    der: bytes, *, now: datetime | None = None
) -> dict[str, object]:
    """Parse and validate the public certificate without reading its private key."""

    if not isinstance(der, bytes) or not der:
        raise CertificateReceiptError("public_bridge_certificate_invalid")
    try:
        certificate = x509.load_der_x509_certificate(der)
        not_before = certificate.not_valid_before_utc.astimezone(UTC)
        not_after = certificate.not_valid_after_utc.astimezone(UTC)
        san = certificate.extensions.get_extension_for_class(
            x509.SubjectAlternativeName
        ).value
        ip_sans = set(san.get_values_for_type(x509.IPAddress))
    except (ValueError, x509.ExtensionNotFound) as exc:
        raise CertificateReceiptError("public_bridge_certificate_invalid") from exc
    observed_at = (now or datetime.now(UTC)).astimezone(UTC)
    if observed_at < not_before or observed_at > not_after:
        raise CertificateReceiptError("public_bridge_certificate_not_current")
    remaining = (not_after - observed_at).total_seconds()
    if remaining < MINIMUM_REMAINING_VALIDITY_SECONDS:
        raise CertificateReceiptError(
            "public_bridge_certificate_remaining_validity_insufficient"
        )
    expected_sans = {ipaddress.ip_address(value) for value in REQUIRED_IP_SANS}
    if not expected_sans.issubset(ip_sans):
        raise CertificateReceiptError("public_bridge_certificate_ip_san_invalid")
    return {
        "required_ip_sans": list(REQUIRED_IP_SANS),
        "not_before": not_before.isoformat(),
        "not_after": not_after.isoformat(),
        "minimum_remaining_validity_seconds": (
            MINIMUM_REMAINING_VALIDITY_SECONDS
        ),
    }


def build_receipt(
    *,
    source_revision: str,
    identity: dict[str, str],
    der: bytes,
    now: datetime | None = None,
) -> dict[str, object]:
    if _REVISION.fullmatch(source_revision or "") is None:
        raise CertificateReceiptError("source_revision_invalid")
    if identity != {"project": PROJECT, "zone": ZONE, "instance": INSTANCE}:
        raise CertificateReceiptError("vm_identity_binding_invalid")
    observed_at = (now or datetime.now(UTC)).astimezone(UTC)
    evidence = certificate_evidence(der, now=observed_at)
    return {
        "schema": SCHEMA,
        "status": "passed",
        "project": PROJECT,
        "zone": ZONE,
        "instance": INSTANCE,
        "source_revision": source_revision,
        "recorded_at": observed_at.isoformat(),
        "certificate_path": str(CERTIFICATE),
        "algorithm": "x509-der-sha256",
        "certificate_sha256": hashlib.sha256(der).hexdigest(),
        **evidence,
        "private_key_included": False,
        "secret_values_recorded": False,
    }


def write_receipt(path: Path, value: dict[str, object]) -> str:
    if not path.is_absolute() or path.is_symlink():
        raise CertificateReceiptError("absolute_receipt_path_required")
    raw = json.dumps(value, sort_keys=True, indent=2).encode("ascii") + b"\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        prefix=".bridge-certificate-receipt-", dir=path.parent
    )
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
    return hashlib.sha256(raw).hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--certificate", type=Path, default=CERTIFICATE)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        receipt = build_receipt(
            source_revision=args.source_revision,
            identity=vm_identity(),
            der=certificate_der(args.certificate),
        )
        receipt_hash = write_receipt(args.receipt, receipt)
        print(
            json.dumps(
                {
                    "schema": SCHEMA,
                    "status": "passed",
                    "receipt_sha256": receipt_hash,
                    "certificate_sha256": receipt["certificate_sha256"],
                    "private_key_included": False,
                },
                sort_keys=True,
            )
        )
        return 0
    except CertificateReceiptError as exc:
        print(str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
