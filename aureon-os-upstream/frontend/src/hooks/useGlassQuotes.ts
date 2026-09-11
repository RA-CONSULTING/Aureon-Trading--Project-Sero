import { useLayoutEffect, useState } from 'react';
import { flushSync } from 'react-dom';
import type { useTerminalState } from './useTerminalState';
import { freshTerminalQuotes, streamFreshness } from './terminalStateContract';
import { scheduleQuoteExpiry, terminalQuoteExpiryDeadlines } from './terminalQuoteExpiry';

/** Share the terminal poller and expire displayed provider events at their exact deadlines. */
export function useGlassQuotes(terminal: ReturnType<typeof useTerminalState>) {
  const [revision, expire] = useState(0);
  const received = terminal.streamFreshness.receivedAt ? Date.parse(terminal.streamFreshness.receivedAt) : null;
  const now = Date.now();
  const freshness = streamFreshness(terminal.observedState, terminal.error, received, now);
  const { nextQuoteExpiresAtMs } = terminalQuoteExpiryDeadlines(terminal.observedState, terminal.error, received, now);
  useLayoutEffect(() => scheduleQuoteExpiry(nextQuoteExpiresAtMs, () => flushSync(() => expire(value => value + 1))),
    [nextQuoteExpiresAtMs, terminal.observedState, terminal.error, received, revision]);
  const quotes = freshness.status === 'fresh' ? freshTerminalQuotes(terminal.observedState, received, now) : [];
  return { freshness, quotes: [...new Map(quotes.map(quote => [`${quote.source}:${quote.symbol}`, quote])).values()] };
}
