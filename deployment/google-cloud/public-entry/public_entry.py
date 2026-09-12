"""Cloud Run product entry and independently authenticated private VM bridge.

This package contains no operator credentials and grants no release authority.
The owner entry uses IAP. The user entry carries only a browser bearer and a
service-signed route mode; only the bridge can reach the governed loopback UI.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import http.client
import ipaddress
import json
import os
from pathlib import Path
import re
import secrets
import socket
import ssl
import threading
import time
from urllib.parse import quote, urlsplit, unquote

import jwt
from cryptography import x509
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from flask import Flask, Response, jsonify, request

HOLDS = {
    "AUREON_DEPLOYMENT_HOLD": "1", "AUREON_DISABLE_REAL_ORDERS": "1",
    "AUREON_DISABLE_EXCHANGE_MUTATIONS": "1", "AUREON_ORDER_INTENT_PUBLISH": "0",
    "AUREON_LIVE_TRADING": "0", "AUREON_UNIFIED_ORDER_EXECUTOR": "0",
}
IAP_KEYS = "https://www.gstatic.com/iap/verify/public_key"
SERVICE_KEYS = "https://www.googleapis.com/oauth2/v1/certs"
METADATA_IDENTITY = "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/identity"
HEALTH = "/__aureon_health"
MAX_BODY = 256 * 1024
MAX_RESPONSE = 8 * 1024 * 1024
SAFE_METHODS = {"GET", "HEAD"}
INSTANCE_ONLY_API_PATHS = frozenset({
    "/api/terminal-state",
    "/api/flight-test",
    "/api/orca-observations",
})
INTENT_AUDIENCE = "aureon-operator-switchboard-intent"
INTENT_ISSUER = "aureon-private-bridge"
INTENT_SCHEMA = "aureon.operator.cloud-switchboard-intent.v1"
INTENT_HEADER = "X-Aureon-Operator-Intent"
_INTENT_PATH = re.compile(r"/api/switchboard/[A-Z0-9_]{1,64}")
_AUTHORIZATION_PATH = "/api/operator/authorization-lease"
_CLOUD_TRADING_RELEASE_PATH = "/api/operator/cloud-trading-control/apply"


def _intent_route_rule(target):
    if _INTENT_PATH.fullmatch(target):
        return "/api/switchboard/<flag_id>"
    if target == _AUTHORIZATION_PATH:
        return _AUTHORIZATION_PATH
    if target == _CLOUD_TRADING_RELEASE_PATH:
        return _CLOUD_TRADING_RELEASE_PATH
    return None


class BoundaryError(RuntimeError):
    """Fixed codes only: never format tokens, claims, paths, or exception text."""


def holds_ready():
    return all(os.environ.get(name) == value for name, value in HOLDS.items())


@dataclass(frozen=True)
class Config:
    role: str
    origin: str
    iap_audience: str
    allowed_emails: frozenset[str]
    service_email: str
    service_id: str
    bridge_url: str
    revision: str
    ca_file: str = ""
    access_mode: str = "iap"
    owner_origin: str = ""
    intent_key_file: str = ""

    @classmethod
    def from_env(cls):
        return cls(os.environ.get("AUREON_PUBLIC_ROLE", ""), os.environ.get("AUREON_PUBLIC_ORIGIN", ""),
                   os.environ.get("AUREON_IAP_AUDIENCE", ""),
                   frozenset(filter(None, os.environ.get("AUREON_ALLOWED_USER_EMAILS", "").split(","))),
                   os.environ.get("AUREON_ENTRY_SERVICE_ACCOUNT_EMAIL", ""),
                   os.environ.get("AUREON_ENTRY_SERVICE_ACCOUNT_ID", ""),
                   os.environ.get("AUREON_BRIDGE_URL", ""), os.environ.get("AUREON_REVISION", ""),
                   os.environ.get("AUREON_BRIDGE_CA_FILE", ""),
                   os.environ.get("AUREON_PUBLIC_ACCESS_MODE", "iap"),
                   os.environ.get("AUREON_OWNER_ORIGIN", ""),
                   os.environ.get("AUREON_OPERATOR_INTENT_KEY_FILE", ""))

    def origins(self):
        values = {self.origin} if self.origin else set()
        if self.role == "bridge" and self.owner_origin:
            values.add(self.owner_origin)
        return frozenset(values)

    def validate(self):
        if self.role not in {"entry", "bridge"}:
            raise BoundaryError("role_invalid")
        allowed_modes = {"iap", "user"} if self.role == "entry" else {"iap", "user", "hybrid"}
        if self.access_mode not in allowed_modes:
            raise BoundaryError("access_mode_invalid")
        if self.access_mode in {"iap", "hybrid"}:
            if not re.fullmatch(r"/projects/[0-9]{6,20}/locations/[a-z]+-[a-z]+[0-9]/services/[a-z][a-z0-9-]{0,62}", self.iap_audience):
                raise BoundaryError("iap_audience_invalid")
            if not self.allowed_emails or len(self.allowed_emails) > 10 or any(
                    not re.fullmatch(r"[a-z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-z0-9.-]+", email) for email in self.allowed_emails):
                raise BoundaryError("user_allowlist_invalid")
        if self.access_mode == "hybrid" and not self.owner_origin:
            raise BoundaryError("owner_origin_required")
        if not re.fullmatch(r"[a-z][a-z0-9-]{4,28}[a-z0-9]@[a-z][a-z0-9-]+\.iam\.gserviceaccount\.com", self.service_email):
            raise BoundaryError("service_account_invalid")
        if not re.fullmatch(r"[0-9]{10,25}", self.service_id) or not re.fullmatch(r"[0-9a-f]{40}", self.revision):
            raise BoundaryError("identity_or_revision_invalid")
        parsed = urlsplit(self.bridge_url)
        try:
            address = ipaddress.ip_address(parsed.hostname or "")
            valid_ip = address.version == 4 and any(address in ipaddress.ip_network(cidr)
                        for cidr in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"))
            valid = valid_ip and parsed.port == 8443 and self.bridge_url == f"https://{address}:8443"
        except ValueError:
            valid = False
        if not valid:
            raise BoundaryError("bridge_destination_invalid")
        # Empty origin is the explicit all-denied bootstrap state. Wildcards and
        # guessed host suffix trust are never accepted once it is commissioned.
        for origin in self.origins():
            if not re.fullmatch(r"https://[a-z0-9][a-z0-9-]+(?:\.[a-z0-9][a-z0-9-]*)?\.run\.app", origin):
                raise BoundaryError("public_origin_invalid")
        if self.role == "bridge" and self.intent_key_file:
            key_path = Path(self.intent_key_file)
            if not key_path.is_absolute():
                raise BoundaryError("intent_key_path_invalid")


class OperatorIntentSigner:
    """Use the VM-only RSA identity to sign one short-lived intent receipt."""

    def __init__(self, key_file, *, clock=time.time, nonce=secrets.token_urlsafe):
        path = Path(str(key_file or ""))
        try:
            resolved = path.resolve(strict=True)
            raw = resolved.read_bytes()
        except OSError as exc:
            raise BoundaryError("intent_signing_key_unavailable") from exc
        if not path.is_absolute() or path.is_symlink() or not 0 < len(raw) <= 64 * 1024:
            raise BoundaryError("intent_signing_key_invalid")
        try:
            key = serialization.load_pem_private_key(raw, password=None)
        except (ValueError, TypeError) as exc:
            raise BoundaryError("intent_signing_key_invalid") from exc
        if not isinstance(key, rsa.RSAPrivateKey) or key.key_size < 2048:
            raise BoundaryError("intent_signing_key_invalid")
        self._key = key
        self._clock = clock
        self._nonce = nonce

    def sign(self, *, method, target, body, mode, revision):
        route_rule = _intent_route_rule(target)
        if method != "POST" or route_rule is None or mode != "iap":
            raise BoundaryError("intent_signing_scope_denied")
        now = int(self._clock())
        claims = {
            "aud": INTENT_AUDIENCE,
            "body_sha256": hashlib.sha256(body).hexdigest(),
            "exp": now + 10,
            "iat": now,
            "iss": INTENT_ISSUER,
            "jti": self._nonce(32),
            "method": method,
            "mode": mode,
            "path": target,
            "query_sha256": hashlib.sha256(b"").hexdigest(),
            "revision": revision,
            "route_rule": route_rule,
            "schema": INTENT_SCHEMA,
        }
        return jwt.encode(
            claims,
            self._key,
            algorithm="RS256",
            headers={"typ": "JWT"},
        )


def identity_fetch(url, *, metadata=False):
    if metadata:
        if not url.startswith(METADATA_IDENTITY + "?audience="):
            raise BoundaryError("identity_destination_invalid")
    elif url not in {IAP_KEYS, SERVICE_KEYS}:
        raise BoundaryError("identity_destination_invalid")
    headers = {"Metadata-Flavor": "Google"} if metadata else {"Accept": "application/json"}
    parsed = urlsplit(url)
    # Fixed hosts, direct socket transport: proxy environment variables, ambient
    # SDK credentials, redirects, and arbitrary key endpoints are not consulted.
    connection = (http.client.HTTPConnection(parsed.hostname, timeout=5) if metadata
                  else http.client.HTTPSConnection(parsed.hostname, timeout=5))
    timer = None
    deadline = time.monotonic() + 8
    try:
        connection.connect()
        wire_socket = connection.sock
        def expire():
            try:
                wire_socket.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
        timer = threading.Timer(max(0, deadline - time.monotonic()), expire)
        timer.daemon = True
        timer.start()
        connection.request("GET", parsed.path + ("?" + parsed.query if parsed.query else ""), headers=headers)
        response = connection.getresponse()
        if response.status != 200 or (metadata and response.getheader("Metadata-Flavor") != "Google"):
            raise BoundaryError("identity_fetch_failed")
        content = response.read(131073)
        if len(content) > 131072 or time.monotonic() >= deadline:
            raise BoundaryError("identity_response_too_large")
        return content
    except (OSError, ValueError, http.client.HTTPException):
        raise BoundaryError("identity_fetch_failed") from None
    finally:
        if timer:
            timer.cancel()
        connection.close()


class GoogleVerifier:
    """Google keys cached for five minutes; unknown keys refresh with a bound.

    No key, issuer, algorithm, or URL is chosen from untrusted JWT claims.
    Unverified JWT headers are used solely as a lookup in the fixed key set.
    """
    def __init__(self, fetch=identity_fetch):
        self.fetch = fetch
        self.cache = {}
        self.lock = threading.Lock()

    def key(self, url, kid):
        with self.lock:
            now = time.monotonic()
            loaded, keys = self.cache.get(url, (0, {}))
            if now - loaded >= 300 or not keys or (kid not in keys and now - loaded >= 30):
                try:
                    keys = json.loads(self.fetch(url))
                    if not isinstance(keys, dict) or not 0 < len(keys) <= 100:
                        raise ValueError()
                    if any(not isinstance(k, str) or not isinstance(v, str) or len(v) > 16384 for k, v in keys.items()):
                        raise ValueError()
                    self.cache[url] = now, keys
                except (ValueError, TypeError):
                    raise BoundaryError("identity_keys_invalid") from None
            if kid not in keys:
                raise BoundaryError("identity_key_unknown")
            pem = keys[kid]
            if pem.startswith("-----BEGIN CERTIFICATE-----"):
                return x509.load_pem_x509_certificate(pem.encode("ascii")).public_key()
            return pem

    def verify(self, token, *, audience, service=False):
        try:
            if not isinstance(token, str) or not re.fullmatch(r"[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+", token) or len(token) > 16384:
                raise BoundaryError("identity_token_invalid")
            header = jwt.get_unverified_header(token)
            algorithm = "RS256" if service else "ES256"
            if header.get("alg") != algorithm or not isinstance(header.get("kid"), str) or len(header["kid"]) > 128 or "crit" in header:
                raise BoundaryError("identity_header_invalid")
            key = self.key(SERVICE_KEYS if service else IAP_KEYS, header["kid"])
            claims = jwt.decode(token, key, algorithms=[algorithm], audience=audience,
                                issuer=("https://accounts.google.com", "accounts.google.com") if service else "https://cloud.google.com/iap",
                                leeway=30, options={"require": ["exp", "iat", "aud", "iss", "sub", "email"], "strict_aud": True})
            if (any(type(claims.get(k)) is not int for k in ("iat", "exp"))
                    or not isinstance(claims.get("sub"), str) or not claims["sub"]
                    or not isinstance(claims.get("email"), str)):
                raise BoundaryError("identity_claims_invalid")
            if not 0 < claims["exp"] - claims["iat"] <= (3660 if service else 660):
                raise BoundaryError("identity_lifetime_invalid")
            return claims
        except (jwt.PyJWTError, ValueError, TypeError, UnicodeError):
            raise BoundaryError("identity_token_invalid") from None

    def user(self, token, config):
        claims = self.verify(token, audience=config.iap_audience)
        if claims["email"] not in config.allowed_emails:
            raise BoundaryError("user_not_authorized")
        return claims

    def service(self, header, config):
        if not isinstance(header, str) or not header.startswith("Bearer "):
            raise BoundaryError("service_identity_required")
        claims = self.verify(header[7:], audience=config.bridge_url, service=True)
        if (claims["email"] != config.service_email or claims["sub"] != config.service_id
                or claims.get("email_verified") is not True):
            raise BoundaryError("service_identity_denied")
        return claims


class MetadataIdentity:
    def __init__(self, config, verifier, fetch=identity_fetch):
        self.config, self.verifier, self.fetch = config, verifier, fetch
        self.lock = threading.Lock()
        self.cached, self.expires = "", 0

    def __call__(self):
        with self.lock:
            if self.expires <= time.time() + 90:
                raw = self.fetch(METADATA_IDENTITY + "?audience=" + quote(self.config.bridge_url, safe="") + "&format=full", metadata=True)
                try:
                    token = raw.decode("ascii")
                except UnicodeError:
                    raise BoundaryError("metadata_identity_invalid") from None
                claims = self.verifier.service("Bearer " + token, self.config)
                self.cached, self.expires = token, claims["exp"]
            return self.cached


def request_gate(environ, config):
    if not config.origin:
        raise BoundaryError("entry_not_commissioned")
    actual = environ.get("HTTP_HOST") if config.role == "entry" else environ.get("HTTP_X_AUREON_PUBLIC_HOST")
    request_origin = next((origin for origin in config.origins() if origin.removeprefix("https://") == actual), None)
    if request_origin is None:
        raise BoundaryError("public_host_mismatch")
    if config.role == "entry" and environ.get("HTTP_X_FORWARDED_PROTO") != "https":
        raise BoundaryError("https_required")
    if "HTTP_ORIGIN" in environ and environ["HTTP_ORIGIN"] != request_origin:
        raise BoundaryError("same_origin_required")
    method = environ.get("REQUEST_METHOD", "")
    path = environ.get("PATH_INFO", "")
    if method not in {"GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"}:
        raise BoundaryError("method_denied")
    if method not in SAFE_METHODS and environ.get("HTTP_ORIGIN") != request_origin:
        raise BoundaryError("csrf_origin_required")
    if path == "/api" or path.startswith("/api/") or method not in SAFE_METHODS:
        if environ.get("HTTP_SEC_FETCH_SITE") not in {None, "same-origin"}:
            raise BoundaryError("cross_site_request_denied")
        if environ.get("HTTP_ORIGIN") != request_origin and environ.get("HTTP_SEC_FETCH_SITE") != "same-origin":
            raise BoundaryError("same_origin_evidence_required")
    for name, limit in (("HTTP_AUTHORIZATION", 8192), ("HTTP_X_AUREON_AUTH_RESOLUTION", 128)):
        if name in environ and (not isinstance(environ[name], str) or len(environ[name]) > limit or re.search(r"[\r\n\x00]", environ[name])):
            raise BoundaryError("auth_header_invalid")


def forwarded_headers(environ):
    result = {}
    for source, target in (("HTTP_ACCEPT", "Accept"), ("CONTENT_TYPE", "Content-Type"),
                           ("HTTP_AUTHORIZATION", "Authorization"),
                           ("HTTP_X_AUREON_AUTH_RESOLUTION", "X-Aureon-Auth-Resolution"),
                           ("HTTP_ORIGIN", "Origin"), ("HTTP_SEC_FETCH_SITE", "Sec-Fetch-Site")):
        if source in environ:
            value = environ[source]
            if len(value) > 8192 or re.search(r"[\r\n\x00]", value):
                raise BoundaryError("request_header_invalid")
            result[target] = value
    # Deliberate allowlist: no Cookie, client forwarding/identity headers, serverless
    # authorization, proxy headers, websocket upgrades, or arbitrary destinations.
    return result


def entry_mode_allowed(config, mode):
    if config.access_mode == "hybrid":
        return mode in {"iap", "user"}
    return mode == config.access_mode


def request_target(environ):
    path, query = environ.get("PATH_INFO", ""), environ.get("QUERY_STRING", "")
    if not path.startswith("/") or path.startswith("//") or re.search(r"[\x00-\x20\\]", path + query):
        raise BoundaryError("request_target_invalid")
    if any(part in {".", ".."} for part in unquote(path).split("/")):
        raise BoundaryError("request_target_invalid")
    # WSGI PATH_INFO is already URL decoded. Re-encode delimiters so a decoded '?'
    # cannot become a new query and encoded slashes cannot create another origin.
    target = quote(path, safe="/!$&'()*+,;=:@-._~")
    return target + ("?" + query if query else "")


def exchange(host, port, method, target, headers, body, *, context=None, timeout=30, limit=MAX_RESPONSE):
    connection = (http.client.HTTPSConnection(host, port, context=context, timeout=timeout)
                  if context is not None else http.client.HTTPConnection(host, port, timeout=timeout))
    timer = None
    deadline = time.monotonic() + timeout
    try:
        connection.connect()
        wire_socket = connection.sock
        def expire():
            try:
                wire_socket.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
        timer = threading.Timer(max(0, deadline - time.monotonic()), expire)
        timer.daemon = True
        timer.start()
        connection.request(method, target, body=body, headers=headers)
        upstream = connection.getresponse()
        if 300 <= upstream.status < 400 or upstream.getheader("Content-Encoding", "identity") != "identity":
            raise BoundaryError("upstream_response_denied")
        content = upstream.read(limit + 1)
        if len(content) > limit or time.monotonic() >= deadline:
            raise BoundaryError("upstream_response_limit")
        result_headers = {"Content-Type": upstream.getheader("Content-Type", "application/octet-stream")}
        retry = upstream.getheader("Retry-After", "")
        if re.fullmatch(r"[0-9]{1,6}(?:\.[0-9]{1,3})?", retry):
            result_headers["Retry-After"] = retry
        return upstream.status, result_headers, content
    except (OSError, http.client.HTTPException, ValueError):
        raise BoundaryError("upstream_unavailable") from None
    finally:
        if timer:
            timer.cancel()
        connection.close()


class Transport:
    def __init__(self, config):
        self.config = config
        self.context = None
        if config.role == "entry" and config.origin:
            if not config.ca_file or not Path(config.ca_file).is_file():
                raise BoundaryError("bridge_certificate_required")
            # This trust store contains ONLY the deployment's VM certificate.
            self.context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            self.context.minimum_version = ssl.TLSVersion.TLSv1_2
            self.context.load_verify_locations(cafile=config.ca_file)

    def __call__(self, method, target, headers, body, *, health=False):
        if self.config.role == "entry":
            return exchange(urlsplit(self.config.bridge_url).hostname, 8443, method, target, headers, body, context=self.context)
        return exchange("127.0.0.1", 5173, method, target, headers, body,
                        timeout=3 if health else 30, limit=4096 if health else MAX_RESPONSE)


def create_app(
    config=None,
    *,
    verifier=None,
    transport=None,
    identity=None,
    intent_signer=None,
):
    config = config or Config.from_env()
    config.validate()
    verifier = verifier or GoogleVerifier()
    transport = transport or Transport(config)
    identity = identity or MetadataIdentity(config, verifier)
    if config.role == "bridge" and intent_signer is None and config.intent_key_file:
        intent_signer = OperatorIntentSigner(config.intent_key_file)
    app = Flask("aureon_public_" + config.role, static_folder=None)
    app.config["MAX_CONTENT_LENGTH"] = MAX_BODY

    @app.after_request
    def response_policy(response):
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        if config.role == "entry":
            response.headers["Strict-Transport-Security"] = "max-age=31536000"
        return response

    @app.route("/", defaults={"rest": ""}, methods=["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
    @app.route("/<path:rest>", methods=["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
    def proxy(rest):
        del rest
        if not config.origin or not holds_ready():
            return jsonify(error="entry_not_commissioned", available=False), 503
        try:
            request_gate(request.environ, config)
            assertion = request.headers.get("X-Goog-Iap-Jwt-Assertion", "") if config.role == "entry" else request.headers.get("X-Aureon-Iap-Assertion", "")
            if config.role == "bridge":
                if request.host != urlsplit(config.bridge_url).netloc:
                    raise BoundaryError("bridge_host_mismatch")
                verifier.service(request.headers.get("X-Aureon-Service-Authorization", ""), config)
                entry_mode = request.headers.get("X-Aureon-Entry-Mode", "")
                if not entry_mode and config.access_mode == "iap":
                    # Backward-compatible owner bridge deployments predate the
                    # explicit route-mode header and are IAP-only by contract.
                    entry_mode = "iap"
                if not entry_mode_allowed(config, entry_mode):
                    raise BoundaryError("entry_mode_denied")
            else:
                entry_mode = config.access_mode
            if entry_mode == "user" and (request.path == "/api" or request.path.startswith("/api/")):
                # The customer origin must never rely on a downstream registrar
                # to distinguish anonymous traffic from the instance's legacy
                # telemetry processes. Require a tenant-shaped bearer for every
                # API request at the outer boundary and keep the three non-
                # operator loopback surfaces owner-only for every tenant.
                authorization = request.headers.get("Authorization", "")
                if not re.fullmatch(r"Bearer [A-Za-z0-9._-]{20,8192}", authorization):
                    raise BoundaryError("tenant_bearer_required")
                if request.path in INSTANCE_ONLY_API_PATHS:
                    raise BoundaryError("instance_surface_denied")
            if entry_mode == "iap":
                verifier.user(assertion, config)
            elif assertion:
                # A public-user request cannot smuggle an identity assertion
                # into the bridge and have it interpreted by a different mode.
                raise BoundaryError("unexpected_iap_assertion")
            target = request_target(request.environ)
            headers = forwarded_headers(request.environ)
        except BoundaryError:
            return jsonify(error="request_not_authorized", available=False), 403
        try:
            if config.role == "entry":
                headers.update({"X-Aureon-Service-Authorization": "Bearer " + identity(),
                                "X-Aureon-Entry-Mode": entry_mode,
                                "X-Aureon-Public-Host": config.origin.removeprefix("https://")})
                if entry_mode == "iap":
                    headers["X-Aureon-Iap-Assertion"] = assertion
                else:
                    authorization = headers.get("Authorization", "")
                    headers["X-Aureon-Auth-Resolution"] = (
                        "tenant-bearer"
                        if re.fullmatch(r"Bearer [A-Za-z0-9._-]{20,8192}", authorization)
                        else "anonymous"
                    )
            else:
                # Every bridge request requires live, matching loopback health.
                status, _, raw = transport("GET", HEALTH, {}, b"", health=True)
                state = json.loads(raw)
                if (status != 200 or not isinstance(state, dict) or state.get("schema") != "aureon.cloud-http-health.v1"
                        or state.get("role") != "ui-gateway" or state.get("revision") != config.revision
                        or state.get("ready") is not True or state.get("deployment_hold") is not True
                        or state.get("release_authority") is not False):
                    raise BoundaryError("runtime_not_ready")
                # Only after BOTH signed identities + origin checks are valid may
                # the bridge supply same-origin evidence to the loopback gateway.
                # Any client Authorization/failed marker remains present exactly.
                headers.update({"Origin": "http://127.0.0.1:5173", "Sec-Fetch-Site": "same-origin"})
                if request.method == "POST" and _intent_route_rule(target) is not None:
                    if entry_mode != "iap" or intent_signer is None:
                        raise BoundaryError("intent_signer_unavailable")
                    headers[INTENT_HEADER] = intent_signer.sign(
                        method=request.method,
                        target=target,
                        body=request.get_data(),
                        mode=entry_mode,
                        revision=config.revision,
                    )
            status, response_headers, body = transport(request.method, target, headers, request.get_data())
            return Response(body, status=status, headers=response_headers)
        except (BoundaryError, ValueError, TypeError):
            return jsonify(error="cloud_runtime_unavailable", available=False), 502

    @app.errorhandler(413)
    def too_large(error):
        del error
        return jsonify(error="request_too_large"), 413

    return app
