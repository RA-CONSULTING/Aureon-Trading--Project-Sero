import assert from 'node:assert/strict';
import test from 'node:test';
import { ApiError } from '../services/apiClient';
import { captureTestReceipt, datedTestEvidence } from './accountConfigurationEvidence';
import { normalizeProviderDraft, providerErrorDetail, providerRequestBody } from './providerDraft';

const provider = { model: 'fixture-configured-model', default_model: 'fixture-default-model',
  base_url: 'https://example.invalid/v1', default_base_url: 'http://127.0.0.1:11434/v1' };
test('unseeded drafts and button-only partial drafts construct a complete test body', () => {
  for (const partial of [undefined, { testing: true }, { saving: false }, { show: true }]) {
    const draft = normalizeProviderDraft(provider, partial);
    assert.equal(draft.apiKey, '');
    assert.deepEqual(providerRequestBody(draft), { model: provider.model, base_url: provider.base_url });
  }
});
test('draft normalization preserves deliberate blank edits and excludes absent keys', () => {
  const body = providerRequestBody(normalizeProviderDraft(provider, { model: '', baseUrl: '', apiKey: '   ' }));
  assert.deepEqual(body, { model: '', base_url: '' });
  assert.equal('api_key' in body, false);
});
test('a fresh session can seed only defaults without old entered credentials or operation flags', () => {
  const old = normalizeProviderDraft(provider, { apiKey: 'fixture-entered-key', testing: true });
  const fresh = normalizeProviderDraft(provider);
  assert.equal(old.testing, true); assert.equal(fresh.testing, false);
  assert.equal(fresh.apiKey, ''); assert.equal(fresh.saving, false);
});
test('completed HTTP failure is a dated failed test while malformed result remains unknown', () => {
  const result = captureTestReceipt({ ok: false, error: 'LLM HTTP disabled by audit mode', latency_ms: 0 }, 2000);
  assert.equal(datedTestEvidence(result, 2001).ok, false);
  assert.equal(datedTestEvidence(result, 2001).latencyMs, 0);
  assert.equal(result.error, 'LLM HTTP disabled by audit mode');
  assert.equal(datedTestEvidence(captureTestReceipt(undefined, 2000), 2001).current, false);
});
test('HTTP denial and transport detail survive without manufacturing a completed test receipt', () => {
  const denied = new ApiError('LLM HTTP disabled by audit mode', { status: 403, path: '/api/providers/fixture/test' });
  assert.equal(providerErrorDetail(denied), 'HTTP 403: LLM HTTP disabled by audit mode');
  const offline = new ApiError('Request timed out', { offline: true, path: '/api/providers/fixture/test' });
  assert.equal(providerErrorDetail(offline), 'Request timed out');
});
test('error display redacts entered credentials and common auth forms and is bounded', () => {
  const detail = providerErrorDetail(new ApiError('Rejected fixture-entered-key; Bearer fixture-token token=fixture-token https://name:pass@example.invalid',
    { status: 401, path: '/api/providers/fixture/test' }), 'fixture-entered-key');
  assert.match(detail, /^HTTP 401:/);
  assert.doesNotMatch(detail, /fixture-entered-key|fixture-token|name:pass/);
  assert.match(detail, /redacted/);
  assert.ok(providerErrorDetail('x'.repeat(2000)).length <= 400);
});
