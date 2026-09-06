-- Create table for solar flare correlation analysis
CREATE TABLE IF NOT EXISTS public.solar_flare_correlations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  flare_class TEXT NOT NULL,
  flare_time TIMESTAMP WITH TIME ZONE NOT NULL,
  flare_power NUMERIC NOT NULL,
  avg_coherence_before NUMERIC,
  avg_coherence_during NUMERIC,
  avg_coherence_after NUMERIC,
  coherence_boost NUMERIC,
  trading_signals_count INTEGER DEFAULT 0,
  optimal_signals_count INTEGER DEFAULT 0,
  lhe_events_count INTEGER DEFAULT 0,
  avg_signal_strength NUMERIC,
  win_rate NUMERIC,
  avg_return NUMERIC,
  prediction_score NUMERIC,
  analysis_window_hours INTEGER DEFAULT 24,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

-- Enable RLS
ALTER TABLE public.solar_flare_correlations ENABLE ROW LEVEL SECURITY;

-- Create policies
CREATE POLICY "Allow public read access to solar flare correlations"
  ON public.solar_flare_correlations FOR SELECT
  USING (true);

CREATE POLICY "Allow public insert to solar flare correlations"
  ON public.solar_flare_correlations FOR INSERT
  WITH CHECK (true);

CREATE POLICY "Allow public update to solar flare correlations"
  ON public.solar_flare_correlations FOR UPDATE
  USING (true);

-- Create index for faster queries
CREATE INDEX idx_solar_flare_time ON public.solar_flare_correlations(flare_time DESC);
CREATE INDEX idx_solar_flare_class ON public.solar_flare_correlations(flare_class);
CREATE INDEX idx_solar_flare_prediction ON public.solar_flare_correlations(prediction_score DESC NULLS LAST);