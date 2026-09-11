export type CodingDecision = 'approve' | 'request_revision' | 'reject';
export interface CodingArtifact {
  artifact_id: string; artifact_version: string; artifact_digest: string; report_sha256: string; title: string;
  source_report: string; files: Array<{ path: string; sha256: string; size_bytes: number }>;
  execution_authority: false; publication_authority: false;
}
export interface CodingDecisionRequest {
  artifact_id: string; artifact_version: string; artifact_digest: string; expected_decision_id: null;
  decision: CodingDecision; note: string; request_key: string;
}
export interface CodingDecisionReceipt {
  schema: 'aureon.coding-artifact-decision.v1'; receipt_id: string; receipt_digest: string; request_key: string;
  artifact: CodingArtifact; decision: CodingDecision; note: string; recorded_at: number;
  authenticated: true; actor: { actor_id: 'instance_operator'; identity_kind: 'admin'; authn_method: 'operator_bearer' };
  scope: 'artifact_review_only'; execution_authority: false; publication_authority: false;
}
export interface CodingReviewView {
  schema: 'aureon.coding-artifact-review.v1'; available: boolean; artifact: CodingArtifact | null;
  decision: CodingDecisionReceipt | null; can_decide?: boolean; expected_decision_id?: string | null;
  reason?: string; observed_at: number; execution_authority: false; publication_authority: false;
  decision_endpoint_available: boolean; decision_hold_reason?: string | null;
}
const object = (value: unknown): Record<string, unknown> | null => value !== null && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : null;
const hash = (value: unknown) => typeof value === 'string' && /^[0-9a-f]{64}$/.test(value);
const text = (value: unknown) => typeof value === 'string' && value.trim().length > 0;
const noAuthority = (value: Record<string, unknown>) => value.execution_authority === false && value.publication_authority === false;
function readArtifact(value: unknown): CodingArtifact {
  const data = object(value);
  if (!data || !noAuthority(data) || !text(data.artifact_id) || !text(data.artifact_version) || !hash(data.artifact_digest) || !hash(data.report_sha256)
    || !text(data.title) || !text(data.source_report) || !Array.isArray(data.files) || !data.files.length || data.files.length > 256
    || data.files.some(value => { const row = object(value); return !row || !text(row.path) || !hash(row.sha256) || typeof row.size_bytes !== 'number' || !Number.isSafeInteger(row.size_bytes) || row.size_bytes < 0; })) {
    throw new Error('Exact artifact review binding is unavailable.');
  }
  return data as unknown as CodingArtifact;
}
export function readCodingDecision(value: unknown): CodingDecisionReceipt {
  const data = object(value), actor = object(data?.actor);
  if (!data || data.schema !== 'aureon.coding-artifact-decision.v1' || !noAuthority(data) || data.authenticated !== true
    || data.scope !== 'artifact_review_only' || !text(data.receipt_id) || !hash(data.receipt_digest) || !text(data.request_key)
    || !['approve', 'request_revision', 'reject'].includes(String(data.decision)) || typeof data.note !== 'string'
    || typeof data.recorded_at !== 'number' || !Number.isFinite(data.recorded_at) || data.recorded_at <= 0
    || actor?.actor_id !== 'instance_operator' || actor.identity_kind !== 'admin' || actor.authn_method !== 'operator_bearer') {
    throw new Error('Authenticated decision receipt is unavailable.');
  }
  readArtifact(data.artifact);
  return data as unknown as CodingDecisionReceipt;
}
export function readCodingReview(value: unknown): CodingReviewView {
  const data = object(value);
  if (!data || data.schema !== 'aureon.coding-artifact-review.v1' || !noAuthority(data) || typeof data.available !== 'boolean'
    || typeof data.decision_endpoint_available !== 'boolean'
    || typeof data.observed_at !== 'number' || !Number.isFinite(data.observed_at) || data.observed_at <= 0) throw new Error('Artifact review service response is unavailable.');
  if (data.available) {
    const artifact = readArtifact(data.artifact);
    if (data.decision !== null) {
      const decision = readCodingDecision(data.decision);
      if (decision.artifact.artifact_digest !== artifact.artifact_digest || data.expected_decision_id !== decision.receipt_id || data.can_decide !== false) throw new Error('Decision belongs to a different artifact.');
    } else if (data.can_decide !== data.decision_endpoint_available || data.expected_decision_id !== null) throw new Error('Current decision state is unavailable.');
  } else if (data.artifact !== null || data.decision !== null) throw new Error('Unavailable artifact contains conflicting decision data.');
  return data as unknown as CodingReviewView;
}
export function readCodingDecisionAck(value: unknown, request: CodingDecisionRequest): CodingDecisionReceipt {
  const data = object(value);
  if (!data || data.ok !== true || data.persisted !== true || !noAuthority(data)) throw new Error('Durable decision acknowledgement is unavailable.');
  const receipt = readCodingDecision(data.receipt);
  if (receipt.request_key !== request.request_key || receipt.decision !== request.decision || receipt.note !== request.note.trim()
    || ['artifact_id', 'artifact_version', 'artifact_digest'].some(key => receipt.artifact[key as keyof CodingArtifact] !== request[key as keyof CodingDecisionRequest])) {
    throw new Error('Decision acknowledgement does not match this review request.');
  }
  return receipt;
}
