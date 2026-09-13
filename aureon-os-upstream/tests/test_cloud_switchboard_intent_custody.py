from __future__ import annotations

import base64
import hashlib
import hmac
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
    TENANT_INTENT_AUDIENCE,
    TENANT_INTENT_SCHEMA,
    CloudIntentCustodyError,
    CloudSwitchboardIntentCustody,
    owner_intent_route_contract,
    owner_intent_route_rule,
    tenant_intent_route_contract,
    tenant_intent_route_rule,
)


def _route(path: str) -> str:
    return owner_intent_route_rule("POST", path) or "<unmatched>"


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


def _backtest_body(scope: str = "1" * 64) -> bytes:
    return json.dumps(
        {
            "account_scope": scope,
            "request_id": "custody-backtest-request-001",
            "config": {
                "symbol": "BTCUSD",
                "startDate": "2026-09-01",
                "endDate": "2026-09-02",
                "initialCapital": 10000,
                "tradeSize": 0.5,
                "stopLoss": 2,
                "takeProfit": 5,
                "strategy": "momentum_next_open_v1",
                "intervalMinutes": 60,
                "lookbackPeriods": 24,
                "feeBps": 40,
                "slippageBps": 5,
            },
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()


def _token(key, *, now, revision, path, body, method="POST", query=b"", **changes):
    header = {"alg": "RS256", "typ": "JWT"}
    contract = owner_intent_route_contract(method, path) or {}
    claims = {
        "aud": INTENT_AUDIENCE,
        "body_sha256": __import__("hashlib").sha256(body).hexdigest(),
        "effect_class": contract.get("effect_class"),
        "exp": now + 10,
        "iat": now,
        "iss": INTENT_ISSUER,
        "jti": "test_nonce_abcdefghijklmnopqrstuvwxyz012345",
        "method": method,
        "mode": "iap",
        "path": path,
        "payload_schema": contract.get("payload_schema"),
        "query_sha256": __import__("hashlib").sha256(query).hexdigest(),
        "revision": revision,
        "route_rule": owner_intent_route_rule(method, path),
        "schema": INTENT_SCHEMA,
    }
    claims.update(changes)
    first = _b64(json.dumps(header, sort_keys=True, separators=(",", ":")).encode())
    second = _b64(json.dumps(claims, sort_keys=True, separators=(",", ":")).encode())
    signature = key.sign((first + "." + second).encode(), padding.PKCS1v15(), hashes.SHA256())
    return first + "." + second + "." + _b64(signature)


def _tenant_token(
    key,
    *,
    now,
    revision,
    method,
    path,
    query,
    body,
    authorization,
    tenant,
    **changes,
):
    header = {"alg": "RS256", "typ": "JWT"}
    contract = tenant_intent_route_contract(method, path) or {}
    claims = {
        "aud": TENANT_INTENT_AUDIENCE,
        "bearer_sha256": __import__("hashlib").sha256(
            b"aureon-tenant-bearer-v1\x00" + authorization.encode("ascii")
        ).hexdigest(),
        "body_sha256": __import__("hashlib").sha256(body).hexdigest(),
        "effect_class": contract.get("effect_class"),
        "exp": now + 10,
        "iat": now,
        "iss": INTENT_ISSUER,
        "jti": "tenant_nonce_abcdefghijklmnopqrstuvwxyz0123",
        "method": method,
        "mode": "user",
        "path": path,
        "payload_schema": contract.get("payload_schema"),
        "query_sha256": __import__("hashlib").sha256(query).hexdigest(),
        "revision": revision,
        "route_rule": tenant_intent_route_rule(method, path),
        "schema": TENANT_INTENT_SCHEMA,
        "tenant_identity_sha256": __import__("hashlib").sha256(
            b"aureon-tenant-identity-v1\x00" + tenant.encode("utf-8")
        ).hexdigest(),
    }
    claims.update(changes)
    first = _b64(json.dumps(header, sort_keys=True, separators=(",", ":")).encode())
    second = _b64(json.dumps(claims, sort_keys=True, separators=(",", ":")).encode())
    signature = key.sign((first + "." + second).encode(), padding.PKCS1v15(), hashes.SHA256())
    return first + "." + second + "." + _b64(signature)


def _hs_bearer(subject: str, secret: str) -> str:
    header = _b64(b'{"alg":"HS256","typ":"JWT"}')
    payload = _b64(
        json.dumps(
            {"exp": time.time() + 600, "sub": subject},
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    )
    signature = _b64(
        hmac.new(secret.encode(), f"{header}.{payload}".encode(), hashlib.sha256).digest()
    )
    return f"Bearer {header}.{payload}.{signature}"


def _authorize_tenant(
    custody,
    token,
    *,
    now,
    method="POST",
    path="/api/providers/openai",
    query=b"",
    body=b'{"api_key":"tenant-key"}',
    authorization="Bearer tenant.header.signature",
    tenant="tenant-a",
):
    return custody.authorize_and_consume(
        token=token,
        method=method,
        path=path,
        route_rule=tenant_intent_route_rule(method, path) or "<unmatched>",
        query=query,
        body=body,
        identity_kind="tenant",
        is_admin=False,
        authorization=authorization,
        tenant=tenant,
        now=now,
    )


def _authorize(
    custody,
    token,
    *,
    now,
    body=b'{"enabled":true}',
    path="/api/switchboard/AUREON_LIVE_TRADING",
    method="POST",
    query=b"",
):
    return custody.authorize_and_consume(
        token=token,
        method=method,
        path=path,
        route_rule=owner_intent_route_rule(method, path) or "<unmatched>",
        query=query,
        body=body,
        identity_kind="admin",
        is_admin=True,
        now=now,
    )


@pytest.mark.parametrize(
    "method,path,body,query",
    [
        ("POST", "/api/providers/openai", b'{"api_key":"owner-value"}', b""),
        ("DELETE", "/api/connections/binance", b"", b""),
        ("POST", "/api/connections/binance/test", b"{}", b""),
        ("POST", "/api/approvals/a1b2c3d4", b'{"decision":"approve"}', b""),
        ("POST", "/api/cognition/reason", b'{"prompt":"status"}', b""),
        ("GET", "/api/operator/stream", b"", b"prompt=status"),
        ("POST", "/api/trading/backtest", _backtest_body(), b""),
        ("POST", "/api/notifications/telegram", b'{"message":"status"}', b""),
    ],
)
def test_owner_reviewed_control_routes_are_exactly_bound(
    tmp_path, method, path, body, query
):
    key, cert = _fixture(tmp_path)
    revision = "a" * 40
    now = int(time.time())
    custody = CloudSwitchboardIntentCustody(
        certificate_file=str(cert),
        replay_ledger=str(tmp_path / "replay.sqlite3"),
        revision=revision,
    )
    token = _token(
        key,
        now=now,
        revision=revision,
        path=path,
        body=body,
        method=method,
        query=query,
    )
    receipt = _authorize(
        custody,
        token,
        now=now,
        body=body,
        path=path,
        method=method,
        query=query,
    )
    contract = owner_intent_route_contract(method, path)
    assert contract is not None
    assert receipt["intent_recording_authorized"] is True
    assert receipt["owner_route_authorized"] is True
    assert receipt["effect_class"] == contract["effect_class"]
    assert receipt["payload_schema"] == contract["payload_schema"]
    assert receipt["request_method"] == method
    assert receipt["request_path"] == path
    assert receipt["request_revision"] == revision
    assert receipt["route_rule"] == contract["route_rule"]
    assert receipt["query_sha256"] == hashlib.sha256(query).hexdigest()
    assert receipt["body_sha256"] == hashlib.sha256(body).hexdigest()
    assert receipt["state_mutation_authority"] is contract["state_mutation"]
    assert (
        receipt["configuration_mutation_authority"]
        is contract["configuration_mutation"]
    )
    assert receipt["external_read_authority"] is contract["external_read"]
    assert (
        receipt["external_communication_authority"]
        is contract["external_communication"]
    )
    assert receipt["owner_control_authority"] is contract["owner_control"]
    assert receipt["mutation_authority"] is (
        contract["state_mutation"] or contract["external_communication"]
    )
    assert receipt["tool_dispatch_authority"] is False
    assert receipt["economic_mutation_authority"] is False
    assert receipt["production_action_release"] is False


@pytest.mark.parametrize(
    "method,path,body,query",
    [
        ("POST", "/api/providers/openai", b'{"api_key":"x","unknown":true}', b""),
        ("POST", "/api/notifications/telegram", b"{}", b""),
        (
            "GET",
            "/api/cognition/stream",
            b"",
            b"prompt=status&unexpected=true",
        ),
        (
            "POST",
            "/api/trading/backtest",
            b'{"config":{},"request_id":"custody-backtest-request-001",'
            b'"account_scope":"1111111111111111111111111111111111111111111111111111111111111111"}',
            b"",
        ),
    ],
)
def test_route_payload_schema_is_checked_before_receipt_consumption(
    tmp_path, method, path, body, query
):
    key, cert = _fixture(tmp_path)
    revision = "a" * 40
    now = int(time.time())
    custody = CloudSwitchboardIntentCustody(
        certificate_file=str(cert),
        replay_ledger=str(tmp_path / "replay.sqlite3"),
        revision=revision,
    )
    token = _token(
        key,
        now=now,
        revision=revision,
        path=path,
        body=body,
        method=method,
        query=query,
    )
    with pytest.raises(CloudIntentCustodyError, match="cloud_intent_scope_denied"):
        _authorize(
            custody,
            token,
            now=now,
            body=body,
            path=path,
            method=method,
            query=query,
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
    summary = custody.public_summary()
    assert summary["mutation_authority"] is True
    assert summary["state_mutation_authority"] is True
    assert summary["configuration_mutation_authority"] is True
    assert summary["external_read_authority"] is True
    assert summary["external_communication_authority"] is True
    assert summary["unbounded_mutation_authority"] is False
    assert summary["tool_dispatch_authority"] is False
    assert summary["economic_mutation_authority"] is False
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
    assert receipt["mutation_authority"] is True
    assert receipt["configuration_mutation_authority"] is True
    assert receipt["external_communication_authority"] is False
    assert receipt["economic_mutation_authority"] is False
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


def test_tenant_intent_is_identity_bound_exact_and_one_use(tmp_path):
    key, cert = _fixture(tmp_path)
    revision = "a" * 40
    now = int(time.time())
    tenant = "tenant-a"
    authorization = "Bearer tenant.header.signature"
    path = "/api/providers/openai"
    body = b'{"api_key":"tenant-key"}'
    custody = CloudSwitchboardIntentCustody(
        certificate_file=str(cert),
        replay_ledger=str(tmp_path / "replay.sqlite3"),
        revision=revision,
    )
    token = _tenant_token(
        key,
        now=now,
        revision=revision,
        method="POST",
        path=path,
        query=b"",
        body=body,
        authorization=authorization,
        tenant=tenant,
    )

    # Every failed join happens before replay consumption.
    with pytest.raises(CloudIntentCustodyError, match="join_invalid"):
        _authorize_tenant(
            custody,
            token,
            now=now,
            path="/api/providers/anthropic",
            body=body,
            authorization=authorization,
            tenant=tenant,
        )
    with pytest.raises(CloudIntentCustodyError, match="join_invalid"):
        _authorize_tenant(
            custody,
            token,
            now=now,
            body=b'{"api_key":"different"}',
            authorization=authorization,
            tenant=tenant,
        )
    with pytest.raises(CloudIntentCustodyError, match="join_invalid"):
        _authorize_tenant(
            custody,
            token,
            now=now,
            body=body,
            authorization="Bearer swapped.header.signature",
            tenant=tenant,
        )
    with pytest.raises(CloudIntentCustodyError, match="join_invalid"):
        _authorize_tenant(
            custody,
            token,
            now=now,
            body=body,
            authorization=authorization,
            tenant="tenant-b",
        )
    with pytest.raises(CloudIntentCustodyError, match="scope_denied"):
        _authorize_tenant(
            custody,
            token,
            now=now,
            query=b"source=changed",
            body=body,
            authorization=authorization,
            tenant=tenant,
        )

    receipt = _authorize_tenant(
        custody,
        token,
        now=now,
        body=body,
        authorization=authorization,
        tenant=tenant,
    )
    assert receipt["tenant_route_authorized"] is True
    assert receipt["identity_bound"] is True
    assert receipt["intent_recording_authorized"] is False
    assert receipt["economic_mutation_authority"] is False
    assert receipt["owner_control_authority"] is False
    with pytest.raises(CloudIntentCustodyError, match="cloud_intent_receipt_replayed"):
        _authorize_tenant(
            custody,
            token,
            now=now,
            body=body,
            authorization=authorization,
            tenant=tenant,
        )


def test_tenant_connection_delete_receipt_is_subject_bound_and_exactly_one_use(tmp_path):
    key, cert = _fixture(tmp_path)
    revision = "a" * 40
    now = int(time.time())
    tenant = "tenant-delete-a"
    authorization = "Bearer tenant.header.signature"
    path = "/api/connections/binance"
    custody = CloudSwitchboardIntentCustody(
        certificate_file=str(cert),
        replay_ledger=str(tmp_path / "replay.sqlite3"),
        revision=revision,
    )
    token = _tenant_token(
        key,
        now=now,
        revision=revision,
        method="DELETE",
        path=path,
        query=b"",
        body=b"",
        authorization=authorization,
        tenant=tenant,
    )

    with pytest.raises(CloudIntentCustodyError, match="join_invalid"):
        _authorize_tenant(
            custody,
            token,
            now=now,
            method="DELETE",
            path=path,
            body=b"",
            authorization=authorization,
            tenant="tenant-delete-b",
        )
    receipt = _authorize_tenant(
        custody,
        token,
        now=now,
        method="DELETE",
        path=path,
        body=b"",
        authorization=authorization,
        tenant=tenant,
    )
    assert receipt["tenant_route_authorized"] is True
    assert receipt["identity_bound"] is True
    assert receipt["economic_mutation_authority"] is False
    with pytest.raises(CloudIntentCustodyError, match="cloud_intent_receipt_replayed"):
        _authorize_tenant(
            custody,
            token,
            now=now,
            method="DELETE",
            path=path,
            body=b"",
            authorization=authorization,
            tenant=tenant,
        )


def test_tenant_stream_intent_binds_query_and_rejects_body(tmp_path):
    key, cert = _fixture(tmp_path)
    revision = "a" * 40
    now = int(time.time())
    authorization = "Bearer tenant.header.signature"
    tenant = "tenant-a"
    path = "/api/cognition/stream"
    query = b"prompt=hello%20world&session_id=one"
    custody = CloudSwitchboardIntentCustody(
        certificate_file=str(cert),
        replay_ledger=str(tmp_path / "replay.sqlite3"),
        revision=revision,
    )
    token = _tenant_token(
        key,
        now=now,
        revision=revision,
        method="GET",
        path=path,
        query=query,
        body=b"",
        authorization=authorization,
        tenant=tenant,
    )
    with pytest.raises(CloudIntentCustodyError, match="join_invalid"):
        _authorize_tenant(
            custody,
            token,
            now=now,
            method="GET",
            path=path,
            query=b"prompt=different",
            body=b"",
            authorization=authorization,
            tenant=tenant,
        )
    with pytest.raises(CloudIntentCustodyError, match="scope_denied"):
        _authorize_tenant(
            custody,
            token,
            now=now,
            method="GET",
            path=path,
            query=query,
            body=b"unexpected",
            authorization=authorization,
            tenant=tenant,
        )
    receipt = _authorize_tenant(
        custody,
        token,
        now=now,
        method="GET",
        path=path,
        query=query,
        body=b"",
        authorization=authorization,
        tenant=tenant,
    )
    assert receipt["tenant_route_authorized"] is True


@pytest.mark.parametrize(
    "method,path",
    [
        ("POST", "/api/orders"),
        ("POST", "/api/trades/execute"),
        ("POST", "/api/switchboard/AUREON_LIVE_TRADING"),
        ("POST", "/api/operator/cloud-trading-control/apply"),
        ("POST", "/api/billing/charge"),
        ("PATCH", "/api/providers/openai"),
    ],
)
def test_tenant_intent_refuses_unsafe_or_arbitrary_route(tmp_path, method, path):
    key, cert = _fixture(tmp_path)
    revision = "a" * 40
    now = int(time.time())
    custody = CloudSwitchboardIntentCustody(
        certificate_file=str(cert),
        replay_ledger=str(tmp_path / "replay.sqlite3"),
        revision=revision,
    )
    token = _tenant_token(
        key,
        now=now,
        revision=revision,
        method=method,
        path=path,
        query=b"",
        body=b"{}",
        authorization="Bearer tenant.header.signature",
        tenant="tenant-a",
    )
    with pytest.raises(CloudIntentCustodyError, match="scope_denied"):
        _authorize_tenant(
            custody,
            token,
            now=now,
            method=method,
            path=path,
            body=b"{}",
        )


def test_owner_and_tenant_receipts_cannot_cross_modes(tmp_path):
    key, cert = _fixture(tmp_path)
    revision = "a" * 40
    now = int(time.time())
    custody = CloudSwitchboardIntentCustody(
        certificate_file=str(cert),
        replay_ledger=str(tmp_path / "replay.sqlite3"),
        revision=revision,
    )
    owner_body = b'{"enabled":true}'
    owner = _token(
        key,
        now=now,
        revision=revision,
        path="/api/switchboard/AUREON_LIVE_TRADING",
        body=owner_body,
    )
    with pytest.raises(CloudIntentCustodyError, match="scope_denied"):
        _authorize_tenant(
            custody,
            owner,
            now=now,
            path="/api/switchboard/AUREON_LIVE_TRADING",
            body=owner_body,
        )

    authorization = "Bearer tenant.header.signature"
    tenant_body = b'{"api_key":"tenant-key"}'
    tenant = _tenant_token(
        key,
        now=now,
        revision=revision,
        method="POST",
        path="/api/providers/openai",
        query=b"",
        body=tenant_body,
        authorization=authorization,
        tenant="tenant-a",
    )
    with pytest.raises(CloudIntentCustodyError, match="claims_invalid"):
        custody.authorize_and_consume(
            token=tenant,
            method="POST",
            path="/api/providers/openai",
            route_rule="/api/providers/<provider_id>",
            query=b"",
            body=tenant_body,
            identity_kind="admin",
            is_admin=True,
            authorization=authorization,
            tenant=None,
            now=now,
        )


def test_tenant_telegram_requires_supplied_token_before_receipt_verification(tmp_path):
    key, cert = _fixture(tmp_path)
    revision = "a" * 40
    now = int(time.time())
    path = "/api/notifications/telegram"
    authorization = "Bearer tenant.header.signature"
    custody = CloudSwitchboardIntentCustody(
        certificate_file=str(cert),
        replay_ledger=str(tmp_path / "replay.sqlite3"),
        revision=revision,
    )
    body = b'{"message":"must not use instance token"}'
    token = _tenant_token(
        key,
        now=now,
        revision=revision,
        method="POST",
        path=path,
        query=b"",
        body=body,
        authorization=authorization,
        tenant="tenant-a",
    )
    with pytest.raises(CloudIntentCustodyError, match="scope_denied"):
        _authorize_tenant(
            custody,
            token,
            now=now,
            path=path,
            body=body,
            authorization=authorization,
            tenant="tenant-a",
        )


def test_partial_configuration_fails_and_absent_configuration_stays_held(tmp_path):
    assert CloudSwitchboardIntentCustody.from_env({}) is None
    with pytest.raises(CloudIntentCustodyError, match="config_incomplete"):
        CloudSwitchboardIntentCustody.from_env(
            {"AUREON_OPERATOR_INTENT_LEDGER": str(tmp_path / "replay.sqlite3")}
        )


def test_operator_executes_only_exact_verified_tenant_receipt_then_blocks_replay(
    tmp_path, monkeypatch
):
    key, cert = _fixture(tmp_path)
    revision = "a" * 40
    jwt_secret = "tenant-custody-test-secret"
    tenant = "tenant-a"
    authorization = _hs_bearer(tenant, jwt_secret)
    path = "/api/providers/openai"
    body = b'{"api_key":"tenant-exact-key"}'
    now = int(time.time())
    for name in ("AUREON_HNC_PACKET_MASTER_KEY", "HNC_PACKET_MASTER_KEY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("AUREON_OPERATOR_ENV", "test")
    monkeypatch.setenv("AUREON_OPERATOR_API_KEY", "operator-secret")
    monkeypatch.setenv("AUREON_SUPABASE_JWT_SECRET", jwt_secret)
    monkeypatch.setenv("AUREON_LLM_OFFLINE", "1")
    monkeypatch.setenv("AUREON_SUPPRESS_IMPORT_SIDE_EFFECTS", "1")
    monkeypatch.setenv("AUREON_OPERATOR_INTENT_CERT_FILE", str(cert))
    monkeypatch.setenv("AUREON_OPERATOR_INTENT_LEDGER", str(tmp_path / "replay.sqlite3"))
    monkeypatch.setenv("AUREON_OPERATOR_REVISION", revision)

    import aureon.operator.keystore as keystore

    keystore = importlib.reload(keystore)
    config = tmp_path / "tenant-keystore"
    monkeypatch.setattr(keystore, "CONFIG_DIR", config)
    monkeypatch.setattr(keystore, "KEY_PATH", config / "provider_keys.key")
    monkeypatch.setattr(keystore, "STORE_PATH", config / "provider_keys.json.enc")
    monkeypatch.setattr(keystore, "TENANTS_DIR", config / "tenants")

    import aureon.operator.operator_server as server

    server = importlib.reload(server)
    app = server.create_app(operator=SimpleNamespace(providers={}, bus=None))
    client = app.test_client()
    token = _tenant_token(
        key,
        now=now,
        revision=revision,
        method="POST",
        path=path,
        query=b"",
        body=body,
        authorization=authorization,
        tenant=tenant,
    )
    request_headers = {
        "Authorization": authorization,
        "X-Aureon-Operator-Intent": token,
        "Content-Type": "application/json",
    }

    # A route or body substitution is rejected without spending the receipt.
    substituted = client.post(
        "/api/providers/anthropic",
        data=body,
        headers=request_headers,
        base_url="http://127.0.0.1:8080",
    )
    assert substituted.status_code == 403
    assert substituted.get_json()["error"]["reason_code"] == "cloud_intent_receipt_join_invalid"
    changed_body = client.post(
        path,
        data=b'{"api_key":"changed"}',
        headers=request_headers,
        base_url="http://127.0.0.1:8080",
    )
    assert changed_body.status_code == 403
    assert changed_body.get_json()["error"]["reason_code"] == "cloud_intent_receipt_join_invalid"

    accepted = client.post(
        path,
        data=body,
        headers=request_headers,
        base_url="http://127.0.0.1:8080",
    )
    assert accepted.status_code == 200
    assert accepted.get_json()["provider"]["has_key"] is True
    assert keystore.load(tenant)["openai"]["api_key"] == "tenant-exact-key"

    replay = client.post(
        path,
        data=body,
        headers=request_headers,
        base_url="http://127.0.0.1:8080",
    )
    assert replay.status_code == 403
    assert replay.get_json()["error"]["reason_code"] == "cloud_intent_receipt_replayed"


def test_operator_connection_delete_consumes_exact_tenant_receipt_and_only_its_store(
    tmp_path, monkeypatch
):
    key, cert = _fixture(tmp_path)
    revision = "a" * 40
    jwt_secret = "tenant-delete-custody-secret"
    tenant = "tenant-delete-a"
    other = "tenant-delete-b"
    authorization = _hs_bearer(tenant, jwt_secret)
    path = "/api/connections/binance"
    now = int(time.time())
    for name in ("AUREON_HNC_PACKET_MASTER_KEY", "HNC_PACKET_MASTER_KEY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("AUREON_OPERATOR_ENV", "test")
    monkeypatch.setenv("AUREON_OPERATOR_API_KEY", "operator-secret")
    monkeypatch.setenv("AUREON_SUPABASE_JWT_SECRET", jwt_secret)
    monkeypatch.setenv("AUREON_LLM_OFFLINE", "1")
    monkeypatch.setenv("AUREON_SUPPRESS_IMPORT_SIDE_EFFECTS", "1")
    monkeypatch.setenv("AUREON_OPERATOR_INTENT_CERT_FILE", str(cert))
    monkeypatch.setenv("AUREON_OPERATOR_INTENT_LEDGER", str(tmp_path / "replay.sqlite3"))
    monkeypatch.setenv("AUREON_OPERATOR_REVISION", revision)

    import aureon.operator.keystore as keystore

    keystore = importlib.reload(keystore)
    config = tmp_path / "tenant-keystore"
    monkeypatch.setattr(keystore, "CONFIG_DIR", config)
    monkeypatch.setattr(keystore, "KEY_PATH", config / "provider_keys.key")
    monkeypatch.setattr(keystore, "STORE_PATH", config / "provider_keys.json.enc")
    monkeypatch.setattr(keystore, "TENANTS_DIR", config / "tenants")
    for subject, suffix in ((tenant, "a"), (other, "b")):
        keystore.save_provider(
            "binance",
            api_key="tenant-primary-" + suffix,
            extra={"BINANCE_API_SECRET": "tenant-secondary-" + suffix},
            tenant=subject,
        )

    import aureon.operator.operator_server as server

    server = importlib.reload(server)
    client = server.create_app(operator=SimpleNamespace(providers={}, bus=None)).test_client()
    token = _tenant_token(
        key,
        now=now,
        revision=revision,
        method="DELETE",
        path=path,
        query=b"",
        body=b"",
        authorization=authorization,
        tenant=tenant,
    )
    headers = {"Authorization": authorization, "X-Aureon-Operator-Intent": token}

    accepted = client.delete(path, headers=headers, base_url="http://127.0.0.1:8080")
    assert accepted.status_code == 200
    assert accepted.get_json()["disconnected"] is True
    assert "binance" not in keystore.load(tenant)
    assert keystore.load(other)["binance"]["api_key"] == "tenant-primary-b"
    replay = client.delete(path, headers=headers, base_url="http://127.0.0.1:8080")
    assert replay.status_code == 403
    assert replay.get_json()["error"]["reason_code"] == "cloud_intent_receipt_replayed"


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


def test_owner_can_record_and_revoke_bounded_authorization_lease(tmp_path, monkeypatch):
    key, cert = _fixture(tmp_path)
    revision = "a" * 40
    for name in ("AUREON_HNC_PACKET_MASTER_KEY", "HNC_PACKET_MASTER_KEY", "AUREON_SUPABASE_JWT_SECRET"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("AUREON_OPERATOR_ENV", "test")
    monkeypatch.setenv("AUREON_OPERATOR_API_KEY", "operator-secret")
    monkeypatch.setenv("AUREON_LLM_OFFLINE", "1")
    monkeypatch.setenv("AUREON_SUPPRESS_IMPORT_SIDE_EFFECTS", "1")
    monkeypatch.setenv("AUREON_OPERATOR_INTENT_CERT_FILE", str(cert))
    monkeypatch.setenv("AUREON_OPERATOR_INTENT_LEDGER", str(tmp_path / "replay.sqlite3"))
    monkeypatch.setenv("AUREON_OPERATOR_REVISION", revision)
    monkeypatch.setenv("AUREON_RELEASE_LEDGER_PATH", str(tmp_path / "release-ledger.jsonl"))
    import aureon.operator.operator_server as server

    server = importlib.reload(server)
    app = server.create_app(operator=SimpleNamespace(providers={}, bus=None))
    body = (
        b'{"action":"grant","confirm":"AUREON_72_HOUR_OPERATOR_AUTHORIZATION",'
        b'"duration_seconds":259200}'
    )
    now = int(time.time())
    token = _token(
        key, now=now, revision=revision,
        path="/api/operator/authorization-lease", body=body,
    )
    response = app.test_client().post(
        "/api/operator/authorization-lease",
        data=body,
        content_type="application/json",
        headers={"Authorization": "Bearer operator-secret", "X-Aureon-Operator-Intent": token},
        base_url="http://127.0.0.1:8080",
    )
    assert response.status_code == 200
    lease = response.get_json()["lease"]
    assert lease["active"] is True and 259190 <= lease["remaining_seconds"] <= 259200
    assert lease["release_authority"] is False and lease["mutation_authority"] is False
    readback = app.test_client().get(
        "/api/operator/authorization-lease",
        headers={"Authorization": "Bearer operator-secret"},
        base_url="http://127.0.0.1:8080",
    ).get_json()
    assert readback["active"] is True
    assert readback["ledger_event_sha256"] == lease["ledger_event_sha256"]


def test_owner_can_publish_governed_cloud_release_request(tmp_path, monkeypatch):
    key, cert = _fixture(tmp_path)
    revision = "a" * 40
    for name in ("AUREON_HNC_PACKET_MASTER_KEY", "HNC_PACKET_MASTER_KEY", "AUREON_SUPABASE_JWT_SECRET"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("AUREON_OPERATOR_ENV", "test")
    monkeypatch.setenv("AUREON_OPERATOR_API_KEY", "operator-secret")
    monkeypatch.setenv("AUREON_LLM_OFFLINE", "1")
    monkeypatch.setenv("AUREON_SUPPRESS_IMPORT_SIDE_EFFECTS", "1")
    monkeypatch.setenv("AUREON_OPERATOR_INTENT_CERT_FILE", str(cert))
    monkeypatch.setenv("AUREON_OPERATOR_INTENT_LEDGER", str(tmp_path / "replay.sqlite3"))
    monkeypatch.setenv("AUREON_OPERATOR_REVISION", revision)
    import aureon.operator.operator_server as server

    server = importlib.reload(server)
    published = []
    monkeypatch.setattr(server, "build_cloud_trading_control_receipt", lambda: {"operator_can_apply_live": True})
    monkeypatch.setattr(server, "publish_release_request", lambda action, control: published.append((action, control)) or {
        "schema": "aureon.operator.cloud-trading-release-request.v1",
        "request_id": "9" * 64, "controller_pending": True,
    })
    app = server.create_app(operator=SimpleNamespace(providers={}, bus=None))
    path = "/api/operator/cloud-trading-control/apply"
    body = b'{"action":"activate","confirm":"APPLY_AUREON_CLOUD_LIVE_TRADING"}'
    now = int(time.time())
    token = _token(key, now=now, revision=revision, path=path, body=body)
    response = app.test_client().post(
        path, data=body, content_type="application/json",
        headers={"Authorization": "Bearer operator-secret", "X-Aureon-Operator-Intent": token},
        base_url="http://127.0.0.1:8080",
    )
    assert response.status_code == 202 and response.get_json()["ok"] is True
    assert published == [("activate", {"operator_can_apply_live": True})]
