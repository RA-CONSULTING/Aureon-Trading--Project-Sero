import { consoleNumber, consoleReceiptCurrent } from './generatedConsoleEvidence';

export function consoleDisplayValue(value: unknown): string {
  const number = consoleNumber(value);
  if (number !== null) return number.toLocaleString();
  return typeof value === 'string' && value.trim() ? value : 'Unavailable';
}

export function consoleReportedPercent(value: unknown): number | null {
  const number = consoleNumber(value);
  return number !== null && number >= 0 && number <= 1 ? number * 100 : null;
}

export function consoleControlAvailable(receivedAt: number | null, busy: boolean, now = Date.now()): boolean {
  return !busy && consoleReceiptCurrent(receivedAt, now);
}

/** Only the selected proof's own transport and original generation time qualify it. */
export function goldRuntimeObservation(value: unknown, transportCurrent: boolean, now = Date.now()) {
  const proof = value && typeof value === 'object' && !Array.isArray(value)
    ? value as Record<string, unknown> : {};
  const generatedAt = typeof proof.generated_at === 'string' ? Date.parse(proof.generated_at) : NaN;
  const elapsed = now - generatedAt;
  const current = transportCurrent && Number.isFinite(generatedAt) && generatedAt > 0
    && elapsed >= -5_000 && elapsed <= 30_000;
  // Gold's producer reports age at proof generation; this is an age estimate,
  // not an independently published quote timestamp or execution clearance.
  const candidate = proof.fresh_gold_data_source;
  const source = candidate && typeof candidate === 'object' && !Array.isArray(candidate)
    ? candidate as Record<string, unknown> : {};
  const recordedAge = consoleNumber(source.age_sec);
  const ageSeconds = current && recordedAge !== null && recordedAge >= 0
    ? recordedAge + Math.max(0, elapsed) / 1000 : null;
  const price = consoleNumber(source.reference_price ?? source.price);
  const sourceCurrent = current && source.ready === true && ageSeconds !== null && ageSeconds <= 180
    && price !== null && price > 0 && typeof source.source === 'string' && source.source.trim().length > 0;
  return { current, proof: current ? proof : {}, source: sourceCurrent ? source : {},
    sourceCurrent, ageSeconds: sourceCurrent ? ageSeconds : null };
}
