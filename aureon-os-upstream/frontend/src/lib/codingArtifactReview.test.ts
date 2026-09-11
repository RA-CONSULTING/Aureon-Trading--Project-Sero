import assert from 'node:assert/strict';
import test from 'node:test';
import { readCodingDecisionAck, readCodingReview, type CodingDecisionRequest } from './codingArtifactReview';
const hash = 'a'.repeat(64);
const authority = { execution_authority: false, publication_authority: false };
const artifact = { artifact_id: 'job-1', artifact_version: 'build-1', artifact_digest: hash, report_sha256: hash,
  title: 'Fixture artifact', source_report: 'state/forge.json', files: [{ path: 'frontend/public/aureon_test/index.html', sha256: hash, size_bytes: 10 }], ...authority };
const request: CodingDecisionRequest = { artifact_id: 'job-1', artifact_version: 'build-1', artifact_digest: hash,
  expected_decision_id: null, decision: 'approve', note: ' reviewed ', request_key: 'fixture-request-1' };
const receipt = { schema: 'aureon.coding-artifact-decision.v1', receipt_id: 'receipt-1', receipt_digest: hash,
  request_key: request.request_key, artifact, decision: 'approve', note: 'reviewed', recorded_at: 100,
  authenticated: true, actor: { actor_id: 'instance_operator', identity_kind: 'admin', authn_method: 'operator_bearer' },
  scope: 'artifact_review_only', ...authority };
const ack = () => ({ ok: true, persisted: true, receipt: structuredClone(receipt), ...authority });
const view = () => ({ schema: 'aureon.coding-artifact-review.v1', available: true, artifact, decision: null,
  can_decide: true, expected_decision_id: null, observed_at: 100, decision_endpoint_available: true, ...authority });

test('current exact artifact binding and explicit gateway capability are required to enable review', () => {
  assert.equal(readCodingReview(view()).can_decide, true);
  assert.equal(readCodingReview({ ...view(), can_decide: false, decision_endpoint_available: false }).can_decide, false);
  assert.throws(() => readCodingReview({ ...view(), decision_endpoint_available: false }));
  assert.throws(() => readCodingReview({ ...view(), artifact: { ...artifact, artifact_digest: '' } }));
});
test('a successful HTTP response without authenticated durable acknowledgement is rejected', () => {
  assert.equal(readCodingDecisionAck(ack(), request).receipt_id, 'receipt-1');
  for (const override of [{ persisted: false }, { ok: false }, { execution_authority: true }]) assert.throws(() => readCodingDecisionAck({ ...ack(), ...override }, request));
  for (const override of [{ authenticated: false }, { publication_authority: true }, { scope: 'execution' }, { actor: { identity_kind: 'tenant' } }]) {
    assert.throws(() => readCodingDecisionAck({ ...ack(), receipt: { ...receipt, ...override } }, request));
  }
});
test('ACK cannot substitute another version, decision, note or idempotency key', () => {
  for (const override of [{ request_key: 'other-request' }, { decision: 'reject' }, { note: 'unreviewed' },
    { artifact: { ...artifact, artifact_version: 'build-2' } }, { artifact: { ...artifact, artifact_digest: 'b'.repeat(64) } }]) {
    assert.throws(() => readCodingDecisionAck({ ...ack(), receipt: { ...receipt, ...override } }, request));
  }
});
test('a persisted decision can only appear beside its exact artifact and decision head', () => {
  assert.equal(readCodingReview({ ...view(), decision: receipt, can_decide: false, expected_decision_id: 'receipt-1' }).decision?.receipt_id, 'receipt-1');
  assert.throws(() => readCodingReview({ ...view(), decision: receipt }));
  assert.throws(() => readCodingReview({ ...view(), decision: receipt, can_decide: false, expected_decision_id: 'receipt-1', artifact: { ...artifact, artifact_digest: 'b'.repeat(64) } }));
});
