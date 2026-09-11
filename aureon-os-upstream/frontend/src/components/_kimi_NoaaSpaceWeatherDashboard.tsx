/**
 * Space Weather — claim-honest shipped glass (research_solar_space_concept_v1).
 *
 * /research/space-weather paint: zinc/gold/cyan only; EXAMPLE hard on EVERY
 * numeric and NOAA row; observed vs dark honesty; AGRA aspirational;
 * confidence withheld until probe. No mystic-as-instruments; no paint-green;
 * no fake LIVE. Banner: SHIPPED GLASS · EXAMPLE LAYOUT WHERE MARKED
 */

import { type CSSProperties, type ReactNode } from "react";
import {
  AlertTriangle,
  BarChart3,
  RefreshCw,
  Satellite,
  Shield,
} from "lucide-react";

const GOLD = "#FFB800";
const CYAN = "#00E5FF";
const BG = "#09090b";
const PANEL = "rgba(18, 18, 18, 0.78)";
const BORDER = "#3f3f46";
const ZINC = "#a1a1aa";

type ScaleRow = {
  scale: string;
  current: string;
  threshold: string;
  risk: string;
  riskTone: "gold" | "cyan" | "zinc";
};

/** EXAMPLE NOAA scale rows from concept board — not live probes. */
const EXAMPLE_SCALES: ScaleRow[] = [
  {
    scale: "G1–G5 (GEOMAGNETIC)",
    current: "G2",
    threshold: "Kp ≥ 6",
    risk: "MODERATE",
    riskTone: "gold",
  },
  {
    scale: "S1–S5 (SOLAR RADIATION)",
    current: "S1",
    threshold: "≥ 10 pfu",
    risk: "MINOR",
    riskTone: "gold",
  },
  {
    scale: "R1–R5 (RADIO BLACKOUT)",
    current: "R2",
    threshold: "M1–M5",
    risk: "MODERATE",
    riskTone: "gold",
  },
];

const EXAMPLE_SOURCE_AGE = "~ 5–15 MIN";
const EXAMPLE_MSG_ID = "20250601-ALPHA17";
const EXAMPLE_ISSUE = "01 JUN 2025 14:32 UTC";
const EXAMPLE_SUMMARY =
  "G2 WATCH ISSUED. CME ARRIVAL LIKELY 02 JUN 2025 06:00–12:00 UTC. MODERATE GEOMAGNETIC STORM CONDITIONS POSSIBLE.";
const EXAMPLE_LAST_RECEIVED = "~ 5 MIN AGO";
const EXAMPLE_LAST_GAP = "~ 18 MIN AGO";
const EXAMPLE_LAST_HOLD = "~ 1 HR 45 MIN AGO";

/** Illustrative Kp path — not a live instrument. */
const KP_POINTS = [
  { x: 0, y: 42 },
  { x: 18, y: 55 },
  { x: 36, y: 38 },
  { x: 54, y: 62 },
  { x: 72, y: 48 },
  { x: 90, y: 70 },
  { x: 108, y: 58 },
  { x: 126, y: 74 },
  { x: 144, y: 52 },
  { x: 162, y: 66 },
  { x: 180, y: 44 },
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

function KpChart() {
  const path = KP_POINTS.map((p, i) => `${i === 0 ? "M" : "L"}${p.x} ${100 - p.y}`).join(" ");
  return (
    <div
      className="rounded-md border p-2"
      style={{ borderColor: `${CYAN}33`, background: "rgba(0,0,0,0.4)" }}
    >
      <div className="mb-1 flex items-center justify-between gap-2">
        <p className="text-[10px] font-semibold uppercase tracking-[0.14em]" style={{ color: CYAN }}>
          Geomagnetic Kp Index (Est.)
        </p>
        <ExampleBadge label="EXAMPLE CHART" />
      </div>
      <svg viewBox="0 0 180 110" className="h-36 w-full" aria-hidden>
        {[30, 60, 90].map((y) => (
          <line
            key={y}
            x1="20"
            x2="180"
            y1={100 - y}
            y2={100 - y}
            stroke={BORDER}
            strokeDasharray="3 3"
            opacity="0.8"
          />
        ))}
        <text x="4" y={100 - 30} fill={ZINC} fontSize="8">
          3
        </text>
        <text x="4" y={100 - 60} fill={ZINC} fontSize="8">
          6
        </text>
        <text x="4" y={100 - 90} fill={ZINC} fontSize="8">
          9
        </text>
        <path d={path} fill="none" stroke={CYAN} strokeWidth="1.8" opacity="0.95" />
        <path
          d={path}
          fill="none"
          stroke={CYAN}
          strokeWidth="5"
          opacity="0.12"
          transform="translate(0 2)"
        />
        <text x="20" y="108" fill={ZINC} fontSize="8">
          NOW
        </text>
        <text x="85" y="108" fill={ZINC} fontSize="8">
          +12H
        </text>
        <text x="150" y="108" fill={ZINC} fontSize="8">
          +24H
        </text>
      </svg>
      <p className="mt-1 text-center text-[9px] uppercase tracking-wider text-zinc-500">
        Illustrative trace · not a live instrument · confidence withheld
      </p>
    </div>
  );
}

export const NoaaSpaceWeatherDashboard = () => {
  return (
    <div
      className="min-h-full space-y-4 p-4 text-zinc-100"
      style={{ background: BG }}
      data-space-weather="shipped-glass-v1"
      data-space-theme="zinc-gold-cyan"
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
          NOAA rows & ages are EXAMPLE · confidence withheld until probe · not operational instruments
        </p>
      </div>

      <header
        className="flex flex-wrap items-end justify-between gap-3 border-b pb-3"
        style={{ borderColor: BORDER }}
      >
        <div>
          <div className="flex items-center gap-2">
            <Satellite className="h-5 w-5" style={{ color: CYAN }} />
            <h1
              className="text-xl font-semibold uppercase tracking-[0.12em] md:text-2xl"
              style={{ color: GOLD }}
            >
              Space Weather
            </h1>
          </div>
          <p className="mt-1 text-[11px] uppercase tracking-[0.18em] text-zinc-500">
            NOAA Feed Research View · Dual Research Strip
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
          style={{ borderColor: BORDER, background: `${CYAN}0d` }}
        >
          <div className="flex items-center gap-2">
            <Satellite className="h-4 w-4" style={{ color: CYAN }} />
            <div>
              <h2 className="text-[12px] font-semibold uppercase tracking-[0.16em]" style={{ color: CYAN }}>
                Space Weather
              </h2>
              <p className="text-[10px] uppercase tracking-wide text-zinc-500">NOAA feed research view</p>
            </div>
          </div>
          <div
            className="inline-flex items-center gap-2 rounded-md border px-2.5 py-1.5 text-[10px] uppercase tracking-wide"
            style={{ borderColor: `${CYAN}55`, color: CYAN, background: `${CYAN}10` }}
          >
            <RefreshCw className="h-3 w-3" />
            <span>Data source age {EXAMPLE_SOURCE_AGE} (NOAA/SWPC)</span>
            <ExampleBadge label="EXAMPLE AGE" />
          </div>
        </div>

        <div className="space-y-4 p-4">
          {/* NOAA scales table */}
          <div>
            <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
              <h3 className="text-[11px] font-semibold uppercase tracking-[0.16em]" style={{ color: GOLD }}>
                NOAA Space Weather Scales
              </h3>
              <ExampleBadge label="EXAMPLE TABLE" />
            </div>
            <div className="overflow-x-auto rounded-md border" style={{ borderColor: BORDER }}>
              <table className="w-full min-w-[560px] border-collapse text-left text-[11px]">
                <thead>
                  <tr style={{ background: "rgba(0,0,0,0.45)" }}>
                    {["Scale", "Current", "Threshold", "Risk / Condition"].map((h) => (
                      <th
                        key={h}
                        className="border-b px-3 py-2 font-semibold uppercase tracking-wider text-zinc-400"
                        style={{ borderColor: BORDER }}
                      >
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {EXAMPLE_SCALES.map((row) => (
                    <tr key={row.scale} className="border-b" style={{ borderColor: BORDER }}>
                      <td className="px-3 py-2.5 text-zinc-300">
                        <span className="inline-flex flex-wrap items-center gap-1.5">
                          {row.scale}
                          <ExampleBadge />
                        </span>
                      </td>
                      <td className="px-3 py-2.5">
                        <span className="inline-flex items-center gap-1.5 font-mono font-semibold" style={{ color: GOLD }}>
                          {row.current}
                          <ExampleBadge label="EXAMPLE" />
                        </span>
                      </td>
                      <td className="px-3 py-2.5 font-mono text-zinc-400">{row.threshold}</td>
                      <td className="px-3 py-2.5">
                        <span
                          className="inline-flex items-center gap-1.5 font-semibold uppercase tracking-wide"
                          style={{ color: row.riskTone === "gold" ? GOLD : row.riskTone === "cyan" ? CYAN : ZINC }}
                        >
                          {row.risk}
                          <ExampleBadge />
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="mt-1.5 text-[9px] uppercase tracking-wider" style={{ color: `${GOLD}cc` }}>
              Confidence withheld until probe · EXAMPLE layout · not a live NOAA gate
            </p>
          </div>

          {/* NOAA / SWPC feed */}
          <GlassPanel className="overflow-hidden" style={{ background: "rgba(0,0,0,0.28)" }}>
            <div
              className="flex flex-wrap items-center gap-2 border-b px-3 py-2"
              style={{ borderColor: BORDER }}
            >
              <BarChart3 className="h-3.5 w-3.5" style={{ color: CYAN }} />
              <h3 className="text-[11px] font-semibold uppercase tracking-[0.14em]" style={{ color: CYAN }}>
                NOAA / SWPC Feed · Space Weather Message
              </h3>
              <ExampleBadge label="EXAMPLE MESSAGE" />
            </div>
            <div className="grid gap-4 p-3 lg:grid-cols-2">
              <div className="space-y-2 text-[11px]">
                <div className="flex flex-wrap items-baseline gap-2">
                  <span className="uppercase tracking-wide text-zinc-500">Message ID</span>
                  <span className="font-mono" style={{ color: CYAN }}>
                    {EXAMPLE_MSG_ID}
                  </span>
                  <ExampleBadge />
                </div>
                <div className="flex flex-wrap items-baseline gap-2">
                  <span className="uppercase tracking-wide text-zinc-500">Issue Time</span>
                  <span className="font-mono text-zinc-200">{EXAMPLE_ISSUE}</span>
                  <ExampleBadge />
                </div>
                <div className="flex flex-wrap items-baseline gap-2">
                  <span className="uppercase tracking-wide text-zinc-500">Type</span>
                  <span className="font-semibold uppercase tracking-wide" style={{ color: GOLD }}>
                    WATCH
                  </span>
                  <ExampleBadge />
                </div>
                <div
                  className="rounded-md border px-2.5 py-2"
                  style={{ borderColor: `${GOLD}44`, background: `${GOLD}0a` }}
                >
                  <p className="mb-1 text-[10px] font-semibold uppercase tracking-[0.14em]" style={{ color: GOLD }}>
                    Summary (Example)
                  </p>
                  <p className="text-[11px] leading-relaxed text-zinc-300">{EXAMPLE_SUMMARY}</p>
                  <p className="mt-2 text-[9px] uppercase tracking-wider text-zinc-500">
                    Interpretation separated from fact · not operational
                  </p>
                </div>
              </div>
              <KpChart />
            </div>
          </GlassPanel>
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
          <span className="inline-flex items-center gap-1.5" style={{ color: CYAN }}>
            <StatusDot tone="cyan" />
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

export default NoaaSpaceWeatherDashboard;