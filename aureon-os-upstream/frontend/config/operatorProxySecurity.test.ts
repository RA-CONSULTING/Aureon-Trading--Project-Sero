import assert from "node:assert/strict";
import test from "node:test";
import type { IncomingMessage, ServerResponse } from "node:http";

import {
  assertLoopbackProxyTarget,
  assertResolvedLoopbackBindHost,
  createLoopbackProxyRoute,
  createProxyRequestGuard,
  inspectProxyRequest,
  isLoopbackHost,
  operatorAuthorizationConfig,
} from "./operatorProxySecurity";

type RequestShape = Pick<IncomingMessage, "headers" | "socket">;

function requestFixture({
  remoteAddress = "127.0.0.1",
  host = "127.0.0.1:8081",
  origin,
  fetchSite,
  authorization,
}: {
  remoteAddress?: string;
  host?: string;
  origin?: string;
  fetchSite?: string;
  authorization?: string;
} = {}): RequestShape {
  const headers: IncomingMessage["headers"] = { host };
  if (origin !== undefined) headers.origin = origin;
  if (fetchSite !== undefined) headers["sec-fetch-site"] = fetchSite;
  if (authorization !== undefined) headers.authorization = authorization;
  return {
    headers,
    socket: { remoteAddress } as IncomingMessage["socket"],
  };
}

test("loopback classification refuses wildcard, LAN, remote, and ambiguous names", () => {
  for (const host of ["127.0.0.1", "127.9.8.7", "localhost", "::1", "[::1]", "::ffff:127.0.0.1"]) {
    assert.equal(isLoopbackHost(host), true, host);
  }
  for (const host of ["0.0.0.0", "192.168.1.8", "8.8.8.8", "example.com", "localHost.example", " localhost"] ) {
    assert.equal(isLoopbackHost(host), false, host);
  }
});

test("proxy target validation is loopback-only and never reflects rejected values", () => {
  assert.equal(
    assertLoopbackProxyTarget("operator", "http://127.0.0.1:8080"),
    "http://127.0.0.1:8080",
  );
  const rejected = [
    "https://operator.example.test",
    "http://192.168.1.9:8080",
    "http://fixture-secret@127.0.0.1:8080",
    "file:///tmp/operator.sock",
  ];
  for (const target of rejected) {
    assert.throws(
      () => assertLoopbackProxyTarget("operator", target),
      (error: unknown) => error instanceof Error && !error.message.includes(target) && !error.message.includes("fixture-secret"),
    );
  }
});

test("the route constructor has a guard and has no credential injection surface", () => {
  const route = createLoopbackProxyRoute("operator", "http://127.0.0.1:8080", {
    authorization: { policy: "preserve-required" },
  });
  assert.equal(route.target, "http://127.0.0.1:8080");
  assert.equal(route.changeOrigin, true);
  assert.equal(typeof route.bypass, "function");
  assert.equal(Object.hasOwn(route, "headers"), false);
  assert.equal(Object.hasOwn(route, "auth"), false);
  assert.equal(Object.hasOwn(route, "forward"), false);
});

test("request guard accepts a same-origin loopback browser and a local non-browser probe", () => {
  assert.deepEqual(
    inspectProxyRequest({
      ...requestFixture({ origin: "http://127.0.0.1:8081", fetchSite: "same-origin" }),
    }),
    { allowed: true },
  );
  assert.deepEqual(inspectProxyRequest(requestFixture()), { allowed: true });
});

test("request guard rejects remote clients, non-loopback Host, and cross-origin browser requests", () => {
  assert.deepEqual(inspectProxyRequest(requestFixture({ remoteAddress: "192.168.1.4" })), {
    allowed: false,
    reason: "loopback_client_required",
  });
  assert.deepEqual(inspectProxyRequest(requestFixture({ host: "192.168.1.4:8081" })), {
    allowed: false,
    reason: "loopback_host_required",
  });
  assert.deepEqual(inspectProxyRequest(requestFixture({ origin: "http://127.0.0.1:9999" })), {
    allowed: false,
    reason: "same_origin_required",
  });
  assert.deepEqual(inspectProxyRequest(requestFixture({ fetchSite: "cross-site" })), {
    allowed: false,
    reason: "cross_site_request_denied",
  });
});

test("tenant mode requires a caller bearer but preserves invalid bearers for backend rejection", () => {
  const missing = requestFixture();
  assert.deepEqual(inspectProxyRequest(missing, "preserve-required"), {
    allowed: false,
    reason: "caller_authorization_required",
  });

  const invalid = requestFixture({ authorization: "Bearer deliberately-invalid-fixture" });
  assert.deepEqual(inspectProxyRequest(invalid, "preserve-required"), { allowed: true });
  assert.equal(invalid.headers.authorization, "Bearer deliberately-invalid-fixture");

  const empty = requestFixture({ authorization: "" });
  assert.deepEqual(inspectProxyRequest(empty, "preserve-required"), { allowed: true });
  assert.equal(empty.headers.authorization, "");
});

test("transparent is the compatibility default and local operator fallback is explicit", () => {
  assert.deepEqual(operatorAuthorizationConfig(undefined, undefined), { policy: "preserve-optional" });
  assert.deepEqual(operatorAuthorizationConfig("transparent", undefined), { policy: "preserve-optional" });
  assert.deepEqual(operatorAuthorizationConfig("tenant", undefined), { policy: "preserve-required" });
  assert.deepEqual(operatorAuthorizationConfig("local-operator", "fixture-local-token"), {
    policy: "preserve-optional",
    localOperatorBearer: "Bearer fixture-local-token",
  });
  assert.throws(() => operatorAuthorizationConfig("local-operator", undefined), (error: unknown) => {
    return error instanceof Error && error.message === "aureon_local_operator_proxy_bearer_required";
  });
  assert.throws(() => operatorAuthorizationConfig("fixture-secret-mode", "fixture-secret"), (error: unknown) => {
    return error instanceof Error && error.message === "aureon_ui_auth_mode_invalid";
  });
});

test("resolved Vite host cannot be widened by a CLI flag", () => {
  assert.doesNotThrow(() => assertResolvedLoopbackBindHost("127.0.0.1", "server"));
  assert.doesNotThrow(() => assertResolvedLoopbackBindHost("::1", "server"));
  assert.throws(
    () => assertResolvedLoopbackBindHost("0.0.0.0", "server"),
    /aureon_server_must_bind_loopback/,
  );
  assert.throws(() => assertResolvedLoopbackBindHost(true, "server"), /aureon_server_must_bind_loopback/);
});

test("denied requests stop in Vite without mutating their Authorization header", () => {
  const req = requestFixture({
    origin: "https://attacker.example.test",
    authorization: "Bearer deliberately-invalid-fixture",
  });
  const responseHeaders = new Map<string, string>();
  const res = {
    setHeader(name: string, value: string) {
      responseHeaders.set(name.toLowerCase(), value);
    },
  } as unknown as ServerResponse;
  const guard = createProxyRequestGuard("preserve-required");
  assert.equal(guard(req as IncomingMessage, res, {}), false);
  assert.equal(req.headers.authorization, "Bearer deliberately-invalid-fixture");
  assert.equal(responseHeaders.get("cache-control"), "no-store");
  assert.equal(responseHeaders.get("x-content-type-options"), "nosniff");
});
