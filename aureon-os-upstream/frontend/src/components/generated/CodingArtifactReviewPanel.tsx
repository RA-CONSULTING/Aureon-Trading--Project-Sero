import { useEffect, useRef, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { api, ApiError } from '@/services/apiClient';
import { createReadOnlyPoller } from '@/services/readOnlyPoller';
import { useReadOnlyPoller } from '@/hooks/useReadOnlyPoller';
import { readCodingDecisionAck, readCodingReview, type CodingDecision, type CodingDecisionRequest, type CodingDecisionReceipt } from '@/lib/codingArtifactReview';

const reviewStore = createReadOnlyPoller({
  read: async options => readCodingReview(await api.get('/api/coding/artifact-review', options)),
  receiptMaxAgeMs: 30_000,
  validateSource: (data, now) => now >= data.observed_at * 1000 && now - data.observed_at * 1000 <= 30_000
    ? { status: 'fresh', sourceTimestamp: data.observed_at } : { status: 'stale', reason: 'Artifact review observation expired. Refresh before deciding.' },
});
type Editor = { version: number; note: string; pending: CodingDecisionRequest | null; busy: boolean; error: string; confirmed: CodingDecisionReceipt | null };
const emptyEditor = (version: number): Editor => ({ version, note: '', pending: null, busy: false, error: '', confirmed: null });
const decisionLabel = (decision: CodingDecision) => ({ approve: 'Approve', request_revision: 'Request revision', reject: 'Reject' })[decision];

export function CodingArtifactReviewPanel({ recordedState }: { recordedState: string }) {
  const receipt = useReadOnlyPoller(reviewStore, 15_000, 10_000);
  const [editor, setEditor] = useState(() => emptyEditor(receipt.resetVersion));
  const current = editor.version === receipt.resetVersion ? editor : emptyEditor(receipt.resetVersion);
  const version = useRef(receipt.resetVersion); version.current = receipt.resetVersion;
  const active = useRef<{ controller: AbortController; version: number } | null>(null);
  useEffect(() => {
    if (active.current && active.current.version !== receipt.resetVersion) { active.current.controller.abort(); active.current = null; }
    setEditor(previous => previous.version === receipt.resetVersion ? previous : emptyEditor(receipt.resetVersion));
  }, [receipt.resetVersion]);
  useEffect(() => () => { active.current?.controller.abort(); active.current = null; }, []);
  const view = receipt.data, artifact = view?.artifact;
  const patch = (next: Partial<Editor>) => {
    const epoch = version.current;
    setEditor(previous => version.current === epoch ? { ...(previous.version === epoch ? previous : emptyEditor(epoch)), ...next } : previous);
  };
  const decide = async (decision: CodingDecision, retry = false) => {
    if (active.current?.version === version.current) return;
    if (!retry && (!artifact || !view?.can_decide || !receipt.isReceiptCurrent || current.pending)) return;
    const request = retry ? current.pending : { artifact_id: artifact!.artifact_id, artifact_version: artifact!.artifact_version,
      artifact_digest: artifact!.artifact_digest, expected_decision_id: null, decision, note: current.note, request_key: crypto.randomUUID() } satisfies CodingDecisionRequest;
    if (!request) return;
    const epoch = version.current, controller = new AbortController();
    active.current = { version: epoch, controller };
    const stillCurrent = () => version.current === epoch && active.current?.controller === controller && !controller.signal.aborted;
    patch({ pending: request, busy: true, error: '', confirmed: null });
    try {
      const post = readCodingDecisionAck(await api.post('/api/coding/artifact-review/decisions', request, { signal: controller.signal }), request);
      if (!stillCurrent()) return;
      const readback = readCodingDecisionAck(await api.get(`/api/coding/artifact-review/decisions/${encodeURIComponent(post.receipt_id)}`, { signal: controller.signal }), request);
      if (!stillCurrent()) return;
      if (post.receipt_id !== readback.receipt_id || post.receipt_digest !== readback.receipt_digest) throw new Error('Stored receipt does not match the decision acknowledgement.');
      patch({ confirmed: readback, pending: null, note: '' });
      receipt.refresh();
    } catch (error) {
      if (stillCurrent()) {
        const rejected = error instanceof ApiError && error.status >= 400 && error.status < 500 && ![408, 429].includes(error.status);
        patch({ ...(rejected ? { pending: null } : {}), error: `${error instanceof Error ? error.message : 'Decision could not be verified.'} ${rejected ? 'Refresh the artifact review before deciding again.' : 'Retry uses the same request key to resolve any uncertain commit.'}` });
        if (rejected) receipt.refresh();
      }
    } finally {
      if (stillCurrent()) { patch({ busy: false }); active.current = null; }
    }
  };
  const recorded = current.confirmed?.artifact.artifact_digest === artifact?.artifact_digest ? current.confirmed : view?.decision;
  return <div className="space-y-3" aria-label="Persistent artifact review">
    <div className="flex flex-wrap items-center justify-between gap-2"><div className="text-xs font-medium text-primary">Client approval controls</div>
      <Button size="sm" variant="outline" onClick={receipt.refresh} disabled={current.busy}>Refresh review</Button></div>
    <p className="text-xs text-muted-foreground">Forge report state: {recordedState.replaceAll('_', ' ')}. Review decisions below are stored separately and never execute or publish code.</p>
    {receipt.error && <p role="alert" className="text-xs text-destructive">{receipt.error}</p>}
    {!view && !receipt.error && <p className="text-xs">Reading authenticated artifact review…</p>}
    {view && !view.available && <p className="text-xs text-muted-foreground">No reviewable artifact: {view.reason?.replaceAll('_', ' ') || 'source manifest unavailable'}.</p>}
    {view && !view.decision_endpoint_available && <p className="text-xs text-muted-foreground">Decision recording is held by the gateway: {view.decision_hold_reason?.replaceAll('_', ' ') || 'protected ingress availability is unconfirmed'}.</p>}
    {artifact && <div className="space-y-1 text-xs">
      <p className="font-medium">{artifact.title}</p>
      <p>Artifact {artifact.artifact_id} · version {artifact.artifact_version}</p>
      <p className="break-all font-mono">SHA-256 {artifact.artifact_digest}</p>
      <details><summary className="cursor-pointer">Exact reviewed files ({artifact.files.length})</summary>
        <div className="mt-2 max-h-52 space-y-2 overflow-y-auto">{artifact.files.map(file => <p key={file.path} className="break-all font-mono">{file.path} · {file.size_bytes} bytes<br />{file.sha256}</p>)}</div></details>
    </div>}
    {recorded && <div className="space-y-1 rounded border p-2 text-xs" role="status">
      <Badge variant="outline">{decisionLabel(recorded.decision)} · recorded</Badge>
      <p>Version {recorded.artifact.artifact_version} · {new Date(recorded.recorded_at * 1000).toISOString()}</p>
      <p className="break-all font-mono">Receipt {recorded.receipt_id}</p>
      <p>Authenticated instance operator · durable read-back verified.</p>
      {recorded.note && <p className="whitespace-pre-wrap">{recorded.note}</p>}
    </div>}
    <Textarea aria-label="Artifact review note" placeholder="Review note (required for a revision request)" value={current.note} maxLength={2000}
      disabled={current.busy || !!current.pending || !!recorded || !view?.can_decide} onChange={event => patch({ note: event.target.value })} />
    <div className="flex flex-wrap gap-2">{(['approve', 'request_revision', 'reject'] as const).map(decision => <Button key={decision} size="sm" variant="outline"
      disabled={current.busy || !!current.pending || !!recorded || !view?.can_decide || !receipt.isReceiptCurrent || (decision === 'request_revision' && !current.note.trim())}
      onClick={() => void decide(decision)}>{decisionLabel(decision)}</Button>)}</div>
    {current.error && <p role="alert" className="text-xs text-destructive">{current.error}</p>}
    {current.pending && !current.busy && <Button size="sm" variant="outline" onClick={() => void decide(current.pending!.decision, true)}>Retry same decision</Button>}
    <p className="text-[11px] text-muted-foreground">A changed artifact requires a new review. Revision requests record feedback; they do not start a coding job.</p>
  </div>;
}
