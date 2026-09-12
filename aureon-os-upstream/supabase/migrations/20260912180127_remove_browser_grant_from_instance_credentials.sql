-- The global Binance credential table is serviced only by trusted backend
-- code.  RLS already restricts its policies to service_role; remove the
-- inherited Data API grants as a second independent boundary.

BEGIN;

REVOKE ALL PRIVILEGES ON TABLE public.binance_credentials FROM anon, authenticated;
GRANT ALL PRIVILEGES ON TABLE public.binance_credentials TO service_role;

COMMIT;
