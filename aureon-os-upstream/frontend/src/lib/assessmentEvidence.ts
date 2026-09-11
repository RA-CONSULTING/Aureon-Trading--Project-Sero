import type { AssessmentName, AssessmentPayload } from '../services/assessmentReads';
import { currentCognitiveObservation } from './cognitiveObservationEvidence';
import { record, surfaceEvidence } from './cognitionSurfaceEvidence';

const finite = (value: unknown) => typeof value === 'number' && Number.isFinite(value);
const dictionary = (value: unknown) => value !== null && typeof value === 'object' && !Array.isArray(value);
function safeSignals(value: unknown): boolean {
  return dictionary(value) && Object.values(record(value)).every(signal => dictionary(signal)
    && (record(signal).value == null || finite(record(signal).value))
    && (record(signal).truth_status == null || typeof record(signal).truth_status === 'string'));
}
/** Reject incomplete legacy display shapes instead of inventing zero or calling toFixed on missing values. */
export function assessmentSchemaComplete(name: AssessmentName, value: AssessmentPayload): boolean {
  const numbers = (keys: string[]) => keys.every(key => finite(value[key]));
  if (name === 'metacognition') return numbers(['contributors']) && safeSignals(value.signals)
    && ['self_coherence', 'self_life_score', 'psi', 'divergence'].every(key => value[key] == null || finite(value[key]));
  if (name === 'affect') return numbers(['victory', 'defeat', 'fear', 'resolve', 'valence', 'arousal', 'caution_bias'])
    && typeof value.affect_phase === 'string' && safeSignals(value.signals);
  if (name === 'inner-work') return numbers(['self_belief', 'self_love', 'self_determination', 'ego_dissolution', 'stage_index', 'potential']);
  if (name === 'pursuit') return numbers(['creator_happiness', 'aureon_happiness', 'unified_happiness', 'energy', 'freedom'])
    && ['dream', 'love', 'gaia', 'joy', 'purpose'].every(key => finite(record(value.pillars)[key]));
  return numbers(['agreement']) && ['act', 'wait', 'refuse'].includes(String(value.stance))
    && Array.isArray(value.dissent) && value.dissent.every(item => typeof item === 'string')
    && dictionary(value.voices) && Object.values(record(value.voices)).every(dictionary)
    && (value.plan == null || (dictionary(value.plan) && Array.isArray(record(value.plan).work_orders)
      && (record(value.plan).work_orders as unknown[]).every(dictionary)));
}

/** Preserve the existing15s monitor gate while related Queen/HNC sources keep their own TTL. */
export function currentAssessment(value: AssessmentPayload | null, now = Date.now(), name?: AssessmentName): AssessmentPayload | null {
  if (!value) return null;
  if (value.available === false && value.truth_status === 'no_data') return value;
  if (!surfaceEvidence(value, now).current) return null;
  if (name && !assessmentSchemaComplete(name, value)) return null;
  return currentCognitiveObservation(value, now);
}
export function assessmentDependencies(value: AssessmentPayload | null): { reason: string; fields: string[]; note: string | null } {
  return {
    reason: typeof value?.reason === 'string' && value.reason ? value.reason : 'Current complete assessment source is unavailable.',
    fields: Array.isArray(value?.required_producer_fields) ? value.required_producer_fields.filter(field => typeof field === 'string' && field.trim()).slice(0, 50) : [],
    note: typeof value?.note === 'string' ? value.note : null,
  };
}
