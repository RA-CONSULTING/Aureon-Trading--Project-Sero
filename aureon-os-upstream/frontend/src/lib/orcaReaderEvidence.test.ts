import assert from 'node:assert/strict';
import test from 'node:test';
import { ORCA_READER_SCHEMA, readOrcaReaderEvidence } from './orcaReaderEvidence';

const now = Date.parse('2026-09-08T18:00:00Z');
const sourceTime = now / 1_000 - 2;
const position = { provider: 'alpaca', kind: 'positions', source: 'alpaca:GET /v2/positions',
  status: 'observed', source_timestamp: sourceTime, received_at: sourceTime + 1,
  source_timestamp_kind: 'provider_http_date', generated_values: false, max_age_seconds: 300,
  inventory_complete: true, observed_count: 1, rows: [{ symbol: 'EXAMPLE', quantity: 2.5,
    entry_price: 12.25, currency: null, source_timestamp: sourceTime, received_at: sourceTime + 1 }] };
const payload = (value: unknown = position) => ({ schema_version: ORCA_READER_SCHEMA, service: 'orca_command_center',
  scope: 'existing_orca_reader_provider_receipts', provider_positions: { alpaca: value },
  component_imports: { Reader: true, unknown: 'yes' } });

test('Orca native snapshot retains unknown currency and cannot manufacture Kraken inventory', () => {
  const result = readOrcaReaderEvidence(payload(), true, now);
  assert.equal(result.positions.alpaca.available, true);
  assert.equal(result.positions.alpaca.rows[0].currency, null);
  assert.equal(result.positions.kraken.available, false);
  assert.equal(result.positions.kraken.count, null);
  assert.deepEqual(result.componentImports, [{ name: 'Reader', imported: true }]);
});

test('fresh assembly and pending refresh cannot renew original positions clocks', () => {
  const raw = { ...payload({ ...position, refresh_status: 'pending' }), generated_at: new Date(now + 301_000).toISOString() };
  assert.equal(readOrcaReaderEvidence(raw, true, now).positions.alpaca.available, true);
  const expired = readOrcaReaderEvidence(raw, true, now + 299_000).positions.alpaca;
  assert.equal(expired.available, false);
  assert.equal(expired.timestamp, sourceTime);
  assert.deepEqual(expired.rows, []);
});

test('failed transport, absent contract and failed native receipts suppress retained values', () => {
  for (const result of [readOrcaReaderEvidence(payload(), false, now),
    readOrcaReaderEvidence({ systems: { live: true }, timestamp: now }, true, now),
    readOrcaReaderEvidence(payload({ ...position, status: 'unavailable' }), true, now)]) {
    assert.equal(result.positions.alpaca.available, false);
    assert.equal(result.positions.alpaca.count, null);
  }
});

test('only explicit complete empty inventory reports zero; partial inventory remains scoped', () => {
  const empty = { ...position, rows: [], observed_count: 0 };
  assert.equal(readOrcaReaderEvidence(payload(empty), true, now).positions.alpaca.count, 0);
  assert.equal(readOrcaReaderEvidence(payload({ ...empty, inventory_complete: false }), true, now).positions.alpaca.count, null);
  const partial = readOrcaReaderEvidence(payload({ ...position, inventory_complete: false }), true, now).positions.alpaca;
  assert.equal(partial.available, true);
  assert.equal(partial.inventoryComplete, false);
});

test('generic status, malformed values and conflicting row clocks cannot masquerade as native positions', () => {
  const malformed = [
    { ...position, source: 'runtime_registry' },
    { ...position, source_timestamp_kind: 'assembly_time' },
    { ...position, rows: [{ ...position.rows[0], quantity: null }] },
    { ...position, rows: [{ ...position.rows[0], entry_price: Infinity }] },
    { ...position, rows: [{ ...position.rows[0], source_timestamp: sourceTime - 1 }] },
    { ...position, generated_values: true },
  ];
  for (const value of malformed) assert.equal(readOrcaReaderEvidence(payload(value), true, now).positions.alpaca.available, false);
});
