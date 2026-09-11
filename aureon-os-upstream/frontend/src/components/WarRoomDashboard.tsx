import { useTerminalState } from '@/hooks/useTerminalState';
import { readWarRoomEvidence, evidenceNumber } from '@/lib/warRoomEvidence';
import { QuantumStatePanel } from './warroom/QuantumStatePanel';
import { AurisNodesOrbit } from './warroom/AurisNodesOrbit';
import { UnifiedBusStatus } from './warroom/UnifiedBusStatus';
import { MultiExchangePanel } from './warroom/MultiExchangePanel';
import { SystemHealthPanel } from './SystemHealthPanel';
import { TemporalLadderStatus } from './warroom/TemporalLadderStatus';
import { FullEcosystemStatus } from './warroom/FullEcosystemStatus';
import { TradingStatusPanel } from './warroom/TradingStatusPanel';
import { CredentialStatusPanel } from './warroom/CredentialStatusPanel';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Link } from 'react-router-dom';
import { LiveMarketQuotes } from './warroom/LiveMarketQuotes';
import { ProviderAccountObservations } from './warroom/ProviderAccountObservations';
import { ProbabilityFusionPanel } from './warroom/ProbabilityFusionPanel';
import { PrimeSealStatusPanel } from './warroom/PrimeSealStatusPanel';
import { PrismFrequencyPanel } from './warroom/PrismFrequencyPanel';
import { PrismStatus } from './warroom/PrismStatus';
import { EcosystemStatus } from './warroom/EcosystemStatus';

const UNAVAILABLE_SOURCES = [
  ['Gas Tank', 'A reconciled runtime funding ledger is unavailable.'],
  ['Reconciled Position Ledger', 'Complete fill and fee reconciliation is unavailable in this view. Provider-visible positions are shown separately when observed.'],
  ['Live Trade Stream', 'Provider execution receipts are unavailable in this view.'],
  ['Signal Leaderboard', 'Validated signal outcomes and performance records are unavailable.'],
  ['Historical Performance', 'A reconciled historical balance and performance series is unavailable.'],
  ['Projection Horizon', 'Observed future performance is unavailable. Simulation outputs are excluded.'],
] as const;

export default function WarRoomDashboard() {
  const terminal = useTerminalState();
  const { state, error, isFresh, freshness } = terminal;
  const evidence = readWarRoomEvidence(state, isFresh);
  const routeState = isFresh ? state?.exchange_action_plan?.trade_path_state : null;
  const executorEnabled = isFresh ? state?.exchange_action_plan?.executor_enabled : undefined;
  const publishedIntents = isFresh ? evidenceNumber(state?.exchange_action_plan?.order_intents_published) : null;
  const blockers = isFresh ? [
    ...(state?.exchange_action_plan?.global_blockers ?? []),
    ...(state?.exchange_action_plan?.runtime_clearances ?? []),
  ] : [];

  return (
    <div className="min-h-screen bg-gradient-to-br from-background via-background to-primary/5">
      <div className="container mx-auto p-4 space-y-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight text-foreground">Trading War Room</h1>
            <p className="text-muted-foreground mt-1">Provider data and runtime evidence</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Badge variant="outline">Market data: {terminal.streamFreshness.status}</Badge>
            <Badge variant="outline">Runtime tick: {freshness.status}</Badge>
            <Badge variant="outline">HNC analysis: {evidence.available ? 'Observed' : 'Unavailable'}</Badge>
          </div>
        </div>
        <LiveMarketQuotes terminal={terminal} />
        <ProviderAccountObservations terminal={terminal} />
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <EcosystemStatus />
          <PrismStatus evidence={evidence} />
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <PrismFrequencyPanel evidence={evidence} />
          <PrimeSealStatusPanel />
          <ProbabilityFusionPanel />
        </div>
        <Card className="border-primary/30 bg-primary/5">
          <CardHeader><CardTitle className="flex flex-wrap justify-between gap-2 text-lg">
            Runtime Execution Status <Badge variant="outline">{routeState ?? 'Unavailable'}</Badge>
          </CardTitle></CardHeader>
          <CardContent className="space-y-3">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
              <div><p className="text-muted-foreground">Executor configuration</p><p>{executorEnabled === true ? 'Enabled by runtime' : executorEnabled === false ? 'Disabled' : 'Unavailable'}</p></div>
              <div><p className="text-muted-foreground">Data readiness</p><p>{!isFresh ? 'Unavailable' : state?.data_ready === true ? 'Ready' : 'Not ready'}</p></div>
              <div><p className="text-muted-foreground">Published order intents</p><p>{publishedIntents ?? 'Unavailable'}</p></div>
              <div><p className="text-muted-foreground">Evidence age</p><p>{freshness.sourceAgeSec == null ? 'Unavailable' : `${Math.round(freshness.sourceAgeSec)}s`}</p></div>
            </div>
            <p className="text-xs text-muted-foreground">{error ?? freshness.reason}</p>
            {blockers.length > 0 && <div className="flex flex-wrap gap-2">{[...new Set(blockers)].map((blocker) => <Badge key={blocker} variant="outline" className="whitespace-normal break-words">{blocker}</Badge>)}</div>}
            <p className="text-sm text-muted-foreground">Runtime controls are managed by the operator. This page reads evidence and does not enable trading or release execution holds.</p>
            <p className="text-xs text-muted-foreground break-all">Source: /api/terminal-state · Completed tick: {freshness.sourceTimestamp ?? 'Unavailable'}</p>
            <Link to="/trading/hft" className="text-sm text-primary underline">Open runtime trading desk</Link>
          </CardContent>
        </Card>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <TradingStatusPanel />
          <CredentialStatusPanel />
        </div>
        <QuantumStatePanel evidence={evidence} />
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <TemporalLadderStatus evidence={evidence} />
          <FullEcosystemStatus evidence={evidence} />
        </div>
        <AurisNodesOrbit evidence={evidence} />
        <MultiExchangePanel />
        <UnifiedBusStatus evidence={evidence} />
        <SystemHealthPanel />
        <details className="rounded-lg border border-border/50 bg-card/50 p-4">
          <summary className="cursor-pointer font-medium">Source coverage · {UNAVAILABLE_SOURCES.length} panels pending verified observations</summary>
          <p className="mt-3 text-sm text-muted-foreground">These panels remain incomplete until their source observations and receipts are available.</p>
          <div className="mt-3 grid grid-cols-1 md:grid-cols-2 gap-4">
            {UNAVAILABLE_SOURCES.map(([name, reason]) => <div key={name} className="rounded border border-border/50 p-3">
              <p className="text-sm font-medium">{name} · Unavailable</p>
              <p className="text-xs text-muted-foreground mt-1">{reason}</p>
            </div>)}
          </div>
        </details>
      </div>
    </div>
  );
}
