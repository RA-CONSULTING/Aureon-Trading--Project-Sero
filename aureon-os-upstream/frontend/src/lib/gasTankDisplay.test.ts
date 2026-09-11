import assert from 'node:assert/strict';
import test from 'node:test';
import { gasTankMoney, gasTankReceiptIsCurrent } from './gasTankDisplay';

test('initial/default account values cannot appear as an observed balance', () => {
  assert.equal(gasTankMoney(0, false), 'Unavailable');
  assert.equal(gasTankMoney(25, false), 'Unavailable');
  assert.equal(gasTankMoney(0, true), '£0.00');
  for (const value of [null, undefined, NaN, Infinity, '0']) assert.equal(gasTankMoney(value, true), 'Unavailable');
});

test('the last account snapshot cannot remain current indefinitely without another receipt', () => {
  assert.equal(gasTankReceiptIsCurrent(true, 100_000, 400_000), true);
  assert.equal(gasTankReceiptIsCurrent(true, 100_000, 400_001), false);
  assert.equal(gasTankReceiptIsCurrent(false, 100_000, 100_000), false);
  assert.equal(gasTankReceiptIsCurrent(true, null, 100_000), false);
});
