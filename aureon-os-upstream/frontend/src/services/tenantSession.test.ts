import assert from 'node:assert/strict';
import test from 'node:test';
import { endTenantBrowserSession } from './tenantSession';

test('tenant logout requests local browser scope only', async () => {
  let received: unknown;
  await endTenantBrowserSession(async options => {
    received = options;
    return { error: null };
  });
  assert.deepEqual(received, { scope: 'local' });
});

test('tenant logout rejects when the provider does not confirm it', async () => {
  await assert.rejects(
    endTenantBrowserSession(async () => ({ error: new Error('provider unavailable') })),
    /provider unavailable/,
  );
});
