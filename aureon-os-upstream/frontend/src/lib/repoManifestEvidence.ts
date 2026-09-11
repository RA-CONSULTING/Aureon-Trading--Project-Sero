import { z } from 'zod';
import { recordedReportEvidence } from './recordedReportEvidence';

const text = z.string();
const texts = z.array(text);
const number = z.number().finite();
const object = <T extends z.ZodRawShape>(shape: T) => z.object(shape).passthrough();
const summary = z.record(z.unknown());
const pathLink = object({ label: text, path: text });
const route = object({ id: text, label: text, user_action: text, safety_gate: text,
  primary_docs: texts, related_systems: texts, runtime_or_api_surface: texts });
const system = object({ path: text, category: text, readiness_status: text, access_mode: text,
  safety_gate: text, entrypoints: texts, public_artifacts: texts, validation_refs: texts });
const symbols = z.array(object({ ref: text, paths: texts }));
const directory = object({ path: text, name: text, parent: text, depth: number, category: text,
  role: text, zone_id: text, capability_ids: texts, file_count: number, direct_file_count: number,
  child_directory_count: number, child_directories: texts, direct_file_samples: texts });

const schemas: Record<string, z.ZodTypeAny> = {
  '/aureon_repo_sitemap.json': object({ zones: z.array(object({ id: text, label: text, paths: texts })),
    front_doors: z.array(pathLink), autonomous_frontend_manifests: texts.optional(), validation_command: text.optional(),
    public_contract: object({ contains_secrets: z.boolean().optional(), contains_private_runtime_state: z.boolean().optional(),
      contains_customer_data: z.boolean().optional(), purpose: text.optional() }).optional() }),
  '/aureon_end_user_access_map.json': object({ capabilities: z.array(route) }),
  '/aureon_capability_access_matrix.json': object({ summary, capabilities: z.array(object({
    id: text, label: text, description: text, readiness_status: text, access_routes: z.array(route),
    related_systems: z.array(system), end_user_start_points: texts, runtime_or_api_surfaces: texts,
    safety_gates: texts,
  })) }),
  '/aureon_capability_registry.json': object({ summary, capabilities: z.array(object({ id: text,
    label: text, description: text, surface_refs: texts, resolved_paths: texts, runtime_refs: texts,
    generated_refs: texts, command_refs: texts, code_symbol_refs: symbols, unresolved_refs: texts,
    system_paths: texts, access_route_ids: texts, public_artifacts: texts,
  })) }),
  '/aureon_repo_navigation_index.json': object({ summary: object({ category_counts: z.record(number) }),
    entries: z.array(object({ path: text, top_level: text, zone_id: text, category: text, role: text,
      kind: text, extension: text, capability_ids: texts })) }),
  '/aureon_repo_organization_tree.json': object({ summary, directories: z.array(directory),
    top_level: z.array(directory), root_files: texts }),
  '/aureon_repo_navigation_readiness.json': object({ summary: object({ readiness_status: z.enum(['pass', 'warn', 'fail']).optional() }), gates: z.array(object({ id: text,
    label: text, status: z.enum(['pass', 'warn', 'fail']), severity: text, evidence: texts })) }),
  '/aureon_system_integration_map.json': object({ summary, integration_sequence: texts,
    systems: z.array(system.extend({ tracked_files: number, integration_role: text,
      capability_ids: texts, access_route_ids: texts })) }),
  '/aureon_saas_integration_handoff.json': object({ summary: object({ handoff_status: text.optional(), readiness_status: text.optional() }), canonical_shape: text.optional(), public_assets: z.array(object({ id: text, path: text, purpose: text })),
    integration_steps: z.array(object({ id: text, label: text, action: text, evidence: texts, gate: text })),
    auth_and_hardening: object({ production_status: text, public_medium_risk_routes: texts,
      jwt_review_required_routes: texts }).optional() }),
  '/aureon_saas_integration_manifest.json': object({
    environment: object({ groups: z.record(texts) }), supabase: object({ public_endpoint_review_required: texts }),
    deployment_surfaces: z.array(object({ id: text, label: text, paths: texts, mode: text, tracked: z.boolean().optional() })),
    production_gates: texts,
  }),
  '/aureon_supabase_hardening_manifest.json': object({ summary, production_status: text.optional(), public_high_risk_routes: texts,
    public_medium_risk_routes: texts, jwt_review_required_routes: texts, production_gates: texts }),
};

export interface ManifestReceipt {
  source: string; report: Record<string, unknown> | null; date: string | null;
  receivedAt: string | null; reason: string;
}

export function readRepoManifest(source: string, value: unknown, now = Date.now()): ManifestReceipt {
  const metadata = recordedReportEvidence(value, now);
  const shape = schemas[source] ?? object({ summary, status: text.optional() });
  const parsed = shape.safeParse(value);
  if (!/^\/[A-Za-z0-9_.-]+\.json$/.test(source) || !metadata.current || !parsed.success) {
    return { source, report: null, date: metadata.timestamp, receivedAt: null,
      reason: !metadata.current ? metadata.reason : `Malformed report structure at ${!parsed.success ? parsed.error.issues[0]?.path.join('.') || 'root' : 'source'}; source fields unavailable.` };
  }
  return { source, report: value as Record<string, unknown>, date: metadata.timestamp,
    receivedAt: null, reason: 'Recorded structural manifest; current runtime readiness is not attested.' };
}

export async function fetchRepoManifest(source: string, signal: AbortSignal, fetcher: typeof fetch = fetch): Promise<ManifestReceipt> {
  if (!/^\/[A-Za-z0-9_.-]+\.json$/.test(source)) return readRepoManifest(source, null);
  const controller = new AbortController();
  const abort = () => controller.abort();
  if (signal.aborted) controller.abort();
  signal.addEventListener('abort', abort, { once: true });
  const timer = setTimeout(abort, 10_000);
  try {
    const response = await fetcher(source, { cache: 'no-cache', signal: controller.signal });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const receipt = readRepoManifest(source, await response.json());
    return { ...receipt, receivedAt: new Date().toISOString() };
  } catch (error) {
    return { source, report: null, date: null, receivedAt: null,
      reason: controller.signal.aborted ? 'Report request timed out or cancelled' : error instanceof Error ? error.message : 'Report request failed' };
  } finally { clearTimeout(timer); signal.removeEventListener('abort', abort); }
}

/** Bounded readers return independent receipts; a missing sibling never discards a valid report. */
export async function fetchRepoManifests(sources: string[], signal: AbortSignal, fetcher: typeof fetch = fetch): Promise<ManifestReceipt[]> {
  const results: ManifestReceipt[] = [];
  for (let i = 0; i < sources.length; i += 3) {
    if (signal.aborted) break;
    results.push(...await Promise.all(sources.slice(i, i + 3).map(source => fetchRepoManifest(source, signal, fetcher))));
  }
  return results;
}
