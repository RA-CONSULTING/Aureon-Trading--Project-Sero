export interface ClosedPositionWarMetrics {
  status: 'observed' | 'unavailable';
  reason: string;
  count: number;
  netPnL: number | null;
  winningTrades: number;
  totalTrades: number;
  winRate: number | null;
}

const record = (value: unknown): Record<string, unknown> =>
  value !== null && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {};

const text = (value: unknown): string | null => typeof value === 'string' && value.trim() ? value.trim() : null;

const finiteAmount = (value: unknown): number | null => {
  if (typeof value === 'number' && Number.isFinite(value)) return value;
  if (typeof value === 'string' && value.trim()) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
};

const unavailable = (reason: string): ClosedPositionWarMetrics => ({
  status: 'unavailable', reason, count: 0, netPnL: null, winningTrades: 0, totalTrades: 0, winRate: null,
});

/** War Room P&L must come from the local backend's tenant-scoped receipt, never browser-direct table reads. */
export function readClosedPositionWarMetrics(payload: unknown): ClosedPositionWarMetrics {
  const root = record(payload);
  if (root.available !== true) {
    return unavailable(text(root.reason) ?? 'Tenant-scoped closed-position analytics backend is unavailable.');
  }
  if (root.tenant_scope !== 'user_id') {
    return unavailable('Closed-position analytics response is missing tenant user_id scope.');
  }
  const records = root.records;
  const count = root.count;
  if (!Array.isArray(records) || !Number.isInteger(count) || count !== records.length) {
    return unavailable('Closed-position analytics response did not include a complete exact result.');
  }
  if (records.length === 0) {
    return { status: 'observed', reason: 'Tenant-scoped backend returned 0 closed positions for today.', count: 0, netPnL: 0, winningTrades: 0, totalTrades: 0, winRate: 0 };
  }
  let netPnL = 0;
  let winningTrades = 0;
  for (const value of records) {
    const row = record(value);
    const pnl = finiteAmount(row.realized_pnl);
    if (row.status !== 'closed' || row.generated_values !== false || pnl === null) {
      return unavailable('Closed-position analytics response included an invalid or generated closed-position row.');
    }
    netPnL += pnl;
    if (pnl > 0) winningTrades += 1;
  }
  return {
    status: 'observed',
    reason: text(root.reason) ?? 'Tenant-scoped closed-position analytics observed.',
    count: records.length,
    netPnL,
    winningTrades,
    totalTrades: records.length,
    winRate: winningTrades / records.length * 100,
  };
}
