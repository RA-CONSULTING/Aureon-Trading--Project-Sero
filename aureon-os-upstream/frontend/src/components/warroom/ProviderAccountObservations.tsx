import type { useTerminalState } from '@/hooks/useTerminalState';
import { evidenceNumber, evidenceRecord, evidenceText, type EvidenceRecord } from '@/lib/warRoomEvidence';
import { readProviderObservation, type ProviderObservation } from '@/lib/providerObservations';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';

const PROVIDERS = [['capital', 'Capital.com'], ['kraken', 'Kraken'], ['alpaca', 'Alpaca'], ['binance', 'Binance']] as const;
const POSITION_LABELS: Record<string, string> = { entry_price: 'Entry', current_price: 'Mark' };
const format = (value: unknown) => evidenceNumber(value)?.toLocaleString(undefined, { maximumFractionDigits: 8 }) ?? 'Unavailable';
const BALANCE_LABELS: Record<string, string> = {
  free_plus_locked: 'total (free + locked)', total_asset_balance: 'total asset balance', equity: 'equity',
};

const hasNonzeroAmount = (row: EvidenceRecord) =>
  ['balance', 'available', 'cash', 'buying_power', 'locked'].some(field => {
    const value = evidenceNumber(row[field]);
    return value !== null && value !== 0;
  });

function AccountRows({ rows, label }: { rows: EvidenceRecord[]; label: string }) {
  return <div className="max-h-48 overflow-y-auto space-y-2 pr-2" role="region" aria-label={label} tabIndex={0}>
    {rows.map((row, index) => <div key={evidenceText(row.reference) ?? index} className="text-sm flex flex-wrap justify-between gap-2">
      <span>{evidenceText(row.currency) ?? 'Currency unavailable'} {BALANCE_LABELS[evidenceText(row.balance_kind) ?? ''] ?? 'balance'} {format(row.balance)}</span>
      <span className="text-muted-foreground">Available {format(row.available)}</span>
      {evidenceNumber(row.cash) !== null ? <span className="text-muted-foreground">Cash {format(row.cash)}</span> : null}
      {evidenceNumber(row.buying_power) !== null ? <span className="text-muted-foreground">Buying power {format(row.buying_power)}</span> : null}
    </div>)}
  </div>;
}

function PositionRow({ row }: { row: EvidenceRecord }) {
  const symbol = evidenceText(row.symbol) ?? 'Symbol unavailable';
  const side = evidenceText(row.side) ?? 'Side unavailable';
  const quantity = format(row.quantity);
  const pnl = evidenceNumber(row.pnl);
  const pnlPercent = evidenceNumber(row.pnlPercent ?? row.pnl_percent);
  return <div className="rounded bg-muted/30 p-2 text-sm">
    <p>{symbol} · {side} · Qty {quantity}</p>
    <p className="text-xs text-muted-foreground">
      {POSITION_LABELS.entry_price} {format(row.entry_price)} · {POSITION_LABELS.current_price} {format(row.current_price)}
      {pnl !== null ? <span className={pnl >= 0 ? ' text-success' : ' text-destructive'}> · P&L {pnl >= 0 ? '+' : ''}{pnl.toLocaleString(undefined, { maximumFractionDigits: 2 })}</span> : null}
      {pnlPercent !== null ? <span className={pnlPercent >= 0 ? ' text-success' : ' text-destructive'}> ({pnlPercent >= 0 ? '+' : ''}{pnlPercent.toFixed(2)}%)</span> : null}
    </p>
  </div>;
}

function AccountBalances({ observation, providerName }: { observation: ProviderObservation; providerName: string }) {
  if (!observation.available) return <p className="text-xs text-muted-foreground mt-1">{observation.reason}</p>;
  // Preserve every original row. Unknown amounts stay visible, and a nonzero
  // cash/available value must not disappear into the zero-balance section.
  const nonzero = observation.rows.filter(hasNonzeroAmount);
  const unknown = observation.rows.filter(row => !hasNonzeroAmount(row) && evidenceNumber(row.balance) !== 0);
  const zeros = observation.rows.filter(row => !hasNonzeroAmount(row) && evidenceNumber(row.balance) === 0);
  return <div className="space-y-2 mt-2">
    <p className="text-xs text-muted-foreground">{observation.count} observed balance records</p>
    {nonzero.length + unknown.length > 0 && <AccountRows rows={[...nonzero, ...unknown]} label={`${providerName} nonzero and unknown balances`} />}
    {zeros.length > 0 && <details className="rounded border border-border/50 p-2">
      <summary className="cursor-pointer text-sm text-muted-foreground">Zero balances ({zeros.length})</summary>
      <div className="mt-2"><AccountRows rows={zeros} label={`${providerName} zero balances`} /></div>
    </details>}
  </div>;
}

function ReceiptLabel({ observation }: { observation: ProviderObservation }) {
  return <p className="mt-2 text-xs text-muted-foreground break-words">
    {observation.source ?? 'Source unavailable'} · {observation.timestamp === null ? 'No source timestamp' : new Date(observation.timestamp * 1_000).toISOString()}
    {observation.timestampKind === 'local_http_receipt' ? ' · local HTTP receipt time; provider time absent' : observation.timestampKind === 'provider_http_date' ? ' · provider HTTP Date' : ''}
    {observation.available && observation.ageSeconds !== null ? ` · ${Math.max(0, Math.round(observation.ageSeconds))}s old` : ''}
  </p>;
}

export function ProviderAccountObservations({ terminal }: { terminal: ReturnType<typeof useTerminalState> }) {
  const observations = evidenceRecord(terminal.observedState?.provider_observations);
  const providerPositions = evidenceRecord(terminal.observedState?.provider_positions);
  const connected = terminal.error === null && terminal.observedState !== null;
  return <Card className="bg-card/50 border-primary/20">
    <CardHeader><CardTitle className="text-lg">Provider Account Observations</CardTitle></CardHeader>
    <CardContent className="space-y-4">
      <p className="text-sm text-muted-foreground">Balances retain their provider currency. Position visibility is reported separately from fill and fee reconciliation.</p>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">{PROVIDERS.map(([key, name]) => {
        const provider = evidenceRecord(observations[key]);
        const accounts = readProviderObservation(provider.accounts, connected);
        const legacyPositions = readProviderObservation(provider.positions, connected);
        const liveVenue = evidenceRecord(providerPositions[key]);
        const livePositions = Array.isArray(liveVenue.positions) ? liveVenue.positions as EvidenceRecord[] : [];
        const liveAvailable = liveVenue.available === true && livePositions.length > 0;
        const liveReason = evidenceText(liveVenue.reason);
        return <div key={key} className="rounded border border-border/50 p-3 space-y-3">
          <p className="font-medium">{name}</p>
          <div>
            <div className="flex justify-between gap-2 text-sm"><span>Accounts</span><Badge variant="outline">{accounts.available ? 'Observed' : 'Unavailable'}</Badge></div>
            <AccountBalances observation={accounts} providerName={name} />
            <ReceiptLabel observation={accounts} />
          </div>
          <div className="border-t border-border/50 pt-3">
            <div className="flex justify-between gap-2 text-sm"><span>Provider-visible positions</span><Badge variant="outline">{liveAvailable ? livePositions.length : legacyPositions.available ? legacyPositions.count : 'Unavailable'}</Badge></div>
            {liveAvailable ? <div className="space-y-2 mt-2">
              {livePositions.map((row, index) => <PositionRow key={evidenceText(row.symbol) ?? index} row={row} />)}
              <p className="text-xs text-muted-foreground">Live position receipt · {liveReason ? liveReason : 'source timestamp'} {evidenceText(liveVenue.source_timestamp_iso) ?? (typeof liveVenue.source_timestamp === 'number' ? new Date(liveVenue.source_timestamp * 1_000).toISOString() : 'unavailable')}</p>
            </div> : legacyPositions.available ? <div className="space-y-2 mt-2">
              {legacyPositions.rows.map((row, index) => <div key={evidenceText(row.reference) ?? index} className="rounded bg-muted/30 p-2 text-sm">
                <p>{evidenceText(row.symbol) ?? 'Symbol unavailable'} · {evidenceText(row.side) ?? 'Side unavailable'} · Quantity {format(row.quantity)}</p>
                <p className="text-xs text-muted-foreground">Entry price (raw provider value) {format(row.entry_price)} · Price units unverified</p>
                <p className="text-xs text-muted-foreground">Reported position currency: {evidenceText(row.currency) ?? 'Unavailable'} · {row.fill_reconciled === true ? 'Fill receipt reconciled' : 'Fill and fee reconciliation pending'}</p>
              </div>)}
              <p className="text-xs text-muted-foreground">{legacyPositions.inventoryComplete ? 'Provider inventory read completed.' : 'Partial provider inventory; total count is not established.'}</p>
            </div> : <p className="text-xs text-muted-foreground mt-1">{liveReason ?? legacyPositions.reason}</p>}
            <ReceiptLabel observation={legacyPositions} />
          </div>
        </div>;
      })}</div>
    </CardContent>
  </Card>;
}
