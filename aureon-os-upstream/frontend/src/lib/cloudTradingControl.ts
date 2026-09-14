import { api } from '@/services/apiClient';

export const CLOUD_TRADE_CONTROL_IDS = [
  'AUREON_DEPLOYMENT_HOLD',
  'AUREON_DISABLE_REAL_ORDERS',
  'AUREON_DISABLE_EXCHANGE_MUTATIONS',
  'AUREON_LIVE_TRADING',
  'AUREON_ORDER_INTENT_PUBLISH',
  'AUREON_UNIFIED_ORDER_EXECUTOR',
] as const;

export type CloudTradeControlId = typeof CLOUD_TRADE_CONTROL_IDS[number];
export type CloudTradeControls = Record<CloudTradeControlId, boolean>;

export interface CloudTradingProbe {
  intent_id: string;
  receipt_sha256: string;
  source_revision: string;
  runtime_measurement_sha256: string;
  received_at: number;
  age_seconds: number;
  current: boolean;
  chain_verified: true;
  authority_ids: Record<'review' | 'dispatch' | 'executor' | 'receipt', string>;
  key_versions: Record<'review' | 'dispatch' | 'executor' | 'receipt', string>;
  provider_mutation_attempted: false;
  orders_attempted: 0;
  orders_submitted: 0;
  executor_capabilities: {
    live_execution_release: boolean;
    durable_budget_ledger: boolean;
    order_adapter_ready: boolean;
    live_result_binding_ready: boolean;
    instrument_preflight_enforced: boolean;
  } | null;
  provider_readback: {
    provider_count: 4;
    all_authenticated: true;
    instrument_preflight_enforced: true;
    provider_accounts_sha256: string;
    execution_budget_readiness_sha256: string;
    readback_sha256: string;
    providers: Record<'alpaca' | 'binance' | 'capital' | 'kraken', { authenticated: true; account_binding_sha256: string }>;
  } | null;
}

export interface CloudOrderIntentBridge {
  schema: 'aureon.cloud-order-intent-bridge-status.v1';
  observed_at: number;
  revision: string;
  state: 'blocked' | 'idle' | 'published' | 'publish_outcome_unknown';
  operational: boolean;
  candidate_ready: boolean;
  blockers: string[];
  source: {
    runtime_status_sha256: string;
    generated_at_ms: number;
    age_ms: number;
  } | null;
  controller_release: {
    state: 'active';
    generation: number;
    request_id: string;
    source_revision: string;
    authorization_event_sha256: string;
    authorization_expires_at_ms: number;
  } | null;
  last_publish: {
    topic: string;
    intent_id: string;
    client_order_id: string;
    intent_sha256: string;
    market_evidence_sha256: string;
    venue: 'alpaca' | 'binance' | 'capital' | 'kraken';
    symbol: string;
    side: 'BUY' | 'SELL';
    quote_value_usd: number;
    pubsub_message_id: string;
    published_at_ms: number;
  } | null;
  release_authority: boolean;
  mutation_authority: false;
}

export interface CloudTradingControlReceipt {
  schema: 'aureon.operator.cloud-trading-control.v1';
  observed_at: number;
  truth_status: 'real_derived' | 'unavailable';
  read_state: 'observed' | 'recorded' | 'unavailable';
  operator_can_request_controls: boolean;
  operator_can_apply_live: boolean;
  requested_controls: CloudTradeControls;
  effective_controls: CloudTradeControls;
  desired_live_state: boolean;
  authorization: {
    active: boolean;
    state: string;
    expires_at_iso: string | null;
    ledger_event_sha256: string | null;
    release_authority: boolean;
    mutation_authority: false;
  };
  capabilities: Record<string, boolean>;
  last_probe: CloudTradingProbe | null;
  controller_release: {
    schema: 'aureon.cloud-trade-release-state.v1';
    state: 'active' | 'held';
    generation: number;
    request_id: string;
    authorization_expires_at_ms: number;
    signed_at_ms: number;
    source_revision: string;
    controller_key_version: string;
  } | null;
  intent_bridge: CloudOrderIntentBridge | null;
  blockers: string[];
  production_ready: boolean;
  release_authority: boolean;
  mutation_authority: false;
  digest_sha256: string;
  digest_scope: 'operator_cloud_trading_control';
}

const record = (value: unknown): Record<string, unknown> | null => value !== null && typeof value === 'object' && !Array.isArray(value)
  ? value as Record<string, unknown> : null;
const hex64 = (value: unknown): value is string => typeof value === 'string' && /^[a-f0-9]{64}$/.test(value);

function controls(value: unknown): value is CloudTradeControls {
  const raw = record(value);
  return raw !== null && Object.keys(raw).length === CLOUD_TRADE_CONTROL_IDS.length
    && CLOUD_TRADE_CONTROL_IDS.every(key => typeof raw[key] === 'boolean');
}

function stageMap(value: unknown): value is CloudTradingProbe['authority_ids'] {
  const raw = record(value);
  const stages = ['review', 'dispatch', 'executor', 'receipt'] as const;
  return raw !== null && Object.keys(raw).length === stages.length
    && stages.every(stage => typeof raw[stage] === 'string' && raw[stage].length > 0);
}

function probe(value: unknown): value is CloudTradingProbe {
  const raw = record(value);
  const executor = record(raw?.executor_capabilities);
  const provider = record(raw?.provider_readback);
  const providers = record(provider?.providers);
  const providerNames = ['alpaca', 'binance', 'capital', 'kraken'] as const;
  const executorValid = executor === null || (Object.keys(executor).length === 5
    && ['live_execution_release', 'durable_budget_ledger', 'order_adapter_ready', 'live_result_binding_ready', 'instrument_preflight_enforced']
      .every(key => typeof executor[key] === 'boolean'));
  const providerValid = provider === null || (Object.keys(provider).length === 7
    && provider.provider_count === 4 && provider.all_authenticated === true
    && provider.instrument_preflight_enforced === true
    && hex64(provider.provider_accounts_sha256) && hex64(provider.execution_budget_readiness_sha256)
    && hex64(provider.readback_sha256) && providers !== null && Object.keys(providers).length === 4
    && providerNames.every(name => {
      const row = record(providers[name]);
      return row !== null && Object.keys(row).length === 2
        && row.authenticated === true && hex64(row.account_binding_sha256);
    }));
  return raw !== null && hex64(raw.intent_id) && hex64(raw.receipt_sha256)
    && typeof raw.source_revision === 'string' && /^[a-f0-9]{40,64}$/.test(raw.source_revision)
    && hex64(raw.runtime_measurement_sha256)
    && typeof raw.received_at === 'number' && Number.isFinite(raw.received_at)
    && typeof raw.age_seconds === 'number' && Number.isFinite(raw.age_seconds)
    && typeof raw.current === 'boolean' && raw.chain_verified === true
    && stageMap(raw.authority_ids) && stageMap(raw.key_versions)
    && new Set(Object.values(raw.authority_ids)).size === 4
    && new Set(Object.values(raw.key_versions)).size === 4
    && raw.provider_mutation_attempted === false
    && raw.orders_attempted === 0 && raw.orders_submitted === 0
    && executorValid && providerValid;
}

function intentBridge(value: unknown): value is CloudOrderIntentBridge | null {
  if (value === null) return true;
  const raw = record(value);
  const source = record(raw?.source);
  const release = record(raw?.controller_release);
  const published = record(raw?.last_publish);
  const sourceValid = source === null || (hex64(source.runtime_status_sha256)
    && typeof source.generated_at_ms === 'number' && Number.isSafeInteger(source.generated_at_ms)
    && typeof source.age_ms === 'number' && Number.isSafeInteger(source.age_ms));
  const releaseValid = release === null || (release.state === 'active'
    && typeof release.generation === 'number' && Number.isSafeInteger(release.generation) && release.generation > 0
    && hex64(release.request_id) && typeof release.source_revision === 'string'
    && /^[a-f0-9]{40,64}$/.test(release.source_revision)
    && hex64(release.authorization_event_sha256)
    && typeof release.authorization_expires_at_ms === 'number' && Number.isSafeInteger(release.authorization_expires_at_ms));
  const publishValid = published === null || (published.topic === 'projects/aureon-trading/topics/aureon-trade-intents-v1'
    && ['intent_id', 'client_order_id', 'intent_sha256', 'market_evidence_sha256'].every(key => hex64(published[key]))
    && ['alpaca', 'binance', 'capital', 'kraken'].includes(String(published.venue))
    && typeof published.symbol === 'string' && /^[A-Z0-9][A-Z0-9./_-]{1,31}$/.test(published.symbol)
    && (published.side === 'BUY' || published.side === 'SELL')
    && typeof published.quote_value_usd === 'number' && Number.isFinite(published.quote_value_usd)
    && published.quote_value_usd > 0 && published.quote_value_usd <= 5
    && typeof published.pubsub_message_id === 'string' && /^[0-9]{1,64}$/.test(published.pubsub_message_id)
    && typeof published.published_at_ms === 'number' && Number.isSafeInteger(published.published_at_ms));
  return raw !== null && raw.schema === 'aureon.cloud-order-intent-bridge-status.v1'
    && typeof raw.observed_at === 'number' && Number.isFinite(raw.observed_at)
    && typeof raw.revision === 'string' && /^[a-f0-9]{40,64}$/.test(raw.revision)
    && ['blocked', 'idle', 'published', 'publish_outcome_unknown'].includes(String(raw.state))
    && typeof raw.operational === 'boolean' && typeof raw.candidate_ready === 'boolean'
    && Array.isArray(raw.blockers) && raw.blockers.every(item => typeof item === 'string' && item.length > 0)
    && sourceValid && releaseValid && publishValid
    && typeof raw.release_authority === 'boolean' && raw.mutation_authority === false
    && (raw.release_authority === (release !== null))
    && (raw.state !== 'published' || (raw.operational === true && raw.candidate_ready === true && published !== null));
}

function controllerRelease(value: unknown): boolean {
  if (value === null) return true;
  const raw = record(value);
  return raw !== null && raw.schema === 'aureon.cloud-trade-release-state.v1'
    && (raw.state === 'active' || raw.state === 'held')
    && typeof raw.generation === 'number' && Number.isSafeInteger(raw.generation) && raw.generation > 0
    && hex64(raw.request_id)
    && typeof raw.authorization_expires_at_ms === 'number' && Number.isSafeInteger(raw.authorization_expires_at_ms)
    && typeof raw.signed_at_ms === 'number' && Number.isSafeInteger(raw.signed_at_ms)
    && typeof raw.source_revision === 'string' && /^[a-f0-9]{40,64}$/.test(raw.source_revision)
    && typeof raw.controller_key_version === 'string'
    && /^[A-Za-z0-9._:/-]{3,512}$/.test(raw.controller_key_version);
}

export function readCloudTradingControl(value: unknown): CloudTradingControlReceipt {
  const raw = record(value);
  const authorization = record(raw?.authorization);
  const capabilities = record(raw?.capabilities);
  const readStates = new Set(['observed', 'recorded', 'unavailable']);
  if (!raw || raw.schema !== 'aureon.operator.cloud-trading-control.v1'
    || typeof raw.observed_at !== 'number' || !Number.isFinite(raw.observed_at)
    || !['real_derived', 'unavailable'].includes(String(raw.truth_status))
    || !readStates.has(String(raw.read_state))
    || typeof raw.operator_can_request_controls !== 'boolean'
    || typeof raw.operator_can_apply_live !== 'boolean'
    || !controls(raw.requested_controls) || !controls(raw.effective_controls)
    || typeof raw.desired_live_state !== 'boolean'
    || !authorization || typeof authorization.active !== 'boolean' || typeof authorization.state !== 'string'
    || !(authorization.expires_at_iso === null || typeof authorization.expires_at_iso === 'string')
    || !(authorization.ledger_event_sha256 === null || hex64(authorization.ledger_event_sha256))
    || typeof authorization.release_authority !== 'boolean' || authorization.mutation_authority !== false
    || !capabilities || Object.values(capabilities).some(item => typeof item !== 'boolean')
    || !(raw.last_probe === null || probe(raw.last_probe))
    || !controllerRelease(raw.controller_release)
    || !intentBridge(raw.intent_bridge)
    || !Array.isArray(raw.blockers) || raw.blockers.some(item => typeof item !== 'string' || !/^[a-z0-9_]+$/.test(item))
    || typeof raw.production_ready !== 'boolean'
    || typeof raw.release_authority !== 'boolean' || raw.mutation_authority !== false
    || !hex64(raw.digest_sha256) || raw.digest_scope !== 'operator_cloud_trading_control') {
    throw new Error('Cloud trading control evidence unavailable');
  }
  const release = record(raw.controller_release);
  const bridge = record(raw.intent_bridge);
  const lastProbe = record(raw.last_probe);
  if ((raw.production_ready && (!raw.operator_can_apply_live || raw.blockers.length > 0 || raw.release_authority !== true))
    || authorization.release_authority !== raw.release_authority
    || (raw.release_authority && release?.state !== 'active')
    || (raw.production_ready && (lastProbe === null || lastProbe.current !== true
      || lastProbe.provider_readback === null || bridge?.operational !== true
      || bridge?.release_authority !== true))) {
    throw new Error('Cloud trading control evidence inconsistent');
  }
  return raw as unknown as CloudTradingControlReceipt;
}

export function cloudTradingBlockerLabel(value: string): string {
  return value.replace(/^operator_/, '').replace(/_/g, ' ');
}

export const APPLY_CLOUD_LIVE_CONFIRM = 'APPLY_AUREON_CLOUD_LIVE_TRADING';
export const HOLD_CLOUD_LIVE_CONFIRM = 'HOLD_AUREON_CLOUD_LIVE_TRADING';

export async function requestCloudTradingRelease(action: 'activate' | 'hold'): Promise<{ request_id: string }> {
  const response = await api.post<{ ok?: boolean; request?: { request_id?: unknown } }>(
    '/api/operator/cloud-trading-control/apply',
    { action, confirm: action === 'activate' ? APPLY_CLOUD_LIVE_CONFIRM : HOLD_CLOUD_LIVE_CONFIRM },
  );
  const requestId = response.request?.request_id;
  if (response.ok !== true || !hex64(requestId)) throw new Error('Cloud trading release request was not accepted');
  return { request_id: requestId };
}
