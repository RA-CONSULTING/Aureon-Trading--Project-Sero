import { api } from './apiClient';
import { createReadOnlyPoller } from './readOnlyPoller';
import {
  readCompanyCapabilityRuntimeAttestation,
  type CompanyCapabilityRuntimeAttestation,
} from '../lib/companyRoleWorkbenches';

const SOURCE_MAX_AGE_MS = 60_000;

export const companyCapabilityAttestationStore = createReadOnlyPoller<CompanyCapabilityRuntimeAttestation>({
  read: async options => {
    const receipt = readCompanyCapabilityRuntimeAttestation(
      await api.get<unknown>('/api/operator/capability-runtime-attestation', options),
    );
    if (!receipt) throw new Error('Company capability receipt is malformed or exceeds read-only authority');
    return receipt;
  },
  receiptMaxAgeMs: 45_000,
  validateSource: (receipt, nowMs) => {
    const observedAtMs = receipt.observed_at * 1_000;
    if (observedAtMs > nowMs + 5_000) {
      return { status: 'unavailable', reason: 'Capability observation clock is in the future', sourceTimestamp: receipt.observed_at_iso };
    }
    if (nowMs - observedAtMs > SOURCE_MAX_AGE_MS) {
      return { status: 'stale', reason: 'Capability observation expired', sourceTimestamp: receipt.observed_at_iso };
    }
    return { status: 'fresh', sourceTimestamp: receipt.observed_at_iso };
  },
});
