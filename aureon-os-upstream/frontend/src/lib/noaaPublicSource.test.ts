import assert from 'node:assert/strict';
import test from 'node:test';
import { NOAA_FEEDS, NOAA_RESPONSE_MAX_BYTES, noaaFeedView } from './noaaObservationEvidence';
import { fetchNoaaFeed } from './noaaPublicSource';
import { setAuthTokenProvider } from '../services/apiClient';

const now = Date.parse('2026-09-08T16:00:00Z');
const payload = [{ time_tag: '2026-09-08T15:59:00Z', active: true, source: 'SOLAR1', proton_speed: 450, proton_density: 0, proton_temperature: 110_000 }];
const controller = () => new AbortController();

test('public reader uses the exact documented GET with omitted credentials and original source clock', async () => {
  const fetcher = (async (url, init) => {
    assert.equal(url, NOAA_FEEDS.wind.url);
    assert.equal(init?.method, 'GET');
    assert.equal(init?.credentials, 'omit');
    assert.equal(init?.cache, 'no-cache');
    assert.ok(init?.signal);
    return new Response(JSON.stringify(payload));
  }) as typeof fetch;
  const result = await fetchNoaaFeed('wind', controller().signal, fetcher, () => now);
  assert.equal(result.receivedAt, now);
  assert.equal(noaaFeedView(result, now).current?.observedAt, payload[0].time_tag.replace('Z', '.000Z'));
});

test('same-origin research gateway retains the authenticated cloud session', async () => {
  const originalFetch = globalThis.fetch;
  const gatewayReceipt = {
    feed: 'wind', status: 'observed', receivedAt: now, samples: [{
      source: 'SOLAR1', observedAt: '2026-09-08T15:59:00.000Z',
      values: { proton_speed: 450, proton_density: 0, proton_temperature: 110_000 },
    }], reason: 'NOAA public source response via local gateway',
  };
  globalThis.fetch = (async (url, init) => {
    assert.equal(url, '/api/research/noaa/wind');
    assert.equal(init?.method, 'GET');
    assert.equal((init?.headers as Record<string, string>)?.Authorization, 'Bearer tenant-test-token');
    return new Response(JSON.stringify(gatewayReceipt));
  }) as typeof fetch;
  setAuthTokenProvider(async () => 'tenant-test-token');
  try {
    const result = await fetchNoaaFeed('wind', controller().signal);
    assert.equal(result.status, 'observed');
    assert.equal(result.samples.length, 1);
  } finally {
    setAuthTokenProvider(null);
    globalThis.fetch = originalFetch;
  }
});

test('HTTP failure, malformed JSON and transport failure leave values unavailable', async () => {
  for (const fetcher of [
    async () => new Response(JSON.stringify(payload), { status: 503 }),
    async () => new Response('not-json'),
    async () => { throw new Error('Public source unreachable'); },
  ]) {
    const result = await fetchNoaaFeed('wind', controller().signal, fetcher as typeof fetch, () => now);
    assert.equal(result.status, 'unavailable');
    assert.deepEqual(result.samples, []);
    assert.equal(result.receivedAt, null);
  }
});

test('8MiB cap is enforced on both declared and actual streamed bytes', async () => {
  let cancelled = 0;
  const large = new ReadableStream<Uint8Array>({
    start(stream) { stream.enqueue(new Uint8Array(NOAA_RESPONSE_MAX_BYTES)); stream.enqueue(new Uint8Array(1)); },
    cancel() { cancelled++; },
  });
  const streamed = await fetchNoaaFeed('wind', controller().signal, (async () => new Response(large)) as typeof fetch, () => now);
  assert.match(streamed.reason, /8 MiB/);
  assert.equal(cancelled, 1);
  const declared = await fetchNoaaFeed('wind', controller().signal,
    (async () => new Response('{}', { headers: { 'Content-Length': String(NOAA_RESPONSE_MAX_BYTES + 1) } })) as typeof fetch, () => now);
  assert.equal(declared.status, 'unavailable');
  assert.match(declared.reason, /8 MiB/);
});

test('unmount cancellation propagates to an in-flight fetch and cannot publish an observation', async () => {
  const parent = controller();
  const fetcher = (async (_url, init) => new Promise<Response>((_resolve, reject) => {
    init?.signal?.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')), { once: true });
  })) as typeof fetch;
  const pending = fetchNoaaFeed('wind', parent.signal, fetcher, () => now);
  parent.abort();
  const result = await pending;
  assert.equal(result.status, 'unavailable');
  assert.match(result.reason, /cancelled/);
  assert.equal(result.receivedAt, null);
});
