import { useState, useEffect } from 'react';
import { supabase } from '@/integrations/supabase/client';

export interface HistoricalDataPoint {
  timestamp: string;
  coherence: number;
  lighthouse: number;
  pnl: number | null;
  balance: number | null;
  observedAt: string;
}

export interface UseHistoricalDataResult {
  data: HistoricalDataPoint[];
  loading: boolean;
  reason: string | null;
}

interface ClosedPosition {
  closed_at: string;
  realized_pnl: number;
}

export function useHistoricalData(): UseHistoricalDataResult {
  const [data, setData] = useState<HistoricalDataPoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [reason, setReason] = useState<string | null>(null);

  useEffect(() => {
    const fetchHistoricalData = async () => {
      setLoading(true);
      setReason(null);

      try {
        const cutoff = new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString();

        const { data: lighthouseData, error: lighthouseError } = await supabase
          .from('lighthouse_events')
          .select('timestamp, coherence, lighthouse_signal, created_at')
          .gte('timestamp', cutoff)
          .order('timestamp', { ascending: true });

        if (lighthouseError) {
          setData([]);
          setReason(lighthouseError.message);
          return;
        }

        if (!lighthouseData || lighthouseData.length === 0) {
          setData([]);
          setReason('No lighthouse observations have been recorded in the last 24 hours.');
          return;
        }

        const { data: closedPositions } = await supabase
          .from('trading_positions')
          .select('closed_at, realized_pnl')
          .eq('status', 'closed')
          .gte('closed_at', cutoff)
          .order('closed_at', { ascending: true });

        const realized: ClosedPosition[] = (closedPositions || [])
          .map((p) => ({
            closed_at: p.closed_at,
            realized_pnl: p.realized_pnl,
          }))
          .filter(
            (p): p is ClosedPosition =>
              typeof p.closed_at === 'string' &&
              typeof p.realized_pnl === 'number' &&
              Number.isFinite(p.realized_pnl),
          );

        let positionIndex = 0;
        let cumulativePnl = 0;
        const hasRealizedPnl = realized.length > 0;

        const merged: HistoricalDataPoint[] = lighthouseData.map((point) => {
          const ts = point.timestamp;
          while (
            positionIndex < realized.length &&
            realized[positionIndex].closed_at <= ts
          ) {
            cumulativePnl += realized[positionIndex].realized_pnl;
            positionIndex += 1;
          }

          return {
            timestamp: point.timestamp,
            coherence: point.coherence,
            lighthouse: point.lighthouse_signal,
            pnl: hasRealizedPnl ? cumulativePnl : null,
            balance: null,
            observedAt: point.created_at,
          };
        });

        setData(merged);
      } catch (error) {
        console.error('Failed to fetch historical data:', error);
        setData([]);
        setReason('Failed to load historical data.');
      } finally {
        setLoading(false);
      }
    };

    fetchHistoricalData();
    const interval = setInterval(fetchHistoricalData, 10000);
    return () => clearInterval(interval);
  }, []);

  return { data, loading, reason };
}
