import { Link } from 'react-router-dom';
import { useTerminalState } from '@/hooks/useTerminalState';
import { LiveMarketQuotes } from './warroom/LiveMarketQuotes';
import { ProviderAccountObservations } from './warroom/ProviderAccountObservations';
import { MultiExchangePanel } from './warroom/MultiExchangePanel';
import { TradingStatusPanel } from './warroom/TradingStatusPanel';
import { Badge } from './ui/badge';

export function AureonLiveDashboard() {
  const terminal = useTerminalState();
  return <div className="mx-auto max-w-7xl space-y-4 p-4 md:p-6">
    <header className="flex flex-wrap items-start justify-between gap-3">
      <div><h1 className="text-2xl font-semibold tracking-tight">Live Market Bridge</h1>
        <p className="mt-1 text-sm text-muted-foreground">Provider market observations, account receipts and runtime status.</p></div>
      <div className="flex flex-wrap gap-2"><Badge variant="outline">Market data: {terminal.streamFreshness.status}</Badge>
        <Badge variant="outline">Runtime tick: {terminal.freshness.status}</Badge></div>
    </header>
    <LiveMarketQuotes terminal={terminal} />
    <ProviderAccountObservations terminal={terminal} />
    <TradingStatusPanel />
    <MultiExchangePanel />
    <details className="rounded-lg border border-border bg-card p-4">
      <summary className="cursor-pointer font-medium">Source coverage · lifecycle observations unavailable</summary>
      <p className="mt-3 text-sm text-muted-foreground">A reconciled combined portfolio valuation, independently validated signal outcomes, legacy subsystem heartbeats and provider execution receipts are unavailable in this view. Account amounts retain their native currencies and are not summed into an assumed portfolio value.</p>
    </details>
    <p className="text-sm text-muted-foreground">This view reads the shared runtime sources. <Link className="text-primary underline" to="/trading/war-room">Open the Trading War Room</Link> for analysis evidence and full source coverage.</p>
  </div>;
}

export default AureonLiveDashboard;
