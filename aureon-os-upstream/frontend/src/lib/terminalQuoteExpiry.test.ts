import assert from 'node:assert/strict';
import test from 'node:test';
import { freshTerminalQuotes, streamFreshness, type TerminalState } from '../hooks/terminalStateContract';
import { scheduleQuoteExpiry, terminalQuoteExpiryDeadlines, type ExpiryClock } from '../hooks/terminalQuoteExpiry';

const now = Date.parse('2026-09-08T18:30:00Z');
const state = (quotes: { symbol: string; timestamp?: number; age_sec?: number; price?: number }[],
  generatedAt = now - 500): TerminalState => ({ ok: true, stale: true, live_stream_cache: {
    fresh: true, generated_at: new Date(generatedAt).toISOString(), max_age_sec: 5, source: 'test-only-feed',
    quotes: quotes.map(quote => ({ price: 1, source: 'test-only-provider', timestamp_kind: 'provider_event', ...quote })) } });
const q = (symbol: string, ageMs: number) => ({ symbol, timestamp: (now - ageMs) / 1_000, age_sec: ageMs / 1_000 });

test('mixed original clocks schedule table at first expiry and shared label only at last expiry', () => {
  const input = state([q('older', 4_900), q('younger', 1_000)]);
  assert.deepEqual(terminalQuoteExpiryDeadlines(input, null, now, now),
    { nextQuoteExpiresAtMs: now + 100, streamExpiresAtMs: now + 4_000 });
  assert.deepEqual(freshTerminalQuotes(input, now, now + 100).map(row => row.symbol), ['younger']);
  assert.equal(streamFreshness(input, null, now, now + 100).status, 'fresh');
});

test('reported server age retains its original receipt deadline independently of the source clock', () => {
  const input = state([{ ...q('reported-old', 1_000), age_sec: 4.8 }, q('young', 500)]);
  const result = terminalQuoteExpiryDeadlines(input, null, now - 100, now);
  assert.equal(result.nextQuoteExpiresAtMs, now + 100);
  assert.deepEqual(freshTerminalQuotes(input, now - 100, now + 101).map(row => row.symbol), ['young']);
});

test('cache-source expiry can end the stream before any remaining row expires', () => {
  const input = state([q('young', 200)], now - 4_900);
  assert.deepEqual(terminalQuoteExpiryDeadlines(input, null, now, now),
    { nextQuoteExpiresAtMs: now + 100, streamExpiresAtMs: now + 100 });
  assert.equal(streamFreshness(input, null, now, now + 100).status, 'stale');
});

test('a new HTTP receipt cannot extend a provider event deadline', () => {
  const input = state([q('old', 3_000)]);
  assert.equal(terminalQuoteExpiryDeadlines(input, null, now, now).streamExpiresAtMs, now + 2_000);
  assert.equal(terminalQuoteExpiryDeadlines(input, null, now + 1_000, now + 1_000).streamExpiresAtMs, now + 2_000);
});

test('malformed, expired, failed transport and missing evidence schedule no refresh loop', () => {
  for (const [input, error] of [[state([q('expired', 5_000)]), null],
    [state([{ symbol: 'missing' }]), null], [state([q('valid', 1_000)]), 'HTTP failed'], [null, null]] as const) {
    assert.deepEqual(terminalQuoteExpiryDeadlines(input, error, now, now),
      { nextQuoteExpiresAtMs: null, streamExpiresAtMs: null });
  }
});

test('exact five-second boundary is excluded from rows and the stream badge', () => {
  const input = state([q('boundary', 4_999)]);
  assert.equal(freshTerminalQuotes(input, now, now).length, 1);
  assert.equal(freshTerminalQuotes(input, now, now + 1).length, 0);
  assert.equal(streamFreshness(input, null, now, now + 1).status, 'stale');
});

function fakeClock() {
  let time = now;
  let id = 0;
  const pending = new Map<number, { at: number; callback: () => void }>();
  const clock: ExpiryClock = {
    now: () => time,
    setTimeout: (callback, delayMs) => { const handle = ++id; pending.set(handle, { at: time + delayMs, callback }); return handle; },
    clearTimeout: handle => { pending.delete(handle as number); },
  };
  return { clock, pending, advance(target: number) {
    let next;
    while ((next = [...pending.entries()].sort((a, b) => a[1].at - b[1].at)[0]) && next[1].at <= target) {
      time = next[1].at; pending.delete(next[0]); next[1].callback();
    }
    time = target;
  } };
}

test('one-shot deadline scheduling cancels old receipts and handles late commits without extension', () => {
  const timer = fakeClock();
  let called = 0;
  const cancel = scheduleQuoteExpiry(now + 100, () => called++, timer.clock);
  assert.equal(timer.pending.size, 1);
  cancel();
  timer.advance(now + 200);
  assert.equal(called, 0);
  scheduleQuoteExpiry(now + 100, () => called++, timer.clock);
  timer.advance(now + 200);
  assert.equal(called, 1);
  assert.equal(timer.pending.size, 0);
  scheduleQuoteExpiry(null, () => called++, timer.clock);
  assert.equal(timer.pending.size, 0);
});

test('table expiry removes individual rows while a single overall timeout updates the route badge', () => {
  const timer = fakeClock();
  const input = state([q('first', 4_900), q('last', 3_000)]);
  const renders: { at: number; symbols: string[]; badge: string }[] = [];
  const overall: string[] = [];
  const render = () => {
    const time = timer.clock.now();
    const badge = streamFreshness(input, null, now, time).status;
    renders.push({ at: time, symbols: badge === 'fresh' ? freshTerminalQuotes(input, now, time).map(row => row.symbol) : [], badge });
    scheduleQuoteExpiry(terminalQuoteExpiryDeadlines(input, null, now, time).nextQuoteExpiresAtMs, render, timer.clock);
  };
  render();
  scheduleQuoteExpiry(terminalQuoteExpiryDeadlines(input, null, now, now).streamExpiresAtMs,
    () => overall.push(streamFreshness(input, null, now, timer.clock.now()).status), timer.clock);
  timer.advance(now + 100);
  assert.deepEqual(renders.at(-1)?.symbols, ['last']);
  assert.deepEqual(overall, []);
  timer.advance(now + 2_000);
  assert.deepEqual(renders.at(-1), { at: now + 2_000, symbols: [], badge: 'stale' });
  assert.deepEqual(overall, ['stale']);
  assert.equal(timer.pending.size, 0);
});
