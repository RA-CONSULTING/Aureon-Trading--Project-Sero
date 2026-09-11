import { z } from 'zod';

const nonEmptyText = z.string().trim().min(1);
const nullableCount = z.number().int().nonnegative().nullable();
const nullableNumber = z.number().nullable();
const departmentSchema = z.object({
  id: nonEmptyText,
  title: nonEmptyText,
  mission: nonEmptyText,
}).passthrough();
const roleSchema = z.object({
  role_id: nonEmptyText,
  title: nonEmptyText,
  department: nonEmptyText,
  seniority: nonEmptyText,
  mission: nonEmptyText,
  authority_level: nonEmptyText,
  tools_allowed: z.array(nonEmptyText),
}).passthrough();

const runtimeOrganSchema = z.object({
  name: nonEmptyText,
  pid: nullableCount.optional(),
  pid_running: z.boolean().nullable().optional(),
  identity_verified: z.boolean(),
  launch_time_consistent: z.boolean().optional(),
  functional_health: nonEmptyText,
  read_state: nonEmptyText,
  reason: z.string().nullable().optional(),
}).passthrough();


const runtimeBindingManifestSchema = z.object({
  available: z.boolean(),
  read_state: nonEmptyText,
  truth_status: z.union([z.literal('real_derived'), z.literal('no_data')]),
  generated_values: z.literal(false),
  source_path: z.string().nullable().optional(),
  source_generated_at: z.string().nullable().optional(),
  binding_count: nullableCount.optional(),
  scope_note: z.string().nullable().optional(),
  reason: z.string().nullable().optional(),
}).passthrough();


const brainFabricVerificationSchema = z.object({
  available: z.boolean(),
  truth_status: z.union([z.literal('real_derived'), z.literal('no_data')]),
  generated_values: z.literal(false),
  read_state: nonEmptyText,
  source: nonEmptyText,
  source_path: z.string().nullable().optional(),
  source_generated_at: z.string().nullable().optional(),
  report_status: z.string().nullable().optional(),
  brain_fabric_status: z.string().nullable().optional(),
  routing_live: z.boolean(),
  execution_ready: z.boolean(),
  brain_fabric_ready: z.boolean().optional(),
  truth_gate_enforced: z.boolean(),
  provider_mode: z.string().nullable().optional(),
  hnc_routed_brain_count: nullableCount.optional(),
  brain_passport_count: nullableCount.optional(),
  canonical_role_count: nullableCount.optional(),
  agent_brain_count: nullableCount.optional(),
  process_brain_count: nullableCount.optional(),
  all_brains_hnc_routed: z.boolean().optional(),
  tools_enabled: z.boolean().optional(),
  action_eligible: z.boolean().optional(),
  economic_eligible: z.boolean().optional(),
  summary_routing_live: z.boolean().optional(),
  blockers: z.array(nonEmptyText),
}).passthrough();

const runtimeVerificationSchema = z.object({
  available: z.boolean(),
  fresh: z.boolean(),
  read_state: nonEmptyText,
  truth_status: z.union([z.literal('real_observed'), z.literal('no_data')]),
  generated_values: z.literal(false),
  source: nonEmptyText,
  source_path: z.string().nullable().optional(),
  source_timestamp: nullableNumber.optional(),
  receipt_timestamp: nullableNumber.optional(),
  age_seconds: nullableNumber.optional(),
  max_age_seconds: nullableNumber.optional(),
  source_clock_kind: nonEmptyText.optional(),
  identity_receipt_read_state: z.string().nullable().optional(),
  configured_role_count: z.number().int().nonnegative(),
  verified_running_role_count: z.number().int().nonnegative(),
  runtime_role_binding_available: z.boolean(),
  role_binding_state: nonEmptyText,
  live_company_operation_state: nonEmptyText.optional(),
  matching_rule: nonEmptyText,
  unbound_role_count: z.number().int().nonnegative().optional(),
  bound_roles_by_department: z.record(z.number().int().nonnegative()).optional(),
  unbound_roles_by_department: z.record(z.array(z.object({
    role_id: nonEmptyText,
    title: nonEmptyText,
    authority_level: nonEmptyText,
  }).passthrough())).optional(),
  service_surface_bindings_by_organ: z.record(z.number().int().nonnegative()).optional(),
  running_role_matches: z.array(z.object({
    role_id: nonEmptyText,
    organ_name: nonEmptyText,
    pid: nullableCount.optional(),
    binding_kind: nonEmptyText.optional(),
    claim: nonEmptyText.optional(),
    source: nonEmptyText.optional(),
    evidence: z.array(nonEmptyText).optional(),
  }).passthrough()).optional(),
  exact_running_role_match_count: z.number().int().nonnegative().optional(),
  manifest_running_role_match_count: z.number().int().nonnegative().optional(),
  runtime_binding_manifest: runtimeBindingManifestSchema.optional(),
  organ_counts: z.object({
    registered: nullableCount,
    measured: nullableCount,
    running_verified: nullableCount,
    running_unverified: nullableCount,
    running_total: nullableCount,
    absent: nullableCount,
    unknown: nullableCount,
  }).passthrough(),
  sample_running_organs: z.array(runtimeOrganSchema),
  sample_stopped_organs: z.array(runtimeOrganSchema),
  blockers: z.array(nonEmptyText),
  brain_fabric_verification: brainFabricVerificationSchema.optional(),
  scope_note: nonEmptyText,
}).passthrough();

const companyRosterSchema = z.object({
  departments: z.array(departmentSchema),
  roles: z.array(roleSchema),
  summary: z.object({
    role_count: z.number().int().nonnegative(),
    department_count: z.number().int().nonnegative(),
    roles_by_department: z.record(z.number().int().nonnegative()),
  }).passthrough(),
  runtime_verification: runtimeVerificationSchema.optional(),
  note: nonEmptyText,
  provenance: z.object({
    policy: nonEmptyText,
    simulation_fallback_allowed: z.literal(false),
    source_registry_count: z.number().int().nonnegative(),
    truth_statuses: z.array(nonEmptyText).optional(),
  }).passthrough(),
  truth_status: z.literal('real_derived'),
}).passthrough();

export type CompanyRoster = z.infer<typeof companyRosterSchema>;
export type CompanyRuntimeVerification = z.infer<typeof runtimeVerificationSchema>;

function allUnique(values: string[]): boolean {
  return new Set(values).size === values.length;
}

/**
 * Parses the gateway's configured workforce catalogue. Runtime verification, when
 * present, is a separate passive organ-registry observation and must not be used
 * to infer unbound role liveness.
 */
export function readCompanyRoster(value: unknown): CompanyRoster | null {
  const parsed = companyRosterSchema.safeParse(value);
  if (!parsed.success) return null;

  const roster = parsed.data;
  const departmentIds = roster.departments.map(department => department.id);
  const roleIds = roster.roles.map(role => role.role_id);
  if (!allUnique(departmentIds) || !allUnique(roleIds)) return null;
  if (roster.summary.department_count !== roster.departments.length
    || roster.summary.role_count !== roster.roles.length) return null;

  const knownDepartments = new Set(departmentIds);
  if (roster.roles.some(role => !knownDepartments.has(role.department))) return null;

  const reportedDepartments = Object.keys(roster.summary.roles_by_department);
  if (reportedDepartments.some(id => !knownDepartments.has(id))) return null;
  for (const departmentId of departmentIds) {
    const actual = roster.roles.filter(role => role.department === departmentId).length;
    const reported = roster.summary.roles_by_department[departmentId] ?? 0;
    if (reported !== actual) return null;
  }

  const runtime = roster.runtime_verification;
  if (runtime) {
    if (runtime.configured_role_count !== roster.roles.length) return null;
    if (runtime.verified_running_role_count > roster.roles.length) return null;
    if (runtime.available && runtime.truth_status !== 'real_observed') return null;
    if (!runtime.available && runtime.truth_status !== 'no_data') return null;
    if (runtime.runtime_role_binding_available && runtime.verified_running_role_count === 0) return null;
    if (runtime.unbound_role_count !== undefined
      && runtime.unbound_role_count !== roster.roles.length - runtime.verified_running_role_count) return null;
    if (runtime.bound_roles_by_department) {
      for (const departmentId of Object.keys(runtime.bound_roles_by_department)) {
        if (!knownDepartments.has(departmentId)) return null;
      }
    }
    if (runtime.unbound_roles_by_department) {
      for (const [departmentId, entries] of Object.entries(runtime.unbound_roles_by_department)) {
        if (!knownDepartments.has(departmentId)) return null;
        if (entries.some(entry => !roleIds.includes(entry.role_id))) return null;
      }
    }
    const brain = runtime.brain_fabric_verification;
    if (brain) {
      if (brain.available && brain.truth_status !== 'real_derived') return null;
      if (!brain.available && brain.truth_status !== 'no_data') return null;
      if (brain.routing_live && brain.hnc_routed_brain_count !== brain.brain_passport_count) return null;
      if (brain.execution_ready && !brain.truth_gate_enforced) return null;
      if ((brain.action_eligible || brain.economic_eligible || brain.tools_enabled) && !brain.execution_ready) return null;
    }
  }
  return roster;
}
