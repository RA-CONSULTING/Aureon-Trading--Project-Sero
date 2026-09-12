import assert from 'node:assert/strict';
import test from 'node:test';
import { readOperatorAuthorizationLease } from './operatorAuthorization';

const fixture = {
  schema: 'aureon.operator.authorization-lease.v1',
  state: 'active',
  active: true,
  scope: [
    'AUREON_DEPLOYMENT_HOLD',
    'AUREON_DISABLE_REAL_ORDERS',
    'AUREON_DISABLE_EXCHANGE_MUTATIONS',
    'AUREON_LIVE_TRADING',
    'AUREON_ORDER_INTENT_PUBLISH',
    'AUREON_UNIFIED_ORDER_EXECUTOR',
  ],
  account_scope: 'owner_cloud_account',
  authorized_at: 1_789_000_000,
  authorized_at_iso: '2026-09-08T00:00:00Z',
  expires_at: 1_789_259_200,
  expires_at_iso: '2026-09-11T00:00:00Z',
  remaining_seconds: 259_000,
  ledger_sequence: 3,
  ledger_event_sha256: 'a'.repeat(64),
  reason_code: 'operator_authorization_active',
  release_authority: false,
  mutation_authority: false,
};

test('authorization lease parser preserves active bounded evidence', () => {
  assert.equal(readOperatorAuthorizationLease(fixture).active, true);
});

test('authorization lease parser rejects claimed authority and state mismatches', () => {
  assert.throws(() => readOperatorAuthorizationLease({ ...fixture, release_authority: true }));
  assert.throws(() => readOperatorAuthorizationLease({ ...fixture, state: 'expired' }));
  assert.throws(() => readOperatorAuthorizationLease({ ...fixture, remaining_seconds: -1 }));
});
