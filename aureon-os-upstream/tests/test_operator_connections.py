"""
Aureon Operator — unified connections tests.

Catalog completeness, the full-capacity readiness report, and the
/api/connections surface: masked reads with no key leak, keyless probe verdicts,
data-source key set via keystore, exchange writes DELEGATED (never stored in the
operator keystore), and the bearer gate. Offline, no network.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import pathlib
import tempfile

import pytest

pytest.importorskip("flask", reason="operator HTTP surface requires the `.[operator]` extra")
pytest.importorskip("cryptography", reason="keystore requires cryptography (Fernet)")

from aureon.operator import connections_api, keystore  # noqa: E402
from aureon.operator import connections_catalog as cat  # noqa: E402


@pytest.fixture()
def temp_store(monkeypatch):
    tmp = pathlib.Path(tempfile.mkdtemp())
    monkeypatch.setattr(keystore, "CONFIG_DIR", tmp)
    monkeypatch.setattr(keystore, "KEY_PATH", tmp / "provider_keys.key")
    monkeypatch.setattr(keystore, "STORE_PATH", tmp / "provider_keys.json.enc")
    monkeypatch.setattr(keystore, "TENANTS_DIR", tmp / "tenants")
    # Isolate os.environ: apply_to_env() writes real env vars, and importing the
    # aureon package loads any local .env — snapshot and restore so tests don't
    # leak keys into one another (or read the developer's .env).
    import os as _os
    saved = dict(_os.environ)
    for var in (
        keystore.managed_env_vars()
        + [c.key_env for c in cat.CATALOG if c.key_env]
        + [keystore.PINNED_ENV_VARS_ENV, connections_api.CLOUD_EXCHANGE_CREDENTIALS_PINNED_ENV]
    ):
        _os.environ.pop(var, None)
    yield tmp
    _os.environ.clear()
    _os.environ.update(saved)


def _client():
    import aureon.operator.operator_server as srv

    importlib.reload(srv)
    return srv.create_app(
        test_ingress_release=srv.TestOnlyOperatorIngressRelease(
            master_key=b"operator-connections-route-test-key-material",
        )
    ).test_client()


# ── catalog ─────────────────────────────────────────────────────────────────

def test_catalog_spans_all_categories():
    cat_ids = {c.category for c in cat.CATALOG}
    for expected in ("exchange", "market_data", "space_science", "ephemeris",
                     "onchain_whale", "news_social", "notifications"):
        assert expected in cat_ids
    # keyed sources declare a credential env; keyless declare none
    for c in cat.CATALOG:
        if c.requirement == "keyless":
            assert not c.credential_env
        else:
            assert c.credential_env


def test_key_sources_have_get_keys_links():
    for c in cat.CATALOG:
        if c.requirement != "keyless":
            assert c.get_keys_url.startswith("http")


# ── readiness ─────────────────────────────────────────────────────────────────

def test_readiness_report_shape(temp_store):
    r = connections_api.readiness(llm_providers=[])
    s = r["summary"]
    assert {"capacity_pct", "keyed_present", "keyed_total", "all_connected",
            "missing_count", "keyless"} <= set(s)
    assert isinstance(r["missing"], list)
    # internally consistent regardless of which keys happen to be present
    assert s["keyed_total"] > 0
    assert 0 <= s["keyed_present"] <= s["keyed_total"]
    assert s["missing_count"] == s["keyed_total"] - s["keyed_present"]


def test_readiness_counts_a_saved_key(temp_store):
    keystore.save_provider("nasa", api_key="NASA-KEY-1234")
    r = connections_api.readiness(llm_providers=[])
    nasa = next(i for i in r["items"] if i["id"] == "nasa")
    assert nasa["present"] is True
    assert r["summary"]["keyed_present"] >= 1


def _executor_control(*, current=True):
    providers = {
        venue: {"authenticated": True, "account_binding_sha256": index * 64}
        for venue, index in zip(("alpaca", "binance", "capital", "kraken"), "1234", strict=True)
    }
    signed_rows = {venue: {"venue": venue, **row} for venue, row in providers.items()}
    provider_accounts_sha256 = hashlib.sha256(json.dumps(
        signed_rows, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode()).hexdigest()
    execution_budget_readiness_sha256 = "a" * 64
    readback = hashlib.sha256(json.dumps({
        "schema": "aureon.cloud-trade-provider-readback-commitment.v1",
        "provider_accounts_sha256": provider_accounts_sha256,
        "execution_budget_readiness_sha256": execution_budget_readiness_sha256,
    }, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
    return {
        "schema": "aureon.operator.cloud-trading-control.v1",
        "read_state": "observed" if current else "recorded",
        "capabilities": {"all_four_provider_readback_pinned": True},
        "last_probe": {
            "current": current,
            "received_at": 1_000.0,
            "provider_readback": {
                "provider_count": 4,
                "all_authenticated": True,
                "instrument_preflight_enforced": True,
                "provider_accounts_sha256": provider_accounts_sha256,
                "execution_budget_readiness_sha256": execution_budget_readiness_sha256,
                "readback_sha256": readback,
                "providers": providers,
            },
        },
    }


def test_owner_view_reports_current_cloud_executor_auth_without_inventing_key_presence(temp_store):
    control = _executor_control()
    provider = control["last_probe"]["provider_readback"]
    signed_rows = {
        venue: {"venue": venue, **row}
        for venue, row in provider["providers"].items()
    }
    account_rows_sha256 = hashlib.sha256(json.dumps(
        signed_rows, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode()).hexdigest()
    assert provider["readback_sha256"] != account_rows_sha256
    view = connections_api.build_view([], executor_control=control)
    exchanges = next(row for row in view["categories"] if row["category"] == "exchange")
    assert {row["id"] for row in exchanges["connections"] if row["executor_authenticated"]} == {
        "alpaca", "binance", "capital", "kraken",
    }
    assert all(row["has_key"] is False for row in exchanges["connections"])
    assert {
        row["executor_readback_sha256"] for row in exchanges["connections"]
    } == {provider["readback_sha256"]}
    summary = connections_api.readiness([], executor_control=control)["summary"]
    assert summary["executor_authenticated"] == 4
    assert summary["executor_evidence_current"] is True
    readiness = connections_api.readiness([], executor_control=control)
    exchange_items = [row for row in readiness["items"] if row["category"] == "exchange"]
    assert all(row["present"] is True for row in exchange_items)
    assert all(row["presence_basis"] == "signed_executor_readback" for row in exchange_items)
    assert not {row["id"] for row in readiness["missing"]} & {
        "alpaca", "binance", "capital", "kraken",
    }


@pytest.mark.parametrize("field,value", (
    ("provider_accounts_sha256", "0" * 64),
    ("execution_budget_readiness_sha256", "not-a-digest"),
    ("readback_sha256", "0" * 64),
))
def test_owner_view_rejects_tampered_collector_provider_commitments(temp_store, field, value):
    control = _executor_control()
    control["last_probe"]["provider_readback"][field] = value

    view = connections_api.build_view([], executor_control=control)
    exchanges = next(row for row in view["categories"] if row["category"] == "exchange")

    assert all(row["executor_authenticated"] is False for row in exchanges["connections"])


def test_tenant_and_stale_views_do_not_inherit_owner_executor_authentication(temp_store):
    for tenant, control in (("tenant-a", _executor_control()), (None, _executor_control(current=False))):
        view = connections_api.build_view([], tenant=tenant, executor_control=control)
        exchanges = next(row for row in view["categories"] if row["category"] == "exchange")
        assert all(row["executor_authenticated"] is False for row in exchanges["connections"])


def test_tenant_readiness_does_not_read_instance_probe_receipt(temp_store, monkeypatch):
    def leaked_instance_probe():
        raise AssertionError("tenant readiness read the owner instance probe")

    monkeypatch.setattr(connections_api, "_real_data_policy_summary", leaked_instance_probe)
    report = connections_api.readiness([], tenant="tenant-a")

    assert report["runtime_context"] == {
        "workspace_scope": "tenant_account",
        "credential_scope": "account",
        "execution_state": "held",
        "owner_runtime_read": False,
        "owner_runtime_control": False,
        "owner_runtime_session_effect": "none",
        "order_submission_enabled": False,
    }
    policy = report["summary"]["real_data_policy"]
    assert policy["probe_report_status"] == "account_unprobed"
    assert policy["probe_report_path"] == ""
    assert policy["probe_summary"]["operational_ready"] == 0
    assert policy["probe_summary"]["blocked"] == 1
    assert report["summary"]["core_ready"] is False
    assert report["summary"]["all_connected"] is False
    assert report["summary"]["executor_evidence_current"] is False
    assert report["summary"]["operational_ready"] is False
    assert report["summary"]["readiness_basis"] == "account_credentials_only"


def test_empty_tenant_spelling_cannot_alias_the_owner_store(temp_store):
    keystore.save_provider("coinapi", api_key="owner-only")

    assert keystore.load(tenant="") == {}
    tenant_view = connections_api.build_view([], tenant="")
    coinapi = next(
        row
        for section in tenant_view["categories"]
        for row in section["connections"]
        if row["id"] == "coinapi"
    )
    assert coinapi["has_key"] is False
    assert tenant_view["runtime_context"]["workspace_scope"] == "tenant_account"


# ── /api/connections surface ───────────────────────────────────────────────────

def test_connections_list_categorized_and_masked(temp_store):
    c = _client()
    c.post("/api/connections/coinapi", json={"api_key": "coin-SECRET-9999"})
    r = c.get("/api/connections")
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert "coin-SECRET-9999" not in body            # never leak the full key
    cats = {s["category"] for s in r.get_json()["categories"]}
    assert {"ai_llm", "exchange", "space_science", "onchain_whale"} <= cats
    coinapi = next(x for s in r.get_json()["categories"] for x in s["connections"] if x["id"] == "coinapi")
    assert coinapi["has_key"] is True and coinapi["key_masked"].endswith("9999")


def test_unified_llm_test_preserves_provider_and_admin_scope(temp_store, monkeypatch):
    import aureon.operator.operator_server as srv

    c = _client()
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
    response = c.post(
        "/api/connections/openai/test",
        json={"api_key": "route-test-key", "model": "route-test-model"},
    )

    assert response.status_code == 200
    assert response.get_json()["ok"] is True
    assert observed == {
        "provider_id": "openai",
        "tenant": None,
        "api_key": "route-test-key",
        "model": "route-test-model",
    }


def test_set_data_source_persists_to_keystore(temp_store):
    c = _client()
    r = c.post("/api/connections/firms", json={"api_key": "firms-abc1234", "enabled": True})
    assert r.status_code == 200 and r.get_json()["ok"] is True
    assert "firms-abc1234" not in r.get_data(as_text=True)
    assert keystore.load().get("firms", {}).get("api_key") == "firms-abc1234"


def test_exchange_write_is_delegated_not_keystored(temp_store, monkeypatch):
    calls = {}

    def fake_set(conn, api_key, extra):
        calls["conn"] = conn.id
        return {"ok": True, "updated_keys": [conn.key_env], "restart_required": True}

    monkeypatch.setattr(connections_api, "set_exchange_credential", fake_set)
    c = _client()
    r = c.post("/api/connections/binance", json={"api_key": "bnkey", "extra": {"BINANCE_API_SECRET": "s"}})
    assert r.status_code == 200 and r.get_json()["ok"] is True
    assert calls.get("conn") == "binance"
    assert "binance" not in keystore.load()          # NOT stored in the operator keystore


def test_cloud_pinned_owner_rows_are_read_only_without_shadow_writes(temp_store, monkeypatch):
    keystore.save_provider("nasa", api_key="stale-shadow-nasa")
    keystore.save_provider(
        "binance",
        api_key="stale-shadow-binance-primary",
        extra={"BINANCE_API_SECRET": "stale-shadow-binance-secondary"},
    )
    keystore.save_provider(
        "ollama",
        api_key="stale-shadow-ollama",
        base_url="http://localhost:11434/v1",
        model="stale-shadow-model",
    )
    stored_before = keystore.load()
    pinned_fields = (
        "NASA_API_KEY,NOAA_API_KEY,USGS_API_KEY,OLLAMA_API_KEY,"
        "AUREON_LLM_BASE_URL,AUREON_LLM_MODEL"
    )
    monkeypatch.setenv(keystore.PINNED_ENV_VARS_ENV, pinned_fields)
    monkeypatch.setenv(connections_api.CLOUD_EXCHANGE_CREDENTIALS_PINNED_ENV, "1")
    monkeypatch.setenv("NASA_API_KEY", "owner-nasa-secret")
    monkeypatch.setenv("BINANCE_API_KEY", "owner-binance-primary-LEAK")
    monkeypatch.setenv("BINANCE_API_SECRET", "owner-binance-secondary-LEAK")
    monkeypatch.setenv("OLLAMA_API_KEY", "owner-ollama-secret")
    monkeypatch.setenv("AUREON_LLM_BASE_URL", "https://ollama.com/v1")
    monkeypatch.setenv("AUREON_LLM_MODEL", "gpt-oss:120b-cloud")

    delegated = False

    def must_not_delegate(*_args, **_kwargs):
        nonlocal delegated
        delegated = True
        raise AssertionError("pinned exchange write reached the legacy .env writer")

    monkeypatch.setattr(connections_api, "set_exchange_credential", must_not_delegate)
    client = _client()
    categories = client.get("/api/connections").get_json()["categories"]
    rows = {row["id"]: row for section in categories for row in section["connections"]}
    providers = {row["id"]: row for row in client.get("/api/providers").get_json()["providers"]}

    for provider_id in ("nasa", "noaa_cdo", "usgs_water", "binance"):
        assert rows[provider_id]["credential_management"] == "pinned_cloud_secret"
        assert rows[provider_id]["credential_writable"] is False
    assert providers["ollama"]["credential_management"] == "pinned_cloud_secret"
    assert providers["ollama"]["credential_writable"] is False
    assert providers["ollama"]["base_url"] == "https://ollama.com/v1"
    assert providers["ollama"]["model"] == "gpt-oss:120b-cloud"
    assert providers["ollama"]["key_source"] == "env"
    assert rows["nasa"]["key_source"] == "env"
    assert rows["binance"]["key_source"] == "none"
    assert rows["binance"]["key_masked"] == ""
    assert rows["binance"]["has_key"] is False
    rendered_connections = client.get("/api/connections").get_data(as_text=True)
    assert "shadow" not in rendered_connections
    assert "LEAK" not in rendered_connections

    attempts = (
        client.post("/api/connections/nasa", json={"api_key": "shadow-nasa"}),
        client.post("/api/connections/binance", json={"api_key": "shadow-binance"}),
        client.delete("/api/connections/binance"),
        client.post("/api/connections/ollama", json={"api_key": "shadow-ollama"}),
        client.post("/api/providers/ollama", json={"api_key": "shadow-ollama"}),
        client.delete("/api/providers/ollama"),
    )
    for response in attempts:
        assert response.status_code == 409
        error = response.get_json()["error"]
        assert error["error_id"] == connections_api.PINNED_CLOUD_SECRET_ERROR_ID
        assert error["credential_management"] == "pinned_cloud_secret"
    assert delegated is False
    assert keystore.load() == stored_before


def test_owner_exchange_test_uses_current_signed_executor_receipt_not_ui_keys(
    temp_store, monkeypatch
):
    import aureon.operator.operator_server as srv

    monkeypatch.setenv("BINANCE_API_KEY", "ui-owner-primary-must-not-be-used")
    monkeypatch.setenv("BINANCE_API_SECRET", "ui-owner-secondary-must-not-be-used")
    client = _client()
    monkeypatch.setattr(srv, "build_cloud_trading_control_receipt", _executor_control)

    def forbidden(*_args, **_kwargs):
        raise AssertionError("owner exchange test must not instantiate a tenant credential probe")

    monkeypatch.setattr(connections_api, "TenantExchangeProbe", forbidden)
    response = client.post(
        "/api/connections/binance/test",
        json={"api_key": "shadow-primary", "extra": {"BINANCE_API_SECRET": "shadow-secondary"}},
    )

    assert response.status_code == 200
    result = response.get_json()
    assert result["ok"] is True
    assert result["authenticated"] is True
    assert result["probe_scope"] == "signed_cloud_executor_receipt"
    assert result["provider_mutation_attempted"] is False
    rendered = response.get_data(as_text=True)
    for value in (
        "ui-owner-primary-must-not-be-used",
        "ui-owner-secondary-must-not-be-used",
        "shadow-primary",
        "shadow-secondary",
    ):
        assert value not in rendered


def test_owner_exchange_test_fails_closed_when_signed_executor_receipt_is_absent(
    temp_store, monkeypatch
):
    import aureon.operator.operator_server as srv

    client = _client()
    monkeypatch.setattr(srv, "build_cloud_trading_control_receipt", lambda: {})
    response = client.post("/api/connections/kraken/test", json={})

    assert response.status_code == 200
    assert response.get_json() == {
        "ok": False,
        "authenticated": False,
        "http_status": 0,
        "latency_ms": 0,
        "error": "cloud_executor_authentication_receipt_unavailable",
        "reason_code": "cloud_executor_authentication_receipt_unavailable",
        "probe_scope": "signed_cloud_executor_receipt",
        "provider_mutation_attempted": False,
    }


def test_unpinned_owner_provider_remains_writable_in_cloud_mode(temp_store, monkeypatch):
    monkeypatch.setenv(
        keystore.PINNED_ENV_VARS_ENV,
        "NASA_API_KEY,NOAA_API_KEY,USGS_API_KEY,OLLAMA_API_KEY,AUREON_LLM_BASE_URL,AUREON_LLM_MODEL",
    )
    monkeypatch.setenv(connections_api.CLOUD_EXCHANGE_CREDENTIALS_PINNED_ENV, "1")

    response = _client().post(
        "/api/connections/coinapi", json={"api_key": "optional-owner-key"},
    )

    assert response.status_code == 200
    assert keystore.load()["coinapi"]["api_key"] == "optional-owner-key"


def test_readiness_endpoint(temp_store):
    r = _client().get("/api/connections/readiness")
    assert r.status_code == 200
    assert "summary" in r.get_json() and "missing" in r.get_json()


def test_keyless_probe_needs_no_key():
    noaa = cat.get_connection("noaa_swpc")
    assert noaa is not None and noaa.requirement == "keyless"
    # keyed source without a key → verdict "no key", never an exception
    nasa = cat.get_connection("nasa")
    v = connections_api.probe(nasa, api_key="")
    assert v["ok"] is False and "no key" in v["error"]


@pytest.mark.parametrize(
    "provider_id,credential_location",
    [("coinapi", "header"), ("fred", "query"), ("covalent", "bearer")],
)
def test_generic_probe_disables_proxy_redirect_and_exception_disclosure(
    monkeypatch, provider_id, credential_location
):
    connection = cat.get_connection(provider_id)
    assert connection is not None
    observed = {}

    class Response:
        status_code = 302

        def close(self):
            observed["response_closed"] = True

    class Session:
        def __init__(self):
            self.trust_env = True

        def get(self, url, **kwargs):
            observed.update(url=url, kwargs=kwargs, trust_env=self.trust_env)
            return Response()

        def close(self):
            observed["session_closed"] = True

    import requests

    monkeypatch.setattr(requests, "Session", Session)
    result = connections_api.probe(connection, api_key="generic-probe-canary")

    assert result["reason_code"] == "probe_redirect_denied"
    assert "generic-probe-canary" not in json.dumps(result)
    assert observed["trust_env"] is False
    assert observed["kwargs"]["allow_redirects"] is False
    assert observed["kwargs"]["stream"] is True
    assert "proxies" not in observed["kwargs"]
    if credential_location == "header":
        assert "generic-probe-canary" in observed["kwargs"]["headers"].values()
    elif credential_location == "query":
        assert "generic-probe-canary" in observed["kwargs"]["params"].values()
    else:
        assert observed["kwargs"]["headers"]["Authorization"] == "Bearer generic-probe-canary"
    assert observed["response_closed"] is True
    assert observed["session_closed"] is True

    class ExplodingSession(Session):
        def get(self, *_args, **_kwargs):
            raise RuntimeError("exception contains generic-probe-canary")

    monkeypatch.setattr(requests, "Session", ExplodingSession)
    failure = connections_api.probe(connection, api_key="generic-probe-canary")
    assert failure["reason_code"] == "probe_transport_unavailable"
    assert "generic-probe-canary" not in json.dumps(failure)


def test_unknown_connection_404(temp_store):
    assert _client().post("/api/connections/nope", json={}).status_code == 404


def test_connection_writes_bearer_gated(temp_store, monkeypatch):
    monkeypatch.setenv("AUREON_OPERATOR_API_KEY", "sesame")
    c = _client()
    assert c.post("/api/connections/coinapi", json={"api_key": "x"}).status_code == 401
    ok = c.post("/api/connections/coinapi", json={"api_key": "coin-abc1234"},
                headers={"Authorization": "Bearer sesame"})
    assert ok.status_code == 200
