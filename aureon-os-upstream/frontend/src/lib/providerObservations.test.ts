import assert from 'node:assert/strict';
import test from 'node:test';
import { readProviderObservation } from './providerObservations';

const now = 2_000_000;
const fresh = { status: 'observed', generated_values: false, source: 'capital:GET /accounts',
  source_timestamp: 1_990, received_at: 1_991, max_age_seconds: 300, observed_count: 1, inventory_complete: true,
  rows: [{ source_timestamp: 1_990, received_at: 1_991, balance: 0, currency: 'GBP' }] };

test('receipt remains independent of analysis but unavailable on transport failure', () => {
  assert.equal(readProviderObservation(fresh, true, now).available, true);
  assert.equal(readProviderObservation(fresh, false, now).available, false);
  assert.equal(readProviderObservation({}, true, now).count, null);
});

test('immutable source time expires despite recent transport receipt', () => {
  assert.equal(readProviderObservation({ ...fresh, source_timestamp: 1_000, received_at: 1_999 }, true, now).available, false);
  assert.equal(readProviderObservation({ ...fresh, source_timestamp: 2_010 }, true, now).available, false);
});

test('real zero survives and unknown inventory never becomes zero', () => {
  assert.equal(readProviderObservation(fresh, true, now).rows[0].balance, 0);
  assert.equal(readProviderObservation({ ...fresh, observed_count: 0, rows: [], inventory_complete: true }, true, now).count, 0);
  assert.equal(readProviderObservation({ ...fresh, observed_count: 0, rows: [], inventory_complete: false }, true, now).count, null);
  assert.equal(readProviderObservation({ ...fresh, observed_count: 2 }, true, now).available, false);
});

test('local HTTP receipt provenance stays explicit and cannot redate cached rows', () => {
  const local = { ...fresh, source_timestamp_kind: 'local_http_receipt' };
  const observation = readProviderObservation(local, true, now);
  assert.equal(observation.timestampKind, 'local_http_receipt');
  assert.equal(observation.receivedAt, 1_991);
  assert.equal(readProviderObservation({ ...local, received_at: 1_999 }, true, now).available, false);
  const account = { ...fresh, rows: [{ ...fresh.rows[0], balance_kind: 'equity', available: null, cash: 1, buying_power: 2 }] };
  const row = readProviderObservation(account, true, now).rows[0];
  assert.equal(row.available, null);
  assert.equal(row.cash, 1);
  assert.equal(row.buying_power, 2);
});

test('malformed finite epochs cannot crash receipt labels, including unavailable observations', () => {
  for (const value of [1e100, -1e100, Infinity, -Infinity, NaN, 0, -1]) {
    const invalidSource = readProviderObservation({ ...fresh, source_timestamp: value }, true, now);
    assert.equal(invalidSource.available, false);
    assert.equal(invalidSource.timestamp, null);
    const invalidReceipt = readProviderObservation({ ...fresh, received_at: value }, true, now);
    assert.equal(invalidReceipt.available, false);
    assert.equal(invalidReceipt.receivedAt, null);
  }
  const unavailable = readProviderObservation({ ...fresh, status: 'unavailable', source_timestamp: 1e100, received_at: 1e100 }, true, now);
  assert.equal(unavailable.timestamp, null);
  assert.equal(unavailable.receivedAt, null);
});
