import test from 'node:test';
import assert from 'node:assert/strict';
import { readResonanceOneObservation, RESONANCE_ONE_UPDATE_MAX_AGE_MS, RESONANCE_ONE_WINDOW_MAX_AGE_MS, schumannContributionStatus } from './resonanceOneEvidence';
import { fetchResonanceOne, RESONANCE_ONE_MAX_BYTES } from './resonanceOnePublicSource';

const now = Date.parse('2026-09-08T17:10:00Z');
const iso = (value: number) => new Date(value).toISOString();
const report = (time = now) => ({ activity_index: 32, schumann_index: 34, kp_index: 3, solar_flare_index: 5,
  schumann_frequency_hz: 7.83, confidence_score: 90, local_interference: false, data_quality: 'good',
  updated_at: iso(time - 10 * 60_000), observation_window: { start: iso(time - 130 * 60_000), end: iso(time - 70 * 60_000) },
  data_source: 'tomsk', weighting: { schumann_pct: 70, kp_pct: 25, solar_pct: 5 },
  attribution: { schumann: 'Tomsk Space Observing System, TSU', kp: 'NOAA SWPC', solar: 'NOAA SWPC' } });

test('Hourly composite preserves provider clocks, attribution and reported components without a Hz metric', () => {
  const result = readResonanceOneObservation(report(), now, now)!;
  assert.equal(result.updatedAt, iso(now - 10 * 60_000));
  assert.equal(result.windowStart, iso(now - 130 * 60_000));
  assert.equal(result.windowEnd, iso(now - 70 * 60_000));
  assert.equal(result.receivedAt, iso(now));
  assert.deepEqual(result.weighting, { schumann: 70, kp: 25, solar: 5 });
  assert.equal(result.attribution.schumann, 'Tomsk Space Observing System, TSU');
  assert.equal('schumann_frequency_hz' in result, false);
  assert.equal(schumannContributionStatus(result), 'reported');
});

test('A fresh download cannot renew an expired provider update or original hourly window', () => {
  const staleUpdate = { ...report(), updated_at: iso(now - RESONANCE_ONE_UPDATE_MAX_AGE_MS - 1), observation_window: { start: iso(now - 130 * 60_000), end: iso(now - 100 * 60_000) } };
  assert.equal(readResonanceOneObservation(staleUpdate, now, now), null);
  const oldEnd = now - RESONANCE_ONE_WINDOW_MAX_AGE_MS - 1;
  const staleWindow = { ...report(), updated_at: iso(now), observation_window: { start: iso(oldEnd - 60 * 60_000), end: iso(oldEnd) } };
  assert.equal(readResonanceOneObservation(staleWindow, now, now), null);
  const later = now + 66 * 60_000;
  assert.equal(readResonanceOneObservation(report(), later, later), null);
});

test('Unknown values remain absent, numeric zero is observed, and bad primary metrics cannot qualify', () => {
  const data = { ...report(), activity_index: 0, schumann_index: undefined, kp_index: null, solar_flare_index: '0',
    confidence_score: Infinity, local_interference: undefined, weighting: { schumann_pct: 70 }, attribution: {} };
  const result = readResonanceOneObservation(data, now, now)!;
  assert.equal(result.activityIndex, 0);
  for (const value of [result.schumannIndex, result.kpIndex, result.solarFlareIndex, result.confidenceScore, result.localInterference, result.weighting, result.attribution.schumann]) assert.equal(value, null);
  for (const activity_index of [undefined, null, false, '32', NaN, Infinity, -1, 101]) {
    assert.equal(readResonanceOneObservation({ ...report(), activity_index }, now, now), null);
  }
});

test('Interference preserves the held classification; unknown interference never becomes clear', () => {
  const held = readResonanceOneObservation({ ...report(), local_interference: true, confidence_score: 40 }, now, now)!;
  assert.equal(held.schumannIndex, 34);
  assert.equal(held.localInterference, true);
  assert.equal(schumannContributionStatus(held), 'held');
  for (const flag of [undefined, null, 'false', 0]) {
    const unknown = readResonanceOneObservation({ ...report(), local_interference: flag }, now, now)!;
    assert.equal(schumannContributionStatus(unknown), 'unavailable');
  }
});

test('Missing, future, reordered and invalid calendar dates never attest a current report', () => {
  assert.equal(readResonanceOneObservation({}, now, now), null);
  for (const updated_at of [undefined, '2026-02-31T17:00:00Z', '2026-09-08T17:00:00', iso(now + 6_000)]) {
    assert.equal(readResonanceOneObservation({ ...report(), updated_at }, now, now), null);
  }
  assert.equal(readResonanceOneObservation({ ...report(), observation_window: { start: iso(now), end: iso(now - 1) } }, now, now), null);
  assert.equal(readResonanceOneObservation({ ...report(), observation_window: { start: iso(now - 60_000), end: iso(now) } }, now, now), null);
  assert.equal(readResonanceOneObservation(report(), now + 6_000, now), null);
});

test('Public transport requires HTTP success, original clocks and a valid bounded JSON body', async () => {
  let init: RequestInit | undefined;
  const result = await fetchResonanceOne(undefined, async (_url, request) => { init = request; return Response.json(report(Date.now())); });
  assert.ok(result.receivedAt > 0);
  assert.equal(init?.credentials, 'omit');
  assert.equal(init?.cache, 'default');
  await assert.rejects(fetchResonanceOne(undefined, async () => new Response('', { status: 503 })), /HTTP 503/);
  await assert.rejects(fetchResonanceOne(undefined, async () => Response.json(report(Date.now() - 4 * 60 * 60_000))), /stale/);
  await assert.rejects(fetchResonanceOne(undefined, async () => new Response('{')), /JSON/);
  await assert.rejects(fetchResonanceOne(undefined, async () => new Response('x', { headers: { 'content-length': String(RESONANCE_ONE_MAX_BYTES + 1) } })), /size limit/);
});

test('Stream cap cancels excessive responses and aborted callers retain cancellation', async () => {
  let cancelled = false;
  const body = new ReadableStream<Uint8Array>({ pull(controller) { controller.enqueue(new Uint8Array(RESONANCE_ONE_MAX_BYTES + 1)); }, cancel() { cancelled = true; } });
  await assert.rejects(fetchResonanceOne(undefined, async () => new Response(body)), /size limit/);
  assert.equal(cancelled, true);
  const controller = new AbortController(); controller.abort();
  await assert.rejects(fetchResonanceOne(controller.signal, async (_url, init) => { assert.equal(init?.signal?.aborted, true); throw new DOMException('Aborted', 'AbortError'); }), /Aborted/);
});
