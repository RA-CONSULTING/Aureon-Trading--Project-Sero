export const USGS_EARTHQUAKE_SOURCE = 'https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/4.5_week.geojson';
export const USGS_SOURCE_MAX_AGE_MS = 5 * 60 * 1000;
export const USGS_POLL_INTERVAL_MS = 60_000;

const record = (value: unknown): Record<string, unknown> | null => value !== null && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : null;
const finite = (value: unknown): value is number => typeof value === 'number' && Number.isFinite(value);
const optionalNumber = (value: unknown): number | null => finite(value) ? value : null;
const text = (value: unknown): string | null => typeof value === 'string' && value.trim() ? value : null;
const timestamp = (value: unknown, now: number): number | null => finite(value) && value > 0 && value <= now + 5_000 ? value : null;

export interface UsgsEvent {
  id: string; magnitude: number | null; location: string | null; depthKm: number | null;
  occurredAt: string; updatedAt: string | null; latitude: number; longitude: number;
}
export interface UsgsObservation {
  source: string; generatedAt: string; receivedAt: string; events: UsgsEvent[];
  returnedCount: number; rejectedCount: number;
}

/** Feed generation, event occurrence and local receipt are different clocks. */
export function readUsgsObservation(value: unknown, receivedAt: number, now = Date.now()): UsgsObservation | null {
  const data = record(value);
  const metadata = record(data?.metadata);
  const generated = timestamp(metadata?.generated, now);
  if (data?.type !== 'FeatureCollection' || metadata?.status !== 200 || generated === null
    || now - generated > USGS_SOURCE_MAX_AGE_MS || timestamp(receivedAt, now) === null
    || now - receivedAt > USGS_SOURCE_MAX_AGE_MS || !Array.isArray(data.features)
    || !Number.isInteger(metadata?.count) || metadata?.count !== data.features.length) return null;
  const events: UsgsEvent[] = [];
  for (const item of data.features) {
    const feature = record(item);
    const properties = record(feature?.properties);
    const geometry = record(feature?.geometry);
    const coordinates = geometry?.coordinates;
    const occurred = timestamp(properties?.time, now);
    const id = text(feature?.id);
    if (feature?.type !== 'Feature' || !id || !properties || occurred === null
      || geometry?.type !== 'Point' || !Array.isArray(coordinates)
      || !finite(coordinates[0]) || Math.abs(coordinates[0]) > 180
      || !finite(coordinates[1]) || Math.abs(coordinates[1]) > 90) continue;
    const updated = timestamp(properties.updated, now);
    events.push({ id, magnitude: optionalNumber(properties.mag), location: text(properties.place),
      depthKm: optionalNumber(coordinates[2]), longitude: coordinates[0], latitude: coordinates[1],
      occurredAt: new Date(occurred).toISOString(), updatedAt: updated === null ? null : new Date(updated).toISOString() });
  }
  if (data.features.length > 0 && events.length === 0) return null;
  return { source: USGS_EARTHQUAKE_SOURCE, generatedAt: new Date(generated).toISOString(),
    receivedAt: new Date(receivedAt).toISOString(),
    events: events.sort((a, b) => Date.parse(b.occurredAt) - Date.parse(a.occurredAt)),
    returnedCount: data.features.length, rejectedCount: data.features.length - events.length };
}
