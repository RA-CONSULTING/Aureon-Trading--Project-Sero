/**
 * HFT Desk — claim-honest shipped glass (hft_desk_concept_v1).
 *
 * Aligns /trading/hft to claim-passed concept board.
 * Hard rules (Buzz): EXECUTION HOLD visible; empty blotter honest;
 * stages HELD after intel; UI RTT/SLO as —; no fake percentiles /
 * invented e2e; EXAMPLE stamps on illustrative numbers; zinc/gold/cyan
 * only; no mystic trading instruments; no false READY.
 * Banner: SHIPPED GLASS · EXAMPLE LAYOUT WHERE MARKED
 */

import { useMemo, type CSSProperties, type ReactNode } from "react";
import { AlertTriangle, Info, Lock, Shield } from "lucide-react";
import { useTerminalState, type TerminalState } from "@/hooks/useTerminalState";

const GOLD = "#FFB800";
const CYAN = "#00E5FF";
const BG = "#0e0e0e";
const PANEL = "#121212";
const BORDER = "#3f3f46";

const VENUE_FLAGS = [
  ["Kraken", "kraken_ready"],
  ["Binance", "binance_ready"],
  ["Alpaca", "alpaca_ready"],
  ["Capital", "capital_ready"],
] as const;

/** Fail-closed: kraken_ready alone can be false-ready (nonce/auth history). */
const KRAKEN_AUTH_FAIL_RE = /nonce|invalid.?nonce|eapi:\s*invalid|invalid.?key|permission.?denied|authentication|unauthorized/i;

type TerminalProbeExtras = {
  api_governor?: { exchanges?: Record<string, { errors?: number; last_error?: string } | undefined> };
  provider_observations?: Record<
    string,
    { accounts?: { status?: string; source?: string; reason?: string; generated_values?: boolean } | undefined } | undefined
  >;
};

function krakenNonceOrAuthFailed(state: TerminalState & TerminalProbeExtras): boolean {
  const err = String(state.errors?.kraken ?? "");
  if (err && KRAKEN_AUTH_FAIL_RE.test(err)) return true;

  const gov = state.api_governor?.exchanges?.kraken;
  const lastErr = String(gov?.last_error ?? "");
  if (lastErr && KRAKEN_AUTH_FAIL_RE.test(lastErr)) return true;

  const venues = state.exchanges?.execution_venues ?? {};
  for (const [key, venue] of Object.entries(venues)) {
    if (!key.toLowerCase().includes("kraken")) continue;
    const blockers = (venue?.blockers ?? []).join(" ");
    if (blockers && KRAKEN_AUTH_FAIL_RE.test(blockers)) return true;
  }
  return false;
}

/** Spike private probe: fresh private Balance observation — not public ready flag alone. */
function krakenPrivateProbeCleared(state: TerminalProbeExtras): boolean {
  const accounts = state.provider_observations?.kraken?.accounts;
  if (!accounts) return false;
  if (accounts.generated_values === true) return false;
  if (accounts.status !== "observed") return false;
  const source = String(accounts.source ?? "");
  if (!/private\/Balance|private/i.test(source)) return false;
  return true;
}

/** Kraken counts LIVE only with private probe clear + clean governor + no nonce/auth fail. */
function isKrakenCountedLive(state: TerminalState & TerminalProbeExtras): boolean {
  if (state.exchanges?.kraken_ready !== true) return false;
  if (krakenNonceOrAuthFailed(state)) return false;
  if (!krakenPrivateProbeCleared(state)) return false;
  const gov = state.api_governor?.exchanges?.kraken;
  if (gov) {
    if (typeof gov.errors === "number" && gov.errors > 0) return false;
    if (String(gov.last_error ?? "").trim()) return false;
  } else {
    return false;
  }
  return true;
}

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

function GoldBadge({ children }: { children: ReactNode }) {
  return (
    <span
      className="inline-flex items-center rounded px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wider"
      style={{ background: GOLD, color: "#0a0a0a" }}
    >
      {children}
    </span>
  );
}

function Panel({
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
      style={{ background: PANEL, borderColor: BORDER, ...style }}
    >
      {children}
    </div>
  );
}

/** Pipeline stages after INTEL are always HELD while EXECUTION HOLD is painted. */
const PIPELINE_STAGES = [
  {
    id: "intel",
    label: "INTEL SEEN",
    tone: "cyan" as const,
    status: "EXAMPLE",
    detail: "10:15:23.123456",
    example: true,
  },
  {
    id: "dispatch",
    label: "EXEC DISPATCHED",
    tone: "gold" as const,
    status: "HELD",
    detail: "held by EXECUTION HOLD",
    example: false,
  },
  {
    id: "routed",
    label: "ORDER ROUTED",
    tone: "gold" as const,
    status: "HELD",
    detail: "held by EXECUTION HOLD",
    example: false,
  },
  {
    id: "ack",
    label: "VENUE ACK",
    tone: "cyan" as const,
    status: "HELD",
    detail: "held by EXECUTION HOLD",
    example: false,
  },
  {
    id: "fill",
    label: "FILL / PARTIAL",
    tone: "cyan" as const,
    status: "HELD",
    detail: "held by EXECUTION HOLD",
    example: false,
  },
] as const;

const BLOTTER_COLS = [
  "TIME",
  "ORDER ID",
  "SIDE",
  "SYMBOL",
  "VENUE",
  "SIZE",
  "PRICE",
  "STATUS",
  "FILL / LATENCY",
] as const;

export default function HftDeskPage() {
  const terminal = useTerminalState();
  const { state, isFresh, freshness } = terminal;

  const executorEnabled = isFresh ? state?.exchange_action_plan?.executor_enabled : undefined;
  const blockers = isFresh ? state?.exchange_action_plan?.global_blockers ?? [] : [];
  // Fail closed: HOLD unless fresh probe says executor enabled with no blockers.
  const onHold = !(executorEnabled === true && blockers.length === 0);

  // Fail-closed Exchanges KPI: never let Kraken false-ready / nonce-auth inflate LIVE count.
  // Required when Kraken false-ready: "n/4 · Kraken NOT READY" OR "— / 4 unconfirmed".
  const venueLive = useMemo(() => {
    if (!isFresh || !state?.exchanges) {
      return { live: null as number | null, total: VENUE_FLAGS.length, krakenNotReady: false, detail: "" };
    }
    const extras = state as TerminalState & TerminalProbeExtras;
    let live = 0;
    let krakenNotReady = false;
    for (const [name, flag] of VENUE_FLAGS) {
      if (name === "Kraken") {
        if (isKrakenCountedLive(extras)) live += 1;
        else krakenNotReady = true;
        continue;
      }
      if (state.exchanges?.[flag] === true) live += 1;
    }
    return {
      live,
      total: VENUE_FLAGS.length,
      krakenNotReady,
      detail: krakenNotReady
        ? "Kraken NOT READY — waiting on private probe (fail-closed)"
        : "Observed venue ready flags from terminal probe",
    };
  }, [isFresh, state]);

  const venuesDark = !isFresh || venueLive.live == null || venueLive.live === 0;

  return (
    <div
      className="min-h-full space-y-4 p-4 text-zinc-100"
      style={{ background: BG }}
      data-hft-desk="shipped-glass-v1"
      data-hft-theme="aureon-dark"
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
        </div>
        <p className="mt-0.5 flex flex-wrap items-center gap-1.5 text-[10px] uppercase tracking-wide" style={{ color: `${GOLD}cc` }}>
          <AlertTriangle className="h-3 w-3 shrink-0" style={{ color: GOLD }} />
          Example layout data — not Aureon P&amp;L, not measured latency, not third-party facts.
        </p>
      </div>

      {/* Page header */}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="text-2xl font-bold uppercase tracking-[0.08em] text-white">HFT Desk</h1>
            <div
              className="inline-flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-black uppercase tracking-widest"
              style={{ background: GOLD, color: "#0a0a0a" }}
            >
              <Lock className="h-3.5 w-3.5" />
              EXECUTION HOLD
            </div>
            <span className="text-[11px] text-zinc-500">/ analysis-only / real_orders_disabled</span>
          </div>
          <p className="mt-1 text-[11px] text-zinc-500">
            intel may appear · exec stages blank when held · SHIPPED GLASS · EXAMPLE LAYOUT WHERE MARKED
          </p>
        </div>
        <div
          className="inline-flex items-center gap-2 rounded-md border px-3 py-2 text-sm font-black uppercase tracking-widest"
          style={{ borderColor: GOLD, color: GOLD, background: `${GOLD}12` }}
        >
          <Lock className="h-4 w-4" />
          HOLD ANALYSIS-ONLY
        </div>
      </div>

      {/* Always-visible execution hold strip */}
      <div
        className="rounded-md border px-3 py-2"
        style={{ borderColor: `${GOLD}88`, background: `${GOLD}10` }}
      >
        <p className="text-xs font-bold uppercase tracking-[0.14em]" style={{ color: GOLD }}>
          EXECUTION HOLD
        </p>
        <p className="mt-0.5 text-[10px] text-zinc-400">
          {onHold
            ? "Gate closed · real orders disabled · no unlock UI that fights HOLD"
            : "Probe reported executor enabled — HFT Desk still refuses false READY paint"}
          {!isFresh ? " · runtime tick not fresh (diagnostic only)" : ""}
          {blockers.length > 0 ? ` · blockers: ${[...new Set(blockers)].slice(0, 3).join(", ")}` : ""}
        </p>
      </div>

      {/* Top stats — UI RTT / VENUES / BLOTTER / SLO */}
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Panel className="p-3">
          <div className="mb-2 flex items-center justify-between gap-2">
            <span className="text-[11px] uppercase tracking-wide text-zinc-400">UI RTT</span>
            <ExampleBadge />
          </div>
          <div className="font-mono text-2xl font-semibold tabular-nums tracking-tight text-white">— ms</div>
          <p className="mt-1 text-[10px] text-zinc-500">not measured / EXAMPLE · UI RTT ≠ tick→ack</p>
        </Panel>

        <Panel className="p-3">
          <div className="mb-2 flex items-center justify-between gap-2">
            <span className="text-[11px] uppercase tracking-wide text-zinc-400">Venues</span>
            {venuesDark && !venueLive.krakenNotReady ? <ExampleBadge label="DARK" /> : null}
          </div>
          <div className="flex flex-wrap items-baseline gap-2 font-mono text-2xl font-semibold tabular-nums tracking-tight">
            {!isFresh || venueLive.live == null ? (
              <>
                <span className="text-white">— / {venueLive.total}</span>
                <span className="text-sm font-medium text-zinc-500">unconfirmed</span>
              </>
            ) : venueLive.krakenNotReady ? (
              <span className="text-white">
                {venueLive.live}/{venueLive.total}
                <span className="mx-1.5 text-zinc-500">·</span>
                <span className="text-lg font-bold uppercase tracking-wide" style={{ color: GOLD }}>
                  Kraken NOT READY
                </span>
              </span>
            ) : (
              <span className="text-white">
                {venueLive.live} / {venueLive.total}
              </span>
            )}
          </div>
          <p className="mt-1 flex items-center gap-1.5 text-[10px] text-zinc-500">
            <span className="inline-block h-1.5 w-1.5 rounded-full" style={{ background: GOLD }} />
            {!isFresh || venueLive.live == null
              ? "— / 4 unconfirmed · probe stale/unavailable"
              : venueLive.krakenNotReady
                ? venueLive.detail || "Kraken NOT READY — waiting on private probe (fail-closed)"
                : venuesDark
                  ? "dark / none"
                  : venueLive.detail || "observed ready flags"}
          </p>
        </Panel>

        <Panel className="p-3">
          <div className="mb-2 flex items-center justify-between gap-2">
            <span className="text-[11px] uppercase tracking-wide text-zinc-400">Blotter</span>
            <GoldBadge>EMPTY HONEST</GoldBadge>
          </div>
          <div className="font-mono text-2xl font-semibold uppercase tracking-tight text-white">EMPTY</div>
          <p className="mt-1 text-[10px] text-zinc-500">honest · no fills · no activity</p>
        </Panel>

        <Panel className="p-3">
          <div className="mb-2 flex items-center justify-between gap-2">
            <span className="text-[11px] uppercase tracking-wide text-zinc-400">SLO</span>
            <ExampleBadge label="DARK" />
          </div>
          <div className="font-mono text-2xl font-semibold tabular-nums tracking-tight text-white">—</div>
          <p className="mt-1 text-[10px] text-zinc-500">dark honest · no measured data</p>
        </Panel>
      </div>

      {/* Middle: Execution pipeline + Traces */}
      <div className="grid gap-3 xl:grid-cols-[1.4fr_1fr]">
        <Panel className="p-3">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
            <h2 className="text-xs font-semibold uppercase tracking-[0.12em]" style={{ color: GOLD }}>
              Execution Pipeline
            </h2>
            <GoldBadge>HONEST STAGES</GoldBadge>
          </div>
          <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-stretch">
            {PIPELINE_STAGES.map((stage, idx) => {
              const dot = stage.tone === "cyan" ? CYAN : GOLD;
              return (
                <div key={stage.id} className="flex min-w-0 flex-1 items-stretch gap-2">
                  <div
                    className="flex min-w-0 flex-1 flex-col rounded-md border p-2.5"
                    style={{ borderColor: BORDER, background: "#0a0a0a" }}
                  >
                    <div className="mb-1.5 flex items-center gap-1.5">
                      <span className="h-2 w-2 shrink-0 rounded-full" style={{ background: dot }} />
                      <span className="text-[10px] font-semibold uppercase tracking-wide text-zinc-400">
                        {stage.label}
                      </span>
                    </div>
                    <div className="flex flex-wrap items-center gap-1.5">
                      <span
                        className="font-mono text-sm font-bold uppercase tracking-wider"
                        style={{ color: stage.status === "HELD" ? GOLD : CYAN }}
                      >
                        {stage.status}
                      </span>
                      {stage.example ? <ExampleBadge /> : null}
                    </div>
                    <p className="mt-1 font-mono text-[10px] text-zinc-500">{stage.detail}</p>
                  </div>
                  {idx < PIPELINE_STAGES.length - 1 ? (
                    <div className="hidden items-center text-zinc-600 sm:flex" aria-hidden>
                      →
                    </div>
                  ) : null}
                </div>
              );
            })}
          </div>
        </Panel>

        <Panel className="p-3">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
            <h2 className="text-xs font-semibold uppercase tracking-[0.12em]" style={{ color: GOLD }}>
              Traces (E2E)
            </h2>
            <GoldBadge>INCOMPLETE E2E — HONEST</GoldBadge>
          </div>
          <div className="space-y-2 text-[11px]">
            <div className="flex justify-between gap-2 font-mono">
              <span className="uppercase text-zinc-500">Trace ID</span>
              <span className="text-zinc-200">—</span>
            </div>
            <div className="flex items-center justify-between gap-2 font-mono">
              <span className="uppercase text-zinc-500">Status</span>
              <span className="inline-flex items-center gap-1.5" style={{ color: GOLD }}>
                <span className="h-1.5 w-1.5 rounded-full" style={{ background: GOLD }} />
                INCOMPLETE
              </span>
            </div>
            <div
              className="rounded-md border p-2.5"
              style={{ borderColor: BORDER, background: "#0a0a0a" }}
            >
              <div className="flex gap-2">
                <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" style={{ color: CYAN }} />
                <p className="text-[10px] leading-relaxed text-zinc-400">
                  analysis-only + real_orders_disabled. HOLD, not green GO — even if trading_ready
                  semantics trap exists.
                </p>
              </div>
            </div>
            <div className="flex items-center justify-between gap-2 border-t border-zinc-800 pt-2 font-mono">
              <span className="uppercase text-zinc-500">
                Latency (µs) — <span style={{ color: GOLD }}>EXAMPLE</span>
              </span>
              <span className="text-zinc-200">— µs</span>
            </div>
            <p className="text-[10px] text-zinc-600">
              No fake percentiles · latency dark until real JSONL traces · UI RTT is not tick-to-ack
              {freshness.sourceAgeSec != null
                ? ` · source age ${freshness.sourceAgeSec.toFixed(1)}s`
                : ""}
            </p>
          </div>
        </Panel>
      </div>

      {/* Order blotter — empty honest */}
      <Panel className="p-3">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-xs font-semibold uppercase tracking-[0.12em]" style={{ color: GOLD }}>
            Order Blotter
          </h2>
          <GoldBadge>EMPTY HONEST STATE</GoldBadge>
        </div>
        <div className="overflow-auto rounded-md border" style={{ borderColor: BORDER }}>
          <table className="w-full min-w-[720px] text-left text-[10px]">
            <thead>
              <tr className="border-b border-zinc-800 text-zinc-500">
                {BLOTTER_COLS.map((col) => (
                  <th key={col} className="px-2 py-2 font-semibold uppercase tracking-wider">
                    {col}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              <tr>
                <td colSpan={BLOTTER_COLS.length} className="px-2 py-10 text-center">
                  <p className="text-sm font-medium text-zinc-300">No fills — execution held</p>
                  <p className="mt-1 text-[11px] text-zinc-500">
                    No orders dispatched · real_orders_disabled
                  </p>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </Panel>

      {/* Risk footer */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-zinc-800 pt-3">
        <div className="flex items-center gap-2 text-[10px] uppercase tracking-wider text-zinc-400">
          <Shield className="h-3.5 w-3.5" style={{ color: GOLD }} />
          Risk Disclosure
        </div>
        <p className="max-w-2xl text-center text-[10px] text-zinc-500">
          SHIPPED GLASS · EXAMPLE LAYOUT WHERE MARKED. Not financial advice. Do not infer
          performance or trading capability.
        </p>
        <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-zinc-500">
          Clarity Over Confidence
        </p>
      </div>
    </div>
  );
}
