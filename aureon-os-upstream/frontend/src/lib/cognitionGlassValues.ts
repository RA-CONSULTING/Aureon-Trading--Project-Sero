/** Display model ratios only when their source actually reports a value in range. */
export function modelPercent(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) && value >= 0 && value <= 1 ? Math.round(value * 100) : null;
}
export function modelPercentLabel(value: unknown): string {
  const percent = modelPercent(value);
  return percent === null ? 'Unavailable' : `${percent}%`;
}
export function currentModelSignal(value: unknown, status: unknown): number | null {
  return ['live', 'real_observed', 'real_derived'].includes(String(status))
    && typeof value === 'number' && Number.isFinite(value) ? value : null;
}
export function reportedModelStage(value: unknown, count: number): number | null {
  return typeof value === 'number' && Number.isInteger(value) && value >= 0 && value <= count ? value : null;
}
export function reportedWorkOutcome(value: { blocked?: unknown; dry_run?: unknown; executed?: unknown } | null | undefined): string {
  if (value?.blocked === true) return 'Reported blocked';
  if (value?.dry_run === true) return 'Reported dry-run';
  if (value?.executed === true) return 'Producer reports executed';
  return 'Outcome unreported';
}
