/**
 * Repo Map — claim-honest shipped glass (repo_map_concept_v1).
 *
 * Aligns /platform/repo-map to concept board: package composition graph +
 * detail rail. Package counts, versions, and dates are EXAMPLE until a real
 * probe lands. zinc/gold/cyan only; no paint-green; no fake live chips.
 * Banner: SHIPPED GLASS · EXAMPLE LAYOUT WHERE MARKED
 */

import { useMemo, useState, type CSSProperties, type ReactNode } from "react";
import {
  AlertTriangle,
  Boxes,
  GitBranch,
  Grid3X3,
  Info,
  LayoutGrid,
  Network,
  Search,
} from "lucide-react";

const GOLD = "#FFB800";
const CYAN = "#00E5FF";
const BG = "#0e0e0e";
const PANEL = "rgba(18, 18, 18, 0.72)";
const PANEL_SOLID = "#121212";
const BORDER = "#3f3f46";
const WARN = "#EAB308";

type LayoutMode = "grid" | "cluster" | "graph";

type PackageNode = {
  id: string;
  name: string;
  version: string;
  x: number;
  y: number;
  external?: boolean;
  description?: string;
  repoUrl?: string;
  language?: string;
  lineCount?: string;
  lastCommit?: string;
  license?: string;
  team?: string;
  directDeps?: number;
  transitiveDeps?: number;
};

/** EXAMPLE composition until real probe — stamped in UI. */
const EXAMPLE_PACKAGES: PackageNode[] = [
  {
    id: "aureon-ingest",
    name: "aureon-ingest",
    version: "v0.9.40",
    x: 18,
    y: 22,
    description: "Ingest adapters and evidence intake.",
    repoUrl: "github.com/aureon/aureon-ingest",
    language: "Rust",
    lineCount: "~6.2k",
    lastCommit: "2025-05-12",
    license: "Aureon Internal",
    team: "Evidence Platform",
    directDeps: 3,
    transitiveDeps: 11,
  },
  {
    id: "aureon-index",
    name: "aureon-index",
    version: "v0.9.41",
    x: 18,
    y: 58,
    description: "Index and retrieval surface for evidence.",
    repoUrl: "github.com/aureon/aureon-index",
    language: "Rust",
    lineCount: "~9.4k",
    lastCommit: "2025-05-14",
    license: "Aureon Internal",
    team: "Evidence Platform",
    directDeps: 4,
    transitiveDeps: 14,
  },
  {
    id: "aureon-core",
    name: "aureon-core",
    version: "v0.9.42",
    x: 48,
    y: 40,
    description: "Core domain model and evidence engine.",
    repoUrl: "github.com/aureon/aureon-core",
    language: "Rust",
    lineCount: "~18.7k",
    lastCommit: "2025-05-17",
    license: "Aureon Internal",
    team: "Evidence Platform",
    directDeps: 7,
    transitiveDeps: 23,
  },
  {
    id: "aureon-policy",
    name: "aureon-policy",
    version: "v0.9.38",
    x: 72,
    y: 18,
    description: "Policy evaluation and claim gates.",
    repoUrl: "github.com/aureon/aureon-policy",
    language: "Rust",
    lineCount: "~4.1k",
    lastCommit: "2025-05-10",
    license: "Aureon Internal",
    team: "Evidence Platform",
    directDeps: 2,
    transitiveDeps: 8,
  },
  {
    id: "aureon-signals",
    name: "aureon-signals",
    version: "v0.9.39",
    x: 78,
    y: 52,
    description: "Signal bus and observation fan-out.",
    repoUrl: "github.com/aureon/aureon-signals",
    language: "Rust",
    lineCount: "~7.8k",
    lastCommit: "2025-05-15",
    license: "Aureon Internal",
    team: "Evidence Platform",
    directDeps: 5,
    transitiveDeps: 16,
  },
  {
    id: "aureon-entities",
    name: "aureon-entities",
    version: "v0.9.37",
    x: 58,
    y: 72,
    description: "Entity graph and identity bindings.",
    repoUrl: "github.com/aureon/aureon-entities",
    language: "Rust",
    lineCount: "~5.5k",
    lastCommit: "2025-05-09",
    license: "Aureon Internal",
    team: "Evidence Platform",
    directDeps: 3,
    transitiveDeps: 10,
  },
  {
    id: "aureon-events",
    name: "aureon-events",
    version: "v0.9.36",
    x: 32,
    y: 78,
    description: "Event envelope and timeline store.",
    repoUrl: "github.com/aureon/aureon-events",
    language: "Rust",
    lineCount: "~3.9k",
    lastCommit: "2025-05-08",
    license: "Aureon Internal",
    team: "Evidence Platform",
    directDeps: 2,
    transitiveDeps: 7,
  },
  {
    id: "aureon-audit",
    name: "aureon-audit",
    version: "v0.9.35",
    x: 88,
    y: 30,
    description: "Audit trail and integrity receipts.",
    repoUrl: "github.com/aureon/aureon-audit",
    language: "Rust",
    lineCount: "~2.8k",
    lastCommit: "2025-05-07",
    license: "Aureon Internal",
    team: "Evidence Platform",
    directDeps: 2,
    transitiveDeps: 6,
  },
  {
    id: "aureon-sdk",
    name: "aureon-sdk",
    version: "v0.8.12",
    x: 92,
    y: 70,
    external: true,
    description: "External SDK surface — not an internal package.",
    repoUrl: "github.com/aureon/aureon-sdk",
    language: "TypeScript",
    lineCount: "~12.0k",
    lastCommit: "2025-04-28",
    license: "Apache-2.0",
    team: "External / Partner",
    directDeps: 0,
    transitiveDeps: 0,
  },
];

/** EXAMPLE edges — Depends On (cyan) + one external dashed link. */
const EXAMPLE_EDGES: Array<{ from: string; to: string; weak?: boolean; external?: boolean }> = [
  { from: "aureon-core", to: "aureon-ingest" },
  { from: "aureon-core", to: "aureon-index" },
  { from: "aureon-core", to: "aureon-policy" },
  { from: "aureon-core", to: "aureon-signals" },
  { from: "aureon-core", to: "aureon-entities" },
  { from: "aureon-core", to: "aureon-events" },
  { from: "aureon-core", to: "aureon-audit" },
  { from: "aureon-index", to: "aureon-ingest", weak: true },
  { from: "aureon-signals", to: "aureon-events", weak: true },
  { from: "aureon-core", to: "aureon-sdk", external: true },
];

const EXAMPLE_TOTAL = 42;
const EXAMPLE_DIRECT = 9;

function ExampleBadge({ label = "EXAMPLE" }: { label?: string }) {
  return (
    <span
      className="inline-flex items-center rounded px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wider"
      style={{ color: GOLD, background: `${GOLD}18`, border: `1px solid ${GOLD}55` }}
    >
      {label}
    </span>
  );
}

function GlassPanel({
  children,
  className = "",
  style,
}: {
  children: ReactNode;
  className?: string;
  style?: CSSProperties;
}) {
  return (
    <div
      className={`rounded-lg border ${className}`}
      style={{
        background: PANEL,
        borderColor: BORDER,
        backdropFilter: "blur(12px)",
        WebkitBackdropFilter: "blur(12px)",
        ...style,
      }}
    >
      {children}
    </div>
  );
}

function ClaimDot({ tone, label, detail }: { tone: "cyan" | "gold" | "warn"; label: string; detail: string }) {
  const color = tone === "cyan" ? CYAN : tone === "gold" ? GOLD : WARN;
  return (
    <div
      className="rounded-md border px-3 py-2"
      style={{
        borderColor: tone === "warn" ? `${WARN}66` : `${BORDER}`,
        background: tone === "warn" ? `${WARN}12` : "rgba(0,0,0,0.25)",
      }}
    >
      <div className="flex items-center gap-2">
        <span className="h-2 w-2 rounded-full" style={{ background: color, boxShadow: `0 0 8px ${color}` }} />
        <span className="text-[11px] font-semibold uppercase tracking-wider" style={{ color }}>
          {label}
        </span>
        {tone === "warn" ? <Info className="ml-auto h-3.5 w-3.5" style={{ color: WARN }} /> : null}
      </div>
      <p className="mt-1 text-[11px] text-zinc-400">{detail}</p>
    </div>
  );
}

export default function RepoMapPage() {
  const [query, setQuery] = useState("");
  const [layout, setLayout] = useState<LayoutMode>("grid");
  const [selectedId, setSelectedId] = useState("aureon-core");

  const packages = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return EXAMPLE_PACKAGES;
    return EXAMPLE_PACKAGES.filter(
      (p) => p.name.toLowerCase().includes(needle) || p.version.toLowerCase().includes(needle),
    );
  }, [query]);

  const selected = EXAMPLE_PACKAGES.find((p) => p.id === selectedId) ?? EXAMPLE_PACKAGES[2];
  const byId = useMemo(() => new Map(EXAMPLE_PACKAGES.map((p) => [p.id, p])), []);

  const layoutIcons: Array<{ id: LayoutMode; icon: typeof LayoutGrid; label: string }> = [
    { id: "grid", icon: LayoutGrid, label: "Grid / Blocks" },
    { id: "cluster", icon: Boxes, label: "Cluster" },
    { id: "graph", icon: Network, label: "Graph" },
  ];

  return (
    <div
      className="min-h-full space-y-4 p-4 text-zinc-100"
      style={{ background: BG }}
      data-repo-map="shipped-glass-v1"
      data-repo-map-theme="aureon-dark"
    >
      {/* Honesty banner */}
      <div
        className="rounded-md border px-3 py-2"
        style={{ borderColor: `${GOLD}66`, background: `${GOLD}14` }}
      >
        <div className="flex flex-wrap items-center gap-2">
          <p className="text-[11px] font-semibold uppercase tracking-[0.14em]" style={{ color: GOLD }}>
            SHIPPED GLASS · EXAMPLE LAYOUT WHERE MARKED
          </p>
          <ExampleBadge />
        </div>
        <p
          className="mt-0.5 flex flex-wrap items-center gap-1.5 text-[10px] uppercase tracking-wide"
          style={{ color: `${GOLD}cc` }}
        >
          <AlertTriangle className="h-3 w-3 shrink-0" style={{ color: GOLD }} />
          Package counts, versions, and dates are EXAMPLE until a real probe — not live inventory.
        </p>
      </div>

      {/* Header bar */}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="text-2xl font-bold uppercase tracking-[0.08em] text-white">Repo Map</h1>
            <ExampleBadge label="EXAMPLE LAYOUT" />
          </div>
          <p className="mt-1 text-[12px] text-zinc-400">System composition and package dependencies.</p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-zinc-500" />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Filter packages..."
              className="h-9 w-56 rounded-md border bg-black/40 pl-9 pr-3 text-sm text-zinc-100 outline-none placeholder:text-zinc-500 focus:border-[color:var(--rm-cyan)]"
              style={{ borderColor: BORDER, ["--rm-cyan" as string]: CYAN }}
            />
          </div>

          <div className="inline-flex items-center gap-1 rounded-md border p-1" style={{ borderColor: BORDER, background: PANEL_SOLID }}>
            {layoutIcons.map(({ id, icon: Icon, label }) => {
              const active = layout === id;
              return (
                <button
                  key={id}
                  type="button"
                  title={label}
                  aria-label={label}
                  onClick={() => setLayout(id)}
                  className="rounded p-1.5 transition-colors"
                  style={{
                    color: active ? GOLD : "#a1a1aa",
                    background: active ? `${GOLD}22` : "transparent",
                    border: active ? `1px solid ${GOLD}` : "1px solid transparent",
                  }}
                >
                  <Icon className="h-4 w-4" />
                </button>
              );
            })}
          </div>

          <button
            type="button"
            className="inline-flex h-9 items-center gap-2 rounded-md border px-3 text-xs text-zinc-300"
            style={{ borderColor: BORDER, background: PANEL_SOLID }}
          >
            All Systems
            <span className="font-mono" style={{ color: CYAN }}>
              | {EXAMPLE_TOTAL}
            </span>
            <ExampleBadge />
          </button>
        </div>
      </div>

      {/* Main: canvas + detail rail */}
      <div className="grid gap-4 xl:grid-cols-[1fr_320px]">
        <GlassPanel className="relative min-h-[560px] overflow-hidden">
          {/* Dot grid */}
          <div
            className="absolute inset-0 opacity-40"
            style={{
              backgroundImage: `radial-gradient(circle, #3f3f46 1px, transparent 1px)`,
              backgroundSize: "18px 18px",
            }}
          />

          {/* External divider */}
          <div
            className="pointer-events-none absolute bottom-16 right-[8%] top-10 w-px border-l border-dashed"
            style={{ borderColor: `${CYAN}66` }}
          />
          <div
            className="pointer-events-none absolute right-[3%] top-6 text-[10px] font-semibold uppercase tracking-[0.16em]"
            style={{ color: `${CYAN}aa` }}
          >
            External
          </div>

          {/* SVG edges */}
          <svg className="absolute inset-0 h-full w-full" aria-hidden>
            {EXAMPLE_EDGES.map((edge) => {
              const a = byId.get(edge.from);
              const b = byId.get(edge.to);
              if (!a || !b) return null;
              const visible =
                packages.some((p) => p.id === a.id) && packages.some((p) => p.id === b.id);
              if (!visible) return null;
              const stroke = edge.external ? CYAN : edge.weak ? "#71717a" : CYAN;
              return (
                <line
                  key={`${edge.from}-${edge.to}`}
                  x1={`${a.x}%`}
                  y1={`${a.y}%`}
                  x2={`${b.x}%`}
                  y2={`${b.y}%`}
                  stroke={stroke}
                  strokeWidth={edge.weak ? 1 : 1.5}
                  strokeDasharray={edge.external ? "6 5" : undefined}
                  opacity={edge.weak ? 0.55 : 0.85}
                />
              );
            })}
          </svg>

          {/* Nodes */}
          <div className="relative z-10 h-full min-h-[560px]">
            {packages.map((pkg) => {
              const selectedNode = pkg.id === selected.id;
              return (
                <button
                  key={pkg.id}
                  type="button"
                  onClick={() => setSelectedId(pkg.id)}
                  className="absolute -translate-x-1/2 -translate-y-1/2 rounded-md border px-3 py-2 text-left shadow-lg transition-transform hover:scale-[1.03]"
                  style={{
                    left: `${pkg.x}%`,
                    top: `${pkg.y}%`,
                    minWidth: 138,
                    background: selectedNode ? `${GOLD}14` : PANEL_SOLID,
                    borderColor: selectedNode ? GOLD : pkg.external ? CYAN : BORDER,
                    borderStyle: pkg.external ? "dashed" : "solid",
                    borderWidth: selectedNode ? 2 : 1,
                    boxShadow: selectedNode ? `0 0 0 1px ${GOLD}55, 0 0 24px ${GOLD}22` : undefined,
                  }}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-mono text-[12px] font-semibold text-zinc-100">{pkg.name}</span>
                    {selectedNode ? (
                      <span
                        className="rounded px-1 py-0.5 text-[8px] font-bold uppercase tracking-wider"
                        style={{ background: GOLD, color: "#0a0a0a" }}
                      >
                        Selected
                      </span>
                    ) : null}
                    {pkg.external ? (
                      <span className="text-[8px] font-bold uppercase tracking-wider" style={{ color: CYAN }}>
                        External
                      </span>
                    ) : null}
                  </div>
                  <div className="mt-0.5 flex items-center gap-1.5">
                    <span className="font-mono text-[10px] text-zinc-400">{pkg.version}</span>
                    <ExampleBadge />
                  </div>
                </button>
              );
            })}
          </div>

          {/* Legend */}
          <div className="absolute bottom-3 left-3 z-20 flex flex-wrap items-center gap-3 rounded-md border px-3 py-2 text-[10px] text-zinc-400"
            style={{ borderColor: BORDER, background: "rgba(10,10,10,0.85)" }}
          >
            <span className="inline-flex items-center gap-1.5">
              <span className="h-2.5 w-4 rounded-sm" style={{ background: GOLD }} /> Selected Package
            </span>
            <span className="inline-flex items-center gap-1.5">
              <span className="h-0.5 w-5" style={{ background: CYAN }} /> Depends On
            </span>
            <span className="inline-flex items-center gap-1.5">
              <span className="h-0.5 w-5 bg-zinc-500" /> Optional / Weak
            </span>
            <span className="inline-flex items-center gap-1.5">
              <span className="h-0.5 w-5 border-t border-dashed" style={{ borderColor: CYAN }} /> External
            </span>
          </div>

          {/* Status bar */}
          <div
            className="absolute bottom-3 right-3 z-20 rounded-md border px-3 py-1.5 font-mono text-[10px] text-zinc-400"
            style={{ borderColor: BORDER, background: "rgba(10,10,10,0.85)" }}
          >
            Showing 1 selected · {EXAMPLE_DIRECT} direct · {EXAMPLE_TOTAL} total packages{" "}
            <ExampleBadge />
          </div>

          {layout !== "grid" ? (
            <div
              className="absolute left-1/2 top-3 z-20 -translate-x-1/2 rounded-md border px-3 py-1 text-[10px] uppercase tracking-wider"
              style={{ borderColor: `${GOLD}66`, color: GOLD, background: `${GOLD}14` }}
            >
              {layout} view — EXAMPLE layout toggle (grid is the shipped composition)
            </div>
          ) : null}
        </GlassPanel>

        {/* Right detail rail */}
        <GlassPanel className="space-y-4 p-4">
          <section>
            <div className="mb-2 flex items-center justify-between gap-2">
              <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-zinc-500">Package</p>
              <ExampleBadge />
            </div>
            <h2 className="font-mono text-lg font-semibold" style={{ color: GOLD }}>
              {selected.name}
            </h2>
            <p className="mt-0.5 font-mono text-sm text-zinc-400">{selected.version}</p>
            <p className="mt-2 text-sm text-zinc-300">{selected.description}</p>
            {selected.repoUrl ? (
              <a
                href={`https://${selected.repoUrl}`}
                target="_blank"
                rel="noreferrer"
                className="mt-2 inline-flex items-center gap-1 text-xs hover:underline"
                style={{ color: CYAN }}
              >
                <GitBranch className="h-3.5 w-3.5" />
                {selected.repoUrl}
              </a>
            ) : null}
          </section>

          <section className="space-y-2">
            <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-zinc-500">Status Claims</p>
            <ClaimDot
              tone="cyan"
              label="Observed"
              detail="Package and version observed in repository. EXAMPLE until probe."
            />
            <ClaimDot
              tone="gold"
              label="Dark"
              detail="No public release or source artifact available."
            />
            <ClaimDot
              tone="warn"
              label="Hold"
              detail="Integrity or provenance verification withheld."
            />
          </section>

          <section>
            <div className="mb-2 flex items-center justify-between">
              <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-zinc-500">Metadata</p>
              <ExampleBadge />
            </div>
            <dl className="grid grid-cols-2 gap-x-3 gap-y-2 text-xs">
              <div>
                <dt className="text-zinc-500">Language</dt>
                <dd className="text-zinc-200">{selected.language ?? "—"}</dd>
              </div>
              <div>
                <dt className="text-zinc-500">Line Count</dt>
                <dd className="font-mono text-zinc-200">{selected.lineCount ?? "—"}</dd>
              </div>
              <div>
                <dt className="text-zinc-500">Last Commit</dt>
                <dd className="font-mono text-zinc-200">{selected.lastCommit ?? "—"}</dd>
              </div>
              <div>
                <dt className="text-zinc-500">License</dt>
                <dd className="text-zinc-200">{selected.license ?? "—"}</dd>
              </div>
              <div className="col-span-2">
                <dt className="text-zinc-500">Team</dt>
                <dd className="text-zinc-200">{selected.team ?? "—"}</dd>
              </div>
            </dl>
          </section>

          <section>
            <div className="mb-2 flex items-center justify-between">
              <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-zinc-500">Dependencies</p>
              <ExampleBadge />
            </div>
            <p className="text-sm text-zinc-300">
              Direct: <span className="font-mono" style={{ color: CYAN }}>{selected.directDeps ?? 0}</span>
              {" · "}
              Transitive: <span className="font-mono text-zinc-200">{selected.transitiveDeps ?? 0}</span>
            </p>
            <button
              type="button"
              className="mt-2 text-xs hover:underline"
              style={{ color: CYAN }}
              onClick={() => setLayout("graph")}
            >
              View dependency graph →
            </button>
          </section>

          <div className="rounded-md border px-3 py-2 text-[10px] text-zinc-500" style={{ borderColor: BORDER }}>
            <Grid3X3 className="mb-1 inline h-3 w-3" style={{ color: CYAN }} /> Layout mode:{" "}
            <span className="uppercase text-zinc-300">{layout}</span> · composition EXAMPLE · not a live probe
          </div>
        </GlassPanel>
      </div>
    </div>
  );
}
