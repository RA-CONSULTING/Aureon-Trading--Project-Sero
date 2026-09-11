export const NOAA_SOURCE_MAX_AGE_MS = 20 * 60 * 1000;
export const NOAA_REFRESH_MS = 5 * 60 * 1000;
export const NOAA_RESPONSE_MAX_BYTES = 8 * 1024 * 1024;
export const NOAA_REQUEST_TIMEOUT_MS = 10_000;

export type NoaaFeed = 'wind' | 'imf' | 'goes' | 'kp';
interface Metric { key: string; label: string; unit: string; min?: number; max?: number }
interface FeedDefinition { label: string; url: string; kind: string; metrics: Metric[] }

/** Existing NOAA SWPC public products; each product retains its own time_tag. */
export const NOAA_FEEDS: Record<NoaaFeed, FeedDefinition> = {
  wind: {
    label: 'Solar wind plasma', kind: 'Operational observation',
    url: 'https://services.swpc.noaa.gov/json/rtsw/rtsw_wind_1m.json',
    metrics: [
      { key: 'proton_speed', label: 'Speed', unit: 'km/s', min: 0 },
      { key: 'proton_density', label: 'Density', unit: 'protons/cm³', min: 0 },
      { key: 'proton_temperature', label: 'Temperature', unit: 'K', min: 0 },
    ],
  },
  imf: {
    label: 'Interplanetary magnetic field', kind: 'Operational observation',
    url: 'https://services.swpc.noaa.gov/json/rtsw/rtsw_mag_1m.json',
    metrics: [{ key: 'bz_gsm', label: 'Bz (GSM)', unit: 'nT' }],
  },
  goes: {
    label: 'GOES magnetic field', kind: 'Operational observation',
    url: 'https://services.swpc.noaa.gov/json/goes/primary/magnetometers-6-hour.json',
    metrics: [
      { key: 'Hp', label: 'H component', unit: 'nT' },
      { key: 'total', label: 'Total field', unit: 'nT', min: 0 },
    ],
  },
  kp: {
    label: 'Estimated planetary Kp', kind: 'NOAA provider estimate',
    url: 'https://services.swpc.noaa.gov/json/planetary_k_index_1m.json',
    metrics: [{ key: 'estimated_kp', label: 'Estimated Kp', unit: '', min: 0, max: 9 }],
  },
};

export const NOAA_FEED_IDS = Object.keys(NOAA_FEEDS) as NoaaFeed[];
export interface NoaaSample { source: string; observedAt: string; values: Record<string, number | null> }
export interface NoaaReceipt {
  feed: NoaaFeed; status: 'loading' | 'observed' | 'unavailable';
  receivedAt: number | null; samples: NoaaSample[]; reason: string;
}
const record = (value: unknown): Record<string, unknown> | null =>
  value !== null && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : null;

function sourceTime(value: unknown): number | null {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}/.test(value)) return null;
  const stamp = Date.parse(/(?:Z|[+-]\d\d:\d\d)$/i.test(value) ? value : `${value}Z`);
  return Number.isFinite(stamp) ? stamp : null;
}

export function emptyNoaaReceipt(feed: NoaaFeed, loading = false, reason = 'NOAA source unavailable'): NoaaReceipt {
  return { feed, status: loading ? 'loading' : 'unavailable', receivedAt: null, samples: [], reason };
}

export function readNoaaFeed(feed: NoaaFeed, payload: unknown, receivedAt: number, now = receivedAt): NoaaReceipt {
  if (!Array.isArray(payload) || !Number.isFinite(receivedAt) || receivedAt > now + 5_000) {
    return emptyNoaaReceipt(feed, false, 'Malformed NOAA response or receipt');
  }
  const samples: NoaaSample[] = [];
  for (const value of payload) {
    const row = record(value);
    if (!row) continue;
    const stamp = sourceTime(row.time_tag);
    if (stamp === null || stamp > now + 5_000) continue;
    if ((feed === 'wind' || feed === 'imf') && row.active !== true) continue;
    if (feed === 'goes' && row.arcjet_flag !== false) continue;
    const source = feed === 'kp' ? 'NOAA SWPC planetary Kp estimate'
      : feed === 'goes' && typeof row.satellite === 'number' && Number.isInteger(row.satellite) && row.satellite > 0
        ? `NOAA GOES-${row.satellite}`
        : typeof row.source === 'string' ? row.source.trim() : '';
    if (!source || (feed === 'goes' && !source.startsWith('NOAA GOES-'))) continue;
    const values: Record<string, number | null> = {};
    for (const metric of NOAA_FEEDS[feed].metrics) {
      const v = row[metric.key];
      values[metric.key] = typeof v === 'number' && Number.isFinite(v)
        && v !== -9999 && v !== -99999
        && (metric.min === undefined || v >= metric.min) && (metric.max === undefined || v <= metric.max) ? v : null;
    }
    if (!Object.values(values).some(v => v !== null)) continue;
    samples.push({ source, observedAt: new Date(stamp).toISOString(), values });
  }
  samples.sort((a, b) => Date.parse(a.observedAt) - Date.parse(b.observedAt));
  if (!samples.length) return emptyNoaaReceipt(feed, false, 'No qualified timestamped NOAA readings');
  return { feed, status: 'observed', receivedAt, samples: samples.slice(-60), reason: 'NOAA public source response' };
}

export function noaaFeedView(receipt: NoaaReceipt, now = Date.now()) {
  const latest = receipt.samples.at(-1) ?? null;
  const sourceAt = latest ? sourceTime(latest.observedAt) : null;
  const ageMs = sourceAt === null ? null : now - sourceAt;
  const available = receipt.status === 'observed' && receipt.receivedAt !== null
    && now - receipt.receivedAt >= -5_000 && now - receipt.receivedAt <= NOAA_SOURCE_MAX_AGE_MS
    && ageMs !== null && ageMs >= -5_000 && ageMs <= NOAA_SOURCE_MAX_AGE_MS;
  return {
    available, status: available ? 'fresh' : receipt.status === 'loading' ? 'loading' : latest ? 'stale' : 'unavailable',
    current: available ? latest : null, sourceAt: latest?.observedAt ?? null, ageMs,
    reason: available ? 'Original NOAA source time is current'
      : latest ? 'NOAA source or successful receipt has expired' : receipt.reason,
  };
}
