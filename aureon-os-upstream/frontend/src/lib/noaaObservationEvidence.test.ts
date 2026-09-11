import assert from 'node:assert/strict';
import test from 'node:test';
import { NOAA_SOURCE_MAX_AGE_MS, emptyNoaaReceipt, noaaFeedView, readNoaaFeed } from './noaaObservationEvidence';

const now = Date.parse('2026-09-08T16:00:00Z');
const stamp = new Date(now - 60_000).toISOString();
const wind = (extra = {}) => ({ time_tag: stamp, active: true, source: 'SOLAR1',
  proton_speed: 450, proton_density: 0, proton_temperature: 110_000, ...extra });

test('NOAA selects the latest qualified active row irrespective of provider ordering', () => {
  const older = new Date(now - 120_000).toISOString();
  const value = readNoaaFeed('wind', [wind(), wind({ time_tag: older, proton_speed: 400 }),
    wind({ time_tag: new Date(now).toISOString(), active: false, proton_speed: 900 })], now);
  assert.equal(noaaFeedView(value, now).current?.observedAt, stamp);
  assert.equal(noaaFeedView(value, now).current?.values.proton_speed, 450);
  assert.equal(noaaFeedView(value, now).current?.source, 'SOLAR1');
});

test('each NOAA product keeps its original clock, not a clock copied from another product', () => {
  const imfTime = new Date(now - 180_000).toISOString();
  const kpTime = new Date(now - 240_000).toISOString();
  assert.equal(readNoaaFeed('imf', [{ time_tag: imfTime, active: true, source: 'ACE', bz_gsm: 0 }], now).samples[0].observedAt, imfTime);
  assert.equal(readNoaaFeed('kp', [{ time_tag: kpTime, estimated_kp: 0 }], now).samples[0].observedAt, kpTime);
  assert.equal(readNoaaFeed('wind', [wind({ time_tag: '2026-09-08T15:59:00' })], now).samples[0].observedAt, stamp);
});

test('measured zero survives while missing, string, infinite and sentinel values stay null', () => {
  const value = readNoaaFeed('wind', [wind({ proton_speed: null, proton_temperature: Infinity })], now);
  assert.deepEqual(value.samples[0].values, { proton_speed: null, proton_density: 0, proton_temperature: null });
  assert.equal(readNoaaFeed('wind', [wind({ proton_speed: '450', proton_density: null, proton_temperature: -9999 })], now).status, 'unavailable');
  assert.equal(readNoaaFeed('imf', [{ time_tag: stamp, active: true, source: 'ACE', bz_gsm: -9999 }], now).status, 'unavailable');
});

test('repeated successful receipts never freshen an expired source row', () => {
  const expiredAt = now + NOAA_SOURCE_MAX_AGE_MS;
  const renewedDownload = readNoaaFeed('wind', [wind()], expiredAt);
  assert.equal(renewedDownload.receivedAt, expiredAt);
  assert.equal(noaaFeedView(renewedDownload, expiredAt).status, 'stale');
  assert.equal(noaaFeedView(renewedDownload, expiredAt).current, null);
  const original = readNoaaFeed('wind', [wind()], now);
  assert.equal(noaaFeedView(original, now).available, true);
  assert.equal(noaaFeedView(original, expiredAt).available, false);
});

test('missing and malformed clocks, future rows, missing sources and unqualified satellites are rejected', () => {
  for (const time_tag of [null, '', 'not-a-date', new Date(now + 6_000).toISOString()]) {
    assert.equal(readNoaaFeed('wind', [wind({ time_tag })], now).status, 'unavailable');
  }
  assert.equal(readNoaaFeed('wind', [wind({ source: '' })], now).status, 'unavailable');
  const goes = { time_tag: stamp, satellite: 19, Hp: 0, total: 0, arcjet_flag: false };
  assert.equal(readNoaaFeed('goes', [goes], now).samples[0].source, 'NOAA GOES-19');
  assert.equal(readNoaaFeed('goes', [{ ...goes, arcjet_flag: true }], now).status, 'unavailable');
  assert.equal(readNoaaFeed('goes', [{ ...goes, satellite: null }], now).status, 'unavailable');
  assert.equal(readNoaaFeed('kp', [{ time_tag: stamp, estimated_kp: 10 }], now).status, 'unavailable');
});

test('one absent feed never removes another fresh feed and never fabricates a forecast', () => {
  const receipts = { wind: readNoaaFeed('wind', [wind()], now), kp: emptyNoaaReceipt('kp', false, 'HTTP failure') };
  assert.equal(noaaFeedView(receipts.wind, now).available, true);
  assert.equal(noaaFeedView(receipts.kp, now).current, null);
  assert.deepEqual(receipts.kp.samples, []);
  assert.equal('aurora' in receipts, false);
});

test('large source history retains only60 original rows and invalid rows produce no fake points', () => {
  const payload = Array.from({ length: 4000 }, (_, i) => wind({ time_tag: new Date(now - i * 60_000).toISOString() }));
  payload.push(wind({ time_tag: 'invalid' }));
  const value = readNoaaFeed('wind', payload, now);
  assert.equal(value.samples.length, 60);
  assert.equal(value.samples.at(-1)?.observedAt, new Date(now).toISOString());
  for (const payload of [null, {}, [], [null], [wind({ active: false })]]) {
    assert.equal(readNoaaFeed('wind', payload, now).status, 'unavailable');
  }
});
