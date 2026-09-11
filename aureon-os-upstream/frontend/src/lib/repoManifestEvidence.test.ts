import assert from 'node:assert/strict';
import test from 'node:test';
import { fetchRepoManifests, readRepoManifest } from './repoManifestEvidence';
import { readAgentCompanyReport } from './agentCompanyReportEvidence';

const now = Date.parse('2026-09-08T16:00:00Z');
const source = '/aureon_repo_sitemap.json';
const sitemap = () => ({ snapshot_date: '2026-07-13', tracked_file_count: 0, zones: [], front_doors: [] });
const company = () => ({ generated_at: '2026-07-13T12:00:00Z', status: 'registry_only', summary: { role_count: 0 }, departments: [], roles: [], work_orders: [] });

test('structural manifests keep dated recorded zero and do not infer absent contract booleans', () => {
  const value = readRepoManifest(source, sitemap(), now);
  assert.equal(value.date, '2026-07-13');
  assert.equal(value.report?.tracked_file_count, 0);
  assert.equal(value.report?.public_contract, undefined);
  assert.equal(value.receivedAt, null);
  assert.match(value.reason, /current runtime readiness is not attested/);
});

test('missing source dates and malformed nested arrays or booleans cannot qualify a manifest', () => {
  for (const value of [null, {}, { ...sitemap(), snapshot_date: undefined }, { ...sitemap(), zones: 'not rows' },
    { ...sitemap(), zones: [{ id: 'x', label: 'X', paths: false }] },
    { ...sitemap(), public_contract: { contains_secrets: 'false' } }]) {
    assert.equal(readRepoManifest(source, value, now).report, null);
  }
  assert.equal(readRepoManifest('https://example.invalid/arbitrary.json', sitemap(), now).report, null);
});

test('a failed sibling leaves independently observed reports available with original dates', async () => {
  const fetcher = (async (url) => url === source ? new Response(JSON.stringify(sitemap()))
    : new Response('missing', { status: 404 })) as typeof fetch;
  const receipts = await fetchRepoManifests([source, '/aureon_end_user_access_map.json'], new AbortController().signal, fetcher);
  assert.equal(receipts.length, 2);
  assert.equal(receipts[0].report?.tracked_file_count, 0);
  assert.equal(receipts[0].date, '2026-07-13');
  assert.equal(receipts[1].report, null);
  assert.match(receipts[1].reason, /HTTP 404/);
});

test('structural reads never exceed three simultaneous requests and failures remain per source', async () => {
  let active = 0, peak = 0;
  const fetcher = (async () => {
    active++; peak = Math.max(peak, active);
    await new Promise(resolve => setTimeout(resolve, 1));
    active--;
    return new Response(JSON.stringify({ generated_at: '2026-07-13T12:00:00Z', summary: {} }));
  }) as typeof fetch;
  const receipts = await fetchRepoManifests(Array.from({ length: 8 }, (_, i) => `/report_${i}.json`), new AbortController().signal, fetcher);
  assert.equal(peak, 3);
  assert.equal(receipts.filter(receipt => receipt.report).length, 8);
});

test('Agent Company accepts recorded structures, not any object with a nonempty status', () => {
  const report = readAgentCompanyReport(company(), now);
  assert.equal((report?.summary as { role_count: number }).role_count, 0);
  for (const value of [{ status: 'healthy' }, { ...company(), generated_at: undefined },
    { ...company(), work_orders: 'bad' }, { ...company(), roles: [{ role_id: 'r', department: 'd', title: 'R', capabilities: 'bad' }] },
    { ...company(), generated_at: new Date(now + 6_000).toISOString() }]) {
    assert.equal(readAgentCompanyReport(value, now), null);
  }
});
