/**
 * AccountPage — the signed-in user's own plane, stated plainly.
 *
 * Answers the four questions a real end user actually has: who am I signed in as, what can I reach,
 * what have I connected, and how do I leave. Everything on this page is the caller's OWN data — it
 * reads `/api/me`, `/api/providers` and passive `/api/billing/status`, all of which are on the tenant allowlist
 * (see `docs/architecture/MULTI_TENANT_AUTH.md`), so nothing here 403s for a signed-in user.
 *
 * Honest about the boundary rather than silent about it: a signed-in user is told, in words, that the
 * instance's control plane is the operator's and not theirs.
 */

import { useState } from "react";
import { Link } from "react-router-dom";
import { KeyRound, LogOut, Shield, User, UserCircle, Wallet } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useIdentity } from "@/hooks/useIdentity";
import { useSetupStatus } from "@/hooks/useSetupStatus";
import { api } from "@/services/apiClient";
import { createReadOnlyPoller } from "@/services/readOnlyPoller";
import { useReadOnlyPoller } from "@/hooks/useReadOnlyPoller";
import { supabase } from "@/integrations/supabase/client";
import { GlassPageHeader } from "@/shell/GlassPage";

interface BalanceResponse {
  balance_gbp?: number | null;
  currency?: string | null;
  note?: string | null;
  configured?: boolean | null;
  missing_env?: string[];
  tenancy_bridge?: string | null;
}

/** Honest states: we either have a figure, or we say why we do not. */
type BalanceState =
  | { kind: "loading" }
  | { kind: "value"; amount: number; currency: string }
  | { kind: "unavailable"; reason: string };

const balanceStore = createReadOnlyPoller<BalanceResponse>({
  read: options => api.get("/api/billing/status", options), receiptMaxAgeMs: 45_000,
});

export function AccountPage() {
  const { identity, loading: idLoading, error: identityError } = useIdentity();
  const { known: setupKnown, error: setupError, hasProvider, liveProvider, providerCount, loading: setupLoading } = useSetupStatus();
  const balanceRead = useReadOnlyPoller(balanceStore, 30_000, 8_000);
  const amount = balanceRead.data?.balance_gbp;
  const balanceReason = balanceRead.error || balanceRead.data?.note
    || (balanceRead.data?.tenancy_bridge === "off" ? "Tenant billing balance unavailable: tenancy bridge is off" : null)
    || (balanceRead.data?.configured === false
      ? `Billing backend not configured${balanceRead.data.missing_env?.length ? ` (${balanceRead.data.missing_env.join(", ")})` : ""}`
      : "No balance recorded for this account");
  const balance: BalanceState = balanceRead.loading ? { kind: "loading" }
    : typeof amount === "number" && Number.isFinite(amount)
      ? { kind: "value", amount, currency: balanceRead.data?.currency || "GBP" }
      : { kind: "unavailable", reason: balanceReason };
  const [signingOut, setSigningOut] = useState(false);
  const [signOutError, setSignOutError] = useState<string | null>(null);

  const onSignOut = async () => {
    setSigningOut(true);
    setSignOutError(null);
    try {
      const { error } = await supabase.auth.signOut();
      if (error) throw error;
      // AuthGate watches onAuthStateChange and drops back to the sign-in form.
    } catch {
      setSignOutError("Sign out was not confirmed. Retry when the account service is available.");
    } finally {
      setSigningOut(false);
    }
  };

  const isTenant = identity.kind === "tenant";
  const planeLabel =
    identity.kind === "tenant" ? "Your account"
      : identity.kind === "admin" ? "Instance operator"
        : identity.kind === "open" ? "Single-operator (no auth configured)"
          : "Unknown";

  return (
    <div className="space-y-6">
      <GlassPageHeader icon={UserCircle} eyebrow="Your workspace" title="Account & Session"
        description="Who you are signed in as, what you have connected, and what this session may reach." />

      {identityError && (
        <Card>
          <CardContent className="pt-6 text-sm text-muted-foreground">
            Session details cannot be confirmed: {identityError}
          </CardContent>
        </Card>
      )}

      <div className="grid gap-4 md:grid-cols-2">
        {/* ── identity ─────────────────────────────────────────────────────── */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <User className="h-4 w-4" /> Signed in as
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground">Plane</span>
              <Badge variant={isTenant ? "secondary" : "default"}>
                {idLoading ? "checking…" : planeLabel}
              </Badge>
            </div>
            {identity.tenantLabel && (
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">Account ref</span>
                <code className="rounded bg-muted px-1.5 py-0.5 text-xs">{identity.tenantLabel}</code>
              </div>
            )}
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground">Multi-user mode</span>
              <span>{identity.tenancyEnabled === null ? "unknown" : identity.tenancyEnabled ? "on" : "off (single operator)"}</span>
            </div>
            <p className="pt-1 text-xs text-muted-foreground">
              The account ref is a short hash, not your user id — enough to confirm which account you
              are on, or to quote in a support request, without putting your identifier on screen.
            </p>
          </CardContent>
        </Card>

        {/* ── their keys ───────────────────────────────────────────────────── */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <KeyRound className="h-4 w-4" /> Your model keys
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground">Keys stored</span>
              <span>{setupLoading ? "checking…" : !setupKnown ? "unknown" : `${providerCount} provider${providerCount === 1 ? "" : "s"}`}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground">Runtime configuration</span>
              <span>{setupLoading ? "checking…" : !setupKnown ? "unknown" : liveProvider ? "attached" : hasProvider ? "key stored" : "none yet"}</span>
            </div>
            <p className="text-xs text-muted-foreground">{setupError || "Stored configuration and runtime attachment do not confirm a successful model response."}</p>
            <Button asChild variant="outline" size="sm">
              <Link to="/cognition/providers">Manage keys</Link>
            </Button>
          </CardContent>
        </Card>

        {/* ── billing ──────────────────────────────────────────────────────── */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Wallet className="h-4 w-4" /> Billing
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground">Recorded balance</span>
              <span>
                {balance.kind === "loading" && "checking…"}
                {balance.kind === "value" &&
                  `${balance.currency} ${balance.amount.toFixed(2)}`}
                {balance.kind === "unavailable" && (
                  <span className="text-muted-foreground">{balance.reason}</span>
                )}
              </span>
            </div>
            <p className="text-xs text-muted-foreground">
              Metering is record-only. The platform never initiates a payment on its own — fees are
              charged by the operator's server-side loop, not by anything on this page.
            </p>
            <Button asChild variant="outline" size="sm">
              <Link to="/platform/billing">Billing &amp; support</Link>
            </Button>
          </CardContent>
        </Card>

        {/* ── boundary + sign out ──────────────────────────────────────────── */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Shield className="h-4 w-4" /> What this session may reach
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            {isTenant ? (
              <>
                <p className="text-muted-foreground">
                  You have your own plane: your keys, your reasoning, your billing, plus the read-only
                  views of the organism. The instance's control plane — its feature switchboard, host
                  actions, approvals desk and its own credentials — belongs to the operator and is not
                  reachable from this account.
                </p>
                {identity.allowedRoutes && (
                  <p className="text-xs text-muted-foreground">
                    {identity.allowedRoutes.length} endpoints are available to your account.
                  </p>
                )}
              </>
            ) : identity.kind === "admin" || identity.kind === "open" ? (
              <p className="text-muted-foreground">
                This session is on the instance plane and can reach everything, including the control
                plane. {identity.kind === "open" &&
                  "No authentication is configured on this instance — set AUREON_OPERATOR_API_KEY before exposing it."}
              </p>
            ) : <p className="text-muted-foreground">Session permissions are unconfirmed. Account and operator access remain subject to the current server authorization.</p>}
            <Button variant="outline" size="sm" onClick={onSignOut} disabled={signingOut}>
              <LogOut className="mr-2 h-4 w-4" />
              {signingOut ? "Signing out…" : "Sign out"}
            </Button>
            {signOutError && <p role="alert" className="text-sm text-destructive">{signOutError}</p>}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

export default AccountPage;
