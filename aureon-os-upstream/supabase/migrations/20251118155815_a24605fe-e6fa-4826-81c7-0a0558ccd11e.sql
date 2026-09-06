-- Create table for consciousness field history
CREATE TABLE IF NOT EXISTS public.consciousness_field_history (
  id UUID NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
  timestamp TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
  
  -- Schumann Resonance metrics
  schumann_frequency NUMERIC NOT NULL,
  schumann_amplitude NUMERIC NOT NULL,
  schumann_quality NUMERIC NOT NULL,
  schumann_coherence_boost NUMERIC NOT NULL,
  schumann_phase TEXT NOT NULL,
  
  -- Biometric metrics
  hrv NUMERIC,
  heart_rate NUMERIC,
  alpha_waves NUMERIC,
  theta_waves NUMERIC,
  delta_waves NUMERIC,
  beta_waves NUMERIC,
  biometric_coherence_index NUMERIC,
  
  -- Celestial boost for context
  celestial_boost NUMERIC NOT NULL DEFAULT 0,
  
  -- Overall coherence
  total_coherence NUMERIC NOT NULL,
  
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);

-- Enable Row Level Security
ALTER TABLE public.consciousness_field_history ENABLE ROW LEVEL SECURITY;

-- Create policies for public access
CREATE POLICY "Allow public read access to consciousness history"
  ON public.consciousness_field_history
  FOR SELECT
  USING (true);

CREATE POLICY "Allow public insert to consciousness history"
  ON public.consciousness_field_history
  FOR INSERT
  WITH CHECK (true);

-- Create index for faster time-based queries
CREATE INDEX IF NOT EXISTS idx_consciousness_history_timestamp 
  ON public.consciousness_field_history(timestamp DESC);

-- Enable realtime
ALTER PUBLICATION supabase_realtime ADD TABLE public.consciousness_field_history;