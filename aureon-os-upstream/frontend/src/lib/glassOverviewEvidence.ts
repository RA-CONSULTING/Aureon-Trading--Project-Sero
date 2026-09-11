import type { TerminalQuote, TerminalState } from '../hooks/terminalStateContract';
import { evidenceNumber as number, evidenceRecord as record, evidenceText as text } from './warRoomEvidence';

export type GlassCandidate = { key: string; symbol: string; venue: string; side: string; confidence: number | null };

/** Candidate totals use their own measured receipt, rather than cached plan totals. */
export function currentCandidateCount(state: TerminalState | null, connected: boolean, nowMs = Date.now()): number | null {
  const receipt = record(record(state?.exchange_action_plan).candidate_evidence);
  const timestamp = number(receipt.source_timestamp);
  const expires = number(receipt.expires_at);
  const count = number(receipt.active_order_flow_count);
  if (!connected || receipt.available !== true || receipt.generated_values !== false || receipt.truth_status !== 'real_derived'
    || timestamp === null || expires === null || timestamp <= 0 || timestamp > nowMs / 1000 + 5
    || nowMs / 1000 - timestamp > 30 || expires <= nowMs / 1000 || expires <= timestamp
    || count === null || count < 0 || !Number.isInteger(count)) return null;
  return count;
}

/** Current plan candidates are analysis output; confidence never denotes realized profit. */
export function currentGlassCandidates(state: TerminalState | null, isFresh: boolean, nowMs = Date.now()): GlassCandidate[] {
  if (!isFresh) return [];
  const plan = record(state?.exchange_action_plan);
  const generated = typeof plan.generated_at === 'string' ? Date.parse(plan.generated_at) : NaN;
  const elapsed = (nowMs - generated) / 1000;
  if (!Number.isFinite(generated) || elapsed < -5 || elapsed >= 30) return [];
  const rows: GlassCandidate[] = [];
  for (const [key, rawVenue] of Object.entries(record(plan.venues))) {
    const venue = record(rawVenue);
    if (!Array.isArray(venue.top_candidates)) continue;
    for (const value of venue.top_candidates) {
      const candidate = record(value);
      const symbol = text(candidate.symbol);
      const side = text(candidate.side);
      const age = number(record(candidate.fast_money_profile).freshest_age_sec);
      const confidence = number(candidate.confidence);
      if (!symbol || !side || age === null || age < 0 || age + Math.max(0, elapsed) >= 5) continue;
      rows.push({ key: `${key}:${symbol}:${side}`, symbol, venue: text(venue.venue) ?? key, side,
        confidence: confidence !== null && confidence >= 0 && confidence <= 1 ? confidence : null });
    }
  }
  return [...new Map(rows.map(row => [row.key, row])).values()].sort((a, b) => (b.confidence ?? -1) - (a.confidence ?? -1));
}

export type ObservedCandle = { timestamp: number; open: number; high: number; low: number; close: number; samples: number };
export type QuoteSample = { timestamp: number; price: number };
export function appendObservedQuote(samples: QuoteSample[], quote: TerminalQuote | undefined): QuoteSample[] {
  if (!quote || number(quote.timestamp) === null || number(quote.price) === null || quote.timestamp! <= 0 || quote.price! <= 0
    || samples.some(sample => sample.timestamp === quote.timestamp)) return samples;
  return [...samples, { timestamp: quote.timestamp!, price: quote.price! }].sort((a, b) => a.timestamp - b.timestamp).slice(-600);
}

/** Sparse sampled ticks only: never fill empty minutes or invent venue OHLC history. */
export function observedCandles(samples: QuoteSample[]): ObservedCandle[] {
  const buckets = new Map<number, ObservedCandle>();
  for (const sample of samples) {
    const timestamp = Math.floor(sample.timestamp / 60) * 60;
    const previous = buckets.get(timestamp);
    buckets.set(timestamp, previous ? { ...previous, high: Math.max(previous.high, sample.price), low: Math.min(previous.low, sample.price),
      close: sample.price, samples: previous.samples + 1 } : { timestamp, open: sample.price, high: sample.price, low: sample.price, close: sample.price, samples: 1 });
  }
  return [...buckets.values()].slice(-24);
}

/** Recorded instrumentation values, explicitly reported in seconds by the producer. */
export function endToEndMedianMs(state: TerminalState | null, connected: boolean, nowMs = Date.now()): number | null {
  const latency = record(state?.decision_latency_percentiles);
  const generated = typeof latency.generated_at === 'string' ? Date.parse(latency.generated_at) : NaN;
  const row = record(latency.end_to_end_sec);
  const value = number(row.p50);
  const count = number(row.count);
  if (!connected || !Number.isFinite(generated) || generated > nowMs + 5000 || nowMs - generated > 60_000
    || value === null || value < 0 || count === null || count < 1 || !Number.isInteger(count)) return null;
  return value * 1000;
}
