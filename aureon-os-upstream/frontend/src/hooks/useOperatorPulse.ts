import { ApiError, fetchPulse, type OperatorPulse } from '../services/apiClient';
import { createReadOnlyPoller } from '../services/readOnlyPoller';
import { useReadOnlyPoller } from './useReadOnlyPoller';

export interface PulseState {
  pulse: OperatorPulse | null;
  offline: boolean;
  loading: boolean;
  error: string | null;
  /** Browser HTTP completion time; does not attest provider/source freshness. */
  lastOkAt: number | null;
}

const pulseStore = createReadOnlyPoller<OperatorPulse>({
  receiptMaxAgeMs: 45_000,
  read: async options => {
    const pulse = await fetchPulse(options);
    if (!pulse || pulse.ok !== true) throw new ApiError('Operator pulse unavailable', { path: '/api/pulse' });
    return pulse;
  },
  // The composed pulse has no whole-payload original source clock. This
  // receipt permits configuration display, not a claim of live provider data.
  validateSource: pulse => pulse.stale === true
    ? { status: 'stale', reason: 'Operator pulse reports stale data' }
    : { status: 'unattested', reason: 'HTTP configuration receipt; individual source freshness is not attested' },
});

/** Shared, sequential safe GET. Failure/expiry removes the current pulse. */
export function useOperatorPulse(intervalMs = 15_000, timeoutMs = 20_000) {
  const receipt = useReadOnlyPoller(pulseStore, intervalMs, timeoutMs);
  return { pulse: receipt.data, offline: receipt.offline, loading: receipt.loading,
    error: receipt.error, lastOkAt: receipt.lastReceivedAt,
    source: receipt.source, refresh: receipt.refresh, invalidate: receipt.invalidate };
}
