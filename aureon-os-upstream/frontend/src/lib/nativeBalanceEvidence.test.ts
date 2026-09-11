import assert from 'node:assert/strict';
import test from 'node:test';
import { readNativeBalanceEvidence } from './nativeBalanceEvidence';

const now = 2_000_000;
const source = { capital: 'capital:GET /accounts', alpaca: 'alpaca:GET /v2/account', binance: 'binance:GET /api/v3/account', kraken: 'kraken:POST /0/private/Balance' };
function receipt(provider: keyof typeof source, rows: Record<string, unknown>[], extra = {}) {
  return { provider, kind: 'accounts', source: source[provider], status: 'observed', generated_values: false,
    source_timestamp: 1_990, received_at: 1_991, max_age_seconds: 300, observed_count: rows.length, inventory_complete: true,
    rows: rows.map(row => ({ ...row, source_timestamp: 1_990, received_at: 1_991 })), ...extra };
}
const capital = receipt('capital', [{ reference: 'one', currency: 'GBP', balance: 12, available: 8 }, { reference: 'two', currency: 'GBP', balance: 20, available: 16 }]);

test('real same-currency records remain grouped without invented totals or deduplication', () => {
  const view = readNativeBalanceEvidence({ capital: { accounts: capital } }, true, now)[0];
  assert.equal(view.observation.available, true);
  assert.equal(view.visible.length, 1);
  assert.equal(view.visible[0].currency, 'GBP');
  assert.equal(view.visible[0].metric, 'Account balance');
  assert.deepEqual(view.visible[0].rows.map(row => row.balance), [12, 20]);
  assert.equal('total' in view, false);
});

test('native aliases and equity, cash, buying power, asset balances stay distinct', () => {
  const view = readNativeBalanceEvidence({
    alpaca: { accounts: receipt('alpaca', [{ currency: 'USD', balance_kind: 'equity', balance: 25, cash: 9, buying_power: 18, available: null }]) },
    binance: { accounts: receipt('binance', [{ currency: 'LDUSDC', balance_kind: 'free_plus_locked', balance: 7, available: 7 }]) },
    kraken: { accounts: receipt('kraken', [{ currency: 'ZUSD', balance_kind: 'total_asset_balance', balance: 11, available: null }]) },
  }, true, now);
  assert.deepEqual(view.slice(1).map(provider => provider.visible[0].currency), ['USD', 'LDUSDC', 'ZUSD']);
  const equity = view[1].visible[0];
  assert.equal(equity.metric, 'Equity');
  assert.equal(equity.rows[0].balance, 25);
  assert.equal(equity.rows[0].cash, 9);
  assert.equal(equity.rows[0].buyingPower, 18);
  assert.equal(equity.rows[0].available, null);
});

test('original receipt expires and failures remove numbers despite fresh transport', () => {
  for (const [data, connected, clock] of [[capital, true, now + 300_000], [capital, false, now], [{ ...capital, status: 'unavailable', reason: 'provider_read_failed' }, true, now]] as const) {
    const view = readNativeBalanceEvidence({ capital: { accounts: data } }, connected, clock)[0];
    assert.equal(view.observation.available, false);
    assert.equal(view.visible.length + view.zeros.length, 0);
  }
  const pending = readNativeBalanceEvidence({ capital: { accounts: { ...capital, refresh_status: 'pending' } } }, true, now)[0];
  assert.equal(pending.observation.timestamp, 1_990);
  assert.equal(pending.observation.available, true);
});

test('hundreds of observed zeros remain recoverable and nonzero cash stays visible', () => {
  const rows = Array.from({ length: 838 }, (_, i) => ({ currency: `asset-${i}`, balance_kind: 'free_plus_locked', balance: 0, available: 0 }));
  const view = readNativeBalanceEvidence({ binance: { accounts: receipt('binance', rows) }, alpaca: { accounts: receipt('alpaca', [{ currency: 'USD', balance_kind: 'equity', balance: 0, cash: 4 }]) } }, true, now);
  assert.equal(view[2].zeroCount, 838);
  assert.equal(view[2].zeros.flatMap(group => group.rows).length, 838);
  assert.equal(view[2].visible.length, 0);
  assert.equal(view[1].visible[0].rows[0].cash, 4);
});

test('missing, malformed, partial and wrong-source observations remain explicit', () => {
  const view = readNativeBalanceEvidence({ capital: { accounts: { ...capital, source: source.alpaca } } }, true, now);
  assert.equal(view[0].observation.available, false);
  assert.equal(view[1].observation.count, null);
  const partial = readNativeBalanceEvidence({ capital: { accounts: receipt('capital', [{ currency: 'GBP', balance: null, available: null }], { inventory_complete: false }) } }, true, now)[0];
  assert.equal(partial.observation.inventoryComplete, false);
  assert.equal(partial.visible[0].rows[0].balance, null);
  const wrongKind = readNativeBalanceEvidence({ alpaca: { accounts: receipt('alpaca', [{ currency: 'USD', balance_kind: 'unknown', balance: 99 }]) } }, true, now)[1];
  assert.equal(wrongKind.visible[0].rows[0].balance, null);
  assert.match(wrongKind.visible[0].rows[0].reason!, /unqualified/);
  assert.equal(readNativeBalanceEvidence({ capital: { accounts: { ...capital, source_timestamp: 1e100 } } }, true, now)[0].observation.timestamp, null);
});
