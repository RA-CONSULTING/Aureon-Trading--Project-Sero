import assert from 'node:assert/strict';
import test from 'node:test';
import { readFreshBinanceTickers, tickerIsFresh, tickerOpportunityScore, TICKER_MAX_AGE_MS } from './freshTickerEvidence';

const now = Date.parse('2026-09-11T20:00:00Z');
const ticker = (overrides: Record<string, unknown> = {}) => ({
  symbol: 'BTCUSDT', exchange: 'binance', price: 50_000, volume: 2,
  volumeUsd: 100_000, priceChange24h: 0, volatility: 0,
  timestamp: now - 2_000, sourceTimestamp: new Date(now - 2_000).toISOString(),
  sourceId: 'binance:/api/v3/ticker/24hr', truthStatus: 'real_derived', generatedValues: false,
  ...overrides,
});
const payload = (tickers: unknown[] = [ticker()], overrides: Record<string, unknown> = {}) => ({
  success: true, truthStatus: 'real_derived', generatedValues: false, tickers, ...overrides,
});

test('preserves source observation, genuine zero metrics and quote volume units', () => {
  assert.deepEqual(readFreshBinanceTickers(payload(), now), [{
    symbol: 'BTCUSDT', base: 'BTC', quote: 'USDT', price: 50_000,
    volume: 100_000, change: 0, volatility: 0, sourceAt: now - 2_000,
  }]);
});

test('requires successful non-generated response and row provenance', () => {
  for (const override of [{ success: false }, { truthStatus: undefined }, { truthStatus: 'simulated' }, { generatedValues: undefined }, { generatedValues: true }]) {
    assert.deepEqual(readFreshBinanceTickers(payload([ticker()], override), now), []);
  }
  for (const override of [{ exchange: 'kraken' }, { sourceId: '' }, { truthStatus: 'cached' }, { generatedValues: true }, { generatedValues: undefined }]) {
    assert.deepEqual(readFreshBinanceTickers(payload([ticker(override)]), now), []);
  }
});

test('never substitutes receipt time for missing, mismatched, stale or future source time', () => {
  for (const override of [
    { timestamp: undefined }, { sourceTimestamp: undefined }, { sourceTimestamp: 'bad' },
    { timestamp: now - TICKER_MAX_AGE_MS - 1, sourceTimestamp: new Date(now - TICKER_MAX_AGE_MS - 1).toISOString() },
    { timestamp: now + 1, sourceTimestamp: new Date(now + 1).toISOString() },
    { sourceTimestamp: new Date(now).toISOString() },
  ]) assert.deepEqual(readFreshBinanceTickers(payload([ticker(override)]), now), []);
});

test('missing or invalid metrics cannot fall back to historical values or zero', () => {
  for (const field of ['price', 'volumeUsd', 'priceChange24h', 'volatility']) {
    for (const value of [null, undefined, '', '50', NaN, Infinity]) {
      assert.deepEqual(readFreshBinanceTickers(payload([ticker({ [field]: value })]), now), [], `${field}: ${String(value)}`);
    }
  }
  for (const override of [{ price: 0 }, { price: -1 }, { volumeUsd: -1 }, { volatility: -1 }]) {
    assert.deepEqual(readFreshBinanceTickers(payload([ticker(override)]), now), []);
  }
});

test('deduplicates by newest source observation and sorts current quote volume', () => {
  const rows = readFreshBinanceTickers(payload([
    ticker(), ticker({ price: 50_100, timestamp: now - 1_000, sourceTimestamp: new Date(now - 1_000).toISOString() }),
    ticker({ symbol: 'ETHUSDT', volumeUsd: 200_000 }), ticker({ symbol: 'BTCUSD' }),
  ]), now);
  assert.deepEqual(rows.map(row => row.symbol), ['ETHUSDT', 'BTCUSDT']);
  assert.equal(rows[1].price, 50_100);
});

test('freshness expires independently of the next response and rejects invalid clocks', () => {
  assert.equal(tickerIsFresh(now, now + TICKER_MAX_AGE_MS), true);
  assert.equal(tickerIsFresh(now, now + TICKER_MAX_AGE_MS + 1), false);
  assert.equal(tickerIsFresh(now, now - 1), false);
  assert.equal(tickerIsFresh(now, NaN), false);
  assert.equal(tickerIsFresh(0, now), false);
});

test('opportunity ranking is recomputed from current metrics', () => {
  const [first] = readFreshBinanceTickers(payload(), now);
  const [changed] = readFreshBinanceTickers(payload([ticker({ priceChange24h: 10, volatility: 0.2 })]), now);
  assert.ok(tickerOpportunityScore(changed) > tickerOpportunityScore(first));
});

test('empty and malformed provider responses stay empty', () => {
  for (const response of [undefined, null, {}, [], payload([]), payload([null, {}, 'bad'])]) {
    assert.deepEqual(readFreshBinanceTickers(response, now), []);
  }
});
