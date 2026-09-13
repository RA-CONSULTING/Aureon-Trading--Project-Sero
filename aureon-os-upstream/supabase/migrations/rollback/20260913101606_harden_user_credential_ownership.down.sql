-- Exact rollback for 20260913101606_harden_user_credential_ownership.sql.
-- Generated from the live catalog captured at 2026-09-13T13:14:50.069662+00:00.
-- This restores the prior, less secure browser grants and must be paired with
-- an application rollback to the matching pre-migration revision.

BEGIN;

DROP FUNCTION IF EXISTS public.get_aureon_user_session_status();
DROP VIEW IF EXISTS public.aureon_user_session_status;

DROP POLICY IF EXISTS "Users can view own safe session status"
  ON public.aureon_user_sessions;
DROP POLICY IF EXISTS "Users can insert own session"
  ON public.aureon_user_sessions;
DROP POLICY IF EXISTS "Users can update own session"
  ON public.aureon_user_sessions;
DROP POLICY IF EXISTS "Users can view own session"
  ON public.aureon_user_sessions;

CREATE POLICY "Users can insert own session"
  ON public.aureon_user_sessions
  FOR INSERT TO authenticated
  WITH CHECK ((SELECT auth.uid()) = user_id);
CREATE POLICY "Users can update own session"
  ON public.aureon_user_sessions
  FOR UPDATE TO authenticated
  USING ((SELECT auth.uid()) = user_id)
  WITH CHECK ((SELECT auth.uid()) = user_id);
CREATE POLICY "Users can view own session"
  ON public.aureon_user_sessions
  FOR SELECT TO authenticated
  USING ((SELECT auth.uid()) = user_id);

REVOKE ALL PRIVILEGES ON TABLE public.aureon_user_sessions
  FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT, UPDATE ON TABLE public.aureon_user_sessions
  TO authenticated;
GRANT ALL PRIVILEGES ON TABLE public.aureon_user_sessions TO service_role;

DROP POLICY IF EXISTS "Users can view own credential status"
  ON public.user_binance_credentials;
DROP POLICY IF EXISTS "Users can insert own credentials"
  ON public.user_binance_credentials;
DROP POLICY IF EXISTS "Users can update own credentials"
  ON public.user_binance_credentials;
DROP POLICY IF EXISTS "Users can view own credentials"
  ON public.user_binance_credentials;

CREATE POLICY "Users can insert own credentials"
  ON public.user_binance_credentials
  FOR INSERT TO authenticated
  WITH CHECK (auth.uid() = user_id);
CREATE POLICY "Users can update own credentials"
  ON public.user_binance_credentials
  FOR UPDATE TO authenticated
  USING (auth.uid() = user_id);
CREATE POLICY "Users can view own credentials"
  ON public.user_binance_credentials
  FOR SELECT TO authenticated
  USING (auth.uid() = user_id);

REVOKE ALL PRIVILEGES ON TABLE public.user_binance_credentials
  FROM PUBLIC, anon, authenticated;
GRANT ALL PRIVILEGES ON TABLE public.user_binance_credentials TO authenticated;
GRANT ALL PRIVILEGES ON TABLE public.user_binance_credentials TO service_role;

DROP POLICY IF EXISTS "Service role can insert audit logs"
  ON public.data_access_audit;
DROP POLICY IF EXISTS "Users can insert own audit logs"
  ON public.data_access_audit;
DROP POLICY IF EXISTS "Service can insert audit logs"
  ON public.data_access_audit;

CREATE POLICY "Service can insert audit logs"
  ON public.data_access_audit
  FOR INSERT TO service_role
  WITH CHECK (true);

REVOKE ALL PRIVILEGES ON TABLE public.data_access_audit
  FROM anon, authenticated;
GRANT ALL PRIVILEGES ON TABLE public.data_access_audit TO authenticated;
GRANT ALL PRIVILEGES ON TABLE public.data_access_audit TO service_role;

DO $rollback$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_catalog.pg_publication_tables
    WHERE pubname = 'supabase_realtime'
      AND schemaname = 'public'
      AND tablename = 'aureon_user_sessions'
  ) THEN
    EXECUTE 'ALTER PUBLICATION supabase_realtime ADD TABLE public.aureon_user_sessions';
  END IF;
END
$rollback$;

COMMIT;
