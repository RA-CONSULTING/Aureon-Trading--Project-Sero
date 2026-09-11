import assert from 'node:assert/strict';
import test from 'node:test';
import { renderToStaticMarkup } from 'react-dom/server';
import { CognitiveRuntimeObservations } from './cognitiveEvidenceCards';

const now = 2_000_000;
const meta = { source_timestamp: 1995, source_clock_kind: 'producer_timestamp', max_age_seconds: 300,
  available: true, fresh: true, read_state: 'observed' };
test('actual Queen fields render zero and false under the original report clock', () => {
  const html = renderToStaticMarkup(<CognitiveRuntimeObservations now={now} sources={{ queen_report: {
    ...meta, measurement_kind: 'computed_runtime_report', cycle: 0,
    metacognition_state: { reflection_count: 0, insight_count: 4 },
    consciousness: { awakening_index: 0, learning_active: false },
  } }} />);
  assert.match(html, /Report cycle/); assert.match(html, /Reflection count/);
  assert.match(html, />0</); assert.match(html, />No</);
  assert.match(html, /Unavailable/); // absent report metrics are not filled
  assert.match(html, /computed software measurements/);
});
test('expired Queen and process snapshots hide old metric and PID values', () => {
  const html = renderToStaticMarkup(<CognitiveRuntimeObservations now={2_400_000} sources={{ queen_report: {
    ...meta, measurement_kind: 'computed_runtime_report', consciousness: { level: 'OLD_PRIVATE_FIXTURE' },
  } }} process={{ ...meta, max_age_seconds: 15, source_clock_kind: 'os_process_measurement',
    organs: [{ name: 'OLD_PROCESS_FIXTURE', pid: 123456, pid_running: true, identity_verified: true }],
  }} />);
  assert.doesNotMatch(html, /OLD_PRIVATE_FIXTURE|OLD_PROCESS_FIXTURE|123456/);
  assert.match(html, /Current Queen report measurements unavailable/);
  assert.match(html, /Current process observations unavailable/);
});
