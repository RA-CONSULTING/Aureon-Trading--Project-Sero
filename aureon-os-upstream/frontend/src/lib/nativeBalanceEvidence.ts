import { readProviderObservation, type ProviderObservation } from './providerObservations';
import { evidenceNumber, evidenceRecord, evidenceText } from './warRoomEvidence';

const PROVIDERS = [
  { id: 'capital', name: 'Capital.com', source: 'capital:GET /accounts', kind: null, metric: 'Account balance' },
  { id: 'alpaca', name: 'Alpaca', source: 'alpaca:GET /v2/account', kind: 'equity', metric: 'Equity' },
  { id: 'binance', name: 'Binance', source: 'binance:GET /api/v3/account', kind: 'free_plus_locked', metric: 'Total (free + locked)' },
  { id: 'kraken', name: 'Kraken', source: 'kraken:POST /0/private/Balance', kind: 'total_asset_balance', metric: 'Total asset balance' },
] as const;

export type NativeBalanceRow = {
  key: string; balance: number | null; available: number | null; cash: number | null;
  buyingPower: number | null; locked: number | null; reason: string | null;
};
export type NativeBalanceGroup = {
  key: string; currency: string; metric: string; rows: NativeBalanceRow[];
};
export type NativeProviderBalances = {
  id: string; name: string; observation: ProviderObservation;
  visible: NativeBalanceGroup[]; zeros: NativeBalanceGroup[]; zeroCount: number;
};

/** Existing native receipts only: never infer currency aliases, FX or portfolio equity. */
export function readNativeBalanceEvidence(value: unknown, connected: boolean, nowMs = Date.now()): NativeProviderBalances[] {
  const providers = evidenceRecord(value);
  return PROVIDERS.map(provider => {
    const raw = evidenceRecord(evidenceRecord(providers[provider.id]).accounts);
    let observation = readProviderObservation(raw, connected, nowMs);
    if (observation.available && (raw.provider !== provider.id || raw.kind !== 'accounts' || raw.source !== provider.source)) {
      observation = { ...observation, available: false, reason: 'Provider account source does not match', rows: [], count: null, inventoryComplete: null };
    }
    const visible = new Map<string, NativeBalanceGroup>();
    const zeros = new Map<string, NativeBalanceGroup>();
    let zeroCount = 0;
    observation.rows.forEach((row, index) => {
      const currency = evidenceText(row.currency);
      const metricMatches = (evidenceText(row.balance_kind) ?? null) === provider.kind;
      const qualified = Boolean(currency) && metricMatches;
      const metric = metricMatches ? provider.metric : 'Balance metric unavailable';
      const read = (field: string) => qualified ? evidenceNumber(row[field]) : null;
      const balance: NativeBalanceRow = {
        key: `${index}:${evidenceText(row.reference) ?? 'unreported'}`,
        balance: read('balance'), available: read('available'), cash: read('cash'),
        buyingPower: read('buying_power'), locked: read('locked'),
        reason: !currency ? 'Currency unavailable' : !metricMatches ? 'Provider balance metric is unqualified' : null,
      };
      const isZero = balance.balance === 0 && [balance.available, balance.cash, balance.buyingPower, balance.locked]
        .every(amount => amount === null || amount === 0);
      if (isZero) zeroCount += 1;
      const groups = isZero ? zeros : visible;
      const key = JSON.stringify([currency, metric]);
      const group = groups.get(key) ?? { key, currency: currency ?? 'Currency unavailable', metric, rows: [] };
      group.rows.push(balance);
      groups.set(key, group);
    });
    const ordered = (groups: Map<string, NativeBalanceGroup>) => [...groups.values()]
      .sort((a, b) => a.currency.localeCompare(b.currency) || a.metric.localeCompare(b.metric));
    return { id: provider.id, name: provider.name, observation, visible: ordered(visible), zeros: ordered(zeros), zeroCount };
  });
}
