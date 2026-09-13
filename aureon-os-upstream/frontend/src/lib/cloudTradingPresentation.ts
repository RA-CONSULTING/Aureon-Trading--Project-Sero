import type { CloudTradingControlReceipt } from './cloudTradingControl';
import { cloudTradingBlockerLabel } from './cloudTradingControl';

export type CloudExecutionEvidenceState = 'active' | 'held' | 'stale' | 'unavailable';

export interface CloudTradingReadEvidence {
  data: CloudTradingControlReceipt | null;
  isReceiptCurrent: boolean;
  error: string | null;
  source: {
    status: 'fresh' | 'stale' | 'unavailable' | 'unattested';
    reason?: string;
    sourceTimestamp?: number | string | null;
  };
}

export interface CloudExecutionPresentation {
  state: CloudExecutionEvidenceState;
  headline: string;
  detail: string;
  release: string;
  intentBridge: string;
  executionAuthentication: string;
  executionAuthenticationDetail: string;
  orderOutcome: string;
  blockers: string[];
  active: boolean;
  pathOperational: boolean;
}

export function cloudTradingSourceEvidence(
  control: CloudTradingControlReceipt,
  nowMs: number,
): CloudTradingReadEvidence['source'] {
  if (control.truth_status === 'unavailable' || control.read_state === 'unavailable') {
    return { status: 'unavailable', reason: 'Cloud control source evidence is unavailable' };
  }
  const observedMs = control.observed_at * 1_000;
  if (!Number.isFinite(observedMs) || !Number.isFinite(nowMs) || observedMs > nowMs + 5_000
    || nowMs - observedMs > 45_000 || control.read_state === 'recorded'
    || control.last_probe?.current !== true) {
    return { status: 'stale', reason: 'Cloud control source evidence is stale', sourceTimestamp: control.observed_at };
  }
  return { status: 'fresh', sourceTimestamp: control.observed_at };
}

const unavailable = (stale: boolean): CloudExecutionPresentation => stale ? {
  state: 'stale',
  headline: 'CLOUD EXECUTION EVIDENCE STALE',
  detail: 'A prior owner control receipt or signed probe is outside its current evidence window. Cloud release authority is unconfirmed.',
  release: 'Unconfirmed · evidence stale',
  intentBridge: 'Unconfirmed · evidence stale',
  executionAuthentication: '— / 4',
  executionAuthenticationDetail: 'Current signed cloud executor authentication is unconfirmed.',
  orderOutcome: 'No current signed terminal order/fill receipt',
  blockers: ['cloud execution evidence stale'],
  active: false,
  pathOperational: false,
} : {
  state: 'unavailable',
  headline: 'CLOUD EXECUTION EVIDENCE UNAVAILABLE',
  detail: 'The protected owner control endpoint did not return a current validated receipt. Cloud release authority is unconfirmed.',
  release: 'Unconfirmed · evidence unavailable',
  intentBridge: 'Unconfirmed · evidence unavailable',
  executionAuthentication: '— / 4',
  executionAuthenticationDetail: 'Current signed cloud executor authentication is unavailable.',
  orderOutcome: 'No current signed terminal order/fill receipt',
  blockers: ['cloud execution evidence unavailable'],
  active: false,
  pathOperational: false,
};

/**
 * Present the controller authority independently from the VM planner flags.
 * A signed no-order authentication probe can establish connectivity, but never an
 * order or fill. This control receipt deliberately exposes no live-result body.
 */
export function cloudExecutionPresentation(read: CloudTradingReadEvidence): CloudExecutionPresentation {
  const control = read.data;
  const receiptExpired = read.source.status === 'stale'
    || /expired|stale/i.test(read.error ?? '');
  if (!control || !read.isReceiptCurrent) return unavailable(receiptExpired);
  if (control.truth_status === 'unavailable' || control.read_state === 'unavailable') return unavailable(false);
  if (control.read_state === 'recorded' || control.last_probe?.current !== true) return unavailable(true);

  const providerRows = control.last_probe.provider_readback?.providers;
  const authenticated = providerRows
    ? Object.values(providerRows).filter(provider => provider.authenticated === true).length
    : 0;
  const currentAuthentication = control.last_probe.provider_readback?.all_authenticated === true
    && authenticated === 4;
  const active = control.release_authority === true && control.controller_release?.state === 'active';
  const bridge = control.intent_bridge;
  const pathOperational = active && control.production_ready === true
    && bridge?.operational === true && bridge.release_authority === true;
  const blockers = control.blockers.map(cloudTradingBlockerLabel);

  let intentBridge = 'Unavailable · no current governed bridge receipt';
  if (bridge?.operational === true) {
    intentBridge = bridge.state === 'published'
      ? 'Operational · order intent published'
      : bridge.state === 'publish_outcome_unknown'
        ? 'Operational · intent publish outcome unknown'
        : 'Operational · waiting for a qualifying candidate';
  } else if (bridge) {
    const reason = bridge.blockers.length > 0
      ? bridge.blockers.slice(0, 2).map(cloudTradingBlockerLabel).join(' · ')
      : 'bridge receipt reports held';
    intentBridge = `Held · ${reason}`;
  }

  const orderOutcome = bridge?.last_publish
    ? 'Intent publish receipt present; no signed terminal order/fill receipt'
    : 'No signed terminal order/fill receipt in this control readback';
  const authentication = currentAuthentication ? '4 / 4' : '— / 4';
  const authenticationDetail = currentAuthentication
    ? 'Current signed no-order cloud executor probe; separate from VM account inventories.'
    : 'Current signed cloud executor authentication is unavailable.';

  if (active) {
    const expiry = control.controller_release
      ? new Date(control.controller_release.authorization_expires_at_ms).toISOString()
      : 'unavailable';
    return {
      state: 'active',
      headline: 'CONTROLLER-SIGNED CLOUD RELEASE ACTIVE',
      detail: pathOperational
        ? 'The governed cloud authority path is released. VM planner flags are shown separately and do not replace this controller receipt.'
        : 'The controller release is active, but the governed order-intent path is not currently operational. VM planner flags remain a separate signal.',
      release: `Active until ${expiry}`,
      intentBridge,
      executionAuthentication: authentication,
      executionAuthenticationDetail: authenticationDetail,
      orderOutcome,
      blockers,
      active: true,
      pathOperational,
    };
  }

  return {
    state: 'held',
    headline: 'CONTROLLER-SIGNED CLOUD RELEASE HELD',
    detail: control.operator_can_apply_live
      ? 'The signed prerequisites are current and the owner can request activation. The controller has not granted live release authority.'
      : 'The cloud authority chain is held by the current controller evidence. Local analysis can continue without live release authority.',
    release: control.operator_can_apply_live ? 'Held · eligible for owner activation' : 'Held · prerequisites incomplete',
    intentBridge,
    executionAuthentication: authentication,
    executionAuthenticationDetail: authenticationDetail,
    orderOutcome,
    blockers,
    active: false,
    pathOperational: false,
  };
}
