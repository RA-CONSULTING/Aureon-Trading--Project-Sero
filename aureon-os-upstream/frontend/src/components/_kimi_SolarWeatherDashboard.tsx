/**
 * Solar Weather — claim-honest shipped glass (research_solar_space_concept_v1).
 *
 * /research/solar paint: zinc/gold/cyan only; EXAMPLE hard on EVERY numeric;
 * observed vs dark honesty; AGRA aspirational; confidence withheld until probe.
 * No mystic-as-instruments; no paint-green; no fake LIVE.
 * Banner: SHIPPED GLASS · EXAMPLE LAYOUT WHERE MARKED
 */

import { type CSSProperties, type ReactNode } from "react";
import { AlertTriangle, Activity, RefreshCw, Shield, Sun } from "lucide-react";

const GOLD = "#FFB800";
const CYAN = "#00E5FF";
const BG = "#09090b";
const PANEL = "rgba(18, 18, 18, 0.78)";
const BORDER = "#3f3f46";
const ZINC = "#a1a1aa";

/** EXAMPLE meters from concept board — illustrative only; not live probes. */
const EXAMPLE_ACTIVITY = "152";
const EXAMPLE_XRAY = "M 3.7";
const EXAMPLE_PROTON = "1.8";
const EXAMPLE_SOURCE_AGE = "~ 8 MIN";
const EXAMPLE_LAST_RECEIVED = "~ 8 MIN AGO";
const EXAMPLE_LAST_GAP = "~ 23 MIN AGO";
const EXAMPLE_LAST_HOLD = "~ 2 HR 17 MIN AGO";

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

function StatusDot({ tone }: { tone: "cyan" | "gold" | "zinc" }) {
  const color = tone === "cyan" ? CYAN : tone === "gold" ? GOLD : ZINC;
  return (
    <span
      className="inline-block h-2 w-2 shrink-0 rounded-full"
      style={{ background: color, boxShadow: `0 0 6px ${color}` }}
      aria-hidden
    />
  );
}

function SunDisc() {
  return (
    <div
      className="relative mx-auto aspect-square w-full max-w-[280px] overflow-hidden rounded-full"
      style={{
        background: `radial-gradient(circle at 42% 38%, #ffffff 0%, ${GOLD} 32%, #B8860B 64%, #18181b 100%)`,
        border: `2px solid ${GOLD}66`,
        boxShadow: `0 0 40px ${GOLD}33, inset 0 0 40px rgba(0,0,0,0.35)`,
      }}
      aria-hidden
    >
      <div
        className="absolute inset-[12%] rounded-full opacity-70"
        style={{
          background:
            "radial-gradient(circle at 60% 55%, transparent 30%, rgba(0,0,0,0.35) 70%)",
        }}
      />
      <svg viewBox="0 0 200 200" className="absolute inset-0 h-full w-full opacity-80">
        <path
          d="M40 110 C55 70, 80 50, 110 55 S160 90, 170 120"
          fill="none"
          stroke={GOLD}
          strokeWidth="2"
          opacity="0.55"
        />
        <path
          d="M30 90 C60 40, 100 30, 140 55"
          fill="none"
          stroke="#e4e4e7"
          strokeWidth="1.5"
          opacity="0.45"
        />
        <circle cx="118" cy="78" r="14" fill="#27272a" opacity="0.55" />
        <circle cx="72" cy="120" r="9" fill="#27272a" opacity="0.4" />
      </svg>
      <div className="absolute bottom-3 left-0 right-0 text-center">
        <ExampleBadge label="EXAMPLE VISUAL" />
      </div>
    </div>
  );
}

function SegmentBar({ filled = 7, total = 10 }: { filled?: number; total?: number }) {
  return (
    <div className="mt-2 flex gap-1" aria-hidden>
      {Array.from({ length: total }).map((_, i) => (
        <span
          key={i}
          className="h-1.5 flex-1 rounded-sm"
          style={{
            background: i < filled ? GOLD : `${BORDER}`,
            opacity: i < filled ? 0.95 : 0.55,
          }}
        />
      ))}
    </div>
  );
}

export const SolarWeatherDashboard = (_props?: {
  title?: string;
  showHistory?: boolean;
}) => {
  return (
    <div
      className="min-h-full space-y-4 p-4 text-zinc-100"
      style={{ background: BG }}
      data-solar="shipped-glass-v1"
      data-solar-theme="zinc-gold-cyan"
    >
      <div
        className="rounded-md border px-3 py-2"
        style={{ borderColor: `${GOLD}66`, background: `${GOLD}14` }}
      >
        <div className="flex flex-wrap items-center gap-2">
          <p className="text-[11px] font-semibold uppercase tracking-[0.14em]" style={{ color: GOLD }}>
            SHIPPED GLASS · EXAMPLE LAYOUT WHERE MARKED
          </p>
          <ExampleBadge />
          <ExampleBadge label="AGRA ASPIRATIONAL" />
        </div>
        <p
          className="mt-0.5 flex flex-wrap items-center gap-1.5 text-[10px] uppercase tracking-wide"
          style={{ color: `${GOLD}cc` }}
        >
          <AlertTriangle className="h-3 w-3 shrink-0" style={{ color: GOLD }} />
          Numerics & ages are EXAMPLE · confidence withheld until probe · not operational instruments
        </p>
      </div>

      <header
        className="flex flex-wrap items-end justify-between gap-3 border-b pb-3"
        style={{ borderColor: BORDER }}
      >
        <div>
          <div className="flex items-center gap-2">
            <Sun className="h-5 w-5" style={{ color: GOLD }} />
            <h1
              className="text-xl font-semibold uppercase tracking-[0.12em] md:text-2xl"
              style={{ color: GOLD }}
            >
              Solar Weather
            </h1>
          </div>
          <p className="mt-1 text-[11px] uppercase tracking-[0.18em] text-zinc-500">
            Solar Activity Research · Dual Research Strip
          </p>
        </div>
        <div className="text-right text-[10px] uppercase tracking-wide text-zinc-500">
          <p>Claim-honest · EXAMPLE data · research use only</p>
          <p className="mt-0.5">Interpretation separated from fact</p>
        </div>
      </header>

      <GlassPanel className="overflow-hidden">
        <div
          className="flex flex-wrap items-center justify-between gap-2 border-b px-3 py-2.5"
          style={{ borderColor: BORDER, background: `${GOLD}0d` }}
        >
          <div className="flex items-center gap-2">
            <Sun className="h-4 w-4" style={{ color: GOLD }} />
            <div>
              <h2 className="text-[12px] font-semibold uppercase tracking-[0.16em]" style={{ color: GOLD }}>
                Solar Weather
              </h2>
              <p className="text-[10px] uppercase tracking-wide text-zinc-500">Solar activity research</p>
            </div>
          </div>
          <div
            className="inline-flex items-center gap-2 rounded-md border px-2.5 py-1.5 text-[10px] uppercase tracking-wide"
            style={{ borderColor: `${CYAN}55`, color: CYAN, background: `${CYAN}10` }}
          >
            <RefreshCw className="h-3 w-3" />
            <span>Data source age {EXAMPLE_SOURCE_AGE} (SDO/GOES)</span>
            <ExampleBadge label="EXAMPLE AGE" />
          </div>
        </div>

        <div className="grid gap-4 p-4 lg:grid-cols-[minmax(200px,280px)_1fr]">
          <SunDisc />

          <div className="space-y-3">
            <GlassPanel className="p-3" style={{ background: "rgba(0,0,0,0.35)" }}>
              <div className="mb-1 flex items-center justify-between gap-2">
                <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-zinc-400">
                  Solar Activity Index
                </p>
                <ExampleBadge label="EXAMPLE VALUE" />
              </div>
              <p className="font-mono text-4xl font-semibold tracking-tight" style={{ color: GOLD }}>
                {EXAMPLE_ACTIVITY}
              </p>
              <p className="mt-1 text-[11px] uppercase tracking-wide" style={{ color: GOLD }}>
                (Moderate)
              </p>
              <SegmentBar filled={7} total={10} />
              <p className="mt-2 text-[9px] uppercase tracking-wider" style={{ color: `${GOLD}cc` }}>
                Confidence withheld · awaiting probe
              </p>
            </GlassPanel>

            <div className="grid gap-3 sm:grid-cols-2">
              <GlassPanel className="p-3" style={{ background: "rgba(0,0,0,0.35)" }}>
                <div className="mb-1 flex items-center justify-between gap-2">
                  <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-zinc-400">
                    X-Ray Flux (0.1–0.8 nm)
                  </p>
                  <ExampleBadge />
                </div>
                <p className="font-mono text-2xl font-semibold" style={{ color: CYAN }}>
                  {EXAMPLE_XRAY}
                </p>
                <p className="mt-1 text-[10px] uppercase tracking-wide text-zinc-500">
                  Class (M1–M5 range)
                </p>
                <p className="mt-1 text-[9px] uppercase tracking-wider" style={{ color: `${GOLD}cc` }}>
                  Confidence withheld
                </p>
              </GlassPanel>

              <GlassPanel className="p-3" style={{ background: "rgba(0,0,0,0.35)" }}>
                <div className="mb-1 flex items-center justify-between gap-2">
                  <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-zinc-400">
                    Proton Flux (&gt;10 MeV)
                  </p>
                  <ExampleBadge />
                </div>
                <p className="font-mono text-2xl font-semibold" style={{ color: CYAN }}>
                  {EXAMPLE_PROTON}{" "}
                  <span className="text-sm text-zinc-400">pfu</span>
                </p>
                <p className="mt-1 text-[10px] uppercase tracking-wide text-zinc-500">
                  (Below S1 threshold)
                </p>
                <p className="mt-1 text-[9px] uppercase tracking-wider" style={{ color: `${GOLD}cc` }}>
                  Confidence withheld
                </p>
              </GlassPanel>
            </div>
          </div>
        </div>

        <div className="border-t px-4 pb-4 pt-3" style={{ borderColor: BORDER }}>
          <div
            className="rounded-md border px-3 py-3"
            style={{ borderColor: `${GOLD}66`, background: `${GOLD}0f` }}
          >
            <div className="mb-2 flex flex-wrap items-center gap-2">
              <Activity className="h-3.5 w-3.5" style={{ color: GOLD }} />
              <h3 className="text-[11px] font-semibold uppercase tracking-[0.16em]" style={{ color: GOLD }}>
                Interpretation (Example)
              </h3>
              <ExampleBadge label="NOT FACT" />
            </div>
            <p className="text-[12px] leading-relaxed text-zinc-300">
              Moderate solar activity observed. M-class flare risk elevated. Proton levels nominal.
              CME monitoring in progress.
            </p>
            <p className="mt-2 text-[10px] uppercase tracking-wide text-zinc-500">
              Interpretation separated from fact · not a forecast · not a trading signal
            </p>
          </div>
        </div>

        <div
          className="flex flex-wrap items-center gap-x-5 gap-y-2 border-t px-4 py-3 text-[10px] uppercase tracking-wide"
          style={{ borderColor: BORDER, background: "rgba(0,0,0,0.28)" }}
        >
          <span className="inline-flex items-center gap-1.5" style={{ color: CYAN }}>
            <StatusDot tone="cyan" />
            Observed
            <span className="font-mono text-zinc-400">Last received {EXAMPLE_LAST_RECEIVED}</span>
            <ExampleBadge label="EXAMPLE" />
          </span>
          <span className="inline-flex items-center gap-1.5" style={{ color: GOLD }}>
            <StatusDot tone="gold" />
            Dark / Gaps
            <span className="font-mono text-zinc-400">Last gap {EXAMPLE_LAST_GAP}</span>
            <ExampleBadge label="EXAMPLE" />
          </span>
          <span className="inline-flex items-center gap-1.5 text-zinc-400">
            <StatusDot tone="zinc" />
            Hold / Quiet
            <span className="font-mono">Last hold {EXAMPLE_LAST_HOLD}</span>
            <ExampleBadge label="EXAMPLE" />
          </span>
        </div>
        <p className="border-t px-4 py-2 text-[9px] uppercase tracking-wider text-zinc-500" style={{ borderColor: BORDER }}>
          Example · not operational data · uncertainty exists · no paint-green · no fake LIVE
        </p>
      </GlassPanel>

      <footer className="flex flex-wrap items-center justify-between gap-2 pb-2 text-[10px] uppercase tracking-wider text-zinc-500">
        <span className="inline-flex items-center gap-1.5">
          <Shield className="h-3 w-3" style={{ color: GOLD }} />
          Aureon Evidence OS · Research Console · Solar + Space Weather Evidence Workspace
        </span>
        <span>Data age visible · sources identified · interpretation separated from fact</span>
      </footer>
    </div>
  );
};

export default SolarWeatherDashboard;