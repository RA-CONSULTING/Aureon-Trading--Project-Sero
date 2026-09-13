"""Provider-verified Supabase owner identity and downgrade regressions."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from types import SimpleNamespace

from aureon.operator.identity import (
    SupabaseAuthVerifier,
    SupabaseOwnerPolicy,
    owner_email_commitment,
    owner_identity_commitment,
    resolve_identity,
)

OWNER_ID = "da9d48f0-6992-4cdb-9450-dd3a4aa8c5e5"
OWNER_EMAIL = "owner@example.test"
TOKEN = "header.payload.signature"


def _verifier(payload: dict) -> SupabaseAuthVerifier:
    return SupabaseAuthVerifier(
        "https://siihxcwetdjdsrfdexmb.supabase.co",
        "sb_publishable_fixture_value_123456",
        fetch=lambda *_args: (200, json.dumps(payload).encode()),
    )


def _owner_payload(**changes) -> dict:
    result = {
        "id": OWNER_ID,
        "email": OWNER_EMAIL,
        "email_confirmed_at": "2026-09-13T12:00:00Z",
        "app_metadata": {"aureon_role": "owner"},
        "user_metadata": {"aureon_role": "attacker-controlled-and-ignored"},
    }
    result.update(changes)
    return result


def _policy() -> SupabaseOwnerPolicy:
    return SupabaseOwnerPolicy(
        subject=OWNER_ID,
        email_sha256=owner_email_commitment(OWNER_EMAIL),
    )


def _legacy_hs256_token(payload: dict, secret: str) -> str:
    """Create the legacy test token without adding a runtime JWT dependency."""

    def encode(value: bytes) -> str:
        return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")

    header = encode(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    body = encode(json.dumps(payload, separators=(",", ":")).encode())
    signing_input = f"{header}.{body}".encode("ascii")
    signature = encode(hmac.new(secret.encode(), signing_input, hashlib.sha256).digest())
    return f"{header}.{body}.{signature}"


def test_only_fresh_auth_server_app_metadata_and_exact_commissioning_record_elevate():
    ident = resolve_identity(
        f"Bearer {TOKEN}",
        operator_key="static-admin",
        jwt_secret="",
        tenant_verifier=_verifier(_owner_payload()),
        owner_policy=_policy(),
    )
    assert (ident.kind, ident.tenant, ident.ok, ident.auth_source) == (
        "owner",
        OWNER_ID,
        True,
        "supabase_auth_server",
    )


def test_every_owner_designation_mismatch_downgrades_to_isolated_tenant():
    variants = (
        _owner_payload(app_metadata={}),
        _owner_payload(app_metadata={"aureon_role": "tenant"}),
        _owner_payload(email="other@example.test"),
        _owner_payload(email_confirmed_at=None),
        _owner_payload(id="00000000-0000-4000-8000-000000000001"),
        # A user-editable claim is never consulted for authorization.
        _owner_payload(app_metadata={}, user_metadata={"aureon_role": "owner"}),
    )
    for payload in variants:
        ident = resolve_identity(
            f"Bearer {TOKEN}",
            operator_key="static-admin",
            jwt_secret="",
            tenant_verifier=_verifier(payload),
            owner_policy=_policy(),
        )
        assert ident.kind == "tenant"
        assert ident.ok is True
        assert ident.auth_source == "supabase_auth_server"


def test_locally_signed_or_forged_role_claim_can_never_become_owner():
    secret = "legacy-test-secret-at-least-thirty-two-bytes"
    token = _legacy_hs256_token(
        {
            "sub": OWNER_ID,
            "exp": int(time.time()) + 600,
            "role": "authenticated",
            "app_metadata": {"aureon_role": "owner"},
            "user_metadata": {"aureon_role": "owner"},
            "email": OWNER_EMAIL,
        },
        secret,
    )
    ident = resolve_identity(
        f"Bearer {token}",
        operator_key="static-admin",
        jwt_secret=secret,
        owner_policy=_policy(),
    )
    assert ident.kind == "tenant"
    assert ident.auth_source == "legacy_hs256"


def test_owner_policy_configuration_is_atomic_and_never_stores_plaintext_email():
    expected = owner_email_commitment(OWNER_EMAIL)
    policy = SupabaseOwnerPolicy.from_env(
        {
            "AUREON_SUPABASE_OWNER_SUBJECT": OWNER_ID,
            "AUREON_SUPABASE_OWNER_EMAIL_SHA256": expected,
        }
    )
    assert policy is not None
    assert policy.email_sha256 == expected
    assert OWNER_EMAIL not in repr(policy)

    for partial in (
        {"AUREON_SUPABASE_OWNER_SUBJECT": OWNER_ID},
        {"AUREON_SUPABASE_OWNER_EMAIL_SHA256": expected},
    ):
        try:
            SupabaseOwnerPolicy.from_env(partial)
        except ValueError as exc:
            assert str(exc) == "supabase_owner_identity_config_incomplete"
        else:  # pragma: no cover - explicit failure message
            raise AssertionError("partial owner configuration was accepted")


def test_operator_routes_owner_to_instance_plane_and_signout_loses_access(
    monkeypatch,
):
    import aureon.operator.identity as identity_module
    import aureon.operator.operator_server as server

    owner_claims = _verifier(_owner_payload())(TOKEN)
    tenant_claims = _verifier(
        _owner_payload(
            id="00000000-0000-4000-8000-000000000001",
            email="tenant@example.test",
            app_metadata={},
        )
    )(TOKEN)

    class FixedVerifier:
        def __init__(self, *_args, **_kwargs):
            pass

        def __call__(self, token):
            return owner_claims if token == "owner.token.signature" else tenant_claims

    monkeypatch.setattr(identity_module, "SupabaseAuthVerifier", FixedVerifier)
    monkeypatch.setenv("AUREON_OPERATOR_ENV", "test")
    monkeypatch.setenv("AUREON_OPERATOR_API_KEY", "static-admin")
    monkeypatch.delenv("AUREON_SUPABASE_JWT_SECRET", raising=False)
    monkeypatch.setenv(
        "AUREON_SUPABASE_URL", "https://siihxcwetdjdsrfdexmb.supabase.co"
    )
    monkeypatch.setenv(
        "AUREON_SUPABASE_PUBLISHABLE_KEY", "sb_publishable_fixture_value_123456"
    )
    monkeypatch.setenv("AUREON_SUPABASE_OWNER_SUBJECT", OWNER_ID)
    monkeypatch.setenv(
        "AUREON_SUPABASE_OWNER_EMAIL_SHA256", owner_email_commitment(OWNER_EMAIL)
    )
    for name in (
        "AUREON_OPERATOR_INTENT_CERT_FILE",
        "AUREON_OPERATOR_INTENT_LEDGER",
        "AUREON_OPERATOR_REVISION",
    ):
        monkeypatch.delenv(name, raising=False)

    app = server.create_app(operator=SimpleNamespace(providers={}, bus=None))
    client = app.test_client()
    owner = client.get(
        "/api/me", headers={"Authorization": "Bearer owner.token.signature"}
    )
    assert owner.status_code == 200
    assert owner.get_json() == {
        **owner.get_json(),
        "kind": "owner",
        "is_admin": True,
        "plane": "instance",
        "auth_source": "supabase_auth_server",
        "owner_designation_verified": True,
        "identity_commitment_sha256": owner_identity_commitment(OWNER_ID),
    }
    assert client.get(
        "/api/pulse", headers={"Authorization": "Bearer owner.token.signature"}
    ).status_code == 200

    tenant = client.get(
        "/api/me", headers={"Authorization": "Bearer tenant.token.signature"}
    )
    assert tenant.status_code == 200
    assert tenant.get_json()["kind"] == "tenant"
    assert tenant.get_json()["is_admin"] is False
    assert client.get(
        "/api/pulse", headers={"Authorization": "Bearer tenant.token.signature"}
    ).status_code == 403

    # After local browser sign-out there is no bearer to inherit the previous
    # owner identity. Every new request resolves independently and is denied.
    assert client.get("/api/me").status_code == 401
