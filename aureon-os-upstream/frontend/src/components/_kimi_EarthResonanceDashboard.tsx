/**
 * Earth Resonance — claim-honest shipped glass (research_earth_concept_v2).
 *
 * /research/earth paint: zinc/gold/cyan only; EXAMPLE hard on EVERY numeric;
 * Schumann Hz EXAMPLE (never verified fact); AGRA aspirational;
 * confidence withheld until probe. No mystic-as-instruments; no paint-green;
 * observed vs dark honesty; no leftover concept banner.
 * Banner: SHIPPED GLASS · EXAMPLE LAYOUT WHERE MARKED
 */

import { type CSSProperties, type ReactNode } from "react";
import {
  Activity,
  AlertTriangle,
  Crosshair,
  Globe2,
  Info,
  Radio,
  Shield,
} from "lucide-react";

const GOLD = "#FFB800";
const CYAN = "#00E5FF";
const BG = "#09090b";
const PANEL = "rgba(18, 18, 18, 0.78)";
const BORDER = "#3f3f46";
const ZINC = "#a1a1aa";
const AMBER = "#F59E0B";

/** EXAMPLE-only numerics from research_earth board — illustrative; not live probes. */
const EXAMPLE_BAND_CENTER = "7.83";
const EXAMPLE_LAST_MOVEMENT = "00:17:42 UTC";
const EXAMPLE_COHERENCE = "0.62";
const EXAMPLE_PHASE = "0.58";
const EXAMPLE_ENTRAINMENT = "0.55";
const EXAMPLE_CHECKSUM =
  "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855";
const EXAMPLE_SENSOR_NODES = "32";
const EXAMPLE_LAST_CAL = "2025-05-17 12:00 UTC";

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

function StatusPill({
  label,
  tone,
}: {
  label: string;
  tone: "cyan" | "zinc" | "amber";
}) {
  const color = tone === "cyan" ? CYAN : tone === "amber" ? AMBER : ZINC;
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider"
      style={{ color, border: `1px solid ${color}66`, background: `${color}14` }}
    >
      <span
        className="inline-block h-1.5 w-1.5 rounded-full"
        style={{ background: color, boxShadow: `0 0 6px ${color}` }}
        aria-hidden
      />
      {label}
    </span>
  );
}

function PanelHeader({
  title,
  icon,
  badge,
}: {
  title: string;
  icon: ReactNode;
  badge?: string;
}) {
  return (
    <div
      className="flex flex-wrap items-center justify-between gap-2 border-b px-3 py-2.5"
      style={{ borderColor: BORDER, background: `${CYAN}0d` }}
    >
      <div className="flex items-center gap-2">
        {icon}
        <h2
          className="text-[11px] font-semibold uppercase tracking-[0.14em]"
          style={{ color: GOLD }}
        >
          {title}
        </h2>
      </div>
      {badge ? <ExampleBadge label={badge} /> : <ExampleBadge />}
    </div>
  );
}

/** Dotted low-res world map with four EXAMPLE crosshair nodes. */
function WorldMapExample() {
  const nodes = [
    { cx: 52, cy: 58, label: "NA" },
    { cx: 78, cy: 108, label: "SA" },
    { cx: 148, cy: 52, label: "EU/AF" },
    { cx: 230, cy: 78, label: "EA/AU" },
  ];
  return (
    <div
      className="relative overflow-hidden rounded-md border"
      style={{ borderColor: `${GOLD}44`, background: "rgba(0,0,0,0.45)" }}
    >
      <svg viewBox="0 0 280 150" className="h-36 w-full" aria-hidden>
        {/* dotted landmass silhouettes — illustrative only */}
        {[
          // N America
          "M28 42 C40 28, 70 22, 88 38 C98 48, 92 70, 78 78 C60 88, 42 72, 28 42 Z",
          // S America
          "M72 88 C82 92, 88 110, 84 128 C78 138, 68 132, 64 118 C60 100, 66 90, 72 88 Z",
          // Europe / Africa
          "M130 34 C148 28, 160 36, 158 48 C170 52, 168 78, 160 100 C152 122, 142 118, 138 98 C132 78, 128 52, 130 34 Z",
          // Asia / Australia hint
          "M176 36 C210 24, 240 40, 248 58 C252 72, 236 78, 220 70 C200 62, 188 52, 176 36 Z",
          "M220 96 C236 92, 248 104, 242 116 C232 124, 218 116, 220 96 Z",
        ].map((d, i) => (
          <path
            key={i}
            d={d}
            fill="none"
            stroke={GOLD}
            strokeWidth="1.2"
            strokeDasharray="1.5 2.5"
            opacity="0.75"
          />
        ))}
        {/* latitude / longitude grid */}
        {[30, 60, 90, 120].map((y) => (
          <line
            key={`h${y}`}
            x1="8"
            x2="272"
            y1={y}
            y2={y}
            stroke={BORDER}
            strokeDasharray="2 4"
            opacity="0.55"
          />
        ))}
        {[40, 80, 120, 160, 200, 240].map((x) => (
          <line
            key={`v${x}`}
            x1={x}
            x2={x}
            y1="12"
            y2="138"
            stroke={BORDER}
            strokeDasharray="2 4"
            opacity="0.45"
          />
        ))}
        {nodes.map((n) => (
          <g key={n.label}>
            <circle cx={n.cx} cy={n.cy} r="7" fill="none" stroke={CYAN} strokeWidth="1.4" />
            <line
              x1={n.cx - 11}
              x2={n.cx + 11}
              y1={n.cy}
              y2={n.cy}
              stroke={CYAN}
              strokeWidth="1"
            />
            <line
              x1={n.cx}
              x2={n.cx}
              y1={n.cy - 11}
              y2={n.cy + 11}
              stroke={CYAN}
              strokeWidth="1"
            />
            <circle cx={n.cx} cy={n.cy} r="1.6" fill={CYAN} />
          </g>
        ))}
      </svg>
      <div className="absolute bottom-1.5 right-1.5">
        <ExampleBadge label="EXAMPLE MAP" />
      </div>
    </div>
  );
}

function WaveformStrip() {
  const pts = [
    8, 22, 14, 30, 18, 36, 12, 28, 20, 34, 10, 26, 16, 32, 14, 38, 18, 28, 12, 24,
  ];
  const d = pts
    .map((y, i) => `${i === 0 ? "M" : "L"}${8 + i * 14} ${40 - y * 0.7}`)
    .join(" ");
  return (
    <div
      className="mt-2 rounded-md border px-2 py-1"
      style={{ borderColor: `${CYAN}33`, background: "rgba(0,0,0,0.35)" }}
    >
      <svg viewBox="0 0 290 44" className="h-10 w-full" aria-hidden>
        <path d={d} fill="none" stroke={CYAN} strokeWidth="1.6" opacity="0.95" />
        <path
          d={d}
          fill="none"
          stroke={CYAN}
          strokeWidth="4"
          opacity="0.12"
          transform="translate(0 1)"
        />
      </svg>
    </div>
  );
}

/** Schumann band chart — EXAMPLE peak at 7.83 Hz, not a live read. */
function SchumannBandChart() {
  // Illustrative log-ish amplitude curve peaking near 7.83 Hz
  const curve = [
    { x: 20, y: 78 },
    { x: 40, y: 70 },
    { x: 55, y: 42 }, // ~7.83 peak
    { x: 70, y: 68 },
    { x: 95, y: 58 },
    { x: 115, y: 72 },
    { x: 140, y: 64 },
    { x: 165, y: 76 },
    { x: 190, y: 70 },
    { x: 215, y: 80 },
    { x: 240, y: 74 },
  ];
  const path = curve.map((p, i) => `${i === 0 ? "M" : "L"}${p.x} ${p.y}`).join(" ");
  return (
    <div
      className="rounded-md border p-2"
      style={{ borderColor: `${CYAN}33`, background: "rgba(0,0,0,0.4)" }}
    >
      <div className="mb-1 flex items-center justify-between gap-2">
        <p className="text-[10px] font-semibold uppercase tracking-[0.14em]" style={{ color: CYAN }}>
          Amplitude (nT/√Hz) · Frequency (Hz)
        </p>
        <ExampleBadge label="EXAMPLE" />
      </div>
      <svg viewBox="0 0 260 110" className="h-40 w-full" aria-hidden>
        {/* log-ish grid */}
        {[28, 48, 68, 88].map((y) => (
          <line
            key={y}
            x1="28"
            x2="250"
            y1={y}
            y2={y}
            stroke={BORDER}
            strokeDasharray="3 3"
            opacity="0.75"
          />
        ))}
        <text x="2" y="30" fill={ZINC} fontSize="7">
          10⁻³
        </text>
        <text x="2" y="50" fill={ZINC} fontSize="7">
          10⁻⁴
        </text>
        <text x="2" y="70" fill={ZINC} fontSize="7">
          10⁻⁵
        </text>
        {/* peak marker at ~7.83 */}
        <line
          x1="55"
          x2="55"
          y1="18"
          y2="92"
          stroke={GOLD}
          strokeDasharray="3 3"
          strokeWidth="1.2"
          opacity="0.9"
        />
        <text x="42" y="14" fill={GOLD} fontSize="8" fontWeight="600">
          7.83 Hz
        </text>
        <text x="48" y="24" fill={GOLD} fontSize="6">
          (EXAMPLE)
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
        <text x="28" y="104" fill={ZINC} fontSize="8">
          5
        </text>
        <text x="95" y="104" fill={ZINC} fontSize="8">
          15
        </text>
        <text x="160" y="104" fill={ZINC} fontSize="8">
          25
        </text>
        <text x="230" y="104" fill={ZINC} fontSize="8">
          30
        </text>
      </svg>
      <p className="mt-1 text-center text-[9px] uppercase tracking-wider text-zinc-500">
        Not a live read · example band only until instrumented feed is established
      </p>
    </div>
  );
}

function CoherenceMeter({
  label,
  value,
  fill,
}: {
  label: string;
  value: string;
  fill: number;
}) {
  return (
    <div
      className="rounded-md border px-3 py-2.5"
      style={{ borderColor: BORDER, background: "rgba(0,0,0,0.35)" }}
    >
      <div className="flex items-center justify-between gap-2">
        <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-zinc-400">
          {label}
        </p>
        <ExampleBadge />
      </div>
      <p className="mt-1 font-mono text-2xl font-semibold" style={{ color: CYAN }}>
        {value}
      </p>
      <div
        className="mt-2 h-1.5 w-full overflow-hidden rounded-full"
        style={{ background: `${BORDER}` }}
      >
        <div
          className="h-full rounded-full"
          style={{
            width: `${Math.max(0, Math.min(100, fill))}%`,
            background: `linear-gradient(90deg, ${CYAN}88, ${CYAN})`,
          }}
        />
      </div>
    </div>
  );
}

export const EarthResonanceDashboard = () => {
  return (
    <div
      className="min-h-full space-y-4 p-4 text-zinc-100"
      style={{ background: BG }}
      data-earth-resonance="shipped-glass-v2"
      data-earth-theme="zinc-gold-cyan"
    >
      {/* Honesty banner — SHIPPED GLASS */}
      <div
        className="rounded-md border px-3 py-2"
        style={{ borderColor: `${GOLD}66`, background: `${GOLD}14` }}
      >
        <div className="flex flex-wrap items-center gap-2">
          <p
            className="text-[11px] font-semibold uppercase tracking-[0.14em]"
            style={{ color: GOLD }}
          >
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
          Schumann Hz & AGRA are EXAMPLE · confidence withheld until probe · not
          operational instruments
        </p>
      </div>

      <header
        className="flex flex-wrap items-end justify-between gap-3 border-b pb-3"
        style={{ borderColor: BORDER }}
      >
        <div>
          <div className="flex items-center gap-2">
            <Activity className="h-5 w-5" style={{ color: CYAN }} />
            <h1
              className="text-xl font-semibold uppercase tracking-[0.12em] md:text-2xl"
              style={{ color: GOLD }}
            >
              Earth Resonance Research
            </h1>
          </div>
          <p className="mt-1 max-w-2xl text-[11px] uppercase tracking-[0.14em] text-zinc-500">
            Observing planetary electromagnetic resonance phenomena through disciplined
            instrumentation and evidence-led inquiry.
          </p>
        </div>
        <div className="text-right text-[10px] uppercase tracking-wide text-zinc-500">
          <p>Claim-honest · EXAMPLE data · research use only</p>
          <p className="mt-0.5">Confidence withheld until probe-instrumented feed</p>
        </div>
      </header>

      {/* Top row: Overview + Schumann band */}
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <GlassPanel className="overflow-hidden">
          <PanelHeader
            title="Resonance Overview"
            icon={<Globe2 className="h-4 w-4" style={{ color: CYAN }} />}
            badge="EXAMPLE LAYOUT"
          />
          <div className="space-y-3 p-3">
            <WorldMapExample />
            <WaveformStrip />
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-[10px] uppercase tracking-wider text-zinc-500">Status</span>
              <StatusPill label="Observed" tone="cyan" />
              <StatusPill label="Dark" tone="zinc" />
              <StatusPill label="Hold" tone="amber" />
            </div>
            <div className="flex flex-wrap items-center gap-2 text-[11px]">
              <span className="uppercase tracking-wider text-zinc-500">Last movement</span>
              <span className="font-mono" style={{ color: CYAN }}>
                {EXAMPLE_LAST_MOVEMENT}
              </span>
              <ExampleBadge />
            </div>
            <p className="text-[10px] leading-relaxed text-zinc-500">
              All values and states are EXAMPLE-tagged until probe instrumentation confirms
              live feed. Observed / Dark / Hold are honesty labels for example datasets —
              not verified instrument states.
            </p>
          </div>
        </GlassPanel>

        <GlassPanel className="overflow-hidden">
          <PanelHeader
            title="Schumann Resonance Band"
            icon={<Radio className="h-4 w-4" style={{ color: CYAN }} />}
            badge="EXAMPLE"
          />
          <div className="space-y-3 p-3">
            <SchumannBandChart />
            <div
              className="flex flex-wrap items-center gap-x-4 gap-y-2 rounded-md border px-3 py-2 text-[11px]"
              style={{ borderColor: BORDER, background: "rgba(0,0,0,0.3)" }}
            >
              <div className="flex items-center gap-1.5">
                <span className="uppercase tracking-wider text-zinc-500">
                  Nominal band center
                </span>
                <span className="font-mono font-semibold" style={{ color: GOLD }}>
                  {EXAMPLE_BAND_CENTER} Hz
                </span>
                <ExampleBadge />
              </div>
              <div className="flex items-center gap-1.5">
                <span className="uppercase tracking-wider text-zinc-500">
                  Amplitude (peak)
                </span>
                <span className="font-mono text-zinc-400">— nT/√Hz</span>
                <ExampleBadge label="WITHHELD" />
              </div>
            </div>
            <p className="text-[10px] leading-relaxed text-zinc-500">
              Schumann Hz values are EXAMPLE hard — never presented as verified facts. Not a
              live read. Example band only until instrumented feed is established.
            </p>
          </div>
        </GlassPanel>
      </div>

      {/* Middle row: Coherence + Data integrity */}
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <GlassPanel className="overflow-hidden">
          <PanelHeader
            title="Coherence & Phase Summary"
            icon={<Activity className="h-4 w-4" style={{ color: CYAN }} />}
            badge="EXAMPLE"
          />
          <div className="space-y-2.5 p-3">
            <CoherenceMeter
              label="Global Coherence"
              value={EXAMPLE_COHERENCE}
              fill={62}
            />
            <CoherenceMeter label="Phase Stability" value={EXAMPLE_PHASE} fill={58} />
            <CoherenceMeter
              label="Field Entrainment"
              value={EXAMPLE_ENTRAINMENT}
              fill={55}
            />
            <p className="text-[10px] leading-relaxed text-zinc-500">
              Coherence numbers are EXAMPLE-tagged and illustrative only. Not derived from
              confirmed live instrumentation. Confidence withheld until probe.
            </p>
          </div>
        </GlassPanel>

        <GlassPanel className="overflow-hidden">
          <PanelHeader
            title="Data Integrity"
            icon={<Shield className="h-4 w-4" style={{ color: CYAN }} />}
            badge="EXAMPLE / UNCONFIRMED"
          />
          <div className="space-y-3 p-3">
            <div
              className="rounded-md border px-3 py-2.5"
              style={{ borderColor: BORDER, background: "rgba(0,0,0,0.35)" }}
            >
              <p className="text-[10px] uppercase tracking-wider text-zinc-500">Data origin</p>
              <div className="mt-1 flex flex-wrap items-center gap-2">
                <p className="text-sm font-medium" style={{ color: GOLD }}>
                  EXAMPLE DATASET / SIMULATED FEED
                </p>
                <ExampleBadge label="EXAMPLE / UNCONFIRMED" />
              </div>
            </div>
            <div
              className="rounded-md border px-3 py-2.5"
              style={{ borderColor: BORDER, background: "rgba(0,0,0,0.35)" }}
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="text-[10px] uppercase tracking-wider text-zinc-500">
                  Checksum (SHA-256)
                </p>
                <ExampleBadge />
              </div>
              <p className="mt-1 break-all font-mono text-[11px] text-zinc-300">
                {EXAMPLE_CHECKSUM}
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <ExampleBadge label="EXAMPLE / UNCONFIRMED" />
              <ExampleBadge label="NOT VERIFIED LIVE" />
            </div>
            <p className="text-[10px] leading-relaxed text-zinc-500">
              Checksum and origin are EXAMPLE-tagged. Not a verified live data run. No
              “Verified” claim is asserted as real.
            </p>
          </div>
        </GlassPanel>
      </div>

      {/* Bottom row: AGRA + Research status */}
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <GlassPanel className="overflow-hidden">
          <PanelHeader
            title="Instrumentation Context"
            icon={<Crosshair className="h-4 w-4" style={{ color: CYAN }} />}
            badge="ASPIRATIONAL / EXAMPLE"
          />
          <div className="space-y-3 p-3">
            <div>
              <p className="text-sm font-semibold uppercase tracking-[0.1em]" style={{ color: GOLD }}>
                Aureon Global Research Array (AGRA)
              </p>
              <p className="mt-0.5 text-[10px] uppercase tracking-wider text-zinc-500">
                Example configuration · aspirational / EXAMPLE
              </p>
            </div>
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
              <div
                className="rounded-md border px-3 py-2"
                style={{ borderColor: BORDER, background: "rgba(0,0,0,0.35)" }}
              >
                <p className="text-[9px] uppercase tracking-wider text-zinc-500">
                  Sensor nodes (example)
                </p>
                <div className="mt-1 flex items-baseline gap-1.5">
                  <span className="font-mono text-xl font-semibold" style={{ color: CYAN }}>
                    {EXAMPLE_SENSOR_NODES}
                  </span>
                  <ExampleBadge label="ASPIRATIONAL" />
                </div>
              </div>
              <div
                className="rounded-md border px-3 py-2"
                style={{ borderColor: BORDER, background: "rgba(0,0,0,0.35)" }}
              >
                <p className="text-[9px] uppercase tracking-wider text-zinc-500">
                  Calibration state
                </p>
                <div className="mt-1 flex flex-wrap items-center gap-1.5">
                  <span className="text-sm font-medium text-zinc-300">EXAMPLE CALIBRATED</span>
                  <ExampleBadge />
                </div>
              </div>
              <div
                className="rounded-md border px-3 py-2"
                style={{ borderColor: BORDER, background: "rgba(0,0,0,0.35)" }}
              >
                <p className="text-[9px] uppercase tracking-wider text-zinc-500">
                  Last calibration
                </p>
                <div className="mt-1 flex flex-wrap items-center gap-1.5">
                  <span className="font-mono text-[12px] text-zinc-300">{EXAMPLE_LAST_CAL}</span>
                  <ExampleBadge />
                </div>
              </div>
            </div>
            <div
              className="flex items-start gap-2 rounded-md border px-3 py-2"
              style={{ borderColor: `${GOLD}55`, background: `${GOLD}10` }}
            >
              <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" style={{ color: GOLD }} />
              <p className="text-[10px] leading-relaxed" style={{ color: `${GOLD}dd` }}>
                Company-built aspiration only. Not a claim of current deployment or
                operational calibration. AGRA remains ASPIRATIONAL.
              </p>
            </div>
          </div>
        </GlassPanel>

        <GlassPanel className="overflow-hidden">
          <PanelHeader
            title="Research Status"
            icon={<Shield className="h-4 w-4" style={{ color: CYAN }} />}
            badge="HONESTY LABELS"
          />
          <div className="space-y-3 p-3">
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
              <div
                className="rounded-md border px-3 py-2.5"
                style={{ borderColor: `${CYAN}55`, background: `${CYAN}0d` }}
              >
                <StatusPill label="Observed" tone="cyan" />
                <p className="mt-2 text-[10px] leading-relaxed text-zinc-400">
                  Signal patterns present in example datasets
                </p>
              </div>
              <div
                className="rounded-md border px-3 py-2.5"
                style={{ borderColor: `${ZINC}55`, background: "rgba(0,0,0,0.35)" }}
              >
                <StatusPill label="Dark" tone="zinc" />
                <p className="mt-2 text-[10px] leading-relaxed text-zinc-400">
                  Regions or bands below detection or unresolved
                </p>
              </div>
              <div
                className="rounded-md border px-3 py-2.5"
                style={{ borderColor: `${AMBER}55`, background: `${AMBER}0d` }}
              >
                <StatusPill label="Hold" tone="amber" />
                <p className="mt-2 text-[10px] leading-relaxed text-zinc-400">
                  Interpretation suspended pending probe confirmation
                </p>
              </div>
            </div>
            <div
              className="flex flex-wrap items-center gap-x-4 gap-y-1 rounded-md border px-3 py-2 text-[10px] uppercase tracking-wider"
              style={{ borderColor: BORDER, background: "rgba(0,0,0,0.3)" }}
            >
              <span className="text-zinc-500">
                Research mode:{" "}
                <span className="text-zinc-300">Institutional linear</span>
              </span>
              <span className="text-zinc-500">
                Confidence:{" "}
                <span style={{ color: GOLD }}>Withheld until probe-instrumented feed</span>
              </span>
            </div>
          </div>
        </GlassPanel>
      </div>

      <footer
        className="flex flex-wrap items-center justify-between gap-2 border-t pt-3 text-[10px] uppercase tracking-[0.12em] text-zinc-500"
        style={{ borderColor: BORDER }}
      >
        <span>Aureon Evidence OS — Institutional Linear Research Console</span>
        <span>
          Source ages (if present): EXAMPLE-tagged · Research — not trading or commercial
          feed · SHIPPED GLASS · EXAMPLE LAYOUT WHERE MARKED
        </span>
      </footer>
    </div>
  );
};

export default EarthResonanceDashboard;
