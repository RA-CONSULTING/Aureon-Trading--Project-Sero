import assert from 'node:assert/strict';
import test from 'node:test';
import { readRepoManifest } from './repoManifestEvidence';
import { frontendPackageGraph, repositoryGraph, visibleGraphNodes } from './repoGraphEvidence';

const manifest = (zones: unknown[]) => readRepoManifest('/aureon_repo_sitemap.json', {
  snapshot_date: '2026-07-13', zones, front_doors: [],
}, Date.parse('2026-09-11T00:00:00Z'));
test('repository graph preserves dated actual containment, not package or running-service claims', () => {
  const graph = repositoryGraph(manifest([{ id: 'runtime', label: 'Runtime', paths: ['aureon/', 'scripts/'] }]));
  assert.equal(graph.error, null); assert.equal(graph.nodes.length, 4); assert.equal(graph.date, '2026-07-13');
  assert.deepEqual(graph.edges, [{ from: 'repository', to: 'zone:runtime' }, { from: 'zone:runtime', to: 'path:aureon/' }, { from: 'zone:runtime', to: 'path:scripts/' }]);
  assert.ok(graph.nodes.every(node => node.version === undefined));
});
test('missing, future, malformed and duplicate manifests cannot produce inventory nodes', () => {
  assert.equal(repositoryGraph(null).nodes.length, 0);
  assert.equal(repositoryGraph(readRepoManifest('/aureon_repo_sitemap.json', { snapshot_date: '2099-01-01', zones: [], front_doors: [] })).nodes.length, 0);
  for (const zones of [[{ id: 'bad', label: 'Bad', paths: ['../private'] }], [{ id: 'a', label: 'A', paths: [] }, { id: 'a', label: 'Again', paths: [] }]]) {
    assert.equal(repositoryGraph(manifest(zones)).nodes.length, 0);
  }
});
test('shared paths produce one node with recorded containment edges and no invented dependency metadata', () => {
  const graph = repositoryGraph(manifest([{ id: 'a', label: 'A', paths: ['shared/'] }, { id: 'b', label: 'B', paths: ['shared/'] }]));
  assert.equal(graph.nodes.filter(node => node.path === 'shared/').length, 1);
  assert.equal(graph.edges.filter(edge => edge.to === 'path:shared/').length, 2);
});
test('frontend source declarations preserve ranges and dependency kinds', () => {
  const graph = frontendPackageGraph({ name: 'actual-app', version: '0.0.0', dependencies: { react: '^18.3.1' }, devDependencies: { vite: '^5.4.1' } });
  assert.equal(graph.nodes.find(node => node.name === 'react')?.version, '^18.3.1');
  assert.equal(graph.nodes.find(node => node.name === 'vite')?.kind, 'development');
  assert.equal(graph.edges.length, 2); assert.match(graph.description, /installed and transitive versions are not attested/);
  assert.equal(frontendPackageGraph({ name: 'bad', version: '1', dependencies: { bad: false }, devDependencies: {} }).nodes.length, 0);
});
test('all real nodes remain accessible by pagination and filtering', () => {
  const graph = frontendPackageGraph({ name: 'app', version: '1', dependencies: Object.fromEntries(Array.from({ length: 30 }, (_, i) => [`dep-${i}`, '^1'])), devDependencies: {} });
  assert.equal(visibleGraphNodes(graph, '', 0).pages, 3);
  assert.equal(visibleGraphNodes(graph, '', 999).nodes.length, 7);
  assert.equal(visibleGraphNodes(graph, 'dep-29', 999).nodes[0].name, 'dep-29');
  assert.equal(visibleGraphNodes(graph, 'nonexistent', 0).total, 0);
});
