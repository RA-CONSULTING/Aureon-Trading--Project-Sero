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
  } | null;
  provider_readback: {
    provider_count: 4;
    all_authenticated: true;
    readback_sha256: string;
    providers: Record<'alpaca' | 'binance' | 'capital' | 'kraken', { authenticated: true; account_binding_sha256: string }>;
  } | null;
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
    release_authority: false;
    mutation_authority: false;
  };
  capabilities: Record<string, boolean>;
  last_probe: CloudTradingProbe | null;
  blockers: string[];
  production_ready: boolean;
  release_authority: false;
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
  const executorValid = executor === null || (Object.keys(executor).length === 3
    && ['live_execution_release', 'durable_budget_ledger', 'order_adapter_ready'].every(key => typeof executor[key] === 'boolean'));
  const providerValid = provider === null || (provider.provider_count === 4 && provider.all_authenticated === true
    && hex64(provider.readback_sha256) && providers !== null && Object.keys(providers).length === 4
    && providerNames.every(name => {
      const row = record(providers[name]);
      return row?.authenticated === true && hex64(row.account_binding_sha256);
    }));
  return raw !== null && hex64(raw.intent_id) && hex64(raw.receipt_sha256)
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
    || authorization.release_authority !== false || authorization.mutation_authority !== false
    || !capabilities || Object.values(capabilities).some(item => typeof item !== 'boolean')
    || !(raw.last_probe === null || probe(raw.last_probe))
    || !Array.isArray(raw.blockers) || raw.blockers.some(item => typeof item !== 'string' || !/^[a-z0-9_]+$/.test(item))
    || typeof raw.production_ready !== 'boolean'
    || raw.release_authority !== false || raw.mutation_authority !== false
    || !hex64(raw.digest_sha256) || raw.digest_scope !== 'operator_cloud_trading_control') {
    throw new Error('Cloud trading control evidence unavailable');
  }
  if (raw.operator_can_apply_live !== raw.production_ready || (raw.operator_can_apply_live && raw.blockers.length > 0)) {
    throw new Error('Cloud trading control evidence inconsistent');
  }
  return raw as unknown as CloudTradingControlReceipt;
}

export function cloudTradingBlockerLabel(value: string): string {
  return value.replace(/^operator_/, '').replace(/_/g, ' ');
}
