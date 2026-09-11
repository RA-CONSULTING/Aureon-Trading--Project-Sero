import { api } from './apiClient';
import { createReadOnlyPoller } from './readOnlyPoller';
import type { RuntimeSourceObservation } from '../lib/runtimeSourceStatus';
import { readCompanyRoster, type CompanyRoster } from '../lib/companyRosterEvidence';

export interface CognitiveObservation extends RuntimeSourceObservation {
  available?: boolean;
  source_clock_kind?: string;
  receipt_timestamp?: number;
  classification?: string;
  historical_available?: boolean;
  truth_status?: string;
  generated?: boolean;
  simulated?: boolean;
  [key: string]: unknown;
}
export interface CognitivePayload {
  /** Redacted producer-reported events; separate from cognitive readiness. */
  research_activity?: unknown;
  surfaces?: Record<string, CognitiveObservation>;
  runtime_sources?: Record<string, CognitiveObservation>;
  process_observation?: CognitiveObservation;
  provenance?: { policy?: string; source_registry_count?: number; simulation_fallback_allowed?: boolean };
}
export interface ConsciousnessSurface extends CognitiveObservation {
  key: string; label: string; category: string; purpose: string; route: string;
  safety_posture: string; posture_note?: string; configuration_available?: boolean;
  source_observation?: CognitiveObservation;
}
export interface ConsciousnessPayload {
  categories?: Record<string, { purpose?: string; surfaces?: ConsciousnessSurface[] }>;
  state_of_being?: CognitiveObservation;
  runtime_sources?: Record<string, CognitiveObservation>;
  process_observation?: CognitiveObservation;
  counts?: { total?: number; category_count?: number; by_safety_posture?: Record<string, number> };
}
export interface DefenseModule {
  key: string; name: string; module?: string; group?: string;
  passed?: boolean | null;
  metrics?: Record<string, number | string | null>;
  invariants_passed?: number | null; invariants_total?: number | null;
  evidence?: string; truth_status?: string;
  runtime_observation?: CognitiveObservation;
}
export interface DefenseGroup {
  label?: string; purpose?: string; module_count?: number; passing?: number;
  modules?: DefenseModule[];
}
export interface DefensePayload {
  generated_at?: string | number | null;
  group_order?: string[];
  groups?: Record<string, DefenseGroup>;
  counts?: { total?: number; passing?: number; groups?: number };
  report_observation?: CognitiveObservation;
  note?: string; truth_status?: string;
}
export interface CognitiveFieldPayload {
  surface?: string;
  data?: CognitiveObservation & {
    available?: boolean;
    fresh?: boolean;
    max_age_seconds?: number;
    canonical?: CognitiveObservation & {
      available?: boolean;
      data_status?: string;
      freshness_status?: string;
      generated_values?: boolean;
      lambda_t?: number;
      coherence_gamma?: number;
      consciousness_psi?: number;
      receipt_id?: string;
    };
  };
}

// Catalogues and historical reports have no single live clock. Their individual
// observations are checked by the view; the 45s limit only expires HTTP receipts.
export const cognitionStore = createReadOnlyPoller<CognitivePayload>({
  read: options => api.get<CognitivePayload>('/api/cognition', options), receiptMaxAgeMs: 45_000,
});
export const consciousnessStore = createReadOnlyPoller<ConsciousnessPayload>({
  read: options => api.get<ConsciousnessPayload>('/api/consciousness', options), receiptMaxAgeMs: 45_000,
});
export const defenseStore = createReadOnlyPoller<DefensePayload>({
  read: options => api.get<DefensePayload>('/api/defense', options), receiptMaxAgeMs: 45_000,
});
export const cognitionFieldStore = createReadOnlyPoller<CognitiveFieldPayload>({
  read: options => api.get<CognitiveFieldPayload>('/api/cognition/field', options), receiptMaxAgeMs: 10_000,
});
export const companyRosterStore = createReadOnlyPoller<CompanyRoster>({
  read: async options => {
    const roster = readCompanyRoster(await api.get<unknown>('/api/company', options));
    if (!roster) throw new Error('Company roster response is malformed or internally inconsistent');
    return roster;
  },
  receiptMaxAgeMs: 45_000,
});
