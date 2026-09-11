import { GlassPageHeader } from '@/shell/GlassPage';
import { Button } from '@/components/ui/button';
import { Link } from "react-router-dom";
import { Brain, ArrowRight } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { LiveDataNotice } from "@/shell/Page";
import { useReadOnlyPoller } from "@/hooks/useReadOnlyPoller";
import { consciousnessStore, type ConsciousnessSurface } from "@/services/cognitiveReads";
import { observedValue, record, surfaceEvidence } from "@/lib/cognitionSurfaceEvidence";
import { currentModelSignal } from '@/lib/cognitionGlassValues';
import { safetyPostureStyle } from "../truthStatus";
import { CognitiveReadUnavailable, CognitiveRuntimeObservations, EvidenceStamp } from "./cognitiveEvidenceCards";

const CATEGORY_LABEL: Record<string, string> = {
  self_perception: "Self-perception", selfhood: "Selfhood", purpose: "Purpose",
  governance: "Governance", workforce: "The Workforce", body: "The Body",
};
const ROUTE_TO_PAGE: Record<string, string> = {
  "/api/metacognition": "/cognition/metacognition", "/api/affect": "/ops/affect",
  "/api/soul": "/ops/soul", "/api/inner-work": "/ops/inner-work",
  "/api/pursuit": "/ops/pursuit", "/api/approvals": "/ops/approvals",
  "/api/company": "/cognition/agents", "/api/organism": "/console",
};
function SurfaceCard({ surface, now }: { surface: ConsciousnessSurface; now: number }) {
  const page = ROUTE_TO_PAGE[surface.route];
  const evidence = surfaceEvidence(surface.source_observation, now);
  const posture = surface.safety_posture || 'unavailable';
  const body = <Card className="h-full transition-colors hover:border-primary/40">
    <CardHeader><CardTitle className="text-sm">{surface.label}</CardTitle></CardHeader>
    <CardContent className="space-y-3">
      <p className="text-xs text-muted-foreground">{surface.purpose}</p>
      <Badge variant="outline">{surface.configuration_available === true ? 'Configured catalogue entry' : 'Configuration unavailable'}</Badge>
      <EvidenceStamp evidence={evidence} />
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant="outline" className={`text-[10px] ${safetyPostureStyle(posture)}`}>{posture.replaceAll('_', ' ')}</Badge>
        {page && <span className="flex items-center gap-1 text-xs">Open view <ArrowRight className="h-3 w-3" /></span>}
      </div>
    </CardContent></Card>;
  return page ? <Link to={page} className="block">{body}</Link> : body;
}
export default function ConsciousnessPage() {
  const receipt = useReadOnlyPoller(consciousnessStore, 10_000, 8_000);
  const data = receipt.data;
  const now = Date.now();
  const stateEvidence = surfaceEvidence(data?.state_of_being, now);
  const axes = record(data?.state_of_being?.axes);
  return <div className="space-y-6">
    <GlassPageHeader title="Consciousness" icon={Brain} eyebrow="Cognition &amp; LLM" description="Configured capabilities and current producer observations, with catalogue definitions kept separate." actions={<Button variant="outline" size="sm" onClick={receipt.refresh}>Refresh observation</Button>} />

      <LiveDataNotice />
    {receipt.loading && !data && <Skeleton className="h-36 w-full" />}
    {!receipt.loading && !data && <CognitiveReadUnavailable {...receipt} />}
    {data && <>
      <CognitiveRuntimeObservations sources={data.runtime_sources} process={data.process_observation} now={now} />
      <Card><CardHeader><CardTitle className="text-base">State of being monitor</CardTitle></CardHeader>
        <CardContent className="space-y-3"><EvidenceStamp evidence={stateEvidence} />
          {stateEvidence.current ? <>
            <p className="text-sm">Reported wholeness: {observedValue(data.state_of_being?.wholeness)}</p>
            <dl className="flex flex-wrap gap-3">{Object.entries(axes).map(([name, axis]) => {
              const value = record(axis);
              return <div key={name}><dt className="text-xs text-muted-foreground">{name.replaceAll('_', ' ')}</dt>
                <dd className="font-mono text-sm">{observedValue(currentModelSignal(value.value, value.truth_status))}</dd></div>;
            })}</dl>
          </> : <p className="text-sm text-muted-foreground">No current dedicated state-of-being producer observation. Queen report measurements above retain their own schema.</p>}
        </CardContent></Card>
      <Card><CardHeader><CardTitle className="text-base">Capability catalogue</CardTitle></CardHeader>
        <CardContent className="space-y-2 text-sm text-muted-foreground">
          <p>Listed capabilities: {observedValue(data.counts?.total)} · Categories: {observedValue(data.counts?.category_count)}</p>
          <p>Catalogue definitions and configured safety postures describe available interfaces. Current observations are shown separately.</p>
        </CardContent></Card>
      {!data.categories && <p className="text-sm text-muted-foreground">Catalogue entries unavailable.</p>}
      {Object.entries(data.categories ?? {}).map(([name, block]) => <section key={name} className="space-y-3">
        <h2 className="text-sm font-semibold">{CATEGORY_LABEL[name] ?? name}</h2>
        <p className="text-xs text-muted-foreground">{block.purpose}</p>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">{(Array.isArray(block.surfaces) ? block.surfaces : []).map(surface =>
          <SurfaceCard key={surface.key} surface={surface} now={now} />)}</div>
      </section>)}
    </>}
  </div>;
}
