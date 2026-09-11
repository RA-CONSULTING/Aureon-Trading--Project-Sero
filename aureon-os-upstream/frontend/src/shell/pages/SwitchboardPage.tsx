/** Glass control desk backed by the operator's registered feature configuration. */
import { useEffect, useRef, useState, type CSSProperties, type ReactNode } from 'react';
import { Activity, Brain, Loader2, Lock, RefreshCw, Settings, Shield, UserRound, type LucideIcon } from 'lucide-react';
import { toast } from 'sonner';
import { Link } from 'react-router-dom';
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from '@/components/ui/alert-dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { useIdentity } from '@/hooks/useIdentity';
import { useReadOnlyPoller } from '@/hooks/useReadOnlyPoller';
import { configurationMessage, configurationStatus } from '@/lib/accountConfigurationEvidence';
import { SwitchboardWriteGuard, type SwitchboardConfiguration, type SwitchboardFlag } from '@/lib/platformConfiguration';
import { submitSwitchboardChange } from '@/lib/switchboardControl';
import { switchboardStore } from '@/services/platformReads';

const GOLD = '#FFB800';
const CYAN = '#00E5FF';
const BG = '#0e0e0e';
const PANEL = 'rgba(18, 18, 18, 0.72)';
const BORDER = '#3f3f46';
const BORDER_GOLD = 'rgba(255, 184, 0, 0.45)';
const GROUP_ICONS: Record<string, LucideIcon> = {
  'Organism & Connectome': Activity, 'Cognition Routing': Brain, Notifications: Settings, 'Hard Boundary': Shield,
};

function GlassPanel({ children, className = '', style }: { children: ReactNode; className?: string; style?: CSSProperties }) {
  return <div className={`rounded-lg border ${className}`} style={{ background: PANEL, borderColor: BORDER_GOLD,
    backdropFilter: 'blur(12px)', WebkitBackdropFilter: 'blur(12px)', ...style }}>{children}</div>;
}

function StatusBadge({ children, active = false }: { children: ReactNode; active?: boolean }) {
  const color = active ? CYAN : GOLD;
  return <span className="inline-flex items-center rounded px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wider"
    style={{ color, background: `${color}18`, border: `1px solid ${color}55` }}>{children}</span>;
}

function ConfigurationToggle({ flag, disabled, saving, onToggle }: {
  flag: SwitchboardFlag; disabled: boolean; saving: boolean; onToggle(flag: SwitchboardFlag, next: boolean): void;
}) {
  return <div className="flex shrink-0 flex-col items-center gap-1">
    <button type="button" role="switch" aria-checked={flag.enabled} aria-label={`${flag.label} configuration`}
      disabled={disabled} onClick={() => onToggle(flag, !flag.enabled)}
      className="relative inline-flex h-6 w-11 shrink-0 items-center rounded-full disabled:cursor-not-allowed disabled:opacity-45 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-cyan-300"
      style={{ border: `1px solid ${flag.enabled ? CYAN : GOLD}`, background: flag.enabled ? `${CYAN}18` : 'rgba(0,0,0,0.55)' }}>
      <span className={`absolute h-4 w-4 rounded-full transition-transform ${flag.enabled ? 'translate-x-6' : 'translate-x-1'}`}
        style={{ background: flag.enabled ? CYAN : GOLD }} />
    </button>
    <span className="flex items-center gap-1 font-mono text-[10px]" style={{ color: flag.enabled ? CYAN : GOLD }}>
      {saving && <Loader2 className="h-3 w-3 animate-spin" />}{flag.enabled ? 'ON' : 'OFF'}
    </span>
  </div>;
}

/** Counts and controls come only from a validated current registry. */
export function SwitchboardConfigurationCards({ configuration, canManage, saving, onToggle }: {
  configuration: SwitchboardConfiguration; canManage: boolean; saving: string | null;
  onToggle(flag: SwitchboardFlag, next: boolean): void;
}) {
  return <div className="grid items-start gap-4 md:grid-cols-2">
    {configuration.groups.map(group => {
      const Icon = GROUP_ICONS[group.label] ?? Settings;
      const enabled = group.flags.filter(flag => flag.enabled).length;
      return <GlassPanel key={group.label} className="overflow-hidden">
        <div className="flex items-start justify-between gap-3 border-b px-4 py-3" style={{ borderColor: BORDER_GOLD }}>
          <div className="flex items-center gap-2"><Icon className="h-4 w-4 shrink-0" style={{ color: GOLD }} />
            <h2 className="text-sm font-bold uppercase tracking-[0.12em]" style={{ color: GOLD }}>{group.label}</h2></div>
          <StatusBadge active={enabled > 0}>{enabled}/{group.flags.length} ON</StatusBadge>
        </div>
        <ul className="divide-y divide-zinc-800 px-4">
          {group.flags.map(flag => <li key={flag.id} className="flex items-start gap-3 py-4">
            <div className="min-w-0 flex-1 space-y-1.5">
              <div className="flex flex-wrap items-center gap-1.5"><span className="text-[13px] font-medium text-zinc-100">{flag.label}</span>
                <StatusBadge>{flag.effect === 'live' ? 'Operator applies now' : 'Restart required for changes'}</StatusBadge>
                {flag.armed && <StatusBadge>Armed configuration</StatusBadge>}
                {flag.pending_restart === true && <StatusBadge>Pending restart</StatusBadge>}
                {flag.effect === 'restart' && flag.pending_restart === null && <StatusBadge>Restart status unknown</StatusBadge>}
              </div>
              <p className="text-[11px] leading-relaxed text-zinc-400">{flag.description}</p>
              <p className="text-[10px] leading-relaxed text-zinc-500">{flag.effect_note} · Source: {flag.source}</p>
              {flag.stored !== null && flag.stored !== flag.enabled && <p className="text-[11px]" style={{ color: GOLD }}>
                Saved intent {flag.stored ? 'ON' : 'OFF'} differs from effective operator configuration {flag.enabled ? 'ON' : 'OFF'}.
              </p>}
              <details className="text-[10px] text-zinc-500"><summary className="cursor-pointer">Configuration details</summary>
                <code className="mt-1 block break-all">{flag.env_var}</code>
                <p>Default: {flag.default ? 'ON' : 'OFF'} · Saved intent: {flag.stored === null ? 'No saved decision' : flag.stored ? 'ON' : 'OFF'}</p>
                {flag.decided_at !== null && <p>Decision recorded: {new Date(flag.decided_at * 1_000).toISOString()}</p>}
              </details>
            </div>
            <ConfigurationToggle flag={flag} disabled={!canManage || saving !== null} saving={saving === flag.id} onToggle={onToggle} />
          </li>)}
        </ul>
      </GlassPanel>;
    })}
  </div>;
}

export default function SwitchboardPage() {
  const receipt = useReadOnlyPoller(switchboardStore, 15_000, 8_000);
  const identity = useIdentity();
  const status = configurationStatus(receipt);
  const configuration = status === 'observed' ? receipt.data : null;
  const canManage = configuration !== null && identity.known && identity.identity.isAdmin;
  const accessRef = useRef(canManage);
  accessRef.current = canManage;
  const [guard] = useState(() => new SwitchboardWriteGuard());
  const [saving, setSaving] = useState<string | null>(null);
  const [arm, setArm] = useState<SwitchboardFlag | null>(null);
  const [armText, setArmText] = useState('');
  const alive = useRef(true);

  useEffect(() => {
    alive.current = true;
    return () => { alive.current = false; guard.invalidate(); };
  }, [guard]);
  useEffect(() => {
    guard.invalidate(); setArm(null); setArmText('');
  }, [guard, receipt.resetVersion, identity.identity.kind, identity.identity.tenantLabel]);

  async function save(flag: SwitchboardFlag, enabled: boolean, confirm?: string) {
    if (saving !== null || guard.busy) return;
    setSaving(flag.id);
    try {
      const result = await submitSwitchboardChange({ guard, flag, enabled, confirm,
        current: switchboardStore.getSnapshot, canManage: () => accessRef.current });
      if (alive.current) toast.success(`${flag.label}: intent saved ${result.stored ? 'ON' : 'OFF'}`, {
        description: result.stored !== result.enabled ? `${result.applied} Effective operator configuration remains ${result.enabled ? 'ON' : 'OFF'}.` : result.applied,
      });
    } catch (error) {
      if (alive.current) toast.error(`Could not confirm ${flag.label}`, { description: error instanceof Error ? error.message : 'Configuration request failed' });
    } finally {
      if (alive.current) {
        setSaving(null);
        // A timed-out save may have reached the server. Reread instead of
        // optimistically painting the requested value or retrying the write.
        switchboardStore.invalidate();
      }
    }
  }

  function onToggle(flag: SwitchboardFlag, next: boolean) {
    if (!canManage || saving !== null) return;
    if (flag.kind === 'hard_boundary' && next) { setArm(flag); setArmText(''); return; }
    void save(flag, next);
  }

  const restartUnknown = configuration?.groups.flatMap(group => group.flags)
    .filter(flag => flag.effect === 'restart' && flag.pending_restart === null).length ?? null;

  return <div className="min-h-full space-y-4 p-4 text-zinc-100" style={{ background: BG }}
    data-switchboard="wired-glass-v3" data-switchboard-theme="aureon-dark" data-switchboard-claim={status}>
    <div className="rounded-md border px-3 py-2" style={{ borderColor: `${GOLD}66`, background: `${GOLD}14` }}>
      <p className="text-[11px] font-semibold uppercase tracking-[0.14em]" style={{ color: GOLD }}>Operator configuration · {status}</p>
      <p className="mt-1 text-[11px] text-zinc-400">These switches show the current registered configuration. Running services and trading execution have separate runtime checks.</p>
    </div>
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div><h1 className="text-2xl font-bold uppercase tracking-[0.12em] text-white">Switchboard</h1>
        <p className="mt-1 text-[11px] uppercase tracking-[0.18em]" style={{ color: GOLD }}>Control · Evidence · Oversight</p>
        <p className="mt-1 text-[12px] text-zinc-400">Configure the systems registered by the operator. Each setting shows when its consumer applies a change.</p></div>
      <div className="flex flex-col items-end gap-2">
        <div className="inline-flex items-center gap-2 rounded-md border px-3 py-1.5 text-[11px] uppercase tracking-wider"
          style={{ borderColor: GOLD, color: GOLD, background: `${GOLD}12` }}><UserRound className="h-3.5 w-3.5" />
          {!identity.known ? 'Checking operator access' : identity.identity.isAdmin ? 'Operator controls' : 'View only'}</div>
        <button type="button" onClick={receipt.refresh} disabled={saving !== null}
          className="inline-flex items-center gap-1.5 rounded border border-zinc-700 px-2.5 py-1.5 text-[11px] text-zinc-300 hover:border-cyan-300 disabled:opacity-50">
          <RefreshCw className="h-3 w-3" /> Refresh configuration
        </button>
      </div>
    </div>
    {configuration ? <>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {[
          ['Configured ON', `${configuration.summary.enabled}/${configuration.summary.total}`],
          ['Armed settings', `${configuration.summary.armed}/${configuration.summary.hard_boundary_total}`],
          ['Pending restart', String(configuration.summary.pending_restart)],
          ['Restart status unknown', String(restartUnknown)],
        ].map(([label, value]) => <GlassPanel key={label} className="px-4 py-3"><p className="text-[10px] uppercase tracking-wider text-zinc-500">{label}</p>
          <p className="mt-1 font-mono text-2xl" style={{ color: CYAN }}>{value}</p></GlassPanel>)}
      </div>
      <div className="flex flex-wrap justify-between gap-2 text-[10px] text-zinc-500">
        <span>Configuration received: {receipt.lastReceivedAt === null ? 'Unavailable' : new Date(receipt.lastReceivedAt).toISOString()}</span>
        <span>Refreshes every 15 seconds</span>
      </div>
      {!identity.known && <p role="status" className="text-sm" style={{ color: GOLD }}>{identity.error ?? 'Waiting for a current operator identity before enabling controls.'}</p>}
      {identity.known && !identity.identity.isAdmin && <p role="status" className="text-sm" style={{ color: GOLD }}>This account can view configuration. Changes require an operator session.</p>}
      <SwitchboardConfigurationCards configuration={configuration} canManage={canManage} saving={saving} onToggle={onToggle} />
    </> : <GlassPanel className="p-5"><div role="status" className="flex items-center gap-2 text-sm" style={{ color: GOLD }}>
      {receipt.loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Lock className="h-4 w-4" />}
      {configurationMessage(status, receipt.error)}</div>
      <p className="mt-2 text-[11px] text-zinc-500">Configuration values and change controls appear after a valid current response.</p>
    </GlassPanel>}
    <div className="grid gap-3 md:grid-cols-2">
      <GlassPanel className="px-4 py-3"><div className="flex items-start gap-3"><Shield className="mt-0.5 h-4 w-4 shrink-0" style={{ color: GOLD }} />
        <div><p className="text-[11px] font-semibold uppercase tracking-[0.12em]" style={{ color: GOLD }}>Configuration and runtime</p>
          <p className="mt-1 text-[11px] text-zinc-400">An ON setting records configuration. Check runtime evidence to confirm a service has applied it and its required gates have passed.</p>
          <Link to="/trading/war-room" className="mt-2 inline-block text-[11px] underline" style={{ color: CYAN }}>Open trading runtime</Link></div></div></GlassPanel>
      <GlassPanel className="px-4 py-3"><p className="text-[11px] font-semibold uppercase tracking-[0.12em]" style={{ color: GOLD }}>Consequential settings</p>
        <p className="mt-1 text-[11px] text-zinc-400">Arming a hard-boundary setting requires its exact flag ID. The operator records that decision; downstream authority and execution checks remain in force.</p>
        <Link to="/platform/coverage" className="mt-2 inline-block text-[11px] underline" style={{ color: CYAN }}>Open system coverage</Link></GlassPanel>
    </div>
    <AlertDialog open={arm !== null} onOpenChange={open => { if (!open) { setArm(null); setArmText(''); } }}>
      <AlertDialogContent style={{ background: BG, borderColor: BORDER_GOLD }} className="text-zinc-100">
        <AlertDialogHeader><AlertDialogTitle>Arm {arm?.label}?</AlertDialogTitle>
          <AlertDialogDescription className="text-zinc-400">{arm?.description} {arm?.effect_note}
            {' '}This saves your configuration decision. It does not prove execution readiness.</AlertDialogDescription></AlertDialogHeader>
        <div className="space-y-2"><Label htmlFor="switchboard-arm">Type <code className="break-all" style={{ color: GOLD }}>{arm?.id}</code> to confirm</Label>
          <Input id="switchboard-arm" value={armText} autoComplete="off" onChange={event => setArmText(event.target.value)} />
        </div>
        <AlertDialogFooter><AlertDialogCancel>Cancel</AlertDialogCancel>
          <AlertDialogAction disabled={!canManage || saving !== null || !arm || armText !== arm.id}
            style={{ background: GOLD, color: '#0a0a0a' }} onClick={() => {
              if (!arm || armText !== arm.id) return;
              const flag = arm, confirm = armText;
              setArm(null); setArmText(''); void save(flag, true, confirm);
            }}>Save armed configuration</AlertDialogAction></AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
    <div className="border-t pt-3 text-[10px] uppercase tracking-wider text-zinc-500" style={{ borderColor: BORDER }}>Aureon · operator switchboard</div>
  </div>;
}
