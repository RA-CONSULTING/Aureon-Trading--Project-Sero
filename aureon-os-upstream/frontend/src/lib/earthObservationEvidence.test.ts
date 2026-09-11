import assert from 'node:assert/strict';
import test from 'node:test';
import { EARTH_TELEMETRY_MAX_AGE_MS, SEISMIC_RECEIPT_MAX_AGE_MS, readSchumannObservation, readSeismicObservation, validNoaaObservation } from './earthObservationEvidence';

const now = Date.parse('2026-09-08T10:00:00Z');
const stamp = new Date(now - 1_000).toISOString();
const schumann = () => ({ truthStatus: 'real_observed', generatedValues: false, sourceId: 'station-test',
  sourceTimestamp: stamp, measurementKind: 'frequency', frequencyReported: true, fundamentalHz: 7.82, amplitude: 0, quality: 0, variance: 0,
  coherenceBoost: 0, resonancePhase: 'disturbed' });
const stationActivity = () => ({ truthStatus: 'real_observed', generatedValues: false, sourceId: 'SUNGEO_STATION_ACTIVITY',
  sourceTimestamp: stamp, measurementKind: 'station_activity', frequencyReported: false,
  frequencyBasis: 'nominal_reference_not_source_measurement', fundamentalHz: 7.83,
  amplitude: 0.44, activityScore: 44, quality: 0.83, variance: 0.01, coherenceBoost: 0,
  resonancePhase: 'elevated', stationCount: 5, stationsMonitored: 6,
  stationSignals: [{ source: 'bgs', status: 'active', activityScore: 65, timestamp: stamp }] });
const noaa = () => ({
  timestamp: new Date(now).toISOString(), truthStatus: 'live',
  solarWind: { current: { timestamp: stamp, speed: 400, density: 0, temperature: 1, bz: 0 }, history: [],
    provenance: { sourceId: 'noaa_swpc_rtsw', truthStatus: 'live', sourceTimestamp: stamp } },
  magnetometer: { current: { timestamp: stamp, hComponent: 1, intensity: 2, kIndex: 0 }, history: [],
    provenance: { sourceId: 'noaa_swpc_goes_magnetometer', truthStatus: 'live', sourceTimestamp: stamp } },
  aurora: { current: { timestamp: new Date(now + 3_600_000).toISOString(), kpIndex: 0, probability: 0, viewingLatitude: 70 }, forecast: [] },
  alerts: { solarWindAlert: false, magneticStorm: false, auroraAlert: false },
});

test('Schumann accepts observed zeros, preserves the source clock and invents no harmonics', () => {
  const value = readSchumannObservation(schumann(), now);
  assert.ok(value);
  assert.equal(value.amplitude, 0);
  assert.equal(value.quality, 0);
  assert.equal(value.variance, 0);
  assert.equal(value.timestamp.toISOString(), stamp);
  assert.deepEqual(value.harmonics, []);
});

test('Schumann accepts direct station activity without treating nominal frequency as measured', () => {
  const value = readSchumannObservation(stationActivity(), now);
  assert.ok(value);
  assert.equal(value.measurementKind, 'station_activity');
  assert.equal(value.frequencyReported, false);
  assert.equal(value.fundamentalHz, 7.83);
  assert.equal(value.activityScore, 44);
  assert.equal(value.coherenceBoost, 0);
  assert.equal(value.stationSignals[0].source, 'bgs');
  assert.equal(readSchumannObservation({ ...stationActivity(), frequencyReported: true }, now), null);
  assert.equal(readSchumannObservation({ ...stationActivity(), coherenceBoost: 0.01 }, now), null);
});

test('derived proxies and incomplete measurements cannot become direct Schumann observations', () => {
  assert.equal(readSchumannObservation({ ...schumann(), truthStatus: 'real_derived' }, now), null);
  for (const field of ['sourceTimestamp', 'measurementKind', 'frequencyReported', 'amplitude', 'quality', 'variance', 'resonancePhase']) {
    const incomplete: Record<string, unknown> = schumann();
    delete incomplete[field];
    assert.equal(readSchumannObservation(incomplete, now), null, field);
  }
  assert.equal(readSchumannObservation({ ...schumann(), amplitude: Number.NaN }, now), null);
  assert.equal(readSchumannObservation({ ...schumann(), measurementKind: 'unknown' }, now), null);
  assert.equal(readSchumannObservation({ ...schumann(), frequencyReported: false }, now), null);
});

test('Schumann retains the bounded provider expiry and oldest station source deadline', () => {
  const source = { ...stationActivity(), freshnessTtlSeconds: 30,
    stationSignals: [{ ...stationActivity().stationSignals[0], timestamp: new Date(now - 20_000).toISOString() }] };
  const value = readSchumannObservation(source, now);
  assert.ok(value);
  assert.equal(value.expiresAt?.getTime(), now + 10_000);
  assert.equal(readSchumannObservation(source, now + 10_001), null);
  assert.equal(readSchumannObservation({ ...schumann(), freshnessTtlSeconds: 3600 }, now)?.expiresAt?.getTime(), Date.parse(stamp) + EARTH_TELEMETRY_MAX_AGE_MS);
});

test('fresh fetch metadata cannot renew expired or future source observations', () => {
  assert.equal(readSchumannObservation({ ...schumann(), collectedAt: new Date(now).toISOString() }, now + EARTH_TELEMETRY_MAX_AGE_MS), null);
  assert.equal(readSchumannObservation({ ...schumann(), sourceTimestamp: new Date(now + 6_000).toISOString() }, now), null);
});

test('NOAA telemetry expires per original sensor and provenance clocks', () => {
  const data = noaa();
  assert.equal(validNoaaObservation(data, now), true);
  data.solarWind.current.timestamp = new Date(now - EARTH_TELEMETRY_MAX_AGE_MS - 1).toISOString();
  assert.equal(validNoaaObservation(data, now), false);
  const oldReceipt = noaa();
  oldReceipt.magnetometer.provenance.sourceTimestamp = data.solarWind.current.timestamp;
  assert.equal(validNoaaObservation(oldReceipt, now), false);
  assert.equal(validNoaaObservation({ error: 'upstream unavailable' }, now), false);
});

test('NOAA preserves measured zero and rejects missing or malformed sensor values', () => {
  const data = noaa();
  assert.equal(validNoaaObservation(data, now), true);
  assert.equal(validNoaaObservation({ ...data, solarWind: { ...data.solarWind, current: { timestamp: stamp } } }, now), false);
  data.magnetometer.current.kIndex = Infinity;
  assert.equal(validNoaaObservation(data, now), false);
});

test('USGS empty results differ from missing data and event times stay original', () => {
  assert.deepEqual(readSeismicObservation({ timestamp: stamp, events: [] }, now), { timestamp: stamp, events: [] });
  assert.equal(readSeismicObservation(null, now), null);
  assert.equal(readSeismicObservation({ timestamp: stamp, events: [] }, now + SEISMIC_RECEIPT_MAX_AGE_MS), null);
  const event = { id: 'event', magnitude: 0, depth: 0, location: 'Observed location', timestamp: new Date(now - 86_400_000).toISOString(), latitude: 0, longitude: 0, significance: 0 };
  assert.equal(readSeismicObservation({ timestamp: stamp, events: [event] }, now)?.events[0].timestamp, event.timestamp);
  assert.equal(readSeismicObservation({ timestamp: stamp, events: [{ ...event, magnitude: null }] }, now), null);
});
