import assert from "node:assert/strict";
import test from "node:test";

import { api, setAuthTokenProvider } from "./apiClient";
import { AUTH_RESOLUTION_FAILED, AUTH_RESOLUTION_HEADER } from "./authResolution";

async function capturedHeaders(provider: () => Promise<string | null>): Promise<Headers> {
  const originalFetch = globalThis.fetch;
  let captured: RequestInit | undefined;
  globalThis.fetch = (async (_input: RequestInfo | URL, init?: RequestInit) => {
    captured = init;
    return {
      ok: true,
      status: 200,
      json: async () => ({ ok: true }),
    } as Response;
  }) as typeof fetch;
  setAuthTokenProvider(provider);
  try {
    await api.get("/api/test");
  } finally {
    setAuthTokenProvider(null);
    globalThis.fetch = originalFetch;
  }
  assert.ok(captured);
  return new Headers(captured.headers);
}

test("a verified no-session result remains an ordinary request", async () => {
  const headers = await capturedHeaders(async () => null);
  assert.equal(headers.get("Authorization"), null);
  assert.equal(headers.get(AUTH_RESOLUTION_HEADER), null);
});

test("a session lookup failure emits the local fallback denial sentinel", async () => {
  const headers = await capturedHeaders(async () => {
    throw new Error("fixture session lookup failed");
  });
  assert.equal(headers.get("Authorization"), null);
  assert.equal(headers.get(AUTH_RESOLUTION_HEADER), AUTH_RESOLUTION_FAILED);
});

test("a resolved caller token is forwarded without an auth-resolution sentinel", async () => {
  const headers = await capturedHeaders(async () => "deliberately-invalid-tenant-fixture");
  assert.equal(headers.get("Authorization"), "Bearer deliberately-invalid-tenant-fixture");
  assert.equal(headers.get(AUTH_RESOLUTION_HEADER), null);
});
