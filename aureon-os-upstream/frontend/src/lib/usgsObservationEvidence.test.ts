import test from 'node:test';
import assert from 'node:assert/strict';
import { readUsgsObservation, USGS_SOURCE_MAX_AGE_MS } from './usgsObservationEvidence';
import { fetchUsgsEarthquakes, USGS_MAX_RESPONSE_BYTES } from './usgsPublicSource';

const now = Date.parse('2026-09-08T17:00:00Z');
const event = () => ({ type: 'Feature', id: 'test-quake', properties: { mag: 4.6, place: 'Test location', time: now - 86_400_000, updated: now - 60_000 }, geometry: { type: 'Point', coordinates: [12, 34, 0] } });
const feed = (features: unknown[] = [event()], generated = now - 1_000) => ({ type: 'FeatureCollection', metadata: { generated, status: 200, count: features.length }, features });

test('USGS feed freshness keeps original generation, event occurrence and update clocks distinct', () => {
  const result = readUsgsObservation(feed(), now, now)!;
  assert.equal(result.generatedAt, new Date(now - 1_000).toISOString());
  assert.equal(result.receivedAt, new Date(now).toISOString());
  assert.equal(result.events[0].occurredAt, new Date(now - 86_400_000).toISOString());
  assert.equal(result.events[0].updatedAt, new Date(now - 60_000).toISOString());
  assert.equal(readUsgsObservation(feed(), now + USGS_SOURCE_MAX_AGE_MS, now + USGS_SOURCE_MAX_AGE_MS), null);
  assert.equal(readUsgsObservation(feed([], now + 6_000), now, now), null);
});

test('Observed empty feeds and measured zero differ from missing metrics and malformed reports', () => {
  assert.equal(readUsgsObservation(feed([]), now, now)?.returnedCount, 0);
  const item = event(); item.properties.mag = 0;
  assert.equal(readUsgsObservation(feed([item]), now, now)?.events[0].magnitude, 0);
  const missing = { ...item, properties: { time: now - 1_000 } };
  const result = readUsgsObservation(feed([missing]), now, now)!;
  assert.equal(result.events[0].magnitude, null);
  assert.equal(result.events[0].updatedAt, null);
  assert.equal(result.events[0].location, null);
  assert.equal(result.events[0].depthKm, 0);
  assert.equal(readUsgsObservation({}, now, now), null);
  assert.equal(readUsgsObservation({ ...feed(), metadata: { generated: now, status: 200 } }, now, now), null);
});

test('Malformed-only event feeds are unavailable; partial records preserve explicit rejected count', () => {
  assert.equal(readUsgsObservation(feed([{}]), now, now), null);
  const result = readUsgsObservation(feed([{}, event()]), now, now)!;
  assert.equal(result.returnedCount, 2); assert.equal(result.rejectedCount, 1); assert.equal(result.events.length, 1);
  const item = event(); item.geometry.coordinates[0] = 999;
  assert.equal(readUsgsObservation(feed([item]), now, now), null);
});

test('Public reader requires successful HTTP and fresh provider time, never a fresh HTTP receipt alone', async () => {
  const current = { ...feed([]), metadata: { generated: Date.now(), status: 200, count: 0 } };
  let request: RequestInit | undefined;
  const ok: typeof fetch = async (_input, init) => { request = init; return Response.json(current); };
  assert.ok((await fetchUsgsEarthquakes(undefined, ok)).receivedAt > 0);
  assert.equal(request?.credentials, 'omit');
  await assert.rejects(fetchUsgsEarthquakes(undefined, async () => new Response('', { status: 503 })), /HTTP 503/);
  await assert.rejects(fetchUsgsEarthquakes(undefined, async () => Response.json(feed([], Date.now() - USGS_SOURCE_MAX_AGE_MS - 1_000))), /stale/);
  await assert.rejects(fetchUsgsEarthquakes(undefined, async () => new Response('{')), /JSON/);
});

test('Public reader rejects oversized declared and streamed bodies and propagates cancellation', async () => {
  await assert.rejects(fetchUsgsEarthquakes(undefined, async () => new Response('x', { headers: { 'content-length': String(USGS_MAX_RESPONSE_BYTES + 1) } })), /size limit/);
  let cancelled = false;
  const stream = new ReadableStream<Uint8Array>({ pull(controller) { controller.enqueue(new Uint8Array(USGS_MAX_RESPONSE_BYTES + 1)); }, cancel() { cancelled = true; } });
  await assert.rejects(fetchUsgsEarthquakes(undefined, async () => new Response(stream)), /size limit/);
  assert.equal(cancelled, true);
  const controller = new AbortController(); controller.abort();
  await assert.rejects(fetchUsgsEarthquakes(controller.signal, async (_input, init) => { assert.equal(init?.signal?.aborted, true); throw new DOMException('Aborted', 'AbortError'); }), /Aborted/);
});
