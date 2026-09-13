/** Live Bridge glass, reading the same authenticated runtime receipts as the operating panels. */
import { useState, type CSSProperties, type ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { Bus, Radio, Shield, Waypoints } from 'lucide-react';
import { useTerminalState } from '@/hooks/useTerminalState';
import { useGlassQuotes } from '@/hooks/useGlassQuotes';
import { readNativeBalanceEvidence } from '@/lib/nativeBalanceEvidence';
import { executionGlassState } from '@/lib/glassTradingEvidence';
import { currentCandidateCount, currentGlassCandidates } from '@/lib/glassOverviewEvidence';
import { cloudExecutionPresentation } from '@/lib/cloudTradingPresentation';
import { useReadOnlyPoller } from '@/hooks/useReadOnlyPoller';
import { cloudTradingControlStore } from '@/services/platformReads';

const GOLD = '#FFB800';
const CYAN = '#00E5FF';
const BG = '#0e0e0e';
const PANEL = '#121212';
const BORDER = '#3f3f46';
const format = (value: number | null | undefined) => value == null ? '—' : value.toLocaleString(undefined, { maximumSignificantDigits: 12 });
function EvidenceBadge({ children }: { children: ReactNode }) {
  return <span className="inline-flex rounded border px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wider" style={{ color: GOLD, background: `${GOLD}18`, borderColor: `${GOLD}55` }}>{children}</span>;
}
function Panel({ children, className = '', style }: { children: ReactNode; className?: string; style?: CSSProperties }) {
  return <div className={`rounded-lg border ${className}`} style={{ background: PANEL, borderColor: BORDER, ...style }}>{children}</div>;
}

export default function LiveBridgePage() {
  const terminal = useTerminalState();
  const cloudRead = useReadOnlyPoller(cloudTradingControlStore, 15_000, 8_000);
  const cloud = cloudExecutionPresentation(cloudRead);
  const { state, observedState, isFresh, error, freshness } = terminal;
  const market = useGlassQuotes(terminal);
  const connected = error === null && observedState !== null;
  const providers = readNativeBalanceEvidence(observedState?.provider_observations, connected);
  const [showZeros, setShowZeros] = useState(false);
  const zeroCount = providers.reduce((sum, provider) => sum + provider.zeroCount, 0);
  const balances = providers.flatMap(provider => [...provider.visible, ...(showZeros ? provider.zeros : [])].flatMap(group => group.rows.map((row, index) => ({
    ...row, id: `${provider.id}:${group.key}:${row.key}`, asset: group.currency, venue: provider.name,
    metric: group.metric, record: group.rows.length > 1 ? index + 1 : null,
  }))));
  const execution = executionGlassState(state, isFresh, market.freshness.status === 'fresh');
  const candidates = currentGlassCandidates(state, isFresh);
  const candidateCount = currentCandidateCount(observedState, connected);
  const currentAccounts = providers.filter(provider => provider.observation.available).length;
  const cloudProviders = cloudRead.isReceiptCurrent && cloudRead.data?.last_probe?.current === true
    ? cloudRead.data.last_probe.provider_readback?.providers ?? null
    : null;
  const cloudColor = cloud.active ? CYAN : GOLD;

  return <div className="min-h-full space-y-4 p-4 text-zinc-100" style={{ background: BG }} data-live-bridge="shipped-glass-v2" data-cloud-release-state={cloud.state}>
    <div className="rounded-md border px-3 py-2" style={{ borderColor: `${cloudColor}55`, background: `${cloudColor}0d` }}><p className="text-[11px] font-semibold uppercase tracking-[0.14em]" style={{ color: cloudColor }}>{cloud.headline}</p><p className="mt-0.5 text-[10px] text-zinc-400">{cloud.detail}</p></div>
    <div className="flex flex-wrap items-start justify-between gap-3"><div className="flex items-start gap-3"><div className="flex h-10 w-10 items-center justify-center rounded-md" style={{ background: `${GOLD}18`, border: `1px solid ${GOLD}66` }}><Waypoints className="h-5 w-5" style={{ color: GOLD }} /></div><div><h1 className="text-2xl font-bold uppercase tracking-[0.08em] text-white">Live Bridge</h1><p className="mt-1 text-[11px] text-zinc-400">One shared observation feed · no additional trading connection</p></div></div>
      <div className="inline-flex items-center gap-2 rounded-md border px-3 py-2 text-sm font-black uppercase tracking-wide" style={{ borderColor: cloudColor, color: cloudColor, background: `${cloudColor}12` }}><Shield className="h-4 w-4" />{cloud.release}</div></div>
    <div className="rounded-md border px-3 py-2" style={{ borderColor: `${cloudColor}88`, background: `${cloudColor}10` }}><p className="text-xs font-bold uppercase tracking-wide" style={{ color: cloudColor }}>{cloud.intentBridge}</p><p className="mt-0.5 text-[10px] text-zinc-400">Cloud authority: {cloud.state} · VM planner: {execution.mode.replaceAll('_', ' ')} · runtime {freshness.status}</p><p className="mt-1 text-[10px] text-zinc-500">{cloud.orderOutcome}</p><Link to="/trading/war-room" className="mt-1 inline-block text-[10px] underline" style={{ color: CYAN }}>Open cloud authority and VM planner evidence</Link></div>
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
      <Panel className="p-3"><div className="mb-2 flex items-center justify-between gap-2"><span className="text-[11px] uppercase tracking-wide text-zinc-400">Cloud execution authentication</span><EvidenceBadge>Signed no-order probe</EvidenceBadge></div><div className="text-2xl font-semibold tabular-nums text-white">{cloud.executionAuthentication}</div><p className="mt-1 text-[10px] text-zinc-500">{cloud.executionAuthenticationDetail}</p></Panel>
      <Panel className="p-3"><div className="mb-2 flex items-center justify-between gap-2"><span className="text-[11px] uppercase tracking-wide text-zinc-400">Native account inventories</span><EvidenceBadge>VM provider receipts</EvidenceBadge></div><div className="text-2xl font-semibold tabular-nums text-white">{connected ? currentAccounts : '—'} / 4</div><p className="mt-1 text-[10px] text-zinc-500">Current balance/account coverage; it does not determine cloud executor authentication.</p></Panel>
      <Panel className="p-3"><div className="mb-2 flex items-center justify-between gap-2"><span className="text-[11px] uppercase tracking-wide text-zinc-400">Current order-flow candidates</span><EvidenceBadge>{candidateCount === null ? 'Unavailable' : 'Runtime derived'}</EvidenceBadge></div><div className="text-2xl font-semibold tabular-nums text-white">{format(candidateCount)}</div><p className="mt-1 text-[10px] text-zinc-500">Measured candidate receipt · no count inferred from a missing source.</p></Panel>
      <Panel className="p-3"><div className="mb-2 flex items-center justify-between gap-2"><span className="text-[11px] uppercase tracking-wide text-zinc-400">Current market events</span><EvidenceBadge>{market.freshness.status}</EvidenceBadge></div><div className="text-2xl font-semibold tabular-nums text-white">{market.freshness.status === 'fresh' ? market.quotes.length : '—'}</div><p className="mt-1 text-[10px] text-zinc-500">Unique symbol / provider observations inside their source expiry.</p></Panel>
      <Panel className="p-3"><div className="mb-2 flex items-center justify-between gap-2"><span className="text-[11px] uppercase tracking-wide text-zinc-400">Bridge transport</span><EvidenceBadge>{connected ? 'Observed' : 'Unavailable'}</EvidenceBadge></div><div className="flex items-center gap-2"><Bus className="h-6 w-6" style={{ color: CYAN }} /><div><p className="text-sm font-semibold" style={{ color: connected ? CYAN : GOLD }}>{connected ? 'Shared HTTP readback' : 'Waiting for runtime'}</p><p className="text-[10px] text-zinc-500">{terminal.transportRttMs === null ? 'HTTP RTT unavailable' : `HTTP RTT ${terminal.transportRttMs} ms`} · separate from trade latency</p></div></div></Panel>
    </div>
    <div><div className="mb-2 flex flex-wrap items-center justify-between gap-2"><h2 className="text-sm font-semibold uppercase tracking-[0.14em]" style={{ color: GOLD }}>Exchange status</h2><Link to="/platform/switchboard" className="text-[10px] underline text-zinc-400">System controls</Link></div>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">{providers.map(provider => {
        const observation = provider.observation;
        const cloudProvider = cloudProviders?.[provider.id];
        const color = cloudProvider?.authenticated === true ? CYAN : observation.available ? CYAN : GOLD;
        const venue = state?.exchanges?.execution_venues?.[provider.id === 'capital' ? 'capital_cfd' : `${provider.id}_spot`];
        const groups = provider.visible.length ? provider.visible : provider.zeros;
        return <Panel key={provider.id} className="space-y-2 p-3"><div className="flex items-start justify-between gap-2"><div className="flex items-center gap-2"><div className="flex h-8 w-8 items-center justify-center rounded-md text-[11px] font-black" style={{ background: `${color}18`, border: `1px solid ${color}55`, color }}>{provider.name.slice(0, 1)}</div><div><p className="text-xs font-semibold uppercase text-zinc-200">{provider.name}</p><p className="text-[10px] font-bold uppercase" style={{ color: cloudProvider?.authenticated === true ? CYAN : GOLD }}>Cloud executor: {cloudProvider?.authenticated === true ? 'authenticated' : 'unconfirmed'}</p><p className="text-[9px] uppercase text-zinc-500">VM inventory: {observation.available ? 'receipt current' : 'unavailable'}</p></div></div></div>
          <p className="text-sm font-semibold tabular-nums text-white">{observation.available ? `${observation.count} account records` : '—'}</p>
          {groups.slice(0, 2).map(group => <p key={group.key} className="text-[11px] text-zinc-400">{group.currency} · {group.metric}: {group.rows.map(row => format(row.balance)).join(' / ')}</p>)}
          <p className="text-[10px] text-zinc-500">VM planner route: {!isFresh ? 'unconfirmed' : venue?.ready === true ? 'reported ready' : venue?.ready === false ? 'held' : 'unreported'}{isFresh && venue?.blockers?.length ? ` · ${venue.blockers.join(' · ').replaceAll('_', ' ')}` : ''}</p>
          <p className="text-[10px] text-zinc-500">{observation.reason} · age {observation.ageSeconds === null ? '—' : `${Math.max(0, observation.ageSeconds).toFixed(1)}s`}</p>
          <details className="text-[10px] text-zinc-500"><summary className="cursor-pointer">Source receipt</summary><p className="mt-1 break-words">{observation.source ?? 'No source'} · {observation.timestamp === null ? 'No timestamp' : new Date(observation.timestamp * 1000).toISOString()}</p></details></Panel>;
      })}</div></div>
    <div className="grid gap-3 lg:grid-cols-12">
      <Panel className="space-y-3 p-4 lg:col-span-5"><div className="flex items-center justify-between gap-2"><h2 className="text-sm font-semibold uppercase tracking-[0.14em] text-zinc-200">Combined Balances</h2><EvidenceBadge>Native units</EvidenceBadge></div><p className="text-[10px] text-zinc-500">Account balances, equity and asset totals retain each provider's metric. Unreported available or locked amounts remain blank.</p>
        <label className="flex items-center gap-2 text-[10px] text-zinc-400"><input type="checkbox" checked={showZeros} onChange={event => setShowZeros(event.target.checked)} />Show {zeroCount} observed zero records</label>
        <div className="max-h-80 overflow-auto rounded-md border" style={{ borderColor: BORDER }} tabIndex={0} role="region" aria-label="Native provider balances"><table className="w-full text-left text-[11px]"><thead className="sticky top-0 bg-zinc-900 text-zinc-500"><tr>{['Asset / metric', 'Venue', 'Balance', 'Locked', 'Available'].map(heading => <th key={heading} className="px-2 py-1.5 font-medium">{heading}</th>)}</tr></thead><tbody>{balances.map(row => <tr key={row.id} className="border-t" style={{ borderColor: BORDER }}><td className="px-2 py-1.5 font-mono text-zinc-200">{row.asset}<small className="block text-[9px] text-zinc-500">{row.metric}{row.record ? ` · record ${row.record}` : ''}</small>{row.reason && <small className="block text-amber-300">{row.reason}</small>}</td><td className="px-2 py-1.5 text-zinc-400">{row.venue}</td><td className="px-2 py-1.5 tabular-nums">{format(row.balance)}</td><td className="px-2 py-1.5 tabular-nums text-zinc-500">{format(row.locked)}</td><td className="px-2 py-1.5 tabular-nums">{format(row.available)}</td></tr>)}{!balances.length && <tr><td colSpan={5} className="p-3 text-zinc-500">{currentAccounts ? 'No nonzero qualified balances in current receipts.' : 'Current account receipts unavailable.'}</td></tr>}</tbody></table></div></Panel>
      <Panel className="space-y-3 p-4 lg:col-span-3"><div className="flex items-center justify-between gap-2"><h2 className="flex items-center gap-2 text-sm font-semibold uppercase" style={{ color: CYAN }}><Radio className="h-4 w-4" />Live Signals</h2><EvidenceBadge>Analysis</EvidenceBadge></div><p className="text-[10px] text-zinc-500">Fresh plan candidates with source age checks. Model confidence does not measure realized success.</p>
        <div className="max-h-80 space-y-2 overflow-y-auto">{candidates.slice(0, 12).map(row => <div key={row.key} className="rounded border p-2 text-[11px]" style={{ borderColor: `${CYAN}44`, background: `${CYAN}08` }}><p className="font-mono">{row.symbol} · {row.side}</p><p className="mt-1 text-zinc-500">{row.venue} · confidence {row.confidence === null ? 'unavailable' : `${(row.confidence * 100).toFixed(1)}%`}</p></div>)}{!candidates.length && <div className="rounded border border-dashed p-4 text-[11px] text-zinc-400" style={{ borderColor: `${CYAN}55` }}>No current, source-qualified candidate rows. The count above uses a separate order-flow receipt.</div>}</div><Link to="/trading/war-room" className="inline-block text-[10px] underline" style={{ color: CYAN }}>Inspect analysis</Link></Panel>
      <Panel className="space-y-3 p-4 lg:col-span-4"><div className="flex items-center justify-between gap-2"><h2 className="text-sm font-semibold uppercase tracking-[0.14em] text-zinc-200">Top Movers</h2><EvidenceBadge>24h change unavailable</EvidenceBadge></div><p className="text-[10px] text-zinc-500">A timestamped 24-hour change series is not exposed by this feed. Current prices below are observed quotes, sorted by symbol.</p>
        <div className="max-h-72 overflow-auto rounded border" style={{ borderColor: BORDER }}><table className="w-full text-left text-[11px]"><thead className="bg-zinc-900 text-zinc-500"><tr><th className="p-2 font-medium">Symbol</th><th className="p-2 font-medium">Source</th><th className="p-2 font-medium">Price</th></tr></thead><tbody>{[...market.quotes].sort((a, b) => a.symbol.localeCompare(b.symbol)).slice(0, 20).map(quote => <tr key={`${quote.source}:${quote.symbol}`} className="border-t" style={{ borderColor: BORDER }}><td className="p-2 font-mono">{quote.symbol}</td><td className="p-2 text-zinc-500">{quote.source}</td><td className="p-2 font-mono" style={{ color: CYAN }}>{format(quote.price)}</td></tr>)}{!market.quotes.length && <tr><td colSpan={3} className="p-3 text-zinc-500">No current quote rows.</td></tr>}</tbody></table></div></Panel>
    </div>
    <div className="grid gap-3 lg:grid-cols-4"><Panel className="p-3" style={{ borderColor: `${cloudColor}88`, background: `${cloudColor}10` }}><p className="text-[10px] uppercase text-zinc-500">Order / fill evidence</p><p className="mt-1 text-sm" style={{ color: cloudColor }}>{cloud.orderOutcome}</p><p className="mt-1 text-[10px] text-zinc-500">A release or authentication probe is not an order, acknowledgment, or fill.</p></Panel><Panel className="p-3"><p className="text-[10px] uppercase text-zinc-500">Connectivity</p><p className="mt-1 text-sm">{connected ? 'Terminal observation received' : error ?? 'Waiting for the first receipt'}</p><p className="mt-1 text-[10px] text-zinc-500">Auto refresh through the shared runtime reader.</p></Panel><Panel className="p-3"><p className="text-[10px] uppercase text-zinc-500">Runtime tick</p><p className="mt-1 text-sm">{freshness.status} · age {freshness.sourceAgeSec === null ? '—' : `${freshness.sourceAgeSec.toFixed(1)}s`}</p><p className="mt-1 text-[10px] text-zinc-500">{freshness.reason}</p></Panel><Panel className="p-3" style={{ borderColor: `${GOLD}88`, background: `${GOLD}10` }}><p className="text-[10px] uppercase text-zinc-500">Provider event stream</p><p className="mt-1 text-sm" style={{ color: market.freshness.status === 'fresh' ? CYAN : GOLD }}>{market.freshness.status} · {market.freshness.source}</p><p className="mt-1 text-[10px] text-zinc-500">{market.freshness.reason}</p></Panel></div>
  </div>;
}
