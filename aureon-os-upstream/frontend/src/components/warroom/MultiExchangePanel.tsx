import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { CheckCircle2, AlertTriangle, TrendingUp, Zap } from 'lucide-react';
import { useTerminalState } from '@/hooks/useTerminalState';
import { readNativeBalanceEvidence, type NativeBalanceGroup } from '@/lib/nativeBalanceEvidence';

const ROUTES = [
  ['Binance', 'binance_spot'],
  ['Kraken', 'kraken_spot'],
  ['Alpaca', 'alpaca_spot'],
  ['Capital.com', 'capital_cfd'],
] as const;

const formatAmount = (value: number | null) => value === null ? 'Unavailable' : value.toLocaleString(undefined, { maximumSignificantDigits: 12 });

function NativeBalanceGroups({ groups, label }: { groups: NativeBalanceGroup[]; label: string }) {
  return <div className="max-h-48 overflow-y-auto space-y-3 pr-2" role="region" aria-label={label} tabIndex={0}>
    {groups.map(group => <div key={group.key} className="text-xs space-y-1">
      <p className="font-medium">{group.currency} · {group.metric}</p>
      {group.rows.map((row, index) => <div key={row.key} className="flex flex-wrap gap-x-3 gap-y-1 text-muted-foreground">
        <span>{group.rows.length > 1 ? `Record ${index + 1}: ` : ''}<strong className="text-foreground font-mono">{formatAmount(row.balance)}</strong></span>
        <span>Available {formatAmount(row.available)}</span>
        {row.cash !== null && <span>Cash {formatAmount(row.cash)}</span>}
        {row.buyingPower !== null && <span>Buying power {formatAmount(row.buyingPower)}</span>}
        {row.locked !== null && <span>Locked {formatAmount(row.locked)}</span>}
        {row.reason && <span>{row.reason}</span>}
      </div>)}
    </div>)}
  </div>;
}

export function MultiExchangePanel() {
  const { state, observedState, error } = useTerminalState();
  const exchanges = state?.exchanges;
  const venues = exchanges?.execution_venues ?? {};
  const active = ROUTES.filter(([, route]) => venues[route]?.ready === true).length;
  const fresh = !error && state?.ok === true && state.stale !== true && state.data_ready === true;
  const balances = readNativeBalanceEvidence(observedState?.provider_observations, error === null && observedState !== null);

  return (
    <div className="space-y-4">
      <Card className="bg-card/50 border-primary/20">
        <CardHeader className="pb-2">
          <CardTitle className="text-lg font-bold flex items-center gap-2">
            <Zap className="h-5 w-5 text-primary" />
            Multi-Exchange Status
            <Badge variant={fresh ? 'default' : 'secondary'} className="ml-auto">
              {fresh ? 'LIVE TICK' : 'STALE'}
            </Badge>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-4 mb-4">
            <div className="flex items-center gap-2">
              {fresh && active === ROUTES.length ? <CheckCircle2 className="h-5 w-5 text-success" /> : <AlertTriangle className="h-5 w-5 text-warning" />}
              <span className="text-sm">{fresh ? `${active}/${ROUTES.length} primary routes observed ready` : 'Route observation unavailable or stale'}</span>
            </div>
            <span className="text-xs text-muted-foreground">
              tick age {state?.last_tick_age_sec == null ? '--' : `${Math.round(state.last_tick_age_sec)}s`}
            </span>
          </div>
          <div className="grid grid-cols-2 gap-3">
            {ROUTES.map(([name, route]) => {
              const venue = venues[route];
              const ready = fresh && venue?.ready === true;
              const blocker = venue?.blockers?.[0];
              return (
                <div key={route} className={`p-3 rounded-lg border ${ready ? 'bg-success/10 border-success/30' : 'bg-warning/10 border-warning/30'}`}>
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm font-bold">{name}</span>
                    <Badge variant={ready ? 'default' : 'secondary'} className="text-xs">{!fresh ? 'STALE / UNAVAILABLE' : ready ? 'READY' : 'HELD'}</Badge>
                  </div>
                  <div className="text-xs text-muted-foreground space-y-1">
                    <div className="flex justify-between"><span>Path:</span><span className="font-mono">{fresh ? venue?.trade_path_state || 'unavailable' : 'observation expired'}</span></div>
                    <div className="flex justify-between"><span>Candidates:</span><span className="font-mono">{fresh ? venue?.candidate_count ?? '--' : '--'} ({fresh ? venue?.ready_candidate_count ?? '--' : '--'} ready)</span></div>
                    {blocker ? <div className="truncate text-warning" title={blocker}>{blocker}</div> : null}
                  </div>
                </div>
              );
            })}
          </div>
          {error ? <p className="mt-3 text-xs text-destructive">{error}</p> : null}
          <p className="mt-3 text-xs text-muted-foreground">
            Route readiness is sourced from the local trader heartbeat. This panel does not invent balances or treat a key as proof of a usable route.
          </p>
        </CardContent>
      </Card>

      <Card className="bg-card/50 border-primary/20">
        <CardHeader className="pb-2">
          <CardTitle className="text-lg font-bold flex items-center gap-2">
            <TrendingUp className="h-5 w-5 text-primary" />
            Consolidated Balances
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="mb-3 text-xs text-muted-foreground">Native provider balances, grouped by currency and metric. No currency conversion or combined portfolio valuation is applied.</p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">{balances.map(provider => {
            const receipt = provider.observation;
            return <div key={provider.id} className="rounded-lg border border-primary/20 bg-primary/5 p-3 space-y-2">
              <div className="flex justify-between gap-2"><span className="text-sm font-medium">{provider.name}</span><Badge variant="outline">{receipt.available ? 'Observed' : 'Unavailable'}</Badge></div>
              {receipt.available ? <>
                <p className="text-xs text-muted-foreground">{receipt.count} observed records · {receipt.inventoryComplete ? 'Complete provider inventory' : 'Partial provider inventory'}</p>
                {provider.visible.length > 0 && <NativeBalanceGroups groups={provider.visible} label={`${provider.name} native balances`} />}
                {provider.zeroCount > 0 && <details className="rounded border border-border/50 p-2">
                  <summary className="cursor-pointer text-xs">Zero balances ({provider.zeroCount})</summary>
                  <div className="mt-2"><NativeBalanceGroups groups={provider.zeros} label={`${provider.name} zero native balances`} /></div>
                </details>}
                {receipt.count === 0 && <p className="text-xs text-muted-foreground">Provider returned an empty balance inventory.</p>}
              </> : <p className="text-xs text-muted-foreground">{receipt.reason}</p>}
              <p className="text-xs text-muted-foreground break-words">{receipt.source ?? 'Source unavailable'} · {receipt.timestamp === null ? 'No source timestamp' : new Date(receipt.timestamp * 1_000).toISOString()}
                {receipt.timestampKind === 'local_http_receipt' ? ' · local HTTP receipt; provider time absent' : ''}
                {receipt.available && receipt.ageSeconds !== null ? ` · ${Math.max(0, Math.round(receipt.ageSeconds))}s old` : ''}</p>
            </div>;
          })}</div>
        </CardContent>
      </Card>
    </div>
  );
}
