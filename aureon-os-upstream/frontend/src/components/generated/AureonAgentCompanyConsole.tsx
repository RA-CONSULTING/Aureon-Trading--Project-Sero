import { GlassPageHeader } from "@/shell/GlassPage";
import { useEffect, useState } from "react";
import { GeneratedReportBoundary } from "./GeneratedReportBoundary";
import { CompanyRoleWorkbench } from "./CompanyRoleWorkbench";
import { recordedNumber, recordedArrayCount, recordedBoolean } from "@/lib/recordedReportEvidence";
import { AGENT_COMPANY_SOURCE, readAgentCompanyReport } from "@/lib/agentCompanyReportEvidence";
import { fetchRepoManifest } from "@/lib/repoManifestEvidence";
import { useReadOnlyPoller } from "@/hooks/useReadOnlyPoller";
import { companyRosterStore } from "@/services/cognitiveReads";
import type { CompanyRoster } from "@/lib/companyRosterEvidence";
import { Building2, BriefcaseBusiness, ListChecks, Network, ShieldCheck, Users, Workflow, type LucideIcon } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";

// eslint-disable-next-line @typescript-eslint/no-explicit-any -- Generated report fields are schema-checked at read boundaries before display.
type JsonMap = Record<string, any>;
type RuntimeVerification = NonNullable<CompanyRoster["runtime_verification"]>;
type CompanyRole = CompanyRoster["roles"][number];

function departmentRoles(report: JsonMap, departmentId: string): JsonMap[] {
  const roles = Array.isArray(report.roles) ? report.roles : [];
  return roles.filter((role: JsonMap) => role.department === departmentId);
}

function countLabel(value: number | null | undefined): string {
  return typeof value === "number" && Number.isFinite(value) ? value.toLocaleString() : "Unavailable";
}

function runtimeTimestamp(value: number | null | undefined): string {
  return typeof value === "number" && Number.isFinite(value) ? new Date(value * 1000).toISOString() : "unavailable";
}

function RuntimeOrganSamples({ runtime }: { runtime: RuntimeVerification }) {
  const running = runtime.sample_running_organs.slice(0, 6);
  const stopped = runtime.sample_stopped_organs.slice(0, 6);
  return <div className="grid min-w-0 grid-cols-1 gap-2 md:grid-cols-2">
    <div className="rounded-md border border-border/40 bg-muted/10 p-3">
      <div className="mb-2 text-xs font-medium">Observed running organs</div>
      <div className="space-y-1">
        {running.map(organ => <div key={organ.name} className="flex flex-wrap justify-between gap-2 text-[11px] text-muted-foreground">
          <span className="font-mono text-foreground">{organ.name}</span>
          <span>pid {countLabel(organ.pid)} · identity {organ.identity_verified ? "verified" : "unverified"}</span>
        </div>)}
        {!running.length ? <div className="text-[11px] text-muted-foreground">No running organs were observed in this receipt.</div> : null}
      </div>
    </div>
    <div className="rounded-md border border-border/40 bg-muted/10 p-3">
      <div className="mb-2 text-xs font-medium">Held, stopped, or unmeasured organs</div>
      <div className="space-y-1">
        {stopped.map(organ => <div key={organ.name} className="flex flex-wrap justify-between gap-2 text-[11px] text-muted-foreground">
          <span className="font-mono text-foreground">{organ.name}</span>
          <span>{organ.read_state}{organ.reason ? ` · ${organ.reason}` : ""}</span>
        </div>)}
        {!stopped.length ? <div className="text-[11px] text-muted-foreground">No stopped or unmeasured organs were reported in this receipt.</div> : null}
      </div>
    </div>
  </div>;
}

function RuntimeRoleBindings({ runtime }: { runtime: RuntimeVerification }) {
  const matches = runtime.running_role_matches ?? [];
  const manifest = runtime.runtime_binding_manifest;
  const roleSurfaceGaps = Array.isArray(runtime.role_surface_gaps)
    ? runtime.role_surface_gaps as Array<{ role_id?: string; missing_surfaces?: string[] }>
    : [];
  const roleSurfaceGapCount = typeof runtime.role_surface_gap_count === "number"
    ? runtime.role_surface_gap_count
    : roleSurfaceGaps.length;
  const unboundGroups = Object.entries(runtime.unbound_roles_by_department ?? {})
    .filter(([, roles]) => roles.length > 0);
  const bindingsByOrgan = Object.entries(runtime.service_surface_bindings_by_organ ?? {})
    .sort(([, a], [, b]) => b - a);
  return <div className="rounded-md border border-border/40 bg-muted/10 p-3">
    <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
      <div className="text-xs font-medium">Live service-surface role bindings</div>
      <div className="flex flex-wrap gap-1">
        <Badge variant="outline">{countLabel(runtime.manifest_running_role_match_count)} manifest</Badge>
        <Badge variant="outline">{countLabel(runtime.unbound_role_count)} unbound</Badge>
        <Badge variant="outline">{countLabel(roleSurfaceGapCount)} surface gaps</Badge>
      </div>
    </div>
    <p className="text-[11px] text-muted-foreground">
      Manifest bindings let a configured role work through an identity-verified live service surface. They do not create autonomous employee processes or grant exchange, filing, payment, credential, or tool authority.
      {manifest?.source_generated_at ? ` Manifest generated ${manifest.source_generated_at}.` : ""}
    </p>
    {bindingsByOrgan.length ? <div className="mt-2 flex flex-wrap gap-1">
      {bindingsByOrgan.map(([organ, count]) => <Badge key={organ} variant="outline" className="text-[10px]">
        {organ}: {count}
      </Badge>)}
    </div> : null}
    <div className="mt-2 grid min-w-0 grid-cols-1 max-h-[420px] gap-1 overflow-auto pr-1 md:grid-cols-2 xl:grid-cols-3">
      {matches.map(match => <div key={`${match.role_id}-${match.organ_name}`} className="rounded border border-border/30 bg-background/25 px-2 py-1.5">
        <div className="whitespace-normal [overflow-wrap:anywhere] text-[11px] font-medium">{match.role_id}</div>
        <div className="whitespace-normal [overflow-wrap:anywhere] font-mono text-[10px] text-muted-foreground">{match.organ_name} · pid {countLabel(match.pid)}</div>
        <div className="text-[10px] text-muted-foreground">{match.binding_kind ?? "service surface"}</div>
      </div>)}
      {!matches.length ? <div className="text-[11px] text-muted-foreground">No role-to-service bindings were verified in this receipt.</div> : null}
    </div>
    {unboundGroups.length ? <div className="mt-3 rounded border border-amber-400/30 bg-amber-500/5 p-2">
      <div className="text-[11px] font-medium text-amber-200">Roles still waiting for a verified service surface</div>
      <div className="mt-1 grid min-w-0 grid-cols-1 gap-1 md:grid-cols-2">
        {unboundGroups.map(([department, roles]) => <div key={department} className="text-[10px] text-muted-foreground">
          <span className="font-mono text-foreground">{department}</span>: {roles.map(role => role.role_id).join(", ")}
        </div>)}
      </div>
    </div> : null}
    {roleSurfaceGaps.length ? <div className="mt-3 rounded border border-amber-400/30 bg-amber-500/5 p-2">
      <div className="text-[11px] font-medium text-amber-200">Role-specific surfaces still missing</div>
      <div className="mt-1 grid min-w-0 grid-cols-1 gap-1 md:grid-cols-2">
        {roleSurfaceGaps.map(gap => <div key={gap.role_id} className="text-[10px] text-muted-foreground">
          <span className="font-mono text-foreground">{gap.role_id}</span>: {(gap.missing_surfaces ?? []).join(", ") || "surface unavailable"}
        </div>)}
      </div>
    </div> : null}
  </div>;
}

function ConfiguredCompanyRoster({ roster, loading, error, receivedAt, current }: {
  roster: CompanyRoster | null; loading: boolean; error: string | null;
  receivedAt: number | null; current: boolean;
}) {
  const departments = roster?.departments ?? [];
  const roles = roster?.roles ?? [];
  const [selectedRoleId, setSelectedRoleId] = useState<string | null>(null);
  const selectedRole: CompanyRole | null = roles.find(role => role.role_id === selectedRoleId) ?? null;
  const runtime = current ? roster?.runtime_verification ?? null : null;
  const counts = runtime?.organ_counts;
  const brain = runtime?.brain_fabric_verification;
  return <Card className="bg-card/80">
    <CardHeader className="pb-3">
      <CardTitle className="flex items-center gap-2 text-base">
        <Users className="h-4 w-4 text-primary" /> Configured workforce catalogue
      </CardTitle>
    </CardHeader>
    <CardContent className="space-y-3">
      <div className="flex flex-wrap gap-2">
        <Badge variant="outline">Configured roles: {roster ? roster.summary.role_count : "Unavailable"}</Badge>
        <Badge variant="outline">Departments: {roster ? roster.summary.department_count : "Unavailable"}</Badge>
        <Badge variant="outline">Gateway receipt: {current ? "current" : "unavailable"}</Badge>
        <Badge variant="outline">Runtime organs: {runtime ? `${countLabel(counts?.running_total)}/${countLabel(counts?.registered)}` : "Unavailable"}</Badge>
        <Badge variant="outline">Identity-verified organs: {runtime ? countLabel(counts?.running_verified) : "Unavailable"}</Badge>
        <Badge variant="outline">Role/service binding: {runtime?.role_binding_state ?? "unavailable"}</Badge>
        <Badge variant="outline">Company operation: {runtime?.live_company_operation_state?.replace(/_/g, " ") ?? "unavailable"}</Badge>
        <Badge variant="outline">Surface-bound roles: {runtime ? countLabel(runtime.verified_running_role_count) : "Unavailable"}</Badge>
        <Badge variant="outline">Unbound roles: {runtime ? countLabel(runtime.unbound_role_count) : "Unavailable"}</Badge>
        <Badge variant="outline">Brain routing: {brain ? `${countLabel(brain.hnc_routed_brain_count)}/${countLabel(brain.brain_passport_count)}` : "Unavailable"}</Badge>
        <Badge variant="outline">Brain provider: {brain?.provider_mode ?? "Unavailable"}</Badge>
        <Badge variant="outline">Brain execution: {brain?.execution_ready ? "ready" : brain ? "held" : "Unavailable"}</Badge>
      </div>
      <p className="text-xs text-muted-foreground">
        This is the gateway-served role configuration. Runtime organs come from the passive registered-PID OS probe. Role/service bindings come from the evidence manifest and prove only live service surfaces. Brain routing comes from the generated HNC/Ollama passport report and is separate from executable tool/action authority.
        {receivedAt ? ` HTTP receipt ${new Date(receivedAt).toISOString()}; runtime observed ${runtimeTimestamp(runtime?.source_timestamp)}.` : ""}
      </p>
      {brain ? <p className="text-xs text-muted-foreground">Brain fabric: {brain.brain_fabric_status ?? "unavailable"}; truth gate {brain.truth_gate_enforced ? "enforced" : "held"}; generated {brain.source_generated_at ?? "unavailable"}.</p> : null}
      {runtime?.blockers.length ? <p className="text-xs text-amber-300">Runtime blockers: {runtime.blockers.join("; ")}</p> : null}
      {brain?.blockers.length ? <p className="text-xs text-amber-300">Brain blockers: {brain.blockers.join("; ")}</p> : null}
      {runtime ? <RuntimeRoleBindings runtime={runtime} /> : null}
      {runtime ? <RuntimeOrganSamples runtime={runtime} /> : null}
      {loading ? <p className="text-xs text-muted-foreground">Loading configured roles…</p> : null}
      {error ? <p className="text-xs text-destructive">{error}</p> : null}
      <Dialog open={selectedRole !== null} onOpenChange={open => { if (!open) setSelectedRoleId(null); }}>
        <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-4xl">
          <DialogHeader>
            <DialogTitle>Company role workbench</DialogTitle>
            <DialogDescription>
              Current department data and links to existing operator screens for this configured role perspective.
            </DialogDescription>
          </DialogHeader>
          {selectedRole ? <CompanyRoleWorkbench role={{
            role_id: selectedRole.role_id ?? '',
            title: selectedRole.title ?? selectedRole.role_id ?? 'Configured role',
            department: selectedRole.department ?? '',
          }} /> : null}
        </DialogContent>
      </Dialog>
      {roster ? <div className="overflow-y-auto min-w-0 h-[360px] pr-3">
        <div className="space-y-3">
          {departments.map(department => {
            const departmentRoster = roles.filter(role => role.department === department.id);
            return <div key={department.id} className="rounded-md border border-border/40 bg-muted/10 p-3">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div><div className="text-sm font-medium">{department.title}</div>
                  <div className="mt-1 text-xs text-muted-foreground">{department.mission}</div></div>
                <Badge variant="outline">{departmentRoster.length} configured roles</Badge>
              </div>
              <div className="mt-3 grid min-w-0 grid-cols-1 gap-2 md:grid-cols-2 xl:grid-cols-3">
                {departmentRoster.map(role => <div key={role.role_id} className="rounded border border-border/30 bg-background/30 p-2">
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div><div className="text-xs font-medium">{role.title}</div>
                      <div className="text-[11px] text-muted-foreground">{role.seniority}</div></div>
                    <Badge variant="outline" className="text-[10px]">{role.authority_level.replace(/_/g, " ")}</Badge>
                  </div>
                  <div className="mt-1 text-[11px] text-muted-foreground">{role.mission}</div>
                  <div className="mt-2 flex flex-wrap gap-1">{role.tools_allowed.map(tool =>
                    <Badge key={tool} variant="outline" className="text-[10px]">{tool.replace(/_/g, " ")}</Badge>)}</div>
                  <Button type="button" size="sm" variant="outline" className="mt-2 h-7 w-full text-[11px]"
                    onClick={() => setSelectedRoleId(role.role_id)}>
                    Open current workbench
                  </Button>
                </div>)}
              </div>
            </div>;
          })}
          {!departments.length ? <div className="text-xs text-muted-foreground">The current catalogue explicitly contains no configured departments.</div> : null}
        </div>
      </div> : null}
    </CardContent>
  </Card>;
}

export function AureonAgentCompanyConsole() {
  const [report, setReport] = useState<JsonMap>({});
  const [loadError, setLoadError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const rosterRead = useReadOnlyPoller(companyRosterStore, 30_000, 8_000);
  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const controller = new AbortController();
    const refresh = async () => {
      const receipt = await fetchRepoManifest(AGENT_COMPANY_SOURCE, controller.signal);
      if (cancelled) return;
      const value = readAgentCompanyReport(receipt.report);
      setReport(value ?? {});
      setLoadError(value ? null : receipt.report ? "Malformed Agent Company report; recorded metrics unavailable."
        : "Recorded Agent Company report is unavailable at the configured source.");
      setLoading(false);
      timer = setTimeout(() => void refresh(), 30_000);
    };
    void refresh();
    return () => { cancelled = true; controller.abort(); clearTimeout(timer); };
  }, []);

  const summary = report.summary || {};
  const departments = Array.isArray(report.departments) ? report.departments : [];
  const boundaries = Array.isArray(report.authority_boundaries) ? report.authority_boundaries : [];
  const workOrders = Array.isArray(report.work_orders) ? report.work_orders : [];
  const coverage = Array.isArray(report.capability_coverage) ? report.capability_coverage : [];
  const handoffMap = Array.isArray(report.handoff_map) ? report.handoff_map : [];
  const dailyLoop = Array.isArray(report.daily_operating_loop) ? report.daily_operating_loop : [];
  const accessPolicy = report.whole_organism_access_policy || {};
  const myceliumDoctrine = report.mycelium_organisation_doctrine || {};
  const myceliumMap = Array.isArray(myceliumDoctrine.metaphor_map) ? myceliumDoctrine.metaphor_map : [];
  const myceliumPrinciples = Array.isArray(myceliumDoctrine.operating_principles) ? myceliumDoctrine.operating_principles : [];
  const bioCosmicDoctrine = report.bio_cosmic_organisation_doctrine || {};
  const bioCosmicScale = Array.isArray(bioCosmicDoctrine.scale_ladder) ? bioCosmicDoctrine.scale_ladder : [];
  const bioCosmicLaws = Array.isArray(bioCosmicDoctrine.operating_laws) ? bioCosmicDoctrine.operating_laws : [];
  const agencyModel = report.agency_operating_model || {};
  const clientJobLifecycle = Array.isArray(report.prompt_client_job_lifecycle) ? report.prompt_client_job_lifecycle : [];
  const retirementPolicy = report.subcontractor_retirement_policy || {};
  const memoryPhonebook = report.workforce_memory_phonebook || {};
  const memorySummary = memoryPhonebook.summary || {};
  const recruitmentEngine = report.recruitment_engine || {};
  const recruitmentSummary = recruitmentEngine.summary || {};
  const recruitedWorkers = Array.isArray(recruitmentEngine.recruited_workers) ? recruitmentEngine.recruited_workers : [];
  const recruitmentStages = Array.isArray(recruitmentEngine.stage_flow) ? recruitmentEngine.stage_flow : [];
  const onlineSearch = recruitmentEngine.online_skill_searches || {};
  const onlineSearches = Array.isArray(onlineSearch.searches) ? onlineSearch.searches : [];
  const topWorkOrders = workOrders.slice(0, 5);

  const rosterCard = <ConfiguredCompanyRoster roster={rosterRead.data} loading={rosterRead.loading}
    error={rosterRead.error} receivedAt={rosterRead.lastReceivedAt} current={rosterRead.isReceiptCurrent} />;

  const pageHeader = <GlassPageHeader eyebrow="Cognition & LLM" title="Agent company" icon={Building2}
    description="Configured departments, role workbenches and dated company records." />;

  if (loading) return <div className="space-y-5">{pageHeader}{rosterCard}
    <Card className="p-4 text-sm text-muted-foreground">Loading recorded Agent Company report…</Card></div>;
  return (
    <div className="space-y-5">
    {pageHeader}
    {rosterCard}
    {loadError && <p className="text-sm text-muted-foreground">{loadError}</p>}
    <GeneratedReportBoundary report={report} source={AGENT_COMPANY_SOURCE} scope="recorded">
    <Card className="mb-5 bg-card/80">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-base">
          <Building2 className="h-4 w-4 text-primary" />
          Aureon Agent Company · recorded registry
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex flex-wrap gap-2">
          <Badge variant="outline">Recorded status: {report.status || "Unavailable"}</Badge>
          <Badge variant="outline">Report generated: {report.generated_at || "Unavailable"}</Badge>
          <Badge variant="outline">Recorded gates preserved: {recordedBoolean(summary.existing_gates_preserved)}</Badge>
          <Badge variant="outline">Recorded mode: {summary.registry_mode || "Unavailable"}</Badge>
        </div>

        <div className="grid min-w-0 grid-cols-1 gap-2 md:grid-cols-4 xl:grid-cols-8">
          <Stat icon={Users} label="roles" value={recordedNumber(summary.role_count)} />
          <Stat icon={Building2} label="departments" value={recordedNumber(summary.department_count)} />
          <Stat icon={BriefcaseBusiness} label="recorded mapped roles" value={recordedNumber(summary.active_surface_role_count)} />
          <Stat icon={Workflow} label="work orders" value={recordedNumber(summary.work_order_count)} />
          <Stat icon={ShieldCheck} label="boundaries" value={recordedNumber(summary.authority_boundary_count)} />
          <Stat icon={Network} label="coverage" value={recordedNumber(summary.coverage_percent, "%")} />
          <Stat icon={ListChecks} label="day plans" value={recordedNumber(summary.roles_with_day_plan_count)} />
          <Stat icon={Network} label="whole access" value={recordedNumber(summary.roles_with_whole_organism_access_count)} />
          <Stat icon={BriefcaseBusiness} label="agency roles" value={recordedNumber(summary.agency_workforce_role_count)} />
          <Stat icon={Workflow} label="temp-ready" value={recordedNumber(summary.subcontractor_eligible_role_count)} />
          <Stat icon={Users} label="recruited" value={recordedNumber(summary.recruited_worker_count)} />
          <Stat icon={Network} label="online scans" value={recordedNumber(summary.online_recruitment_search_count)} />
          <Stat icon={Network} label="memory packs" value={recordedNumber(summary.sha256_memory_entry_count)} />
          <Stat icon={Network} label="mycelium map" value={recordedNumber(summary.mycelium_metaphor_count)} />
          <Stat icon={Network} label="bio scale" value={recordedNumber(summary.bio_cosmic_scale_count)} />
        </div>

        <div className="grid min-w-0 grid-cols-1 gap-3 xl:grid-cols-[1.15fr_0.85fr]">
          <div className="rounded-md border border-border/40 bg-muted/10 p-3">
            <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
              <div className="text-sm font-medium">Company Departments</div>
              <Badge variant="outline">CEO to cleaner</Badge>
            </div>
            <div className="overflow-y-auto min-w-0 h-[420px] pr-3">
              <div className="space-y-3">
                {departments.map((department: JsonMap) => {
                  const roles = departmentRoles(report, department.id);
                  return (
                    <div key={department.id} className="rounded-md border border-border/40 bg-background/30 p-3">
                      <div className="flex flex-wrap items-start justify-between gap-2">
                        <div>
                          <div className="text-sm font-medium">{department.title}</div>
                          <div className="mt-1 text-xs text-muted-foreground">{department.mission}</div>
                        </div>
                        <Badge variant="outline">{roles.length} roles</Badge>
                      </div>
                      <div className="mt-3 grid min-w-0 grid-cols-1 gap-2 md:grid-cols-2">
                        {roles.map((role: JsonMap) => (
                          <div key={role.role_id} className="rounded border border-border/30 bg-muted/10 p-2">
                            <div className="flex items-start justify-between gap-2">
                              <div className="min-w-0">
                                <div className="whitespace-normal [overflow-wrap:anywhere] text-xs font-medium">{role.title}</div>
                                <div className="mt-1 line-clamp-2 text-[11px] text-muted-foreground">{role.mission}</div>
                              </div>
                              <Badge variant="outline">{String(role.authority_level || "authority").replace(/_/g, " ")}</Badge>
                            </div>
                            <div className="mt-2 flex flex-wrap gap-1">
                              {(role.capabilities || []).slice(0, 3).map((capability: string) => (
                                <Badge key={capability} variant="outline" className="text-[10px]">
                                  {capability.replace(/_/g, " ")}
                                </Badge>
                              ))}
                            </div>
                            <div className="mt-2 space-y-1 border-t border-border/30 pt-2">
                              {(role.day_to_day || []).slice(0, 2).map((item: string, index: number) => (
                                <div key={`${role.role_id}-day-${index}`} className="line-clamp-2 text-[11px] text-muted-foreground">
                                  {item}
                                </div>
                              ))}
                              <div className="flex flex-wrap gap-1 pt-1">
                                <Badge variant="outline" className="text-[10px]">
                                  access {recordedArrayCount(role.whole_organism_access?.allowed_surfaces)}
                                </Badge>
                                <Badge variant="outline" className="text-[10px]">
                                  checks {recordedArrayCount(role.standing_checks)}
                                </Badge>
                                <Badge variant="outline" className="text-[10px]">
                                  escalates {recordedArrayCount(role.escalation_rules)}
                                </Badge>
                                <Badge variant="outline" className="text-[10px]">
                                  {String(role.workforce_lifecycle?.employment_model || "workforce").replace(/_/g, " ")}
                                </Badge>
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  );
                })}
                {!departments.length ? (
                  <div className="rounded-md border border-border/40 bg-muted/10 p-4 text-sm text-muted-foreground">
                    No department records are present in this report.
                  </div>
                ) : null}
              </div>
            </div>
          </div>

          <div className="space-y-3">
            <div className="rounded-md border border-success/30 bg-success/10 p-3">
              <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                <div className="text-sm font-medium text-success">Mycelium Organisation Ethos</div>
                <Badge variant="outline">
                  {String(myceliumDoctrine.ethos || "waiting").replace(/_/g, " ")}
                </Badge>
              </div>
              <div className="text-[11px] text-muted-foreground">{myceliumDoctrine.one_line || "Waiting for mycelium doctrine."}</div>
              <div className="mt-2 space-y-1">
                {myceliumMap.slice(0, 5).map((item: JsonMap) => (
                  <div key={item.mycelium_part} className="rounded border border-success/20 bg-background/20 px-2 py-1.5">
                    <div className="text-[11px] font-medium">
                      {String(item.mycelium_part || "").replace(/_/g, " ")} {"->"} {item.aureon_part}
                    </div>
                    <div className="mt-0.5 text-[11px] text-muted-foreground">{item.function}</div>
                  </div>
                ))}
              </div>
              <div className="mt-2 grid min-w-0 grid-cols-1 gap-1">
                {myceliumPrinciples.slice(0, 4).map((principle: string) => (
                  <div key={principle} className="rounded border border-success/20 bg-background/15 px-2 py-1 text-[11px] text-muted-foreground">
                    {principle}
                  </div>
                ))}
              </div>
            </div>

            <div className="rounded-md border border-primary/30 bg-primary/10 p-3">
              <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                <div className="text-sm font-medium text-primary">Cells To Stars Doctrine</div>
                <Badge variant="outline">
                  {String(bioCosmicDoctrine.ethos || "waiting").replace(/_/g, " ")}
                </Badge>
              </div>
              <div className="text-[11px] text-muted-foreground">{bioCosmicDoctrine.one_line || "Waiting for living-system doctrine."}</div>
              <div className="mt-2 grid min-w-0 grid-cols-1 gap-1">
                {bioCosmicScale.slice(0, 6).map((item: JsonMap) => (
                  <div key={item.scale} className="rounded border border-primary/20 bg-background/20 px-2 py-1.5">
                    <div className="text-[11px] font-medium">{String(item.scale || "").replace(/_/g, " ")}</div>
                    <div className="mt-0.5 text-[11px] text-muted-foreground">{item.aureon_translation}</div>
                  </div>
                ))}
              </div>
              <div className="mt-2 grid min-w-0 grid-cols-1 gap-1">
                {bioCosmicLaws.slice(0, 4).map((law: string) => (
                  <div key={law} className="rounded border border-primary/20 bg-background/15 px-2 py-1 text-[11px] text-muted-foreground">
                    {law}
                  </div>
                ))}
              </div>
            </div>

            <div className="rounded-md border border-primary/30 bg-primary/10 p-3">
              <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                <div className="text-sm font-medium text-primary">Prompt As Client Job</div>
                <Badge variant="outline">{recordedNumber(summary.agency_lifecycle_step_count)} stages</Badge>
              </div>
              <div className="text-[11px] text-muted-foreground">{agencyModel.analogy || "Waiting for agency model."}</div>
              <div className="mt-2 space-y-2">
                {clientJobLifecycle.map((step: JsonMap) => (
                  <div key={step.step} className="rounded border border-primary/20 bg-background/25 p-2">
                    <div className="flex items-center justify-between gap-2">
                      <div className="text-xs font-medium">{String(step.step || "").replace(/_/g, " ")}</div>
                      <Badge variant="outline" className="text-[10px]">{step.owner}</Badge>
                    </div>
                    <div className="mt-1 text-[11px] text-muted-foreground">{step.action}</div>
                  </div>
                ))}
              </div>
            </div>

            <div className="rounded-md border border-primary/30 bg-primary/10 p-3">
              <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                <div className="text-sm font-medium text-primary">Recruitment Engine</div>
                <Badge variant="outline">
                  {recruitmentEngine.status || "waiting"}
                </Badge>
              </div>
              <div className="grid min-w-0 grid-cols-1 gap-2 md:grid-cols-2">
                <div className="rounded border border-primary/20 bg-background/25 p-2">
                  <div className="text-xs font-medium">Search Stack</div>
                  <div className="mt-1 text-[11px] text-muted-foreground">
                    recorded internal hits {recordedNumber(recruitmentSummary.internal_hit_count)}; online enabled {recordedBoolean(recruitmentSummary.online_enabled)}; status {recruitmentSummary.online_status || "Unavailable"}
                  </div>
                  <div className="mt-2 space-y-1">
                    {onlineSearches.slice(0, 3).map((search: JsonMap) => (
                      <div key={search.id || search.query} className="whitespace-normal [overflow-wrap:anywhere] text-[11px] text-muted-foreground">
                        {search.query} ({recordedNumber(search.result_count)})
                      </div>
                    ))}
                  </div>
                </div>
                <div className="rounded border border-primary/20 bg-background/25 p-2">
                  <div className="text-xs font-medium">Recruited Crew</div>
                  <div className="mt-1 text-[11px] text-muted-foreground">
                    {recordedArrayCount(recruitmentEngine.recruited_workers)} workers; blueprints {recordedNumber(recruitmentSummary.agent_blueprint_count)}
                  </div>
                  <div className="mt-2 flex flex-wrap gap-1">
                    {recruitedWorkers.slice(0, 6).map((worker: JsonMap) => (
                      <Badge key={worker.role_id} variant="outline" className="text-[10px]">
                        {worker.title}
                      </Badge>
                    ))}
                  </div>
                </div>
              </div>
              <div className="mt-2 space-y-1">
                {recruitmentStages.slice(0, 4).map((stage: JsonMap) => (
                  <div key={stage.stage} className="rounded border border-primary/20 bg-background/20 px-2 py-1.5">
                    <div className="text-[11px] font-medium">{String(stage.stage || "").replace(/_/g, " ")}</div>
                    <div className="mt-0.5 text-[11px] text-muted-foreground">{stage.owner}: {stage.action}</div>
                  </div>
                ))}
              </div>
            </div>

            <div className="rounded-md border border-warning/30 bg-warning/10 p-3">
              <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                <div className="text-sm font-medium text-warning">Hire / Retire Crews</div>
                <Badge variant="outline">
                  Recorded ready: {recordedBoolean(summary.temporary_staff_retirement_policy_ready)}
                </Badge>
              </div>
              <div className="space-y-1 text-[11px] text-muted-foreground">
                <div>{retirementPolicy.retire_means || "Waiting for retirement policy."}</div>
                <div>{retirementPolicy.delete_means || ""}</div>
              </div>
            </div>

            <div className="rounded-md border border-primary/30 bg-primary/10 p-3">
              <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                <div className="text-sm font-medium text-primary">Memory Phonebook</div>
                <Badge variant="outline">
                  {recordedNumber(memorySummary.entry_count)} packs
                </Badge>
              </div>
              <div className="space-y-1 text-[11px] text-muted-foreground">
                <div>sha256 addressed: {recordedBoolean(memorySummary.sha256_addressed)}</div>
                <div>zlib compressed: {recordedBoolean(memorySummary.zlib_compressed)}</div>
                <div>compression ratio: {recordedNumber(memorySummary.compression_ratio)}</div>
              </div>
              <div className="mt-2 space-y-1">
                {(memoryPhonebook.entries || []).slice(0, 3).map((entry: JsonMap) => (
                  <div key={entry.archive_key} className="whitespace-normal [overflow-wrap:anywhere] font-mono text-[10px] text-muted-foreground">
                    {entry.role_id} {entry.archive_key}
                  </div>
                ))}
              </div>
            </div>

            <div className="rounded-md border border-primary/30 bg-primary/10 p-3">
              <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                <div className="text-sm font-medium">Daily Operating Loop</div>
                <Badge variant="outline">
                  Recorded ready: {recordedBoolean(summary.daily_operating_loop_ready)}
                </Badge>
              </div>
              <div className="space-y-2">
                {dailyLoop.map((step: JsonMap) => (
                  <div key={step.step} className="rounded border border-primary/20 bg-background/25 p-2">
                    <div className="text-xs font-medium">{String(step.step || "").replace(/_/g, " ")}</div>
                    <div className="mt-1 text-[11px] text-muted-foreground">{step.action}</div>
                  </div>
                ))}
              </div>
            </div>

            <div className="rounded-md border border-primary/30 bg-primary/10 p-3">
              <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                <div className="text-sm font-medium text-primary">Whole Organism Access</div>
                <Badge variant="outline">{recordedArrayCount(accessPolicy.universal_surfaces)} surfaces</Badge>
              </div>
              <div className="text-[11px] text-muted-foreground">{accessPolicy.purpose || "Waiting for access policy."}</div>
              <div className="mt-2 flex flex-wrap gap-1">
                {(accessPolicy.universal_surfaces || []).slice(0, 8).map((surface: string) => (
                  <Badge key={surface} variant="outline" className="text-[10px]">
                    {surface}
                  </Badge>
                ))}
              </div>
            </div>

            <div className="rounded-md border border-success/30 bg-success/10 p-3">
              <div className="mb-2 text-sm font-medium text-success">Authority Boundaries</div>
              <div className="space-y-2">
                {boundaries.map((boundary: JsonMap) => (
                  <div key={boundary.id} className="rounded border border-success/20 bg-background/25 p-2">
                    <div className="text-xs font-medium">{boundary.title}</div>
                    <div className="mt-1 text-[11px] text-muted-foreground">{boundary.rule}</div>
                  </div>
                ))}
              </div>
            </div>

            <div className="rounded-md border border-border/40 bg-muted/10 p-3">
              <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                <div className="text-sm font-medium">Capability Coverage</div>
                <Badge variant="outline">{recordedArrayCount(report.capability_coverage)} recorded entries</Badge>
              </div>
              <div className="space-y-2">
                {coverage.slice(0, 8).map((item: JsonMap) => (
                  <div key={item.id} className="flex items-center justify-between gap-2 rounded border border-border/30 bg-background/25 px-2 py-1.5">
                    <span className="whitespace-normal [overflow-wrap:anywhere] text-xs">{item.title}</span>
                    <Badge variant="outline">{recordedNumber(item.mapped_role_count)}</Badge>
                  </div>
                ))}
              </div>
            </div>

            <div className="rounded-md border border-warning/30 bg-warning/10 p-3">
              <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                <div className="text-sm font-medium text-warning">Work Orders</div>
                <Badge variant="outline">{workOrders.length}</Badge>
              </div>
              <div className="space-y-2">
                {topWorkOrders.map((order: JsonMap) => (
                  <div key={order.id} className="rounded border border-warning/20 bg-background/25 p-2">
                    <div className="text-xs font-medium">{order.title}</div>
                    <div className="mt-1 text-[11px] text-muted-foreground">{order.exact_aureon_prompt}</div>
                  </div>
                ))}
                {!topWorkOrders.length ? <div className="text-xs text-muted-foreground">No work orders are recorded in this report; this does not establish complete role coverage.</div> : null}
              </div>
            </div>

            <div className="rounded-md border border-border/40 bg-muted/10 p-3">
              <div className="mb-2 text-sm font-medium">Handoff Map</div>
              <div className="grid min-w-0 grid-cols-1 gap-1">
                {handoffMap.slice(0, 8).map((handoff: JsonMap, index: number) => (
                  <div key={`${handoff.from}-${handoff.to}-${index}`} className="whitespace-normal [overflow-wrap:anywhere] font-mono text-[11px] text-muted-foreground">
                    {handoff.from} {"->"} {handoff.to}
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
    </GeneratedReportBoundary>
    </div>
  );
}

function Stat({ icon: Icon, label, value }: { icon: LucideIcon; label: string; value: string | number }) {
  return (
    <div className="rounded-md border border-border/40 bg-muted/10 p-3">
      <div className="mb-2 flex items-center gap-2 text-xs text-muted-foreground">
        <Icon className="h-3.5 w-3.5" />
        {label}
      </div>
      <div className="text-lg font-semibold">{value}</div>
    </div>
  );
}
