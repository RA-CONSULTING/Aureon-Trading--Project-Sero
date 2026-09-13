import type { Identity } from './accountConfigurationEvidence';

export type PlaneRouteDecision = 'allow' | 'pending' | 'redirect';

/** Frontend routing mirrors the backend's owner boundary; backend authorization remains authoritative. */
export function planeRouteDecision(operatorOnly: boolean | undefined, identity: Identity, known: boolean): PlaneRouteDecision {
  if (!operatorOnly) return 'allow';
  if (!known) return 'pending';
  const verifiedSupabaseOwner = identity.kind === 'owner'
    && identity.authSource === 'supabase_auth_server'
    && identity.ownerDesignationVerified === true
    && typeof identity.identityCommitmentSha256 === 'string'
    && /^[0-9a-f]{64}$/.test(identity.identityCommitmentSha256);
  return (identity.kind === 'admin' || verifiedSupabaseOwner || identity.kind === 'open') && identity.isAdmin && identity.plane === 'instance' ? 'allow' : 'redirect';
}
