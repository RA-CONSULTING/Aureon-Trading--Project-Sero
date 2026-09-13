import { evidenceNumber, evidenceRecord, evidenceText } from './warRoomEvidence';
import { readProviderObservation, type ProviderObservation } from './providerObservations';

export const ORCA_OPERATOR_SCHEMA = 'aureon.operator.orca-observations.v2';
export const ORCA_READER_SCHEMA = ORCA_OPERATOR_SCHEMA;
export const ORCA_POSITION_PROVIDERS = ['capital', 'alpaca', 'kraken', 'binance'] as const;
export type OrcaPositionProvider = typeof ORCA_POSITION_PROVIDERS[number];
export type OrcaReaderEvidence = {
  contractAvailable: boolean;
  positions: Record<OrcaPositionProvider, ProviderObservation>;
};

const POSITION_SOURCES: Partial<Record<OrcaPositionProvider, string>> = {
  capital: 'capital:GET /positions',
  alpaca: 'alpaca:GET /v2/positions',
};

/** Only the operator's saved, sanitized terminal-state receipt can establish position evidence. */
export function readOrcaReaderEvidence(payload: unknown, transportOk: boolean, nowMs = Date.now()): OrcaReaderEvidence {
  const raw = evidenceRecord(payload);
  const contractAvailable = transportOk && raw.schema_version === ORCA_READER_SCHEMA
    && raw.service === 'aureon_operator'
    && raw.scope === 'terminal_state_sanitized_provider_position_receipts'
    && raw.provider_calls === false && raw.mutation_authority === false;
  const providers = evidenceRecord(raw.provider_positions);
  const positions = Object.fromEntries(ORCA_POSITION_PROVIDERS.map((provider) => {
    const value = evidenceRecord(providers[provider]);
    const expectedSource = POSITION_SOURCES[provider] ?? null;
    const observation = readProviderObservation(value, contractAvailable, nowMs);
    const validRows = observation.rows.every((row) => !!evidenceText(row.symbol)
      && (evidenceNumber(row.quantity) ?? 0) > 0 && (evidenceNumber(row.entry_price) ?? 0) > 0);
    const validContract = value.provider === provider && value.kind === 'positions'
      && expectedSource !== null && observation.source === expectedSource
      && ['provider_http_date', 'local_http_receipt'].includes(observation.timestampKind ?? '')
      && typeof value.inventory_complete === 'boolean' && validRows;
    if (observation.available && !validContract) {
      return [provider, { ...observation, available: false, reason: 'Native position provenance or rows unavailable',
        rows: [], count: null, inventoryComplete: null }];
    }
    return [provider, observation];
  })) as OrcaReaderEvidence['positions'];
  return { contractAvailable, positions };
}
