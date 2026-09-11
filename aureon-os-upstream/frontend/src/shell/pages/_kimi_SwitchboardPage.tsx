/**
 * Switchboard — claim-honest shipped glass (switchboard_concept_v2).
 *
 * Aligns /platform/switchboard to concept board: Feature Toggle Grid
 * (TRADING / RESEARCH / COGNITION / OPS). All organs aspirational while OFF.
 * Hard rules (Buzz): ALL toggles OFF; NO paint-green / no fake LIVE / no ready
 * greens; zinc/gold/cyan glass only; EXAMPLE stamps on filler layout.
 * Banner: SHIPPED GLASS · EXAMPLE LAYOUT WHERE MARKED
 */

import type { CSSProperties, ReactNode } from "react";
import {
  Activity,
  AlertTriangle,
  Brain,
  FlaskConical,
  Lock,
  Microscope,
  Settings,
  Shield,
  TrendingUp,
  UserRound,
  type LucideIcon,
} from "lucide-react";

const GOLD = "#FFB800";
const CYAN = "#00E5FF";
const BG = "#0e0e0e";
const PANEL = "rgba(18, 18, 18, 0.72)";
const PANEL_SOLID = "#121212";
const BORDER = "#3f3f46";
const BORDER_GOLD = "rgba(255, 184, 0, 0.45)";

type ToggleRow = { id: string; label: string; Icon: LucideIcon };

type OrganCard = {
  id: string;
  title: string;
  Icon: LucideIcon;
  rows: ToggleRow[];
};

/** EXAMPLE aspirational organs — all OFF until operator enablement + audit. */
const ORGAN_CARDS: OrganCard[] = [
  {
    id: "trading",
    title: "TRADING",
    Icon: TrendingUp,
    rows: [
      { id: "live-market-execution", label: "Live Market Execution", Icon: Activity },
      { id: "smart-order-routing", label: "Smart Order Routing", Icon: TrendingUp },
      { id: "position-exposure", label: "Position & Exposure Control", Icon: Shield },
      { id: "latency-optimizer", label: "Latency Optimizer", Icon: Activity },
    ],
  },
  {
    id: "research",
    title: "RESEARCH",
    Icon: Microscope,
    rows: [
      { id: "alpha-discovery", label: "Alpha Discovery Pipeline", Icon: FlaskConical },
      { id: "backtest-sim", label: "Backtest & Simulation Engine", Icon: FlaskConical },
      { id: "alt-data", label: "Alternative Data Layer", Icon: Activity },
      { id: "signal-quality", label: "Signal Quality Scoring", Icon: Activity },
    ],
  },
  {
    id: "cognition",
    title: "COGNITION",
    Icon: Brain,
    rows: [
      { id: "reasoning-planning", label: "Reasoning & Planning Module", Icon: Brain },
      { id: "memory-context", label: "Memory & Context Store", Icon: Brain },
      { id: "goal-decomp", label: "Goal Decomposition Engine", Icon: Brain },
      { id: "critic-consistency", label: "Critic & Consistency Layer", Icon: Shield },
    ],
  },
  {
    id: "ops",
    title: "OPS",
    Icon: Settings,
    rows: [
      { id: "workflow-orch", label: "Workflow Orchestration", Icon: Settings },
      { id: "alert-escalation", label: "Alert & Escalation Routing", Icon: AlertTriangle },
      { id: "runbook-remediation", label: "Runbook & Remediation Control", Icon: Settings },
      { id: "resource-quota", label: "Resource & Quota Guard", Icon: Shield },
    ],
  },
];

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
        borderColor: BORDER_GOLD,
        backdropFilter: "blur(12px)",
        WebkitBackdropFilter: "blur(12px)",
        ...style,
      }}
    >
      {children}
    </div>
  );
}

/** Visual OFF toggle — gold outline, nub LEFT. Never paints green / ON. */
function OffToggle({ label }: { label: string }) {
  return (
    <span
      role="switch"
      aria-checked={false}
      aria-label={`${label} — OFF`}
      title="ALL OFF · requires human enablement"
      className="relative inline-flex h-5 w-9 shrink-0 items-center rounded-full"
      style={{
        border: `1px solid ${GOLD}`,
        background: "rgba(0,0,0,0.55)",
        boxShadow: `inset 0 0 0 1px ${GOLD}22`,
      }}
    >
      <span
        className="absolute left-0.5 h-3.5 w-3.5 rounded-full"
        style={{
          background: GOLD,
          boxShadow: `0 0 6px ${GOLD}88`,
        }}
      />
    </span>
  );
}

function OrganToggleCard({ card }: { card: OrganCard }) {
  const TitleIcon = card.Icon;
  return (
    <GlassPanel className="flex flex-col overflow-hidden">
      <div className="flex items-start justify-between gap-3 border-b px-4 py-3" style={{ borderColor: BORDER_GOLD }}>
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <TitleIcon className="h-4 w-4 shrink-0" style={{ color: GOLD }} />
            <h2 className="text-sm font-bold uppercase tracking-[0.14em]" style={{ color: GOLD }}>
              {card.title}
            </h2>
            <ExampleBadge />
          </div>
          <p className="mt-1 text-[10px] uppercase tracking-[0.12em] text-zinc-500">
            Aspirational capability — company-built
          </p>
        </div>
      </div>

      <ul className="flex-1 divide-y px-2 py-1" style={{ borderColor: BORDER }}>
        {card.rows.map((row) => {
          const RowIcon = row.Icon;
          return (
            <li
              key={row.id}
              className="flex items-center gap-3 px-2 py-2.5"
              style={{ borderColor: `${BORDER}99` }}
            >
              <RowIcon className="h-3.5 w-3.5 shrink-0 text-zinc-500" />
              <span className="min-w-0 flex-1 text-[12px] text-zinc-200">{row.label}</span>
              <OffToggle label={row.label} />
            </li>
          );
        })}
      </ul>

      <div
        className="border-t px-4 py-2 text-center text-[10px] font-semibold uppercase tracking-[0.14em]"
        style={{ borderColor: BORDER_GOLD, color: `${GOLD}cc` }}
      >
        ALL OFF · REQUIRES HUMAN ENABLEMENT
      </div>
    </GlassPanel>
  );
}

export default function SwitchboardPage() {
  const totalToggles = ORGAN_CARDS.reduce((n, c) => n + c.rows.length, 0);

  return (
    <div
      className="min-h-full space-y-4 p-4 text-zinc-100"
      style={{ background: BG }}
      data-switchboard="shipped-glass-v2"
      data-switchboard-theme="aureon-dark"
      data-switchboard-claim="all-off"
    >
      {/* Honesty banner — SHIPPED GLASS */}
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
          All organs aspirational while OFF · no paint-green · no fake LIVE · enablement needs operator + audit
        </p>
      </div>

      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="text-2xl font-bold uppercase tracking-[0.12em] text-white">Switchboard</h1>
            <ExampleBadge label="EXAMPLE LAYOUT" />
          </div>
          <p className="mt-1 text-[11px] uppercase tracking-[0.18em]" style={{ color: GOLD }}>
            Control · Evidence · Oversight
          </p>
          <p className="mt-1 text-[12px] text-zinc-400">
            Feature organs default OFF. Layout is EXAMPLE until real enablement probes land.
          </p>
        </div>

        <div className="flex flex-col items-end gap-2">
          <div
            className="inline-flex items-center gap-2 rounded-md border px-3 py-1.5 text-[11px] font-semibold uppercase tracking-wider"
            style={{ borderColor: GOLD, color: GOLD, background: `${GOLD}12` }}
          >
            <Lock className="h-3.5 w-3.5" />
            Operator-only
          </div>
          <p className="text-[10px] uppercase tracking-wide text-zinc-500">
            Human discretion · no paint-green
          </p>
        </div>
      </div>

      {/* Feature Toggle Grid heading */}
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-lg font-bold uppercase tracking-[0.14em] text-white">Feature Toggle Grid</h2>
          <p className="mt-0.5 text-[11px] uppercase tracking-[0.12em]" style={{ color: `${GOLD}cc` }}>
            Aspirational &amp; company-built capabilities — ALL OFF
          </p>
        </div>
        <div className="flex flex-col items-end gap-1">
          <div
            className="inline-flex items-center gap-2 rounded-md border px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wider"
            style={{ borderColor: BORDER_GOLD, color: GOLD, background: PANEL_SOLID }}
          >
            <UserRound className="h-3 w-3" />
            Operator-only access
          </div>
          <span className="font-mono text-[10px]" style={{ color: CYAN }}>
            {totalToggles}/{totalToggles} OFF
          </span>
        </div>
      </div>

      {/* 2×2 organ cards — every toggle OFF */}
      <div className="grid gap-4 md:grid-cols-2">
        {ORGAN_CARDS.map((card) => (
          <OrganToggleCard key={card.id} card={card} />
        ))}
      </div>

      {/* Mid claim strip */}
      <div
        className="flex items-center justify-center gap-3 border-y py-2"
        style={{ borderColor: BORDER_GOLD }}
      >
        <span className="h-px flex-1" style={{ background: BORDER_GOLD }} />
        <p className="text-[10px] font-semibold uppercase tracking-[0.18em]" style={{ color: GOLD }}>
          Human discretion · no paint-green
        </p>
        <span className="h-px flex-1" style={{ background: BORDER_GOLD }} />
      </div>

      {/* Status + risk footer */}
      <div className="grid gap-3 md:grid-cols-2">
        <GlassPanel className="px-4 py-3">
          <div className="flex items-start gap-3">
            <Shield className="mt-0.5 h-4 w-4 shrink-0" style={{ color: GOLD }} />
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-[0.12em]" style={{ color: GOLD }}>
                Status: ALL OFF · no green claims
              </p>
              <p className="mt-1 text-[11px] text-zinc-400">Baseline: toggles default OFF</p>
            </div>
          </div>
        </GlassPanel>

        <GlassPanel className="px-4 py-3">
          <div className="flex items-start gap-3">
            <Shield className="mt-0.5 h-4 w-4 shrink-0" style={{ color: GOLD }} />
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-[0.12em]" style={{ color: GOLD }}>
                Risk footer
              </p>
              <p className="mt-1 text-[11px] text-zinc-400">
                All toggles default OFF. No capability is active. Enablement requires operator action +
                audit trail.
              </p>
            </div>
          </div>
        </GlassPanel>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-2 pb-2 text-[10px] uppercase tracking-wider text-zinc-500">
        <span>SHIPPED GLASS · EXAMPLE LAYOUT WHERE MARKED</span>
        <span>Aureon internal · confidential</span>
      </div>
    </div>
  );
}
