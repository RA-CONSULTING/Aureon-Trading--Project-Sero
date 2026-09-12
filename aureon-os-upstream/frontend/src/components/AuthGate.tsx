/**
 * AuthGate — optional Supabase session gate for the whole console.
 *
 * Off by default: the console stays open in dev/local exactly as before.
 * Set VITE_REQUIRE_AUTH=1 at build time (the production image does) and the
 * public console renders the existing AuthForm until a Supabase session exists.
 * The separately protected owner hostname may use its current backend-confirmed
 * Google IAP admin identity, avoiding a second tenant login on the owner plane.
 */

import { type ReactNode, useEffect, useState } from "react";
import type { Session } from "@supabase/supabase-js";
import { supabase } from "@/integrations/supabase/client";
import { AuthForm } from "@/components/AuthForm";
import { Button } from "@/components/ui/button";
import { api } from "@/services/apiClient";
import { hasCurrentOwnerIngress } from "@/services/authGateAccess";

const REQUIRE_AUTH = (import.meta.env.VITE_REQUIRE_AUTH as string | undefined) === "1";

export function AuthGate({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [ownerIngress, setOwnerIngress] = useState(false);
  const [checking, setChecking] = useState(REQUIRE_AUTH);

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
        <AuthForm onSuccess={() => supabase.auth.getSession().then(({ data }) => setSession(data.session))} />
      </div>
    );
  }

  if (ownerIngress) return <>{children}</>;

  return (
    <>
      <div className="fixed top-2 right-2 z-50">
        <Button
          variant="ghost"
          size="sm"
          className="text-xs text-muted-foreground"
          onClick={() => supabase.auth.signOut()}
        >
          Sign out{session.user?.email ? ` (${session.user.email})` : ""}
        </Button>
      </div>
      {children}
    </>
  );
}
