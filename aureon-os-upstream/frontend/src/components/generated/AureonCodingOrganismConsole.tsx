import { GlassPageHeader } from "@/shell/GlassPage";
import { consoleControlAvailable, consoleDisplayValue } from "@/lib/generatedConsoleDisplayEvidence";
import { consoleReceiptCurrent } from "@/lib/generatedConsoleEvidence";
import React, { useEffect, useRef, useState, type ChangeEvent, type ComponentType } from "react";
import { BrainCircuit, CheckCircle2, Code2, FileText, MessageSquare, MousePointer2, Radio, RefreshCw, Send, ShieldCheck, TestTube2, Upload } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/services/apiClient";
import {
  AUREON_EVOLUTION_RUNTIME_PATCH_SUMMARY,
  AUREON_EVOLUTION_RUNTIME_PATCHES,
  aureonEvolutionActivePatchCount,
} from "@/components/generated/aureonEvolutionRuntimePatches";

// Runtime receipts are heterogeneous generated JSON envelopes.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
type JsonMap = Record<string, any>;
type ChatMessage = {
  role: "user" | "assistant";
  text: string;
  ts?: string;
  source?: string;
  model?: string;
  latency_ms?: number;
  response_quality?: { score?: number; passed?: boolean; compiler_applied?: boolean; snags?: string[] };
  weaver?: { policy?: string; shards?: Array<{ name?: string; ok?: boolean; latency_ms?: number }> };
  dynamic_filter?: {
    filter_mode?: string;
    lane?: string;
    task_family?: string;
    source_packets?: Array<{ title?: string; source_path?: string; confidence?: number }>;
    hnc_auris_report?: JsonMap;
    handover_ready?: boolean;
  };
};
type ArtifactItem = {
  url: string;
  path?: string;
  kind: "image" | "video" | "file";
  title: string;
};

const CODING_STATUS_PATH = "/api/coding/status";
const CODING_STATUS_SCHEMA = "aureon.operator.coding-cloud-status.v1";
const LIVE_REFRESH_FALLBACK_MS = 5000;
const NOT_COMMISSIONED_MESSAGE =
  "The cloud coding worker is not commissioned. This authenticated page is read-only until a reviewed worker and action-custody contract are deployed.";

function hasPayload(value: unknown): value is JsonMap {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value) && Object.keys(value as JsonMap).length > 0;
}

function fmt(value: unknown): string {
  return consoleDisplayValue(value);
}

function compactEvidence(stage: JsonMap): string {
  const evidence = stage.evidence || {};
  const parts: string[] = [];
  if (evidence.intent) parts.push(`intent ${evidence.intent}`);
  if (evidence.tool_used) parts.push(`tool ${evidence.tool_used}`);
  if (evidence.plan_status) parts.push(`plan ${evidence.plan_status}`);
  if (evidence.proposal_status) parts.push(`proposal ${evidence.proposal_status}`);
  if (typeof evidence.vm_tool_count !== "undefined") parts.push(`VM tools ${evidence.vm_tool_count}`);
  if (Array.isArray(evidence.commands)) parts.push(`${evidence.commands.length} command(s)`);
  if (Array.isArray(evidence.published_files)) parts.push(`${evidence.published_files.length} file(s) published`);
  if (evidence.validation?.confidence) parts.push(`confidence ${Math.round(Number(evidence.validation.confidence) * 100)}%`);
  return parts.join(" | ") || "evidence attached";
}

function normalizePublicUrl(value: unknown): string {
  const raw = String(value || "").trim();
  if (!raw) return "";
  if (/^https?:\/\//i.test(raw)) return raw;
  if (raw.startsWith("/")) return raw;
  const publicIndex = raw.replace(/\\/g, "/").indexOf("frontend/public/");
  if (publicIndex >= 0) {
    return `/${raw.replace(/\\/g, "/").slice(publicIndex + "frontend/public/".length)}`;
  }
  return raw.startsWith("aureon_") ? `/${raw}` : raw;
}

function artifactKind(url: string): ArtifactItem["kind"] {
  const lower = url.toLowerCase();
  if (/\.(svg|png|jpe?g|gif|webp)(?:$|\?)/.test(lower)) return "image";
  if (/\.(mp4|webm|mov)(?:$|\?)/.test(lower)) return "video";
  return "file";
}

function collectArtifacts(status: JsonMap): ArtifactItem[] {
  const found: ArtifactItem[] = [];
  const push = (urlValue: unknown, pathValue: unknown, titleValue: unknown) => {
    const url = normalizePublicUrl(urlValue);
    if (!url || found.some((item) => item.url === url)) return;
    found.push({
      url,
      path: String(pathValue || ""),
      kind: artifactKind(url),
      title: String(titleValue || "Aureon artifact"),
    });
  };

  const steps = status.goal_route?.plan?.steps;
  if (Array.isArray(steps)) {
    steps.forEach((step: JsonMap) => {
      const result = step.execution_result || step.result?.result || step.result || {};
      push(result.public_url, result.asset_path || result.artifact_path, step.title || step.intent);
      push(result.preview_url, result.preview_path, step.title || step.intent);
    });
  }
  push(status.public_url, status.asset_path || status.artifact_path, status.subject || status.status);
  push(status.where?.public_url, status.where?.asset_path, status.what?.subject || "Aureon artifact");
  push(status.artifact_manifest?.public_url, status.artifact_manifest?.asset_path, status.task_family || "Capability forge artifact");
  push(status.artifact_manifest?.preview_url, status.artifact_manifest?.preview_path, status.task_family || "Capability forge preview");
  push(status.capability_forge?.artifact_manifest?.public_url, status.capability_forge?.artifact_manifest?.asset_path, status.capability_forge?.task_family || "Capability forge artifact");
  push(status.capability_forge?.artifact_manifest?.preview_url, status.capability_forge?.artifact_manifest?.preview_path, status.capability_forge?.task_family || "Capability forge preview");
  const complexCases = status.complex_build_stress_audit?.cases;
  if (Array.isArray(complexCases)) {
    complexCases.forEach((stressCase: JsonMap) => {
      const manifest = stressCase.quality_report?.artifact_manifest || {};
      const title = stressCase.id || stressCase.actual_artifacts?.kind || "Complex stress artifact";
      push(manifest.preview_url || stressCase.actual_artifacts?.url, manifest.preview_path || stressCase.actual_artifacts?.path, title);
      push(manifest.public_url || stressCase.actual_artifacts?.url, manifest.asset_path || stressCase.actual_artifacts?.path, title);
    });
  }
  return found;
}

export function AureonCodingOrganismConsole() {
  const [status, setStatus] = useState<JsonMap>({});
  const [prompt, setPrompt] = useState("Connect Aureon coding systems, inspect the repo, propose the smallest safe patch, and run focused tests.");
  const [runTests, setRunTests] = useState(true);
  const [includeDesktop, setIncludeDesktop] = useState(true);
  const busy = false;
  const [error, setError] = useState("");
  const [loadedFileName, setLoadedFileName] = useState("");
  const [scopeAnswers, setScopeAnswers] = useState<Record<string, string>>({});
  const [phiStatus, setPhiStatus] = useState<JsonMap>({});
  const [chatInput, setChatInput] = useState("What can you see in the coding cockpit right now?");
  const [chatMessages] = useState<ChatMessage[]>([]);
  const chatBusy = false;
  const [chatError, setChatError] = useState("");
  const [ollamaStatus, setOllamaStatus] = useState<JsonMap>({});
  const reloadBusy = false;
  const [cloudStatus, setCloudStatus] = useState<JsonMap>({});
  const [cloudStatusError, setCloudStatusError] = useState("");
  const [now, setNow] = useState(Date.now);
  const [gatewayReceivedAt, setGatewayReceivedAt] = useState<number | null>(null);
  const [statusReceivedAt, setStatusReceivedAt] = useState<number | null>(null);
  const [phiReceivedAt, setPhiReceivedAt] = useState<number | null>(null);
  const [ollamaReceivedAt, setOllamaReceivedAt] = useState<number | null>(null);
  const refreshInFlight = useRef(false);
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, []);
  const refresh = async () => {
    if (refreshInFlight.current) return;
    refreshInFlight.current = true;
    try {
      const payload = await api.get<JsonMap>("/api/coding/status", { timeoutMs: 8000 });
      if (
        payload.schema_version !== CODING_STATUS_SCHEMA ||
        payload.capabilities?.status_read !== true ||
        payload.authority?.owner_only !== true ||
        payload.authority?.tenant_access !== false ||
        payload.authority?.execution_authority !== false
      ) {
        throw new Error("coding_status_contract_invalid");
      }
      const receivedAt = Date.now();
      const workerAvailable = payload.available === true && payload.commissioned === true;
      const lastRun = hasPayload(payload.last_run) ? payload.last_run : {};
      const phi = hasPayload(payload.phi) ? payload.phi : {};
      const ollama = hasPayload(payload.ollama) ? payload.ollama : {};

      setCloudStatus(payload);
      setCloudStatusError("");
      setGatewayReceivedAt(receivedAt);
      setStatus(lastRun);
      setStatusReceivedAt(workerAvailable && hasPayload(lastRun) ? receivedAt : null);
      setPhiStatus(phi);
      setPhiReceivedAt(workerAvailable && phi.available === true ? receivedAt : null);
      setOllamaStatus(ollama);
      setOllamaReceivedAt(workerAvailable && ollama.available === true ? receivedAt : null);
    } catch {
      setCloudStatus({});
      setCloudStatusError("Cannot reach the authenticated cloud coding status route.");
      setGatewayReceivedAt(null);
      setStatus({});
      setStatusReceivedAt(null);
      setPhiStatus({});
      setPhiReceivedAt(null);
      setOllamaStatus({});
      setOllamaReceivedAt(null);
    } finally {
      refreshInFlight.current = false;
    }
  };

  useEffect(() => {
    refresh();
    const timer = window.setInterval(refresh, LIVE_REFRESH_FALLBACK_MS);
    return () => window.clearInterval(timer);
  }, []);

  const submitPrompt = async (extraBody: JsonMap = {}) => {
    void extraBody;
    setError(NOT_COMMISSIONED_MESSAGE);
  };

  const sendPhiChat = async () => {
    setChatError(NOT_COMMISSIONED_MESSAGE);
  };

  const reloadPhiVoiceWorker = async () => {
    setChatError(NOT_COMMISSIONED_MESSAGE);
  };

  const approveScope = async () => {
    await submitPrompt({
      scope_approved: true,
      scope_answers: scopeAnswers,
      base_job_id: status.client_job?.job_id || "",
    });
  };

  const sendFullCodingJob = async () => {
    await submitPrompt({
      scope_approved: true,
      scope_answers: {
        goal: prompt,
        deliverables: "Repo changes or reports, code proposal, focused tests, proof checklist, snagging result, and client handover.",
        target_system: "Aureon repository, coding organism bridge, generated console evidence, and target files named by the prompt.",
        constraints: "Preserve live trading, payment, filing, credential, and destructive OS boundaries. Do not expose secrets.",
        acceptance: "Goal route is clean, focused tests pass or are explicitly skipped, HNC/Auris proof is recorded, and blocking snags are zero.",
        ...scopeAnswers,
      },
      base_job_id: status.client_job?.job_id || "",
    });
  };

  const loadPromptFile = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    const text = await file.text();
    setLoadedFileName(file.name);
    setPrompt(
      `Aureon must ingest ${file.name}, marry up what Codex can do with Aureon, write bridge work orders, test itself, and publish a completion report.\n\n` +
      `Source document uploaded through the coding organism UI:\n\n${text}`
    );
    event.target.value = "";
  };

  const summary = status.summary || {};
  const route = status.goal_route || {};
  const plan = route.plan || {};
  const safeCode = status.safe_code_status || {};
  const tests = status.tests || {};
  const desktop = status.desktop_run_flow || {};
  const desktopController = desktop.local_desktop_controller || {};
  const productAudit = status.finished_product_audit || {};
  const clientJob = status.client_job || {};
  const capabilityForge = status.capability_forge || clientJob.capability_forge || {};
  const qualityReport = status.artifact_quality_report || clientJob.artifact_quality_report || capabilityForge.artifact_quality_report || {};
  const stressAudit = status.capability_stress_audit || {};
  const stressSummary = stressAudit.summary || {};
  const stressCases = Array.isArray(stressAudit.cases) ? stressAudit.cases : [];
  const complexStress = status.complex_build_stress_audit || {};
  const complexSummary = complexStress.summary || {};
  const complexCases = Array.isArray(complexStress.cases) ? complexStress.cases : [];
  const selfFix = status.autonomous_self_fix_director || {};
  const selfFixSummary = selfFix.summary || {};
  const selfFixSwot = selfFix.swot || {};
  const selfFixBacklog = Array.isArray(selfFix.repair_backlog) ? selfFix.repair_backlog : [];
  const selfFixSelectedRepairs = Array.isArray(selfFix.selected_repairs) ? selfFix.selected_repairs : [];
  const selfFixPatchEvidence = Array.isArray(selfFix.patch_apply_evidence) ? selfFix.patch_apply_evidence : [];
  const selfFixSnags = Array.isArray(selfFix.snags) ? selfFix.snags : [];
  const selfFixCodexAudit = selfFix.codex_audit_state || {};
  const selfRun = status.autonomous_self_run_loop || {};
  const selfRunSummary = selfRun.summary || {};
  const selfRunHeartbeat = selfRun.heartbeat || {};
  const selfRunCycles = Array.isArray(selfRun.cycles) ? selfRun.cycles : [];
  const selfRunLatest = selfRunCycles.length ? selfRunCycles[selfRunCycles.length - 1] : {};
  const selfRunTasks = Array.isArray(selfRunLatest.tasks) ? selfRunLatest.tasks : [];
  const selfRunWorkOrders = Array.isArray(selfRun.autonomous_work_orders) ? selfRun.autonomous_work_orders : [];
  const selfRunHardHolds = Array.isArray(selfRun.hard_boundary_holds) ? selfRun.hard_boundary_holds : [];
  const autonomousJobs = status.autonomous_job_executor || {};
  const autonomousJobsSummary = autonomousJobs.summary || {};
  const autonomousJobList = Array.isArray(autonomousJobs.jobs)
    ? autonomousJobs.jobs
    : Array.isArray(autonomousJobs.recent_jobs)
      ? autonomousJobs.recent_jobs
      : [];
  const autonomousActiveJob = autonomousJobs.active_job || autonomousJobs.current_job || {};
  const autonomousRecentJobs = autonomousJobList.slice(-5).reverse();
  const autonomousProof = Array.isArray(autonomousActiveJob.proof_checklist) ? autonomousActiveJob.proof_checklist : [];
  const evolutionQueueCertification = status.evolution_queue_autonomous_certification || {};
  const evolutionQueueCertificationSummary = evolutionQueueCertification.summary || {};
  const evolutionQueueCertificationCases = Array.isArray(evolutionQueueCertification.cases)
    ? evolutionQueueCertification.cases
    : Array.isArray(evolutionQueueCertification.sample_cases)
      ? evolutionQueueCertification.sample_cases
      : [];
  const workOrderExecution = status.frontend_work_order_execution || {};
  const workOrderExecutionSummary = workOrderExecution.summary || {};
  const workOrderMovement = workOrderExecution.queue_movement || {};
  const workOrderValidation = workOrderExecution.validation_summary || {};
  const runtimePatchRegistry = status.frontend_runtime_patch_registry || workOrderExecution.runtime_patch_registry || {};
  const runtimePatchSummary = runtimePatchRegistry.summary || {};
  const runtimePatches = Array.isArray(runtimePatchRegistry.patches) ? runtimePatchRegistry.patches : [];
  const materializedPatchCount = AUREON_EVOLUTION_RUNTIME_PATCHES.length;
  const materializedActivePatchCount = aureonEvolutionActivePatchCount();
  const codingCapability = status.coding_capability_unblocker || clientJob.coding_capability_unblocker || {};
  const codingCapabilitySummary = codingCapability.summary || {};
  const codingGates = Array.isArray(codingCapability.autonomous_gates) ? codingCapability.autonomous_gates : [];
  const codingWorkOrders = Array.isArray(codingCapability.autonomous_work_orders) ? codingCapability.autonomous_work_orders : [];
  const sourceRoutes = Array.isArray(codingCapability.source_discovery_routes) ? codingCapability.source_discovery_routes : [];
  const creativeGuardian = status.creative_process_guardian || clientJob.creative_process_guardian || {};
  const creativeSummary = creativeGuardian.summary || {};
  const creativeMind = creativeGuardian.organism_mind_contract || {};
  const creativeSources = Array.isArray(creativeMind.source_contracts) ? creativeMind.source_contracts : [];
  const creativeLoop = Array.isArray(creativeGuardian.creative_process_loop) ? creativeGuardian.creative_process_loop : [];
  const creativeRoleMap = Array.isArray(creativeGuardian.agent_creative_process_map) ? creativeGuardian.agent_creative_process_map : [];
  const creativeSnags = Array.isArray(creativeGuardian.snagging_list) ? creativeGuardian.snagging_list : [];
  const qualityChecks = Array.isArray(qualityReport.checks) ? qualityReport.checks : [];
  const qualitySnags = Array.isArray(qualityReport.snags) ? qualityReport.snags : [];
  const adaptiveSkill = (capabilityForge.adaptive_skill_evidence || capabilityForge.adaptive_skill_report?.adaptive_skill || {}) as JsonMap;
  const fullStackSystem = capabilityForge.full_stack_system_report || {};
  const fullStackManifest = fullStackSystem.artifact_manifest || {};
  const fullStackValidation = fullStackSystem.validation || {};
  const fullStackFlow = Array.isArray(fullStackSystem.agent_build_flow) ? fullStackSystem.agent_build_flow : [];
  const approvalState = capabilityForge.approval_state?.state || clientJob.approval_state?.state || qualityReport.approval_state?.state || "forge_unavailable";
  const scopeOfWorks = clientJob.scope_of_works || {};
  const clientQuestions = Array.isArray(clientJob.client_questions) ? clientJob.client_questions : [];
  const agentTeam = Array.isArray(clientJob.agent_team) ? clientJob.agent_team : [];
  const phaseTimers = Array.isArray(clientJob.phase_timers) ? clientJob.phase_timers : [];
  const proofChecklist = Array.isArray(clientJob.proof_checklist) ? clientJob.proof_checklist : productAudit.proof_checklist || [];
  const snaggingList = Array.isArray(clientJob.snagging_list) ? clientJob.snagging_list : productAudit.snagging_list || [];
  const handoverStatus = clientJob.handover_status || productAudit.handover_status || {};
  const finalHandoverVisible = Boolean(handoverStatus.client_visible_product || productAudit.ready_to_run);
  const journal = status.work_journal || {};
  const journalStages = Array.isArray(journal.stages) ? journal.stages : [];
  const steps = Array.isArray(plan.steps) ? plan.steps : [];
  const statusReceiptCurrent = consoleReceiptCurrent(statusReceivedAt, now) && !error;
  const gatewayReceiptCurrent = consoleReceiptCurrent(gatewayReceivedAt, now) && !cloudStatusError;
  const phiReceiptCurrent = consoleReceiptCurrent(phiReceivedAt, now);
  const ollamaReceiptCurrent = consoleReceiptCurrent(ollamaReceivedAt, now);
  const codingServiceCommissioned = cloudStatus.available === true && cloudStatus.commissioned === true;
  const codingControlAvailable =
    codingServiceCommissioned &&
    cloudStatus.capabilities?.coding_prompt === true &&
    consoleControlAvailable(statusReceivedAt, busy, now);
  const phiControlAvailable =
    codingServiceCommissioned &&
    cloudStatus.capabilities?.phi_chat === true &&
    consoleControlAvailable(phiReceivedAt, chatBusy || reloadBusy, now);
  const hubActive = codingServiceCommissioned && statusReceiptCurrent;
  const recordedCodingReady = Boolean(summary.goal_route_clean && summary.tests_ok && summary.ready_to_run && summary.blocking_snag_count === 0);
  const phiBridge = phiReceiptCurrent ? phiStatus.phi_bridge || {} : {};
  const phiCadence = phiBridge.cadence || {};
  const phiReady = phiReceiptCurrent && phiStatus.ok === true;
  const ollamaBridge = ollamaReceiptCurrent ? ollamaStatus : {};
  const ollamaSummary = ollamaBridge.summary || {};
  const ollamaModel = ollamaSummary.resolved_model || ollamaBridge.model_resolution?.resolved_model || ollamaBridge.model_resolution?.configured_model || "model waiting";
  const ollamaChecks = Array.isArray(ollamaBridge.proof_checklist) ? ollamaBridge.proof_checklist : [];
  const ollamaFlow = Array.isArray(ollamaBridge.handshake_flow) ? ollamaBridge.handshake_flow : [];
  const ollamaActions = Array.isArray(ollamaBridge.next_actions) ? ollamaBridge.next_actions : [];
  const liveRefreshMs = Number(cloudStatus.refresh_interval_ms || LIVE_REFRESH_FALLBACK_MS);
  const lastAssistant = [...chatMessages].reverse().find((item) => item.role === "assistant");
  const dynamicFilterState = (lastAssistant?.dynamic_filter || phiStatus.dynamic_prompt_filter || status.dynamic_prompt_filter || {}) as JsonMap;
  const dynamicSourcePackets = Array.isArray(dynamicFilterState.source_packets) ? dynamicFilterState.source_packets : [];
  const dynamicHncAuris = dynamicFilterState.hnc_auris_report || {};
  const dynamicAuris = dynamicHncAuris.auris_voice_filter || {};
  const dynamicFilterReady = Boolean(dynamicFilterState.filter_mode || dynamicFilterState.lane || dynamicSourcePackets.length);
  const artifactItems = collectArtifacts(status);

  return (
    <div className="space-y-5">
    <GlassPageHeader eyebrow="Coding System" title="Coding organism" icon={Code2}
      description="Prompt and chat workspaces, scoped jobs, test receipts and recorded artifact evidence."
      actions={<Badge variant={gatewayReceiptCurrent ? "success" : "warning"}>Owner route {gatewayReceiptCurrent ? "reachable" : "unavailable"}</Badge>} />
    <Card className="mb-5 bg-card/80">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-base">
          <Code2 className="h-4 w-4 text-primary" />
          Aureon Coding Organism
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="text-xs text-muted-foreground">
          Authenticated owner route: {gatewayReceiptCurrent ? "current" : "unavailable or expired"} · Coding worker: {codingServiceCommissioned ? "commissioned" : "not commissioned"} · Phi worker: {phiReceiptCurrent ? "current" : "not commissioned"}. No recorded JSON is treated as a live worker receipt.
        </p>
        {cloudStatusError ? <div className="rounded-md border border-destructive/30 bg-destructive/10 p-2 text-xs text-destructive">{cloudStatusError}</div> : null}
        <div className="flex flex-wrap gap-2">
          <Badge variant={codingServiceCommissioned && status.ok ? "success" : "warning"}>{status.status || cloudStatus.status || "coding status unavailable"}</Badge>
          <Badge variant="outline">Recorded source {status.generated_at ? new Date(status.generated_at).toLocaleString() : "Unavailable"}</Badge>
          <Badge variant={summary.goal_engine_routed ? "success" : "warning"}>recorded goal route {summary.goal_engine_routed ? "routed" : "unavailable"}</Badge>
          <Badge variant={summary.scope_locked ? "success" : "warning"}>scope {String(summary.scope_status || "scope unavailable").replace(/_/g, " ")}</Badge>
          <Badge variant={summary.safe_code_proposal_created ? "success" : "outline"}>code queue {summary.safe_code_proposal_created ? "written" : "not published"}</Badge>
          <Badge variant={summary.tests_ok ? "success" : summary.tests_requested ? "warning" : "outline"}>tests {summary.tests_requested ? (summary.tests_ok ? "passed" : "attention") : "off"}</Badge>
          <Badge variant={summary.ready_to_run ? "success" : "warning"}>product {String(summary.finished_product_status || "audit pending").replace(/_/g, " ")}</Badge>
          <Badge variant={summary.blocking_snag_count === 0 ? "success" : "warning"}>recorded snags {fmt(summary.blocking_snag_count)}</Badge>
          <Badge variant={summary.desktop_handoff_created ? "success" : "outline"}>desktop handoff {summary.desktop_handoff_created ? "ready" : "off"}</Badge>
          <Badge variant={summary.artifact_quality_passed ? "success" : summary.artifact_quality_gate_present ? "warning" : "outline"}>
            quality {summary.artifact_quality_gate_present ? `${Math.round(Number(summary.artifact_quality_score || 0) * 100)}%` : "unavailable"}
          </Badge>
          <Badge variant={summary.creative_process_guardian_ok || creativeGuardian.ok ? "success" : creativeGuardian.schema_version ? "warning" : "outline"}>
            mind guard {summary.creative_process_guardian_ok || creativeGuardian.ok ? "passed" : creativeGuardian.schema_version ? "attention" : "unavailable"}
          </Badge>
          <Badge variant={codingCapability.ok ? "success" : codingCapability.schema_version ? "warning" : "outline"}>
            coding gates {fmt(codingCapabilitySummary.ready_gate_count)}/{fmt(codingCapabilitySummary.gate_count)}
          </Badge>
        </div>

        <div className="rounded-md border border-primary/30 bg-primary/10 p-3">
          <div className="mb-3 flex flex-wrap items-start justify-between gap-2">
            <div>
              <div className="text-sm font-medium text-primary">Human Coding Cockpit</div>
              <div className="mt-1 text-xs text-primary/75">
                This cloud cockpit reaches the owner-authenticated operator plane over the current website origin. Prompt and repo-changing actions remain unavailable until a separately reviewed coding worker is commissioned.
              </div>
            </div>
            <div className="flex flex-wrap gap-2">
              <Badge variant="outline">Job evidence: {hasPayload(status) ? "recorded" : "unavailable"}</Badge>
              <Badge variant={hubActive ? "success" : "warning"}>worker {hubActive ? "reachable" : "not commissioned"}</Badge>
              <Badge variant="outline">Recorded handover {recordedCodingReady ? "ready" : "gated or unavailable"}</Badge>
            </div>
          </div>
          <div className="grid grid-cols-1 gap-2 text-xs md:grid-cols-3">
            <div>
              <div className="uppercase text-primary/70">Owner route</div>
              <div className="mt-1 font-mono text-primary">GET {CODING_STATUS_PATH}</div>
            </div>
            <div>
              <div className="uppercase text-primary/70">Worker state</div>
              <div className="mt-1 font-mono text-primary">{cloudStatus.reason_code || "status route unavailable"}</div>
            </div>
            <div>
              <div className="uppercase text-primary/70">Authority</div>
              <div className="mt-1 font-mono text-primary">read-only · owner only · no proxy or repo mutation</div>
            </div>
          </div>
        </div>

        {codingServiceCommissioned ? (
          <>
        <div className="rounded-md border border-primary/30 bg-primary/10 p-3">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="flex items-start gap-2">
              <MessageSquare className="mt-0.5 h-4 w-4 text-primary" />
              <div>
                <div className="text-sm font-medium text-primary">Aureon Phi Live Chat</div>
                <div className="mt-1 text-xs text-primary/75">
                  This lane activates only after the cloud coding worker publishes a current commissioned receipt.
                </div>
              </div>
            </div>
            <div className="flex flex-wrap gap-2">
              <Badge variant={phiReady ? "success" : "warning"}>phi {phiReady ? "reachable" : "unavailable"}</Badge>
              <Badge variant="outline">
                <Radio className="mr-1 h-3 w-3" />
                {typeof phiCadence.frequency_hz === "number" && Number.isFinite(phiCadence.frequency_hz) ? `${phiCadence.frequency_hz.toFixed(2)} Hz reported cadence` : "Cadence unavailable"}
              </Badge>
              <Badge variant="outline">
                <RefreshCw className="mr-1 h-3 w-3" />
                {fmt(liveRefreshMs)}ms
              </Badge>
              <Badge variant={lastAssistant?.source === "local_llm" || lastAssistant?.source === "ollama_cognitive_hybrid" || lastAssistant?.source === "ollama_cognitive_weaver" ? "success" : "outline"}>
                {lastAssistant?.source || phiStatus.chat?.adapter_model || "voice lane"}
              </Badge>
              <Badge variant={dynamicFilterReady ? "success" : "outline"}>
                filter {dynamicFilterState.filter_mode || "unavailable"}
              </Badge>
              <Badge variant={dynamicSourcePackets.length ? "success" : "outline"}>
                {dynamicSourcePackets.length || 0} source packets
              </Badge>
            </div>
          </div>

          <div className="overflow-y-auto min-w-0 mt-3 h-[180px] rounded-md border border-primary/20 bg-background/25 p-3 pr-4">
            <div className="space-y-2">
              {chatMessages.map((message, index) => (
                <div
                  key={`${message.ts || index}-${message.role}`}
                  className={`rounded-md border px-3 py-2 text-xs ${
                    message.role === "assistant"
                      ? "border-primary/30 bg-primary/10 text-primary"
                      : "border-primary/25 bg-primary/10 text-primary"
                  }`}
                >
                  <div className="mb-1 flex items-center justify-between gap-2 text-[10px] uppercase opacity-75">
                    <span>{message.role === "assistant" ? "Aureon" : "Operator"}</span>
                    <span>{message.latency_ms ? `${fmt(message.latency_ms)}ms` : message.source || ""}</span>
                  </div>
                  <div className="whitespace-pre-wrap leading-relaxed">{message.text}</div>
                  {message.weaver?.shards?.length ? (
                    <div className="mt-2 flex flex-wrap gap-1 text-[10px] text-primary/70">
                      {message.weaver.shards.map((shard) => (
                        <Badge key={`${message.ts}-${shard.name}`} variant={shard.ok ? "success" : "warning"}>
                          {String(shard.name || "shard").replace(/_/g, " ")}
                        </Badge>
                      ))}
                    </div>
                  ) : null}
                  {message.dynamic_filter ? (
                    <div className="mt-2 flex flex-wrap gap-1 text-[10px] text-primary/70">
                      <Badge variant="outline">{message.dynamic_filter.lane || "chat"}</Badge>
                      <Badge variant="outline">{message.dynamic_filter.task_family || "conversation"}</Badge>
                      {(message.dynamic_filter.source_packets || []).slice(0, 3).map((packet) => (
                        <Badge key={`${message.ts}-${packet.source_path}`} variant="outline">
                          {packet.title || packet.source_path || "source"}
                        </Badge>
                      ))}
                    </div>
                  ) : null}
                  {message.response_quality ? (
                    <div className="mt-2 flex flex-wrap gap-1 text-[10px] text-primary/70">
                      <Badge variant={message.response_quality.passed ? "success" : "warning"}>
                        quality {typeof message.response_quality.score === "number" && Number.isFinite(message.response_quality.score) ? `${Math.round(message.response_quality.score * 100)}%` : "Unavailable"}
                      </Badge>
                      {message.response_quality.compiler_applied ? <Badge variant="outline">operator compiled</Badge> : null}
                      {(message.response_quality.snags || []).slice(0, 2).map((snag) => (
                        <Badge key={`${message.ts}-${snag}`} variant="warning">
                          {snag.replace(/_/g, " ")}
                        </Badge>
                      ))}
                    </div>
                  ) : null}
                </div>
              ))}
              {!chatMessages.length ? (
                <div className="rounded-md border border-primary/20 bg-background/20 p-3 text-xs text-primary/75">
                  {codingServiceCommissioned ? "The commissioned chat lane is waiting for your first live message." : "Chat is unavailable because the cloud coding worker is not commissioned."}
                </div>
              ) : null}
            </div>
          </div>

          <div className="mt-3 grid grid-cols-1 gap-2 md:grid-cols-4">
            <Mini label="Prompt Filter" value={dynamicFilterState.filter_mode || "unavailable"} />
            <Mini label="Lane" value={dynamicFilterState.lane || "chat"} />
            <Mini label="Packets" value={dynamicSourcePackets.length} />
            <Mini label="Auris" value={dynamicAuris.accepted === false ? "hold" : dynamicAuris.accepted ? "pass" : "pending"} />
          </div>
          {dynamicSourcePackets.length ? (
            <div className="mt-2 flex flex-wrap gap-1 text-[10px] text-primary/75">
              {dynamicSourcePackets.slice(0, 4).map((packet: JsonMap) => (
                <Badge key={packet.source_path || packet.title} variant="outline">
                  {packet.title || packet.source_path}
                </Badge>
              ))}
            </div>
          ) : null}

          <div className="mt-3 grid grid-cols-1 gap-2 md:grid-cols-[1fr_auto]">
            <Textarea
              data-testid="phi-chat-input"
              aria-label="Phi chat message"
              value={chatInput}
              disabled={!phiControlAvailable}
              onChange={(event) => setChatInput(event.target.value)}
              onKeyDown={(event) => {
                if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
                  event.preventDefault();
                  sendPhiChat();
                }
              }}
              className="min-h-[72px] bg-background/60 text-xs"
            />
            <Button
              data-testid="phi-chat-submit"
              type="button"
              className="md:self-end"
              size="sm"
              onClick={sendPhiChat}
              disabled={!phiControlAvailable || !chatInput.trim()}
            >
              <Send className="mr-2 h-4 w-4" />
              Talk To Aureon
            </Button>
          </div>
          {chatError ? <div className="mt-2 rounded-md border border-destructive/30 bg-destructive/10 p-2 text-xs text-destructive">{chatError}</div> : null}
        </div>

        <div className="rounded-md border border-primary/30 bg-primary/10 p-3">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="flex items-start gap-2">
              <BrainCircuit className="mt-0.5 h-4 w-4 text-primary" />
              <div>
                <div className="text-sm font-medium text-primary">Ollama Cognitive Handshake</div>
                <div className="mt-1 text-xs text-primary/75">
                  Ollama readiness is reported only by a commissioned cloud coding worker; provider configuration alone does not make this lane live.
                </div>
              </div>
            </div>
            <div className="flex flex-wrap gap-2">
              <Badge variant={ollamaSummary.ollama_reachable ? "success" : "warning"}>
                Ollama {ollamaSummary.ollama_reachable ? "reachable" : "not commissioned"}
              </Badge>
              <Badge variant={ollamaBridge.ok ? "success" : "warning"}>
                {ollamaBridge.status || "handshake waiting"}
              </Badge>
              <Badge variant={ollamaSummary.hnc_auris_ready ? "success" : "warning"}>
                HNC/Auris {ollamaSummary.hnc_auris_ready ? "ready" : "held"}
              </Badge>
              <Badge variant={ollamaSummary.metacognitive_ready ? "success" : "warning"}>
                cognition {ollamaSummary.metacognitive_ready ? "ready" : "held"}
              </Badge>
              <Button size="sm" variant="outline" onClick={reloadPhiVoiceWorker} disabled={!phiControlAvailable}>
                <RefreshCw className="mr-2 h-4 w-4" />
                {reloadBusy ? "Reloading…" : "Reload Voice Worker"}
              </Button>
            </div>
          </div>

          <div className="mt-3 grid grid-cols-1 gap-2 md:grid-cols-5">
            <Mini label="Model" value={ollamaModel} />
            <Mini label="Installed" value={ollamaSummary.installed_model_count} />
            <Mini label="Running" value={ollamaSummary.running_model_count} />
            <Mini label="Sources" value={ollamaBridge.cognitive_readiness?.cognitive_source_count} />
            <Mini label="Blockers" value={ollamaSummary.blocking_check_count} />
          </div>

          <div className="mt-3 grid grid-cols-1 gap-3 lg:grid-cols-3">
            <div className="rounded-md border border-primary/25 bg-background/25 p-3">
              <div className="mb-2 text-xs font-medium text-primary">Handshake Proof</div>
              <div className="space-y-1">
                {ollamaChecks.slice(0, 8).map((check: JsonMap) => (
                  <div key={check.id} className="flex items-center justify-between gap-2 rounded border border-primary/20 bg-background/20 px-2 py-1 text-[11px]">
                    <span>{check.label || check.id}</span>
                    <Badge variant={check.ok ? "success" : check.blocking ? "warning" : "outline"}>{check.ok ? "pass" : "hold"}</Badge>
                  </div>
                ))}
                {!ollamaChecks.length ? <div className="text-xs text-primary/70">Ollama proof appears after the bridge report or live hub endpoint responds.</div> : null}
              </div>
            </div>
            <div className="rounded-md border border-primary/25 bg-background/25 p-3">
              <div className="mb-2 text-xs font-medium text-primary">Agent-Like Flow</div>
              <div className="space-y-1">
                {ollamaFlow.slice(0, 5).map((step: JsonMap) => (
                  <div key={step.step} className="rounded border border-primary/20 bg-background/20 px-2 py-1 text-[11px]">
                    <div className="font-medium">{String(step.step || "").replace(/_/g, " ")}</div>
                    <div className="mt-1 text-primary/70">{step.owner}</div>
                  </div>
                ))}
                {!ollamaFlow.length ? <div className="text-xs text-primary/70">Handshake flow unavailable until the Ollama cognitive bridge report is present.</div> : null}
              </div>
            </div>
            <div className="rounded-md border border-primary/25 bg-background/25 p-3">
              <div className="mb-2 text-xs font-medium text-primary">Setup / Repair Actions</div>
              <div className="space-y-1">
                {ollamaActions.slice(0, 4).map((action: JsonMap) => (
                  <div key={action.id} className="rounded border border-primary/20 bg-background/20 px-2 py-1 text-[11px]">
                    <div className="font-medium">{action.action || action.id}</div>
                    {action.powershell ? <div className="mt-1 font-mono text-primary/70">{action.powershell}</div> : null}
                  </div>
                ))}
                {!ollamaActions.length ? <div className="text-xs text-primary/70">No repair actions are currently published.</div> : null}
              </div>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 gap-2 md:grid-cols-6">
          <Stat icon={BrainCircuit} label="plan steps" value={plan.step_count || summary.target_file_count || 0} />
          <Stat icon={ShieldCheck} label="pending proposals" value={safeCode.pending_count || summary.pending_code_proposal_count || 0} />
          <Stat icon={Code2} label="target files" value={summary.target_file_count} />
          <Stat icon={TestTube2} label="test commands" value={tests.command_count} />
          <Stat icon={MousePointer2} label="VM tools" value={summary.remote_vm_tool_count} />
          <Stat icon={CheckCircle2} label="route ok" value={route.ok ? "yes" : "no"} />
        </div>

        <div className="rounded-md border border-primary/30 bg-primary/10 p-3">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <div className="text-sm font-medium text-primary">Autonomous Self-Run Loop</div>
              <div className="mt-1 text-xs text-primary/75">
                The coding organism wakes its gates, creative process, stress certification, and self-fix director without depending on Codex when work stays inside safe local authority.
              </div>
            </div>
            <div className="flex flex-wrap gap-2">
              <Badge variant={selfRunSummary.loop_active ? "success" : selfRun.schema_version ? "warning" : "outline"}>
                {selfRun.status || "self-run waiting"}
              </Badge>
              <Badge variant={selfRunSummary.handover_ready ? "success" : selfRun.schema_version ? "warning" : "outline"}>
                autonomous {selfRunSummary.loop_active ? "active" : "held"}
              </Badge>
              <Badge variant={Number(selfRunSummary.hard_boundary_hold_count || 0) ? "warning" : "success"}>
                hard holds {selfRunSummary.hard_boundary_hold_count || 0}
              </Badge>
              <Badge variant="outline">cycles {selfRunSummary.cycle_count || 0}</Badge>
            </div>
          </div>
          <div className="mt-3 grid grid-cols-1 gap-2 md:grid-cols-5">
            <Mini label="Tasks" value={`${selfRunSummary.latest_task_ok_count || 0}/${selfRunSummary.latest_task_count || 0}`} />
            <Mini label="Critical failures" value={selfRunSummary.critical_failure_count} />
            <Mini label="Soft failures" value={selfRunSummary.soft_failure_count} />
            <Mini label="Work orders" value={selfRunSummary.autonomous_work_order_count} />
            <Mini label="Heartbeat" value={selfRunHeartbeat.status || selfRunSummary.heartbeat_status || "unavailable"} />
          </div>
          <div className="mt-3 grid grid-cols-1 gap-3 lg:grid-cols-3">
            <div className="rounded-md border border-primary/25 bg-background/25 p-3">
              <div className="mb-2 text-xs font-medium text-primary">Latest Cycle Tasks</div>
              <div className="space-y-1">
                {selfRunTasks.slice(0, 6).map((task: JsonMap) => (
                  <div key={task.id} className="rounded border border-primary/20 bg-background/20 px-2 py-1 text-[11px] text-primary/80">
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-medium">{String(task.title || task.id).replace(/_/g, " ")}</span>
                      <Badge variant={task.ok ? "success" : task.critical ? "warning" : "outline"}>{task.status || "unavailable"}</Badge>
                    </div>
                    <div className="mt-1 text-primary/70">
                      {task.authority || "safe local"} | {task.duration_ms || 0}ms
                    </div>
                  </div>
                ))}
                {!selfRunTasks.length ? <div className="text-xs text-primary/70">Run the self-run loop to publish autonomous cycle evidence.</div> : null}
              </div>
            </div>
            <div className="rounded-md border border-primary/25 bg-background/25 p-3">
              <div className="mb-2 text-xs font-medium text-primary">Autonomous Next Work</div>
              <div className="space-y-1">
                {selfRunWorkOrders.slice(0, 5).map((order: JsonMap) => (
                  <div key={order.id} className="rounded border border-primary/20 bg-background/20 px-2 py-1 text-[11px] text-primary/80">
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-medium">{String(order.title || order.id).replace(/_/g, " ")}</span>
                      <Badge variant={order.autonomous ? "success" : "warning"}>{order.priority || "P1"}</Badge>
                    </div>
                    <div className="mt-1 text-primary/70">{order.next_action}</div>
                  </div>
                ))}
                {!selfRunWorkOrders.length ? <div className="text-xs text-primary/70">No autonomous repair work is waiting in the latest cycle.</div> : null}
              </div>
            </div>
            <div className="rounded-md border border-primary/25 bg-background/25 p-3">
              <div className="mb-2 text-xs font-medium text-primary">Authority Boundary</div>
              <div className="space-y-1">
                {selfRunHeartbeat.status ? (
                  <div className="rounded border border-primary/20 bg-background/20 px-2 py-1 text-[11px] text-primary/80">
                    <div className="font-medium">heartbeat {selfRunHeartbeat.status}</div>
                    <div className="mt-1">
                      due {selfRunHeartbeat.next_cycle_due_seconds ?? 0}s | stale after {selfRunHeartbeat.stale_after_seconds ?? 0}s
                    </div>
                  </div>
                ) : null}
                {selfRunHardHolds.slice(0, 5).map((hold: JsonMap) => (
                  <div key={hold.id} className="rounded border border-warning/30 bg-warning/10 px-2 py-1 text-[11px] text-warning">
                    <div className="font-medium">{String(hold.id || "manual hold").replace(/_/g, " ")}</div>
                    <div className="mt-1">{hold.reason}</div>
                  </div>
                ))}
                {!selfRunHardHolds.length ? (
                  <div className="rounded border border-primary/20 bg-background/20 px-2 py-1 text-[11px] text-primary/80">
                    No hard boundary is holding the safe local coding lane.
                  </div>
                ) : null}
              </div>
            </div>
          </div>
        </div>

        <div className="rounded-md border border-primary/30 bg-primary/10 p-3">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <div className="text-sm font-medium text-primary">Autonomous Job Executor</div>
              <div className="mt-1 text-xs text-primary/75">
                Every human coding, UI, media, or tool prompt becomes a durable job that can be claimed, built, tested, repaired, and handed over when proof passes.
              </div>
            </div>
            <div className="flex flex-wrap gap-2">
              <Badge variant={autonomousJobs.ok ? "success" : autonomousJobs.schema_version ? "warning" : "outline"}>
                {autonomousJobs.status || "jobs waiting"}
              </Badge>
              <Badge variant={Number(autonomousJobsSummary.queue_depth || 0) ? "warning" : "outline"}>
                Queue depth {autonomousJobsSummary.queue_depth || 0}
              </Badge>
              <Badge variant={autonomousActiveJob.state === "handover_ready" ? "success" : autonomousActiveJob.state ? "warning" : "outline"}>
                active {autonomousActiveJob.state || "none"}
              </Badge>
              <Badge variant="outline">handover {autonomousJobsSummary.handover_ready_count || 0}</Badge>
            </div>
          </div>
          <div className="mt-3 grid grid-cols-1 gap-2 md:grid-cols-5">
            <Mini label="Jobs" value={autonomousJobsSummary.job_count || autonomousJobList.length || 0} />
            <Mini label="Queue depth" value={autonomousJobsSummary.queue_depth} />
            <Mini label="Active" value={autonomousJobsSummary.active_job_count || (autonomousActiveJob.job_id ? 1 : 0)} />
            <Mini label="Manual holds" value={autonomousJobsSummary.manual_hold_count} />
            <Mini label="Failed budget" value={autonomousJobsSummary.failed_after_budget_count} />
          </div>
          <div className="mt-3 grid grid-cols-1 gap-3 lg:grid-cols-3">
            <div className="rounded-md border border-primary/25 bg-background/25 p-3">
              <div className="mb-2 text-xs font-medium text-primary">Active Job</div>
              {autonomousActiveJob.job_id ? (
                <div className="rounded border border-primary/20 bg-background/20 px-2 py-1 text-[11px] text-primary/80">
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-medium">{autonomousActiveJob.job_id}</span>
                    <Badge variant={autonomousActiveJob.handover_ready ? "success" : "warning"}>{autonomousActiveJob.state || "active"}</Badge>
                  </div>
                  <div className="mt-1 text-primary/70">{String(autonomousActiveJob.prompt || "").slice(0, 140)}</div>
                  <div className="mt-1 text-primary/70">
                    phase {autonomousActiveJob.phase || "unavailable"} | attempts {autonomousActiveJob.attempts || 0}/{autonomousActiveJob.attempt_budget || 0}
                  </div>
                  {autonomousActiveJob.handover?.public_url ? (
                    <a className="mt-2 block text-primary underline" href={String(autonomousActiveJob.handover.public_url)}>
                      Open handover artifact
                    </a>
                  ) : null}
                </div>
              ) : (
                <div className="text-xs text-primary/70">No active job is currently claimed by the worker.</div>
              )}
            </div>
            <div className="rounded-md border border-primary/25 bg-background/25 p-3">
              <div className="mb-2 text-xs font-medium text-primary">Proof Checklist</div>
              <div className="space-y-1">
                {autonomousProof.slice(0, 6).map((check: JsonMap) => (
                  <div key={check.id} className="rounded border border-primary/20 bg-background/20 px-2 py-1 text-[11px] text-primary/80">
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-medium">{String(check.id || "proof").replace(/_/g, " ")}</span>
                      <Badge variant={check.ok ? "success" : "warning"}>{check.ok ? "pass" : "hold"}</Badge>
                    </div>
                    <div className="mt-1 text-primary/70">{check.evidence || "waiting for proof"}</div>
                  </div>
                ))}
                {!autonomousProof.length ? <div className="text-xs text-primary/70">Proof appears after a job reaches the build and test phases.</div> : null}
              </div>
            </div>
            <div className="rounded-md border border-primary/25 bg-background/25 p-3">
              <div className="mb-2 text-xs font-medium text-primary">Recent Jobs</div>
              <div className="space-y-1">
                {autonomousRecentJobs.map((job: JsonMap) => (
                  <div key={job.job_id} className="rounded border border-primary/20 bg-background/20 px-2 py-1 text-[11px] text-primary/80">
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-medium">{job.job_id}</span>
                      <Badge variant={job.state === "handover_ready" ? "success" : job.state === "held_manual_boundary" ? "warning" : "outline"}>{job.state || "unavailable"}</Badge>
                    </div>
                    <div className="mt-1 text-primary/70">{String(job.prompt || "").slice(0, 110)}</div>
                  </div>
                ))}
                {!autonomousRecentJobs.length ? <div className="text-xs text-primary/70">Submit a cockpit prompt to create the first durable autonomous job.</div> : null}
              </div>
            </div>
          </div>
        </div>

        <div className="rounded-md border border-primary/30 bg-primary/10 p-3">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <div className="text-sm font-medium text-primary">Evolution Queue 584 Certification</div>
              <div className="mt-1 text-xs text-primary/75">
                The real throughput test: Aureon reads every frontend evolution work order, assigns a safe autonomous outcome, proves the data contract, and records true boundaries without stopping the coding lane.
              </div>
            </div>
            <div className="flex flex-wrap gap-2">
              <Badge variant={evolutionQueueCertification.ok ? "success" : evolutionQueueCertification.schema_version ? "warning" : "outline"}>
                {evolutionQueueCertification.status || "certification waiting"}
              </Badge>
              <Badge variant={Number(evolutionQueueCertificationSummary.fake_pass_count || 0) ? "warning" : "success"}>
                fake passes {evolutionQueueCertificationSummary.fake_pass_count || 0}
              </Badge>
              <Badge variant="outline">
                processed {evolutionQueueCertificationSummary.processed_count || 0}/{evolutionQueueCertificationSummary.queue_count || 0}
              </Badge>
            </div>
          </div>
          <div className="mt-3 grid grid-cols-1 gap-2 md:grid-cols-5">
            <Mini label="Throughput" value={`${evolutionQueueCertificationSummary.throughput_percent || 0}%`} />
            <Mini label="Autonomous outcomes" value={evolutionQueueCertificationSummary.safe_autonomous_outcome_count} />
            <Mini label="Read-only adapters" value={evolutionQueueCertificationSummary.read_only_adapter_count} />
            <Mini label="Blocker cards" value={evolutionQueueCertificationSummary.blocker_card_count} />
            <Mini label="Boundary visible" value={evolutionQueueCertificationSummary.manual_boundary_visible_count} />
          </div>
          <div className="mt-3 grid grid-cols-1 gap-3 lg:grid-cols-3">
            <div className="rounded-md border border-primary/25 bg-background/25 p-3">
              <div className="mb-2 text-xs font-medium text-primary">Outcome Buckets</div>
              <div className="space-y-1">
                {Object.entries(evolutionQueueCertificationSummary.outcome_buckets || {}).map(([bucket, count]) => (
                  <div key={bucket} className="flex items-center justify-between rounded border border-primary/20 bg-background/20 px-2 py-1 text-[11px] text-primary/80">
                    <span className="font-medium">{bucket.replace(/_/g, " ")}</span>
                    <Badge variant="outline">{String(count)}</Badge>
                  </div>
                ))}
                {!Object.keys(evolutionQueueCertificationSummary.outcome_buckets || {}).length ? (
                  <div className="text-xs text-primary/70">Run the evolution queue certification to publish all 584 outcomes.</div>
                ) : null}
              </div>
            </div>
            <div className="rounded-md border border-primary/25 bg-background/25 p-3 lg:col-span-2">
              <div className="mb-2 text-xs font-medium text-primary">Sample Work Order Proof</div>
              <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
                {evolutionQueueCertificationCases.slice(0, 6).map((item: JsonMap) => (
                  <div key={item.id} className="rounded border border-primary/20 bg-background/20 px-2 py-1 text-[11px] text-primary/80">
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-medium">{String(item.id || "work order").replace(/_/g, " ")}</span>
                      <Badge variant={item.ok ? "success" : "warning"}>{item.autonomous_outcome || "unavailable"}</Badge>
                    </div>
                    <div className="mt-1 text-primary/70">
                      {item.target_screen || "screen"} | {item.handover_state?.state || "handover waiting"}
                    </div>
                    <div className="mt-1 text-primary/60">{String(item.source_path || "").slice(0, 120)}</div>
                  </div>
                ))}
                {!evolutionQueueCertificationCases.length ? (
                  <div className="text-xs text-primary/70">No certified queue cases are published yet.</div>
                ) : null}
              </div>
            </div>
          </div>
        </div>

        <div className="rounded-md border border-primary/30 bg-primary/10 p-3">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <div className="text-sm font-medium text-primary">Live Queue Runtime Patches</div>
              <div className="mt-1 text-xs text-primary/75">
                Shows the queue moving into validated runtime patch records: each completed work order has validation proof and an active read-only patch entry.
              </div>
            </div>
            <div className="flex flex-wrap gap-2">
              <Badge variant={workOrderExecution.status ? "success" : "outline"}>{workOrderExecution.status || "execution waiting"}</Badge>
              <Badge variant={Number(workOrderExecutionSummary.remaining_queue_count || 0) ? "warning" : "success"}>
                remaining queue {workOrderExecutionSummary.remaining_queue_count ?? workOrderMovement.remaining_queue_count ?? 0}
              </Badge>
              <Badge variant={Number(workOrderExecutionSummary.failed_validation_count || 0) ? "warning" : "success"}>
                validation failures {workOrderExecutionSummary.failed_validation_count || workOrderValidation.failed_validation_count || 0}
              </Badge>
              <Badge variant="outline">code materialized {materializedPatchCount}</Badge>
            </div>
          </div>
          <div className="mt-3 grid grid-cols-1 gap-2 md:grid-cols-5">
            <Mini label="Moved from queue" value={workOrderExecutionSummary.moved_from_queue_count || workOrderMovement.moved_from_queue_count || 0} />
            <Mini label="Completed validated" value={workOrderMovement.completed_validated_count || workOrderExecutionSummary.validated_count || 0} />
            <Mini label="Active runtime patches" value={runtimePatchSummary.active_patch_count || workOrderExecutionSummary.runtime_patch_count || 0} />
            <Mini label="Patch registry" value={runtimePatchRegistry.status || workOrderExecutionSummary.runtime_patch_status || "unavailable"} />
            <Mini label="Queue drained" value={workOrderMovement.queue_drained ? "yes" : "no"} />
          </div>
          <div className="mt-3 grid grid-cols-1 gap-3 lg:grid-cols-3">
            <div className="rounded-md border border-primary/25 bg-background/25 p-3">
              <div className="mb-2 text-xs font-medium text-primary">Queue Movement</div>
              <div className="space-y-1 text-[11px] text-primary/80">
                <div className="flex items-center justify-between rounded border border-primary/20 bg-background/20 px-2 py-1">
                  <span>source queue</span>
                  <Badge variant="outline">{workOrderMovement.source_queue_count || workOrderExecutionSummary.source_queue_count || 0}</Badge>
                </div>
                <div className="flex items-center justify-between rounded border border-primary/20 bg-background/20 px-2 py-1">
                  <span>moved from queue</span>
                  <Badge variant="outline">{workOrderMovement.moved_from_queue_count || workOrderExecutionSummary.moved_from_queue_count || 0}</Badge>
                </div>
                <div className="flex items-center justify-between rounded border border-primary/20 bg-background/20 px-2 py-1">
                  <span>remaining queue</span>
                  <Badge variant={Number(workOrderMovement.remaining_queue_count || 0) ? "warning" : "outline"}>{workOrderMovement.remaining_queue_count ?? workOrderExecutionSummary.remaining_queue_count ?? 0}</Badge>
                </div>
              </div>
            </div>
            <div className="rounded-md border border-primary/25 bg-background/25 p-3">
              <div className="mb-2 text-xs font-medium text-primary">Materialized Repo Code</div>
              <div className="space-y-1 text-[11px] text-primary/80">
                <div className="flex items-center justify-between rounded border border-primary/20 bg-background/20 px-2 py-1">
                  <span>generated TS patches</span>
                  <Badge variant="outline">{materializedPatchCount}</Badge>
                </div>
                <div className="flex items-center justify-between rounded border border-primary/20 bg-background/20 px-2 py-1">
                  <span>active in code</span>
                  <Badge variant="outline">{materializedActivePatchCount}</Badge>
                </div>
                <div className="flex items-center justify-between rounded border border-primary/20 bg-background/20 px-2 py-1">
                  <span>module status</span>
                  <Badge variant="outline">{AUREON_EVOLUTION_RUNTIME_PATCH_SUMMARY.status}</Badge>
                </div>
                <div className="font-mono text-primary/65">
                  frontend/src/components/generated/aureonEvolutionRuntimePatches.ts
                </div>
              </div>
            </div>
            <div className="rounded-md border border-primary/25 bg-background/25 p-3 lg:col-span-2">
              <div className="mb-2 text-xs font-medium text-primary">Active Runtime Patches</div>
              <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
                {runtimePatches.slice(0, 6).map((patch: JsonMap) => (
                  <div key={patch.patch_id} className="rounded border border-primary/20 bg-background/20 px-2 py-1 text-[11px] text-primary/80">
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-medium">{String(patch.patch_type || "patch").replace(/_/g, " ")}</span>
                      <Badge variant={patch.active ? "success" : "warning"}>{patch.status || "unavailable"}</Badge>
                    </div>
                    <div className="mt-1 text-primary/70">{patch.target_screen || "screen"} | {String(patch.source_path || "").slice(0, 110)}</div>
                  </div>
                ))}
                {!runtimePatches.length ? <div className="text-xs text-primary/70">Run work-order execution to activate runtime patch records.</div> : null}
              </div>
            </div>
          </div>
        </div>

        <div className="rounded-md border border-success/30 bg-success/10 p-3">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <div className="text-sm font-medium text-success">Autonomous Coding Capability Gates</div>
              <div className="mt-1 text-xs text-success/75">
                Missing skills, tools, dependencies, tests, and source knowledge become autonomous gates; live trading, payments, filings, credentials, and destructive OS actions remain manual holds.
              </div>
            </div>
            <div className="flex flex-wrap gap-2">
              <Badge variant={codingCapability.ok ? "success" : codingCapability.schema_version ? "warning" : "outline"}>
                {codingCapability.status || "unblocker waiting"}
              </Badge>
              <Badge variant="outline">gates {fmt(codingCapabilitySummary.ready_gate_count)}/{fmt(codingCapabilitySummary.gate_count)}</Badge>
              <Badge variant={Number(codingCapabilitySummary.converted_coding_blocker_count || 0) ? "success" : "outline"}>
                converted {codingCapabilitySummary.converted_coding_blocker_count || 0}
              </Badge>
              <Badge variant={Number(codingCapabilitySummary.manual_authority_hold_count || 0) ? "warning" : "outline"}>
                manual holds {codingCapabilitySummary.manual_authority_hold_count || 0}
              </Badge>
            </div>
          </div>
          <div className="mt-3 grid grid-cols-1 gap-2 md:grid-cols-5">
            <Mini label="Work orders" value={codingCapabilitySummary.work_order_count} />
            <Mini label="Source packets" value={codingCapabilitySummary.source_packet_count} />
            <Mini label="Research routes" value={codingCapabilitySummary.external_research_routes_ready || sourceRoutes.length || 0} />
            <Mini label="Gate repairs" value={codingCapabilitySummary.gate_repair_count} />
            <Mini label="Policy" value={codingCapability.provider_policy || "local first"} />
          </div>
          <div className="mt-3 grid grid-cols-1 gap-2 lg:grid-cols-3">
            <div className="rounded-md border border-success/25 bg-background/25 p-3">
              <div className="mb-2 text-xs font-medium text-success">System Gates</div>
              <div className="space-y-1">
                {codingGates.slice(0, 9).map((gate: JsonMap) => (
                  <div key={gate.id} className="rounded border border-success/20 bg-background/20 px-2 py-1 text-[11px]">
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-medium">{gate.title || gate.id}</span>
                      <Badge variant={gate.open ? "success" : "warning"}>{gate.status || "unavailable"}</Badge>
                    </div>
                    <div className="mt-1 text-success/70">{gate.next_action}</div>
                  </div>
                ))}
                {!codingGates.length ? <div className="text-xs text-success/70">Run the unblocker to publish coding autonomy gates.</div> : null}
              </div>
            </div>
            <div className="rounded-md border border-success/25 bg-background/25 p-3">
              <div className="mb-2 text-xs font-medium text-success">Source Discovery</div>
              <div className="space-y-1">
                {sourceRoutes.slice(0, 4).map((routeItem: JsonMap) => (
                  <div key={routeItem.id} className="rounded border border-success/20 bg-background/20 px-2 py-1 text-[11px]">
                    <div className="font-medium">{routeItem.name || routeItem.id}</div>
                    <div className="mt-1 text-success/70">{String(routeItem.mode || "").replace(/_/g, " ")}</div>
                  </div>
                ))}
                {!sourceRoutes.length ? <div className="text-xs text-success/70">Source routes are unavailable until the unblocker report is present.</div> : null}
              </div>
            </div>
            <div className="rounded-md border border-success/25 bg-background/25 p-3">
              <div className="mb-2 text-xs font-medium text-success">Autonomous Work Orders</div>
              <div className="space-y-1">
                {codingWorkOrders.slice(0, 5).map((workOrder: JsonMap) => (
                  <div key={workOrder.id} className="rounded border border-success/20 bg-background/20 px-2 py-1 text-[11px]">
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-medium">{String(workOrder.id || "").replace(/_/g, " ")}</span>
                      <Badge variant="outline">{workOrder.priority || "P60"}</Badge>
                    </div>
                    <div className="mt-1 text-success/70">{workOrder.acceptance}</div>
                  </div>
                ))}
                {!codingWorkOrders.length ? <div className="text-xs text-success/70">No unblocker work orders are published yet.</div> : null}
              </div>
            </div>
          </div>
        </div>

        <div className="rounded-md border border-primary/30 bg-primary/10 p-3">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <div className="text-sm font-medium text-primary">Local Capability Forge</div>
              <div className="mt-1 text-xs text-primary/75">
                Aureon classifies the job, recruits a local crew, keeps external providers reference-only, and blocks handover until quality proof passes.
              </div>
            </div>
            <div className="flex flex-wrap gap-2">
              <Badge variant={capabilityForge.handover_ready || qualityReport.handover_ready ? "success" : "warning"}>
                {capabilityForge.status || qualityReport.status || "forge unavailable"}
              </Badge>
              <Badge variant="outline">{capabilityForge.task_family || qualityReport.task_family || "task pending"}</Badge>
              <Badge variant={qualityReport.handover_ready ? "success" : qualityReport.schema_version ? "warning" : "outline"}>
                score {qualityReport.schema_version ? `${Math.round(Number(qualityReport.score || 0) * 100)}%` : "unavailable"}
              </Badge>
              <Badge variant={approvalState === "approved" ? "success" : approvalState === "rejected" ? "destructive" : "outline"}>
                {String(approvalState).replace(/_/g, " ")}
              </Badge>
            </div>
          </div>

          <div className="mt-3 grid grid-cols-1 gap-2 md:grid-cols-4">
            <Mini label="Provider" value={capabilityForge.provider_policy || qualityReport.provider_policy || "local only"} />
            <Mini label="Crew" value={(capabilityForge.recruited_crew || []).length || 0} />
            <Mini label="Tools" value={(capabilityForge.local_tools_used || []).length || 0} />
            <Mini label="Snags" value={qualitySnags.length} />
          </div>
          {adaptiveSkill.name ? (
            <div className="mt-3 rounded-md border border-primary/25 bg-background/25 p-3 text-xs text-primary/80">
              <span className="font-medium text-primary">Adaptive skill:</span> {adaptiveSkill.name}
              {adaptiveSkill.skill_contract ? <span> - {adaptiveSkill.skill_contract}</span> : null}
            </div>
          ) : null}
          {fullStackSystem.status ? (
            <div className="mt-3 rounded-md border border-primary/25 bg-primary/10 p-3">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <div className="text-sm font-medium text-primary">Full-Stack Agent Build</div>
                  <div className="mt-1 text-xs text-primary/75">
                    Agents generated backend, frontend, data contract, tests, and runbook as a local full-stack system.
                  </div>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Badge variant={fullStackSystem.ok ? "success" : "warning"}>{fullStackSystem.status}</Badge>
                  <Badge variant={fullStackValidation.status === "contract_validated" ? "success" : "warning"}>
                    {fullStackValidation.status || "validation waiting"}
                  </Badge>
                </div>
              </div>
              <div className="mt-3 grid grid-cols-1 gap-2 md:grid-cols-4">
                <Mini label="Backend" value={fullStackManifest.backend_path ? "written" : "unavailable"} />
                <Mini label="Frontend" value={fullStackManifest.frontend_path ? "written" : "unavailable"} />
                <Mini label="Tests" value={fullStackManifest.test_path ? "written" : "unavailable"} />
                <Mini label="CRUD proof" value={fullStackValidation.crud_ok ? "pass" : "unavailable"} />
              </div>
              <div className="mt-3 grid grid-cols-1 gap-2 lg:grid-cols-2">
                <div className="rounded border border-primary/20 bg-background/20 p-2 text-[11px] text-primary/80">
                  <div className="mb-1 font-medium text-primary">Agent Flow</div>
                  {fullStackFlow.slice(0, 6).map((step: string) => (
                    <div key={step} className="py-0.5">{step}</div>
                  ))}
                </div>
                <div className="rounded border border-primary/20 bg-background/20 p-2 text-[11px] text-primary/80">
                  <div className="mb-1 font-medium text-primary">Generated System Paths</div>
                  <div className="whitespace-normal [overflow-wrap:anywhere] font-mono">{fullStackManifest.frontend_path || "frontend waiting"}</div>
                  <div className="whitespace-normal [overflow-wrap:anywhere] font-mono">{fullStackManifest.backend_path || "backend waiting"}</div>
                  <div className="whitespace-normal [overflow-wrap:anywhere] font-mono">{fullStackManifest.test_path || "tests waiting"}</div>
                  {fullStackManifest.public_url ? (
                    <a href={normalizePublicUrl(fullStackManifest.public_url)} target="_blank" rel="noreferrer" className="mt-2 inline-flex font-medium text-primary underline underline-offset-2">
                      Open full-stack preview
                    </a>
                  ) : null}
                </div>
              </div>
            </div>
          ) : null}

          <div className="mt-3 grid grid-cols-1 gap-3 lg:grid-cols-2">
            <div className="rounded-md border border-primary/25 bg-background/25 p-3">
              <div className="mb-2 text-xs font-medium text-primary">Quality Checks</div>
              <div className="space-y-1">
                {qualityChecks.slice(0, 7).map((check: JsonMap) => (
                  <div key={check.id} className="flex items-center justify-between gap-2 rounded border border-primary/20 bg-background/20 px-2 py-1 text-[11px]">
                    <span>{check.label || check.id}</span>
                    <Badge variant={check.ok ? "success" : check.blocking ? "warning" : "outline"}>{check.ok ? "pass" : "hold"}</Badge>
                  </div>
                ))}
                {!qualityChecks.length ? <div className="text-xs text-primary/70">Quality proof appears after Aureon produces an artifact or forge report.</div> : null}
              </div>
            </div>
            <div className="rounded-md border border-primary/25 bg-background/25 p-3">
              <div className="text-xs font-medium text-primary">Recorded artifact review</div>
              <div className="mt-2 text-xs text-primary/70">
                {String(approvalState).replace(/_/g, " ")}. This cloud status surface has no approval writer.
              </div>
              {qualitySnags.length ? (
                <div className="mt-3 space-y-1">
                  {qualitySnags.slice(0, 4).map((snag: JsonMap) => (
                    <div key={snag.id} className="rounded border border-warning/30 bg-warning/10 px-2 py-1 text-[11px] text-warning">
                      {snag.title || snag.id}
                    </div>
                  ))}
                </div>
              ) : null}
            </div>
          </div>
        </div>

        <div className="rounded-md border border-warning/30 bg-warning/10 p-3">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <div className="text-sm font-medium text-warning">Capability Stress Audit</div>
              <div className="mt-1 text-xs text-warning/75">
                Aureon stress-tests task families, detects fake passes, and separates proven handovers from correctly held work.
              </div>
            </div>
            <div className="flex flex-wrap gap-2">
              <Badge variant={stressAudit.ok ? "success" : stressAudit.schema_version ? "warning" : "outline"}>
                {stressAudit.status || "audit waiting"}
              </Badge>
              <Badge variant={Number(stressSummary.fake_pass_count || 0) ? "warning" : "success"}>
                fake passes {stressSummary.fake_pass_count || 0}
              </Badge>
              <Badge variant="outline">cases {stressSummary.passed_count || 0}/{stressSummary.case_count || 0}</Badge>
            </div>
          </div>
          <div className="mt-3 grid grid-cols-1 gap-2 md:grid-cols-4">
            <Mini label="Proven now" value={(stressAudit.capability_scope?.proven_now || []).length || 0} />
            <Mini label="Held correctly" value={(stressAudit.capability_scope?.correctly_blocked || []).length || 0} />
            <Mini label="Needs repair" value={(stressAudit.capability_scope?.needs_repair || []).length || 0} />
            <Mini label="Legacy findings" value={stressSummary.legacy_finding_count} />
          </div>
          <div className="mt-3 grid grid-cols-1 gap-2 lg:grid-cols-2">
            {stressCases.slice(0, 4).map((item: JsonMap) => (
              <div key={item.id} className="rounded-md border border-warning/25 bg-background/25 p-2 text-xs text-warning/80">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-medium text-warning">{String(item.id || "case").replace(/_/g, " ")}</span>
                  <Badge variant={item.ok ? "success" : "warning"}>{item.actual_handover ? "handover" : "held"}</Badge>
                </div>
                <div className="mt-1 text-warning/70">
                  {item.artifact_kind || "artifact pending"} | score {Math.round(Number(item.quality_score || 0) * 100)}%
                </div>
              </div>
            ))}
            {!stressCases.length ? <div className="text-xs text-warning/70">Run the stress audit to publish capability scope evidence.</div> : null}
          </div>
        </div>

        <div className="rounded-md border border-destructive/30 bg-destructive/10 p-3">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <div className="text-sm font-medium text-destructive">Complex Build Stress Certification</div>
              <div className="mt-1 text-xs text-destructive/75">
                Mixed-mode certification for broad client jobs: sandbox builds, live repo probes, safe auto-repairs, fake-pass detection, and handover gates.
              </div>
            </div>
            <div className="flex flex-wrap gap-2">
              <Badge variant={complexStress.ok ? "success" : complexStress.schema_version ? "warning" : "outline"}>
                {complexStress.status || "certification waiting"}
              </Badge>
              <Badge variant={Number(complexSummary.fake_pass_count || 0) ? "warning" : "success"}>
                fake passes {complexSummary.fake_pass_count || 0}
              </Badge>
              <Badge variant="outline">cases {complexSummary.passed_count || 0}/{complexSummary.case_count || 0}</Badge>
              <Badge variant={Number(complexSummary.repair_attempt_count || 0) ? "warning" : "outline"}>
                repairs {complexSummary.repair_attempt_count || 0}
              </Badge>
            </div>
          </div>
          <div className="mt-3 grid grid-cols-1 gap-2 md:grid-cols-5">
            <Mini label="Handover ready" value={complexSummary.handover_ready_count} />
            <Mini label="Correctly held" value={complexSummary.correctly_held_count} />
            <Mini label="Sandbox" value={complexSummary.sandbox_case_count} />
            <Mini label="Live repo" value={complexSummary.live_repo_case_count} />
            <Mini label="Needs repair" value={(complexStress.capability_scope?.needs_repair || []).length || 0} />
          </div>
          <div className="mt-3 grid grid-cols-1 gap-2 lg:grid-cols-2">
            {complexCases.slice(0, 10).map((item: JsonMap) => {
              const artifactUrl = normalizePublicUrl(item.quality_report?.artifact_manifest?.preview_url || item.actual_artifacts?.url || "");
              return (
                <div key={item.id} className="rounded-md border border-destructive/25 bg-background/25 p-2 text-xs text-destructive/80">
                  <div className="flex items-center justify-between gap-2">
                  <span className="font-medium text-destructive">{String(item.id || "case").replace(/_/g, " ")}</span>
                  <Badge variant={item.ok ? "success" : "warning"}>{item.handover_state?.state || "unavailable"}</Badge>
                  </div>
                  <div className="mt-1 text-destructive/70">
                  {item.actual_artifacts?.kind || "artifact pending"} | repairs {(item.repair_attempts || []).length || 0}
                  </div>
                  {artifactUrl ? (
                    <a href={artifactUrl} target="_blank" rel="noreferrer" className="mt-2 inline-flex text-[11px] font-medium text-destructive underline underline-offset-2">
                      Open preview
                    </a>
                  ) : null}
                </div>
              );
            })}
            {!complexCases.length ? <div className="text-xs text-destructive/70">Run complex build certification to publish broad build/workload evidence.</div> : null}
          </div>
        </div>

        <div className="rounded-md border border-success/30 bg-success/10 p-3">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <div className="text-sm font-medium text-success">Aureon Self-Fix SWOT</div>
              <div className="mt-1 text-xs text-success/75">
                Aureon audits its own coding evidence, selects repair work, applies safe local patches autonomously, reruns tests, and records Codex/user audit as evidence.
              </div>
            </div>
            <div className="flex flex-wrap gap-2">
              <Badge variant={selfFix.handover_ready ? "success" : selfFix.schema_version ? "warning" : "outline"}>
                {selfFix.status || "self-fix waiting"}
              </Badge>
              <Badge variant={selfFixCodexAudit.state === "failed" ? "destructive" : selfFixCodexAudit.state ? "success" : "outline"}>
                audit {selfFixCodexAudit.state || "unavailable"}
              </Badge>
              <Badge variant={Number(selfFixSummary.blocking_snag_count || 0) ? "warning" : "success"}>
                snags {selfFixSummary.blocking_snag_count || 0}
              </Badge>
              <Badge variant="outline">repairs {selfFixSummary.selected_repair_count || 0}</Badge>
            </div>
          </div>

          <div className="mt-3 grid grid-cols-1 gap-2 md:grid-cols-5">
            <Mini label="Backlog" value={selfFixSummary.repair_backlog_count || selfFixBacklog.length || 0} />
            <Mini label="Selected" value={selfFixSummary.selected_repair_count || selfFixSelectedRepairs.length || 0} />
            <Mini label="Patch candidates" value={selfFixSummary.patch_candidate_count} />
            <Mini label="Applied patches" value={selfFixSummary.patch_applied_count} />
            <Mini label="Tests" value={selfFix.test_evidence?.status || "unavailable"} />
          </div>

          <div className="mt-3 grid grid-cols-1 gap-3 lg:grid-cols-4">
            {(["strengths", "weaknesses", "opportunities", "threats"] as const).map((bucket) => {
              const items = Array.isArray(selfFixSwot[bucket]) ? selfFixSwot[bucket] : [];
              return (
                <div key={bucket} className="rounded-md border border-success/25 bg-background/25 p-3">
                  <div className="mb-2 text-xs font-medium capitalize text-success">{bucket}</div>
                  <div className="space-y-1">
                    {items.slice(0, 4).map((item: JsonMap) => (
                      <div key={item.id || item.text} className="rounded border border-success/20 bg-background/20 px-2 py-1 text-[11px] text-success/80">
                        <div className="flex items-center justify-between gap-2">
                          <span className="font-medium">{String(item.id || bucket).replace(/_/g, " ")}</span>
                          <Badge variant={item.present === false ? "outline" : bucket === "threats" || bucket === "weaknesses" ? "warning" : "success"}>
                            {item.present === false ? "missing" : "seen"}
                          </Badge>
                        </div>
                        <div className="mt-1 text-success/70">{item.text}</div>
                      </div>
                    ))}
                    {!items.length ? <div className="text-xs text-success/70">Self-fix director evidence unavailable.</div> : null}
                  </div>
                </div>
              );
            })}
          </div>

          <div className="mt-3 grid grid-cols-1 gap-3 lg:grid-cols-3">
            <div className="rounded-md border border-success/25 bg-background/25 p-3">
              <div className="mb-2 text-xs font-medium text-success">Selected Repairs</div>
              <div className="space-y-1">
                {selfFixSelectedRepairs.slice(0, 5).map((repair: JsonMap) => (
                  <div key={repair.id} className="rounded border border-success/20 bg-background/20 px-2 py-1 text-[11px] text-success/80">
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-medium">{String(repair.title || repair.id).replace(/_/g, " ")}</span>
                      <Badge variant="outline">{repair.priority || "P1"}</Badge>
                    </div>
                    <div className="mt-1 text-success/70">{repair.acceptance}</div>
                  </div>
                ))}
                {!selfFixSelectedRepairs.length ? <div className="text-xs text-success/70">No selected self-fix repairs are published yet.</div> : null}
              </div>
            </div>

            <div className="rounded-md border border-success/25 bg-background/25 p-3">
              <div className="mb-2 text-xs font-medium text-success">Patch Apply Evidence</div>
              <div className="space-y-1">
                {selfFixPatchEvidence.slice(0, 5).map((patch: JsonMap) => (
                  <div key={patch.proposal_id || patch.blocked_reason} className="rounded border border-success/20 bg-background/20 px-2 py-1 text-[11px] text-success/80">
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-medium">{patch.proposal_id || "proposal"}</span>
                      <Badge variant={patch.status === "applied" ? "success" : patch.applied ? "warning" : "outline"}>
                        {patch.status || "unavailable"}
                      </Badge>
                    </div>
                    <div className="mt-1 text-success/70">
                      {(patch.target_files || []).slice(0, 2).join(", ") || patch.blocked_reason || "no patch target"}
                    </div>
                  </div>
                ))}
                {!selfFixPatchEvidence.length ? <div className="text-xs text-success/70">No guarded patch has been attempted in the latest self-fix report.</div> : null}
              </div>
            </div>

            <div className="rounded-md border border-success/25 bg-background/25 p-3">
              <div className="mb-2 text-xs font-medium text-success">Audit Verdict</div>
              <div className="space-y-2 text-xs text-success/80">
                <div className="rounded border border-success/20 bg-background/20 px-2 py-1">
                  Audit record: {selfFixCodexAudit.state || "unavailable"}
                </div>
                <div className="rounded border border-success/20 bg-background/20 px-2 py-1">
                  Autonomous handover: {selfFix.handover_ready ? "ready" : "held"}
                </div>
                <div className="rounded border border-success/20 bg-background/20 px-2 py-1">
                  Test evidence: {selfFix.test_evidence?.status || "unavailable"}
                </div>
              </div>
              {selfFixSnags.length ? (
                <div className="mt-3 space-y-1">
                  {selfFixSnags.slice(0, 4).map((snag: JsonMap) => (
                    <div key={snag.id} className="rounded border border-warning/30 bg-warning/10 px-2 py-1 text-[11px] text-warning">
                      {snag.title || snag.id}
                    </div>
                  ))}
                </div>
              ) : null}
            </div>
          </div>
        </div>

        <div className="rounded-md border border-primary/30 bg-primary/10 p-3">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <div className="text-sm font-medium text-primary">Metacognitive Creative Process Guardian</div>
              <div className="mt-1 text-xs text-primary/75">
                Every agent role must sense Aureon's metacognitive, sensory, HNC/Auris, and sentient-style evidence before declaring who, what, where, when, how, and act.
              </div>
            </div>
            <div className="flex flex-wrap gap-2">
              <Badge variant={creativeGuardian.ok ? "success" : creativeGuardian.schema_version ? "warning" : "outline"}>
                {creativeGuardian.status || "guardian waiting"}
              </Badge>
              <Badge variant={creativeSummary.hnc_auris_ready ? "success" : "warning"}>
                HNC/Auris {creativeSummary.hnc_auris_ready ? "ready" : "held"}
              </Badge>
              <Badge variant={creativeSummary.who_what_where_when_how_act_ready ? "success" : "warning"}>
                roles {creativeSummary.creative_process_ready_role_count || 0}/{creativeSummary.role_count || 0}
              </Badge>
            </div>
          </div>

          <div className="mt-3 grid grid-cols-1 gap-2 md:grid-cols-5">
            <Mini label="Metacognitive" value={creativeSummary.metacognitive_ready ? "ready" : "unavailable"} />
            <Mini label="Sensory" value={creativeSummary.sensory_ready ? "ready" : "unavailable"} />
            <Mini label="Sentient-style" value={creativeSummary.sentient_style_ready ? "ready" : "unavailable"} />
            <Mini label="Repo surfaces" value={creativeSummary.repo_agent_surface_count} />
            <Mini label="Snags" value={creativeSummary.blocking_snag_count} />
          </div>

          <div className="mt-3 grid grid-cols-1 gap-3 lg:grid-cols-3">
            <div className="rounded-md border border-primary/25 bg-background/25 p-3">
              <div className="mb-2 text-xs font-medium text-primary">Mind Sources</div>
              <div className="space-y-1">
                {creativeSources.slice(0, 6).map((source: JsonMap) => (
                  <div key={source.name} className="flex items-center justify-between gap-2 rounded border border-primary/20 bg-background/20 px-2 py-1 text-[11px]">
                    <span>{String(source.name || "").replace(/_/g, " ")}</span>
                    <Badge variant={source.present && !source.stale ? "success" : source.present ? "warning" : "outline"}>
                      {source.present ? (source.stale ? "stale" : "present") : "missing"}
                    </Badge>
                  </div>
                ))}
                {!creativeSources.length ? <div className="text-xs text-primary/70">Mind source evidence appears after the guardian runs.</div> : null}
              </div>
            </div>
            <div className="rounded-md border border-primary/25 bg-background/25 p-3">
              <div className="mb-2 text-xs font-medium text-primary">Creative Loop</div>
              <div className="space-y-1">
                {creativeLoop.slice(0, 6).map((step: JsonMap) => (
                  <div key={step.step} className="rounded border border-primary/20 bg-background/20 px-2 py-1 text-[11px]">
                    <div className="font-medium">{String(step.step || "").replace(/_/g, " ")}</div>
                    <div className="mt-1 text-primary/70">{step.owner}</div>
                  </div>
                ))}
                {!creativeLoop.length ? <div className="text-xs text-primary/70">The creative loop evidence is unavailable until guardian evidence is present.</div> : null}
              </div>
            </div>
            <div className="rounded-md border border-primary/25 bg-background/25 p-3">
              <div className="mb-2 text-xs font-medium text-primary">Role Process Sample</div>
              <div className="space-y-1">
                {creativeRoleMap.slice(0, 6).map((role: JsonMap) => (
                  <div key={role.role_id || role.title} className="flex items-center justify-between gap-2 rounded border border-primary/20 bg-background/20 px-2 py-1 text-[11px]">
                    <span>{role.title || role.role_id}</span>
                    <Badge variant={role.status === "creative_process_ready" ? "success" : "warning"}>
                      {role.status === "creative_process_ready" ? "ready" : "hold"}
                    </Badge>
                  </div>
                ))}
                {!creativeRoleMap.length ? <div className="text-xs text-primary/70">Role contracts appear after the agent company registry is loaded.</div> : null}
              </div>
              {creativeSnags.filter((snag: JsonMap) => snag.severity === "blocking").length ? (
                <div className="mt-3 rounded border border-warning/30 bg-warning/10 px-2 py-1 text-[11px] text-warning">
                  {creativeSnags.filter((snag: JsonMap) => snag.severity === "blocking").length} blocking creative-process snag(s)
                </div>
              ) : null}
            </div>
          </div>
        </div>

        <div className="rounded-md border border-warning/30 bg-warning/10 p-3">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <div className="text-sm font-medium text-warning">Scope Of Works</div>
              <div className="mt-1 text-xs text-warning/75">
                Aureon treats each prompt as a client job: scope first, team handoff second, HNC/Auris drift proof, then snagging before client handover.
              </div>
            </div>
            <div className="flex flex-wrap gap-2">
              <Badge variant={clientJob.scope_locked ? "success" : "warning"}>
                {String(clientJob.scope_status || "prompt_evidence_unavailable").replace(/_/g, " ")}
              </Badge>
              <Badge variant="outline">questions {clientQuestions.length}</Badge>
              <Badge variant={finalHandoverVisible ? "success" : "warning"}>
                handover {finalHandoverVisible ? "visible" : "held"}
              </Badge>
            </div>
          </div>

          <div className="mt-3 grid grid-cols-1 gap-2 md:grid-cols-2">
            <Mini label="Goal" value={scopeOfWorks.goal || "unavailable"} />
            <Mini label="Deliverables" value={scopeOfWorks.deliverables || "unavailable"} />
            <Mini label="Target" value={scopeOfWorks.target_system || "unavailable"} />
            <Mini label="Acceptance" value={scopeOfWorks.acceptance || "unavailable"} />
          </div>

          {clientQuestions.length ? (
            <div className="mt-3 space-y-2">
              {clientQuestions.map((question: JsonMap) => (
                <div key={question.id} className="rounded-md border border-warning/30 bg-background/30 p-3">
                  <div className="text-xs font-medium text-warning">{question.question}</div>
                  <div className="mt-1 text-[11px] text-warning/70">{question.why_needed}</div>
                  <Textarea
                    value={scopeAnswers[question.id] || ""}
                    onChange={(event) =>
                      setScopeAnswers((current) => ({ ...current, [question.id]: event.target.value }))
                    }
                    className="mt-2 min-h-[64px] bg-background/60 text-xs"
                    placeholder="Client answer for this scope item"
                  />
                </div>
              ))}
              <Button size="sm" onClick={approveScope} disabled={!codingControlAvailable}>
                <Send className="mr-2 h-4 w-4" />
                Approve Scope And Send To Team
              </Button>
            </div>
          ) : null}

          <div className="mt-3 grid grid-cols-1 gap-2 lg:grid-cols-3">
            <div className="rounded-md border border-border/30 bg-background/25 p-3">
              <div className="text-xs font-medium">Agent Team</div>
              <div className="mt-2 space-y-1">
                {agentTeam.slice(0, 6).map((agent: JsonMap) => (
                  <div key={`${agent.role}-${agent.phase}`} className="flex items-center justify-between gap-2 text-[11px]">
                    <span>{agent.role}</span>
                    <Badge variant={agent.status === "active" ? "success" : "outline"}>{String(agent.status || "unavailable").replace(/_/g, " ")}</Badge>
                  </div>
                ))}
                {!agentTeam.length ? <div className="text-xs text-muted-foreground">Team appears after first client job intake.</div> : null}
              </div>
            </div>
            <div className="rounded-md border border-border/30 bg-background/25 p-3">
              <div className="text-xs font-medium">Phase Timers</div>
              <div className="mt-2 space-y-1">
                {phaseTimers.slice(0, 7).map((phase: JsonMap) => (
                  <div key={phase.phase} className="flex items-center justify-between gap-2 text-[11px]">
                    <span>{String(phase.phase || "").replace(/_/g, " ")}</span>
                    <Badge variant={phase.status === "completed" ? "success" : phase.status === "waiting_client" ? "warning" : "outline"}>
                      {String(phase.status || "pending").replace(/_/g, " ")}
                    </Badge>
                  </div>
                ))}
                {!phaseTimers.length ? <div className="text-xs text-muted-foreground">Timers start when a prompt enters the client lane.</div> : null}
              </div>
            </div>
            <div className="rounded-md border border-border/30 bg-background/25 p-3">
              <div className="text-xs font-medium">Handover Gate</div>
              <div className="mt-2 text-xs text-muted-foreground">
                {handoverStatus.reason || "Finished products stay hidden until proof and snagging are clear."}
              </div>
              <div className="mt-2 grid grid-cols-2 gap-2">
                <Mini label="Proof" value={`${proofChecklist.filter((item: JsonMap) => item.ok).length}/${proofChecklist.length || 0}`} />
                <Mini label="Snags" value={snaggingList.filter((item: JsonMap) => item.severity === "blocking").length} />
              </div>
            </div>
          </div>
        </div>

        <div className="rounded-md border border-primary/30 bg-primary/5 p-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <FileText className="h-4 w-4 text-primary" />
              <div>
                <div className="text-sm font-medium">Work Journal: Prompt To Finished Files</div>
                <div className="text-xs text-muted-foreground">
                  Aureon shows every stage it went through, with evidence and verification.
                </div>
              </div>
            </div>
            <div className="flex flex-wrap gap-2">
              <Badge variant={journal.status === "complete" ? "success" : "warning"}>
                {journal.status || "unavailable"}
              </Badge>
              <Badge variant="outline">{journal.completed_count || 0}/{journal.stage_count || 0} stages</Badge>
              <Badge variant={journal.attention_count ? "warning" : "outline"}>
                attention {journal.attention_count || 0}
              </Badge>
            </div>
          </div>

          <div className="overflow-y-auto min-w-0 mt-3 h-[300px] pr-3">
            <div className="space-y-2">
              {journalStages.map((stage: JsonMap, index: number) => (
                <div key={stage.id || stage.title || index} className="rounded-md border border-border/40 bg-background/50 p-3">
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="flex h-6 w-6 items-center justify-center rounded-full border border-primary/40 bg-primary/10 text-[11px] font-semibold">
                          {index + 1}
                        </span>
                        <div className="text-sm font-medium">{stage.title || stage.id}</div>
                      </div>
                      <div className="mt-2 text-xs text-muted-foreground">{stage.summary || "No summary published."}</div>
                      <div className="mt-2 font-mono text-[11px] text-muted-foreground">{compactEvidence(stage)}</div>
                    </div>
                    <Badge variant={stage.ok ? "success" : "warning"}>{String(stage.status || "pending").replace(/_/g, " ")}</Badge>
                  </div>
                  {Array.isArray(stage.evidence?.published_files) && stage.evidence.published_files.length ? (
                    <div className="mt-2 flex flex-wrap gap-1">
                      {stage.evidence.published_files.slice(0, 4).map((file: string) => (
                        <Badge key={file} variant="outline" className="max-w-full whitespace-normal [overflow-wrap:anywhere] font-mono text-[10px]">
                          {file}
                        </Badge>
                      ))}
                    </div>
                  ) : null}
                  {Array.isArray(stage.evidence?.commands) && stage.evidence.commands.length ? (
                    <div className="mt-2 space-y-1">
                      {stage.evidence.commands.slice(0, 2).map((command: JsonMap, commandIndex: number) => (
                        <div key={`${stage.id}-command-${commandIndex}`} className="rounded border border-border/30 bg-muted/20 px-2 py-1 font-mono text-[10px] text-muted-foreground">
                          {command.ok ? "PASS" : "ATTN"} {command.command}
                        </div>
                      ))}
                    </div>
                  ) : null}
                </div>
              ))}
              {!journalStages.length ? (
                <div className="rounded-md border border-border/40 bg-muted/10 p-4 text-sm text-muted-foreground">
                  No current cloud work journal is available. A commissioned worker must publish one before this panel can show it.
                </div>
              ) : null}
            </div>
          </div>
        </div>

        {artifactItems.length ? (
          <div className="rounded-md border border-success/30 bg-success/10 p-3">
            <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
              <div className="text-sm font-medium text-success">Finished Artifacts</div>
              <Badge variant="success">{artifactItems.length} visible</Badge>
            </div>
            <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
              {artifactItems.map((artifact) => (
                <div key={artifact.url} className="rounded-md border border-success/25 bg-background/30 p-3">
                  <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                    <div className="text-xs font-medium text-success">{artifact.title}</div>
                    <a
                      href={artifact.url}
                      target="_blank"
                      rel="noreferrer"
                      className="rounded-md border border-success/40 px-2 py-1 text-[11px] text-success hover:bg-success/10"
                    >
                      Open Artifact
                    </a>
                  </div>
                  {artifact.kind === "image" ? (
                    <img src={artifact.url} alt={artifact.title} className="max-h-[320px] w-full rounded border border-success/20 bg-white object-contain" />
                  ) : artifact.kind === "video" ? (
                    <video src={artifact.url} className="max-h-[320px] w-full rounded border border-success/20 bg-black" controls />
                  ) : (
                    <div className="rounded border border-success/20 bg-muted/20 p-3 font-mono text-[11px] text-muted-foreground">{artifact.url}</div>
                  )}
                  <div className="mt-2 whitespace-normal [overflow-wrap:anywhere] font-mono text-[10px] text-success/70">{artifact.path || artifact.url}</div>
                </div>
              ))}
            </div>
          </div>
        ) : null}

        <div className="grid grid-cols-1 gap-3 lg:grid-cols-[1fr_0.8fr]">
          <div className="space-y-2">
            <Textarea
              value={prompt}
              onChange={(event) => setPrompt(event.target.value)}
              disabled={!codingControlAvailable}
              className="min-h-[130px] font-mono text-xs"
            />
            <div className="flex flex-wrap items-center justify-between gap-2">
              <label className="flex items-center gap-2 text-xs text-muted-foreground">
                <input
                  type="checkbox"
                  checked={runTests}
                  disabled={!codingControlAvailable}
                  onChange={(event) => setRunTests(event.target.checked)}
                  className="h-4 w-4"
                />
                Run focused coding tests
              </label>
              <label className="flex items-center gap-2 text-xs text-muted-foreground">
                <input
                  type="checkbox"
                  checked={includeDesktop}
                  disabled={!codingControlAvailable}
                  onChange={(event) => setIncludeDesktop(event.target.checked)}
                  className="h-4 w-4"
                />
                Prepare desktop/run handoff
              </label>
              <div className="flex flex-wrap gap-2">
                <label aria-disabled={!codingControlAvailable} className={`inline-flex items-center rounded-md border border-input bg-background px-3 py-2 text-xs font-medium ${codingControlAvailable ? "cursor-pointer hover:bg-accent hover:text-accent-foreground" : "cursor-not-allowed opacity-50"}`}>
                  <Upload className="mr-2 h-4 w-4" />
                  {loadedFileName ? loadedFileName : "Load MD"}
                  <input type="file" accept=".md,.txt" className="hidden" onChange={loadPromptFile} disabled={!codingControlAvailable} />
                </label>
                <Button size="sm" variant="outline" onClick={refresh}>
                  Refresh
                </Button>
                <Button size="sm" variant="outline" onClick={sendFullCodingJob} disabled={!codingControlAvailable || !prompt.trim()}>
                  Full Coding Job
                </Button>
                <Button size="sm" onClick={() => submitPrompt()} disabled={!codingControlAvailable || !prompt.trim()}>
                  <Send className="mr-2 h-4 w-4" />
                  Send To Aureon
                </Button>
              </div>
            </div>
            {error ? <div className="rounded-md border border-destructive/30 bg-destructive/10 p-2 text-xs text-destructive">{error}</div> : null}
          </div>

          <div className="space-y-2 rounded-md border border-border/40 bg-muted/10 p-3">
            <div className="text-sm font-medium">Who What Where When How Act</div>
            {["who", "what", "where", "when", "how", "act"].map((key) => (
              <div key={key} className="rounded-md border border-border/30 bg-background/20 px-3 py-2">
                <div className="text-[10px] uppercase text-muted-foreground">{key}</div>
                <div className="mt-1 whitespace-normal [overflow-wrap:anywhere] font-mono text-[11px]">{JSON.stringify(status[key] || {})}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
          <div className="space-y-2 rounded-md border border-success/30 bg-success/10 p-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="text-sm font-medium text-success">Finished Product Audit</div>
              <Badge variant={finalHandoverVisible ? "success" : "warning"}>
                {finalHandoverVisible ? "ready for client" : "handover held"}
              </Badge>
            </div>
            {finalHandoverVisible ? (
              (productAudit.stages || []).slice(0, 8).map((stage: JsonMap) => (
                <div key={stage.stage} className="flex items-center justify-between rounded-md border border-success/20 bg-background/30 px-3 py-2 text-xs">
                  <span>{String(stage.stage || "").replace(/_/g, " ")}</span>
                  <span className={stage.ok ? "text-success" : "text-warning"}>{stage.ok ? "pass" : "attention"}</span>
                </div>
              ))
            ) : (
              <div className="rounded-md border border-warning/30 bg-warning/10 p-3 text-xs text-warning">
                Final handover is hidden until scope, route, proof, and snagging gates pass.
              </div>
            )}
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
              <div className="space-y-1">
                <div className="text-[11px] uppercase text-success/70">Proof checklist</div>
                {proofChecklist.slice(0, 6).map((item: JsonMap) => (
                  <div key={item.id} className="flex items-center justify-between rounded border border-success/20 bg-background/20 px-2 py-1 text-[11px]">
                    <span>{item.label}</span>
                    <span className={item.ok ? "text-success" : "text-warning"}>{item.ok ? "pass" : "hold"}</span>
                  </div>
                ))}
              </div>
              <div className="space-y-1">
                <div className="text-[11px] uppercase text-success/70">Snagging list</div>
                {snaggingList.slice(0, 6).map((snag: JsonMap) => (
                  <div key={snag.id} className="rounded border border-success/20 bg-background/20 px-2 py-1 text-[11px]">
                    <div className="flex items-center justify-between gap-2">
                      <span>{snag.title}</span>
                      <span className={snag.severity === "blocking" ? "text-warning" : "text-success"}>{snag.status}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div className="space-y-2 rounded-md border border-primary/30 bg-primary/10 p-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="text-sm font-medium text-primary">Desktop And Remote Run Handoff</div>
              <Badge variant={desktopController.emergency_stopped ? "destructive" : "outline"}>
                {desktopController.dry_run === false ? "live" : "dry run"}
              </Badge>
            </div>
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
              <Mini label="Armed" value={desktopController.armed ? "yes" : "no"} />
              <Mini label="Pending" value={(desktopController.pending_actions || []).length} />
              <Mini label="VM tools" value={desktop.remote_vm_control?.tool_count} />
            </div>
            <div className="text-xs text-primary/75">
              {desktop.safety?.desktop_default || "Desktop control is dry-run unless the operator arms it."}
            </div>
          </div>
        </div>

        <div className="overflow-y-auto min-w-0 h-[220px] pr-3">
          <div className="space-y-2">
            {steps.map((step: JsonMap) => (
              <div key={step.step_id || step.title} className="rounded-md border border-border/40 bg-muted/10 p-3">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div>
                    <div className="text-sm font-medium">{step.title || step.intent}</div>
                    <div className="mt-1 font-mono text-[11px] text-muted-foreground">{step.intent}</div>
                  </div>
                  <Badge variant={step.status === "completed" ? "success" : "outline"}>{step.status || "pending"}</Badge>
                </div>
              </div>
            ))}
            {!steps.length ? (
              <div className="rounded-md border border-border/40 bg-muted/10 p-4 text-sm text-muted-foreground">
                No coding route has been published yet.
              </div>
            ) : null}
          </div>
        </div>
          </>
        ) : (
          <div data-testid="coding-worker-unavailable" className="rounded-md border border-warning/35 bg-warning/10 p-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <div className="text-sm font-medium text-warning">Cloud coding worker not commissioned</div>
                <div className="mt-1 max-w-3xl text-xs text-warning/80">
                  The owner status route is live and authenticated, but there is no reviewed cloud worker behind it. No prompt, chat, reload, autonomous job, repo mutation, proxy, or credential capability is exposed.
                </div>
              </div>
              <Button size="sm" variant="outline" onClick={refresh}>Refresh authenticated status</Button>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
    </div>
  );
}

function Stat({ icon: Icon, label, value }: { icon: ComponentType<{ className?: string }>; label: string; value: unknown }) {
  return (
    <div className="rounded-md border border-border/40 bg-muted/10 p-3">
      <div className="flex items-center gap-2 text-[11px] uppercase text-muted-foreground">
        <Icon className="h-3.5 w-3.5" />
        {label}
      </div>
      <div className="mt-1 text-lg font-semibold">{typeof value === "number" ? fmt(value) : consoleDisplayValue(value)}</div>
    </div>
  );
}

function Mini({ label, value }: { label: string; value: unknown }) {
  return (
    <div className="rounded-md border border-border/30 bg-background/20 px-3 py-2 text-xs">
      <div className="text-[10px] uppercase text-muted-foreground">{label}</div>
      <div className="mt-1 font-semibold">{typeof value === "number" ? fmt(value) : consoleDisplayValue(value)}</div>
    </div>
  );
}
