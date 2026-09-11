import { api, ApiError } from './apiClient';
import { createReadOnlyPoller } from './readOnlyPoller';
import type { CognitiveObservation } from './cognitiveReads';

export type AssessmentName = 'metacognition' | 'affect' | 'soul' | 'inner-work' | 'pursuit';
export interface AssessmentPayload extends CognitiveObservation {
  runtime_sources?: Record<string, CognitiveObservation>;
  required_producer_fields?: string[];
  note?: string;
}
const names: AssessmentName[] = ['metacognition', 'affect', 'soul', 'inner-work', 'pursuit'];
// Missing monitor schemas and related producer observations have separate clocks.
export const assessmentStores = Object.fromEntries(names.map(name => [name, createReadOnlyPoller<AssessmentPayload>({
  receiptMaxAgeMs: 45_000,
  read: async options => {
    const payload = await api.get<AssessmentPayload>(`/api/${name}`, options);
    if (!payload || typeof payload !== 'object' || Array.isArray(payload) || typeof payload.available !== 'boolean') {
      throw new ApiError('Assessment response is incomplete', { status: 200, path: `/api/${name}` });
    }
    return payload;
  },
})])) as Record<AssessmentName, ReturnType<typeof createReadOnlyPoller<AssessmentPayload>>>;
