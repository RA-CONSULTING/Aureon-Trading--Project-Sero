export function consoleNumber(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

export function generatedReportEvidence(value: unknown, now = Date.now()) {
  const report = value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {};
  const source = typeof report.generated_at === 'string' ? report.generated_at : null;
  const timestamp = source ? Date.parse(source) : NaN;
  const valid = Number.isFinite(timestamp) && timestamp > 0;
  const age = valid ? now - timestamp : NaN;
  const current = valid && age >= -5_000 && age <= 300_000;
  return { current, timestamp: valid ? source : null,
    reason: !valid ? 'Generated report timestamp unavailable.' : current ? 'Current generated report; underlying input freshness is not attested.' : 'Generated report is stale. Current status and metrics are unavailable.' };
}

export function consoleReceiptCurrent(receivedAt: number | null, now = Date.now()) {
  return receivedAt !== null && Number.isFinite(receivedAt) && receivedAt > 0 && now - receivedAt >= -5_000 && now - receivedAt <= 30_000;
}
