import { GlassPageHeader } from '@/shell/GlassPage';
/**
 * Operator Chat — talk to the grounded Aureon cognition.
 *
 * POSTs to the gateway's /api/cognition/reason (through the nginx /api proxy)
 * and renders the full provenance honestly: repo grounding sources, tool calls,
 * the conscience verdict, and blocks. No backend → a clear offline notice.
 */

import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Brain, KeyRound, Send, ShieldAlert, ShieldCheck, Wrench } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { api, ApiError } from "@/services/apiClient";
import { useSetupStatus } from "@/hooks/useSetupStatus";
import { useReadOnlyPoller } from "@/hooks/useReadOnlyPoller";
import { operatorReleaseReadinessStore } from "@/services/platformReads";
import { RELEASE_REQUIREMENTS, operatorConscienceVerdict, releaseReadinessView } from "@/lib/operatorReleaseReadiness";
import { appendChatSessionTurn, chatSessionForVersion, emptyChatSession } from '@/lib/operatorChatSession';
import { LiveDataNotice } from "../Page";

interface GroundingSource {
  title?: string;
  path?: string;
  score?: string;
}

interface ResponseEnvelope {
  status?: string;
  sources_statement?: string;
  capability?: { families?: string[]; complex?: boolean };
  coherence?: { lead_family?: string; gamma_by_cluster?: Record<string, number | null> } | null;
  actualization?: { realized_count?: number; parked_count?: number; answer?: string } | null;
  bake?: { passes?: number; complete?: boolean | null; refined?: boolean } | null;
  knowledge_reach?: string[];
  acquisition?: { triggered?: boolean; outcome?: string } | null;
  coherence_gate?: { aperture?: string; field_status?: string } | null;
  heart?: {
    alive?: { symbolic_life_score?: number | null; status?: string };
    love?: { love_amplitude?: number | null; mood?: string | null; status?: string };
    power?: { withheld?: string[]; statement?: string };
  } | null;
}

interface CognitionReply {
  text?: string;
  grounded?: boolean;
  blocked?: boolean;
  conscience_verdict?: string;
  conscience_message?: string;
  turns?: number;
  elapsed_ms?: number;
  grounding?: { sources?: GroundingSource[] } | null;
  tool_calls?: Array<{ tool?: string; name?: string }>;
  trace_id?: string;
  envelope?: ResponseEnvelope | null;
}

interface ChatTurn {
  role: "user" | "aureon" | "error";
  text: string;
  reply?: CognitionReply;
}

const SUGGESTIONS = [
  "How does Aureon ground its answers in the repo?",
  "Explain the Master Formula Λ(t) in plain language.",
  "What does the current platform status mean?",
  "How do I run the operator gateway locally?",
];

function ConscienceBadge({ reply }: { reply: CognitionReply }) {
  const verdict = operatorConscienceVerdict(reply.conscience_verdict);
  const approved = reply.blocked === false && verdict.approved;
  return (
    <Badge variant="outline" className={`gap-1 ${reply.blocked === true ? 'border-destructive/40 text-destructive' : approved ? 'border-success/40 text-success' : 'text-muted-foreground'}`}>
      {approved ? <ShieldCheck className="h-3 w-3" /> : <ShieldAlert className="h-3 w-3" />}
      {reply.blocked === true ? 'blocked · ' : 'conscience: '}{verdict.label}
    </Badge>
  );
}

export default function OperatorChatPage() {
  const scrollRef = useRef<HTMLDivElement>(null);
  const setup = useSetupStatus();
  const releaseReceipt = useReadOnlyPoller(operatorReleaseReadinessStore, 15_000, 8_000);
  const [session, setSession] = useState(() => emptyChatSession<ChatTurn>(releaseReceipt.resetVersion));
  const { turns, input, busy } = chatSessionForVersion(session, releaseReceipt.resetVersion);
  const sessionVersion = useRef(releaseReceipt.resetVersion);
  sessionVersion.current = releaseReceipt.resetVersion;
  const request = useRef<{ version: number; controller: AbortController } | null>(null);
  useEffect(() => {
    if (request.current && request.current.version !== releaseReceipt.resetVersion) {
      request.current.controller.abort();
      request.current = null;
    }
    setSession(previous => chatSessionForVersion(previous, releaseReceipt.resetVersion));
  }, [releaseReceipt.resetVersion]);
  useEffect(() => () => {
    request.current?.controller.abort();
    request.current = null;
  }, []);
  const release = releaseReadinessView(releaseReceipt);
  // Gateway reachable but no model connected → guide the user instead of failing at send time.
  const needsKey = setup.known && setup.hasProvider === false;

  const ask = async (prompt: string) => {
    const trimmed = prompt.trim();
    const version = sessionVersion.current;
    if (!trimmed || busy || needsKey || request.current?.version === version) return;
    request.current?.controller.abort();
    const controller = new AbortController();
    request.current = { version, controller };
    const stillCurrent = () => sessionVersion.current === version && request.current?.controller === controller && !controller.signal.aborted;
    setSession(previous => ({
      ...appendChatSessionTurn(chatSessionForVersion(previous, version), version, { role: 'user', text: trimmed }),
      input: '', busy: true,
    }));
    try {
      // Reasoning can take a while; allow a generous timeout. apiClient attaches the
      // end-user session bearer when one exists (tenant identity).
      const reply = await api.post<CognitionReply>(
        "/api/cognition/reason",
        { prompt: trimmed },
        { timeoutMs: 80000, signal: controller.signal },
      );
      if (stillCurrent()) setSession(previous => sessionVersion.current === version
        ? appendChatSessionTurn(previous, version, { role: 'aureon', text: reply.text || '(empty answer)', reply }) : previous);
    } catch (err) {
      if (!stillCurrent()) return;
      const offline = err instanceof ApiError && err.offline;
      const message = err instanceof Error ? err.message : String(err);
      setSession(previous => sessionVersion.current === version ? appendChatSessionTurn(previous, version, {
          role: "error",
          text: offline
            ? `Could not reach the cognition gateway (${message}). Start the operator service or check the /api proxy.`
            : `The cognition gateway returned an error: ${message}`,
        }) : previous);
    } finally {
      if (stillCurrent()) {
        request.current = null;
        setSession(previous => previous.version === version && sessionVersion.current === version ? { ...previous, busy: false } : previous);
        requestAnimationFrame(() => {
          if (sessionVersion.current === version) scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' });
        });
      }
    }
  };

  return (
    <div className="mx-auto flex h-full max-w-3xl flex-col gap-4 p-6">
      <GlassPageHeader title="Operator Chat" icon={Brain} eyebrow="Cognition &amp; LLM" description="Talk to the configured cognition service and inspect its response provenance, grounding and reported tool use." actions={<Button variant="outline" size="sm" onClick={releaseReceipt.refresh}>Refresh observation</Button>} />

      <LiveDataNotice />

      <Card className={release.state === 'held' ? 'border-warning/40' : undefined}>
        <CardContent className="space-y-2 pt-4 text-sm">
          <p className="flex items-center gap-2 font-medium"><ShieldAlert className="h-4 w-4" />
            {release.state === 'held' ? 'Operator requests held' : release.state === 'loading' ? 'Reading release status' : 'Release status unavailable'}
          </p>
          <p className="text-muted-foreground">{release.message}</p>
          {release.state === 'held' && releaseReceipt.data && (
            <>
              <p className="text-xs text-muted-foreground">Implementation contract received {new Date(release.receivedAt).toISOString()}. Source and configuration attestations are unavailable.</p>
              <details className="text-xs">
                <summary className="cursor-pointer">Release requirements ({releaseReceipt.data.requirements.length})</summary>
                <ul className="mt-2 space-y-1 text-muted-foreground">
                  {releaseReceipt.data.requirements.map(row => <li key={row.id}>{RELEASE_REQUIREMENTS[row.id].label}: {row.state.replace(/_/g, ' ')}</li>)}
                </ul>
                <p className="mt-2 text-muted-foreground">These states describe integration into this gateway. They do not establish whether external keys or services exist.</p>
              </details>
            </>
          )}
        </CardContent>
      </Card>

      <div className="flex-1 overflow-y-auto rounded-lg border border-border/60" ref={scrollRef}>
        <div className="space-y-4 p-4">
          {turns.length === 0 && needsKey && (
            <div className="flex flex-col items-center gap-3 py-10 text-center">
              <KeyRound className="h-8 w-8 text-muted-foreground" />
              <div className="space-y-1">
                <p className="text-sm font-medium">Connect a model to start chatting</p>
                <p className="max-w-sm text-sm text-muted-foreground">
                  Add an API key for any model and Aureon can reason for you. It takes a minute —
                  your key is stored encrypted and, when you're signed in, kept to your account alone.
                </p>
              </div>
              <Button asChild size="sm">
                <Link to="/cognition/providers">Add a model key</Link>
              </Button>
            </div>
          )}
          {turns.length === 0 && !needsKey && (
            <div className="space-y-2 py-8 text-center">
              <p className="text-sm text-muted-foreground">Ask anything — from the repo to the cosmos.</p>
              <div className="flex flex-wrap justify-center gap-2">
                {SUGGESTIONS.map((s) => (
                  <Button key={s} size="sm" variant="outline" className="text-xs" onClick={() => ask(s)}>
                    {s}
                  </Button>
                ))}
              </div>
            </div>
          )}
          {turns.map((turn, i) => (
            <div key={i} className={turn.role === "user" ? "flex justify-end" : "flex justify-start"}>
              <Card
                className={
                  turn.role === "user"
                    ? "max-w-[85%] border-primary/30 bg-primary/10"
                    : turn.role === "error"
                      ? "max-w-[85%] border-destructive/40"
                      : "max-w-[85%] border-border/60"
                }
              >
                <CardContent className="space-y-2 p-3">
                  <p className="whitespace-pre-wrap text-sm">{turn.text}</p>
                  {turn.reply && (
                    <div className="flex flex-wrap items-center gap-1.5 border-t border-border/40 pt-2">
                      <ConscienceBadge reply={turn.reply} />
                      <Badge variant="outline" className="text-muted-foreground">
                        {turn.reply.envelope?.sources_statement ||
                          (turn.reply.grounded === true ? "repo-grounded" : turn.reply.grounded === false ? "general knowledge" : "grounding unreported")}
                      </Badge>
                      {turn.reply.envelope?.status && turn.reply.envelope.status !== "ok" && (
                        <Badge variant="outline" className="border-warning/40 text-warning">
                          {turn.reply.envelope.status.replace(/_/g, " ")}
                        </Badge>
                      )}
                      {turn.reply.envelope?.coherence?.lead_family && (
                        <Badge variant="outline" className="text-muted-foreground">
                          council lead: {turn.reply.envelope.coherence.lead_family.replace(/^safe_/, "").replace(/_/g, " ")}
                        </Badge>
                      )}
                      {turn.reply.envelope?.actualization &&
                        (turn.reply.envelope.actualization.parked_count ?? 0) > 0 && (
                          <Badge variant="outline" className="text-muted-foreground">
                            {turn.reply.envelope.actualization.realized_count ?? 'unreported'} reported realized ·{" "}
                            {turn.reply.envelope.actualization.parked_count} parked
                          </Badge>
                        )}
                      {turn.reply.envelope?.knowledge_reach &&
                        turn.reply.envelope.knowledge_reach.join(",") !== "general_knowledge" && (
                          <Badge variant="outline" className="text-muted-foreground">
                            reach: {turn.reply.envelope.knowledge_reach.join(" + ").replace(/_/g, " ")}
                          </Badge>
                        )}
                      {turn.reply.envelope?.acquisition?.triggered && (
                        <Badge variant="outline" className="text-muted-foreground">
                          acquired: {turn.reply.envelope.acquisition.outcome}
                        </Badge>
                      )}
                      {turn.reply.envelope?.coherence_gate?.aperture &&
                        turn.reply.envelope.coherence_gate.aperture !== "full" && (
                          <Badge variant="outline" className="border-warning/40 text-warning">
                            aperture: {turn.reply.envelope.coherence_gate.aperture}
                          </Badge>
                        )}
                      {typeof turn.reply.envelope?.heart?.alive?.symbolic_life_score === "number" && (
                        <Badge variant="outline" className="text-muted-foreground">
                          symbolic-life model: {turn.reply.envelope.heart.alive.symbolic_life_score.toFixed(2)}
                        </Badge>
                      )}
                      {(turn.reply.envelope?.heart?.power?.withheld?.length ?? 0) > 0 && (
                        <Badge
                          variant="outline"
                          className="text-muted-foreground"
                          title={turn.reply.envelope?.heart?.power?.statement}
                        >
                          power held: {turn.reply.envelope?.heart?.power?.withheld?.length}
                        </Badge>
                      )}
                      {turn.reply.envelope?.bake?.refined && (
                        <Badge variant="outline" className="text-muted-foreground">
                          refinement passes: {turn.reply.envelope.bake.passes ?? 'unreported'}
                        </Badge>
                      )}
                      {turn.reply.envelope?.bake?.complete === false && (
                        <Badge variant="outline" className="border-warning/40 text-warning">
                          incomplete — honest seal
                        </Badge>
                      )}
                      {(turn.reply.tool_calls?.length ?? 0) > 0 && (
                        <Badge variant="outline" className="gap-1 text-muted-foreground">
                          <Wrench className="h-3 w-3" /> {turn.reply.tool_calls?.length} tool call
                          {(turn.reply.tool_calls?.length ?? 0) > 1 ? "s" : ""}
                        </Badge>
                      )}
                      {typeof turn.reply.elapsed_ms === "number" && (
                        <span className="text-[10px] text-muted-foreground">
                          {Math.round(turn.reply.elapsed_ms)} ms
                        </span>
                      )}
                    </div>
                  )}
                  {turn.reply?.grounding?.sources?.length ? (
                    <div className="space-y-0.5">
                      {turn.reply.grounding.sources.slice(0, 4).map((s, j) => (
                        <p key={j} className="truncate font-mono text-[10px] text-muted-foreground">
                           {s.path || s.title}
                          {s.score ? ` · ${s.score}` : ""}
                        </p>
                      ))}
                    </div>
                  ) : null}
                </CardContent>
              </Card>
            </div>
          ))}
          {busy && <p className="animate-pulse text-xs text-muted-foreground">Aureon is reasoning…</p>}
        </div>
      </div>

      <form
        className="flex gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          ask(input);
        }}
      >
        <Textarea
          value={input}
          disabled={needsKey}
          onChange={(e) => {
            const value = e.target.value;
            const version = sessionVersion.current;
            setSession(previous => ({ ...chatSessionForVersion(previous, version), input: value }));
          }}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              ask(input);
            }
          }}
          placeholder={needsKey ? "Connect and test your own model before chatting" : "Ask the Aureon cognition… (Enter to send, Shift+Enter for newline)"}
          className="min-h-[44px] resize-none"
          rows={1}
        />
        <Button type="submit" disabled={busy || needsKey || !input.trim()} aria-label="Send">
          <Send className="h-4 w-4" />
        </Button>
      </form>
    </div>
  );
}
