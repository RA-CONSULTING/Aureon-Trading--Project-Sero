import type { ReadOnlySnapshot } from '../services/readOnlyPoller';

export type ConfigurationStatus = 'loading' | 'observed' | 'unauthorized' | 'forbidden' | 'offline' | 'error' | 'stale' | 'unknown';
export const CONFIGURATION_RECEIPT_MAX_AGE_MS = 45_000;
export function configurationStatus<T>(receipt: ReadOnlySnapshot<T>): ConfigurationStatus {
  if (receipt.loading) return 'loading';
  if (receipt.httpStatus === 401) return 'unauthorized';
  if (receipt.httpStatus === 403) return 'forbidden';
  if (receipt.offline) return 'offline';
  if (receipt.lastReceivedAt !== null && !receipt.isReceiptCurrent && receipt.error === 'HTTP receipt expired; current data unavailable') return 'stale';
  if (receipt.error) return 'error';
  return receipt.data !== null && receipt.isReceiptCurrent ? 'observed' : 'unknown';
}
export function configurationMessage(status: ConfigurationStatus, error?: string | null): string {
  if (status === 'unauthorized') return 'Sign in to read this account configuration.';
  if (status === 'forbidden') return 'This session is not authorized to read this configuration.';
  if (status === 'offline') return 'The configuration service is unreachable.';
  if (status === 'stale') return 'The configuration receipt expired. Waiting for a current read.';
  if (status === 'loading') return 'Reading current account configuration…';
  return error || 'Current configuration is unavailable; key presence is unknown.';
}
export interface ProviderView {
  id: string;
  has_key: boolean;
  live?: boolean;
  last_test_at?: string | null;
  last_test_ok?: boolean | null;
  last_test_latency_ms?: number | null;
  last_test_error?: string | null;
  [key: string]: unknown;
}
export interface ProviderList { providers: ProviderView[] }
const record = (value: unknown): Record<string, unknown> | null =>
  value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : null;

function isOptionalBoolean(value: unknown): boolean {
  return value === undefined || value === null || typeof value === 'boolean';
}

function isOptionalString(value: unknown): boolean {
  return value === undefined || value === null || typeof value === 'string';
}

function isOptionalNumber(value: unknown): boolean {
  return value === undefined || value === null || (typeof value === 'number' && Number.isFinite(value));
}

export function readProviderList(value: unknown): ProviderList | null {
  const rows = record(value)?.providers;
  if (!Array.isArray(rows) || rows.some(row => !record(row) || typeof row.id !== 'string' || !row.id
    || typeof row.has_key !== 'boolean' || (row.live !== undefined && typeof row.live !== 'boolean')
    || !isOptionalString(row.last_test_at) || !isOptionalBoolean(row.last_test_ok)
    || !isOptionalNumber(row.last_test_latency_ms) || !isOptionalString(row.last_test_error))) return null;
  return { providers: rows as ProviderView[] };
}
export function setupFromReceipt(receipt: ReadOnlySnapshot<ProviderList>) {
  const status = configurationStatus(receipt);
  const known = status === 'observed';
  const rows = known ? receipt.data!.providers : null;
  const providerCount = rows === null ? null : rows.filter(row => row.has_key === true).length;
  const testedProvider = rows === null ? null : rows.some(row => row.last_test_ok === true);
  return { status, known, loading: receipt.loading, offline: receipt.offline, error: receipt.error,
    httpStatus: receipt.httpStatus, lastReceivedAt: receipt.lastReceivedAt,
    hasProvider: providerCount === null ? null : providerCount > 0, providerCount,
    // This flag describes adapter attachment; GET /providers does not run a test.
    liveProvider: rows === null || rows.some(row => typeof row.live !== 'boolean') ? null : rows.some(row => row.live === true),
    // Test history is now persisted on the provider record and exposed by
    // /api/providers, so onboarding can attest a completed successful test.
    testedProvider,
    testedProviderReason: testedProvider === false ? 'Run a provider test to record a successful connection.' : null,
  };
}

export type IdentityKind = 'open' | 'admin' | 'tenant' | 'unknown';
export interface Identity {
  kind: IdentityKind; isAdmin: boolean; tenantLabel: string | null;
  plane: 'instance' | 'account' | 'unknown'; tenancyEnabled: boolean | null;
  authRequired: boolean | null; allowedRoutes: string[] | null;
}
export const UNKNOWN_IDENTITY: Identity = { kind: 'unknown', isAdmin: false, tenantLabel: null,
  plane: 'unknown', tenancyEnabled: null, authRequired: null, allowedRoutes: null };
export function readIdentity(value: unknown): Identity | null {
  const data = record(value);
  if (!data || !['open', 'admin', 'tenant'].includes(String(data.kind)) || typeof data.is_admin !== 'boolean'
    || typeof data.tenancy_enabled !== 'boolean' || typeof data.auth_required !== 'boolean'
    || !['instance', 'account'].includes(String(data.plane))) return null;
  if ((data.is_admin && (data.kind === 'tenant' || data.plane !== 'instance'))
    || (!data.is_admin && (data.kind !== 'tenant' || data.plane !== 'account'))
    || (data.allowed_routes !== null && (!Array.isArray(data.allowed_routes) || data.allowed_routes.some(item => typeof item !== 'string')))
    || (!data.is_admin && !Array.isArray(data.allowed_routes))) return null;
  return { kind: data.kind as IdentityKind, isAdmin: data.is_admin, tenantLabel: typeof data.tenant_label === 'string' ? data.tenant_label : null,
    plane: data.plane as Identity['plane'], tenancyEnabled: data.tenancy_enabled, authRequired: data.auth_required,
    allowedRoutes: data.allowed_routes as string[] | null };
}

/** A completed user-requested test, dated by its actual HTTP response receipt. */
export interface DatedTestReceipt { ok: boolean | null; receivedAt: number; latencyMs: number | null; error: string | null }
export function captureTestReceipt(value: unknown, receivedAt: number): DatedTestReceipt {
  const data = record(value);
  return { ok: typeof data?.ok === 'boolean' ? data.ok : null, receivedAt,
    latencyMs: typeof data?.latency_ms === 'number' && Number.isFinite(data.latency_ms) && data.latency_ms >= 0 ? data.latency_ms : null,
    error: typeof data?.error === 'string' ? data.error : null };
}
export function datedTestEvidence(receipt: DatedTestReceipt | null | undefined, now = Date.now()) {
  const stamp = receipt?.receivedAt;
  const valid = typeof stamp === 'number' && Number.isFinite(stamp) && stamp > 0 && stamp <= 8_640_000_000_000_000;
  // A point-in-time test is shown for five minutes; it never proves continuous availability.
  const current = valid && now >= stamp && now - stamp <= 300_000 && typeof receipt?.ok === 'boolean';
  return { current, ok: current ? receipt!.ok : null, latencyMs: current ? receipt!.latencyMs : null,
    timestamp: valid ? new Date(stamp).toISOString() : null,
    clockKind: 'local_http_receipt' as const };
}

export function validKeyCoverage(value: unknown): boolean {
  const data = record(value), summary = record(data?.summary);
  if (!summary || !Array.isArray(data?.missing)) return false;
  if (data.missing.some(item => !record(item) || typeof item.id !== 'string')) return false;
  const fields = ['keyed_present', 'keyed_total', 'keyless', 'missing_count'];
  if (fields.some(key => typeof summary[key] !== 'number' || !Number.isInteger(summary[key]) || (summary[key] as number) < 0)) return false;
  const present = summary.keyed_present as number, total = summary.keyed_total as number;
  return present <= total && summary.missing_count === total - present
    && data.missing.length === summary.missing_count
    && summary.capacity_pct === (total ? Math.round(100 * present / total) : 100);
}
