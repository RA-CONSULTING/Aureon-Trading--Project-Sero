export const RESONANCE_ONE_SOURCE = 'https://resonanceone.app/api/now';
export const RESONANCE_ONE_DOCUMENTATION = 'https://resonanceone.app/ai';
export const RESONANCE_ONE_POLL_MS = 5 * 60_000;
export const RESONANCE_ONE_UPDATE_MAX_AGE_MS = 90 * 60_000;
export const RESONANCE_ONE_WINDOW_MAX_AGE_MS = 135 * 60_000;

const record = (value: unknown): Record<string, unknown> | null => value !== null && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : null;
const text = (value: unknown): string | null => typeof value === 'string' && value.trim() && value.length <= 500 ? value.trim() : null;
const range = (value: unknown, maximum = 100): number | null => typeof value === 'number' && Number.isFinite(value) && value >= 0 && value <= maximum ? value : null;

function sourceTime(value: unknown, now: number): number | null {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/.test(value)) return null;
  const calendar = value.slice(0, 10);
  const day = Date.parse(`${calendar}T00:00:00Z`);
  const time = Date.parse(value);
  return Number.isFinite(day) && new Date(day).toISOString().slice(0, 10) === calendar
    && Number.isFinite(time) && time > 0 && time <= now + 5_000 ? time : null;
}

export interface ResonanceOneObservation {
  source: string; dataSource: string; updatedAt: string; windowStart: string; windowEnd: string; receivedAt: string;
  activityIndex: number; schumannIndex: number | null; kpIndex: number | null; solarFlareIndex: number | null;
  localInterference: boolean | null; dataQuality: string | null; confidenceScore: number | null;
  weighting: { schumann: number; kp: number; solar: number } | null;
  attribution: { schumann: string | null; kp: string | null; solar: string | null };
}

/** An hourly third-party composite, never an attestation of direct station measurements. */
export function readResonanceOneObservation(value: unknown, receivedAt: number, now = Date.now()): ResonanceOneObservation | null {
  const data = record(value);
  const window = record(data?.observation_window);
  const updated = sourceTime(data?.updated_at, now);
  const start = sourceTime(window?.start, now);
  const end = sourceTime(window?.end, now);
  const activity = range(data?.activity_index);
  const source = text(data?.data_source);
  if (!data || updated === null || start === null || end === null || activity === null || !source
    || start >= end || end - start > 90 * 60_000 || end > updated
    || now - updated > RESONANCE_ONE_UPDATE_MAX_AGE_MS || now - end > RESONANCE_ONE_WINDOW_MAX_AGE_MS
    || !Number.isFinite(receivedAt) || receivedAt <= 0 || receivedAt > now + 5_000
    || now - receivedAt > RESONANCE_ONE_UPDATE_MAX_AGE_MS) return null;
  const weights = record(data.weighting);
  const schumann = range(weights?.schumann_pct);
  const kp = range(weights?.kp_pct);
  const solar = range(weights?.solar_pct);
  const weighting = schumann !== null && kp !== null && solar !== null && Math.abs(schumann + kp + solar - 100) < 0.001
    ? { schumann, kp, solar } : null;
  const attribution = record(data.attribution);
  return {
    source: RESONANCE_ONE_SOURCE, dataSource: source, activityIndex: activity,
    updatedAt: new Date(updated).toISOString(), windowStart: new Date(start).toISOString(), windowEnd: new Date(end).toISOString(), receivedAt: new Date(receivedAt).toISOString(),
    schumannIndex: range(data.schumann_index), kpIndex: range(data.kp_index, 9), solarFlareIndex: range(data.solar_flare_index),
    localInterference: typeof data.local_interference === 'boolean' ? data.local_interference : null,
    dataQuality: text(data.data_quality), confidenceScore: range(data.confidence_score), weighting,
    attribution: { schumann: text(attribution?.schumann), kp: text(attribution?.kp), solar: text(attribution?.solar) },
  };
}

export function schumannContributionStatus(observation: ResonanceOneObservation): 'reported' | 'held' | 'unavailable' {
  if (observation.schumannIndex === null || observation.localInterference === null) return 'unavailable';
  return observation.localInterference ? 'held' : 'reported';
}
