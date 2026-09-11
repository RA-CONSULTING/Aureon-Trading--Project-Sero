import assert from 'node:assert/strict';
import test from 'node:test';
import { readOrcaObservation } from './orcaObservation';

const now = Date.parse('2026-09-08T12:00:00Z');
const feed = { source_id: 'market-feed', receipt_id: 'receipt-1', source_timestamp: (now - 1_000) / 1_000,
  received_at: now / 1_000, data_status: 'live', generated_values: false, event_count: 0 };

test('response timestamps and registry heartbeat defaults cannot establish Orca liveness', () => {
  assert.equal(readOrcaObservation({ timestamp: new Date(now).toISOString(), last_heartbeat: now / 1_000, ready_for_execution: true }, true, 5, now).available, false);
});

test('fresh HTTP responses cannot renew old source observations', () => {
  const result = readOrcaObservation({ ...feed, timestamp: new Date(now + 121_000).toISOString() }, true, 120, now + 121_000);
  assert.equal(result.available, false);
  assert.deepEqual(result.data, {});
  assert.equal(readOrcaObservation(feed, true, 120, now).available, true);
});

test('failed HTTP reads suppress retained metrics and genuine zero remains observed', () => {
  assert.deepEqual(readOrcaObservation(feed, false, 120, now).data, {});
  assert.equal(readOrcaObservation(feed, true, 120, now).data.event_count, 0);
  assert.equal(readOrcaObservation({ ...feed, generated_values: true }, true, 120, now).available, false);
});

test('invalid, future and conflicting nested clocks fail without timestamp formatting errors', () => {
  for (const source_timestamp of [1e100, (now + 6_000) / 1_000, null]) {
    assert.equal(readOrcaObservation({ ...feed, source_timestamp }, true, 120, now).available, false);
  }
  assert.equal(readOrcaObservation({ ...feed, metadata: { source_timestamp: (now - 150_000) / 1_000 } }, true, 120, now).available, false);
});
