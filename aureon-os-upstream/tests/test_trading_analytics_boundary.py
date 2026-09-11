"""Provider transport fixtures; no real records or credentials used."""
import json

import pytest
from flask import Flask, g

from aureon.saas import gateway


def test_open_mode_never_uses_configured_service_account(monkeypatch):
    monkeypatch.delenv("AUREON_SUPABASE_JWT_SECRET", raising=False)
    monkeypatch.setenv("SUPABASE_URL", "https://fixture.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-service-secret")
    monkeypatch.setenv("AUREON_TRADING_TENANT_ID", "operator-account")
    monkeypatch.setattr(gateway, "_open_supabase_request", lambda *_a, **_k: pytest.fail("privileged request in open mode"))
    app = gateway.register_saas_routes(Flask(__name__))
    response = app.test_client().get("/api/trading/closed-position-analytics")
    assert response.status_code == 401
    assert response.headers["Cache-Control"] == "no-store"


@pytest.mark.parametrize("url", ["", "http://fixture.supabase.co", "https://fixture.supabase.co@evil.test",
                                    "https://fixture.supabase.co:bad", "https://fixture.supabase.co/?secret=yes"])
def test_source_destination_must_be_pinned_https_configuration(monkeypatch, url):
    monkeypatch.setenv("SUPABASE_URL", url)
    monkeypatch.delenv("VITE_SUPABASE_URL", raising=False)
    assert gateway._supabase_url_from_env_or_claims({"ref": "caller-selected"}, {}) == ""


def test_privileged_provider_rows_are_checked_against_exact_account(monkeypatch):
    class Response:
        headers = {"content-range": "0-0/1"}
        def __enter__(self): return self
        def __exit__(self, *_args): return False
        def read(self, _size): return json.dumps([{"id": "record", "user_id": "another-account"}]).encode()
    monkeypatch.setattr(gateway, "_open_supabase_request", lambda *_a, **_k: Response())
    result = gateway._read_supabase_closed_position_analytics("7d", "account", auth={
        "tenant_id": "account", "url": "https://fixture.supabase.co", "apikey": "fixture",
        "authorization": "fixture", "mode": "server_service_role_user_id_filter"})
    assert result["available"] is False and result["records"] == []
    assert "ownership" in result["reason"]


def test_credentialed_transport_rejects_redirect_without_forwarding_headers():
    from http.server import BaseHTTPRequestHandler, HTTPServer
    from threading import Thread
    from urllib.request import Request
    from urllib.error import HTTPError

    visits = []
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            visits.append(self.path)
            self.send_response(302)
            self.send_header("Location", "/credential-capture")
            self.end_headers()
        def log_message(self, *_args): pass
    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        request = Request(f"http://127.0.0.1:{server.server_port}/start", headers={
            "Authorization": "Bearer test-only", "apikey": "test-only"})
        with pytest.raises(HTTPError) as caught:
            gateway._open_supabase_request(request, timeout=2)
        assert caught.value.code == 302
        assert visits == ["/start"]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(2)
