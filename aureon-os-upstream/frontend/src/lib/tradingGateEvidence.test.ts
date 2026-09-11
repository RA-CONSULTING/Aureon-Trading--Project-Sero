import assert from 'node:assert/strict';
import test from 'node:test';
import type { TerminalState } from '../hooks/terminalStateContract';
import { evaluateTradingGates } from './tradingGateEvidence';

const now = Date.parse('2026-09-08T20:00:00Z');
const sourceTimestamp = (now - 1_000) / 1_000;
const expiresAt = (now + 4_000) / 1_000;

const sourceReceipt = {
  available: true,
  truth_status: 'real_derived',
  generated_values: false,
  source_timestamp: sourceTimestamp,
  expires_at: expiresAt,
};

function receipt(overrides: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    schema_version: 1,
    truth_status: 'real_derived',
    generated_values: false,
    source: sourceReceipt,
    analysis_policy: {
      available: true,
      truth_status: 'real_derived',
      generated_values: false,
      source: 'operator-versioned-policy',
      policy_id: 'policy-2026-09-08',
      source_timestamp: sourceTimestamp,
      required_gates: ['auris', 'lighthouse', 'lhe', 'qgita'],
      auris_min_coherence: 0.7,
      lighthouse_min_confidence: 0.8,
      lhe_required: true,
      allowed_qgita_tiers: ['A'],
    },
    auris: { available: true, truth_status: 'real_derived', generated_values: false, coherence: 0.75 },
    lighthouse: { available: true, truth_status: 'real_derived', generated_values: false, confidence: 0.85 },
    lhe: { available: true, truth_status: 'real_derived', generated_values: false, is_lhe: true },
    qgita: { available: true, truth_status: 'real_derived', generated_values: false, tier: 'A' },
    opportunities: { ...sourceReceipt, active_order_flow_count: 7 },
    analysis_ready: true,
    ...overrides,
  };
}

function state(overrides: Partial<TerminalState> = {}): TerminalState {
  return {
    ok: true,
    stale: false,
    trading_ready: true,
    live_stream_cache: { fresh: true, usable_for_decision: true },
    trading_gate_evidence: receipt(),
    exchange_action_plan: {
      executor_enabled: true,
      order_intent_publish_enabled: true,
      live_enabled: true,
      real_orders_disabled: false,
      exchange_mutations_disabled: false,
      trade_path_state: 'available',
      global_blockers: [],
      runtime_clearances: [],
    },
    ...overrides,
  };
}

test('data freshness requires both completed tick and direct market stream', () => {
  assert.equal(evaluateTradingGates(state(), true, true, now).dataFresh, true);
  assert.equal(evaluateTradingGates(state(), false, true, now).dataFresh, false);
  assert.equal(evaluateTradingGates(state(), true, false, now).dataFresh, false);
  assert.equal(evaluateTradingGates(state({ stale: true }), true, true, now).dataFresh, false);
  assert.equal(evaluateTradingGates(state({ live_stream_cache: { fresh: true, usable_for_decision: false } }), true, true, now).dataFresh, false);
});

test('data freshness accepts current provider rows when older endpoint omits usable flag', () => {
  const result = evaluateTradingGates(state({
    live_stream_cache: {
      fresh: true,
      symbol_count: 10,
      quotes: [{ symbol: 'BTCUSDT', price: 50000, timestamp: sourceTimestamp }],
    },
  }), true, true, now);

  assert.equal(result.dataFresh, true);
});

test('missing policy leaves named analysis gates unavailable without hiding a real Auris measurement', () => {
  const evidence = receipt({
    analysis_policy: {
      available: false,
      truth_status: 'unavailable',
      generated_values: false,
      required_gates: null,
    },
    lighthouse: { available: false, truth_status: 'unavailable', generated_values: false },
    lhe: { available: false, truth_status: 'unavailable', generated_values: false },
    qgita: { available: false, truth_status: 'unavailable', generated_values: false },
  });
  const result = evaluateTradingGates(state({ trading_gate_evidence: evidence }), true, true, now);
  assert.equal(result.auris.measurementAvailable, true);
  assert.equal(result.auris.available, false);
  assert.equal(result.auris.value, '0.750');
  assert.equal(result.lighthouse.available, false);
  assert.equal(result.lhe.available, false);
  assert.equal(result.qgita.available, false);
  assert.equal(result.analysisReady, false);
  assert.equal(result.executionOpen, false);
  assert.equal(result.opportunities, 7);
});

test('assembly time cannot renew expired provider or opportunity evidence', () => {
  const expired = { ...sourceReceipt, expires_at: (now - 1) / 1_000 };
  const result = evaluateTradingGates(state({ trading_gate_evidence: receipt({
    generated_at: new Date(now).toISOString(),
    source: expired,
    opportunities: { ...expired, active_order_flow_count: 7 },
  }) }), true, true, now);
  assert.equal(result.receiptFresh, false);
  assert.equal(result.analysisReceiptFresh, false);
  assert.equal(result.analysisReady, false);
  assert.equal(result.opportunities, null);
});

test('completed tick analysis remains visible after source expiry while execution stays closed', () => {
  const generatedAt = now - 3_000;
  const completedTickSource = {
    ...sourceReceipt,
    source_timestamp: (now - 7_000) / 1_000,
    expires_at: (now - 1_000) / 1_000,
  };
  const result = evaluateTradingGates(state({ trading_gate_evidence: receipt({
    generated_at: new Date(generatedAt).toISOString(),
    source: completedTickSource,
    opportunities: { ...completedTickSource, active_order_flow_count: 7 },
  }) }), true, true, now);
  assert.equal(result.receiptFresh, false);
  assert.equal(result.analysisReceiptFresh, true);
  assert.equal(result.analysisReady, true);
  assert.equal(result.opportunities, 7);
  assert.equal(result.executionOpen, false);
  assert.equal(result.executionReason, 'Current trading-gate source receipt expired');
});

test('generated values are rejected even when timestamps and values look current', () => {
  const result = evaluateTradingGates(state({ trading_gate_evidence: receipt({ generated_values: true }) }), true, true, now);
  assert.equal(result.receiptFresh, false);
  assert.equal(result.analysisReceiptFresh, false);
  assert.equal(result.executionOpen, false);
});

test('analysis reason names the specific failed required gate', () => {
  const evidence = receipt({
    analysis_ready: false,
    auris: { available: true, truth_status: 'real_derived', generated_values: false, coherence: 0.49 },
  });
  const result = evaluateTradingGates(state({ trading_gate_evidence: evidence }), true, true, now);

  assert.equal(result.analysisReady, false);
  assert.equal(result.executionOpen, false);
  assert.equal(result.analysisReason, 'Auris coherence below policy threshold');
  assert.equal(result.executionReason, 'Auris coherence below policy threshold');
});


test('current HNC proof keeps analysis visible only when the gate receipt is absent', () => {
  const timestamp = new Date(now - 1_000).toISOString();
  const proof = {
    generated_at: timestamp,
    status: 'passing',
    passed: true,
    passed_count: 9,
    step_count: 9,
    flow: [
      'real_market_data',
      'hnc_master_formula',
      'auris_nodes',
      'hnc_operating_cycle',
      'seer_vision',
      'lyra_resonance',
      'king_capital_logic',
      'shadow_trade_self_validation',
      'public_state_publication',
    ].map((step) => ({ step, passed: true, timestamp })),
  };
  const operatingCycle = {
    generated_at: timestamp,
    status: 'passing',
    passed: true,
    passed_count: 6,
    step_count: 6,
  };
  const heldPlan = {
    executor_enabled: false,
    order_intent_publish_enabled: false,
    live_enabled: false,
    real_orders_disabled: true,
    exchange_mutations_disabled: true,
    trade_path_state: 'available',
    global_blockers: [],
    runtime_clearances: ['real_orders_disabled', 'exchange_mutations_disabled', 'order_intent_publish_disabled'],
  };

  const fallback = evaluateTradingGates(state({
    trading_gate_evidence: undefined,
    hnc_cognitive_proof: proof,
    hnc_operating_cycle: operatingCycle,
    exchange_action_plan: heldPlan,
  }), true, true, now);

  assert.equal(fallback.analysisReceiptFresh, false);
  assert.equal(fallback.analysisReady, true);
  assert.equal(fallback.analysisReason, 'HNC proof flow passed with current terminal-state data; trading-gate receipt unavailable');
  assert.equal(fallback.executionOpen, false);
  assert.equal(fallback.executionReason, 'Order or exchange mutation hold remains');

  const explicitRejectedReceipt = evaluateTradingGates(state({
    trading_gate_evidence: { schema_version: 1, truth_status: 'real_derived', generated_values: true },
    hnc_cognitive_proof: proof,
    hnc_operating_cycle: operatingCycle,
    exchange_action_plan: heldPlan,
  }), true, true, now);

  assert.equal(explicitRejectedReceipt.analysisReady, false);
  assert.equal(explicitRejectedReceipt.executionOpen, false);
});


test('execution requires intent publication, available path, and explicit empty blockers and clearances', () => {
  assert.equal(evaluateTradingGates(state(), true, true, now).executionOpen, true);
  const blockedPlans: TerminalState['exchange_action_plan'][] = [
    { executor_enabled: true, order_intent_publish_enabled: false, live_enabled: true, real_orders_disabled: false, exchange_mutations_disabled: false, trade_path_state: 'available', global_blockers: [], runtime_clearances: [] },
    { executor_enabled: true, order_intent_publish_enabled: true, live_enabled: false, real_orders_disabled: false, exchange_mutations_disabled: false, trade_path_state: 'available', global_blockers: [], runtime_clearances: [] },
    { executor_enabled: true, order_intent_publish_enabled: true, live_enabled: true, real_orders_disabled: true, exchange_mutations_disabled: false, trade_path_state: 'available', global_blockers: [], runtime_clearances: [] },
    { executor_enabled: true, order_intent_publish_enabled: true, live_enabled: true, real_orders_disabled: false, exchange_mutations_disabled: true, trade_path_state: 'available', global_blockers: [], runtime_clearances: [] },
    { executor_enabled: true, order_intent_publish_enabled: true, live_enabled: true, real_orders_disabled: false, exchange_mutations_disabled: false, trade_path_state: 'held', global_blockers: [], runtime_clearances: [] },
    { executor_enabled: true, order_intent_publish_enabled: true, live_enabled: true, real_orders_disabled: false, exchange_mutations_disabled: false, trade_path_state: 'available', global_blockers: ['hold'], runtime_clearances: [] },
    { executor_enabled: true, order_intent_publish_enabled: true, live_enabled: true, real_orders_disabled: false, exchange_mutations_disabled: false, trade_path_state: 'available', global_blockers: [], runtime_clearances: ['approval'] },
    { executor_enabled: true, order_intent_publish_enabled: true, live_enabled: true, real_orders_disabled: false, exchange_mutations_disabled: false, trade_path_state: 'available' },
  ];
  for (const exchange_action_plan of blockedPlans) {
    assert.equal(evaluateTradingGates(state({ exchange_action_plan }), true, true, now).executionOpen, false);
  }
});

test('a versioned policy can explicitly make LHE optional', () => {
  const evidence = receipt();
  const policy = evidence.analysis_policy as Record<string, unknown>;
  evidence.analysis_policy = { ...policy, lhe_required: false };
  evidence.lhe = { available: false, truth_status: 'unavailable', generated_values: false };
  const result = evaluateTradingGates(state({ trading_gate_evidence: evidence }), true, true, now);
  assert.equal(result.lhe.available, true);
  assert.equal(result.lhe.passed, true);
  assert.equal(result.lhe.value, 'not required');
  assert.equal(result.analysisReady, true);
});

test('opportunity count must be an integer in its own current receipt', () => {
  for (const active_order_flow_count of [-1, 1.5, Number.NaN]) {
    const result = evaluateTradingGates(state({ trading_gate_evidence: receipt({
      opportunities: { ...sourceReceipt, active_order_flow_count },
    }) }), true, true, now);
    assert.equal(result.opportunities, null);
  }
});
