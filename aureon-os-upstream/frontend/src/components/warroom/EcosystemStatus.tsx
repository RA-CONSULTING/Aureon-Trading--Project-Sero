/**
 * Ecosystem Status Component
 * Visualizes connected systems using runtime-backed evidence only.
 */

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Sparkles, Activity, Brain, Zap, Radio, Waves, Target, Layers, GitBranch } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useTerminalState } from '@/hooks/useTerminalState';
import { readWarRoomEvidence, type RuntimeMetric } from '@/lib/warRoomEvidence';

interface SystemMetric extends RuntimeMetric {
  name: string;
  icon: React.ElementType;
  color?: string;
}

function unavailableMetric(status: string): RuntimeMetric {
  return {
    available: false,
    value: null,
    status,
    source: null,
    timestamp: null,
  };
}

interface SystemDisplayProps {
  metric: SystemMetric;
}

function SystemDisplay({ metric }: SystemDisplayProps) {
  const { name, icon: Icon, available, value, status, color } = metric;
  const active = available === true;
  const coherence = typeof value === 'number' && Number.isFinite(value) ? value : 0;

  const getStatusColor = () => {
    if (!active) return 'bg-muted-foreground';
    if (coherence > 0.8) return 'bg-success';
    if (coherence > 0.5) return 'bg-warning';
    return 'bg-warning';
  };

  return (
    <div className="flex items-center gap-2 py-1" title={status}>
      <div className={cn('h-2 w-2 rounded-full', getStatusColor())} />
      <Icon className={cn('h-3 w-3', color || 'text-muted-foreground')} />
      <span className={cn('text-xs', active ? 'text-foreground' : 'text-muted-foreground')}>
        {name}
      </span>
      <span className="text-[10px] text-muted-foreground ml-auto font-mono">
        {active ? `${(coherence * 100).toFixed(0)}%` : 'Unavailable'}
      </span>
    </div>
  );
}

function keyForName(name: string): string {
  return name.toLowerCase().replaceAll(' ', '_');
}

function mergeReceiptSystem(metric: SystemMetric, receipt: RuntimeMetric | undefined): SystemMetric {
  if (!receipt || !receipt.available) return metric;
  return { ...metric, ...receipt, color: metric.color };
}

export function EcosystemStatus() {
  const terminal = useTerminalState();
  const evidence = readWarRoomEvidence(terminal.state, terminal.isFresh);
  const ecosystem = evidence.ecosystem;

  const coreMetrics: SystemMetric[] = [
    mergeReceiptSystem({ name: 'Harmonic Nexus', icon: Sparkles, color: 'text-primary', ...unavailableMetric('No runtime-backed Harmonic Nexus receipt is published.') }, ecosystem.systems[keyForName('Harmonic Nexus')]),
    mergeReceiptSystem({ name: 'Omega Equation', icon: Activity, color: 'text-primary', ...unavailableMetric('No runtime-backed Omega Equation receipt is published.') }, ecosystem.systems[keyForName('Omega Equation')]),
    mergeReceiptSystem({ name: 'QGITA Engine', icon: Brain, color: 'text-primary', ...unavailableMetric('No runtime-backed QGITA Engine receipt is published.') }, ecosystem.systems[keyForName('QGITA Engine')]),
    { name: 'Master Equation', icon: Zap, color: 'text-warning', ...evidence.masterFormula },
    { name: 'Lighthouse', icon: Radio, color: 'text-warning', ...evidence.lighthouseConfidence },
  ];

  const enhancementMetrics: SystemMetric[] = [
    mergeReceiptSystem({ name: 'Eckoushic Cascade', icon: Waves, color: 'text-primary', ...unavailableMetric('No runtime-backed Eckoushic Cascade receipt is published.') }, ecosystem.systems[keyForName('Eckoushic Cascade')]),
    mergeReceiptSystem({ name: 'Unity Detector', icon: Target, color: 'text-success', ...unavailableMetric('No runtime-backed Unity Detector receipt is published.') }, ecosystem.systems[keyForName('Unity Detector')]),
    mergeReceiptSystem({ name: 'Fibonacci Lattice', icon: Layers, color: 'text-warning', ...unavailableMetric('No runtime-backed Fibonacci Lattice receipt is published.') }, ecosystem.systems[keyForName('Fibonacci Lattice')]),
    { name: 'Rainbow Bridge', icon: Sparkles, color: 'text-primary', ...evidence.rainbowBridge },
    { name: 'The Prism', icon: Sparkles, color: 'text-success', ...evidence.prismState },
  ];

  const allMetrics = [...coreMetrics, ...enhancementMetrics];
  const totalSystems = allMetrics.length;
  const activeSystems = allMetrics.filter((m) => m.available).length;
  const overallHealth = totalSystems > 0 ? activeSystems / totalSystems : 0;

  const getHealthColor = (health: number) => {
    if (health > 0.8) return 'text-success';
    if (health > 0.5) return 'text-warning';
    return 'text-warning';
  };

  return (
    <Card className="border-border/50 lg:col-span-2">
      <CardHeader className="pb-2">
        <CardTitle className="text-xs font-medium text-muted-foreground flex items-center justify-between">
          <span className="flex items-center gap-1">
            <GitBranch className="h-3 w-3" /> ECOSYSTEM
          </span>
          <Badge variant="outline" className="text-[9px]">
            {activeSystems}/{totalSystems} systems
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {/* Overall Health */}
        <div className="flex items-center justify-between pb-2 border-b border-border/30">
          <span className="text-xs text-muted-foreground">Integration Health</span>
          <span className={cn('text-sm font-mono font-bold', getHealthColor(overallHealth))}>
            {(overallHealth * 100).toFixed(0)}%
          </span>
        </div>

        {/* Systems */}
        <div className="grid grid-cols-2 gap-x-4">
          <div className="space-y-0.5">
            <p className="text-[9px] text-muted-foreground uppercase tracking-wider mb-1">Core Systems</p>
            {coreMetrics.map((metric) => (
              <SystemDisplay key={metric.name} metric={metric} />
            ))}
          </div>

          <div className="space-y-0.5">
            <p className="text-[9px] text-muted-foreground uppercase tracking-wider mb-1">Enhancement Systems</p>
            {enhancementMetrics.map((metric) => (
              <SystemDisplay key={metric.name} metric={metric} />
            ))}
          </div>
        </div>

        {/* Live ecosystem scalar metrics */}
        {ecosystem.available && (
          <div className="grid grid-cols-2 gap-2 pt-2 border-t border-border/30">
            {([
              ['Global resonance', ecosystem.globalResonance],
              ['Market energy', ecosystem.marketEnergy],
              ['Ecosystem coherence', ecosystem.ecosystemCoherence],
              ['Dominant frequency', ecosystem.dominantFrequency],
            ] as const).map(([label, value]) => (
              value !== null && (
                <div key={label} className="rounded bg-muted/30 p-2">
                  <p className="text-[9px] text-muted-foreground">{label}</p>
                  <p className="text-xs font-mono">{label === 'Dominant frequency' ? `${value.toFixed(2)} Hz` : `${(value * 100).toFixed(1)}%`}</p>
                </div>
              )
            ))}
            {ecosystem.activeWaveforms && ecosystem.activeWaveforms.length > 0 && (
              <div className="col-span-2 rounded bg-muted/30 p-2">
                <p className="text-[9px] text-muted-foreground">Active waveforms</p>
                <p className="text-xs">{ecosystem.activeWaveforms.join(', ')}</p>
              </div>
            )}
          </div>
        )}

        {/* Evidence status */}
        <div className="pt-2 border-t border-border/30">
          <p className="text-[10px] text-muted-foreground">
            {ecosystem.available
              ? `Runtime evidence: ${ecosystem.reason}`
              : evidence.available
                ? evidence.reason
                : ecosystem.reason}
            {ecosystem.timestamp && ` · ${ecosystem.timestamp}`}
          </p>
        </div>
      </CardContent>
    </Card>
  );
}
