-- Fix security issues from previous migration

-- Drop and recreate the view without SECURITY DEFINER issues
DROP VIEW IF EXISTS public.recent_optimal_signals;

-- Create view with proper security context (views are SECURITY INVOKER by default)
CREATE VIEW public.recent_optimal_signals 
WITH (security_invoker = true)
AS
SELECT 
  ts.id,
  ts.timestamp,
  ts.signal_type,
  ts.strength,
  ts.reason,
  ts.coherence,
  ts.lighthouse_value,
  le.is_lhe,
  le.lighthouse_signal,
  le.confidence as lhe_confidence
FROM public.trading_signals ts
LEFT JOIN public.lighthouse_events le ON ts.lighthouse_event_id = le.id
WHERE ts.signal_type = 'LONG' 
  AND ts.strength > 0.7
  AND ts.timestamp > now() - interval '24 hours'
ORDER BY ts.timestamp DESC;

-- Drop and recreate function with proper search_path
DROP FUNCTION IF EXISTS public.get_signal_statistics(INTERVAL);

CREATE OR REPLACE FUNCTION public.get_signal_statistics(
  time_range INTERVAL DEFAULT '24 hours'
)
RETURNS TABLE (
  total_signals BIGINT,
  long_signals BIGINT,
  short_signals BIGINT,
  hold_signals BIGINT,
  optimal_signals BIGINT,
  avg_strength DECIMAL,
  lhe_count BIGINT
) 
LANGUAGE SQL
STABLE
SECURITY INVOKER
SET search_path = public
AS $$
  SELECT 
    COUNT(*)::BIGINT as total_signals,
    COUNT(*) FILTER (WHERE signal_type = 'LONG')::BIGINT as long_signals,
    COUNT(*) FILTER (WHERE signal_type = 'SHORT')::BIGINT as short_signals,
    COUNT(*) FILTER (WHERE signal_type = 'HOLD')::BIGINT as hold_signals,
    COUNT(*) FILTER (WHERE reason LIKE '🎯 OPTIMAL%')::BIGINT as optimal_signals,
    AVG(strength) as avg_strength,
    (SELECT COUNT(*)::BIGINT FROM public.lighthouse_events 
     WHERE is_lhe = true 
     AND timestamp > now() - time_range) as lhe_count
  FROM public.trading_signals
  WHERE timestamp > now() - time_range;
$$;