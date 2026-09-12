import assert from 'node:assert/strict';
import test from 'node:test';
import { readFileSync } from 'node:fs';
import { RELEASE_REQUIREMENTS, operatorConscienceVerdict, readOperatorReleaseReadiness, releaseReadinessView, type ReleaseReadinessReceipt } from './operatorReleaseReadiness';

const contract = () => ({ schema: 'aureon.operator.release-readiness.v1', scope: 'operator_protected_http_ingress',
  basis: 'serving_implementation_contract', state: 'held', reason_code: 'production_magic_star_release_unavailable',
  release_available: false, production_ready: false, source_attestation: null, configuration_attestation: null,
  requirements: Object.entries(RELEASE_REQUIREMENTS).map(([id, row]) => ({
    id, state: row.state, label: row.label, owner_surface: '/ops/operational', verification_route: '/api/operator/release-readiness',
    blocked_until: `${id}_attested`, work_order: `Complete ${row.label}`, evidence_required: [`${row.label} receipt`] })),
  work_orders: Object.entries(RELEASE_REQUIREMENTS).map(([id, row]) => ({
    id: `release:${id}`, title: row.label, status: row.state, owner_surface: '/ops/operational', verification_route: '/api/operator/release-readiness',
    blocked_until: `${id}_attested`, evidence_required: [`${row.label} receipt`] })),
  operator_handoff: { state: 'blocked', control_surface: '/platform/switchboard', release_status_route: '/api/operator/release-readiness',
    protected_request_policy: 'mutating requests require HNC custody and release authority before handlers run',
    operator_can_record_intent: true, operator_can_release_execution: false,
    blocked_requirement_ids: Object.entries(RELEASE_REQUIREMENTS).filter(([, row]) => row.state !== 'integrated').map(([id]) => id) } });
const receipt = (): ReleaseReadinessReceipt => ({ data: readOperatorReleaseReadiness(contract()), loading: false, error: null,
  httpStatus: null, isReceiptCurrent: true, lastReceivedAt: 100_000 });

test('strict held contract preserves unavailable attestations without inventing a source clock', () => {
  const parsed = readOperatorReleaseReadiness(contract());
  assert.equal(parsed.production_ready, false); assert.equal(parsed.source_attestation, null);
  assert.equal(parsed.configuration_attestation, null);
  assert.equal('observed_at' in parsed, false);
  assert.equal(parsed.requirements.length, 7);
  assert.equal(parsed.work_orders.length, 7);
  assert.match(releaseReadinessView(receipt(), 100_000).message, /4 production release work orders still block production; 3 integrated/);
  assert.equal(releaseReadinessView(receipt(), 100_000).state, 'held');
  assert.equal(parsed.operator_handoff.operator_can_record_intent, true);
  assert.equal(parsed.operator_handoff.operator_can_release_execution, false);
});

test('unknown versions, missing fields, positive release claims and arbitrary attestations fail closed', () => {
  for (const patch of [{ schema: 'future' }, { state: 'ready' }, { release_available: true }, { production_ready: true },
    { source_attestation: {} }, { configuration_attestation: 'verified' }, { work_orders: [] },
    { operator_handoff: { ...contract().operator_handoff, operator_can_release_execution: true } },
    { extra: 'secret-bearing-field' }]) {
    assert.throws(() => readOperatorReleaseReadiness({ ...contract(), ...patch }));
  }
  assert.throws(() => readOperatorReleaseReadiness({}));
  const missing: Record<string, unknown> = contract(); delete missing.reason_code;
  assert.throws(() => readOperatorReleaseReadiness(missing));
});

test('duplicate, missing, changed, and unknown requirements cannot become a valid summary', () => {
  const rows = contract().requirements;
  for (const requirements of [[], rows.slice(1), [rows[0], ...rows.slice(0, -1)],
    [{ ...rows[0], id: 'unexpected' }, ...rows.slice(1)], [{ ...rows[0], state: 'verified' }, ...rows.slice(1)],
    [{ ...rows[0], owner_surface: 'https://external.invalid' }, ...rows.slice(1)], [{ ...rows[0], evidence_required: [] }, ...rows.slice(1)]]) {
    assert.throws(() => readOperatorReleaseReadiness({ ...contract(), requirements }));
  }
});

test('work orders must match their held requirements exactly', () => {
  const good = contract();
  assert.equal(readOperatorReleaseReadiness(good).work_orders[0].id, 'release:production_ingress_custody');
  for (const patch of [
    { title: 'Different title' },
    { status: 'verified' },
    { owner_surface: '/wrong' },
    { verification_route: '/wrong' },
    { blocked_until: 'different' },
    { evidence_required: ['different receipt'] },
  ]) {
    const bad = { ...good, work_orders: [{ ...good.work_orders[0], ...patch }, ...good.work_orders.slice(1)] };
    assert.throws(() => readOperatorReleaseReadiness(bad));
  }
});

test('receipt expiry, failures and missing session state never retain a held/current card', () => {
  assert.equal(releaseReadinessView(receipt(), 145_000).state, 'held');
  assert.equal(releaseReadinessView(receipt(), 145_001).state, 'unavailable');
  for (const patch of [{ data: null }, { error: 'failed' }, { isReceiptCurrent: false }, { lastReceivedAt: Infinity },
    { lastReceivedAt: 1e100 }, { lastReceivedAt: null }, { lastReceivedAt: 100_001 }]) {
    const view = releaseReadinessView({ ...receipt(), ...patch }, 100_000);
    assert.equal(view.state, 'unavailable'); assert.equal(view.receivedAt, null);
  }
  assert.match(releaseReadinessView({ ...receipt(), httpStatus: 401 }, 100_000).message, /Sign in/);
  assert.match(releaseReadinessView({ ...receipt(), httpStatus: 403 }, 100_000).message, /cannot read/);
  assert.equal(releaseReadinessView({ ...receipt(), data: null, loading: true }, 100_000).state, 'loading');
});

test('absent or unfamiliar conscience verdicts never acquire approval', () => {
  for (const value of [undefined, null, '', ' ', false, 0]) assert.deepEqual(operatorConscienceVerdict(value), { label: 'Unavailable', approved: false });
  assert.deepEqual(operatorConscienceVerdict('VETO'), { label: 'VETO', approved: false });
  assert.equal(operatorConscienceVerdict('future-verdict').approved, false);
  assert.deepEqual(operatorConscienceVerdict('APPROVED'), { label: 'APPROVED', approved: true });
});

test('chat renders the verdict parser instead of the legacy fabricated approval fallback', () => {
  const source = readFileSync(new URL('../shell/pages/OperatorChatPage.tsx', import.meta.url), 'utf8');
  assert.match(source, /operatorConscienceVerdict\(reply\.conscience_verdict\)/);
  assert.match(source, /reply\.blocked === false && verdict\.approved/);
  assert.doesNotMatch(source, /conscience_verdict\s*\|\|\s*["']APPROVED/);
  assert.match(source, /Operator requests held/);
});
