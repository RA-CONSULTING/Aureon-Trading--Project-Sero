import { generatedReportEvidence } from './generatedConsoleEvidence';

export function recordedReportEvidence(value: unknown, now = Date.now()) {
  const report = value !== null && typeof value === 'object' && !Array.isArray(value)
    ? value as Record<string, unknown> : null;
  const raw = report?.generated_at ?? report?.snapshot_date;
  const text = typeof raw === 'string' ? raw : null;
  const stamp = text && /^\d{4}-\d{2}-\d{2}(?:$|T| )/.test(text) ? Date.parse(text) : NaN;
  const calendar = text?.slice(0, 10);
  const calendarTime = calendar ? Date.parse(`${calendar}T00:00:00Z`) : NaN;
  const valid = Number.isFinite(stamp) && stamp > 0 && stamp <= now + 5_000
    && Number.isFinite(calendarTime) && new Date(calendarTime).toISOString().slice(0, 10) === calendar;
  return {
    current: valid, timestamp: valid ? text : null,
    reason: valid ? 'Recorded report. Historical definitions and counts do not establish current runtime health.'
      : 'Recorded report unavailable: a valid original date, no later than the current time, is required.',
  };
}

export function reportBoundaryEvidence(value: unknown, scope: 'current' | 'recorded' = 'current', now = Date.now()) {
  return scope === 'recorded' ? recordedReportEvidence(value, now) : generatedReportEvidence(value, now);
}

export function recordedNumber(value: unknown, suffix = ''): string {
  return typeof value === 'number' && Number.isFinite(value) && value >= 0 ? `${value.toLocaleString()}${suffix}` : 'Unavailable';
}

export function recordedArrayCount(value: unknown): string {
  return Array.isArray(value) ? value.length.toLocaleString() : 'Unavailable';
}

export function recordedBoolean(value: unknown): 'true' | 'false' | 'Unavailable' {
  return value === true ? 'true' : value === false ? 'false' : 'Unavailable';
}

export function recordedContractCheck(containsValue: unknown): 'recorded clear' | 'recorded review' | 'unavailable' {
  return containsValue === false ? 'recorded clear' : containsValue === true ? 'recorded review' : 'unavailable';
}
