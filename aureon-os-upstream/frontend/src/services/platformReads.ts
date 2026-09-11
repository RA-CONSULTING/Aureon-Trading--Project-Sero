import { api } from "./apiClient";
import { createReadOnlyPoller } from "./readOnlyPoller";
import type { RuntimeSourceObservation } from "@/lib/runtimeSourceStatus";
import { readBillingStatus, readRecordedCompanyProfile, readSwitchboardConfiguration } from "../lib/platformConfiguration";
import { readOperatorReleaseReadiness } from "../lib/operatorReleaseReadiness";

export interface PlatformStatus {
  status?: string;
  status_scope?: string;
  reachability_status?: string;
  domains_reachable?: number;
  domains_total?: number;
  product_domains?: Record<string, { status?: string; reachable?: number; total?: number }>;
  operational_core?: { available?: boolean; source_observation?: RuntimeSourceObservation };
  runtime_sources?: Record<string, RuntimeSourceObservation>;
  note?: string;
}

// Import availability is configuration. Source observations retain their own clocks.
export const platformStatusStore = createReadOnlyPoller<PlatformStatus>({
  read: (options) => api.get<PlatformStatus>("/api/status", options),
  receiptMaxAgeMs: 45_000,
});

export const billingStore = createReadOnlyPoller({
  read: async options => readBillingStatus(await api.get("/api/billing/status", options)), receiptMaxAgeMs: 45_000,
});
export const switchboardStore = createReadOnlyPoller({
  read: async options => readSwitchboardConfiguration(await api.get("/api/switchboard", options)), receiptMaxAgeMs: 45_000,
});
export const companyStore = createReadOnlyPoller({
  read: async options => readRecordedCompanyProfile(await api.get("/api/org", options)), receiptMaxAgeMs: 90_000,
});

export const operatorReleaseReadinessStore = createReadOnlyPoller({
  read: async options => readOperatorReleaseReadiness(await api.get("/api/operator/release-readiness", options)),
  receiptMaxAgeMs: 45_000,
});
