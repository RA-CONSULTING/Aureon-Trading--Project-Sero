/**
 * Harmonic Nexus Research Console — claim-honest shipped glass (research_nexus_v1).
 *
 * /research/nexus paint: zinc/gold/cyan only; EXAMPLE hard on EVERY numeric;
 * observed vs dark honesty; AGRA aspirational; confidence withheld until probe.
 * No mystic-as-instruments; no solfeggio/lighthouse-as-market; no paint-green;
 * no fake LIVE chips. Banner: SHIPPED GLASS · EXAMPLE LAYOUT WHERE MARKED
 */

import { useMemo, useState, type CSSProperties, type ReactNode } from "react";
import {
  AlertTriangle,
  BookOpen,
  FlaskConical,
  Info,
  Landmark,
  Radio,
  Shield,
} from "lucide-react";

const GOLD = "#FFB800";
const CYAN = "#00E5FF";
const BG = "#09090b"; /* zinc-950 */
const PANEL = "rgba(18, 18, 18, 0.78)";
const PANEL_SOLID = "#121212";
const BORDER = "#3f3f46";
const ZINC = "#a1a1aa";

/** EXAMPLE meters — illustrative only; not live probes. Confidence withheld. */
const EXAMPLE_OVERALL = "0.62";
const EXAMPLE_SNR_DB = "8.7";
const EXAMPLE_FRESHNESS = "87";
const EXAMPLE_SOURCE_DIV = "3 / 4";

type ClaimLane = "observed" | "dark" | "hold";

type FeedCard = {
  lane: ClaimLane;
  title: string;
  subtitle: string;
  source: string;
  age: string;
  footerUrl: string;
  footerRef: string;
  chart: "wave-cyan" | "bars-zinc" | "wave-gold";
};

const FEEDS: FeedCard[] = [
  {
    lane: "observed",
    title: "OBSERVED",
    subtitle: "Evidence-linked detections",
    source: "NOAA / SWPC · SOLAR & GEOPHYSICAL FEED",
    age: "12m",
    footerUrl: "swpc.noaa.gov",
    footerRef: "ACE · GOES · DSCOVR",
    chart: "wave-cyan",
  },
  {
    lane: "dark",
    title: "DARK",
    subtitle: "Unconfirmed / low-evidence",
    source: "NASA / ADS · ASTROPHYSICS FEED",
    age: "2h 47m",
    footerUrl: "ui.adsabs.harvard.edu",
    footerRef: "arXiv reference",
    chart: "bars-zinc",
  },
  {
    lane: "hold",
    title: "HOLD",
    subtitle: "Awaiting replication / context",
    source: "NOAA / NCEI · GEOMAGNETIC FEED",
    age: "6h 19m",
    footerUrl: "ncei.noaa.gov",
    footerRef: "INTERMAGNET Kp Index",
    chart: "wave-gold",
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

function laneColor(lane: ClaimLane): string {
  if (lane === "observed") return CYAN;
  if (lane === "hold") return GOLD;
  return ZINC;
}

function MiniWave({ tone }: { tone: "cyan" | "gold" | "zinc" }) {
  const color = tone === "cyan" ? CYAN : tone === "gold" ? GOLD : ZINC;
  const path =
    tone === "zinc"
      ? null
      : tone === "cyan"
        ? "M0 28 C12 22, 18 34, 30 26 S48 12, 60 22 S78 36, 90 24 S108 14, 120 28"
        : "M0 30 L10 18 L20 34 L30 12 L40 28 L50 16 L60 32 L70 10 L80 26 L90 20 L100 34 L110 14 L120 28";
  if (tone === "zinc") {
    const heights = [8, 14, 6, 18, 10, 22, 7, 16, 12, 20, 9, 15, 11, 19, 8, 17];
    return (
      <svg viewBox="0 0 120 40" className="h-16 w-full" aria-hidden>
        {heights.map((h, i) => (
          <rect
            key={i}
            x={i * 7.5 + 2}
            y={40 - h}
            width={5}
            height={h}
            fill={color}
            opacity={0.45 + (i % 3) * 0.1}
          />
        ))}
      </svg>
    );
  }
  return (
    <svg viewBox="0 0 120 40" className="h-16 w-full" aria-hidden>
      <path d={path!} fill="none" stroke={color} strokeWidth="1.6" opacity={0.9} />
      <path
        d={path!}
        fill="none"
        stroke={color}
        strokeWidth="4"
        opacity={0.12}
        transform="translate(0 2)"
      />
    </svg>
  );
}

function FeedColumn({ feed }: { feed: FeedCard }) {
  const color = laneColor(feed.lane);
  const chartTone = feed.chart === "wave-cyan" ? "cyan" : feed.chart === "wave-gold" ? "gold" : "zinc";
  return (
    <GlassPanel className="flex flex-col overflow-hidden">
      <div
        className="flex items-start justify-between gap-2 border-b px-3 py-2.5"
        style={{ borderColor: `${color}33`, background: `${color}0d` }}
      >
        <div>
          <div className="flex items-center gap-2">
            <span className="h-2 w-2 rounded-full" style={{ background: color, boxShadow: `0 0 8px ${color}` }} />
            <h3 className="text-[11px] font-semibold uppercase tracking-[0.14em]" style={{ color }}>
              {feed.title}
            </h3>
          </div>
          <p className="mt-0.5 text-[10px] text-zinc-400">{feed.subtitle}</p>
        </div>
        <ExampleBadge />
      </div>
      <div className="space-y-2 px-3 py-3">
        <p className="text-[10px] uppercase tracking-wide text-zinc-500">{feed.source}</p>
        <div className="flex items-center gap-1.5 text-[10px] text-zinc-400">
          <span>Source age</span>
          <span className="font-mono" style={{ color }}>
            {feed.age}
          </span>
          <ExampleBadge label="EXAMPLE AGE" />
        </div>
        <div
          className="rounded-md border px-2 py-2"
          style={{ borderColor: `${color}28`, background: "rgba(0,0,0,0.35)" }}
        >
          <MiniWave tone={chartTone} />
          <p className="mt-1 text-center text-[9px] uppercase tracking-wider text-zinc-500">
            Illustrative trace · not a live instrument
          </p>
        </div>
        <div className="border-t pt-2 text-[10px] text-zinc-500" style={{ borderColor: BORDER }}>
          <p className="truncate" style={{ color: `${color}cc` }}>
            {feed.footerUrl}
          </p>
          <p className="mt-0.5">{feed.footerRef}</p>
        </div>
      </div>
    </GlassPanel>
  );
}

function MeterCard({
  label,
  value,
  unit,
  detail,
  ring,
}: {
  label: string;
  value: string;
  unit?: string;
  detail: string;
  ring?: number;
}) {
  const r = 28;
  const c = 2 * Math.PI * r;
  const pct = Math.max(0, Math.min(1, ring ?? 0));
  return (
    <GlassPanel className="relative p-3">
      <div className="mb-2 flex items-center justify-between gap-2">
        <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-zinc-400">{label}</p>
        <ExampleBadge />
      </div>
      <div className="flex items-center gap-3">
        {ring !== undefined ? (
          <svg width="72" height="72" viewBox="0 0 72 72" aria-hidden>
            <circle cx="36" cy="36" r={r} fill="none" stroke={BORDER} strokeWidth="5" />
            <circle
              cx="36"
              cy="36"
              r={r}
              fill="none"
              stroke={CYAN}
              strokeWidth="5"
              strokeLinecap="round"
              strokeDasharray={`${c * pct} ${c}`}
              transform="rotate(-90 36 36)"
              opacity={0.95}
            />
          </svg>
        ) : null}
        <div>
          <p className="font-mono text-2xl font-semibold tracking-tight" style={{ color: CYAN }}>
            {value}
            {unit ? <span className="ml-1 text-sm text-zinc-400">{unit}</span> : null}
          </p>
          <p className="mt-0.5 text-[10px] uppercase tracking-wide text-zinc-400">{detail}</p>
          <p className="mt-1 text-[9px] uppercase tracking-wider" style={{ color: `${GOLD}cc` }}>
            Confidence withheld · awaiting probe
          </p>
        </div>
      </div>
    </GlassPanel>
  );
}

export default function NexusLiveDashboard() {
  const [filter, setFilter] = useState<"all" | ClaimLane>("all");

  const visible = useMemo(
    () => (filter === "all" ? FEEDS : FEEDS.filter((f) => f.lane === filter)),
    [filter],
  );

  const filters: Array<{ id: "all" | ClaimLane; label: string; tone: string }> = [
    { id: "observed", label: "OBSERVED", tone: CYAN },
    { id: "dark", label: "DARK", tone: ZINC },
    { id: "hold", label: "HOLD", tone: GOLD },
  ];

  return (
    <div
      className="min-h-full space-y-4 p-4 text-zinc-100"
      style={{ background: BG }}
      data-nexus="shipped-glass-v1"
      data-nexus-theme="zinc-gold-cyan"
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
          <ExampleBadge label="AGRA ASPIRATIONAL" />
        </div>
        <p
          className="mt-0.5 flex flex-wrap items-center gap-1.5 text-[10px] uppercase tracking-wide"
          style={{ color: `${GOLD}cc` }}
        >
          <AlertTriangle className="h-3 w-3 shrink-0" style={{ color: GOLD }} />
          Meters & ages are EXAMPLE · confidence withheld until probe · not trading instruments
        </p>
      </div>

      {/* Header */}
      <header className="flex flex-wrap items-end justify-between gap-3 border-b pb-3" style={{ borderColor: BORDER }}>
        <div>
          <div className="flex items-center gap-2">
            <Radio className="h-5 w-5" style={{ color: GOLD }} />
            <h1
              className="text-xl font-semibold uppercase tracking-[0.12em] md:text-2xl"
              style={{ color: GOLD }}
            >
              Harmonic Nexus Research Console
            </h1>
          </div>
          <p className="mt-1 text-[11px] uppercase tracking-[0.18em] text-zinc-500">
            Coherence · Observation · Evidence
          </p>
        </div>
        <div className="text-right text-[10px] uppercase tracking-wide text-zinc-500">
          <p>Shipped glass · not mystic UI</p>
          <p className="mt-0.5">Research strip · claim-honest feed</p>
        </div>
      </header>

      <div className="grid gap-4 xl:grid-cols-[1fr_280px]">
        <div className="space-y-4">
          {/* Claim-honest feed */}
          <GlassPanel className="p-3">
            <div className="mb-3 flex flex-wrap items-start justify-between gap-2">
              <div>
                <h2 className="text-[12px] font-semibold uppercase tracking-[0.16em]" style={{ color: GOLD }}>
                  Claim-honest feed
                </h2>
                <p className="mt-1 max-w-3xl text-[11px] text-zinc-400">
                  Structured observation. Source-linked. No mystic-as-trading-instruments. No
                  solfeggio / lighthouse as market tools.
                </p>
              </div>
              <ExampleBadge label="ILLUSTRATIVE LAYOUT" />
            </div>

            <div className="mb-3 flex flex-wrap gap-2">
              {filters.map((f) => {
                const selected = filter === f.id;
                return (
                  <button
                    key={f.id}
                    type="button"
                    onClick={() => setFilter(selected ? "all" : f.id)}
                    className="inline-flex items-center gap-2 rounded-full border px-3 py-1 text-[10px] font-semibold uppercase tracking-wider transition"
                    style={{
                      borderColor: selected ? `${f.tone}88` : BORDER,
                      background: selected ? `${f.tone}18` : "rgba(0,0,0,0.25)",
                      color: selected ? f.tone : ZINC,
                    }}
                    aria-pressed={selected}
                  >
                    <span className="h-1.5 w-1.5 rounded-full" style={{ background: f.tone }} />
                    {f.label}
                  </button>
                );
              })}
              {filter !== "all" ? (
                <button
                  type="button"
                  onClick={() => setFilter("all")}
                  className="rounded-full border px-3 py-1 text-[10px] uppercase tracking-wider text-zinc-500"
                  style={{ borderColor: BORDER }}
                >
                  Show all
                </button>
              ) : null}
            </div>

            <div className={`grid gap-3 ${visible.length === 1 ? "md:grid-cols-1" : "md:grid-cols-3"}`}>
              {visible.map((feed) => (
                <FeedColumn key={feed.lane} feed={feed} />
              ))}
            </div>
          </GlassPanel>

          {/* Coherence meters */}
          <div>
            <div className="mb-2 flex flex-wrap items-center gap-2">
              <h2 className="text-[12px] font-semibold uppercase tracking-[0.16em]" style={{ color: GOLD }}>
                Coherence meters
              </h2>
              <ExampleBadge />
              <span className="text-[10px] uppercase tracking-wide text-zinc-500">
                Hard EXAMPLE · AGRA aspirational · confidence withheld
              </span>
            </div>
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
              <MeterCard
                label="Overall coherence"
                value={`${EXAMPLE_OVERALL} / 1.0`}
                detail="Moderate · stable (illustrative)"
                ring={0.62}
              />
              <MeterCard
                label="Signal-to-noise"
                value={EXAMPLE_SNR_DB}
                unit="dB"
                detail="Acceptable (illustrative)"
              />
              <MeterCard
                label="Data freshness"
                value={`${EXAMPLE_FRESHNESS}%`}
                detail="Within window (illustrative)"
              />
              <MeterCard
                label="Source diversity"
                value={EXAMPLE_SOURCE_DIV}
                detail="NOAA · NASA · NCEI · ADS"
              />
            </div>
          </div>
        </div>

        {/* Research notes */}
        <aside className="space-y-3">
          <GlassPanel className="p-3">
            <div className="mb-3 flex items-center gap-2">
              <BookOpen className="h-4 w-4" style={{ color: GOLD }} />
              <h2 className="text-[12px] font-semibold uppercase tracking-[0.16em]" style={{ color: GOLD }}>
                Research notes
              </h2>
            </div>
            <ul className="space-y-3 text-[11px] text-zinc-300">
              <li className="rounded-md border p-2.5" style={{ borderColor: BORDER, background: PANEL_SOLID }}>
                <p className="font-semibold uppercase tracking-wide" style={{ color: GOLD }}>
                  Focus: Harmonic Nexus
                </p>
                <p className="mt-1 text-zinc-400">Investigating phase and resonance as research signals — not market tools.</p>
              </li>
              <li className="rounded-md border p-2.5" style={{ borderColor: BORDER, background: PANEL_SOLID }}>
                <p className="font-semibold uppercase tracking-wide" style={{ color: GOLD }}>
                  Design principle
                </p>
                <p className="mt-1 text-zinc-400">Claim-honest by architecture. Observed vs dark vs hold lanes stay separable.</p>
              </li>
              <li className="rounded-md border p-2.5" style={{ borderColor: BORDER, background: PANEL_SOLID }}>
                <p className="font-semibold uppercase tracking-wide" style={{ color: GOLD }}>
                  Exclusions
                </p>
                <p className="mt-1 text-zinc-400">
                  No solfeggio. No lighthouse-as-market-signal. No sacred-geometry trading logic. Research, not retail
                  metaphysics.
                </p>
              </li>
              <li className="rounded-md border p-2.5" style={{ borderColor: BORDER, background: PANEL_SOLID }}>
                <p className="font-semibold uppercase tracking-wide" style={{ color: GOLD }}>
                  Institutional orientation
                </p>
                <p className="mt-1 text-zinc-400">Built for evidence discipline, not speculation.</p>
              </li>
              <li className="rounded-md border p-2.5" style={{ borderColor: `${GOLD}44`, background: `${GOLD}0d` }}>
                <div className="flex items-center gap-1.5">
                  <FlaskConical className="h-3.5 w-3.5" style={{ color: GOLD }} />
                  <p className="font-semibold uppercase tracking-wide" style={{ color: GOLD }}>
                    AGRA
                  </p>
                  <ExampleBadge label="ASPIRATIONAL" />
                </div>
                <p className="mt-1 text-zinc-400">
                  AGRA scoring is aspirational on this surface. No confidence figure is asserted until a named probe
                  returns evidence.
                </p>
              </li>
            </ul>
          </GlassPanel>

          <GlassPanel className="p-3" style={{ borderColor: `${GOLD}55` }}>
            <div className="flex items-start gap-2">
              <Info className="mt-0.5 h-4 w-4 shrink-0" style={{ color: GOLD }} />
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.14em]" style={{ color: GOLD }}>
                  Research lens
                </p>
                <p className="mt-1 text-[11px] text-zinc-400">
                  These are research signals and EXAMPLE layout chrome — not trading predictions, not biofield proof,
                  not live instrument readouts.
                </p>
              </div>
            </div>
          </GlassPanel>
        </aside>
      </div>

      {/* Risk footer */}
      <footer
        className="flex flex-wrap items-center justify-between gap-3 rounded-md border px-3 py-2.5"
        style={{ borderColor: `${GOLD}44`, background: "rgba(0,0,0,0.35)" }}
      >
        <div className="flex items-center gap-2 text-[10px] uppercase tracking-[0.14em]" style={{ color: GOLD }}>
          <Landmark className="h-3.5 w-3.5" />
          Institutional research console
        </div>
        <div className="flex max-w-2xl items-start gap-2 text-[10px] text-zinc-400">
          <Shield className="mt-0.5 h-3.5 w-3.5 shrink-0" style={{ color: GOLD }} />
          <p>
            <span className="font-semibold uppercase tracking-wide" style={{ color: GOLD }}>
              Risk footer: research, not trading.
            </span>{" "}
            Illustrative numbers carry EXAMPLE stamps. Confidence withheld until probe. No execution path on this
            surface.
          </p>
        </div>
        <p className="text-[9px] uppercase tracking-wide text-zinc-600">
          Aureon Evidence OS · zinc-950 · gold · cyan · shipped glass
        </p>
      </footer>
    </div>
  );
}

export { NexusLiveDashboard as NexusLiveDashboardComplete };
