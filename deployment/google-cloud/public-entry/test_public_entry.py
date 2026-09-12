"""Real cryptographic identity tests and cross-boundary proxy failure tests."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import ipaddress
import json
import ssl
import threading
import time

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from cryptography import x509
from cryptography.x509.oid import NameOID
import jwt
import pytest

import public_entry as entry


BASE = entry.Config("entry", "https://aureon-console-123456789012.europe-west1.run.app",
                    "/projects/123456789012/locations/europe-west1/services/aureon-console",
                    frozenset({"owner@example.com"}), "aureon-public-entry@example-project.iam.gserviceaccount.com",
                    "123456789012345678901", "https://10.40.0.2:8443", "a" * 40)


@pytest.fixture(autouse=True)
def holds(monkeypatch):
    for name, value in entry.HOLDS.items():
        monkeypatch.setenv(name, value)


@pytest.fixture(scope="module")
def keys():
    return ec.generate_private_key(ec.SECP256R1()), rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture
def verifier(keys):
    def fetch(url):
        key = keys[1] if url == entry.SERVICE_KEYS else keys[0]
        pem = key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode()
        return json.dumps({"test-key": pem}).encode()
    return entry.GoogleVerifier(fetch)


def signed(keys, *, service=False, **changes):
    now = int(time.time())
    claims = {"iat": now - 1, "exp": now + (3599 if service else 599),
              "iss": "https://accounts.google.com" if service else "https://cloud.google.com/iap",
              "aud": BASE.bridge_url if service else BASE.iap_audience,
              "sub": BASE.service_id if service else "accounts.google.com:owner-id",
              "email": BASE.service_email if service else "owner@example.com"}
    if service:
        claims["email_verified"] = True
    claims.update(changes)
    return jwt.encode(claims, keys[int(service)], algorithm="RS256" if service else "ES256", headers={"kid": "test-key"})


def healthy():
    return 200, {"Content-Type": "application/json"}, json.dumps({"schema": "aureon.cloud-http-health.v1", "role": "ui-gateway",
              "revision": BASE.revision, "ready": True, "deployment_hold": True, "release_authority": False}).encode()


def headers(keys, *, bridge=False):
    result = {"Origin": BASE.origin, "Sec-Fetch-Site": "same-origin", "X-Forwarded-Proto": "https"}
    result["X-Aureon-Iap-Assertion" if bridge else "X-Goog-Iap-Jwt-Assertion"] = signed(keys)
    if bridge:
        result.update({"X-Aureon-Public-Host": BASE.origin[8:], "X-Aureon-Service-Authorization": "Bearer " + signed(keys, service=True)})
    return result


def client(verifier, *, bridge=False, transport=None, identity=None, config=None):
    cfg = config or replace(BASE, role="bridge" if bridge else "entry")
    app = entry.create_app(cfg, verifier=verifier,
                           transport=transport or (lambda *a, **k: (200, {"Content-Type": "text/plain"}, b"ui")),
                           identity=identity or (lambda: "runtime-service-identity"))
    return app.test_client(), cfg.bridge_url if bridge else (cfg.origin or BASE.origin)


def test_both_signed_identities_are_cryptographically_validated(keys, verifier):
    assert verifier.user(signed(keys), BASE)["email"] == "owner@example.com"
    assert verifier.service("Bearer " + signed(keys, service=True), BASE)["sub"] == BASE.service_id


@pytest.mark.parametrize("changes", [
    {"iss": "https://attacker.invalid"}, {"aud": "/projects/wrong"},
    {"aud": [BASE.iap_audience]}, {"email": "other@example.com"},
    {"exp": 1, "iat": 0}, {"iat": int(time.time()) + 600},
    {"exp": int(time.time()) + 2000}, {"email": ["owner@example.com"]}, {"sub": ""},
])
def test_bad_iap_claims_rejected(keys, verifier, changes):
    with pytest.raises(entry.BoundaryError):
        verifier.user(signed(keys, **changes), BASE)


@pytest.mark.parametrize("changes", [{"sub": "different"}, {"email": "other@example-project.iam.gserviceaccount.com"},
                                     {"email_verified": False}, {"aud": BASE.origin}, {"exp": 1, "iat": 0}])
def test_bad_service_claims_rejected(keys, verifier, changes):
    with pytest.raises(entry.BoundaryError):
        verifier.service("Bearer " + signed(keys, service=True, **changes), BASE)


def test_invalid_signature_and_algorithm_rejected(keys, verifier):
    wrong = ec.generate_private_key(ec.SECP256R1())
    claims = jwt.decode(signed(keys), options={"verify_signature": False})
    for token in (jwt.encode(claims, wrong, algorithm="ES256", headers={"kid": "test-key"}),
                  jwt.encode(claims, "nonproduction-test-string-32-or-more", algorithm="HS256", headers={"kid": "test-key"}),
                  jwt.encode(claims, None, algorithm="none", headers={"kid": "test-key"})):
        with pytest.raises(entry.BoundaryError):
            verifier.user(token, BASE)


@pytest.mark.parametrize("path", ["/", "/api/terminal-state", "/assets/ui.js", "/__aureon_health"])
def test_uncommissioned_entry_never_fetches_or_exposes_data(path, verifier):
    def forbidden(*args, **kwargs):
        pytest.fail("uncommissioned network access")
    c, base = client(verifier, config=replace(BASE, origin=""), transport=forbidden, identity=forbidden)
    assert c.get(path, base_url=base).status_code == 503


def test_unsigned_request_and_forged_plain_identity_headers_denied(verifier):
    c, base = client(verifier)
    response = c.get("/api/state", base_url=base, headers={"X-Goog-Authenticated-User-Email": "owner@example.com", "X-Forwarded-Proto": "https"})
    assert response.status_code == 403 and b"ui" not in response.data


@pytest.mark.parametrize("replacement", [{"Origin": "https://evil.invalid"}, {"Sec-Fetch-Site": "cross-site"},
                                        {"X-Forwarded-Proto": "http"}, {"Host": "other.run.app"}])
def test_authenticated_cross_origin_or_wrong_host_denied(keys, verifier, replacement):
    c, base = client(verifier)
    h = headers(keys)
    h.update(replacement)
    assert c.get("/api/state", base_url=base, headers=h).status_code == 403


def test_post_requires_explicit_exact_origin(keys, verifier):
    c, base = client(verifier)
    h = headers(keys)
    del h["Origin"]
    assert c.post("/api/control", base_url=base, headers=h).status_code == 403


def test_browser_navigation_allowed_but_api_requires_same_origin_evidence(keys, verifier):
    c, base = client(verifier)
    h = {"X-Goog-Iap-Jwt-Assertion": signed(keys), "X-Forwarded-Proto": "https"}
    assert c.get("/console", base_url=base, headers=h).status_code == 200
    assert c.get("/api/state", base_url=base, headers=h).status_code == 403


def test_public_user_entry_never_requires_or_forwards_iap_identity(verifier):
    captured = []

    def transport(*args, **kwargs):
        captured.append(args)
        return 200, {"Content-Type": "application/json"}, b"{}"

    cfg = replace(BASE, access_mode="user")
    c, base = client(verifier, transport=transport, config=cfg)
    assert c.get("/console", base_url=base, headers={"X-Forwarded-Proto": "https"}).status_code == 200
    assert captured[-1][2]["X-Aureon-Entry-Mode"] == "user"
    assert captured[-1][2]["X-Aureon-Auth-Resolution"] == "anonymous"
    assert "X-Aureon-Iap-Assertion" not in captured[-1][2]

    bearer = "Bearer header.payload.signature"
    response = c.get(
        "/api/me",
        base_url=base,
        headers={
            "X-Forwarded-Proto": "https",
            "Origin": BASE.origin,
            "Sec-Fetch-Site": "same-origin",
            "Authorization": bearer,
            "X-Aureon-Auth-Resolution": "attacker-selected",
        },
    )
    assert response.status_code == 200
    assert captured[-1][2]["Authorization"] == bearer
    assert captured[-1][2]["X-Aureon-Auth-Resolution"] == "tenant-bearer"


def test_public_user_entry_still_requires_exact_origin_for_mutation(verifier):
    cfg = replace(BASE, access_mode="user")
    c, base = client(verifier, config=cfg)
    assert c.post(
        "/api/providers/openai",
        base_url=base,
        headers={"X-Forwarded-Proto": "https", "Sec-Fetch-Site": "same-origin"},
    ).status_code == 403
    assert c.post(
        "/api/providers/openai",
        base_url=base,
        headers={
            "X-Forwarded-Proto": "https",
            "Origin": BASE.origin,
            "Sec-Fetch-Site": "same-origin",
        },
    ).status_code == 200


@pytest.mark.parametrize("authorization", [None, "", "Bearer invalid-client-token"])
@pytest.mark.parametrize("marker", [None, "", "failed"])
def test_entry_preserves_explicit_authorization_and_failure_marker(keys, verifier, authorization, marker):
    captured = []
    def transport(*args, **kwargs):
        captured.append(args)
        return 200, {"Content-Type": "application/json"}, b"{}"
    c, base = client(verifier, transport=transport)
    h = headers(keys)
    h.update({"Cookie": "private-browser-session", "X-Serverless-Authorization": "inbound-infrastructure-token",
              "X-Aureon-Service-Authorization": "attacker-token", "X-Aureon-Public-Host": "evil.invalid"})
    if authorization is not None:
        h["Authorization"] = authorization
    if marker is not None:
        h["X-Aureon-Auth-Resolution"] = marker
    assert c.get("/api/state", base_url=base, headers=h).status_code == 200
    sent = captured[0][2]
    assert ("Authorization" in sent) == (authorization is not None)
    assert ("X-Aureon-Auth-Resolution" in sent) == (marker is not None)
    if authorization is not None:
        assert sent["Authorization"] == authorization
    if marker is not None:
        assert sent["X-Aureon-Auth-Resolution"] == marker
    assert sent["X-Aureon-Service-Authorization"] == "Bearer runtime-service-identity"
    assert sent["X-Aureon-Public-Host"] == BASE.origin[8:]
    assert "Cookie" not in sent and "X-Serverless-Authorization" not in sent


def test_bridge_requires_both_identities_before_any_loopback_access(keys, verifier):
    def forbidden(*args, **kwargs):
        pytest.fail("unauthorized loopback access")
    c, base = client(verifier, bridge=True, transport=forbidden)
    for missing in ("X-Aureon-Iap-Assertion", "X-Aureon-Service-Authorization"):
        h = headers(keys, bridge=True)
        del h[missing]
        assert c.get("/api/state", base_url=base, headers=h).status_code == 403


def test_hybrid_bridge_accepts_service_authenticated_user_entry_without_admin_fallback(keys, verifier):
    calls = []

    def transport(method, target, forwarded, body, **kwargs):
        calls.append((target, forwarded, kwargs))
        if kwargs.get("health"):
            return healthy()
        return 401, {"Content-Type": "application/json"}, b'{"error":"missing_user"}'

    cfg = replace(
        BASE,
        role="bridge",
        access_mode="hybrid",
        owner_origin="https://aureon-owner-123456789012.europe-west1.run.app",
    )
    c, base = client(verifier, bridge=True, transport=transport, config=cfg)
    h = {
        "Origin": BASE.origin,
        "Sec-Fetch-Site": "same-origin",
        "X-Aureon-Public-Host": BASE.origin[8:],
        "X-Aureon-Entry-Mode": "user",
        "X-Aureon-Auth-Resolution": "anonymous",
        "X-Aureon-Service-Authorization": "Bearer " + signed(keys, service=True),
    }
    response = c.get("/api/me", base_url=base, headers=h)
    assert response.status_code == 401
    assert calls[1][1]["X-Aureon-Auth-Resolution"] == "anonymous"
    assert "Authorization" not in calls[1][1]
    assert "X-Aureon-Iap-Assertion" not in calls[1][1]

    owner_headers = headers(keys, bridge=True)
    owner_headers.update({
        "Origin": cfg.owner_origin,
        "X-Aureon-Public-Host": cfg.owner_origin[8:],
        "X-Aureon-Entry-Mode": "iap",
    })
    assert c.get("/api/me", base_url=base, headers=owner_headers).status_code == 401

    h.pop("X-Aureon-Entry-Mode")
    assert c.get("/api/me", base_url=base, headers=h).status_code == 403
    assert len(calls) == 4


def test_bridge_checks_health_then_creates_loopback_origin_preserving_bad_auth(keys, verifier):
    calls = []
    def transport(method, target, forwarded, body, **kwargs):
        calls.append((target, forwarded, kwargs))
        if kwargs.get("health"):
            return healthy()
        return 401, {"Content-Type": "application/json"}, b'{"error":"invalid_auth"}'
    c, base = client(verifier, bridge=True, transport=transport)
    h = headers(keys, bridge=True)
    h.update({"Authorization": "", "X-Aureon-Auth-Resolution": "failed"})
    result = c.post("/api/control", base_url=base, headers=h, json={"action": "inspect"})
    assert result.status_code == 401
    assert calls[0][0] == entry.HEALTH and calls[0][1] == {}
    assert calls[1][1]["Authorization"] == ""
    assert calls[1][1]["X-Aureon-Auth-Resolution"] == "failed"
    assert calls[1][1]["Origin"] == "http://127.0.0.1:5173"
    assert not any("Iap" in key or "Service-Authorization" in key for key in calls[1][1])


@pytest.mark.parametrize("change", [{"deployment_hold": False}, {"release_authority": True}, {"revision": "b" * 40},
                                    {"ready": False}, {"role": "operator"}])
def test_mismatched_or_released_runtime_cannot_be_proxied(keys, verifier, change):
    calls = []
    def transport(*args, **kwargs):
        calls.append(args)
        status, meta, raw = healthy()
        state = json.loads(raw)
        state.update(change)
        return status, meta, json.dumps(state).encode()
    c, base = client(verifier, bridge=True, transport=transport)
    result = c.get("/api/state", base_url=base, headers=headers(keys, bridge=True))
    assert result.status_code == 502 and len(calls) == 1


def test_hold_change_is_checked_each_request(keys, verifier, monkeypatch):
    c, base = client(verifier)
    assert c.get("/", base_url=base, headers=headers(keys)).status_code == 200
    monkeypatch.setenv("AUREON_DEPLOYMENT_HOLD", "0")
    assert c.get("/", base_url=base, headers=headers(keys)).status_code == 503


def test_unavailable_identity_or_upstream_never_falls_back(keys, verifier):
    def fail(*args, **kwargs):
        raise entry.BoundaryError("expected_failure")
    c, base = client(verifier, identity=fail)
    assert c.get("/", base_url=base, headers=headers(keys)).status_code == 502
    c, base = client(verifier, transport=fail)
    assert c.get("/", base_url=base, headers=headers(keys)).status_code == 502


@pytest.mark.parametrize("origin", ["https://*.run.app", "http://valid.run.app", "https://valid.run.app.evil.invalid", "https://valid.run.app/", "https://valid.run.app:443"])
def test_origin_configuration_rejects_wildcards_and_ambiguous_hosts(origin):
    with pytest.raises(entry.BoundaryError):
        replace(BASE, origin=origin).validate()


@pytest.mark.parametrize("url", ["https://8.8.8.8:8443", "http://10.40.0.2:8443", "https://metadata.google.internal:8443", "https://10.40.0.2:443", "https://10.40.0.2:8443/path"])
def test_bridge_destination_is_private_fixed_https(url):
    with pytest.raises(entry.BoundaryError):
        replace(BASE, bridge_url=url).validate()


def test_jwt_public_key_fetch_is_cached(keys):
    calls = []
    def fetch(url):
        calls.append(url)
        return json.dumps({"test-key": keys[0].public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode()}).encode()
    verifier = entry.GoogleVerifier(fetch)
    verifier.user(signed(keys), BASE)
    verifier.user(signed(keys), BASE)
    assert calls == [entry.IAP_KEYS]


def test_encoded_query_delimiters_do_not_change_target_route():
    assert entry.request_target({"PATH_INFO": "/api/a?b", "QUERY_STRING": "x=1"}) == "/api/a%3Fb?x=1"
    with pytest.raises(entry.BoundaryError):
        entry.request_target({"PATH_INFO": "//evil.invalid/api", "QUERY_STRING": ""})


def test_request_body_limit(keys, verifier):
    c, base = client(verifier)
    result = c.post("/api/data", base_url=base, headers=headers(keys), data=b"x" * (entry.MAX_BODY + 1))
    assert result.status_code == 413


@pytest.fixture
def tls_server(tmp_path):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "ephemeral-test-only")])
    now = datetime.now(timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(now - timedelta(minutes=1))
            .not_valid_after(now + timedelta(minutes=10))
            .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
            .add_extension(x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]), critical=False)
            .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False)
            .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(key.public_key()), critical=False)
            .sign(key, hashes.SHA256()))
    cert_path, key_path = tmp_path / "test-cert.pem", tmp_path / "test-key.pem"
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    observed = []
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass
        def do_GET(self):
            observed.append(self.path)
            if self.path == "/redirect":
                self.send_response(302)
                self.send_header("Location", "https://attacker.invalid/secret")
                self.end_headers()
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Set-Cookie", "private-cookie=not-forwarded")
            self.send_header("Access-Control-Allow-Origin", "*")
            if self.path == "/encoded":
                self.send_header("Content-Encoding", "gzip")
            self.end_headers()
            if self.path == "/slow":
                time.sleep(0.7)
            try:
                self.wfile.write(b"genuine-upstream-body")
            except (OSError, ssl.SSLError):
                pass
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    server_context.load_cert_chain(cert_path, key_path)
    server.socket = server_context.wrap_socket(server.socket, server_side=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.load_verify_locations(cert_path)
    yield server.server_port, context, observed
    server.shutdown()
    server.server_close()
    thread.join(timeout=2)


def test_actual_tls_pin_and_response_metadata_allowlist(tls_server):
    port, context, observed = tls_server
    status, response_headers, body = entry.exchange("127.0.0.1", port, "GET", "/api/state", {}, b"", context=context)
    assert status == 200 and body == b"genuine-upstream-body"
    assert response_headers == {"Content-Type": "text/plain"}
    assert observed == ["/api/state"]


def test_actual_tls_wrong_trust_store_is_rejected(tls_server):
    port, _, observed = tls_server
    with pytest.raises(entry.BoundaryError):
        entry.exchange("127.0.0.1", port, "GET", "/api/state", {}, b"", context=ssl.create_default_context())
    assert observed == []


@pytest.mark.parametrize("path", ["/redirect", "/encoded"])
def test_actual_proxy_refuses_redirects_and_encoded_payloads(tls_server, path):
    port, context, observed = tls_server
    with pytest.raises(entry.BoundaryError):
        entry.exchange("127.0.0.1", port, "GET", path, {}, b"", context=context)
    assert observed == [path]


def test_actual_response_size_and_wall_clock_bounds(tls_server):
    port, context, _ = tls_server
    with pytest.raises(entry.BoundaryError):
        entry.exchange("127.0.0.1", port, "GET", "/", {}, b"", context=context, limit=3)
    start = time.monotonic()
    with pytest.raises(entry.BoundaryError):
        entry.exchange("127.0.0.1", port, "GET", "/slow", {}, b"", context=context, timeout=0.15)
    assert time.monotonic() - start < 0.6


def test_metadata_identity_validates_exact_account_and_caches(keys, verifier):
    calls = []
    def fetch(url, **kwargs):
        calls.append((url, kwargs))
        return signed(keys, service=True).encode()
    identity = entry.MetadataIdentity(BASE, verifier, fetch)
    assert identity() == identity()
    assert len(calls) == 1
    assert calls[0] == (entry.METADATA_IDENTITY + "?audience=https%3A%2F%2F10.40.0.2%3A8443&format=full", {"metadata": True})


def test_metadata_wrong_account_rejected(keys, verifier):
    def fetch(*args, **kwargs):
        return signed(keys, service=True, sub="wrong-service-id").encode()
    with pytest.raises(entry.BoundaryError):
        entry.MetadataIdentity(BASE, verifier, fetch)()


def test_identity_fetch_destination_allowlist():
    for url in ("https://attacker.invalid/certs", "http://127.0.0.1:8080/secrets"):
        with pytest.raises(entry.BoundaryError):
            entry.identity_fetch(url)
