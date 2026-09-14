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
  last_probe: { intent_id: digest, receipt_sha256: digest, source_revision: 'b'.repeat(40),
    runtime_measurement_sha256: digest, received_at: 1, age_seconds: 0, current: true,
    chain_verified: true, authority_ids: { review: 'r', dispatch: 'd', executor: 'e', receipt: 't' },
    key_versions: { review: 'kr', dispatch: 'kd', executor: 'ke', receipt: 'kt' },
    provider_mutation_attempted: false, orders_attempted: 0, orders_submitted: 0,
    executor_capabilities: { live_execution_release: false, durable_budget_ledger: true, order_adapter_ready: true,
      live_result_binding_ready: true, instrument_preflight_enforced: true },
    provider_readback: null },
  controller_release: null,
  intent_bridge: null,
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

function activeReceipt(): Record<string, any> {
  const active = structuredClone(receipt) as Record<string, any>;
  active.operator_can_apply_live = true;
  active.requested_controls = {
    AUREON_DEPLOYMENT_HOLD: false,
    AUREON_DISABLE_REAL_ORDERS: false,
    AUREON_DISABLE_EXCHANGE_MUTATIONS: false,
    AUREON_LIVE_TRADING: true,
    AUREON_ORDER_INTENT_PUBLISH: true,
    AUREON_UNIFIED_ORDER_EXECUTOR: true,
  };
  active.desired_live_state = true;
  active.authorization.release_authority = true;
  active.release_authority = true;
  active.production_ready = true;
  active.blockers = [];
  active.last_probe.provider_readback = {
    provider_count: 4, all_authenticated: true, instrument_preflight_enforced: true,
    provider_accounts_sha256: digest, execution_budget_readiness_sha256: digest, readback_sha256: digest,
    providers: Object.fromEntries(['alpaca', 'binance', 'capital', 'kraken'].map((name, index) => [name,
      { authenticated: true, account_binding_sha256: String(index + 1).repeat(64) }])),
  };
  active.controller_release = {
    schema: 'aureon.cloud-trade-release-state.v1', state: 'active', generation: 2, request_id: digest,
    authorization_expires_at_ms: 2_000_000, signed_at_ms: 1_000_000, source_revision: 'b'.repeat(40),
    controller_key_version: 'controller-key/1',
  };
  active.intent_bridge = {
    schema: 'aureon.cloud-order-intent-bridge-status.v1', observed_at: 1, revision: 'b'.repeat(40), state: 'idle',
    operational: true, candidate_ready: false, blockers: ['qualifying_candidate_unavailable'],
    source: { runtime_status_sha256: digest, generated_at_ms: 1_000, age_ms: 0 },
    controller_release: { state: 'active', generation: 2, request_id: digest, source_revision: 'b'.repeat(40),
      authorization_event_sha256: digest, authorization_expires_at_ms: 2_000_000 },
    last_publish: null, release_authority: true, mutation_authority: false,
  };
  return active;
}

test('accepts the current active controller, four-provider probe and governed idle bridge contract', () => {
  const result = readCloudTradingControl(activeReceipt());
  assert.equal(result.release_authority, true);
  assert.equal(result.production_ready, true);
  assert.equal(result.last_probe?.provider_readback?.provider_count, 4);
  assert.equal(result.intent_bridge?.operational, true);
});

test('rejects provider evidence without both component commitments', () => {
  const active = activeReceipt();
  delete active.last_probe.provider_readback.execution_budget_readiness_sha256;
  assert.throws(() => readCloudTradingControl(active), /evidence unavailable/);

  const malformed = activeReceipt();
  malformed.last_probe.provider_readback.provider_accounts_sha256 = 'not-a-digest';
  assert.throws(() => readCloudTradingControl(malformed), /evidence unavailable/);
});

test('keeps an active signed controller visible when its separately observed bridge is held', () => {
  const active = activeReceipt();
  active.production_ready = false;
  active.blockers = ['order_intent_bridge_status_missing'];
  active.intent_bridge = null;
  const result = readCloudTradingControl(active);
  assert.equal(result.release_authority, true);
  assert.equal(result.production_ready, false);
});
