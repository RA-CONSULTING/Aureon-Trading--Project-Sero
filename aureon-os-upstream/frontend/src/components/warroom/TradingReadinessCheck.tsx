import { useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { CheckCircle2, XCircle, AlertTriangle, Loader2 } from 'lucide-react';
import { useGlobalState } from '@/hooks/useGlobalState';
import { useHncCoherence } from '@/hooks/useHncCoherence';
import { useTerminalState } from '@/hooks/useTerminalState';

interface ReadinessCheck {
  name: string;
  status: 'pass' | 'fail' | 'warn' | 'checking';
  message: string;
}

const PRIMARY_ROUTES = [
  ['Binance', 'binance_ready', 'binance_spot'],
  ['Kraken', 'kraken_ready', 'kraken_spot'],
  ['Alpaca', 'alpaca_ready', 'alpaca_spot'],
  ['Capital.com', 'capital_ready', 'capital_cfd'],
] as const;

export function TradingReadinessCheck() {
  const [checks, setChecks] = useState<ReadinessCheck[]>([]);
  const [isReady, setIsReady] = useState(false);
  const globalState = useGlobalState();
  const { gamma: hncGamma } = useHncCoherence();
  const { state: terminalState, error: terminalError } = useTerminalState();

  useEffect(() => {
    const runtimeAvailable = Boolean(terminalState) && !terminalError;
    const runtimeDataFresh =
      runtimeAvailable &&
      terminalState?.data_ready === true &&
      terminalState.stale !== true;
    const routeReadyCount = PRIMARY_ROUTES.filter(
      ([, flag]) => terminalState?.exchanges?.[flag] === true,
    ).length;
    const heldRoute = PRIMARY_ROUTES.find(
      ([, flag]) => terminalState?.exchanges?.[flag] !== true,
    );
    const coherenceAvailable = hncGamma != null;
    const coherenceOk = hncGamma != null && hncGamma >= 0.35;

    const executorEnabled = terminalState?.exchange_action_plan?.executor_enabled === true;
    const runtimeTradingReady =
      terminalState?.trading_ready === true && executorEnabled === true;

    const results: ReadinessCheck[] = [
      {
        name: 'Authentication',
        status: globalState.isAuthenticated ? 'pass' : 'fail',
        message: globalState.isAuthenticated ? 'User authenticated' : 'Not logged in',
      },
      {
        name: 'Quantum Systems',
        status: runtimeDataFresh ? 'pass' : 'warn',
        message:
          runtimeDataFresh
            ? 'Runtime data path online'
            : terminalError
              ? 'Terminal-state unavailable: ' + terminalError
              : terminalState?.stale_reason
                ? 'Terminal stale: ' + terminalState.stale_reason
                : 'Systems not observed online',
      },
      {
        name: 'HNC Coherence',
        status: coherenceOk ? 'pass' : 'warn',
        message: coherenceAvailable
          ? 'Gamma = ' + (hncGamma * 100).toFixed(1) + '% (min: 35%)'
          : 'Unavailable from runtime HNC proof',
      },
      {
        name: 'Exchange Runtime Taps',
        status: routeReadyCount === PRIMARY_ROUTES.length ? 'pass' : routeReadyCount > 0 ? 'warn' : 'fail',
        message:
          routeReadyCount === PRIMARY_ROUTES.length
            ? '4/4 primary routes observed ready'
            : heldRoute
              ? routeReadyCount + '/4 routes ready; ' + heldRoute[0] + ' held'
              : 'No route state observed',
      },
      {
        name: 'Data Freshness',
        status: runtimeDataFresh ? 'pass' : 'warn',
        message: runtimeDataFresh
          ? 'Live terminal tick (' + (terminalState?.last_tick_age_sec?.toFixed(1) ?? '-') + 's old)'
          : terminalError
            ? 'Terminal-state unavailable: ' + terminalError
            : terminalState?.stale_reason ? 'Terminal stale: ' + terminalState.stale_reason : 'Live data not fresh',
      },
      {
        name: 'Trading Config',
        status: runtimeTradingReady ? 'pass' : 'warn',
        message: runtimeTradingReady
          ? 'Runtime executor enabled'
          : 'Execution disabled by runtime gates',
      },
    ];

    setChecks(results);
    setIsReady(results.every((check) => check.status === 'pass'));
  }, [
    globalState.coherence,
    globalState.isAuthenticated,
    hncGamma,
    terminalError,
    terminalState,
  ]);

  const passCount = checks.filter((check) => check.status === 'pass').length;
  const issueCount = checks.filter((check) => check.status !== 'pass').length;

  return (
    <Card className="bg-card/50 backdrop-blur border-primary/20">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center justify-between text-base">
          <span>Trading Readiness</span>
          <Badge
            variant={isReady ? 'default' : 'destructive'}
            className={isReady ? 'bg-success' : ''}
          >
            {isReady ? 'READY' : issueCount + ' ISSUES'}
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-2">
          {checks.map((check, idx) => (
            <div
              key={idx}
              className="flex items-center justify-between gap-3 p-2 rounded-lg bg-background/50"
            >
              <div className="flex items-center gap-2">
                {check.status === 'checking' && (
                  <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
                )}
                {check.status === 'pass' && <CheckCircle2 className="h-4 w-4 text-success" />}
                {check.status === 'fail' && <XCircle className="h-4 w-4 text-destructive" />}
                {check.status === 'warn' && <AlertTriangle className="h-4 w-4 text-warning" />}
                <span className="text-sm font-medium">{check.name}</span>
              </div>
              <span className="text-right text-xs text-muted-foreground">{check.message}</span>
            </div>
          ))}
        </div>

        <div className="mt-3 pt-3 border-t border-border/50 text-center">
          <p className="text-xs text-muted-foreground">
            {passCount}/{checks.length} checks passed; readiness requires every gate.
          </p>
        </div>
      </CardContent>
    </Card>
  );
}
