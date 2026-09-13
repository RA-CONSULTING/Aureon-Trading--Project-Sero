export const GOVERNED_ORDER_ACTION_UNAVAILABLE_CODE = 'GOVERNED_ORDER_REVIEW_DISPATCH_CLIENT_UNAVAILABLE' as const;

export const GOVERNED_ORDER_ACTION_UNAVAILABLE_MESSAGE =
  'Order action unavailable: this surface has no typed governed Cloud Run review and dispatch client.';

export interface UnavailableTradingAction {
  available: false;
  code: typeof GOVERNED_ORDER_ACTION_UNAVAILABLE_CODE;
  message: typeof GOVERNED_ORDER_ACTION_UNAVAILABLE_MESSAGE;
  action: string;
  scope: 'analysis_only';
  tenant_runtime_authority: false;
  provider_mutation_attempted: false;
}

export function unavailableTradingAction(action: string): UnavailableTradingAction {
  return {
    available: false,
    code: GOVERNED_ORDER_ACTION_UNAVAILABLE_CODE,
    message: GOVERNED_ORDER_ACTION_UNAVAILABLE_MESSAGE,
    action,
    scope: 'analysis_only',
    tenant_runtime_authority: false,
    provider_mutation_attempted: false,
  };
}
