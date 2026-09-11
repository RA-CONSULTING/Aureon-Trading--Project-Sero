import { freshTerminalQuotes, streamFreshness, type TerminalState } from './terminalStateContract';

export type QuoteExpiryDeadlines = { nextQuoteExpiresAtMs: number | null; streamExpiresAtMs: number | null };

/** Absolute deadlines: receiving or rendering an old quote never extends them. */
export function terminalQuoteExpiryDeadlines(state: TerminalState | null, error: string | null,
  receivedAtMs: number | null, nowMs = Date.now()): QuoteExpiryDeadlines {
  const none = { nextQuoteExpiresAtMs: null, streamExpiresAtMs: null };
  if (streamFreshness(state, error, receivedAtMs, nowMs).status !== 'fresh') return none;
  const stream = state!.live_stream_cache!;
  const limitMs = (typeof stream.max_age_sec === 'number' && Number.isFinite(stream.max_age_sec)
    && stream.max_age_sec > 0 ? stream.max_age_sec : 5) * 1_000;
  const cacheDeadline = Date.parse(stream.generated_at!) + limitMs;
  const quotes = freshTerminalQuotes(state, receivedAtMs, nowMs);
  const deadlines = quotes.map(quote => {
    const sourceDeadline = quote.timestamp! * 1_000 + limitMs;
    const reportedDeadline = receivedAtMs !== null && typeof quote.age_sec === 'number' && Number.isFinite(quote.age_sec)
      ? receivedAtMs + limitMs - quote.age_sec * 1_000 : Infinity;
    return Math.min(sourceDeadline, reportedDeadline);
  });
  if (Array.isArray(stream.quotes)) {
    if (!deadlines.length) return none;
    return { nextQuoteExpiresAtMs: Math.min(cacheDeadline, ...deadlines),
      streamExpiresAtMs: Math.min(cacheDeadline, Math.max(...deadlines)) };
  }
  const legacyReportedDeadline = receivedAtMs !== null && typeof stream.oldest_selected_age_sec === 'number'
    && Number.isFinite(stream.oldest_selected_age_sec)
    ? receivedAtMs + limitMs - stream.oldest_selected_age_sec * 1_000 : Infinity;
  return { nextQuoteExpiresAtMs: null, streamExpiresAtMs: Math.min(cacheDeadline, legacyReportedDeadline) };
}

export type ExpiryClock = {
  now: () => number;
  setTimeout: (callback: () => void, delayMs: number) => unknown;
  clearTimeout: (handle: unknown) => void;
};
const browserClock: ExpiryClock = {
  now: Date.now,
  setTimeout: (callback, delayMs) => setTimeout(callback, delayMs),
  clearTimeout: handle => clearTimeout(handle as ReturnType<typeof setTimeout>),
};

/** One cancellable timeout, including an immediate refresh if commit was late. */
export function scheduleQuoteExpiry(deadlineMs: number | null, callback: () => void,
  clock: ExpiryClock = browserClock): () => void {
  if (deadlineMs === null || !Number.isFinite(deadlineMs)) return () => {};
  const handle = clock.setTimeout(callback, Math.max(0, Math.ceil(deadlineMs - clock.now())));
  return () => clock.clearTimeout(handle);
}
