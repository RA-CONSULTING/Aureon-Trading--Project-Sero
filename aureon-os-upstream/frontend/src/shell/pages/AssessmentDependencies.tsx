import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { assessmentDependencies } from '@/lib/assessmentEvidence';
import type { AssessmentPayload } from '@/services/assessmentReads';
import { CognitiveRuntimeObservations } from './cognitiveEvidenceCards';

export function AssessmentDependencies({ payload }: { payload: AssessmentPayload }) {
  const dependency = assessmentDependencies(payload);
  return <div className="space-y-3">
    <Card><CardHeader><CardTitle className="text-base">Complete monitor observation unavailable</CardTitle></CardHeader>
      <CardContent className="space-y-3 text-sm text-muted-foreground">
        <p>The dedicated producer has not supplied a current complete assessment. Related runtime reports keep their own names and measurement meanings.</p>
        <p>Producer reason: <code>{dependency.reason}</code></p>
        <details><summary className="cursor-pointer">Required producer evidence</summary>
          {dependency.fields.length ? <ul className="mt-2 list-inside list-disc text-xs">{dependency.fields.map(field => <li key={field}>{field}</li>)}</ul>
            : <p className="mt-2 text-xs">The response did not specify required fields.</p>}
        </details>
        {dependency.note && <p className="text-xs">{dependency.note}</p>}
      </CardContent></Card>
    <CognitiveRuntimeObservations sources={payload.runtime_sources} now={Date.now()} showProcess={false} />
  </div>;
}
