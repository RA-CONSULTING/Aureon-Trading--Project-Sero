/**
 * Get Started — reviewed glass design (get_started_concept_v1), current account setup.
 *
 * Route: /start. Account onboarding covers isolated model, exchange and data-source keys,
 * followed by model testing and chat.
 * Softs: Companies House · Innovate NI Silver · MIT License · Honest Provenance.
 * Palette: zinc / gold / cyan only — no paint-green, no fake live chips.
 * Provider setup uses the shared authenticated read owner; past tests retain their date.
 */

import type { ReactNode } from "react";
import {
  ArrowRight,
  Award,
  CheckCircle2,
  ExternalLink,
  HelpCircle,
  Info,
  KeyRound,
  MessageSquare,
  Network,
  Play,
  RefreshCw,
  Scale,
  ScrollText,
  Shield,
} from "lucide-react";
import { Link, useLocation } from "react-router-dom";
import { useProviderConfiguration } from "@/hooks/useSetupStatus";
import { useIdentity } from "@/hooks/useIdentity";
import { configurationMessage, setupFromReceipt } from "@/lib/accountConfigurationEvidence";
import { onboardingProviderEvidence } from "@/lib/onboardingEvidence";
import { operatingContextView } from "@/lib/operatingContext";
import { COMPANY, RECOGNITION } from "../companyFacts";

const GOLD = "#FFB800";
const CYAN = "#00E5FF";
const BG = "#0e0e0e";
const PANEL = "rgba(18, 18, 18, 0.78)";
const BORDER = "#3f3f46";

const CH_URL = `https://find-and-update.company-information.service.gov.uk/company/${COMPANY.companyNumber}`;
const LICENSE_URL = `${COMPANY.repository}/blob/main/LICENSE`;

type StepState = "done" | "current" | "todo";

function GlassCard({
  children,
  className = "",
  active = false,
}: {
  children: ReactNode;
  className?: string;
  active?: boolean;
}) {
  return (
    <div
      className={`flex h-full flex-col rounded-xl border p-5 backdrop-blur-md ${className}`}
      style={{
        background: PANEL,
        borderColor: active ? `${GOLD}66` : BORDER,
        boxShadow: active ? `0 0 0 1px ${GOLD}22 inset` : undefined,
      }}
    >
      {children}
    </div>
  );
}

function Stepper({
  steps,
}: {
  steps: Array<{ label: string; state: StepState }>;
}) {
  return (
    <div className="relative mx-auto mb-8 max-w-3xl px-2">
      <div
        className="absolute left-[16.6%] right-[16.6%] top-4 h-px"
        style={{ background: BORDER }}
        aria-hidden
      />
      <ol className="relative grid grid-cols-3 gap-2">
        {steps.map((s, i) => {
          const active = s.state === "current" || s.state === "done";
          return (
            <li key={s.label} className="flex flex-col items-center text-center">
              <span
                className="relative z-[1] flex h-8 w-8 items-center justify-center rounded-full border text-sm font-semibold"
                style={
                  active
                    ? { background: GOLD, borderColor: GOLD, color: "#0a0a0a" }
                    : { background: BG, borderColor: BORDER, color: "#a1a1aa" }
                }
              >
                {s.state === "done" ? <CheckCircle2 className="h-4 w-4" /> : i + 1}
              </span>
              <span
                className="mt-2 text-xs font-medium"
                style={{ color: active ? GOLD : "#71717a" }}
              >
                {s.label}
              </span>
            </li>
          );
        })}
      </ol>
    </div>
  );
}

function SoftChip({
  icon: Icon,
  title,
  detail,
  href,
  accent = "gold",
}: {
  icon: typeof Shield;
  title: string;
  detail: string;
  href?: string;
  accent?: "gold" | "cyan";
}) {
  const color = accent === "cyan" ? CYAN : GOLD;
  const inner = (
    <>
      <Icon className="mt-0.5 h-4 w-4 shrink-0" style={{ color }} />
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-1.5">
          <span className="text-[12px] font-medium text-zinc-100">{title}</span>
          {href && <ExternalLink className="h-3 w-3 text-zinc-500" />}
        </div>
        <p className="text-[10px] leading-snug text-zinc-500">{detail}</p>
      </div>
    </>
  );
  const className =
    "flex items-start gap-2.5 rounded-lg border px-3 py-2.5 backdrop-blur-sm transition-colors hover:border-zinc-500";
  const style = { background: PANEL, borderColor: BORDER };
  if (href?.startsWith("http")) {
    return (
      <a href={href} target="_blank" rel="noreferrer" className={className} style={style}>
        {inner}
      </a>
    );
  }
  if (href) {
    return (
      <Link to={href} className={className} style={style}>
        {inner}
      </Link>
    );
  }
  return (
    <div className={className} style={style}>
      {inner}
    </div>
  );
}

export default function GetStartedPage() {
  const location = useLocation();
  const identityReceipt = useIdentity();
  const operatingContext = operatingContextView(identityReceipt.identity, identityReceipt.known);
  const ownerRouteRedirect = Boolean((location.state as { ownerRouteRedirect?: boolean } | null)?.ownerRouteRedirect);
  const configuration = useProviderConfiguration();
  const setup = setupFromReceipt(configuration);
  const providerEvidence = onboardingProviderEvidence(setup.known ? configuration.providers : null);

  const step1: StepState = setup.hasProvider === true ? "done" : "current";
  const step2: StepState =
    providerEvidence.tested === true ? "done" : setup.hasProvider === true ? "current" : "todo";
  const step3: StepState = providerEvidence.attached === true ? "current" : "todo";

  const steppers = [
    { label: "Connect a model", state: step1 === "done" ? ("done" as const) : ("current" as const) },
    { label: "Test connection", state: step2 },
    { label: "Open chat", state: step3 === "todo" ? ("todo" as const) : ("current" as const) },
  ];

  const modelConnected = setup.known && setup.hasProvider === true;
  const modelTested = setup.known && providerEvidence.tested === true;
  const chatReady = setup.known && providerEvidence.attached === true;

  return (
    <div className="min-h-full space-y-5 p-4 text-zinc-100 sm:p-6" style={{ background: BG }} data-page="get-started-v1">
      {/* Honesty banner — SHIPPED GLASS */}
      <div
        className="rounded-md border px-3 py-2"
        style={{ borderColor: `${GOLD}55`, background: `${GOLD}0d` }}
      >
        <p className="text-[11px] font-semibold uppercase tracking-[0.14em]" style={{ color: GOLD }}>
          {operatingContext.kind === 'owner' ? 'Owner runtime · instance configuration' : operatingContext.kind === 'tenant' ? 'Account workspace · held configuration' : 'Model setup · verifying context'}
        </p>
        <p className="mt-0.5 text-[10px] uppercase tracking-wide" style={{ color: `${GOLD}cc` }}>
          {operatingContext.kind === 'owner'
            ? 'Setup comes from the protected instance. Connection tests show their original recorded date.'
            : 'Setup comes from the current account. Connection tests show their original recorded date.'}
        </p>
      </div>

      {ownerRouteRedirect && operatingContext.kind === 'tenant' && (
        <div role="status" className="rounded-md border border-cyan-400/30 bg-cyan-400/[0.06] px-3 py-2 text-xs text-zinc-300">
          That surface belongs to the protected owner instance. Your private account workspace stayed active, and no owner runtime setting changed.
        </div>
      )}

      <div
        className="flex items-center gap-2 rounded-md border px-3 py-2"
        style={{ borderColor: `${GOLD}44`, background: "#0a0a0a" }}
      >
        <Info className="h-3.5 w-3.5 shrink-0" style={{ color: CYAN }} />
        <p className="flex-1 text-[11px] text-zinc-400">
          {setup.lastReceivedAt ? `Configuration read: ${new Date(setup.lastReceivedAt).toLocaleString()}` : 'Waiting for account configuration.'}
        </p>
        <button type="button" onClick={() => configuration.refresh()} className="inline-flex items-center gap-1.5 text-xs" style={{ color: CYAN }}><RefreshCw className="h-3.5 w-3.5" />Refresh</button>
      </div>

      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-white sm:text-3xl">Get Started</h1>
          <p className="mt-1 text-sm text-zinc-400">
            {operatingContext.kind === 'owner'
              ? 'Review the cloud instance configuration, its masked credential inventory, and current provider receipts.'
              : 'Configure this account\'s private keys, verify its connections, and open its workspace.'}
          </p>
        </div>
        <Link
          to="/legal"
          className="inline-flex items-center gap-1.5 text-sm font-medium transition-colors hover:opacity-90"
          style={{ color: GOLD }}
        >
          <HelpCircle className="h-4 w-4" />
          Need help?
          <ArrowRight className="h-3.5 w-3.5" />
        </Link>
      </div>

      <GlassCard active>
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-start gap-3">
            <KeyRound className="mt-0.5 h-5 w-5 shrink-0" style={{ color: CYAN }} />
            <div>
              <h2 className="text-sm font-semibold text-zinc-100">
                {operatingContext.kind === 'owner' ? 'Owner instance connections' : 'Connect your account'}
              </h2>
              <p className="mt-1 max-w-3xl text-xs leading-relaxed text-zinc-400">
                {operatingContext.kind === 'owner'
                  ? 'This protected cloud instance keeps its runtime configuration and preconfigured credentials server-side. Connections shows masked presence and separately dated provider evidence; tenant sessions cannot replace this configuration.'
                  : 'Add this user\'s exchange, market-data and notification credentials in Connections. Values are stored in the signed-in account\'s encrypted tenant store and are never taken from the owner instance, another user, or returned to the browser.'}
              </p>
              <p className="mt-2 text-[10px] uppercase tracking-wide text-zinc-500">
                {operatingContext.kind === 'owner'
                  ? 'Preconfigured does not mean currently available. Require a dated test or signed provider receipt; no order activity is inferred.'
                  : 'This workspace begins held. Saving a key records configuration only; a dated provider test and separate human trading approval are required before an execution route can be treated as usable.'}
              </p>
            </div>
          </div>
          <Link
            to="/ops/connections"
            className="inline-flex shrink-0 items-center justify-center gap-2 rounded-md px-4 py-2.5 text-sm font-semibold transition-opacity hover:opacity-90"
            style={{ background: GOLD, color: "#0a0a0a" }}
          >
            {operatingContext.kind === 'owner' ? 'Review instance connections' : 'Add account keys'}
            <ArrowRight className="h-4 w-4" />
          </Link>
        </div>
      </GlassCard>

      {setup.loading && (
        <div className="grid gap-4 md:grid-cols-3">
          {[0, 1, 2].map((i) => (
            <div
              key={i}
              className="h-64 animate-pulse rounded-xl border"
              style={{ background: PANEL, borderColor: BORDER }}
            />
          ))}
        </div>
      )}

      {!setup.loading && !setup.known && (
        <GlassCard>
          <div className="flex items-start gap-3">
            <Info className="mt-0.5 h-5 w-5 shrink-0" style={{ color: GOLD }} />
            <div>
              <h2 className="text-sm font-semibold text-zinc-100">Setup state unavailable</h2>
              <p className="mt-1 text-sm text-zinc-400">{configurationMessage(setup.status, setup.error)}</p>
              <p className="mt-2 text-[10px] uppercase tracking-wide text-zinc-500">
                Fail-closed — no readiness claimed without a configuration receipt.
              </p>
              <div className="mt-3 flex flex-wrap gap-4 text-xs" style={{ color: CYAN }}><Link to="/account">Open account and session</Link><Link to="/cognition/providers">Open model providers</Link></div>
            </div>
          </div>
        </GlassCard>
      )}

      {!setup.loading && setup.known && (
        <>
          <Stepper steps={steppers} />

          <div className="grid gap-4 lg:grid-cols-3">
            {/* 1 Connect a model */}
            <GlassCard active={step1 === "current" || step1 === "done"}>
              <h2
                className="text-sm font-semibold"
                style={{ color: GOLD }}
              >
                1 Connect a model
              </h2>
              <p className="mt-1 text-xs leading-relaxed text-zinc-400">
                Select and configure a supported model provider or endpoint.
              </p>
              <div
                className="mt-4 flex flex-1 flex-col items-center justify-center rounded-lg border border-dashed px-4 py-8 text-center"
                style={{ borderColor: BORDER, background: "#0a0a0a" }}
              >
                {modelConnected ? (
                  <>
                    <CheckCircle2 className="mb-2 h-8 w-8" style={{ color: CYAN }} />
                    <p className="text-sm font-medium text-zinc-100">
                      {setup.providerCount} model endpoint{setup.providerCount === 1 ? "" : "s"} configured
                    </p>
                    <p className="mt-1 text-[11px] text-zinc-500">
                      {setup.liveProvider === true
                        ? "An adapter is attached to the runtime."
                        : "Runtime attachment is not confirmed."}
                    </p>
                  </>
                ) : (
                  <>
                    <Network className="mb-2 h-8 w-8" style={{ color: CYAN }} />
                    <p className="text-sm font-medium text-zinc-100">No model connected</p>
                    <p className="mt-1 text-[11px] text-zinc-500">
                      Add a model provider or endpoint to begin.
                    </p>
                  </>
                )}
              </div>
              <Link
                to="/cognition/providers"
                className="mt-4 inline-flex w-full items-center justify-center gap-2 rounded-md px-4 py-2.5 text-sm font-semibold transition-opacity hover:opacity-90"
                style={
                  step1 === "done"
                    ? { background: "transparent", color: GOLD, border: `1px solid ${GOLD}88` }
                    : { background: GOLD, color: "#0a0a0a" }
                }
              >
                {modelConnected ? "Manage Model" : "Add Model"}
                <ArrowRight className="h-4 w-4" />
              </Link>
            </GlassCard>

            {/* 2 Test connection */}
            <GlassCard active={step2 === "current"}>
              <h2
                className="text-sm font-semibold"
                style={{ color: step2 === "current" || step2 === "done" ? GOLD : "#a1a1aa" }}
              >
                2 Test connection
              </h2>
              <p className="mt-1 text-xs leading-relaxed text-zinc-400">
                Verify the endpoint, authentication, and basic response.
              </p>
              <div
                className="mt-4 flex flex-1 flex-col items-center justify-center rounded-lg border px-4 py-8 text-center"
                style={{ borderColor: BORDER, background: "#0a0a0a" }}
              >
                {modelTested ? (
                  <>
                    <CheckCircle2 className="mb-2 h-8 w-8" style={{ color: CYAN }} />
                    <p className="text-sm font-medium text-zinc-100">Successful test recorded</p>
                    <p className="mt-1 text-[11px] text-zinc-500">
                      {providerEvidence.testedProvider}: {providerEvidence.testedAt}
                      {' '}This records a past response; run a new test to check it now.
                    </p>
                  </>
                ) : (
                  <>
                    <RefreshCw className="mb-2 h-8 w-8" style={{ color: CYAN }} />
                    <p className="text-sm font-medium text-zinc-100">Not tested</p>
                    {setup.testedProviderReason ? (
                      <p className="mt-1 text-[11px] text-zinc-500">{setup.testedProviderReason}</p>
                    ) : (
                      <p className="mt-1 text-[11px] text-zinc-500">
                        Run a real round-trip from Providers — nothing is assumed.
                      </p>
                    )}
                  </>
                )}
              </div>
              <Link
                to="/cognition/providers"
                className="mt-4 inline-flex w-full items-center justify-center gap-2 rounded-md border px-4 py-2.5 text-sm font-medium text-zinc-200 transition-colors hover:border-zinc-500"
                style={{
                  borderColor: step2 === "current" ? `${GOLD}66` : BORDER,
                  background: "#121212",
                  opacity: 1,
                  pointerEvents: "auto",
                }}
              >
                <Play className="h-4 w-4" style={{ color: step2 === "current" ? GOLD : CYAN }} />
                {modelTested ? "Retest on Providers" : "Run Test"}
              </Link>
            </GlassCard>

            {/* 3 Open chat */}
            <GlassCard active={step3 === "current"}>
              <h2
                className="text-sm font-semibold"
                style={{ color: step3 === "current" ? GOLD : "#a1a1aa" }}
              >
                3 Open chat
              </h2>
              <p className="mt-1 text-xs leading-relaxed text-zinc-400">
                Once verified, open a secure chat and start working with evidence.
              </p>
              <div
                className="mt-4 flex flex-1 flex-col items-center justify-center rounded-lg border px-4 py-8 text-center"
                style={{ borderColor: BORDER, background: "#0a0a0a" }}
              >
                {chatReady ? (
                  <>
                    <MessageSquare className="mb-2 h-8 w-8" style={{ color: CYAN }} />
                    <p className="text-sm font-medium text-zinc-100">Runtime model attached</p>
                    <p className="mt-1 text-[11px] text-zinc-500">
                      Open Operator Chat to send a request through the current provider.
                    </p>
                  </>
                ) : (
                  <>
                    <MessageSquare className="mb-2 h-8 w-8" style={{ color: CYAN }} />
                    <p className="text-sm font-medium text-zinc-100">Runtime attachment not confirmed</p>
                    <p className="mt-1 text-[11px] text-zinc-500">
                      Review Providers for connection and test details. Chat shows the response state for each request.
                    </p>
                  </>
                )}
              </div>
                <Link
                  to="/cognition/operator"
                  className="mt-4 inline-flex w-full items-center justify-center gap-2 rounded-md px-4 py-2.5 text-sm font-semibold transition-opacity hover:opacity-90"
                  style={chatReady ? { background: GOLD, color: "#0a0a0a" } : { background: '#121212', color: CYAN, border: `1px solid ${BORDER}` }}
                >
                  <MessageSquare className="h-4 w-4" />
                  Open Chat
                </Link>
            </GlassCard>
          </div>
        </>
      )}

      {/* Softs / claim bar */}
      <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
        <SoftChip
          icon={Shield}
          title={`Companies House ${COMPANY.companyNumber}`}
          detail="Registered company (NI) — verifiable public register"
          href={CH_URL}
        />
        <SoftChip
          icon={Award}
          title="Innovate NI · Silver"
          detail={`${RECOGNITION.issuer} · ${RECOGNITION.date}`}
          href="/company"
        />
        <SoftChip
          icon={Scale}
          title="MIT License"
          detail="Open-source MIT license — not a university affiliation"
          href={LICENSE_URL}
        />
        <SoftChip
          icon={ScrollText}
          title="Honest Provenance"
          detail="Inspect published evidence and its stated sources."
          href="/evidence"
          accent="cyan"
        />
      </div>

      {/* Risk disclosure */}
      <div
        className="flex flex-wrap items-center justify-between gap-3 rounded-md border px-3 py-2.5"
        style={{ borderColor: BORDER, background: "#0a0a0a" }}
      >
        <div className="flex min-w-0 flex-1 items-start gap-2">
          <Info className="mt-0.5 h-3.5 w-3.5 shrink-0 text-zinc-500" />
          <p className="text-[11px] leading-snug text-zinc-400">
            <span className="font-semibold text-zinc-300">Risk Disclosure:</span> Aureon Evidence OS
            is not financial advice. Model outputs may be inaccurate or incomplete. Users are
            responsible for independent verification and due diligence.
          </p>
        </div>
        <Link
          to="/legal#risk"
          className="inline-flex shrink-0 items-center gap-1.5 text-[11px] font-semibold transition-opacity hover:opacity-90"
          style={{ color: GOLD }}
        >
          Read Full Risk Disclosure
          <ExternalLink className="h-3 w-3" />
        </Link>
      </div>

    </div>
  );
}
