import type { TerminalDecisionTrace, TerminalState } from '../hooks/terminalStateContract';
import { evidenceNumber, evidenceRecord, evidenceText } from './warRoomEvidence';
import { evaluateTradingGates } from './tradingGateEvidence';

export function executionGlassState(state: TerminalState | null, isFresh: boolean, streamFresh = false, nowMs = Date.now()) {
  const plan = isFresh ? state?.exchange_action_plan : undefined;
  const available = !!plan;
  const blockers = plan?.global_blockers ?? [];
  const gates = evaluateTradingGates(state, isFresh, streamFresh, nowMs);
  // The analysis receipt never grants execution authority. Use the existing
  // runtime/policy/route evaluator rather than turning its false metadata into a veto.
  const enabled = gates.executionOpen;
  const blocked = blockers.length > 0 || plan?.executor_enabled === false
    || plan?.real_orders_disabled === true || plan?.exchange_mutations_disabled === true
    || plan?.order_intent_publish_enabled === false;
  return { available, enabled, blockers,
    label: !available ? 'Execution unconfirmed' : enabled ? 'Execution enabled' : blocked ? 'Execution held' : 'Execution unconfirmed',
    reason: gates.executionReason,
    analysisReady: gates.analysisReady,
    analysisReason: gates.analysisReason,
    mode: evidenceText(evidenceRecord(plan).mode) ?? 'Mode unreported',
    intent: plan?.order_intent_publish_enabled === true ? 'Enabled' : plan?.order_intent_publish_enabled === false ? 'Disabled' : 'Unconfirmed',
    orders: plan?.real_orders_disabled === false ? 'Permitted by runtime flag' : plan?.real_orders_disabled === true ? 'Disabled' : 'Unconfirmed',
  };
}

export const TRACE_STAGES = [
  ['t_intel_seen', 'Intel seen'], ['t_signal_scored', 'Signal scored'],
  ['t_intent_ready', 'Intent ready'], ['t_exec_dispatched', 'Dispatched'],
  ['t_exchange_ack', 'Venue acknowledgment'], ['t_state_converged', 'State converged'],
] as const;

function traceTime(value: unknown, nowMs: number): number | null {
  const time = evidenceNumber(value);
  return time !== null && time > 0 && time * 1000 <= nowMs + 5000 ? time : null;
}

/** These are recorded decisions, never inferred orders or fills. */
export function glassDecisionTraces(state: TerminalState | null, fresh: boolean, nowMs = Date.now()) {
  if (!fresh || !Array.isArray(state?.decision_traces)) return [];
  return state.decision_traces.filter(trace => evidenceText(trace.decision_trace_id)
    && traceTime(trace.t_intel_seen, nowMs) !== null).map(trace => {
    let previous = 0;
    let chainBroken = false;
    const stages = TRACE_STAGES.map(([key, label]) => {
      const stamp = traceTime(trace[key], nowMs);
      // A timestamp cannot skip a missing predecessor or run backwards.
      const recorded = !chainBroken && stamp !== null && stamp >= previous;
      if (recorded) previous = stamp;
      else chainBroken = true;
      return { key, label, timestamp: recorded ? stamp : null };
    });
    const intel = stages[0].timestamp!;
    const final = stages[stages.length - 1]?.timestamp;
    return { trace, stages, timestamp: intel, e2eSeconds: final != null ? final - intel : null };
  }).sort((a, b) => b.timestamp - a.timestamp);
}

export function glassLatency(value: unknown) {
  const row = evidenceRecord(value);
  const count = evidenceNumber(row.count);
  const p50 = evidenceNumber(row.p50);
  const p95 = evidenceNumber(row.p95);
  const p99 = evidenceNumber(row.p99);
  if (count === null || !Number.isInteger(count) || count <= 0 || p50 === null
      || p95 === null || p99 === null || p50 < 0 || p95 < p50 || p99 < p95) return null;
  return { count, p50, p95, p99 };
}

export const traceName = (trace: TerminalDecisionTrace) =>
  [trace.venue, trace.symbol, trace.side].filter(Boolean).join(' · ');
