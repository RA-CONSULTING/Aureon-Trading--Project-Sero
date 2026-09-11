import assert from "node:assert/strict";
import { createServer as createHttpServer, request as httpRequest, type Server } from "node:http";
import { createRequire } from "node:module";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { pathToFileURL } from "node:url";
import test from "node:test";

import {
  createLoopbackIngressPlugin,
  createLoopbackProxyRoute,
  operatorAuthorizationConfig,
} from "./operatorProxySecurity";
import {
  AUTH_RESOLUTION_FAILED,
  AUTH_RESOLUTION_HEADER,
} from "../src/services/authResolution";

async function loadViteCreateServer(upstreamFrontend: string): Promise<typeof import("vite")["createServer"]> {
  const requireFromFrontend = createRequire(path.join(upstreamFrontend, "package.json"));
  const cjsEntry = requireFromFrontend.resolve("vite");
  const esmEntry = path.join(path.dirname(cjsEntry), "dist", "node", "index.js");
  const vite = await import(pathToFileURL(esmEntry).href) as typeof import("vite");
  return vite.createServer;
}

function listen(server: Server): Promise<number> {
  return new Promise((resolve, reject) => {
    server.once("error", reject);
    server.listen(0, "127.0.0.1", () => {
      server.off("error", reject);
      const address = server.address();
      if (!address || typeof address === "string") reject(new Error("test_server_address_unavailable"));
      else resolve(address.port);
    });
  });
}

function close(server: Server): Promise<void> {
  return new Promise((resolve, reject) => server.close((error) => (error ? reject(error) : resolve())));
}

async function findFreeLoopbackPort(): Promise<number> {
  const probe = createHttpServer();
  const port = await listen(probe);
  await close(probe);
  return port;
}

function requestWithHost(port: number, host: string): Promise<number> {
  return new Promise((resolve, reject) => {
    const req = httpRequest(
      {
        host: "127.0.0.1",
        port,
        path: "/api/open",
        headers: { Host: host },
      },
      (res) => {
        res.resume();
        res.once("end", () => resolve(res.statusCode ?? 0));
      },
    );
    req.once("error", reject);
    req.end();
  });
}

test("actual Vite proxy preserves caller identity and blocks cross-origin and LAN Host requests", async () => {
  const upstreamFrontend = process.env.AUREON_UPSTREAM_FRONTEND;
  assert.ok(upstreamFrontend, "AUREON_UPSTREAM_FRONTEND is required for this integration test");
  const createViteServer = await loadViteCreateServer(upstreamFrontend);

  const observed: Array<{
    authorization?: string;
    authResolution?: string;
    method?: string;
    url?: string;
  }> = [];
  const backend = createHttpServer((req, res) => {
    observed.push({
      authorization: req.headers.authorization,
      authResolution: req.headers[AUTH_RESOLUTION_HEADER.toLowerCase()] as string | undefined,
      method: req.method,
      url: req.url,
    });
    res.statusCode = 200;
    res.setHeader("Content-Type", "application/json");
    res.end(JSON.stringify({ ok: true }));
  });
  const backendPort = await listen(backend);
  const frontendPort = await findFreeLoopbackPort();
  const root = await mkdtemp(path.join(tmpdir(), "aureon-ingress-proxy-"));
  let vite: Awaited<ReturnType<typeof createViteServer>> | undefined;

  try {
    vite = await createViteServer({
      configFile: false,
      root,
      cacheDir: path.join(root, ".vite-cache"),
      appType: "custom",
      logLevel: "silent",
      plugins: [createLoopbackIngressPlugin(false)],
      server: {
        host: "127.0.0.1",
        port: frontendPort,
        strictPort: true,
        proxy: {
          "/api/local": createLoopbackProxyRoute(
            "local_operator",
            `http://127.0.0.1:${backendPort}`,
            {
              authorization: operatorAuthorizationConfig("local-operator", "fixture-local-operator-token"),
            },
          ),
          "/api/tenant": createLoopbackProxyRoute(
            "operator",
            `http://127.0.0.1:${backendPort}`,
            { authorization: { policy: "preserve-required" } },
          ),
          "/api": createLoopbackProxyRoute(
            "transparent",
            `http://127.0.0.1:${backendPort}`,
          ),
        },
      },
    });
    await vite.listen();
    const address = vite.httpServer?.address();
    assert.ok(address && typeof address !== "string");
    const vitePort = address.port;
    const base = `http://127.0.0.1:${vitePort}`;

    const ordinaryLocal = await fetch(`${base}/api/open`);
    assert.equal(ordinaryLocal.status, 200);
    assert.deepEqual(observed.at(-1), {
      authorization: undefined,
      authResolution: undefined,
      method: "GET",
      url: "/api/open",
    });

    const invalidBearer = "Bearer deliberately-invalid-tenant-fixture";
    const accepted = await fetch(`${base}/api/tenant`, {
      method: "POST",
      headers: {
        Authorization: invalidBearer,
        Origin: base,
        "Sec-Fetch-Site": "same-origin",
      },
      body: "{}",
    });
    assert.equal(accepted.status, 200);
    assert.deepEqual(observed.at(-1), {
      authorization: invalidBearer,
      authResolution: undefined,
      method: "POST",
      url: "/api/tenant",
    });

    const beforeDenied = observed.length;
    const missingBearer = await fetch(`${base}/api/tenant`);
    assert.equal(missingBearer.status, 404);
    assert.equal(observed.length, beforeDenied);

    const crossOrigin = await fetch(`${base}/api/open`, {
      headers: {
        Authorization: invalidBearer,
        Origin: "http://127.0.0.1:1",
        "Sec-Fetch-Site": "cross-site",
      },
    });
    assert.equal(crossOrigin.status, 403);
    assert.equal(observed.length, beforeDenied);

    assert.equal(await requestWithHost(vitePort, `192.168.1.20:${vitePort}`), 403);
    assert.equal(observed.length, beforeDenied);

    const localFallback = await fetch(`${base}/api/local`, {
      headers: { Origin: base, "Sec-Fetch-Site": "same-origin" },
    });
    assert.equal(localFallback.status, 200);
    assert.deepEqual(observed.at(-1), {
      authorization: "Bearer fixture-local-operator-token",
      authResolution: undefined,
      method: "GET",
      url: "/api/local",
    });

    const suppliedInvalid = await fetch(`${base}/api/local`, {
      headers: {
        Authorization: invalidBearer,
        Origin: base,
        "Sec-Fetch-Site": "same-origin",
      },
    });
    assert.equal(suppliedInvalid.status, 200);
    assert.deepEqual(observed.at(-1), {
      authorization: invalidBearer,
      authResolution: undefined,
      method: "GET",
      url: "/api/local",
    });

    const suppliedEmpty = await fetch(`${base}/api/local`, {
      headers: {
        Authorization: "",
        Origin: base,
        "Sec-Fetch-Site": "same-origin",
      },
    });
    assert.equal(suppliedEmpty.status, 200);
    assert.deepEqual(observed.at(-1), {
      authorization: "",
      authResolution: undefined,
      method: "GET",
      url: "/api/local",
    });

    const resolutionFailure = await fetch(`${base}/api/local`, {
      headers: {
        [AUTH_RESOLUTION_HEADER]: AUTH_RESOLUTION_FAILED,
        Origin: base,
        "Sec-Fetch-Site": "same-origin",
      },
    });
    assert.equal(resolutionFailure.status, 200);
    assert.deepEqual(observed.at(-1), {
      authorization: undefined,
      authResolution: undefined,
      method: "GET",
      url: "/api/local",
    });
  } finally {
    if (vite) await vite.close();
    await close(backend);
    await rm(root, { recursive: true, force: true });
  }
});

test("Vite config resolution rejects a CLI-style wildcard bind before listening", async () => {
  const upstreamFrontend = process.env.AUREON_UPSTREAM_FRONTEND;
  assert.ok(upstreamFrontend, "AUREON_UPSTREAM_FRONTEND is required for this integration test");
  const createViteServer = await loadViteCreateServer(upstreamFrontend);
  const root = await mkdtemp(path.join(tmpdir(), "aureon-ingress-bind-"));
  try {
    await assert.rejects(
      createViteServer({
        configFile: false,
        root,
        logLevel: "silent",
        plugins: [createLoopbackIngressPlugin(false)],
        server: { host: "0.0.0.0", port: 0 },
      }),
      /aureon_server_must_bind_loopback/,
    );
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});
