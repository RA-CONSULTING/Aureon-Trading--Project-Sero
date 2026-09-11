import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { Activity, Lock, Radio, Shield } from 'lucide-react';
import { useTerminalState } from '@/hooks/useTerminalState';
import { LiveMarketQuotes } from '@/components/warroom/LiveMarketQuotes';
import { readNativeBalanceEvidence } from '@/lib/nativeBalanceEvidence';
import { executionGlassState, glassDecisionTraces, glassLatency } from '@/lib/glassTradingEvidence';
import { evidenceRecord } from '@/lib/warRoomEvidence';

const GOLD = '#FFB800';
const CYAN = '#00E5FF';
function Panel({ title, children, className = '' }: { title: string; children: ReactNode; className?: string }) {
  return <section className={`rounded-lg border border-zinc-700 bg-[#121212]/95 p-4 backdrop-blur-xl ${className}`}><h2 className="mb-3 text-xs font-semibold uppercase tracking-[0.12em]" style={{ color: GOLD }}>{title}</h2>{children}</section>;
}
function Metric({ title, value, detail }: { title: string; value: string; detail: string }) {
  return <div className="rounded-md border border-zinc-800 bg-[#0a0a0a] p-3"><p className="text-[10px] uppercase text-zinc-500">{title}</p><p className="mt-2 font-mono text-xl" style={{ color: CYAN }}>{value}</p><p className="mt-2 text-[10px] text-zinc-500">{detail}</p></div>;
}

export default function WarRoomPage() {
  const terminal = useTerminalState();
  const { state, isFresh, freshness } = terminal;
  const execution = executionGlassState(state, isFresh, terminal.isStreamFresh);
  const gate = isFresh ? evidenceRecord(state?.trading_gate_evidence) : {};
  const analysisBlockers = Array.isArray(gate.analysis_blockers) ? gate.analysis_blockers.filter((item): item is string => typeof item === 'string') : [];
  const providers = readNativeBalanceEvidence(state?.provider_observations, !terminal.error && !!state);
  const traces = glassDecisionTraces(state, isFresh);
  const latency = isFresh ? glassLatency(evidenceRecord(state?.decision_latency_percentiles).intent_ready_sec) : null;
  const bridgeCount = providers.filter(p => p.observation.available).length;
  return <div className="min-h-full space-y-4 bg-[#0e0e0e] p-4 text-zinc-100" data-war-room="wired-glass-v2">
    <div className="flex flex-wrap justify-between gap-2 rounded-md border border-zinc-700 bg-[#121212] px-3 py-2 text-[11px]">
      <span className="font-semibold uppercase tracking-wider" style={{ color: CYAN }}>Runtime observations · {freshness.status}</span><span className="text-zinc-400">Completed tick {freshness.sourceTimestamp ?? 'unavailable'}</span>
    </div>
    <header className="flex flex-wrap items-start justify-between gap-3"><div className="flex items-center gap-3"><Shield style={{ color: GOLD }} /><div><h1 className="text-2xl font-bold uppercase tracking-[0.08em]">War Room</h1><p className="mt-1 text-xs text-zinc-400">Market observations, account connections and execution gates.</p></div></div>
      <span className="flex items-center gap-2 rounded-md border px-3 py-2 text-sm font-bold uppercase" style={{ color: execution.enabled ? CYAN : GOLD, borderColor: execution.enabled ? CYAN : GOLD }}>{execution.enabled ? <Activity size={16} /> : <Lock size={16} />}{execution.label}</span>
    </header>
    <div className="rounded-md border px-3 py-2 text-xs" style={{ borderColor: `${GOLD}66`, background: `${GOLD}0d` }}><p>{execution.mode.replaceAll('_', ' ')}</p><p className="mt-1 text-zinc-400">{execution.reason}{execution.blockers.length ? ` · ${execution.blockers.join(' · ').replaceAll('_', ' ')}` : ''}</p></div>
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      <Panel title="Execution gate"><p className="text-sm" style={{ color: GOLD }}>{execution.label}</p></Panel>
      <Panel title="Intent publishing"><p className="text-sm">{execution.intent}</p></Panel>
      <Panel title="Real order setting"><p className="text-sm">{execution.orders}</p></Panel>
      <Panel title="Live Bridge"><Link to="/trading/live" className="text-sm underline underline-offset-4" style={{ color: CYAN }}>{bridgeCount} / {providers.length} private account reads</Link></Panel>
    </div>
    <div className="grid gap-3 lg:grid-cols-12">
      <Panel title="Execution control" className="lg:col-span-3">
        <p className="text-xs text-zinc-400">Review the active gates and configure the existing operator controls.</p>
        <dl className="my-4 space-y-2 text-xs"><div className="flex justify-between"><dt>Analysis</dt><dd>{!isFresh ? 'Unconfirmed' : execution.analysisReady ? 'Ready' : 'Blocked'}</dd></div><div className="flex justify-between"><dt>Executor</dt><dd>{isFresh && state?.exchange_action_plan?.executor_enabled === true ? 'Enabled' : isFresh && state?.exchange_action_plan?.executor_enabled === false ? 'Disabled' : 'Unconfirmed'}</dd></div></dl>
        <div className="space-y-2 text-xs">{[['/ops/approvals', 'Release readiness and approvals'], ['/platform/switchboard', 'Runtime configuration'], ['/trading/hft', 'Decision traces and latency']].map(([to, label]) => <Link key={to} to={to} className="block rounded-md border border-zinc-700 px-3 py-2 hover:border-cyan-400" style={{ color: CYAN }}>{label}</Link>)}</div>
      </Panel>
      <Panel title="Mission / pulse board" className="lg:col-span-6">
        <div className="mb-3 flex items-center gap-2 text-[11px] text-zinc-400"><Radio size={13} style={{ color: CYAN }} />Current reads and recorded measurements</div>
        <div className="grid gap-2 sm:grid-cols-2">
          <Metric title="Provider market stream" value={terminal.isStreamFresh ? 'Fresh' : terminal.streamFreshness.status} detail={terminal.streamFreshness.reason} />
          <Metric title="Recorded decision tail" value={isFresh && Array.isArray(state?.decision_traces) ? String(traces.length) : '—'} detail="Accepted timestamped decisions in this response" />
          <Metric title="UI round-trip" value={terminal.transportRttMs == null || terminal.error ? '—' : `${terminal.transportRttMs} ms`} detail="Measured terminal HTTP response; not order latency" />
          <Metric title="Intent-ready p95" value={latency ? `${latency.p95.toFixed(3)} s` : '—'} detail={latency ? `${latency.count.toLocaleString()} samples in the recorded log window` : 'No measured sample set available'} />
        </div>
        <p className="mt-3 text-[11px] text-zinc-500">Detailed depth and pressure need timestamped order-book receipts. Quote prices are shown in the market tape below.</p>
      </Panel>
      <Panel title="Current blockers" className="lg:col-span-3">
        <h3 className="text-xs text-zinc-400">Analysis</h3><ul className="mt-2 space-y-2 text-[11px]">{analysisBlockers.map(reason => <li key={reason} style={{ color: GOLD }}>{reason.replaceAll('_', ' ')}</li>)}</ul>
        <p className="mt-2 text-[11px] text-zinc-500">{execution.analysisReason}</p>
        <h3 className="mt-4 text-xs text-zinc-400">Execution</h3><ul className="mt-2 space-y-2 text-[11px]">{execution.blockers.map(reason => <li key={reason} style={{ color: GOLD }}>{reason.replaceAll('_', ' ')}</li>)}</ul>
        <p className="mt-4 text-[10px] text-zinc-500">Source age {freshness.sourceAgeSec == null ? 'unavailable' : `${freshness.sourceAgeSec.toFixed(1)}s`}. Settings and runtime authorization are checked separately.</p>
      </Panel>
    </div>
    <div className="[&_.bg-card]:bg-[#121212] [&_.text-green-300]:text-cyan-300 [&_.text-card-foreground]:text-zinc-100 [&_table]:text-zinc-200"><LiveMarketQuotes terminal={terminal} /></div>
    <footer className="flex flex-wrap justify-between gap-3 border-t border-zinc-800 pt-3 text-[10px] text-zinc-500"><span>Provider source times are preserved; expired observations become unavailable.</span><Link to="/trading/hft" style={{ color: CYAN }}>Open HFT Desk →</Link></footer>
  </div>;
}
