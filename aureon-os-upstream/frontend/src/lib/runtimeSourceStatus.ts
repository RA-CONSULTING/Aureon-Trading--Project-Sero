export interface RuntimeSourceObservation {
  source?: string;
  source_timestamp?: number | null;
  max_age_seconds?: number;
  fresh?: boolean;
  read_state?: string;
  reason?: string | null;
  cycle?: number | null;
  step?: number | null;
  input_count?: number | null;
  measurement_kind?: string;
}

/** Recheck the producer's original clock as the browser view ages. */
export function runtimeSourceFresh(source: RuntimeSourceObservation | undefined, nowMs: number): boolean {
  if (!source || source.fresh !== true || source.read_state !== "observed") return false;
  const stamp = source.source_timestamp;
  const limit = source.max_age_seconds;
  return typeof stamp === "number" && Number.isFinite(stamp) && stamp > 0
    && typeof limit === "number" && Number.isFinite(limit) && limit > 0 && limit <= 300
    && Number.isFinite(nowMs) && nowMs / 1000 - stamp >= -5 && nowMs / 1000 - stamp <= limit;
}

export function runtimeCount(value: unknown): string {
  return typeof value === "number" && Number.isSafeInteger(value) && value >= 0
    ? value.toLocaleString() : "—";
}
