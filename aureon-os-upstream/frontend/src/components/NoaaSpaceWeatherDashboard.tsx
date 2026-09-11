import { researchNumber } from '@/lib/researchGlassEvidence';
import { Link } from 'react-router-dom';
import { Satellite } from 'lucide-react';
import { useNoaaSpaceWeather } from '@/hooks/useNoaaSpaceWeather';
import { NOAA_FEEDS, NOAA_FEED_IDS, noaaFeedView } from '@/lib/noaaObservationEvidence';
import { NoaaObservedChart, NoaaSourceReceipt, ResearchBadge, ResearchBanner, ResearchPanel, RESEARCH_BORDER as BORDER, RESEARCH_CYAN as CYAN, RESEARCH_GOLD as GOLD } from './research/ResearchGlass';

export const NoaaSpaceWeatherDashboard = () => {
  const { feeds, now } = useNoaaSpaceWeather();
  const current = NOAA_FEED_IDS.filter(feed => noaaFeedView(feeds[feed], now).available).length;
  return <div className="min-h-full space-y-4 p-4 text-zinc-100" style={{ background: '#09090b' }} data-space-weather="shipped-glass-v1" data-space-theme="zinc-gold-cyan">
    <ResearchBanner>Four independent NOAA public products. Measured fields, provider Kp estimates and official warnings remain distinct.</ResearchBanner>
    <header className="flex flex-wrap items-end justify-between gap-3 border-b pb-3" style={{ borderColor: BORDER }}><div><h1 className="flex items-center gap-2 text-xl font-semibold uppercase tracking-[0.12em] md:text-2xl" style={{ color: GOLD }}><Satellite className="h-5 w-5" style={{ color: CYAN }} />Space Weather</h1><p className="mt-1 text-[11px] uppercase tracking-wide text-zinc-500">NOAA feed research view</p></div><ResearchBadge current={current > 0}>{current} / 4 current products</ResearchBadge></header>
    <ResearchPanel className="overflow-hidden"><div className="border-b px-3 py-2.5" style={{ borderColor: BORDER, background: `${CYAN}0d` }}><h2 className="text-xs font-semibold uppercase tracking-[0.16em]" style={{ color: CYAN }}>NOAA observation feed</h2></div><div className="space-y-4 p-4">
      <div className="overflow-auto rounded-md border" style={{ borderColor: BORDER }}><table className="w-full min-w-[550px] text-left text-[11px]"><thead className="bg-zinc-950/50 text-zinc-400"><tr>{['Product', 'Current measurement', 'Units', 'Observation'].map(name => <th key={name} className="p-3 font-medium uppercase">{name}</th>)}</tr></thead><tbody>{NOAA_FEED_IDS.flatMap(feed => {
        const view = noaaFeedView(feeds[feed], now);
        return NOAA_FEEDS[feed].metrics.map(metric => <tr key={`${feed}:${metric.key}`} className="border-t" style={{ borderColor: BORDER }}><td className="p-3 text-zinc-300">{NOAA_FEEDS[feed].label}<small className="block text-zinc-500">{metric.label}</small></td><td className="p-3 font-mono" style={{ color: CYAN }}>{researchNumber(view.current?.values[metric.key])}</td><td className="p-3 text-zinc-500">{metric.unit || 'dimensionless'}</td><td className="p-3"><ResearchBadge current={view.available}>{view.status}</ResearchBadge><small className="mt-1 block text-zinc-500">{view.sourceAt ?? view.reason}</small></td></tr>);
      })}</tbody></table></div>
      <div className="grid gap-4 lg:grid-cols-2"><ResearchPanel className="space-y-3 p-3" style={{ background: 'rgba(0,0,0,0.28)' }}><h3 className="text-[11px] font-semibold uppercase" style={{ color: CYAN }}>Estimated planetary Kp history</h3><NoaaObservedChart feed="kp" receipt={feeds.kp} metric="estimated_kp" now={now} /><NoaaSourceReceipt feed="kp" receipt={feeds.kp} now={now} /></ResearchPanel><ResearchPanel className="space-y-3 p-3" style={{ background: 'rgba(0,0,0,0.28)' }}><h3 className="text-[11px] font-semibold uppercase" style={{ color: CYAN }}>Solar-wind magnetic field</h3><NoaaObservedChart feed="imf" receipt={feeds.imf} metric="bz_gsm" now={now} /><NoaaSourceReceipt feed="imf" receipt={feeds.imf} now={now} /></ResearchPanel></div>
      <ResearchPanel className="p-3"><h3 className="text-[11px] font-semibold uppercase" style={{ color: GOLD }}>NOAA Space Weather Scales &amp; Messages</h3><div className="mt-3 grid gap-3 md:grid-cols-3">{['Geomagnetic G scale', 'Solar radiation S scale', 'Radio blackout R scale'].map(label => <div key={label} className="rounded border p-3" style={{ borderColor: BORDER }}><p className="text-xs text-zinc-300">{label}</p><p className="mt-2 font-mono text-lg text-zinc-500">—</p><ResearchBadge>Official scale unavailable</ResearchBadge></div>)}</div><p className="mt-3 text-[11px] text-zinc-400">No official watch, warning, issue time or event message is present in these four connected products. A current Kp estimate is shown above without turning it into a published NOAA alert.</p></ResearchPanel>
      <div className="grid gap-4 sm:grid-cols-2"><NoaaSourceReceipt feed="wind" receipt={feeds.wind} now={now} /><NoaaSourceReceipt feed="goes" receipt={feeds.goes} now={now} /></div>
    </div></ResearchPanel>
    <footer className="flex flex-wrap justify-between gap-2 text-[11px] text-zinc-500"><span>Source histories are observed samples, not forecasts.</span><Link to="/research/solar" className="underline" style={{ color: CYAN }}>Open solar observations</Link></footer>
  </div>;
};
export default NoaaSpaceWeatherDashboard;
