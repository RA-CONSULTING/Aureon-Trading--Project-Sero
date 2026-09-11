import assert from 'node:assert/strict';
import test from 'node:test';
import { ApiError } from './apiClient';
import { createReadOnlyPoller, invalidateReadOnlyPollers, type PollerClock } from './readOnlyPoller';

const flush = async () => { await Promise.resolve(); await Promise.resolve(); await Promise.resolve(); };
const deferred = <T>() => {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>(done => { resolve = done; });
  return { promise, resolve };
};
function fakeClock() {
  let now = 100_000, id = 0;
  const timers = new Map<number, { at: number; run: () => void }>();
  const clock: PollerClock = {
    now: () => now,
    setTimeout: (run, ms) => { const key = ++id; timers.set(key, { at: now + ms, run }); return key as unknown as ReturnType<typeof setTimeout>; },
    clearTimeout: key => { timers.delete(Number(key)); },
  };
  return { clock, timers, async advance(ms: number) {
    const end = now + ms;
    while (true) {
      const next = [...timers.entries()].filter(([, value]) => value.at <= end).sort((a, b) => a[1].at - b[1].at)[0];
      if (!next) break;
      now = next[1].at; timers.delete(next[0]); next[1].run(); await flush();
    }
    now = end; await flush();
  } };
}

test('two consumers share one request, slow reads never overlap, refresh coalesces', async t => {
  const fake = fakeClock();
  const pending = deferred<number>();
  let calls = 0;
  const store = createReadOnlyPoller({ clock: fake.clock, receiptMaxAgeMs: 45_000,
    read: () => { calls++; return calls === 1 ? pending.promise : Promise.resolve(0); } });
  const off1 = store.subscribe(() => {}, 1_000), off2 = store.subscribe(() => {}, 2_000);
  t.after(() => { off1(); off2(); });
  await fake.advance(10_000);
  store.refresh(); store.refresh();
  assert.equal(calls, 1);
  pending.resolve(0); await flush(); await fake.advance(0);
  assert.equal(calls, 2);
  assert.equal(store.getSnapshot().data, 0);
  assert.equal(store.getSnapshot().source.status, 'unattested');
  await fake.advance(999); assert.equal(calls, 2);
  await fake.advance(1); assert.equal(calls, 3);
});

test('HTTP failure clears current data while retaining its original receipt time', async t => {
  const fake = fakeClock();
  let fail = false;
  const store = createReadOnlyPoller({ clock: fake.clock, receiptMaxAgeMs: 45_000,
    read: async () => { if (fail) throw new ApiError('forbidden', { status: 403, path: '/api/test' }); return { count: 0 }; } });
  const off = store.subscribe(() => {}, 1_000); t.after(off); await flush();
  assert.equal(store.getSnapshot().data?.count, 0);
  const received = store.getSnapshot().lastReceivedAt;
  fail = true; await fake.advance(1_000);
  assert.equal(store.getSnapshot().data, null);
  assert.equal(store.getSnapshot().lastReceivedAt, received);
  assert.equal(store.getSnapshot().offline, false);
  assert.equal(store.getSnapshot().httpStatus, 403);
  assert.equal(store.getSnapshot().error, 'forbidden');
});

test('receipt expires independently while a new read remains pending', async t => {
  const fake = fakeClock();
  let calls = 0;
  const store = createReadOnlyPoller({ clock: fake.clock, receiptMaxAgeMs: 2_000,
    read: () => ++calls === 1 ? Promise.resolve({ value: 0 }) : new Promise<{ value: number }>(() => {}) });
  const off = store.subscribe(() => {}, 1_000); t.after(off); await flush();
  await fake.advance(2_000); assert.equal(store.getSnapshot().data?.value, 0);
  await fake.advance(1_000);
  assert.equal(store.getSnapshot().data, null);
  assert.equal(store.getSnapshot().isReceiptCurrent, false);
  assert.equal(calls, 2);
});

test('fresh HTTP receipts never renew the original source clock', async t => {
  const fake = fakeClock();
  const sourceTimestamp = fake.clock.now();
  const store = createReadOnlyPoller({ clock: fake.clock, receiptMaxAgeMs: 45_000,
    read: async () => ({ sourceTimestamp, value: 0 }),
    validateSource: (data, now) => ({ status: now - data.sourceTimestamp <= 2_000 ? 'fresh' : 'stale', sourceTimestamp: data.sourceTimestamp }) });
  const off = store.subscribe(() => {}, 1_000); t.after(off); await flush();
  await fake.advance(3_000);
  const state = store.getSnapshot();
  assert.equal(state.data, null);
  assert.equal(state.isReceiptCurrent, true);
  assert.equal(state.source.status, 'stale');
  assert.equal(state.source.sourceTimestamp, sourceTimestamp);
});

test('last unsubscribe clears data, aborts old requests and ignores late completion after remount', async () => {
  const fake = fakeClock();
  const old = deferred<string>(), current = deferred<string>();
  const signals: AbortSignal[] = [];
  const store = createReadOnlyPoller({ clock: fake.clock, receiptMaxAgeMs: 45_000,
    read: ({ signal }) => { signals.push(signal); return signals.length === 1 ? old.promise : current.promise; } });
  const off = store.subscribe(() => {});
  off();
  assert.equal(signals[0].aborted, true);
  assert.equal(fake.timers.size, 0);
  assert.equal(store.getSnapshot().lastReceivedAt, null);
  const off2 = store.subscribe(() => {});
  old.resolve('old account'); await flush();
  assert.equal(store.getSnapshot().data, null);
  current.resolve('current account'); await flush();
  assert.equal(store.getSnapshot().data, 'current account');
  off2();
  assert.equal(store.getSnapshot().data, null);
});

test('auth invalidation clears all subscribed stores and cancels pre-change responses', async t => {
  const fake = fakeClock();
  const late = deferred<string>();
  let calls = 0;
  const store = createReadOnlyPoller({ clock: fake.clock, receiptMaxAgeMs: 45_000,
    read: () => ++calls === 1 ? Promise.resolve('prior account') : late.promise });
  const off = store.subscribe(() => {}); t.after(off); await flush();
  assert.equal(store.getSnapshot().data, 'prior account');
  const previousReset = store.getSnapshot().resetVersion;
  invalidateReadOnlyPollers();
  assert.equal(store.getSnapshot().data, null);
  assert.equal(store.getSnapshot().lastReceivedAt, null);
  assert.equal(store.getSnapshot().resetVersion, previousReset + 1);
  assert.equal(calls, 2);
});

test('a source validator failure cannot leave current data or a fresh source claim', async t => {
  const fake = fakeClock();
  const store = createReadOnlyPoller({ clock: fake.clock, receiptMaxAgeMs: 45_000,
    read: async () => ({ value: 0 }), validateSource: () => { throw new Error('invalid evidence'); } });
  const off = store.subscribe(() => {}); t.after(off); await flush();
  assert.equal(store.getSnapshot().data, null);
  assert.equal(store.getSnapshot().source.status, 'unavailable');
});
