BEGIN;

CREATE SCHEMA IF NOT EXISTS private;
REVOKE ALL ON SCHEMA private FROM PUBLIC, anon, authenticated;
GRANT USAGE ON SCHEMA private TO authenticated, service_role;

ALTER FUNCTION public.has_role(uuid, public.app_role) SET SCHEMA private;
ALTER FUNCTION public.session_belongs_to_current_user(uuid) SET SCHEMA private;

ALTER FUNCTION private.has_role(uuid, public.app_role)
  SET search_path TO pg_catalog, public;
ALTER FUNCTION private.session_belongs_to_current_user(uuid)
  SET search_path TO pg_catalog, public;

REVOKE ALL ON FUNCTION private.has_role(uuid, public.app_role)
  FROM PUBLIC, anon;
REVOKE ALL ON FUNCTION private.session_belongs_to_current_user(uuid)
  FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION private.has_role(uuid, public.app_role)
  TO authenticated, service_role;
GRANT EXECUTE ON FUNCTION private.session_belongs_to_current_user(uuid)
  TO authenticated, service_role;

COMMIT;
