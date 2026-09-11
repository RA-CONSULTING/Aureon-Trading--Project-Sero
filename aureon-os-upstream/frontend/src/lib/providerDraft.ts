import { ApiError } from '../services/apiClient';

export interface ProviderDraft {
  apiKey: string; model: string; baseUrl: string; show: boolean; testing: boolean; saving: boolean;
}
export interface ProviderDefaults { model?: unknown; default_model?: unknown; base_url?: unknown; default_base_url?: unknown }
const text = (value: unknown) => typeof value === 'string' ? value : '';
/** A patch to an unseeded/reset draft must still produce every controlled field. */
export function normalizeProviderDraft(provider: ProviderDefaults, draft?: Partial<ProviderDraft>): ProviderDraft {
  return {
    apiKey: text(draft?.apiKey),
    model: typeof draft?.model === 'string' ? draft.model : text(provider.model) || text(provider.default_model),
    baseUrl: typeof draft?.baseUrl === 'string' ? draft.baseUrl : text(provider.base_url) || text(provider.default_base_url),
    show: draft?.show === true, testing: draft?.testing === true, saving: draft?.saving === true,
  };
}
export function providerRequestBody(draft: ProviderDraft): Record<string, unknown> {
  const body: Record<string, unknown> = { model: draft.model, base_url: draft.baseUrl };
  if (draft.apiKey.trim()) body.api_key = draft.apiKey.trim();
  return body;
}
/** Keep actionable server errors without echoing an entered credential. */
export function providerErrorDetail(error: unknown, enteredKey = ''): string {
  let detail = error instanceof Error ? error.message : typeof error === 'string' ? error : 'No completed test receipt was returned.';
  const key = enteredKey.trim();
  if (key) detail = detail.split(key).join('[redacted]');
  detail = detail.replace(/Bearer\s+[^\s,;"']+/gi, 'Bearer [redacted]')
    .replace(/((?:api[_-]?key|token|authorization)\s*[=:]\s*)[^\s,;&"']+/gi, '$1[redacted]')
    .replace(/(https?:\/\/)[^\s/@]+:[^\s/@]+@/gi, '$1[redacted]@')
    .replace(/[\r\n\t]+/g, ' ').slice(0, 400);
  if (error instanceof ApiError && error.status > 0) return `HTTP ${error.status}: ${detail}`;
  return detail;
}
