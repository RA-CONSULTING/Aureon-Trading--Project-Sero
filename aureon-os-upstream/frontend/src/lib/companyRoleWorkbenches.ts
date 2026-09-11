export const COMPANY_CAPABILITY_SURFACES = {
  operator_status: {
    label: 'Operator platform status',
    apiRoute: '/api/status',
    uiPath: '/ops/operational',
  },
  company_workforce: {
    label: 'Agent company workforce',
    apiRoute: '/api/company',
    uiPath: '/cognition/agents',
  },
  coverage_map: {
    label: 'Whole-system coverage map',
    apiRoute: '/api/coverage',
    uiPath: '/platform/coverage',
  },
  feature_switchboard: {
    label: 'Feature switchboard',
    apiRoute: '/api/switchboard',
    uiPath: '/platform/switchboard',
  },
  terminal_state: {
    label: 'Terminal runtime state',
    apiRoute: '/api/terminal-state',
    uiPath: '/trading/hft',
  },
  terminal_receipt: {
    label: 'Terminal receipt service',
    apiRoute: '/api/operator/terminal-receipt',
    uiPath: '/ops/operational',
  },
  release_readiness: {
    label: 'Production release readiness',
    apiRoute: '/api/operator/release-readiness',
    uiPath: '/ops/approvals',
  },
  ingress_custody: {
    label: 'Operator ingress custody',
    apiRoute: '/api/operator/ingress-custody',
    uiPath: '/ops/connections',
  },
  executor_isolation: {
    label: 'Executor isolation',
    apiRoute: '/api/operator/executor-isolation',
    uiPath: '/trading/hft',
  },
  authority_map: {
    label: 'Independent authority map',
    apiRoute: '/api/operator/authority-map',
    uiPath: '/cognition/agents',
  },
  result_binding: {
    label: 'Protected result binding',
    apiRoute: '/api/operator/result-binding',
    uiPath: '/defense',
  },
  release_ledger: {
    label: 'Durable release ledger',
    apiRoute: '/api/operator/release-ledger',
    uiPath: '/ops/approvals',
  },
} as const;

export type CompanyCapabilitySurfaceId = keyof typeof COMPANY_CAPABILITY_SURFACES;

export const COMPANY_DEPARTMENT_WORKBENCHES = {
  executive: ['operator_status', 'company_workforce', 'coverage_map', 'release_readiness'],
  agency_workforce: ['company_workforce', 'release_readiness', 'result_binding'],
  product_ui: ['company_workforce', 'coverage_map', 'terminal_state'],
  public_design: ['company_workforce', 'coverage_map', 'release_readiness'],
  engineering: ['operator_status', 'coverage_map', 'feature_switchboard', 'release_readiness', 'release_ledger'],
  trading_data: ['terminal_state', 'terminal_receipt', 'executor_isolation', 'result_binding'],
  intelligence: ['operator_status', 'coverage_map', 'terminal_state'],
  accounting_admin: ['release_ledger', 'authority_map', 'result_binding'],
  security_ops: ['ingress_custody', 'authority_map', 'executor_isolation', 'result_binding', 'release_ledger'],
} as const satisfies Record<string, readonly CompanyCapabilitySurfaceId[]>;

export type CompanyWorkbenchDepartment = keyof typeof COMPANY_DEPARTMENT_WORKBENCHES;

export interface CompanyCapabilitySurfaceReceipt {
  id: CompanyCapabilitySurfaceId;
  label: string;
  route: string;
  method: 'GET';
  source: string;
  mode: 'read_only';
  mutation_authority: false;
  read_state: string;
  truth_status: string;
  current: boolean;
  evidence: string[];
  evidence_digest_sha256: string | null;
  summary: Record<string, unknown>;
}

export interface CompanyCapabilityRuntimeAttestation {
  schema: 'aureon.operator.capability-runtime-attestation.v1';
  generated_values: false;
  observed_at: number;
  observed_at_iso: string;
  surface_count: number;
  observed_surface_count: number;
  unavailable_surface_count: number;
  all_surfaces_observed: boolean;
  production_ready: boolean;
  release_authority: boolean;
  mutation_authority: boolean;
  routes: CompanyCapabilitySurfaceReceipt[];
  digest_sha256: string;
  digest_scope: string;
}

export interface CompanyWorkbenchRole {
  role_id: string;
  title: string;
  department: string;
}

export interface CompanyRoleWorkbenchBinding {
  id: CompanyCapabilitySurfaceId;
  label: string;
  apiRoute: string;
  uiPath: string;
  observation: CompanyCapabilitySurfaceReceipt | null;
}

export interface CompanyRoleWorkbench {
  roleId: string;
  roleTitle: string;
  department: CompanyWorkbenchDepartment;
  mode: 'read_only_observation';
  commandControls: false;
  mutationControls: false;
  bindings: CompanyRoleWorkbenchBinding[];
  currentSurfaceCount: number;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function isNonEmptyString(value: unknown): value is string {
  return typeof value === 'string' && value.trim().length > 0;
}

function isCount(value: unknown): value is number {
  return typeof value === 'number' && Number.isInteger(value) && value >= 0;
}

function isSha256(value: unknown): value is string {
  return typeof value === 'string' && /^[0-9a-f]{64}$/.test(value);
}

function isSurfaceId(value: unknown): value is CompanyCapabilitySurfaceId {
  return typeof value === 'string'
    && Object.prototype.hasOwnProperty.call(COMPANY_CAPABILITY_SURFACES, value);
}

function readSurface(value: unknown): CompanyCapabilitySurfaceReceipt | null {
  if (!isRecord(value) || !isSurfaceId(value.id)) return null;
  const definition = COMPANY_CAPABILITY_SURFACES[value.id];
  if (!isNonEmptyString(value.label)
    || !isNonEmptyString(value.route)
    || value.route !== definition.apiRoute
    || value.method !== 'GET'
    || !isNonEmptyString(value.source)
    || value.mode !== 'read_only'
    || value.mutation_authority !== false
    || !isNonEmptyString(value.read_state)
    || !isNonEmptyString(value.truth_status)
    || typeof value.current !== 'boolean'
    || !Array.isArray(value.evidence)
    || value.evidence.some(item => !isNonEmptyString(item))
    || !isRecord(value.summary)) return null;
  const digest = value.evidence_digest_sha256;
  if (digest !== null && !isSha256(digest)) return null;
  const projectedDigest: string | null = isSha256(digest) ? digest : null;
  if (value.current && (value.read_state !== 'observed' || !isSha256(digest))) return null;
  if (!value.current && value.read_state === 'observed') return null;
  return {
    id: value.id,
    label: value.label.trim(),
    route: value.route,
    method: 'GET',
    source: value.source.trim(),
    mode: 'read_only',
    mutation_authority: false,
    read_state: value.read_state.trim(),
    truth_status: value.truth_status.trim(),
    current: value.current,
    evidence: value.evidence.map(item => item.trim()),
    evidence_digest_sha256: projectedDigest,
    summary: value.summary,
  };
}

/**
 * Accept the operator's capability receipt only when every exposed surface is a
 * known same-origin GET with surface mutation authority false. Receipt-level
 * production/release/mutation flags remain display metadata and never create a
 * role control or alter the workbench's fixed no-action authority.
 */
export function readCompanyCapabilityRuntimeAttestation(
  value: unknown,
): CompanyCapabilityRuntimeAttestation | null {
  if (!isRecord(value)
    || value.schema !== 'aureon.operator.capability-runtime-attestation.v1'
    || value.generated_values !== false
    || typeof value.observed_at !== 'number'
    || !Number.isFinite(value.observed_at)
    || value.observed_at < 0
    || !isNonEmptyString(value.observed_at_iso)
    || !isCount(value.surface_count)
    || !isCount(value.observed_surface_count)
    || !isCount(value.unavailable_surface_count)
    || typeof value.all_surfaces_observed !== 'boolean'
    || typeof value.production_ready !== 'boolean'
    || typeof value.release_authority !== 'boolean'
    || typeof value.mutation_authority !== 'boolean'
    || !Array.isArray(value.routes)
    || !isSha256(value.digest_sha256)
    || !isNonEmptyString(value.digest_scope)) return null;

  const routes = value.routes.map(readSurface);
  if (routes.some(route => route === null)) return null;
  const observedIsoMs = Date.parse(value.observed_at_iso);
  if (!Number.isFinite(observedIsoMs) || Math.abs(observedIsoMs - value.observed_at * 1_000) > 1_000) return null;
  const projected = routes as CompanyCapabilitySurfaceReceipt[];
  const ids = projected.map(route => route.id);
  if (new Set(ids).size !== ids.length) return null;
  const observed = projected.filter(route => route.current).length;
  if (value.surface_count !== projected.length
    || value.observed_surface_count !== observed
    || value.unavailable_surface_count !== projected.length - observed
    || value.all_surfaces_observed !== (observed === projected.length)) return null;

  return {
    schema: 'aureon.operator.capability-runtime-attestation.v1',
    generated_values: false,
    observed_at: value.observed_at,
    observed_at_iso: value.observed_at_iso.trim(),
    surface_count: value.surface_count,
    observed_surface_count: value.observed_surface_count,
    unavailable_surface_count: value.unavailable_surface_count,
    all_surfaces_observed: value.all_surfaces_observed,
    production_ready: value.production_ready,
    release_authority: value.release_authority,
    mutation_authority: value.mutation_authority,
    routes: projected,
    digest_sha256: value.digest_sha256,
    digest_scope: value.digest_scope.trim(),
  };
}

export function buildCompanyRoleWorkbench(
  role: CompanyWorkbenchRole,
  attestation: CompanyCapabilityRuntimeAttestation | null,
): CompanyRoleWorkbench | null {
  if (!Object.prototype.hasOwnProperty.call(COMPANY_DEPARTMENT_WORKBENCHES, role.department)) return null;
  const department = role.department as CompanyWorkbenchDepartment;
  const observations = new Map(
    attestation?.routes.filter(route => route.current).map(route => [route.id, route]) ?? [],
  );
  const bindings = COMPANY_DEPARTMENT_WORKBENCHES[department].map(id => ({
    id,
    ...COMPANY_CAPABILITY_SURFACES[id],
    observation: observations.get(id) ?? null,
  }));
  return {
    roleId: role.role_id,
    roleTitle: role.title,
    department,
    mode: 'read_only_observation',
    commandControls: false,
    mutationControls: false,
    bindings,
    currentSurfaceCount: bindings.filter(binding => binding.observation?.current === true).length,
  };
}
