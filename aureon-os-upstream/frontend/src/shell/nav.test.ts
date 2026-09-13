import assert from 'node:assert/strict';
import test from 'node:test';
import { ALL_NAV_ITEMS, HASH_REDIRECTS, navSectionsForPlane } from './nav';

const paths = (isAdmin: boolean) => navSectionsForPlane(isAdmin).flatMap(section => section.items.map(item => item.path));

test('tenant navigation omits instance runtime and mutation surfaces', () => {
  const tenantPaths = paths(false);
  for (const path of [
    '/console', '/platform/switchboard', '/trading/war-room', '/trading/hft', '/trading/live',
    '/trading/orca', '/trading/analytics', '/ops/approvals', '/ops/systems', '/ops/operational',
    '/cognition/consciousness', '/cognition/systems', '/cognition/metacognition',
    '/cognition/agents', '/coding/organism', '/defense', '/ops/affect', '/ops/soul', '/ops/inner-work', '/ops/pursuit',
  ]) assert.equal(tenantPaths.includes(path), false, path);
});

test('tenant navigation retains its own setup and allowed read surfaces while owner sees instance routes', () => {
  const tenantPaths = paths(false);
  for (const path of [
    '/start', '/account', '/ops/connections', '/cognition/providers', '/cognition/operator',
    '/trading/backtesting', '/platform/repo-map', '/platform/coverage',
    '/platform/company', '/research/solar', '/research/space-weather',
  ]) {
    assert.equal(tenantPaths.includes(path), true, path);
  }
  const ownerPaths = paths(true);
  for (const path of ['/console', '/platform/switchboard', '/trading/war-room', '/trading/analytics', '/coding/organism', '/ops/approvals']) {
    assert.equal(ownerPaths.includes(path), true, path);
  }
});

test('uncommissioned report routes and the superseded legacy console are unroutable', () => {
  const routed = new Set(ALL_NAV_ITEMS.map(item => item.path));
  for (const path of [
    '/platform/console', '/cognition/agents', '/coding/skills',
    '/coding/work-orders', '/coding/director', '/ops/gold-capital',
  ]) assert.equal(routed.has(path), false, path);
  for (const target of Object.values(HASH_REDIRECTS)) {
    assert.equal(target.startsWith('/platform/console'), false, target);
    const pathname = target.split('#')[0];
    assert.equal(routed.has(pathname) || pathname === '/evidence', true, target);
  }
});
