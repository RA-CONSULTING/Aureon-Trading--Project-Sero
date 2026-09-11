import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { Activity, Lock, Radio } from 'lucide-react';
import { useTerminalState } from '@/hooks/useTerminalState';
import { readNativeBalanceEvidence } from '@/lib/nativeBalanceEvidence';
import { evidenceRecord } from '@/lib/warRoomEvidence';
import { executionGlassState, glassDecisionTraces, glassLatency, traceName, TRACE_STAGES } from '@/lib/glassTradingEvidence';

const GOLD = '#FFB800';
const CYAN = '#00E5FF';
function Panel({ title, children, className = '' }: { title: string; children: ReactNode; className?: string }) {
  return <section className={`rounded-lg border border-zinc-700 bg-[#121212]/95 p-4 backdrop-blur-xl ${className}`}>
    <h2 className="mb-3 text-xs font-semibold uppercase tracking-[0.12em]" style={{ color: GOLD }}>{title}</h2>{children}
  </section>;
}
const stamp = (seconds: number | null | undefined) => seconds == null ? '—' : new Date(seconds * 1000).toISOString();
const seconds = (value: number | null | undefined) => value == null ? '—' : `${value.toFixed(3)} s`;

export default function HftDeskPage() {
  const terminal = useTerminalState();
  const { state, isFresh, freshness } = terminal;
  const execution = executionGlassState(state, isFresh, terminal.isStreamFresh);
  const traces = glassDecisionTraces(state, isFresh);
  const latest = traces[0];
  const providers = readNativeBalanceEvidence(state?.provider_observations, !terminal.error && !!state);
  const latency = isFresh ? evidenceRecord(state?.decision_latency_percentiles) : {};
  const e2e = glassLatency(latency.end_to_end_sec);
  const intent = glassLatency(latency.intent_ready_sec);
  const rtt = !terminal.error ? terminal.transportRttMs : null;
  const analysis = isFresh ? execution.analysisReady : undefined;
  const analysisBlockers = isFresh && Array.isArray(state?.trading_gate_evidence?.analysis_blockers)
    ? state.trading_gate_evidence.analysis_blockers.filter((item): item is string => typeof item === 'string') : [];
  return <div className="min-h-full space-y-4 bg-[#0e0e0e] p-4 text-zinc-100" data-hft-desk="wired-glass-v2" data-hft-theme="aureon-dark">
    <div className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-zinc-700 bg-[#121212] px-3 py-2 text-[11px]">
      <span className="font-semibold uppercase tracking-wider" style={{ color: CYAN }}>Runtime observations · {freshness.status}</span>
      <span className="text-zinc-400">Completed tick {freshness.sourceTimestamp ?? 'unavailable'}</span>
    </div>
    <header className="flex flex-wrap items-start justify-between gap-3">
      <div><h1 className="text-2xl font-bold uppercase tracking-[0.08em]">HFT Desk</h1>
        <p className="mt-1 text-xs text-zinc-400">Current execution controls, recorded decisions and measured latency.</p></div>
      <span className="flex items-center gap-2 rounded-md border px-3 py-2 text-sm font-bold uppercase" style={{ color: execution.enabled ? CYAN : GOLD, borderColor: execution.enabled ? CYAN : GOLD }}>
        {execution.enabled ? <Activity size={16} /> : <Lock size={16} />}{execution.label}
      </span>
    </header>
    <div className="rounded-md border px-3 py-2 text-xs" style={{ borderColor: `${GOLD}66`, background: `${GOLD}0d` }}>
      <p>{execution.mode.replaceAll('_', ' ')} · Intent publishing: {execution.intent} · Real orders: {execution.orders}</p>
      <p className="mt-1 text-zinc-400">{execution.reason}{execution.blockers.length ? ` · ${execution.blockers.join(' · ').replaceAll('_', ' ')}` : ''}</p>
      <Link to="/ops/approvals" className="mt-2 inline-block underline underline-offset-4" style={{ color: CYAN }}>Open release readiness and approvals</Link>
    </div>
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      <Panel title="UI round-trip"><p className="font-mono text-2xl">{rtt == null ? '—' : rtt} <span className="text-sm">ms</span></p><p className="mt-2 text-[11px] text-zinc-500">Measured terminal HTTP request; separate from execution latency.</p></Panel>
      <Panel title="Private account reads"><p className="font-mono text-2xl">{providers.filter(p => p.observation.available).length} / {providers.length}</p>
        <div className="mt-2 space-y-1 text-[11px]">{providers.map(p => <div key={p.id} className="flex justify-between gap-2" title={p.observation.reason}><span>{p.name}</span><span style={{ color: p.observation.available ? CYAN : GOLD }}>{p.observation.available ? 'Observed' : 'Unavailable'}</span></div>)}</div></Panel>
      <Panel title="Recorded decisions"><p className="font-mono text-2xl">{isFresh && Array.isArray(state?.decision_traces) ? traces.length : '—'}</p><p className="mt-2 text-[11px] text-zinc-500">Recent decision trace tail. Decision records do not establish fills.</p></Panel>
      <Panel title="Recorded E2E p95"><p className="font-mono text-2xl">{seconds(e2e?.p95)}</p><p className="mt-2 text-[11px] text-zinc-500">{e2e ? `${e2e.count} instrumentation samples · intel to recorded convergence` : 'No complete recorded samples available.'}</p></Panel>
    </div>
    <div className="grid gap-3 xl:grid-cols-[1.5fr_1fr]">
      <Panel title="Execution pipeline · latest recorded decision">
        <p className="mb-3 break-all font-mono text-[11px] text-zinc-400">{latest ? `${traceName(latest.trace)} · ${latest.trace.decision_trace_id}` : 'No current trace receipt available.'}</p>
        <div className="grid gap-2 sm:grid-cols-3">{TRACE_STAGES.map(([key, label], index) => {
          const time = latest?.stages[index].timestamp;
          return <div key={key} className="rounded-md border border-zinc-800 bg-[#0a0a0a] p-3"><p className="text-[10px] uppercase text-zinc-500">{label}</p>
            <p className="mt-1 text-xs font-bold" style={{ color: time != null ? CYAN : GOLD }}>{time != null ? 'Recorded' : !latest ? 'Unavailable' : 'Not recorded'}</p>
            <p className="mt-1 break-all font-mono text-[10px] text-zinc-400">{stamp(time)}</p></div>;
        })}</div>
        <p className="mt-3 text-[10px] text-zinc-500">Stages describe this recorded decision. Acknowledgment and convergence are not fill receipts.</p>
      </Panel>
      <Panel title="Trace measurements">
        <dl className="space-y-2 text-xs"><div className="flex justify-between"><dt>Analysis</dt><dd>{analysis === true ? 'Ready' : analysis === false ? 'Blocked' : 'Unconfirmed'}</dd></div>
          <div className="flex justify-between"><dt>Latest recorded E2E</dt><dd>{seconds(latest?.e2eSeconds)}</dd></div>
          <div className="flex justify-between"><dt>Intent-ready p50</dt><dd>{seconds(intent?.p50)}</dd></div>
          <div className="flex justify-between"><dt>Intent-ready p95</dt><dd>{seconds(intent?.p95)}</dd></div>
          <div className="flex justify-between"><dt>Intent-ready samples</dt><dd>{intent?.count.toLocaleString() ?? '—'}</dd></div>
        </dl>
        <p className="mt-3 text-[11px] text-zinc-400">{execution.analysisReason} {analysisBlockers.join(' · ').replaceAll('_', ' ')}</p>
        <p className="mt-3 text-[10px] text-zinc-500">Percentiles cover the recorded log window. Venue acknowledgment timing still requires instrumentation validation. {freshness.sourceAgeSec == null ? '' : `Runtime source age ${freshness.sourceAgeSec.toFixed(1)}s.`}</p>
      </Panel>
    </div>
    <Panel title="Decision trace ledger">
      <div className="max-h-80 overflow-auto"><table className="w-full min-w-[720px] text-left text-[11px]"><thead className="text-zinc-500"><tr>{['Intel observed (UTC)', 'Trace ID', 'Venue', 'Symbol', 'Side', 'Last recorded stage', 'E2E'].map(label => <th key={label} className="p-2">{label}</th>)}</tr></thead>
        <tbody>{traces.map((row, index) => <tr key={`${row.trace.decision_trace_id}:${row.timestamp}:${index}`} className="border-t border-zinc-800">
          <td className="p-2 font-mono">{stamp(row.timestamp)}</td><td className="max-w-60 break-all p-2 font-mono">{row.trace.decision_trace_id}</td><td className="p-2">{row.trace.venue || '—'}</td><td className="p-2">{row.trace.symbol || '—'}</td><td className="p-2">{row.trace.side || '—'}</td><td className="p-2">{row.stages.filter(s => s.timestamp != null).slice(-1)[0]?.label ?? '—'}</td><td className="p-2">{seconds(row.e2eSeconds)}</td>
        </tr>)}{!traces.length ? <tr><td colSpan={7} className="p-6 text-center text-zinc-500">No accepted decision records in the current runtime response.</td></tr> : null}</tbody></table></div>
    </Panel>
    <Panel title="Order blotter / fills">
      <p className="text-xs text-zinc-400">The current terminal contract does not publish an order/fill ledger. Provider account reads and decision traces cannot establish an empty or completed order history.</p>
      <div className="mt-3 flex flex-wrap gap-4 text-xs" style={{ color: CYAN }}><Link className="underline" to="/trading/live">Open live account bridge</Link><Link className="underline" to="/trading/war-room">Open War Room</Link></div>
    </Panel>
    <footer className="flex items-center gap-2 border-t border-zinc-800 pt-3 text-[10px] text-zinc-500"><Radio size={13} />Source: terminal runtime and timestamped provider receipts. Trading controls remain governed by the backend.</footer>
  </div>;
}
