import type { ManifestReceipt } from './repoManifestEvidence';

export interface RepoGraphNode {
  id: string;
  name: string;
  detail: string;
  path?: string;
  version?: string;
  kind: 'repository' | 'zone' | 'path' | 'package' | 'dependency' | 'development';
}
export interface RepoGraph {
  nodes: RepoGraphNode[];
  edges: Array<{ from: string; to: string }>;
  source: string;
  date: string | null;
  description: string;
  error: string | null;
}
const object = (value: unknown): Record<string, unknown> | null =>
  value !== null && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : null;
const safePath = (value: unknown): value is string => typeof value === 'string' && value.length > 0
  && value.length <= 240 && !/^[\\/]|^[A-Za-z]:|(?:^|[\\/])\.\.(?:[\\/]|$)/.test(value)
  && Array.from(value).every(character => character.charCodeAt(0) >= 32);

/** Repository zones are recorded containment, never inferred package dependencies. */
export function repositoryGraph(receipt: ManifestReceipt | null): RepoGraph {
  const base: RepoGraph = { nodes: [], edges: [], source: '/aureon_repo_sitemap.json', date: receipt?.date ?? null,
    description: 'Recorded repository structure. This snapshot does not attest the current checkout or running services.',
    error: receipt?.reason ?? 'Waiting for repository manifest.' };
  if (!receipt?.report) return base;
  const zones = receipt.report.zones;
  if (!Array.isArray(zones) || zones.length > 100) return { ...base, error: 'Repository zones are malformed.' };
  const nodes: RepoGraphNode[] = [{ id: 'repository', name: 'Aureon repository', kind: 'repository', detail: base.description }];
  const edges: RepoGraph['edges'] = [];
  const ids = new Set(['repository']);
  for (const item of zones) {
    const row = object(item);
    if (!row || typeof row.id !== 'string' || !/^[A-Za-z0-9_-]{1,100}$/.test(row.id)
      || typeof row.label !== 'string' || !row.label.trim() || !Array.isArray(row.paths)
      || row.paths.length > 200 || row.paths.some(path => !safePath(path))) {
      return { ...base, error: 'Repository zone fields are malformed.' };
    }
    const id = `zone:${row.id}`;
    if (ids.has(id)) return { ...base, error: 'Repository zone identities are duplicated.' };
    ids.add(id);
    nodes.push({ id, name: row.label, kind: 'zone', detail: `${row.paths.length} paths listed in this recorded zone.` });
    edges.push({ from: 'repository', to: id });
    for (const path of row.paths as string[]) {
      const pathId = `path:${path}`;
      if (!ids.has(pathId)) {
        ids.add(pathId);
        nodes.push({ id: pathId, name: path, path, kind: 'path', detail: 'Source path listed in the repository sitemap.' });
      }
      if (!edges.some(edge => edge.from === id && edge.to === pathId)) edges.push({ from: id, to: pathId });
    }
  }
  return { ...base, nodes, edges, error: null };
}

/** Source manifest declarations, not claims about installed versions or runtime activity. */
export function frontendPackageGraph(value: unknown): RepoGraph {
  const base: RepoGraph = { nodes: [], edges: [], source: 'frontend/package.json', date: null,
    description: 'Declarations from the frontend source bundled with this page. Version ranges are requested versions; installed and transitive versions are not attested.', error: null };
  const manifest = object(value);
  if (!manifest || typeof manifest.name !== 'string' || typeof manifest.version !== 'string') return { ...base, error: 'Frontend package manifest is unavailable.' };
  const nodes: RepoGraphNode[] = [{ id: 'frontend', name: manifest.name, version: manifest.version,
    kind: 'package', path: 'frontend/package.json', detail: 'Frontend root package declared in the source manifest.' }];
  const edges: RepoGraph['edges'] = [];
  for (const [field, kind] of [['dependencies', 'dependency'], ['devDependencies', 'development']] as const) {
    const rows = object(manifest[field]);
    if (!rows) return { ...base, error: `Frontend ${field} declarations are malformed.` };
    for (const [name, version] of Object.entries(rows)) {
      if (typeof version !== 'string' || !version || !name) return { ...base, error: 'A frontend dependency declaration is malformed.' };
      const id = `${kind}:${name}`;
      nodes.push({ id, name, version, kind, detail: `Declared in ${field}. The source manifest does not attest an installed version.` });
      edges.push({ from: 'frontend', to: id });
    }
  }
  nodes.splice(1, nodes.length - 1, ...nodes.slice(1).sort((a, b) => a.name.localeCompare(b.name)));
  return { ...base, nodes, edges };
}

export function visibleGraphNodes(graph: RepoGraph, query: string, page: number, pageSize = 12) {
  const needle = query.trim().toLowerCase();
  const matches = graph.nodes.filter(node => !needle || `${node.name} ${node.version ?? ''} ${node.kind}`.toLowerCase().includes(needle));
  const pages = Math.max(1, Math.ceil(matches.length / pageSize));
  const currentPage = Math.max(0, Math.min(pages - 1, page));
  return { nodes: matches.slice(currentPage * pageSize, (currentPage + 1) * pageSize), total: matches.length, pages, page: currentPage };
}
