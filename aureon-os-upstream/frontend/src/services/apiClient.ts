/**
 * apiClient — the single typed entry point to the Aureon operator REST surface.
 *
 * Every dashboard reaches the backend over relative `/api/...` paths, which Vite
 * proxies to the operator server in dev (see vite.config.ts) and are same-origin
 * in production. This wrapper gives the whole UI ONE honest contract:
 *
 *   - a uniform result: it returns data on success and throws a typed `ApiError`
 *     on any non-2xx or transport failure, so callers can distinguish "backend
 *     offline" from "backend said no" and degrade honestly (never fabricate).
 *   - a short timeout so a dead gateway surfaces as "offline" instead of hanging.
 *   - no embedded credentials, but an optional injected auth token: when an
 *     end-user session exists, its bearer is attached to every `/api/*` call so
 *     the backend can identify the tenant. With no session, no header is sent —
 *     the single-operator/same-origin path is unchanged.
 *
 * Prefer this over bare `fetch("/api/...")` in new code.
 */

import {
  AUTH_RESOLUTION_FAILED,
  AUTH_RESOLUTION_HEADER,
} from './authResolution';

/**
 * An optional async provider of the current auth bearer token (e.g. the Supabase
 * session access token). Injected once at app bootstrap via `setAuthTokenProvider`
 * so this module stays decoupled from the auth library (and testable). When it
 * returns null/throws, no `Authorization` header is attached — backward compatible.
 */
let authTokenProvider: (() => Promise<string | null>) | null = null;

export function setAuthTokenProvider(fn: (() => Promise<string | null>) | null): void {
  authTokenProvider = fn;
}

/** Thrown for any failed backend call. `offline` marks transport failures
 *  (gateway down / timeout / network) as opposed to a real HTTP error status. */
export class ApiError extends Error {
  readonly status: number;
  readonly offline: boolean;
  readonly path: string;
  constructor(message: string, opts: { status?: number; offline?: boolean; path: string }) {
    super(message);
    this.name = "ApiError";
    this.status = opts.status ?? 0;
    this.offline = opts.offline ?? false;
    this.path = opts.path;
  }
}

const DEFAULT_TIMEOUT_MS = 8000;

export interface RequestOptions {
  /** Abort the request after this many ms (default 8000). */
  timeoutMs?: number;
  /** Extra headers merged over the defaults. */
  headers?: Record<string, string>;
  signal?: AbortSignal;
}

async function request<T>(
  method: "GET" | "POST" | "DELETE",
  path: string,
  body?: unknown,
  opts: RequestOptions = {},
): Promise<T> {
  const controller = new AbortController();
  let timedOut = false;
  const timeout = setTimeout(() => { timedOut = true; controller.abort(); }, opts.timeoutMs ?? DEFAULT_TIMEOUT_MS);
  const callerAbort = () => controller.abort();
  opts.signal?.addEventListener("abort", callerAbort, { once: true });
  if (opts.signal?.aborted) controller.abort();
  const abortError = () => new ApiError(`Request to ${path} ${timedOut ? "timed out" : "was cancelled"}`, { offline: true, path });
  let rejectOnAbort: () => void;
  const aborted = new Promise<never>((_, reject) => {
    rejectOnAbort = () => reject(abortError());
    if (controller.signal.aborted) rejectOnAbort();
    else controller.signal.addEventListener("abort", rejectOnAbort, { once: true });
  });
  let responseStatus = 0;
  const execute = async (): Promise<T> => {
    if (controller.signal.aborted) throw abortError();
    // Preserve optional bearer semantics. A rejected provider emits only the
    // fallback-denial sentinel; a deadline/cancellation ends before fetch starts.
    let authHeader: Record<string, string> = {};
    let authResolutionHeader: Record<string, string> = {};
    try {
      const token = authTokenProvider ? await authTokenProvider() : null;
      if (token) authHeader = { Authorization: `Bearer ${token}` };
    } catch {
      // Distinguish a verified no-session result from a failed lookup. A local
      // operator proxy must never turn the latter into its administrator bearer.
      authResolutionHeader = { [AUTH_RESOLUTION_HEADER]: AUTH_RESOLUTION_FAILED };
    }
    if (controller.signal.aborted) throw abortError();
    const res = await fetch(path, {
      method,
      cache: "no-store",
      signal: controller.signal,
      headers: {
        Accept: "application/json",
        ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
        ...authHeader,
        ...opts.headers,
        ...authResolutionHeader,
      },
      ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
    });
    responseStatus = res.status;
    if (!res.ok) {
      let detail = "";
      try {
        const j = await res.json();
        detail = typeof j?.error === "string" ? j.error
          : typeof j?.error?.message === "string" ? j.error.message : "";
        // The gateway's structured refusal is useful context. Never stringify
        // its remaining fields, which may contain internal commitments/details.
        if (typeof j?.error?.reason_code === "string" && /^[a-z0-9_]{1,120}$/.test(j.error.reason_code)) {
          detail += `${detail ? ": " : ""}${j.error.reason_code}`;
        }
        detail = detail.slice(0, 1_000);
      } catch {
        /* A malformed error body keeps the HTTP status. The outer deadline
           still bounds a stalled body, including this error-response path. */
      }
      throw new ApiError(detail || `${method} ${path} -> ${res.status}`, { status: res.status, path });
    }
    if (res.status === 204) return undefined as T;
    return (await res.json()) as T;
  };
  try {
    // One deadline covers session resolution, headers AND body consumption.
    // Racing also bounds token providers/custom fetches that ignore abort.
    return await Promise.race([execute(), aborted]);
  } catch (err) {
    if (controller.signal.aborted) throw abortError();
    if (err instanceof ApiError) throw err;
    throw new ApiError(responseStatus ? `Invalid JSON response from ${path}` : `Cannot reach ${path}`, {
      status: responseStatus, offline: responseStatus === 0, path,
    });
  } finally {
    clearTimeout(timeout);
    opts.signal?.removeEventListener("abort", callerAbort);
    controller.signal.removeEventListener("abort", rejectOnAbort!);
  }
}

export const api = {
  get: <T>(path: string, opts?: RequestOptions) => request<T>("GET", path, undefined, opts),
  post: <T>(path: string, body?: unknown, opts?: RequestOptions) =>
    request<T>("POST", path, body, opts),
  del: <T>(path: string, opts?: RequestOptions) => request<T>("DELETE", path, undefined, opts),
};

/**
 * `/api/pulse` — the operator's one-call vitals (providers + platform status +
 * organism + switchboard). The richest single read for a top-of-app health band.
 * Shape is intentionally permissive: fields the backend omits stay optional.
 */
export interface OperatorPulse {
  ok?: boolean;
  status?: "healthy" | "degraded" | "critical" | string;
  /** Configured LLM providers — a list; its length is the provider count. */
  providers?: unknown[];
  switchboard?: { total?: number; enabled?: number; armed?: number } & Record<string, unknown>;
  organism?: {
    connectome?: import('../lib/runtimeSourceStatus').RuntimeSourceObservation & { coverage_pct?: number; nodes?: number; woven?: number } & Record<string, unknown>;
  } & Record<string, unknown>;
  service?: unknown;
  [key: string]: unknown;
}

/** Fetch the operator pulse. Throws `ApiError` (with `.offline`) when the
 *  backend is unreachable, so callers show an honest offline state. */
export function fetchPulse(opts?: RequestOptions): Promise<OperatorPulse> {
  return api.get<OperatorPulse>("/api/pulse", opts);
}
