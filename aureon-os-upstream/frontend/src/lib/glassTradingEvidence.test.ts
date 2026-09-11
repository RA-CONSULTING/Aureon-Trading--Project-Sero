import assert from 'node:assert/strict';
import test from 'node:test';
import { executionGlassState, glassDecisionTraces, glassLatency } from './glassTradingEvidence';
import type { TerminalState } from '../hooks/terminalStateContract';

const now = Date.now();
const source = { available: true, truth_status: 'real_derived', generated_values: false, source_timestamp: (now - 1000) / 1000, expires_at: (now + 4000) / 1000 };
const enabled: TerminalState = { ok: true, stale: false, trading_ready: true,
  live_stream_cache: { fresh: true, usable_for_decision: true },
  trading_gate_evidence: { schema_version: 1, truth_status: 'real_derived', generated_values: false, source, execution_authority: false,
    analysis_policy: { available: true, truth_status: 'real_derived', generated_values: false, source: 'operator-versioned-policy', policy_id: 'fixture', source_timestamp: source.source_timestamp,
      required_gates: ['auris', 'lighthouse', 'lhe', 'qgita'], auris_min_coherence: 0.7, lighthouse_min_confidence: 0.8, lhe_required: true, allowed_qgita_tiers: ['A'] },
    auris: { available: true, truth_status: 'real_derived', generated_values: false, coherence: 0.75 },
    lighthouse: { available: true, truth_status: 'real_derived', generated_values: false, confidence: 0.9 },
    lhe: { available: true, truth_status: 'real_derived', generated_values: false, is_lhe: true },
    qgita: { available: true, truth_status: 'real_derived', generated_values: false, tier: 'A' }, analysis_ready: true,
  }, exchange_action_plan: {
  executor_enabled: true, live_enabled: true, real_orders_disabled: false,
  exchange_mutations_disabled: false, order_intent_publish_enabled: true, global_blockers: [], trade_path_state: 'available', runtime_clearances: [],
} };
test('runtime readiness alone cannot enable execution; fully attested flags can', () => {
  assert.equal(executionGlassState({ trading_ready: true }, true).enabled, false);
  assert.equal(executionGlassState(enabled, true, true, now).label, 'Execution enabled');
  assert.equal(executionGlassState(enabled, true, false, now).enabled, false);
  for (const state of [
    { ...enabled, trading_gate_evidence: {} },
    { ...enabled, exchange_action_plan: { ...enabled.exchange_action_plan, global_blockers: undefined } },
    { ...enabled, exchange_action_plan: { ...enabled.exchange_action_plan, real_orders_disabled: true } },
    { ...enabled, exchange_action_plan: { ...enabled.exchange_action_plan, global_blockers: ['held'] } },
  ]) assert.equal(executionGlassState(state, true, true, now).enabled, false);
  assert.equal(executionGlassState(enabled, false).label, 'Execution unconfirmed');
});
test('recorded trace timestamps survive; missing, reversed or future stages are not fabricated', () => {
  const traces = [{ decision_trace_id: 'a', t_intel_seen: 100, t_signal_scored: 101,
    t_intent_ready: 102, t_exec_dispatched: 103, t_exchange_ack: 104, t_state_converged: 105 }];
  assert.equal(glassDecisionTraces({ decision_traces: traces }, true, 110000)[0].e2eSeconds, 5);
  for (const t of [{ ...traces[0], t_signal_scored: undefined }, { ...traces[0], t_signal_scored: 99 },
    { ...traces[0], t_signal_scored: 999 }]) {
    const result = glassDecisionTraces({ decision_traces: [t] }, true, 110000)[0];
    assert.equal(result.e2eSeconds, null);
    assert.equal(result.stages[result.stages.length - 1]?.timestamp, null);
  }
  assert.deepEqual(glassDecisionTraces({ decision_traces: traces }, false), []);
});
test('latency needs a positive sample count and ordered measured percentiles', () => {
  assert.deepEqual(glassLatency({ count: 4012, p50: 11.4, p95: 26.1, p99: 35.1 }), { count: 4012, p50: 11.4, p95: 26.1, p99: 35.1 });
  for (const row of [{ count: 0, p50: 0, p95: 0, p99: 0 }, { count: 2, p50: 5, p95: 3, p99: 6 },
    { count: 2, p50: '1', p95: 2, p99: 3 }, { count: 1, p50: Infinity, p95: Infinity, p99: Infinity }]) {
    assert.equal(glassLatency(row), null);
  }
});
