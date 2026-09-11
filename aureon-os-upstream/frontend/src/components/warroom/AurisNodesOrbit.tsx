import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import type { WarRoomEvidence } from '@/lib/warRoomEvidence';

export function AurisNodesOrbit({ evidence }: { evidence: WarRoomEvidence }) {
  return <Card className="bg-card/50 border-primary/20">
    <CardHeader><CardTitle className="flex items-center justify-between gap-2">Auris Nodes <Badge variant="outline">{evidence.nodes.length ? `${evidence.nodes.length} reported` : 'Unavailable'}</Badge></CardTitle></CardHeader>
    <CardContent className="space-y-4">
      <p className="text-xs text-muted-foreground">Calculated runtime readings from provider market inputs. Scores are dimensionless; configured frequencies and model weights are not sensor measurements.</p>
      {evidence.nodes.length ? <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">{evidence.nodes.map((node) => <div key={node.name} className="rounded border border-primary/20 p-3 space-y-2">
        <p className="text-sm font-medium">{node.name}</p>
        <p className="text-xl font-mono">{(node.value * 100).toFixed(1)}%</p>
        <div className="h-1.5 bg-muted rounded"><div className="h-full bg-primary rounded" style={{ width: `${node.value * 100}%` }} /></div>
        <p className="text-xs text-muted-foreground">{node.role ?? 'Role unavailable'}</p>
      </div>)}</div> : <p className="text-sm text-muted-foreground">No fresh provider-backed Auris node readings are available.</p>}
      {evidence.timestamp && <p className="text-xs text-muted-foreground break-all">Observed: {evidence.timestamp}</p>}
    </CardContent>
  </Card>;
}
