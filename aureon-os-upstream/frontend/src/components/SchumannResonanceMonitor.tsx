import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Activity, Radio, TrendingUp, Waves } from "lucide-react";
import { useSchumannResonance } from "@/hooks/useSchumannResonance";

export function SchumannResonanceMonitor() {
  const { schumannData, isConnected } = useSchumannResonance();

  const getPhaseColor = (phase: string) => {
    switch (phase) {
      case 'peak': return 'bg-success';
      case 'elevated': return 'bg-primary';
      case 'stable': return 'bg-warning';
      case 'disturbed': return 'bg-destructive';
      default: return 'bg-gray-500';
    }
  };

  const getPhaseGlow = (phase: string) => {
    switch (phase) {
      case 'peak': return 'shadow-[0_0_20px_rgba(34,197,94,0.6)]';
      case 'elevated': return 'shadow-[0_0_20px_rgba(59,130,246,0.6)]';
      case 'stable': return 'shadow-[0_0_15px_rgba(234,179,8,0.4)]';
      case 'disturbed': return 'shadow-[0_0_15px_rgba(239,68,68,0.4)]';
      default: return '';
    }
  };

  if (!isConnected || !schumannData) {
    return (
      <Card className="bg-card/50 backdrop-blur border-border/50">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Radio className="w-5 h-5 text-muted-foreground animate-pulse" />
            Schumann Resonance Monitor
          </CardTitle>
          <CardDescription>Connecting to Earth's electromagnetic field...</CardDescription>
        </CardHeader>
      </Card>
    );
  }

  const frequencyReported = schumannData.frequencyReported;
  const activityScore = schumannData.activityScore ?? schumannData.amplitude * 100;
  const deviation = Math.abs(schumannData.fundamentalHz - 7.83);
  const coherencePercent = (schumannData.coherenceBoost / 0.12) * 100;

  return (
    <Card className="bg-card/50 backdrop-blur border-border/50 relative overflow-hidden">
      <div className="absolute inset-0 bg-gradient-to-br from-success/5 via-primary/5 to-primary/5" />
      
      <CardHeader className="relative">
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="flex items-center gap-2">
              <Radio className="w-5 h-5 text-success" />
              Schumann Resonance Monitor
            </CardTitle>
            <CardDescription>
              Live Schumann telemetry with source limits preserved
            </CardDescription>
          </div>
          <Badge className={`${getPhaseColor(schumannData.resonancePhase)} text-white ${getPhaseGlow(schumannData.resonancePhase)}`}>
            {schumannData.resonancePhase.toUpperCase()}
          </Badge>
        </div>
      </CardHeader>

      <CardContent className="relative space-y-4">
        {/* Fundamental Frequency Display */}
        <div className="flex items-center justify-center p-6 bg-gradient-to-br from-success/10 to-primary/10 rounded-lg border border-border/50">
          <div className="text-center">
            <div className="flex items-center justify-center gap-2 mb-2">
              <Waves className="w-6 h-6 text-success" />
              <span className="text-sm text-muted-foreground font-medium">{frequencyReported ? 'Fundamental Frequency' : 'Station Activity Score'}</span>
            </div>
            <div className="text-5xl font-bold bg-gradient-to-r from-success to-primary bg-clip-text text-transparent">
              {frequencyReported ? `${schumannData.fundamentalHz.toFixed(3)} Hz` : `${activityScore.toFixed(0)}/100`}
            </div>
            <div className="text-xs text-muted-foreground mt-1">
              {frequencyReported ? `Base: 7.83 Hz • Deviation: ${(deviation * 1000).toFixed(1)}mHz` : `Stations: ${schumannData.stationCount ?? '—'}/${schumannData.stationsMonitored ?? '—'} • frequency not reported`}
            </div>
          </div>
        </div>

        {/* Metrics Grid */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="p-4 bg-background/50 rounded-lg border border-border/50">
            <div className="flex items-center gap-2 mb-2">
              <Activity className="w-4 h-4 text-primary" />
              <span className="text-xs text-muted-foreground">{frequencyReported ? 'Amplitude' : 'Relative Activity'}</span>
            </div>
            <div className="text-2xl font-bold">{frequencyReported ? schumannData.amplitude.toFixed(2) : `${activityScore.toFixed(0)}/100`}</div>
            <Progress value={frequencyReported ? schumannData.amplitude * 50 : activityScore} className="mt-2 h-1" />
          </div>

          <div className="p-4 bg-background/50 rounded-lg border border-border/50">
            <div className="flex items-center gap-2 mb-2">
              <TrendingUp className="w-4 h-4 text-success" />
              <span className="text-xs text-muted-foreground">Quality</span>
            </div>
            <div className="text-2xl font-bold">{(schumannData.quality * 100).toFixed(0)}%</div>
            <Progress value={schumannData.quality * 100} className="mt-2 h-1" />
          </div>

          <div className="p-4 bg-background/50 rounded-lg border border-border/50">
            <div className="flex items-center gap-2 mb-2">
              <Waves className="w-4 h-4 text-primary" />
              <span className="text-xs text-muted-foreground">Variance</span>
            </div>
            <div className="text-2xl font-bold">{(schumannData.variance * 1000).toFixed(1)}</div>
            <div className="text-xs text-muted-foreground mt-1">mHz</div>
          </div>

          <div className="p-4 bg-gradient-to-br from-success/20 to-primary/20 rounded-lg border border-success/50">
            <div className="flex items-center gap-2 mb-2">
              <Activity className="w-4 h-4 text-success" />
              <span className="text-xs text-success">{frequencyReported ? 'Coherence Boost' : 'Trading Boost Held'}</span>
            </div>
            <div className="text-2xl font-bold text-success">{frequencyReported ? `+${(schumannData.coherenceBoost * 100).toFixed(1)}%` : '0.0%'}</div>
            <Progress value={coherencePercent} className="mt-2 h-1" />
          </div>
        </div>

        {/* Phase Information */}
        <div className="p-4 bg-muted/50 rounded-lg">
          <h4 className="text-sm font-semibold mb-2 flex items-center gap-2">
            <Radio className="w-4 h-4" />
            Resonance Phase Analysis
          </h4>
          <ul className="text-xs text-muted-foreground space-y-1">
            <li>• <strong>Peak</strong>: Optimal Earth resonance, maximum coherence boost</li>
            <li>• <strong>Elevated</strong>: Strong resonance, enhanced field stability</li>
            <li>• <strong>Stable</strong>: Normal Earth heartbeat, baseline coherence</li>
            <li>• <strong>Disturbed</strong>: Geomagnetic activity detected, reduced coherence</li>
          </ul>
        </div>

        {/* Real-time Insights */}
        {schumannData.resonancePhase === 'peak' && (
          <div className="p-4 bg-success/10 border border-success/30 rounded-lg">
            <p className="text-sm text-success font-medium">
              ⚡ Peak resonance detected! Earth's electromagnetic field is highly coherent. 
              {frequencyReported ? `AUREON coherence boosted by ${(schumannData.coherenceBoost * 100).toFixed(1)}%.` : 'Station activity is observed, but no trading or coherence gate is opened from this feed.'}
            </p>
          </div>
        )}

        {schumannData.resonancePhase === 'disturbed' && (
          <div className="p-4 bg-destructive/10 border border-destructive/30 rounded-lg">
            <p className="text-sm text-destructive font-medium">
              ⚠️ Geomagnetic disturbance detected. Schumann resonance variance elevated. 
              No trading signal is opened from this environmental telemetry.
            </p>
          </div>
        )}

        <div className="pt-2 border-t border-border/50">
          <p className="text-xs text-muted-foreground text-center">
            Last Update: {schumannData.timestamp.toLocaleTimeString()}
          </p>
        </div>
      </CardContent>
    </Card>
  );
}