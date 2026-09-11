import assert from 'node:assert/strict';
import test from 'node:test';
import { captureTestReceipt, configurationMessage, configurationStatus, datedTestEvidence, readIdentity,
  readProviderList, setupFromReceipt, UNKNOWN_IDENTITY, validKeyCoverage, type ProviderList } from './accountConfigurationEvidence';
import type { ReadOnlySnapshot } from '../services/readOnlyPoller';

function receipt(overrides: Partial<ReadOnlySnapshot<ProviderList>> = {}): ReadOnlySnapshot<ProviderList> {
  return { data: { providers: [] }, loading: false, error: null, offline: false, httpStatus: null,
    resetVersion: 1, lastReceivedAt: 100_000, isReceiptCurrent: true, source: { status: 'unattested' }, ...overrides };
}
test('missing provider inventory is unknown; a complete observed empty inventory is zero', () => {
  for (const value of [null, {}, { providers: null }, { providers: [{}] }, { providers: [{ id: 'fixture', has_key: null }] }]) {
    assert.equal(readProviderList(value), null);
  }
  const state = setupFromReceipt(receipt());
  assert.equal(state.known, true);
  assert.equal(state.hasProvider, false);
  assert.equal(state.providerCount, 0);
});
test('401 and403 remain distinct from offline, unconfigured and other errors', () => {
  for (const [httpStatus, expected] of [[401, 'unauthorized'], [403, 'forbidden'], [503, 'error']] as const) {
    const state = setupFromReceipt(receipt({ data: null, error: 'request failed', httpStatus, isReceiptCurrent: false }));
    assert.equal(state.status, expected);
    assert.equal(state.known, false);
    assert.equal(state.providerCount, null);
    assert.equal(state.hasProvider, null);
    assert.equal(state.offline, false);
    assert.notEqual(configurationMessage(state.status, state.error), 'No key set.');
  }
  assert.equal(configurationStatus(receipt({ data: null, error: 'transport failed', offline: true, isReceiptCurrent: false })), 'offline');
});
test('configuration expiration and session reset cannot retain old key counts', () => {
  const current = receipt({ data: { providers: [{ id: 'fixture', has_key: true, live: true }] } });
  assert.equal(setupFromReceipt(current).providerCount, 1);
  for (const change of [
    { data: null, isReceiptCurrent: false, error: 'HTTP receipt expired; current data unavailable' },
    { data: null, isReceiptCurrent: false, loading: true, lastReceivedAt: null, resetVersion: 2 },
  ]) {
    const state = setupFromReceipt({ ...current, ...change });
    assert.equal(state.hasProvider, null);
    assert.equal(state.providerCount, null);
  }
});
test('runtime attachment is not evidence of a successful dated test', () => {
  const state = setupFromReceipt(receipt({ data: { providers: [{ id: 'fixture', has_key: true, live: true }] } }));
  assert.equal(state.hasProvider, true);
  assert.equal(state.liveProvider, true);
  assert.equal(state.testedProvider, false);
  assert.equal(state.testedProviderReason, 'Run a provider test to record a successful connection.');
  assert.equal(setupFromReceipt(receipt({ data: { providers: [{ id: 'fixture', has_key: false }] } })).liveProvider, null);
});
test('persisted successful test history completes step 2/3 attestation', () => {
  const state = setupFromReceipt(receipt({ data: { providers: [{ id: 'fixture', has_key: true, live: false, last_test_ok: true }] } }));
  assert.equal(state.hasProvider, true);
  assert.equal(state.testedProvider, true);
  assert.equal(state.testedProviderReason, null);
});
test('persisted failed test history does not complete step 2/3 attestation', () => {
  const state = setupFromReceipt(receipt({ data: { providers: [{ id: 'fixture', has_key: true, last_test_ok: false, last_test_error: 'denied' }] } }));
  assert.equal(state.hasProvider, true);
  assert.equal(state.testedProvider, false);
});
test('identity requires explicit coherent fields; unknown never defaults to administrator', () => {
  assert.equal(readIdentity({ kind: 'tenant' }), null);
  assert.equal(UNKNOWN_IDENTITY.isAdmin, false);
  assert.equal(UNKNOWN_IDENTITY.tenancyEnabled, null);
  assert.equal(UNKNOWN_IDENTITY.authRequired, null);
  const tenant = { kind: 'tenant', is_admin: false, plane: 'account', tenancy_enabled: true, auth_required: true, allowed_routes: ['GET /api/me'] };
  assert.equal(readIdentity(tenant)?.isAdmin, false);
  assert.equal(readIdentity({ ...tenant, is_admin: true }), null);
  assert.equal(readIdentity({ ...tenant, allowed_routes: null }), null);
  const operator = { kind: 'open', is_admin: true, plane: 'instance', tenancy_enabled: false, auth_required: false, allowed_routes: null };
  assert.equal(readIdentity(operator)?.kind, 'open');
});
test('test receipt preserves actual zero latency and expires without clock renewal', () => {
  const source = captureTestReceipt({ ok: true, latency_ms: 0 }, 100_000);
  const current = datedTestEvidence(source, 100_001);
  assert.equal(current.ok, true);
  assert.equal(current.latencyMs, 0);
  assert.equal(current.clockKind, 'local_http_receipt');
  const expired = datedTestEvidence(source, 400_001);
  assert.equal(expired.current, false);
  assert.equal(expired.ok, null);
  assert.equal(expired.timestamp, current.timestamp);
  assert.equal(source.receivedAt, 100_000);
});
test('missing test success, invalid date and future date cannot become a successful current test', () => {
  assert.equal(datedTestEvidence(captureTestReceipt({ latency_ms: 1 }, 100_000), 100_001).current, false);
  for (const receivedAt of [NaN, Infinity, 1e100, 0, 200_000]) {
    assert.equal(datedTestEvidence(captureTestReceipt({ ok: true }, receivedAt), 100_000).current, false);
  }
  assert.equal(datedTestEvidence(captureTestReceipt({ ok: false, error: 'denied' }, 100_000), 100_001).ok, false);
});
test('key coverage validates presence counts without relying on connected flags', () => {
  const data = { summary: { keyed_present: 1, keyed_total: 2, keyless: 3, missing_count: 1, capacity_pct: 50, all_connected: true }, missing: [{ id: 'fixture' }] };
  assert.equal(validKeyCoverage(data), true);
  assert.equal(validKeyCoverage({ ...data, summary: { ...data.summary, capacity_pct: 100 } }), false);
  assert.equal(validKeyCoverage({ ...data, missing: [] }), false);
  assert.equal(validKeyCoverage({ ...data, missing: [null] }), false);
  assert.equal(validKeyCoverage({ summary: { keyed_present: 0, keyed_total: 0, keyless: 0, missing_count: 0, capacity_pct: 100 }, missing: [] }), true);
  assert.equal(validKeyCoverage({}), false);
});
