"""Offline cloud composition contract tests; no cloud calls or economic actions."""
import base64
import importlib.util
import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from flask import Flask, jsonify, request
from werkzeug.test import Client
from werkzeug.wrappers import Response

MODULE = Path(__file__).resolve().parents[1] / "cloud_http_runtime.py"
spec = importlib.util.spec_from_file_location("cloud_http_runtime", MODULE)
cloud = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cloud)

# Deliberately generated test fixture, never a deployment credential.
FIXTURE = "offline_fixture_only_" * 3
REVISION = "a" * 40
RESOURCE = "projects/123456789/secrets/operator-http/versions/7"


def secret_response(data=FIXTURE.encode(), **override):
    response = {"name": RESOURCE, "payload": {"data": base64.b64encode(data).decode(), "dataCrc32c": str(cloud.crc32c(data))}}
    response.update(override)
    return json.dumps(response).encode()


class SecretTests(unittest.TestCase):
    def test_crc32c_and_exact_payload(self):
        self.assertEqual(cloud.crc32c(b"123456789"), 0xE3069283)
        self.assertEqual(cloud.decode_secret_response(secret_response(), resource=RESOURCE), FIXTURE)

    def test_unpinned_references_and_unsafe_payloads_rejected(self):
        for version in ("latest", "0", "7:access", "../7", " 7", "07"):
            with self.subTest(version=version), self.assertRaises(cloud.CloudHTTPError):
                cloud.validate_secret_reference("test-project", "operator-http", version)
        for value in (b"short", FIXTURE.encode() + b"\n", b"X" * 129, b'{"bearer":"value"}'):
            with self.assertRaises(cloud.CloudHTTPError):
                cloud.validate_bearer(value)

    def test_wrong_resource_and_checksum_rejected(self):
        for raw in (secret_response(name=RESOURCE + "0"), secret_response(payload={"data": base64.b64encode(FIXTURE.encode()).decode(), "dataCrc32c": "1"}),
                    secret_response(payload={"data": "***", "dataCrc32c": "0"}), b"null"):
            with self.assertRaises(cloud.CloudHTTPError):
                cloud.decode_secret_response(raw, resource=RESOURCE)

    def test_metadata_identity_only_and_exact_destination(self):
        calls = []
        def reader(url, headers, **options):
            calls.append((url, headers, options))
            if url.endswith("project/project-id"):
                return b"test-project"
            if url.endswith("project/numeric-project-id"):
                return b"123456789"
            if url.endswith("default/token"):
                return json.dumps({"access_token": "offline_metadata_fixture", "expires_in": 3600, "token_type": "Bearer"}).encode()
            return secret_response()
        self.assertEqual(cloud.fetch_secret_worker("test-project", "operator-http", "7", reader), FIXTURE)
        self.assertEqual(len(calls), 4)
        for url, headers, options in calls[:3]:
            self.assertTrue(url.startswith(cloud.METADATA_BASE))
            self.assertEqual(headers, {"Metadata-Flavor": "Google"})
            self.assertTrue(options["metadata"])
        self.assertEqual(calls[-1][0], "https://secretmanager.googleapis.com/v1/" + RESOURCE + ":access")
        self.assertEqual(calls[-1][1]["Authorization"], "Bearer offline_metadata_fixture")

    def test_wrong_metadata_project_rejected_before_access(self):
        calls = []
        def reader(url, headers, **options):
            calls.append(url)
            return b"wrong-project" if url.endswith("project/project-id") else b"123456789"
        with self.assertRaises(cloud.CloudHTTPError):
            cloud.fetch_secret_worker("test-project", "operator-http", "7", reader)
        self.assertEqual(len(calls), 2)

    def test_worker_env_strips_credentials_proxies_and_pythonpath(self):
        environment = {"LANG": "C.UTF-8", "TEMP": "temp", "GOOGLE_APPLICATION_CREDENTIALS": "forbidden",
                       "HTTP_PROXY": "forbidden", "AUREON_OPERATOR_API_KEY": "forbidden", "PYTHONPATH": "forbidden"}
        self.assertEqual(cloud.worker_environment(environment), {"LANG": "C.UTF-8", "TEMP": "temp"})

    def test_worker_pipe_and_timeout_kill_reap_contract(self):
        captured = {}
        class Child:
            returncode = 0
            killed = False
            def communicate(self, timeout):
                captured.setdefault("timeouts", []).append(timeout)
                if not self.killed:
                    raise subprocess.TimeoutExpired("offline_worker", timeout)
                return b"", b""
            def kill(self):
                self.killed = True
        def popen(command, **kwargs):
            captured.update(command=command, options=kwargs)
            captured["child"] = Child()
            return captured["child"]
        with self.assertRaisesRegex(cloud.CloudHTTPError, "deadline_exceeded"):
            cloud.load_cloud_secret("test-project", "operator-http", "7", popen=popen)
        self.assertTrue(captured["child"].killed)
        self.assertEqual(captured["timeouts"], [cloud.SECRET_DEADLINE, cloud.SECRET_CLEANUP])
        self.assertEqual(captured["command"][1:4], ["-I", "-S", "-B"])
        self.assertEqual(captured["options"]["stdout"], subprocess.PIPE)
        self.assertNotIn(FIXTURE, " ".join(captured["command"]))

    def test_worker_failure_does_not_reflect_output(self):
        class Child:
            returncode = 1
            def communicate(self, timeout):
                return FIXTURE.encode(), FIXTURE.encode()
        with self.assertRaises(cloud.CloudHTTPError) as error:
            cloud.load_cloud_secret("test-project", "operator-http", "7", popen=lambda *a, **k: Child())
        self.assertEqual(str(error.exception), "cloud_secret_access_failed")


class GatewayTests(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict(os.environ, cloud.HOLDS)
        self.environment.start()
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        (self.root / "assets").mkdir()
        (self.root / "assets/app.js").write_text("window.example=true", encoding="utf-8")
        (self.root / "index.html").write_text('<html><script type="module" src="/assets/app.js"></script><div id="root"></div></html>', encoding="utf-8")
        self.calls = []
        self.backend = Flask("offline_operator_fixture")

        @self.backend.route("/api/me", methods=["GET"])
        def me():
            if request.headers.get("Authorization") != "Bearer " + FIXTURE:
                return jsonify(error="unauthenticated"), 401
            return jsonify(authenticated=True)

        @self.backend.route("/api/hnc/dispatch", methods=["POST"])
        def held():
            if request.headers.get("Authorization") != "Bearer " + FIXTURE:
                return jsonify(error="unauthenticated"), 401
            return jsonify(error="production_magic_star_release_unavailable", dispatch=False), 503

        self.operator = Client(cloud.operator_envelope(self.backend, REVISION), Response)
        self.app = cloud.create_ui_gateway(self.root, REVISION, FIXTURE, self.transport)
        self.client = self.app.test_client()

    def tearDown(self):
        self.directory.cleanup()
        self.environment.stop()

    def transport(self, port, method, target, headers, body=b"", **kwargs):
        self.calls.append((port, method, target, dict(headers), body))
        if port == 8080:
            response = self.operator.open(target, method=method, headers=headers, data=body,
                                          base_url="http://127.0.0.1:8080", environ_overrides={"REMOTE_ADDR": "127.0.0.1"})
            return response.status_code, {"Content-Type": "application/json"}, response.data
        return 200, {"Content-Type": "application/json"}, b'{"available":true,"source":"offline_fixture"}'

    def get(self, path="/api/me", headers=None, **kwargs):
        return self.client.get(path, headers=headers or {}, base_url="http://127.0.0.1:5173", **kwargs)

    def test_matching_origin_and_same_origin_fetch_inject(self):
        for headers in ({"Origin": "http://127.0.0.1:5173"}, {"Sec-Fetch-Site": "same-origin"}):
            response = self.get(headers=headers)
            self.assertEqual(response.status_code, 200)
            self.assertNotIn(FIXTURE.encode(), response.data)

    def test_missing_evidence_none_and_auth_failure_never_inject(self):
        for headers in ({}, {"Sec-Fetch-Site": "none"}, {"Origin": "http://127.0.0.1:5173", "X-Aureon-Auth-Resolution": "failed"},
                        {"Origin": "http://127.0.0.1:5173", "X-Aureon-Auth-Resolution": ""}):
            response = self.get(headers=headers)
            self.assertEqual(response.status_code, 401)
            self.assertNotIn("Authorization", self.calls[-1][3])

    def test_supplied_invalid_or_empty_identity_is_preserved(self):
        for value in ("Bearer invalid", ""):
            response = self.get(headers={"Origin": "http://127.0.0.1:5173", "Authorization": value})
            self.assertEqual(response.status_code, 401)
            self.assertEqual(self.calls[-1][3]["Authorization"], value)

    def test_explicit_valid_caller_identity_needs_no_admin_fallback(self):
        self.assertEqual(self.get(headers={"Authorization": "Bearer " + FIXTURE}).status_code, 200)

    def test_bad_origin_host_peer_and_oversized_auth_are_denied_locally(self):
        for headers in ({"Origin": "https://evil.invalid"}, {"Origin": "http://127.0.0.1:5174"},
                        {"Sec-Fetch-Site": "same-site"}, {"Host": "evil.invalid"},
                        {"Authorization": "a" * 8193}, {"X-Aureon-Auth-Resolution": "a" * 129}):
            self.assertEqual(self.get(headers=headers).status_code, 403)
        self.assertEqual(self.get(environ_overrides={"REMOTE_ADDR": "192.0.2.1"}).status_code, 403)
        self.assertEqual(self.calls, [])

    def test_all_passive_routes_strip_every_credential_and_keep_queries(self):
        for path, port, mapped in (("/api/terminal-state", 8791, "/api/terminal-state"),
                                   ("/api/flight-test", 8791, "/api/flight-test"),
                                   ("/api/orca-observations", 8888, "/api/observations")):
            response = self.get(path + "?limit=3", headers={"Origin": "http://127.0.0.1:5173", "Authorization": "Bearer " + FIXTURE,
                                                           "Cookie": "private=cookie", "X-Forwarded-For": "192.0.2.1"})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(self.calls[-1][:3], (port, "GET", mapped + "?limit=3"))
            self.assertEqual(self.calls[-1][3], {})
        response = self.client.post("/api/flight-test", base_url="http://127.0.0.1:5173")
        self.assertEqual(response.status_code, 405)
        self.assertEqual(len(self.calls), 3)

    def test_protected_post_reaches_existing_authority_and_stays_held(self):
        response = self.client.post("/api/hnc/dispatch", json={"intent": "offline fixture"},
                                    headers={"Origin": "http://127.0.0.1:5173"}, base_url="http://127.0.0.1:5173")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json["dispatch"], False)
        self.assertEqual(self.calls[-1][1:3], ("POST", "/api/hnc/dispatch"))

    def test_direct_operator_remains_authenticated_except_exact_get_health(self):
        response = self.operator.get("/api/me", base_url="http://127.0.0.1:8080", environ_overrides={"REMOTE_ADDR": "127.0.0.1"})
        self.assertEqual(response.status_code, 401)
        response = self.operator.get(cloud.HEALTH_PATH, base_url="http://127.0.0.1:8080", environ_overrides={"REMOTE_ADDR": "127.0.0.1"})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json["ready"])
        self.assertFalse(response.json["release_authority"])
        response = self.operator.post(cloud.HEALTH_PATH, base_url="http://127.0.0.1:8080", environ_overrides={"REMOTE_ADDR": "127.0.0.1"})
        self.assertEqual(response.status_code, 404)

    def test_health_binds_revision_and_never_implies_release(self):
        response = self.get(cloud.HEALTH_PATH)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["revision"], REVISION)
        self.assertFalse(response.json["release_authority"])
        mismatch = cloud.create_ui_gateway(self.root, "b" * 40, FIXTURE, self.transport).test_client()
        self.assertEqual(mismatch.get(cloud.HEALTH_PATH, base_url="http://127.0.0.1:5173").status_code, 503)
        (self.root / "assets/app.js").unlink()
        self.assertEqual(self.get(cloud.HEALTH_PATH).status_code, 503)

    def test_hold_loss_invalidates_both_services(self):
        for name in cloud.HOLDS:
            with patch.dict(os.environ, {name: "invalid"}):
                self.assertEqual(self.get(cloud.HEALTH_PATH).status_code, 503)
                self.assertEqual(self.get().status_code, 503)
                with self.assertRaises(cloud.CloudHTTPError):
                    cloud.require_holds()

    def test_static_spa_build_and_missing_assets_are_truthful(self):
        response = self.get("/trading/war-room")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'<div id="root">', response.data)
        response.close()
        response = self.get("/assets/app.js")
        self.assertEqual(response.status_code, 200)
        response.close()
        for path in ("/assets/missing.js", "/missing.json", "/.env", "/assets/../.env"):
            self.assertEqual(self.get(path).status_code, 404)
        (self.root / "index.html").write_text('<script src="/@vite/client"></script>', encoding="utf-8")
        with self.assertRaises(cloud.CloudHTTPError):
            cloud.validate_dist(self.root)

    def test_unavailable_upstream_is_explicit_502_and_uncached(self):
        def unavailable(*args, **kwargs):
            raise cloud.CloudHTTPError("private_exception_not_reflected")
        client = cloud.create_ui_gateway(self.root, REVISION, FIXTURE, unavailable).test_client()
        response = client.get("/api/terminal-state", base_url="http://127.0.0.1:5173")
        self.assertEqual(response.status_code, 502)
        self.assertFalse(response.json["available"])
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        self.assertNotIn(b"private_exception", response.data)

    def test_real_waitress_serves_prebound_socket_and_same_origin_auth(self):
        from waitress import create_server
        listener = socket.socket()
        listener.bind(("127.0.0.1", 0))
        listener.listen(16)
        port = listener.getsockname()[1]
        server = create_server(self.app, sockets=[listener], threads=2, expose_tracebacks=False,
                               max_request_body_size=cloud.MAX_REQUEST, clear_untrusted_proxy_headers=True)
        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()
        connection = cloud.http.client.HTTPConnection("127.0.0.1", port, timeout=3)
        try:
            connection.request("GET", "/api/me", headers={"Origin": f"http://127.0.0.1:{port}"})
            response = connection.getresponse()
            self.assertEqual(response.status, 200)
            self.assertNotIn(FIXTURE.encode(), response.read())
            connection.request("GET", "/api/me")
            response = connection.getresponse()
            self.assertEqual(response.status, 401)
            response.read()
            connection.request("GET", "/trading/war-room")
            response = connection.getresponse()
            self.assertEqual(response.status, 200)
            self.assertIn(b'<div id="root">', response.read())
        finally:
            connection.close()
            server.close()
            server.task_dispatcher.shutdown(cancel_pending=True, timeout=2)
            thread.join(timeout=2)

    def test_duplicate_port_is_rejected_before_second_boot(self):
        port_picker = socket.socket()
        port_picker.bind(("127.0.0.1", 0))
        port = port_picker.getsockname()[1]
        port_picker.close()
        with patch.dict(cloud.PORTS, {"operator": port}):
            with cloud.reserve_port("operator"):
                with self.assertRaisesRegex(cloud.CloudHTTPError, "already_owned"):
                    cloud.reserve_port("operator")


class TransportTests(unittest.TestCase):
    def test_redirects_are_not_followed_and_credentials_never_leave_first_connection(self):
        class Upstream:
            status = 302
        class Connection:
            sock = None
            def __init__(self, host, port, **kwargs):
                self.host, self.port = host, port
            def connect(self):
                pass
            def request(self, method, target, **kwargs):
                self.method, self.target = method, target
            def getresponse(self):
                return Upstream()
            def close(self):
                pass
        with patch.object(cloud.http.client, "HTTPConnection", Connection):
            with self.assertRaisesRegex(cloud.CloudHTTPError, "redirect_denied"):
                cloud.loopback_request(8080, "GET", "/api/me", {"Authorization": "Bearer " + FIXTURE})

    def test_real_slow_headers_are_interrupted_by_total_deadline(self):
        # Actual ephemeral loopback server; substitute only the fixed-port dial so
        # no deployed listener is touched. Headers keep trickling before timeout.
        listener = socket.socket()
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        port = listener.getsockname()[1]
        completed = threading.Event()
        def serve():
            with listener:
                connection, _ = listener.accept()
                with connection:
                    connection.recv(8192)
                    try:
                        for byte in b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n":
                            connection.sendall(bytes([byte]))
                            time.sleep(0.04)
                    except OSError:
                        pass
                completed.set()
        thread = threading.Thread(target=serve, daemon=True)
        thread.start()
        original = cloud.http.client.HTTPConnection
        started = time.monotonic()
        with patch.object(cloud.http.client, "HTTPConnection", lambda host, ignored, **kwargs: original(host, port, **kwargs)):
            with self.assertRaises(cloud.CloudHTTPError):
                cloud.loopback_request(8080, "GET", "/api/me", {}, timeout=0.2)
        self.assertLess(time.monotonic() - started, 1.5)
        self.assertTrue(completed.wait(2))


if __name__ == "__main__":
    unittest.main()
