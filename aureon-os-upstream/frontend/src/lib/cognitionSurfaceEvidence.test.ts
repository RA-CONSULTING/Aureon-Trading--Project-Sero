import assert from 'node:assert/strict';
import test from 'node:test';
import { benchmarkResult, brainHistoryRecords, observedPercent, observedValue, processRowCurrent, readFailureMessage, surfaceEvidence } from './cognitionSurfaceEvidence';
import type { CognitiveObservation } from '../services/cognitiveReads';

const now = 2_000_000;
const observed: CognitiveObservation = { source_timestamp: 1995, source_clock_kind: 'producer_timestamp',
  available: true, fresh: true, read_state: 'observed', max_age_seconds: 300, receipt_timestamp: 2000 };
const history: CognitiveObservation = { ...observed, source_timestamp: 1000, available: false, fresh: false,
  read_state: 'stale', classification: 'recorded_history', historical_available: true };

test('fresh producer fields independently expire without refreshing original source time', () => {
  assert.equal(surfaceEvidence(observed, now).current, true);
  assert.equal(surfaceEvidence({ ...observed, receipt_timestamp: 9999 }, 2_296_000).displayable, false);
  assert.equal(observed.source_timestamp, 1995);
});
test('receipt clocks, missing source clocks and malformed dates cannot create freshness', () => {
  for (const change of [{ source_timestamp: null }, { source_timestamp: NaN }, { source_timestamp: 9e15 },
    { source_timestamp: 2010 }, { source_clock_kind: '' }, { source_clock_kind: 'http_response_receipt' },
    { source_clock_kind: 'generated_at' }]) {
    assert.equal(surfaceEvidence({ ...observed, ...change }, now).current, false);
  }
});
test('explicit unavailable, failed, stale, fixture and simulated data do not render current values', () => {
  for (const change of [{ available: false }, { fresh: false }, { read_state: 'failed' }, { read_state: 'stale' },
    { truth_status: 'no_data' }, { truth_status: 'test_fixture' }, { generated: true }, { simulated: true },
    { generated_values: true }, { stale: true }]) {
    assert.equal(surfaceEvidence({ ...observed, ...change }, now).displayable, false);
  }
});
test('actual process and bus observations use15s cadence, not report300s or response clocks', () => {
  for (const kind of ['os_process_measurement', 'in_process_bus_measurement']) {
    const value = { ...observed, source_clock_kind: kind, max_age_seconds: 15 };
    assert.equal(surfaceEvidence(value, now, 15).current, true);
    assert.equal(surfaceEvidence(value, 2_011_000, 15).current, false);
    assert.equal(surfaceEvidence({ ...value, max_age_seconds: 300 }, now, 15).current, false);
  }
});
test('a measured process collection cannot supply clocks to unmeasured or older PID rows', () => {
  const process = { ...observed, max_age_seconds: 15, source_clock_kind: 'os_process_measurement' };
  assert.equal(processRowCurrent(process, { source_timestamp: 1995, read_state: 'observed', pid_running: true, identity_verified: true }, now), true);
  for (const source_timestamp of [null, 1980, NaN, 2010]) {
    assert.equal(processRowCurrent(process, { source_timestamp, pid_running: true }, now), false);
  }
});
test('failed or malformed process rows cannot borrow a fresh collection clock; observed absence is valid', () => {
  const process = { ...observed, max_age_seconds: 15, source_clock_kind: 'os_process_measurement' };
  const row = { source_timestamp: 1995, read_state: 'observed', pid_running: true, identity_verified: true };
  for (const change of [{ read_state: 'failed' }, { read_state: 'unavailable' }, { read_state: undefined },
    { pid_running: 'true' }, { pid_running: false }, { identity_verified: null }]) {
    assert.equal(processRowCurrent(process, { ...row, ...change }, now), false);
  }
  assert.equal(processRowCurrent(process, { ...row, read_state: 'absent', pid_running: false, identity_verified: false }, now), true);
});
test('history requires explicit recorded classification and original readable record clock', () => {
  const result = surfaceEvidence(history, now);
  assert.equal(result.historical, true);
  assert.equal(result.current, false);
  assert.equal(result.sourceTime, new Date(1_000_000).toISOString());
  for (const change of [{ historical_available: false }, { classification: 'current' }, { read_state: 'failed' },
    { source_timestamp: null }]) assert.equal(surfaceEvidence({ ...history, ...change }, now).historical, false);
});
test('a recently dated historical record never counts as a currently qualified runtime surface', () => {
  const value = { ...observed, historical_available: true, classification: 'recorded_history' };
  assert.equal(surfaceEvidence(value, now).current, false);
  assert.equal(surfaceEvidence(value, now).historical, true);
});
test('brain child clocks remain independent of each other and the umbrella receipt', () => {
  const rows = brainHistoryRecords({ receipt_timestamp: 2000, source_timestamp: null,
    accuracy: { ...history, total_predictions: 0, validated: 0, accuracy_pct: null },
    knowledge: { ...history, source_timestamp: null, entries: 123 },
  }, now);
  assert.equal(rows[0].evidence.historical, true);
  assert.deepEqual(rows[0].rows[0], ['Predictions', '0']);
  assert.equal(rows[0].rows[2][1], 'Unavailable');
  assert.equal(rows[1].evidence.displayable, false);
});
test('historical pass/fail and missing benchmark result are three different outcomes', () => {
  const report = surfaceEvidence({ ...history, classification: 'recorded_benchmark', source_clock_kind: 'benchmark_generation' }, now);
  assert.equal(benchmarkResult(true, report), 'Recorded pass');
  assert.equal(benchmarkResult(false, report), 'Recorded fail');
  assert.equal(benchmarkResult(null, report), 'Unavailable');
  assert.equal(benchmarkResult(true, surfaceEvidence(observed, now)), 'Unavailable');
});
test('a runtime trace cannot promote benchmark metrics or missing report clocks', () => {
  assert.equal(surfaceEvidence(observed, now).current, true);
  const report = surfaceEvidence({ ...history, source_timestamp: null, receipt_timestamp: 2000 }, now);
  assert.equal(benchmarkResult(true, report), 'Unavailable');
  assert.equal(report.historical, false);
});
test('observed zero and false survive, while missing and nonfinite values remain unavailable', () => {
  assert.equal(observedValue(0), '0'); assert.equal(observedValue(false), 'No');
  assert.equal(observedPercent(0), '0%');
  for (const value of [null, undefined, NaN, Infinity, {}, '']) assert.equal(observedValue(value), 'Unavailable');
  assert.equal(observedPercent(Infinity), 'Unavailable');
});
test('authorization failure remains distinct from transport failure and expiry', () => {
  assert.match(readFailureMessage(401, false, null), /Sign in/);
  assert.match(readFailureMessage(403, false, null), /not permitted/);
  assert.match(readFailureMessage(null, true, null), /could not be reached/);
  assert.equal(readFailureMessage(null, false, 'HTTP receipt expired'), 'HTTP receipt expired');
});
