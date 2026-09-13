import assert from 'node:assert/strict';
import test from 'node:test';
import {
  GOVERNED_ORDER_ACTION_UNAVAILABLE_CODE,
  GOVERNED_ORDER_ACTION_UNAVAILABLE_MESSAGE,
  unavailableTradingAction,
} from './tradingActionAvailability';

test('missing governed dispatch client yields an explicit non-mutating capability receipt', () => {
  const result = unavailableTradingAction('queue_order');

  assert.deepEqual(result, {
    available: false,
    code: GOVERNED_ORDER_ACTION_UNAVAILABLE_CODE,
    message: GOVERNED_ORDER_ACTION_UNAVAILABLE_MESSAGE,
    action: 'queue_order',
    scope: 'analysis_only',
    tenant_runtime_authority: false,
    provider_mutation_attempted: false,
  });
  assert.doesNotMatch(result.message, /queued|submitted|executed|success/i);
});

test('callers cannot override the unavailable authority boundary', () => {
  const result = unavailableTradingAction('force_validated_trade');

  assert.equal(result.available, false);
  assert.equal(result.tenant_runtime_authority, false);
  assert.equal(result.provider_mutation_attempted, false);
  assert.equal(result.scope, 'analysis_only');
});
