export interface BacktestConfig {
  symbol: string; startDate: string; endDate: string; initialCapital: number;
  tradeSize: number; stopLoss: number; takeProfit: number;
  strategy: 'momentum_next_open_v1'; intervalMinutes: 60 | 1440;
  lookbackPeriods: number; feeBps: number; slippageBps: number;
}

export interface BacktestResults {
  totalTrades: number;
  winRate: number | null; totalReturn: number | null; sharpeRatio: number | null;
  maxDrawdown: number | null; profitFactor: number | null; avgWin: number | null; avgLoss: number | null;
  equityCurve: Array<{ date: string; equity: number }>;
  trades: Array<Record<string, unknown>>;
}

export interface BacktestReport {
  schema: 'aureon.backtest-report.v1';
  mode: 'historical_replay';
  config: BacktestConfig;
  receivedAt: number;
  source: string;
  sourceAt: number;
  fetchedAt: number | null;
  datasetHash: string | null;
  currency: string | null;
  metricUnits: Record<string, string>;
  requestId: string | null;
  accountScope: string | null;
  assumptions: string[];
  results: BacktestResults;
}

/** An auth reset cancels both capability reads and replay requests, including late resolutions. */
export function createBacktestScope() {
  let epoch = 0;
  const requests = new Set<AbortController>();
  return {
    begin() { const controller = new AbortController(); requests.add(controller); return { controller, epoch }; },
    current(ticket: { controller: AbortController; epoch: number }) { return epoch === ticket.epoch && !ticket.controller.signal.aborted; },
    finish(ticket: { controller: AbortController }) { requests.delete(ticket.controller); },
    reset() { epoch++; requests.forEach(controller => controller.abort()); requests.clear(); },
  };
}

export const BACKTEST_CAPABILITY_MAX_AGE_MS = 60_000;
const object = (value: unknown): Record<string, unknown> | null =>
  typeof value === 'object' && value !== null && !Array.isArray(value) ? value as Record<string, unknown> : null;
const finite = (value: unknown): number | null => typeof value === 'number' && Number.isFinite(value) ? value : null;

/** GET is a capability read, never a replay submission. Missing metadata cannot enable Run. */
export function backtestServiceAvailable(payload: unknown, receivedAt: number | null, now = Date.now()): boolean {
  const data = object(payload);
  return receivedAt !== null && Number.isFinite(receivedAt) && now >= receivedAt
    && now - receivedAt <= BACKTEST_CAPABILITY_MAX_AGE_MS && data?.available === true
    && data.service === 'aureon-historical-backtest' && data.execution_mode === 'historical_replay'
    && data.source_backed === true && data.executes_orders === false
    && typeof data.account_scope === 'string' && /^[a-f0-9]{64}$/.test(data.account_scope);
}

/** Preserve the request and original dataset clock; HTTP receipt time is not dataset freshness. */
export function readBacktestReport(payload: unknown, config: BacktestConfig, receivedAt = Date.now(), binding?: { requestId: string; accountScope: string }): BacktestReport {
  const data = object(payload);
  const raw = object(data?.results);
  if (!raw) throw new Error('The backtest service returned no result records.');
  if (binding && (data?.request_id !== binding.requestId || data?.account_scope !== binding.accountScope
    || data?.schema !== 'aureon.backtest-result.v1' || data?.service !== 'aureon-historical-backtest')) {
    throw new Error('The replay response does not match this request and authenticated account.');
  }
  const echoedConfig = object(data?.config) ?? object(raw.config);
  if (!echoedConfig || Object.entries(config).some(([key, value]) => echoedConfig[key] !== value)) {
    throw new Error('The service result is not bound to the exact submitted configuration.');
  }
  const provenance = object(data?.provenance) ?? object(raw.provenance);
  if (provenance?.generated !== false || provenance?.execution_mode !== 'historical_replay') {
    throw new Error('Historical dataset provenance is unavailable. Provider-backed replay data is required.');
  }
  const source = typeof provenance.source === 'string' ? provenance.source.trim() : '';
  const sourceAt = typeof provenance.source_at === 'string' ? Date.parse(provenance.source_at) : NaN;
  if (!source || !Number.isFinite(sourceAt) || sourceAt > receivedAt) {
    throw new Error('The historical dataset source or original timestamp is missing or invalid.');
  }
  const fetched = typeof provenance.fetched_at === 'string' ? Date.parse(provenance.fetched_at) : NaN;
  const fetchedAt = Number.isFinite(fetched) && sourceAt <= fetched && fetched <= receivedAt ? fetched : null;
  const datasetHash = typeof provenance.dataset_sha256 === 'string' && /^[a-f0-9]{64}$/.test(provenance.dataset_sha256) ? provenance.dataset_sha256 : null;
  if (binding && (fetchedAt === null || datasetHash === null)) throw new Error('The replay dataset receipt or content hash is missing or invalid.');
  const totalTrades = finite(raw.totalTrades);
  if (totalTrades === null || !Number.isInteger(totalTrades) || totalTrades < 0 || !Array.isArray(raw.trades)
    || raw.trades.length !== totalTrades || raw.trades.some(trade => object(trade) === null)) {
    throw new Error('The reported trade count does not match complete result records.');
  }
  if (!Array.isArray(raw.equityCurve) || raw.equityCurve.length === 0) {
    throw new Error('A dated historical equity curve is unavailable.');
  }
  let previous = -Infinity;
  const start = Date.parse(config.startDate);
  const end = Date.parse(config.endDate) + 86_400_000;
  const equityCurve = raw.equityCurve.map(value => {
    const point = object(value);
    const date = typeof point?.date === 'string' ? point.date : '';
    const timestamp = Date.parse(date);
    const equity = finite(point?.equity);
    if (!Number.isFinite(timestamp) || timestamp < previous || timestamp < start || timestamp > end || equity === null) {
      throw new Error('The equity curve contains invalid dates, ordering, range or amounts.');
    }
    previous = timestamp;
    return { date, equity };
  });
  const metric = (key: string) => {
    if (raw[key] === undefined || raw[key] === null) return null;
    const value = finite(raw[key]);
    if (value === null) throw new Error(`The backtest metric ${key} is invalid.`);
    return value;
  };
  const winRate = metric('winRate');
  if (winRate !== null && (winRate < 0 || winRate > 100)) throw new Error('The reported win rate is outside 0–100%.');
  const units = object(provenance.units);
  const metricUnits = Object.fromEntries(Object.entries(units ?? {}).filter((entry): entry is [string, string] =>
    typeof entry[1] === 'string' && entry[1].length > 0 && entry[1].length <= 32));
  const currency = typeof provenance.currency === 'string' && /^[A-Z]{3,10}$/.test(provenance.currency) ? provenance.currency : null;
  return {
    schema: 'aureon.backtest-report.v1', mode: 'historical_replay', config: { ...config }, receivedAt, source, sourceAt, fetchedAt, datasetHash,
    currency, metricUnits,
    requestId: typeof data?.request_id === 'string' ? data.request_id : null,
    accountScope: typeof data?.account_scope === 'string' ? data.account_scope : null,
    assumptions: Array.isArray(data?.assumptions) ? data.assumptions.filter((value): value is string => typeof value === 'string') : [],
    results: { totalTrades, winRate, totalReturn: metric('totalReturn'), sharpeRatio: metric('sharpeRatio'),
      maxDrawdown: metric('maxDrawdown'), profitFactor: metric('profitFactor'), avgWin: metric('avgWin'), avgLoss: metric('avgLoss'),
      equityCurve, trades: raw.trades.map(trade => ({ ...object(trade)! })) },
  };
}

const csvCell = (value: unknown) => {
  const text = value === null || value === undefined ? '' : typeof value === 'object' ? JSON.stringify(value) : String(value);
  // Neutralize spreadsheet formula cells while preserving their readable content.
  const safe = /^[\s]*[=+@-]/.test(text) && typeof value !== 'number' ? `'${text}` : text;
  return `"${safe.replace(/"/g, '""')}"`;
};

export function backtestReportCsv(report: BacktestReport): string {
  const rows: unknown[][] = [['section', 'field', 'value', 'detail'], ['receipt', 'mode', report.mode],
    ['receipt', 'source', report.source], ['receipt', 'source_at', new Date(report.sourceAt).toISOString()],
    ['receipt', 'received_at', new Date(report.receivedAt).toISOString()], ['receipt', 'currency', report.currency],
    ['receipt', 'fetched_at', report.fetchedAt === null ? null : new Date(report.fetchedAt).toISOString()],
    ['receipt', 'dataset_sha256', report.datasetHash], ['receipt', 'request_id', report.requestId], ['receipt', 'account_scope', report.accountScope]];
  Object.entries(report.config).forEach(([key, value]) => rows.push(['configuration', key, value]));
  Object.entries(report.results).filter(([key]) => !['equityCurve', 'trades'].includes(key))
    .forEach(([key, value]) => rows.push(['metric', key, value, report.metricUnits[key]]));
  report.results.equityCurve.forEach(point => rows.push(['equity', point.date, point.equity]));
  report.results.trades.forEach((trade, index) => rows.push(['trade', index + 1, trade]));
  return rows.map(row => [0, 1, 2, 3].map(index => csvCell(row[index])).join(',')).join('\r\n');
}
