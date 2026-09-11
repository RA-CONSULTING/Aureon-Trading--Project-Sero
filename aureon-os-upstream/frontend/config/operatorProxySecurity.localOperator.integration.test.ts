import assert from "node:assert/strict";
import { createServer as createHttpServer, type Server } from "node:http";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import test from "node:test";
import { createServer as createViteServer } from "vite";

import { createLoopbackIngressPlugin, createLoopbackProxyRoute, operatorAuthorizationConfig } from "./operatorProxySecurity";
import { AUTH_RESOLUTION_FAILED, AUTH_RESOLUTION_HEADER } from "../src/services/authResolution";

function listen(server: Server): Promise<number> {
  return new Promise((resolve, reject) => {
    server.once("error", reject);
    server.listen(0, "127.0.0.1", () => {
      server.off("error", reject);
      const address = server.address();
      if (!address || typeof address === "string") reject(new Error("fixture_address_unavailable"));
      else resolve(address.port);
    });
  });
}

function close(server: Server): Promise<void> {
  return new Promise((resolve, reject) => server.close((error) => error ? reject(error) : resolve()));
}

test("actual local-operator proxy authenticates Origin-only UI reads while failed and missing authentication remain denied", async () => {
  // These are isolated test fixture credentials, never read from runtime profiles.
  const fixtureBearer = "Bearer isolated-local-operator-fixture";
  const observed: Array<{ authorization?: string; failedAuthHeader?: string }> = [];
  const backend = createHttpServer((req, res) => {
    observed.push({ authorization: req.headers.authorization,
      failedAuthHeader: req.headers[AUTH_RESOLUTION_HEADER.toLowerCase()] as string | undefined });
    res.statusCode = req.headers.authorization === fixtureBearer ? 200 : 401;
    res.setHeader("Content-Type", "application/json");
    res.end(JSON.stringify({ authenticated: res.statusCode === 200 }));
  });
  const backendPort = await listen(backend);
  const frontendProbe = createHttpServer();
  const frontendPort = await listen(frontendProbe);
  await close(frontendProbe);
  const root = await mkdtemp(path.join(tmpdir(), "aureon-local-operator-auth-"));
  let vite: Awaited<ReturnType<typeof createViteServer>> | undefined;
  try {
    vite = await createViteServer({
      configFile: false, root, cacheDir: path.join(root, ".vite-cache"), appType: "custom", logLevel: "silent",
      plugins: [createLoopbackIngressPlugin(false)],
      server: { host: "127.0.0.1", port: frontendPort, strictPort: true, proxy: {
        "/api": createLoopbackProxyRoute("operator", `http://127.0.0.1:${backendPort}`, {
          authorization: operatorAuthorizationConfig("local-operator", fixtureBearer),
        }),
      } },
    });
    await vite.listen();
    const address = vite.httpServer?.address();
    assert.ok(address && typeof address !== "string");
    const base = `http://127.0.0.1:${address.port}`;
    const cases: Array<{ name: string; headers: Record<string, string>; status: number; expectedAuth?: string }> = [
      { name: "Origin-only browser read", headers: { Origin: base }, status: 200, expectedAuth: fixtureBearer },
      { name: "same-origin Fetch Metadata read", headers: { "Sec-Fetch-Site": "same-origin" }, status: 200, expectedAuth: fixtureBearer },
      { name: "missing browser evidence", headers: {}, status: 401 },
      { name: "navigation does not prove same origin", headers: { "Sec-Fetch-Site": "none" }, status: 401 },
      { name: "caller invalid bearer remains invalid", headers: { Origin: base, Authorization: "Bearer invalid-fixture" }, status: 401, expectedAuth: "Bearer invalid-fixture" },
      { name: "caller empty bearer remains empty", headers: { Origin: base, Authorization: "" }, status: 401, expectedAuth: "" },
      { name: "failed auth resolution never escalates", headers: { Origin: base, [AUTH_RESOLUTION_HEADER]: AUTH_RESOLUTION_FAILED }, status: 401 },
      { name: "any auth failure marker prevents fallback", headers: { Origin: base, [AUTH_RESOLUTION_HEADER]: "" }, status: 401 },
    ];
    for (const fixture of cases) {
      const response = await fetch(`${base}/api/me`, { headers: fixture.headers });
      await response.arrayBuffer();
      assert.equal(response.status, fixture.status, fixture.name);
      assert.equal(observed.at(-1)?.authorization, fixture.expectedAuth, fixture.name);
      assert.equal(observed.at(-1)?.failedAuthHeader, undefined, fixture.name);
    }
    const beforeCrossOrigin = observed.length;
    const deniedRequests: Array<Record<string, string>> = [
      { Origin: "http://127.0.0.1:1" },
      { Origin: base, "Sec-Fetch-Site": "cross-site" },
      { Origin: "null" },
    ];
    for (const headers of deniedRequests) {
      const response = await fetch(`${base}/api/me`, { headers });
      await response.arrayBuffer();
      assert.equal(response.status, 403);
      assert.equal(observed.length, beforeCrossOrigin);
    }
  } finally {
    if (vite) await vite.close();
    await close(backend);
    const resolved = path.resolve(root);
    assert.equal(path.dirname(resolved), path.resolve(tmpdir()));
    assert.ok(path.basename(resolved).startsWith("aureon-local-operator-auth-"));
    await rm(resolved, { recursive: true, force: true });
  }
});
