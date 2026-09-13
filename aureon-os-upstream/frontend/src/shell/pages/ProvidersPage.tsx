import { GlassPageHeader } from '@/shell/GlassPage';
/**
 * Providers — LLM API-key management.
 *
 * Bring your own key for every model (OpenAI, Anthropic/Claude, xAI/Grok,
 * Gemini, Ollama, DeepSeek, Mistral, Groq, OpenRouter, Perplexity). Keys are
 * stored encrypted on the server (never returned in full — only masked), and
 * saving hot-reloads the switchboard. Reads GET /api/providers; writes
 * POST/DELETE /api/providers/<id> and POST /api/providers/<id>/test.
 */

import { useEffect, useRef, useState } from "react";
import { KeyRound, Eye, EyeOff, Loader2, CheckCircle2, ExternalLink } from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/services/apiClient";
import { useProviderConfiguration } from "@/hooks/useSetupStatus";
import { captureTestReceipt, configurationMessage, configurationStatus, datedTestEvidence, type DatedTestReceipt, type ProviderView } from "@/lib/accountConfigurationEvidence";
import { LiveDataNotice } from "@/shell/Page";
import { normalizeProviderDraft, providerErrorDetail, providerRequestBody, type ProviderDraft } from "@/lib/providerDraft";

interface Provider extends ProviderView {
  id: string;
  label: string;
  kind: string;
  default_model: string;
  default_base_url: string;
  get_keys_url: string;
  docs_url: string;
  key_optional: boolean;
  notes: string;
  model: string;
  base_url: string;
  has_key: boolean;
  key_masked: string;
  key_source: "keystore" | "env" | "none";
  credential_management?: "account_keystore" | "instance_configuration" | "pinned_cloud_secret";
  credential_writable?: boolean;
  credential_management_reason?: string;
  enabled: boolean;
  live: boolean;
}

interface EditorState {
  version: number;
  drafts: Record<string, ProviderDraft>;
  tests: Record<string, DatedTestReceipt>;
  failures: Record<string, string>;
}
const emptyEditor = (version: number): EditorState => ({ version, drafts: {}, tests: {}, failures: {} });

export default function ProvidersPage() {
  const receipt = useProviderConfiguration<Provider>();
  const providers = receipt.loading ? undefined : receipt.providers;
  const status = configurationStatus(receipt);
  const [editor, setEditor] = useState<EditorState>(() => emptyEditor(receipt.resetVersion));
  // Discard another session's drafts during render, before effects run.
  const current = editor.version === receipt.resetVersion ? editor : emptyEditor(receipt.resetVersion);
  const { drafts, tests, failures } = current;
  const version = useRef(receipt.resetVersion);
  version.current = receipt.resetVersion;
  useEffect(() => {
    setEditor(previous => {
      const base = previous.version === receipt.resetVersion ? previous : emptyEditor(receipt.resetVersion);
      if (!providers) return emptyEditor(receipt.resetVersion);
      const next: Record<string, ProviderDraft> = {};
      for (const provider of providers) next[provider.id] = normalizeProviderDraft(provider, base.drafts[provider.id]);
      return { ...base, drafts: next };
    });
  }, [providers, receipt.resetVersion]);

  const patch = (provider: Provider, fields: Partial<ProviderDraft>) => setEditor(previous => {
    const base = previous.version === version.current ? previous : emptyEditor(version.current);
    return { ...base, drafts: { ...base.drafts, [provider.id]: {
      ...normalizeProviderDraft(provider, base.drafts[provider.id]), ...fields,
    } } };
  });

  async function save(p: Provider, extra?: Partial<{ enabled: boolean }>) {
    if (p.credential_writable === false) return;
    const operationVersion = version.current;
    const d = normalizeProviderDraft(p, drafts[p.id]);
    patch(p, { saving: true });
    try {
      const body = { ...providerRequestBody(d), ...extra };
      await api.post(`/api/providers/${p.id}`, body);
      if (version.current !== operationVersion) return;
      toast.success(`${p.label} saved`);
      patch(p, { apiKey: "" }); // never keep the raw key in the field
      receipt.invalidate();
    } catch (error) {
      if (version.current === operationVersion) toast.error(`Could not save ${p.label}`, { description: providerErrorDetail(error, d.apiKey) });
    } finally {
      if (version.current === operationVersion) patch(p, { saving: false });
    }
  }

  async function test(p: Provider) {
    const operationVersion = version.current;
    const d = normalizeProviderDraft(p, drafts[p.id]);
    setEditor(previous => {
      const next = previous.version === operationVersion ? previous : emptyEditor(operationVersion);
      const nextTests = { ...next.tests }; const nextFailures = { ...next.failures };
      delete nextTests[p.id]; delete nextFailures[p.id];
      return { ...next, tests: nextTests, failures: nextFailures };
    });
    patch(p, { testing: true });
    try {
      const body = providerRequestBody(d);
      const v = await api.post<{ ok?: boolean; latency_ms?: number; sample?: string; error?: string }>(
        `/api/providers/${p.id}/test`,
        body,
        { timeoutMs: 30000 },
      );
      if (version.current !== operationVersion) return;
      const result = captureTestReceipt(v, Date.now());
      if (result.error) result.error = providerErrorDetail(result.error, d.apiKey);
      setEditor(previous => previous.version === operationVersion
        ? { ...previous, tests: { ...previous.tests, [p.id]: result } } : previous);
      if (result.ok === true) toast.success(`${p.label} test passed`, { description: `Response received ${new Date(result.receivedAt).toISOString()}` });
      else if (result.ok === false) toast.error(`${p.label} test failed`, { description: result.error || 'The provider returned a failed test result.' });
      else toast.error(`${p.label} test unavailable`, { description: 'The response did not contain a completed test result.' });
    } catch (error) {
      if (version.current === operationVersion) {
        const detail = providerErrorDetail(error, d.apiKey);
        setEditor(previous => previous.version === operationVersion
          ? { ...previous, failures: { ...previous.failures, [p.id]: detail } } : previous);
        toast.error(`${p.label} test unavailable`, { description: detail });
      }
    } finally {
      if (version.current === operationVersion) patch(p, { testing: false });
    }
  }

  async function clearKey(p: Provider) {
    if (p.credential_writable === false) return;
    const operationVersion = version.current;
    try {
      await api.del(`/api/providers/${p.id}`);
      if (version.current !== operationVersion) return;
      toast.success(`${p.label} cleared`);
      receipt.invalidate();
    } catch (error) {
      if (version.current === operationVersion) toast.error(`Could not clear ${p.label}`, { description: providerErrorDetail(error) });
    }
  }

  function statusBadge(p: Provider) {
    if (p.live === true) return <Badge variant="secondary">runtime attached</Badge>;
    if (p.has_key) return <Badge variant="secondary">key configured</Badge>;
    return <Badge variant="outline">{p.key_optional ? 'key optional' : 'key not configured'}</Badge>;
  }

  return (
    <div className="space-y-6">
      <GlassPageHeader title="Providers" icon={KeyRound} eyebrow="Cognition &amp; LLM" description="Manage model connections and test them explicitly. Masked configuration and dated test results remain separate." actions={<Button variant="outline" size="sm" onClick={receipt.refresh}>Refresh observation</Button>} />

      <LiveDataNotice />
      {receipt.isReceiptCurrent && <p className="text-xs text-muted-foreground">Configuration received {new Date(receipt.lastReceivedAt!).toISOString()}. This receipt does not attest provider availability.</p>}

      {providers === undefined && (
        <div className="grid gap-4 md:grid-cols-2">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-56 w-full" />
          ))}
        </div>
      )}

      {providers === null && (
        <Card>
          <CardHeader>
            <CardTitle>Provider configuration unavailable</CardTitle>
            <CardDescription>
              {configurationMessage(status, receipt.error)}
            </CardDescription>
            <Button variant="outline" onClick={receipt.refresh}>Retry read</Button>
          </CardHeader>
        </Card>
      )}

      {Array.isArray(providers) && (
        <div className="grid gap-4 md:grid-cols-2">
          {providers.length === 0 && <Card><CardContent className="pt-6 text-sm text-muted-foreground">The current configuration returned an empty provider inventory.</CardContent></Card>}
          {providers.map((p) => {
            const d = normalizeProviderDraft(p, drafts[p.id]);
            const managedByPinnedSecret = p.credential_management === "pinned_cloud_secret" || p.credential_writable === false;
            const observedTest = datedTestEvidence(tests[p.id]);
            return (
              <Card key={p.id} className="flex flex-col">
                <CardHeader className="pb-3">
                  <div className="flex items-center justify-between gap-2">
                    <CardTitle className="text-lg">{p.label}</CardTitle>
                    <div className="flex items-center gap-2">
                      {statusBadge(p)}
                      <Switch
                        checked={p.enabled}
                        disabled={managedByPinnedSecret}
                        onCheckedChange={(v) => save(p, { enabled: v })}
                        aria-label={`Enable ${p.label}`}
                      />
                    </div>
                  </div>
                  <CardDescription>
                    {p.has_key ? (
                      <span className="inline-flex items-center gap-1">
                        <CheckCircle2 className="h-3.5 w-3.5 text-success" />
                        key {p.key_masked} ({p.key_source})
                      </span>
                    ) : (
                      p.notes || "No key set."
                    )}
                  </CardDescription>
                </CardHeader>
                <CardContent className="flex flex-1 flex-col gap-3">
                  <p className="text-xs text-muted-foreground">
                    {observedTest.current
                      ? `Last requested test ${observedTest.ok ? 'passed' : 'failed'} · response received ${observedTest.timestamp}${observedTest.latencyMs !== null ? ` · ${observedTest.latencyMs} ms` : ''}. Point-in-time result.`
                      : 'No current dated test result. Runtime attachment and key presence do not prove a successful test.'}
                  </p>
                  {failures[p.id] && <p className="text-xs text-destructive">Test request unavailable: {failures[p.id]}</p>}
                  {observedTest.current && tests[p.id]?.error && <p className="text-xs text-muted-foreground">{tests[p.id].error}</p>}
                  {managedByPinnedSecret && (
                    <p className="text-xs text-warning" data-testid={`pinned-secret-${p.id}`}>
                      {p.credential_management_reason || "Managed by a pinned cloud secret. Update Secret Manager and redeploy to change this owner configuration."}
                    </p>
                  )}
                  <div className="space-y-1.5">
                    <Label htmlFor={`key-${p.id}`}>
                      API key{p.key_optional ? " (optional for local)" : ""}
                    </Label>
                    <div className="flex gap-2">
                      <Input
                        id={`key-${p.id}`}
                        type={d.show ? "text" : "password"}
                        placeholder={p.has_key ? "•••• (leave blank to keep)" : "paste key"}
                        value={d.apiKey}
                        autoComplete="off"
                        disabled={managedByPinnedSecret}
                        onChange={(e) => patch(p, { apiKey: e.target.value })}
                      />
                      <Button
                        type="button"
                        variant="outline"
                        size="icon"
                        disabled={managedByPinnedSecret}
                        onClick={() => patch(p, { show: !d.show })}
                        aria-label={d.show ? "Hide key" : "Show key"}
                      >
                        {d.show ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                      </Button>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-2">
                    <div className="space-y-1.5">
                      <Label htmlFor={`model-${p.id}`}>Model</Label>
                      <Input
                        id={`model-${p.id}`}
                        value={d.model}
                        disabled={managedByPinnedSecret}
                        onChange={(e) => patch(p, { model: e.target.value })}
                      />
                    </div>
                    <div className="space-y-1.5">
                      <Label htmlFor={`url-${p.id}`}>Base URL</Label>
                      <Input
                        id={`url-${p.id}`}
                        value={d.baseUrl}
                        placeholder={p.default_base_url}
                        disabled={managedByPinnedSecret}
                        onChange={(e) => patch(p, { baseUrl: e.target.value })}
                      />
                    </div>
                  </div>

                  <div className="mt-auto flex items-center justify-between pt-2">
                    <div className="flex gap-3 text-xs">
                      <a
                        className="inline-flex items-center gap-1 text-primary hover:underline"
                        href={p.get_keys_url}
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        Get key <ExternalLink className="h-3 w-3" />
                      </a>
                      <a
                        className="inline-flex items-center gap-1 text-muted-foreground hover:underline"
                        href={p.docs_url}
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        Docs <ExternalLink className="h-3 w-3" />
                      </a>
                      {p.has_key && !managedByPinnedSecret && (
                        <button
                          type="button"
                          className="text-muted-foreground hover:text-destructive hover:underline"
                          onClick={() => clearKey(p)}
                        >
                          Clear
                        </button>
                      )}
                    </div>
                    <div className="flex gap-2">
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        disabled={d.testing}
                        onClick={() => test(p)}
                      >
                        {d.testing && <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" />}
                        Test
                      </Button>
                      <Button type="button" size="sm" disabled={d.saving || managedByPinnedSecret} onClick={() => save(p)}>
                        {d.saving && <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" />}
                        {managedByPinnedSecret ? 'Managed' : 'Save'}
                      </Button>
                    </div>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
