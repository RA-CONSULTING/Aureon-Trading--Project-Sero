import { useState, useEffect, useCallback, useRef } from 'react';
import { useMarketScanner, type MarketOpportunity } from './useMarketScanner';
import { useToast } from '@/hooks/use-toast';
import { QGITASignalGenerator } from '@/core/qgitaSignalGenerator';
import { MasterEquation } from '@/core/masterEquation';
import type { MarketSnapshot } from '@/core/aurisNodes';
import { unavailableTradingAction } from '@/lib/tradingActionAvailability';

const LIGHTHOUSE_THRESHOLD = 0.945;

export function useAutonomousTrading() {
  const [isActive, setIsActive] = useState(false);
  const [signalObservations, setSignalObservations] = useState<Record<string, unknown>[]>([]);
  const { opportunities, scanMarket, isScanning, totalPairs, lastError } = useMarketScanner();
  const { toast } = useToast();
  const signalGenerator = useRef(new QGITASignalGenerator());
  const masterEquation = useRef(new MasterEquation());
  const processingRef = useRef(false);

  const processOpportunity = useCallback(async (opp: MarketOpportunity) => {
    const snapshot: MarketSnapshot = {
      price: opp.price,
      volume: opp.volume24h,
      volatility: opp.volatility,
      momentum: opp.momentum,
      spread: opp.spread,
      timestamp: opp.timestamp,
      truthStatus: opp.truthStatus,
      sourceId: opp.sourceId,
      sourceTimestamp: opp.sourceTimestamp,
      generatedValues: false,
    };
    const lambdaState = await masterEquation.current.step(snapshot);
    if (lambdaState.coherence < LIGHTHOUSE_THRESHOLD) return;

    const signal = signalGenerator.current.generateSignal(
      snapshot.timestamp,
      snapshot.price,
      snapshot.volume,
      lambdaState.lambda,
      lambdaState.coherence,
      lambdaState.substrate,
      lambdaState.observer,
      lambdaState.echo,
      snapshot,
    );
    if (!signal || !signal.lighthouse.isLHE || signal.tier !== 1 || signal.signalType === 'HOLD') return;

    const unavailable = unavailableTradingAction('autonomous_signal_order');
    setSignalObservations((observations) => [...observations, {
      symbol: opp.symbol,
      signalType: signal.signalType,
      confidence: signal.confidence,
      tier: signal.tier,
      coherence: lambdaState.coherence,
      truthStatus: opp.truthStatus,
      sourceId: opp.sourceId,
      sourceTimestamp: opp.sourceTimestamp,
      generatedValues: false,
      executionAvailable: unavailable.available,
      executionUnavailableReason: unavailable.code,
      providerMutationAttempted: unavailable.provider_mutation_attempted,
    }].slice(-100));
  }, []);

  useEffect(() => {
    if (!isActive || processingRef.current || opportunities.length === 0) return;
    let cancelled = false;
    const run = async () => {
      processingRef.current = true;
      try {
        for (const opportunity of opportunities.slice(0, 20)) {
          if (cancelled) break;
          try {
            await processOpportunity(opportunity);
          } catch (error) {
            console.error(`[AutonomousTrading] ${opportunity.symbol}:`, error);
          }
        }
      } finally {
        processingRef.current = false;
      }
    };
    run();
    return () => { cancelled = true; };
  }, [opportunities, isActive, processOpportunity]);

  useEffect(() => {
    if (!isActive) return;
    scanMarket();
    const interval = setInterval(scanMarket, 30_000);
    return () => clearInterval(interval);
  }, [isActive, scanMarket]);

  const start = useCallback(() => {
    setIsActive(true);
    toast({
      title: 'Autonomous analysis scan enabled',
      description: 'Live order execution is disabled. Only market scanning and signal observation are active.',
    });
  }, [toast]);

  const stop = useCallback(() => {
    setIsActive(false);
    toast({
      title: 'Autonomous analysis stopped',
      description: `${signalObservations.length} qualifying signals observed. No orders were attempted.`,
    });
  }, [signalObservations.length, toast]);

  return {
    isActive,
    isScanning,
    tradesExecuted: 0,
    totalProfit: null,
    totalFees: null,
    netProfit: null,
    executionReceipts: [],
    signalObservations,
    executionAvailable: false,
    executionUnavailableReason: unavailableTradingAction('autonomous_signal_order').message,
    opportunities: opportunities.slice(0, 20),
    totalPairs,
    lastError,
    start,
    stop,
  };
}
