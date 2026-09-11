import { GlassPageHeader } from "@/shell/GlassPage";
import { Network } from "lucide-react";
import { Link } from 'react-router-dom';
import { useTerminalState } from '@/hooks/useTerminalState';
import { readWarRoomEvidence } from '@/lib/warRoomEvidence';
import { Badge } from '@/components/ui/badge';
import { LiveMarketQuotes } from './warroom/LiveMarketQuotes';
import { ProviderAccountObservations } from './warroom/ProviderAccountObservations';
import { FullEcosystemStatus } from './warroom/FullEcosystemStatus';
import { TemporalLadderStatus } from './warroom/TemporalLadderStatus';
import { QuantumStatePanel } from './warroom/QuantumStatePanel';
import { AurisNodesOrbit } from './warroom/AurisNodesOrbit';
import { UnifiedBusStatus } from './warroom/UnifiedBusStatus';

const PENDING_SOURCES = [
  'Independent Temporal Ladder heartbeats and failover receipts',
  'Measured Zero Point and Dimensional Dialler observations',
  'Measured Akashic frequency and alignment observations',
  'Reconciled Queen Hive equity and generation ledger',
];

export function SystemsIntegrationDashboard() {
  const terminal = useTerminalState();
  const evidence = readWarRoomEvidence(terminal.state, terminal.isFresh);
  return <div className="space-y-5">
    <GlassPageHeader eyebrow="Operations" title="Systems integration" icon={Network}
      description="Observed runtime analysis, market feeds and provider receipts."
      actions={<div className="flex flex-wrap gap-2">
        <Badge variant="outline">Market data: {terminal.streamFreshness.status}</Badge>
        <Badge variant="outline">Runtime tick: {terminal.freshness.status}</Badge>
        <Badge variant="outline">HNC analysis: {evidence.available ? 'Observed' : 'Unavailable'}</Badge>
      </div>} />
    <LiveMarketQuotes terminal={terminal} />
    <ProviderAccountObservations terminal={terminal} />
    <div className="grid gap-4 lg:grid-cols-2">
      <FullEcosystemStatus evidence={evidence} />
      <TemporalLadderStatus evidence={evidence} />
    </div>
    <QuantumStatePanel evidence={evidence} />
    <AurisNodesOrbit evidence={evidence} />
    <UnifiedBusStatus evidence={evidence} />
    <details className="rounded-lg border border-border bg-card p-4">
      <summary className="cursor-pointer font-medium">Source coverage · {PENDING_SOURCES.length} integrations pending observations</summary>
      <p className="mt-3 text-sm text-muted-foreground">These integrations remain unavailable until the runtime publishes the corresponding source evidence.</p>
      <ul className="mt-3 list-disc space-y-2 pl-5 text-sm text-muted-foreground">
        {PENDING_SOURCES.map((source) => <li key={source}>{source}</li>)}
      </ul>
    </details>
    <p className="text-sm text-muted-foreground">This read-only view does not activate integrations or change execution controls. <Link to="/trading/war-room" className="text-primary underline">Open the Trading War Room</Link> for execution status and complete source coverage.</p>
  </div>;
}

export default SystemsIntegrationDashboard;
