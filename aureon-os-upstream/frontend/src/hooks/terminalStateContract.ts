export type TerminalVenue = {
  venue?: string;
  market_type?: string;
  ready?: boolean;
  candidate_count?: number;
  ready_candidate_count?: number;
  blockers?: string[];
  trade_path_state?: string;
};

export type TerminalQuote = {
  symbol: string; base?: string; quote?: string; price?: number; bid?: number; ask?: number;
  source?: string; timestamp?: number; timestamp_kind?: string; age_sec?: number;
};

export type TerminalPrismReceipt = {
  available?: boolean;
  truth_status?: string;
  generated_values?: boolean;
  source_timestamp?: number | null;
  source_timestamp_iso?: string | null;
  expires_at?: number | null;
  expires_at_iso?: string | null;
  source?: string | null;
  reason?: string | null;
  frequency?: number;
  state?: string;
  level?: number;
  resonance?: number;
  harmonic_purity?: number;
  love_locked?: boolean;
  layers?: Record<string, number>;
  [key: string]: unknown;
};

export type TerminalPosition = {
  symbol?: string;
  side?: string;
  quantity?: number;
  pnl?: number;
  pnlPercent?: number;
  entry_price?: number;
  current_price?: number;
  currency?: string;
  [key: string]: unknown;
};

export type TerminalProviderPositionVenue = {
  available?: boolean;
  count?: number;
  truth_status?: string;
  reason?: string | null;
  source_timestamp?: number | null;
  positions?: TerminalPosition[];
  [key: string]: unknown;
};

export type TerminalProviderPositions = {
  kraken?: TerminalProviderPositionVenue;
  capital?: TerminalProviderPositionVenue;
  alpaca?: TerminalProviderPositionVenue;
  binance?: TerminalProviderPositionVenue;
  [key: string]: unknown;
};

export type TerminalEcosystemReceipt = {
  available?: boolean;
  truth_status?: string;
  generated_values?: boolean;
  source_timestamp?: number | null;
  source_timestamp_iso?: string | null;
  expires_at?: number | null;
  expires_at_iso?: string | null;
  source?: string | null;
  reason?: string | null;
  global_resonance?: number;
  market_energy?: number;
  ecosystem_coherence?: number;
  dominant_frequency?: number;
  active_waveforms?: string[];
  systems?: Record<string, unknown>;
  [key: string]: unknown;
};

export type TerminalPrimeSealReceipt = {
  available?: boolean;
  truth_status?: string;
  generated_values?: boolean;
  source_timestamp?: number | null;
  source_timestamp_iso?: string | null;
  expires_at?: number | null;
  expires_at_iso?: string | null;
  source?: string | null;
  reason?: string | null;
  prime_coherence?: number;
  seal_lock?: boolean;
  systems_contributing?: string[];
  consensus_signal?: string;
  intent_text?: string;
  packet_value?: number;
  [key: string]: unknown;
};

export type TerminalProbabilityFusionReceipt = {
  available?: boolean;
  truth_status?: string;
  generated_values?: boolean;
  source_timestamp?: number | null;
  source_timestamp_iso?: string | null;
  expires_at?: number | null;
  expires_at_iso?: string | null;
  source?: string | null;
  reason?: string | null;
  fused_probability?: number;
  fusedProbability?: number;
  action?: string;
  confidence?: number;
  wave_state?: string;
  waveState?: string;
  harmonic_lock?: boolean;
  harmonicLock?: boolean;
  probability6D?: number;
  probability_6d?: number;
  probabilityHNC?: number;
  probability_hnc?: number;
  probabilityLighthouse?: number;
  probability_lighthouse?: number;
  weight6D?: number;
  weight_6d?: number;
  weightHNC?: number;
  weight_hnc?: number;
  weightLighthouse?: number;
  weight_lighthouse?: number;
  resonance_boost?: number;
  [key: string]: unknown;
};

export type TerminalDecisionTrace = {
  decision_trace_id?: string;
  t_intel_seen?: number;
  t_signal_scored?: number;
  t_intent_ready?: number;
  t_exec_dispatched?: number;
  t_exchange_ack?: number;
  t_state_converged?: number;
  venue?: string;
  symbol?: string;
  side?: string;
  stage_statuses?: Record<string, unknown>;
  [key: string]: unknown;
};

export type TerminalLatencyPercentile = {
  p50?: number;
  p95?: number;
  p99?: number;
  sample_count?: number;
  [key: string]: unknown;
};

export type TerminalDecisionLatencyPercentiles = {
  venues?: Record<string, TerminalLatencyPercentile>;
  [key: string]: unknown;
};

export type TerminalState = {
  ok?: boolean;
  stale?: boolean;
  booting?: boolean;
  duplicate_runtime?: boolean;
  source?: string;
  generated_at?: string;
  stale_reason?: string;
  last_tick_completed_at?: string | null;
  last_tick_age_sec?: number | null;
  tick_phase?: string;
  errors?: { last_tick_error?: string; [key: string]: string | undefined };
  trading_ready?: boolean;
  data_ready?: boolean;
  runtime_writer?: { pid?: number | null; heartbeat_at?: string | null; owns_lock?: boolean };
  live_stream_cache?: { source?: string; fresh?: boolean; usable_for_decision?: boolean; symbol_count?: number; reason?: string; generated_at?: string | null; observed_at?: string; max_age_sec?: number; newest_selected_age_sec?: number; oldest_selected_age_sec?: number; quotes?: TerminalQuote[] };
  hnc_cognitive_proof?: { master_formula?: { score?: number }; real_data?: Record<string, unknown>; [key: string]: unknown };
  hnc_operating_cycle?: { master_formula_score?: number; auris_coherence?: number; [key: string]: unknown };
  trading_gate_evidence?: Record<string, unknown>;
  exchanges?: {
    kraken_ready?: boolean;
    binance_ready?: boolean;
    alpaca_ready?: boolean;
    capital_ready?: boolean;
    all_four_connected?: boolean;
    ready_execution_venue_count?: number;
    execution_venues?: Record<string, TerminalVenue>;
  };
  combined?: { open_positions?: number; kraken_equity?: number; capital_equity_gbp?: number; portfolio_balances?: Record<string, Record<string, number>> };
  exchange_action_plan?: {
    candidate_count?: number | null;
    executor_enabled?: boolean;
    order_intent_publish_enabled?: boolean;
    live_enabled?: boolean;
    real_orders_disabled?: boolean;
    exchange_mutations_disabled?: boolean;
    order_intents_published?: number;
    global_blockers?: string[];
    global_clearances?: string[];
    runtime_clearances?: string[];
    runtime_clearances_required?: string[];
    trade_path_state?: string;
  };
  runtime_watchdog?: {
    tick_stale?: boolean;
    tick_long_running?: boolean;
    tick_active?: boolean;
    tick_stale_after_sec?: number;
    status_file_fresh?: boolean;
    severity?: string;
    recovery_action?: string;
  };
  runtime_stall_diagnostic?: { reason?: string };
  prism_receipt?: TerminalPrismReceipt;
  provider_positions?: TerminalProviderPositions;
  ecosystem_receipt?: TerminalEcosystemReceipt;
  prime_seal_receipt?: TerminalPrimeSealReceipt;
  probability_fusion_receipt?: TerminalProbabilityFusionReceipt;
  decision_traces?: TerminalDecisionTrace[];
  decision_latency_percentiles?: TerminalDecisionLatencyPercentiles;
  [key: string]: unknown;
};

export type TerminalFreshness = {
  status: "loading" | "fresh" | "stale" | "unavailable";
  reason: string;
  source: string;
  sourceTimestamp: string | null;
  sourceAgeSec: number | null;
  receivedAt: string | null;
};

/** A transport receipt or a status-file heartbeat cannot refresh a market tick. */
export function terminalFreshness(state: TerminalState | null, error: string | null, receivedAtMs: number | null, nowMs = Date.now()): TerminalFreshness {
  const timestamp = typeof state?.last_tick_completed_at === "string" ? state.last_tick_completed_at : null;
  // The current producer emits local datetime.now() values. Preserve their
  // local semantics; never append Z and silently change their instant.
  const sourceMs = timestamp ? Date.parse(timestamp) : NaN;
  const elapsedSec = receivedAtMs == null ? 0 : Math.max(0, nowMs - receivedAtMs) / 1_000;
  const reportedAge = state?.last_tick_age_sec;
  const wallAgeSec = Number.isFinite(sourceMs) ? (nowMs - sourceMs) / 1_000 : null;
  const sourceAgeSec = wallAgeSec == null ? null : Math.max(0, wallAgeSec,
    typeof reportedAge === "number" && Number.isFinite(reportedAge) ? reportedAge + elapsedSec : 0);
  const threshold = state?.runtime_watchdog?.tick_stale_after_sec;
  const maxAgeSec = typeof threshold === "number" && Number.isFinite(threshold) && threshold > 0 ? threshold : 45;
  let reason = "Fresh completed runtime tick";
  let status: TerminalFreshness["status"] = "fresh";
  if (error) { status = "unavailable"; reason = error; }
  else if (!state) { status = "loading"; reason = "Waiting for a terminal observation"; }
  else if (!Number.isFinite(sourceMs)) { status = "unavailable"; reason = "Completed tick timestamp unavailable"; }
  else if (wallAgeSec! < -5) { status = "stale"; reason = "Completed tick timestamp is in the future"; }
  else if (sourceAgeSec! > maxAgeSec) { status = "stale"; reason = `Completed tick exceeds ${maxAgeSec}s freshness limit`; }
  else if (state.ok !== true || state.stale !== false || state.booting === true || state.duplicate_runtime === true || state.runtime_watchdog?.tick_stale === true || state.runtime_watchdog?.tick_long_running === true || state.runtime_watchdog?.status_file_fresh === false) {
    status = "stale";
    reason = state.stale_reason || (state.booting ? "Runtime booting" : "Runtime did not attest a fresh healthy tick");
  }
  return { status, reason, source: state?.source || "terminal-state source unreported", sourceTimestamp: timestamp,
    sourceAgeSec, receivedAt: receivedAtMs == null ? null : new Date(receivedAtMs).toISOString() };
}

/** Fail closed for older consumers that still inspect readiness flags directly. */
export function freshnessGatedState(state: TerminalState | null, freshness: TerminalFreshness): TerminalState | null {
  if (!state || freshness.status === "fresh") return state;
  return {
    ...state, ok: false, stale: true, stale_reason: freshness.reason, data_ready: false, trading_ready: false,
    exchanges: state.exchanges ? {
      ...state.exchanges, kraken_ready: false, binance_ready: false, alpaca_ready: false, capital_ready: false, all_four_connected: false,
      ready_execution_venue_count: 0,
      execution_venues: Object.fromEntries(Object.entries(state.exchanges.execution_venues ?? {}).map(([key, venue]) => [key,
        { ...venue, ready: false, trade_path_state: "observation_unavailable" }]))
    } : undefined,
    exchange_action_plan: state.exchange_action_plan ? { ...state.exchange_action_plan, executor_enabled: false, trade_path_state: "observation_unavailable" } : undefined,
  };
}

/** Expire individual provider events without hiding other current quotes. */
export function freshTerminalQuotes(state: TerminalState | null, receivedAtMs: number | null, nowMs = Date.now()): TerminalQuote[] {
  const stream = state?.live_stream_cache;
  const limit = typeof stream?.max_age_sec === 'number' && stream.max_age_sec > 0 ? stream.max_age_sec : 5;
  const elapsed = receivedAtMs == null ? 0 : Math.max(0, nowMs - receivedAtMs) / 1_000;
  return (Array.isArray(stream?.quotes) ? stream.quotes : []).filter(quote => {
    if (typeof quote.timestamp !== 'number' || !Number.isFinite(quote.timestamp) || quote.timestamp <= 0
      || typeof quote.price !== 'number' || !Number.isFinite(quote.price) || quote.price <= 0 || !quote.symbol) return false;
    const age = (nowMs - quote.timestamp * 1_000) / 1_000;
    const reported = typeof quote.age_sec === 'number' && Number.isFinite(quote.age_sec) ? quote.age_sec + elapsed : age;
    return age >= -5 && Math.max(age, reported) < limit;
  });
}

/** The separately observed quote cache may be fresh while the trader is stalled. */
export function streamFreshness(state: TerminalState | null, error: string | null, receivedAtMs: number | null, nowMs = Date.now()): TerminalFreshness {
  const stream = state?.live_stream_cache;
  const timestamp = stream?.generated_at ?? null;
  const sourceMs = timestamp ? Date.parse(timestamp) : NaN;
  const elapsedSec = receivedAtMs == null ? 0 : Math.max(0, nowMs - receivedAtMs) / 1_000;
  const usableQuotes = freshTerminalQuotes(state, receivedAtMs, nowMs);
  const hasQuoteRows = Array.isArray(stream?.quotes);
  const reportedAge = hasQuoteRows && usableQuotes.length
    ? Math.min(...usableQuotes.map(quote => Math.max(0, (nowMs - quote.timestamp! * 1_000) / 1_000))) - elapsedSec
    : stream?.oldest_selected_age_sec;
  const sourceAgeSec = Number.isFinite(sourceMs) ? Math.max(0, (nowMs - sourceMs) / 1_000,
    typeof reportedAge === "number" && Number.isFinite(reportedAge) ? reportedAge + elapsedSec : 0) : null;
  const maxAge = typeof stream?.max_age_sec === "number" && Number.isFinite(stream.max_age_sec) && stream.max_age_sec > 0 ? stream.max_age_sec : 5;
  const sourceFresh = sourceAgeSec != null && sourceAgeSec < maxAge && sourceMs <= nowMs + 5_000;
  const fresh = !error && stream?.fresh === true && sourceFresh && (!hasQuoteRows || usableQuotes.length > 0);
  return { status: fresh ? "fresh" : !state && !error ? "loading" : error || !stream ? "unavailable" : "stale",
    reason: error || (fresh ? "Fresh market-cache observation" : stream?.fresh === true && (!sourceFresh || !usableQuotes.length)
      ? "Market quotes expired since the last successful observation" : stream?.reason || "Market cache is unavailable or expired"),
    source: stream?.source || "market-cache source unreported", sourceTimestamp: timestamp, sourceAgeSec,
    receivedAt: receivedAtMs == null ? null : new Date(receivedAtMs).toISOString() };
}

export function parseTerminalState(payload: unknown): TerminalState {
  const record = (value: unknown): value is Record<string, unknown> => value !== null && typeof value === "object" && !Array.isArray(value);
  const invalid = () => { throw new Error("Invalid terminal-state response"); };
  if (!record(payload) || typeof payload.ok !== "boolean") invalid();
  const root = payload as Record<string, unknown>;
  const check = (row: Record<string, unknown>, strings: string[], numbers: string[], booleans: string[], arrays: string[] = []) => {
    for (const key of strings) if (row[key] != null && typeof row[key] !== "string") invalid();
    for (const key of numbers) if (row[key] != null && (typeof row[key] !== "number" || !Number.isFinite(row[key]))) invalid();
    for (const key of booleans) if (row[key] != null && typeof row[key] !== "boolean") invalid();
    for (const key of arrays) if (row[key] != null && (!Array.isArray(row[key]) || !(row[key] as unknown[]).every(value => typeof value === "string"))) invalid();
  };
  check(root, ['source', 'generated_at', 'last_tick_completed_at', 'stale_reason', 'tick_phase'], ['last_tick_age_sec'], ['stale', 'booting', 'duplicate_runtime', 'data_ready', 'trading_ready']);
  for (const key of ['exchanges', 'exchange_action_plan', 'trading_gate_evidence', 'runtime_watchdog', 'live_stream_cache', 'combined', 'errors', 'prism_receipt', 'provider_positions', 'ecosystem_receipt', 'prime_seal_receipt', 'probability_fusion_receipt', 'decision_latency_percentiles']) {
    if (root[key] != null && !record(root[key])) invalid();
  }
  if (root.decision_traces != null && !Array.isArray(root.decision_traces)) invalid();
  const exchanges = (root.exchanges ?? {}) as Record<string, unknown>;
  check(exchanges, [], ['ready_execution_venue_count'], ['kraken_ready', 'binance_ready', 'alpaca_ready', 'capital_ready', 'all_four_connected']);
  if (exchanges.execution_venues != null) {
    if (!record(exchanges.execution_venues)) invalid();
    for (const venue of Object.values(exchanges.execution_venues)) {
      if (!record(venue)) invalid();
      check(venue as Record<string, unknown>, ['venue', 'market_type', 'trade_path_state'], ['candidate_count', 'ready_candidate_count'], ['ready'], ['blockers']);
    }
  }
  check((root.exchange_action_plan ?? {}) as Record<string, unknown>, ['trade_path_state'], ['candidate_count', 'order_intents_published'], ['executor_enabled', 'order_intent_publish_enabled', 'live_enabled', 'real_orders_disabled', 'exchange_mutations_disabled'], ['global_blockers', 'global_clearances', 'runtime_clearances', 'runtime_clearances_required']);
  check((root.runtime_watchdog ?? {}) as Record<string, unknown>, [], ['tick_stale_after_sec'], ['tick_stale', 'tick_long_running', 'tick_active', 'status_file_fresh']);
  const cache = (root.live_stream_cache ?? {}) as Record<string, unknown>;
  check(cache, ['source', 'generated_at', 'observed_at', 'reason'], ['symbol_count', 'max_age_sec', 'oldest_selected_age_sec'], ['fresh', 'usable_for_decision']);
  if (cache.quotes != null) {
    if (!Array.isArray(cache.quotes)) invalid();
    for (const quote of cache.quotes as unknown[]) {
      if (!record(quote)) invalid();
      check(quote as Record<string, unknown>, ['symbol', 'base', 'quote', 'source', 'timestamp_kind'], ['price', 'bid', 'ask', 'timestamp', 'age_sec'], []);
    }
  }
  check((root.errors ?? {}) as Record<string, unknown>, ['last_tick_error'], [], []);
  const providerPositions = (root.provider_positions ?? {}) as Record<string, unknown>;
  for (const venue of Object.values(providerPositions)) {
    if (!record(venue)) invalid();
    const v = venue as Record<string, unknown>;
    check(v, ['truth_status', 'reason'], ['count', 'source_timestamp'], ['available']);
    if (v.positions != null) {
      if (!Array.isArray(v.positions)) invalid();
      for (const pos of v.positions as unknown[]) {
        if (!record(pos)) invalid();
        check(pos as Record<string, unknown>, ['symbol', 'side', 'currency'], ['quantity', 'pnl', 'pnlPercent', 'entry_price', 'current_price'], []);
      }
    }
  }
  for (const receipt of [root.ecosystem_receipt, root.prime_seal_receipt, root.probability_fusion_receipt]) {
    if (receipt != null) {
      if (!record(receipt)) invalid();
      const r = receipt as Record<string, unknown>;
      check(r, ['truth_status', 'reason', 'source', 'source_timestamp_iso', 'expires_at_iso'], ['source_timestamp', 'expires_at'], ['available', 'generated_values']);
    }
  }
  if (root.decision_latency_percentiles != null) {
    const percentiles = root.decision_latency_percentiles as Record<string, unknown>;
    if (percentiles.venues != null) {
      if (!record(percentiles.venues)) invalid();
      for (const venue of Object.values(percentiles.venues as Record<string, unknown>)) {
        if (!record(venue)) invalid();
        check(venue as Record<string, unknown>, [], ['p50', 'p95', 'p99', 'sample_count'], []);
      }
    }
  }
  if (root.decision_traces != null) {
    for (const trace of root.decision_traces as unknown[]) {
      if (!record(trace)) invalid();
      const t = trace as Record<string, unknown>;
      check(t, ['decision_trace_id', 'venue', 'symbol', 'side'], ['t_intel_seen', 't_signal_scored', 't_intent_ready', 't_exec_dispatched', 't_exchange_ack', 't_state_converged'], []);
      if (t.stage_statuses != null && !record(t.stage_statuses)) invalid();
    }
  }
  return payload as TerminalState;
}
