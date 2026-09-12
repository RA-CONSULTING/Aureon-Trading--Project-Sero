BEGIN;

REVOKE ALL PRIVILEGES ON TABLE public.recent_optimal_signals FROM anon;

DROP POLICY IF EXISTS "Service role full access" ON public.exchange_balance_cache;
CREATE POLICY "Service role full access"
  ON public.exchange_balance_cache FOR ALL TO service_role
  USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS "service_role_performance_metrics"
  ON public.harmonic_nexus_performance_metrics;
CREATE POLICY "service_role_performance_metrics"
  ON public.harmonic_nexus_performance_metrics FOR ALL TO service_role
  USING (true) WITH CHECK (true);

COMMIT;
