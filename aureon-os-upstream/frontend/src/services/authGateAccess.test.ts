import assert from 'node:assert/strict';
import test from 'node:test';
import { hasCurrentOwnerIngress, requiresConsoleAuth } from './authGateAccess';

test('Cloud Run consoles require authentication even when the build flag is absent', () => {
  assert.equal(requiresConsoleAuth(undefined, 'aureon-fusion-web-25xhneniva-ew.a.run.app'), true);
  assert.equal(requiresConsoleAuth('0', 'AUREON-FUSION-WEB-25XHNENIVA-EW.A.RUN.APP'), true);
});

test('local development remains opt-in while an explicit build flag requires auth everywhere', () => {
  assert.equal(requiresConsoleAuth(undefined, '127.0.0.1'), false);
  assert.equal(requiresConsoleAuth('0', 'localhost'), false);
  assert.equal(requiresConsoleAuth('1', 'localhost'), true);
});

test('a current backend admin receipt admits the Google IAP owner plane', async () => {
  assert.equal(await hasCurrentOwnerIngress(async () => ({
    kind: 'admin', is_admin: true, tenant_label: null, plane: 'instance',
    tenancy_enabled: true, auth_required: true, allowed_routes: null,
  })), true);
});

test('a fully bound Supabase owner receipt admits the same owner UI plane', async () => {
  assert.equal(await hasCurrentOwnerIngress(async () => ({
    kind: 'owner', is_admin: true, tenant_label: 'owner-a1b2', plane: 'instance',
    tenancy_enabled: true, auth_required: true, allowed_routes: null,
    auth_source: 'supabase_auth_server', owner_designation_verified: true,
    identity_commitment_sha256: 'a'.repeat(64),
  })), true);
  assert.equal(await hasCurrentOwnerIngress(async () => ({
    kind: 'owner', is_admin: true, tenant_label: 'owner-a1b2', plane: 'instance',
    tenancy_enabled: true, auth_required: true, allowed_routes: null,
    auth_source: 'supabase_auth_server', owner_designation_verified: false,
    identity_commitment_sha256: 'a'.repeat(64),
  })), false);
});

test('tenant, malformed, and failed identity reads never acquire owner access', async () => {
  assert.equal(await hasCurrentOwnerIngress(async () => ({
    kind: 'tenant', is_admin: false, tenant_label: 'tenant-fixture', plane: 'account',
    tenancy_enabled: true, auth_required: true, allowed_routes: ['GET /api/me'],
  })), false);
  assert.equal(await hasCurrentOwnerIngress(async () => ({ is_admin: true })), false);
  assert.equal(await hasCurrentOwnerIngress(async () => { throw new Error('unavailable'); }), false);
});
