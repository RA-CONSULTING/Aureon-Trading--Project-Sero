import type { TerminalState } from '@/hooks/useTerminalState';

export type EvidenceRecord = Record<string, unknown>;
export const evidenceRecord = (value: unknown): EvidenceRecord =>
  value !== null && typeof value === 'object' && !Array.isArray(value)
    ? value as EvidenceRecord : {};
export const evidenceNumber = (value: unknown): number | null =>
  typeof value === 'number' && Number.isFinite(value) ? value : null;
export const evidenceText = (value: unknown): string | null =>
  typeof value === 'string' && value.trim() ? value.trim() : null;

export type AurisReading = { name: string; value: number; role: string | null };
export type RuntimeReading = { name: string; evaluated: boolean; status: string };
export type CycleReading = { step: string; passed: boolean | null; answer: string | null };
export type RuntimeMetric = {
  available: boolean;
  value: number | null;
  status: string;
  source: string | null;
  timestamp: string | null;
};
export type ProviderPositionVenue = {
  available: boolean;
  reason: string;
  count: number | null;
  source: string | null;
  timestamp: string | null;
  positions: EvidenceRecord[];
};
export type EcosystemMetric = {
  available: boolean;
  reason: string;
  systems: Record<string, RuntimeMetric>;
  globalResonance: number | null;
  marketEnergy: number | null;
  ecosystemCoherence: number | null;
  dominantFrequency: number | null;
  activeWaveforms: string[] | null;
  source: string | null;
  timestamp: string | null;
};
export type PrimeSealMetric = {
  available: boolean;
  reason: string;
  primeCoherence: number | null;
  sealLock: boolean | null;
  systemsContributing: string[];
  consensusSignal: string | null;
  intentText: string | null;
  packetValue: number | null;
  source: string | null;
  timestamp: string | null;
};
export type ProbabilityFusionMetric = {
  available: boolean;
  reason: string;
  fusedProbability: number | null;
  action: string | null;
  confidence: number | null;
  waveState: string | null;
  harmonicLock: boolean | null;
  probability6D: number | null;
  probabilityHNC: number | null;
  probabilityLighthouse: number | null;
  weight6D: number | null;
  weightHNC: number | null;
  weightLighthouse: number | null;
  resonanceBoost: number | null;
  source: string | null;
  timestamp: string | null;
};
export type PrismReceipt = {
  available: boolean;
  reason: string;
  frequency: number | null;
  state: string | null;
  level: number | null;
  resonance: number | null;
  harmonicPurity: number | null;
  isLoveLocked: boolean | null;
  layers: Record<string, number> | null;
  source: string | null;
  timestamp: string | null;
};
export type WarRoomEvidence = {
  available: boolean;
  reason: string;
  timestamp: string | null;
  sourceCount: number | null;
  sourceNames: string[];
  symbolCount: number | null;
  priceCount: number | null;
  aurisCoherence: number | null;
  nodes: AurisReading[];
  systems: RuntimeReading[];
  cycle: CycleReading[];
  actionState: string | null;
  lighthouseConfidence: RuntimeMetric;
  masterFormula: RuntimeMetric;
  prismState: RuntimeMetric;
  prismReceipt: PrismReceipt;
  rainbowBridge: RuntimeMetric;
  probabilityFusion: ProbabilityFusionMetric;
  providerPositions: Record<string, ProviderPositionVenue>;
  ecosystem: EcosystemMetric;
  primeSeal: PrimeSealMetric;
};

const unavailableMetric = (status: string): RuntimeMetric => ({
  available: false,
  value: null,
  status,
  source: null,
  timestamp: null,
});

const unavailablePrismReceipt = (reason: string): PrismReceipt => ({
  available: false,
  reason,
  frequency: null,
  state: null,
  level: null,
  resonance: null,
  harmonicPurity: null,
  isLoveLocked: null,
  layers: null,
  source: null,
  timestamp: null,
});

const unavailableEcosystemMetric = (reason: string): EcosystemMetric => ({
  available: false, reason, systems: {}, globalResonance: null, marketEnergy: null,
  ecosystemCoherence: null, dominantFrequency: null, activeWaveforms: null, source: null, timestamp: null,
});
const unavailablePrimeSealMetric = (reason: string): PrimeSealMetric => ({
  available: false, reason, primeCoherence: null, sealLock: null, systemsContributing: [],
  consensusSignal: null, intentText: null, packetValue: null, source: null, timestamp: null,
});
const unavailableProbabilityFusionMetric = (reason: string): ProbabilityFusionMetric => ({
  available: false, reason, fusedProbability: null, action: null, confidence: null, waveState: null,
  harmonicLock: null, probability6D: null, probabilityHNC: null, probabilityLighthouse: null,
  weight6D: null, weightHNC: null, weightLighthouse: null, resonanceBoost: null, source: null, timestamp: null,
});

const unavailable = (reason: string, timestamp: string | null = null): WarRoomEvidence => ({
  available: false, reason, timestamp, sourceCount: null, sourceNames: [],
  symbolCount: null, priceCount: null, aurisCoherence: null, nodes: [], systems: [], cycle: [], actionState: null,
  lighthouseConfidence: unavailableMetric('Current Lighthouse runtime evidence unavailable.'),
  masterFormula: unavailableMetric('Fresh HNC master-formula runtime evidence unavailable.'),
  prismState: unavailableMetric('No timestamped Prism runtime receipt is published.'),
  prismReceipt: unavailablePrismReceipt('No timestamped Prism runtime receipt is published.'),
  rainbowBridge: unavailableMetric('No timestamped Rainbow Bridge runtime receipt is published.'),
  probabilityFusion: unavailableProbabilityFusionMetric('No timestamped ProbabilityMatrix runtime receipt is published.'),
  providerPositions: {},
  ecosystem: unavailableEcosystemMetric('No runtime-backed Ecosystem receipt is published.'),
  primeSeal: unavailablePrimeSealMetric('No fresh runtime seal observation is published.'),
});

const epochMs = (value: unknown): number | null => {
  if (typeof value === 'number' && Number.isFinite(value) && value > 0) return value * 1_000;
  const text = evidenceText(value);
  if (!text) return null;
  const parsed = Date.parse(text);
  return Number.isFinite(parsed) ? parsed : null;
};

const sourceReceiptCurrent = (row: EvidenceRecord, nowMs: number, maxAgeMs = 60_000): boolean => {
  if (row.available !== true || row.truth_status !== 'real_derived' || row.generated_values !== false) return false;
  const sourceMs = epochMs(row.source_timestamp ?? row.source_timestamp_iso);
  if (sourceMs === null || sourceMs <= 0 || sourceMs > nowMs + 5_000) return false;
  const expiresMs = epochMs(row.expires_at ?? row.expires_at_iso);
  if (expiresMs !== null) return expiresMs > nowMs;
  return nowMs - sourceMs <= maxAgeMs;
};

const sourceReceiptWasCurrentWhenGenerated = (row: EvidenceRecord, generatedMs: number): boolean => {
  if (row.available !== true || row.truth_status !== 'real_derived' || row.generated_values !== false) return false;
  const sourceMs = epochMs(row.source_timestamp ?? row.source_timestamp_iso);
  const expiresMs = epochMs(row.expires_at ?? row.expires_at_iso);
  return sourceMs !== null && expiresMs !== null && sourceMs <= generatedMs + 5_000 && expiresMs >= generatedMs;
};

function readPrismReceipt(value: unknown, nowMs: number): PrismReceipt {
  if (value === undefined || value === null) {
    return unavailablePrismReceipt('No timestamped Prism runtime receipt is published.');
  }
  const row = evidenceRecord(value);
  if (!sourceReceiptCurrent(row, nowMs)) {
    return unavailablePrismReceipt('Prism runtime receipt is stale or has no valid source timestamp.');
  }
  const frequency = evidenceNumber(row.frequency);
  const level = evidenceNumber(row.level);
  const resonance = evidenceNumber(row.resonance);
  const harmonicPurity = evidenceNumber(row.harmonic_purity);
  const state = evidenceText(row.state);
  const isLoveLocked = typeof row.love_locked === 'boolean' ? row.love_locked : null;
  if (frequency === null || level === null || !Number.isInteger(level) || level < 0 || level > 5 || state === null) {
    return unavailablePrismReceipt('Prism runtime receipt is missing required measured fields.');
  }
  const rawLayers = evidenceRecord(row.layers);
  const layers = Object.entries(rawLayers).reduce<Record<string, number>>((acc, [key, value]) => {
    const num = evidenceNumber(value);
    if (num !== null) acc[key] = num;
    return acc;
  }, {});
  return {
    available: true,
    reason: 'Current Prism runtime receipt observed.',
    frequency,
    state,
    level,
    resonance: resonance !== null && resonance >= 0 && resonance <= 1 ? resonance : null,
    harmonicPurity: harmonicPurity !== null && harmonicPurity >= 0 && harmonicPurity <= 1 ? harmonicPurity : null,
    isLoveLocked,
    layers: Object.keys(layers).length > 0 ? layers : null,
    source: evidenceText(row.source),
    timestamp: evidenceText(row.source_timestamp_iso) ?? (typeof row.source_timestamp === 'number' ? new Date(row.source_timestamp * 1_000).toISOString() : null),
  };
}

const proofTimestampCurrent = (timestamp: string | null, ageLimitSec: number, nowMs: number): boolean => {
  const measuredAt = timestamp ? Date.parse(timestamp) : NaN;
  return Number.isFinite(measuredAt) && measuredAt <= nowMs + 5_000 && nowMs - measuredAt <= ageLimitSec * 1_000;
};

/** Accept source observations, never browser registrations or default numeric fields. */
export function readWarRoomEvidence(
  state: TerminalState | null, terminalFresh: boolean, nowMs = Date.now(),
): WarRoomEvidence {
  if (!terminalFresh || !state) return unavailable('Fresh runtime evidence is unavailable.');
  const proof = evidenceRecord(state.hnc_cognitive_proof);
  const timestamp = evidenceText(proof.generated_at);
  const watchdog = evidenceRecord(state.runtime_watchdog);
  const ageLimit = evidenceNumber(watchdog.tick_stale_after_sec) ?? 45;
  if (!proofTimestampCurrent(timestamp, ageLimit, nowMs)) {
    return unavailable('HNC source observation is missing, stale, or has an invalid timestamp.', timestamp);
  }
  const source = evidenceRecord(proof.real_data);
  if (source.passed !== true || proof.status === 'no_data') {
    return unavailable('The runtime has not verified fresh provider data for this HNC observation.', timestamp);
  }
  const auris = evidenceRecord(proof.auris_nodes);
  const aurisAvailable = auris.evaluated === true && auris.data_status === 'live';
  const nodes = aurisAvailable ? Object.entries(evidenceRecord(auris.nodes)).flatMap(([name, raw]) => {
    const row = evidenceRecord(raw);
    const value = evidenceNumber(row.value);
    return value !== null && value >= 0 && value <= 1
      ? [{ name, value, role: evidenceText(row.role) }] : [];
  }) : [];

  const master = evidenceRecord(proof.master_formula);
  const masterScore = evidenceNumber(master.score);
  const masterTimestamp = evidenceText(master.timestamp) ?? timestamp;
  const masterFormula = master.evaluated === true
    && master.passed === true
    && masterScore !== null
    && masterScore >= 0
    && masterScore <= 1
    && proofTimestampCurrent(masterTimestamp, ageLimit, nowMs)
    ? {
        available: true,
        value: masterScore,
        status: 'Runtime master formula evaluated.',
        source: evidenceText(master.source),
        timestamp: masterTimestamp,
      }
    : unavailableMetric('Fresh HNC master-formula runtime evidence unavailable.');

  const gate = evidenceRecord(state.trading_gate_evidence);
  const lighthouseRow = evidenceRecord(gate.lighthouse);
  const lighthouseConfidence = evidenceNumber(lighthouseRow.confidence);
  const lighthouseSource = evidenceRecord(gate.source);
  const lighthouseTimestamp = evidenceText(lighthouseRow.source_timestamp_iso) ?? evidenceText(lighthouseSource.source_timestamp_iso);
  const lighthouseSourceCurrent = sourceReceiptCurrent(lighthouseSource, nowMs);
  const gateGeneratedMs = epochMs(gate.generated_at);
  const streamFresh = evidenceRecord(state.live_stream_cache).fresh === true;
  const lighthouseSourceValidAtGate = Boolean(
    streamFresh
    && gateGeneratedMs !== null
    && sourceReceiptWasCurrentWhenGenerated(lighthouseSource, gateGeneratedMs),
  );
  const lighthouseConfidenceMetric = (lighthouseSourceCurrent || lighthouseSourceValidAtGate)
    && lighthouseRow.available === true
    && lighthouseRow.truth_status === 'real_derived'
    && lighthouseRow.generated_values === false
    && lighthouseConfidence !== null
    && lighthouseConfidence >= 0
    && lighthouseConfidence <= 1
    ? {
        available: true,
        value: lighthouseConfidence,
        status: lighthouseSourceCurrent
          ? 'Current provider-derived Lighthouse receipt observed.'
          : 'Completed-tick provider-derived Lighthouse receipt observed.',
        source: evidenceText(lighthouseRow.source) ?? evidenceText(lighthouseSource.reason),
        timestamp: lighthouseTimestamp,
      }
    : unavailableMetric('Current Lighthouse runtime evidence unavailable or expired.');

  const prismReceipt = readPrismReceipt(state.prism_receipt, nowMs);
  const prismState: RuntimeMetric = prismReceipt.available
    ? {
        available: true,
        value: prismReceipt.frequency,
        status: `Prism state ${prismReceipt.state}`,
        source: prismReceipt.source,
        timestamp: prismReceipt.timestamp,
      }
    : unavailableMetric(prismReceipt.reason);

  const fusionRow = evidenceRecord(state.probability_fusion_receipt ?? proof.probability_fusion);
  const fusionValue = evidenceNumber(fusionRow.fused_probability ?? fusionRow.fusedProbability);
  const fusionReceiptCurrent = sourceReceiptCurrent(fusionRow, nowMs);
  const probabilityFusion: ProbabilityFusionMetric = fusionReceiptCurrent
    && fusionValue !== null
    && fusionValue >= 0
    && fusionValue <= 1
    ? {
        available: true,
        reason: 'Current ProbabilityMatrix runtime receipt observed.',
        fusedProbability: fusionValue,
        action: evidenceText(fusionRow.action),
        confidence: (() => {
          const c = evidenceNumber(fusionRow.confidence);
          return c !== null && c >= 0 && c <= 1 ? c : null;
        })(),
        waveState: evidenceText(fusionRow.wave_state ?? fusionRow.waveState),
        harmonicLock: typeof (fusionRow.harmonic_lock ?? fusionRow.harmonicLock) === 'boolean'
          ? (fusionRow.harmonic_lock ?? fusionRow.harmonicLock) as boolean : null,
        probability6D: evidenceNumber(fusionRow.probability_6d ?? fusionRow.probability6D),
        probabilityHNC: evidenceNumber(fusionRow.probability_hnc ?? fusionRow.probabilityHNC),
        probabilityLighthouse: evidenceNumber(fusionRow.probability_lighthouse ?? fusionRow.probabilityLighthouse),
        weight6D: evidenceNumber(fusionRow.weight_6d ?? fusionRow.weight6D),
        weightHNC: evidenceNumber(fusionRow.weight_hnc ?? fusionRow.weightHNC),
        weightLighthouse: evidenceNumber(fusionRow.weight_lighthouse ?? fusionRow.weightLighthouse),
        resonanceBoost: evidenceNumber(fusionRow.resonance_boost ?? fusionRow.resonanceBoost),
        source: evidenceText(fusionRow.source),
        timestamp: evidenceText(fusionRow.source_timestamp_iso)
          ?? (typeof fusionRow.source_timestamp === 'number' ? new Date(fusionRow.source_timestamp * 1_000).toISOString() : null),
      }
    : unavailableProbabilityFusionMetric('No timestamped ProbabilityMatrix runtime receipt is published.');

  const systems = Object.entries(evidenceRecord(proof.systems)).map(([key, raw]) => {
    const row = evidenceRecord(raw);
    const reading = evidenceRecord(row.runtime_reading);
    const evaluated = reading.evaluated === true;
    if (key === 'hnc_master_protocol' && masterFormula.available) {
      return {
        name: evidenceText(row.name) ?? 'HNC master protocol',
        evaluated: true,
        status: 'Runtime master formula evaluated.',
      };
    }
    if (key === 'auris_nodes' && aurisAvailable) {
      return {
        name: evidenceText(row.name) ?? 'Auris nodes',
        evaluated: true,
        status: 'Runtime Auris nodes evaluated.',
      };
    }
    if (key === 'hnc_probability_matrix' && row.present === true && row.passed === true) {
      return {
        name: evidenceText(row.name) ?? 'HNC probability matrix',
        evaluated: false,
        status: 'Contract verified; timestamped runtime matrix reading unavailable.',
      };
    }
    return {
      name: evidenceText(row.name) ?? key.replaceAll('_', ' '),
      evaluated,
      status: evaluated ? 'Runtime reading received.' : 'Runtime reading unavailable.',
    };
  });
  const cycleSource = evidenceRecord(proof.operating_cycle ?? state.hnc_operating_cycle);
  const rows = Array.isArray(cycleSource.questions) ? cycleSource.questions : [];
  const cycle = rows.flatMap((raw) => {
    const row = evidenceRecord(raw);
    const step = evidenceText(row.step);
    // The old how/act answers include shadow-validation/model blends.
    if (!step || !['who', 'what', 'where', 'when'].includes(step)) return [];
    return [{ step, passed: typeof row.passed === 'boolean' ? row.passed : null, answer: evidenceText(row.answer) }];
  });
  const coherence = aurisAvailable ? evidenceNumber(auris.coherence) : null;

  const providerPositions = readProviderPositions(state.provider_positions, nowMs);
  const ecosystem = readEcosystemMetric(state.ecosystem_receipt, nowMs);
  const primeSeal = readPrimeSealMetric(state.prime_seal_receipt, nowMs);

  return {
    available: true, reason: 'Provider-backed runtime observation', timestamp,
    sourceCount: evidenceNumber(source.source_count), symbolCount: evidenceNumber(source.symbol_count),
    sourceNames: Array.isArray(source.source_names) ? source.source_names.filter((name): name is string => typeof name === 'string' && Boolean(name.trim())) : [],
    priceCount: evidenceNumber(source.price_count),
    aurisCoherence: coherence !== null && coherence >= 0 && coherence <= 1 ? coherence : null,
    nodes, systems, cycle, actionState: evidenceText(state.exchange_action_plan?.trade_path_state),
    lighthouseConfidence: lighthouseConfidenceMetric,
    masterFormula,
    prismState,
    prismReceipt,
    rainbowBridge: unavailableMetric('No timestamped Rainbow Bridge runtime receipt is published.'),
    probabilityFusion,
    providerPositions,
    ecosystem,
    primeSeal,
  };
}

function readProviderPositions(value: unknown, nowMs: number): Record<string, ProviderPositionVenue> {
  const root = evidenceRecord(value);
  const result: Record<string, ProviderPositionVenue> = {};
  for (const [key, raw] of Object.entries(root)) {
    const row = evidenceRecord(raw);
    const available = row.available === true && row.truth_status === 'real_derived' && row.generated_values === false
      && sourceReceiptCurrent(row, nowMs);
    const count = evidenceNumber(row.count);
    const positions = Array.isArray(row.positions) ? row.positions.map(evidenceRecord) : [];
    result[key] = {
      available,
      reason: available ? 'Current provider position receipt observed.' : evidenceText(row.reason) ?? 'Provider position receipt unavailable or stale.',
      count: count !== null && Number.isInteger(count) && count >= 0 ? count : positions.length,
      source: evidenceText(row.source),
      timestamp: evidenceText(row.source_timestamp_iso) ?? (typeof row.source_timestamp === 'number' ? new Date(row.source_timestamp * 1_000).toISOString() : null),
      positions,
    };
  }
  return result;
}

function readEcosystemMetric(value: unknown, nowMs: number): EcosystemMetric {
  const row = evidenceRecord(value);
  const current = sourceReceiptCurrent(row, nowMs);
  const systems: Record<string, RuntimeMetric> = {};
  const systemRows = evidenceRecord(row.systems);
  for (const [name, raw] of Object.entries(systemRows)) {
    const sys = evidenceRecord(raw);
    const available = current && sys.available === true && sys.truth_status === 'real_derived' && sys.generated_values === false;
    const coherence = evidenceNumber(sys.coherence ?? sys.value);
    systems[name] = {
      available,
      value: coherence !== null && coherence >= 0 && coherence <= 1 ? coherence : null,
      status: available ? evidenceText(sys.status) ?? `Runtime ${name} observed.` : evidenceText(sys.reason) ?? `Runtime ${name} evidence unavailable.`,
      source: evidenceText(sys.source ?? row.source),
      timestamp: evidenceText(sys.source_timestamp_iso ?? row.source_timestamp_iso)
        ?? (typeof (sys.source_timestamp ?? row.source_timestamp) === 'number'
          ? new Date((sys.source_timestamp ?? row.source_timestamp) as number * 1_000).toISOString() : null),
    };
  }
  const globalResonance = evidenceNumber(row.global_resonance);
  const marketEnergy = evidenceNumber(row.market_energy);
  const ecosystemCoherence = evidenceNumber(row.ecosystem_coherence);
  const dominantFrequency = evidenceNumber(row.dominant_frequency);
  const activeWaveforms = Array.isArray(row.active_waveforms)
    ? row.active_waveforms.filter((item): item is string => typeof item === 'string') : null;
  return {
    available: current,
    reason: current ? 'Current ecosystem runtime receipt observed.' : evidenceText(row.reason) ?? 'Ecosystem runtime receipt unavailable or stale.',
    systems,
    globalResonance: globalResonance !== null && globalResonance >= 0 && globalResonance <= 1 ? globalResonance : null,
    marketEnergy: marketEnergy !== null && marketEnergy >= 0 ? marketEnergy : null,
    ecosystemCoherence: ecosystemCoherence !== null && ecosystemCoherence >= 0 && ecosystemCoherence <= 1 ? ecosystemCoherence : null,
    dominantFrequency: dominantFrequency !== null && dominantFrequency > 0 ? dominantFrequency : null,
    activeWaveforms: activeWaveforms?.length ? activeWaveforms : null,
    source: evidenceText(row.source),
    timestamp: evidenceText(row.source_timestamp_iso) ?? (typeof row.source_timestamp === 'number' ? new Date(row.source_timestamp * 1_000).toISOString() : null),
  };
}

function readPrimeSealMetric(value: unknown, nowMs: number): PrimeSealMetric {
  const row = evidenceRecord(value);
  const current = sourceReceiptCurrent(row, nowMs);
  const primeCoherence = evidenceNumber(row.prime_coherence);
  const sealLock = typeof row.seal_lock === 'boolean' ? row.seal_lock : null;
  const systemsContributing = Array.isArray(row.systems_contributing)
    ? row.systems_contributing.filter((item): item is string => typeof item === 'string') : [];
  return {
    available: current,
    reason: current ? 'Current Prime Seal runtime receipt observed.' : evidenceText(row.reason) ?? 'Prime Seal runtime receipt unavailable or stale.',
    primeCoherence: primeCoherence !== null && primeCoherence >= 0 && primeCoherence <= 1 ? primeCoherence : null,
    sealLock,
    systemsContributing,
    consensusSignal: evidenceText(row.consensus_signal),
    intentText: evidenceText(row.intent_text),
    packetValue: evidenceNumber(row.packet_value),
    source: evidenceText(row.source),
    timestamp: evidenceText(row.source_timestamp_iso) ?? (typeof row.source_timestamp === 'number' ? new Date(row.source_timestamp * 1_000).toISOString() : null),
  };
}
