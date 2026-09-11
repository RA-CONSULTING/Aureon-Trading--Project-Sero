import { ExternalLink, RefreshCw } from 'lucide-react';
import { Link } from 'react-router-dom';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { useReadOnlyPoller } from '@/hooks/useReadOnlyPoller';
import { buildCompanyRoleWorkbench, type CompanyWorkbenchRole } from '@/lib/companyRoleWorkbenches';
import { companyCapabilityAttestationStore } from '@/services/companyRoleWorkbenches';

function displayValue(value: unknown): string | null {
  if (typeof value === 'boolean') return value ? 'yes' : 'no';
  if (typeof value === 'number' && Number.isFinite(value)) return value.toLocaleString();
  if (typeof value === 'string' && value.trim()) return value.trim().replace(/_/g, ' ');
  return null;
}

function summaryEntries(summary: Record<string, unknown>): Array<[string, string]> {
  return Object.entries(summary)
    .map(([key, value]) => [key, displayValue(value)] as const)
    .filter((entry): entry is readonly [string, string] => entry[1] !== null)
    .slice(0, 6)
    .map(([key, value]) => [key, value]);
}

export function CompanyRoleWorkbench({ role }: { role: CompanyWorkbenchRole }) {
  const capabilityRead = useReadOnlyPoller(companyCapabilityAttestationStore, 15_000, 8_000);
  const acceptedReceipt = capabilityRead.isReceiptCurrent ? capabilityRead.data : null;
  const workbench = buildCompanyRoleWorkbench(role, acceptedReceipt);

  if (!workbench) {
    return <p className="text-sm text-amber-300">This role has no reviewed observational workbench binding.</p>;
  }

  return <div className="space-y-3">
    <div className="flex flex-wrap items-center justify-between gap-2">
      <div>
        <div className="text-sm font-medium">{workbench.roleTitle}</div>
        <div className="font-mono text-[11px] text-muted-foreground">{workbench.roleId} · {workbench.department}</div>
      </div>
      <div className="flex flex-wrap gap-1">
        <Badge variant="outline">Read-only observation</Badge>
        <Badge variant="outline">Current surfaces {workbench.currentSurfaceCount}/{workbench.bindings.length}</Badge>
        <Badge variant="outline">No commands in this view</Badge>
      </div>
    </div>
    <p className="text-xs text-muted-foreground">
      Current department data and links to its operating pages. This view does not expose commands.
    </p>
    <div className="flex flex-wrap items-center gap-2 text-[11px] text-muted-foreground">
      <span>Capability receipt: {acceptedReceipt ? 'current' : 'unavailable'}</span>
      {acceptedReceipt?.observed_at_iso ? <span>observed {acceptedReceipt.observed_at_iso}</span> : null}
      <Button type="button" size="sm" variant="ghost" className="h-7 px-2 text-[11px]" onClick={capabilityRead.refresh}>
        <RefreshCw className="mr-1 h-3 w-3" /> Refresh
      </Button>
    </div>
    {capabilityRead.loading ? <p className="text-xs text-muted-foreground">Reading current capability surfaces…</p> : null}
    {capabilityRead.error ? <p className="text-xs text-amber-300">
      {capabilityRead.httpStatus === 403
        ? 'An authenticated operator session is required to read these company workbench surfaces.'
        : capabilityRead.error}
    </p> : null}
    <div className="grid gap-2 md:grid-cols-2">
      {workbench.bindings.map(binding => {
        const observation = binding.observation;
        const entries = observation?.current ? summaryEntries(observation.summary) : [];
        return <div key={binding.id} className="rounded-md border border-border/40 bg-muted/10 p-3">
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div>
              <div className="text-xs font-medium">{binding.label}</div>
              <div className="font-mono text-[10px] text-muted-foreground">GET {binding.apiRoute}</div>
            </div>
            <Badge variant="outline" className="text-[10px]">
              {observation?.current ? 'observed' : 'unknown'}
            </Badge>
          </div>
          {entries.length ? <dl className="mt-2 grid grid-cols-2 gap-x-2 gap-y-1 text-[10px]">
            {entries.map(([key, value]) => <div key={key} className="contents">
              <dt className="truncate text-muted-foreground">{key.replace(/_/g, ' ')}</dt>
              <dd className="truncate text-right text-foreground">{value}</dd>
            </div>)}
          </dl> : <p className="mt-2 text-[10px] text-muted-foreground">
            No current summary was accepted for this surface.
          </p>}
          <Button asChild size="sm" variant="outline" className="mt-3 h-7 w-full text-[11px]">
            <Link to={binding.uiPath}>Open operating page <ExternalLink className="ml-1 h-3 w-3" /></Link>
          </Button>
        </div>;
      })}
    </div>
  </div>;
}
