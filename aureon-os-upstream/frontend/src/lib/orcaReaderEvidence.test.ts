import assert from 'node:assert/strict';
import test from 'node:test';
import { ORCA_POSITION_PROVIDERS, ORCA_READER_SCHEMA, readOrcaReaderEvidence } from './orcaReaderEvidence';

const now = Date.parse('2026-09-08T18:00:00Z');
const sourceTime = now / 1_000 - 2;
const position = { provider: 'alpaca', kind: 'positions', source: 'alpaca:GET /v2/positions',
  status: 'observed', source_timestamp: sourceTime, received_at: sourceTime + 1,
  source_timestamp_kind: 'provider_http_date', generated_values: false, max_age_seconds: 300,
  inventory_complete: true, observed_count: 1, rows: [{ symbol: 'EXAMPLE', quantity: 2.5,
    entry_price: 12.25, currency: null, source_timestamp: sourceTime, received_at: sourceTime + 1 }] };
const capital = { ...position, provider: 'capital', source: 'capital:GET /positions' };
const payload = (value: unknown = position) => ({ schema_version: ORCA_READER_SCHEMA, service: 'aureon_operator',
  scope: 'terminal_state_sanitized_provider_position_receipts', provider_calls: false, mutation_authority: false,
  provider_positions: { capital, alpaca: value,
    kraken: { provider: 'kraken', kind: 'positions', status: 'unavailable', generated_values: false,
      reason: 'operator_position_reader_not_supported', rows: [], observed_count: null },
    binance: { provider: 'binance', kind: 'positions', status: 'unavailable', generated_values: false,
      reason: 'operator_position_reader_not_supported', rows: [], observed_count: null } } });

test('operator snapshot covers four providers and cannot manufacture unsupported inventory', () => {
  const result = readOrcaReaderEvidence(payload(), true, now);
  assert.deepEqual(Object.keys(result.positions), [...ORCA_POSITION_PROVIDERS]);
  assert.equal(result.positions.capital.available, true);
  assert.equal(result.positions.alpaca.available, true);
  assert.equal(result.positions.alpaca.rows[0].currency, null);
  assert.equal(result.positions.kraken.available, false);
  assert.equal(result.positions.kraken.count, null);
  assert.equal(result.positions.binance.available, false);
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

test('contract needs explicit passive operator boundaries', () => {
  for (const broken of [
    { ...payload(), provider_calls: true },
    { ...payload(), mutation_authority: true },
    { ...payload(), service: 'orca_command_center' },
  ]) {
    const result = readOrcaReaderEvidence(broken, true, now);
    assert.equal(result.contractAvailable, false);
    assert.equal(result.positions.capital.available, false);
    assert.equal(result.positions.alpaca.available, false);
  }
});

test('unsupported provider observation cannot masquerade as a position reader', () => {
  const invented = { ...position, provider: 'kraken', source: 'kraken:POST /0/private/OpenPositions',
    reason: 'invented_source' };
  const raw = payload();
  raw.provider_positions.kraken = invented;
  const result = readOrcaReaderEvidence(raw, true, now);
  assert.equal(result.positions.kraken.available, false);
  assert.equal(result.positions.kraken.count, null);
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
