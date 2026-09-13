import assert from 'node:assert/strict';
import test from 'node:test';
import { planeRouteDecision } from './planeRouteAccess';
import type { Identity } from './accountConfigurationEvidence';

const owner: Identity = { kind: 'admin', isAdmin: true, tenantLabel: null, plane: 'instance', tenancyEnabled: true, authRequired: true, allowedRoutes: null };
const tenant: Identity = { kind: 'tenant', isAdmin: false, tenantLabel: 'tenant-test', plane: 'account', tenancyEnabled: true, authRequired: true, allowedRoutes: ['GET /api/me'] };

test('owner-only surfaces wait for identity and admit only the verified instance owner', () => {
  assert.equal(planeRouteDecision(true, owner, false), 'pending');
  assert.equal(planeRouteDecision(true, owner, true), 'allow');
  assert.equal(planeRouteDecision(true, { ...owner, kind: 'owner', tenantLabel: 'owner-a1b2',
    authSource: 'supabase_auth_server', ownerDesignationVerified: true,
    identityCommitmentSha256: 'a'.repeat(64) }, true), 'allow');
  assert.equal(planeRouteDecision(true, { ...owner, kind: 'owner', tenantLabel: 'owner-a1b2' }, true), 'redirect');
  assert.equal(planeRouteDecision(true, { ...owner, kind: 'open', authRequired: false }, true), 'allow');
  assert.equal(planeRouteDecision(true, tenant, true), 'redirect');
});

test('account and showcase surfaces remain available to both planes', () => {
  assert.equal(planeRouteDecision(false, owner, true), 'allow');
  assert.equal(planeRouteDecision(undefined, tenant, true), 'allow');
});
