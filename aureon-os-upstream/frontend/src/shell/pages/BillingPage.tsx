/**
 * Billing & Support — the honest money page.
 *
 * Gas-tank balance (Supabase, via useGasTank when signed in), platform
 * billing/metering state from GET /api/billing/status, and the
 * support-the-project links. Free access; nothing here gates usage.
 */

import { useEffect, useState } from "react";
import { CreditCard, Fuel, Heart } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { supabase } from "@/integrations/supabase/client";
import { useGasTank } from "@/hooks/useGasTank";
import { SUPPORT_PAYMENT_URLS } from "@/hooks/useSupportProject";
import { gasTankMoney, gasTankReceiptIsCurrent } from "@/lib/gasTankDisplay";
import { billingStore } from "@/services/platformReads";
import { useReadOnlyPoller } from "@/hooks/useReadOnlyPoller";
import { configurationMessage, configurationStatus } from "@/lib/accountConfigurationEvidence";
import { sessionUserObserver } from "@/lib/platformConfiguration";
import { GlassPageHeader } from "@/shell/GlassPage";

function GasTankCard({ userId }: { userId: string }) {
  const gasTank = useGasTank(userId);
  const [, refreshAge] = useState(0);
  useEffect(() => {
    const timer = window.setInterval(() => refreshAge((value) => value + 1), 1_000);
    return () => window.clearInterval(timer);
  }, []);
  const observed = gasTankReceiptIsCurrent(gasTank.receipt.observed, gasTank.receipt.receivedAt);
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardDescription className="flex items-center gap-1.5">
          <Fuel className="h-3.5 w-3.5" /> Gas tank
        </CardDescription>
        <CardTitle className="text-2xl">{gasTankMoney(gasTank.balance, observed)}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-1 text-xs text-muted-foreground">
        <p>status: {observed ? gasTank.status ?? 'Unavailable' : 'Unavailable'} · membership: {observed ? gasTank.membershipType ?? 'Unavailable' : 'Unavailable'}</p>
        <p>total fees paid: {gasTankMoney(gasTank.totalFeesPaid, observed)}</p>
        <p>{gasTank.receipt.observed && !observed ? 'Account receipt expired; fresh read unavailable' : gasTank.receipt.reason}{gasTank.receipt.observed && gasTank.receipt.receivedAt ? ` · received ${new Date(gasTank.receipt.receivedAt).toISOString()}` : ''}</p>
        <p>Source: account ledger snapshot. Read time does not establish a current exchange balance.</p>
      </CardContent>
    </Card>
  );
}

export default function BillingPage() {
  const receipt = useReadOnlyPoller(billingStore, 15_000, 8_000);
  const status = receipt.loading ? undefined : receipt.data;
  const [userId, setUserId] = useState<string | null>(null);
  const [sessionLoading, setSessionLoading] = useState(true);
  const [sessionError, setSessionError] = useState<string | null>(null);

  useEffect(() => {
    const observer = sessionUserObserver(id => { setUserId(id); setSessionLoading(false); setSessionError(null); });
    const deadline = window.setTimeout(() => { observer.event(null); setSessionError('Account session read timed out'); }, 8_000);
    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      window.clearTimeout(deadline);
      observer.event(session?.user?.id ?? null);
    });
    void supabase.auth.getSession().then(({ data, error }) => {
      if (observer.initial(error ? null : data.session?.user?.id ?? null)) {
        window.clearTimeout(deadline);
        if (error) setSessionError('Account session unavailable');
      }
    }).catch(() => {
      if (observer.initial(null)) { window.clearTimeout(deadline); setSessionError('Account session unavailable'); }
    });
    return () => { observer.stop(); window.clearTimeout(deadline); subscription.unsubscribe(); };
  }, []);

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-6">
      <GlassPageHeader icon={CreditCard} eyebrow="Account ledger" title="Billing & Support"
        description={<>
          Aureon runs free. The gas tank is a prepaid wallet charged only as a
          performance fee on profit above your high-water mark; usage metering is
          record-only. The platform never initiates payments.
        </>} />

      <div className="grid gap-4 md:grid-cols-2">
        {userId ? (
          <GasTankCard key={userId} userId={userId} />
        ) : (
          <Card>
            <CardHeader className="pb-2">
              <CardDescription className="flex items-center gap-1.5">
                <Fuel className="h-3.5 w-3.5" /> Gas tank
              </CardDescription>
              <CardTitle className="text-lg text-muted-foreground">{sessionLoading ? 'Reading account session…' : sessionError ?? 'Sign in to view'}</CardTitle>
            </CardHeader>
            <CardContent className="text-xs text-muted-foreground">
              Your balance lives in your Supabase account.
            </CardContent>
          </Card>
        )}

        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Platform billing state</CardDescription>
            <CardTitle className="text-lg">
              {status === undefined ? (
                <Skeleton className="h-6 w-32" />
              ) : status === null ? (
                <span className="text-muted-foreground">configuration unavailable</span>
              ) : (
                <span className="flex flex-wrap gap-1.5">
                  <Badge variant="outline">metering: {status.metering?.sink ?? "Unavailable"}</Badge>
                  <Badge variant="outline">
                    charge-fee: {status.charge_endpoint?.enabled === true ? "enabled" : status.charge_endpoint?.enabled === false ? "off" : "Unavailable"}
                  </Badge>
                </span>
              )}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-1 text-xs text-muted-foreground">
            <p>{receipt.isReceiptCurrent && receipt.lastReceivedAt ? `Configuration received ${new Date(receipt.lastReceivedAt).toISOString()}; provider activity is separate.` : configurationMessage(configurationStatus(receipt), receipt.error)}</p>
            {status?.metering && (
              <p>
                events — flushed: {status.metering.flushed ?? 'Unavailable'} · pending: {status.metering.pending ?? 'Unavailable'} ·
                dropped: {status.metering.dropped ?? 'Unavailable'}
              </p>
            )}
            {status?.configured === false && (
              <p>Supabase billing backend not configured{status.missing_env?.length ? ` (missing: ${status.missing_env.join(", ")})` : ""}.</p>
            )}
            {status?.configured === null && <p>Billing backend configuration is unknown.</p>}
          </CardContent>
        </Card>
      </div>

      <Card className="border-primary/30">
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-2 text-base">
            <Heart className="h-4 w-4 text-primary" /> Support the project
          </CardTitle>
          <CardDescription>
            Aureon is free-access, open-source software. If it earns its keep, support keeps it running.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-2">
          {SUPPORT_PAYMENT_URLS.map((url, i) => (
            <Button key={url} size="sm" variant={i === 0 ? "default" : "outline"} asChild>
              <a href={url} target="_blank" rel="noopener noreferrer">
                Support via SumUp{SUPPORT_PAYMENT_URLS.length > 1 ? ` (${i + 1})` : ""}
              </a>
            </Button>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}
