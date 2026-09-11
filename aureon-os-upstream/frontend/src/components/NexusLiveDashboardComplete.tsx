import { researchNumber } from '@/lib/researchGlassEvidence';
import { useState } from 'react';
import { Link } from 'react-router-dom';
import { BookOpen, Radio } from 'lucide-react';
import { useAurisWS } from '@/hooks/useNexusResearchStream';
import { useNoaaSpaceWeather } from '@/hooks/useNoaaSpaceWeather';
import { NOAA_FEED_IDS, noaaFeedView } from '@/lib/noaaObservationEvidence';
import { NoaaObservedChart, NoaaSourceReceipt, ResearchBadge, ResearchBanner, ResearchMetric, ResearchPanel, RESEARCH_BORDER as BORDER, RESEARCH_CYAN as CYAN, RESEARCH_GOLD as GOLD } from './research/ResearchGlass';

type Lane = 'all' | 'observed' | 'unavailable' | 'stale';
export default function NexusLiveDashboard() {
  const research = useAurisWS();
  const noaa = useNoaaSpaceWeather();
  const kp = noaaFeedView(noaa.feeds.kp, noaa.now);
  const [filter, setFilter] = useState<Lane>('all');
  const freshNoaa = NOAA_FEED_IDS.map(feed => noaaFeedView(noaa.feeds[feed], noaa.now)).filter(view => view.available);
  const sources = new Set([...freshNoaa.map(view => view.current?.source), research.auris.available ? research.auris.source : null, research.aura.available ? research.aura.source : null].filter(Boolean));
  const currentProducts = freshNoaa.length + Number(research.auris.available) + Number(research.aura.available);
  const coherence = research.auris.values.coherence_score;
  const qualifiedCoherence = typeof coherence === 'number' && coherence >= 0 && coherence <= 1 ? coherence : null;
  const panels = [
    { id: 'noaa', title: 'NOAA / SWPC', subtitle: 'Planetary Kp estimate', lane: kp.available ? 'observed' : kp.status === 'stale' ? 'stale' : 'unavailable' },
    { id: 'auris', title: 'Auris research channel', subtitle: 'Source-reported research output', lane: research.auris.available ? 'observed' : research.auris.timestamp ? 'stale' : 'unavailable' },
    { id: 'aura', title: 'Aura research channel', subtitle: 'Source-reported research output', lane: research.aura.available ? 'observed' : research.aura.timestamp ? 'stale' : 'unavailable' },
  ];
  const visible = panels.filter(panel => filter === 'all' || filter === panel.lane);
  return <div className="min-h-full space-y-4 p-4 text-zinc-100" style={{ background: '#09090b' }} data-nexus="shipped-glass-v1" data-nexus-theme="zinc-gold-cyan">
    <ResearchBanner>Observed sources and source-reported research outputs carry timestamps. Missing channels do not produce placeholder readings or scientific confidence.</ResearchBanner>
    <header className="flex flex-wrap items-end justify-between gap-3 border-b pb-3" style={{ borderColor: BORDER }}><div><h1 className="flex items-center gap-2 text-xl font-semibold uppercase tracking-[0.12em] md:text-2xl" style={{ color: GOLD }}><Radio className="h-5 w-5" />Harmonic Nexus Research Console</h1><p className="mt-1 text-[11px] uppercase tracking-[0.18em] text-zinc-500">Coherence · observation · evidence</p></div><ResearchBadge current={research.connected}>{research.connected ? 'Research transport connected' : 'Research transport unavailable'}</ResearchBadge></header>
    <div className="grid gap-4 xl:grid-cols-[1fr_280px]"><div className="space-y-4"><ResearchPanel className="p-3"><div className="mb-3 flex items-start justify-between gap-2"><div><h2 className="text-xs font-semibold uppercase tracking-[0.16em]" style={{ color: GOLD }}>Source observation feed</h2><p className="mt-1 text-[11px] text-zinc-400">Provider measurements and research algorithm outputs remain separate.</p></div><ResearchBadge current={currentProducts > 0}>{currentProducts} / 6 current channels</ResearchBadge></div>
      <div className="mb-3 flex flex-wrap gap-2">{(['all','observed','stale','unavailable'] as Lane[]).map(lane => <button key={lane} type="button" aria-pressed={filter === lane} onClick={() => setFilter(lane)} className="rounded-full border px-3 py-1 text-[10px] uppercase tracking-wide" style={{ borderColor: filter === lane ? CYAN : BORDER, color: filter === lane ? CYAN : '#a1a1aa', background: filter === lane ? `${CYAN}18` : 'rgba(0,0,0,0.25)' }}>{lane === 'all' ? 'Show all' : lane}</button>)}</div>
      <div className={`grid gap-3 ${visible.length > 1 ? 'md:grid-cols-3' : ''}`}>{visible.map(panel => {
        const channel = panel.id === 'auris' ? research.auris : research.aura;
        return <ResearchPanel key={panel.id} className="overflow-hidden"><div className="flex justify-between gap-2 border-b px-3 py-2.5" style={{ borderColor: BORDER, background: `${panel.lane === 'observed' ? CYAN : GOLD}0d` }}><div><h3 className="text-[11px] font-semibold uppercase" style={{ color: panel.lane === 'observed' ? CYAN : GOLD }}>{panel.title}</h3><p className="mt-1 text-[10px] text-zinc-500">{panel.subtitle}</p></div><ResearchBadge current={panel.lane === 'observed'}>{panel.lane}</ResearchBadge></div>
          <div className="space-y-3 p-3">{panel.id === 'noaa' ? <><NoaaObservedChart feed="kp" receipt={noaa.feeds.kp} metric="estimated_kp" now={noaa.now} /><NoaaSourceReceipt feed="kp" receipt={noaa.feeds.kp} now={noaa.now} /></> : <><div className="min-h-32 space-y-2 rounded border p-3" style={{ borderColor: BORDER }}>{channel.available ? Object.entries(channel.values).map(([name, value]) => <p key={name} className="flex flex-wrap justify-between gap-2 text-[11px]"><span className="text-zinc-400">{name.replaceAll('_', ' ')}</span><span className="font-mono" style={{ color: CYAN }}>{researchNumber(value)}</span></p>) : <p className="text-[11px] text-zinc-500">{channel.reason}</p>}</div><p className="text-[10px] text-zinc-500">Source {channel.source ?? 'unavailable'}</p><p className="break-words text-[10px] text-zinc-500">{channel.timestamp ?? 'Original source timestamp unavailable'}</p></>}</div>
        </ResearchPanel>;
      })}{!visible.length && <p className="p-4 text-xs text-zinc-500">No source channels currently match this filter.</p>}</div></ResearchPanel>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4"><ResearchMetric label="Auris coherence output" value={researchNumber(qualifiedCoherence)} unit="/ 1" detail="Source-reported normalized research score; not measured planetary coherence." available={research.auris.available && qualifiedCoherence !== null} /><ResearchMetric label="Signal-to-noise" value="—" unit="dB" detail="No measured signal/noise power receipt is provided." /><ResearchMetric label="Current channels" value={String(currentProducts)} unit="/ 6" detail="Four NOAA products and two research socket channels; freshness evaluated separately." available={true} /><ResearchMetric label="Named sources observed" value={String(sources.size)} detail="Distinct current source names; not independent scientific replications." available={true} /></div>
    </div><aside className="space-y-3"><ResearchPanel className="space-y-3 p-3"><h2 className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.16em]" style={{ color: GOLD }}><BookOpen className="h-4 w-4" />Research notes</h2><p className="rounded border p-3 text-[11px] text-zinc-400" style={{ borderColor: BORDER }}>NOAA Kp is a provider estimate. Auris and Aura values are timestamped outputs reported by their named research source.</p><p className="rounded border p-3 text-[11px] text-zinc-400" style={{ borderColor: BORDER }}>No measured SNR, cross-source scientific confidence, AGRA validation score, NASA ADS ingestion, or NCEI dataset receipt is connected on this surface.</p><p className="rounded border p-3 text-[11px] text-zinc-400" style={{ borderColor: BORDER }}>{research.error ?? (research.connected ? 'Research transport is connected; each channel must still supply valid source provenance.' : 'The research socket has no connected observation transport.')}</p><Link to="/platform/switchboard" className="block text-[11px] underline" style={{ color: CYAN }}>Open system controls</Link><Link to="/research/earth" className="block text-[11px] underline" style={{ color: CYAN }}>Inspect direct station evidence</Link><Link to="/research/space-weather" className="block text-[11px] underline" style={{ color: CYAN }}>Inspect all NOAA products</Link></ResearchPanel></aside></div>
  </div>;
}
export { NexusLiveDashboard as NexusLiveDashboardComplete };
