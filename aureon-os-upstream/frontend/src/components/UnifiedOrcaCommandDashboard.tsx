import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Badge } from './ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { evidenceNumber, evidenceText } from '@/lib/warRoomEvidence';
import { ORCA_POSITION_PROVIDERS, readOrcaReaderEvidence } from '@/lib/orcaReaderEvidence';
import { RadioTower } from 'lucide-react';
import { GlassPageHeader } from '@/shell/GlassPage';

const SOURCE_URL = '/api/orca-observations';
type Receipt = { ok: boolean; payload: unknown; error: string | null; receivedAt: number | null };
const UNAVAILABLE = [
  ['Closed fills and realized performance', 'The collector has no persisted native close/fill ledger. Its legacy kill list and calculated statistics are not used.'],
  ['System coordination and health', 'Imported components do not establish operating status, readiness or a measured health percentage.'],
  ['Consolidated feeds and decision inputs', 'No independently timestamped feed or provider-backed decision contract is exposed by this reader.'],
];
const date = (value: number | null) => value === null ? 'Unavailable' : new Date(value * 1_000).toISOString();
const number = (value: unknown) => {
  const observed = evidenceNumber(value);
  return observed === null ? 'Unavailable' : observed.toLocaleString(undefined, { maximumFractionDigits: 8 });
};

export default function UnifiedOrcaCommandDashboard() {
  const [receipt, setReceipt] = useState<Receipt | null>(null);
  const [, refreshAge] = useState(0);
  useEffect(() => {
    let alive = true;
    let inFlight: AbortController | null = null;
    const poll = async () => {
      if (!alive || inFlight) return;
      const controller = new AbortController();
      inFlight = controller;
      const timeout = window.setTimeout(() => controller.abort(), 10_000);
      let next: Receipt;
      try {
        const response = await fetch(SOURCE_URL, { cache: 'no-store', signal: controller.signal });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        if (Number(response.headers.get('content-length')) > 1_048_576) throw new Error('Reader response exceeds the 1 MiB limit');
        const reader = response.body?.getReader();
        if (!reader) throw new Error('Reader response body unavailable');
        const chunks: Uint8Array[] = [];
        let size = 0;
        try {
          while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            size += value.byteLength;
            if (size > 1_048_576) { await reader.cancel(); throw new Error('Reader response exceeds the 1 MiB limit'); }
            chunks.push(value);
          }
        } finally { reader.releaseLock(); }
        const bytes = new Uint8Array(size);
        let offset = 0;
        for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.byteLength; }
        const payload: unknown = JSON.parse(new TextDecoder().decode(bytes));
        next = { ok: true, payload, error: null, receivedAt: Date.now() };
      } catch (error) {
        next = { ok: false, payload: null, error: controller.signal.aborted ? 'Reader request timed out'
          : error instanceof Error ? error.message : 'Reader unavailable', receivedAt: null };
      } finally {
        clearTimeout(timeout);
        if (inFlight === controller) inFlight = null;
      }
      if (alive) setReceipt(next);
    };
    void poll();
    const pollTimer = window.setInterval(() => void poll(), 3_000);
    const ageTimer = window.setInterval(() => refreshAge((value) => value + 1), 1_000);
    return () => { alive = false; clearInterval(pollTimer); clearInterval(ageTimer); inFlight?.abort(); };
  }, []);
  const evidence = readOrcaReaderEvidence(receipt?.payload, receipt?.ok === true);
  return <div className="mx-auto max-w-7xl space-y-4 p-4 md:p-6">
    <GlassPageHeader icon={RadioTower} eyebrow="Trading observations" title="Orca Position Observations"
      description="Sanitized position receipts already retained in the operator terminal state. Provider inventory snapshots are separate from fills, current market quotes and execution readiness." />
    <Card><CardContent className="pt-6 space-y-2">
      <div className="flex flex-wrap items-center gap-2"><p className="font-medium">Operator receipt transport</p><Badge variant="outline">{evidence.contractAvailable ? 'Receipt contract received' : 'Unavailable'}</Badge></div>
      <p className="text-sm text-muted-foreground">{receipt?.error ?? (receipt?.ok && !evidence.contractAvailable ? 'Expected operator position schema unavailable' : receipt ? 'Successful HTTP read; individual original source clocks determine data availability.' : 'Awaiting the operator receipt.')}</p>
      <p className="break-words text-xs text-muted-foreground">Source: {SOURCE_URL}{receipt?.receivedAt ? ` · HTTP received ${new Date(receipt.receivedAt).toISOString()}` : ''}</p>
    </CardContent></Card>
    <div className="grid gap-4 lg:grid-cols-2">{ORCA_POSITION_PROVIDERS.map((provider) => {
      const observation = evidence.positions[provider];
      return <Card key={provider}><CardHeader><CardTitle className="flex flex-wrap items-center gap-2 text-lg"><span className="capitalize">{provider} position inventory</span><Badge variant="outline">{observation.available ? 'Observed snapshot' : 'Unavailable'}</Badge></CardTitle></CardHeader>
        <CardContent className="space-y-3">
          <p className="text-sm">{observation.reason}</p>
          {observation.available && <p>{observation.count} provider-reported position{observation.count === 1 ? '' : 's'} in this receipt{observation.inventoryComplete === false ? ' (partial inventory)' : ''}.</p>}
          {observation.rows.length > 0 && <div className="max-h-96 space-y-2 overflow-auto">{observation.rows.map((row, index) => <div key={`${row.reference ?? row.symbol}:${index}`} className="rounded border border-border p-3 text-sm">
            <p className="font-medium">{evidenceText(row.symbol) ?? 'Symbol unavailable'} · {evidenceText(row.side) ?? 'Side unavailable'}</p>
            <p>Quantity: {number(row.quantity)}</p>
            <p>Provider average entry: {number(row.entry_price)} {evidenceText(row.currency) ?? '(currency unreported)'}</p>
            <p className="mt-1 text-xs text-muted-foreground">Entry time, current price, fees and fill reconciliation are not attested by this projection.</p>
          </div>)}</div>}
          <div className="break-words text-xs text-muted-foreground space-y-1">
            <p>Source: {observation.source ?? 'Unavailable'}</p>
            <p>Original clock: {date(observation.timestamp)} · {observation.timestampKind?.replaceAll('_', ' ') ?? 'Clock kind unavailable'}</p>
            <p>Provider HTTP received: {date(observation.receivedAt)}{observation.ageSeconds !== null ? ` · ${Math.max(0, Math.floor(observation.ageSeconds))}s old` : ''}</p>
            <p>Inventory receipts expire after at most 5 minutes. Browser reads and cached provider results never renew this clock.</p>
          </div>
        </CardContent></Card>;
    })}</div>
    <Card><CardHeader><CardTitle className="text-lg">Source coverage</CardTitle></CardHeader><CardContent className="space-y-3">
      {UNAVAILABLE.map(([name, reason]) => <div key={name}><p className="font-medium">{name} · Unavailable</p><p className="text-sm text-muted-foreground">{reason}</p></div>)}
      <p className="text-sm text-muted-foreground">This page provides observations only. It does not activate or acknowledge trading commands.</p>
    </CardContent></Card>
    <p className="text-xs text-muted-foreground">This endpoint reads the operator's existing sanitized terminal-state receipts. It makes no provider request and carries no mutation authority.</p>
    <p className="text-sm text-muted-foreground"><Link className="text-primary underline" to="/trading/war-room">Open the Trading War Room</Link> for independent market quotes and governed runtime status.</p>
  </div>;
}
