import type { Identity } from './accountConfigurationEvidence';

export type OperatingContextKind = 'owner' | 'tenant' | 'unknown';

export interface OperatingContextView {
  kind: OperatingContextKind;
  badge: string;
  eyebrow: string;
  title: string;
  description: string;
  boundary: string;
}

/**
 * Translate the current backend identity receipt into one explicit operating
 * context. Unknown or internally inconsistent identities stay fail-closed.
 */
export function operatingContextView(identity: Identity, known: boolean): OperatingContextView {
  const verifiedSupabaseOwner = identity.kind === 'owner'
    && identity.authSource === 'supabase_auth_server'
    && identity.ownerDesignationVerified === true
    && typeof identity.identityCommitmentSha256 === 'string'
    && /^[0-9a-f]{64}$/.test(identity.identityCommitmentSha256);
  if (known && (identity.kind === 'admin' || verifiedSupabaseOwner || identity.kind === 'open') && identity.isAdmin && identity.plane === 'instance') {
    const protectedOwner = identity.kind === 'admin';
    const signedInOwner = identity.kind === 'owner';
    return {
      kind: 'owner',
      badge: protectedOwner || signedInOwner ? 'OWNER INSTANCE' : 'LOCAL INSTANCE',
      eyebrow: signedInOwner ? 'Verified owner account' : protectedOwner ? 'Protected owner plane' : 'Single-operator plane',
      title: protectedOwner || signedInOwner ? 'Owner cloud runtime' : 'Local instance runtime',
      description: `${protectedOwner || signedInOwner ? 'This protected instance' : 'This local instance'} uses its server-side runtime configuration and preconfigured credentials. Tenant workspaces cannot replace, stop, or reconfigure it.`,
      boundary: `${protectedOwner || signedInOwner ? '' : 'Authentication is not configured; do not expose this instance publicly. '}Provider tests and signed receipts establish current availability. This context does not claim that an order was placed.`,
    };
  }

  if (known && identity.kind === 'tenant' && !identity.isAdmin && identity.plane === 'account') {
    const account = identity.tenantLabel ? `Account ${identity.tenantLabel}` : 'Signed-in account';
    return {
      kind: 'tenant',
      badge: 'PRIVATE WORKSPACE',
      eyebrow: 'Isolated tenant plane',
      title: `${account} workspace`,
      description: 'This workspace uses only this account\'s encrypted credentials and cannot change the protected owner cloud runtime.',
      boundary: 'Execution remains held until this account supplies and tests its own keys and completes the required human approvals. Signing out ends only this browser session.',
    };
  }

  return {
    kind: 'unknown',
    badge: 'VERIFYING CONTEXT',
    eyebrow: 'Access boundary',
    title: 'Operating context unconfirmed',
    description: 'Waiting for a current backend identity receipt before showing an owner or account context.',
    boundary: 'Privileged controls remain subject to server authorization while identity is unconfirmed.',
  };
}
