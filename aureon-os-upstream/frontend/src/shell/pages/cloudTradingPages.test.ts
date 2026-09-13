import assert from 'node:assert/strict';
import test from 'node:test';
import { readFileSync } from 'node:fs';

const source = (name: string) => readFileSync(new URL(`./${name}`, import.meta.url), 'utf8');

test('owner War Room reads signed cloud authority and labels VM inventory separately', () => {
  const page = source('WarRoomPage.tsx');
  assert.match(page, /useReadOnlyPoller\(cloudTradingControlStore/);
  assert.match(page, /cloudExecutionPresentation\(cloudRead\)/);
  assert.match(page, /Cloud exchange authentication/);
  assert.match(page, /Native account inventories/);
  assert.match(page, /Current VM balance\/account receipts; separate from cloud executor authentication/);
  assert.match(page, /VM direct planner/);
  assert.match(page, /do not override a current signed cloud controller receipt/);
});

test('owner Live Bridge separates cloud executor authentication from native inventory coverage', () => {
  const page = source('LiveBridgePage.tsx');
  assert.match(page, /useReadOnlyPoller\(cloudTradingControlStore/);
  assert.match(page, /Cloud execution authentication/);
  assert.match(page, /Native account inventories/);
  assert.match(page, /Cloud executor:/);
  assert.match(page, /VM inventory:/);
  assert.match(page, /A release or authentication probe is not an order, acknowledgment, or fill/);
});
