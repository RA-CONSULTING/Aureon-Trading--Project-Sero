import React from 'react';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { readResearchActivity, type ActivityRow } from '@/lib/researchActivityEvidence';

const display = (value: unknown) => value === true ? 'Yes' : value === false ? 'No'
  : typeof value === 'number' ? String(value) : typeof value === 'string' ? value.replaceAll('_', ' ') : 'Unavailable';
const LABELS = { recent: 'Recent recorded activity', history: 'Recorded history', dry_run: 'Dry-run record', unavailable: 'Unavailable' };

function ActivityRecord({ row, label }: { row: ActivityRow; label: string }) {
  return <div className="space-y-2 rounded-md border p-3 text-xs">
    <div className="flex flex-wrap justify-between gap-2"><p className="font-medium">{label}</p><Badge variant="outline">{LABELS[row.status]}</Badge></div>
    <p>Run started: {row.sourceTime || 'Unavailable'}</p>
    <p className="text-muted-foreground">{row.reason}</p>
    {row.status !== 'unavailable' && <>
      <p>Reported outcome: {display(row.outcome)}{row.dryRun !== null ? ' · Dry run: ' + display(row.dryRun) : ''}</p>
      <dl className="grid grid-cols-2 gap-2">{Object.entries(row.counts).map(([key, value]) => <div key={key}>
        <dt className="text-muted-foreground">Reported {key.replaceAll('_', ' ')}</dt><dd className="font-mono">{display(value)}</dd>
      </div>)}</dl>
      {Object.keys(row.ingesterCounts).length > 0 && <details><summary className="cursor-pointer">Reported ingester counters</summary>
        {Object.entries(row.ingesterCounts).map(([key, value]) => <p key={key}>{key.replaceAll('_', ' ')}: {display(value)}</p>)}
      </details>}
      {row.dryRun !== null && <details><summary className="cursor-pointer">Recorded gate decisions</summary>
        <p className="mt-1 text-muted-foreground">These are the event's reported decisions, not current permission or current input measurements.</p>
        {row.gate ? Object.entries(row.gate).map(([key, value]) => <p key={key}>{key.replaceAll('_', ' ')}: {display(value)}</p>)
          : <p>Gate stages were not recorded for this event.</p>}
      </details>}
    </>}
  </div>;
}

export function ResearchActivityCard({ value, now }: { value: unknown; now: number }) {
  const view = readResearchActivity(value, now);
  const latest = view.learning.rows.at(-1);
  return <Card><CardHeader><CardTitle className="text-base">Recorded learning and research activity</CardTitle></CardHeader>
    <CardContent className="space-y-4">
      <p className="text-xs text-muted-foreground">Existing producer journals report these outcomes. Counts do not prove committed knowledge or externally verified facts. Run-start clocks remain separate from HTTP receipt time, and activity is excluded from cognitive readiness totals.</p>
      <div className="grid gap-4 lg:grid-cols-2">
        <section className="space-y-2"><h3 className="text-sm font-medium">Learning Will journal</h3>
          <p className="text-xs text-muted-foreground">{view.learning.reason}</p>
          {view.learning.truncated && <p className="text-xs text-muted-foreground">Bounded tail; older records omitted.</p>}
          {view.learning.partialLastRecord && <p className="text-xs text-muted-foreground">An incomplete trailing record was withheld.</p>}
          {view.learning.invalidRecords !== null && view.learning.invalidRecords > 0 && <p className="text-xs text-muted-foreground">{view.learning.invalidRecords} invalid records were withheld.</p>}
          {latest ? <ActivityRecord row={latest} label="Last complete record in the returned journal tail" />
            : <p className="text-sm">Activity record unavailable.</p>}
          {view.learning.rows.length > 1 && <details><summary className="cursor-pointer text-xs">Earlier returned records ({view.learning.rows.length - 1})</summary>
            <div className="mt-2 space-y-2">{view.learning.rows.slice(0, -1).reverse().map((row, index) => <ActivityRecord key={String(row.sourceTime) + '-' + index} row={row} label="Recorded journal event" />)}</div>
          </details>}
        </section>
        <section className="space-y-2"><h3 className="text-sm font-medium">Research faculty records</h3>
          <p className="text-xs text-muted-foreground">{view.research.reason}</p>
          {view.research.available ? view.research.rows.map(row => <ActivityRecord key={row.mode} row={row} label={display(row.mode)} />)
            : <p className="text-sm">Research records unavailable.</p>}
        </section>
      </div>
    </CardContent>
  </Card>;
}
