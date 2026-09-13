"""
Aureon Operator — end-user identity + per-tenant key isolation.

Proves the multi-tenant increment holds its two hard invariants:
  * **Isolation** — one tenant can never read, test, or apply another tenant's keys; a tenant sees only
    their own isolated store, never the instance/admin env keys.
  * **No leak** — a tenant write NEVER mutates ``os.environ`` (the shared process env), which is the only
    way one tenant's key could leak into another's reasoning.

Also covers the identity resolver matrix and backward-compat (no secrets ⇒ open, unchanged). Offline; the
keystore is redirected to a tmp dir so the real ``~/.aureon`` is never touched.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import importlib
import json
import logging
import os
import time

import pytest

pytest.importorskip("flask", reason="operator HTTP surface requires the `.[operator]` extra")

from aureon.operator.identity import resolve_identity  # noqa: E402

SECRET = "tenant-test-secret"
ADMIN_KEY = "admin-static-key"


def _mk_jwt(sub: str, secret: str = SECRET, exp: float | None = None) -> str:
    def b(d: dict) -> str:
        return base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=").decode()

    h, p = b({"alg": "HS256", "typ": "JWT"}), b({"sub": sub, "exp": exp or time.time() + 3600})
    sig = base64.urlsafe_b64encode(
        hmac.new(secret.encode(), f"{h}.{p}".encode(), hashlib.sha256).digest()
    ).rstrip(b"=").decode()
    return f"{h}.{p}.{sig}"


def _tenant(sub: str) -> dict:
    return {"Authorization": f"Bearer {_mk_jwt(sub)}"}


_ADMIN = {"Authorization": f"Bearer {ADMIN_KEY}"}


@pytest.fixture
def env(tmp_path, monkeypatch):
    """A tenancy-enabled operator with the keystore isolated to a tmp dir. Returns (client, keystore)."""
    monkeypatch.setenv("AUREON_LLM_OFFLINE", "1")
    monkeypatch.setenv("AUREON_SUPPRESS_IMPORT_SIDE_EFFECTS", "1")
    monkeypatch.setenv("AUREON_SUPABASE_JWT_SECRET", SECRET)
    monkeypatch.setenv("AUREON_OPERATOR_API_KEY", ADMIN_KEY)

    import aureon.operator.keystore as ks

    importlib.reload(ks)
    cfg = tmp_path / ".aureon"
    monkeypatch.setattr(ks, "CONFIG_DIR", cfg)
    monkeypatch.setattr(ks, "KEY_PATH", cfg / "provider_keys.key")
    monkeypatch.setattr(ks, "STORE_PATH", cfg / "provider_keys.json.enc")
    monkeypatch.setattr(ks, "TENANTS_DIR", cfg / "tenants")

    import aureon.operator.operator_server as srv

    importlib.reload(srv)
    app = srv.create_app(
        test_ingress_release=srv.TestOnlyOperatorIngressRelease(
            master_key=b"operator-tenant-keys-route-test-material",
        )
    )
    return app.test_client(), ks, cfg


def _openai_view(payload: dict) -> dict:
    return next(p for p in payload["providers"] if p["id"] == "openai")


# ── identity resolver matrix ────────────────────────────────────────────────────

def test_resolve_identity_matrix():
    # open: neither secret configured
    assert resolve_identity(None, operator_key="", jwt_secret="") == \
        __import__("aureon.operator.identity", fromlist=["Identity"]).Identity(
            "open", None, True, auth_source="open"
        )
    # admin: static key
    i = resolve_identity(f"Bearer {ADMIN_KEY}", operator_key=ADMIN_KEY, jwt_secret=SECRET)
    assert (i.kind, i.tenant, i.ok) == ("admin", None, True)
    # tenant: valid jwt
    i = resolve_identity(f"Bearer {_mk_jwt('user-x')}", operator_key=ADMIN_KEY, jwt_secret=SECRET)
    assert (i.kind, i.tenant, i.ok) == ("tenant", "user-x", True)
    # invalid token when a scheme is on
    assert resolve_identity("Bearer nope", operator_key=ADMIN_KEY, jwt_secret=SECRET).ok is False
    # expired jwt
    bad = _mk_jwt("user-x", exp=time.time() - 10)
    assert resolve_identity(f"Bearer {bad}", operator_key="", jwt_secret=SECRET).ok is False


# ── isolation over the HTTP surface ─────────────────────────────────────────────

def test_tenant_keys_are_isolated(env):
    client, _ks, _cfg = env
    r = client.post("/api/providers/openai", json={"api_key": "sk-AAAA1234"}, headers=_tenant("aaa"))
    assert r.status_code == 200

    a_view = _openai_view(client.get("/api/providers", headers=_tenant("aaa")).get_json())
    b_view = _openai_view(client.get("/api/providers", headers=_tenant("bbb")).get_json())
    assert a_view["has_key"] is True and a_view["key_masked"].endswith("1234")
    assert b_view["has_key"] is False           # tenant B can never see tenant A's key
    # "live" describes the plane that will answer THIS caller: A's own key now drives A's own
    # engine (per-user live reasoning), and B — who has no key — sees nothing live.
    assert a_view["live"] is True
    assert b_view["live"] is False


def test_tenant_write_never_mutates_os_environ(env):
    """The core leak test: a tenant write must not touch the shared process env.

    Asserted as a DELTA, not an absolute: another test in the session may legitimately have left
    OPENAI_API_KEY set (e.g. an admin-plane ``apply_to_env``), and the invariant we care about is
    that *this* tenant write changes nothing — which must hold whatever the starting value was.
    """
    client, _ks, _cfg = env
    before = os.environ.get("OPENAI_API_KEY")
    client.post("/api/providers/openai", json={"api_key": "sk-TENANTKEY"}, headers=_tenant("aaa"))
    assert os.environ.get("OPENAI_API_KEY") == before   # unchanged → no cross-tenant leak
    assert os.environ.get("OPENAI_API_KEY") != "sk-TENANTKEY"


def test_tenant_write_lands_in_isolated_file(env):
    client, ks, cfg = env
    client.post("/api/providers/openai", json={"api_key": "sk-AAAA1234"}, headers=_tenant("aaa"))
    # "v_" marks the verbatim namespace — kept disjoint from the "h_" hashed one so the two can
    # never name the same directory (see test_safe_tenant_namespaces_cannot_collide).
    assert (cfg / "tenants" / "v_aaa" / "provider_keys.json.enc").exists()
    assert not (cfg / "tenants" / "v_bbb").exists()
    assert ks.load(tenant="bbb") == {}                 # B's store is empty
    assert "openai" in ks.load(tenant="aaa")


def test_admin_plane_uses_global_store_not_tenant(env):
    client, ks, _cfg = env
    r = client.post("/api/providers/openai", json={"api_key": "sk-GLOBAL99"}, headers=_ADMIN)
    assert r.status_code == 200
    assert "openai" in ks.load()                       # admin writes the global store
    # a tenant still sees nothing (admin's global key is not exposed to tenants)
    assert _openai_view(client.get("/api/providers", headers=_tenant("aaa")).get_json())["has_key"] is False
    # clean up any env the admin apply_to_env set, so the test leaves no residue
    os.environ.pop("OPENAI_API_KEY", None)


def test_tenant_can_live_test_own_key(env):
    client, _ks, _cfg = env
    client.post("/api/providers/openai", json={"api_key": "sk-AAAA1234"}, headers=_tenant("aaa"))
    r = client.post("/api/providers/openai/test", json={}, headers=_tenant("aaa"))
    assert r.status_code == 200
    body = r.get_json()
    assert set(body) >= {"ok", "latency_ms", "model"}   # an honest verdict, not a 500


def test_tenant_unified_connection_test_preserves_account_scope(env, monkeypatch):
    client, _ks, _cfg = env
    import aureon.operator.operator_server as srv

    observed = {}

    def fake_test(info, api_key, base_url, model, *, provider_id, tenant=None):
        observed.update({
            "provider_id": provider_id,
            "tenant": tenant,
            "api_key": api_key,
            "model": model,
        })
        return {"ok": True, "latency_ms": 1, "model": model}

    monkeypatch.setattr(srv, "_test_provider_adapter", fake_test)
    response = client.post(
        "/api/connections/openai/test",
        json={"api_key": "tenant-route-test-key", "model": "tenant-route-test-model"},
        headers=_tenant("aaa"),
    )

    assert response.status_code == 200
    assert response.get_json()["ok"] is True
    assert observed == {
        "provider_id": "openai",
        "tenant": "aaa",
        "api_key": "tenant-route-test-key",
        "model": "tenant-route-test-model",
    }


# ── per-tenant live reasoning ────────────────────────────────────────────────────

def test_tenant_without_key_gets_honest_keyless_reply(env):
    # A signed-in user with no model of their own is answered honestly — NEVER the
    # instance's models — on both reasoning entrypoints.
    client, _ks, _cfg = env
    for path in ("/api/cognition/reason", "/api/operator/respond"):
        r = client.post(path, json={"prompt": "hello"}, headers=_tenant("nokey"))
        assert r.status_code == 200
        assert r.get_json().get("tenant_no_key") is True


def test_tenant_with_key_reasons_on_own_model(env):
    # After connecting a local model, the tenant reasons on THEIR engine (no keyless
    # fallback), and no key leaks into the process env.
    client, _ks, _cfg = env
    before = os.environ.get("OLLAMA_API_KEY")
    client.post("/api/providers/ollama",
                json={"api_key": "tok", "base_url": "https://ollama.com/v1", "model": "llama3"},
                headers=_tenant("aaa"))
    r = client.post("/api/cognition/reason", json={"prompt": "say OK"}, headers=_tenant("aaa"))
    assert r.status_code == 200
    j = r.get_json()
    assert not j.get("tenant_no_key")                    # the tenant engine answered
    assert j.get("text")
    # delta, not absolute (see test_tenant_write_never_mutates_os_environ)
    assert os.environ.get("OLLAMA_API_KEY") == before     # no env leak from reasoning
    assert os.environ.get("OLLAMA_API_KEY") != "tok"


@pytest.mark.parametrize(
    "url",
    (
        "http://169.254.169.254/computeMetadata/v1/",
        "http://127.0.0.1:8080/v1",
        "http://10.1.2.3/v1",
        "https://example.invalid/v1",
        "https://api.openai.com/v1?next=http://metadata.google.internal/",
        "https://api.openai.com@169.254.169.254/v1",
    ),
)
def test_tenant_direct_provider_url_is_rejected_before_storage(env, url):
    client, ks, _cfg = env

    response = client.post(
        "/api/providers/openai",
        json={"api_key": "tenant-key", "base_url": url},
        headers=_tenant("ssrf-direct"),
    )

    assert response.status_code == 400
    assert ks.load("ssrf-direct") == {}


def test_tenant_unified_connection_url_is_pinned_to_catalog(env):
    client, ks, _cfg = env

    rejected = client.post(
        "/api/connections/openai",
        json={"api_key": "tenant-key", "base_url": "http://192.168.1.4/v1"},
        headers=_tenant("ssrf-connection"),
    )
    accepted = client.post(
        "/api/connections/openai",
        json={"api_key": "tenant-key", "base_url": "https://api.openai.com/v1/"},
        headers=_tenant("ssrf-connection"),
    )

    assert rejected.status_code == 400
    assert accepted.status_code == 200
    assert ks.load("ssrf-connection")["openai"]["base_url"] == "https://api.openai.com/v1"


def test_tenant_byok_remains_writable_when_owner_cloud_secrets_are_pinned(env, monkeypatch):
    client, ks, _cfg = env
    monkeypatch.setenv(
        ks.PINNED_ENV_VARS_ENV,
        "NASA_API_KEY,NOAA_API_KEY,USGS_API_KEY,OLLAMA_API_KEY,AUREON_LLM_BASE_URL,AUREON_LLM_MODEL",
    )
    monkeypatch.setenv("AUREON_CLOUD_EXCHANGE_CREDENTIALS_PINNED", "1")
    headers = _tenant("pinned-owner-byo-tenant")

    assert client.post(
        "/api/providers/ollama",
        json={"api_key": "tenant-ollama", "base_url": "https://ollama.com/v1"},
        headers=headers,
    ).status_code == 200
    assert client.post(
        "/api/connections/nasa", json={"api_key": "tenant-nasa"}, headers=headers,
    ).status_code == 200
    assert client.post(
        "/api/connections/binance",
        json={"api_key": "tenant-binance", "extra": {"BINANCE_API_SECRET": "tenant-secret"}},
        headers=headers,
    ).status_code == 200

    stored = ks.load("pinned-owner-byo-tenant")
    assert stored["ollama"]["api_key"] == "tenant-ollama"
    assert stored["nasa"]["api_key"] == "tenant-nasa"
    assert stored["binance"]["api_key"] == "tenant-binance"


def test_tenant_exchange_test_uses_only_its_stored_catalog_fields(env, monkeypatch):
    client, ks, _cfg = env
    import aureon.operator.connections_api as connections_api

    headers = _tenant("exchange-test-a")
    assert client.post(
        "/api/connections/binance",
        json={
            "api_key": "tenant-binance-primary",
            "extra": {"BINANCE_API_SECRET": "tenant-binance-secondary"},
        },
        headers=headers,
    ).status_code == 200
    observed = {}

    class Probe:
        def authenticate(self, venue, values):
            observed.update(venue=venue, values=dict(values))
            return {
                "ok": True,
                "authenticated": True,
                "http_status": 200,
                "latency_ms": 1,
                "error": "",
                "reason_code": "exchange_authenticated",
                "probe_scope": "credential",
                "provider_mutation_attempted": False,
            }

    monkeypatch.setattr(connections_api, "TenantExchangeProbe", Probe)
    response = client.post(
        "/api/connections/binance/test", json={}, headers=headers,
    )

    assert response.status_code == 200 and response.get_json()["authenticated"] is True
    assert observed == {
        "venue": "binance",
        "values": {
            "BINANCE_API_KEY": "tenant-binance-primary",
            "BINANCE_API_SECRET": "tenant-binance-secondary",
        },
    }
    assert ks.load("exchange-test-a")["binance"]["api_key"] == "tenant-binance-primary"


def test_tenant_exchange_test_never_falls_back_to_owner_environment(env, monkeypatch):
    client, _ks, _cfg = env
    import aureon.operator.connections_api as connections_api

    monkeypatch.setenv("BINANCE_API_KEY", "owner-primary-must-not-be-used")
    monkeypatch.setenv("BINANCE_API_SECRET", "owner-secondary-must-not-be-used")
    observed = {}

    class Probe:
        def authenticate(self, venue, values):
            observed.update(venue=venue, values=dict(values))
            return {
                "ok": False,
                "authenticated": False,
                "http_status": 0,
                "latency_ms": 0,
                "error": "exchange_credentials_incomplete",
                "reason_code": "exchange_credentials_incomplete",
                "probe_scope": "credential",
                "provider_mutation_attempted": False,
            }

    monkeypatch.setattr(connections_api, "TenantExchangeProbe", Probe)
    response = client.post(
        "/api/connections/binance/test", json={}, headers=_tenant("exchange-test-empty"),
    )

    assert response.status_code == 200
    assert response.get_json()["reason_code"] == "exchange_credentials_incomplete"
    assert observed == {"venue": "binance", "values": {}}
    assert "owner-primary" not in response.get_data(as_text=True)
    assert "owner-secondary" not in response.get_data(as_text=True)


@pytest.mark.parametrize("path", ["/api/connections/binance", "/api/connections/binance/test"])
def test_tenant_exchange_payload_rejects_unknown_or_malformed_fields_before_storage_or_probe(
    env, monkeypatch, path
):
    client, ks, _cfg = env
    import aureon.operator.connections_api as connections_api

    called = False

    class Probe:
        def authenticate(self, *_args, **_kwargs):
            nonlocal called
            called = True
            raise AssertionError("invalid payload reached provider probe")

    monkeypatch.setattr(connections_api, "TenantExchangeProbe", Probe)
    headers = _tenant("exchange-invalid")
    attempts = (
        {"api_key": "value", "extra": {"UNDECLARED": "value"}},
        {"api_key": "value", "extra": {"BINANCE_API_SECRET": "bad\r\nvalue"}},
        {"api_key": ["not", "text"], "extra": {"BINANCE_API_SECRET": "value"}},
        {"api_key": "value", "unexpected": "value"},
    )
    for payload in attempts:
        response = client.post(path, json=payload, headers=headers)
        assert response.status_code == 400
        assert response.get_json()["error"]["reason_code"].startswith("connection_")
    assert called is False
    assert ks.load("exchange-invalid") == {}


def test_tenant_connection_delete_is_subject_isolated_and_llm_delete_path_remains(env):
    client, ks, _cfg = env
    for tenant, suffix in (("delete-a", "a"), ("delete-b", "b")):
        headers = _tenant(tenant)
        assert client.post(
            "/api/connections/binance",
            json={
                "api_key": f"binance-{suffix}",
                "extra": {"BINANCE_API_SECRET": f"binance-secondary-{suffix}"},
            },
            headers=headers,
        ).status_code == 200
        assert client.post(
            "/api/connections/openai",
            json={"api_key": f"openai-{suffix}"},
            headers=headers,
        ).status_code == 200

    deleted = client.delete("/api/connections/binance", headers=_tenant("delete-a"))
    llm_deleted = client.delete("/api/providers/openai", headers=_tenant("delete-a"))

    assert deleted.status_code == 200 and deleted.get_json() == {
        "ok": True, "connection_id": "binance", "disconnected": True,
    }
    assert llm_deleted.status_code == 200
    assert "binance" not in ks.load("delete-a") and "openai" not in ks.load("delete-a")
    assert ks.load("delete-b")["binance"]["api_key"] == "binance-b"
    assert ks.load("delete-b")["openai"]["api_key"] == "openai-b"


def test_undeclared_stored_exchange_field_is_rejected_until_tenant_disconnects(env, monkeypatch):
    client, ks, _cfg = env
    import aureon.operator.connections_api as connections_api

    tenant = "legacy-extra"
    ks.save_provider(
        "binance",
        api_key="tenant-primary",
        extra={
            "BINANCE_API_SECRET": "tenant-secondary",
            "LEGACY_UNDECLARED_FIELD": "must-not-reach-transport",
        },
        tenant=tenant,
    )
    called = False

    class Probe:
        def authenticate(self, *_args, **_kwargs):
            nonlocal called
            called = True
            raise AssertionError("undeclared stored field reached transport")

    monkeypatch.setattr(connections_api, "TenantExchangeProbe", Probe)
    response = client.post(
        "/api/connections/binance/test", json={}, headers=_tenant(tenant),
    )

    assert response.status_code == 400
    assert response.get_json()["error"]["reason_code"] == "connection_credential_store_invalid"
    assert called is False
    assert client.delete(
        "/api/connections/binance", headers=_tenant(tenant),
    ).status_code == 200
    assert "binance" not in ks.load(tenant)


def test_persisted_tenant_url_is_rejected_before_provider_test(env, monkeypatch):
    client, ks, _cfg = env
    import aureon.operator.operator_server as srv

    ks.save_provider(
        "openai",
        api_key="tenant-key",
        base_url="http://metadata.google.internal/computeMetadata/v1/",
        tenant="ssrf-persisted",
    )

    called = False

    def must_not_run(*args, **kwargs):  # noqa: ANN002, ANN003
        nonlocal called
        called = True
        raise AssertionError("provider adapter must not receive a persisted custom URL")

    monkeypatch.setattr(srv, "_test_provider_adapter", must_not_run)
    response = client.post(
        "/api/providers/openai/test",
        json={},
        headers=_tenant("ssrf-persisted"),
    )

    assert response.status_code == 400
    assert called is False


def test_persisted_custom_url_cannot_enter_tenant_reasoning_provider_set():
    from aureon.operator.provider_catalog import get_provider
    from aureon.operator.providers import (
        build_provider_set_from_entries,
        tenant_provider_base_url,
    )

    assert tenant_provider_base_url(get_provider("ollama")) == "https://ollama.com/v1"
    providers = build_provider_set_from_entries(
        {
            "openai": {
                "api_key": "tenant-key",
                "base_url": "http://169.254.169.254/latest/meta-data/",
                "enabled": True,
            }
        },
        tenant_mode=True,
    )
    assert providers == {}


def test_tenant_provider_transport_rejects_redirects_and_proxies():
    from aureon.operator import providers

    class Response:
        status_code = 200
        is_redirect = False
        is_permanent_redirect = False
        history = ()

    class Session:
        trust_env = True
        proxies = {"https": "http://ambient-proxy.invalid"}
        max_redirects = 30

        def __init__(self):
            self.kwargs = None
            self.redirect = False

        def request(self, method, url, **kwargs):  # noqa: ANN001
            self.kwargs = kwargs
            response = Response()
            if self.redirect:
                response.status_code = 302
                response.is_redirect = True
            return response

        def post(self, url, **kwargs):  # noqa: ANN001
            return self.request("POST", url, **kwargs)

    adapter = type("Adapter", (), {"_session": Session()})()
    providers._harden_tenant_transport(adapter)
    assert adapter._session.trust_env is False
    assert adapter._session.proxies == {}
    assert adapter._session.max_redirects == 0

    adapter._session.post("https://api.openai.com/v1/chat/completions")
    assert adapter._session.kwargs["allow_redirects"] is False
    assert adapter._session.kwargs["proxies"] == {}
    with pytest.raises(RuntimeError, match="redirects_forbidden"):
        adapter._session.post(
            "https://api.openai.com/v1/chat/completions", allow_redirects=True
        )
    with pytest.raises(RuntimeError, match="proxy_forbidden"):
        adapter._session.post(
            "https://api.openai.com/v1/chat/completions",
            proxies={"https": "http://proxy.invalid"},
        )
    adapter._session.redirect = True
    with pytest.raises(RuntimeError, match="redirect_rejected"):
        adapter._session.post("https://api.openai.com/v1/chat/completions")


def test_gemini_key_is_header_only_and_transport_error_is_sanitized(monkeypatch, caplog):
    from aureon.operator.providers import AureonGeminiAdapter

    canary = "GEMINI-CANARY-SECRET-123456"
    observed = {}

    class FailingSession:
        def post(self, url, **kwargs):  # noqa: ANN001
            observed.update({"url": url, "headers": kwargs.get("headers", {})})
            raise RuntimeError(f"transport echoed {canary}")

    adapter = AureonGeminiAdapter(api_key=canary)
    adapter._session = FailingSession()
    monkeypatch.delenv("AUREON_LLM_OFFLINE", raising=False)
    monkeypatch.delenv("AUREON_AUDIT_MODE", raising=False)
    monkeypatch.delenv("AUREON_DISABLE_LLM_HTTP", raising=False)
    with caplog.at_level(logging.ERROR, logger="aureon.operator.providers"):
        result = adapter.prompt([{"role": "user", "content": "OK"}])

    assert "?key=" not in observed["url"]
    assert canary not in observed["url"]
    assert observed["headers"]["x-goog-api-key"] == canary
    assert canary not in result.text
    assert canary not in caplog.text


def test_provider_test_canary_never_enters_response_receipt_or_logs(env, monkeypatch, caplog):
    client, ks, _cfg = env
    from aureon.inhouse_ai.llm_adapter import LLMResponse
    from aureon.operator import providers

    canary = "PROVIDER-TEST-CANARY-SECRET-987654"
    client.post(
        "/api/providers/gemini",
        json={"api_key": canary},
        headers=_tenant("canary-tenant"),
    )

    class EchoingAdapter:
        def prompt(self, *args, **kwargs):  # noqa: ANN002, ANN003
            return LLMResponse(
                text=f"[ERROR] upstream URL contained {canary}", stop_reason="error"
            )

    monkeypatch.setattr(providers, "build_adapter", lambda *args, **kwargs: EchoingAdapter())
    with caplog.at_level(logging.WARNING):
        response = client.post(
            "/api/providers/gemini/test",
            json={},
            headers=_tenant("canary-tenant"),
        )

    payload_text = response.get_data(as_text=True)
    stored = ks.load("canary-tenant")["gemini"]
    assert response.status_code == 200
    assert canary not in payload_text
    assert stored["last_test_error"] == "provider_test_failed"
    assert canary not in stored["last_test_error"]
    assert canary.encode() not in ks._store_path("canary-tenant").read_bytes()
    assert canary not in caplog.text


def test_tenant_reasoning_is_isolated(env):
    # A connects a model; B (no key) still gets the honest keyless reply — never A's engine.
    client, _ks, _cfg = env
    client.post("/api/providers/ollama", json={"api_key": "tok"}, headers=_tenant("aaa"))
    rb = client.post("/api/cognition/reason", json={"prompt": "hi"}, headers=_tenant("bbb"))
    assert rb.get_json().get("tenant_no_key") is True


def test_admin_reasoning_uses_shared_engine(env):
    # The admin/global plane reasons on the instance engine exactly as before — no
    # tenant scoping, no keyless gate.
    client, _ks, _cfg = env
    r = client.post("/api/cognition/reason", json={"prompt": "say OK"}, headers=_ADMIN)
    assert r.status_code == 200
    assert not r.get_json().get("tenant_no_key")


# ── keystore unit isolation ─────────────────────────────────────────────────────

def test_keystore_tenant_isolation_unit(tmp_path, monkeypatch):
    import aureon.operator.keystore as ks

    importlib.reload(ks)
    cfg = tmp_path / ".aureon"
    monkeypatch.setattr(ks, "CONFIG_DIR", cfg)
    monkeypatch.setattr(ks, "KEY_PATH", cfg / "provider_keys.key")
    monkeypatch.setattr(ks, "STORE_PATH", cfg / "provider_keys.json.enc")
    monkeypatch.setattr(ks, "TENANTS_DIR", cfg / "tenants")

    ks.save_provider("openai", api_key="sk-aaa", tenant="aaa")
    assert ks.load(tenant="bbb") == {}
    assert ks.load() == {}                              # global untouched by a tenant write
    assert ks.load(tenant="aaa")["openai"]["api_key"] == "sk-aaa"


def test_safe_tenant_defends_against_traversal():
    import aureon.operator.keystore as ks

    safe = ks._safe_tenant("../../etc/evil")
    assert "/" not in safe and ".." not in safe
    assert safe.startswith("h_") and len(safe) == 66     # hashed, not the raw path


def test_safe_tenant_namespaces_cannot_collide():
    """The verbatim and hashed forms must live in disjoint namespaces.

    A SHA-256 hex digest itself satisfies the verbatim whitelist. Without distinct prefixes, a tenant
    whose ``sub`` happens to be the digest of another tenant's crafted ``sub`` would be handed that
    tenant's store — reading their keys and hijacking their rotations.
    """
    import hashlib

    import aureon.operator.keystore as ks

    crafted = "../../etc/evil"
    digest = hashlib.sha256(crafted.encode("utf-8")).hexdigest()
    assert ks._safe_tenant(digest) != ks._safe_tenant(crafted)
    # and the two forms are separable by construction, for every input
    assert ks._safe_tenant(digest).startswith("v_")
    assert ks._safe_tenant(crafted).startswith("h_")


# ── backward compatibility (no secrets ⇒ open) ──────────────────────────────────

def test_open_mode_unchanged(tmp_path, monkeypatch):
    monkeypatch.setenv("AUREON_LLM_OFFLINE", "1")
    monkeypatch.setenv("AUREON_SUPPRESS_IMPORT_SIDE_EFFECTS", "1")
    monkeypatch.delenv("AUREON_SUPABASE_JWT_SECRET", raising=False)
    monkeypatch.delenv("AUREON_OPERATOR_API_KEY", raising=False)

    import aureon.operator.operator_server as srv

    importlib.reload(srv)
    c = srv.create_app(
        test_ingress_release=srv.TestOnlyOperatorIngressRelease(
            master_key=b"operator-open-mode-route-test-key-material",
        )
    ).test_client()
    # open: no auth needed, and a stray JWT header is simply ignored (no tenant scoping)
    assert c.get("/api/providers").status_code == 200
    assert c.get("/api/providers", headers=_tenant("aaa")).status_code == 200


# ── concurrency: a tenant's store must survive simultaneous writes ─────────────

def test_concurrent_saves_for_one_tenant_do_not_lose_writes(tmp_path, monkeypatch):
    """``save_provider`` is read-modify-write over the WHOLE store, so without a lock two concurrent
    saves race and the loser's provider is silently dropped.

    Reproduced before the fix: 24 threads saving two different providers for one tenant left exactly
    ONE provider stored. A user connecting two models at once would lose one, with no error.
    """
    import threading

    import aureon.operator.keystore as ks

    importlib.reload(ks)
    cfg = tmp_path / ".aureon"
    monkeypatch.setattr(ks, "CONFIG_DIR", cfg)
    monkeypatch.setattr(ks, "KEY_PATH", cfg / "provider_keys.key")
    monkeypatch.setattr(ks, "STORE_PATH", cfg / "provider_keys.json.enc")
    monkeypatch.setattr(ks, "TENANTS_DIR", cfg / "tenants")

    errors: list = []

    def writer(i: int) -> None:
        try:
            ks.save_provider("openai" if i % 2 else "ollama", api_key=f"key-{i}", tenant="aaa")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{type(exc).__name__}: {exc}")

    threads = [threading.Thread(target=writer, args=(i,)) for i in range(24)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"concurrent saves raised: {errors[:3]}"
    stored = ks.load(tenant="aaa")
    assert set(stored) == {"openai", "ollama"}, f"a concurrent save was lost: kept {sorted(stored)}"


def test_a_torn_store_write_cannot_silently_empty_the_keystore(tmp_path, monkeypatch):
    """``_persist`` must be atomic. A partial Fernet token cannot be decrypted, and ``load`` reports
    an unreadable store as ``{}`` — so a torn write does not raise, it silently empties the store, and
    the next save then persists only its own entry, making the loss permanent.

    Asserts the write leaves no half-written file behind under the real store name, and that a
    temp-file crash is recoverable (the previous store is still intact).
    """
    import aureon.operator.keystore as ks

    importlib.reload(ks)
    cfg = tmp_path / ".aureon"
    monkeypatch.setattr(ks, "CONFIG_DIR", cfg)
    monkeypatch.setattr(ks, "KEY_PATH", cfg / "provider_keys.key")
    monkeypatch.setattr(ks, "STORE_PATH", cfg / "provider_keys.json.enc")
    monkeypatch.setattr(ks, "TENANTS_DIR", cfg / "tenants")

    ks.save_provider("openai", api_key="sk-first", tenant="aaa")
    path = ks._store_path("aaa")
    before = path.read_bytes()

    # A write that dies partway must not touch the live store.
    real_replace = os.replace

    def _boom(src, dst):  # noqa: ANN001
        raise OSError("simulated crash between temp write and rename")

    monkeypatch.setattr(os, "replace", _boom)
    with pytest.raises(OSError):
        ks.save_provider("ollama", api_key="sk-second", tenant="aaa")
    monkeypatch.setattr(os, "replace", real_replace)

    assert path.read_bytes() == before               # the live store is untouched
    assert ks.load(tenant="aaa")["openai"]["api_key"] == "sk-first"   # and still decrypts
    leftovers = [p.name for p in path.parent.iterdir() if p.name.endswith(".tmp")]
    assert not leftovers, f"temp files left behind: {leftovers}"
