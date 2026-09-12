from __future__ import annotations

import base64
import importlib
import json
import os
import stat
import time
from datetime import UTC, datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.x509.oid import NameOID

from aureon.operator.cloud_intent_custody import (
    INTENT_AUDIENCE,
    INTENT_ISSUER,
    INTENT_SCHEMA,
    CloudIntentCustodyError,
    CloudSwitchboardIntentCustody,
)


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _fixture(tmp_path):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "aureon-private-bridge")])
    now = datetime.now(UTC)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(days=1))
        .sign(key, hashes.SHA256())
    )
    cert_path = tmp_path / "bridge-cert.pem"
    cert_path.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
    return key, cert_path


def _token(key, *, now, revision, path, body, **changes):
    header = {"alg": "RS256", "typ": "JWT"}
    claims = {
        "aud": INTENT_AUDIENCE,
        "body_sha256": __import__("hashlib").sha256(body).hexdigest(),
        "exp": now + 10,
        "iat": now,
        "iss": INTENT_ISSUER,
        "jti": "test_nonce_abcdefghijklmnopqrstuvwxyz012345",
        "method": "POST",
        "mode": "iap",
        "path": path,
        "query_sha256": __import__("hashlib").sha256(b"").hexdigest(),
        "revision": revision,
        "route_rule": "/api/switchboard/<flag_id>",
        "schema": INTENT_SCHEMA,
    }
    claims.update(changes)
    first = _b64(json.dumps(header, sort_keys=True, separators=(",", ":")).encode())
    second = _b64(json.dumps(claims, sort_keys=True, separators=(",", ":")).encode())
    signature = key.sign((first + "." + second).encode(), padding.PKCS1v15(), hashes.SHA256())
    return first + "." + second + "." + _b64(signature)


def _authorize(custody, token, *, now, body=b'{"enabled":true}', path="/api/switchboard/AUREON_LIVE_TRADING"):
    return custody.authorize_and_consume(
        token=token,
        method="POST",
        path=path,
        route_rule="/api/switchboard/<flag_id>",
        query=b"",
        body=body,
        identity_kind="admin",
        is_admin=True,
        now=now,
    )


def test_signed_intent_is_exact_one_use_and_never_action_authority(tmp_path):
    key, cert = _fixture(tmp_path)
    revision = "a" * 40
    body = b'{"enabled":true}'
    now = int(time.time())
    custody = CloudSwitchboardIntentCustody(
        certificate_file=str(cert),
        replay_ledger=str(tmp_path / "replay.sqlite3"),
        revision=revision,
    )
    if os.name == "posix":
        assert stat.S_IMODE((tmp_path / "replay.sqlite3").stat().st_mode) == 0o600
    token = _token(
        key,
        now=now,
        revision=revision,
        path="/api/switchboard/AUREON_LIVE_TRADING",
        body=body,
    )
    receipt = _authorize(custody, token, now=now, body=body)
    assert receipt["intent_recording_authorized"] is True
    assert receipt["production_action_release"] is False
    assert receipt["release_authority"] is False
    assert receipt["mutation_authority"] is False
    with pytest.raises(CloudIntentCustodyError, match="cloud_intent_receipt_replayed"):
        _authorize(custody, token, now=now, body=body)


@pytest.mark.parametrize(
    "change,error",
    [
        ({"mode": "user"}, "join_invalid"),
        ({"revision": "b" * 40}, "join_invalid"),
        ({"route_rule": "/api/connections/<id>"}, "join_invalid"),
        ({"exp": 4_000_000_000}, "time_invalid"),
    ],
)
def test_signed_intent_rejects_wrong_scope_revision_and_lifetime(tmp_path, change, error):
    key, cert = _fixture(tmp_path)
    revision = "a" * 40
    body = b'{"enabled":true}'
    now = int(time.time())
    custody = CloudSwitchboardIntentCustody(
        certificate_file=str(cert),
        replay_ledger=str(tmp_path / "replay.sqlite3"),
        revision=revision,
    )
    token_changes = {key: value for key, value in change.items() if key != "revision"}
    token = _token(
        key,
        now=now,
        revision=str(change.get("revision", revision)),
        path="/api/switchboard/AUREON_LIVE_TRADING",
        body=body,
        **token_changes,
    )
    with pytest.raises(CloudIntentCustodyError, match=error):
        _authorize(custody, token, now=now, body=body)


def test_signed_intent_binds_body_path_and_admin_plane(tmp_path):
    key, cert = _fixture(tmp_path)
    revision = "a" * 40
    body = b'{"enabled":true}'
    now = int(time.time())
    custody = CloudSwitchboardIntentCustody(
        certificate_file=str(cert), replay_ledger=str(tmp_path / "replay.sqlite3"), revision=revision
    )
    token = _token(key, now=now, revision=revision, path="/api/switchboard/AUREON_LIVE_TRADING", body=body)
    with pytest.raises(CloudIntentCustodyError, match="join_invalid"):
        _authorize(custody, token, now=now, body=b'{"enabled":false}')
    with pytest.raises(CloudIntentCustodyError, match="join_invalid"):
        _authorize(custody, token, now=now, body=body, path="/api/switchboard/AUREON_DEPLOYMENT_HOLD")
    with pytest.raises(CloudIntentCustodyError, match="scope_denied"):
        custody.authorize_and_consume(
            token=token, method="POST", path="/api/switchboard/AUREON_LIVE_TRADING",
            route_rule="/api/switchboard/<flag_id>", query=b"", body=body,
            identity_kind="tenant", is_admin=False, now=now,
        )


def test_partial_configuration_fails_and_absent_configuration_stays_held(tmp_path):
    assert CloudSwitchboardIntentCustody.from_env({}) is None
    with pytest.raises(CloudIntentCustodyError, match="config_incomplete"):
        CloudSwitchboardIntentCustody.from_env(
            {"AUREON_OPERATOR_INTENT_LEDGER": str(tmp_path / "replay.sqlite3")}
        )


def test_operator_accepts_exact_owner_intent_but_keeps_runtime_hold(tmp_path, monkeypatch):
    key, cert = _fixture(tmp_path)
    revision = "a" * 40
    ledger = tmp_path / "replay.sqlite3"
    for name in (
        "AUREON_HNC_PACKET_MASTER_KEY",
        "HNC_PACKET_MASTER_KEY",
        "AUREON_SUPABASE_JWT_SECRET",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("AUREON_OPERATOR_ENV", "test")
    monkeypatch.setenv("AUREON_OPERATOR_API_KEY", "operator-secret")
    monkeypatch.setenv("AUREON_LLM_OFFLINE", "1")
    monkeypatch.setenv("AUREON_SUPPRESS_IMPORT_SIDE_EFFECTS", "1")
    monkeypatch.setenv("AUREON_OPERATOR_INTENT_CERT_FILE", str(cert))
    monkeypatch.setenv("AUREON_OPERATOR_INTENT_LEDGER", str(ledger))
    monkeypatch.setenv("AUREON_OPERATOR_REVISION", revision)
    import aureon.operator.operator_server as server

    server = importlib.reload(server)
    operator = SimpleNamespace(providers={}, bus=None)
    app = server.create_app(operator=operator)
    import aureon.operator.feature_switchboard as switchboard

    monkeypatch.setattr(switchboard, "CONFIG_DIR", tmp_path / "flags")
    monkeypatch.setattr(switchboard, "KEY_PATH", tmp_path / "flags" / "feature_flags.key")
    monkeypatch.setattr(switchboard, "STORE_PATH", tmp_path / "flags" / "feature_flags.json.enc")
    body = b'{"confirm":"AUREON_LIVE_TRADING","enabled":true}'
    now = int(time.time())
    token = _token(
        key,
        now=now,
        revision=revision,
        path="/api/switchboard/AUREON_LIVE_TRADING",
        body=body,
    )
    response = app.test_client().post(
        "/api/switchboard/AUREON_LIVE_TRADING",
        data=body,
        content_type="application/json",
        headers={
            "Authorization": "Bearer operator-secret",
            "X-Aureon-Operator-Intent": token,
        },
        base_url="http://127.0.0.1:8080",
    )
    assert response.status_code == 200
    assert response.get_json()["ok"] is True
    assert response.get_json()["flag"]["stored"] is True
    assert response.get_json()["flag"]["enabled"] is False
    assert response.get_json()["flag"]["pending_handoff"] is True
    assert app.extensions["aureon_cloud_intent_custody"]["release_authority"] is False
    replay = app.test_client().post(
        "/api/switchboard/AUREON_LIVE_TRADING",
        data=body,
        content_type="application/json",
        headers={
            "Authorization": "Bearer operator-secret",
            "X-Aureon-Operator-Intent": token,
        },
        base_url="http://127.0.0.1:8080",
    )
    assert replay.status_code == 403
    assert replay.get_json()["error"]["reason_code"] == "cloud_intent_receipt_replayed"
