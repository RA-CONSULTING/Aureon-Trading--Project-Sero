const record = (value: unknown): Record<string, unknown> | null => value !== null && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : null;
const text = (value: unknown): string | null => typeof value === 'string' && value.trim() ? value : null;
const bool = (value: unknown): boolean | null => typeof value === 'boolean' ? value : null;
export const configurationCount = (value: unknown): number | null => typeof value === 'number' && Number.isSafeInteger(value) && value >= 0 ? value : null;

export interface SwitchboardFlag {
  id: string; env_var: string; label: string; group: string;
  kind: 'safe' | 'hard_boundary'; effect: 'live' | 'restart' | 'handoff'; effect_note: string; description: string;
  default: boolean; enabled: boolean; stored: boolean | null; source: 'store' | 'env' | 'default';
  risk_value: boolean; armed: boolean; requested_armed: boolean; decided_at: number | null;
  pending_restart: boolean | null; pending_handoff: boolean; env_hold: boolean;
}
export interface SwitchboardConfiguration {
  groups: { label: string; flags: SwitchboardFlag[] }[];
  summary: { total: number; enabled: number; requested_enabled: number; armed: number; requested_armed: number;
    pending_restart: number; pending_handoff: number; hard_boundary_total: number };
}
export function readSwitchboardConfiguration(value: unknown): SwitchboardConfiguration {
  const raw = record(value);
  if (!raw || !Array.isArray(raw.groups) || !raw.groups.length || raw.groups.length > 64 || !record(raw.summary)) throw new Error('Switchboard configuration is malformed');
  const ids = new Set<string>();
  const groups = raw.groups.map(value => {
    const group = record(value);
    if (!group || !text(group.label) || !Array.isArray(group.flags) || !group.flags.length) throw new Error('Switchboard group is malformed');
    const flags = group.flags.map(value => {
      const f = record(value);
      if (!f || !text(f.id) || !/^[a-zA-Z0-9_.-]{1,120}$/.test(f.id as string) || ids.has(f.id as string)
        || !['safe', 'hard_boundary'].includes(String(f.kind)) || !['live', 'restart', 'handoff'].includes(String(f.effect))
        || !['store', 'env', 'default'].includes(String(f.source)) || f.group !== group.label
        || ['env_var', 'label', 'effect_note', 'description'].some(key => !text(f[key]))
        || ['enabled', 'default', 'risk_value', 'armed', 'requested_armed', 'pending_handoff', 'env_hold'].some(key => typeof f[key] !== 'boolean')
        || (f.stored !== null && typeof f.stored !== 'boolean') || (f.pending_restart !== null && typeof f.pending_restart !== 'boolean')
        || (f.decided_at !== null && (typeof f.decided_at !== 'number' || !Number.isFinite(f.decided_at) || f.decided_at <= 0 || f.decided_at > 8_640_000_000_000))
        || f.armed !== (f.kind === 'hard_boundary' && f.enabled === f.risk_value)
        || f.requested_armed !== (f.kind === 'hard_boundary' && (f.stored ?? f.enabled) === f.risk_value)
        || f.pending_handoff !== (f.effect === 'handoff' && f.stored !== null && f.stored !== f.enabled)) throw new Error('Switchboard flag is malformed');
      ids.add(f.id as string);
      if (ids.size > 512) throw new Error('Switchboard flag limit exceeded');
      return { ...f } as unknown as SwitchboardFlag;
    });
    return { label: group.label as string, flags };
  });
  const flags = groups.flatMap(group => group.flags);
  const summary = { total: flags.length, enabled: flags.filter(f => f.enabled).length,
    requested_enabled: flags.filter(f => f.stored ?? f.enabled).length,
    armed: flags.filter(f => f.armed).length, requested_armed: flags.filter(f => f.requested_armed).length,
    pending_restart: flags.filter(f => f.pending_restart === true).length,
    pending_handoff: flags.filter(f => f.pending_handoff).length,
    hard_boundary_total: flags.filter(f => f.kind === 'hard_boundary').length };
  if (Object.entries(summary).some(([key, count]) => record(raw.summary)![key] !== count)) throw new Error('Switchboard summary does not match its flag records');
  return { groups, summary };
}

export function sameSwitchboardFlag(expected: SwitchboardFlag, actual: SwitchboardFlag | undefined): boolean {
  return Boolean(actual && ['id', 'kind', 'enabled', 'stored', 'env_var', 'effect', 'risk_value', 'armed', 'requested_armed', 'pending_handoff']
    .every(key => expected[key as keyof SwitchboardFlag] === actual[key as keyof SwitchboardFlag]));
}
type FlagSnapshot = { data: SwitchboardConfiguration | null; isReceiptCurrent: boolean; resetVersion: number };
const findFlag = (data: SwitchboardConfiguration | null, id: string) => data?.groups.flatMap(group => group.flags).find(flag => flag.id === id);

/** Serializes existing user actions and binds preflight to the current session. */
export class SwitchboardWriteGuard {
  private generation = 0;
  private operation: AbortController | null = null;
  private blockedResetVersion: number | null = null;
  get busy() { return this.operation !== null; }
  invalidate(resetVersion?: number) {
    this.generation++;
    if (resetVersion !== undefined) this.blockedResetVersion = resetVersion;
    this.operation?.abort();
  }
  async run<T>(expected: SwitchboardFlag, enabled: boolean, confirm: string | undefined, io: {
    current(): FlagSnapshot;
    read(signal: AbortSignal): Promise<SwitchboardConfiguration>;
    write(signal: AbortSignal): Promise<T>;
  }): Promise<T> {
    if (this.operation) throw new Error('A configuration request is already in progress');
    const initial = io.current();
    if (!initial.isReceiptCurrent || initial.resetVersion === this.blockedResetVersion || !sameSwitchboardFlag(expected, findFlag(initial.data, expected.id))) throw new Error('Read current flag configuration before changing it');
    if (enabled === (expected.stored ?? expected.enabled)) throw new Error('Flag state already matches the requested value');
    if (expected.kind === 'hard_boundary' && enabled === expected.risk_value && confirm !== expected.id) throw new Error('Typed flag confirmation is required');
    const generation = this.generation;
    const controller = new AbortController();
    this.operation = controller;
    const requireSameSession = () => {
      if (controller.signal.aborted || this.generation !== generation || io.current().resetVersion !== initial.resetVersion) throw new Error('Session changed; confirm again using current configuration');
    };
    try {
      const current = await io.read(controller.signal);
      requireSameSession();
      if (!sameSwitchboardFlag(expected, findFlag(current, expected.id))) throw new Error('Flag changed since it was displayed; review it again');
      const result = await io.write(controller.signal);
      requireSameSession();
      return result;
    } finally {
      if (this.operation === controller) this.operation = null;
    }
  }
}

export interface BillingStatus {
  configured: boolean | null; missing_env: string[];
  metering: { sink: string | null; pending: number | null; flushed: number | null; dropped: number | null; flush_failures: number | null } | null;
  charge_endpoint: { enabled: boolean | null } | null;
}
export function readBillingStatus(value: unknown): BillingStatus {
  const raw = record(value);
  if (!raw || !['configured', 'metering', 'charge_endpoint'].some(key => key in raw)) throw new Error('Billing configuration is unavailable');
  const metering = record(raw.metering), charge = record(raw.charge_endpoint);
  return { configured: bool(raw.configured), missing_env: Array.isArray(raw.missing_env) ? raw.missing_env.filter((item): item is string => typeof item === 'string') : [],
    metering: metering ? { sink: text(metering.sink), pending: configurationCount(metering.pending), flushed: configurationCount(metering.flushed), dropped: configurationCount(metering.dropped), flush_failures: configurationCount(metering.flush_failures) } : null,
    charge_endpoint: charge ? { enabled: bool(charge.enabled) } : null };
}

export interface RecordedCompanyProfile {
  identity: Record<string, string>; identity_note: string; recognition: Record<string, string>;
  community: { summary: string; partners: string[] }; product: Record<string, string>; contact: Record<string, string>;
  disclaimer: string; source: string | null;
}
export function readRecordedCompanyProfile(value: unknown): RecordedCompanyProfile {
  const raw = record(value);
  const stringMap = (value: unknown) => { const map = record(value); return map && Object.values(map).every(item => typeof item === 'string') ? map as Record<string, string> : null; };
  const identity = stringMap(raw?.identity), recognition = stringMap(raw?.recognition), product = stringMap(raw?.product), contact = stringMap(raw?.contact), community = record(raw?.community);
  if (!raw || !identity?.registered_name || !recognition || !product || !contact || !community || typeof community.summary !== 'string'
    || !Array.isArray(community.partners) || community.partners.some(item => typeof item !== 'string')
    || ['identity_note', 'disclaimer'].some(key => typeof raw[key] !== 'string')) throw new Error('Recorded company profile is malformed');
  return { identity, recognition, product, contact, community: { summary: community.summary, partners: community.partners as string[] },
    identity_note: raw.identity_note as string, disclaimer: raw.disclaimer as string, source: text(raw.source) };
}

/** Auth callbacks stay synchronous; a late initial read cannot restore an old user. */
export function sessionUserObserver(publish: (userId: string | null) => void) {
  let active = true, eventSeen = false;
  return {
    event(userId: string | null) { eventSeen = true; if (active) publish(userId); },
    initial(userId: string | null) { if (active && !eventSeen) { eventSeen = true; publish(userId); return true; } return false; },
    stop() { active = false; },
  };
}
