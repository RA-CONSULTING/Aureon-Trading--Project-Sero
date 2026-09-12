-- Restrict production product data to its owning user or the service role.
-- These tables previously inherited broad Data API grants and several
-- unrestricted service policies were accidentally assigned to PUBLIC.

BEGIN;

ALTER TABLE public.aureon_user_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.trading_positions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.gas_tank_accounts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.gas_tank_transactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.oms_order_queue ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.trade_audit_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.user_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.user_roles ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Service role can manage sessions" ON public.aureon_user_sessions;
DROP POLICY IF EXISTS "Users can view own session" ON public.aureon_user_sessions;
DROP POLICY IF EXISTS "Users can insert own session" ON public.aureon_user_sessions;
DROP POLICY IF EXISTS "Users can update own session" ON public.aureon_user_sessions;

CREATE POLICY "Service role can manage sessions"
  ON public.aureon_user_sessions FOR ALL TO service_role
  USING (true) WITH CHECK (true);
CREATE POLICY "Users can view own session"
  ON public.aureon_user_sessions FOR SELECT TO authenticated
  USING ((SELECT auth.uid()) = user_id);
CREATE POLICY "Users can insert own session"
  ON public.aureon_user_sessions FOR INSERT TO authenticated
  WITH CHECK ((SELECT auth.uid()) = user_id);
CREATE POLICY "Users can update own session"
  ON public.aureon_user_sessions FOR UPDATE TO authenticated
  USING ((SELECT auth.uid()) = user_id)
  WITH CHECK ((SELECT auth.uid()) = user_id);

DROP POLICY IF EXISTS "Service role can insert positions" ON public.trading_positions;
DROP POLICY IF EXISTS "Service role can update positions" ON public.trading_positions;
DROP POLICY IF EXISTS "Users can view own positions" ON public.trading_positions;

CREATE POLICY "Service role can insert positions"
  ON public.trading_positions FOR INSERT TO service_role
  WITH CHECK (true);
CREATE POLICY "Service role can update positions"
  ON public.trading_positions FOR UPDATE TO service_role
  USING (true) WITH CHECK (true);
CREATE POLICY "Users can view own positions"
  ON public.trading_positions FOR SELECT TO authenticated
  USING ((SELECT auth.uid()) = user_id);

DROP POLICY IF EXISTS "Service manages gas tanks" ON public.gas_tank_accounts;
DROP POLICY IF EXISTS "Users view own gas tank" ON public.gas_tank_accounts;

CREATE POLICY "Service manages gas tanks"
  ON public.gas_tank_accounts FOR ALL TO service_role
  USING (true) WITH CHECK (true);
CREATE POLICY "Users view own gas tank"
  ON public.gas_tank_accounts FOR SELECT TO authenticated
  USING ((SELECT auth.uid()) = user_id);

DROP POLICY IF EXISTS "Service inserts transactions" ON public.gas_tank_transactions;
DROP POLICY IF EXISTS "Users view own transactions" ON public.gas_tank_transactions;

CREATE POLICY "Service inserts transactions"
  ON public.gas_tank_transactions FOR INSERT TO service_role
  WITH CHECK (true);
CREATE POLICY "Users view own transactions"
  ON public.gas_tank_transactions FOR SELECT TO authenticated
  USING (
    account_id IN (
      SELECT account.id
      FROM public.gas_tank_accounts AS account
      WHERE account.user_id = (SELECT auth.uid())
    )
  );

DROP POLICY IF EXISTS "Service manages orders" ON public.oms_order_queue;
DROP POLICY IF EXISTS "Users view own orders" ON public.oms_order_queue;

CREATE POLICY "Service manages orders"
  ON public.oms_order_queue FOR ALL TO service_role
  USING (true) WITH CHECK (true);
CREATE POLICY "Users view own orders"
  ON public.oms_order_queue FOR SELECT TO authenticated
  USING (
    session_id IN (
      SELECT session.id
      FROM public.hive_sessions AS session
      WHERE session.user_id = (SELECT auth.uid())
    )
  );

-- The audit table does not contain a tenant/user key. Keep it service-only
-- until a tenant binding is added and backfilled.
DROP POLICY IF EXISTS "Authenticated users can read trade audit log" ON public.trade_audit_log;
DROP POLICY IF EXISTS "Service role can manage trade audit log" ON public.trade_audit_log;

CREATE POLICY "Service role can manage trade audit log"
  ON public.trade_audit_log FOR ALL TO service_role
  USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS "Admins can view all profiles" ON public.user_profiles;
DROP POLICY IF EXISTS "Users can update their own profile" ON public.user_profiles;
DROP POLICY IF EXISTS "Users can view their own profile" ON public.user_profiles;

CREATE POLICY "Admins can view all profiles"
  ON public.user_profiles FOR SELECT TO authenticated
  USING (public.has_role((SELECT auth.uid()), 'admin'::public.app_role));
CREATE POLICY "Users can update their own profile"
  ON public.user_profiles FOR UPDATE TO authenticated
  USING ((SELECT auth.uid()) = id)
  WITH CHECK ((SELECT auth.uid()) = id);
CREATE POLICY "Users can view their own profile"
  ON public.user_profiles FOR SELECT TO authenticated
  USING ((SELECT auth.uid()) = id);

DROP POLICY IF EXISTS "Admins can manage all roles" ON public.user_roles;
DROP POLICY IF EXISTS "Users can view own roles" ON public.user_roles;

CREATE POLICY "Admins can manage all roles"
  ON public.user_roles FOR ALL TO authenticated
  USING (public.has_role((SELECT auth.uid()), 'admin'::public.app_role))
  WITH CHECK (public.has_role((SELECT auth.uid()), 'admin'::public.app_role));
CREATE POLICY "Users can view own roles"
  ON public.user_roles FOR SELECT TO authenticated
  USING ((SELECT auth.uid()) = user_id);

REVOKE ALL PRIVILEGES ON TABLE
  public.aureon_user_sessions,
  public.trading_positions,
  public.gas_tank_accounts,
  public.gas_tank_transactions,
  public.oms_order_queue,
  public.trade_audit_log,
  public.user_profiles,
  public.user_roles
FROM anon, authenticated;

GRANT SELECT, INSERT, UPDATE ON TABLE public.aureon_user_sessions TO authenticated;
GRANT SELECT ON TABLE public.trading_positions TO authenticated;
GRANT SELECT ON TABLE public.gas_tank_accounts TO authenticated;
GRANT SELECT ON TABLE public.gas_tank_transactions TO authenticated;
GRANT SELECT ON TABLE public.oms_order_queue TO authenticated;
GRANT SELECT, UPDATE ON TABLE public.user_profiles TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.user_roles TO authenticated;

GRANT ALL PRIVILEGES ON TABLE
  public.aureon_user_sessions,
  public.trading_positions,
  public.gas_tank_accounts,
  public.gas_tank_transactions,
  public.oms_order_queue,
  public.trade_audit_log,
  public.user_profiles,
  public.user_roles
TO service_role;

COMMIT;
