/**
 * AuthGate — optional Supabase session gate for the whole console.
 *
 * Off by default: the console stays open in dev/local exactly as before.
 * Set VITE_REQUIRE_AUTH=1 at build time, or serve from a Cloud Run hostname,
 * and the public console renders the existing AuthForm until a Supabase session exists.
 * The separately protected owner hostname may use its current backend-confirmed
 * Google IAP admin identity, avoiding a second tenant login on the owner plane.
 */

import { type ReactNode, useEffect, useState } from "react";
import type { Session } from "@supabase/supabase-js";
import { supabase } from "@/integrations/supabase/client";
import { AuthForm } from "@/components/AuthForm";
import { Button } from "@/components/ui/button";
import { api } from "@/services/apiClient";
import { hasCurrentOwnerIngress, requiresConsoleAuth } from "@/services/authGateAccess";
import { endTenantBrowserSession } from "@/services/tenantSession";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";

const REQUIRE_AUTH = requiresConsoleAuth(
  import.meta.env.VITE_REQUIRE_AUTH as string | undefined,
  window.location.hostname,
);

export function AuthGate({ children }: { children: ReactNode }) {
  const navigate = useNavigate();
  const [session, setSession] = useState<Session | null>(null);
  const [ownerIngress, setOwnerIngress] = useState(false);
  const [checking, setChecking] = useState(REQUIRE_AUTH);
  const [signingOut, setSigningOut] = useState(false);

  useEffect(() => {
    if (!REQUIRE_AUTH) return;
    let active = true;
    let generation = 0;
    const resolve = async (next: Session | null) => {
      const current = ++generation;
      if (next) {
        if (active && current === generation) {
          setSession(next); setOwnerIngress(false); setChecking(false);
        }
        return;
      }
      const owner = await hasCurrentOwnerIngress(() => api.get('/api/me'));
      if (active && current === generation) {
        setSession(null); setOwnerIngress(owner); setChecking(false);
      }
    };
    supabase.auth.getSession().then(({ data }) => resolve(data.session), () => resolve(null));
    const { data: sub } = supabase.auth.onAuthStateChange((_event, next) => {
      setChecking(true);
      void resolve(next);
    });
    return () => { active = false; generation++; sub.subscription.unsubscribe(); };
  }, []);

  if (!REQUIRE_AUTH) return <>{children}</>;

  if (checking) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background text-muted-foreground">
        Checking session…
      </div>
    );
  }

  if (!session && !ownerIngress) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background p-4">
        <AuthForm onSuccess={() => supabase.auth.getSession().then(({ data }) => {
          setSession(data.session);
          if (data.session) navigate('/start', { replace: true });
        })} />
      </div>
    );
  }

  if (ownerIngress) return <>{children}</>;

  const signOutTenant = async () => {
    setSigningOut(true);
    try {
      await endTenantBrowserSession(options => supabase.auth.signOut(options));
      setSession(null);
      setOwnerIngress(false);
      navigate('/console', { replace: true });
      toast.success('Signed out of this account workspace', {
        description: 'The protected owner cloud runtime continues independently.',
      });
    } catch (error) {
      toast.error('Could not sign out of this account workspace', {
        description: error instanceof Error ? error.message : 'The account service did not confirm sign out.',
      });
    } finally {
      setSigningOut(false);
    }
  };

  return (
    <>
      <div className="fixed top-2 right-2 z-50">
        <Button
          variant="ghost"
          size="sm"
          className="text-xs text-muted-foreground"
          onClick={signOutTenant}
          disabled={signingOut}
        >
          {signingOut ? 'Signing out…' : 'Sign out of account'}{session.user?.email ? ` (${session.user.email})` : ""}
        </Button>
      </div>
      {children}
    </>
  );
}
