/**
 * Company — the organization behind Aureon OS.
 *
 * Reads GET /api/org and renders R&A Consulting and Brokerage Services Ltd
 * (trading as Aureon Zorza Technologies): the registered company facts, the
 * Innovate NI Silver recognition, community support, and contact — all
 * verifiable public data transcribed from COMPANY.md, carried with an honest
 * data-provenance badge. An unavailable gateway falls back to the explicitly
 * recorded repository profile, without asserting current official status.
 */

import { Award, Building2, ExternalLink, HeartHandshake, ScrollText } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { buildStaticCompanyProfile } from "../companyFacts";
import { useReadOnlyPoller } from "@/hooks/useReadOnlyPoller";
import { companyStore } from "@/services/platformReads";
import { readRecordedCompanyProfile } from "@/lib/platformConfiguration";
import { configurationMessage, configurationStatus } from "@/lib/accountConfigurationEvidence";
import { GlassPageHeader } from "@/shell/GlassPage";

/** Turn snake_case keys into a human label ("company_number" → "Company number"). */
function humanize(key: string): string {
  const s = key.replace(/_/g, " ");
  return s.charAt(0).toUpperCase() + s.slice(1);
}

const IDENTITY_ORDER = [
  "registered_name", "company_number", "registrar", "status",
  "registered_office", "director", "trading_name", "research_identity", "website",
];

export default function CompanyPage() {
  const receipt = useReadOnlyPoller(companyStore, 30_000, 8_000);
  const fallback = !receipt.loading && receipt.data === null;
  const data = receipt.loading ? undefined : receipt.data ?? readRecordedCompanyProfile(buildStaticCompanyProfile());

  return (
    <div className="space-y-6">
      <GlassPageHeader icon={Building2} eyebrow="Organization record" title="Company"
        description="Recorded company profile and project information."
        actions={data && <Badge variant="outline">{fallback ? 'Committed record' : 'Recorded profile'}</Badge>} />

      <p className="text-xs text-muted-foreground">
        {fallback ? `${configurationMessage(configurationStatus(receipt), receipt.error)} Showing the committed repository profile.`
          : receipt.lastReceivedAt ? `Gateway copy received ${new Date(receipt.lastReceivedAt).toISOString()}.` : 'Reading recorded profile…'}
        {' '}Source: {data?.source ?? 'committed companyFacts.ts / COMPANY.md'}. A current HTTP response does not verify current official registration or recognition status.
      </p>

      {data === undefined && (
        <div className="space-y-3">{Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-40 w-full" />)}</div>
      )}

      {data && (
        <>
          <Card>
            <CardHeader className="pb-2">
              <div className="flex items-center gap-2">
                <Building2 className="h-4 w-4 text-primary" />
                <CardTitle className="text-base">Recorded registration details</CardTitle>
              </div>
            </CardHeader>
            <CardContent className="space-y-3">
              <dl className="grid gap-x-6 gap-y-2 sm:grid-cols-2">
                {IDENTITY_ORDER.filter((k) => data.identity[k]).map((k) => (
                  <div key={k} className="flex flex-col">
                    <dt className="text-xs uppercase tracking-wide text-muted-foreground">{humanize(k)}</dt>
                    <dd className="text-sm">
                      {k === "website" ? (
                        <a className="inline-flex items-center gap-1 text-primary hover:underline"
                           href={data.identity[k]} target="_blank" rel="noreferrer">
                          {data.identity[k].replace(/^https?:\/\//, "")}
                          <ExternalLink className="h-3 w-3" />
                        </a>
                      ) : k === "company_number" ? (
                        <span className="font-mono">{data.identity[k]}</span>
                      ) : (
                        data.identity[k]
                      )}
                    </dd>
                  </div>
                ))}
              </dl>
              <p className="text-xs text-muted-foreground border-t border-border/60 pt-3">{data.identity_note}</p>
            </CardContent>
          </Card>

          <div className="grid gap-4 md:grid-cols-2">
            <Card>
              <CardHeader className="pb-2">
                <div className="flex items-center gap-2">
                  <Award className="h-4 w-4 text-warning" />
                  <CardTitle className="text-base">Recognition</CardTitle>
                </div>
              </CardHeader>
              <CardContent className="space-y-2 text-sm">
                <p className="font-medium">{data.recognition.award}</p>
                <p className="text-muted-foreground">{data.recognition.issuer}</p>
                <p className="text-xs text-muted-foreground">
                  {data.recognition.signatory} · {data.recognition.date}
                </p>
                <p className="text-xs text-muted-foreground">{data.recognition.detail}</p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-2">
                <div className="flex items-center gap-2">
                  <HeartHandshake className="h-4 w-4 text-primary" />
                  <CardTitle className="text-base">Community</CardTitle>
                </div>
              </CardHeader>
              <CardContent className="space-y-2 text-sm">
                <p className="text-muted-foreground">{data.community.summary}</p>
                <div className="flex flex-wrap gap-1.5">
                  {data.community.partners.map((p) => (
                    <Badge key={p} variant="secondary" className="text-[10px]">{p}</Badge>
                  ))}
                </div>
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-base">{data.product.name} · {data.product.powered_by}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
              <p className="text-muted-foreground">{data.product.summary}</p>
              <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs">
                {data.contact.website && (
                  <a className="inline-flex items-center gap-1 text-primary hover:underline"
                     href={data.contact.website} target="_blank" rel="noreferrer">
                    {data.contact.website.replace(/^https?:\/\//, "")}<ExternalLink className="h-3 w-3" />
                  </a>
                )}
                {data.contact.repository && (
                  <a className="inline-flex items-center gap-1 text-primary hover:underline"
                     href={data.contact.repository} target="_blank" rel="noreferrer">
                    repository<ExternalLink className="h-3 w-3" />
                  </a>
                )}
                {data.contact.license && <span className="text-muted-foreground">License: {data.contact.license}</span>}
                {data.contact.copyright && <span className="text-muted-foreground">{data.contact.copyright}</span>}
              </div>
            </CardContent>
          </Card>

          <p className="flex items-start gap-2 text-[11px] text-muted-foreground">
            <ScrollText className="mt-0.5 h-3.5 w-3.5 shrink-0" />
            {data.disclaimer}
          </p>
        </>
      )}
    </div>
  );
}
