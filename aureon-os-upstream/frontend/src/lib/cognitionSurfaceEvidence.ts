import type { CognitiveObservation } from '../services/cognitiveReads';

export function record(value: unknown): Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {};
}
export function observationTime(value: unknown): string | null {
  return typeof value === 'number' && Number.isFinite(value) && value > 0 && value < 253402300800
    ? new Date(value * 1000).toISOString() : null;
}
export function observedValue(value: unknown): string {
  if (typeof value === 'number') return Number.isFinite(value)
    ? Number.isInteger(value) ? String(value) : value.toFixed(3) : 'Unavailable';
  if (typeof value === 'boolean') return value ? 'Yes' : 'No';
  return typeof value === 'string' && value.trim() ? value : 'Unavailable';
}
export function observedPercent(value: unknown): string {
  return typeof value === 'number' && Number.isFinite(value) ? `${observedValue(value)}%` : 'Unavailable';
}
export interface SurfaceEvidence {
  current: boolean; historical: boolean; displayable: boolean;
  label: string; reason: string; sourceTime: string | null;
}
/** No receipt/assembly clock can promote a cached producer observation. */
export function surfaceEvidence(value: CognitiveObservation | undefined, nowMs: number, maxAgeSeconds = 300): SurfaceEvidence {
  const sourceTime = observationTime(value?.source_timestamp);
  const missing = (reason: string): SurfaceEvidence => ({ current: false, historical: false,
    displayable: false, label: 'Unavailable', reason, sourceTime });
  if (!value || !sourceTime || !Number.isFinite(nowMs)) return missing('Original producer timestamp unavailable.');
  const age = nowMs / 1000 - value.source_timestamp!;
  if (age < -5) return missing('Producer timestamp is in the future.');
  if (typeof value.source_clock_kind !== 'string' || !['producer_timestamp', 'benchmark_generation',
    'os_process_measurement', 'in_process_bus_measurement'].includes(value.source_clock_kind)) {
    return missing('Original producer clock is not attested.');
  }
  if (value.generated === true || value.generated_values === true || value.simulated === true
    || record(value.provenance).simulation_fallback_allowed === true || value.truth_status === 'test_fixture') {
    return missing('Generated or fixture data is not a current observation.');
  }
  if (value.stale === true && value.historical_available !== true) return missing('Producer marked this observation stale.');
  if (['failed', 'missing', 'unavailable'].includes(value.read_state ?? '')) return missing(value.reason || 'Producer read unavailable.');
  const historical = value.historical_available === true
    && ['recorded_history', 'recorded_benchmark'].includes(value.classification ?? '')
    && ['observed', 'stale'].includes(value.read_state ?? '');
  const limit = value.max_age_seconds;
  const current = value.available === true && value.fresh === true && value.read_state === 'observed'
    && value.truth_status !== 'no_data' && typeof limit === 'number' && Number.isFinite(limit)
    && limit > 0 && limit <= maxAgeSeconds && age <= limit;
  if (historical) return { current: false, historical: true, displayable: true,
    label: value.classification === 'recorded_benchmark' ? 'Recorded benchmark' : 'Recorded history',
    reason: 'Dated recorded evidence; this does not establish current functional health.', sourceTime };
  if (current) return { current: true, historical: false, displayable: true, label: 'Current observation',
    reason: 'Original source clock is within its published age limit.', sourceTime };
  return missing(typeof limit === 'number' && age > limit ? 'Producer observation expired.'
    : value.reason || 'Current source evidence is not available.');
}
export function benchmarkResult(passed: unknown, report: SurfaceEvidence): 'Recorded pass' | 'Recorded fail' | 'Unavailable' {
  return report.historical && typeof passed === 'boolean' ? passed ? 'Recorded pass' : 'Recorded fail' : 'Unavailable';
}
export function brainHistoryRecords(brain: CognitiveObservation | undefined, nowMs: number) {
  const accuracy = record(brain?.accuracy) as CognitiveObservation;
  const knowledge = record(brain?.knowledge) as CognitiveObservation;
  return [
    { name: 'Prediction history', evidence: surfaceEvidence(accuracy, nowMs), rows: [
      ['Predictions', observedValue(accuracy.total_predictions)], ['Validated', observedValue(accuracy.validated)],
      ['Accuracy', observedPercent(accuracy.accuracy_pct)],
    ] },
    { name: 'Knowledge history', evidence: surfaceEvidence(knowledge, nowMs), rows: [
      ['Knowledge entries', observedValue(knowledge.entries)],
    ] },
  ];
}
export function processRowCurrent(process: CognitiveObservation | undefined, row: Record<string, unknown>, nowMs: number): boolean {
  const stamp = row.source_timestamp;
  const observed = row.read_state === 'observed' || (row.read_state === 'absent' && row.pid_running === false && row.identity_verified === false);
  return process?.source_clock_kind === 'os_process_measurement' && surfaceEvidence(process, nowMs, 15).current
    && observed && typeof row.pid_running === 'boolean' && typeof row.identity_verified === 'boolean'
    && !(row.identity_verified === true && row.pid_running !== true) && typeof stamp === 'number'
    && observationTime(stamp) !== null && nowMs / 1000 - stamp >= -5 && nowMs / 1000 - stamp <= 15;
}
export function readFailureMessage(httpStatus: number | null, offline: boolean, error: string | null): string {
  if (httpStatus === 401) return 'Sign in to read this page. Current data is unavailable.';
  if (httpStatus === 403) return 'This account is not permitted to read this page.';
  if (offline) return 'The gateway could not be reached. Current data is unavailable.';
  return error || 'No current response is available.';
}
