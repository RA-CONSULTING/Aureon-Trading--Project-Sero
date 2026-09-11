import type { CSSProperties, ReactNode } from 'react';
import { NOAA_FEEDS, noaaFeedView, type NoaaFeed, type NoaaReceipt } from '@/lib/noaaObservationEvidence';
import { researchNumber, researchAge } from '@/lib/researchGlassEvidence';

export const RESEARCH_GOLD = '#FFB800';
export const RESEARCH_CYAN = '#00E5FF';
export const RESEARCH_BORDER = '#3f3f46';

export function ResearchPanel({ children, className = '', style }: { children: ReactNode; className?: string; style?: CSSProperties }) {
  return <div className={`rounded-lg border ${className}`} style={{ background: 'rgba(18,18,18,0.78)', borderColor: RESEARCH_BORDER, backdropFilter: 'blur(12px)', WebkitBackdropFilter: 'blur(12px)', ...style }}>{children}</div>;
}
export function ResearchBadge({ children, current = false }: { children: ReactNode; current?: boolean }) {
  const color = current ? RESEARCH_CYAN : RESEARCH_GOLD;
  return <span className="inline-flex rounded border px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wider" style={{ color, background: `${color}18`, borderColor: `${color}55` }}>{children}</span>;
}
export function ResearchBanner({ children }: { children: ReactNode }) {
  return <div className="rounded-md border px-3 py-2" style={{ borderColor: `${RESEARCH_GOLD}66`, background: `${RESEARCH_GOLD}14` }}><p className="text-[11px] font-semibold uppercase tracking-[0.14em]" style={{ color: RESEARCH_GOLD }}>Research glass · source observations</p><p className="mt-1 text-[10px] text-zinc-400">{children}</p></div>;
}
export function ResearchMetric({ label, value, unit, detail, available = false }: { label: string; value: string; unit?: string; detail: string; available?: boolean }) {
  return <ResearchPanel className="space-y-2 p-3"><div className="flex justify-between gap-2"><p className="text-[10px] font-semibold uppercase tracking-wide text-zinc-400">{label}</p><ResearchBadge current={available}>{available ? 'Source reported' : 'Unavailable'}</ResearchBadge></div><p className="font-mono text-2xl" style={{ color: available ? RESEARCH_CYAN : RESEARCH_GOLD }}>{value} <span className="text-xs text-zinc-500">{unit}</span></p><p className="text-[10px] text-zinc-500">{detail}</p></ResearchPanel>;
}
export function NoaaSourceReceipt({ feed, receipt, now }: { feed: NoaaFeed; receipt: NoaaReceipt; now: number }) {
  const view = noaaFeedView(receipt, now);
  return <div className="space-y-1 text-[10px] text-zinc-500"><p><ResearchBadge current={view.available}>{view.status}</ResearchBadge> Source age {researchAge(view.ageMs)}</p><p>{view.sourceAt ?? 'No source timestamp'} · {view.current?.source ?? 'No current source reading'}</p><p>{view.reason}</p><a className="inline-block break-all underline" style={{ color: RESEARCH_CYAN }} href={NOAA_FEEDS[feed].url} target="_blank" rel="noreferrer">NOAA {NOAA_FEEDS[feed].label} source</a></div>;
}
export function NoaaObservedChart({ feed, receipt, metric, now }: { feed: NoaaFeed; receipt: NoaaReceipt; metric: string; now: number }) {
  const view = noaaFeedView(receipt, now);
  const series = receipt.samples.map(sample => ({ timestamp: Date.parse(sample.observedAt), value: sample.values[metric] }))
    .filter((sample): sample is { timestamp: number; value: number } => Number.isFinite(sample.timestamp) && typeof sample.value === 'number' && Number.isFinite(sample.value));
  const definition = NOAA_FEEDS[feed].metrics.find(item => item.key === metric);
  if (!series.length) return <div className="flex h-36 items-center justify-center rounded border border-dashed p-3 text-xs text-zinc-500" style={{ borderColor: RESEARCH_BORDER }}>No qualified source history for {definition?.label ?? metric}.</div>;
  const low = Math.min(...series.map(row => row.value));
  const high = Math.max(...series.map(row => row.value));
  const from = series[0].timestamp;
  const until = series[series.length - 1].timestamp;
  const x = (stamp: number) => 20 + ((stamp - from) / Math.max(1, until - from)) * 440;
  const y = (value: number) => 125 - ((value - low) / Math.max(1e-9, high - low)) * 95;
  return <div className="rounded border p-2" style={{ borderColor: `${RESEARCH_CYAN}33`, background: 'rgba(0,0,0,0.35)' }}><p className="text-[10px] uppercase text-zinc-400">{definition?.label} · {definition?.unit} · {view.available ? 'Observed history' : 'Historical source data; current reading unavailable'}</p><svg viewBox="0 0 480 150" className={`h-36 w-full ${view.available ? '' : 'opacity-40'}`} role="img" aria-label={`${definition?.label ?? metric}: timestamped NOAA historical observations; not a forecast`}>
    {[30, 75, 125].map(line => <line key={line} x1={20} x2={460} y1={line} y2={line} stroke={RESEARCH_BORDER} strokeDasharray="3 3" />)}
    <polyline points={series.map(row => `${x(row.timestamp)},${y(row.value)}`).join(' ')} fill="none" stroke={RESEARCH_CYAN} strokeWidth={1.5} />
    {series.length === 1 && <circle cx={x(from)} cy={y(series[0].value)} r={3} fill={RESEARCH_CYAN} />}
    <text x={20} y={145} fill="#a1a1aa" fontSize={9}>{new Date(from).toISOString().slice(11, 16)} UTC</text><text x={390} y={145} fill="#a1a1aa" fontSize={9}>{new Date(until).toISOString().slice(11, 16)} UTC</text>
  </svg><p className="text-[10px] text-zinc-500">Range {researchNumber(low)}–{researchNumber(high)} {definition?.unit} · {series.length} observed samples</p></div>;
}
