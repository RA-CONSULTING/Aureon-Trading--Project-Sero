import assert from 'node:assert/strict';
import test from 'node:test';
import { consoleControlAvailable, consoleDisplayValue, consoleReportedPercent, goldRuntimeObservation } from './generatedConsoleDisplayEvidence';

const now = Date.parse('2026-09-11T12:00:00Z');
const proof = (age = 20) => ({ generated_at: new Date(now - 10_000).toISOString(),
  gold_runtime_candidate_ready: true,
  fresh_gold_data_source: { ready: true, age_sec: age, source: 'capital', reference_price: 2000 } });

test('unknown telemetry remains unavailable while genuine zero and recorded labels survive', () => {
  for (const value of [null, undefined, NaN, Infinity, {}, false, '']) assert.equal(consoleDisplayValue(value), 'Unavailable');
  assert.equal(consoleDisplayValue(0), '0');
  assert.equal(consoleDisplayValue('completed_validated'), 'completed_validated');
  assert.equal(consoleReportedPercent(0), 0);
  assert.equal(consoleReportedPercent(0.75), 75);
  for (const value of [null, undefined, NaN, Infinity, -0.2, 1.1, '0.5']) assert.equal(consoleReportedPercent(value), null);
});

test('coding controls require their own current receipt and no pending action', () => {
  assert.equal(consoleControlAvailable(now - 500, false, now), true);
  assert.equal(consoleControlAvailable(now - 500, true, now), false);
  for (const receipt of [null, NaN, now - 30_001, now + 5_001]) assert.equal(consoleControlAvailable(receipt, false, now), false);
});

test('gold observations advance recorded source age without rewriting the original proof', () => {
  const input = proof();
  const view = goldRuntimeObservation(input, true, now);
  assert.equal(view.current, true);
  assert.equal(view.sourceCurrent, true);
  assert.equal(view.ageSeconds, 30);
  assert.equal(input.fresh_gold_data_source.age_sec, 20);
  assert.equal(view.source.reference_price, 2000);
});

test('disconnected, expired, absent and future gold proof cannot inherit unrelated freshness', () => {
  const cases: [unknown, boolean][] = [[proof(), false], [{ ...proof(), generated_at: new Date(now - 30_001).toISOString() }, true],
    [{ ...proof(), generated_at: new Date(now + 5_001).toISOString() }, true], [{ ...proof(), generated_at: undefined }, true], [null, true]];
  for (const [input, current] of cases) {
    const view = goldRuntimeObservation(input, current, now);
    assert.equal(view.current, false);
    assert.equal(view.sourceCurrent, false);
    assert.deepEqual(view.proof, {});
    assert.deepEqual(view.source, {});
  }
});

test('a ready candidate cannot make absent, stale or unready source data fresh', () => {
  const quote = proof().fresh_gold_data_source;
  for (const source of [{}, { ready: true }, { ...quote, ready: false }, { ...quote, age_sec: -1 }, { ...quote, age_sec: 171 },
    { ...quote, reference_price: 0 }, { ...quote, reference_price: NaN }, { ...quote, source: '' }]) {
    const view = goldRuntimeObservation({ ...proof(), fresh_gold_data_source: source }, true, now);
    assert.equal(view.current, true);
    assert.equal(view.sourceCurrent, false);
    assert.equal(view.ageSeconds, null);
    assert.deepEqual(view.source, {});
  }
});
