/** Operator glass: current evidence from the existing shared runtime. */
import { useEffect, useState, type ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { Activity, Building2, Clock, Radio, Shield, ArrowUpRight } from 'lucide-react';
import { useTerminalState, type TerminalQuote } from '@/hooks/useTerminalState';
import { useGlassQuotes } from '@/hooks/useGlassQuotes';
import { readNativeBalanceEvidence } from '@/lib/nativeBalanceEvidence';
import { executionGlassState } from '@/lib/glassTradingEvidence';
import { appendObservedQuote, currentCandidateCount, currentGlassCandidates, endToEndMedianMs, observedCandles, type QuoteSample } from '@/lib/glassOverviewEvidence';

const GOLD = '#FFB800';
const CYAN = '#00E5FF';
const BG = '#0e0e0e';
const PANEL = '#121212';
const BORDER = '#3f3f46';
const format = (value: number | null | undefined) => value == null ? '—' : value.toLocaleString(undefined, { maximumSignificantDigits: 10 });

function EvidenceBadge({ children }: { children: ReactNode }) {
  return <span className="inline-flex rounded border px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wider"
    style={{ background: `${GOLD}18`, color: GOLD, borderColor: `${GOLD}55` }}>{children}</span>;
}
function Panel({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <div className={`rounded-lg border ${className}`} style={{ background: PANEL, borderColor: BORDER }}>{children}</div>;
}
function SampledCandles({ quote, current }: { quote: TerminalQuote | undefined; current: boolean }) {
  const [samples, setSamples] = useState<QuoteSample[]>([]);
  useEffect(() => {
    if (current && quote) setSamples(previous => appendObservedQuote(previous, quote));
  }, [quote, current]);
  const candles = observedCandles(samples);
  const low = candles.length ? Math.min(...candles.map(row => row.low)) : 0;
  const high = candles.length ? Math.max(...candles.map(row => row.high)) : 1;
  const margin = Math.max((high - low) * 0.1, high * 0.00001);
  const y = (value: number) => 12 + ((high + margin - value) / (high - low + margin * 2)) * 150;
  const start = candles[0]?.timestamp ?? 0;
  const slots = Math.max(8, ((candles.slice(-1)[0]?.timestamp ?? start) - start) / 60 + 1);
  const slot = 464 / slots;
  if (!candles.length) return <div className="flex h-44 items-center justify-center rounded border border-dashed text-xs text-zinc-500" style={{ borderColor: BORDER }}>Waiting for a current provider quote.</div>;
  return <div><svg viewBox="0 0 480 180" className={`h-44 w-full ${current ? '' : 'opacity-40'}`} role="img" aria-label="Observed quote samples grouped by minute; partial candles collected while this page is open">
    {[0, 1, 2, 3, 4].map(index => <line key={index} x1={8} x2={472} y1={12 + index * 38} y2={12 + index * 38} stroke={BORDER} strokeWidth={0.5} />)}
    {candles.map(row => {
      const x = 8 + ((row.timestamp - start) / 60 + 0.5) * slot;
      const color = row.close >= row.open ? CYAN : GOLD;
      return <g key={row.timestamp}><title>{new Date(row.timestamp * 1000).toISOString()} · {row.samples} observed samples</title>
        <line x1={x} x2={x} y1={y(row.high)} y2={y(row.low)} stroke={color} />
        <rect x={x - slot * 0.24} y={Math.min(y(row.open), y(row.close))} width={slot * 0.48} height={Math.max(1.5, Math.abs(y(row.open) - y(row.close)))} fill={color} /></g>;
    })}</svg><p className="text-[10px] text-zinc-500">{current ? 'Observed samples' : 'Historical samples · current quote expired'} · {samples.length} ticks · partial 1-minute candles collected in this view. Full venue OHLC history is unavailable.</p></div>;
}

export default function OverviewPage() {
  const terminal = useTerminalState();
  const market = useGlassQuotes(terminal);
  const { state, observedState, isFresh, error, freshness } = terminal;
  const connected = error === null && observedState !== null;
  const providers = readNativeBalanceEvidence(observedState?.provider_observations, connected);
  const accounts = providers.filter(provider => provider.observation.available).length;
  const capital = providers.find(provider => provider.id === 'capital');
  const capitalGbp = capital?.observation.available && capital.observation.inventoryComplete === true
    ? [...capital.visible, ...capital.zeros].filter(group => group.currency === 'GBP' && group.metric === 'Account balance').flatMap(group => group.rows) : [];
  const capitalAmount = capitalGbp.length && capitalGbp.every(row => row.balance !== null) ? capitalGbp.reduce((sum, row) => sum + row.balance!, 0) : null;
  const execution = executionGlassState(state, isFresh, market.freshness.status === 'fresh');
  const candidates = currentGlassCandidates(state, isFresh);
  const candidateCount = currentCandidateCount(observedState, connected);
  const latencyMs = endToEndMedianMs(observedState, connected);
  const [selected, setSelected] = useState('');
  const quotes = [...market.quotes].sort((a, b) => `${a.source}:${a.symbol}`.localeCompare(`${b.source}:${b.symbol}`));
  const firstQuoteKey = quotes[0] ? `${quotes[0].source}:${quotes[0].symbol}` : '';
  useEffect(() => {
    if (!selected && firstQuoteKey) setSelected(firstQuoteKey);
  }, [selected, firstQuoteKey]);
  const selectedQuote = selected ? quotes.find(quote => `${quote.source}:${quote.symbol}` === selected) : quotes[0];
  const selectedKey = selected || (selectedQuote ? `${selectedQuote.source}:${selectedQuote.symbol}` : '');
  const bid = typeof selectedQuote?.bid === 'number' && selectedQuote.bid > 0 ? selectedQuote.bid : null;
  const ask = typeof selectedQuote?.ask === 'number' && selectedQuote.ask > 0 ? selectedQuote.ask : null;
  const spread = bid !== null && ask !== null && ask >= bid ? ask - bid : null;

  return <div className="min-h-full space-y-4 p-4 text-zinc-100" style={{ background: BG }} data-overview="operator-v2">
    <h1 className="sr-only">Operator overview</h1>
    <div className="flex flex-wrap items-center justify-between gap-2 rounded-md border px-3 py-2" style={{ borderColor: `${GOLD}55`, background: `${GOLD}0d` }}>
      <div><p className="text-[11px] font-semibold uppercase tracking-[0.14em]" style={{ color: GOLD }}>Operator glass · current source evidence</p><p className="mt-0.5 text-[10px] text-zinc-400">Accounts, market events and completed runtime ticks carry separate freshness.</p></div>
      <Link to="/platform/switchboard" className="inline-flex items-center gap-1 text-xs text-zinc-300 underline">System controls <ArrowUpRight className="h-3 w-3" /></Link></div>
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      <Panel className="p-3"><div className="mb-2 flex justify-between gap-2"><span className="text-[11px] uppercase tracking-wide text-zinc-400">1) Capital GBP balance</span><EvidenceBadge>{capitalAmount === null ? 'Unavailable' : 'Provider receipt'}</EvidenceBadge></div><div className="text-2xl font-semibold tabular-nums text-white">{capitalAmount === null ? '—' : `£${capitalAmount.toFixed(2)}`}</div><p className="mt-2 text-[10px] text-zinc-500">Native Capital account balances. Combined portfolio FX valuation unavailable.</p><Link to="/trading/live" className="mt-1 inline-block text-[10px] underline" style={{ color: CYAN }}>Inspect account receipts</Link></Panel>
      <Panel className="p-3"><div className="mb-2 flex justify-between gap-2"><span className="text-[11px] uppercase tracking-wide text-zinc-400">2) Execution</span><EvidenceBadge>{freshness.status}</EvidenceBadge></div><div className="inline-flex rounded-md px-3 py-2 text-base font-black uppercase tracking-wide" style={{ background: execution.enabled ? CYAN : GOLD, color: '#0a0a0a' }}>{execution.label}</div><p className="mt-2 text-[10px] text-zinc-500">{execution.mode} · order intents {execution.intent.toLowerCase()}</p></Panel>
      <Panel className="p-3"><div className="mb-2 flex justify-between gap-2"><span className="text-[11px] uppercase tracking-wide text-zinc-400">3) Exchanges</span><EvidenceBadge>Account observations</EvidenceBadge></div><div className="text-2xl font-semibold tabular-nums text-white">{connected ? accounts : '—'} / 4</div><p className="mt-2 text-[10px] text-zinc-500">Fresh private account readbacks. Connectivity does not prove execution readiness.</p></Panel>
      <Panel className="p-3"><div className="mb-2 flex justify-between gap-2"><span className="text-[11px] uppercase tracking-wide text-zinc-400">4) Recorded latency p50</span><EvidenceBadge>{latencyMs === null ? 'No samples' : 'Recorded traces'}</EvidenceBadge></div><div className="text-2xl font-semibold tabular-nums text-white">{latencyMs === null ? '—' : `${format(latencyMs)} ms`}</div><p className="mt-2 text-[10px] text-zinc-500">Recorded instrumentation, not independently verified tick-to-ack performance. HTTP response time is separate.</p></Panel>
    </div>
    <div className="grid gap-3 lg:grid-cols-12">
      <Panel className="space-y-4 p-4 lg:col-span-3"><h2 className="text-[11px] uppercase tracking-[0.16em] text-zinc-500">Status &amp; Claim</h2>
        <div className="flex items-start gap-3"><Shield className="mt-1 h-5 w-5 shrink-0" style={{ color: GOLD }} /><div><p className="text-sm font-semibold uppercase" style={{ color: execution.enabled ? CYAN : GOLD }}>{execution.label}</p><p className="text-[11px] text-zinc-500">Real orders: {execution.orders}. Existing exposure requires provider reconciliation.</p></div></div>
        {execution.blockers.length > 0 && <ul className="space-y-1 text-[10px] text-amber-300">{execution.blockers.map(blocker => <li key={blocker}>· {blocker.replaceAll('_', ' ')}</li>)}</ul>}
        <div className="space-y-2 border-t pt-3" style={{ borderColor: BORDER }}>{[['Market stream', market.freshness.status], ['Runtime tick', freshness.status], ['Account sources', `${accounts}/4 current`], ['Candidate receipt', candidateCount === null ? 'unavailable' : `${candidateCount} current`]].map(([name, value]) => <div key={name} className="flex justify-between gap-2 text-xs"><span className="text-zinc-400">{name}</span><span style={{ color: value.includes('fresh') || value.includes('current') ? CYAN : GOLD }}>{value}</span></div>)}</div>
        <p className="text-[10px] text-zinc-500">{freshness.reason} · age {freshness.sourceAgeSec === null ? '—' : `${freshness.sourceAgeSec.toFixed(1)}s`}</p>
        <div className="space-y-2 border-t pt-3 text-xs" style={{ borderColor: BORDER }}><Link to="/trading/war-room" className="block underline" style={{ color: CYAN }}>Open analysis &amp; trading gates</Link><Link to="/platform/coverage" className="block underline text-zinc-400">Inspect all system coverage</Link></div><p className="flex items-center gap-1.5 text-[10px] text-zinc-500"><Clock className="h-3 w-3" />Source tick {freshness.sourceTimestamp ?? 'unavailable'}</p></Panel>
      <Panel className="p-4 lg:col-span-5"><div className="mb-3 flex items-center justify-between gap-2"><h2 className="flex items-center gap-2 text-sm"><Activity className="h-4 w-4" style={{ color: CYAN }} />Market Pulse</h2><EvidenceBadge>{market.freshness.status}</EvidenceBadge></div>
        <div className="mb-3 flex flex-wrap items-end justify-between gap-3"><div><label className="block text-[10px] text-zinc-500" htmlFor="overview-symbol">Observed symbol / source</label><select id="overview-symbol" value={selectedKey} onChange={event => setSelected(event.target.value)} className="mt-1 max-w-full rounded border border-zinc-700 bg-zinc-950 px-2 py-1 text-xs">
          {!quotes.length && <option value={selectedKey}>{selectedKey || 'No current quotes'}</option>}{selected && !selectedQuote && quotes.length > 0 && <option value={selected}>{selected} · expired</option>}{quotes.map(quote => <option key={`${quote.source}:${quote.symbol}`} value={`${quote.source}:${quote.symbol}`}>{quote.symbol} · {quote.source}</option>)}</select></div><div className="text-right"><p className="font-mono text-2xl font-semibold" style={{ color: CYAN }}>{format(selectedQuote?.price)}</p><p className="text-[10px] text-zinc-500">{selectedQuote?.quote ?? 'Native quote units'}</p></div></div>
        <SampledCandles key={selectedKey} quote={selectedQuote} current={Boolean(selectedQuote)} />
        <div className="mt-3 grid grid-cols-2 gap-4">{([['Best bid', bid], ['Best ask', ask]] as const).map(([label, value]) => <div key={label} className="rounded border p-2" style={{ borderColor: BORDER }}><p className="text-[10px] uppercase text-zinc-500">{label}</p><p className="font-mono text-sm" style={{ color: label === 'Best bid' ? CYAN : GOLD }}>{format(value)}</p></div>)}</div>
        <p className="mt-2 text-[10px] text-zinc-500">Spread {format(spread)} in quote units. Depth quantities are unavailable from this feed.</p><p className="mt-2 break-words text-[10px] text-zinc-500">{market.freshness.source} · {market.freshness.sourceTimestamp ?? 'timestamp unavailable'}</p></Panel>
      <div className="flex flex-col gap-3 lg:col-span-4"><Panel className="p-4"><div className="mb-3 flex items-center justify-between gap-2"><h2 className="flex items-center gap-2 text-sm"><Building2 className="h-4 w-4 text-zinc-400" />Competitors Watch</h2><EvidenceBadge>Unavailable</EvidenceBadge></div><div className="rounded border border-dashed p-4 text-xs leading-relaxed text-zinc-400" style={{ borderColor: BORDER }}>No timestamped competitor measurement source is connected. Competitor latency and rankings require sourced evidence.</div><Link to="/platform/coverage" className="mt-3 inline-block text-[11px] underline" style={{ color: CYAN }}>Inspect source coverage</Link></Panel>
        <Panel className="p-4"><div className="mb-1 flex items-center justify-between gap-2"><h2 className="flex items-center gap-2 text-sm"><Radio className="h-4 w-4" style={{ color: GOLD }} />Cash-Cow Matrix</h2><EvidenceBadge>{candidates.length ? 'Runtime derived' : 'Unavailable'}</EvidenceBadge></div><p className="mb-3 text-[10px] text-zinc-500">Current plan candidates · model confidence is not verified profitability.</p>
          <div className="overflow-auto rounded border" style={{ borderColor: BORDER }}><table className="w-full text-left text-[11px]"><thead><tr className="text-zinc-500"><th className="p-2 font-medium">Symbol / venue</th><th className="p-2 font-medium">Confidence</th><th className="p-2 font-medium">Side</th></tr></thead><tbody>{candidates.slice(0, 5).map(row => <tr key={row.key} className="border-t" style={{ borderColor: BORDER }}><td className="p-2 font-mono">{row.symbol}<small className="block text-zinc-500">{row.venue}</small></td><td className="p-2">{row.confidence === null ? '—' : `${(row.confidence * 100).toFixed(1)}%`}{row.confidence !== null && <div className="mt-1 h-1 rounded bg-zinc-800"><div className="h-full rounded" style={{ width: `${row.confidence * 100}%`, background: CYAN }} /></div>}</td><td className="p-2" style={{ color: CYAN }}>{row.side}</td></tr>)}{!candidates.length && <tr><td colSpan={3} className="p-3 text-zinc-500">No current candidate rows meet their source freshness limit.</td></tr>}</tbody></table></div><Link to="/trading/war-room" className="mt-3 inline-block text-[11px] underline" style={{ color: CYAN }}>Inspect decision evidence &amp; gates</Link></Panel></div>
    </div>
  </div>;
}
