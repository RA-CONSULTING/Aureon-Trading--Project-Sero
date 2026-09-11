import { evidenceNumber, evidenceRecord, evidenceText, type EvidenceRecord } from './warRoomEvidence';

export type ProviderObservation = {
  available: boolean; reason: string; source: string | null; timestamp: number | null;
  timestampKind: string | null; receivedAt: number | null;
  ageSeconds: number | null; rows: EvidenceRecord[]; count: number | null; inventoryComplete: boolean | null;
};

// Date can represent at most 8.64e15 milliseconds. Keep even unavailable
// metadata renderable: a finite JSON number is not necessarily a valid date.
const epochSeconds = (value: unknown): number | null => {
  const timestamp = evidenceNumber(value);
  return timestamp !== null && timestamp > 0 && timestamp <= 8_640_000_000_000 ? timestamp : null;
};

/** Receipt time and provider observation time remain separate from analysis ticks. */
export function readProviderObservation(value: unknown, connected: boolean, nowMs = Date.now()): ProviderObservation {
  const raw = evidenceRecord(value);
  const source = evidenceText(raw.source);
  const timestamp = epochSeconds(raw.source_timestamp);
  const receivedAt = epochSeconds(raw.received_at);
  const timestampKind = evidenceText(raw.source_timestamp_kind);
  const ageSeconds = timestamp === null ? null : nowMs / 1_000 - timestamp;
  const limit = Math.min(300, Math.max(1, evidenceNumber(raw.max_age_seconds) ?? 300));
  const unavailable = (reason: string): ProviderObservation => ({ available: false, reason, source,
    timestamp, timestampKind, receivedAt, ageSeconds, rows: [], count: null, inventoryComplete: null });
  if (!connected) return unavailable('Runtime transport unavailable');
  if (raw.status !== 'observed' || raw.generated_values !== false || !source) {
    return unavailable(evidenceText(raw.reason)?.replaceAll('_', ' ') ?? 'Provider receipt unavailable');
  }
  if (timestamp === null || timestamp <= 0 || receivedAt === null || receivedAt <= 0 || ageSeconds! < -5 || ageSeconds! > limit
      || receivedAt > nowMs / 1_000 + 5 || nowMs / 1_000 - receivedAt > limit) {
    return unavailable('Provider receipt is stale or has no valid source timestamp');
  }
  if (!Array.isArray(raw.rows)) return unavailable('Provider rows unavailable');
  const rows = raw.rows.map(evidenceRecord);
  if (rows.some((row) => evidenceNumber(row.source_timestamp) !== timestamp || evidenceNumber(row.received_at) !== receivedAt)) {
    return unavailable('Provider row provenance is incomplete');
  }
  const count = evidenceNumber(raw.observed_count);
  if (count === null || count < 0 || !Number.isInteger(count) || count !== rows.length) {
    return unavailable('Provider inventory count is incomplete');
  }
  if (count === 0 && raw.inventory_complete !== true) return unavailable('Provider inventory is incomplete');
  return { available: true, reason: 'Fresh provider receipt', source, timestamp, timestampKind, receivedAt, ageSeconds, rows, count,
    inventoryComplete: typeof raw.inventory_complete === 'boolean' ? raw.inventory_complete : null };
}
