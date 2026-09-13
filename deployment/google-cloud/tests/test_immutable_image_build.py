"""Offline tests for immutable image build and digest receipts."""

from __future__ import annotations

import importlib.util
from datetime import UTC, datetime, timedelta
import hashlib
import ipaddress
import json
from pathlib import Path
import subprocess
import sys

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
import pytest


CONTROL = Path(__file__).resolve().parents[1] / "trading-control"
sys.path.insert(0, str(CONTROL))
spec = importlib.util.spec_from_file_location(
    "immutable_image_build", CONTROL / "immutable_image_build.py"
)
assert spec and spec.loader
images = importlib.util.module_from_spec(spec)
spec.loader.exec_module(images)


def source_tree(tmp_path):
    source = (tmp_path / "source").resolve()
    authority = source / "deployment/google-cloud/trading-control"
    public = source / "deployment/google-cloud/public-entry"
    authority.mkdir(parents=True)
    public.mkdir(parents=True)
    for name in images.AUTHORITY_FILES:
        (authority / name).write_text("authority " + name, encoding="utf-8")
    for name in images.PUBLIC_FILES:
        (public / name).write_text("public " + name, encoding="utf-8")
    return source


def certificate_fixture(tmp_path, *, ip_san="10.40.0.2", expires_days=2):
    now = datetime.now(UTC)
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "fixture")])
    certificate = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=5))
        .not_valid_after(now + timedelta(days=expires_days))
        .add_extension(
            x509.SubjectAlternativeName(
                [x509.IPAddress(ipaddress.ip_address(ip_san))]
            ),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )
    certificate_path = (tmp_path / "bridge-cert.pem").resolve()
    certificate_path.write_bytes(
        certificate.public_bytes(serialization.Encoding.PEM)
    )
    receipt = {
        "schema": images.CERTIFICATE_RECEIPT_SCHEMA,
        "status": "passed",
        "project": images.PROJECT,
        "zone": "europe-west1-b",
        "instance": "aureon-sero-20260906",
        "source_revision": "a" * 40,
        "recorded_at": now.isoformat(),
        "certificate_path": "/etc/aureon-public/bridge-cert.pem",
        "algorithm": "x509-der-sha256",
        "certificate_sha256": hashlib.sha256(
            certificate.public_bytes(serialization.Encoding.DER)
        ).hexdigest(),
        "required_ip_sans": ["10.40.0.2"],
        "not_before": certificate.not_valid_before_utc.isoformat(),
        "not_after": certificate.not_valid_after_utc.isoformat(),
        "minimum_remaining_validity_seconds": 86_400,
        "private_key_included": False,
        "secret_values_recorded": False,
    }
    receipt_path = (tmp_path / "certificate-receipt.json").resolve()
    raw = json.dumps(receipt, sort_keys=True).encode("ascii")
    receipt_path.write_bytes(raw)
    return certificate_path, receipt_path, hashlib.sha256(raw).hexdigest()


def test_certificate_validation_requires_current_exact_ip_san(tmp_path):
    certificate, receipt, receipt_hash = certificate_fixture(tmp_path)
    pem, fingerprint, evidence = images.validate_certificate(
        certificate, receipt, receipt_hash, "a" * 40
    )
    assert pem.startswith(b"-----BEGIN CERTIFICATE-----")
    assert len(fingerprint) == 64
    assert evidence == {
        "receipt_sha256": receipt_hash,
        "fingerprint_sha256": fingerprint,
        "required_ip_sans": ["10.40.0.2"],
        "not_before": json.loads(receipt.read_bytes())["not_before"],
        "not_after": json.loads(receipt.read_bytes())["not_after"],
        "minimum_remaining_validity_seconds": 86_400,
    }


def test_certificate_validation_rejects_wrong_ip_san(tmp_path):
    certificate, receipt, receipt_hash = certificate_fixture(
        tmp_path, ip_san="10.40.0.3"
    )
    with pytest.raises(images.ImageBuildError, match="ip_san_invalid"):
        images.validate_certificate(
            certificate, receipt, receipt_hash, "a" * 40
        )


def test_build_plan_and_execution_bind_both_contexts(monkeypatch, tmp_path):
    source = source_tree(tmp_path)
    certificate = (tmp_path / "bridge-cert.pem").resolve()
    certificate.write_bytes(b"public-certificate")
    receipt = (tmp_path / "certificate-receipt.json").resolve()
    receipt.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(images, "bind_source", lambda *_: "b" * 40)
    monkeypatch.setattr(
        images,
        "_git_blob",
        lambda checkout, _revision, relative: (checkout / relative).read_bytes(),
    )
    monkeypatch.setattr(
        images,
        "validate_certificate",
        lambda *_: (
            b"public-certificate",
            "c" * 64,
            {
                "receipt_sha256": "d" * 64,
                "fingerprint_sha256": "c" * 64,
                "required_ip_sans": ["10.40.0.2"],
                "not_before": "2026-09-12T00:00:00+00:00",
                "not_after": "2027-09-12T00:00:00+00:00",
                "minimum_remaining_validity_seconds": 86_400,
            },
        ),
    )
    plan, pem = images.build_plan(
        source,
        "a" * 40,
        certificate,
        receipt,
        "d" * 64,
    )
    assert [row["name"] for row in plan["images"]] == [
        "authority",
        "public_entry",
    ]
    assert all(row["tag"].endswith(":" + "a" * 40) for row in plan["images"])

    class Runner:
        def __init__(self):
            self.contexts = []
            self.digest_requests = []

        def build(self, context, tag):
            self.contexts.append((sorted(path.name for path in context.iterdir()), tag))
            return "fixture-build-id-1234"

        def digest(self, build_id, tag):
            self.digest_requests.append((build_id, tag))
            return "sha256:" + ("e" if "authority" in tag else "f") * 64

    runner = Runner()
    completed = images.execute(source, plan, pem, runner)
    assert len(completed) == 2
    assert all("@sha256:" in row["image"] for row in completed)
    assert runner.digest_requests == [
        ("fixture-build-id-1234", row["tag"]) for row in plan["images"]
    ]
    assert "bridge-cert.pem" not in runner.contexts[0][0]
    assert "bridge-cert.pem" in runner.contexts[1][0]


def test_gcloud_digest_reads_exact_build_result(monkeypatch):
    build_id = "fixture-build-id-1234"
    tag = images.AUTHORITY_REPOSITORY + ":" + "a" * 40
    expected_digest = "sha256:" + "e" * 64
    calls = []

    def run(argv, **kwargs):
        calls.append((argv, kwargs))
        return subprocess.CompletedProcess(
            argv,
            0,
            stdout=json.dumps(
                {
                    "id": build_id,
                    "status": "SUCCESS",
                    "results": {
                        "images": [{"name": tag, "digest": expected_digest}]
                    },
                }
            ),
            stderr="",
        )

    monkeypatch.setattr(images.subprocess, "run", run)
    assert images.Gcloud("gcloud").digest(build_id, tag) == expected_digest
    assert calls[0][0][:4] == ["gcloud", "builds", "describe", build_id]
    assert "--region=" + images.REGION in calls[0][0]
    assert "artifacts" not in calls[0][0]


def test_gcloud_digest_rejects_result_from_a_different_tag(monkeypatch):
    build_id = "fixture-build-id-1234"
    tag = images.AUTHORITY_REPOSITORY + ":" + "a" * 40

    def run(argv, **_kwargs):
        return subprocess.CompletedProcess(
            argv,
            0,
            stdout=json.dumps(
                {
                    "id": build_id,
                    "status": "SUCCESS",
                    "results": {
                        "images": [
                            {
                                "name": images.AUTHORITY_REPOSITORY
                                + ":"
                                + "b" * 40,
                                "digest": "sha256:" + "e" * 64,
                            }
                        ]
                    },
                }
            ),
            stderr="",
        )

    monkeypatch.setattr(images.subprocess, "run", run)
    with pytest.raises(images.ImageBuildError, match="digest_readback_failed"):
        images.Gcloud("gcloud").digest(build_id, tag)


def test_gcloud_digest_rejects_result_from_a_different_build(monkeypatch):
    build_id = "fixture-build-id-1234"
    tag = images.AUTHORITY_REPOSITORY + ":" + "a" * 40

    def run(argv, **_kwargs):
        return subprocess.CompletedProcess(
            argv,
            0,
            stdout=json.dumps(
                {
                    "id": "different-build-id-5678",
                    "status": "SUCCESS",
                    "results": {
                        "images": [
                            {"name": tag, "digest": "sha256:" + "e" * 64}
                        ]
                    },
                }
            ),
            stderr="",
        )

    monkeypatch.setattr(images.subprocess, "run", run)
    with pytest.raises(images.ImageBuildError, match="digest_readback_failed"):
        images.Gcloud("gcloud").digest(build_id, tag)
