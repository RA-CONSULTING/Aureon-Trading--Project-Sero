import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Activity, Database, Shield, Zap } from 'lucide-react';
import { useTerminalState } from '@/hooks/useTerminalState';
import type { WarRoomEvidence } from '@/lib/warRoomEvidence';

const SYSTEMS = [
  ['Data ingestion', 'terminal'],
  ['Lighthouse', 'lighthouse'],
  ['Master equation', 'equation'],
  ['Rainbow bridge', 'bridge'],
] as const;

type SystemKey = typeof SYSTEMS[number][1];

export function UnifiedBusStatus({ evidence }: { evidence: WarRoomEvidence }) {
  const { state, error, isStreamFresh } = useTerminalState();
  const fresh = !error && state?.ok === true && state.stale !== true && state.data_ready === true;
  const routes = state?.exchanges?.execution_venues ?? {};
  const routeCount = Object.values(routes).filter((route) => route.ready === true).length;

  const statusFor = (key: SystemKey): { live: boolean; detail: string } => {
    if (key === 'terminal') {
      return {
        live: isStreamFresh,
        detail: isStreamFresh ? 'Fresh provider market quotes.' : 'Market stream source unavailable or expired.',
      };
    }
    if (key === 'lighthouse') {
      return {
        live: evidence.lighthouseConfidence.available,
        detail: evidence.lighthouseConfidence.available
          ? `${evidence.lighthouseConfidence.status} L ${evidence.lighthouseConfidence.value?.toFixed(3) ?? '-'}`
          : evidence.lighthouseConfidence.status,
      };
    }
    if (key === 'equation') {
      return {
        live: evidence.masterFormula.available,
        detail: evidence.masterFormula.available
          ? `${evidence.masterFormula.status} score ${evidence.masterFormula.value?.toFixed(3) ?? '-'}`
          : evidence.masterFormula.status,
      };
    }
    return { live: false, detail: evidence.rainbowBridge.status };
  };

  return (
    <Card className="bg-card/50 backdrop-blur border-primary/20">
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2 text-lg">
          <Activity className="h-5 w-5 text-primary" />
          Runtime Feed Status
          <Badge variant={fresh ? 'default' : 'secondary'} className={fresh ? 'bg-success ml-auto' : 'ml-auto'}>
            {fresh ? 'ANALYSIS FRESH' : isStreamFresh ? 'QUOTES LIVE' : 'WAITING'}
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="rounded-lg border border-primary/20 bg-primary/5 p-3">
          <div className="flex items-center justify-between text-sm">
            <span>Trader heartbeat</span>
            <span className={fresh ? 'text-success font-mono' : 'text-warning font-mono'}>
              {fresh && state?.last_tick_age_sec != null ? `${Math.round(state.last_tick_age_sec)}s old` : 'unavailable or stale'}
            </span>
          </div>
          <div className="mt-1 flex items-center justify-between text-xs text-muted-foreground">
            <span>Primary exchange routes</span><span>{fresh ? `${routeCount}/4 ready` : 'source unavailable or stale'}</span>
          </div>
        </div>
        <div className="grid grid-cols-2 gap-2">
          {SYSTEMS.map(([name, key]) => {
            const { live, detail } = statusFor(key);
            const Icon = key === 'terminal' ? Database : key === 'equation' ? Shield : Zap;
            return (
              <div key={key} className={`p-3 rounded-lg border ${live ? 'border-success/30 bg-success/5' : 'border-border/50 bg-muted/20'}`}>
                <div className="flex items-center gap-2">
                  <Icon className={`h-4 w-4 ${live ? 'text-success' : 'text-muted-foreground'}`} />
                  <span className="text-sm font-medium">{name}</span>
                </div>
                <p className="mt-1 text-xs text-muted-foreground">{detail}</p>
              </div>
            );
          })}
        </div>
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <span className={`h-2 w-2 rounded-full ${fresh ? 'bg-success animate-pulse' : 'bg-warning'}`} />
          {error || (fresh ? 'Read-only operator runtime feed is connected.' : 'Waiting for the operator runtime feed.')}
        </div>
      </CardContent>
    </Card>
  );
}
