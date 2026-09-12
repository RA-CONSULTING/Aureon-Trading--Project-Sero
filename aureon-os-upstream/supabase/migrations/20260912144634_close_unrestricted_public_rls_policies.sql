-- Remove legacy unrestricted PUBLIC policies before enabling customer sign-in.
-- Service policies are recreated for service_role only. Other unrestricted
-- writes and internal/global reads are removed; tenant-scoped policies created
-- by later migrations remain untouched.

BEGIN;

DO $$
DECLARE
  existing_policy record;
  statement text;
  keep_as_service boolean;
BEGIN
  FOR existing_policy IN
    SELECT tablename, policyname, permissive, cmd, qual, with_check
    FROM pg_policies
    WHERE schemaname = 'public'
      AND roles @> ARRAY['public']::name[]
      AND (COALESCE(qual, '') = 'true' OR COALESCE(with_check, '') = 'true')
      AND NOT (
        tablename = 'crypto_assets_registry'
        AND policyname = 'Anyone can read crypto assets registry'
        AND cmd = 'SELECT'
      )
    ORDER BY tablename, policyname
  LOOP
    keep_as_service := existing_policy.policyname ILIKE '%service%'
      OR existing_policy.cmd IN ('ALL', 'INSERT', 'UPDATE', 'DELETE');

    EXECUTE format(
      'DROP POLICY IF EXISTS %I ON public.%I',
      existing_policy.policyname,
      existing_policy.tablename
    );

    IF keep_as_service THEN
      statement := format(
        'CREATE POLICY %I ON public.%I AS %s FOR %s TO service_role',
        existing_policy.policyname,
        existing_policy.tablename,
        existing_policy.permissive,
        existing_policy.cmd
      );
      IF existing_policy.qual IS NOT NULL
         AND existing_policy.cmd IN ('ALL', 'SELECT', 'UPDATE', 'DELETE') THEN
        statement := statement || format(' USING (%s)', existing_policy.qual);
      END IF;
      IF existing_policy.with_check IS NOT NULL
         AND existing_policy.cmd IN ('ALL', 'INSERT', 'UPDATE') THEN
        statement := statement || format(' WITH CHECK (%s)', existing_policy.with_check);
      END IF;
      EXECUTE statement;
    END IF;
  END LOOP;
END
$$;

-- The browser needs no direct anonymous database access for sign-in. Supabase
-- Auth is a separate endpoint. Keep only the non-sensitive asset catalogue as
-- an intentional public read.
DO $$
DECLARE
  target_table record;
BEGIN
  FOR target_table IN
    SELECT c.relname
    FROM pg_class AS c
    JOIN pg_namespace AS n ON n.oid = c.relnamespace
    WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p')
  LOOP
    EXECUTE format('REVOKE ALL PRIVILEGES ON TABLE public.%I FROM anon', target_table.relname);
  END LOOP;
END
$$;

GRANT SELECT ON TABLE public.crypto_assets_registry TO anon;

COMMIT;
