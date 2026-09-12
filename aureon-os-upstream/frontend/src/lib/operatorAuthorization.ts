import { api } from '@/services/apiClient';

export const OPERATOR_AUTHORIZATION_CONFIRM = 'AUREON_72_HOUR_OPERATOR_AUTHORIZATION';
export const MAX_OPERATOR_AUTHORIZATION_SECONDS = 72 * 60 * 60;

export interface OperatorAuthorizationLease {
  schema: 'aureon.operator.authorization-lease.v1';
  state: 'active' | 'expired' | 'revoked' | 'unavailable';
  active: boolean;
  scope: string[];
  account_scope: 'owner_cloud_account';
  authorized_at: number | null;
  authorized_at_iso: string | null;
  expires_at: number | null;
  expires_at_iso: string | null;
  remaining_seconds: number;
  ledger_sequence: number | null;
  ledger_event_sha256: string | null;
  reason_code: string;
  release_authority: false;
  mutation_authority: false;
}

const record = (value: unknown): Record<string, unknown> | null => value !== null && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : null;

export function readOperatorAuthorizationLease(value: unknown): OperatorAuthorizationLease {
  const raw = record(value);
  const states = new Set(['active', 'expired', 'revoked', 'unavailable']);
  if (!raw || raw.schema !== 'aureon.operator.authorization-lease.v1'
    || typeof raw.state !== 'string' || !states.has(raw.state)
    || typeof raw.active !== 'boolean' || raw.active !== (raw.state === 'active')
    || raw.account_scope !== 'owner_cloud_account'
    || !Array.isArray(raw.scope) || raw.scope.length !== 6 || raw.scope.some(item => typeof item !== 'string' || !item.startsWith('AUREON_'))
    || typeof raw.remaining_seconds !== 'number' || !Number.isSafeInteger(raw.remaining_seconds) || raw.remaining_seconds < 0
    || typeof raw.reason_code !== 'string' || !raw.reason_code.startsWith('operator_authorization_')
    || raw.release_authority !== false || raw.mutation_authority !== false) {
    throw new Error('Operator authorization lease unavailable');
  }
  const optionalTime = (field: unknown) => field === null || (typeof field === 'number' && Number.isFinite(field) && field > 0);
  const optionalText = (field: unknown) => field === null || typeof field === 'string';
  const optionalSequence = (field: unknown) => field === null || (typeof field === 'number' && Number.isSafeInteger(field) && field > 0);
  if (!optionalTime(raw.authorized_at) || !optionalTime(raw.expires_at)
    || !optionalText(raw.authorized_at_iso) || !optionalText(raw.expires_at_iso)
    || !optionalSequence(raw.ledger_sequence)
    || !(raw.ledger_event_sha256 === null || (typeof raw.ledger_event_sha256 === 'string' && /^[a-f0-9]{64}$/.test(raw.ledger_event_sha256)))) {
    throw new Error('Operator authorization lease evidence unavailable');
  }
  return raw as unknown as OperatorAuthorizationLease;
}

export async function grantOperatorAuthorization(): Promise<OperatorAuthorizationLease> {
  const response = await api.post<{ ok?: boolean; lease?: unknown }>('/api/operator/authorization-lease', {
    action: 'grant',
    confirm: OPERATOR_AUTHORIZATION_CONFIRM,
    duration_seconds: MAX_OPERATOR_AUTHORIZATION_SECONDS,
  });
  if (response.ok !== true) throw new Error('Operator authorization was not recorded');
  return readOperatorAuthorizationLease(response.lease);
}

export async function revokeOperatorAuthorization(): Promise<OperatorAuthorizationLease> {
  const response = await api.post<{ ok?: boolean; lease?: unknown }>('/api/operator/authorization-lease', {
    action: 'revoke',
    confirm: 'REVOKE_AUREON_OPERATOR_AUTHORIZATION',
  });
  if (response.ok !== true) throw new Error('Operator authorization revocation was not recorded');
  return readOperatorAuthorizationLease(response.lease);
}
