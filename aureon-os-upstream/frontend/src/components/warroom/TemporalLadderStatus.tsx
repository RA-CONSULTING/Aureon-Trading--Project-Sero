import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import type { WarRoomEvidence } from '@/lib/warRoomEvidence';

export function TemporalLadderStatus({ evidence }: { evidence: WarRoomEvidence }) {
  return <Card className="bg-card/50 border-primary/20">
    <CardHeader><CardTitle className="flex items-center justify-between gap-2 text-lg">
      Temporal Ladder <Badge variant="outline">{evidence.available && evidence.cycle.length ? 'Observed cycle' : 'Unavailable'}</Badge>
    </CardTitle></CardHeader>
    <CardContent className="space-y-3">
      <p className="text-xs text-muted-foreground">Runtime operating cycle · {evidence.timestamp ?? 'No observation timestamp'}</p>
      {evidence.cycle.length ? evidence.cycle.map((row) => <div key={row.step} className="rounded border border-border/50 p-2">
        <div className="flex items-center justify-between gap-2">
          <span className="text-sm capitalize">{row.step}</span>
          <Badge variant="outline">{row.passed === true ? 'Reported pass' : row.passed === false ? 'Needs attention' : 'Unavailable'}</Badge>
        </div>
        <p className="mt-1 text-xs text-muted-foreground break-words">{row.answer ?? 'No evidence recorded'}</p>
      </div>) : <p className="text-sm text-muted-foreground">{evidence.reason}</p>}
      <div className="flex justify-between gap-3 text-sm"><span>Execution route state</span><span>{evidence.actionState ?? 'Unavailable'}</span></div>
      <p className="text-xs text-muted-foreground">Failover and full ladder health need runtime receipts. No stable state is inferred from an empty browser registry.</p>
    </CardContent>
  </Card>;
}
