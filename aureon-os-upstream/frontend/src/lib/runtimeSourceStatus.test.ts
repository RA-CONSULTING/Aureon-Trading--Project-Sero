import { test } from "node:test";
import assert from "node:assert/strict";
import { runtimeCount, runtimeSourceFresh } from "./runtimeSourceStatus.ts";

const sample = { fresh: true, read_state: "observed", source_timestamp: 1_000, max_age_seconds: 300 };
test("fresh runtime expires from its original source clock without another response", () => {
  assert.equal(runtimeSourceFresh(sample, 1_299_000), true);
  assert.equal(runtimeSourceFresh(sample, 1_300_001), false);
});
test("fresh HTTP flags cannot rescue missing, future, stale or invalid source evidence", () => {
  for (const source of [undefined, { ...sample, source_timestamp: null }, { ...sample, source_timestamp: 2_000 },
    { ...sample, fresh: false }, { ...sample, read_state: "failed" }, { ...sample, max_age_seconds: Infinity },
    { ...sample, max_age_seconds: 10_000 }, { ...sample, source_timestamp: NaN }]) {
    assert.equal(runtimeSourceFresh(source, 1_100_000), false);
  }
});
test("runtime counts preserve observed zero and do not invent missing measurements", () => {
  assert.equal(runtimeCount(0), "0");
  assert.equal(runtimeCount(12), "12");
  for (const value of [null, undefined, "12", false, NaN, Infinity, -1, 1.5]) {
    assert.equal(runtimeCount(value), "—");
  }
});
