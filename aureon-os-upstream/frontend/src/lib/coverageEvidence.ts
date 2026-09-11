const object = (value: unknown): value is Record<string, unknown> => !!value && typeof value === "object" && !Array.isArray(value);
const count = (value: unknown) => typeof value === "number" && Number.isSafeInteger(value) && value >= 0;
const fraction = (value: unknown) => typeof value === "number" && Number.isFinite(value) && value >= 0 && value <= 1;
const strings = (value: unknown) => Array.isArray(value) && value.every(item => typeof item === "string");

/** Validate fields the coverage view consumes before a malformed report can imply completeness. */
export function validateCoveragePayload(value: unknown): void {
  const invalid = () => { throw new Error("Coverage report is incomplete or invalid"); };
  if (!object(value)) return invalid();
  if (value.error || !["fs_package_count", "taxonomy_count", "adapter_deep_count", "surfaced_with_systems"].every(key => count(value[key]))
    || !["covered", "uncovered", "phantom"].every(key => strings(value[key]))
    || !fraction(value.coverage_fraction) || typeof value.all_covered !== "boolean" || !Array.isArray(value.domains)) return invalid();
  for (const row of value.domains) {
    if (!object(row) || typeof row.domain !== "string" || typeof row.product_domain !== "string"
      || typeof row.has_adapter !== "boolean") return invalid();
    if (row.health != null) {
      const h = row.health;
      if (!object(h) || !["system_count", "dashboards", "total_loc"].every(key => count(h[key]))
        || !fraction(h.wired_fraction) || !strings(h.capabilities)) return invalid();
    }
  }
  const b = value.benchmark_coverage;
  if (b != null && (!object(b) || typeof b.status !== "string")) return invalid();
  if (object(b) && b.status === "measured") {
    if (!["benchmarks", "module_pin_count", "total_modules"].every(key => count(b[key]))
      || !strings(b.covered_domains) || !strings(b.uncovered_domains)) return invalid();
    if (b.ratchet != null && (!object(b.ratchet) || typeof b.ratchet.ok !== "boolean")) return invalid();
  }
}
