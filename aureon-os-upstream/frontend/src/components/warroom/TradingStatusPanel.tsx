import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { CheckCircle2, XCircle, AlertCircle, Activity } from 'lucide-react';
import { useTerminalState } from '@/hooks/useTerminalState';
import { evaluateTradingGates } from '@/lib/tradingGateEvidence';

interface GateStatus {
  name: string;
  passed: boolean;
  available: boolean;
  value: string;
  threshold: string;
}

const PRIMARY_ROUTES = [
  ['Binance', 'binance_ready'],
  ['Kraken', 'kraken_ready'],
  ['Alpaca', 'alpaca_ready'],
  ['Capital.com', 'capital_ready'],
] as const;

function formatScanTime(value?: string | null): string {
  if (!value) return '--';
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? '--' : parsed.toLocaleTimeString();
}

export function TradingStatusPanel() {
  const { state, observedState, error, isFresh, isStreamFresh } = useTerminalState();
  const runtimeAvailable = Boolean(state) && !error;
  const evaluation = evaluateTradingGates(state, isFresh, isStreamFresh);
  const dataFresh = runtimeAvailable && evaluation.dataFresh;
  const primaryRouteCount = PRIMARY_ROUTES.filter(
    ([, flag]) => observedState?.exchanges?.[flag] === true,
  ).length;
  const routeSummary = state
    ? primaryRouteCount + '/4 primary routes in ' + (dataFresh ? 'current' : 'last') + ' observation'
    : 'route state unavailable';
  const analysisReady = runtimeAvailable && dataFresh && evaluation.analysisReady;

  const gates: GateStatus[] = [
    {
      name: 'Auris coherence',
      passed: evaluation.auris.passed,
      available: evaluation.auris.available,
      value: evaluation.auris.value,
      threshold: evaluation.auris.threshold,
    },
    {
      name: 'Lighthouse Confidence',
      passed: evaluation.lighthouse.passed,
      available: evaluation.lighthouse.available,
      value: evaluation.lighthouse.value,
      threshold: evaluation.lighthouse.threshold,
    },
    {
      name: 'LHE Required',
      passed: evaluation.lhe.passed,
      available: evaluation.lhe.available,
      value: evaluation.lhe.value,
      threshold: evaluation.lhe.threshold,
    },
    {
      name: 'QGITA Tier',
      passed: evaluation.qgita.passed,
      available: evaluation.qgita.available,
      value: evaluation.qgita.value,
      threshold: evaluation.qgita.threshold,
    },
    {
      name: 'Data Fresh',
      passed: dataFresh,
      available: runtimeAvailable,
      value: dataFresh ? 'yes' : state?.stale_reason ? 'stale' : 'no',
      threshold: 'completed tick + direct stream',
    },
    {
      name: 'Execution Gate',
      passed: evaluation.executionOpen,
      available: runtimeAvailable,
      value: evaluation.executionOpen ? 'open' : 'blocked',
      threshold: 'evidence + runtime clearance',
    },
  ];

  const allGatesPassed = gates.length > 0 && gates.every((gate) => gate.passed);
  const tradingMode = allGatesPassed && evaluation.executionOpen ? 'live' : 'hold';
  const evidenceCurrent = runtimeAvailable && dataFresh;
  const statusTone = evaluation.executionOpen ? 'live' : evidenceCurrent ? 'analysis' : 'blocked';
  const statusLabel = evaluation.executionOpen
    ? 'READY TO TRADE'
    : analysisReady
      ? 'ANALYSIS READY / EXECUTION HELD'
      : evidenceCurrent
        ? 'ANALYSIS BLOCKED / EXECUTION HELD'
        : 'DATA UNAVAILABLE / EXECUTION HELD';
  const lastScanTime = formatScanTime(state?.last_tick_completed_at);

  return (
    <Card className="bg-card/50 backdrop-blur border-primary/20">
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center justify-between text-lg">
          <span className="flex items-center gap-2">
            <Activity className="h-5 w-5 text-primary" />
            Trading Gates
          </span>
          <Badge variant={tradingMode === 'live' ? 'destructive' : 'secondary'}>
            {tradingMode === 'live' ? 'EXECUTOR ENABLED' : 'EXECUTION HOLD'}
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div
          className={
            'p-3 rounded-lg ' +
            (statusTone === 'live'
              ? 'bg-success/20 border border-success/30'
              : statusTone === 'analysis'
                ? 'bg-warning/20 border border-warning/30'
                : 'bg-destructive/20 border border-destructive/30')
          }
        >
          <div className="flex items-center justify-between">
            <span className="font-semibold">
              {statusLabel}
            </span>
            <span className="text-xs text-muted-foreground">Last tick: {lastScanTime}</span>
          </div>
          <p className="mt-1 text-xs text-muted-foreground">
            {runtimeAvailable
              ? routeSummary + '; execution: ' + evaluation.executionReason
              : error || 'Waiting for terminal-state'}
          </p>
        </div>

        <div className="space-y-2">
          {gates.map((gate) => (
            <div
              key={gate.name}
              className="flex items-center justify-between gap-3 p-2 rounded bg-muted/30"
            >
              <div className="flex items-center gap-2">
                {gate.passed ? (
                  <CheckCircle2 className="h-4 w-4 text-success" />
                ) : gate.available ? (
                  <XCircle className="h-4 w-4 text-destructive" />
                ) : (
                  <AlertCircle className="h-4 w-4 text-warning" />
                )}
                <span className="text-sm">{gate.name}</span>
              </div>
              <div className="flex items-center gap-2 text-xs">
                <span
                  className={
                    gate.passed
                      ? 'text-success'
                      : gate.available
                        ? 'text-destructive'
                        : 'text-warning'
                  }
                >
                  {gate.value}
                </span>
                <span className="text-muted-foreground">({gate.threshold})</span>
              </div>
            </div>
          ))}
        </div>

        <div className="flex items-center justify-between text-sm p-2 rounded bg-muted/30">
          <span className="flex items-center gap-2">
            <AlertCircle className="h-4 w-4 text-warning" />
            Opportunities Found
          </span>
          <Badge variant="outline">
            {evaluation.opportunities == null ? 'Unavailable' : evaluation.opportunities}
          </Badge>
        </div>
        <p className="text-center text-[11px] text-muted-foreground">
          Analysis-only runtime. Order intents and exchange mutations remain disabled.
        </p>
      </CardContent>
    </Card>
  );
}
