import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Activity, AlertTriangle, CheckCircle2, Server, ShieldCheck, WifiOff } from 'lucide-react';
import { useTerminalState } from '@/hooks/useTerminalState';

interface SystemHealthPanelProps {
  userId?: string;
  tradingMode?: 'paper' | 'live';
}

const PRIMARY_ROUTES = [
  ['Binance', 'binance_ready', 'binance_spot'],
  ['Kraken', 'kraken_ready', 'kraken_spot'],
  ['Alpaca', 'alpaca_ready', 'alpaca_spot'],
  ['Capital.com', 'capital_ready', 'capital_cfd'],
] as const;

function ageLabel(age?: number | null) {
  if (age == null || !Number.isFinite(age)) return 'age unavailable';
  if (age < 1) return 'just now';
  return `${Math.round(age)}s ago`;
}

export function SystemHealthPanel(_props: SystemHealthPanelProps) {
  void _props; // Legacy callers may supply props; runtime evidence is session-independent.
  const { state, error } = useTerminalState();
  const runtime = Boolean(state) && !error;
  const exchanges = state?.exchanges;
  const routes = exchanges?.execution_venues ?? {};
  const routeReadyCount = PRIMARY_ROUTES.filter(([, flag]) => exchanges?.[flag] === true).length;
  const tickFresh = runtime && state?.ok === true && state?.stale !== true && state?.data_ready === true;
  const streamFresh = runtime && state?.live_stream_cache?.fresh === true;
  const executorEnabled = tickFresh && state?.exchange_action_plan?.executor_enabled === true;

  const checks = [
    ...PRIMARY_ROUTES.map(([name, flag, route]) => {
      const routeState = routes[route];
      const ready = tickFresh && exchanges?.[flag] === true;
      const blocker = routeState?.blockers?.[0] || state?.errors?.[flag.replace('_ready', '')];
      return {
        name: `${name} route`,
        ok: ready,
        message: ready
          ? `Provider tap observed ready; ${routeState?.candidate_count ?? 'unavailable'} candidates`
          : !tickFresh ? 'Route observation unavailable or stale' : blocker || 'Route is held',
        live: ready,
      };
    }),
    {
      name: 'Trader heartbeat',
      ok: tickFresh,
      message: tickFresh
        ? `Live terminal tick ${ageLabel(state?.last_tick_age_sec)}`
        : error || state?.stale_reason || 'Waiting for terminal-state',
      live: tickFresh,
    },
    {
      name: 'Market stream',
      ok: streamFresh,
      message: streamFresh
        ? `${state?.live_stream_cache?.symbol_count ?? '--'} quotes observed at the last cache read; current quote rows expire individually`
        : state?.live_stream_cache?.reason || 'No fresh websocket tickers; REST-backed route data remains separate',
      live: streamFresh,
    },
    {
      name: 'Execution controls',
      ok: false,
      message: !tickFresh ? 'Current execution control readback unavailable' : executorEnabled
        ? 'Order executor enabled by runtime'
        : 'Order intents and exchange mutations disabled by runtime',
      live: tickFresh,
    },
  ];

  const workingCount = checks.filter((check) => check.ok).length;
  const warnings = checks.length - workingCount;

  return (
    <Card className="bg-card/50 backdrop-blur border-primary/20">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center justify-between text-base">
          <span className="flex items-center gap-2"><Server className="h-4 w-4" />System Health &amp; Data Status</span>
          <Badge variant={tickFresh ? 'default' : 'secondary'}>{runtime ? 'LOCAL RUNTIME' : 'UNAVAILABLE'}</Badge>
        </CardTitle>
        <div className="flex gap-2 mt-2 flex-wrap">
          <Badge className="bg-success/20 text-success">OK {workingCount} observed healthy</Badge>
          <Badge className="bg-warning/20 text-warning">ATTN {warnings} needs attention</Badge>
          <Badge variant={streamFresh ? 'default' : 'secondary'} className={streamFresh ? 'bg-success' : ''}>
            {streamFresh ? 'STREAM FRESH' : 'STREAM HOLD'}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {checks.map((check) => (
          <div key={check.name} className={`p-3 rounded-lg border ${check.ok ? 'border-success/30 bg-success/5' : 'border-warning/30 bg-warning/5'}`}>
            <div className="flex items-center gap-3">
              {check.ok ? <CheckCircle2 className="h-5 w-5 text-success" /> : <AlertTriangle className="h-5 w-5 text-warning" />}
              <div className="min-w-0">
                <div className="font-medium flex items-center gap-2">
                  {check.name}
                  <Badge variant="outline" className="text-xs">{check.live ? 'runtime evidence' : 'unavailable'}</Badge>
                </div>
                <p className="text-sm text-muted-foreground break-words">{check.message}</p>
              </div>
            </div>
          </div>
        ))}
        <div className="rounded-lg border border-primary/20 bg-primary/5 p-3 text-sm">
          <div className="flex items-center gap-2 font-medium"><ShieldCheck className="h-4 w-4 text-primary" />Runtime posture</div>
          <p className="mt-1 text-muted-foreground">
            {tickFresh ? `${routeReadyCount}/4 primary routes observed ready` : 'Route evidence expired or unavailable'}; writer PID {state?.runtime_writer?.pid ?? '--'}; last completed tick {ageLabel(state?.last_tick_age_sec)}.
          </p>
          <p className="mt-1 text-xs text-muted-foreground">Credentials stay in the local env file and are never returned to the browser.</p>
        </div>
        {!runtime && (
          <div className="flex items-center gap-2 rounded border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive">
            <WifiOff className="h-4 w-4" /> Terminal-state endpoint is unavailable.
          </div>
        )}
        {runtime && !tickFresh && (
          <div className="flex items-center gap-2 rounded border border-warning/30 bg-warning/5 p-3 text-sm text-warning">
            <Activity className="h-4 w-4" /> The runtime is present but its last completed tick is not fresh enough for decisions.
          </div>
        )}
      </CardContent>
    </Card>
  );
}
