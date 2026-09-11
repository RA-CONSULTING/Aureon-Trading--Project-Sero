import { researchNumber } from '@/lib/researchGlassEvidence';
import { Link } from 'react-router-dom';
import { Sun } from 'lucide-react';
import { useNoaaSpaceWeather } from '@/hooks/useNoaaSpaceWeather';
import { noaaFeedView } from '@/lib/noaaObservationEvidence';
import { NoaaObservedChart, NoaaSourceReceipt, ResearchBadge, ResearchBanner, ResearchMetric, ResearchPanel, RESEARCH_BORDER as BORDER, RESEARCH_CYAN as CYAN, RESEARCH_GOLD as GOLD } from './research/ResearchGlass';

function SunDisc() {
  return <div className="relative mx-auto aspect-square w-full max-w-[280px] overflow-hidden rounded-full" style={{ background: `radial-gradient(circle at 42% 38%, #fff 0%, ${GOLD} 32%, #B8860B 64%, #18181b 100%)`, border: `2px solid ${GOLD}66`, boxShadow: `0 0 40px ${GOLD}33, inset 0 0 40px rgba(0,0,0,0.35)` }} aria-hidden="true"><div className="absolute inset-[12%] rounded-full opacity-70" style={{ background: 'radial-gradient(circle at 60% 55%, transparent 30%, rgba(0,0,0,0.35) 70%)' }} /><div className="absolute bottom-3 left-0 right-0 text-center"><ResearchBadge>Solar illustration</ResearchBadge></div></div>;
}

export const SolarWeatherDashboard = ({ title = 'Solar Weather', showHistory = true }: { title?: string; showHistory?: boolean } = {}) => {
  const { feeds, now } = useNoaaSpaceWeather();
  const wind = noaaFeedView(feeds.wind, now);
  const magnetic = noaaFeedView(feeds.imf, now);
  return <div className="min-h-full space-y-4 p-4 text-zinc-100" style={{ background: '#09090b' }} data-solar="shipped-glass-v1" data-solar-theme="zinc-gold-cyan">
    <ResearchBanner>Original NOAA observation times determine freshness. Solar artwork is a reference illustration; it is not a current instrument image.</ResearchBanner>
    <header className="flex flex-wrap items-end justify-between gap-3 border-b pb-3" style={{ borderColor: BORDER }}><div><h1 className="flex items-center gap-2 text-xl font-semibold uppercase tracking-[0.12em] md:text-2xl" style={{ color: GOLD }}><Sun className="h-5 w-5" />{title}</h1><p className="mt-1 text-[11px] uppercase tracking-wide text-zinc-500">NOAA source observations · solar and geophysical context</p></div><Link to="/research/space-weather" className="text-[11px] underline" style={{ color: CYAN }}>Open all space-weather feeds</Link></header>
    <ResearchPanel className="overflow-hidden"><div className="flex items-center justify-between gap-2 border-b px-3 py-2.5" style={{ borderColor: BORDER, background: `${CYAN}0d` }}><h2 className="text-xs font-semibold uppercase tracking-[0.16em]" style={{ color: GOLD }}>Solar Weather</h2><ResearchBadge current={wind.available}>{wind.status}</ResearchBadge></div>
      <div className="grid gap-4 p-4 lg:grid-cols-[minmax(200px,280px)_1fr]"><div className="space-y-3"><SunDisc /><p className="text-center text-[10px] text-zinc-500">No current solar image is connected.</p></div><div className="space-y-3">
        <ResearchPanel className="p-3" style={{ background: 'rgba(0,0,0,0.35)' }}><div className="flex justify-between gap-2"><p className="text-[10px] uppercase tracking-wide text-zinc-400">Solar wind speed</p><ResearchBadge current={wind.available}>{wind.status}</ResearchBadge></div><p className="mt-2 font-mono text-4xl" style={{ color: GOLD }}>{researchNumber(wind.current?.values.proton_speed)} <span className="text-sm text-zinc-500">km/s</span></p><div className="mt-3"><NoaaSourceReceipt feed="wind" receipt={feeds.wind} now={now} /></div></ResearchPanel>
        <div className="grid gap-3 sm:grid-cols-2"><ResearchMetric label="X-ray flux (0.1–0.8 nm)" value="—" unit="W/m²" detail="The connected NOAA feed set does not include GOES X-ray flux. No flare class inferred." /><ResearchMetric label="Proton flux (>10 MeV)" value="—" unit="pfu" detail="Energetic proton flux is unavailable. Solar-wind proton density is a different measurement." /></div>
      </div></div>
      <div className="grid gap-3 border-t p-4 md:grid-cols-3" style={{ borderColor: BORDER }}><ResearchMetric label="Solar wind density" value={researchNumber(wind.current?.values.proton_density)} unit="protons/cm³" detail="NOAA active solar-wind source" available={wind.current?.values.proton_density != null} /><ResearchMetric label="Solar wind temperature" value={researchNumber(wind.current?.values.proton_temperature, 0)} unit="K" detail="NOAA active solar-wind source" available={wind.current?.values.proton_temperature != null} /><ResearchMetric label="Interplanetary Bz (GSM)" value={researchNumber(magnetic.current?.values.bz_gsm)} unit="nT" detail="Independent NOAA magnetic-field receipt" available={magnetic.current?.values.bz_gsm != null} /></div>
      {showHistory && <div className="grid gap-4 border-t p-4 lg:grid-cols-2" style={{ borderColor: BORDER }}><NoaaObservedChart feed="wind" receipt={feeds.wind} metric="proton_speed" now={now} /><div className="space-y-3"><NoaaObservedChart feed="imf" receipt={feeds.imf} metric="bz_gsm" now={now} /><NoaaSourceReceipt feed="imf" receipt={feeds.imf} now={now} /></div></div>}
      <div className="border-t p-4" style={{ borderColor: BORDER }}><div className="rounded-md border p-3" style={{ borderColor: `${GOLD}66`, background: `${GOLD}0f` }}><h3 className="text-[11px] font-semibold uppercase" style={{ color: GOLD }}>Interpretation</h3><p className="mt-2 text-xs text-zinc-400">These panels report measured solar-wind conditions. Solar-activity classifications, flare risk, radiation-storm scales, CME forecasts and gap-history events require their own source products.</p></div></div>
    </ResearchPanel>
  </div>;
};
export default SolarWeatherDashboard;
