import { supabase } from '@/integrations/supabase/client';
import { unavailableTradingAction } from '@/lib/tradingActionAvailability';

export interface ValidationStep {
  step: number;
  name: string;
  status: 'pending' | 'running' | 'success' | 'failed';
  input?: Record<string, unknown>;
  output?: Record<string, unknown>;
  error?: string;
  timestamp: string;
}

export interface ValidationTrace {
  steps: ValidationStep[];
  startTime: string;
  endTime?: string;
  success: boolean;
  tradeId?: string;
  orderId?: string;
}

export interface ForceTradeResult {
  success: boolean;
  available: false;
  trace: ValidationTrace;
  message: string;
  error?: string;
  providerMutationAttempted: false;
}

export async function forceValidatedTrade(
  userId: string,
  symbol: string = 'BTCUSDT',
  side: 'BUY' | 'SELL' = 'BUY',
  mode: 'paper' | 'live' = 'paper'
): Promise<ForceTradeResult> {
  void userId;
  void symbol;
  void side;
  void mode;
  const unavailable = unavailableTradingAction('force_validated_trade');
  return {
    success: false,
    available: false,
    trace: { steps: [], startTime: new Date().toISOString(), success: false },
    message: unavailable.message,
    error: unavailable.code,
    providerMutationAttempted: unavailable.provider_mutation_attempted,
  };
}

// Get the last forced validation trade - simplified to avoid type issues
export async function getLastForcedValidation(userId: string): Promise<ValidationTrace | null> {
  try {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const { data, error } = await (supabase as any)
      .from('trading_executions')
      .select('validation_trace')
      .eq('user_id', userId)
      .eq('is_forced_validation', true)
      .order('created_at', { ascending: false })
      .limit(1);

    if (error || !data || data.length === 0) {
      return null;
    }

    const trace = data[0]?.validation_trace;
    if (typeof trace === 'object' && trace !== null && 'steps' in trace && 'startTime' in trace) {
      return trace as ValidationTrace;
    }
    
    return null;
  } catch {
    return null;
  }
}
