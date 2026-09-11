import { useOperatorPulse } from "@/hooks/useOperatorPulse";
import { useTerminalState } from "@/hooks/useTerminalState";
import { readWarRoomEvidence } from "@/lib/warRoomEvidence";

export interface HncCoherence {
  gamma: number | null;
  offline: boolean;
  loading: boolean;
  source: string | null;
  sourceTimestamp: string | null;
  reason: string | null;
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function extractPulseCoherence(pulse: Record<string, unknown> | null): number | null {
  if (!pulse) return null;
  const organism = (pulse.organism ?? {}) as Record<string, unknown>;
  const unification = (organism.unification ?? {}) as Record<string, unknown>;
  const gamma = unification.coherence_gamma;
  if (isFiniteNumber(gamma) && gamma >= 0 && gamma <= 1) return gamma;
  return null;
}

/** Fresh, measured Auris coherence.
 * 1. Prefer an explicit HNC coherence value from the operator pulse when the pulse is live.
 * 2. Fall back to the timestamped Auris-node coherence published in terminal-state.
 * 3. Otherwise report unavailable with the reason.
 */
export function useHncCoherence(): HncCoherence {
  const terminal = useTerminalState();
  const pulse = useOperatorPulse(15_000, 20_000);

  const pulseGamma = extractPulseCoherence(pulse.pulse);
  const pulseFresh = pulseGamma !== null && !pulse.loading && !pulse.offline;

  const evidence = readWarRoomEvidence(terminal.state, terminal.isFresh);
  const terminalGamma = evidence.available ? evidence.aurisCoherence : null;

  if (pulseFresh) {
    const ts = pulse.lastOkAt ? new Date(pulse.lastOkAt).toISOString() : null;
    return {
      gamma: pulseGamma,
      offline: false,
      loading: false,
      source: "operator pulse organism.unification.coherence_gamma",
      sourceTimestamp: ts,
      reason: null,
    };
  }

  const gamma = terminalGamma;
  const offline = terminal.freshness.status === "unavailable" || terminal.freshness.status === "stale";
  const loading = terminal.freshness.status === "loading";
  return {
    gamma,
    offline,
    loading,
    source: gamma == null ? null : "terminal-state hnc_cognitive_proof.auris_nodes.coherence",
    sourceTimestamp: evidence.timestamp,
    reason: gamma == null
      ? evidence.available
        ? "Measured Auris coherence is unavailable"
        : evidence.reason
      : null,
  };
}
