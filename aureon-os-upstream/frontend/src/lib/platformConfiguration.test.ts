import assert from 'node:assert/strict';
import test from 'node:test';
import { buildStaticCompanyProfile } from '../shell/companyFacts';
import {
  readBillingStatus, readRecordedCompanyProfile, readSwitchboardConfiguration,
  sessionUserObserver, SwitchboardWriteGuard, type SwitchboardConfiguration, type SwitchboardFlag,
} from './platformConfiguration';

function flag(overrides: Partial<SwitchboardFlag> = {}): SwitchboardFlag {
  return { id: 'read_tool', env_var: 'READ_TOOL', label: 'Read tool', group: 'Tools', kind: 'safe',
    effect: 'live', effect_note: 'Applied in process', description: 'Existing read tool setting',
    default: false, enabled: false, stored: null, source: 'default', risk_value: true, armed: false,
    requested_armed: false, decided_at: null, pending_restart: false, pending_handoff: false, env_hold: false, ...overrides };
}
function configuration(flags = [flag()]): SwitchboardConfiguration {
  const labels = [...new Set(flags.map(f => f.group))];
  return { groups: labels.map(label => ({ label, flags: flags.filter(f => f.group === label) })),
    summary: { total: flags.length, enabled: flags.filter(f => f.enabled).length,
      requested_enabled: flags.filter(f => f.stored ?? f.enabled).length,
      armed: flags.filter(f => f.armed).length, requested_armed: flags.filter(f => f.requested_armed).length,
      pending_restart: flags.filter(f => f.pending_restart === true).length,
      pending_handoff: flags.filter(f => f.pending_handoff).length,
      hard_boundary_total: flags.filter(f => f.kind === 'hard_boundary').length } };
}
const deferred = <T>() => {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>(done => { resolve = done; });
  return { promise, resolve };
};
function setup(expected = flag()) {
  let snapshot = { data: configuration([expected]) as SwitchboardConfiguration | null, isReceiptCurrent: true, resetVersion: 1 };
  let writes = 0, reads = 0;
  const io = { current: () => snapshot,
    read: async () => { reads++; return configuration([expected]); },
    write: async () => { writes++; return 'recorded'; } };
  return { guard: new SwitchboardWriteGuard(), io, expected,
    snapshot: (next: Partial<typeof snapshot>) => { snapshot = { ...snapshot, ...next }; },
    counts: () => ({ reads, writes }) };
}

test('switchboard preserves explicit false and zero counts; incomplete control records fail closed', () => {
  assert.equal(readSwitchboardConfiguration(configuration()).summary.enabled, 0);
  for (const bad of [{}, { groups: [], summary: {} }, configuration([flag({ kind: 'unknown' as 'safe' })]),
    configuration([flag({ enabled: undefined as unknown as boolean })]), configuration([flag({ armed: true })]),
    configuration([flag({ pending_handoff: true })]),
    configuration([flag({ decided_at: Infinity })]), configuration([flag(), flag()]),
    { ...configuration(), summary: { ...configuration().summary, total: 2 } }]) {
    assert.throws(() => readSwitchboardConfiguration(bad));
  }
});

test('a user change gets a fresh matching configuration before its one existing write', async () => {
  const f = setup();
  assert.equal(await f.guard.run(f.expected, true, undefined, f.io), 'recorded');
  assert.deepEqual(f.counts(), { reads: 1, writes: 1 });
  assert.equal(f.guard.busy, false);
});

test('missing, stale, or reset configuration cannot authorize any preflight or write', async () => {
  for (const patch of [{ data: null }, { isReceiptCurrent: false }]) {
    const f = setup(); f.snapshot(patch);
    await assert.rejects(f.guard.run(f.expected, true, undefined, f.io), /current flag configuration/);
    assert.deepEqual(f.counts(), { reads: 0, writes: 0 });
  }
  const f = setup();
  f.guard.invalidate(1);
  await assert.rejects(f.guard.run(f.expected, true, undefined, f.io), /current flag configuration/);
  assert.deepEqual(f.counts(), { reads: 0, writes: 0 });
  f.snapshot({ resetVersion: 2 });
  await f.guard.run(f.expected, true, undefined, f.io);
  assert.equal(f.counts().writes, 1);
});

test('hard-boundary enable keeps exact typed confirmation; no-op requests are rejected', async () => {
  const f = setup(flag({ id: 'armed_action', kind: 'hard_boundary' }));
  await assert.rejects(f.guard.run(f.expected, true, 'armed', f.io), /Typed flag confirmation/);
  await assert.rejects(f.guard.run(f.expected, false, undefined, f.io), /already matches/);
  assert.deepEqual(f.counts(), { reads: 0, writes: 0 });
  await f.guard.run(f.expected, true, 'armed_action', f.io);
  assert.equal(f.counts().writes, 1);
});

test('turning a safety hold off is the confirmed hard-boundary action', async () => {
  const expected = flag({ id: 'deployment_hold', kind: 'hard_boundary', effect: 'handoff',
    default: true, enabled: true, risk_value: false });
  const f = setup(expected);
  await assert.rejects(f.guard.run(expected, false, undefined, f.io), /Typed flag confirmation/);
  assert.deepEqual(f.counts(), { reads: 0, writes: 0 });
  await f.guard.run(expected, false, expected.id, f.io);
  assert.equal(f.counts().writes, 1);
});

test('changed flag identity, kind, or enabled state in preflight prevents a write', async () => {
  for (const patch of [{ id: 'different' }, { kind: 'hard_boundary' as const }, { enabled: true }, { env_var: 'OTHER' }]) {
    const f = setup();
    await assert.rejects(f.guard.run(f.expected, true, undefined, { ...f.io,
      read: async () => configuration([flag(patch)]) }), /Flag changed/);
    assert.equal(f.counts().writes, 0);
  }
});

test('overlapping controls share no write; session cancellation aborts an in-flight preflight', async () => {
  const f = setup(), pending = deferred<SwitchboardConfiguration>();
  let signal: AbortSignal | undefined;
  const first = f.guard.run(f.expected, true, undefined, { ...f.io, read: value => { signal = value; return pending.promise; } });
  assert.equal(f.guard.busy, true);
  await assert.rejects(f.guard.run(f.expected, true, undefined, f.io), /already in progress/);
  f.guard.invalidate(1);
  assert.equal(signal?.aborted, true);
  pending.resolve(configuration());
  await assert.rejects(first, /Session changed/);
  assert.equal(f.counts().writes, 0);
  assert.equal(f.guard.busy, false);
});

test('a shared store reset during a preflight cannot reuse its previous authorization', async () => {
  const f = setup(), pending = deferred<SwitchboardConfiguration>();
  const result = f.guard.run(f.expected, true, undefined, { ...f.io, read: () => pending.promise });
  f.snapshot({ resetVersion: 2 }); pending.resolve(configuration());
  await assert.rejects(result, /Session changed/);
  assert.equal(f.counts().writes, 0);
});

test('preflight failures propagate and late old-session write results are not reported as success', async () => {
  const f = setup();
  await assert.rejects(f.guard.run(f.expected, true, undefined, { ...f.io, read: async () => { throw new Error('403 Forbidden'); } }), /403/);
  assert.equal(f.counts().writes, 0);
  const pending = deferred<string>();
  let enteredWrite = false;
  const result = f.guard.run(f.expected, true, undefined, { ...f.io, write: () => { enteredWrite = true; return pending.promise; } });
  await Promise.resolve();
  assert.equal(enteredWrite, true);
  f.guard.invalidate(1); pending.resolve('previous session response');
  await assert.rejects(result, /Session changed/);
});

test('billing distinguishes supported zero and false from missing or malformed fields', () => {
  const absent = readBillingStatus({ configured: null, metering: {}, charge_endpoint: {} });
  assert.equal(absent.configured, null); assert.equal(absent.charge_endpoint?.enabled, null);
  assert.equal(absent.metering?.pending, null); assert.equal(absent.metering?.flushed, null);
  const observed = readBillingStatus({ configured: false, charge_endpoint: { enabled: false }, metering: { pending: 0, flushed: 0, dropped: 0, flush_failures: 0 } });
  assert.equal(observed.configured, false); assert.equal(observed.charge_endpoint?.enabled, false);
  assert.equal(observed.metering?.pending, 0);
  const bad = readBillingStatus({ configured: 'true', charge_endpoint: { enabled: 'false' }, metering: { pending: NaN, flushed: -1, dropped: 0.5, flush_failures: Infinity } });
  assert.equal(bad.configured, null); assert.equal(bad.charge_endpoint?.enabled, null);
  for (const key of ['pending', 'flushed', 'dropped', 'flush_failures'] as const) assert.equal(bad.metering?.[key], null);
  assert.throws(() => readBillingStatus({}));
});

test('company fallback remains a recorded profile and ignores a generated live classification', () => {
  const committed = buildStaticCompanyProfile();
  const result = readRecordedCompanyProfile({ ...committed, truth_status: 'live', generated_at: Date.now() });
  assert.deepEqual(result.identity, committed.identity);
  assert.equal(result.source, 'companyFacts.ts');
  assert.equal('truth_status' in result, false); assert.equal('generated_at' in result, false);
  assert.throws(() => readRecordedCompanyProfile({ identity: {} }));
});

test('auth events win over late initial sessions; unsubscribe prevents late account publication', () => {
  const users: (string | null)[] = [];
  const observer = sessionUserObserver(value => users.push(value));
  observer.event('current-user');
  assert.equal(observer.initial('old-user'), false);
  observer.event(null);
  assert.equal(observer.initial('old-user'), false);
  observer.stop(); observer.event('late-user');
  assert.equal(observer.initial('late-user'), false);
  assert.deepEqual(users, ['current-user', null]);
});

test('initial session may publish once before auth changes; timeout cannot revive an old user', () => {
  const users: (string | null)[] = [];
  const observer = sessionUserObserver(value => users.push(value));
  assert.equal(observer.initial('initial-user'), true);
  assert.equal(observer.initial('duplicate-initial'), false);
  observer.event(null);
  assert.equal(observer.initial('delayed-user'), false);
  observer.event('new-user');
  assert.deepEqual(users, ['initial-user', null, 'new-user']);
});
