import { GlassPageHeader } from '@/shell/GlassPage';
import { Button } from '@/components/ui/button';
import { ShieldCheck, ShieldAlert, FlaskConical, Radar } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { LiveDataNotice } from "@/shell/Page";
import { useReadOnlyPoller } from "@/hooks/useReadOnlyPoller";
import { defenseStore, type DefenseModule } from "@/services/cognitiveReads";
import { benchmarkResult, observedValue, surfaceEvidence, type SurfaceEvidence } from "@/lib/cognitionSurfaceEvidence";
import { CognitiveReadUnavailable, EvidenceStamp } from "./cognitiveEvidenceCards";

const GROUP_ICON: Record<string, typeof ShieldCheck> = {
  cognitive_immune_layer: ShieldCheck, statistical_validity: FlaskConical, sensor_lane: Radar,
};
function ModuleCard({ mod, report, now }: { mod: DefenseModule; report: SurfaceEvidence; now: number }) {
  const result = benchmarkResult(mod.passed, report);
  const runtime = surfaceEvidence(mod.runtime_observation, now);
  return <Card><CardHeader><div className="flex items-start justify-between gap-2">
    <CardTitle className="text-sm">{mod.name}</CardTitle>
    <Badge variant={result === 'Recorded pass' ? 'success' : result === 'Recorded fail' ? 'destructive' : 'outline'}>{result}</Badge>
  </div></CardHeader><CardContent className="space-y-3">
    {report.historical ? <>
      <p className="text-xs text-muted-foreground">Recorded benchmark metrics</p>
      <dl className="grid grid-cols-2 gap-2 text-xs">{Object.entries(mod.metrics ?? {}).slice(0, 4).map(([name, value]) => <div key={name}>
        <dt className="text-muted-foreground">{name.replaceAll('_', ' ')}</dt><dd className="font-mono">{observedValue(value)}</dd>
      </div>)}</dl>
      <p className="text-xs text-muted-foreground">Recorded invariants: {observedValue(mod.invariants_passed)} / {observedValue(mod.invariants_total)}</p>
      {mod.evidence && <p className="text-xs text-muted-foreground">{mod.evidence}</p>}
    </> : <p className="text-sm text-muted-foreground">Dated benchmark results unavailable.</p>}
    <div className="border-t pt-3"><p className="mb-2 text-xs font-medium">Runtime trace</p><EvidenceStamp evidence={runtime} />
      {runtime.current && typeof mod.runtime_observation?.boundary === 'string' && <p className="mt-2 text-xs text-muted-foreground">{mod.runtime_observation.boundary}</p>}
      <p className="mt-2 text-xs text-muted-foreground">A recent trace does not rerun or refresh the recorded benchmark.</p>
    </div>
  </CardContent></Card>;
}
export default function DefensePage() {
  const receipt = useReadOnlyPoller(defenseStore, 15_000, 8_000);
  const data = receipt.data;
  const now = Date.now();
  const report = surfaceEvidence(data?.report_observation, now);
  return <div className="space-y-6">
    <GlassPageHeader title="Defense &amp; Validation" icon={ShieldCheck} eyebrow="Defense &amp; Validation" description="Recorded benchmark results with independently timestamped current runtime traces." actions={<Button variant="outline" size="sm" onClick={receipt.refresh}>Refresh observation</Button>} />

      <LiveDataNotice />
    {receipt.loading && !data && <Skeleton className="h-40 w-full" />}
    {!receipt.loading && !data && <CognitiveReadUnavailable {...receipt} />}
    {data && <>
      <Card><CardHeader><CardTitle className="text-base">Recorded benchmark report</CardTitle></CardHeader>
        <CardContent className="space-y-3"><EvidenceStamp evidence={report} />
          {report.historical && <p className="text-sm">{observedValue(data.counts?.passing)} recorded passes across {observedValue(data.counts?.total)} listed modules.</p>}
          <p className="text-xs text-muted-foreground">{data.note || 'Benchmark results describe the original report scope and date.'}</p>
        </CardContent></Card>
      {!data.groups && <p className="text-sm text-muted-foreground">Module catalogue unavailable.</p>}
      {(data.group_order ?? Object.keys(data.groups ?? {})).map(key => {
        const group = data.groups?.[key];
        if (!group) return null;
        const Icon = GROUP_ICON[key] ?? ShieldAlert;
        return <section key={key} className="space-y-3">
          <h2 className="flex items-center gap-2 text-lg font-semibold"><Icon className="h-4 w-4 text-primary" />{group.label || key}</h2>
          <p className="text-sm text-muted-foreground">{group.purpose}</p>
          <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">{(Array.isArray(group.modules) ? group.modules : []).map(mod =>
            <ModuleCard key={mod.key} mod={mod} report={report} now={now} />)}</div>
        </section>;
      })}
    </>}
  </div>;
}
