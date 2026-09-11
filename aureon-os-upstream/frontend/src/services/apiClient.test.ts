import assert from 'node:assert/strict';
import { afterEach, test } from 'node:test';
import { api, ApiError, setAuthTokenProvider } from './apiClient';

const originalFetch = globalThis.fetch;
afterEach(() => { globalThis.fetch = originalFetch; setAuthTokenProvider(null); });
const deferred = <T>() => {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>(done => { resolve = done; });
  return { promise, resolve };
};

test('token-resolution deadline prevents a late provider from starting a request', async () => {
  const token = deferred<string>();
  let calls = 0;
  setAuthTokenProvider(() => token.promise);
  globalThis.fetch = async () => { calls++; return new Response('{}'); };
  await assert.rejects(api.get('/api/status', { timeoutMs: 25 }), error => error instanceof ApiError && /timed out/.test(error.message));
  token.resolve('test-only-token');
  await new Promise(done => setTimeout(done, 5));
  assert.equal(calls, 0);
});

test('deadline covers a stalled successful JSON body', async () => {
  globalThis.fetch = async () => ({ ok: true, status: 200, json: () => new Promise(() => {}) }) as Response;
  await assert.rejects(api.get('/api/status', { timeoutMs: 25 }), error => error instanceof ApiError && error.offline && /timed out/.test(error.message));
});

test('deadline also covers an error response whose body never finishes', async () => {
  globalThis.fetch = async () => ({ ok: false, status: 503, json: () => new Promise(() => {}) }) as Response;
  await assert.rejects(api.get('/api/status', { timeoutMs: 25 }), error => error instanceof ApiError && /timed out/.test(error.message));
});

test('caller cancellation covers token resolution and removes its listener', async () => {
  const controller = new AbortController();
  const signal = controller.signal;
  let added = 0, removed = 0, calls = 0;
  const add = signal.addEventListener.bind(signal), remove = signal.removeEventListener.bind(signal);
  signal.addEventListener = (...args) => { added++; return add(...args); };
  signal.removeEventListener = (...args) => { removed++; return remove(...args); };
  setAuthTokenProvider(() => new Promise(() => {}));
  globalThis.fetch = async () => { calls++; return new Response('{}'); };
  const pending = api.get('/api/status', { signal, timeoutMs: 500 });
  controller.abort();
  await assert.rejects(pending, error => error instanceof ApiError && /cancelled/.test(error.message));
  assert.equal(calls, 0);
  assert.equal(added, 1);
  assert.equal(removed, 1);
});

test('already-aborted calls do not resolve credentials or start fetch', async () => {
  let calls = 0;
  setAuthTokenProvider(async () => { calls++; return null; });
  globalThis.fetch = async () => { calls++; return new Response('{}'); };
  await assert.rejects(api.get('/api/status', { signal: AbortSignal.abort() }), ApiError);
  assert.equal(calls, 0);
});

test('optional bearer, explicit headers, observed zero and JSON body remain unchanged', async () => {
  let options: RequestInit | undefined;
  setAuthTokenProvider(async () => 'test-only-token');
  globalThis.fetch = async (_path, opts) => { options = opts; return new Response('{"count":0}'); };
  assert.deepEqual(await api.post('/api/test', { count: 0 }), { count: 0 });
  assert.equal((options!.headers as Record<string, string>).Authorization, 'Bearer test-only-token');
  assert.equal(options!.body, '{"count":0}');
  assert.equal(options!.cache, 'no-store');
  setAuthTokenProvider(async () => { throw new Error('test provider rejection'); });
  await api.get('/api/status', { headers: { 'X-Test': 'present' } });
  assert.equal((options!.headers as Record<string, string>).Authorization, undefined);
  assert.equal((options!.headers as Record<string, string>)['X-Test'], 'present');
});

test('HTTP denial and malformed JSON remain reachable errors, not offline or success', async () => {
  globalThis.fetch = async () => new Response('{"error":"forbidden"}', { status: 403 });
  await assert.rejects(api.get('/api/status'), error => error instanceof ApiError && error.status === 403 && !error.offline);
  globalThis.fetch = async () => new Response('not-json', { status: 200 });
  await assert.rejects(api.get('/api/status'), error => error instanceof ApiError && error.status === 200 && !error.offline);
  globalThis.fetch = async () => new Response(null, { status: 204 });
  assert.equal(await api.get('/api/status'), undefined);
});

test('structured gateway holds retain their reason without exposing other response fields', async () => {
  globalThis.fetch = async () => new Response(JSON.stringify({ error: {
    code: 503, message: 'operator control-plane ingress held', reason_code: 'production_magic_star_release_unavailable',
    admission_commitment: 'fixture-private-commitment', handler_invoked: false,
  } }), { status: 503 });
  await assert.rejects(api.post('/api/providers/fixture/test', {}), error => error instanceof ApiError
    && error.status === 503 && !error.offline
    && error.message === 'operator control-plane ingress held: production_magic_star_release_unavailable'
    && !error.message.includes('fixture-private-commitment'));
});
