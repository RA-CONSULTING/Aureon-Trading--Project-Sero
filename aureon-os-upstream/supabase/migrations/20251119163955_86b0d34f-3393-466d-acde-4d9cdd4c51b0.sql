-- Create scheduler history table to track auto-trading decisions
CREATE TABLE IF NOT EXISTS public.scheduler_history (
  id UUID NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
  timestamp TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
  action TEXT NOT NULL,
  reason TEXT NOT NULL,
  coherence_at_action NUMERIC NOT NULL,
  lighthouse_events_count INTEGER NOT NULL DEFAULT 0,
  trading_enabled_before BOOLEAN NOT NULL,
  trading_enabled_after BOOLEAN NOT NULL,
  daily_activations INTEGER NOT NULL DEFAULT 0,
  metadata JSONB DEFAULT '{}'::jsonb,
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);

-- Enable RLS
ALTER TABLE public.scheduler_history ENABLE ROW LEVEL SECURITY;

-- Create policies
CREATE POLICY "Authenticated users can read scheduler history"
ON public.scheduler_history
FOR SELECT
USING (true);

CREATE POLICY "Service role can insert scheduler history"
ON public.scheduler_history
FOR INSERT
WITH CHECK (true);