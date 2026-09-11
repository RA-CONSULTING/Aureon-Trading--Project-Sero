/**
 * Connections — every external source, in one view.
 *
 * Trading exchanges → market data → NASA/space weather → on-chain/whale → news →
 * notifications, plus the AI/LLM models. Shows a "full operational capacity"
 * readiness banner, then per-category rows with a status dot, a connectivity
 * Test, and inline key entry. Exchange keys are delegated to the trader's .env
 * writer; keyless feeds get a reachability test only. Keys are masked; the raw
 * value only travels on Save/Test. Reads GET /api/connections(+/readiness);
 * writes POST /api/connections/<id>(+/test).
 */

import { useEffect, useRef, useState } from "react";
import { GlassPageHeader } from "@/shell/GlassPage";
import { Radar, Eye, EyeOff, Loader2, ExternalLink } from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError, api } from "@/services/apiClient";
import { createReadOnlyPoller } from "@/services/readOnlyPoller";
import { useReadOnlyPoller } from "@/hooks/useReadOnlyPoller";
import { CONFIGURATION_RECEIPT_MAX_AGE_MS, captureTestReceipt, configurationMessage, configurationStatus, datedTestEvidence, validKeyCoverage, type DatedTestReceipt } from "@/lib/accountConfigurationEvidence";
import { LiveDataNotice } from "@/shell/Page";

interface Conn {
  id: string;
  label: string;
  category: string;
  requirement: "required" | "optional" | "keyless";
  consumed_by?: string;
  has_key: boolean;
  key_masked: string;
  key_source?: string;
  enabled: boolean;
  connected?: boolean | null;
  runtime_ready?: boolean | null;
  unlocks?: string;
  get_keys_url?: string;
  docs_url?: string;
  has_probe?: boolean;
  extra_envs?: string[];
  secondary_labels?: string[];
  notes?: string;
}
interface Section { category: string; label: string; connections: Conn[]; }
interface Readiness {
  summary: {
    capacity_pct: number; keyed_present: number; keyed_total: number;
    keyless: number; all_connected: boolean; missing_count: number;
  };
  missing: { id: string; label: string; category: string; unlocks: string; get_keys_url: string }[];
}
interface Draft { apiKey: string; extra: Record<string, string>; show: boolean; testing: boolean; saving: boolean; }

const connectionStore = createReadOnlyPoller<{ sections: Section[]; readiness: Readiness }>({
  receiptMaxAgeMs: CONFIGURATION_RECEIPT_MAX_AGE_MS,
  read: async options => {
    // Both handlers read configuration/recorded metadata; neither performs a test.
    const [connections, readiness] = await Promise.all([
      api.get<{ categories?: Section[] }>('/api/connections', options),
      api.get<Readiness>('/api/connections/readiness', options),
    ]);
    if (!Array.isArray(connections?.categories) || connections.categories.some(section =>
      !section || typeof section.category !== 'string' || !Array.isArray(section.connections)
      || section.connections.some(connection => !connection || typeof connection.id !== 'string'
        || typeof connection.has_key !== 'boolean' || !['required', 'optional', 'keyless'].includes(connection.requirement)))
      || !validKeyCoverage(readiness)) {
      throw new ApiError('Connection configuration response is incomplete', { status: 200, path: '/api/connections' });
    }
    return { sections: connections.categories, readiness };
  },
});

export default function ConnectionsPage() {
  const receipt = useReadOnlyPoller(connectionStore, 15_000, 8_000);
  const sections = receipt.loading ? undefined : receipt.data?.sections ?? null;
  const readiness = receipt.data?.readiness ?? null;
  const status = configurationStatus(receipt);
  const [drafts, setDrafts] = useState<Record<string, Draft>>({});
  const [tests, setTests] = useState<Record<string, DatedTestReceipt>>({});
  const [showMissing, setShowMissing] = useState(false);
  const version = useRef(receipt.resetVersion);
  version.current = receipt.resetVersion;
  useEffect(() => { if (!sections) { setDrafts({}); setTests({}); } }, [sections]);
  useEffect(() => { setDrafts({}); setTests({}); setShowMissing(false); }, [receipt.resetVersion]);

  const draft = (c: Conn): Draft => drafts[c.id] ?? { apiKey: "", extra: {}, show: false, testing: false, saving: false };
  const patch = (id: string, f: Partial<Draft>) =>
    setDrafts((d) => ({ ...d, [id]: { ...draft({ id } as Conn), ...d[id], ...f } }));

  function body(c: Conn) {
    const d = draft(c);
    const b: Record<string, unknown> = {};
    if (d.apiKey.trim()) b.api_key = d.apiKey.trim();
    if (c.extra_envs?.length && Object.keys(d.extra).length) b.extra = d.extra;
    return b;
  }

  async function save(c: Conn) {
    const operationVersion = version.current;
    patch(c.id, { saving: true });
    try {
      const v = await api.post<{ ok?: boolean; error?: string }>(`/api/connections/${encodeURIComponent(c.id)}`, body(c));
      if (version.current !== operationVersion) return;
      if (v?.ok !== true) throw new Error(v?.error || "The server did not confirm this save. Your entered values have been kept.");
      toast.success(`${c.label} saved`, {
        description: c.category === "exchange" ? "written to .env — trader picks it up on restart" : undefined,
      });
      patch(c.id, { apiKey: "", extra: {} });
      receipt.invalidate();
    } catch (e) {
      if (version.current === operationVersion) toast.error(`Could not save ${c.label}`, { description: e instanceof Error ? e.message : undefined });
    } finally {
      if (version.current === operationVersion) patch(c.id, { saving: false });
    }
  }

  async function test(c: Conn) {
    const operationVersion = version.current;
    setTests(prev => { const next = { ...prev }; delete next[c.id]; return next; });
    patch(c.id, { testing: true });
    try {
      const v = await api.post<{ ok?: boolean; latency_ms?: number; error?: string }>(
        `/api/connections/${encodeURIComponent(c.id)}/test`,
        body(c),
        { timeoutMs: 30000 },
      );
      if (version.current !== operationVersion) return;
      const result = captureTestReceipt(v, Date.now());
      setTests(prev => ({ ...prev, [c.id]: result }));
      if (v.ok === true) toast.success(`${c.label} test passed`, { description: `Response received ${new Date(result.receivedAt).toISOString()}` });
      else toast.error(`${c.label} test failed`, { description: v.error });
    } catch {
      if (version.current === operationVersion) toast.error(`${c.label} test unavailable`, { description: 'No completed test receipt was returned.' });
    } finally {
      if (version.current === operationVersion) patch(c.id, { testing: false });
    }
  }

  function dot(c: Conn) {
    const test = datedTestEvidence(tests[c.id]);
    const color = test.current ? test.ok ? 'bg-emerald-500' : 'bg-destructive' : c.requirement === 'keyless' ? 'bg-sky-500' : c.has_key ? 'bg-amber-500' : 'bg-muted-foreground/40';
    const title = test.current ? `Requested test ${test.ok ? 'passed' : 'failed'} at ${test.timestamp}` : c.requirement === 'keyless' ? 'Public endpoint; availability untested' : c.has_key ? 'Key configured; availability untested' : 'Key not configured';
    return <span className={`inline-block h-2.5 w-2.5 rounded-full ${color}`} title={title} />;
  }

  return (
    <div className="space-y-6">
      <GlassPageHeader icon={Radar} eyebrow="External sources" title="Connections"
          description={<>
            External-source configuration and separately dated connection tests.
            Key presence and runtime flags do not establish current source availability.
          </>} />

      <LiveDataNotice />
      {receipt.isReceiptCurrent && <p className="text-xs text-muted-foreground">Configuration received {new Date(receipt.lastReceivedAt!).toISOString()}.</p>}

      {/* Readiness banner */}
      {readiness && (
        <Card>
          <CardHeader className="pb-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <CardTitle className="text-base">
                Key configuration coverage: {readiness.summary.capacity_pct}%
              </CardTitle>
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Badge variant="secondary">
                  {readiness.summary.keyed_present}/{readiness.summary.keyed_total} keys configured
                </Badge>
                <Badge variant="outline">{readiness.summary.keyless} public endpoints</Badge>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-2">
            <p className="text-xs text-muted-foreground">Configuration inventory only. These counts do not measure connection health, data freshness or operational capacity.</p>
            <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
              <div className="h-full bg-primary transition-all" style={{ width: `${readiness.summary.capacity_pct}%` }} />
            </div>
            {readiness.summary.missing_count > 0 && (
              <button className="text-xs text-primary hover:underline" onClick={() => setShowMissing((s) => !s)}>
                {readiness.summary.missing_count} sources need a key — {showMissing ? "hide" : "show"}
              </button>
            )}
            {showMissing && (
              <div className="flex flex-wrap gap-1.5 pt-1">
                {readiness.missing.map((m) => (
                  <a key={m.id} href={m.get_keys_url} target="_blank" rel="noopener noreferrer"
                     className="rounded-full border px-2 py-0.5 text-xs text-muted-foreground hover:border-primary hover:text-primary"
                     title={m.unlocks}>{m.label}</a>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {sections === undefined && (
        <div className="space-y-3">{Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-40 w-full" />)}</div>
      )}
      {sections === null && (
        <Card><CardHeader><CardTitle>Connection configuration unavailable</CardTitle></CardHeader>
          <CardContent className="space-y-2 text-sm text-muted-foreground"><p>{configurationMessage(status, receipt.error)}</p><Button variant="outline" onClick={receipt.refresh}>Retry read</Button></CardContent></Card>
      )}

      {Array.isArray(sections) && sections.map((sec) => sec.connections.length > 0 && (
        <div key={sec.category} className="space-y-2">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">{sec.label}</h2>
          <div className="grid gap-3 md:grid-cols-2">
            {sec.connections.map((c) => {
              const d = draft(c);
              const keyed = c.requirement !== "keyless";
              const observedTest = datedTestEvidence(tests[c.id]);
              return (
                <Card key={c.id} className="flex flex-col">
                  <CardContent className="flex flex-1 flex-col gap-2 pt-4">
                    <div className="flex items-center justify-between gap-2">
                      <div className="flex items-center gap-2">{dot(c)}<span className="font-medium">{c.label}</span></div>
                      {c.has_key && keyed && <Badge variant="outline" className="text-[10px]">{c.key_masked} · {c.key_source}</Badge>}
                      {c.requirement === "keyless" && <Badge variant="outline" className="text-[10px]">keyless</Badge>}
                    </div>
                    {c.unlocks && <p className="text-xs text-muted-foreground">{c.unlocks}</p>}
                    <p className="text-xs text-muted-foreground">
                      {observedTest.current
                        ? `Requested test ${observedTest.ok ? 'passed' : 'failed'} · response received ${observedTest.timestamp}${observedTest.latencyMs !== null ? ` · ${observedTest.latencyMs} ms` : ''}. Point-in-time result.`
                        : 'No current dated connection-test result.'}
                    </p>
                    {(c.connected !== undefined || c.runtime_ready !== undefined) && <p className="text-xs text-muted-foreground">Runtime attachment/readiness flag: {c.connected === true || c.runtime_ready === true ? 'reported' : 'not confirmed'}. No source timestamp is supplied for this flag.</p>}

                    {keyed && (
                      <div className="flex gap-2">
                        <Input
                          type={d.show ? "text" : "password"}
                          aria-label={`${c.label} API key`}
                          placeholder={c.has_key ? "•••• (leave blank to keep)" : "paste key"}
                          value={d.apiKey} autoComplete="off"
                          onChange={(e) => patch(c.id, { apiKey: e.target.value })}
                        />
                        <Button type="button" variant="outline" size="icon"
                          onClick={() => patch(c.id, { show: !d.show })} aria-label="toggle">
                          {d.show ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                        </Button>
                      </div>
                    )}
                    {keyed && (c.extra_envs ?? []).map((env, i) => (
                      <Input key={env} placeholder={c.secondary_labels?.[i] ?? env}
                        aria-label={c.secondary_labels?.[i] ?? env}
                        value={d.extra[env] ?? ""} autoComplete="off"
                        onChange={(e) => patch(c.id, { extra: { ...d.extra, [env]: e.target.value } })} />
                    ))}
                    {c.category === "exchange" && (
                      <p className="text-[11px] text-warning">Saved to .env — the trading process applies it on restart.</p>
                    )}

                    <div className="mt-auto flex items-center justify-between pt-1">
                      <div className="flex gap-3 text-xs">
                        {c.get_keys_url && <a className="inline-flex items-center gap-1 text-primary hover:underline" href={c.get_keys_url} target="_blank" rel="noopener noreferrer">Get key <ExternalLink className="h-3 w-3" /></a>}
                        {c.docs_url && <a className="inline-flex items-center gap-1 text-muted-foreground hover:underline" href={c.docs_url} target="_blank" rel="noopener noreferrer">Docs</a>}
                      </div>
                      <div className="flex gap-2">
                        {(c.has_probe || c.category === "ai_llm") && (
                          <Button type="button" variant="outline" size="sm" disabled={d.testing} onClick={() => test(c)}>
                            {d.testing && <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" />}Test
                          </Button>
                        )}
                        {keyed && (
                          <Button type="button" size="sm" disabled={d.saving} onClick={() => save(c)}>
                            {d.saving && <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" />}Save
                          </Button>
                        )}
                      </div>
                    </div>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}
