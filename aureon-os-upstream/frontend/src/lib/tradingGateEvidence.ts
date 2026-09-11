import type { TerminalState } from '../hooks/terminalStateContract';

type EvidenceRecord = Record<string, unknown>;

const record = (value: unknown): EvidenceRecord =>
  value !== null && typeof value === 'object' && !Array.isArray(value)
    ? value as EvidenceRecord
    : {};

const finite = (value: unknown): number | null =>
  typeof value === 'number' && Number.isFinite(value) ? value : null;

const text = (value: unknown): string | null =>
  typeof value === 'string' && value.trim() ? value.trim() : null;

const stringArray = (value: unknown): string[] | null =>
  Array.isArray(value) && value.every((item) => typeof item === 'string')
    ? value as string[]
    : null;

const epochMs = (value: unknown): number | null => {
  if (typeof value === 'number' && Number.isFinite(value) && value > 0) return value * 1_000;
  if (typeof value !== 'string' || !value.trim()) return null;
  const parsed = Date.parse(value);
  return Number.isFinite(parsed) ? parsed : null;
};

const hasPayload = (value: EvidenceRecord): boolean => Object.keys(value).length > 0;

function everyPassedTimedStep(value: unknown, nowMs: number): boolean {
  if (!Array.isArray(value) || value.length === 0) return false;
  return value.every((item) => {
    const row = record(item);
    const step = text(row.step);
    const timestampMs = epochMs(row.timestamp ?? row.generated_at ?? row.observed_at);
    return row.passed === true
      && step !== null
      && timestampMs !== null
      && timestampMs <= nowMs + 5_000;
  });
}

function currentHncProofAnalysisReady(
  state: TerminalState | null,
  terminalFresh: boolean,
  streamFresh: boolean,
  nowMs: number,
): boolean {
  if (!state || !terminalFresh || !streamFresh || state.ok !== true || state.stale === true) return false;
  const proof = record(state.hnc_cognitive_proof);
  const cycle = record(state.hnc_operating_cycle);
  const proofPassedCount = finite(proof.passed_count);
  const proofStepCount = finite(proof.step_count);
  const cyclePassedCount = finite(cycle.passed_count);
  const cycleStepCount = finite(cycle.step_count);
  const proofGeneratedMs = epochMs(proof.generated_at);
  const cycleGeneratedMs = epochMs(cycle.generated_at);
  return proof.passed === true
    && cycle.passed === true
    && proofPassedCount !== null
    && proofStepCount !== null
    && proofStepCount > 0
    && proofPassedCount === proofStepCount
    && cyclePassedCount !== null
    && cycleStepCount !== null
    && cycleStepCount > 0
    && cyclePassedCount === cycleStepCount
    && proofGeneratedMs !== null
    && proofGeneratedMs <= nowMs + 5_000
    && cycleGeneratedMs !== null
    && cycleGeneratedMs <= nowMs + 5_000
    && everyPassedTimedStep(proof.flow, nowMs);
}

function currentReceipt(row: EvidenceRecord, nowMs: number): boolean {
  if (row.available !== true || row.truth_status !== 'real_derived' || row.generated_values !== false) return false;
  const sourceMs = epochMs(row.source_timestamp ?? row.source_timestamp_iso);
  const expiresMs = epochMs(row.expires_at ?? row.expires_at_iso);
  return sourceMs !== null && expiresMs !== null && sourceMs <= nowMs + 5_000 && expiresMs > nowMs;
}

function receiptWasCurrentWhenGenerated(row: EvidenceRecord, generatedMs: number): boolean {
  if (row.available !== true || row.truth_status !== 'real_derived' || row.generated_values !== false) return false;
  const sourceMs = epochMs(row.source_timestamp ?? row.source_timestamp_iso);
  const expiresMs = epochMs(row.expires_at ?? row.expires_at_iso);
  return sourceMs !== null && expiresMs !== null && sourceMs <= generatedMs + 5_000 && expiresMs >= generatedMs;
}

export type GateReading = {
  available: boolean;
  measurementAvailable: boolean;
  passed: boolean;
  value: string;
  threshold: string;
  reason: string;
};

export type TradingGateEvaluation = {
  receiptFresh: boolean;
  analysisReceiptFresh: boolean;
  policyAvailable: boolean;
  analysisReady: boolean;
  dataFresh: boolean;
  executionOpen: boolean;
  executionReason: string;
  analysisReason: string;
  auris: GateReading;
  lighthouse: GateReading;
  lhe: GateReading;
  qgita: GateReading;
  opportunities: number | null;
};

export function evaluateTradingGates(
  state: TerminalState | null,
  terminalFresh: boolean,
  streamFresh: boolean,
  nowMs = Date.now(),
): TradingGateEvaluation {
  const receipt = record(state?.trading_gate_evidence);
  const receiptHasPayload = hasPayload(receipt);
  const source = record(receipt.source);
  const receiptRootValid = receipt.schema_version === 1
    && receipt.truth_status === 'real_derived'
    && receipt.generated_values === false;
  const receiptFresh = receiptRootValid && currentReceipt(source, nowMs);
  const receiptGeneratedMs = epochMs(receipt.generated_at);
  const analysisReceiptFresh = receiptFresh || Boolean(
    receiptRootValid
    && terminalFresh
    && streamFresh
    && receiptGeneratedMs !== null
    && receiptWasCurrentWhenGenerated(source, receiptGeneratedMs),
  );

  const policy = record(receipt.analysis_policy);
  const requiredGates = stringArray(policy.required_gates);
  const allowedGateNames = new Set(['auris', 'lighthouse', 'lhe', 'qgita']);
  const policyAvailable = analysisReceiptFresh
    && policy.available === true
    && policy.truth_status === 'real_derived'
    && policy.generated_values === false
    && text(policy.source) !== null
    && text(policy.policy_id) !== null
    && epochMs(policy.source_timestamp) !== null
    && epochMs(policy.source_timestamp)! <= nowMs + 5_000
    && requiredGates !== null
    && requiredGates.length > 0
    && requiredGates.every((gate) => allowedGateNames.has(gate));

  const aurisRow = record(receipt.auris);
  const coherence = finite(aurisRow.coherence);
  const aurisMeasurement = analysisReceiptFresh
    && aurisRow.available === true
    && aurisRow.truth_status === 'real_derived'
    && aurisRow.generated_values === false
    && coherence !== null && coherence >= 0 && coherence <= 1;
  const aurisThreshold = finite(policy.auris_min_coherence);
  const aurisAvailable = aurisMeasurement && policyAvailable
    && aurisThreshold !== null && aurisThreshold >= 0 && aurisThreshold <= 1;
  const auris: GateReading = {
    available: aurisAvailable,
    measurementAvailable: aurisMeasurement,
    passed: aurisAvailable && coherence! >= aurisThreshold!,
    value: aurisMeasurement ? coherence!.toFixed(3) : '-',
    threshold: aurisAvailable ? `>= ${aurisThreshold!.toFixed(3)}` : 'policy unavailable',
    reason: aurisMeasurement ? (aurisAvailable ? 'Current provider-derived measurement and policy' : 'Current measurement; policy unavailable') : 'Current provider-derived Auris evidence unavailable',
  };

  const lighthouseRow = record(receipt.lighthouse);
  const lighthouseConfidence = finite(lighthouseRow.confidence);
  const lighthouseMeasurement = analysisReceiptFresh
    && lighthouseRow.available === true
    && lighthouseRow.truth_status === 'real_derived'
    && lighthouseRow.generated_values === false
    && lighthouseConfidence !== null && lighthouseConfidence >= 0 && lighthouseConfidence <= 1;
  const lighthouseThreshold = finite(policy.lighthouse_min_confidence);
  const lighthouseAvailable = lighthouseMeasurement && policyAvailable
    && lighthouseThreshold !== null && lighthouseThreshold >= 0 && lighthouseThreshold <= 1;
  const lighthouse: GateReading = {
    available: lighthouseAvailable,
    measurementAvailable: lighthouseMeasurement,
    passed: lighthouseAvailable && lighthouseConfidence! >= lighthouseThreshold!,
    value: lighthouseMeasurement ? lighthouseConfidence!.toFixed(3) : '-',
    threshold: lighthouseAvailable ? `>= ${lighthouseThreshold!.toFixed(3)}` : 'source or policy unavailable',
    reason: lighthouseMeasurement ? (lighthouseAvailable ? 'Current provider-derived Lighthouse measurement and policy' : 'Current measurement; policy unavailable') : 'Current Lighthouse runtime evidence unavailable',
  };

  const lheRow = record(receipt.lhe);
  const lheRequired = typeof policy.lhe_required === 'boolean' ? policy.lhe_required : null;
  const isLhe = typeof lheRow.is_lhe === 'boolean' ? lheRow.is_lhe : null;
  const lheMeasurement = analysisReceiptFresh
    && lheRow.available === true
    && lheRow.truth_status === 'real_derived'
    && lheRow.generated_values === false
    && isLhe !== null;
  const lheAvailable = policyAvailable && lheRequired !== null && (!lheRequired || lheMeasurement);
  const lhe: GateReading = {
    available: lheAvailable,
    measurementAvailable: lheMeasurement,
    passed: lheAvailable && (!lheRequired || isLhe === true),
    value: lheRequired === null ? '-' : lheRequired ? (lheMeasurement ? (isLhe ? 'yes' : 'no') : '-') : 'not required',
    threshold: lheRequired === null ? 'policy unavailable' : lheRequired ? 'required' : 'not required',
    reason: lheAvailable ? 'Current LHE policy evaluated' : 'Current LHE evidence or policy unavailable',
  };

  const qgitaRow = record(receipt.qgita);
  const qgitaTier = text(qgitaRow.tier);
  const allowedTiers = stringArray(policy.allowed_qgita_tiers);
  const qgitaMeasurement = analysisReceiptFresh
    && qgitaRow.available === true
    && qgitaRow.truth_status === 'real_derived'
    && qgitaRow.generated_values === false
    && qgitaTier !== null;
  const qgitaAvailable = qgitaMeasurement && policyAvailable && allowedTiers !== null && allowedTiers.length > 0;
  const qgita: GateReading = {
    available: qgitaAvailable,
    measurementAvailable: qgitaMeasurement,
    passed: qgitaAvailable && allowedTiers!.includes(qgitaTier!),
    value: qgitaMeasurement ? qgitaTier! : '-',
    threshold: qgitaAvailable ? `allowed: ${allowedTiers!.join(', ')}` : 'source or policy unavailable',
    reason: qgitaMeasurement ? (qgitaAvailable ? 'Current provider-derived QGITA tier and policy' : 'Current tier; policy unavailable') : 'Current QGITA runtime evidence unavailable',
  };

  const readingByName: Record<string, GateReading> = { auris, lighthouse, lhe, qgita };
  const gateLabels: Record<string, string> = {
    auris: 'Auris coherence',
    lighthouse: 'Lighthouse confidence',
    lhe: 'LHE check',
    qgita: 'QGITA tier',
  };
  const failedRequiredGates = policyAvailable && requiredGates !== null
    ? requiredGates.filter((gate) => readingByName[gate]?.passed !== true)
    : [];
  const receiptAnalysisReady = receipt.analysis_ready === true
    && policyAvailable
    && requiredGates !== null
    && failedRequiredGates.length === 0;
  const hncProofFallbackReady = !receiptHasPayload
    && currentHncProofAnalysisReady(state, terminalFresh, streamFresh, nowMs);
  const analysisReady = receiptAnalysisReady || hncProofFallbackReady;
  const analysisReason = receiptAnalysisReady
    ? 'Required analysis gates passed'
    : hncProofFallbackReady
      ? 'HNC proof flow passed with current terminal-state data; trading-gate receipt unavailable'
      : !analysisReceiptFresh
        ? 'Fresh trading-gate evidence required'
        : !policyAvailable
          ? 'Required analysis policy unavailable'
          : failedRequiredGates.length > 0
            ? failedRequiredGates.map((gate) => {
                const reading = readingByName[gate];
                if (!reading) return `${gateLabels[gate] ?? gate} unavailable`;
                if (reading.available) return `${gateLabels[gate] ?? gate} below policy threshold`;
                return reading.measurementAvailable
                  ? `${gateLabels[gate] ?? gate} policy unavailable`
                  : `${gateLabels[gate] ?? gate} unavailable`;
              }).join('; ')
            : 'Required analysis evidence unavailable';
  const streamUsable = state?.live_stream_cache?.usable_for_decision;
  const streamRowCount = finite(state?.live_stream_cache?.symbol_count)
    ?? (Array.isArray(state?.live_stream_cache?.quotes) ? state.live_stream_cache.quotes.length : null);
  const dataFresh = Boolean(
    state
    && terminalFresh
    && streamFresh
    && state.ok === true
    && state.stale === false
    && (
      streamUsable === true
      || (streamUsable !== false && streamRowCount !== null && streamRowCount > 0)
    ),
  );

  const plan = state?.exchange_action_plan;
  const blockers = stringArray(plan?.global_blockers);
  const clearances = stringArray(
    plan?.runtime_clearances_required
      ?? plan?.runtime_clearances
      ?? plan?.global_clearances,
  );
  const executionOpen = Boolean(
    dataFresh
    && analysisReady
    && receiptFresh
    && state?.trading_ready === true
    && plan?.executor_enabled === true
    && plan?.order_intent_publish_enabled === true
    && plan?.live_enabled === true
    && plan?.real_orders_disabled === false
    && plan?.exchange_mutations_disabled === false
    && plan?.trade_path_state === 'available'
    && blockers !== null && blockers.length === 0
    && clearances !== null && clearances.length === 0,
  );
  const executionReason = executionOpen
    ? 'All current runtime, policy, route, and authority checks passed'
    : !dataFresh
      ? 'Fresh completed tick and direct market stream required'
      : !analysisReady
        ? analysisReason
        : plan?.live_enabled !== true || plan?.real_orders_disabled !== false || plan?.exchange_mutations_disabled !== false
          ? 'Order or exchange mutation hold remains'
        : !receiptFresh
          ? 'Current trading-gate source receipt expired'
        : plan?.order_intent_publish_enabled !== true
            ? 'Order-intent publication disabled'
            : plan?.trade_path_state !== 'available'
              ? 'Runtime trade path unavailable'
              : blockers === null || blockers.length > 0 || clearances === null || clearances.length > 0
                ? 'Runtime blockers or clearances remain'
                : 'Executor or route readiness unavailable';

  const opportunityRow = record(receipt.opportunities);
  const opportunityCount = finite(opportunityRow.active_order_flow_count);
  const opportunityFresh = currentReceipt(opportunityRow, nowMs)
    || Boolean(receiptGeneratedMs !== null && receiptWasCurrentWhenGenerated(opportunityRow, receiptGeneratedMs));
  const opportunities = analysisReceiptFresh && dataFresh && opportunityFresh
    && opportunityCount !== null
    && Number.isInteger(opportunityCount)
    && opportunityCount >= 0
      ? opportunityCount
      : null;

  return {
    receiptFresh,
    analysisReceiptFresh,
    policyAvailable,
    analysisReady,
    dataFresh,
    executionOpen,
    executionReason,
    analysisReason,
    auris,
    lighthouse,
    lhe,
    qgita,
    opportunities,
  };
}
