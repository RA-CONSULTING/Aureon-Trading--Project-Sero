import { useState, useEffect } from 'react';
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

interface PrismStatusProps {
  evidence?: WarRoomEvidence;
}

export const PrismStatus = ({ evidence: evidenceProp }: PrismStatusProps) => {
  const terminal = useTerminalState();
  const evidence = evidenceProp ?? readWarRoomEvidence(terminal.state, terminal.isFresh);
  const receipt = evidence.prismReceipt;
  const [pulseAnimation, setPulseAnimation] = useState(false);

  useEffect(() => {
    if (receipt.isLoveLocked) {
      setPulseAnimation(true);
      const timer = setTimeout(() => setPulseAnimation(false), 1000);
      return () => clearTimeout(timer);
    }
  }, [receipt.isLoveLocked]);

  if (!receipt.available) {
    return (
      <div className="bg-card/50 backdrop-blur-sm border border-border/50 rounded-lg p-4">
        <h3 className="text-sm font-semibold text-foreground flex items-center gap-2">🔮 THE PRISM</h3>
        <p className="mt-2 text-sm text-muted-foreground">{receipt.reason}</p>
        <p className="mt-1 text-xs text-muted-foreground">
          Prism status requires a current runtime receipt. Browser harmonic transforms are not used as live data.
        </p>
      </div>
    );
  }

  const { frequency, state, level, resonance, harmonicPurity, isLoveLocked, layers } = receipt;
  const displayFrequency = frequency ?? 0;
  const displayState = state ?? 'Unknown';
  const displayLevel = level ?? 0;
  const layerEntries = layers ? Object.entries(layers) : [];
  const levelLabels = ['HNC', 'INPUT', 'CREATE', 'REFLECT', 'UNITY', 'LOVE'];
  const stateEmoji = displayState === 'FORMING' ? '🔶' : displayState === 'CONVERGING' ? '🔷' : displayState === 'MANIFEST' ? '💚' : '🔮';

  return (
    <div className="bg-card/50 backdrop-blur-sm border border-border/50 rounded-lg p-4">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-foreground flex items-center gap-2">
          🔮 THE PRISM
          {isLoveLocked && (
            <span
              className={`text-xs px-2 py-0.5 rounded-full bg-success/20 text-success ${
                pulseAnimation ? 'animate-pulse' : ''
              }`}
            >
              528 Hz LOCKED
            </span>
          )}
        </h3>
        <span className="text-2xl">{stateEmoji}</span>
      </div>

      {/* Main Frequency Display */}
      <div className="text-center mb-4">
        <div className="text-4xl font-bold mb-1" style={{ color: frequencyColor(displayFrequency) }}>
          {displayFrequency} Hz
        </div>
        <div className="text-xs text-muted-foreground">
          {displayState} • Level {displayLevel}
        </div>
      </div>

      {/* Resonance Bar */}
      <div className="mb-4">
        <div className="flex justify-between text-xs mb-1">
          <span className="text-muted-foreground">Resonance</span>
          <span className="text-foreground">{resonance === null ? 'Unavailable' : `${(resonance * 100).toFixed(1)}%`}</span>
        </div>
        <div className="h-2 bg-muted rounded-full overflow-hidden">
          <div
            className="h-full transition-all duration-500 rounded-full"
            style={{
              width: `${resonance === null ? 0 : resonance * 100}%`,
              background: `linear-gradient(90deg, hsl(15, 90%, 55%), hsl(45, 100%, 50%), hsl(150, 100%, 50%))`,
            }}
          />
        </div>
      </div>

      {/* Harmonic Purity */}
      <div className="mb-4">
        <div className="flex justify-between text-xs mb-1">
          <span className="text-muted-foreground">Harmonic Purity</span>
          <span className="text-foreground">{harmonicPurity === null ? 'Unavailable' : `${(harmonicPurity * 100).toFixed(1)}%`}</span>
        </div>
        <div className="h-1.5 bg-muted rounded-full overflow-hidden">
          <div
            className="h-full bg-primary transition-all duration-500 rounded-full"
            style={{ width: `${harmonicPurity === null ? 0 : harmonicPurity * 100}%` }}
          />
        </div>
      </div>

      {/* 5 Layer Visualization */}
      {layerEntries.length > 0 && (
        <div className="grid grid-cols-6 gap-1 text-center">
          {layerEntries.map(([key, value], index) => (
            <div key={key} className="flex flex-col items-center">
              <div
                className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold mb-1 transition-all ${
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
              <span className="text-[9px] text-muted-foreground">{levelLabels[index] ?? key}</span>
              <span className="text-[8px] text-foreground/60">{Math.round(value)}</span>
            </div>
          ))}
        </div>
      )}

      {/* 528 Hz Target Indicator */}
      <div className="mt-4 pt-3 border-t border-border/30">
        <div className="flex items-center justify-between text-xs">
          <span className="text-muted-foreground">Distance to 528 Hz</span>
          <span className={isLoveLocked ? 'text-success font-bold' : 'text-foreground'}>
            {isLoveLocked ? '✓ ALIGNED' : `${Math.abs(displayFrequency - 528)} Hz`}
          </span>
        </div>
      </div>

      <p className="mt-3 text-xs text-muted-foreground">
        Source: {receipt.source ?? 'unreported'} · {receipt.timestamp ?? 'no timestamp'}
      </p>
    </div>
  );
};
