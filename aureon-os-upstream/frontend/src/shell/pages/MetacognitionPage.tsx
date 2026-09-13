import { GlassPageHeader } from '@/shell/GlassPage';
import { Button } from '@/components/ui/button';
/**
 * Metacognition — watch the organism sense itself.
 *
 * Polls GET /api/metacognition and builds a client-side time series so you can
 * watch the self-assessment *breathe*: self-coherence (Γ), awareness (ψ), and
 * self-disagreement (divergence) over the polling window, plus the per-signal
 * breakdown the monitor read about itself — each with its honest truth_status.
 * The monitor scores its own signals with the same Λ machinery that computes the
 * field and loops the result back in (the HNC β·Λ(t−τ) self-term); this page is
 * the read-only window onto that loop. A dormant signal shows no_data, never a
 * fabricated number.
 */

import React, { useEffect, useRef, useState } from "react";
import { Brain, Activity, Waves, GitBranch } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { LiveDataNotice } from "@/shell/Page";
import { cognitiveSourceWindow } from "@/lib/cognitiveObservationEvidence";
import { useAssessmentRead } from "@/hooks/useAssessmentRead";
import { AssessmentDependencies } from "./AssessmentDependencies";
import { CognitiveReadUnavailable } from "./cognitiveEvidenceCards";
import { type TruthStatus, TRUTH_STATUS_STYLE } from "../truthStatus";
import { currentModelSignal } from '@/lib/cognitionGlassValues';


interface Signal {
  value?: number;
  confidence?: number;
  state?: string;
  truth_status?: TruthStatus;
  blocker?: string;
}

interface Assessment {
  available: boolean;
  self_coherence: number | null;
  self_life_score: number | null;
  psi: number | null;
  consciousness_level: string | null;
  divergence: number | null;
  contributors: number;
  truth_status: TruthStatus;
  signals: Record<string, Signal>;
  provenance?: { simulation_fallback_allowed?: boolean; source_registry_count?: number };
}

interface Sample {
  coherence: number | null;
  psi: number | null;
  divergence: number | null;
}

const STATUS_STYLE = TRUTH_STATUS_STYLE;

const POLL_MS = 5000;
const MAX_SAMPLES = 60;

function StatusBadge({ status }: { status?: TruthStatus }) {
  const cls = STATUS_STYLE[status ?? "no_data"] ?? STATUS_STYLE.no_data;
  return <Badge variant="outline" className={`text-[10px] ${cls}`}>{(status ?? "no_data").replace("_", " ")}</Badge>;
}

/** Dependency-free sparkline over a numeric series; scales to its own min/max. */
function Sparkline({ values, colorClass }: { values: number[]; colorClass: string }) {
  const pts = values.filter((v) => Number.isFinite(v));
  if (pts.length < 2) return <div className="h-9" aria-hidden />;
  const w = 120;
  const h = 36;
  const min = Math.min(...pts);
  const max = Math.max(...pts);
  const span = max - min || 1;
  const d = pts
    .map((v, i) => `${(i / (pts.length - 1)) * w},${(h - ((v - min) / span) * h).toFixed(2)}`)
    .join(" ");
  return (
    <span className={colorClass}>
      <svg viewBox={`0 0 ${w} ${h}`} className="h-9 w-full" preserveAspectRatio="none" role="img"
           aria-label="trend sparkline">
        <polyline points={d} fill="none" stroke="currentColor" strokeWidth={1.5}
                  vectorEffect="non-scaling-stroke" strokeLinejoin="round" strokeLinecap="round" />
      </svg>
    </span>
  );
}

function Metric({ label, value, series, colorClass, fmt }: {
  label: string; value: number | null; series: number[]; colorClass: string;
  fmt?: (n: number) => string;
}) {
  const shown = value == null ? "—" : (fmt ? fmt(value) : value.toFixed(3));
  return (
    <Card className="flex flex-col">
      <CardHeader className="pb-1">
        <CardTitle className="text-xs font-medium text-muted-foreground">{label}</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-1 flex-col gap-2">
        <div className="font-mono text-2xl tabular-nums">{shown}</div>
        <div className="mt-auto"><Sparkline values={series} colorClass={colorClass} /></div>
      </CardContent>
    </Card>
  );
}

export default function MetacognitionPage() {
  const receipt = useAssessmentRead<Assessment>('metacognition');
  const { data } = receipt;
  const [history, setHistory] = useState<Sample[]>([]);
  const lastObservedAt = useRef<number | null>(null);
  useEffect(() => {
    const source = cognitiveSourceWindow(data);
    if (!data?.available || !source) {
      setHistory([]); lastObservedAt.current = null; return;
    }
    if (lastObservedAt.current === source.observedAt) return;
    lastObservedAt.current = source.observedAt;
    setHistory(previous => [...previous.slice(-(MAX_SAMPLES - 1)), { coherence: data.self_coherence, psi: data.psi, divergence: data.divergence }]);
  }, [data, receipt.resetVersion]);

  const coherenceSeries = history.map((s) => s.coherence ?? NaN);
  const psiSeries = history.map((s) => s.psi ?? NaN);
  const divergenceSeries = history.map((s) => s.divergence ?? NaN);

  return (
    <div className="space-y-6">
      <GlassPageHeader title="Metacognition" icon={Brain} eyebrow="Cognition &amp; LLM" description="Current software self-assessment, dependency receipts and observed trends from the dedicated monitor." actions={<Button variant="outline" size="sm" onClick={receipt.refresh}>Refresh observation</Button>} />

      <LiveDataNotice />

      {data === undefined && (
        <div className="grid gap-3 md:grid-cols-3">{Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-32 w-full" />)}</div>
      )}
      {data === null && !receipt.raw && <CognitiveReadUnavailable {...receipt} />}
      {receipt.raw && (!data || data.available === false) && <AssessmentDependencies payload={receipt.raw} />}

      {data && data.available && (
        <>
          {/* Hero — the current self-coherence + consciousness level + provenance */}
          <Card>
            <CardHeader className="pb-2">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <CardTitle className="text-base">
                  Self-coherence {data.self_coherence?.toFixed(3) ?? "—"}
                  {data.consciousness_level && (
                    <span className="ml-2 text-sm font-normal text-muted-foreground">· {data.consciousness_level}</span>
                  )}
                </CardTitle>
                <div className="flex items-center gap-2">
                  <StatusBadge status={data.truth_status} />
                  <Badge variant="outline" className="text-[10px]">{data.contributors} contributors</Badge>
                  <Badge variant="outline" className="text-[10px]">
                    synthetic fallback: {data.provenance?.simulation_fallback_allowed === true ? "allowed" : data.provenance?.simulation_fallback_allowed === false ? "off" : "unreported"}
                  </Badge>
                </div>
              </div>
            </CardHeader>
            <CardContent className="text-xs text-muted-foreground">
              The organism reading itself — updated every {POLL_MS / 1000}s, {history.length} samples in the window.
            </CardContent>
          </Card>

          {/* The three vital signs, breathing over the polling window */}
          <div className="grid gap-3 md:grid-cols-3">
            <Metric label="Self-coherence (Γ)" value={data.self_coherence} series={coherenceSeries} colorClass="text-emerald-500" />
            <Metric label="Awareness (ψ)" value={data.psi} series={psiSeries} colorClass="text-sky-500" />
            <Metric label="Self-disagreement (divergence)" value={data.divergence} series={divergenceSeries} colorClass="text-amber-500" />
          </div>

          {/* What the organism is sensing about itself */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm flex items-center gap-2"><Activity className="h-4 w-4 text-primary" /> Signals it read about itself</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid gap-2 sm:grid-cols-2">
                {Object.entries(data.signals).map(([name, sig]) => (
                  <div key={name} className="flex items-center justify-between gap-2 rounded-md border px-3 py-2">
                    <div className="flex items-center gap-2 text-sm">
                      {name === "self_agreement" ? <GitBranch className="h-3.5 w-3.5 text-muted-foreground" />
                        : <Waves className="h-3.5 w-3.5 text-muted-foreground" />}
                      <span>{name.replace(/_/g, " ")}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-xs tabular-nums">{currentModelSignal(sig.value, sig.truth_status)?.toFixed(3) ?? 'Unavailable'}</span>
                      <StatusBadge status={sig.truth_status} />
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
