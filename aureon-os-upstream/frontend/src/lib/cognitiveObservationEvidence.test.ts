import assert from 'node:assert/strict';
import test from 'node:test';
import { COGNITIVE_SOURCE_MAX_AGE_MS, cognitiveSourceWindow, currentCognitiveObservation } from './cognitiveObservationEvidence';

const now = Date.parse('2026-09-08T10:00:00Z');
const observed = now - 1000;
const payload = () => ({ available: true, truth_status: 'real_derived', source_timestamp: observed / 1000, self_coherence: 0 });

test('valid current zero is retained with its original source clock', () => {
  const value = payload();
  assert.equal(currentCognitiveObservation(value, now), value);
  assert.equal(currentCognitiveObservation(value, now)?.self_coherence, 0);
  assert.deepEqual(cognitiveSourceWindow(value, now), { observedAt: observed, expiresAt: observed + COGNITIVE_SOURCE_MAX_AGE_MS });
});

test('a failed request clears the current value even while its previous clock was fresh', () => {
  assert.equal(currentCognitiveObservation(payload(), now, true), null);
});

test('gateway timestamps and available flags cannot establish original source freshness', () => {
  assert.equal(currentCognitiveObservation({ available: true, truth_status: 'live', generated_at: new Date(now).toISOString(), ts: now / 1000 }, now), null);
  assert.equal(currentCognitiveObservation({ ...payload(), source_timestamp: null }, now), null);
  assert.equal(currentCognitiveObservation({ ...payload(), truth_status: undefined }, now), null);
});

test('source expiry is independent of new response timestamps and current fetch time', () => {
  const expiredAt = observed + COGNITIVE_SOURCE_MAX_AGE_MS + 1;
  assert.equal(currentCognitiveObservation({ ...payload(), generated_at: new Date(expiredAt).toISOString() }, expiredAt), null);
  assert.equal(currentCognitiveObservation({ ...payload(), source_timestamp: (now + 6000) / 1000 }, now), null);
});

test('shorter declared source TTL and oldest contributing clock constrain freshness', () => {
  assert.equal(currentCognitiveObservation({ ...payload(), freshness_ttl_ms: 500 }, now), null);
  assert.equal(currentCognitiveObservation({ ...payload(), provenance: { source_timestamp: (now - 60_000) / 1000 } }, now), null);
  assert.equal(cognitiveSourceWindow({ ...payload(), freshness_ttl_ms: 86_400_000 }, now)?.expiresAt, observed + COGNITIVE_SOURCE_MAX_AGE_MS);
});

test('explicit no-data remains no-data and simulation-enabled readings are unavailable', () => {
  const noData = { available: false, truth_status: 'no_data' };
  assert.equal(currentCognitiveObservation(noData, now), noData);
  assert.equal(currentCognitiveObservation({ ...payload(), provenance: { simulation_fallback_allowed: true } }, now), null);
  assert.equal(currentCognitiveObservation({ ...payload(), stale: true }, now), null);
});
