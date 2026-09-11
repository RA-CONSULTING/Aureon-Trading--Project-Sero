import assert from 'node:assert/strict';
import test from 'node:test';
import { onboardingProviderEvidence } from './onboardingEvidence';
const now = Date.parse('2026-09-11T12:00:00Z');
test('unavailable account config stays unknown, empty config stays observed empty', () => {
  assert.equal(onboardingProviderEvidence(null, now).configured, null);
  assert.deepEqual(onboardingProviderEvidence([], now), { configured: 0, attached: false, tested: false, testedAt: null, testedProvider: null });
});
test('historical success retains original timestamp and does not imply runtime attachment', () => {
  const evidence = onboardingProviderEvidence([{ id: 'ollama', has_key: true, live: false, last_test_ok: true, last_test_at: '2026-09-09T21:05:41Z' }], now);
  assert.equal(evidence.tested, true); assert.equal(evidence.attached, false); assert.equal(evidence.testedAt, '2026-09-09T21:05:41Z');
});
test('removed providers and undated, malformed, future or failed tests never advance test completion', () => {
  for (const row of [{ has_key: false, last_test_ok: true, last_test_at: '2026-09-10T00:00:00Z' },
    { has_key: true, last_test_ok: true, last_test_at: null }, { has_key: true, last_test_ok: true, last_test_at: 'invalid' },
    { has_key: true, last_test_ok: true, last_test_at: '2026-09-12T00:00:00Z' }, { has_key: true, last_test_ok: false, last_test_at: '2026-09-10T00:00:00Z' }]) {
    assert.equal(onboardingProviderEvidence([{ id: 'provider', ...row }], now).tested, false);
  }
});
test('latest valid recorded successful provider test is selected without changing its clock', () => {
  const evidence = onboardingProviderEvidence([
    { id: 'a', has_key: true, live: true, last_test_ok: true, last_test_at: '2026-09-09T01:00:00Z' },
    { id: 'b', has_key: true, live: false, last_test_ok: true, last_test_at: '2026-09-10T02:00:00Z' }], now);
  assert.equal(evidence.testedProvider, 'b'); assert.equal(evidence.attached, true); assert.equal(evidence.configured, 2);
});
