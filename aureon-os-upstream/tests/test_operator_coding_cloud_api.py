"""Security and truthfulness checks for the cloud coding cockpit route."""

from __future__ import annotations

import base64
import hashlib
import hmac
import importlib
import json
import time
from pathlib import Path

import pytest

pytest.importorskip("flask", reason="operator HTTP surface requires Flask")

SECRET = "coding-cloud-tenant-secret"
ADMIN_KEY = "coding-cloud-admin-key"


def _jwt(subject: str) -> str:
    def encode(value: dict[str, object]) -> str:
        return base64.urlsafe_b64encode(json.dumps(value).encode()).rstrip(b"=").decode()

    header = encode({"alg": "HS256", "typ": "JWT"})
    payload = encode({"sub": subject, "exp": time.time() + 3600})
    signature = base64.urlsafe_b64encode(
        hmac.new(SECRET.encode(), f"{header}.{payload}".encode(), hashlib.sha256).digest()
    ).rstrip(b"=").decode()
    return f"{header}.{payload}.{signature}"


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("AUREON_LLM_OFFLINE", "1")
    monkeypatch.setenv("AUREON_SUPPRESS_IMPORT_SIDE_EFFECTS", "1")
    monkeypatch.setenv("AUREON_SUPABASE_JWT_SECRET", SECRET)
    monkeypatch.setenv("AUREON_OPERATOR_API_KEY", ADMIN_KEY)

    import aureon.operator.operator_server as server

    importlib.reload(server)
    app = server.create_app(
        test_ingress_release=server.TestOnlyOperatorIngressRelease(
            master_key=b"coding-cloud-status-test-ingress-material",
        )
    )
    return app.test_client(), app


def test_owner_gets_bounded_not_commissioned_receipt(client):
    browser, _app = client
    response = browser.get(
        "/api/coding/status",
        headers={"Authorization": f"Bearer {ADMIN_KEY}"},
    )

    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    payload = response.get_json()
    assert payload["schema_version"] == "aureon.operator.coding-cloud-status.v1"
    assert payload["available"] is False
    assert payload["commissioned"] is False
    assert payload["reason_code"] == "coding_service_not_commissioned"
    assert payload["last_run"] is None
    assert payload["capabilities"] == {
        "status_read": True,
        "coding_prompt": False,
        "phi_chat": False,
        "voice_reload": False,
        "autonomous_self_run": False,
        "autonomous_jobs": False,
        "repo_mutation": False,
    }
    encoded = json.dumps(payload).casefold()
    assert "127.0.0.1:13002" not in encoded
    assert "localhost:13002" not in encoded
    assert "api_key" not in encoded
    assert "secret" not in encoded


def test_tenant_and_anonymous_callers_cannot_read_owner_coding_status(client):
    browser, _app = client
    tenant = browser.get(
        "/api/coding/status",
        headers={"Authorization": f"Bearer {_jwt('tenant-a')}"},
    )
    anonymous = browser.get("/api/coding/status")

    assert tenant.status_code == 403
    assert tenant.get_json()["error"]["plane"] == "admin"
    assert anonymous.status_code == 401


def test_cloud_coding_registration_exposes_no_action_or_proxy_route(client):
    _browser, app = client
    rules = {(method, rule.rule) for rule in app.url_map.iter_rules() for method in rule.methods}

    assert ("GET", "/api/coding/status") in rules
    for path in (
        "/api/coding/prompt",
        "/api/phi-bridge/chat",
        "/api/phi-bridge/reload",
        "/api/autonomous-self-run/tick",
        "/api/autonomous-jobs/tick",
    ):
        assert all(rule != path for _method, rule in rules)


def test_coding_console_uses_only_authenticated_same_origin_status_client():
    source = (
        Path(__file__).resolve().parents[1]
        / "frontend/src/components/generated/AureonCodingOrganismConsole.tsx"
    ).read_text(encoding="utf-8")

    assert 'from "@/services/apiClient"' in source
    assert 'api.get<JsonMap>("/api/coding/status"' in source
    assert "127.0.0.1:13002" not in source
    assert "localhost:13002" not in source
    assert "api.post" not in source
    assert "CodingArtifactReviewPanel" not in source
    assert "/api/coding/artifact-review" not in source
