import { Badge } from '@/components/ui/badge';
import { Card } from '@/components/ui/card';
import { useResonanceOne } from '@/hooks/useResonanceOne';
import { RESONANCE_ONE_DOCUMENTATION, RESONANCE_ONE_SOURCE, schumannContributionStatus } from '@/lib/resonanceOneEvidence';

const metric = (value: number | null, suffix = '') => value === null ? 'Unavailable' : `${value.toLocaleString(undefined, { maximumFractionDigits: 2 })}${suffix}`;

export function ReportedEnvironmentalIndex() {
  const { observation: data, loading, error } = useResonanceOne();
  const schumannStatus = data ? schumannContributionStatus(data) : 'unavailable';
  return <Card className="space-y-4 p-6">
    <div className="flex flex-wrap items-center justify-between gap-2">
      <h3 className="font-semibold">ResonanceOne · Reported Environmental Index</h3>
      <Badge variant="outline">{data ? 'Hourly provider composite' : loading ? 'Loading provider report' : 'Unavailable'}</Badge>
    </div>
    <p className="text-sm text-muted-foreground">An index computed by ResonanceOne from Schumann, geomagnetic and solar inputs. This third-party interpretation does not establish a calibrated station frequency or amplitude.</p>
    {data ? <>
      <div className="grid gap-4 sm:grid-cols-3">
        <div><div className="text-xs text-muted-foreground">Reported activity index</div><div className="text-2xl font-mono">{metric(data.activityIndex, '/100')}</div></div>
        <div><div className="text-xs text-muted-foreground">Provider-reported Kp</div><div className="font-mono">{metric(data.kpIndex, '/9')}</div></div>
        <div><div className="text-xs text-muted-foreground">Reported solar contribution index</div><div className="font-mono">{metric(data.solarFlareIndex, '/100')}</div></div>
      </div>
      <div className="space-y-2 text-sm">
        <p>Schumann contribution: {schumannStatus === 'unavailable' ? 'Unavailable' : `${metric(data.schumannIndex, '/100')} · ${schumannStatus === 'held' ? 'held previous value' : 'provider-reported index'}`}</p>
        <p className="text-muted-foreground">{data.localInterference === true
          ? 'Provider reports local interference. The composite includes a held Schumann contribution; the original clean reading time is unavailable.'
          : data.localInterference === false ? 'Provider reports no local interference in this observation window.'
            : 'Interference status is unavailable. The Schumann contribution is withheld.'}</p>
        <p>Provider quality label: {data.dataQuality ?? 'Unavailable'} · Provider confidence score: {metric(data.confidenceScore, '/100')}</p>
        <p className="text-muted-foreground">Reported weighting: {data.weighting
          ? `Schumann ${data.weighting.schumann}% · Kp ${data.weighting.kp}% · Solar ${data.weighting.solar}%` : 'Unavailable'}</p>
      </div>
      <div className="space-y-1 text-xs text-muted-foreground">
        <p>Provider updated: {data.updatedAt} · Received: {data.receivedAt}</p>
        <p>Original hourly observation window: {data.windowStart} → {data.windowEnd}</p>
        <p>Hourly report expires after 90 minutes from the provider update or 135 minutes from the observation-window end.</p>
        <p>Reported source: {data.dataSource} · Schumann attribution: {data.attribution.schumann ?? 'Unavailable'}</p>
        <p>Kp attribution: {data.attribution.kp ?? 'Unavailable'} · Solar attribution: {data.attribution.solar ?? 'Unavailable'}</p>
      </div>
    </> : <p className="text-sm text-muted-foreground">{error ?? 'Waiting for a valid timestamped hourly provider report.'}</p>}
    <div className="flex flex-wrap gap-4 text-xs">
      <a href={RESONANCE_ONE_SOURCE} className="underline" target="_blank" rel="noreferrer">Original public report</a>
      <a href={RESONANCE_ONE_DOCUMENTATION} className="underline" target="_blank" rel="noreferrer">Provider methodology and interference policy</a>
    </div>
  </Card>;
}
