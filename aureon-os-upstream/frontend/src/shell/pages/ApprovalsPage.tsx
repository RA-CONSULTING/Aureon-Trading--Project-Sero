/**
 * Approvals — the director's desk.
 *
 * The big plays Aureon prepared and is holding for your call. Polls
 * GET /api/approvals; Approve / Reject POST to /api/approvals/<id>. Approving
 * RECORDS your decision (the human gate) — it does not itself execute the live move
 * (the trade / payment / filing stays your deliberate step). You can also decide by
 * replying to the email Aureon sends.
 */

import { useRef, useState } from "react";
import { GlassPageHeader } from "@/shell/GlassPage";
import { ListChecks, ShieldCheck, Check, X } from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { LiveDataNotice } from "@/shell/Page";
import { api } from "@/services/apiClient";
import { createReadOnlyPoller } from "@/services/readOnlyPoller";
import { useReadOnlyPoller } from "@/hooks/useReadOnlyPoller";
import { parseApprovalDesk, requirePendingApproval, type ApprovalDesk as Desk } from "@/lib/approvalDesk";

const deskStore = createReadOnlyPoller<Desk>({
  read: async (options) => parseApprovalDesk(await api.get("/api/approvals", options)),
  receiptMaxAgeMs: 15_000,
});

export default function ApprovalsPage() {
  const desk = useReadOnlyPoller(deskStore, 5_000, 8_000);
  const data = desk.loading ? undefined : desk.data;
  const [busy, setBusy] = useState<string | null>(null);
  const deciding = useRef(false);

  async function decide(id: string, decision: "approve" | "reject") {
    const current = deskStore.getSnapshot();
    if (deciding.current || !current.isReceiptCurrent || !current.data || current.error) return;
    deciding.current = true;
    setBusy(id);
    try {
      const latest = parseApprovalDesk(await api.get("/api/approvals", { timeoutMs: 8_000 }));
      requirePendingApproval(latest, id);
      const saved = await api.post<{ ok?: boolean }>(`/api/approvals/${encodeURIComponent(id)}`, { decision });
      if (saved?.ok !== true) throw new Error("The server did not confirm this decision. Refresh the desk to check its recorded state.");
      toast.success(decision === "approve" ? "Approval recorded" : "Rejection recorded");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not record the decision");
    } finally {
      deskStore.invalidate();
      deciding.current = false;
      setBusy(null);
    }
  }

  return (
    <div className="space-y-6">
      <GlassPageHeader icon={ListChecks} eyebrow="Director's desk" title="Approvals"
        description="Prepared proposals and their recorded decisions. Approval records do not execute the proposed move." />

      <LiveDataNotice />

      <div className="flex items-start gap-2 rounded-md border px-3 py-2 text-[11px] text-muted-foreground">
        <ShieldCheck className="mt-0.5 h-3.5 w-3.5 shrink-0" />
        <span>
          Approving <strong>records your decision</strong> — the human gate. It does not itself
          execute the live move; the trade, payment, or filing stays your deliberate step. You can
          also decide by replying to the email Aureon sends.
        </span>
      </div>

      {data === undefined && (
        <div className="space-y-3">{Array.from({ length: 2 }).map((_, i) => <Skeleton key={i} className="h-24 w-full" />)}</div>
      )}
      {data === null && (
        <Card><CardHeader><CardTitle>Current approval queue unavailable</CardTitle></CardHeader>
          <CardContent className="space-y-3 text-sm text-muted-foreground">
            <p>{desk.error || "The queue has not been confirmed. Decisions require a current read."}</p>
            <Button variant="outline" size="sm" onClick={desk.refresh}>Refresh queue</Button>
          </CardContent></Card>
      )}

      {data && data.pending?.length === 0 && (
        <Card>
          <CardHeader><CardTitle className="text-base">Desk clear</CardTitle></CardHeader>
          <CardContent className="text-sm text-muted-foreground">
            The current queue contains no pending decisions.
          </CardContent>
        </Card>
      )}

      {data && data.pending?.map((it) => (
        <Card key={it.id}>
          <CardHeader className="pb-2">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <CardTitle className="text-base capitalize">{it.kind}</CardTitle>
              <div className="flex items-center gap-2">
                <Badge variant="outline" className="text-[10px]">risk {it.risk}</Badge>
                <Badge variant="outline" className="text-[10px]">by {it.prepared_by}</Badge>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-3">
            <p className="text-sm">{it.summary}</p>
            <div className="flex gap-2">
              <Button size="sm" disabled={busy !== null || !desk.isReceiptCurrent || Boolean(desk.error)} onClick={() => decide(it.id, "approve")}>
                <Check className="mr-1 h-4 w-4" /> Approve
              </Button>
              <Button size="sm" variant="outline" disabled={busy !== null || !desk.isReceiptCurrent || Boolean(desk.error)} onClick={() => decide(it.id, "reject")}>
                <X className="mr-1 h-4 w-4" /> Reject
              </Button>
            </div>
          </CardContent>
        </Card>
      ))}

      {data && data.recent && data.recent.some((r) => r.status !== "pending") && (
        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-sm">Recent decisions</CardTitle></CardHeader>
          <CardContent className="space-y-1.5">
            {data.recent.filter((r) => r.status !== "pending").slice(0, 8).map((r) => (
              <div key={r.id} className="flex items-center justify-between gap-2 rounded-md border px-3 py-1.5 text-sm">
                <span className="min-w-0 truncate"><span className="capitalize">{r.kind}</span> — {r.summary}</span>
                <Badge variant="outline" className={`text-[10px] ${r.status === "approved" ? "text-success" : "text-destructive"}`}>
                  {r.status}
                </Badge>
              </div>
            ))}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
