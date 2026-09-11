import assert from 'node:assert/strict';
import test from 'node:test';
import { assessmentDependencies, assessmentSchemaComplete, currentAssessment } from './assessmentEvidence';
import type { AssessmentPayload, AssessmentName } from '../services/assessmentReads';

const now = 1_800_000_000_000;
const meta: AssessmentPayload = { available: true, fresh: true, read_state: 'observed', truth_status: 'real_derived',
  source_timestamp: now / 1000 - 1, source_clock_kind: 'producer_timestamp', max_age_seconds: 300 };
test('each missing assessment retains the exact producer dependency without substituting another model', () => {
  for (const name of ['metacognition', 'affect', 'soul', 'inner-work', 'pursuit'] as AssessmentName[]) {
    const payload: AssessmentPayload = { available: false, truth_status: 'no_data', source_timestamp: null,
      reason: 'complete_producer_assessment_snapshot_not_published', required_producer_fields: ['source_timestamp', 'producer', 'input_observations', name],
      runtime_sources: { queen_report: { ...meta, cycle: 42 } } };
    assert.equal(currentAssessment(payload, now, name), payload);
    assert.equal(currentAssessment(payload, now, name)?.available, false);
    assert.deepEqual(assessmentDependencies(payload).fields, payload.required_producer_fields);
  }
});
test('monitor source expires at the existing15s gate despite a new HTTP or longer related report TTL', () => {
  assert.equal(currentAssessment(meta, now), meta);
  assert.equal(currentAssessment({ ...meta, receipt_timestamp: now / 1000 + 100 }, now + 15_000), null);
  assert.equal(currentAssessment({ ...meta, max_age_seconds: 1 }, now + 1000), null);
  assert.equal(currentAssessment({ ...meta, fresh: false }, now), null);
});
test('partial current monitor schemas are withheld instead of zero-filling or unsafe legacy formatting', () => {
  for (const name of ['metacognition', 'affect', 'soul', 'inner-work', 'pursuit'] as AssessmentName[]) {
    assert.equal(assessmentSchemaComplete(name, meta), false);
    assert.equal(currentAssessment(meta, now, name), null);
  }
  const affect = { ...meta, victory: 0, defeat: 0, fear: 0, resolve: 0, valence: 0, arousal: 0, caution_bias: 0, affect_phase: 'measured', signals: {} };
  assert.equal(currentAssessment(affect, now, 'affect'), affect);
  assert.equal(currentAssessment({ ...affect, fear: null }, now, 'affect'), null);
});
test('missing or malformed dependency lists remain explicit and bounded', () => {
  assert.deepEqual(assessmentDependencies(null).fields, []);
  assert.equal(assessmentDependencies({ required_producer_fields: Array(60).fill('field') }).fields.length, 50);
  assert.match(assessmentDependencies(null).reason, /unavailable/);
});
