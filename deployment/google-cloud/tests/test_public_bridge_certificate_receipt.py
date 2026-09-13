"""Offline tests for the redacted public bridge certificate receipt."""

from __future__ import annotations

import importlib.util
import ipaddress
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID
import pytest


MODULE = (
    Path(__file__).resolve().parents[1]
    / "public-entry"
    / "public_bridge_certificate_receipt.py"
)
spec = importlib.util.spec_from_file_location("bridge_certificate_receipt", MODULE)
assert spec and spec.loader
receipt_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(receipt_module)


def identity():
    return {
        "project": "aureon-trading",
        "zone": "europe-west1-b",
        "instance": "aureon-sero-20260906",
    }


NOW = datetime(2026, 9, 13, 12, 0, tzinfo=UTC)


def certificate(
    *,
    not_before: datetime | None = None,
    not_after: datetime | None = None,
    ip_san: str = "10.40.0.2",
):
    key = ec.generate_private_key(ec.SECP256R1())
    subject = issuer = x509.Name(
        [x509.NameAttribute(NameOID.COMMON_NAME, "aureon-public-bridge")]
    )
    value = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(not_before or NOW - timedelta(days=1))
        .not_valid_after(not_after or NOW + timedelta(days=30))
        .add_extension(
            x509.SubjectAlternativeName(
                [x509.IPAddress(ipaddress.ip_address(ip_san))]
            ),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )
    return key, value


def test_receipt_binds_vm_revision_and_only_public_fingerprint(tmp_path):
    _key, public_certificate = certificate()
    value = receipt_module.build_receipt(
        source_revision="a" * 40,
        identity=identity(),
        der=public_certificate.public_bytes(serialization.Encoding.DER),
        now=NOW,
    )
    path = (tmp_path / "receipt.json").resolve()
    receipt_hash = receipt_module.write_receipt(path, value)
    observed = json.loads(path.read_text(encoding="ascii"))
    assert observed["schema"] == receipt_module.SCHEMA
    assert observed["private_key_included"] is False
    assert observed["secret_values_recorded"] is False
    assert observed["required_ip_sans"] == ["10.40.0.2"]
    assert observed["not_before"] == (NOW - timedelta(days=1)).isoformat()
    assert observed["not_after"] == (NOW + timedelta(days=30)).isoformat()
    assert observed["minimum_remaining_validity_seconds"] == 86_400
    assert len(observed["certificate_sha256"]) == 64
    assert len(receipt_hash) == 64
    assert "PRIVATE KEY" not in path.read_text(encoding="ascii")


@pytest.mark.parametrize(
    ("not_before", "not_after", "reason"),
    [
        (
            NOW + timedelta(minutes=1),
            NOW + timedelta(days=30),
            "public_bridge_certificate_not_current",
        ),
        (
            NOW - timedelta(days=30),
            NOW - timedelta(seconds=1),
            "public_bridge_certificate_not_current",
        ),
        (
            NOW - timedelta(days=1),
            NOW + timedelta(hours=23),
            "public_bridge_certificate_remaining_validity_insufficient",
        ),
    ],
)
def test_certificate_validity_fails_closed(not_before, not_after, reason):
    _key, public_certificate = certificate(
        not_before=not_before,
        not_after=not_after,
    )
    with pytest.raises(receipt_module.CertificateReceiptError, match=reason):
        receipt_module.build_receipt(
            source_revision="a" * 40,
            identity=identity(),
            der=public_certificate.public_bytes(serialization.Encoding.DER),
            now=NOW,
        )


def test_wrong_ip_san_fails_then_correct_certificate_recovers():
    _key, wrong = certificate(ip_san="10.40.0.3")
    with pytest.raises(
        receipt_module.CertificateReceiptError,
        match="public_bridge_certificate_ip_san_invalid",
    ):
        receipt_module.build_receipt(
            source_revision="a" * 40,
            identity=identity(),
            der=wrong.public_bytes(serialization.Encoding.DER),
            now=NOW,
        )

    _key, corrected = certificate()
    value = receipt_module.build_receipt(
        source_revision="a" * 40,
        identity=identity(),
        der=corrected.public_bytes(serialization.Encoding.DER),
        now=NOW,
    )
    assert value["status"] == "passed"
    assert value["required_ip_sans"] == ["10.40.0.2"]


def test_certificate_file_is_parsed_as_x509_and_private_key_is_rejected(
    tmp_path, monkeypatch
):
    key, public_certificate = certificate()
    path = tmp_path / "bridge-cert.pem"
    path.write_bytes(public_certificate.public_bytes(serialization.Encoding.PEM))
    monkeypatch.setattr(receipt_module, "CERTIFICATE", path)
    der = receipt_module.certificate_der(path)
    assert der == public_certificate.public_bytes(serialization.Encoding.DER)

    path.write_bytes(
        public_certificate.public_bytes(serialization.Encoding.PEM)
        + key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    with pytest.raises(
        receipt_module.CertificateReceiptError,
        match="private_key_material_forbidden",
    ):
        receipt_module.certificate_der(path)


def test_vm_metadata_identity_mismatch_fails_closed():
    values = {
        "project/project-id": "wrong-project",
        "instance/zone": "projects/1/zones/europe-west1-b",
        "instance/name": "aureon-sero-20260906",
    }
    with pytest.raises(
        receipt_module.CertificateReceiptError,
        match="vm_identity_binding_invalid",
    ):
        receipt_module.vm_identity(values.__getitem__)
