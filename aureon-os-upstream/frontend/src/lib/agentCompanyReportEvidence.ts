import { z } from 'zod';
import { recordedReportEvidence } from './recordedReportEvidence';

export const AGENT_COMPANY_SOURCE = '/aureon_agent_company_bill_list.json';
const text = z.string();
const texts = z.array(text);
const object = <T extends z.ZodRawShape>(shape: T) => z.object(shape).passthrough();
const rows = z.array(object({
  id: text.optional(), title: text.optional(), mission: text.optional(), rule: text.optional(), query: text.optional(),
  action: text.optional(), owner: text.optional(), from: text.optional(), to: text.optional(),
  exact_aureon_prompt: text.optional(), aureon_part: text.optional(), function: text.optional(),
  aureon_translation: text.optional(), role_id: text.optional(), archive_key: text.optional(),
}));
const reportSchema = object({
  generated_at: text, status: text.optional(), summary: object({ registry_mode: text.optional() }),
  departments: z.array(object({ id: text, title: text, mission: text.optional() })),
  roles: z.array(object({ role_id: text, department: text, title: text, mission: text.optional(),
    capabilities: texts.optional(), day_to_day: texts.optional(), standing_checks: texts.optional(),
    escalation_rules: texts.optional(), work_orders: z.array(z.unknown()).optional(),
    whole_organism_access: object({ allowed_surfaces: texts.optional() }).optional(),
  })),
  work_orders: rows, authority_boundaries: rows.optional(), capability_coverage: rows.optional(),
  handoff_map: rows.optional(), daily_operating_loop: rows.optional(), prompt_client_job_lifecycle: rows.optional(),
  whole_organism_access_policy: object({ universal_surfaces: texts.optional(), purpose: text.optional() }).optional(),
  mycelium_organisation_doctrine: object({ metaphor_map: rows.optional(), operating_principles: texts.optional(), ethos: text.optional(), one_line: text.optional() }).optional(),
  bio_cosmic_organisation_doctrine: object({ scale_ladder: rows.optional(), operating_laws: texts.optional(), ethos: text.optional(), one_line: text.optional() }).optional(),
  agency_operating_model: object({ analogy: text.optional() }).optional(),
  subcontractor_retirement_policy: object({ retire_means: text.optional(), delete_means: text.optional() }).optional(),
  workforce_memory_phonebook: object({ entries: rows.optional(), summary: z.record(z.unknown()).optional() }).optional(),
  recruitment_engine: object({ recruited_workers: rows.optional(), stage_flow: rows.optional(),
    status: text.optional(), summary: object({ online_status: text.optional() }).optional(), online_skill_searches: object({ searches: rows.optional() }).optional() }).optional(),
});

export function readAgentCompanyReport(value: unknown, now = Date.now()): Record<string, unknown> | null {
  return recordedReportEvidence(value, now).current && reportSchema.safeParse(value).success
    ? value as Record<string, unknown> : null;
}
