import assert from 'node:assert/strict';
import test from 'node:test';
import { readResearchActivity } from './researchActivityEvidence';

const NOW = 1788890400000;
function row(age = 20) {
  return { source_timestamp: NOW / 1000 - age, source_timestamp_original: NOW / 1000 - age,
    source_clock_kind: 'producer_run_start', max_age_seconds: 300, recent: true,
    classification: 'recorded_activity', outcome: 'absorbed', dry_run: false,
    reported_counts: { absorbed: 0, contested_stored: 2 }, gate: null };
}
function fixture() {
  return { schema_version: 'aureon-research-activity-v1', measurement_kind: 'producer_reported_activity', recent_window_seconds: 300,
    learning_will: { source_id: 'learning_will', read_state: 'observed', file_read_at: NOW / 1000,
      events: [row()], coverage: { scope: 'current_journal_file_only', includes_rotated_or_pid_sidecars: false,
        start_truncated: false, partial_last_record: false, invalid_records: 0, records_omitted_from_tail: 0 } },
    research_faculty: { source_id: 'research_faculty', read_state: 'observed', file_read_at: NOW / 1000,
      records: [{ ...row(), mode: 'topic', read_state: 'observed', outcome: 'researched', reported_counts: { questions_processed: 0, items_pulled: 2 } }],
      coverage: { scope: 'last_recorded_run_per_named_mode', includes_unrecorded_attempts: false } } };
}

test('original recorded counts preserve zero and missing counts remain unavailable', () => {
  const view = readResearchActivity(fixture(), NOW);
  assert.equal(view.learning.rows[0].status, 'recent');
  assert.deepEqual(view.learning.rows[0].counts, { absorbed: 0, contested_stored: 2, dropped: null });
  assert.equal(view.research.rows[1].counts.questions_processed, 0);
  assert.equal(view.research.rows[1].counts.fragments_added, null);
  assert.deepEqual(view.research.rows.map(row => row.status), ['unavailable', 'recent', 'unavailable', 'unavailable']);
});

test('the original clock independently expires at 300 seconds even after fresh HTTP/file reads', () => {
  const value = fixture();
  value.learning_will.events = [row(300)];
  assert.equal(readResearchActivity(value, NOW).learning.rows[0].status, 'recent');
  value.learning_will.file_read_at = (NOW + 1) / 1000;
  const expired = readResearchActivity(value, NOW + 1).learning.rows[0];
  assert.equal(expired.status, 'history');
  assert.equal(expired.sourceTime, new Date(NOW - 300000).toISOString());
});

test('backend rejection cannot be promoted by a frontend clock', () => {
  const value = fixture();
  value.learning_will.events[0].recent = false;
  assert.equal(readResearchActivity(value, NOW).learning.rows[0].status, 'history');
});

test('dry-run records remain separately labelled even if falsely marked recent', () => {
  const value = fixture();
  Object.assign(value.learning_will.events[0], { dry_run: true, classification: 'dry_run_record', recent: true });
  assert.equal(readResearchActivity(value, NOW).learning.rows[0].status, 'dry_run');
});

test('missing/malformed source, false producer, unknown schemas and absent source clocks do not create activity', () => {
  for (const value of [undefined, null, [], {}, { ...fixture(), schema_version: 'fixture' }]) {
    const view = readResearchActivity(value, NOW);
    assert.equal(view.learning.available, false);
    assert.equal(view.research.available, false);
  }
  const value = fixture();
  value.learning_will.source_id = 'unknown';
  value.research_faculty.read_state = 'failed';
  const view = readResearchActivity(value, NOW);
  assert.equal(view.learning.available, false);
  assert.equal(view.research.available, false);
});

test('clock mismatch, future, extended TTL, malformed booleans and invalid local time fail closed', () => {
  for (const change of [
    { source_timestamp_original: null }, { source_timestamp_original: NOW / 1000 },
    { source_timestamp: Infinity }, { source_clock_kind: 'http_receipt' },
    { source_timestamp: NOW / 1000 + 6, source_timestamp_original: NOW / 1000 + 6 },
    { max_age_seconds: 600 }, { dry_run: 'false' }, { outcome: 'healthy' },
  ]) {
    const value = fixture();
    Object.assign(value.learning_will.events[0], change);
    assert.equal(readResearchActivity(value, NOW).learning.rows[0].status, 'unavailable');
  }
  assert.equal(readResearchActivity(fixture(), NaN).learning.rows[0].status, 'unavailable');
});

test('ISO original timestamp is retained by value while missing timezone is rejected', () => {
  const value = fixture();
  Object.assign(value.learning_will.events[0], { source_timestamp_original: new Date(NOW - 20000).toISOString() });
  assert.equal(readResearchActivity(value, NOW).learning.rows[0].sourceTime, new Date(NOW - 20000).toISOString());
  Object.assign(value.learning_will.events[0], { source_timestamp_original: new Date(NOW - 20000).toISOString().slice(0, -1) });
  assert.equal(readResearchActivity(value, NOW).learning.rows[0].status, 'unavailable');
});

test('redacts arbitrary fields and invalid counters instead of coercing them', () => {
  const value = fixture();
  const privateText = 'PRIVATE_TOPIC_URL_CANDIDATE';
  Object.assign(value.learning_will.events[0], { intent: privateText, receipt: privateText,
    reported_counts: { absorbed: true, contested_stored: '2', dropped: -1, secret: privateText } });
  const view = readResearchActivity(value, NOW);
  assert.deepEqual(view.learning.rows[0].counts, { absorbed: null, contested_stored: null, dropped: null });
  assert.equal(JSON.stringify(view).includes(privateText), false);
});

test('mode duplicates and unproven research coverage are rejected independently', () => {
  const value = fixture();
  value.research_faculty.records.push(value.research_faculty.records[0]);
  assert.equal(readResearchActivity(value, NOW).research.available, false);
  assert.equal(readResearchActivity(value, NOW).learning.available, true);
  value.research_faculty.records.pop();
  value.research_faculty.coverage.includes_unrecorded_attempts = true;
  assert.equal(readResearchActivity(value, NOW).research.available, false);
});

test('tail coverage is visible and an unavailable final record does not promote prior history', () => {
  const value = fixture();
  Object.assign(value.learning_will.coverage, { start_truncated: true, partial_last_record: true, invalid_records: 2 });
  Object.assign(value.learning_will, { events: [row(), { read_state: 'failed', reason_code: 'source_timestamp_future' }] });
  const view = readResearchActivity(value, NOW).learning;
  assert.equal(view.truncated, true);
  assert.equal(view.partialLastRecord, true);
  assert.equal(view.invalidRecords, 2);
  assert.equal(view.rows.at(-1)?.status, 'unavailable');
});

test('complete recorded gates are separate data; contradictions and missing stages suppress passed', () => {
  const value = fixture();
  const gate = { passed: true, outcome: 'authorized', conscience_verdict: 'APPROVED',
    coherence_passed: true, authorization_passed: true, authorization_verdict: 'ALLOW', record_consistent: true };
  Object.assign(value.learning_will.events[0], { gate });
  assert.equal(readResearchActivity(value, NOW).learning.rows[0].gate?.passed, true);
  gate.authorization_verdict = 'DENY';
  assert.equal(readResearchActivity(value, NOW).learning.rows[0].gate?.passed, null);
  Object.assign(value.learning_will.events[0], { gate: { passed: true, record_consistent: true } });
  assert.equal(readResearchActivity(value, NOW).learning.rows[0].gate?.passed, null);
});

test('empty observed journal yields no invented row and oversized payloads are refused', () => {
  const value = fixture();
  value.learning_will.events = [];
  value.learning_will.read_state = 'empty';
  assert.deepEqual(readResearchActivity(value, NOW).learning.rows, []);
  value.learning_will.events = Array.from({ length: 11 }, () => row());
  assert.equal(readResearchActivity(value, NOW).learning.available, false);
});
