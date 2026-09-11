import assert from 'node:assert/strict';
import test from 'node:test';

import {
  COMPANY_CAPABILITY_SURFACES,
  COMPANY_DEPARTMENT_WORKBENCHES,
  buildCompanyRoleWorkbench,
  readCompanyCapabilityRuntimeAttestation,
  type CompanyCapabilitySurfaceId,
} from './companyRoleWorkbenches';

const sha = 'a'.repeat(64);

function surface(id: CompanyCapabilitySurfaceId, current = true) {
  const definition = COMPANY_CAPABILITY_SURFACES[id];
  return {
    id,
    label: definition.label,
    route: definition.apiRoute,
    method: 'GET',
    source: `test.${id}`,
    mode: 'read_only',
    mutation_authority: false,
    read_state: current ? 'observed' : 'unavailable',
    truth_status: current ? 'real_derived' : 'unavailable',
    current,
    evidence: ['truth_status'],
    evidence_digest_sha256: current ? sha : null,
    summary: current ? { available: true } : { reason: 'source_unavailable' },
  };
}

function receipt(routes = [surface('operator_status'), surface('company_workforce')]) {
  const observed = routes.filter(route => route.current).length;
  return {
    schema: 'aureon.operator.capability-runtime-attestation.v1',
    generated_values: false,
    observed_at: 1_789_000_000,
    observed_at_iso: new Date(1_789_000_000_000).toISOString(),
    surface_count: routes.length,
    observed_surface_count: observed,
    unavailable_surface_count: routes.length - observed,
    all_surfaces_observed: observed === routes.length,
    production_ready: false,
    release_authority: false,
    mutation_authority: false,
    routes,
    digest_sha256: sha,
    digest_scope: 'capability_route_evidence_matrix',
  };
}

test('accepts a count-consistent, observation-only capability receipt', () => {
  const parsed = readCompanyCapabilityRuntimeAttestation(receipt());
  assert.ok(parsed);
  assert.equal(parsed.routes.length, 2);
  assert.equal(parsed.routes[0].method, 'GET');
  assert.equal(parsed.routes[0].mutation_authority, false);
});

test('rejects command, surface authority, route injection, duplicate, and receipt contradictions', () => {
  const command = structuredClone(receipt()) as unknown as { routes: Array<{ method: string }> };
  command.routes[0].method = 'POST';
  assert.equal(readCompanyCapabilityRuntimeAttestation(command), null);

  const surfaceAuthority = structuredClone(receipt()) as unknown as { routes: Array<{ mutation_authority: boolean }> };
  surfaceAuthority.routes[0].mutation_authority = true;
  assert.equal(readCompanyCapabilityRuntimeAttestation(surfaceAuthority), null);

  const injected = structuredClone(receipt()) as unknown as { routes: Array<{ route: string }> };
  injected.routes[0].route = 'https://example.invalid/collect';
  assert.equal(readCompanyCapabilityRuntimeAttestation(injected), null);

  const duplicate = receipt([surface('operator_status'), surface('operator_status')]);
  assert.equal(readCompanyCapabilityRuntimeAttestation(duplicate), null);

  const badCount = structuredClone(receipt()) as unknown as { observed_surface_count: number };
  badCount.observed_surface_count = 0;
  assert.equal(readCompanyCapabilityRuntimeAttestation(badCount), null);

  const badClock = structuredClone(receipt()) as unknown as { observed_at: number; observed_at_iso: string };
  badClock.observed_at_iso = new Date((badClock.observed_at + 30) * 1_000).toISOString();
  assert.equal(readCompanyCapabilityRuntimeAttestation(badClock), null);
});

test('production-state metadata stays viewable without creating role command authority', () => {
  const production = structuredClone(receipt()) as unknown as {
    production_ready: boolean; release_authority: boolean; mutation_authority: boolean;
  };
  production.production_ready = true;
  production.release_authority = true;
  production.mutation_authority = true;
  const parsed = readCompanyCapabilityRuntimeAttestation(production);
  assert.ok(parsed);
  assert.equal(parsed.production_ready, true);
  assert.equal(parsed.release_authority, true);
  assert.equal(parsed.mutation_authority, true);
  assert.ok(parsed.routes.every(route => route.method === 'GET' && route.mode === 'read_only'));
  assert.ok(parsed.routes.every(route => route.mutation_authority === false));

  const workbench = buildCompanyRoleWorkbench({
    role_id: 'ceo_goal_steward', title: 'CEO Goal Steward', department: 'executive',
  }, parsed);
  assert.ok(workbench);
  assert.equal(workbench.commandControls, false);
  assert.equal(workbench.mutationControls, false);
});

test('every configured department maps only to known same-origin read surfaces', () => {
  const departments = [
    'executive', 'agency_workforce', 'product_ui', 'public_design', 'engineering',
    'trading_data', 'intelligence', 'accounting_admin', 'security_ops',
  ];
  assert.deepEqual(Object.keys(COMPANY_DEPARTMENT_WORKBENCHES).sort(), departments.sort());
  for (const ids of Object.values(COMPANY_DEPARTMENT_WORKBENCHES)) {
    assert.ok(ids.length > 0);
    for (const id of ids) {
      const definition = COMPANY_CAPABILITY_SURFACES[id];
      assert.match(definition.apiRoute, /^\/api\//);
      assert.match(definition.uiPath, /^\/(?!\/)/);
      assert.doesNotMatch(definition.uiPath, /:\/\//);
    }
  }
});

test('builds a role workbench from observed receipts without inferring action authority', () => {
  const parsed = readCompanyCapabilityRuntimeAttestation(receipt([
    surface('terminal_state'),
    surface('terminal_receipt', false),
    surface('executor_isolation'),
    surface('result_binding'),
  ]));
  assert.ok(parsed);
  const workbench = buildCompanyRoleWorkbench({
    role_id: 'risk_governor', title: 'Risk Governor', department: 'trading_data',
  }, parsed);
  assert.ok(workbench);
  assert.equal(workbench.mode, 'read_only_observation');
  assert.equal(workbench.commandControls, false);
  assert.equal(workbench.mutationControls, false);
  assert.equal(workbench.bindings.length, 4);
  assert.equal(workbench.currentSurfaceCount, 3);
  assert.equal(workbench.bindings.find(binding => binding.id === 'terminal_receipt')?.observation, null);
});

test('a current receipt envelope cannot expose a noncurrent surface summary', () => {
  const parsed = readCompanyCapabilityRuntimeAttestation(receipt([
    surface('terminal_state'),
    surface('terminal_receipt', false),
  ]));
  assert.ok(parsed);
  assert.deepEqual(parsed.routes.find(route => route.id === 'terminal_receipt')?.summary,
    { reason: 'source_unavailable' });
  const workbench = buildCompanyRoleWorkbench({
    role_id: 'shadow_trade_validator', title: 'Shadow Trade Validator', department: 'trading_data',
  }, parsed);
  assert.ok(workbench);
  const staleBinding = workbench.bindings.find(binding => binding.id === 'terminal_receipt');
  assert.ok(staleBinding);
  assert.equal(staleBinding.observation, null);
  assert.equal(workbench.currentSurfaceCount, 1);
});

test('unknown departments remain unbound instead of receiving a guessed workbench', () => {
  assert.equal(buildCompanyRoleWorkbench({
    role_id: 'unknown', title: 'Unknown', department: 'not_registered',
  }, readCompanyCapabilityRuntimeAttestation(receipt())), null);
});
