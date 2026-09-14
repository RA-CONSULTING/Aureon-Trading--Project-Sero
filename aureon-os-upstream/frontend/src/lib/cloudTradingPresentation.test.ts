import assert from 'node:assert/strict';
import test from 'node:test';
import { CLOUD_TRADE_CONTROL_IDS, type CloudTradingControlReceipt } from './cloudTradingControl';
import { cloudExecutionPresentation, cloudTradingSourceEvidence } from './cloudTradingPresentation';

const digest = 'a'.repeat(64);
const revision = 'b'.repeat(40);
const requestedControls = Object.fromEntries(CLOUD_TRADE_CONTROL_IDS.map(key => [key,
  !['AUREON_DEPLOYMENT_HOLD', 'AUREON_DISABLE_REAL_ORDERS', 'AUREON_DISABLE_EXCHANGE_MUTATIONS'].includes(key),
])) as CloudTradingControlReceipt['effective_controls'];
const effectiveVmControls = Object.fromEntries(CLOUD_TRADE_CONTROL_IDS.map(key => [key,
  ['AUREON_DEPLOYMENT_HOLD', 'AUREON_DISABLE_REAL_ORDERS', 'AUREON_DISABLE_EXCHANGE_MUTATIONS'].includes(key),
])) as CloudTradingControlReceipt['effective_controls'];

function activeControl(): CloudTradingControlReceipt {
  return {
    schema: 'aureon.operator.cloud-trading-control.v1', observed_at: 2_000, truth_status: 'real_derived', read_state: 'observed',
    operator_can_request_controls: true, operator_can_apply_live: true,
    requested_controls: requestedControls, effective_controls: effectiveVmControls, desired_live_state: true,
    authorization: { active: true, state: 'active', expires_at_iso: '2026-09-15T00:00:00Z', ledger_event_sha256: digest,
      release_authority: true, mutation_authority: false },
    capabilities: { signed_authority_chain: true, governed_order_intent_bridge: true },
    last_probe: {
      intent_id: digest, receipt_sha256: digest, source_revision: revision, runtime_measurement_sha256: digest,
      received_at: 2_000, age_seconds: 0, current: true, chain_verified: true,
      authority_ids: { review: 'r', dispatch: 'd', executor: 'e', receipt: 't' },
      key_versions: { review: 'kr', dispatch: 'kd', executor: 'ke', receipt: 'kt' },
      provider_mutation_attempted: false, orders_attempted: 0, orders_submitted: 0,
      executor_capabilities: { live_execution_release: true, durable_budget_ledger: true, order_adapter_ready: true,
        live_result_binding_ready: true, instrument_preflight_enforced: true },
      provider_readback: {
        provider_count: 4, all_authenticated: true, instrument_preflight_enforced: true,
        provider_accounts_sha256: digest, execution_budget_readiness_sha256: digest, readback_sha256: digest,
        providers: Object.fromEntries(['alpaca', 'binance', 'capital', 'kraken'].map((venue, index) => [venue,
          { authenticated: true, account_binding_sha256: String(index + 1).repeat(64) }])) as
            NonNullable<NonNullable<CloudTradingControlReceipt['last_probe']>['provider_readback']>['providers'],
      },
    },
    controller_release: { schema: 'aureon.cloud-trade-release-state.v1', state: 'active', generation: 4,
      request_id: digest, authorization_expires_at_ms: 2_100_000, signed_at_ms: 1_999_000,
      source_revision: revision, controller_key_version: 'controller-key/1' },
    intent_bridge: {
      schema: 'aureon.cloud-order-intent-bridge-status.v1', observed_at: 2_000, revision, state: 'idle',
      operational: true, candidate_ready: false, blockers: ['qualifying_candidate_unavailable'],
      source: { runtime_status_sha256: digest, generated_at_ms: 1_999_000, age_ms: 1_000 },
      controller_release: { state: 'active', generation: 4, request_id: digest, source_revision: revision,
        authorization_event_sha256: digest, authorization_expires_at_ms: 2_100_000 },
      last_publish: null, release_authority: true, mutation_authority: false,
    },
    blockers: [], production_ready: true, release_authority: true, mutation_authority: false,
    digest_sha256: digest, digest_scope: 'operator_cloud_trading_control',
  };
}

const currentRead = (data: CloudTradingControlReceipt | null) => ({
  data, isReceiptCurrent: data !== null, error: null,
  source: { status: data ? 'fresh' as const : 'unavailable' as const },
});

test('active signed cloud release remains operative while the separate VM planner may be held', () => {
  const legacyLocalReadiness = 'held';
  const view = cloudExecutionPresentation(currentRead(activeControl()));
  assert.equal(legacyLocalReadiness, 'held');
  assert.equal(view.state, 'active');
  assert.equal(view.headline, 'CONTROLLER-SIGNED CLOUD RELEASE ACTIVE');
  assert.equal(view.release, 'Active until 1970-01-01T00:35:00.000Z');
  assert.equal(view.intentBridge, 'Operational · waiting for a qualifying candidate');
  assert.match(view.detail, /VM planner flags are shown separately/);
});

test('current signed no-order probe reports 4 / 4 execution authentication separately from inventory', () => {
  const view = cloudExecutionPresentation(currentRead(activeControl()));
  assert.equal(view.executionAuthentication, '4 / 4');
  assert.equal(view.executionAuthenticationDetail,
    'Current signed no-order cloud executor probe; separate from VM account inventories.');
  assert.equal(view.orderOutcome, 'No signed terminal order/fill receipt in this control readback');
  assert.doesNotMatch(`${view.headline} ${view.detail} ${view.orderOutcome}`, /order (submitted|filled)|fill confirmed/i);
});

test('held signed controller is labelled held without converting authentication into authority', () => {
  const control = activeControl();
  control.authorization.release_authority = false;
  control.controller_release!.state = 'held';
  control.intent_bridge = null;
  control.production_ready = false;
  control.release_authority = false;
  control.blockers = ['live_execution_release_held'];
  const view = cloudExecutionPresentation(currentRead(control));
  assert.equal(view.state, 'held');
  assert.equal(view.headline, 'CONTROLLER-SIGNED CLOUD RELEASE HELD');
  assert.equal(view.executionAuthentication, '4 / 4');
  assert.deepEqual(view.blockers, ['live execution release held']);
});

test('recorded or expired cloud evidence is labelled stale and withholds prior 4 / 4 authentication', () => {
  const control = activeControl();
  control.read_state = 'recorded';
  control.last_probe!.current = false;
  const source = cloudTradingSourceEvidence(control, 2_001_000);
  const view = cloudExecutionPresentation({ data: control, isReceiptCurrent: true, error: null, source });
  assert.equal(source.status, 'stale');
  assert.equal(view.state, 'stale');
  assert.equal(view.headline, 'CLOUD EXECUTION EVIDENCE STALE');
  assert.equal(view.executionAuthentication, '— / 4');
  assert.equal(view.orderOutcome, 'No current signed terminal order/fill receipt');
});

test('missing protected owner evidence is unavailable and never inherits a live claim', () => {
  const view = cloudExecutionPresentation({ data: null, isReceiptCurrent: false, error: 'HTTP 403',
    source: { status: 'unavailable' } });
  assert.equal(view.state, 'unavailable');
  assert.equal(view.headline, 'CLOUD EXECUTION EVIDENCE UNAVAILABLE');
  assert.equal(view.release, 'Unconfirmed · evidence unavailable');
  assert.equal(view.active, false);
});
