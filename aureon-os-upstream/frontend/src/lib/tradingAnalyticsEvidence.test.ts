import assert from 'node:assert/strict';
import test from 'node:test';
import { ANALYTICS_MAX_AGE_MS, analyticsRangeStart, createAnalyticsAccountScope, readTradingAnalytics, type AnalyticsReceipt } from './tradingAnalyticsEvidence';

test('account changes and sign-out cancel old analytics; token refresh preserves the same account query', () => {
  const scope = createAnalyticsAccountScope();
  assert.equal(scope.observeAccount('account-a'), true);
  const previous = scope.begin();
  assert.equal(scope.observeAccount('account-a'), false);
  assert.equal(scope.current(previous), true);
  assert.equal(scope.observeAccount('account-b'), true);
  assert.equal(previous.controller.signal.aborted, true);
  assert.equal(scope.current(previous), false);
  const current = scope.begin();
  assert.equal(scope.current(current), true);
  assert.equal(scope.observeAccount(null), true);
  assert.equal(scope.current(current), false);
  assert.equal(current.controller.signal.aborted, true);
});

test('replaced range or refresh queries and unmounted queries cannot restore old rows', () => {
  const scope = createAnalyticsAccountScope();
  scope.observeAccount('account-a');
  const old = scope.begin();
  const latest = scope.begin();
  assert.equal(scope.current(old), false);
  assert.equal(old.controller.signal.aborted, true);
  assert.equal(scope.current(latest), true);
  scope.stop();
  assert.equal(scope.current(latest), false);
});

const now = Date.parse('2026-09-08T12:00:00Z');
const row = {
  id: 'close-1', symbol: 'BTCUSDT', exchange: 'binance', side: 'LONG', status: 'closed',
  opened_at: '2026-09-04T11:00:00Z', closed_at: '2026-09-04T12:00:00Z',
  source_id: 'provider-close-receipt', source_timestamp: '2026-09-04T12:00:00Z',
  truth_status: 'live', generated_values: false, realized_pnl: 10, entry_price: 100, exit_price: 110,
  current_price: 999,
};
const receipt = (data: unknown = [row], fields: Partial<AnalyticsReceipt> = {}): AnalyticsReceipt => ({
  range: '7d', receivedAt: now, status: 200, error: null, count: Array.isArray(data) ? data.length : null, data, ...fields,
});
const read = (value: AnalyticsReceipt | null, time = now) => readTradingAnalytics(value, '7d', time);

test('missing, failed and incomplete query results never produce zero performance', () => {
  assert.equal(read(null).status, 'loading');
  for (const value of [receipt(null), receipt([], { error: { message: 'denied' } }), receipt([], { status: 401 }),
    receipt([row], { count: 2 }), receipt([], { count: null }), receipt([], { status: NaN }),
    receipt([], { available: false, reason: 'Tenant/user id is required for server-side trading_positions filtering' })]) {
    const result = read(value);
    assert.equal(result.status, 'unavailable');
    assert.equal(result.count, null);
    assert.equal(result.metrics, null);
    assert.deepEqual(result.timeSeries, []);
    assert.deepEqual(result.symbols, []);
  }
});

test('only a complete successful empty receipt reports zero records, with no invented ratios', () => {
  const result = read(receipt([]));
  assert.equal(result.status, 'empty');
  assert.equal(result.count, 0);
  assert.equal(result.metrics, null);
  assert.equal(result.best, null);
});

test('query expiry and range changes hide old records; historical source time stays historical', () => {
  const fresh = read(receipt());
  assert.equal(fresh.status, 'observed');
  assert.equal(fresh.positions[0].sourceAt, Date.parse(row.source_timestamp));
  assert.equal(fresh.metrics?.avgDurationMinutes, 60);
  assert.equal(read(receipt(), now + ANALYTICS_MAX_AGE_MS + 1).metrics, null);
  assert.equal(read(receipt([], { receivedAt: now - ANALYTICS_MAX_AGE_MS - 1 })).count, null);
  assert.equal(readTradingAnalytics(receipt(), '24h', now).status, 'loading');
  assert.equal(read(receipt([], { receivedAt: now + 6_000 })).status, 'unavailable');
});

test('generated, missing P&L, malformed lifecycle and missing provenance invalidate performance', () => {
  for (const patch of [{ realized_pnl: null }, { realized_pnl: '0' }, { realized_pnl: Infinity }, { source_id: null },
    { generated_values: true }, { truth_status: 'simulated' }, { source_timestamp: 'invalid' }, { source_timestamp: '2027-01-01' },
    { closed_at: null }, { closed_at: '2026-09-01' }, { status: 'open' }]) {
    const result = read(receipt([{ ...row, ...patch }]));
    assert.equal(result.status, 'unavailable', JSON.stringify(patch));
    assert.equal(result.metrics, null);
  }
  assert.equal(read(receipt([row, row])).status, 'unavailable');
});

test('unknown or mixed P&L currency keeps record evidence but withholds monetary aggregates', () => {
  for (const rows of [[row], [{ ...row, pnl_currency: 'USD' }, { ...row, id: 'close-2', pnl_currency: 'GBP' }]]) {
    const result = read(receipt(rows));
    assert.equal(result.status, 'observed');
    assert.equal(result.metrics?.winRate, 100);
    assert.equal(result.metrics?.totalPnL, null);
    assert.equal(result.metrics?.profitFactor, null);
    assert.equal(result.best, null);
    assert.deepEqual(result.timeSeries, []);
    assert.equal(result.symbols[0].pnl, null);
  }
});

test('supported zero and breakeven remain real; absent denominator stays unavailable', () => {
  const zero = read(receipt([{ ...row, realized_pnl: 0, pnl_currency: 'USDT' }]));
  assert.equal(zero.metrics?.totalPnL, 0);
  assert.equal(zero.metrics?.winRate, 0);
  assert.equal(zero.metrics?.breakeven, 1);
  assert.equal(zero.metrics?.profitFactor, null);
  assert.equal(zero.metrics?.avgWin, null);
  assert.equal(zero.metrics?.avgLoss, null);
  const onlyWins = read(receipt([{ ...row, pnl_currency: 'USDT' }]));
  assert.equal(onlyWins.metrics?.profitFactor, null);
  assert.equal(onlyWins.metrics?.avgLoss, null);
});

test('same-currency sums and ranking use recorded P&L and actual exit fields', () => {
  const result = read(receipt([
    { ...row, pnl_currency: 'USDT' },
    { ...row, id: 'close-2', realized_pnl: -5, pnl_currency: 'USDT', exit_price: null, closed_at: '2026-09-05T12:00:00Z' },
  ]));
  assert.equal(result.metrics?.totalPnL, 5);
  assert.equal(result.metrics?.profitFactor, 2);
  assert.equal(result.metrics?.winRate, 50);
  assert.equal(result.best?.exitPrice, 110);
  assert.equal(result.worst?.exitPrice, null);
  assert.equal(result.timeSeries[1].cumulativePnL, 5);
});

test('malformed receipt date metadata is safe even on a failed response', () => {
  for (const receivedAt of [1e100, Infinity, NaN, 0, -1]) {
    assert.equal(read(receipt([], { receivedAt })).receivedAt, null);
    assert.equal(read(receipt([], { receivedAt, error: true })).receivedAt, null);
  }
  assert.equal(analyticsRangeStart('7d', now), '2026-09-01T12:00:00.000Z');
  assert.equal(analyticsRangeStart('all', now), '1970-01-01T00:00:00.000Z');
});
