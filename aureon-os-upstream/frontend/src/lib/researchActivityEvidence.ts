type ObjectValue = Record<string, unknown>;
const object = (value: unknown): ObjectValue | null => value !== null && typeof value === 'object' && !Array.isArray(value) ? value as ObjectValue : null;
const count = (value: unknown): number | null => typeof value === 'number' && Number.isSafeInteger(value) && value >= 0 ? value : null;
const flag = (value: unknown): boolean | null => typeof value === 'boolean' ? value : null;
const member = (value: unknown, choices: readonly string[]): string | null => typeof value === 'string' && choices.includes(value) ? value : null;
const MODES = ['proactive', 'topic', 'questions', 'actuator'] as const;
const LEARNING_COUNTS = ['absorbed', 'contested_stored', 'dropped'] as const;
const RESEARCH_COUNTS = ['questions_processed', 'items_pulled', 'fragments_added', 'items_filtered_novelty', 'novelty_errors', 'corroborated_items', 'questions_marked_researched'] as const;

export interface ActivityRow {
  mode?: string; status: 'recent' | 'history' | 'dry_run' | 'unavailable';
  sourceTime: string | null; outcome: string | null; dryRun: boolean | null;
  counts: Record<string, number | null>; ingesterCounts: Record<string, number | null>;
  gate: Record<string, boolean | string | null> | null; reason: string;
}
export interface ActivitySource {
  available: boolean; reason: string; rows: ActivityRow[];
  truncated: boolean; partialLastRecord: boolean; invalidRecords: number | null;
}
export interface ResearchActivityView { learning: ActivitySource; research: ActivitySource }
const unavailable = (mode?: string): ActivityRow => ({ mode, status: 'unavailable', sourceTime: null,
  outcome: null, dryRun: null, counts: {}, ingesterCounts: {}, gate: null, reason: 'Valid original activity record unavailable.' });
const missing = (): ActivitySource => ({ available: false, reason: 'Source file unavailable or invalid.',
  rows: [], truncated: false, partialLastRecord: false, invalidRecords: null });
const mapCounts = (value: unknown, keys: readonly string[]) => {
  const values = object(value);
  return Object.fromEntries(keys.map(key => [key, count(values?.[key])]));
};

function originalEpoch(value: unknown): number | null {
  const result = typeof value === 'number' ? value
    : typeof value === 'string' && /(?:Z|[+-]\d{2}:\d{2})$/.test(value) ? Date.parse(value) / 1_000 : NaN;
  return Number.isFinite(result) && result > 0 && result < 253402300800 ? result : null;
}
function readRow(value: unknown, nowMs: number, learning: boolean, mode?: string): ActivityRow {
  const row = object(value);
  const empty = unavailable(mode);
  if (!row || ['missing', 'failed'].includes(String(row.read_state))) return empty;
  const stamp = originalEpoch(row.source_timestamp);
  const original = originalEpoch(row.source_timestamp_original);
  if (stamp === null || original === null || Math.abs(stamp - original) > 0.001
    || row.source_clock_kind !== 'producer_run_start' || row.max_age_seconds !== 300 || !Number.isFinite(nowMs)) return empty;
  const age = nowMs / 1000 - stamp;
  if (age < -5) return empty;
  const dryRun = learning ? flag(row.dry_run) : null;
  const outcome = member(row.outcome, learning
    ? ['absorbed', 'refused', 'deferred', 'no_intent', 'held_incoherent', 'vetoed'] : ['researched']);
  if (!outcome || (learning && dryRun === null)
    || (mode && row.mode !== mode)
    || (learning && row.classification !== (dryRun ? 'dry_run_record' : 'recorded_activity'))
    || (!learning && row.classification !== 'recorded_activity')) return empty;
  const rawGate = learning ? object(row.gate) : null;
  const gate = rawGate ? {
    passed: flag(rawGate.passed), outcome: member(rawGate.outcome, ['authorized', 'vetoed', 'held_incoherent', 'deferred']),
    conscience_verdict: member(rawGate.conscience_verdict, ['APPROVED', 'CONCERNED', 'VETO', 'TEACHING_MOMENT']),
    coherence_passed: flag(rawGate.coherence_passed), authorization_passed: flag(rawGate.authorization_passed),
    authorization_verdict: member(rawGate.authorization_verdict, ['ALLOW', 'HOLD', 'DENY']),
    record_consistent: flag(rawGate.record_consistent),
  } : null;
  if (gate?.passed === true && (gate.record_consistent !== true || gate.conscience_verdict === null || gate.conscience_verdict === 'VETO'
    || gate.coherence_passed !== true || gate.authorization_passed !== true
    || gate.authorization_verdict !== 'ALLOW' || gate.outcome !== 'authorized')) gate.passed = null;
  const status = dryRun ? 'dry_run' : row.recent === true && age <= 300 ? 'recent' : 'history';
  return { mode, status, sourceTime: new Date(stamp * 1_000).toISOString(), outcome, dryRun,
    counts: mapCounts(row.reported_counts, learning ? LEARNING_COUNTS : RESEARCH_COUNTS),
    ingesterCounts: learning ? {} : mapCounts(row.reported_ingester_counts, ['items_pulled', 'vault_ingests', 'errors']),
    gate, reason: status === 'recent' ? 'Recorded run start is within 300 seconds.'
      : status === 'dry_run' ? 'Dry-run record; excluded from recent operational activity.'
      : 'Dated history; no current activity or successful knowledge commit is inferred.' };
}

/** A fresh HTTP receipt never redates an event or promotes dry-run records. */
export function readResearchActivity(value: unknown, nowMs = Date.now()): ResearchActivityView {
  const root = object(value);
  if (!root || root.schema_version !== 'aureon-research-activity-v1'
    || root.measurement_kind !== 'producer_reported_activity' || root.recent_window_seconds !== 300) {
    return { learning: missing(), research: missing() };
  }
  const learningRaw = object(root.learning_will);
  const researchRaw = object(root.research_faculty);
  let learning = missing();
  let research = missing();
  if (learningRaw?.source_id === 'learning_will' && ['observed', 'empty'].includes(String(learningRaw.read_state))
    && Array.isArray(learningRaw.events) && learningRaw.events.length <= 10) {
    const coverage = object(learningRaw.coverage);
    if (coverage?.scope === 'current_journal_file_only' && coverage.includes_rotated_or_pid_sidecars === false) {
      learning = { available: true,
        reason: learningRaw.read_state === 'empty' ? 'The current journal file contains no records.'
          : 'Current journal file only; rotated history and per-process fallback files are not included.',
        rows: learningRaw.events.map(row => readRow(row, nowMs, true)),
        truncated: coverage.start_truncated === true || (count(coverage.records_omitted_from_tail) ?? 0) > 0,
        partialLastRecord: coverage.partial_last_record === true, invalidRecords: count(coverage.invalid_records) };
    }
  }
  if (researchRaw?.source_id === 'research_faculty' && researchRaw.read_state === 'observed'
    && Array.isArray(researchRaw.records) && researchRaw.records.length <= 4) {
    const coverage = object(researchRaw.coverage);
    const rawRows = researchRaw.records.map(object);
    const modes = rawRows.map(row => member(row?.mode, MODES));
    if (coverage?.scope === 'last_recorded_run_per_named_mode' && coverage.includes_unrecorded_attempts === false
      && modes.every(mode => mode !== null) && new Set(modes).size === modes.length) {
      research = { available: true, reason: 'Last persisted run per mode; unrecorded attempts and current gate decisions are not included.',
        rows: MODES.map(mode => readRow(rawRows.find(row => row?.mode === mode), nowMs, false, mode)),
        truncated: false, partialLastRecord: false, invalidRecords: null };
    }
  }
  return { learning, research };
}
