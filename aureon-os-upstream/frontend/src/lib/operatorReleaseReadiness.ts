export const RELEASE_REQUIREMENTS = {
  production_ingress_custody: { label: 'Production ingress custody', state: 'not_integrated' },
  independent_authorities: { label: 'Independent review, dispatch, executor and receipt authorities', state: 'not_integrated' },
  isolated_executor: { label: 'Isolated executor', state: 'not_integrated' },
  durable_release_ledger: { label: 'Durable release ledger', state: 'integrated' },
  terminal_receipt_service: { label: 'Terminal receipt service', state: 'integrated' },
  capability_runtime_attestation: { label: 'Capability and runtime attestation', state: 'integrated' },
  verified_result_binding: { label: 'Verified result binding', state: 'not_integrated' },
} as const;
type RequirementId = keyof typeof RELEASE_REQUIREMENTS;
type RequirementState = 'not_integrated' | 'unverified' | 'integrated';
export interface ReleaseRequirement {
  id: RequirementId;
  state: RequirementState;
  label: string;
  owner_surface: string;
  verification_route: string;
  blocked_until: string;
  work_order: string;
  evidence_required: string[];
}
export interface ReleaseWorkOrder {
  id: `release:${RequirementId}`;
  title: string;
  status: RequirementState;
  owner_surface: string;
  verification_route: string;
  blocked_until: string;
  evidence_required: string[];
}
export interface OperatorReleaseHandoff {
  state: 'blocked';
  control_surface: string;
  release_status_route: string;
  protected_request_policy: string;
  operator_can_record_intent: true;
  operator_can_release_execution: false;
  blocked_requirement_ids: RequirementId[];
}
export interface OperatorReleaseReadiness {
  schema: 'aureon.operator.release-readiness.v1';
  scope: 'operator_protected_http_ingress';
  basis: 'serving_implementation_contract';
  state: 'held';
  reason_code: 'production_magic_star_release_unavailable';
  release_available: false;
  production_ready: false;
  source_attestation: null;
  configuration_attestation: null;
  requirements: ReleaseRequirement[];
  work_orders: ReleaseWorkOrder[];
  operator_handoff: OperatorReleaseHandoff;
}
const record = (value: unknown): Record<string, unknown> | null => value !== null && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : null;
const hasOwn = (value: object, key: string) => Object.prototype.hasOwnProperty.call(value, key);
const exactKeys = (value: Record<string, unknown>, keys: string[]) => Object.keys(value).length === keys.length && keys.every(key => hasOwn(value, key));
const nonEmptyText = (value: unknown): string | null => typeof value === 'string' && value.trim() ? value.trim().slice(0, 240) : null;
function stringList(value: unknown): string[] | null {
  if (!Array.isArray(value) || value.length === 0 || value.length > 8) return null;
  const rows = value.map(nonEmptyText);
  return rows.every(Boolean) ? rows as string[] : null;
}
function parseRequirement(value: unknown, seen: Set<string>): ReleaseRequirement {
  const row = record(value);
  if (!row || !exactKeys(row, ['id', 'state', 'label', 'owner_surface', 'verification_route', 'blocked_until', 'work_order', 'evidence_required'])
    || typeof row.id !== 'string' || !hasOwn(RELEASE_REQUIREMENTS, row.id) || seen.has(row.id)
    || row.state !== RELEASE_REQUIREMENTS[row.id as RequirementId].state) throw new Error('Release requirement contract unavailable');
  const label = nonEmptyText(row.label), owner_surface = nonEmptyText(row.owner_surface), verification_route = nonEmptyText(row.verification_route);
  const blocked_until = nonEmptyText(row.blocked_until), work_order = nonEmptyText(row.work_order), evidence_required = stringList(row.evidence_required);
  if (!label || !owner_surface || !verification_route || !blocked_until || !work_order || !evidence_required
    || !owner_surface.startsWith('/') || !verification_route.startsWith('/')) throw new Error('Release requirement evidence unavailable');
  seen.add(row.id);
  return { id: row.id as RequirementId, state: row.state as RequirementState, label, owner_surface, verification_route, blocked_until, work_order, evidence_required };
}
function parseWorkOrder(value: unknown, requirements: Map<RequirementId, ReleaseRequirement>): ReleaseWorkOrder {
  const row = record(value);
  if (!row || !exactKeys(row, ['id', 'title', 'status', 'owner_surface', 'verification_route', 'blocked_until', 'evidence_required'])
    || typeof row.id !== 'string' || !row.id.startsWith('release:')) throw new Error('Release work order contract unavailable');
  const id = row.id.slice('release:'.length) as RequirementId;
  const requirement = requirements.get(id);
  const title = nonEmptyText(row.title), owner_surface = nonEmptyText(row.owner_surface), verification_route = nonEmptyText(row.verification_route);
  const blocked_until = nonEmptyText(row.blocked_until), evidence_required = stringList(row.evidence_required);
  if (!requirement || row.status !== requirement.state || !title || title !== requirement.label
    || owner_surface !== requirement.owner_surface || verification_route !== requirement.verification_route
    || blocked_until !== requirement.blocked_until || !evidence_required
    || evidence_required.join('\\n') !== requirement.evidence_required.join('\\n')) throw new Error('Release work order evidence unavailable');
  return { id: row.id as `release:${RequirementId}`, title, status: row.status as RequirementState, owner_surface, verification_route, blocked_until, evidence_required };
}
function parseOperatorHandoff(value: unknown, requirements: ReleaseRequirement[]): OperatorReleaseHandoff {
  const row = record(value);
  if (!row || !exactKeys(row, ['state', 'control_surface', 'release_status_route', 'protected_request_policy', 'operator_can_record_intent', 'operator_can_release_execution', 'blocked_requirement_ids'])
    || row.state !== 'blocked' || row.operator_can_record_intent !== true || row.operator_can_release_execution !== false) throw new Error('Release operator handoff contract unavailable');
  const control_surface = nonEmptyText(row.control_surface), release_status_route = nonEmptyText(row.release_status_route);
  const protected_request_policy = nonEmptyText(row.protected_request_policy);
  if (!control_surface?.startsWith('/') || !release_status_route?.startsWith('/') || !protected_request_policy) throw new Error('Release operator handoff routes unavailable');
  const expected = requirements.filter(item => item.state !== 'integrated').map(item => item.id);
  const blocked = Array.isArray(row.blocked_requirement_ids) ? row.blocked_requirement_ids : null;
  if (!blocked || blocked.length !== expected.length || blocked.some(item => typeof item !== 'string' || !hasOwn(RELEASE_REQUIREMENTS, item))
    || blocked.join('\n') !== expected.join('\n')) throw new Error('Release operator handoff blockers unavailable');
  return { state: 'blocked', control_surface, release_status_route, protected_request_policy,
    operator_can_record_intent: true, operator_can_release_execution: false, blocked_requirement_ids: blocked as RequirementId[] };
}

/** V1 only describes the held implementation. It cannot convey permission. */
export function readOperatorReleaseReadiness(value: unknown): OperatorReleaseReadiness {
  const raw = record(value);
  if (!raw || !exactKeys(raw, ['schema', 'scope', 'basis', 'state', 'reason_code', 'release_available', 'production_ready', 'source_attestation', 'configuration_attestation', 'requirements', 'work_orders', 'operator_handoff'])
    || raw.schema !== 'aureon.operator.release-readiness.v1' || raw.scope !== 'operator_protected_http_ingress'
    || raw.basis !== 'serving_implementation_contract' || raw.state !== 'held'
    || raw.reason_code !== 'production_magic_star_release_unavailable' || raw.release_available !== false || raw.production_ready !== false
    || raw.source_attestation !== null || raw.configuration_attestation !== null
    || !Array.isArray(raw.requirements) || raw.requirements.length !== Object.keys(RELEASE_REQUIREMENTS).length
    || !Array.isArray(raw.work_orders) || raw.work_orders.length !== Object.keys(RELEASE_REQUIREMENTS).length) throw new Error('Release readiness contract unavailable');
  const seen = new Set<string>();
  const requirements = raw.requirements.map(value => parseRequirement(value, seen));
  const requirementMap = new Map(requirements.map(row => [row.id, row]));
  const work_orders = raw.work_orders.map(value => parseWorkOrder(value, requirementMap));
  const operator_handoff = parseOperatorHandoff(raw.operator_handoff, requirements);
  if (new Set(work_orders.map(row => row.id)).size !== work_orders.length) throw new Error('Duplicate release work order contract');
  return { schema: raw.schema, scope: raw.scope, basis: raw.basis, state: raw.state,
    reason_code: raw.reason_code, release_available: false, production_ready: false,
    source_attestation: null, configuration_attestation: null, requirements, work_orders, operator_handoff };
}

export interface ReleaseReadinessReceipt {
  data: OperatorReleaseReadiness | null;
  loading: boolean;
  error: string | null;
  httpStatus: number | null;
  isReceiptCurrent: boolean;
  lastReceivedAt: number | null;
}
export function releaseReadinessView(receipt: ReleaseReadinessReceipt, now = Date.now()) {
  if (receipt.loading) return { state: 'loading' as const, message: 'Reading release status…', receivedAt: null };
  if (receipt.httpStatus === 401) return { state: 'unavailable' as const, message: 'Sign in to read release status.', receivedAt: null };
  if (receipt.httpStatus === 403) return { state: 'unavailable' as const, message: 'This session cannot read release status.', receivedAt: null };
  const stamp = receipt.lastReceivedAt;
  if (receipt.error || !receipt.data || !receipt.isReceiptCurrent || stamp === null || !Number.isFinite(stamp)
    || stamp <= 0 || stamp > 8_640_000_000_000_000 || !Number.isFinite(now) || now < stamp || now - stamp > 45_000) {
    return { state: 'unavailable' as const, message: 'Current release status is unavailable. No release authorization is established.', receivedAt: null };
  }
  const remaining = receipt.data.work_orders.filter(row => row.status !== 'integrated').length;
  const integrated = receipt.data.work_orders.length - remaining;
  return { state: 'held' as const, message: `${remaining} production release work orders still block production; ${integrated} integrated. Operator intent can be recorded, but execution release is still blocked.`, receivedAt: stamp,
    remaining, integrated };
}

/** Missing or unfamiliar verdicts must never acquire an approval badge. */
export function operatorConscienceVerdict(value: unknown): { label: string; approved: boolean } {
  if (typeof value !== 'string' || !value.trim()) return { label: 'Unavailable', approved: false };
  const label = value.trim();
  return { label: label.slice(0, 120), approved: label === 'APPROVED' };
}

