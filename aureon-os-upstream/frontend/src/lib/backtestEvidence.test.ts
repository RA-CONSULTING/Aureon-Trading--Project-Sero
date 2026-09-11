import assert from 'node:assert/strict';
import test from 'node:test';
import { backtestReportCsv, backtestServiceAvailable, createBacktestScope, readBacktestReport, type BacktestConfig } from './backtestEvidence';

const now = Date.parse('2026-09-11T12:00:00Z');
const config: BacktestConfig = { symbol: 'BTCUSD', startDate: '2026-09-01', endDate: '2026-09-10', initialCapital: 10000,
  tradeSize: 0.5, stopLoss: 2, takeProfit: 5, strategy: 'momentum_next_open_v1', intervalMinutes: 60, lookbackPeriods: 24, feeBps: 40, slippageBps: 5 };
const capability = { service: 'aureon-historical-backtest', available: true, execution_mode: 'historical_replay', source_backed: true, executes_orders: false, account_scope: 'a'.repeat(64) };
const response = () => ({ config: { ...config }, provenance: { generated: false, execution_mode: 'historical_replay', source: 'provider:dated-candles', source_at: '2026-09-10T23:00:00Z' },
  results: { totalTrades: 1, winRate: 0, trades: [{ id: 'close-1', outcome: 'loss' }], equityCurve: [{ date: '2026-09-01', equity: 10000 }, { date: '2026-09-10', equity: 9900 }] } });

test('Run requires every capability guarantee and a current receipt', () => {
  assert.equal(backtestServiceAvailable(capability, now, now), true);
  for (const key of Object.keys(capability)) {
    const incomplete = { ...capability } as Record<string, unknown>;
    delete incomplete[key];
    assert.equal(backtestServiceAvailable(incomplete, now, now), false, key);
  }
  assert.equal(backtestServiceAvailable(capability, now, now + 60_001), false);
  assert.equal(backtestServiceAvailable(capability, now + 1, now), false);
  assert.equal(backtestServiceAvailable(capability, null, now), false);
  assert.equal(backtestServiceAvailable({ ...capability, executes_orders: true }, now, now), false);
});

test('missing metrics remain unavailable while genuine zero and original source dates survive', () => {
  const report = readBacktestReport(response(), config, now);
  assert.equal(report.results.winRate, 0);
  assert.equal(report.results.profitFactor, null);
  assert.equal(report.sourceAt, Date.parse('2026-09-10T23:00:00Z'));
  assert.equal(report.receivedAt, now);
});

test('missing, synthetic and future dataset provenance cannot produce a report', () => {
  assert.throws(() => readBacktestReport({ config, results: response().results }, config, now), /provenance/);
  for (const override of [{ generated: true }, { source: '' }, { source_at: '2026-09-12T00:00:00Z' }, { execution_mode: 'live' }]) {
    const payload = response();
    Object.assign(payload.provenance, override);
    assert.throws(() => readBacktestReport(payload, config, now));
  }
});

test('incomplete trade counts and invalid, unordered or out-of-range equity records are rejected', () => {
  const missingTrade = response();
  missingTrade.results.totalTrades = 2;
  assert.throws(() => readBacktestReport(missingTrade, config, now), /trade count/);
  for (const curve of [[], [{ date: 'invalid', equity: 1 }], [{ date: '2026-09-10', equity: Infinity }],
    [{ date: '2026-09-12', equity: 1 }], [{ date: '2026-09-10', equity: 1 }, { date: '2026-09-01', equity: 1 }]]) {
    const payload = response();
    payload.results.equityCurve = curve;
    assert.throws(() => readBacktestReport(payload, config, now));
  }
});

test('non-finite or impossible supplied metrics cannot become zero', () => {
  for (const winRate of [Infinity, NaN, -1, 101]) {
    const payload = response();
    payload.results.winRate = winRate;
    assert.throws(() => readBacktestReport(payload, config, now));
  }
});

test('exports retain the submitted configuration when the editable form changes', () => {
  const submitted = { ...config };
  const report = readBacktestReport(response(), submitted, now);
  submitted.symbol = 'ETHUSD';
  submitted.initialCapital = 500;
  assert.equal(report.config.symbol, 'BTCUSD');
  assert.equal(report.config.initialCapital, 10000);
  const csv = backtestReportCsv(report);
  assert.match(csv, /"configuration","symbol","BTCUSD"/);
  assert.match(csv, /"metric","profitFactor",""/);
  assert.match(csv, /"trade","1"/);
  assert.match(csv, /2026-09-10T23:00:00.000Z/);
});

test('CSV quotes source text and neutralizes spreadsheet formulas', () => {
  const report = readBacktestReport(response(), config, now);
  report.source = '=HYPERLINK("untrusted")';
  const csv = backtestReportCsv(report);
  assert.ok(csv.includes('"\'=HYPERLINK(""untrusted"")"'));
});

test('mismatched or absent echoed configuration cannot relabel another replay as the request', () => {
  const missing = { ...response() } as Record<string, unknown>;
  delete missing.config;
  assert.throws(() => readBacktestReport(missing, config, now), /exact submitted configuration/);
  for (const override of [{ symbol: 'ETHUSD' }, { initialCapital: 500 }, { lookbackPeriods: 2 }, { tradeSize: 0.99 }, { startDate: '2026-09-02' }]) {
    const payload = response();
    Object.assign(payload.config, override);
    assert.throws(() => readBacktestReport(payload, config, now), /exact submitted configuration/);
  }
});

test('auth resets abort both request stages and reject late results without invalidating a new request', () => {
  const scope = createBacktestScope();
  const probe = scope.begin();
  const replay = scope.begin();
  assert.equal(scope.current(probe), true);
  scope.reset();
  const next = scope.begin();
  assert.equal(probe.controller.signal.aborted, true);
  assert.equal(replay.controller.signal.aborted, true);
  assert.equal(scope.current(probe), false);
  assert.equal(scope.current(replay), false);
  scope.finish(replay);
  assert.equal(scope.current(next), true);
  scope.finish(next);
});

test('unreported units and currency remain unknown and declared metadata survives exports', () => {
  const unknown = readBacktestReport(response(), config, now);
  assert.equal(unknown.currency, null);
  assert.deepEqual(unknown.metricUnits, {});
  const payload = response();
  Object.assign(payload.provenance, { currency: 'USDT', units: { avgWin: 'USDT', winRate: 'percent' } });
  const report = readBacktestReport(payload, config, now);
  assert.equal(report.currency, 'USDT');
  assert.equal(report.metricUnits.avgWin, 'USDT');
  assert.match(backtestReportCsv(report), /"metric","winRate","0","percent"/);
});

test('request and authenticated account bindings must both match before accepting results', () => {
  const binding = { requestId: 'request-a', accountScope: 'a'.repeat(64) };
  const payload = { ...response(), schema: 'aureon.backtest-result.v1', service: 'aureon-historical-backtest', request_id: binding.requestId, account_scope: binding.accountScope };
  Object.assign(payload.provenance, { fetched_at: '2026-09-11T10:00:00Z', dataset_sha256: 'b'.repeat(64) });
  assert.equal(readBacktestReport(payload, config, now, binding).requestId, binding.requestId);
  assert.throws(() => readBacktestReport({ ...payload, request_id: 'request-b' }, config, now, binding), /request and authenticated account/);
  assert.throws(() => readBacktestReport({ ...payload, account_scope: 'b'.repeat(64) }, config, now, binding), /request and authenticated account/);
  assert.throws(() => readBacktestReport({ ...payload, provenance: response().provenance }, config, now, binding), /dataset receipt/);
});
