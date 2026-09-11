import { evidenceNumber, evidenceRecord, evidenceText } from './warRoomEvidence';
import { readProviderObservation, type ProviderObservation } from './providerObservations';

export const ORCA_READER_SCHEMA = 'orca-reader-observations-v1';
export type OrcaReaderEvidence = {
  contractAvailable: boolean;
  positions: Record<'alpaca' | 'kraken', ProviderObservation>;
  componentImports: { name: string; imported: boolean }[];
};

/** Only the Orca collector's saved native receipt can establish position evidence. */
export function readOrcaReaderEvidence(payload: unknown, transportOk: boolean, nowMs = Date.now()): OrcaReaderEvidence {
  const raw = evidenceRecord(payload);
  const contractAvailable = transportOk && raw.schema_version === ORCA_READER_SCHEMA
    && raw.service === 'orca_command_center' && raw.scope === 'existing_orca_reader_provider_receipts';
  const providers = evidenceRecord(raw.provider_positions);
  const positions = Object.fromEntries((['alpaca', 'kraken'] as const).map((provider) => {
    const value = evidenceRecord(providers[provider]);
    const expectedSource = provider === 'alpaca' ? 'alpaca:GET /v2/positions' : null;
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
  return { contractAvailable, positions,
    componentImports: contractAvailable ? Object.entries(evidenceRecord(raw.component_imports))
      .filter((entry): entry is [string, boolean] => typeof entry[1] === 'boolean')
      .map(([name, imported]) => ({ name, imported })) : [] };
}
