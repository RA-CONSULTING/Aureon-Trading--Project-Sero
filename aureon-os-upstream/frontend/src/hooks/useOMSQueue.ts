import { useState, useEffect, useCallback } from 'react';
import { supabase } from '@/integrations/supabase/client';
import { useToast } from '@/hooks/use-toast';
import { GOVERNED_ORDER_ACTION_UNAVAILABLE_MESSAGE } from '@/lib/tradingActionAvailability';

export interface OMSStatus {
  queueDepth: number;
  processing: number;
  rateLimit: {
    limit: number;
    used: number;
    available: number;
    utilization: number;
    windowDurationMs: number;
  } | null;
  metrics: {
    queue_depth: number;
    current_window_orders: number;
    rate_limit_utilization: number;
    orders_executed_last_minute: number;
    orders_failed_last_minute: number;
  } | null;
  readState: 'observed';
  mutationActionsAvailable: false;
  mutationUnavailableReason: string;
}

export interface QueuedOrder {
  id: string;
  symbol: string;
  side: 'BUY' | 'SELL';
  quantity: number;
  price: number;
  priority: number;
  status: string;
  queued_at: string;
}

export function useOMSQueue(sessionId: string | null) {
  const [status, setStatus] = useState<OMSStatus | null>(null);
  const [orders, setOrders] = useState<QueuedOrder[]>([]);
  const { toast } = useToast();

  const fetchOrders = useCallback(async () => {
    if (!sessionId) return;

    try {
      const { data, error } = await supabase
        .from('oms_order_queue')
        .select('*')
        .eq('session_id', sessionId)
        .in('status', ['queued', 'processing'])
        .order('priority', { ascending: false })
        .order('queued_at', { ascending: true });

      if (error) throw error;
      const observedOrders = (data || []).map(order => ({
        ...order,
        side: order.side as 'BUY' | 'SELL',
      }));
      setOrders(observedOrders);
      setStatus({
        queueDepth: observedOrders.filter(order => order.status === 'queued').length,
        processing: observedOrders.filter(order => order.status === 'processing').length,
        rateLimit: null,
        metrics: null,
        readState: 'observed',
        mutationActionsAvailable: false,
        mutationUnavailableReason: GOVERNED_ORDER_ACTION_UNAVAILABLE_MESSAGE,
      });
    } catch (error) {
      console.error('Failed to fetch orders:', error);
    }
  }, [sessionId]);

  const enqueueOrder = useCallback(async (orderParams: {
    hiveId: string;
    agentId: string;
    symbol: string;
    side: 'BUY' | 'SELL';
    quantity: number;
    price: number;
    priority?: number;
    metadata?: {
      signalStrength?: number;
      coherence?: number;
      lighthouseValue?: number;
    };
  }) => {
    void orderParams;
    if (!sessionId) return null;
    toast({
      title: 'Order action unavailable',
      description: GOVERNED_ORDER_ACTION_UNAVAILABLE_MESSAGE,
      variant: 'destructive',
    });
    return null;
  }, [sessionId, toast]);

  const processQueue = useCallback(async () => {
    if (!sessionId) return;
    toast({
      title: 'Queue processing unavailable',
      description: GOVERNED_ORDER_ACTION_UNAVAILABLE_MESSAGE,
      variant: 'destructive',
    });
  }, [sessionId, toast]);

  const cancelOrder = useCallback(async (orderId: string) => {
    void orderId;
    toast({
      title: 'Queue cancellation unavailable',
      description: GOVERNED_ORDER_ACTION_UNAVAILABLE_MESSAGE,
      variant: 'destructive',
    });
  }, [toast]);

  // Auto-refresh status every 2 seconds
  useEffect(() => {
    if (!sessionId) return;

    fetchOrders();

    const interval = setInterval(() => {
      fetchOrders();
    }, 2000);

    return () => clearInterval(interval);
  }, [sessionId, fetchOrders]);

  return {
    status,
    orders,
    enqueueOrder,
    processQueue,
    cancelOrder,
    isProcessing: false,
    mutationActionsAvailable: false,
    mutationUnavailableReason: GOVERNED_ORDER_ACTION_UNAVAILABLE_MESSAGE,
  };
}
