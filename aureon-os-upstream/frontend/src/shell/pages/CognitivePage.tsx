import { GlassPageHeader } from '@/shell/GlassPage';
import { Button } from '@/components/ui/button';
import { Brain, Radio, Network, Waypoints, Activity, BookOpen } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { LiveDataNotice } from "@/shell/Page";
import { useReadOnlyPoller } from "@/hooks/useReadOnlyPoller";
import { cognitionStore, type CognitiveObservation } from "@/services/cognitiveReads";
import { brainHistoryRecords, observedValue, observedPercent, surfaceEvidence } from "@/lib/cognitionSurfaceEvidence";
import { CognitiveReadUnavailable, CognitiveRuntimeObservations, EvidenceStamp } from "./cognitiveEvidenceCards";
import { ResearchActivityCard } from "./ResearchActivityCard";

const SURFACE_META: Record<string, { label: string; icon: typeof Brain; blurb: string }> = {
  field: { label: "HNC Field", icon: Radio, blurb: "Canonical HNC validation and source-backed field readings." },
  bus: { label: "Thought-Bus Links", icon: Waypoints, blurb: "Observed topic subscriptions and timestamped cognitive events." },
  mycelium: { label: "Mycelium Mesh", icon: Network, blurb: "Measurements from an already-running mesh when a producer publishes them." },
  connectome: { label: "Connectome Body-Map", icon: Activity, blurb: "Recorded connections and coverage, when supplied by the saved body-map." },
  brain: { label: "Miner Brain", icon: BookOpen, blurb: "Recorded prediction accuracy and knowledge memory." },
};

/** Render the human-relevant fields of one surface without leaking internals. */
function surfaceDetail(name: string, s: CognitiveObservation): { label: string; value: string }[] {
  const rows: { label: string; value: string }[] = [];
  const num = observedValue;
  if (name === "field") {
    const canonical = (s.canonical ?? {}) as Record<string, unknown>;
    const blended = (s.blended ?? {}) as Record<string, unknown>;
    const subs = (s.subfields ?? {}) as Record<string, unknown>;
    rows.push({ label: "symbolic life", value: num(canonical.symbolic_life_score) });
    rows.push({ label: "coherence γ", value: num(canonical.coherence_gamma) });
    rows.push({ label: "sub-fields", value: num(subs.count) });
    rows.push({ label: "blended contributors", value: num(blended.contributors) });
  } else if (name === "bus") {
    rows.push({ label: "subscribed topics", value: num(s.subscribed_topic_count) });
    rows.push({ label: "total subscribers", value: num(s.total_subscribers) });
    rows.push({ label: "topic families with recent events", value: num(s.cognitive_links_flowing) });
    rows.push({ label: "event window (seconds)", value: num(s.event_window_seconds) });
  } else if (name === "mycelium") {
    rows.push({ label: "coherence", value: num(s.coherence) });
    rows.push({ label: "hives", value: num(s.hive_count) });
    rows.push({ label: "agents", value: num(s.agent_count) });
    rows.push({ label: "connected systems", value: num(s.connected_count) });
  } else if (name === "connectome") {
    const map = (s.body_map ?? {}) as Record<string, unknown>;
    rows.push({ label: "nodes", value: num(map.nodes) });
    rows.push({ label: "baton linked", value: num(map.baton_linked) });
    rows.push({ label: "woven", value: num(map.woven) });
    rows.push({ label: "coverage", value: observedPercent(map.coverage_pct) });
  } else if (name === "brain") {
    const acc = (s.accuracy ?? {}) as Record<string, unknown>;
    const know = (s.knowledge ?? {}) as Record<string, unknown>;
    rows.push({ label: "predictions", value: num(acc.total_predictions) });
    rows.push({ label: "validated", value: num(acc.validated) });
    rows.push({ label: "accuracy", value: observedPercent(acc.accuracy_pct) });
    rows.push({ label: "knowledge entries", value: num(know.entries) });
  }
  return rows;
}

export default function CognitivePage() {
  const receipt = useReadOnlyPoller(cognitionStore, 10_000, 8_000);
  const data = receipt.data;
  const now = Date.now();
  const currentCount = Object.keys(SURFACE_META).filter(name => surfaceEvidence(data?.surfaces?.[name], now).current).length;
  return <div className="space-y-6">
    <GlassPageHeader title="Cognitive Systems" icon={Brain} eyebrow="Cognition &amp; LLM" description="Source-clock observations from the field, thought bus, mesh and brain, alongside dated recorded history." actions={<Button variant="outline" size="sm" onClick={receipt.refresh}>Refresh observation</Button>} />

      <LiveDataNotice />
    {receipt.loading && !data && <Skeleton className="h-36 w-full" />}
    {!receipt.loading && !data && <CognitiveReadUnavailable {...receipt} />}
    {data && <>
      <Card><CardHeader><CardTitle className="text-base">{currentCount} of {Object.keys(SURFACE_META).length} listed surfaces have current source evidence</CardTitle></CardHeader>
        <CardContent className="space-y-2 text-xs text-muted-foreground">
          <p>Source evidence is checked independently of the HTTP response. Recorded history remains labelled as history.</p>
          <p>{data.provenance?.policy}</p>
          <Badge variant="outline">Synthetic fallback: {data.provenance?.simulation_fallback_allowed === false ? 'disabled' : data.provenance?.simulation_fallback_allowed === true ? 'allowed by response policy' : 'policy unavailable'}</Badge>
        </CardContent></Card>
      <div className="grid gap-3 md:grid-cols-2">{Object.entries(SURFACE_META).map(([name, meta]) => {
        const surface = data.surfaces?.[name];
        const evidence = surfaceEvidence(surface, now);
        const Icon = meta.icon;
        return <Card key={name}><CardHeader><CardTitle className="flex items-center gap-2 text-sm"><Icon className="h-4 w-4 text-primary" />{meta.label}</CardTitle></CardHeader>
          <CardContent className="space-y-3"><p className="text-xs text-muted-foreground">{meta.blurb}</p>
            {name === 'brain' ? brainHistoryRecords(surface, now).map(component => <div key={component.name} className="space-y-2 border-t pt-2">
              <p className="text-xs font-medium">{component.name}</p><EvidenceStamp evidence={component.evidence} />
              {component.evidence.historical && <dl className="grid grid-cols-2 gap-2 text-xs">{component.rows.map(([label, value]) =>
                <div key={label}><dt className="text-muted-foreground">{label}</dt><dd className="font-mono">{value}</dd></div>)}</dl>}
            </div>) : <><EvidenceStamp evidence={evidence} />
            {evidence.displayable && surface ? <dl className="grid grid-cols-2 gap-2 text-xs">{surfaceDetail(name, surface).map(row => <div key={row.label}>
              <dt className="text-muted-foreground">{row.label}</dt><dd className="font-mono">{row.value}</dd>
            </div>)}</dl> : <p className="text-xs text-muted-foreground">Current measurements unavailable.</p>}</>}
          </CardContent></Card>;
      })}</div>
      <CognitiveRuntimeObservations sources={data.runtime_sources} process={data.process_observation} now={now} />
      <ResearchActivityCard value={data.research_activity} now={now} />
    </>}
  </div>;
}
