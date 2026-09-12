"""Private cloud HTTP composition; no release, executor, or provider authority.

Only the distinct cloud HTTP units own these ports. Do not also schedule the
Windows operator_gateway/frontend_vite registry entries on the cloud host.
The stdlib-only secret worker communicates exclusively through an anonymous pipe.
"""
from __future__ import annotations

import argparse
import base64
import binascii
import hmac
import http.client
import ipaddress
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import threading
import time
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener


HOLDS = {
    "AUREON_DEPLOYMENT_HOLD": "1",
    "AUREON_DISABLE_REAL_ORDERS": "1",
    "AUREON_DISABLE_EXCHANGE_MUTATIONS": "1",
    "AUREON_ORDER_INTENT_PUBLISH": "0",
    "AUREON_LIVE_TRADING": "0",
    "AUREON_UNIFIED_ORDER_EXECUTOR": "0",
}
PORTS = {"operator": 8080, "ui-gateway": 5173}
HEALTH_PATH = "/__aureon_health"
HEALTH_SCHEMA = "aureon.cloud-http-health.v1"
MAX_REQUEST = 256 * 1024
MAX_RESPONSE = 8 * 1024 * 1024
AUTH_RESOLUTION_KEY = "HTTP_X_AUREON_AUTH_RESOLUTION"
METADATA_BASE = "http://metadata.google.internal/computeMetadata/v1/"
SECRET_DEADLINE = 20
SECRET_CLEANUP = 2


class CloudHTTPError(RuntimeError):
    """Only fixed, non-sensitive error codes may leave this module."""


def require_holds(environment=None):
    environment = os.environ if environment is None else environment
    if any(environment.get(name) != value for name, value in HOLDS.items()):
        raise CloudHTTPError("cloud_deployment_holds_required")


def holds_ready():
    return all(os.environ.get(name) == value for name, value in HOLDS.items())


def validate_secret_reference(project, secret, version):
    if not isinstance(project, str) or not re.fullmatch(r"(?:[a-z][a-z0-9-]{4,61}[a-z0-9]|[0-9]{6,20})", project):
        raise CloudHTTPError("cloud_project_invalid")
    if not isinstance(secret, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,255}", secret):
        raise CloudHTTPError("cloud_secret_reference_invalid")
    if not isinstance(version, str) or not re.fullmatch(r"[1-9][0-9]{0,18}", version):
        raise CloudHTTPError("cloud_secret_version_must_be_pinned")


def validate_bearer(raw):
    if not isinstance(raw, bytes) or not re.fullmatch(rb"[A-Za-z0-9_-]{48,128}", raw):
        raise CloudHTTPError("cloud_secret_payload_invalid")
    return raw.decode("ascii")


def validate_supabase_tenant_config(raw):
    """Validate the complete public Supabase tenant-auth configuration.

    The publishable key is intentionally client-visible, but it still travels
    through Secret Manager so one pinned, checksummed deployment input owns the
    operator's tenant-verification configuration.  Extra fields are rejected so
    this payload can never grow into a provider/service credential carrier.
    """
    if not isinstance(raw, bytes) or not 1 <= len(raw) <= 8192:
        raise CloudHTTPError("cloud_tenant_secret_payload_invalid")
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeError, ValueError, TypeError) as exc:
        raise CloudHTTPError("cloud_tenant_secret_payload_invalid") from exc
    if not isinstance(payload, dict) or set(payload) != {"project_url", "publishable_key"}:
        raise CloudHTTPError("cloud_tenant_secret_payload_invalid")
    project_url = payload.get("project_url")
    publishable_key = payload.get("publishable_key")
    if not isinstance(project_url, str) or not isinstance(publishable_key, str):
        raise CloudHTTPError("cloud_tenant_secret_payload_invalid")
    parsed = urlsplit(project_url)
    host = parsed.hostname or ""
    if (parsed.scheme != "https" or parsed.port is not None or parsed.username is not None
            or parsed.password is not None or parsed.path not in {"", "/"} or parsed.query
            or parsed.fragment or not re.fullmatch(r"[a-z0-9]{20}\.supabase\.co", host)):
        raise CloudHTTPError("cloud_tenant_project_url_invalid")
    if (not 20 <= len(publishable_key) <= 4096
            or re.search(r"[^\x21-\x7e]", publishable_key)
            or not (publishable_key.startswith("sb_publishable_") or publishable_key.count(".") == 2)):
        raise CloudHTTPError("cloud_tenant_publishable_key_invalid")
    if publishable_key.count(".") == 2:
        try:
            segment = publishable_key.split(".")[1]
            segment += "=" * (-len(segment) % 4)
            claims = json.loads(base64.urlsafe_b64decode(segment.encode("ascii")))
        except (ValueError, UnicodeError, binascii.Error, TypeError) as exc:
            raise CloudHTTPError("cloud_tenant_publishable_key_invalid") from exc
        if (not isinstance(claims, dict) or claims.get("role") != "anon"
                or claims.get("ref") not in {None, host.split(".", 1)[0]}):
            raise CloudHTTPError("cloud_tenant_publishable_key_invalid")
    return {"project_url": project_url.rstrip("/"), "publishable_key": publishable_key}


def crc32c(data):
    """Castagnoli CRC, verified with the standard 123456789 test vector."""
    value = 0xFFFFFFFF
    for byte in data:
        value ^= byte
        for _ in range(8):
            value = (value >> 1) ^ (0x82F63B78 if value & 1 else 0)
    return value ^ 0xFFFFFFFF


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise CloudHTTPError("cloud_secret_redirect_denied")


def _secret_http_read(url, headers, *, metadata=False):
    # Only fetch_secret_worker constructs URLs. No environment proxies, alternate
    # credentials, redirect traversal, or unbounded response body is accepted.
    opener = build_opener(ProxyHandler({}), NoRedirects())
    with opener.open(Request(url, headers=headers), timeout=5) as response:
        if response.status != 200:
            raise CloudHTTPError("cloud_secret_access_failed")
        if metadata and response.headers.get("Metadata-Flavor") != "Google":
            raise CloudHTTPError("cloud_metadata_identity_invalid")
        data = response.read(16385)
        if len(data) > 16384:
            raise CloudHTTPError("cloud_secret_response_too_large")
        return data


def decode_secret_payload(raw, *, resource):
    try:
        result = json.loads(raw)
        if not isinstance(result, dict) or result.get("name") != resource:
            raise CloudHTTPError("cloud_secret_resource_mismatch")
        payload = result["payload"]
        if not isinstance(payload, dict) or not isinstance(payload.get("data"), str):
            raise CloudHTTPError("cloud_secret_payload_invalid")
        data = base64.b64decode(payload["data"], validate=True)
        checksum = payload.get("dataCrc32c")
        if not isinstance(checksum, str) or not re.fullmatch(r"[0-9]{1,10}", checksum):
            raise CloudHTTPError("cloud_secret_checksum_missing")
        if int(checksum) != crc32c(data):
            raise CloudHTTPError("cloud_secret_checksum_mismatch")
        return data
    except (ValueError, KeyError, TypeError, binascii.Error) as exc:
        raise CloudHTTPError("cloud_secret_response_invalid") from exc


def decode_secret_response(raw, *, resource):
    return validate_bearer(decode_secret_payload(raw, resource=resource))


def fetch_secret_worker(project, secret, version, reader=_secret_http_read, *, secret_kind="bearer"):
    """Runs only in the isolated, deadline-bounded child, never logs payloads."""
    validate_secret_reference(project, secret, version)
    header = {"Metadata-Flavor": "Google"}
    project_id = reader(METADATA_BASE + "project/project-id", header, metadata=True).decode("ascii")
    project_number = reader(METADATA_BASE + "project/numeric-project-id", header, metadata=True).decode("ascii")
    if project not in {project_id, project_number} or not re.fullmatch(r"[0-9]{6,20}", project_number):
        raise CloudHTTPError("cloud_metadata_project_mismatch")
    identity = json.loads(reader(METADATA_BASE + "instance/service-accounts/default/token", header, metadata=True))
    token = identity.get("access_token")
    expires = identity.get("expires_in")
    if (not isinstance(token, str) or not 20 <= len(token) <= 8192
            or re.search(r"[^\x21-\x7e]", token)
            or identity.get("token_type", "").lower() != "bearer"
            or type(expires) is not int or not 30 <= expires <= 86400):
        raise CloudHTTPError("cloud_metadata_token_invalid")
    resource = f"projects/{project_number}/secrets/{secret}/versions/{version}"
    raw = reader("https://secretmanager.googleapis.com/v1/" + resource + ":access",
                 {"Authorization": "Bearer " + token, "Accept": "application/json"})
    payload = decode_secret_payload(raw, resource=resource)
    if secret_kind == "bearer":
        return validate_bearer(payload)
    if secret_kind == "supabase-tenant":
        return json.dumps(validate_supabase_tenant_config(payload), sort_keys=True, separators=(",", ":"))
    raise CloudHTTPError("cloud_secret_kind_invalid")


def worker_environment(environment=None):
    environment = os.environ if environment is None else environment
    # No provider/API credentials, proxy settings, PYTHONPATH, or SDK key files.
    return {key: environment[key] for key in ("SYSTEMROOT", "WINDIR", "TEMP", "TMP", "LANG", "LC_ALL") if key in environment}


def load_cloud_secret(project, secret, version, *, popen=subprocess.Popen):
    validate_secret_reference(project, secret, version)
    command = [sys.executable, "-I", "-S", "-B", str(Path(__file__).resolve()),
               "--secret-worker", "--project", project, "--secret", secret, "--secret-version", version]
    process = popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE, env=worker_environment(), close_fds=True)
    try:
        output, errors = process.communicate(timeout=SECRET_DEADLINE)
    except subprocess.TimeoutExpired:
        process.kill()
        try:
            process.communicate(timeout=SECRET_CLEANUP)
        except subprocess.TimeoutExpired:
            raise CloudHTTPError("cloud_secret_worker_cleanup_failed") from None
        raise CloudHTTPError("cloud_secret_deadline_exceeded") from None
    if process.returncode != 0 or errors:
        # Neither stdout nor stderr (nor the process exception) is logged.
        raise CloudHTTPError("cloud_secret_access_failed")
    return validate_bearer(output)


def load_cloud_tenant_config(project, secret, version, *, popen=subprocess.Popen):
    validate_secret_reference(project, secret, version)
    command = [sys.executable, "-I", "-S", "-B", str(Path(__file__).resolve()),
               "--secret-worker", "--secret-kind", "supabase-tenant", "--project", project,
               "--secret", secret, "--secret-version", version]
    process = popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE, env=worker_environment(), close_fds=True)
    try:
        output, errors = process.communicate(timeout=SECRET_DEADLINE)
    except subprocess.TimeoutExpired:
        process.kill()
        try:
            process.communicate(timeout=SECRET_CLEANUP)
        except subprocess.TimeoutExpired:
            raise CloudHTTPError("cloud_secret_worker_cleanup_failed") from None
        raise CloudHTTPError("cloud_secret_deadline_exceeded") from None
    if process.returncode != 0 or errors:
        raise CloudHTTPError("cloud_secret_access_failed")
    return validate_supabase_tenant_config(output)


def _loopback(value, *, allow_name=False):
    if allow_name and value == "localhost":
        return True
    try:
        address = ipaddress.ip_address(value)
        if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped:
            address = address.ipv4_mapped
        return address.is_loopback
    except ValueError:
        return False


def _origin(value, *, host=False):
    if not isinstance(value, str) or not value or len(value) > (255 if host else 512):
        return None
    if re.search(r"[\s\\,@?#]", value) or (host and "/" in value):
        return None
    try:
        parsed = urlsplit("http://" + value if host else value)
        if (parsed.scheme != "http" or not _loopback(parsed.hostname, allow_name=True)
                or parsed.username or parsed.password or parsed.path not in {"", "/"}
                or parsed.query or parsed.fragment):
            return None
        port = parsed.port or 80
        return parsed.scheme, parsed.hostname, port
    except (ValueError, TypeError):
        return None


def inspect_ingress(environ):
    if not _loopback(environ.get("REMOTE_ADDR", "")):
        return "loopback_client_required"
    expected = _origin(environ.get("HTTP_HOST"), host=True)
    if expected is None:
        return "loopback_host_required"
    if "HTTP_SEC_FETCH_SITE" in environ and environ["HTTP_SEC_FETCH_SITE"] not in {"same-origin", "none"}:
        return "cross_site_request_denied"
    if "HTTP_ORIGIN" in environ and _origin(environ["HTTP_ORIGIN"]) != expected:
        return "same_origin_required"
    for name, limit in (("HTTP_AUTHORIZATION", 8192), (AUTH_RESOLUTION_KEY, 128)):
        if name in environ and (not isinstance(environ[name], str) or len(environ[name]) > limit
                                or re.search(r"[\r\n\x00]", environ[name])):
            return "bounded_auth_header_required"
    return None


def same_origin_evidence(environ):
    if inspect_ingress(environ) is not None:
        return False
    if "HTTP_ORIGIN" in environ:
        return _origin(environ["HTTP_ORIGIN"]) == _origin(environ.get("HTTP_HOST"), host=True)
    return environ.get("HTTP_SEC_FETCH_SITE") == "same-origin"


def proxy_route(path):
    if path == "/api/orca-observations":
        return 8888, "/api/observations", True
    if path in {"/api/terminal-state", "/api/flight-test"}:
        return 8791, path, True
    if path == "/api" or path.startswith("/api/"):
        return 8080, path, False
    raise CloudHTTPError("cloud_api_route_invalid")


def proxy_headers(environ, bearer, port):
    result = {}
    for original, forwarded in (("HTTP_ACCEPT", "Accept"), ("CONTENT_TYPE", "Content-Type")):
        if original in environ:
            value = environ[original]
            if len(value) > 2048 or re.search(r"[\r\n\x00]", value):
                raise CloudHTTPError("cloud_proxy_header_invalid")
            result[forwarded] = value
    if port == 8080:
        if "HTTP_AUTHORIZATION" in environ:
            # Including empty/invalid: caller identity can never fall back to admin.
            result["Authorization"] = environ["HTTP_AUTHORIZATION"]
        elif AUTH_RESOLUTION_KEY not in environ and same_origin_evidence(environ):
            result["Authorization"] = "Bearer " + bearer
    return result


def loopback_request(port, method, target, headers, body=b"", *, timeout=30, max_bytes=MAX_RESPONSE):
    if port not in {8080, 8791, 8888} or not target.startswith("/") or target.startswith("//"):
        raise CloudHTTPError("cloud_upstream_route_invalid")
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=timeout)
    deadline = time.monotonic() + timeout
    timer = None
    try:
        connection.connect()
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise CloudHTTPError("cloud_upstream_unavailable")
        wire_socket = connection.sock

        def expire():
            # Socket shutdown also interrupts buffered headers/chunk framing;
            # a read timeout alone would reset on every byte of a slow response.
            try:
                wire_socket.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass

        timer = threading.Timer(remaining, expire)
        timer.daemon = True
        timer.start()
        connection.request(method, target, body=body, headers=headers)
        response = connection.getresponse()
        if 300 <= response.status < 400:
            raise CloudHTTPError("cloud_upstream_redirect_denied")
        if response.getheader("Content-Encoding", "identity") != "identity":
            raise CloudHTTPError("cloud_upstream_encoding_unsupported")
        content = response.read(max_bytes + 1)
        if time.monotonic() >= deadline:
            raise CloudHTTPError("cloud_upstream_unavailable")
        if len(content) > max_bytes:
            raise CloudHTTPError("cloud_upstream_response_too_large")
        # Whitelisted response metadata only; no cookies, redirects, CORS or auth.
        response_headers = {"Content-Type": response.getheader("Content-Type", "application/octet-stream")}
        retry = response.getheader("Retry-After")
        if retry and re.fullmatch(r"[0-9]{1,6}(?:\.[0-9]{1,3})?", retry):
            response_headers["Retry-After"] = retry
        return response.status, response_headers, content
    except (OSError, http.client.HTTPException, ValueError):
        raise CloudHTTPError("cloud_upstream_unavailable") from None
    finally:
        if timer is not None:
            timer.cancel()
        connection.close()


def _health(role, revision, ready, *, tenant_auth_ready=False):
    return {"schema": HEALTH_SCHEMA, "role": role, "revision": revision,
            "ready": bool(ready), "deployment_hold": holds_ready(), "release_authority": False,
            "tenant_auth_ready": bool(tenant_auth_ready)}


def _json_wsgi(start_response, status, data):
    body = json.dumps(data, separators=(",", ":")).encode("utf-8")
    start_response(status, [("Content-Type", "application/json"), ("Content-Length", str(len(body))),
                            ("Cache-Control", "no-store"), ("X-Content-Type-Options", "nosniff")])
    return [body]


def operator_envelope(app, revision, *, tenant_auth_ready=False):
    """Health is the only exact-path bypass. All API identity/HNC stays in app."""
    def wrapped(environ, start_response):
        reason = inspect_ingress(environ)
        if reason:
            return _json_wsgi(start_response, "403 Forbidden", {"error": reason})
        if environ.get("PATH_INFO") == HEALTH_PATH and environ.get("REQUEST_METHOD") == "GET":
            ready = holds_ready() and tenant_auth_ready
            return _json_wsgi(start_response, "200 OK" if ready else "503 Service Unavailable",
                              _health("operator", revision, ready, tenant_auth_ready=tenant_auth_ready))
        if not holds_ready():
            return _json_wsgi(start_response, "503 Service Unavailable", {"error": "cloud_deployment_holds_required"})
        return app(environ, start_response)
    return wrapped


def validate_dist(dist_root):
    root = Path(dist_root).resolve(strict=True)
    index = root / "index.html"
    if not index.is_file() or index.is_symlink() or not 0 < index.stat().st_size <= 256 * 1024:
        raise CloudHTTPError("cloud_built_index_required")
    text = index.read_text(encoding="utf-8")
    if any(marker in text for marker in ("@vite/client", "/src/main.", "jsx-dev-runtime")):
        raise CloudHTTPError("cloud_production_build_required")
    assets = re.findall(r'(?:src|href)=["\'](/assets/[^"\']+)["\']', text)
    if not assets or not any(asset.endswith(".js") for asset in assets):
        raise CloudHTTPError("cloud_built_assets_required")
    for asset in assets:
        candidate = (root / asset.lstrip("/")).resolve(strict=True)
        if not candidate.is_relative_to(root) or not candidate.is_file():
            raise CloudHTTPError("cloud_built_asset_invalid")
    return root, tuple((root / asset.lstrip("/")).resolve() for asset in assets)


def create_ui_gateway(dist_root, revision, bearer, transport=loopback_request):
    from flask import Flask, Response, jsonify, request, send_file

    require_holds()
    validate_bearer(bearer.encode("ascii"))
    root, assets = validate_dist(dist_root)
    app = Flask("aureon_cloud_ui", static_folder=None)
    app.config["MAX_CONTENT_LENGTH"] = MAX_REQUEST

    @app.before_request
    def ingress():
        reason = inspect_ingress(request.environ)
        if reason:
            return jsonify(error=reason), 403
        if not holds_ready() and request.path != HEALTH_PATH:
            return jsonify(error="cloud_deployment_holds_required"), 503
        return None

    @app.after_request
    def private_response(response):
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        return response

    @app.get(HEALTH_PATH)
    def health():
        ready = False
        tenant_auth_ready = False
        if holds_ready() and (root / "index.html").is_file() and all(path.is_file() for path in assets):
            try:
                status, _, body = transport(8080, "GET", HEALTH_PATH, {}, timeout=3, max_bytes=4096)
                upstream = json.loads(body)
                tenant_auth_ready = upstream.get("tenant_auth_ready") is True if isinstance(upstream, dict) else False
                ready = (status == 200 and isinstance(upstream, dict)
                         and upstream.get("schema") == HEALTH_SCHEMA and upstream.get("role") == "operator"
                         and upstream.get("revision") == revision and upstream.get("ready") is True
                         and upstream.get("deployment_hold") is True and upstream.get("release_authority") is False
                         and tenant_auth_ready)
            except (CloudHTTPError, ValueError, TypeError):
                pass
        return jsonify(_health("ui-gateway", revision, ready,
                               tenant_auth_ready=tenant_auth_ready)), 200 if ready else 503

    @app.route("/api", defaults={"rest": ""}, methods=["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
    @app.route("/api/<path:rest>", methods=["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
    def api(rest):
        del rest
        try:
            port, target, passive = proxy_route(request.path)
            if passive and request.method not in {"GET", "HEAD"}:
                return jsonify(error="cloud_observation_route_read_only"), 405
            if request.query_string:
                target += "?" + request.query_string.decode("ascii")
            headers = proxy_headers(request.environ, bearer, port)
            status, response_headers, body = transport(port, request.method, target, headers, request.get_data())
            return Response(body, status=status, headers=response_headers)
        except CloudHTTPError:
            # Uniform explicit unavailable response; no fallback/synthetic data.
            return jsonify(error="cloud_upstream_unavailable", available=False), 502
        except UnicodeError:
            return jsonify(error="cloud_request_encoding_invalid"), 400

    @app.get("/", defaults={"path": ""})
    @app.get("/<path:path>")
    def static_ui(path):
        parts = path.split("/")
        if "\\" in path or any(part.startswith(".") for part in parts if part):
            return jsonify(error="cloud_static_path_invalid"), 404
        candidate = (root / path).resolve()
        if not candidate.is_relative_to(root):
            return jsonify(error="cloud_static_path_invalid"), 404
        if path and candidate.is_file():
            return send_file(candidate, conditional=True)
        if path.startswith("assets/") or (path and Path(path).suffix):
            return jsonify(error="cloud_static_asset_missing"), 404
        return send_file(root / "index.html", conditional=True)

    return app


def build_operator(source_root, revision, bearer, tenant_config):
    require_holds()
    validate_bearer(bearer.encode("ascii"))
    root = Path(source_root).resolve(strict=True)
    if not (root / "aureon/operator/operator_server.py").is_file():
        raise CloudHTTPError("cloud_operator_source_missing")
    tenant_config = validate_supabase_tenant_config(
        json.dumps(tenant_config, sort_keys=True, separators=(",", ":")).encode("utf-8")
    )
    settings = {
        "AUREON_OPERATOR_API_KEY": bearer, "AUREON_OPERATOR_ENV": "production",
        "AUREON_OPERATOR_DEV": "0", "AUREON_OPERATOR_HOST": "127.0.0.1", "AUREON_OPERATOR_PORT": "8080",
        "AUREON_OPERATOR_RATE_RPS": "40", "AUREON_OPERATOR_RATE_BURST": "160",
        "AUREON_OPERATOR_HTTP_PROCESSES": "1", "AUREON_OPERATOR_REPLICAS": "1",
        "AUREON_OPERATOR_MAX_BODY": str(MAX_REQUEST), "AUREON_OPERATOR_TRUSTED_PROXY_CIDRS": "",
        "SERO_WORKSPACE": str(root.parent),
        "AUREON_SUPABASE_URL": tenant_config["project_url"],
        "AUREON_SUPABASE_PUBLISHABLE_KEY": tenant_config["publishable_key"],
    }
    os.environ.update(settings)
    sys.path[:0] = [str(root), str(root.parent)]
    os.chdir(root)
    from aureon.operator.operator_server import build_boot_app
    app = build_boot_app()
    require_holds()
    if any(not hmac.compare_digest(os.environ.get(key, ""), value) for key, value in settings.items()):
        raise CloudHTTPError("cloud_operator_boot_profile_changed")
    if getattr(app, "debug", False) or getattr(app, "testing", False):
        raise CloudHTTPError("cloud_operator_production_app_required")
    return operator_envelope(app, revision, tenant_auth_ready=True)


def reserve_port(role):
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # No SO_REUSEPORT: fail before importing/booting a second operator process.
    try:
        listener.bind(("127.0.0.1", PORTS[role]))
        listener.listen(128)
    except OSError:
        listener.close()
        raise CloudHTTPError("cloud_http_port_already_owned") from None
    return listener


def run(role=None, argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--role", choices=tuple(PORTS), default=role)
    parser.add_argument("--source-root")
    parser.add_argument("--dist-root")
    parser.add_argument("--revision")
    parser.add_argument("--project", required=True)
    parser.add_argument("--secret", required=True)
    parser.add_argument("--secret-version", required=True)
    parser.add_argument("--tenant-secret")
    parser.add_argument("--tenant-secret-version")
    parser.add_argument("--secret-worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--secret-kind", choices=("bearer", "supabase-tenant"), default="bearer",
                        help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    try:
        validate_secret_reference(args.project, args.secret, args.secret_version)
        if args.secret_worker:
            # Refuse interactive use; the credential goes only to the parent pipe.
            if sys.stdout.isatty():
                raise CloudHTTPError("cloud_secret_worker_pipe_required")
            token = fetch_secret_worker(args.project, args.secret, args.secret_version,
                                        secret_kind=args.secret_kind)
            sys.stdout.buffer.write(token.encode("ascii"))
            sys.stdout.buffer.flush()
            return 0
        require_holds()
        if args.role not in PORTS or (role is not None and args.role != role):
            raise CloudHTTPError("cloud_http_role_invalid")
        tenant_reference = bool(args.tenant_secret or args.tenant_secret_version)
        if args.role == "operator" and not (args.tenant_secret and args.tenant_secret_version):
            raise CloudHTTPError("cloud_tenant_auth_reference_required")
        if args.role != "operator" and tenant_reference:
            raise CloudHTTPError("cloud_tenant_auth_reference_operator_only")
        if args.role == "operator":
            validate_secret_reference(args.project, args.tenant_secret, args.tenant_secret_version)
        if not re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", args.revision or ""):
            raise CloudHTTPError("cloud_revision_required")
        if not args.source_root or not Path(args.source_root).is_dir():
            raise CloudHTTPError("cloud_source_root_required")
        if args.role == "ui-gateway":
            if not args.dist_root:
                raise CloudHTTPError("cloud_dist_root_required")
            validate_dist(args.dist_root)
        # Resolve production server before any cognition/services are imported.
        from waitress import create_server
        with reserve_port(args.role) as listener:
            bearer = load_cloud_secret(args.project, args.secret, args.secret_version)
            tenant_config = (load_cloud_tenant_config(args.project, args.tenant_secret,
                                                       args.tenant_secret_version)
                             if args.role == "operator" else None)
            app = (build_operator(args.source_root, args.revision, bearer, tenant_config) if args.role == "operator"
                   else create_ui_gateway(args.dist_root, args.revision, bearer))
            server = create_server(app, sockets=[listener], threads=8, max_request_body_size=MAX_REQUEST,
                                   max_request_header_size=32768, expose_tracebacks=False, clear_untrusted_proxy_headers=True)
            try:
                server.run()
            finally:
                server.close()
                server.task_dispatcher.shutdown(cancel_pending=True, timeout=5)
        return 0
    except CloudHTTPError as error:
        print(str(error), file=sys.stderr)
        return 1
    except Exception:
        # Do not serialize credential, upstream, configuration, or import errors.
        print("cloud_http_startup_failed", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(run())
