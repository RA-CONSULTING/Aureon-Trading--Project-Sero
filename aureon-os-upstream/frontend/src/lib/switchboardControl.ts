import { api } from '../services/apiClient';
import { readSwitchboardConfiguration, SwitchboardWriteGuard, type SwitchboardConfiguration, type SwitchboardFlag } from './platformConfiguration';

type CurrentConfiguration = { data: SwitchboardConfiguration | null; isReceiptCurrent: boolean; resetVersion: number };
export interface SwitchboardSaveReceipt { stored: boolean; enabled: boolean; applied: string }

/** One explicit user gesture, a fresh matching read, then the existing guarded write. */
export async function submitSwitchboardChange(options: {
  guard: SwitchboardWriteGuard; flag: SwitchboardFlag; enabled: boolean; confirm?: string;
  current(): CurrentConfiguration; canManage(): boolean;
}): Promise<SwitchboardSaveReceipt> {
  const requireOperator = () => {
    if (!options.canManage()) throw new Error('A current operator session is required to change configuration');
  };
  requireOperator();
  return options.guard.run(options.flag, options.enabled, options.confirm, {
    current: options.current,
    read: async signal => readSwitchboardConfiguration(await api.get('/api/switchboard', { signal })),
    write: async signal => {
      requireOperator();
      const value = await api.post<{
        ok?: boolean; applied?: string; flag?: { id?: string; stored?: boolean; enabled?: boolean };
      }>(`/api/switchboard/${encodeURIComponent(options.flag.id)}`, {
        enabled: options.enabled, ...(options.confirm === undefined ? {} : { confirm: options.confirm }),
      }, { signal });
      requireOperator();
      if (value?.ok !== true || value.flag?.id !== options.flag.id
        || value.flag.stored !== options.enabled || typeof value.flag.enabled !== 'boolean'
        || typeof value.applied !== 'string') {
        throw new Error('Configuration save was not confirmed; refresh the registry before retrying');
      }
      // An environment hold can keep the effective value OFF after ON intent was
      // stored. Preserve both values instead of painting the requested value.
      return { stored: value.flag.stored, enabled: value.flag.enabled, applied: value.applied };
    },
  });
}
