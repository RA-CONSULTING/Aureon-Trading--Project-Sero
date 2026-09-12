import assert from 'node:assert/strict';
import test from 'node:test';
import { CLOUD_TRADE_CONTROL_IDS, readCloudTradingControl } from './cloudTradingControl';

const controls = Object.fromEntries(CLOUD_TRADE_CONTROL_IDS.map(key => [key, false]));
const digest = 'a'.repeat(64);
const receipt = {
  schema: 'aureon.operator.cloud-trading-control.v1', observed_at: 1, truth_status: 'real_derived', read_state: 'observed',
  operator_can_request_controls: true, operator_can_apply_live: false,
  requested_controls: controls, effective_controls: controls, desired_live_state: false,
  authorization: { active: true, state: 'active', expires_at_iso: '2026-09-15T00:00:00Z', ledger_event_sha256: digest,
    release_authority: false, mutation_authority: false },
  capabilities: { signed_authority_chain: true },
  last_probe: { intent_id: digest, receipt_sha256: digest, received_at: 1, age_seconds: 0, current: true,
    chain_verified: true, authority_ids: { review: 'r', dispatch: 'd', executor: 'e', receipt: 't' },
    key_versions: { review: 'kr', dispatch: 'kd', executor: 'ke', receipt: 'kt' },
    provider_mutation_attempted: false, orders_attempted: 0, orders_submitted: 0,
    executor_capabilities: { live_execution_release: false, durable_budget_ledger: true, order_adapter_ready: true },
    provider_readback: null },
  blockers: ['live_order_adapter_unavailable'], production_ready: false,
  release_authority: false, mutation_authority: false, digest_sha256: digest,
  digest_scope: 'operator_cloud_trading_control',
};

test('accepts a held signed authority receipt without granting mutation authority', () => {
  const result = readCloudTradingControl(receipt);
  assert.equal(result.last_probe?.chain_verified, true);
  assert.equal(result.operator_can_apply_live, false);
  assert.equal(result.mutation_authority, false);
});

test('rejects duplicate authority identities', () => {
  const invalid = structuredClone(receipt);
  invalid.last_probe.authority_ids.executor = 'r';
  assert.throws(() => readCloudTradingControl(invalid), /evidence unavailable/);
});

test('rejects a ready claim that still has blockers', () => {
  assert.throws(() => readCloudTradingControl({ ...receipt, operator_can_apply_live: true, production_ready: true }), /inconsistent/);
});
