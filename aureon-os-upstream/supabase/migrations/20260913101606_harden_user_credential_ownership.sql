-- Keep end-user credential material in a server-owned vault while preserving
-- an account-scoped, non-secret presence check for the Settings UI.
--
-- Edge Functions authenticate the caller, derive user_id from that verified
-- session and perform credential writes with the service role.  Browser roles
-- therefore need no INSERT/UPDATE/DELETE access to encrypted credential bytes.

BEGIN;

-- aureon_user_sessions historically mixed harmless telemetry with exchange
-- ciphertext and live-trading authority.  RLS only constrained rows; a browser
-- selecting its own row still received every column and could write authority.
-- Keep the source table service-owned and expose a deliberately narrow,
-- account-scoped status RPC for browser dashboards.
ALTER TABLE public.aureon_user_sessions ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can view own session"
  ON public.aureon_user_sessions;
DROP POLICY IF EXISTS "Users can insert own session"
  ON public.aureon_user_sessions;
DROP POLICY IF EXISTS "Users can update own session"
  ON public.aureon_user_sessions;

CREATE POLICY "Users can view own safe session status"
  ON public.aureon_user_sessions
  FOR SELECT TO authenticated
  USING ((SELECT auth.uid()) = user_id);

REVOKE ALL PRIVILEGES ON TABLE public.aureon_user_sessions
  FROM PUBLIC, anon, authenticated;
GRANT ALL PRIVILEGES ON TABLE public.aureon_user_sessions TO service_role;

DROP VIEW IF EXISTS public.aureon_user_session_status;
DROP FUNCTION IF EXISTS public.get_aureon_user_session_status();
CREATE FUNCTION public.get_aureon_user_session_status()
RETURNS TABLE (
  id uuid,
  user_id uuid,
  current_coherence numeric,
  current_lambda numeric,
  current_lighthouse_signal numeric,
  dominant_node text,
  prism_level integer,
  prism_state text,
  measurement_truth_status text,
  measurement_source_id text,
  measurement_source_timestamp timestamptz,
  measurement_collected_at timestamptz,
  measurement_generated_values boolean,
  total_equity_usdt numeric,
  total_equity_usd numeric,
  available_balance_usdt numeric,
  total_trades integer,
  winning_trades integer,
  total_pnl_usdt numeric,
  gas_tank_balance numeric,
  last_trade_at timestamptz,
  last_quantum_update_at timestamptz,
  created_at timestamptz,
  updated_at timestamptz,
  binance_credentials_configured boolean,
  kraken_credentials_configured boolean,
  alpaca_credentials_configured boolean,
  capital_credentials_configured boolean
)
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = ''
AS $function$
  SELECT
    session.id,
    session.user_id,
    session.current_coherence,
    session.current_lambda,
    session.current_lighthouse_signal,
    session.dominant_node,
    session.prism_level,
    session.prism_state,
    session.measurement_truth_status,
    session.measurement_source_id,
    session.measurement_source_timestamp,
    session.measurement_collected_at,
    session.measurement_generated_values,
    session.total_equity_usdt,
    session.total_equity_usd,
    session.available_balance_usdt,
    session.total_trades,
    session.winning_trades,
    session.total_pnl_usdt,
    session.gas_tank_balance,
    session.last_trade_at,
    session.last_quantum_update_at,
    session.created_at,
    session.updated_at,
    (
      session.binance_api_key_encrypted IS NOT NULL
      AND session.binance_api_secret_encrypted IS NOT NULL
    ) OR EXISTS (
      SELECT 1
      FROM public.user_binance_credentials AS binance
      WHERE binance.user_id = session.user_id
        AND binance.api_key_encrypted IS NOT NULL
        AND binance.api_secret_encrypted IS NOT NULL
    ),
    session.kraken_api_key_encrypted IS NOT NULL
      AND session.kraken_api_secret_encrypted IS NOT NULL,
    session.alpaca_api_key_encrypted IS NOT NULL
      AND session.alpaca_secret_key_encrypted IS NOT NULL,
    session.capital_api_key_encrypted IS NOT NULL
      AND session.capital_password_encrypted IS NOT NULL
  FROM public.aureon_user_sessions AS session
  WHERE session.user_id = (SELECT auth.uid());
$function$;

REVOKE ALL PRIVILEGES ON FUNCTION public.get_aureon_user_session_status()
  FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.get_aureon_user_session_status()
  TO authenticated, service_role;

-- Realtime serializes the source row, so column grants alone are not an
-- adequate secret boundary.  Browser status reads use the safe view above.
DO $migration$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM pg_catalog.pg_publication_tables
    WHERE pubname = 'supabase_realtime'
      AND schemaname = 'public'
      AND tablename = 'aureon_user_sessions'
  ) THEN
    EXECUTE 'ALTER PUBLICATION supabase_realtime DROP TABLE public.aureon_user_sessions';
  END IF;
END
$migration$;

ALTER TABLE public.user_binance_credentials ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can view own credentials"
  ON public.user_binance_credentials;
DROP POLICY IF EXISTS "Users can insert own credentials"
  ON public.user_binance_credentials;
DROP POLICY IF EXISTS "Users can update own credentials"
  ON public.user_binance_credentials;

CREATE POLICY "Users can view own credential status"
  ON public.user_binance_credentials
  FOR SELECT TO authenticated
  USING ((SELECT auth.uid()) = user_id);

REVOKE ALL PRIVILEGES ON TABLE public.user_binance_credentials
  FROM PUBLIC, anon, authenticated;
GRANT SELECT (id, user_id, created_at, updated_at, last_used_at)
  ON TABLE public.user_binance_credentials TO authenticated;
GRANT ALL PRIVILEGES ON TABLE public.user_binance_credentials TO service_role;

-- The original audit INSERT policy had no target role and a true check.  Bind
-- client-authored events to the authenticated account and reserve unrestricted
-- audit writes for service_role.
ALTER TABLE public.data_access_audit ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Service can insert audit logs"
  ON public.data_access_audit;
DROP POLICY IF EXISTS "Users can insert own audit logs"
  ON public.data_access_audit;

CREATE POLICY "Service role can insert audit logs"
  ON public.data_access_audit
  FOR INSERT TO service_role
  WITH CHECK (true);
CREATE POLICY "Users can insert own audit logs"
  ON public.data_access_audit
  FOR INSERT TO authenticated
  WITH CHECK (
    (SELECT auth.uid()) = user_id
    AND (SELECT auth.uid()) = accessed_by
  );

REVOKE ALL PRIVILEGES ON TABLE public.data_access_audit
  FROM anon, authenticated;
GRANT SELECT, INSERT ON TABLE public.data_access_audit TO authenticated;
GRANT ALL PRIVILEGES ON TABLE public.data_access_audit TO service_role;

-- Fail the migration transaction if the effective database ACL does not match
-- the intended browser contract.  These checks inspect PostgreSQL's actual
-- privilege state after every statement above rather than trusting SQL text.
DO $contract$
DECLARE
  sensitive_column text;
  safe_column text;
BEGIN
  IF has_table_privilege('anon', 'public.aureon_user_sessions', 'SELECT')
     OR has_table_privilege('authenticated', 'public.aureon_user_sessions', 'SELECT')
     OR has_table_privilege('authenticated', 'public.aureon_user_sessions', 'INSERT')
     OR has_table_privilege('authenticated', 'public.aureon_user_sessions', 'UPDATE')
     OR has_table_privilege('authenticated', 'public.aureon_user_sessions', 'DELETE') THEN
    RAISE EXCEPTION 'aureon_user_sessions_browser_table_acl_contract_failed';
  END IF;

  FOREACH sensitive_column IN ARRAY ARRAY[
    'binance_api_key_encrypted', 'binance_api_secret_encrypted', 'binance_iv',
    'kraken_api_key_encrypted', 'kraken_api_secret_encrypted', 'kraken_iv',
    'alpaca_api_key_encrypted', 'alpaca_secret_key_encrypted', 'alpaca_iv',
    'capital_api_key_encrypted', 'capital_password_encrypted',
    'capital_identifier_encrypted', 'capital_iv',
    'payment_completed', 'payment_completed_at',
    'is_trading_active', 'trading_mode', 'recent_trades'
  ] LOOP
    IF has_column_privilege(
      'authenticated', 'public.aureon_user_sessions', sensitive_column, 'SELECT'
    ) OR has_column_privilege(
      'authenticated', 'public.aureon_user_sessions', sensitive_column, 'INSERT'
    ) OR has_column_privilege(
      'authenticated', 'public.aureon_user_sessions', sensitive_column, 'UPDATE'
    ) THEN
      RAISE EXCEPTION 'aureon_user_sessions_sensitive_column_acl_contract_failed: %',
        sensitive_column;
    END IF;
  END LOOP;

  IF EXISTS (
    SELECT 1
    FROM pg_catalog.pg_publication_tables
    WHERE pubname = 'supabase_realtime'
      AND schemaname = 'public'
      AND tablename = 'aureon_user_sessions'
  ) THEN
    RAISE EXCEPTION 'aureon_user_sessions_realtime_contract_failed';
  END IF;

  IF has_function_privilege(
       'anon', 'public.get_aureon_user_session_status()', 'EXECUTE'
     ) OR NOT has_function_privilege(
       'authenticated', 'public.get_aureon_user_session_status()', 'EXECUTE'
     ) OR pg_get_function_result(
       'public.get_aureon_user_session_status()'::regprocedure
     ) ~ '(api_key_encrypted|api_secret_encrypted|password_encrypted|is_trading_active|trading_mode|recent_trades)' THEN
    RAISE EXCEPTION 'aureon_user_session_status_rpc_contract_failed';
  END IF;

  IF has_table_privilege('anon', 'public.user_binance_credentials', 'SELECT')
     OR has_table_privilege('authenticated', 'public.user_binance_credentials', 'INSERT')
     OR has_table_privilege('authenticated', 'public.user_binance_credentials', 'UPDATE')
     OR has_table_privilege('authenticated', 'public.user_binance_credentials', 'DELETE') THEN
    RAISE EXCEPTION 'user_binance_credentials_browser_table_acl_contract_failed';
  END IF;

  FOREACH safe_column IN ARRAY ARRAY[
    'id', 'user_id', 'created_at', 'updated_at', 'last_used_at'
  ] LOOP
    IF NOT has_column_privilege(
      'authenticated', 'public.user_binance_credentials', safe_column, 'SELECT'
    ) THEN
      RAISE EXCEPTION 'user_binance_credentials_safe_column_acl_contract_failed: %',
        safe_column;
    END IF;
  END LOOP;

  FOREACH sensitive_column IN ARRAY ARRAY[
    'api_key_encrypted', 'api_secret_encrypted'
  ] LOOP
    IF has_column_privilege(
      'authenticated', 'public.user_binance_credentials', sensitive_column, 'SELECT'
    ) OR has_column_privilege(
      'authenticated', 'public.user_binance_credentials', sensitive_column, 'INSERT'
    ) OR has_column_privilege(
      'authenticated', 'public.user_binance_credentials', sensitive_column, 'UPDATE'
    ) THEN
      RAISE EXCEPTION 'user_binance_credentials_sensitive_column_acl_contract_failed: %',
        sensitive_column;
    END IF;
  END LOOP;

  IF has_table_privilege('anon', 'public.data_access_audit', 'SELECT')
     OR has_table_privilege('anon', 'public.data_access_audit', 'INSERT')
     OR NOT has_table_privilege('authenticated', 'public.data_access_audit', 'SELECT')
     OR NOT has_table_privilege('authenticated', 'public.data_access_audit', 'INSERT')
     OR has_table_privilege('authenticated', 'public.data_access_audit', 'UPDATE')
     OR has_table_privilege('authenticated', 'public.data_access_audit', 'DELETE') THEN
    RAISE EXCEPTION 'data_access_audit_browser_acl_contract_failed';
  END IF;

  IF NOT EXISTS (
    SELECT 1
    FROM pg_catalog.pg_policy AS policy
    JOIN pg_catalog.pg_class AS relation ON relation.oid = policy.polrelid
    JOIN pg_catalog.pg_namespace AS namespace ON namespace.oid = relation.relnamespace
    WHERE namespace.nspname = 'public'
      AND relation.relname = 'data_access_audit'
      AND policy.polname = 'Users can insert own audit logs'
      AND policy.polcmd = 'a'
      AND ('authenticated'::regrole)::oid = ANY(policy.polroles)
      AND pg_catalog.pg_get_expr(policy.polwithcheck, policy.polrelid) LIKE '%user_id%'
      AND pg_catalog.pg_get_expr(policy.polwithcheck, policy.polrelid) LIKE '%accessed_by%'
  ) THEN
    RAISE EXCEPTION 'data_access_audit_authenticated_policy_contract_failed';
  END IF;

  IF NOT EXISTS (
    SELECT 1
    FROM pg_catalog.pg_policy AS policy
    JOIN pg_catalog.pg_class AS relation ON relation.oid = policy.polrelid
    JOIN pg_catalog.pg_namespace AS namespace ON namespace.oid = relation.relnamespace
    WHERE namespace.nspname = 'public'
      AND relation.relname = 'data_access_audit'
      AND policy.polname = 'Service role can insert audit logs'
      AND policy.polcmd = 'a'
      AND ('service_role'::regrole)::oid = ANY(policy.polroles)
  ) THEN
    RAISE EXCEPTION 'data_access_audit_service_policy_contract_failed';
  END IF;
END
$contract$;

COMMIT;
