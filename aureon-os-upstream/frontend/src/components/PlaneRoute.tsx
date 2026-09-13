import type { ReactNode } from 'react';
import { Navigate } from 'react-router-dom';
import { ShieldCheck } from 'lucide-react';
import { useIdentity } from '@/hooks/useIdentity';
import { planeRouteDecision } from '@/lib/planeRouteAccess';

export function PlaneRoute({ operatorOnly, children }: { operatorOnly?: boolean; children: ReactNode }) {
  const identityReceipt = useIdentity();
  const decision = planeRouteDecision(operatorOnly, identityReceipt.identity, identityReceipt.known);

  if (decision === 'redirect') {
    return <Navigate to="/start" replace state={{ ownerRouteRedirect: true }} />;
  }
  if (decision === 'pending') {
    return (
      <div className="flex min-h-[45vh] items-center justify-center p-6" role="status">
        <div className="max-w-lg rounded-xl border border-border/60 bg-card/70 p-6 text-center">
          <ShieldCheck className="mx-auto mb-3 h-6 w-6 text-primary" />
          <p className="font-medium">Checking protected owner access</p>
          <p className="mt-1 text-sm text-muted-foreground">This instance surface opens only after a current backend owner receipt.</p>
        </div>
      </div>
    );
  }
  return <>{children}</>;
}
