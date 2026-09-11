import { useEffect, useRef, useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Slider } from "@/components/ui/slider";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Play, RotateCcw, Download, Save, AlertCircle, History, RefreshCw } from "lucide-react";
import { XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Area, AreaChart } from "recharts";
import { useToast } from "@/hooks/use-toast";
import { supabase } from "@/integrations/supabase/client";
import { z } from "zod";
import { GlassPageHeader } from "@/shell/GlassPage";
import { backtestReportCsv, backtestServiceAvailable, createBacktestScope, readBacktestReport, type BacktestConfig, type BacktestReport } from "@/lib/backtestEvidence";
import { api } from "@/services/apiClient";

// Input validation schema
const backtestConfigSchema = z.object({
  symbol: z.string().min(1, "Symbol is required").max(20, "Symbol too long"),
  startDate: z.string().refine((date) => !isNaN(Date.parse(date)), "Invalid start date"),
  endDate: z.string().refine((date) => !isNaN(Date.parse(date)), "Invalid end date"),
  initialCapital: z.number().min(10, "Minimum capital is 10 quote units").max(1000000000, "Capital too large"),
  tradeSize: z.number().min(0.01, "Minimum 0.01").max(1, "Maximum 1 (100%)"),
  stopLoss: z.number().min(0.1, "Minimum 0.1%").max(50, "Maximum 50%"),
  takeProfit: z.number().min(0.1, "Minimum 0.1%").max(100, "Maximum 100%"),
  strategy: z.literal('momentum_next_open_v1'),
  intervalMinutes: z.union([z.literal(60), z.literal(1440)]),
  lookbackPeriods: z.number().int().min(2).max(100),
  feeBps: z.number().min(0).max(1000),
  slippageBps: z.number().min(0).max(1000),
});

const defaultConfig = (): BacktestConfig => {
  const end = new Date();
  end.setUTCDate(end.getUTCDate() - 1);
  const start = new Date(end);
  start.setUTCDate(start.getUTCDate() - 6);
  return { symbol: "BTCUSD", startDate: start.toISOString().slice(0, 10), endDate: end.toISOString().slice(0, 10),
    initialCapital: 10000, tradeSize: 0.5, stopLoss: 2, takeProfit: 5,
    strategy: 'momentum_next_open_v1', intervalMinutes: 60, lookbackPeriods: 24, feeBps: 40, slippageBps: 5 };
};

type Capability = { payload: unknown; receivedAt: number | null; reason: string; loading: boolean };
const EMPTY_CAPABILITY: Capability = { payload: null, receivedAt: null, reason: 'Checking the historical replay service…', loading: true };

/** Downloads are local artifacts, never a database-save receipt. */
function downloadReport(contents: string, type: string, name: string) {
  const url = URL.createObjectURL(new Blob([contents], { type }));
  const link = document.createElement('a');
  link.href = url;
  link.download = name;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1_000);
}

async function readCapability(signal: AbortSignal): Promise<Capability> {
  const data = await api.get<Record<string, unknown>>('/api/trading/backtest/capabilities', { signal, timeoutMs: 8_000 });
  const receivedAt = Date.now();
  return { payload: data, receivedAt, loading: false,
    reason: backtestServiceAvailable(data, receivedAt) ? 'Historical replay capability received. The requested provider dataset is checked when a replay is admitted.'
      : typeof data.reason === 'string' ? data.reason : 'Historical replay unavailable: the operator has not confirmed authenticated replay dispatch.' };
}

export function BacktestingInterface() {
  const { toast } = useToast();
  const [isRunning, setIsRunning] = useState(false);
  const [report, setReport] = useState<BacktestReport | null>(null);
  const results = report?.results ?? null;
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [runError, setRunError] = useState<string | null>(null);
  const [capability, setCapability] = useState<Capability>(EMPTY_CAPABILITY);
  const [probeVersion, setProbeVersion] = useState(0);
  const [now, setNow] = useState(Date.now);
  const running = useRef(false);
  const scope = useRef(createBacktestScope());
  const mounted = useRef(true);
  const serviceAvailable = backtestServiceAvailable(capability.payload, capability.receivedAt, now);

  useEffect(() => {
    const requests = scope.current;
    let accountId: string | null | undefined;
    mounted.current = true;
    const { data: { subscription } } = supabase.auth.onAuthStateChange((event, session) => {
      const nextAccount = session?.user?.id ?? null;
      const accountChanged = accountId !== undefined && accountId !== nextAccount;
      accountId = nextAccount;
      if (event === 'INITIAL_SESSION') return;
      requests.reset();
      running.current = false;
      setIsRunning(false);
      setReport(null);
      setCapability(EMPTY_CAPABILITY);
      setErrors({});
      setRunError(null);
      if (event === 'SIGNED_OUT' || accountChanged) setConfig(defaultConfig());
      // No Supabase calls inside the auth callback; the effect performs the new safe GET.
      setProbeVersion(value => value + 1);
    });
    return () => { mounted.current = false; requests.reset(); subscription.unsubscribe(); };
  }, []);
  useEffect(() => {
    const requests = scope.current;
    const ticket = requests.begin();
    setCapability(EMPTY_CAPABILITY);
    void readCapability(ticket.controller.signal).then(value => {
      if (requests.current(ticket)) { setCapability(value); setNow(Date.now()); }
    }).catch(error => {
      if (requests.current(ticket)) setCapability({ payload: null, receivedAt: null, loading: false,
        reason: error instanceof Error ? `Historical replay capability unavailable: ${error.message}` : 'Historical replay service check failed. Retry the service check.' });
    }).finally(() => requests.finish(ticket));
    return () => { ticket.controller.abort(); requests.finish(ticket); };
  }, [probeVersion]);
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1_000);
    return () => window.clearInterval(timer);
  }, []);

  // Configuration state
  const [config, setConfig] = useState<BacktestConfig>(defaultConfig);

  const validateConfig = (): boolean => {
    try {
      backtestConfigSchema.parse(config);
      
      // Additional validation: end date must be after start date
      if (new Date(config.endDate) < new Date(config.startDate)) {
        setErrors({ endDate: "End date must be on or after start date" });
        return false;
      }
      const end = Date.parse(config.endDate) + 86_400_000;
      const bars = (end - Date.parse(config.startDate)) / (config.intervalMinutes * 60_000);
      if (end > Date.now() || bars > 672 || bars + config.lookbackPeriods + 1 > 719) {
        setErrors({ endDate: 'Choose completed UTC days within 672 candles, leaving room for the look-back window.' });
        return false;
      }
      
      setErrors({});
      return true;
    } catch (error) {
      if (error instanceof z.ZodError) {
        const newErrors: Record<string, string> = {};
        error.errors.forEach((err) => {
          if (err.path.length > 0) {
            newErrors[err.path[0].toString()] = err.message;
          }
        });
        setErrors(newErrors);
      }
      return false;
    }
  };

  const runBacktest = async () => {
    if (running.current || !serviceAvailable) return;
    if (!validateConfig()) {
      toast({
        title: "Invalid Configuration",
        description: "Please check your input parameters",
        variant: "destructive",
      });
      return;
    }

    const submittedConfig = { ...config, symbol: config.symbol.trim() };
    running.current = true;
    setIsRunning(true);
    setReport(null);
    setRunError(null);
    const requests = scope.current;
    const ticket = requests.begin();
    const controller = ticket.controller;

    try {
      // Re-read the capability before a user-requested replay, including after session changes.
      const current = await readCapability(controller.signal);
      if (!mounted.current || !requests.current(ticket)) return;
      setCapability(current);
      if (!backtestServiceAvailable(current.payload, current.receivedAt)) throw new Error(current.reason);
      const requestId = crypto.randomUUID();
      const accountScope = (current.payload as { account_scope: string }).account_scope;
      const data = await api.post('/api/trading/backtest', { config: submittedConfig, request_id: requestId, account_scope: accountScope },
        { signal: controller.signal, timeoutMs: 30_000 });
      if (!mounted.current || !requests.current(ticket)) return;
      const completed = readBacktestReport(data, submittedConfig, Date.now(), { requestId, accountScope });
      setReport(completed);
      toast({
        title: "Historical replay received",
        description: `${completed.results.totalTrades} replay trade records. Dataset source and dates are included in the report.`,
      });
    } catch (error) {
      if (!mounted.current || !requests.current(ticket)) return;
      const message = error instanceof Error ? error.message : 'The historical replay service did not return a usable report.';
      setRunError(message);
      toast({
        title: "Historical replay unavailable",
        description: message,
        variant: "destructive",
      });
    } finally {
      if (requests.current(ticket)) {
        running.current = false;
        if (mounted.current) setIsRunning(false);
      }
      requests.finish(ticket);
    }
  };

  const saveResults = () => {
    if (report) downloadReport(JSON.stringify(report, null, 2), 'application/json', 'aureon-backtest-report.json');
  };

  const resetConfig = () => {
    setConfig(defaultConfig());
    setReport(null);
    setRunError(null);
    setErrors({});
  };

  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat('en-US', {
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(value);
  };
  const metric = (key: string, value: number | null, digits = 2) => {
    if (value === null) return 'Unavailable';
    const unit = report?.metricUnits[key];
    return `${value.toFixed(digits)}${unit === 'percent' ? '%' : unit ? ` ${unit}` : ['sharpeRatio', 'profitFactor'].includes(key) ? '' : ' (unit unreported)'}`;
  };

  return (
    <div className="space-y-6">
      <GlassPageHeader icon={History} eyebrow="Historical evidence" title="Backtesting"
        description="Replay strategies against recorded provider data. Results describe a historical replay and do not establish live trading performance."
        actions={<Button variant="outline" disabled={capability.loading || isRunning} onClick={() => setProbeVersion(value => value + 1)}>
          <RefreshCw className={`mr-2 h-4 w-4 ${capability.loading ? 'animate-spin' : ''}`} />{capability.loading ? 'Checking service…' : 'Check replay service'}
        </Button>} />
      <Card><CardContent className="pt-6 space-y-2" aria-live="polite">
        <Badge variant="outline">{capability.loading ? 'Checking capability' : serviceAvailable ? 'Replay service observed' : 'Replay unavailable'}</Badge>
        <p className="text-sm text-muted-foreground">{!serviceAvailable && capability.payload && backtestServiceAvailable(capability.payload, capability.receivedAt, capability.receivedAt ?? 0)
          ? 'The service capability receipt expired. Check the replay service again before running.' : capability.reason}</p>
        <p className="text-xs text-muted-foreground">Service: operator historical replay. {capability.receivedAt && `Capability read ${new Date(capability.receivedAt).toISOString()}. `}Capability reads expire after one minute and do not attest a dataset or release a protected request.</p>
        <p className="text-xs text-muted-foreground">Cloud saving is unavailable in this workspace. Configuration and completed reports can be downloaded locally.</p>
        {runError && <p role="alert" className="text-sm text-destructive">{runError}</p>}
      </CardContent></Card>
    <Card className="bg-card/50 backdrop-blur border-border/50">
      <CardContent className="pt-6">
        <Tabs defaultValue="config" className="w-full">
          <TabsList className="grid w-full grid-cols-2">
            <TabsTrigger value="config">Configuration</TabsTrigger>
            <TabsTrigger value="results" disabled={!results}>Results</TabsTrigger>
          </TabsList>

          <TabsContent value="config" className="space-y-6 mt-6">
            {/* Basic Settings */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="symbol">Symbol</Label>
                <Select
                  value={config.symbol}
                  onValueChange={(value) => setConfig({ ...config, symbol: value })}
                >
                  <SelectTrigger id="symbol">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="BTCUSD">BTC/USD · Kraken</SelectItem>
                    <SelectItem value="ETHUSD">ETH/USD · Kraken</SelectItem>
                    <SelectItem value="SOLUSD">SOL/USD · Kraken</SelectItem>
                  </SelectContent>
                </Select>
                {errors.symbol && <p className="text-xs text-destructive">{errors.symbol}</p>}
              </div>

              <div className="space-y-2">
                <Label htmlFor="capital">Initial Capital (quote units)</Label>
                <Input
                  id="capital"
                  type="number"
                  value={config.initialCapital}
                  onChange={(e) => setConfig({ ...config, initialCapital: Number(e.target.value) })}
                  min={10}
                  max={1000000000}
                  className="font-mono"
                />
                {errors.initialCapital && <p className="text-xs text-destructive">{errors.initialCapital}</p>}
              </div>

              <div className="space-y-2">
                <Label htmlFor="startDate">Start Date</Label>
                <Input
                  id="startDate"
                  type="date"
                  value={config.startDate}
                  onChange={(e) => setConfig({ ...config, startDate: e.target.value })}
                />
                {errors.startDate && <p className="text-xs text-destructive">{errors.startDate}</p>}
              </div>

              <div className="space-y-2">
                <Label htmlFor="endDate">End Date</Label>
                <Input
                  id="endDate"
                  type="date"
                  value={config.endDate}
                  onChange={(e) => setConfig({ ...config, endDate: e.target.value })}
                />
                {errors.endDate && <p className="text-xs text-destructive">{errors.endDate}</p>}
              </div>
            </div>

            {/* Risk Parameters */}
            <div className="space-y-4 p-4 bg-muted/30 rounded-lg border border-border/30">
              <h4 className="text-sm font-semibold text-foreground">Risk Parameters</h4>
              
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <Label>Trade Size ({(config.tradeSize * 100).toFixed(0)}%)</Label>
                  <span className="text-sm font-mono text-muted-foreground">
                    {formatCurrency(config.initialCapital * config.tradeSize)}
                  </span>
                </div>
                <Slider
                  value={[config.tradeSize]}
                  onValueChange={([value]) => setConfig({ ...config, tradeSize: value })}
                  min={0.01}
                  max={1}
                  step={0.01}
                />
              </div>

              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <Label>Stop Loss ({config.stopLoss.toFixed(1)}%)</Label>
                </div>
                <Slider
                  value={[config.stopLoss]}
                  onValueChange={([value]) => setConfig({ ...config, stopLoss: value })}
                  min={0.1}
                  max={50}
                  step={0.1}
                />
              </div>

              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <Label>Take Profit ({config.takeProfit.toFixed(1)}%)</Label>
                </div>
                <Slider
                  value={[config.takeProfit]}
                  onValueChange={([value]) => setConfig({ ...config, takeProfit: value })}
                  min={0.1}
                  max={100}
                  step={0.1}
                />
              </div>
            </div>

            <div className="space-y-4 p-4 bg-primary/5 rounded-lg border border-primary/30">
              <h2 className="text-sm font-semibold">Momentum replay method</h2>
              <p className="text-sm text-muted-foreground">A long/flat baseline uses completed close-to-close momentum and enters at the next open. Fresh Kraken candles are required; missing dates are never replaced or interpolated.</p>
              <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-2"><Label htmlFor="replayInterval">Candle interval</Label>
                  <Select value={String(config.intervalMinutes)} onValueChange={value => setConfig({ ...config, intervalMinutes: Number(value) as 60 | 1440 })}>
                    <SelectTrigger id="replayInterval"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="60">Hourly</SelectItem><SelectItem value="1440">Daily</SelectItem></SelectContent>
                  </Select>
                </div>
                <div className="space-y-2"><Label htmlFor="lookbackPeriods">Momentum look-back (candles)</Label>
                  <Input id="lookbackPeriods" type="number" min={2} max={100} step={1} value={config.lookbackPeriods} onChange={event => setConfig({ ...config, lookbackPeriods: Number(event.target.value) })} />
                  {errors.lookbackPeriods && <p className="text-xs text-destructive">{errors.lookbackPeriods}</p>}
                </div>
                <div className="space-y-2"><Label htmlFor="feeBps">Assumed fee per side (basis points)</Label>
                  <Input id="feeBps" type="number" min={0} max={1000} value={config.feeBps} onChange={event => setConfig({ ...config, feeBps: Number(event.target.value) })} />
                  {errors.feeBps && <p className="text-xs text-destructive">{errors.feeBps}</p>}
                </div>
                <div className="space-y-2"><Label htmlFor="slippageBps">Assumed slippage per side (basis points)</Label>
                  <Input id="slippageBps" type="number" min={0} max={1000} value={config.slippageBps} onChange={event => setConfig({ ...config, slippageBps: Number(event.target.value) })} />
                  {errors.slippageBps && <p className="text-xs text-destructive">{errors.slippageBps}</p>}
                </div>
              </div>
              <p className="text-xs text-muted-foreground">Costs are editable analysis assumptions, not a verified account fee tier. One basis point is 0.01%. Replay fills are hypothetical; the input candles come from the provider.</p>
              <details className="rounded-lg border p-3 text-sm text-muted-foreground"><summary className="cursor-pointer">Advanced HNC replay · unavailable</summary>
                <p className="mt-2">Coherence, Kelly optimization, Lighthouse confidence, Prism level and Lighthouse Event gates require their own timestamped historical signal records. They are not inferred from candles or applied by this momentum baseline.</p>
              </details>
            </div>

            {/* Action Buttons */}
            <div className="flex flex-wrap gap-3">
              <Button
                onClick={runBacktest}
                  disabled={isRunning || !serviceAvailable}
                className="flex-1"
              >
                {isRunning ? (
                  <>
                    <div className="h-4 w-4 border-2 border-current border-t-transparent rounded-full animate-spin mr-2" />
                    Running...
                  </>
                ) : (
                  <>
                    <Play className="h-4 w-4 mr-2" />
                    {serviceAvailable ? 'Run historical replay' : 'Replay service unavailable'}
                  </>
                )}
              </Button>
              <Button onClick={resetConfig} variant="outline" disabled={isRunning}>
                <RotateCcw className="h-4 w-4 mr-2" />
                Reset
              </Button>
              <Button variant="outline" onClick={() => downloadReport(JSON.stringify({ schema: 'aureon.backtest-configuration.v1', config }, null, 2), 'application/json', 'aureon-backtest-configuration.json')}>
                <Download className="h-4 w-4 mr-2" /> Export configuration
              </Button>
            </div>

            {Object.keys(errors).length > 0 && (
              <div className="flex items-start gap-2 p-3 bg-destructive/10 border border-destructive/30 rounded-lg">
                <AlertCircle className="h-4 w-4 text-destructive mt-0.5" />
                <div className="text-xs">
                  <p className="font-semibold text-destructive">Configuration Errors</p>
                  <p className="text-muted-foreground">Please correct the errors above</p>
                </div>
              </div>
            )}
          </TabsContent>

          <TabsContent value="results" className="space-y-6 mt-6">
            {results && report && (
              <>
                <div className="rounded-lg border p-4 space-y-2 text-sm">
                  <p>Historical replay: {report.config.symbol} · {report.config.startDate} to {report.config.endDate} · initial capital {formatCurrency(report.config.initialCapital)} {report.currency ?? '(currency unreported)'}</p>
                  <p className="text-muted-foreground">Dataset: {report.source} · source timestamp {new Date(report.sourceAt).toISOString()}</p>
                  <p className="text-xs text-muted-foreground">Fetched {report.fetchedAt === null ? 'unreported' : new Date(report.fetchedAt).toISOString()} · dataset SHA256 {report.datasetHash ?? 'unreported'}</p>
                  <p className="text-xs text-muted-foreground">Report received {new Date(report.receivedAt).toISOString()}. Changing configuration does not change this saved report.</p>
                  {report.assumptions.length > 0 && <details><summary className="cursor-pointer">Replay method and assumptions</summary><ul className="mt-2 list-disc space-y-1 pl-5">{report.assumptions.map(note => <li key={note}>{note}</li>)}</ul></details>}
                </div>
                {/* Performance Metrics */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <div className="p-4 bg-muted/30 rounded-lg border border-border/30">
                    <p className="text-xs text-muted-foreground mb-1">Total Trades</p>
                    <p className="text-2xl font-bold font-mono text-foreground">{results.totalTrades}</p>
                  </div>
                  <div className="p-4 bg-muted/30 rounded-lg border border-border/30">
                    <p className="text-xs text-muted-foreground mb-1">Win Rate</p>
                    <p className="text-2xl font-bold font-mono text-success">{metric('winRate', results.winRate, 1)}</p>
                  </div>
                  <div className="p-4 bg-muted/30 rounded-lg border border-border/30">
                    <p className="text-xs text-muted-foreground mb-1">Total Return</p>
                    <p className="text-2xl font-bold font-mono text-primary">{metric('totalReturn', results.totalReturn, 1)}</p>
                  </div>
                  <div className="p-4 bg-muted/30 rounded-lg border border-border/30">
                    <p className="text-xs text-muted-foreground mb-1">Sharpe Ratio</p>
                    <p className="text-2xl font-bold font-mono text-foreground">{metric('sharpeRatio', results.sharpeRatio)}</p>
                  </div>
                </div>

                {/* Equity Curve */}
                <div className="p-4 bg-muted/30 rounded-lg border border-border/30">
                  <h4 className="text-sm font-semibold mb-4 text-foreground">Equity Curve · {report.currency ?? 'currency unreported'}</h4>
                  <div className="h-80">
                    <ResponsiveContainer width="100%" height="100%">
                      <AreaChart data={results.equityCurve}>
                        <defs>
                          <linearGradient id="equityGradient" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor="hsl(var(--primary))" stopOpacity={0.3}/>
                            <stop offset="95%" stopColor="hsl(var(--primary))" stopOpacity={0}/>
                          </linearGradient>
                        </defs>
                        <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" opacity={0.3} />
                        <XAxis 
                          dataKey="date" 
                          stroke="hsl(var(--muted-foreground))"
                          style={{ fontSize: '12px' }}
                        />
                        <YAxis 
                          stroke="hsl(var(--muted-foreground))"
                          style={{ fontSize: '12px' }}
                          tickFormatter={(value) => `${(value / 1000).toFixed(0)}K`}
                        />
                        <Tooltip 
                          contentStyle={{ 
                            backgroundColor: 'hsl(var(--card))',
                            border: '1px solid hsl(var(--border))',
                            borderRadius: '8px'
                          }}
                          formatter={(value: number) => [`${formatCurrency(value)} ${report.currency ?? '(currency unreported)'}`, 'Equity']}
                        />
                        <Area 
                          type="linear"
                          dataKey="equity" 
                          stroke="hsl(var(--primary))"
                          strokeWidth={2}
                          fillOpacity={1}
                          fill="url(#equityGradient)"
                        />
                      </AreaChart>
                    </ResponsiveContainer>
                  </div>
                </div>

                {/* Additional Metrics */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <div className="p-3 bg-background/50 rounded border border-border/30">
                    <p className="text-xs text-muted-foreground">Max Drawdown</p>
                    <p className="text-lg font-bold font-mono text-destructive">{metric('maxDrawdown', results.maxDrawdown, 1)}</p>
                  </div>
                  <div className="p-3 bg-background/50 rounded border border-border/30">
                    <p className="text-xs text-muted-foreground">Profit Factor</p>
                    <p className="text-lg font-bold font-mono text-foreground">{metric('profitFactor', results.profitFactor)}</p>
                  </div>
                  <div className="p-3 bg-background/50 rounded border border-border/30">
                    <p className="text-xs text-muted-foreground">Avg Win</p>
                    <p className="text-lg font-bold font-mono text-success">{metric('avgWin', results.avgWin)}</p>
                  </div>
                  <div className="p-3 bg-background/50 rounded border border-border/30">
                    <p className="text-xs text-muted-foreground">Avg Loss</p>
                    <p className="text-lg font-bold font-mono text-destructive">{metric('avgLoss', results.avgLoss)}</p>
                  </div>
                </div>

                {/* Actions */}
                <div className="flex flex-wrap gap-3">
                  <Button onClick={saveResults} className="flex-1">
                    <Save className="h-4 w-4 mr-2" />
                    Save report JSON
                  </Button>
                  <Button variant="outline" onClick={() => downloadReport(backtestReportCsv(report), 'text/csv;charset=utf-8', 'aureon-backtest-report.csv')}>
                    <Download className="h-4 w-4 mr-2" />
                    Export CSV
                  </Button>
                </div>
              </>
            )}
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
    </div>
  );
}
