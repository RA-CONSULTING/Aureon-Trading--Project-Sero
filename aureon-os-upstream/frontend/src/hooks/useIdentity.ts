import { ApiError, api } from '../services/apiClient';
import { createReadOnlyPoller } from '../services/readOnlyPoller';
import { useReadOnlyPoller } from './useReadOnlyPoller';
import { CONFIGURATION_RECEIPT_MAX_AGE_MS, configurationStatus, readIdentity, UNKNOWN_IDENTITY, type Identity } from '../lib/accountConfigurationEvidence';
export type { Identity, IdentityKind } from '../lib/accountConfigurationEvidence';

const identityStore = createReadOnlyPoller<Identity>({
  receiptMaxAgeMs: CONFIGURATION_RECEIPT_MAX_AGE_MS,
  read: async options => {
    const identity = readIdentity(await api.get<unknown>('/api/me', options));
    if (!identity) throw new ApiError('Identity response is incomplete', { status: 200, path: '/api/me' });
    return identity;
  },
});

/** Identity presentation follows this session's current GET receipt; backend authorization is unchanged. */
export function useIdentity() {
  const receipt = useReadOnlyPoller(identityStore, 15_000, 8_000);
  const status = configurationStatus(receipt);
  return { identity: receipt.data ?? UNKNOWN_IDENTITY, known: status === 'observed', status,
    loading: receipt.loading, offline: receipt.offline, error: receipt.error,
    httpStatus: receipt.httpStatus, lastReceivedAt: receipt.lastReceivedAt,
    refresh: receipt.refresh, invalidate: receipt.invalidate };
}
