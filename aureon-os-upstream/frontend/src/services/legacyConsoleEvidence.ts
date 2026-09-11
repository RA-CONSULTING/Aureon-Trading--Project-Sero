import { api, type RequestOptions } from './apiClient';
import { createReadOnlyPoller } from './readOnlyPoller';
import { terminalFreshness, type TerminalState } from '../hooks/terminalStateContract';
import type { OperationalRead } from './operationalSnapshot';

export type LegacyReport = Record<string, unknown>;
export function legacyNumber(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}
export function formatLegacyNumber(value: unknown): string {
  return legacyNumber(value)?.toLocaleString() ?? 'Unavailable';
}
/** Inventory structure is a recorded heuristic, never operational health. */
export function legacyReadiness(summary: { surface_count?: unknown; security_blocker_count?: unknown; orphaned_frontend_count?: unknown }): number | null {
  const total = legacyNumber(summary.surface_count);
  const blockers = legacyNumber(summary.security_blocker_count);
  const orphaned = legacyNumber(summary.orphaned_frontend_count);
  if (total === null || total <= 0 || blockers === null || blockers < 0 || orphaned === null || orphaned < 0) return null;
  return Math.max(0, Math.min(100, Math.round(100 - ((blockers * 25 + orphaned * .12) / total) * 100)));
}
export function legacyRuntimeEvidence(snapshot: OperationalRead | null, error: string | null, receivedAt: number | null, now = Date.now()) {
  const observed = snapshot?.runtime as TerminalState | null ?? null;
  const freshness = terminalFreshness(observed, error, receivedAt, now);
  return { freshness, data: freshness.status === 'fresh' ? observed : null };
}

export const legacyReportPaths = {
  tradingChecklist: '/aureon_trading_intelligence_checklist.json',
  exchangeChecklist: '/aureon_exchange_monitoring_checklist.json',
  exchangeDataMatrix: '/aureon_exchange_data_capability_matrix.json',
  globalCoverageMap: '/aureon_global_financial_coverage_map.json',
  hncSecurityComparison: '/aureon_hnc_packet_security_comparison.json',
  liveGoalTradeAudit: '/aureon_live_goal_trade_audit.json',
  orderLifecycleStressAudit: '/aureon_order_lifecycle_stress_audit.json',
  capitalEcosystemIntelligence: '/aureon_capital_ecosystem_intelligence_company.json',
  capitalRevenueLogicStressAudit: '/aureon_capital_revenue_logic_stress_audit.json',
  capitalRevenueLiveGateReadinessAudit: '/aureon_capital_revenue_live_gate_readiness_audit.json',
  capitalThreePLiveExecutionCertificationAudit: '/aureon_capital_3p_live_execution_certification_audit.json',
  capitalThreePBlockerBurndownAudit: '/aureon_capital_3p_blocker_burndown_audit.json',
  performanceReadinessAudit: '/aureon_performance_readiness_audit.json',
  aureonMurgeUnityBridge: '/aureon_murge_unity_bridge.json',
  aureonMurgeRuntimeActivation: '/aureon_murge_runtime_activation_stress_audit.json',
  liveTradeSignalFabric: '/aureon_live_trade_signal_fabric.json',
  liveTradeSignalFabricStressAudit: '/aureon_live_trade_signal_fabric_stress_audit.json',
  swarmSearchMappingStressAudit: '/aureon_swarm_search_mapping_stress_audit.json',
  parallelStrategyUnity: '/aureon_parallel_strategy_unity.json',
  parallelStrategyUnityStressAudit: '/aureon_parallel_strategy_unity_stress_audit.json',
  capitalLiveDryStressAudit: '/aureon_capital_ecosystem_live_dry_stress_audit.json',
} as const;
export type LegacyReports = Partial<Record<keyof typeof legacyReportPaths, LegacyReport>>;
type Reader = (path: string, options: RequestOptions) => Promise<LegacyReport>;

/** Fixed public report paths, three concurrent reads, one overall cancellation deadline. */
export async function readLegacyReports(options: RequestOptions, read: Reader = (path, opts) => api.get(path, opts)): Promise<LegacyReports> {
  const controller = new AbortController();
  const abort = () => controller.abort();
  options.signal?.addEventListener('abort', abort, { once: true });
  if (options.signal?.aborted) abort();
  const timer = setTimeout(abort, Math.min(options.timeoutMs ?? 8_000, 8_000));
  const entries = Object.entries(legacyReportPaths) as [keyof LegacyReports, string][];
  const data: LegacyReports = {};
  let cursor = 0;
  try {
    await Promise.all(Array.from({ length: 3 }, async () => {
      while (cursor < entries.length && !controller.signal.aborted) {
        const [key, path] = entries[cursor++];
        try {
          const value = await read(path, { ...options, signal: controller.signal, timeoutMs: Math.min(options.timeoutMs ?? 8_000, 2_000) });
          if (!controller.signal.aborted && value && typeof value === 'object' && !Array.isArray(value)) data[key] = value;
        } catch { /* This cycle has no report for this path; previous data is not retained. */ }
      }
    }));
    return data;
  } finally {
    clearTimeout(timer);
    options.signal?.removeEventListener('abort', abort);
  }
}
export const legacyReportsStore = createReadOnlyPoller({ read: readLegacyReports, receiptMaxAgeMs: 45_000 });

/** Original report-generation clock only. This does not attest its underlying provider inputs. */
export function currentLegacyReport<T>(value: unknown, now = Date.now(), maxAgeSec = 120): T | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null;
  const report = value as LegacyReport;
  const source = typeof report.generated_at === 'string' ? Date.parse(report.generated_at) : NaN;
  const age = now - source;
  if (!Number.isFinite(source) || source <= 0 || age < -5_000 || age > maxAgeSec * 1_000 || report.stale === true || report.generated_values === true || report.simulated === true) return null;
  return report as T;
}
