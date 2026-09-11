"""Strict-JSON regression tests for browser-facing SaaS responses."""

from __future__ import annotations

import json
from unittest.mock import Mock

import pytest

from aureon.core.jsonsafe import json_safe


def _reject_nonfinite(value: str) -> None:
    raise AssertionError(f"non-finite JSON constant emitted: {value}")


def test_json_safe_recurses_without_mutating_finite_values() -> None:
    source = {
        "finite": 1.25,
        "nested": [float("nan"), (float("inf"), float("-inf"))],
    }

    assert json_safe(source) == {
        "finite": 1.25,
        "nested": [None, [None, None]],
    }


def test_cognition_route_emits_browser_parseable_json(monkeypatch) -> None:
    flask = pytest.importorskip("flask", reason="SaaS gateway requires Flask")
    from aureon.saas import cognitive
    from aureon.saas.gateway import register_saas_routes

    monkeypatch.delenv("AUREON_SUPABASE_JWT_SECRET", raising=False)
    monkeypatch.setattr(
        cognitive,
        "field_surface",
        lambda: {"coherence": float("nan"), "energy": float("inf")},
    )
    app = flask.Flask(__name__)
    register_saas_routes(app)

    response = app.test_client().get("/api/cognition/field")

    assert response.status_code == 200
    payload = json.loads(response.get_data(as_text=True), parse_constant=_reject_nonfinite)
    assert payload == {"surface": "field", "data": {"coherence": None, "energy": None}}


def _status_client(monkeypatch, source, *, require_tenant=False):
    flask = pytest.importorskip("flask", reason="SaaS gateway requires Flask")
    from aureon.saas import cognitive, status
    from aureon.saas.gateway import register_saas_routes

    if require_tenant:
        monkeypatch.setenv("AUREON_SUPABASE_JWT_SECRET", "status-json-test-only-key")
    else:
        monkeypatch.delenv("AUREON_SUPABASE_JWT_SECRET", raising=False)
    probe = Mock(return_value=source)
    monkeypatch.setattr(status, "get_platform_status", probe)
    monkeypatch.setattr(cognitive, "provenance_block", lambda: {"source": "fixture"})
    app = flask.Flask(__name__)
    register_saas_routes(app)
    return app.test_client(), probe


@pytest.mark.parametrize("health", ["healthy", "degraded", "critical"])
def test_status_route_recursively_nulls_nonfinite_without_changing_health(monkeypatch, health):
    source = {
        "status": health,
        "operational_core": {
            "available": False,
            "age_seconds": float("inf"),
            "samples": [float("nan"), {"age_seconds": float("-inf"), "count": 0}],
        },
        "domains_reachable": 2,
    }
    client, probe = _status_client(monkeypatch, source)

    response = client.get("/api/status")

    assert response.status_code == 200
    assert response.mimetype == "application/json"
    payload = json.loads(response.get_data(as_text=True), parse_constant=_reject_nonfinite)
    assert payload == {
        "status": health,
        "operational_core": {
            "available": False,
            "age_seconds": None,
            "samples": [None, {"age_seconds": None, "count": 0}],
        },
        "domains_reachable": 2,
        "truth_status": "no_data",
        "provenance": {"source": "fixture"},
    }
    assert source["operational_core"]["age_seconds"] == float("inf")
    probe.assert_called_once_with()


def test_status_route_preserves_finite_values_and_availability(monkeypatch):
    source = {
        "status": "healthy",
        "operational_core": {"available": True, "age_seconds": 1.25, "count": 0},
        "coordinator": {"available": False},
    }
    client, probe = _status_client(monkeypatch, source)

    response = client.get("/api/status")

    assert response.status_code == 200
    payload = json.loads(response.get_data(as_text=True), parse_constant=_reject_nonfinite)
    assert payload == {**source, "truth_status": "no_data", "provenance": {"source": "fixture"}}
    probe.assert_called_once_with()


@pytest.mark.parametrize("headers", [{}, {"Authorization": "Bearer invalid-test-token"}])
def test_status_route_keeps_tenant_guard_before_status_probe(monkeypatch, headers):
    client, probe = _status_client(monkeypatch, {"status": "healthy"}, require_tenant=True)

    response = client.get("/api/status", headers=headers)

    assert response.status_code == 401
    payload = json.loads(response.get_data(as_text=True), parse_constant=_reject_nonfinite)
    assert payload["error"]["code"] == 401
    probe.assert_not_called()


def test_status_route_accepts_valid_tenant_and_emits_strict_json(monkeypatch):
    import base64
    import hashlib
    import hmac
    import time

    def encoded(value):
        return base64.urlsafe_b64encode(json.dumps(value).encode()).rstrip(b"=").decode()

    head = encoded({"alg": "HS256", "typ": "JWT"})
    body = encoded({"sub": "status-json-fixture", "exp": time.time() + 60})
    signature = hmac.new(b"status-json-test-only-key", f"{head}.{body}".encode(), hashlib.sha256).digest()
    token = f"{head}.{body}.{base64.urlsafe_b64encode(signature).rstrip(b'=').decode()}"
    client, probe = _status_client(
        monkeypatch, {"status": "degraded", "age_seconds": float("inf")}, require_tenant=True,
    )

    response = client.get("/api/status", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    payload = json.loads(response.get_data(as_text=True), parse_constant=_reject_nonfinite)
    assert payload["status"] == "degraded"
    assert payload["age_seconds"] is None
    probe.assert_called_once_with()
