export const ANALYTICS_MAX_AGE_MS = 300_000;
export type AnalyticsRange = '24h' | '7d' | '30d' | 'all';

/** Scope one local query to its observed account; same-account token refreshes preserve history. */
export function createAnalyticsAccountScope() {
  let accountId: string | null | undefined;
  let epoch = 0;
  let active: AbortController | null = null;
  return {
    observeAccount(next: string | null) {
      if (accountId === next) return false;
      accountId = next;
      epoch++;
      active?.abort();
      active = null;
      return true;
    },
    begin() {
      active?.abort();
      active = new AbortController();
      return { epoch, controller: active };
    },
    current(ticket: { epoch: number; controller: AbortController }) {
      return ticket.epoch === epoch && ticket.controller === active && !ticket.controller.signal.aborted;
    },
    stop() { epoch++; active?.abort(); active = null; },
  };
}

export interface AnalyticsReceipt {
  range: AnalyticsRange;
  receivedAt: number;
  data: unknown;
  error: unknown;
  count: number | null;
  status: number;
  available?: boolean;
  reason?: unknown;
}

interface ClosedPosition {
  id: string;
  symbol: string;
  exchange: string;
  side: string;
  openedAt: number;
  closedAt: number;
  sourceAt: number;
  source: string;
  pnl: number;
  currency: string | null;
  entryPrice: number | null;
  exitPrice: number | null;
  closeReason: string | null;
}

export interface AnalyticsEvidence {
  status: 'loading' | 'unavailable' | 'empty' | 'observed';
  reason: string;
  receivedAt: number | null;
  count: number | null;
  positions: ClosedPosition[];
  currency: string | null;
  metrics: {
    wins: number;
    losses: number;
    breakeven: number;
    winRate: number;
    avgDurationMinutes: number;
    totalPnL: number | null;
    avgPnL: number | null;
    avgWin: number | null;
    avgLoss: number | null;
    profitFactor: number | null;
  } | null;
  timeSeries: { date: string; pnl: number; cumulativePnL: number; trades: number }[];
  symbols: { symbol: string; exchange: string; trades: number; winRate: number; pnl: number | null }[];
  best: ClosedPosition | null;
  worst: ClosedPosition | null;
}

const record = (value: unknown): Record<string, unknown> =>
  value !== null && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {};
const finite = (value: unknown): number | null => typeof value === 'number' && Number.isFinite(value) ? value : null;
const text = (value: unknown): string | null => typeof value === 'string' && value.trim() ? value.trim() : null;
const timestamp = (value: unknown): number | null => {
  const parsed = typeof value === 'string' ? Date.parse(value) : NaN;
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
};

export function analyticsRangeStart(range: AnalyticsRange, now: number): string {
  const days = { '24h': 1, '7d': 7, '30d': 30 };
  return new Date(range === 'all' ? 0 : now - days[range] * 86_400_000).toISOString();
}

/** A fresh query attests the visible historical records, not a current provider/fee ledger. */
export function readTradingAnalytics(
  receipt: AnalyticsReceipt | null,
  range: AnalyticsRange,
  now = Date.now(),
): AnalyticsEvidence {
  const receivedAt = receipt && Number.isFinite(receipt.receivedAt) && receipt.receivedAt > 0 &&
    Number.isFinite(new Date(receipt.receivedAt).getTime()) ? receipt.receivedAt : null;
  const unavailable = (reason: string, status: AnalyticsEvidence['status'] = 'unavailable'): AnalyticsEvidence => ({
    status, reason, receivedAt, count: null, positions: [], currency: null,
    metrics: null, timeSeries: [], symbols: [], best: null, worst: null,
  });
  if (!receipt || receipt.range !== range) return unavailable('Loading closed-position records…', 'loading');
  if (receipt.available === false) return unavailable(text(receipt.reason) ?? text(receipt.error) ?? 'Closed-position analytics backend is unavailable.');
  if (receipt.error || !Number.isInteger(receipt.status) || receipt.status < 200 || receipt.status >= 300) return unavailable('Closed-position query failed. Performance is unavailable.');
  if (receivedAt === null || now - receipt.receivedAt < -5_000 || now - receipt.receivedAt > ANALYTICS_MAX_AGE_MS) {
    return { ...unavailable('Query receipt is stale. Select a time range to request current records.'), receivedAt: null };
  }
  if (!Array.isArray(receipt.data) || !Number.isInteger(receipt.count) || receipt.count !== receipt.data.length) {
    return unavailable('The query did not return a verified complete result. Performance is unavailable.');
  }
  if (receipt.count === 0) return { ...unavailable('0 closed-position records returned for this account view and period. Performance ratios are unavailable.', 'empty'), count: 0 };

  const positions: ClosedPosition[] = [];
  const ids = new Set<string>();
  for (const value of receipt.data) {
    const row = record(value);
    const id = text(row.id), symbol = text(row.symbol), exchange = text(row.exchange), side = text(row.side);
    const source = text(row.source_id), sourceAt = timestamp(row.source_timestamp);
    const openedAt = timestamp(row.opened_at), closedAt = timestamp(row.closed_at), pnl = finite(row.realized_pnl);
    if (!id || ids.has(id) || !symbol || !exchange || !side || !source || sourceAt === null || openedAt === null || closedAt === null ||
      closedAt < openedAt || Math.max(openedAt, closedAt, sourceAt) > receipt.receivedAt + 5_000 || pnl === null ||
      row.status !== 'closed' || row.generated_values !== false || !['live', 'real_derived'].includes(String(row.truth_status))) {
      return unavailable('Closed-position records contain missing, generated or invalid source/close evidence. Performance is unavailable.');
    }
    ids.add(id);
    positions.push({ id, symbol, exchange, side, source, sourceAt, openedAt, closedAt, pnl,
      // The current table has no P&L denomination. Never infer USD from a symbol or account balance.
      currency: text(row.pnl_currency), entryPrice: finite(row.entry_price), exitPrice: finite(row.exit_price), closeReason: text(row.close_reason) });
  }
  positions.sort((a, b) => a.closedAt - b.closedAt);
  const wins = positions.filter(position => position.pnl > 0);
  const losses = positions.filter(position => position.pnl < 0);
  const commonCurrency = positions[0].currency;
  const currency = commonCurrency && positions.every(position => position.currency === commonCurrency) ? commonCurrency : null;
  const sum = (items: ClosedPosition[]) => items.reduce((total, position) => total + position.pnl, 0);
  const total = sum(positions), winTotal = sum(wins), lossTotal = Math.abs(sum(losses));
  const financialsAvailable = currency !== null && [total, winTotal, lossTotal].every(Number.isFinite);
  const safeRatio = (numerator: number, denominator: number): number | null => denominator > 0 && Number.isFinite(numerator / denominator) ? numerator / denominator : null;
  const daily = new Map<string, { pnl: number; trades: number }>();
  const symbols = new Map<string, { symbol: string; exchange: string; pnl: number; trades: number; wins: number }>();
  positions.forEach(position => {
    const date = new Date(position.closedAt).toISOString().slice(0, 10);
    const day = daily.get(date) ?? { pnl: 0, trades: 0 };
    daily.set(date, { pnl: day.pnl + position.pnl, trades: day.trades + 1 });
    const key = `${position.exchange}:${position.symbol}`;
    const symbol = symbols.get(key) ?? { symbol: position.symbol, exchange: position.exchange, pnl: 0, trades: 0, wins: 0 };
    symbols.set(key, { ...symbol, pnl: symbol.pnl + position.pnl, trades: symbol.trades + 1, wins: symbol.wins + (position.pnl > 0 ? 1 : 0) });
  });
  let cumulativePnL = 0;
  const timeSeries = financialsAvailable ? Array.from(daily, ([date, day]) => ({ date, ...day, cumulativePnL: cumulativePnL += day.pnl })) : [];
  if (timeSeries.some(day => !Number.isFinite(day.pnl) || !Number.isFinite(day.cumulativePnL))) {
    return unavailable('Recorded amounts exceed the supported numeric range. Performance is unavailable.');
  }
  const ranked = financialsAvailable ? [...positions].sort((a, b) => b.pnl - a.pnl) : [];
  return {
    status: 'observed', reason: 'Historical records from trading_positions. Provider fills, fees and completeness across providers are not attested by this table.',
    receivedAt: receipt.receivedAt, count: positions.length, positions, currency: financialsAvailable ? currency : null,
    metrics: {
      wins: wins.length, losses: losses.length, breakeven: positions.length - wins.length - losses.length,
      winRate: wins.length / positions.length * 100,
      avgDurationMinutes: positions.reduce((total, position) => total + (position.closedAt - position.openedAt) / 60_000, 0) / positions.length,
      totalPnL: financialsAvailable ? total : null, avgPnL: financialsAvailable ? total / positions.length : null,
      avgWin: financialsAvailable ? safeRatio(winTotal, wins.length) : null,
      avgLoss: financialsAvailable ? safeRatio(lossTotal, losses.length) : null,
      profitFactor: financialsAvailable ? safeRatio(winTotal, lossTotal) : null,
    },
    timeSeries, symbols: Array.from(symbols.values(), symbol => ({ ...symbol, winRate: symbol.wins / symbol.trades * 100,
      pnl: financialsAvailable && Number.isFinite(symbol.pnl) ? symbol.pnl : null })),
    best: ranked[0] ?? null, worst: ranked[ranked.length - 1] ?? null,
  };
}
