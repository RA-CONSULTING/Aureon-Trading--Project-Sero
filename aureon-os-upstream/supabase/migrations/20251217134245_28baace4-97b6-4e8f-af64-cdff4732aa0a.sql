-- Create system_runtime_stats table for terminal metrics persistence
CREATE TABLE public.system_runtime_stats (
  id UUID NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id UUID NOT NULL,
  
  -- Session tracking
  session_start_time TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
  
  -- Portfolio metrics
  peak_equity NUMERIC DEFAULT 0,
  max_drawdown_percent NUMERIC DEFAULT 0,
  current_drawdown_percent NUMERIC DEFAULT 0,
  cycle_pnl NUMERIC DEFAULT 0,
  avg_hold_time_minutes NUMERIC DEFAULT 0,
  
  -- Trading mode
  trading_mode TEXT DEFAULT 'BALANCED',
  entry_coherence_threshold NUMERIC DEFAULT 0.45,
  exit_coherence_threshold NUMERIC DEFAULT 0.35,
  risk_multiplier NUMERIC DEFAULT 1.0,
  take_profit_multiplier NUMERIC DEFAULT 1.2,
  
  -- Frequency state
  gaia_lattice_state TEXT DEFAULT 'NEUTRAL',
  gaia_frequency NUMERIC DEFAULT 432,
  purity_percent INTEGER DEFAULT 0,
  carrier_wave_phi NUMERIC DEFAULT 0,
  harmonic_lock_432 INTEGER DEFAULT 0,
  
  -- HNC state
  hnc_frequency INTEGER DEFAULT 432,
  hnc_market_state TEXT DEFAULT 'CONSOLIDATION',
  hnc_coherence_percent INTEGER DEFAULT 0,
  hnc_modifier NUMERIC DEFAULT 1.0,
  
  -- Mycelium state
  mycelium_hives INTEGER DEFAULT 1,
  mycelium_agents INTEGER DEFAULT 5,
  mycelium_generation INTEGER DEFAULT 0,
  max_generation INTEGER DEFAULT 0,
  queen_state TEXT DEFAULT 'HOLD',
  queen_pnl NUMERIC DEFAULT 0,
  
  -- Capital management
  compounded_capital NUMERIC DEFAULT 0,
  harvested_capital NUMERIC DEFAULT 0,
  pool_total NUMERIC DEFAULT 0,
  pool_available NUMERIC DEFAULT 0,
  scout_count INTEGER DEFAULT 0,
  split_count INTEGER DEFAULT 0,
  
  -- WebSocket stats
  ws_message_count INTEGER DEFAULT 0,
  
  -- Timestamps
  created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

-- Enable Row Level Security
ALTER TABLE public.system_runtime_stats ENABLE ROW LEVEL SECURITY;

-- Create policies for user access
CREATE POLICY "Users can view their own runtime stats" 
ON public.system_runtime_stats 
FOR SELECT 
USING (auth.uid() = user_id);

CREATE POLICY "Users can create their own runtime stats" 
ON public.system_runtime_stats 
FOR INSERT 
WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own runtime stats" 
ON public.system_runtime_stats 
FOR UPDATE 
USING (auth.uid() = user_id);

-- Create index for user lookups
CREATE INDEX idx_system_runtime_stats_user_id ON public.system_runtime_stats(user_id);

-- Create trigger for automatic timestamp updates
CREATE TRIGGER update_system_runtime_stats_updated_at
BEFORE UPDATE ON public.system_runtime_stats
FOR EACH ROW
EXECUTE FUNCTION public.handle_updated_at();

-- Enable realtime for live updates
ALTER PUBLICATION supabase_realtime ADD TABLE public.system_runtime_stats;