import assert from 'node:assert/strict';
import test from 'node:test';
import { readOperatorConfiguration, type OperatorConfigurationReceipt } from './operatorConfiguration';

const now = 100_000;
const receipt: OperatorConfigurationReceipt = {
  pulse: { ok: true, providers: [], switchboard: { enabled: 0, total: 4 }, organism: { connectome: { coverage_pct: 0,
    source_timestamp: now / 1000, max_age_seconds: 300, fresh: true, read_state: 'observed' } } },
  error: null, offline: false, loading: false, lastOkAt: now,
};

test('HTTP failures cannot retain apparently current configuration even when transport is reachable', () => {
  assert.deepEqual(readOperatorConfiguration({ ...receipt, error: 'GET /api/pulse -> 500' }, now), []);
  assert.deepEqual(readOperatorConfiguration({ ...receipt, offline: true }, now), []);
  assert.deepEqual(readOperatorConfiguration({ ...receipt, pulse: { ok: false, providers: [] } }, now), []);
});

test('an offline model stub and an unstamped connectome cannot become attached or observed', () => {
  const items = readOperatorConfiguration({ ...receipt, pulse: { ok: true,
    providers: [{ name: 'offline', adapter: 'AureonStubAdapter' }, { name: 'fallback', adapter: 'AureonUnavailableAdapter', is_fallback: true },
      { name: 'local', adapter: 'AureonLocalAdapter' }],
    organism: { connectome: { coverage_pct: 0 } },
  } }, now);
  assert.deepEqual(items, [{ label: 'model adapters attached', value: '1' }]);
});

test('configuration receipt expires between polls and cannot be refreshed by a render', () => {
  assert.equal(readOperatorConfiguration(receipt, now + 45_000).length, 3);
  assert.deepEqual(readOperatorConfiguration(receipt, now + 45_001), []);
  assert.deepEqual(readOperatorConfiguration(receipt, now - 1), []);
  assert.deepEqual(readOperatorConfiguration({ ...receipt, lastOkAt: null }, now), []);
});

test('observed zero survives while malformed fields stay unavailable', () => {
  assert.deepEqual(readOperatorConfiguration(receipt, now).map((item) => item.value), ['0', '0/4', '0.0%']);
  assert.deepEqual(readOperatorConfiguration({ ...receipt, pulse: {
    ok: true, switchboard: { enabled: 5, total: 4 }, organism: { connectome: { coverage_pct: Infinity } },
  } }, now), []);
});
