import assert from "node:assert/strict";
import test from "node:test";
import { connectionCanDisconnect, connectionDisconnectPath } from "./connectionDisconnect";

test("connection disconnect keeps pinned owner rows read only", () => {
    assert.equal(connectionCanDisconnect({
      id: "binance",
      category: "exchange",
      has_key: true,
      credential_management: "pinned_cloud_secret",
      credential_writable: false,
    }), false);
});

test("connection disconnect allows tenant BYOK through the connection route", () => {
    const row = {
      id: "binance",
      category: "exchange",
      has_key: true,
      credential_management: "account_keystore" as const,
      credential_writable: true,
    };
    assert.equal(connectionCanDisconnect(row), true);
    assert.equal(connectionDisconnectPath(row), "/api/connections/binance");
});

test("connection disconnect preserves the established tenant LLM delete route", () => {
    assert.equal(
      connectionDisconnectPath({ id: "openai", category: "ai_llm" }),
      "/api/providers/openai",
    );
});
