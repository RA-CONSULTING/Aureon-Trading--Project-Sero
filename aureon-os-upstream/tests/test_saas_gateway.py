"""
Aureon SaaS — gateway HTTP routes + Supabase JWT bridge.

Offline; skips when flask isn't installed (CI installs the operator extra).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import importlib
import json
import os
import time

import pytest

pytest.importorskip("flask", reason="SaaS gateway requires the `.[operator]` extra")

from aureon.saas.gateway import verify_supabase_jwt  # noqa: E402


def _app(**env):
    # Save-and-restore, never pop-blind: the suite exports AUREON_LLM_OFFLINE=1
    # process-wide, and popping it here deleted it for every LATER test module —
    # the soul's deterministic self-authorship (and anything else reading the
    # flag) silently switched to the live-LLM path mid-suite. Measured breaking
    # tests/test_soul.py from tests/test_saas_gateway.py::test_catalog_route.
    previous = {k: os.environ.get(k) for k in env}
    for k, v in env.items():
        os.environ[k] = v
    try:
        import aureon.operator.operator_server as srv

        importlib.reload(srv)
        return srv.create_app(
            test_ingress_release=srv.TestOnlyOperatorIngressRelease(
                master_key=b"saas-gateway-http-route-test-key-material",
            )
        ).test_client()
    finally:
        for k, v in previous.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def _mk_jwt(claims, secret):
    def b(d):
        return base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=").decode()
    h, p = b({"alg": "HS256", "typ": "JWT"}), b(claims)
    sig = base64.urlsafe_b64encode(
        hmac.new(secret.encode(), f"{h}.{p}".encode(), hashlib.sha256).digest()
    ).rstrip(b"=").decode()
    return f"{h}.{p}.{sig}"


# ── routes ────────────────────────────────────────────────────────────────────

def test_catalog_route():
    c = _app(AUREON_LLM_OFFLINE="1")
    r = c.get("/api/catalog")
    assert r.status_code == 200
    assert len(r.get_json()["categories"]) == 12


def test_domains_routes():
    c = _app(AUREON_LLM_OFFLINE="1")
    d = c.get("/api/domains").get_json()
    assert len(d["product_domains"]) == 6 and len(d["domains"]) >= 24
    one = c.get("/api/domains/trading").get_json()
    assert one["domain"] == "trading" and one["system_count"] >= 0


def test_status_route():
    c = _app(AUREON_LLM_OFFLINE="1")
    s = c.get("/api/status").get_json()
    assert s["status"] in {"healthy", "degraded", "critical"}


def test_manifests_refresh_route(tmp_path, monkeypatch):
    from aureon.saas import catalog

    # Exercise the real catalog scan, but keep every output in this test's
    # directory and never overwrite the release's static public manifests.
    monkeypatch.setattr(catalog, "_CATALOG_CACHE", tmp_path / "catalog.json")
    monkeypatch.setattr(catalog, "_FRONTEND_PUBLIC", tmp_path / "public")
    monkeypatch.setenv("AUREON_WRITE_STATIC_MANIFESTS", "0")
    c = _app(AUREON_LLM_OFFLINE="1")
    r = c.post("/api/manifests/refresh").get_json()
    assert r["refreshed"] is True
    assert set(r["manifests"]) == {"aureon_saas_system_inventory.json", "aureon_organism_runtime_status.json"}
    assert r["static_files_written"] == []
    assert (tmp_path / "catalog.json").is_file()
    assert not (tmp_path / "public").exists()


def test_manifest_get_route():
    c = _app(AUREON_LLM_OFFLINE="1")
    inv = c.get("/api/manifests/aureon_saas_system_inventory.json")
    assert inv.status_code == 200
    assert inv.get_json()["summary"]["surface_count"] > 0
    runtime = c.get("/api/manifests/aureon_organism_runtime_status.json").get_json()
    assert runtime["mode"] == "live" and len(runtime["domains"]) == 6
    missing = c.get("/api/manifests/nope.json")
    assert missing.status_code == 404
    assert "available" in missing.get_json()["error"]


# ── Supabase JWT bridge ────────────────────────────────────────────────────

def test_verify_supabase_jwt_unit():
    good = _mk_jwt({"sub": "u1", "exp": time.time() + 3600}, "sekret")
    assert verify_supabase_jwt(good, "sekret")["sub"] == "u1"
    assert verify_supabase_jwt(good, "wrong") is None                       # bad sig
    assert verify_supabase_jwt(_mk_jwt({"sub": "u", "exp": time.time() - 5}, "sekret"), "sekret") is None  # expired
    assert verify_supabase_jwt("not.a.jwt", "sekret") is None


def test_jwt_bridge_gates_when_secret_set():
    c = _app(AUREON_LLM_OFFLINE="1", AUREON_SUPABASE_JWT_SECRET="sekret")
    assert c.get("/api/catalog").status_code == 401                          # no token
    good = _mk_jwt({"sub": "u", "exp": time.time() + 3600}, "sekret")
    assert c.get("/api/catalog", headers={"Authorization": f"Bearer {good}"}).status_code == 200

def test_company_route_includes_passive_runtime_verification(tmp_path, monkeypatch):
    flask = pytest.importorskip("flask")
    monkeypatch.delenv("AUREON_SUPABASE_JWT_SECRET", raising=False)
    from aureon.saas import cognitive, gateway, observed_runtime

    # Process liveness cannot establish company-role bindings. Private runtime
    # manifests are deliberately absent from a clean source release; this test
    # must not depend on an operator's local or restored deployment state.
    manifest_path = tmp_path / "empty-bindings.json"
    manifest_path.write_text(json.dumps({
        "schema_version": "aureon-agent-company-runtime-bindings-v1",
        "truth_status": "real_derived", "generated_values": False,
        "bindings": [],
    }), encoding="utf-8")
    monkeypatch.setenv("AUREON_AGENT_COMPANY_RUNTIME_BINDING_PATH", str(manifest_path))

    monkeypatch.setattr(cognitive, "provenance_block", lambda: {
        "policy": "no fabricated values",
        "simulation_fallback_allowed": False,
        "source_registry_count": 1,
        "truth_statuses": ["real_derived", "real_observed", "no_data"],
    })
    monkeypatch.setattr(observed_runtime, "process_observation", lambda: {
        "available": True,
        "fresh": True,
        "read_state": "observed",
        "source": "registered_pid_os_probe",
        "source_path": "state/organ_registry.json",
        "source_timestamp": 1_788_884_400.0,
        "receipt_timestamp": 1_788_884_400.0,
        "max_age_seconds": 15,
        "source_clock_kind": "os_process_measurement",
        "identity_receipt_read_state": "observed",
        "counts": {
            "registered": 2,
            "measured": 2,
            "running_verified": 1,
            "running_unverified": 0,
            "absent": 0,
            "unknown": 0,
        },
        "organs": [
            {"name": "operator_gateway", "pid": 123, "pid_running": True, "identity_verified": True,
             "launch_time_consistent": True, "functional_health": "unknown", "read_state": "observed"},
            {"name": "aureon_radar_suite", "pid": None, "pid_running": None, "identity_verified": False,
             "functional_health": "unknown", "read_state": "unavailable", "reason": "no_recorded_pid"},
        ],
    })
    app = flask.Flask(__name__)
    gateway.register_saas_routes(app)

    response = app.test_client().get("/api/company")
    assert response.status_code == 200
    payload = response.get_json()
    runtime = payload["runtime_verification"]
    assert payload["truth_status"] == "real_derived"
    assert runtime["truth_status"] == "real_observed"
    assert runtime["generated_values"] is False
    assert runtime["organ_counts"]["running_total"] == 1
    assert runtime["sample_running_organs"][0]["name"] == "operator_gateway"
    assert runtime["role_binding_state"] == "unavailable"
    assert runtime["runtime_role_binding_available"] is False
    assert runtime["live_company_operation_state"] == "configured_catalogue_only_runtime_unbound"
    assert runtime["verified_running_role_count"] == 0
    assert runtime["unbound_role_count"] == payload["summary"]["role_count"] - runtime["verified_running_role_count"]
    assert runtime["service_surface_bindings_by_organ"] == {}
    assert "agent_role_to_runtime_organ_binding_manifest_unavailable" in runtime["blockers"]
    assert "running" not in payload["roles"][0]
    assert "private-command" not in json.dumps(payload)



def test_closed_position_analytics_route_requires_server_side_tenant_scope(monkeypatch):
    flask = pytest.importorskip("flask")
    monkeypatch.delenv("AUREON_SUPABASE_JWT_SECRET", raising=False)
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "server-side-secret-value")
    monkeypatch.delenv("AUREON_TRADING_TENANT_ID", raising=False)
    monkeypatch.delenv("AUREON_SUPABASE_USER_ID", raising=False)
    monkeypatch.delenv("SUPABASE_USER_ID", raising=False)

    from aureon.saas import gateway

    app = flask.Flask(__name__)
    gateway.register_saas_routes(app)
    response = app.test_client().get("/api/trading/closed-position-analytics?range=7d")

    assert response.status_code == 401
    payload = response.get_json()
    assert payload["available"] is False
    assert payload["records"] == []
    assert payload["count"] == 0
    assert "Authenticated account" in payload["reason"]
    assert "server-side-secret-value" not in json.dumps(payload)



def test_closed_position_analytics_route_uses_tenant_bearer_and_user_filter(monkeypatch):
    flask = pytest.importorskip("flask")
    monkeypatch.delenv("AUREON_SUPABASE_JWT_SECRET", raising=False)
    monkeypatch.setenv("SUPABASE_URL", "https://siihxcwetdjdsrfdexmb.supabase.co")
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)

    from aureon.saas import gateway

    seen = {}

    class _Headers(dict):
        def get(self, key, default=None):
            return super().get(key, default)

    class _Response:
        headers = _Headers({"content-range": "0-0/1"})

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self, _size=-1):
            return json.dumps([{
                "id": "closed-1",
                "user_id": "tenant-gary",
                "symbol": "BTCUSDT",
                "exchange": "binance",
                "side": "LONG",
                "opened_at": "2026-09-09T00:00:00Z",
                "closed_at": "2026-09-09T01:00:00Z",
                "source_id": "provider",
                "source_timestamp": "2026-09-09T01:00:00Z",
                "realized_pnl": 1,
                "status": "closed",
                "generated_values": False,
                "truth_status": "live",
                "entry_price": 1,
                "exit_price": 2,
                "close_reason": "target",
            }]).encode("utf-8")

    def fake_urlopen(request, timeout):
        seen["url"] = request.full_url
        seen["headers"] = dict(request.header_items())
        seen["timeout"] = timeout
        return _Response()

    user_token = _mk_jwt({
        "sub": "tenant-gary",
        "iss": "https://siihxcwetdjdsrfdexmb.supabase.co/auth/v1",
        "exp": time.time() + 3600,
    }, "test-secret")
    anon_key = _mk_jwt({
        "role": "anon",
        "ref": "siihxcwetdjdsrfdexmb",
        "exp": time.time() + 3600,
    }, "test-secret")
    monkeypatch.setattr(gateway, "_open_supabase_request", fake_urlopen)

    app = flask.Flask(__name__)
    gateway.register_saas_routes(app)
    response = app.test_client().get(
        "/api/trading/closed-position-analytics?range=7d",
        headers={
            "Authorization": f"Bearer {user_token}",
            "X-Aureon-Supabase-Publishable-Key": anon_key,
        },
    )

    payload = response.get_json()
    serialized = json.dumps(payload)
    assert response.status_code == 200
    assert payload["available"] is True
    assert payload["auth_mode"] == "tenant_bearer_rls"
    assert payload["count"] == 1
    assert "user_id=eq.tenant-gary" in seen["url"]
    assert seen["url"].startswith("https://siihxcwetdjdsrfdexmb.supabase.co/rest/v1/trading_positions?")
    assert seen["headers"]["Authorization"] == f"Bearer {user_token}"
    assert seen["headers"]["Apikey"] == anon_key
    assert user_token not in serialized
    assert anon_key not in serialized


def test_closed_position_analytics_accepts_pinned_operator_supabase_names(monkeypatch):
    flask = pytest.importorskip("flask")
    from aureon.saas import gateway

    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("VITE_SUPABASE_URL", raising=False)
    monkeypatch.delenv("AUREON_SUPABASE_JWT_SECRET", raising=False)
    monkeypatch.delenv("SUPABASE_ANON_KEY", raising=False)
    monkeypatch.delenv("VITE_SUPABASE_ANON_KEY", raising=False)
    monkeypatch.delenv("VITE_SUPABASE_PUBLISHABLE_KEY", raising=False)
    monkeypatch.setenv("AUREON_SUPABASE_URL", "https://siihxcwetdjdsrfdexmb.supabase.co")
    monkeypatch.setenv("AUREON_SUPABASE_PUBLISHABLE_KEY", "sb_publishable_" + "x" * 40)
    seen = {}

    class _Response:
        headers = {"content-range": "*/0"}
        def __enter__(self): return self
        def __exit__(self, *_args): return False
        def read(self, _size=-1): return b"[]"

    def fake_open(request, timeout):
        seen["url"] = request.full_url
        seen["headers"] = dict(request.header_items())
        return _Response()

    token = _mk_jwt({
        "sub": "tenant-gary",
        "iss": "https://siihxcwetdjdsrfdexmb.supabase.co/auth/v1",
        "exp": time.time() + 3600,
    }, "fixture")
    monkeypatch.setattr(gateway, "_open_supabase_request", fake_open)
    app = flask.Flask(__name__)

    @app.before_request
    def verified_outer_tenant_identity():
        flask.g.identity_kind = "tenant"

    gateway.register_saas_routes(app)
    response = app.test_client().get(
        "/api/trading/closed-position-analytics?range=24h",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.get_json()["auth_mode"] == "tenant_bearer_rls"
    assert "user_id=eq.tenant-gary" in seen["url"]
    assert seen["headers"]["Apikey"].startswith("sb_publishable_")



def test_sungeo_schumann_activity_keeps_frequency_unreported(monkeypatch):
    from aureon.saas import gateway

    now = 1_788_948_000.0
    monkeypatch.setattr(gateway.time, "time", lambda: now)
    payload = {
        "status": "elevated",
        "score": 44,
        "stations": 5,
        "stations_monitored": 6,
        "updated_at": gateway._utc_iso_from_epoch(now - 60),
        "attribution": "Data & analysis SunGeo.net",
    }
    stations = {
        "bgs": {"status": "active", "score": 65, "updated_at": gateway._utc_iso_from_epoch(now - 120)},
        "old": {"status": "storm", "score": 95, "updated_at": gateway._utc_iso_from_epoch(now - 20_000)},
    }

    observation = gateway._read_sungeo_schumann_activity(payload, int((now - 30) * 1000), station_payload=stations)

    assert observation is not None
    assert observation["truthStatus"] == "real_observed"
    assert observation["measurementKind"] == "station_activity"
    assert observation["frequencyReported"] is False
    assert observation["frequencyBasis"] == "nominal_reference_not_source_measurement"
    assert observation["fundamentalHz"] == 7.83
    assert observation["activityScore"] == 44
    assert observation["coherenceBoost"] == 0.0
    assert observation["stationCount"] == 5
    assert observation["stationsMonitored"] == 6
    assert [signal["source"] for signal in observation["stationSignals"]] == ["bgs"]


def test_schumann_route_prefers_sungeo_station_activity(monkeypatch):
    flask = pytest.importorskip("flask")
    monkeypatch.delenv("AUREON_SUPABASE_JWT_SECRET", raising=False)
    from aureon.saas import gateway

    now = 1_788_948_000.0
    monkeypatch.setattr(gateway.time, "time", lambda: now)
    current = {
        "status": "calm",
        "score": 12,
        "stations": 4,
        "stations_monitored": 6,
        "updated_at": gateway._utc_iso_from_epoch(now - 60),
    }
    stations = {"etna": {"status": "calm", "score": 12, "updated_at": gateway._utc_iso_from_epoch(now - 90)}}

    def fake_public_json(url, **_kwargs):
        if url == gateway.SCHUMANN_SUNGEO_CURRENT_SOURCE:
            return current, int((now - 20) * 1000)
        if url == gateway.SCHUMANN_SUNGEO_STATIONS_SOURCE:
            return stations, int((now - 20) * 1000)
        raise AssertionError(f"unexpected fallback fetch: {url}")

    monkeypatch.setattr(gateway, "_bounded_public_json", fake_public_json)
    app = flask.Flask(__name__)
    gateway.register_saas_routes(app)

    response = app.test_client().get("/api/research/schumann")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["sourceId"] == gateway.SCHUMANN_SUNGEO_SOURCE_ID
    assert payload["measurementKind"] == "station_activity"
    assert payload["frequencyReported"] is False
    assert payload["activityScore"] == 12
    assert payload["stationSignals"][0]["source"] == "etna"


def test_company_route_accepts_verified_service_surface_bindings(tmp_path, monkeypatch):
    flask = pytest.importorskip("flask")
    monkeypatch.delenv("AUREON_SUPABASE_JWT_SECRET", raising=False)
    from aureon.saas import cognitive, gateway, observed_runtime

    manifest_path = tmp_path / "bindings.json"
    manifest_path.write_text(json.dumps({
        "schema_version": "aureon-agent-company-runtime-bindings-v1",
        "generated_at": "2026-09-09T01:00:00+00:00",
        "truth_status": "real_derived",
        "generated_values": False,
        "bindings": [{
            "role_id": "frontend_console_builder",
            "organ_name": "frontend_vite",
            "binding_kind": "service_surface",
            "claim": "live_service_surface_binding_only",
            "source": "test_manifest",
            "evidence": ["role declares frontend surface", "frontend_vite identity verified"],
        }],
    }), encoding="utf-8")
    monkeypatch.setenv("AUREON_AGENT_COMPANY_RUNTIME_BINDING_PATH", str(manifest_path))
    monkeypatch.setattr(cognitive, "provenance_block", lambda: {
        "policy": "no fabricated values",
        "simulation_fallback_allowed": False,
        "source_registry_count": 1,
        "truth_statuses": ["real_derived", "real_observed", "no_data"],
    })
    monkeypatch.setattr(observed_runtime, "process_observation", lambda: {
        "available": True,
        "fresh": True,
        "read_state": "observed",
        "source": "registered_pid_os_probe",
        "source_path": "state/organ_registry.json",
        "source_timestamp": 1_788_884_400.0,
        "receipt_timestamp": 1_788_884_400.0,
        "max_age_seconds": 15,
        "source_clock_kind": "os_process_measurement",
        "identity_receipt_read_state": "observed",
        "counts": {
            "registered": 1,
            "measured": 1,
            "running_verified": 1,
            "running_unverified": 0,
            "absent": 0,
            "unknown": 0,
        },
        "organs": [
            {"name": "frontend_vite", "pid": 456, "pid_running": True, "identity_verified": True,
             "launch_time_consistent": True, "functional_health": "unknown", "read_state": "observed"},
        ],
    })
    app = flask.Flask(__name__)
    gateway.register_saas_routes(app)

    payload = app.test_client().get("/api/company").get_json()
    runtime = payload["runtime_verification"]
    assert runtime["role_binding_state"] == "partial"
    assert runtime["runtime_role_binding_available"] is True
    assert runtime["verified_running_role_count"] == 1
    assert runtime["manifest_running_role_match_count"] == 1
    assert runtime["running_role_matches"][0]["role_id"] == "frontend_console_builder"
    assert runtime["running_role_matches"][0]["claim"] == "live_service_surface_binding_only"
    assert "agent_role_to_runtime_organ_binding_manifest_unavailable" not in runtime["blockers"]
    assert "agent_role_to_runtime_organ_binding_manifest_partial" in runtime["blockers"]
    assert "private-command" not in json.dumps(payload)
