import assert from 'node:assert/strict';
import test from 'node:test';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { setAuthTokenProvider } from '../../services/apiClient';
import { assessmentStores, type AssessmentName } from '../../services/assessmentReads';
import MetacognitionPage from './MetacognitionPage';
import AffectPage from './AffectPage';
import SoulPage from './SoulPage';
import InnerWorkPage from './InnerWorkPage';
import PursuitPage from './PursuitPage';

test('all five actual monitor pages render passive no_data fixtures through the authenticated shared GET owner', async () => {
  const originalFetch = globalThis.fetch;
  const unsubscribers: (() => void)[] = [];
  const calls: string[] = [];
  const pages = { metacognition: MetacognitionPage, affect: AffectPage, soul: SoulPage, 'inner-work': InnerWorkPage, pursuit: PursuitPage };
  setAuthTokenProvider(async () => 'fixture-bearer');
  globalThis.fetch = async (input, options) => {
    const path = String(input); assert.ok(Object.keys(pages).some(name => path === `/api/${name}`));
    assert.equal(options?.method, 'GET');
    assert.equal(new Headers(options?.headers).get('Authorization'), 'Bearer fixture-bearer');
    calls.push(path);
    return new Response(JSON.stringify({ available: false, fresh: false, truth_status: 'no_data', source_timestamp: null,
      reason: 'complete_producer_assessment_snapshot_not_published',
      required_producer_fields: ['source_timestamp', 'producer', 'input_observations'],
      runtime_sources: { queen_report: { available: true, fresh: true, read_state: 'observed', source_timestamp: Date.now() / 1000,
        source_clock_kind: 'producer_timestamp', max_age_seconds: 300, measurement_kind: 'computed_runtime_report', cycle: 42,
        metacognition_state: { reflection_count: 0, insight_count: 3 }, consciousness: { learning_active: false } } },
    }), { status: 200, headers: { 'Content-Type': 'application/json' } });
  };
  try {
    await Promise.all(Object.keys(pages).map(name => new Promise<void>(resolve => {
      const store = assessmentStores[name as AssessmentName];
      unsubscribers.push(store.subscribe(() => { if (!store.getSnapshot().loading) resolve(); }, 5000, 8000));
    })));
    for (const Page of Object.values(pages)) {
      const html = renderToStaticMarkup(createElement(Page));
      assert.match(html, /complete_producer_assessment_snapshot_not_published/);
      assert.match(html, /Required producer evidence/); assert.match(html, /input_observations/);
      assert.match(html, /Queen runtime report/); assert.match(html, /Report cycle/); assert.match(html, />42</);
      assert.doesNotMatch(html, /NaN|undefined|honest silence|loop lights up/);
    }
    assert.equal(calls.length, 5);
  } finally {
    unsubscribers.forEach(unsubscribe => unsubscribe());
    globalThis.fetch = originalFetch;
    setAuthTokenProvider(null);
  }
  for (const store of Object.values(assessmentStores)) assert.equal(store.getSnapshot().data, null);
});
