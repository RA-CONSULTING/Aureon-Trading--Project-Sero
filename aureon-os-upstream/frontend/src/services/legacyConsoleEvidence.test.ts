import test from 'node:test';
import assert from 'node:assert/strict';
import { currentLegacyReport, formatLegacyNumber, legacyReadiness, legacyRuntimeEvidence, legacyReportPaths, readLegacyReports } from './legacyConsoleEvidence';
import { unifiedFrontendStateFromReports } from './aureonAutonomousFrontend';
import type { OperationalRead } from './operationalSnapshot';

const now = Date.parse('2026-09-08T12:00:00Z');
const snapshot = (runtime: Record<string, unknown>): OperationalRead => ({
  runtime, loadedAt: new Date(now).toISOString(), runtimeEndpoint: '/api/terminal-state',
  data: {}, loading: false, errors: [], flight: null, reboot: null,
  statusRead: null, company: null, coverage: null, switchboardLive: null, releaseReadiness: null, ingressCustody: null, executorIsolation: null, authorityMap: null, resultBinding: null, capabilityAttestation: null, releaseLedger: null,
});

test('missing or malformed numeric observations stay unavailable; measured zero remains zero', () => {
  for (const value of [undefined, null, '', '0', false, NaN, Infinity]) assert.equal(formatLegacyNumber(value), 'Unavailable');
  assert.equal(formatLegacyNumber(0), '0');
  assert.equal(legacyReadiness({}), null);
  assert.equal(legacyReadiness({ surface_count: 0, security_blocker_count: 0, orphaned_frontend_count: 0 }), null);
  assert.equal(legacyReadiness({ surface_count: 100, security_blocker_count: 0, orphaned_frontend_count: 0 }), 100);
});

test('fresh transport and generated status timestamps cannot replace a missing completed source tick', () => {
  const reading = legacyRuntimeEvidence(snapshot({ ok: true, stale: false, generated_at: new Date(now).toISOString() }), null, now, now);
  assert.equal(reading.data, null);
  assert.equal(reading.freshness.sourceTimestamp, null);
});

test('source clock expires independently and errors retire all runtime metrics', () => {
  const original = new Date(now - 1_000).toISOString();
  const data = snapshot({ ok: true, stale: false, last_tick_completed_at: original, combined: { open_positions: 0 } });
  assert.equal(legacyRuntimeEvidence(data, null, now, now).data?.combined?.open_positions, 0);
  assert.equal(legacyRuntimeEvidence(data, null, now, now).freshness.sourceTimestamp, original);
  assert.equal(legacyRuntimeEvidence(data, null, now, now + 45_000).data, null);
  assert.equal(legacyRuntimeEvidence(data, 'HTTP 401', now, now).data, null);
  assert.equal(data.runtime?.last_tick_completed_at, original);
});

test('recorded manifest projection keeps original clocks and missing summaries empty', () => {
  const original = '2026-09-01T10:00:00Z';
  const result = unifiedFrontendStateFromReports({ inventory: { generated_at: original, summary: { surface_count: 7 } } }, new Date(now).toISOString());
  assert.equal(result.inventory.generated_at, original);
  assert.deepEqual(result.organism.summary, {});
  assert.deepEqual(result.switchboard.summary, {});
  assert.equal(result.organism.generated_at, undefined);
  assert.equal(result.errors.length, 4);
});

test('generated report clock does not refresh on a new read and explicit stale/simulation fails', () => {
  const report = { generated_at: new Date(now - 90_000).toISOString(), total: 0 };
  assert.deepEqual(currentLegacyReport(report, now, 90), report);
  assert.equal(currentLegacyReport(report, now + 1, 90), null);
  assert.equal(currentLegacyReport({ total: 0 }, now, 90), null);
  assert.equal(currentLegacyReport({ ...report, stale: true }, now, 90), null);
  assert.equal(currentLegacyReport({ ...report, simulated: true }, now, 90), null);
});

test('fixed report batch is bounded to three requests and a later failed cycle contains no old values', async () => {
  let active = 0, peak = 0;
  const paths: string[] = [];
  const first = await readLegacyReports({}, async (path) => {
    paths.push(path); peak = Math.max(peak, ++active);
    await new Promise(resolve => setTimeout(resolve, 1)); active--;
    return { generated_at: new Date(now).toISOString(), runtime_feed_url: 'https://not-a-source.invalid' };
  });
  assert.equal(peak, 3);
  assert.deepEqual(paths.sort(), Object.values(legacyReportPaths).sort());
  assert.equal(Object.keys(first).length, 21);
  const second = await readLegacyReports({}, async () => { throw new Error('missing'); });
  assert.deepEqual(second, {});
});

test('cancellation aborts current reads and stops queueing further report requests', async () => {
  const controller = new AbortController();
  let started = 0, aborted = 0;
  const pending = readLegacyReports({ signal: controller.signal }, async (_path, options) => {
    started++;
    return await new Promise((_resolve, reject) => options.signal?.addEventListener('abort', () => { aborted++; reject(new Error('cancelled')); }, { once: true }));
  });
  assert.equal(started, 3);
  controller.abort();
  assert.deepEqual(await pending, {});
  assert.equal(started, 3);
  assert.equal(aborted, 3);
});

test('overall report deadline aborts slow reads without scheduling the remaining queue', async () => {
  let started = 0;
  const result = await readLegacyReports({ timeoutMs: 5 }, async (_path, options) => {
    started++;
    return await new Promise((_resolve, reject) => options.signal?.addEventListener('abort', () => reject(new Error('deadline')), { once: true }));
  });
  assert.equal(started, 3);
  assert.deepEqual(result, {});
});




