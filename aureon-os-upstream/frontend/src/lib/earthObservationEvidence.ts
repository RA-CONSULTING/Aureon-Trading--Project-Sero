export const EARTH_TELEMETRY_MAX_AGE_MS = 20 * 60 * 1000;
export const SEISMIC_RECEIPT_MAX_AGE_MS = 15 * 60 * 1000;

const record = (value: unknown): Record<string, unknown> | null =>
  typeof value === 'object' && value !== null && !Array.isArray(value) ? value as Record<string, unknown> : null;
export const finiteObservation = (value: unknown): value is number => typeof value === 'number' && Number.isFinite(value);

export function observationTime(value: unknown): number | null {
  if (value instanceof Date) return Number.isFinite(value.getTime()) ? value.getTime() : null;
  if (typeof value !== 'string' || !value.trim()) return null;
  // NOAA time tags without an offset are UTC, never the browser's local zone.
  const text = /(?:Z|[+-]\d\d:\d\d)$/i.test(value) ? value : `${value}Z`;
  const stamp = Date.parse(text);
  return Number.isFinite(stamp) ? stamp : null;
}

export function freshObservation(value: unknown, maxAgeMs: number, now = Date.now()): boolean {
  const stamp = observationTime(value);
  return stamp !== null && now - stamp >= -5_000 && now - stamp <= maxAgeMs;
}

export interface SchumannHarmonic { frequency: number; amplitude: number; name: string }
export type SchumannMeasurementKind = 'frequency' | 'station_activity';
export interface SchumannStationSignal { source: string; status: string; activityScore: number; timestamp: Date }
export interface SchumannData {
  measurementKind: SchumannMeasurementKind;
  fundamentalHz: number; frequencyReported: boolean; amplitude: number; quality: number; variance: number;
  timestamp: Date; expiresAt?: Date; sourceId: string; sourceUrl?: string; coherenceBoost: number;
  resonancePhase: 'stable' | 'elevated' | 'peak' | 'disturbed';
  harmonics: SchumannHarmonic[]; spectrumHistory: number[][]; dataSource: 'LIVE' | 'UNAVAILABLE';
  activityScore?: number; stationCount?: number; stationsMonitored?: number; stationSignals: SchumannStationSignal[];
}

export function readSchumannObservation(value: unknown, now = Date.now()): SchumannData | null {
  const data = record(value);
  if (!data || !['real_observed', 'live'].includes(String(data.truthStatus)) || data.generatedValues !== false
      || typeof data.sourceId !== 'string' || !data.sourceId.trim()) return null;
  const ttl = finiteObservation(data.freshnessTtlSeconds) && data.freshnessTtlSeconds > 0
    ? Math.min(EARTH_TELEMETRY_MAX_AGE_MS, data.freshnessTtlSeconds * 1000) : EARTH_TELEMETRY_MAX_AGE_MS;
  if (!freshObservation(data.sourceTimestamp, ttl, now)) return null;
  if (data.measurementKind !== 'station_activity' && data.measurementKind !== 'frequency') return null;
  const measurementKind: SchumannMeasurementKind = data.measurementKind;
  if (measurementKind === 'frequency' && data.frequencyReported !== true) return null;
  const frequencyReported = measurementKind === 'frequency' && data.frequencyReported === true;
  const { fundamentalHz, amplitude, quality, variance, coherenceBoost } = data;
  if (![fundamentalHz, amplitude, quality, variance, coherenceBoost].every(finiteObservation)
      || !(fundamentalHz as number > 0) || (amplitude as number) < 0 || (variance as number) < 0
      || (quality as number) < 0 || (quality as number) > 1 || (coherenceBoost as number) < 0 || (coherenceBoost as number) > 1
      || !['stable', 'elevated', 'peak', 'disturbed'].includes(String(data.resonancePhase))) return null;
  if (measurementKind === 'station_activity') {
    if (coherenceBoost !== 0 || data.frequencyReported !== false || data.frequencyBasis !== 'nominal_reference_not_source_measurement'
        || !finiteObservation(data.activityScore) || data.activityScore < 0 || data.activityScore > 100) return null;
    if (data.stationCount !== undefined && (!finiteObservation(data.stationCount) || data.stationCount <= 0)) return null;
    if (data.stationsMonitored !== undefined && (!finiteObservation(data.stationsMonitored) || data.stationsMonitored <= 0)) return null;
  }
  const harmonics = data.harmonics === undefined ? [] : data.harmonics;
  if (!Array.isArray(harmonics)) return null;
  const parsedHarmonics: SchumannHarmonic[] = [];
  for (const value of harmonics) {
    const harmonic = record(value);
    if (!harmonic || !finiteObservation(harmonic.frequency) || harmonic.frequency <= 0
        || !finiteObservation(harmonic.amplitude) || harmonic.amplitude < 0 || typeof harmonic.name !== 'string') return null;
    parsedHarmonics.push({ frequency: harmonic.frequency, amplitude: harmonic.amplitude, name: harmonic.name });
  }
  const stationSignalsRaw = data.stationSignals === undefined ? [] : data.stationSignals;
  if (!Array.isArray(stationSignalsRaw)) return null;
  const stationSignals: SchumannStationSignal[] = [];
  for (const value of stationSignalsRaw) {
    const station = record(value);
    if (!station || typeof station.source !== 'string' || !station.source.trim() || typeof station.status !== 'string'
        || !finiteObservation(station.activityScore) || station.activityScore < 0 || station.activityScore > 100
        || !freshObservation(station.timestamp, ttl, now)) return null;
    stationSignals.push({
      source: station.source,
      status: station.status,
      activityScore: station.activityScore,
      timestamp: new Date(observationTime(station.timestamp)!),
    });
  }
  return {
    measurementKind, frequencyReported,
    fundamentalHz: fundamentalHz as number, amplitude: amplitude as number, quality: quality as number,
    variance: variance as number, coherenceBoost: coherenceBoost as number,
    timestamp: new Date(observationTime(data.sourceTimestamp)!),
    expiresAt: new Date(Math.min(observationTime(data.sourceTimestamp)!, ...stationSignals.map(station => station.timestamp.getTime())) + ttl),
    sourceId: data.sourceId,
    sourceUrl: typeof data.sourceUrl === 'string' ? data.sourceUrl : undefined,
    resonancePhase: data.resonancePhase as SchumannData['resonancePhase'],
    harmonics: parsedHarmonics, spectrumHistory: [], dataSource: 'LIVE',
    activityScore: finiteObservation(data.activityScore) ? data.activityScore : undefined,
    stationCount: finiteObservation(data.stationCount) ? data.stationCount : undefined,
    stationsMonitored: finiteObservation(data.stationsMonitored) ? data.stationsMonitored : undefined,
    stationSignals,
  };
}

export function validNoaaObservation(value: unknown, now = Date.now()): boolean {
  const data = record(value);
  if (!data || data.truthStatus !== 'live') return false;
  for (const [name, fields] of [
    ['solarWind', ['speed', 'density', 'temperature', 'bz']],
    ['magnetometer', ['hComponent', 'intensity', 'kIndex']],
  ] as const) {
    const part = record(data[name]);
    const current = record(part?.current);
    const provenance = record(part?.provenance);
    if (!current || !provenance || provenance.truthStatus !== 'live'
        || typeof provenance.sourceId !== 'string' || !provenance.sourceId
        || !freshObservation(current.timestamp, EARTH_TELEMETRY_MAX_AGE_MS, now)
        || !freshObservation(provenance.sourceTimestamp, EARTH_TELEMETRY_MAX_AGE_MS, now)
        || !fields.every(field => finiteObservation(current[field])) || !Array.isArray(part?.history)) return false;
  }
  const aurora = record(data.aurora);
  const forecast = record(aurora?.current);
  const alerts = record(data.alerts);
  return !!forecast && observationTime(forecast.timestamp) !== null
    && ['kpIndex', 'probability', 'viewingLatitude'].every(key => finiteObservation(forecast[key]))
    && Array.isArray(aurora?.forecast) && !!alerts
    && ['solarWindAlert', 'magneticStorm', 'auroraAlert'].every(key => typeof alerts[key] === 'boolean');
}

export interface EarthquakeEvent {
  id: string; magnitude: number; location: string; depth: number; timestamp: string;
  latitude: number; longitude: number; significance: number;
}
export interface SeismicObservation { timestamp: string; events: EarthquakeEvent[] }
export function readSeismicObservation(value: unknown, now = Date.now()): SeismicObservation | null {
  const data = record(value);
  if (!data || !freshObservation(data.timestamp, SEISMIC_RECEIPT_MAX_AGE_MS, now) || !Array.isArray(data.events)) return null;
  if (!data.events.every(value => {
    const event = record(value);
    const stamp = observationTime(event?.timestamp);
    return event && typeof event.id === 'string' && typeof event.location === 'string'
      && ['magnitude', 'depth', 'latitude', 'longitude', 'significance'].every(key => finiteObservation(event[key]))
      && stamp !== null && stamp <= now + 5_000;
  })) return null;
  // The wrapper timestamp is the existing USGS fetch receipt, not an event time.
  return { timestamp: data.timestamp as string, events: data.events as EarthquakeEvent[] };
}
