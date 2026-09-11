import assert from 'node:assert/strict';
import test from 'node:test';
import { readCompanyRoster } from './companyRosterEvidence';

function roster() {
  return {
    departments: [{ id: 'engineering', title: 'Engineering', mission: 'Build and verify.' }],
    roles: [{ role_id: 'test_pilot', title: 'Test Pilot', department: 'engineering', seniority: 'specialist',
      mission: 'Run bounded checks.', authority_level: 'local_tests_only', tools_allowed: ['execute_shell'] }],
    summary: { role_count: 1, department_count: 1, roles_by_department: { engineering: 1 } },
    note: 'Configured workforce catalogue.',
    provenance: { policy: 'no fabricated values', simulation_fallback_allowed: false, source_registry_count: 1,
      truth_statuses: ['real_derived'] },
    truth_status: 'real_derived',
  };
}

test('accepts a count-consistent configured roster without inferring liveness', () => {
  const parsed = readCompanyRoster(roster());
  assert.equal(parsed?.roles[0].role_id, 'test_pilot');
  assert.equal(parsed?.truth_status, 'real_derived');
  assert.equal('running' in (parsed?.roles[0] ?? {}), false);
});

test('rejects duplicate department or role identities', () => {
  const duplicateDepartment = roster();
  duplicateDepartment.departments.push({ ...duplicateDepartment.departments[0] });
  duplicateDepartment.summary.department_count = 2;
  assert.equal(readCompanyRoster(duplicateDepartment), null);

  const duplicateRole = roster();
  duplicateRole.roles.push({ ...duplicateRole.roles[0] });
  duplicateRole.summary.role_count = 2;
  duplicateRole.summary.roles_by_department.engineering = 2;
  assert.equal(readCompanyRoster(duplicateRole), null);
});

test('rejects roles assigned to unknown departments', () => {
  const value = roster();
  value.roles[0].department = 'missing';
  assert.equal(readCompanyRoster(value), null);
});

test('rejects malformed role tools and simulated provenance', () => {
  const value = roster();
  const badTools = { ...value, roles: [{ ...value.roles[0], tools_allowed: 'execute_shell' }] };
  assert.equal(readCompanyRoster(badTools), null);

  const simulated = { ...value, provenance: { ...value.provenance, simulation_fallback_allowed: true } };
  assert.equal(readCompanyRoster(simulated), null);
});

test('rejects summary totals and per-department counts that contradict rows', () => {
  const total = roster();
  total.summary.role_count = 2;
  assert.equal(readCompanyRoster(total), null);

  const distribution = roster();
  distribution.summary.roles_by_department.engineering = 0;
  assert.equal(readCompanyRoster(distribution), null);
});

test('distinguishes an explicit empty catalogue from missing arrays', () => {
  const value = roster();
  const empty = { ...value, departments: [], roles: [],
    summary: { role_count: 0, department_count: 0, roles_by_department: {} } };
  assert.ok(readCompanyRoster(empty));

  const missing = value;
  Reflect.deleteProperty(missing, 'roles');
  assert.equal(readCompanyRoster(missing), null);
});

test('accepts a declared zero-role department when the backend omits its zero count', () => {
  const value = roster();
  const emptyDepartment = { id: 'research', title: 'Research', mission: 'Observe sources.' };
  const response = { ...value, departments: [...value.departments, emptyDepartment],
    summary: { ...value.summary, department_count: 2 } };
  assert.ok(readCompanyRoster(response));
});

test('accepts separate passive runtime verification without converting roles into live processes', () => {
  const value = { ...roster(), runtime_verification: {
    available: true, fresh: true, read_state: 'observed', truth_status: 'real_observed', generated_values: false,
    source: 'registered_pid_os_probe', source_path: 'state/organ_registry.json', source_timestamp: 1_788_884_400,
    receipt_timestamp: 1_788_884_401, age_seconds: 0, max_age_seconds: 15, source_clock_kind: 'os_process_measurement',
    identity_receipt_read_state: 'observed', configured_role_count: 1, verified_running_role_count: 0,
    runtime_role_binding_available: false, role_binding_state: 'unavailable',
    matching_rule: 'exact_role_id_equals_verified_runtime_organ_name', running_role_matches: [],
    organ_counts: { registered: 2, measured: 2, running_verified: 1, running_unverified: 1, running_total: 2, absent: 0, unknown: 0 },
    sample_running_organs: [{ name: 'operator_gateway', pid: 123, pid_running: true, identity_verified: true,
      launch_time_consistent: true, functional_health: 'unknown', read_state: 'observed', reason: null }],
    sample_stopped_organs: [], blockers: ['agent_role_to_runtime_organ_binding_manifest_unavailable'],
    scope_note: 'Registered PID liveness and launch identity only.',
  } };
  const parsed = readCompanyRoster(value);
  assert.equal(parsed?.runtime_verification?.organ_counts.running_total, 2);
  assert.equal(parsed?.runtime_verification?.role_binding_state, 'unavailable');
  assert.equal('running' in (parsed?.roles[0] ?? {}), false);
});

test('rejects runtime verification that fabricates values or contradicts roster counts', () => {
  const value = roster();
  const runtime = {
    available: true, fresh: true, read_state: 'observed', truth_status: 'real_observed', generated_values: false,
    source: 'registered_pid_os_probe', configured_role_count: 1, verified_running_role_count: 0,
    runtime_role_binding_available: false, role_binding_state: 'unavailable',
    matching_rule: 'exact_role_id_equals_verified_runtime_organ_name',
    organ_counts: { registered: 0, measured: 0, running_verified: 0, running_unverified: 0, running_total: 0, absent: 0, unknown: 0 },
    sample_running_organs: [], sample_stopped_organs: [], blockers: ['agent_role_to_runtime_organ_binding_manifest_unavailable'],
    scope_note: 'Registered PID liveness and launch identity only.',
  };
  assert.equal(readCompanyRoster({ ...value, runtime_verification: { ...runtime, generated_values: true } }), null);
  assert.equal(readCompanyRoster({ ...value, runtime_verification: { ...runtime, configured_role_count: 2 } }), null);
  assert.equal(readCompanyRoster({ ...value, runtime_verification: { ...runtime, truth_status: 'no_data' } }), null);
});

