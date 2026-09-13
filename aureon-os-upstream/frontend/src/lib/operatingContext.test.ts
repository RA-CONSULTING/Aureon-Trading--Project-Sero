import assert from 'node:assert/strict';
import test from 'node:test';
import { operatingContextView } from './operatingContext';
import type { Identity } from './accountConfigurationEvidence';

const owner: Identity = {
  kind: 'admin', isAdmin: true, tenantLabel: null, plane: 'instance',
  tenancyEnabled: true, authRequired: true, allowedRoutes: null,
};
const tenant: Identity = {
  kind: 'tenant', isAdmin: false, tenantLabel: 'tenant-a1b2', plane: 'account',
  tenancyEnabled: true, authRequired: true, allowedRoutes: ['GET /api/me'],
};

test('owner context describes the protected instance without claiming an order', () => {
  const view = operatingContextView(owner, true);
  assert.equal(view.kind, 'owner');
  assert.match(view.description, /server-side runtime configuration and preconfigured credentials/);
  assert.match(view.description, /Tenant workspaces cannot replace, stop, or reconfigure it/);
  assert.match(view.boundary, /does not claim that an order was placed/);
});

test('verified Supabase owner sees the same instance context on the public address', () => {
  const view = operatingContextView({ ...owner, kind: 'owner', tenantLabel: 'owner-a1b2',
    authSource: 'supabase_auth_server', ownerDesignationVerified: true,
    identityCommitmentSha256: 'a'.repeat(64) }, true);
  assert.equal(view.kind, 'owner');
  assert.equal(view.eyebrow, 'Verified owner account');
  assert.equal(view.title, 'Owner cloud runtime');
});

test('tenant context is isolated, held, and local-session scoped', () => {
  const view = operatingContextView(tenant, true);
  assert.equal(view.kind, 'tenant');
  assert.match(view.title, /tenant-a1b2/);
  assert.match(view.description, /cannot change the protected owner cloud runtime/);
  assert.match(view.boundary, /Execution remains held/);
  assert.match(view.boundary, /Signing out ends only this browser session/);
});

test('unverified or internally inconsistent identities never receive an owner label', () => {
  assert.equal(operatingContextView(owner, false).kind, 'unknown');
  assert.equal(operatingContextView({ ...owner, plane: 'account' }, true).kind, 'unknown');
  assert.equal(operatingContextView({ ...tenant, isAdmin: true }, true).kind, 'unknown');
  assert.equal(operatingContextView({ ...tenant, kind: 'owner' }, true).kind, 'unknown');
});

test('open local mode retains the instance UI and carries an exposure warning', () => {
  const view = operatingContextView({ ...owner, kind: 'open', authRequired: false }, true);
  assert.equal(view.kind, 'owner');
  assert.equal(view.badge, 'LOCAL INSTANCE');
  assert.match(view.boundary, /do not expose this instance publicly/);
});
