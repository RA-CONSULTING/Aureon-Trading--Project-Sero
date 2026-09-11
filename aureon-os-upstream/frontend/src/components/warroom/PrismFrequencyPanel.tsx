/**
 * Prism Frequency Panel for War Room
 * Displays a measured Prism frequency receipt from the runtime.
 * Falls back to an honest unavailable card when no receipt is published.
 */

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { Sparkles, Heart } from 'lucide-react';
import type { WarRoomEvidence } from '@/lib/warRoomEvidence';
import { useTerminalState } from '@/hooks/useTerminalState';
import { readWarRoomEvidence } from '@/lib/warRoomEvidence';

function frequencyColor(frequency: number): string {
  const normalized = Math.max(0, Math.min(1, (frequency - 174) / (963 - 174)));
  return `hsl(${Math.round(normalized * 300)}, 80%, 50%)`;
}

function stateColor(state: string): string {
  if (state === 'FORMING') return 'hsl(15, 90%, 55%)';
  if (state === 'CONVERGING') return 'hsl(45, 100%, 50%)';
  if (state === 'MANIFEST') return 'hsl(150, 100%, 50%)';
  return 'hsl(var(--muted-foreground))';
}

interface PrismFrequencyPanelProps {
  evidence?: WarRoomEvidence;
}

export function PrismFrequencyPanel({ evidence: evidenceProp }: PrismFrequencyPanelProps) {
  const terminal = useTerminalState();
  const evidence = evidenceProp ?? readWarRoomEvidence(terminal.state, terminal.isFresh);
  const receipt = evidence.prismReceipt;

  if (!receipt.available) {
    return (
      <Card className="bg-card/50 backdrop-blur border-primary/20">
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-2 text-lg">
            <Sparkles className="w-5 h-5 text-primary" />
            The Prism
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          <p className="text-sm text-muted-foreground">{receipt.reason}</p>
          <p className="text-xs text-muted-foreground">
            Prism frequency requires a current runtime receipt. Browser harmonic transforms are not used as live data.
          </p>
        </CardContent>
      </Card>
    );
  }

  const { frequency, state, level, resonance, harmonicPurity, isLoveLocked, layers } = receipt;
  const levelLabels = ['HNC', 'INPUT', 'CREATE', 'REFLECT', 'UNITY', 'LOVE'];
  const displayLevel = level ?? 0;
  const displayFrequency = frequency ?? 0;
  const displayState = state ?? 'Unknown';
  const layerEntries = layers ? Object.entries(layers) : [];

  return (
    <Card
      className={`bg-card/50 backdrop-blur border-primary/20 transition-all duration-500 ${
        isLoveLocked ? 'border-success/50 shadow-[0_0_20px_rgba(34,197,94,0.3)]' : ''
      }`}
    >
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2 text-lg">
            <Sparkles className="w-5 h-5 text-primary" />
            The Prism
          </CardTitle>
          {isLoveLocked && (
            <Badge className="bg-success animate-pulse">
              <Heart className="w-3 h-3 mr-1" /> 528Hz LOCKED
            </Badge>
          )}
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Frequency Display */}
        <div className="text-center p-3 bg-background/30 rounded-lg">
          <div className="text-4xl font-bold mb-1" style={{ color: frequencyColor(displayFrequency) }}>
            {displayFrequency} Hz
          </div>
          <div className="text-xs text-muted-foreground flex items-center justify-center gap-2">
            <span>{displayState}</span>
            <span>•</span>
            <span>Level {displayLevel}/5</span>
          </div>
        </div>

        {/* Resonance & Purity */}
        <div className="grid grid-cols-2 gap-3">
          <div>
            <div className="flex justify-between text-xs mb-1">
              <span className="text-muted-foreground">Resonance</span>
              <span>{resonance === null ? 'Unavailable' : `${(resonance * 100).toFixed(0)}%`}</span>
            </div>
            <Progress value={resonance === null ? 0 : resonance * 100} className="h-2" />
          </div>
          <div>
            <div className="flex justify-between text-xs mb-1">
              <span className="text-muted-foreground">Purity</span>
              <span>{harmonicPurity === null ? 'Unavailable' : `${(harmonicPurity * 100).toFixed(0)}%`}</span>
            </div>
            <Progress value={harmonicPurity === null ? 0 : harmonicPurity * 100} className="h-2" />
          </div>
        </div>

        {/* 5-Layer Visualization */}
        {layerEntries.length > 0 && (
          <div className="grid grid-cols-6 gap-1">
            {layerEntries.map(([key, value], index) => (
              <div key={key} className="flex flex-col items-center">
                <div
                  className={`w-7 h-7 rounded-full flex items-center justify-center text-[10px] font-bold transition-all ${
                    index <= displayLevel ? 'opacity-100' : 'opacity-30'
                  }`}
                  style={{
                    background:
                      index <= displayLevel
                        ? `linear-gradient(135deg, ${frequencyColor(value)}, ${stateColor(displayState)})`
                        : 'hsl(var(--muted))',
                    color: index <= displayLevel ? 'white' : 'hsl(var(--muted-foreground))',
                  }}
                >
                  {index}
                </div>
                <span className="text-[8px] text-muted-foreground mt-0.5">{levelLabels[index] ?? key}</span>
              </div>
            ))}
          </div>
        )}

        {/* 528 Hz Distance */}
        <div className="flex items-center justify-between text-xs p-2 bg-background/30 rounded-lg">
          <span className="text-muted-foreground">Distance to 528 Hz</span>
          <span className={isLoveLocked ? 'text-success font-bold' : ''}>
            {isLoveLocked ? '✓ ALIGNED' : `${Math.abs(displayFrequency - 528)} Hz`}
          </span>
        </div>

        <p className="text-xs text-muted-foreground">
          Source: {receipt.source ?? 'unreported'} · {receipt.timestamp ?? 'no timestamp'}
        </p>
      </CardContent>
    </Card>
  );
}
