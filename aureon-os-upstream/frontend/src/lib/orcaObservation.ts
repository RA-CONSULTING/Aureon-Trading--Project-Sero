import { evidenceNumber, evidenceRecord, evidenceText, type EvidenceRecord } from './warRoomEvidence';

export type OrcaObservation = {
  available: boolean; reason: string; source: string | null; timestamp: string | null;
  ageSeconds: number | null; receiptId: string | null; data: EvidenceRecord;
};

function epoch(value: unknown): number | null {
  const stamp = typeof value === 'string' ? Date.parse(value)
    : typeof value === 'number' && value > 0 ? (value < 1e11 ? value * 1_000 : value) : NaN;
  return Number.isFinite(stamp) && Math.abs(stamp) <= 8.64e15 ? stamp : null;
}

/** HTTP generation time and registry-created heartbeats are never source evidence. */
export function readOrcaObservation(value: unknown, transportOk: boolean, maxAgeSeconds: number, nowMs = Date.now()): OrcaObservation {
  const raw = evidenceRecord(value);
  const metadata = evidenceRecord(raw.metadata);
  const source = evidenceText(raw.source_id ?? raw.source ?? metadata.source_id ?? metadata.source);
  const receiptId = evidenceText(raw.receipt_id ?? metadata.receipt_id);
  const clocks = [raw.source_timestamp, metadata.source_timestamp, raw.received_at, metadata.received_at]
    .filter((stamp) => stamp !== undefined).map(epoch);
  const sourceClock = epoch(raw.source_timestamp ?? metadata.source_timestamp);
  const timestamp = sourceClock === null ? null : new Date(sourceClock).toISOString();
  const ageSeconds = sourceClock === null ? null : (nowMs - sourceClock) / 1_000;
  const unavailable = (reason: string): OrcaObservation => ({ available: false, reason, source, timestamp, ageSeconds, receiptId, data: {} });
  if (!transportOk) return unavailable('Successful HTTP receipt unavailable');
  if (!source || !receiptId || sourceClock === null) return unavailable('Original source observation and receipt unavailable');
  const statuses = [raw.data_status, metadata.data_status].filter((status) => status !== undefined);
  const generated = [raw.generated_values, metadata.generated_values].filter((flag) => flag !== undefined);
  if (!statuses.length || statuses.some((status) => status !== 'live' && status !== 'observed')
    || !generated.length || generated.some((flag) => flag !== false) || raw.stale === true || metadata.stale === true) {
    return unavailable('Observed-data provenance unavailable');
  }
  const declaredLimit = evidenceNumber(raw.max_age_seconds ?? metadata.max_age_seconds);
  const limit = declaredLimit !== null && declaredLimit > 0 ? Math.min(declaredLimit, maxAgeSeconds) : maxAgeSeconds;
  if (!Number.isFinite(limit) || limit <= 0 || clocks.some((stamp) => stamp === null
    || stamp > nowMs + 5_000 || nowMs - stamp > limit * 1_000)) return unavailable('Source observation is stale or future-dated');
  return { available: true, reason: 'Source observation received', source, timestamp, ageSeconds, receiptId, data: raw };
}
