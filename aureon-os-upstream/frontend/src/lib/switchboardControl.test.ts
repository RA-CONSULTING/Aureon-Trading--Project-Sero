import assert from 'node:assert/strict';
import test from 'node:test';
import { setAuthTokenProvider } from '../services/apiClient';
import { SwitchboardWriteGuard, type SwitchboardConfiguration, type SwitchboardFlag } from './platformConfiguration';
import { submitSwitchboardChange } from './switchboardControl';

function fixture(patch: Partial<SwitchboardFlag> = {}) {
  const flag: SwitchboardFlag = { id: 'AUREON_TEST_SETTING', env_var: 'AUREON_TEST_SETTING', label: 'Fixture setting',
    group: 'Fixture', kind: 'safe', effect: 'live', effect_note: 'Applies now', description: 'Fixture only',
    default: false, enabled: false, stored: null, source: 'default', armed: false, decided_at: null, pending_restart: false, ...patch };
  const configuration: SwitchboardConfiguration = { groups: [{ label: 'Fixture', flags: [flag] }],
    summary: { total: 1, enabled: Number(flag.enabled), armed: Number(flag.armed), pending_restart: Number(flag.pending_restart === true), hard_boundary_total: Number(flag.kind === 'hard_boundary') } };
  return { flag, configuration, options: { guard: new SwitchboardWriteGuard(), flag, enabled: true,
    current: () => ({ data: configuration, isReceiptCurrent: true, resetVersion: 1 }), canManage: () => true } };
}

function json(value: unknown, status = 200) { return new Response(JSON.stringify(value), { status, headers: { 'content-type': 'application/json' } }); }
async function withFetch(run: (calls: { path: string; method: string; body: unknown }[], setResponse: (value: typeof fetch) => void) => Promise<void>) {
  const original = globalThis.fetch;
  const calls: { path: string; method: string; body: unknown }[] = [];
  let respond: typeof fetch = async () => { throw new Error('Unexpected request'); };
  setAuthTokenProvider(async () => 'fixture-session');
  globalThis.fetch = async (path, init) => {
    assert.equal(new Headers(init?.headers).get('Authorization'), 'Bearer fixture-session');
    calls.push({ path: String(path), method: init?.method ?? 'GET', body: init?.body ? JSON.parse(String(init.body)) : null });
    return respond(path, init);
  };
  try { await run(calls, fn => { respond = fn; }); }
  finally { globalThis.fetch = original; setAuthTokenProvider(null); }
}

test('explicit setting changes use one authenticated fresh preflight followed by one existing POST', async () => {
  await withFetch(async (calls, respond) => {
    const { options, configuration, flag } = fixture();
    assert.equal(calls.length, 0);
    respond(async (_path, init) => init?.method === 'GET' ? json(configuration)
      : json({ ok: true, flag: { id: flag.id, stored: true, enabled: true }, applied: 'Applied to operator' }));
    const receipt = await submitSwitchboardChange(options);
    assert.equal(receipt.enabled, true);
    assert.deepEqual(calls, [
      { path: '/api/switchboard', method: 'GET', body: null },
      { path: '/api/switchboard/AUREON_TEST_SETTING', method: 'POST', body: { enabled: true } },
    ]);
  });
});

test('consequential settings require the exact user confirmation; stored intent does not become runtime state', async () => {
  await withFetch(async (calls, respond) => {
    const { options, configuration, flag } = fixture({ kind: 'hard_boundary', effect: 'restart' });
    await assert.rejects(submitSwitchboardChange({ ...options, confirm: 'wrong' }), /Typed flag confirmation/);
    assert.equal(calls.length, 0);
    respond(async (_path, init) => init?.method === 'GET' ? json(configuration)
      : json({ ok: true, flag: { id: flag.id, stored: true, enabled: false }, applied: 'Restart required' }));
    const receipt = await submitSwitchboardChange({ ...options, confirm: flag.id });
    assert.deepEqual(receipt, { stored: true, enabled: false, applied: 'Restart required' });
    assert.deepEqual(calls[1].body, { enabled: true, confirm: flag.id });
  });
});

test('missing operator access sends nothing; access loss during the preflight prevents a POST', async () => {
  await withFetch(async (calls, respond) => {
    const { options, configuration } = fixture();
    await assert.rejects(submitSwitchboardChange({ ...options, canManage: () => false }), /operator session/);
    assert.equal(calls.length, 0);
    let canManage = true;
    respond(async () => { canManage = false; return json(configuration); });
    await assert.rejects(submitSwitchboardChange({ ...options, canManage: () => canManage }), /operator session/);
    assert.deepEqual(calls.map(call => call.method), ['GET']);
  });
});

test('expired configuration and backend access failures never send or retry a setting change', async () => {
  await withFetch(async (calls, respond) => {
    const { options } = fixture();
    await assert.rejects(submitSwitchboardChange({ ...options, current: () => ({ ...options.current(), isReceiptCurrent: false }) }), /current flag/);
    assert.equal(calls.length, 0);
    respond(async () => json({ error: { message: 'Operator required' } }, 403));
    await assert.rejects(submitSwitchboardChange(options), /Operator required/);
    assert.deepEqual(calls.map(call => call.method), ['GET']);
  });
});

test('malformed write receipts are uncertain rather than confirmed saves', async () => {
  await withFetch(async (calls, respond) => {
    const { options, configuration } = fixture();
    respond(async (_path, init) => init?.method === 'GET' ? json(configuration) : json({ ok: true }));
    await assert.rejects(submitSwitchboardChange(options), /not confirmed/);
    assert.equal(calls.length, 2);
  });
});
