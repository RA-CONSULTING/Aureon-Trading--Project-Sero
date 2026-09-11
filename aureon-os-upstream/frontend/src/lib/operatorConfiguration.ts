import type { OperatorPulse } from '../services/apiClient';
import { runtimeSourceFresh } from './runtimeSourceStatus';

export interface OperatorConfigurationReceipt {
  pulse: OperatorPulse | null;
  error: string | null;
  offline: boolean;
  loading: boolean;
  lastOkAt: number | null;
}

/** These are configuration values read at receipt time, not provider health. */
export function readOperatorConfiguration(receipt: OperatorConfigurationReceipt, nowMs = Date.now()) {
  const { pulse, error, offline, loading, lastOkAt } = receipt;
  if (!pulse || pulse.ok !== true || error || offline || loading || lastOkAt == null
    || !Number.isFinite(lastOkAt) || nowMs < lastOkAt || nowMs - lastOkAt > 45_000) return [];

  const items: Array<{ label: string; value: string }> = [];
  if (Array.isArray(pulse.providers)) {
    const attached = pulse.providers.filter(value => {
      if (!value || typeof value !== 'object') return false;
      const row = value as Record<string, unknown>;
      return typeof row.name === 'string' && typeof row.adapter === 'string'
        && row.name !== 'offline' && row.is_fallback !== true && !/stub|unavailable/i.test(row.adapter);
    });
    items.push({ label: 'model adapters attached', value: String(attached.length) });
  }
  const enabled = pulse.switchboard?.enabled;
  const total = pulse.switchboard?.total;
  if (typeof enabled === 'number' && typeof total === 'number' && Number.isInteger(enabled)
    && Number.isInteger(total) && enabled >= 0 && total >= enabled) {
    items.push({ label: 'switchboard flags', value: `${enabled}/${total}` });
  }
  const coverage = pulse.organism?.connectome?.coverage_pct;
  if (runtimeSourceFresh(pulse.organism?.connectome, nowMs)
    && typeof coverage === 'number' && Number.isFinite(coverage) && coverage >= 0 && coverage <= 100) {
    items.push({ label: 'connectome coverage', value: `${coverage.toFixed(1)}%` });
  }
  return items;
}
