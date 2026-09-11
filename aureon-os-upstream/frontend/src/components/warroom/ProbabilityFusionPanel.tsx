/**
 * Probability Fusion Panel for War Room
 * Displays HNC Probability Matrix fusion results only when a real runtime
 * receipt is published. Never fabricates inputs or falls back to the singleton.
 */

import { useMemo } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { Blend, Target, TrendingUp, TrendingDown, Minus, Zap, AlertCircle } from 'lucide-react';
import { useTerminalState } from '@/hooks/useTerminalState';
import { readWarRoomEvidence, evidenceNumber, evidenceText, evidenceRecord, type EvidenceRecord } from '@/lib/warRoomEvidence';
import { probabilityMatrix, type ProbabilityFusion, type TradingAction } from '@/core/enhanced6DProbabilityMatrix';
import type { TerminalState } from '@/hooks/useTerminalState';

type FusionReceipt = {
  fusion: ProbabilityFusion;
  hasInputs: boolean;
  hasConfidence: boolean;
  hasWaveState: boolean;
  hasResonanceBoost: boolean;
};

function readFusionReceipt(state: TerminalState | null): FusionReceipt | null {
  if (!state) return null;
  const row = evidenceRecord(
    state.probability_fusion_receipt
    ?? (state.hnc_cognitive_proof as Record<string, unknown> | undefined)?.probability_fusion,
  );
  if (row.available !== true || row.truth_status !== 'real_derived' || row.generated_values !== false) {
    return null;
  }
  const fusedProbability = evidenceNumber(row.fused_probability ?? row.fusedProbability);
  if (fusedProbability === null || fusedProbability < 0 || fusedProbability > 1) return null;

  const probability6D = evidenceNumber(row.probability_6d ?? row.probability6D);
  const probabilityHNC = evidenceNumber(row.probability_hnc ?? row.probabilityHNC);
  const probabilityLighthouse = evidenceNumber(row.probability_lighthouse ?? row.probabilityLighthouse);
  const confidence = evidenceNumber(row.confidence);
  const actionText = evidenceText(row.action) as TradingAction | null;

  const action: TradingAction = actionText ?? (fusedProbability >= 0.55 ? 'BUY' : fusedProbability <= 0.45 ? 'SELL' : 'HOLD');

  const fusion: ProbabilityFusion = {
    probability6D: probability6D ?? 0.5,
    probabilityHNC: probabilityHNC ?? 0.5,
    probabilityLighthouse: probabilityLighthouse ?? 0.5,
    weight6D: evidenceNumber(row.weight_6d ?? row.weight6D) ?? 0.33,
    weightHNC: evidenceNumber(row.weight_hnc ?? row.weightHNC) ?? 0.34,
    weightLighthouse: evidenceNumber(row.weight_lighthouse ?? row.weightLighthouse) ?? 0.33,
    fusedProbability,
    action,
    confidence: confidence ?? Math.abs(fusedProbability - 0.5) * 2,
    waveState: (evidenceText(row.wave_state ?? row.waveState) as ProbabilityFusion['waveState']) ?? 'RESONANT',
    harmonicLock: row.harmonic_lock === true || row.harmonicLock === true,
    resonanceBoost: evidenceNumber(row.resonance_boost ?? row.resonanceBoost) ?? 0,
  };

  return {
    fusion,
    hasInputs: probability6D !== null && probabilityHNC !== null && probabilityLighthouse !== null,
    hasConfidence: confidence !== null,
    hasWaveState: evidenceText(row.wave_state ?? row.waveState) !== null,
    hasResonanceBoost: evidenceNumber(row.resonance_boost ?? row.resonanceBoost) !== null,
  };
}

function unavailableReason(row: EvidenceRecord): string {
  if (row.available !== true) return evidenceText(row.reason) ?? 'ProbabilityMatrix receipt is unavailable.';
  if (row.truth_status !== 'real_derived' || row.generated_values !== false) return 'ProbabilityMatrix receipt is not provider-derived.';
  return 'ProbabilityMatrix receipt is stale or has no valid source timestamp.';
}

export function ProbabilityFusionPanel() {
  const terminal = useTerminalState();
  const evidence = useMemo(
    () => readWarRoomEvidence(terminal.state, terminal.isFresh),
    [terminal.state, terminal.isFresh],
  );

  // Stop polling the singleton matrix; only a real terminal receipt is allowed.
  const receipt = useMemo(() => readFusionReceipt(terminal.state), [terminal.state]);
  const fusionMetric = evidence.probabilityFusion;
  const hasReceipt = fusionMetric.available && receipt !== null;

  if (!hasReceipt) {
    const row = evidenceRecord(terminal.state?.probability_fusion_receipt);
    const reason = fusionMetric.available
      ? 'ProbabilityMatrix receipt is missing required fusion fields.'
      : unavailableReason(row);
    return (
      <Card className="bg-card/50 backdrop-blur border-primary/20">
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-2 text-lg">
            <Blend className="w-5 h-5 text-primary" />
            Probability Fusion
            <Badge variant="outline" className="ml-auto">Unavailable</Badge>
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex items-start gap-2 text-sm text-muted-foreground">
            <AlertCircle className="w-4 h-4 mt-0.5 text-warning" />
            <span>No real probability fusion receipt is available.</span>
          </div>
          <p className="text-xs text-muted-foreground">
            Reason: {reason}
          </p>
          <p className="text-xs text-muted-foreground">
            The panel waits for a timestamped ProbabilityMatrix runtime receipt (truth_status: real_derived,
            generated_values: false) from /api/terminal-state. Singleton matrix cache is not used.
          </p>
        </CardContent>
      </Card>
    );
  }

  const { fusion, hasInputs, hasConfidence, hasResonanceBoost } = receipt;

  const ActionIcon = fusion.action.includes('BUY') ? TrendingUp :
                     fusion.action.includes('SELL') ? TrendingDown : Minus;

  const actionColor = fusion.action.includes('BUY') ? 'text-success' :
                      fusion.action.includes('SELL') ? 'text-destructive' : 'text-muted-foreground';

  return (
    <Card className={`bg-card/50 backdrop-blur border-primary/20 transition-all duration-500 ${
      fusion.harmonicLock ? 'border-success/50 shadow-[0_0_20px_rgba(34,197,94,0.3)]' : ''
    }`}>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2 text-lg">
            <Blend className="w-5 h-5 text-primary" />
            Probability Fusion
          </CardTitle>
          {fusion.harmonicLock && (
            <Badge className="bg-success animate-pulse">
              <Zap className="w-3 h-3 mr-1" /> HARMONIC LOCK
            </Badge>
          )}
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {/* Input Probabilities */}
        <div className="space-y-2">
          {hasInputs ? (
            <>
              <ProbabilityBar label="6D Harmonic" value={fusion.probability6D} weight={fusion.weight6D} color="bg-primary" />
              <ProbabilityBar label="HNC Matrix" value={fusion.probabilityHNC} weight={fusion.weightHNC} color="bg-primary" />
              <ProbabilityBar label="Lighthouse" value={fusion.probabilityLighthouse} weight={fusion.weightLighthouse} color="bg-warning" />
            </>
          ) : (
            <p className="text-xs text-muted-foreground">
              Individual probability inputs are not included in this runtime receipt.
            </p>
          )}
        </div>

        {/* Fused Probability Meter */}
        <div className="p-3 bg-background/30 rounded-lg">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs text-muted-foreground">Fused Probability</span>
            {hasResonanceBoost && (
              <span className="text-xs text-success">+{(fusion.resonanceBoost * 100).toFixed(0)}% boost</span>
            )}
          </div>

          <div className="relative h-5 bg-muted/30 rounded-full overflow-hidden mb-2">
            <div className="absolute inset-0 bg-gradient-to-r from-destructive via-warning to-success opacity-30" />
            <div
              className="absolute top-0 bottom-0 w-1 bg-white shadow-lg transition-all duration-500"
              style={{ left: `${fusion.fusedProbability * 100}%` }}
            />
            <div
              className="absolute top-0 bottom-0 flex items-center transition-all duration-500"
              style={{ left: `${fusion.fusedProbability * 100}%`, transform: 'translateX(-50%)' }}
            >
              <span className="text-xs font-bold bg-background/80 px-1 rounded">
                {(fusion.fusedProbability * 100).toFixed(1)}%
              </span>
            </div>
          </div>
        </div>

        {/* Action & Confidence */}
        <div className="flex items-center justify-between p-2 bg-background/30 rounded-lg">
          <div className="flex items-center gap-2">
            <ActionIcon className={`w-5 h-5 ${actionColor}`} />
            <span className={`text-lg font-bold ${actionColor}`}>
              {fusion.action.replace('_', ' ')}
            </span>
          </div>
          <div className="text-right flex items-center gap-1">
            <Target className="w-4 h-4 text-muted-foreground" />
            <span className="text-sm font-bold">
              {hasConfidence ? `${(fusion.confidence * 100).toFixed(0)}%` : 'Unavailable'}
            </span>
          </div>
        </div>

        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <span className="h-2 w-2 rounded-full bg-success animate-pulse" />
          Runtime receipt observed.
          {fusionMetric.timestamp && (
            <span className="break-all">Source: {fusionMetric.timestamp}</span>
          )}
        </div>
        <p className="text-xs text-muted-foreground">
          Singleton matrix has runtime data: {probabilityMatrix.hasRuntimeData() ? 'yes' : 'no'}
        </p>
      </CardContent>
    </Card>
  );
}

function ProbabilityBar({ label, value, weight, color }: { label: string; value: number; weight: number; color: string }) {
  const direction = value >= 0.5 ? 'BULL' : 'BEAR';
  const dirColor = value >= 0.5 ? 'text-success' : 'text-destructive';

  return (
    <div>
      <div className="flex items-center justify-between mb-0.5">
        <div className="flex items-center gap-2">
          <span className="text-xs">{label}</span>
          <span className="text-[10px] text-muted-foreground">({(weight * 100).toFixed(0)}%)</span>
        </div>
        <div className="flex items-center gap-2">
          <span className={`text-[10px] ${dirColor}`}>{direction}</span>
          <span className="text-xs font-mono">{(value * 100).toFixed(0)}%</span>
        </div>
      </div>
      <Progress value={value * 100} className={`h-1.5 ${color}`} />
    </div>
  );
}
