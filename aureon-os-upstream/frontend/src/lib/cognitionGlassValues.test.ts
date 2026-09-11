import assert from 'node:assert/strict';
import test from 'node:test';
import { currentModelSignal, modelPercent, modelPercentLabel, reportedModelStage, reportedWorkOutcome } from './cognitionGlassValues';

test('model ratios preserve observed zero and reject missing or out-of-range values instead of clamping', () => {
  assert.equal(modelPercent(0), 0);
  assert.equal(modelPercentLabel(0), '0%');
  assert.equal(modelPercentLabel(0.275), '28%');
  for (const value of [null, undefined, NaN, Infinity, '0.5', -0.01, 1.01]) {
    assert.equal(modelPercent(value), null);
    assert.equal(modelPercentLabel(value), 'Unavailable');
  }
});
test('child signal numerics cannot override missing, fixture or expired provenance', () => {
  for (const status of ['live', 'real_observed', 'real_derived']) assert.equal(currentModelSignal(0, status), 0);
  for (const status of ['no_data', 'test_fixture', 'cached_real', undefined, 'unknown']) assert.equal(currentModelSignal(0.9, status), null);
  assert.equal(currentModelSignal(NaN, 'live'), null);
});
test('reported symbolic stage must be an integer within the model taxonomy', () => {
  assert.equal(reportedModelStage(0, 7), 0);
  assert.equal(reportedModelStage(7, 7), 7);
  for (const value of [null, -1, 1.5, 8, '2']) assert.equal(reportedModelStage(value, 7), null);
});
test('work outcome labels preserve source reporting and do not invent completed execution', () => {
  assert.equal(reportedWorkOutcome(null), 'Outcome unreported');
  assert.equal(reportedWorkOutcome({ executed: 'true' }), 'Outcome unreported');
  assert.equal(reportedWorkOutcome({ executed: true }), 'Producer reports executed');
  assert.equal(reportedWorkOutcome({ dry_run: true, executed: true }), 'Reported dry-run');
  assert.equal(reportedWorkOutcome({ blocked: true, executed: true }), 'Reported blocked');
});
