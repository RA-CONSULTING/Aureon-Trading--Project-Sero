import { useEffect, useRef, useState } from 'react';
import type { QGITASignal } from '@/core/qgitaSignalGenerator';
import { useToast } from '@/hooks/use-toast';
import {
  GOVERNED_ORDER_ACTION_UNAVAILABLE_CODE,
  GOVERNED_ORDER_ACTION_UNAVAILABLE_MESSAGE,
} from '@/lib/tradingActionAvailability';

interface QGITAAutoTradingProps {
  signal: QGITASignal | null;
  symbol: string;
  currentPrice: number;
  enabled: boolean;
}

interface QGITASignalObservation {
  symbol: string;
  signalType: 'BUY' | 'SELL';
  tier: 1 | 2;
  confidence: number;
  price: number;
  sourceTimestamp: number;
  executionAvailable: false;
  executionUnavailableReason: typeof GOVERNED_ORDER_ACTION_UNAVAILABLE_CODE;
  providerMutationAttempted: false;
}

const MAX_PRICE_AGE_MS = 2000;

export function useQGITAAutoTrading({ signal, symbol, currentPrice, enabled }: QGITAAutoTradingProps) {
  const { toast } = useToast();
  const [lastObservation, setLastObservation] = useState<QGITASignalObservation | null>(null);
  const lastObservedSignalRef = useRef<string | null>(null);

  useEffect(() => {
    if (!enabled || !signal || !Number.isFinite(currentPrice) || currentPrice <= 0) return;
    if (signal.tier === 3 || signal.signalType === 'HOLD') return;

    const dataAge = Date.now() - signal.timestamp;
    if (!Number.isFinite(dataAge) || dataAge < 0 || dataAge > MAX_PRICE_AGE_MS) return;

    const signalKey = `${signal.timestamp}-${signal.signalType}-${signal.confidence}`;
    if (lastObservedSignalRef.current === signalKey) return;
    lastObservedSignalRef.current = signalKey;

    setLastObservation({
      symbol,
      signalType: signal.signalType,
      tier: signal.tier,
      confidence: signal.confidence,
      price: currentPrice,
      sourceTimestamp: signal.timestamp,
      executionAvailable: false,
      executionUnavailableReason: GOVERNED_ORDER_ACTION_UNAVAILABLE_CODE,
      providerMutationAttempted: false,
    });
    toast({
      title: 'QGITA signal observed',
      description: GOVERNED_ORDER_ACTION_UNAVAILABLE_MESSAGE,
    });
  }, [enabled, signal, symbol, currentPrice, toast]);

  return {
    isExecuting: false,
    lastObservation,
    executionAvailable: false,
    executionUnavailableReason: GOVERNED_ORDER_ACTION_UNAVAILABLE_MESSAGE,
  };
}

export function useQGITAAutoTradingToggle() {
  return {
    isEnabled: false,
    setIsEnabled: (_enabled: boolean) => {
      void _enabled;
      try {
        localStorage.removeItem('qgita-auto-trading-enabled');
      } catch {
        // Storage access is optional; execution remains unavailable either way.
      }
    },
    executionAvailable: false,
    executionUnavailableReason: GOVERNED_ORDER_ACTION_UNAVAILABLE_MESSAGE,
  };
}
