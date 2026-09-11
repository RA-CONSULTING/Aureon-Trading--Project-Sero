import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { AlertTriangle, CheckCircle2, Key, Loader2 } from 'lucide-react';
import { Link } from 'react-router-dom';
import { useTerminalState, type TerminalState } from '@/hooks/useTerminalState';

interface CredentialStatusPanelProps {
  /** Kept for the existing War Room call site; local runtime evidence is session-independent. */
  userId?: string | null;
}

type RuntimeExchange = {
  name: string;
  flag: keyof NonNullable<TerminalState['exchanges']>;
  route: string;
  errorKey: string;
};

const RUNTIME_EXCHANGES: RuntimeExchange[] = [
  { name: 'Binance', flag: 'binance_ready', route: 'binance_spot', errorKey: 'binance' },
  { name: 'Kraken', flag: 'kraken_ready', route: 'kraken_spot', errorKey: 'kraken' },
  { name: 'Alpaca', flag: 'alpaca_ready', route: 'alpaca_spot', errorKey: 'alpaca' },
  { name: 'Capital.com', flag: 'capital_ready', route: 'capital_cfd', errorKey: 'capital' },
];

/**
 * Show the local terminal's observed route state. Credential values and the
 * Supabase session are deliberately not used here: a key being present does
 * not prove that a provider route is usable.
 */
export function CredentialStatusPanel(_props: CredentialStatusPanelProps) {
  void _props; // Keep existing call sites compatible without using a browser session as evidence.
  const { state, error } = useTerminalState();
  const runtimeAvailable = Boolean(state) && !error;
  const fresh = runtimeAvailable && state?.ok === true && state?.stale !== true && state?.data_ready === true;
  const routeReadyCount = RUNTIME_EXCHANGES.filter(
    (exchange) => state?.exchanges?.[exchange.flag] === true,
  ).length;

  if (!state && !error) {
    return (
      <Card className="bg-card/50 backdrop-blur border-primary/20">
        <CardContent className="p-6 flex items-center justify-center">
          <Loader2 className="h-6 w-6 animate-spin" />
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="bg-card/50 backdrop-blur border-primary/20">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center justify-between text-base">
          <span className="flex items-center gap-2">
            <Key className="h-4 w-4" />
            Exchange Runtime Taps
          </span>
          <Badge variant={fresh && routeReadyCount > 0 ? 'default' : 'secondary'}>
            {fresh ? `${routeReadyCount}/4 route-ready` : runtimeAvailable ? 'stale observation' : 'unavailable'}
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        {RUNTIME_EXCHANGES.map((exchange) => {
          const route = state?.exchanges?.execution_venues?.[exchange.route];
          const ready = fresh && state?.exchanges?.[exchange.flag] === true;
          const blocker = route?.blockers?.[0] || state?.errors?.[exchange.errorKey];

          return (
            <div
              key={exchange.name}
              className="flex items-center justify-between gap-3 p-2 rounded-lg bg-background/50"
            >
              <div className="flex min-w-0 items-center gap-2">
                {ready ? (
                  <CheckCircle2 className="h-4 w-4 shrink-0 text-success" />
                ) : (
                  <AlertTriangle className="h-4 w-4 shrink-0 text-warning" />
                )}
                <div className="min-w-0">
                  <span className="text-sm font-medium">{exchange.name}</span>
                  {blocker ? (
                    <p className="truncate text-[10px] text-muted-foreground" title={blocker}>
                      {blocker}
                    </p>
                  ) : null}
                </div>
              </div>

              <Badge variant="outline" className="shrink-0 text-xs">
                {ready ? 'observed ready' : !fresh ? 'source unavailable or stale' : 'held'}
              </Badge>
            </div>
          );
        })}

        {error ? (
          <div className="rounded border border-amber-500/40 bg-amber-950/20 p-2 text-xs text-amber-200">
            terminal-state read failed: {error}
          </div>
        ) : (
          <p className="pt-2 text-center text-xs text-muted-foreground">
            Local runtime route evidence only. Credential values are never returned to the browser.
          </p>
        )}

        {!runtimeAvailable ? (
          <div className="text-center pt-2">
            <Button asChild variant="outline" size="sm">
              <Link to="/settings">Open exchange settings</Link>
            </Button>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
