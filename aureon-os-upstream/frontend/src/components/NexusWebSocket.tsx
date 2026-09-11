import { useState } from 'react';
import { Button } from './ui/button';

export type HarmonicControlRequest = { gain: number; fundamental: number; intent: string };

/** Calibration targets are manually entered requests, never measured telemetry. */
export function HarmonicControls({ onUpdate, disabled }: { onUpdate: (params: HarmonicControlRequest) => boolean; disabled: boolean }) {
  const [gain, setGain] = useState('');
  const [fundamental, setFundamental] = useState('');
  const [intent, setIntent] = useState('');
  const [status, setStatus] = useState<string | null>(null);
  const gainNumber = gain.trim() ? Number(gain) : NaN;
  const fundamentalNumber = fundamental.trim() ? Number(fundamental) : NaN;
  const valid = Number.isFinite(gainNumber) && gainNumber >= 0 && gainNumber <= 1
    && Number.isFinite(fundamentalNumber) && fundamentalNumber > 0;
  const apply = () => {
    if (disabled || !valid) return;
    const sent = onUpdate({ gain: gainNumber, fundamental: fundamentalNumber, intent });
    setStatus(sent ? 'Request sent. Runtime acknowledgement is unavailable.' : 'Request could not be sent.');
  };
  return <div className="rounded-lg border border-border bg-card p-4 space-y-3">
    <h2 className="font-semibold">Manual calibration request</h2>
    <p className="text-sm text-muted-foreground">Enter a target for a connected research receiver. These inputs are settings, not observed frequencies or biological measurements.</p>
    <div className="grid gap-3 md:grid-cols-3">
      <label className="text-sm">Gain (0 to 1)<input className="mt-1 w-full rounded bg-muted p-2" type="number" min="0" max="1" step="0.01" value={gain} onChange={(event) => setGain(event.target.value)} /></label>
      <label className="text-sm">Target frequency (Hz)<input className="mt-1 w-full rounded bg-muted p-2" type="number" min="0" value={fundamental} onChange={(event) => setFundamental(event.target.value)} /></label>
      <label className="text-sm">Experiment note<input className="mt-1 w-full rounded bg-muted p-2" value={intent} onChange={(event) => setIntent(event.target.value)} /></label>
    </div>
    <Button disabled={disabled || !valid} onClick={apply}>Send calibration request</Button>
    {status && <p role="status" className="text-sm text-muted-foreground">{status}</p>}
  </div>;
}
