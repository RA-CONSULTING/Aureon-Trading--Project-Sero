import { ApiError } from './apiClient';

export interface SourceEvidence {
  status: 'fresh' | 'stale' | 'unavailable' | 'unattested';
  reason?: string;
  sourceTimestamp?: number | string | null;
}
export interface ReadOnlySnapshot<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  offline: boolean;
  httpStatus: number | null;
  /** Changes whenever account-bound data is discarded; also clears local drafts. */
  resetVersion: number;
  /** Browser HTTP completion time; never an observation/source clock. */
  lastReceivedAt: number | null;
  isReceiptCurrent: boolean;
  source: SourceEvidence;
}
export interface PollerClock {
  now(): number;
  setTimeout(callback: () => void, ms: number): ReturnType<typeof setTimeout>;
  clearTimeout(timer: ReturnType<typeof setTimeout>): void;
}
export interface ReadOnlyPollerOptions<T> {
  /** Caller must verify the GET handler is observational before registering it. */
  read(options: { signal: AbortSignal; timeoutMs: number }): Promise<T>;
  receiptMaxAgeMs: number;
  /** Endpoint-specific original source validation, not response assembly time. */
  validateSource?(data: T, nowMs: number): SourceEvidence;
  clock?: PollerClock;
}
export interface ReadOnlyPoller<T> {
  subscribe(listener: () => void, intervalMs?: number, timeoutMs?: number): () => void;
  getSnapshot(): ReadOnlySnapshot<T>;
  /** Coalesces concurrent refresh requests into one subsequent read. */
  refresh(): void;
  /** Discards data, cancels the old request, then rereads if subscribed. */
  invalidate(): void;
}
const activePollers = new Set<{ invalidate(): void }>();
/** Invoke at account/session changes to discard data even in a mounted shell. */
export function invalidateReadOnlyPollers(): void {
  [...activePollers].forEach(poller => poller.invalidate());
}

/** One module-scoped owner per safe GET; no reads or timers until subscribed. */
export function createReadOnlyPoller<T>(options: ReadOnlyPollerOptions<T>): ReadOnlyPoller<T> {
  if (!Number.isFinite(options.receiptMaxAgeMs) || options.receiptMaxAgeMs <= 0) {
    throw new Error('A positive receipt age limit is required');
  }
  const clock: PollerClock = options.clock ?? { now: () => Date.now(),
    setTimeout: (callback, ms) => setTimeout(callback, ms), clearTimeout: timer => clearTimeout(timer) };
  const listeners = new Map<() => void, { intervalMs: number; timeoutMs: number }>();
  let resetVersion = 0;
  const initial = (): ReadOnlySnapshot<T> => ({ data: null, loading: true, error: null, offline: false,
    httpStatus: null, resetVersion,
    lastReceivedAt: null, isReceiptCurrent: false, source: { status: 'unattested' } });
  let snapshot = initial();
  let data: T | null = null;
  let receivedAt: number | null = null;
  let requestError: string | null = null;
  let offline = false;
  let httpStatus: number | null = null;
  let loading = true;
  let request: AbortController | null = null;
  let nextRead: ReturnType<typeof setTimeout> | undefined;
  let ageTimer: ReturnType<typeof setTimeout> | undefined;
  let refreshQueued = false;

  function publish() {
    const now = clock.now();
    const isReceiptCurrent = !requestError && receivedAt !== null && Number.isFinite(now)
      && now >= receivedAt && now - receivedAt <= options.receiptMaxAgeMs;
    let source: SourceEvidence = { status: 'unattested' };
    if (data !== null && options.validateSource) {
      try { source = options.validateSource(data, now); }
      catch { source = { status: 'unavailable', reason: 'Source evidence could not be validated' }; }
    }
    const rejected = source.status === 'stale' || source.status === 'unavailable';
    const error = requestError ?? (receivedAt !== null && !isReceiptCurrent ? 'HTTP receipt expired; current data unavailable' : null)
      ?? (rejected ? source.reason ?? 'Current source evidence unavailable' : null);
    snapshot = { data: isReceiptCurrent && !rejected ? data : null, loading, error, offline, httpStatus, resetVersion,
      lastReceivedAt: receivedAt, isReceiptCurrent, source };
    listeners.forEach((_, listener) => listener());
  }
  function age() {
    publish();
    if (listeners.size) ageTimer = clock.setTimeout(age, 1_000);
  }
  async function read() {
    if (request || !listeners.size) return;
    const controller = new AbortController();
    request = controller;
    const timeoutMs = Math.min(...Array.from(listeners.values(), value => value.timeoutMs));
    try {
      const next = await options.read({ signal: controller.signal, timeoutMs });
      if (request !== controller) return;
      data = next;
      receivedAt = clock.now();
      requestError = null;
      offline = false;
      httpStatus = null;
    } catch (error) {
      if (request !== controller) return;
      data = null;
      requestError = error instanceof Error ? error.message : 'Read unavailable';
      offline = error instanceof ApiError ? error.offline : true;
      httpStatus = error instanceof ApiError && error.status > 0 ? error.status : null;
    } finally {
      if (request === controller) {
        request = null;
        loading = false;
        publish();
        if (listeners.size) {
          const delay = refreshQueued ? 0 : Math.min(...Array.from(listeners.values(), value => value.intervalMs));
          refreshQueued = false;
          nextRead = clock.setTimeout(() => { nextRead = undefined; void read(); }, delay);
        }
      }
    }
  }
  function clear() {
    resetVersion++;
    if (nextRead !== undefined) clock.clearTimeout(nextRead);
    nextRead = undefined;
    const old = request;
    request = null;
    old?.abort();
    refreshQueued = false;
    data = null;
    receivedAt = null;
    requestError = null;
    offline = false;
    httpStatus = null;
    loading = true;
    snapshot = initial();
  }
  const store: ReadOnlyPoller<T> = {
    subscribe(listener, intervalMs = 15_000, timeoutMs = 20_000) {
      listeners.set(listener, {
        intervalMs: Number.isFinite(intervalMs) ? Math.max(1_000, intervalMs) : 15_000,
        timeoutMs: Number.isFinite(timeoutMs) ? Math.max(1, timeoutMs) : 20_000,
      });
      if (listeners.size === 1) {
        activePollers.add(store);
        clear();
        age();
        void read();
      }
      return () => {
        listeners.delete(listener);
        if (!listeners.size) {
          activePollers.delete(store);
          if (ageTimer !== undefined) clock.clearTimeout(ageTimer);
          ageTimer = undefined;
          clear();
        }
      };
    },
    getSnapshot: () => snapshot,
    refresh() {
      if (!listeners.size) return;
      if (request) { refreshQueued = true; return; }
      if (nextRead !== undefined) clock.clearTimeout(nextRead);
      nextRead = undefined;
      void read();
    },
    invalidate() {
      clear();
      publish();
      if (listeners.size) void read();
    },
  };
  return store;
}
