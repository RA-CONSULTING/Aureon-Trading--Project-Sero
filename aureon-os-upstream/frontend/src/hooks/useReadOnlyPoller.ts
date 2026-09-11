import { useCallback, useSyncExternalStore } from 'react';
import type { ReadOnlyPoller } from '../services/readOnlyPoller';

/** Pass a module-scoped store so all mounted readers share one request owner. */
export function useReadOnlyPoller<T>(store: ReadOnlyPoller<T>, intervalMs = 15_000, timeoutMs = 20_000) {
  const subscribe = useCallback((listener: () => void) => store.subscribe(listener, intervalMs, timeoutMs),
    [store, intervalMs, timeoutMs]);
  return { ...useSyncExternalStore(subscribe, store.getSnapshot, store.getSnapshot),
    refresh: store.refresh, invalidate: store.invalidate };
}
