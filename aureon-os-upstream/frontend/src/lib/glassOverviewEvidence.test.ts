import assert from 'node:assert/strict';
import test from 'node:test';
import type { TerminalState } from '../hooks/terminalStateContract';
import { appendObservedQuote, currentCandidateCount, currentGlassCandidates, endToEndMedianMs, observedCandles } from './glassOverviewEvidence';

const now = 2_000_000;
const stateWithReceipt = (change = {}): TerminalState => ({ exchange_action_plan: { candidate_evidence: {
  available: true, truth_status: 'real_derived', generated_values: false,
  source_timestamp: 1999, expires_at: 2029, active_order_flow_count: 0, ...change,
} } } as TerminalState);

test('fresh candidate receipts preserve measured zero and exclude stale, generated, malformed or disconnected observations', () => {
  assert.equal(currentCandidateCount(stateWithReceipt(), true, now), 0);
  for (const change of [{ source_timestamp: 1960 }, { source_timestamp: 2010 }, { expires_at: 2000 },
    { generated_values: true }, { active_order_flow_count: -1 }, { active_order_flow_count: 0.5 },
    { available: false }, { truth_status: 'simulated' }]) assert.equal(currentCandidateCount(stateWithReceipt(change), true, now), null);
  assert.equal(currentCandidateCount(stateWithReceipt(), false, now), null);
  assert.equal(currentCandidateCount(null, true, now), null);
});

const planState = (age = 1, generated = new Date(now - 1000).toISOString()): TerminalState => ({ exchange_action_plan: {
  generated_at: generated, venues: { kraken_spot: { venue: 'kraken', top_candidates: [
    { symbol: 'BTCUSD', side: 'BUY', confidence: 0.75, fast_money_profile: { freshest_age_sec: age } },
  ] } },
} } as TerminalState);

test('current plan rows expire against provider age plus elapsed plan time; unknown timestamp never becomes live', () => {
  assert.equal(currentGlassCandidates(planState(), true, now)[0].confidence, 0.75);
  assert.deepEqual(currentGlassCandidates(planState(4), true, now), []);
  assert.deepEqual(currentGlassCandidates(planState(), false, now), []);
  assert.deepEqual(currentGlassCandidates(planState(0, 'invalid'), true, now), []);
  assert.deepEqual(currentGlassCandidates(planState(0, new Date(now + 6000).toISOString()), true, now), []);
});

test('sampled chart deduplicates provider events, orders observations, and leaves missing minute buckets empty', () => {
  let samples = appendObservedQuote([], { symbol: 'BTCUSD', price: 10, timestamp: 120 });
  assert.equal(appendObservedQuote(samples, { symbol: 'BTCUSD', price: 12, timestamp: 120 }), samples);
  samples = appendObservedQuote(samples, { symbol: 'BTCUSD', price: 8, timestamp: 150 });
  samples = appendObservedQuote(samples, { symbol: 'BTCUSD', price: 13, timestamp: 135 });
  samples = appendObservedQuote(samples, { symbol: 'BTCUSD', price: 15, timestamp: 300 });
  assert.deepEqual(observedCandles(samples), [
    { timestamp: 120, open: 10, high: 13, low: 8, close: 8, samples: 3 },
    { timestamp: 300, open: 15, high: 15, low: 15, close: 15, samples: 1 },
  ]);
  assert.equal(appendObservedQuote(samples, { symbol: 'BTCUSD', price: NaN, timestamp: 400 }), samples);
});

test('end-to-end latency requires current actual samples and converts declared seconds into milliseconds', () => {
  const state: TerminalState = { decision_latency_percentiles: { generated_at: new Date(now).toISOString(), end_to_end_sec: { p50: 0.012, count: 8 } } };
  assert.equal(endToEndMedianMs(state, true, now), 12);
  assert.equal(endToEndMedianMs(state, true, now + 61000), null);
  assert.equal(endToEndMedianMs(state, false, now), null);
  assert.equal(endToEndMedianMs({ decision_latency_percentiles: { ...state.decision_latency_percentiles, end_to_end_sec: { p50: 0, count: 0 } } }, true, now), null);
  assert.equal(endToEndMedianMs({ decision_latency_percentiles: { venues: { example: { p50: 99 } } } }, true, now), null);
});
