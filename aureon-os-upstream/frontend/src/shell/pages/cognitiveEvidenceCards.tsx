import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { RuntimeSourcesPanel } from '@/components/RuntimeSourcesPanel';
import { observationTime, observedValue, processRowCurrent, record, readFailureMessage, surfaceEvidence, type SurfaceEvidence } from '@/lib/cognitionSurfaceEvidence';
import type { CognitiveObservation } from '@/services/cognitiveReads';

export function EvidenceStamp({ evidence }: { evidence: SurfaceEvidence }) {
  return <div className="space-y-1 text-xs text-muted-foreground">
    <Badge variant="outline">{evidence.label}</Badge>
    <p>{evidence.sourceTime ? `Source time: ${evidence.sourceTime}` : 'Source time unavailable'}</p>
    <p>{evidence.reason}</p>
  </div>;
}

export function CognitiveReadUnavailable({ httpStatus, offline, error, refresh }: {
  httpStatus: number | null; offline: boolean; error: string | null; refresh: () => void;
}) {
  return <Card><CardHeader><CardTitle className="text-base">Current response unavailable</CardTitle></CardHeader>
    <CardContent className="space-y-3 text-sm text-muted-foreground">
      <p>{readFailureMessage(httpStatus, offline, error)}</p>
      <Button variant="outline" size="sm" onClick={refresh}>Retry read</Button>
    </CardContent></Card>;
}

/** Actual Queen report fields remain separate from absent monitor schemas. */
export function CognitiveRuntimeObservations({ sources, process, now, showProcess = true }: {
  sources?: Record<string, CognitiveObservation>; process?: CognitiveObservation; now: number; showProcess?: boolean;
}) {
  const queen = sources?.queen_report;
  const queenEvidence = surfaceEvidence(queen, now);
  const consciousness = record(queen?.consciousness);
  const metacognition = record(queen?.metacognition_state);
  const queenRows: [string, unknown][] = [
    ['Report cycle', queen?.cycle], ['Reflection count', metacognition.reflection_count],
    ['Insight count', metacognition.insight_count], ['Awakening index', consciousness.awakening_index],
    ['Reported level', consciousness.level], ['Self-awareness', consciousness.self_awareness],
    ['Brain coherence', consciousness.brain_coherence], ['Learning active', consciousness.learning_active],
    ['Temporal awareness', consciousness.temporal_awareness],
  ];
  const processEvidence = surfaceEvidence(process, now, 15);
  const organs = Array.isArray(process?.organs) ? process.organs.map(record) : null;
  const metadata = Object.fromEntries(Object.entries(sources ?? {}).filter(([key]) => key === 'queen_mind' || key === 'hnc_core'));
  return <div className="space-y-3">
    <RuntimeSourcesPanel sources={metadata} />
    <Card><CardHeader><CardTitle className="text-base">Queen runtime report</CardTitle></CardHeader>
      <CardContent className="space-y-3">
        <EvidenceStamp evidence={queenEvidence} />
        <p className="text-xs text-muted-foreground">These are computed software measurements published by the Queen. They do not establish subjective consciousness or native provider validation.</p>
        {queenEvidence.current && queen?.measurement_kind === 'computed_runtime_report' ? <dl className="grid gap-2 text-sm sm:grid-cols-2 lg:grid-cols-3">
          {queenRows.map(([label, value]) => <div key={label}><dt className="text-xs text-muted-foreground">{label}</dt><dd className="font-mono">{observedValue(value)}</dd></div>)}
        </dl> : <p className="text-sm text-muted-foreground">Current Queen report measurements unavailable.</p>}
      </CardContent></Card>
    {showProcess && <Card><CardHeader><CardTitle className="text-base">Observed runtime processes</CardTitle></CardHeader>
      <CardContent className="space-y-3">
        <EvidenceStamp evidence={processEvidence} />
        <p className="text-xs text-muted-foreground">Operating-system observations of registered producers. A running process and verified identity do not prove functional health.</p>
        {processEvidence.current && organs ? <>
          <p className="text-xs text-muted-foreground">{organs.length} process records returned.</p>
          <div className="grid gap-2 sm:grid-cols-2">{organs.map((organ, index) => {
            const measured = processRowCurrent(process, organ, now);
            return <div key={`${String(organ.name)}-${index}`} className="rounded-md border p-2 text-xs">
            <p className="font-medium">{observedValue(organ.name)}</p>
            <p>Registered PID: {observedValue(organ.pid)} · Running: {measured ? observedValue(organ.pid_running) : 'Unavailable'}</p>
            <p>Identity verified: {measured ? observedValue(organ.identity_verified) : 'Unavailable'}</p>
            <p>Process measurement: {observationTime(organ.source_timestamp) || 'Unavailable'}</p>
            <p className="text-muted-foreground">Functional health: unknown</p>
          </div>; })}</div>
        </> : <p className="text-sm text-muted-foreground">Current process observations unavailable.</p>}
      </CardContent></Card>}
  </div>;
}
