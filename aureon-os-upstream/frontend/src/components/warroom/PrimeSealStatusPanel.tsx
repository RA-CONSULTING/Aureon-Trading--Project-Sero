/**
 * Prime Seal Status Panel for War Room
 * Displays 10-9-1 Prime Seal state only when a real runtime seal receipt is
 * published or at least one runtime-backed bus contribution is present.
 */

import { useEffect, useMemo, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { Lock, Unlock, Sparkles, Heart, Shield, AlertCircle } from 'lucide-react';
import { primeSealComputer, type PrimeSealState } from '@/core/primeSealComputer';
import { unifiedBus, type BusSnapshot } from '@/core/unifiedBus';
import { useTerminalState } from '@/hooks/useTerminalState';
import { readWarRoomEvidence, evidenceRecord, evidenceText, type EvidenceRecord } from '@/lib/warRoomEvidence';
import type { TerminalState } from '@/hooks/useTerminalState';

function sealReason(row: EvidenceRecord): string {
  if (row.available !== true) return evidenceText(row.reason) ?? 'Prime Seal receipt is unavailable.';
  if (row.truth_status !== 'real_derived' || row.generated_values !== false) return 'Prime Seal receipt is not provider-derived.';
  return 'Prime Seal receipt is stale or has no valid source timestamp.';
}

function readSealReceipt(state: TerminalState | null): { packet: PrimeSealState['packet'] } | null {
  if (!state) return null;
  const row = evidenceRecord(state.prime_seal_receipt);
  if (row.available !== true || row.truth_status !== 'real_derived' || row.generated_values !== false) {
    return null;
  }
  const packet = evidenceRecord(row.packet ?? row);
  if (typeof packet.prime_coherence !== 'number' || typeof packet.seal_lock !== 'boolean') return null;
  return { packet: packet as unknown as PrimeSealState['packet'] };
}

function hasRuntimeBusContributions(snapshot: BusSnapshot): boolean {
  return Object.values(snapshot.states).some(
    (s) => s.ready && (s.data?.truthStatus === 'real_derived' || s.data?.truth_status === 'real_derived'),
  );
}

export function PrimeSealStatusPanel() {
  const terminal = useTerminalState();
  const evidence = useMemo(
    () => readWarRoomEvidence(terminal.state, terminal.isFresh),
    [terminal.state, terminal.isFresh],
  );

  const sealReceipt = useMemo(() => readSealReceipt(terminal.state), [terminal.state]);
  const [sealState, setSealState] = useState<PrimeSealState | null>(null);

  const hasBusContributions = hasRuntimeBusContributions(unifiedBus.snapshot());

  useEffect(() => {
    const unsubscribeBus = unifiedBus.subscribe((snapshot) => {
      if (!hasRuntimeBusContributions(snapshot)) {
        setSealState(null);
        return;
      }
      setSealState(primeSealComputer.compute(snapshot));
    });

    const initial = unifiedBus.snapshot();
    if (hasRuntimeBusContributions(initial)) {
      setSealState(primeSealComputer.compute(initial));
    } else {
      setSealState(null);
    }

    return () => {
      unsubscribeBus();
    };
  }, []);

  if (!sealReceipt && !hasBusContributions) {
    const row = evidenceRecord(terminal.state?.prime_seal_receipt);
    const reason = evidence.primeSeal.available
      ? 'No runtime-backed 10-9-1 bus contributions are published and the seal receipt lacks required fields.'
      : sealReason(row);
    return (
      <Card className="bg-card/50 backdrop-blur border-primary/20">
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-2 text-lg">
            <Shield className="w-5 h-5 text-muted-foreground" />
            10-9-1 Prime Seal
            <Badge variant="outline" className="ml-auto">Unavailable</Badge>
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex items-start gap-2 text-sm text-muted-foreground">
            <AlertCircle className="w-4 h-4 mt-0.5 text-warning" />
            <span>No fresh Prime Seal runtime observation is available.</span>
          </div>
          <p className="text-xs text-muted-foreground">
            Reason: {reason}
          </p>
          <p className="text-xs text-muted-foreground">
            The panel waits for either a timestamped <code>prime_seal_receipt</code> in /api/terminal-state
            or runtime-backed contributions on the unified bus. Synthetic local computations are not displayed.
          </p>
        </CardContent>
      </Card>
    );
  }

  if (sealReceipt && !sealState) {
    // A seal receipt exists but we have not computed a local state yet.
    const packet = sealReceipt.packet;
    const isLocked = packet.seal_lock;
    return (
      <Card className={`bg-card/50 backdrop-blur border-2 transition-all duration-500 ${
        isLocked ? 'border-success/50 shadow-[0_0_20px_rgba(34,197,94,0.3)]' : 'border-warning/50'
      }`}>
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between">
            <CardTitle className="flex items-center gap-2 text-lg">
              <Shield className={`w-5 h-5 ${isLocked ? 'text-success' : 'text-warning'}`} />
              10-9-1 Prime Seal
            </CardTitle>
            <Badge
              variant={isLocked ? "default" : "secondary"}
              className={isLocked ? "bg-success animate-pulse" : ""}
            >
              {isLocked ? <><Lock className="w-3 h-3 mr-1" /> SEALED</> : <><Unlock className="w-3 h-3 mr-1" /> OPEN</>}
            </Badge>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="p-3 bg-background/30 rounded-lg text-center">
            <div className="flex items-center justify-center gap-2 mb-1">
              <Heart className="w-4 h-4 text-primary" />
              <span className="text-xs text-muted-foreground">Intent</span>
            </div>
            <div className="text-sm font-medium bg-gradient-to-r from-primary to-primary bg-clip-text text-transparent">
              {packet.intent_text ?? 'Observing'}
            </div>
          </div>
          <div>
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs text-muted-foreground">Prime Coherence</span>
              <span className={`text-sm font-bold ${packet.prime_coherence >= 0.945 ? 'text-success' : 'text-warning'}`}>
                {(packet.prime_coherence * 100).toFixed(1)}%
              </span>
            </div>
            <Progress value={packet.prime_coherence * 100} className="h-2" />
          </div>
          <div className="flex items-center justify-between p-2 bg-background/30 rounded-lg">
            <span className="text-xs text-muted-foreground">Signal:</span>
            <Badge variant={packet.consensus_signal === 'BUY' ? 'default' : packet.consensus_signal === 'SELL' ? 'destructive' : 'secondary'}>
              {packet.consensus_signal ?? 'NEUTRAL'}
            </Badge>
          </div>
          <p className="text-xs text-muted-foreground">
            Source: timestamped Prime Seal receipt from /api/terminal-state.
          </p>
        </CardContent>
      </Card>
    );
  }

  if (!sealState) {
    return (
      <Card className="bg-card/50 backdrop-blur border-primary/20">
        <CardContent className="flex items-center justify-center h-32">
          <div className="text-muted-foreground animate-pulse">Computing Prime Seal...</div>
        </CardContent>
      </Card>
    );
  }

  const { packet, unityCoherence, flowCoherence, anchorCoherence } = sealState;
  const isLocked = packet.seal_lock;

  return (
    <Card className={`bg-card/50 backdrop-blur border-2 transition-all duration-500 ${
      isLocked ? 'border-success/50 shadow-[0_0_20px_rgba(34,197,94,0.3)]' : 'border-warning/50'
    }`}>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2 text-lg">
            <Shield className={`w-5 h-5 ${isLocked ? 'text-success' : 'text-warning'}`} />
            10-9-1 Prime Seal
          </CardTitle>
          <Badge
            variant={isLocked ? "default" : "secondary"}
            className={isLocked ? "bg-success animate-pulse" : ""}
          >
            {isLocked ? <><Lock className="w-3 h-3 mr-1" /> SEALED</> : <><Unlock className="w-3 h-3 mr-1" /> OPEN</>}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Intent Broadcast */}
        <div className="p-3 bg-background/30 rounded-lg text-center">
          <div className="flex items-center justify-center gap-2 mb-1">
            <Heart className="w-4 h-4 text-primary" />
            <span className="text-xs text-muted-foreground">Intent</span>
          </div>
          <div className="text-sm font-medium bg-gradient-to-r from-primary to-primary bg-clip-text text-transparent">
            {packet.intent_text}
          </div>
        </div>

        {/* Prime Coherence Meter */}
        <div>
          <div className="flex items-center justify-between mb-1">
            <span className="text-xs text-muted-foreground">Prime Coherence</span>
            <span className={`text-sm font-bold ${packet.prime_coherence >= 0.945 ? 'text-success' : 'text-warning'}`}>
              {(packet.prime_coherence * 100).toFixed(1)}%
            </span>
          </div>
          <Progress value={packet.prime_coherence * 100} className="h-2" />
          <div className="flex justify-between mt-0.5">
            <span className="text-[10px] text-muted-foreground">0%</span>
            <span className="text-[10px] text-success">Lock: 94.5%</span>
            <span className="text-[10px] text-muted-foreground">100%</span>
          </div>
        </div>

        {/* 10-9-1 Weights Display */}
        <div className="grid grid-cols-3 gap-2">
          <div className="p-2 bg-primary/10 rounded-lg text-center border border-primary/30">
            <div className="text-[10px] text-muted-foreground mb-0.5">Unity (×10)</div>
            <div className="text-lg font-bold text-primary">{(unityCoherence * 100).toFixed(0)}%</div>
            <Sparkles className="w-3 h-3 mx-auto mt-0.5 text-primary" />
          </div>
          <div className="p-2 bg-primary/10 rounded-lg text-center border border-primary/30">
            <div className="text-[10px] text-muted-foreground mb-0.5">Flow (×9)</div>
            <div className="text-lg font-bold text-primary">{(flowCoherence * 100).toFixed(0)}%</div>
            <Sparkles className="w-3 h-3 mx-auto mt-0.5 text-primary" />
          </div>
          <div className="p-2 bg-warning/10 rounded-lg text-center border border-warning/30">
            <div className="text-[10px] text-muted-foreground mb-0.5">Anchor (×1)</div>
            <div className="text-lg font-bold text-warning">{(anchorCoherence * 100).toFixed(0)}%</div>
            <Sparkles className="w-3 h-3 mx-auto mt-0.5 text-warning" />
          </div>
        </div>

        {/* Signal */}
        <div className="flex items-center justify-between p-2 bg-background/30 rounded-lg">
          <div className="flex items-center gap-2">
            <span className="text-xs text-muted-foreground">Signal:</span>
            <Badge variant={packet.consensus_signal === 'BUY' ? 'default' : packet.consensus_signal === 'SELL' ? 'destructive' : 'secondary'}>
              {packet.consensus_signal}
            </Badge>
          </div>
          <div className="text-right">
            <span className="text-xs text-muted-foreground">Packet Value: </span>
            <span className="text-sm font-bold">{packet.packet_value.toFixed(2)}</span>
          </div>
        </div>

        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <span className="h-2 w-2 rounded-full bg-success animate-pulse" />
          Runtime-backed bus contributions: {packet.systems_contributing.join(', ') || 'none'}
        </div>
      </CardContent>
    </Card>
  );
}
