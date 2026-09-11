import assert from 'node:assert/strict';
import test from 'node:test';
import { earthGlassObservation } from './researchGlassEvidence';
import { readSchumannObservation, type SchumannData } from './earthObservationEvidence';

const now = Date.parse('2026-09-11T19:00:00Z');
const station: SchumannData = { measurementKind: 'station_activity', frequencyReported: false, fundamentalHz: 7.83,
  amplitude: 37, quality: 1, variance: 0, coherenceBoost: 0, timestamp: new Date(now - 1000), sourceId: 'station-receipt',
  resonancePhase: 'stable', harmonics: [{ frequency: 7.83, amplitude: 37, name: 'nominal' }], spectrumHistory: [], dataSource: 'LIVE',
  activityScore: 37, stationCount: 5, stationsMonitored: 6, stationSignals: [] };

test('station activity never becomes measured Schumann frequency or spectrum', () => {
  const view = earthGlassObservation(station, now);
  assert.equal(view.available, true);
  assert.equal(view.observation?.activityScore, 37);
  assert.equal(view.frequency, null);
  assert.deepEqual(view.harmonics, []);
  assert.equal(earthGlassObservation({ ...station, frequencyReported: true }, now).frequency, null);
});
test('only current frequency-kind observations expose reported Hz and harmonics', () => {
  const frequency: SchumannData = { ...station, measurementKind: 'frequency', frequencyReported: true, fundamentalHz: 8.1 };
  assert.equal(earthGlassObservation(frequency, now).frequency, 8.1);
  assert.equal(earthGlassObservation(frequency, now).harmonics.length, 1);
  assert.equal(earthGlassObservation({ ...frequency, fundamentalHz: NaN }, now).frequency, null);
  assert.equal(earthGlassObservation({ ...frequency, frequencyReported: false }, now).frequency, null);
});
test('research glass expires old observations and rejects future or absent timestamps', () => {
  for (const value of [null, { ...station, timestamp: new Date(now - 20 * 60000 - 1) },
    { ...station, timestamp: new Date(now + 5001) }, { ...station, timestamp: new Date(NaN) }]) {
    const view = earthGlassObservation(value, now);
    assert.equal(view.available, false);
    assert.equal(view.frequency, null);
    assert.equal(view.observation, null);
  }
});

test('parsed short-TTL station receipt expires in the glass before the next minute poll', () => {
  const payload = { truthStatus: 'real_observed', generatedValues: false, sourceId: 'station-source',
    sourceTimestamp: new Date(now - 1000).toISOString(), freshnessTtlSeconds: 30,
    measurementKind: 'station_activity', frequencyReported: false, frequencyBasis: 'nominal_reference_not_source_measurement',
    fundamentalHz: 7.83, amplitude: 0.1, quality: 1, variance: 0, coherenceBoost: 0, resonancePhase: 'stable', activityScore: 10,
    stationSignals: [{ source: 'station-1', status: 'reported', activityScore: 10, timestamp: new Date(now - 20_000).toISOString() }] };
  const data = readSchumannObservation(payload, now);
  assert.ok(data);
  assert.equal(earthGlassObservation(data, now).expiresAtMs, now + 10_000);
  assert.equal(earthGlassObservation(data, now + 9999).available, true);
  assert.equal(earthGlassObservation(data, now + 10_000).available, false);
  assert.equal(earthGlassObservation(data, now + 10_000).observation, null);
});
