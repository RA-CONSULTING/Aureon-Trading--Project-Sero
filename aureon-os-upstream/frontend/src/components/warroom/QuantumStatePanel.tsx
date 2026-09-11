import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import type { WarRoomEvidence } from '@/lib/warRoomEvidence';
import { useReadOnlyPoller } from '@/hooks/useReadOnlyPoller';
import { cognitionFieldStore } from '@/services/cognitiveReads';

const finite = (value: unknown): number | null =>
  typeof value === 'number' && Number.isFinite(value) ? value : null;

const text = (value: unknown): string | null =>
  typeof value === 'string' && value.trim() ? value.trim() : null;

const record = (value: unknown): Record<string, unknown> =>
  value !== null && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {};

function canonicalFieldValue(payload: unknown, receiptCurrent: boolean): {
  lambda: number | null;
  gamma: number | null;
  psi: number | null;
  receipt: string | null;
} {
  if (!receiptCurrent) return { lambda: null, gamma: null, psi: null, receipt: null };
  const root = record(payload);
  const data = record(root.data);
  const canonical = record(data.canonical);
  const lambda = finite(canonical.lambda_t);
  if (data.available !== true
    || data.fresh !== true
    || data.truth_status !== 'real_derived'
    || canonical.available !== true
    || canonical.data_status !== 'live'
    || canonical.freshness_status !== 'fresh'
    || canonical.generated_values !== false
    || lambda === null) {
    return { lambda: null, gamma: null, psi: null, receipt: null };
  }
  return {
    lambda,
    gamma: finite(canonical.coherence_gamma),
    psi: finite(canonical.consciousness_psi),
    receipt: text(canonical.receipt_id),
  };
}

const percent = (value: number | null) => value === null ? 'Unavailable' : `${(value * 100).toFixed(1)}%`;
const decimal = (value: number | null) => value === null ? 'Unavailable' : value.toFixed(3);

export function QuantumStatePanel({ evidence }: { evidence: WarRoomEvidence }) {
  const fieldRead = useReadOnlyPoller(cognitionFieldStore, 5_000, 8_000);
  const field = canonicalFieldValue(fieldRead.data, fieldRead.isReceiptCurrent);
  const rows = [
    ['Auris coherence', percent(evidence.aurisCoherence)],
    ['Lambda', field.lambda === null ? 'Unavailable' : field.lambda.toFixed(3)],
    ['Lighthouse', decimal(evidence.lighthouseConfidence.value)],
    ['Prism state', 'Unavailable'],
  ];
  const live = evidence.available || field.lambda !== null || evidence.lighthouseConfidence.available;
  return <Card className="bg-card/50 border-primary/20">
    <CardHeader><CardTitle className="flex items-center justify-between gap-2">Quantum State <Badge variant="outline">{live ? 'Runtime observation' : 'Unavailable'}</Badge></CardTitle></CardHeader>
    <CardContent className="space-y-3">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">{rows.map(([name, value]) => <div key={name}>
        <p className="text-xs text-muted-foreground">{name}</p><p className="text-lg font-mono">{value}</p>
      </div>)}</div>
      <div className="grid grid-cols-1 gap-2 text-xs text-muted-foreground md:grid-cols-2">
        <p>Auris coherence and Lighthouse are read from the current terminal-state receipts. Lambda is read from the canonical HNC field receipt.</p>
        <p>{field.lambda !== null ? `HNC Γ ${decimal(field.gamma)} · Ψ ${decimal(field.psi)} · receipt ${field.receipt ?? 'unreported'}` : fieldRead.error ?? 'Waiting for a fresh canonical HNC field receipt.'}</p>
      </div>
      <p className="text-xs text-muted-foreground">Prism remains unavailable until a timestamped Prism runtime receipt is published.</p>
    </CardContent>
  </Card>;
}
