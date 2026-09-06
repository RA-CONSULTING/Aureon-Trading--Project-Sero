-- Create table for coherence history tracking
CREATE TABLE IF NOT EXISTS public.coherence_history (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  timestamp TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
  coherence NUMERIC NOT NULL,
  lambda_value NUMERIC NOT NULL,
  day_of_week INTEGER NOT NULL, -- 0-6 (Sunday-Saturday)
  hour_of_day INTEGER NOT NULL, -- 0-23
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Enable RLS
ALTER TABLE public.coherence_history ENABLE ROW LEVEL SECURITY;

-- Create policies for public access
CREATE POLICY "Allow public insert to coherence history"
  ON public.coherence_history
  FOR INSERT
  WITH CHECK (true);

CREATE POLICY "Allow public read access to coherence history"
  ON public.coherence_history
  FOR SELECT
  USING (true);

-- Create index for faster queries by time ranges
CREATE INDEX idx_coherence_history_timestamp ON public.coherence_history(timestamp DESC);
CREATE INDEX idx_coherence_history_day_hour ON public.coherence_history(day_of_week, hour_of_day);

-- Add comment
COMMENT ON TABLE public.coherence_history IS 'Historical coherence C(t) values for temporal analysis and heatmap generation';
