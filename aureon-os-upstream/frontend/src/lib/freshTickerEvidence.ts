/** Fresh provider observations only. No historical price or browser-clock fallback. */
export const TICKER_MAX_AGE_MS = 30_000;

export interface FreshBinanceTicker {
  symbol: string;
  base: string;
  quote: 'USDT';
  price: number;
  volume: number;
  change: number;
  volatility: number;
  sourceAt: number;
}

function record(value: unknown): Record<string, unknown> | null {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
    ? value as Record<string, unknown> : null;
}

function finite(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value);
}

export function tickerIsFresh(sourceAt: number, now: number): boolean {
  return Number.isFinite(sourceAt) && Number.isFinite(now)
    && sourceAt > 0 && sourceAt <= now && now - sourceAt <= TICKER_MAX_AGE_MS;
}

export function readFreshBinanceTickers(payload: unknown, now: number): FreshBinanceTicker[] {
  const body = record(payload);
  if (!body || body.success !== true || body.truthStatus !== 'real_derived'
      || body.generatedValues !== false || !Array.isArray(body.tickers)) return [];

  const symbols = new Map<string, FreshBinanceTicker>();
  for (const value of body.tickers) {
    const row = record(value);
    if (!row || row.exchange !== 'binance' || row.truthStatus !== 'real_derived'
        || row.generatedValues !== false || row.sourceId !== 'binance:/api/v3/ticker/24hr'
        || typeof row.symbol !== 'string' || !/^[A-Z0-9]{1,16}USDT$/.test(row.symbol)
        || typeof row.sourceTimestamp !== 'string' || !finite(row.timestamp)
        || Date.parse(row.sourceTimestamp) !== row.timestamp || !tickerIsFresh(row.timestamp, now)
        || !finite(row.price) || row.price <= 0
        || !finite(row.volumeUsd) || row.volumeUsd < 0
        || !finite(row.priceChange24h) || !finite(row.volatility) || row.volatility < 0) continue;

    const ticker: FreshBinanceTicker = {
      symbol: row.symbol, base: row.symbol.slice(0, -4), quote: 'USDT',
      price: row.price, volume: row.volumeUsd, change: row.priceChange24h,
      volatility: row.volatility, sourceAt: row.timestamp,
    };
    const previous = symbols.get(ticker.symbol);
    if (!previous || ticker.sourceAt > previous.sourceAt) symbols.set(ticker.symbol, ticker);
  }
  return [...symbols.values()].sort((a, b) => b.volume - a.volume);
}

export function tickerOpportunityScore(ticker: FreshBinanceTicker): number {
  return ticker.volatility * 0.4
    + (Math.log10(Math.max(ticker.volume, 1)) / 10) * 0.3
    + Math.abs(ticker.change / 100) * 0.3;
}
