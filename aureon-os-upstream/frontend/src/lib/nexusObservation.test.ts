import assert from 'node:assert/strict';
import test from 'node:test';
import { readNexusObservation } from './nexusObservation';

const now = Date.parse('2026-09-08T12:00:00Z');
const observation = { type: 'auris_metrics', source: 'sensor-receipt', data_status: 'observed', generated_values: false,
  data: { ts: new Date(now - 1_000).toISOString(), coherence_score: 0 } };

test('a connected socket and numeric outputs do not substitute for source provenance', () => {
  assert.equal(readNexusObservation({ type: 'auris_metrics', data: { coherence_score: 0.8 } }, 'auris_metrics', true, now, now).available, false);
  assert.equal(readNexusObservation({ ...observation, generated_values: true }, 'auris_metrics', true, now, now).available, false);
  assert.equal(readNexusObservation({ ...observation, data: { ...observation.data, generated_values: true } }, 'auris_metrics', true, now, now).available, false);
});

test('source age cannot be renewed by receipt time or reconnection', () => {
  assert.equal(readNexusObservation(observation, 'auris_metrics', true, now + 40_000, now + 40_000).available, false);
  assert.deepEqual(readNexusObservation(observation, 'auris_metrics', false, now, now).values, {});
  assert.equal(readNexusObservation({ ...observation, ts: new Date(now).toISOString(), data: { ts: new Date(now - 60_000).toISOString(), coherence_score: 0.8 } }, 'auris_metrics', true, now, now).available, false);
});

test('observed zero survives and absent values never receive a default', () => {
  const result = readNexusObservation(observation, 'auris_metrics', true, now, now);
  assert.equal(result.available, true);
  assert.deepEqual(result.values, { coherence_score: 0 });
  assert.equal(readNexusObservation({ ...observation, data: { ts: 1e100, coherence_score: 1 } }, 'auris_metrics', true, now, now).available, false);
});
