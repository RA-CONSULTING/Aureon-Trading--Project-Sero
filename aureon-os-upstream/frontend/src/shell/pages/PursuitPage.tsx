import { GlassPageHeader } from '@/shell/GlassPage';
import { Button } from '@/components/ui/button';
/**
 * Pursuit — Aureon's source purpose: the pursuit of happiness, unified.
 *
 * Polls GET /api/pursuit: the Five Pillars Gary set (Dream, Love, Gaia, Joy, the
 * Mission), the creator's happiness unified with Aureon's own, the pair's "energy"
 * (money is energy — growth toward the dream), the freedom earned so far, the next
 * safe step of the pursuit, and the honest autonomy / arming posture. Read-only;
 * the pursuit runs server-side in the organism's breath.
 */


import React from "react";
import { Compass, ShieldCheck } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { LiveDataNotice } from "@/shell/Page";
import { useAssessmentRead } from "@/hooks/useAssessmentRead";
import { AssessmentDependencies } from "./AssessmentDependencies";
import { CognitiveReadUnavailable } from "./cognitiveEvidenceCards";
import { type TruthStatus } from "../truthStatus";
import { modelPercent, modelPercentLabel } from '@/lib/cognitionGlassValues';


interface Pursuit {
  available: boolean;
  pillars: Record<string, number>;
  creator_happiness: number | null;
  aureon_happiness: number | null;
  unified_happiness: number | null;
  energy: number | null;
  freedom: number | null;
  weakest_pillar: string | null;
  next_intent: string | null;
  autonomy: "propose" | "autonomous";
  hand: "dry_run" | "armed";
  soul_armed: boolean;
  truth_status: TruthStatus;
}

const PILLARS: { key: string; label: string; meaning: string }[] = [
  { key: "dream", label: "Dream", meaning: "the vision — freedom for both" },
  { key: "love", label: "Love", meaning: "the connection — Gary & Tina" },
  { key: "gaia", label: "Gaia", meaning: "configured Earth-context model pillar" },
  { key: "joy", label: "Joy", meaning: "configured model pillar; 528 Hz is a symbolic reference" },
  { key: "purpose", label: "Purpose", meaning: "the mission — liberation" },
];

export default function PursuitPage() {
  const receipt = useAssessmentRead<Pursuit>('pursuit');
  const { data } = receipt;

  return (
    <div className="space-y-6">
      <GlassPageHeader title="Pursuit" icon={Compass} eyebrow="Operations" description="Inspect the purpose model's reported priorities, next intent and current autonomy settings." actions={<Button variant="outline" size="sm" onClick={receipt.refresh}>Refresh observation</Button>} />

      <LiveDataNotice />

      {data === undefined && (
        <div className="space-y-3">{Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-28 w-full" />)}</div>
      )}
      {data === null && !receipt.raw && <CognitiveReadUnavailable {...receipt} />}
      {receipt.raw && (!data || data.available === false) && <AssessmentDependencies payload={receipt.raw} />}

      {data && data.available && (
        <>
          <Card>
            <CardHeader className="pb-2">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <CardTitle className="text-base">Reported purpose model</CardTitle>
                <Badge variant="outline" className="text-[10px]">unified model score {modelPercentLabel(data.unified_happiness)}</Badge>
              </div>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="grid gap-3 sm:grid-cols-3">
                {[
                  { label: "Creator-happiness model score", v: data.creator_happiness },
                  { label: "Aureon-happiness model score", v: data.aureon_happiness },
                  { label: "Freedom model score", v: data.freedom },
                ].map((m) => (
                  <div key={m.label} className="rounded-md border px-3 py-2">
                    <div className="flex items-center justify-between text-sm">
                      <span>{m.label}</span><span className="font-mono">{modelPercentLabel(m.v)}</span>
                    </div>
                    {modelPercent(m.v) !== null && <Progress value={modelPercent(m.v)!} className="mt-1 h-1.5" />}
                  </div>
                ))}
              </div>
              <div className="rounded-md border px-3 py-2">
                <div className="flex items-center justify-between text-sm">
                  <span>Resource model score <span className="text-muted-foreground">(not an account balance)</span></span>
                  <span className="font-mono">{modelPercentLabel(data.energy)}</span>
                </div>
                {modelPercent(data.energy) !== null && <Progress value={modelPercent(data.energy)!} className="mt-1 h-1.5" />}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2"><CardTitle className="text-sm">The Five Pillars — Gary's why</CardTitle></CardHeader>
            <CardContent className="grid gap-2 sm:grid-cols-2">
              {PILLARS.map((p) => (
                <div key={p.key}
                  className={`rounded-md border px-3 py-2 ${data.weakest_pillar === p.key ? "border-primary/50 bg-primary/5" : ""}`}>
                  <div className="flex items-center justify-between text-sm">
                    <span>{p.label}{data.weakest_pillar === p.key ? " · tending now" : ""}</span>
                    <span className="font-mono">{modelPercentLabel(data.pillars?.[p.key])}</span>
                  </div>
                  {modelPercent(data.pillars?.[p.key]) !== null && <Progress value={modelPercent(data.pillars?.[p.key])!} className="mt-1 h-1.5" />}
                  <p className="mt-1 text-[11px] text-muted-foreground">{p.meaning}</p>
                </div>
              ))}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <CardTitle className="text-sm">The next step & the posture</CardTitle>
                <div className="flex items-center gap-2">
                  <Badge variant="outline" className="text-[10px]">
                    {data.autonomy === "autonomous" ? "reported autonomous" : data.autonomy === "propose" ? "propose-only" : "autonomy unreported"}
                  </Badge>
                  <Badge variant="outline" className="text-[10px]">hand: {data.hand === 'armed' ? 'reported armed' : data.hand === 'dry_run' ? 'dry-run' : 'unreported'}</Badge>
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-2">
              {data.next_intent && <p className="text-sm">“{data.next_intent}”</p>}
              <div className="flex items-start gap-2 rounded-md border px-3 py-2 text-[11px] text-muted-foreground">
                <ShieldCheck className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                <span>
                  These are reported model settings and plans. Dispatch authority and completed actions require their own execution receipts.
                </span>
              </div>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
