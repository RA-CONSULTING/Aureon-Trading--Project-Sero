import React from 'react';
import assert from 'node:assert/strict';
import test from 'node:test';
import { renderToStaticMarkup } from 'react-dom/server';
import { ResearchActivityCard } from './ResearchActivityCard';

test('missing reports remain visible and no synthetic activity counts or action controls render', () => {
  const html = renderToStaticMarkup(<ResearchActivityCard value={undefined} now={1788890400000} />);
  assert.match(html, /Source file unavailable or invalid/);
  assert.match(html, /Activity record unavailable/);
  assert.match(html, /Research records unavailable/);
  assert.match(html, /excluded from cognitive readiness totals/);
  assert.doesNotMatch(html, /<button|Recent recorded activity|>0</);
});

test('dated dry runs and partial coverage render explicitly without exposing source contents', () => {
  const now = 1788890400000;
  const value = { schema_version: 'aureon-research-activity-v1', measurement_kind: 'producer_reported_activity', recent_window_seconds: 300,
    learning_will: { source_id: 'learning_will', read_state: 'observed', coverage: {
      scope: 'current_journal_file_only', includes_rotated_or_pid_sidecars: false, start_truncated: true,
      partial_last_record: true, invalid_records: 1 }, events: [{
      source_timestamp: now / 1000 - 10, source_timestamp_original: now / 1000 - 10,
      source_clock_kind: 'producer_run_start', max_age_seconds: 300, recent: true, dry_run: true,
      classification: 'dry_run_record', outcome: 'absorbed', reported_counts: { absorbed: 0 },
      intent: 'PRIVATE_QUESTION', gate: null }] } };
  const html = renderToStaticMarkup(<ResearchActivityCard value={value} now={now} />);
  assert.match(html, /Dry-run record/);
  assert.match(html, /Run started: 2026-09-08T/);
  assert.match(html, /Bounded tail; older records omitted/);
  assert.match(html, /incomplete trailing record was withheld/);
  assert.match(html, /Counts do not prove committed knowledge/);
  assert.match(html, /Reported absorbed/);
  assert.match(html, /Unavailable/);
  assert.doesNotMatch(html, /PRIVATE_QUESTION|Recent recorded activity|<button/);
});
