import assert from 'node:assert/strict';
import test from 'node:test';
import { hasCurrentOwnerIngress } from './authGateAccess';

test('a current backend admin receipt admits the Google IAP owner plane', async () => {
  assert.equal(await hasCurrentOwnerIngress(async () => ({
    kind: 'admin', is_admin: true, tenant_label: null, plane: 'instance',
    tenancy_enabled: true, auth_required: true, allowed_routes: null,
  })), true);
});

test('tenant, malformed, and failed identity reads never acquire owner access', async () => {
  assert.equal(await hasCurrentOwnerIngress(async () => ({
    kind: 'tenant', is_admin: false, tenant_label: 'tenant-fixture', plane: 'account',
    tenancy_enabled: true, auth_required: true, allowed_routes: ['GET /api/me'],
  })), false);
  assert.equal(await hasCurrentOwnerIngress(async () => ({ is_admin: true })), false);
  assert.equal(await hasCurrentOwnerIngress(async () => { throw new Error('unavailable'); }), false);
});
