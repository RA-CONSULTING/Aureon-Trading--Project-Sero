// These five panels request snapshots every 5s. Current displays may retain at
// most three request intervals, or a shorter TTL declared by the source.
export const COGNITIVE_SOURCE_MAX_AGE_MS = 15_000;
const CLOCK_SKEW_MS = 5_000;
const asRecord = (value: unknown): Record<string, unknown> | null =>
  value !== null && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : null;

function sourceEpoch(value: unknown): number | null {
  if (typeof value === 'number' && Number.isFinite(value) && value >= 1_000_000_000) {
    return value < 100_000_000_000 ? value * 1000 : value;
  }
  if (typeof value !== 'string' || !value.trim()) return null;
  const stamp = Date.parse(value);
  return Number.isFinite(stamp) ? stamp : null;
}

export function cognitiveSourceWindow(value: unknown, now = Date.now()): { observedAt: number; expiresAt: number } | null {
  const payload = asRecord(value);
  if (!payload || payload.available !== true || payload.stale === true
      || !['live', 'real_observed', 'real_derived'].includes(String(payload.truth_status))) return null;
  const provenance = asRecord(payload.provenance);
  if (payload.generated_values === true || provenance?.simulation_fallback_allowed === true) return null;
  // Only explicitly named source clocks qualify. Gateway ts/generated_at and
  // the browser fetch time describe response assembly, not the source reading.
  const raw = [payload.source_timestamp, payload.sourceTimestamp, payload.observed_at,
    provenance?.source_timestamp, provenance?.sourceTimestamp, provenance?.observed_at].filter(value => value !== undefined);
  const clocks = raw.map(sourceEpoch);
  if (!clocks.length || clocks.some(stamp => stamp === null || now - stamp < -CLOCK_SKEW_MS)) return null;
  const statedTtl = payload.freshness_ttl_ms ?? provenance?.freshness_ttl_ms;
  const ttl = typeof statedTtl === 'number' && Number.isFinite(statedTtl) && statedTtl > 0
    ? Math.min(COGNITIVE_SOURCE_MAX_AGE_MS, statedTtl) : COGNITIVE_SOURCE_MAX_AGE_MS;
  const observedAt = Math.min(...clocks as number[]);
  const expiresAt = observedAt + ttl;
  return now <= expiresAt ? { observedAt, expiresAt } : null;
}

export function currentCognitiveObservation<T>(value: T | null | undefined, now = Date.now(), requestFailed = false): T | null {
  if (requestFailed) return null;
  const payload = asRecord(value);
  if (payload?.available === false && payload.truth_status === 'no_data') return value as T;
  return cognitiveSourceWindow(value, now) ? value as T : null;
}
