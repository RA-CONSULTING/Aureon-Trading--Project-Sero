import { useState, useEffect, useCallback } from 'react';
import { supabase } from '@/integrations/supabase/client';
import { api } from '@/services/apiClient';
import { readClosedPositionWarMetrics } from '@/lib/warMetricsClosedPositions';

export interface WarMetrics {
  totalBalance: number;
  netPnLToday: number;
  tradesToday: number;
  winRate: number;
  avgPositionSize: number;
  maxDrawdown: number;
  currentCoherence: number;
  currentLighthouse: number;
  lighthouseEventsToday: number;
  optimalSignalsToday: number;
  queueDepth: number;
  rateLimitUsage: number;
  roiPercent: number;
  closedPositionAnalyticsStatus: 'observed' | 'unavailable';
  closedPositionAnalyticsReason: string;
}

export function useWarMetrics(initialBalance: number = 0) {
  const [metrics, setMetrics] = useState<WarMetrics>({
    totalBalance: initialBalance,
    netPnLToday: 0,
    tradesToday: 0,
    winRate: 0,
    avgPositionSize: 0,
    maxDrawdown: 0,
    currentCoherence: 0,
    currentLighthouse: 0,
    lighthouseEventsToday: 0,
    optimalSignalsToday: 0,
    queueDepth: 0,
    rateLimitUsage: 0,
    roiPercent: 0,
    closedPositionAnalyticsStatus: 'unavailable',
    closedPositionAnalyticsReason: 'Tenant-scoped closed-position analytics has not been read yet.',
  });

  const fetchMetrics = useCallback(async () => {
    try {
      const today = new Date();
      today.setHours(0, 0, 0, 0);

      // Fetch trading executions for today
      const { data: executions, error: execError } = await supabase
        .from('trading_executions')
        .select('*')
        .gte('created_at', today.toISOString());

      if (execError) throw execError;

      // Fetch closed positions for today's P&L through the local backend only.
      // This route enforces user_id tenant scope and keeps Supabase keys out of browser table reads.
      const closedPositionMetrics = readClosedPositionWarMetrics(await api.get('/api/trading/closed-position-analytics?range=24h', {
        timeoutMs: 10_000,
      }).catch(error => ({ available: false, reason: error instanceof Error ? error.message : 'Closed-position analytics backend unavailable' })));

      // Calculate P&L
      const netPnL = closedPositionMetrics.netPnL ?? 0;
      const winRate = closedPositionMetrics.winRate ?? 0;

      // Fetch latest lighthouse event
      const { data: latestLHE } = await supabase
        .from('lighthouse_events')
        .select('coherence, lighthouse_signal, is_lhe')
        .order('timestamp', { ascending: false })
        .limit(1)
        .single();

      // Fetch today's LHE count
      const { count: lheCount } = await supabase
        .from('lighthouse_events')
        .select('*', { count: 'exact', head: true })
        .eq('is_lhe', true)
        .gte('timestamp', today.toISOString());

      // Fetch optimal signals count
      const { count: optimalCount } = await supabase
        .from('trading_signals')
        .select('*', { count: 'exact', head: true })
        .ilike('reason', '%OPTIMAL%')
        .gte('timestamp', today.toISOString());

      // Fetch queue depth
      const { count: queueCount } = await supabase
        .from('oms_order_queue')
        .select('*', { count: 'exact', head: true })
        .in('status', ['queued', 'pending']);

      // Fetch rate limit metrics
      const { data: rateMetrics } = await supabase
        .from('oms_execution_metrics')
        .select('rate_limit_utilization')
        .order('timestamp', { ascending: false })
        .limit(1)
        .single();

      // Calculate average position size
      const avgSize = executions && executions.length > 0
        ? executions.reduce((sum, ex) => sum + ex.position_size_usdt, 0) / executions.length
        : 0;

      // Calculate max drawdown (simplified)
      const maxDrawdown = closedPositionMetrics.netPnL === null ? 0 : Math.min(0, closedPositionMetrics.netPnL);

      // Calculate ROI
      const roi = initialBalance > 0 ? (netPnL / initialBalance) * 100 : 0;

      setMetrics({
        totalBalance: initialBalance + netPnL,
        netPnLToday: netPnL,
        tradesToday: executions?.length || 0,
        winRate,
        avgPositionSize: avgSize,
        maxDrawdown: Math.abs(maxDrawdown),
        currentCoherence: latestLHE?.coherence || 0,
        currentLighthouse: latestLHE?.lighthouse_signal || 0,
        lighthouseEventsToday: lheCount || 0,
        optimalSignalsToday: optimalCount || 0,
        queueDepth: queueCount || 0,
        rateLimitUsage: rateMetrics?.rate_limit_utilization || 0,
        roiPercent: closedPositionMetrics.netPnL === null ? 0 : roi,
        closedPositionAnalyticsStatus: closedPositionMetrics.status,
        closedPositionAnalyticsReason: closedPositionMetrics.reason,
      });

    } catch (error) {
      console.error('Failed to fetch war metrics:', error);
    }
  }, [initialBalance]);

  // Auto-refresh every 5 seconds
  useEffect(() => {
    fetchMetrics();
    const interval = setInterval(fetchMetrics, 5000);
    return () => clearInterval(interval);
  }, [fetchMetrics]);

  return {
    metrics,
    refresh: fetchMetrics,
  };
}
