import { useState, useEffect, useRef } from 'react';
import { Card } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Badge } from '@/components/ui/badge';
import { LineChart, Line, BarChart, Bar, PieChart, Pie, Cell, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { createAnalyticsAccountScope, readTradingAnalytics, type AnalyticsRange, type AnalyticsReceipt } from '@/lib/tradingAnalyticsEvidence';
import { api } from '@/services/apiClient';
import { ProviderAccountObservations } from './warroom/ProviderAccountObservations';
import { useTerminalState } from '@/hooks/useTerminalState';
import { ChartNoAxesCombined, RefreshCw } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { GlassPageHeader } from '@/shell/GlassPage';
import { supabase } from '@/integrations/supabase/client';

const decimal = (value: number | null, digits = 2) => value === null || !Number.isFinite(value) ? 'Unavailable' : value.toFixed(digits);

export const TradingAnalytics = () => {
  const terminal = useTerminalState();
  const [timeRange, setTimeRange] = useState<AnalyticsRange>('7d');
  const [receipt, setReceipt] = useState<AnalyticsReceipt | null>(null);
  const [now, setNow] = useState(Date.now);
  const [refreshVersion, setRefreshVersion] = useState(0);
  const accountScope = useRef(createAnalyticsAccountScope());

  useEffect(() => {
    const scope = accountScope.current;
    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      if (!scope.observeAccount(session?.user?.id ?? null)) return;
      setReceipt(null);
      setRefreshVersion(value => value + 1);
    });
    return () => { scope.stop(); subscription.unsubscribe(); };
  }, []);

  useEffect(() => {
    const scope = accountScope.current;
    const ticket = scope.begin();
    setReceipt(null);
    api.get<Record<string, unknown>>(`/api/trading/closed-position-analytics?range=${encodeURIComponent(timeRange)}`, {
      signal: ticket.controller.signal,
      timeoutMs: 10_000,
    }).then(payload => {
      if (!scope.current(ticket)) return;
      const receivedAt = Date.now();
      setNow(receivedAt);
      const records = Array.isArray(payload.records) ? payload.records : null;
      const count = typeof payload.count === 'number' && Number.isInteger(payload.count) ? payload.count : null;
      setReceipt({
        range: timeRange,
        receivedAt,
        data: records,
        error: payload.available !== false ? null : payload.reason ?? 'Closed-position analytics backend query failed.',
        count,
        status: 200,
        available: payload.available === true,
        reason: typeof payload.reason === 'string' ? payload.reason : null,
      });
    }).catch(error => {
      if (!scope.current(ticket)) return;
      const receivedAt = Date.now();
      setNow(receivedAt);
      setReceipt({
        range: timeRange,
        receivedAt,
        data: null,
        error,
        count: null,
        status: typeof error === 'object' && error !== null && typeof (error as { status?: unknown }).status === 'number' ? (error as { status: number }).status : 0,
        available: false,
        reason: 'Closed-position analytics local backend is unavailable.',
      });
    });
    return () => ticket.controller.abort();
  }, [timeRange, refreshVersion]);

  // Age the existing receipt without adding polling or refreshing its source time.
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1_000);
    return () => window.clearInterval(timer);
  }, []);

  const evidence = readTradingAnalytics(receipt, timeRange, now);
  const metrics = evidence.metrics;
  const amount = (value: number | null) => value === null ? 'Unavailable' : `${decimal(value)} ${evidence.currency}`;

  return (
    <div className="space-y-6">
      <GlassPageHeader icon={ChartNoAxesCombined} eyebrow="Trading records" title="Trading Analytics"
        description="Recorded closed positions, source dates and provider account observations."
        actions={<Button variant="outline" disabled={receipt === null} onClick={() => setRefreshVersion(value => value + 1)}>
          <RefreshCw className={`mr-2 h-4 w-4 ${receipt === null ? 'animate-spin' : ''}`} />{receipt === null ? 'Reading…' : 'Refresh records'}
        </Button>} />
      <div className="flex flex-wrap gap-2">
        {(['24h', '7d', '30d', 'all'] as const).map(range => (
          <button key={range} onClick={() => setTimeRange(range)}
            className={`px-4 py-2 rounded-lg font-medium transition-colors ${timeRange === range ? 'bg-primary text-primary-foreground' : 'bg-muted hover:bg-muted/80'}`}>
            {range === '24h' ? '24 Hours' : range === '7d' ? '7 Days' : range === '30d' ? '30 Days' : 'All Time'}
          </button>
        ))}
      </div>
      <Card className="p-4 space-y-2" aria-live="polite">
        <div className="flex flex-wrap items-center gap-2"><h2 className="font-semibold">Recorded closed-position analytics</h2><Badge variant="outline">{evidence.status}</Badge></div>
        <p className="text-sm text-muted-foreground">{evidence.reason}</p>
        {evidence.receivedAt !== null && evidence.status !== 'unavailable' && (
          <p className="text-xs text-muted-foreground">Database query received {new Date(evidence.receivedAt).toISOString()}. This view expires after 5 minutes.</p>
        )}
        {evidence.count !== null && <p className="font-medium">{evidence.count} recorded closed positions in this account view</p>}
        {evidence.status !== 'observed' && <p className="text-sm text-muted-foreground">Live provider account and position receipts remain below. Closed-position P&amp;L needs verified closed rows with source timestamps, provider fill/fee reconciliation, and a configured database query.</p>}
      </Card>
      <ProviderAccountObservations terminal={terminal} />
      {metrics && <>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <Card className="p-4"><p className="text-sm text-muted-foreground">Reported total P&amp;L</p><p className="text-2xl font-bold">{amount(metrics.totalPnL)}</p></Card>
          <Card className="p-4"><p className="text-sm text-muted-foreground">Recorded win rate</p><p className="text-2xl font-bold">{decimal(metrics.winRate, 1)}%</p>
            <p className="text-xs text-muted-foreground">{metrics.wins} wins / {metrics.losses} losses / {metrics.breakeven} breakeven</p></Card>
          <Card className="p-4"><p className="text-sm text-muted-foreground">Reported average P&amp;L</p><p className="text-2xl font-bold">{amount(metrics.avgPnL)}</p></Card>
          <Card className="p-4"><p className="text-sm text-muted-foreground">Reported profit factor</p><p className="text-2xl font-bold">{decimal(metrics.profitFactor)}</p>
            <p className="text-xs text-muted-foreground">Recorded average duration: {decimal(metrics.avgDurationMinutes, 0)}m</p></Card>
        </div>
        {!evidence.currency && <p className="text-sm text-muted-foreground">A common P&amp;L currency is not recorded. Monetary totals, charts and comparisons are unavailable.</p>}
        <Tabs defaultValue="performance" className="w-full">
          <TabsList><TabsTrigger value="performance">Performance</TabsTrigger><TabsTrigger value="distribution">Distribution</TabsTrigger>
            <TabsTrigger value="symbols">By Symbol</TabsTrigger><TabsTrigger value="trades">Close Records</TabsTrigger></TabsList>
          <TabsContent value="performance" className="space-y-4">
            {evidence.timeSeries.length > 0 ? <>
              <Card className="p-6"><h3 className="text-lg font-semibold mb-4">Cumulative reported P&amp;L ({evidence.currency})</h3>
                <ResponsiveContainer width="100%" height={300}><LineChart data={evidence.timeSeries}>
                  <CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="date" /><YAxis /><Tooltip /><Legend />
                  <Line type="linear" dataKey="cumulativePnL" stroke="hsl(var(--primary))" strokeWidth={2} name="Cumulative reported P&L" />
                </LineChart></ResponsiveContainer></Card>
              <Card className="p-6"><h3 className="text-lg font-semibold mb-4">Daily reported P&amp;L ({evidence.currency}, UTC)</h3>
                <ResponsiveContainer width="100%" height={300}><BarChart data={evidence.timeSeries}>
                  <CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="date" /><YAxis /><Tooltip /><Legend /><Bar dataKey="pnl" name="Daily reported P&L">
                    {evidence.timeSeries.map(day => <Cell key={day.date} fill={day.pnl >= 0 ? 'hsl(var(--chart-2))' : 'hsl(var(--destructive))'} />)}
                  </Bar></BarChart></ResponsiveContainer></Card>
            </> : <Card className="p-6 text-muted-foreground">P&amp;L charts unavailable: a common recorded currency and finite amounts are required.</Card>}
          </TabsContent>
          <TabsContent value="distribution" className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Card className="p-6"><h3 className="text-lg font-semibold mb-4">Recorded outcome distribution</h3>
              <ResponsiveContainer width="100%" height={300}><PieChart><Pie data={[
                { name: 'Wins', value: metrics.wins }, { name: 'Losses', value: metrics.losses }, { name: 'Breakeven', value: metrics.breakeven },
              ]} dataKey="value" label={entry => `${entry.name}: ${entry.value}`} labelLine={false} outerRadius={80}>
                <Cell fill="hsl(var(--chart-2))" /><Cell fill="hsl(var(--destructive))" /><Cell fill="hsl(var(--muted-foreground))" />
              </Pie><Tooltip /></PieChart></ResponsiveContainer></Card>
            <Card className="p-6 space-y-4"><h3 className="text-lg font-semibold">Reported outcome amounts</h3>
              <p>Average win: {amount(metrics.avgWin)}</p><p>Average loss: {amount(metrics.avgLoss)}</p>
              <p>Average win/loss ratio: {metrics.avgWin !== null && metrics.avgLoss !== null && metrics.avgLoss > 0 ? decimal(metrics.avgWin / metrics.avgLoss) : 'Unavailable'}</p>
            </Card>
          </TabsContent>
          <TabsContent value="symbols"><Card className="p-6 space-y-3"><h3 className="text-lg font-semibold">Recorded outcomes by symbol</h3>
            {evidence.symbols.map(symbol => <div key={`${symbol.exchange}:${symbol.symbol}`} className="flex flex-wrap items-center justify-between gap-3 p-3 border rounded-lg">
              <div><span className="font-semibold">{symbol.symbol}</span><p className="text-xs text-muted-foreground">{symbol.exchange}</p></div>
              <Badge variant="outline">{symbol.trades} records</Badge><span>{decimal(symbol.winRate, 1)}% recorded wins</span><span>{amount(symbol.pnl)}</span>
            </div>)}
          </Card></TabsContent>
          <TabsContent value="trades" className="space-y-4">
            {evidence.best && evidence.worst && <Card className="p-4">Highest reported P&amp;L: {evidence.best.symbol} {amount(evidence.best.pnl)}. Lowest: {evidence.worst.symbol} {amount(evidence.worst.pnl)}.</Card>}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">{evidence.positions.map(position => <Card key={position.id} className="p-4 space-y-2">
              <div className="flex items-center justify-between"><span className="font-semibold">{position.symbol} · {position.exchange}</span><Badge variant="outline">{position.side}</Badge></div>
              <p>Recorded entry: {decimal(position.entryPrice)} · Recorded exit: {decimal(position.exitPrice)}</p>
              <p>Reported P&amp;L: {decimal(position.pnl)} {position.currency ?? '(currency unreported)'}</p>
              <p className="text-xs text-muted-foreground">Price currency is not recorded in this view.</p>
              <p className="text-sm">Close reason: {position.closeReason ?? 'Unavailable'}</p>
              <p className="text-xs text-muted-foreground">Closed {new Date(position.closedAt).toISOString()}</p>
              <p className="text-xs text-muted-foreground break-all">Source: {position.source} · {new Date(position.sourceAt).toISOString()}</p>
            </Card>)}</div>
          </TabsContent>
        </Tabs>
      </>}
    </div>
  );
};
