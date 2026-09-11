import assert from 'node:assert/strict';
import test from 'node:test';
import type { TerminalState } from '../hooks/useTerminalState';
import { readWarRoomEvidence } from './warRoomEvidence';

const now = Date.parse('2026-09-08T10:00:00Z');
const observed = new Date(now - 5_000).toISOString();
function sourceProof(overrides: Record<string, unknown> = {}): TerminalState {
  return {
    live_stream_cache: { fresh: true },
    hnc_cognitive_proof: {
      generated_at: observed, status: 'attention',
      real_data: { passed: true, source_count: 2, symbol_count: 6, price_count: 8 },
      auris_nodes: {
        evaluated: true, data_status: 'live', coherence: 0.4,
        nodes: { Tiger: { value: 0, weight: 1, freq: 220, role: 'volatility' }, Falcon: { value: 0.8, weight: 1.2 } },
      },
      systems: { registered: { passed: true }, seer: { runtime_reading: { evaluated: true } } },
      ...overrides,
    },
  };
}

function gateReceipt(overrides: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    source: {
      available: true,
      truth_status: 'real_derived',
      generated_values: false,
      source_timestamp: (now - 2_000) / 1_000,
      expires_at: (now + 10_000) / 1_000,
    },
    lighthouse: {
      available: true,
      truth_status: 'real_derived',
      generated_values: false,
      confidence: 0.72,
      source: 'state/lighthouse_event.jsonl',
      source_timestamp_iso: new Date(now - 2_000).toISOString(),
    },
    ...overrides,
  };
}

test('transport freshness cannot turn absent provider proof into data', () => {
  assert.equal(readWarRoomEvidence(null, true, now).available, false);
  assert.equal(readWarRoomEvidence({}, true, now).available, false);
  assert.equal(readWarRoomEvidence(sourceProof({ real_data: { passed: false } }), true, now).available, false);
  assert.equal(readWarRoomEvidence(sourceProof({ status: 'no_data' }), true, now).available, false);
});

test('stale or future source proof fails closed even with fresh runtime', () => {
  for (const generated_at of ['invalid', new Date(now - 60_000).toISOString(), new Date(now + 6_000).toISOString()]) {
    assert.equal(readWarRoomEvidence(sourceProof({ generated_at }), true, now).available, false);
  }
  assert.equal(readWarRoomEvidence(sourceProof(), false, now).available, false);
});

test('node readings use observed value, preserving real zero and never model weight or frequency', () => {
  const result = readWarRoomEvidence(sourceProof(), true, now);
  assert.equal(result.available, true);
  assert.equal(result.nodes.length, 2);
  assert.equal(result.nodes[0].value, 0);
  assert.equal(result.nodes[1].value, 0.8);
  assert.equal('weight' in result.nodes[0], false);
  assert.equal('freq' in result.nodes[0], false);
  assert.equal(result.systems[0].evaluated, false);
  assert.equal(result.systems[1].evaluated, true);
});

test('missing, invalid or unevaluated node data remains unavailable', () => {
  const source = sourceProof({ auris_nodes: { evaluated: false, data_status: 'no_data', coherence: 0, nodes: {} } });
  assert.equal(readWarRoomEvidence(source, true, now).aurisCoherence, null);
  assert.deepEqual(readWarRoomEvidence(source, true, now).nodes, []);
  const invalid = sourceProof({ auris_nodes: { evaluated: true, data_status: 'live', coherence: NaN,
    nodes: { Missing: { weight: 1 }, Nan: { value: NaN }, Negative: { value: -1 }, Oversize: { value: 1.1 } } } });
  assert.deepEqual(readWarRoomEvidence(invalid, true, now).nodes, []);
  assert.equal(readWarRoomEvidence(invalid, true, now).aurisCoherence, null);
});

test('fresh master formula is exposed as analysis metric but never replaces Auris coherence', () => {
  const source = sourceProof({ master_formula: {
    evaluated: true, passed: true, score: 0.9, source: 'runtime blend', timestamp: observed,
  }, operating_cycle: {
    questions: [{ step: 'what', passed: true, answer: 'Provider observation' },
      { step: 'how', passed: true, answer: 'Contains shadow blend' },
      { step: 'act', passed: true, answer: 'shadow_validate_and_measure' }],
  } });
  const result = readWarRoomEvidence(source, true, now);
  assert.equal(result.masterFormula.available, true);
  assert.equal(result.masterFormula.value, 0.9);
  assert.equal(result.aurisCoherence, 0.4);
  assert.deepEqual(result.cycle.map((row) => row.step), ['what']);
});

test('fresh trading-gate Lighthouse receipt is exposed only while its source receipt is current', () => {
  const result = readWarRoomEvidence({ ...sourceProof(), trading_gate_evidence: gateReceipt() }, true, now);
  assert.equal(result.lighthouseConfidence.available, true);
  assert.equal(result.lighthouseConfidence.value, 0.72);
  const expired = readWarRoomEvidence({ ...sourceProof(), trading_gate_evidence: gateReceipt({
    source: { available: true, truth_status: 'real_derived', generated_values: false, source_timestamp: (now - 20_000) / 1_000, expires_at: (now - 1_000) / 1_000 },
  }) }, true, now);
  assert.equal(expired.lighthouseConfidence.available, false);
});

test('completed-tick Lighthouse receipt remains visible while terminal and stream evidence are fresh', () => {
  const generatedAt = now - 3_000;
  const completedTickSource = {
    available: true,
    truth_status: 'real_derived',
    generated_values: false,
    source_timestamp: (now - 7_000) / 1_000,
    expires_at: (now - 1_000) / 1_000,
  };
  const result = readWarRoomEvidence({
    ...sourceProof(),
    trading_gate_evidence: gateReceipt({
      generated_at: new Date(generatedAt).toISOString(),
      source: completedTickSource,
    }),
  }, true, now);
  assert.equal(result.lighthouseConfidence.available, true);
  assert.equal(result.lighthouseConfidence.status, 'Completed-tick provider-derived Lighthouse receipt observed.');
});

test('Prism and Rainbow Bridge remain unavailable without timestamped runtime receipts', () => {
  const result = readWarRoomEvidence(sourceProof({ master_formula: {
    evaluated: true, passed: true, score: 0.9, source: 'runtime blend', timestamp: observed,
  } }), true, now);
  assert.equal(result.prismState.available, false);
  assert.equal(result.rainbowBridge.available, false);
  assert.match(result.prismState.status, /No timestamped Prism/);
  assert.match(result.rainbowBridge.status, /No timestamped Rainbow Bridge/);
});

test('fresh terminal-state Prism receipt is exposed as Prism state and receipt', () => {
  const result = readWarRoomEvidence({
    ...sourceProof(),
    prism_receipt: {
      available: true,
      truth_status: 'real_derived',
      generated_values: false,
      source_timestamp: (now - 2_000) / 1_000,
      expires_at: (now + 10_000) / 1_000,
      source: 'runtime/prism.jsonl',
      frequency: 528,
      state: 'MANIFEST',
      level: 5,
      resonance: 0.95,
      harmonic_purity: 0.91,
      love_locked: true,
      layers: { hnc: 528, input: 432, creative: 480, reflection: 504, unity: 516, output: 528 },
    },
  }, true, now);
  assert.equal(result.prismState.available, true);
  assert.equal(result.prismState.value, 528);
  assert.equal(result.prismReceipt.available, true);
  assert.equal(result.prismReceipt.frequency, 528);
  assert.equal(result.prismReceipt.state, 'MANIFEST');
  assert.equal(result.prismReceipt.level, 5);
  assert.equal(result.prismReceipt.isLoveLocked, true);
  assert.equal(result.prismReceipt.layers?.output, 528);
});

test('probability matrix contract is not presented as a live runtime reading', () => {
  const result = readWarRoomEvidence(sourceProof({ systems: {
    hnc_probability_matrix: { name: 'HNC probability matrix', present: true, passed: true },
  } }), true, now);
  assert.equal(result.systems[0].evaluated, false);
  assert.equal(result.systems[0].status, 'Contract verified; timestamped runtime matrix reading unavailable.');
});
