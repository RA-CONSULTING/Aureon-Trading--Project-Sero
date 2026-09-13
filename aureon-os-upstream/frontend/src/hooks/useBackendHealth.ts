interface HealthCheck {
  status: 'healthy' | 'degraded' | 'unhealthy' | 'not_configured' | 'skipped' | 'error';
  message: string;
  timestamp: string;
  [key: string]: unknown;
}

interface HealthReport {
  timestamp: string;
  overall_status: 'healthy' | 'degraded' | 'unhealthy';
  checks: Record<string, HealthCheck>;
  warnings: string[];
  errors: string[];
}

const PRIVILEGED_HEALTH_UNAVAILABLE =
  'Privileged backend health is unavailable on the tenant surface. Use the protected operator health route when it is implemented.';

const unavailableReport: HealthReport = {
  timestamp: '',
  overall_status: 'unhealthy',
  checks: {
    operator_health: {
      status: 'not_configured',
      message: PRIVILEGED_HEALTH_UNAVAILABLE,
      timestamp: '',
      readState: 'unavailable',
      mutationAuthority: false,
      providerCallsAttempted: 0,
      secretPresenceDisclosed: false,
    },
  },
  warnings: [PRIVILEGED_HEALTH_UNAVAILABLE],
  errors: [],
};

export function useBackendHealth(autoRefresh = false, interval = 30000) {
  void autoRefresh;
  void interval;

  return {
    healthReport: unavailableReport,
    loading: false,
    lastChecked: null,
    refresh: async () => undefined,
  };
}
