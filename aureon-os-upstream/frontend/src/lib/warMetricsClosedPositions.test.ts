import assert from 'node:assert/strict';
import test from 'node:test';
import { readClosedPositionWarMetrics } from './warMetricsClosedPositions';

const row = (realized_pnl: number | string) => ({
  id: 'closed-1', status: 'closed', generated_values: false, realized_pnl,
});

test('closed-position War Room metrics require tenant user_id scoped backend receipt', () => {
  assert.equal(readClosedPositionWarMetrics({ available: false, reason: 'Tenant/user id is required' }).status, 'unavailable');
  assert.equal(readClosedPositionWarMetrics({ available: true, tenant_scope: 'account_id', records: [row(1)], count: 1 }).status, 'unavailable');
  assert.equal(readClosedPositionWarMetrics({ available: true, tenant_scope: 'user_id', records: [row(1)], count: 2 }).status, 'unavailable');
});

test('closed-position War Room metrics derive P&L only from complete non-generated closed rows', () => {
  const metrics = readClosedPositionWarMetrics({
    available: true,
    tenant_scope: 'user_id',
    records: [row(10), row('-4'), row(0)],
    count: 3,
    reason: 'Tenant-scoped closed trading_positions records read through the local backend',
  });
  assert.equal(metrics.status, 'observed');
  assert.equal(metrics.netPnL, 6);
  assert.equal(metrics.winningTrades, 1);
  assert.equal(metrics.totalTrades, 3);
  assert.ok(Math.abs(metrics.winRate - (100 / 3)) < 1e-9);
});

test('closed-position War Room metrics reject generated or malformed rows instead of showing false zeroes', () => {
  assert.equal(readClosedPositionWarMetrics({ available: true, tenant_scope: 'user_id', records: [{ ...row(1), generated_values: true }], count: 1 }).netPnL, null);
  assert.equal(readClosedPositionWarMetrics({ available: true, tenant_scope: 'user_id', records: [{ ...row('nan') }], count: 1 }).status, 'unavailable');
});
