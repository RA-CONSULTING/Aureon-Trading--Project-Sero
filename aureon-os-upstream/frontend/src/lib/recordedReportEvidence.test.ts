import assert from 'node:assert/strict';
import test from 'node:test';
import { recordedArrayCount, recordedBoolean, recordedContractCheck, recordedNumber, recordedReportEvidence, reportBoundaryEvidence } from './recordedReportEvidence';

const now = Date.parse('2026-09-08T16:00:00Z');

test('recorded scope preserves historical dates while the existing current boundary stays strict', () => {
  const historical = { generated_at: '2026-07-13T12:00:00Z', summary: { role_count: 0 } };
  assert.equal(reportBoundaryEvidence(historical, 'recorded', now).current, true);
  assert.equal(reportBoundaryEvidence(historical, 'current', now).current, false);
  assert.equal(reportBoundaryEvidence(historical, undefined, now).current, false);
  assert.match(reportBoundaryEvidence(historical, 'recorded', now).reason, /Historical/);
  const recent = { generated_at: new Date(now).toISOString() };
  assert.equal(reportBoundaryEvidence(recent, 'current', now).current, true);
  assert.equal(reportBoundaryEvidence(recent, 'current', now + 300_001).current, false);
});

test('original valid report dates are required and a fresh download cannot replace them', () => {
  for (const report of [null, [], {}, { generated_at: 'invalid' }, { generated_at: '2026-02-31' },
    { generated_at: new Date(now + 6_000).toISOString() }, { received_at: new Date(now).toISOString() }]) {
    assert.equal(recordedReportEvidence(report, now).current, false);
  }
  assert.equal(recordedReportEvidence({ snapshot_date: '2026-07-13' }, now).timestamp, '2026-07-13');
  assert.equal(recordedReportEvidence({ generated_at: '2026-07-13T00:00:00+01:00' }, now).current, true);
});

test('only an explicit false contract claim yields recorded clear, never absence or string false', () => {
  assert.equal(recordedContractCheck(false), 'recorded clear');
  assert.equal(recordedContractCheck(true), 'recorded review');
  for (const value of [undefined, null, 0, '', 'false', {}, []]) assert.equal(recordedContractCheck(value), 'unavailable');
  assert.equal(recordedBoolean(false), 'false');
  assert.equal(recordedBoolean(true), 'true');
  assert.equal(recordedBoolean('true'), 'Unavailable');
});

test('observed zero and empty arrays differ from missing or malformed recorded metrics', () => {
  assert.equal(recordedNumber(0), '0');
  assert.equal(recordedNumber(0, '%'), '0%');
  assert.equal(recordedArrayCount([]), '0');
  for (const value of [undefined, null, false, '', '42', NaN, Infinity, -1, {}]) assert.equal(recordedNumber(value, '%'), 'Unavailable');
  assert.equal(recordedArrayCount(undefined), 'Unavailable');
  assert.equal(recordedArrayCount(''), 'Unavailable');
});
