import assert from 'node:assert/strict';
import test from 'node:test';
import { readOperationalSnapshot } from './operationalSnapshot';

test('real runtime read starts before public reports and survives missing report responses', async () => {
  const calls: string[] = [];
  const result = await readOperationalSnapshot({ timeoutMs: 8_000 }, async path => {
    calls.push(path);
    if (path === '/api/terminal-state') return { last_tick_completed_at: '2026-09-08T17:00:00Z', source: 'fixture' };
    if (path === '/api/flight-test') return { checks: {} };
    throw new Error('missing fixture report');
  });
  assert.deepEqual(calls.slice(0, 2), ['/api/terminal-state', '/api/flight-test']);
  assert.equal(result.runtime?.last_tick_completed_at, '2026-09-08T17:00:00Z');
  assert.equal(result.errors.length, 22);
  assert.equal(result.reboot, null);
});
test('report endpoint declarations cannot redirect authenticated reads or create fake runtime observations', async () => {
  const calls: string[] = [];
  const result = await readOperationalSnapshot({}, async path => {
    calls.push(path);
    if (path.startsWith('/api/')) throw new Error('runtime fixture down');
    return { runtime_feed_url: 'https://untrusted.invalid/api/terminal-state', generated_at: '2026-09-08T17:00:00Z' };
  });
  assert.equal(calls.some(path => path.startsWith('http')), false);
  assert.equal(result.runtime, null);
  assert.equal(result.runtimeEndpoint, '/api/terminal-state');
});
test('public report reads are bounded to three and keep independent runtime deadline options', async () => {
  let active = 0, highest = 0;
  const controller = new AbortController();
  await readOperationalSnapshot({ timeoutMs: 20_000, signal: controller.signal }, async (path, options) => {
    if (path.startsWith('/api/')) {
      assert.equal(options.signal, controller.signal);
      assert.equal(options.timeoutMs, 8_000);
      return {};
    }
    assert.equal(options.signal?.aborted, false);
    assert.equal(options.timeoutMs, 5_000);
    active++; highest = Math.max(highest, active);
    await new Promise(resolve => setTimeout(resolve, 2));
    active--; return {};
  });
  assert.equal(highest, 3);
});
