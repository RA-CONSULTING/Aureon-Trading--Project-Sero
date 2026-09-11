/** Repo Map: the reviewed glass graph, connected to repository and package manifests. */
import { useMemo, useState, type CSSProperties, type ReactNode } from 'react';
import { Boxes, ChevronLeft, ChevronRight, ExternalLink, GitBranch, Info, LayoutGrid, Network, RefreshCw, Search } from 'lucide-react';
import { Link } from 'react-router-dom';
import packageSource from '../../../package.json?raw';
import { useReadOnlyPoller } from '@/hooks/useReadOnlyPoller';
import { repoMapStore } from '@/services/repoMapReads';
import { frontendPackageGraph, repositoryGraph, visibleGraphNodes } from '@/lib/repoGraphEvidence';

const GOLD = '#FFB800', CYAN = '#00E5FF', BG = '#0e0e0e', PANEL = 'rgba(18,18,18,0.72)', BORDER = '#3f3f46';
type LayoutMode = 'grid' | 'cluster' | 'graph';
const frontendGraph = frontendPackageGraph(JSON.parse(packageSource));

function GlassPanel({ children, className = '', style }: { children: ReactNode; className?: string; style?: CSSProperties }) {
  return <div className={`rounded-lg border ${className}`} style={{ background: PANEL, borderColor: BORDER,
    backdropFilter: 'blur(12px)', WebkitBackdropFilter: 'blur(12px)', ...style }}>{children}</div>;
}
function EvidenceBadge({ children }: { children: ReactNode }) {
  return <span className="inline-flex rounded border px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wider"
    style={{ color: CYAN, borderColor: `${CYAN}55`, background: `${CYAN}12` }}>{children}</span>;
}
function position(index: number, count: number, layout: LayoutMode) {
  if (layout === 'graph') {
    if (index === 0) return { x: 50, y: 46 };
    const angle = (index - 1) * 2 * Math.PI / Math.max(1, count - 1) - Math.PI / 2;
    return { x: 50 + Math.cos(angle) * 34, y: 46 + Math.sin(angle) * 34 };
  }
  const cols = layout === 'cluster' ? 2 : 3;
  const rows = Math.ceil(count / cols);
  return { x: layout === 'cluster' ? 27 + (index % cols) * 46 : 18 + (index % cols) * 32,
    y: 12 + Math.floor(index / cols) * (72 / Math.max(1, rows - 1)) };
}

export default function RepoMapPage() {
  const receipt = useReadOnlyPoller(repoMapStore, 60_000, 10_000);
  const [source, setSource] = useState<'repository' | 'frontend'>('repository');
  const [query, setQuery] = useState('');
  const [layout, setLayout] = useState<LayoutMode>('grid');
  const [page, setPage] = useState(0);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const graph = useMemo(() => source === 'frontend' ? frontendGraph : repositoryGraph(receipt.data), [source, receipt.data]);
  const visible = visibleGraphNodes(graph, query, page, layout === 'graph' ? 9 : 12);
  const selected = visible.nodes.find(node => node.id === selectedId) ?? visible.nodes[0] ?? null;
  const positioned = visible.nodes.map((node, index) => ({ ...node, ...position(index, visible.nodes.length, layout) }));
  const byId = new Map(positioned.map(node => [node.id, node]));
  const selectedChildren = selected ? graph.edges.filter(edge => edge.from === selected.id).map(edge => graph.nodes.find(node => node.id === edge.to)!).filter(Boolean) : [];
  const isRepository = source === 'repository';
  const unavailable = isRepository && !receipt.loading && (!!receipt.error || !!graph.error);
  const loading = isRepository && receipt.loading;
  const modeName = isRepository ? 'Recorded structure' : 'Source declarations';
  const chooseSource = (next: 'repository' | 'frontend') => { setSource(next); setPage(0); setSelectedId(null); setQuery(''); };

  return (
    <div className="min-h-full space-y-4 p-4 text-zinc-100" style={{ background: BG }} data-repo-map="shipped-glass-v1" data-repo-map-theme="aureon-dark">
      <div className="rounded-md border px-3 py-2" style={{ borderColor: `${GOLD}66`, background: `${GOLD}14` }}>
        <p className="text-[11px] font-semibold uppercase tracking-[0.14em]" style={{ color: GOLD }}>Repository evidence</p>
        <p className="mt-1 text-xs text-zinc-400">{graph.description}</p>
        {graph.date && <p className="mt-1 text-[11px] font-mono text-zinc-400">Snapshot: {graph.date}</p>}
      </div>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex flex-wrap items-center gap-3"><h1 className="text-2xl font-bold uppercase tracking-[0.08em] text-white">Repo Map</h1><EvidenceBadge>{modeName}</EvidenceBadge></div>
          <p className="mt-1 text-xs text-zinc-400">Explore the repository structure and declared frontend dependencies.</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <label className="relative"><span className="sr-only">Filter repository nodes</span><Search className="pointer-events-none absolute left-3 top-3 h-3.5 w-3.5 text-zinc-500" />
            <input value={query} onChange={event => { setQuery(event.target.value); setPage(0); }} placeholder="Filter nodes..."
              className="h-9 w-56 rounded-md border bg-black/40 pl-9 pr-3 text-sm outline-none" style={{ borderColor: BORDER }} /></label>
          <div className="inline-flex gap-1 rounded-md border p-1" style={{ borderColor: BORDER }}>
            {([{ id: 'grid', icon: LayoutGrid }, { id: 'cluster', icon: Boxes }, { id: 'graph', icon: Network }] as const).map(({ id, icon: Icon }) =>
              <button key={id} type="button" aria-label={`${id} layout`} aria-pressed={layout === id} onClick={() => setLayout(id)}
                className="rounded border p-1.5" style={{ color: layout === id ? GOLD : '#a1a1aa', borderColor: layout === id ? GOLD : 'transparent', background: layout === id ? `${GOLD}22` : 'transparent' }}><Icon className="h-4 w-4" /></button>)}
          </div>
          <button type="button" onClick={() => receipt.refresh()} className="inline-flex h-9 items-center gap-2 rounded border px-3 text-xs" style={{ borderColor: BORDER }}><RefreshCw className="h-3.5 w-3.5" />Refresh manifest</button>
        </div>
      </div>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap gap-2">
          {(['repository', 'frontend'] as const).map(value => <button key={value} type="button" aria-pressed={source === value} onClick={() => chooseSource(value)}
            className="rounded-md border px-3 py-2 text-xs" style={{ color: source === value ? GOLD : '#a1a1aa', borderColor: source === value ? GOLD : BORDER }}>{value === 'repository' ? 'Repository zones' : 'Frontend packages'}</button>)}
        </div>
        <Link to="/platform/coverage" className="inline-flex items-center gap-1.5 text-xs" style={{ color: CYAN }}>Open current systems coverage<ExternalLink className="h-3 w-3" /></Link>
      </div>
      <div className="grid gap-4 xl:grid-cols-[1fr_320px]">
        <GlassPanel className="relative min-h-[620px] overflow-hidden">
          <div className="absolute inset-0 opacity-40" style={{ backgroundImage: 'radial-gradient(circle,#3f3f46 1px,transparent 1px)', backgroundSize: '18px 18px' }} />
          <div className="relative overflow-x-auto">
            <div className="relative h-[560px] min-w-[680px]">
              <svg className="pointer-events-none absolute inset-0 h-full w-full" aria-hidden>
                {graph.edges.map(edge => {
                  const from = byId.get(edge.from), to = byId.get(edge.to);
                  return from && to ? <line key={`${edge.from}-${edge.to}`} x1={`${from.x}%`} y1={`${from.y}%`} x2={`${to.x}%`} y2={`${to.y}%`} stroke={CYAN} strokeWidth={1.25} opacity={0.5} /> : null;
                })}
              </svg>
              {positioned.map(node => <button key={node.id} type="button" onClick={() => setSelectedId(node.id)} aria-pressed={selected?.id === node.id}
                className="absolute w-[174px] -translate-x-1/2 -translate-y-1/2 rounded-md border px-3 py-2 text-left shadow-lg transition-transform hover:scale-[1.03]"
                style={{ left: `${node.x}%`, top: `${node.y}%`, background: selected?.id === node.id ? '#2b2411' : '#121212', borderColor: selected?.id === node.id ? GOLD : BORDER, boxShadow: selected?.id === node.id ? `0 0 24px ${GOLD}22` : undefined }}>
                <div className="break-words font-mono text-[11px] font-semibold text-zinc-100">{node.name}</div>
                <div className="mt-1 flex flex-wrap items-center gap-1.5 text-[10px] text-zinc-400">{node.version && <span>{node.version}</span>}<span>{node.kind}</span></div>
              </button>)}
              {(loading || unavailable || visible.total === 0) && <div className="absolute inset-0 flex items-center justify-center p-8 text-center">
                <div className="max-w-lg rounded-lg border bg-[#121212] p-5" style={{ borderColor: BORDER }} role="status">
                  <Info className="mx-auto mb-2 h-5 w-5" style={{ color: GOLD }} />
                  <p className="text-sm">{loading ? 'Reading repository manifest…' : unavailable ? 'Repository manifest unavailable' : 'No matching nodes'}</p>
                  <p className="mt-2 text-xs text-zinc-400">{unavailable ? receipt.error ?? graph.error : !loading ? 'Change the filter or choose another source.' : 'Retrieving the dated structural report.'}</p>
                </div>
              </div>}
            </div>
          </div>
          <div className="relative flex flex-wrap items-center justify-between gap-3 border-t px-3 py-3 text-[10px] text-zinc-400" style={{ borderColor: BORDER }}>
            <span><span style={{ color: GOLD }}>■</span> Selected · <span style={{ color: CYAN }}>━</span> {isRepository ? 'Contains / lists' : 'Declares dependency'} · {visible.total} matching nodes</span>
            <div className="flex items-center gap-2"><button type="button" aria-label="Previous nodes" disabled={visible.page === 0} onClick={() => setPage(visible.page - 1)} className="rounded border p-1 disabled:opacity-30" style={{ borderColor: BORDER }}><ChevronLeft className="h-4 w-4" /></button>
              <span>{visible.page + 1} / {visible.pages}</span><button type="button" aria-label="Next nodes" disabled={visible.page + 1 >= visible.pages} onClick={() => setPage(visible.page + 1)} className="rounded border p-1 disabled:opacity-30" style={{ borderColor: BORDER }}><ChevronRight className="h-4 w-4" /></button></div>
          </div>
        </GlassPanel>
        <GlassPanel className="space-y-4 p-4">
          <section><p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-zinc-500">Selected node</p>
            <h2 className="mt-2 break-words font-mono text-lg font-semibold" style={{ color: GOLD }}>{selected?.name ?? 'No selection'}</h2>
            {selected?.version && <p className="mt-1 font-mono text-sm text-zinc-400">{selected.version}</p>}<p className="mt-2 text-xs text-zinc-400">{selected?.detail ?? 'Select a node to inspect its source evidence.'}</p></section>
          <section className="rounded-md border p-3" style={{ borderColor: BORDER }}>
            <p className="text-[11px] font-semibold uppercase" style={{ color: CYAN }}>{modeName}</p>
            <p className="mt-1 break-all font-mono text-xs text-zinc-300">{graph.source}</p>
            {graph.date && <p className="mt-2 text-xs text-zinc-400">Original snapshot: {graph.date}</p>}
            {isRepository && receipt.lastReceivedAt && <p className="mt-1 text-xs text-zinc-500">HTTP read: {new Date(receipt.lastReceivedAt).toLocaleString()}</p>}
            <p className="mt-2 text-[11px] text-zinc-500">{isRepository ? 'Historical structure; current checkout contents need a fresh inventory.' : 'Source declaration; installed versions need a runtime inventory.'}</p>
          </section>
          {selected?.path && <section><p className="text-[10px] uppercase text-zinc-500">Source path</p><p className="mt-1 break-all font-mono text-xs text-zinc-300">{selected.path}</p></section>}
          <section><p className="text-[10px] uppercase text-zinc-500">{isRepository ? 'Listed children' : 'Declared direct dependencies'}</p>
            <p className="mt-1 font-mono text-lg" style={{ color: CYAN }}>{selected ? isRepository || selected.kind === 'package' ? selectedChildren.length : 'Unavailable' : '—'}</p>
            {selectedChildren.length > 0 && <div className="mt-2 max-h-48 space-y-1 overflow-y-auto">{selectedChildren.map(node => <button key={node.id} type="button" onClick={() => { setSelectedId(node.id); setQuery(node.name); setPage(0); }} className="block max-w-full break-all text-left font-mono text-[11px] hover:underline" style={{ color: CYAN }}>{node.name}</button>)}</div>}
            <p className="mt-2 text-[11px] text-zinc-500">{isRepository ? 'Lines show only relationships explicitly listed in the manifest.' : 'Transitive dependencies and installed versions are not supplied by this manifest.'}</p>
          </section>
          <div className="space-y-2 border-t pt-3" style={{ borderColor: BORDER }}>
            <a href="/aureon_repo_sitemap.json" target="_blank" rel="noreferrer" className="flex items-center gap-2 text-xs" style={{ color: CYAN }}><GitBranch className="h-3.5 w-3.5" />Open repository source manifest</a>
            <Link to="/platform/console#repo-map" className="flex items-center gap-2 text-xs" style={{ color: CYAN }}><Network className="h-3.5 w-3.5" />Open detailed repository explorer</Link>
          </div>
        </GlassPanel>
      </div>
    </div>
  );
}
