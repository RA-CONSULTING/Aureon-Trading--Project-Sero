type RecordValue = Record<string, unknown>;
const record = (value: unknown): RecordValue => value !== null && typeof value === 'object' && !Array.isArray(value) ? value as RecordValue : {};
const text = (value: unknown) => typeof value === 'string' && value.trim().length > 0 && value.length <= 128 ? value : null;
const MAX_AGE_MS = 30_000;
const FIELDS = {
  auris_metrics: ['coherence_score', 'schumann_lock', 'tsv_gain', 'prime_alignment', 'ten_nine_one_concordance'],
  aura_features: ['alpha_theta_ratio', 'hrv_norm', 'gsr_norm', 'prime_concordance_10_9_1', 'calm_index', 'aura_hue_deg'],
} as const;
export type NexusChannel = keyof typeof FIELDS;
export type NexusObservation = {
  available: boolean; reason: string; source: string | null; timestamp: string | null; values: Record<string, number>;
};

function epoch(value: unknown): number | null {
  const result = typeof value === 'string' ? Date.parse(value)
    : typeof value === 'number' && value > 0 ? (value < 1e11 ? value * 1_000 : value) : NaN;
  return Number.isFinite(result) && Math.abs(result) <= 8.64e15 ? result : null;
}

/** A socket receipt is not sufficient evidence of a current observed measurement. */
export function readNexusObservation(value: unknown, channel: NexusChannel, connected: boolean,
  receivedAt: number | null, nowMs = Date.now()): NexusObservation {
  const message = record(value);
  const data = record(message.data);
  const source = text(data.source) ?? text(message.source);
  const unavailable = (reason: string, timestamp: string | null = null): NexusObservation => ({ available: false, reason, source, timestamp, values: {} });
  if (!connected) return unavailable('Research transport disconnected');
  if (message.type !== channel || receivedAt === null || !Number.isFinite(receivedAt)
    || receivedAt > nowMs + 5_000 || nowMs - receivedAt > MAX_AGE_MS) return unavailable('Current channel receipt unavailable');
  const statuses = [message.data_status, data.data_status].filter((status) => status !== undefined);
  const generated = [message.generated_values, data.generated_values].filter((flag) => flag !== undefined);
  if (!source || !statuses.length || statuses.some((status) => status !== 'live' && status !== 'observed')
    || !generated.length || generated.some((flag) => flag !== false) || message.stale === true || data.stale === true) {
    return unavailable('Named source and observed-data provenance unavailable');
  }
  const clocks = [message.source_timestamp, message.ts, data.source_timestamp, data.ts]
    .filter((stamp) => stamp !== undefined).map(epoch);
  if (!clocks.length || clocks.some((stamp) => stamp === null)) return unavailable('Original source timestamp unavailable');
  const timestampMs = Math.min(...clocks as number[]);
  const timestamp = new Date(timestampMs).toISOString();
  if (clocks.some((stamp) => nowMs - stamp! > MAX_AGE_MS || stamp! > nowMs + 5_000)) {
    return unavailable('Source observation is stale or future-dated', timestamp);
  }
  const values: Record<string, number> = {};
  for (const key of FIELDS[channel]) {
    const observed = data[key];
    if (typeof observed === 'number' && Number.isFinite(observed)) values[key] = observed;
  }
  if (!Object.keys(values).length) return unavailable('Finite source readings unavailable', timestamp);
  return { available: true, reason: 'Timestamped source-reported research output', source, timestamp, values };
}
