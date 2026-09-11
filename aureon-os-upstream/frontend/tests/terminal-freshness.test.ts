import assert from 'node:assert/strict';
import test from 'node:test';
import { freshTerminalQuotes, freshnessGatedState, parseTerminalState, streamFreshness, terminalFreshness, type TerminalState } from '../src/hooks/terminalStateContract';

const now = Date.parse('2026-09-08T09:00:00Z');
function tick(overrides: Partial<TerminalState> = {}): TerminalState {
  return { ok: true, stale: false, source: 'test-only-runtime', last_tick_completed_at: new Date(now - 10_000).toISOString(),
    last_tick_age_sec: 10, data_ready: true, trading_ready: true,
    exchanges: { kraken_ready: true, execution_venues: { kraken_spot: { ready: true } } },
    exchange_action_plan: { executor_enabled: true }, ...overrides };
}

test('requires an attested completed tick, not a fresh HTTP or file heartbeat', () => {
  assert.equal(terminalFreshness(tick(), null, now, now).status, 'fresh');
  const heartbeatOnly = tick({ last_tick_completed_at: null, generated_at: new Date(now).toISOString() });
  assert.equal(terminalFreshness(heartbeatOnly, null, now, now).status, 'unavailable');
  assert.equal(terminalFreshness(tick({ stale: undefined }), null, now, now).status, 'stale');
});

test('ages the same completed tick between polls and despite repeated HTTP receipts', () => {
  assert.equal(terminalFreshness(tick(), null, now, now + 36_000).status, 'stale');
  assert.equal(terminalFreshness(tick(), null, now + 36_000, now + 36_000).status, 'stale');
  assert.equal(terminalFreshness(tick({ last_tick_age_sec: 60 }), null, now, now).status, 'stale');
});

test('future, malformed, booting, duplicate, watchdog and stale status cannot become fresh', () => {
  const cases: Partial<TerminalState>[] = [
    { last_tick_completed_at: new Date(now + 60_000).toISOString() }, { last_tick_completed_at: 'invalid' },
    { ok: false }, { stale: true }, { booting: true }, { duplicate_runtime: true },
    { runtime_watchdog: { tick_stale: true } }, { runtime_watchdog: { tick_long_running: true } },
    { runtime_watchdog: { status_file_fresh: false } },
  ];
  for (const override of cases) assert.notEqual(terminalFreshness(tick(override), null, now, now).status, 'fresh');
});

test('source timezone offset denotes the same instant', () => {
  assert.equal(terminalFreshness(tick({ last_tick_completed_at: '2026-09-08T09:59:50+01:00' }), null, now, now).status, 'fresh');
});

test('transport errors gate all execution readiness without mutating observed evidence', () => {
  const observed = tick();
  const freshness = terminalFreshness(observed, 'connection refused', now, now);
  const state = freshnessGatedState(observed, freshness)!;
  assert.equal(freshness.status, 'unavailable');
  assert.equal(state.ok, false);
  assert.equal(state.data_ready, false);
  assert.equal(state.trading_ready, false);
  assert.equal(state.exchanges?.kraken_ready, false);
  assert.equal(state.exchanges?.execution_venues?.kraken_spot.ready, false);
  assert.equal(state.exchange_action_plan?.executor_enabled, false);
  assert.equal(observed.exchanges?.kraken_ready, true);
});

test('independent observed market cache can stay fresh during a stale trader tick', () => {
  const state = tick({ stale: true, live_stream_cache: { source: 'test-only-cache', fresh: true,
    generated_at: new Date(now - 1_000).toISOString(), oldest_selected_age_sec: 2, max_age_sec: 5 } });
  assert.equal(terminalFreshness(state, null, now, now).status, 'stale');
  assert.equal(streamFreshness(state, null, now, now).status, 'fresh');
  assert.equal(streamFreshness(state, null, now, now + 4_000).status, 'stale');
  assert.equal(streamFreshness(state, 'connection refused', now, now).status, 'unavailable');
});

test('stream cannot use generated receipt time to hide oldest selected quote age', () => {
  const state = tick({ live_stream_cache: { fresh: true, generated_at: new Date(now).toISOString(), oldest_selected_age_sec: 30, max_age_sec: 5 } });
  assert.equal(streamFreshness(state, null, now, now).status, 'stale');
  assert.equal(streamFreshness(tick({ live_stream_cache: { fresh: true } }), null, now, now).status, 'stale');
});

test('unexpected endpoint payloads are rejected rather than replacing known observations', () => {
  for (const value of [null, [], 'html', {}, { ok: 'yes' }, { ok: true, source: {} }, { ok: true, exchanges: { execution_venues: [] } },
    { ok: true, trading_gate_evidence: [] },
    { ok: true, exchange_action_plan: { global_blockers: 'bad' } },
    { ok: true, exchange_action_plan: { order_intent_publish_enabled: 'yes' } },
    { ok: true, exchange_action_plan: { real_orders_disabled: 'no' } },
    { ok: true, exchange_action_plan: { runtime_clearances_required: 'bad' } },
    { ok: true, live_stream_cache: { quotes: [null] } }]) assert.throws(() => parseTerminalState(value));
  assert.equal(parseTerminalState({ ok: false }).ok, false);
});

test('expires old quote rows while preserving separately current provider events', () => {
  const state = tick({ live_stream_cache: { fresh: true, generated_at: new Date(now - 1_000).toISOString(),
    oldest_selected_age_sec: 4, max_age_sec: 5, quotes: [
      { symbol: 'old', price: 1, timestamp: (now - 4_000) / 1_000, age_sec: 4 },
      { symbol: 'current', price: 2, timestamp: (now - 1_000) / 1_000, age_sec: 1 },
      { symbol: 'missing', price: 2 },
      { symbol: 'future', price: 2, timestamp: (now + 60_000) / 1_000 },
    ] } });
  assert.deepEqual(freshTerminalQuotes(state, now, now + 2_000).map(quote => quote.symbol), ['current']);
  assert.equal(streamFreshness(state, null, now, now + 2_000).status, 'fresh');
  assert.equal(streamFreshness(state, null, now, now + 6_000).status, 'stale');
});
