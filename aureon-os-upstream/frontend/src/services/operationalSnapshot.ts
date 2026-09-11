import { api, type RequestOptions } from './apiClient';
import { createReadOnlyPoller } from './readOnlyPoller';

type Report = Record<string, unknown>;
export const operationalReports: Record<string, string> = {
  uiSpec: '/aureon_operational_ui_spec.json', wake: '/aureon_wake_up_manifest.json',
  organism: '/aureon_organism_runtime_status.json', switchboard: '/aureon_autonomous_capability_switchboard.json',
  unification: '/aureon_frontend_unification_plan.json', evolution: '/aureon_frontend_evolution_queue.json',
  inventory: '/aureon_saas_system_inventory.json', tradeEvidence: '/aureon_cognitive_trade_evidence.json',
  harmonic: '/aureon_harmonic_affect_state.json', benchmark: '/aureon_live_cognition_benchmark.json',
  hncProof: '/aureon_hnc_cognitive_proof.json',
};
export interface OperationalRead {
  loadedAt: string; loading: false; data: Record<string, Report>;
  runtime: Report | null; flight: Report | null; reboot: Report | null;
  statusRead: Report | null; company: Report | null; coverage: Report | null; switchboardLive: Report | null; releaseReadiness: Report | null; ingressCustody: Report | null; executorIsolation: Report | null; authorityMap: Report | null; resultBinding: Report | null; capabilityAttestation: Report | null; releaseLedger: Report | null;
  runtimeEndpoint: string; errors: string[];
}
type Reader = (path: string, options: RequestOptions) => Promise<Report>;

/** Canonical reads begin independently of absent public reports; report URLs cannot select an API target. */
export async function readOperationalSnapshot(options: RequestOptions, read: Reader = (path, opts) => api.get(path, opts)): Promise<OperationalRead> {
  const errors: string[] = [];
  const data: Record<string, Report> = {};
  const reportController = new AbortController();
  const cancelReports = () => reportController.abort();
  options.signal?.addEventListener('abort', cancelReports, { once: true });
  if (options.signal?.aborted) cancelReports();
  const reportDeadline = setTimeout(cancelReports, 5_000);
  async function attempt(path: string, report = false): Promise<Report | null> {
    try {
      const result = await read(path, { ...options,
        signal: report ? reportController.signal : options.signal,
        timeoutMs: Math.min(options.timeoutMs ?? 8_000, report ? 5_000 : 8_000) });
      if (!result || typeof result !== 'object' || Array.isArray(result)) throw new Error('Invalid JSON object');
      return result;
    } catch {
      errors.push(`${path} unavailable`);
      return null;
    }
  }
  const runtimePending = attempt('/api/terminal-state');
  const flightPending = attempt('/api/flight-test');
  const statusPending = attempt('/api/status');
  const companyPending = attempt('/api/company');
  const coveragePending = attempt('/api/coverage');
  const switchboardPending = attempt('/api/switchboard');
  const releasePending = attempt('/api/operator/release-readiness');
  const ingressCustodyPending = attempt('/api/operator/ingress-custody');
  const executorIsolationPending = attempt('/api/operator/executor-isolation');
  const authorityMapPending = attempt('/api/operator/authority-map');
  const resultBindingPending = attempt('/api/operator/result-binding');
  const capabilityAttestationPending = attempt('/api/operator/capability-runtime-attestation');
  const releaseLedgerPending = attempt('/api/operator/release-ledger');
  // Only three public reads at a time, each with its own deadline. An absent
  // report cannot consume the runtime request's deadline or select a remote URL.
  const entries = Object.entries(operationalReports);
  let cursor = 0;
  try {
    await Promise.all(Array.from({ length: 3 }, async () => {
      while (cursor < entries.length && !reportController.signal.aborted) {
        const [key, path] = entries[cursor++];
        const report = await attempt(path, true);
        if (report) data[key] = report;
      }
    }));
    const [runtime, flight, statusRead, company, coverage, switchboardLive, releaseReadiness, ingressCustody, executorIsolation, authorityMap, resultBinding, capabilityAttestation, releaseLedger] = await Promise.all([
      runtimePending, flightPending, statusPending, companyPending, coveragePending, switchboardPending, releasePending, ingressCustodyPending, executorIsolationPending, authorityMapPending, resultBindingPending, capabilityAttestationPending, releaseLedgerPending,
    ]);
    return { loadedAt: new Date().toISOString(), loading: false, data, runtime, flight,
      reboot: null, statusRead, company, coverage, switchboardLive, releaseReadiness, ingressCustody, executorIsolation, authorityMap, resultBinding, capabilityAttestation, releaseLedger, runtimeEndpoint: '/api/terminal-state', errors };
  } finally {
    clearTimeout(reportDeadline);
    options.signal?.removeEventListener('abort', cancelReports);
  }
}

export const operationalSnapshotStore = createReadOnlyPoller<OperationalRead>({
  read: readOperationalSnapshot, receiptMaxAgeMs: 45_000,
});
