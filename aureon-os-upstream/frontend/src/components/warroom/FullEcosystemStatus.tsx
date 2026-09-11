import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Network } from 'lucide-react';
import type { WarRoomEvidence } from '@/lib/warRoomEvidence';

export function FullEcosystemStatus({ evidence }: { evidence: WarRoomEvidence }) {
  return (
    <Card className="bg-card/50 border-primary/20">
      <CardHeader><CardTitle className="flex items-center justify-between gap-2 text-lg">
        <span className="flex items-center gap-2"><Network className="h-5 w-5" /> Full Ecosystem Status</span>
        <Badge variant="outline">{evidence.available ? 'Runtime evidence' : 'Unavailable'}</Badge>
      </CardTitle></CardHeader>
      <CardContent className="space-y-4">
        <p className="text-xs text-muted-foreground">{evidence.reason}</p>
        <div className="grid grid-cols-3 gap-3">
          {([['Contributing feeds', evidence.sourceCount], ['Accepted candidate rows', evidence.symbolCount], ['Aggregated reference prices', evidence.priceCount]] as const).map(([label, value]) => (
            <div key={label} className="rounded bg-muted/30 p-3">
              <p className="text-xs text-muted-foreground">{label}</p>
              <p className="font-mono text-lg">{value ?? 'Unavailable'}</p>
            </div>
          ))}
        </div>
        <p className="text-xs text-muted-foreground">Contributing runtime feeds: {evidence.sourceNames.length ? evidence.sourceNames.join(', ') : 'Unavailable'}. Feeds may cover the same providers; reference prices are candidate aggregates.</p>
        {evidence.systems.length > 0 && <div className="grid grid-cols-2 gap-2">
          {evidence.systems.map((system) => <div key={system.name} className="rounded border border-border/50 p-2">
            <p className="text-sm capitalize">{system.name}</p>
            <p className="text-xs text-muted-foreground">{system.status}</p>
          </div>)}
        </div>}
        <p className="text-xs text-muted-foreground">System liveness requires a current runtime observation. Source code registration alone does not establish health.</p>
        {evidence.timestamp && <p className="break-all text-xs text-muted-foreground">Observed: {evidence.timestamp}</p>}
      </CardContent>
    </Card>
  );
}

export default FullEcosystemStatus;
