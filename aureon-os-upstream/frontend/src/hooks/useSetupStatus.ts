import { useEffect, useRef } from 'react';
import { ApiError, api } from '../services/apiClient';
import { createReadOnlyPoller } from '../services/readOnlyPoller';
import { useReadOnlyPoller } from './useReadOnlyPoller';
import { CONFIGURATION_RECEIPT_MAX_AGE_MS, readProviderList, setupFromReceipt, type ProviderList, type ProviderView } from '../lib/accountConfigurationEvidence';

const providerStore = createReadOnlyPoller<ProviderList>({
  receiptMaxAgeMs: CONFIGURATION_RECEIPT_MAX_AGE_MS,
  read: async options => {
    const result = readProviderList(await api.get<unknown>('/api/providers', options));
    if (!result) throw new ApiError('Provider configuration response is incomplete', { status: 200, path: '/api/providers' });
    return result;
  },
});

/** One account-scoped configuration read shared by onboarding and key management. */
export function useProviderConfiguration<T extends ProviderView = ProviderView>() {
  const receipt = useReadOnlyPoller(providerStore, 15_000, 8_000);
  return { ...receipt, providers: receipt.data ? receipt.data.providers as T[] : null };
}

export type SetupStatus = ReturnType<typeof setupFromReceipt>;
/** liveProvider means runtime attachment; it never implies a successful test. */
export function useSetupStatus(refreshKey?: number): SetupStatus {
  const receipt = useProviderConfiguration();
  const { invalidate } = receipt;
  const previousKey = useRef(refreshKey);
  useEffect(() => {
    if (previousKey.current !== refreshKey) {
      previousKey.current = refreshKey;
      invalidate();
    }
  }, [refreshKey, invalidate]);
  return setupFromReceipt(receipt);
}
