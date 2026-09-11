import { EARTH_TELEMETRY_MAX_AGE_MS, type SchumannData } from './earthObservationEvidence';

export const researchNumber = (value: number | null | undefined, digits = 3) =>
  value === null || value === undefined || !Number.isFinite(value) ? '—' : value.toLocaleString(undefined, { maximumFractionDigits: digits });
export const researchAge = (ageMs: number | null) => ageMs === null ? 'unavailable' : `${Math.max(0, ageMs / 60000).toFixed(1)} min`;

/** A station activity score never establishes a measured frequency or calibrated spectrum. */
export function earthGlassObservation(data: SchumannData | null, nowMs = Date.now()) {
  const stamp = data?.timestamp.getTime();
  const deadline = data?.expiresAt?.getTime() ?? (stamp === undefined ? NaN : stamp + EARTH_TELEMETRY_MAX_AGE_MS);
  const available = stamp !== undefined && Number.isFinite(stamp) && stamp <= nowMs + 5000
    && nowMs - stamp <= EARTH_TELEMETRY_MAX_AGE_MS && Number.isFinite(deadline) && deadline > nowMs;
  const observation = available ? data : null;
  const frequency = observation?.measurementKind === 'frequency' && observation.frequencyReported === true
    && Number.isFinite(observation.fundamentalHz) && observation.fundamentalHz > 0 ? observation.fundamentalHz : null;
  return { observation, available, frequency, expiresAtMs: Number.isFinite(deadline) ? deadline : null,
    harmonics: frequency === null ? [] : observation?.harmonics ?? [],
    sourceAgeMs: stamp === undefined || !Number.isFinite(stamp) ? null : nowMs - stamp };
}
