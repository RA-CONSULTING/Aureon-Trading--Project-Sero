import assert from "node:assert/strict";
import test from "node:test";
import { validateCoveragePayload } from "./coverageEvidence.ts";
const valid = { fs_package_count: 1, taxonomy_count: 1, adapter_deep_count: 0, surfaced_with_systems: 0,
  covered: ["fixture"], uncovered: [], phantom: [], coverage_fraction: 1, all_covered: true,
  domains: [{ domain: "fixture", product_domain: "fixture", has_adapter: false, health: null }] };
test("structural inventory can be valid with no runtime rollup", () => {
  assert.doesNotThrow(() => validateCoveragePayload(valid));
});
test("malformed coverage and benchmark fields cannot crash or become complete", () => {
  for (const broken of [null, {}, { ...valid, domains: {} }, { ...valid, coverage_fraction: NaN },
    { ...valid, fs_package_count: -1 }, { ...valid, error: "failed" },
    { ...valid, domains: [{ ...valid.domains[0], health: { system_count: 1 } }] },
    { ...valid, benchmark_coverage: { status: "measured" } }]) {
    assert.throws(() => validateCoveragePayload(broken));
  }
});
