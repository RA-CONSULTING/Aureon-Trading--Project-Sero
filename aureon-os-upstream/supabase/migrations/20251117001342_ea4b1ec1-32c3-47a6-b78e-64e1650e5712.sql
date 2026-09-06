-- Create trading_config table for risk management settings
CREATE TABLE public.trading_config (
  id UUID NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
  is_enabled BOOLEAN NOT NULL DEFAULT false,
  trading_mode TEXT NOT NULL DEFAULT 'paper' CHECK (trading_mode IN ('paper', 'live')),
  
  -- Position sizing
  base_position_size_usdt NUMERIC NOT NULL DEFAULT 100,
  max_position_size_usdt NUMERIC NOT NULL DEFAULT 1000,
  position_size_mode TEXT NOT NULL DEFAULT 'fixed' CHECK (position_size_mode IN ('fixed', 'percentage', 'kelly')),
  
  -- Risk management
  max_daily_loss_usdt NUMERIC NOT NULL DEFAULT 500,
  max_daily_trades INTEGER NOT NULL DEFAULT 10,
  stop_loss_percentage NUMERIC NOT NULL DEFAULT 2.0,
  take_profit_percentage NUMERIC NOT NULL DEFAULT 5.0,
  
  -- Signal filters
  min_coherence NUMERIC NOT NULL DEFAULT 0.945,
  min_lighthouse_confidence NUMERIC NOT NULL DEFAULT 0.7,
  require_lhe BOOLEAN NOT NULL DEFAULT true,
  min_prism_level INTEGER NOT NULL DEFAULT 3,
  
  -- Allowed symbols
  allowed_symbols TEXT[] NOT NULL DEFAULT ARRAY['BTCUSDT'],
  
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
  updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);

-- Create trading_executions table for trade logs
CREATE TABLE public.trading_executions (
  id UUID NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
  signal_id UUID REFERENCES public.trading_signals(id),
  lighthouse_event_id UUID REFERENCES public.lighthouse_events(id),
  
  symbol TEXT NOT NULL,
  side TEXT NOT NULL CHECK (side IN ('BUY', 'SELL')),
  signal_type TEXT NOT NULL CHECK (signal_type IN ('LONG', 'SHORT')),
  
  -- Order details
  order_type TEXT NOT NULL DEFAULT 'MARKET',
  quantity NUMERIC NOT NULL,
  price NUMERIC,
  executed_price NUMERIC,
  
  -- Position sizing
  position_size_usdt NUMERIC NOT NULL,
  stop_loss_price NUMERIC,
  take_profit_price NUMERIC,
  
  -- Execution status
  status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'filled', 'failed', 'cancelled')),
  exchange_order_id TEXT,
  error_message TEXT,
  
  -- Signal context
  coherence NUMERIC NOT NULL,
  lighthouse_value NUMERIC NOT NULL,
  lighthouse_confidence NUMERIC NOT NULL,
  prism_level INTEGER NOT NULL,
  
  executed_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);

-- Create trading_positions table for active positions
CREATE TABLE public.trading_positions (
  id UUID NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
  execution_id UUID REFERENCES public.trading_executions(id),
  
  symbol TEXT NOT NULL,
  side TEXT NOT NULL CHECK (side IN ('LONG', 'SHORT')),
  
  -- Position details
  entry_price NUMERIC NOT NULL,
  quantity NUMERIC NOT NULL,
  position_value_usdt NUMERIC NOT NULL,
  
  -- Risk management
  stop_loss_price NUMERIC,
  take_profit_price NUMERIC,
  current_price NUMERIC,
  unrealized_pnl NUMERIC DEFAULT 0,
  
  -- Status
  status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'closed')),
  closed_at TIMESTAMP WITH TIME ZONE,
  close_reason TEXT,
  realized_pnl NUMERIC,
  
  opened_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
  updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);

-- Enable RLS
ALTER TABLE public.trading_config ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.trading_executions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.trading_positions ENABLE ROW LEVEL SECURITY;

-- Create policies for public access (for demo - in production use auth)
CREATE POLICY "Allow public read trading config"
ON public.trading_config FOR SELECT USING (true);

CREATE POLICY "Allow public update trading config"
ON public.trading_config FOR UPDATE USING (true);

CREATE POLICY "Allow public insert trading config"
ON public.trading_config FOR INSERT WITH CHECK (true);

CREATE POLICY "Allow public read executions"
ON public.trading_executions FOR SELECT USING (true);

CREATE POLICY "Allow public insert executions"
ON public.trading_executions FOR INSERT WITH CHECK (true);

CREATE POLICY "Allow public read positions"
ON public.trading_positions FOR SELECT USING (true);

CREATE POLICY "Allow public insert positions"
ON public.trading_positions FOR INSERT WITH CHECK (true);

CREATE POLICY "Allow public update positions"
ON public.trading_positions FOR UPDATE USING (true);

-- Create indexes
CREATE INDEX idx_trading_executions_signal ON public.trading_executions(signal_id);
CREATE INDEX idx_trading_executions_status ON public.trading_executions(status);
CREATE INDEX idx_trading_positions_status ON public.trading_positions(status);
CREATE INDEX idx_trading_positions_symbol ON public.trading_positions(symbol);

-- Insert default config
INSERT INTO public.trading_config (
  is_enabled,
  trading_mode,
  base_position_size_usdt,
  max_position_size_usdt,
  max_daily_loss_usdt,
  max_daily_trades,
  stop_loss_percentage,
  take_profit_percentage,
  min_coherence,
  min_lighthouse_confidence,
  require_lhe,
  min_prism_level,
  allowed_symbols
) VALUES (
  false,
  'paper',
  100,
  1000,
  500,
  10,
  2.0,
  5.0,
  0.945,
  0.7,
  true,
  3,
  ARRAY['BTCUSDT', 'ETHUSDT', 'BNBUSDT']
);