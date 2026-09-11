import assert from 'node:assert/strict';
import test from 'node:test';
import { consoleNumber, consoleReceiptCurrent, generatedReportEvidence } from './generatedConsoleEvidence';

const now = Date.parse('2026-09-08T12:00:00Z');
test('missing, future and stale reports never become current on reread', () => {
  for (const value of [{}, { generated_at: 'invalid' }, { generated_at: '2026-09-08T12:00:06Z' }, { generated_at: '2026-09-08T11:54:59Z' }]) {
    assert.equal(generatedReportEvidence(value, now).current, false);
  }
  const report = { generated_at: '2026-09-08T12:00:00Z', ok: true };
  assert.equal(generatedReportEvidence(report, now).current, true);
  assert.equal(generatedReportEvidence(report, now + 300_001).current, false);
});
test('receipt expiry is independent of report flags and unknown numbers remain unavailable', () => {
  assert.equal(consoleReceiptCurrent(now, now + 30_001), false);
  assert.equal(consoleReceiptCurrent(null, now), false);
  assert.equal(consoleReceiptCurrent(now, now), true);
  for (const value of [null, undefined, '', false, NaN, Infinity]) assert.equal(consoleNumber(value), null);
  assert.equal(consoleNumber(0), 0);
});
