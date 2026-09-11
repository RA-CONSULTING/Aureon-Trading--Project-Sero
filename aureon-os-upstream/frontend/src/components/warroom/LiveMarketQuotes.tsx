import { useLayoutEffect, useState, type ReactNode } from "react";
import { flushSync } from "react-dom";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { type useTerminalState, type TerminalQuote } from "@/hooks/useTerminalState";
import { freshTerminalQuotes, streamFreshness } from "@/hooks/terminalStateContract";
import { scheduleQuoteExpiry, terminalQuoteExpiryDeadlines } from "@/hooks/terminalQuoteExpiry";

const numeric = (value: unknown) => typeof value === "number" && Number.isFinite(value) ? value : null;
function Zone({ title, subtitle, children }: { title: string; subtitle: string; children: ReactNode }) {
  return <Card><CardHeader className="pb-2"><CardTitle className="text-sm">{title}</CardTitle><CardDescription>{subtitle}</CardDescription></CardHeader>
    <CardContent className="text-xs">{children}</CardContent></Card>;
}
function EmptyEvidence({ children }: { children: ReactNode }) {
  return <div className="rounded border border-dashed border-zinc-700 p-3 text-zinc-400">{children}</div>;
}

function quoteValue(value: unknown) {
  const number = numeric(value);
  return number != null && number > 0 ? number.toLocaleString(undefined, { maximumSignificantDigits: 10 }) : "—";
}

export function LiveMarketQuotes({ terminal }: { terminal: ReturnType<typeof useTerminalState> }) {
  const [expiryRevision, expire] = useState(0);
  const receivedAt = terminal.streamFreshness.receivedAt ? Date.parse(terminal.streamFreshness.receivedAt) : null;
  const nowMs = Date.now();
  // Badge and rows share this exact clock; only the tape rerenders when an
  // individual quote expires between the shared store's age notifications.
  const freshness = streamFreshness(terminal.observedState, terminal.error, receivedAt, nowMs);
  const isStreamFresh = freshness.status === "fresh";
  const observed: TerminalQuote[] = isStreamFresh ? freshTerminalQuotes(terminal.observedState, receivedAt, nowMs) : [];
  const { nextQuoteExpiresAtMs } = terminalQuoteExpiryDeadlines(terminal.observedState, terminal.error, receivedAt, nowMs);
  // Install before paint, then commit the deadline update in the timeout task.
  // A normal concurrent state update can leave expired rows awaiting a commit.
  useLayoutEffect(() => scheduleQuoteExpiry(nextQuoteExpiresAtMs, () => flushSync(() => expire(revision => revision + 1))),
    [nextQuoteExpiresAtMs, terminal.observedState, terminal.error, receivedAt, expiryRevision]);
  const quotes = [...new Map(observed.map(quote => [`${quote.source}:${quote.symbol}`, quote])).values()];
  return <Zone title="Market tape" subtitle="Observed provider quotes; freshness is independent of runtime tick completion">
    <div className="mb-2 flex flex-wrap gap-2 text-zinc-400">
      <Badge variant="outline" className={isStreamFresh ? "text-green-300" : "text-amber-300"}>{freshness.status.toUpperCase()}</Badge>
      <span>{freshness.source}</span><span>observed {freshness.sourceTimestamp || "unavailable"}</span>
      <span>age {freshness.sourceAgeSec == null ? "—" : `${freshness.sourceAgeSec.toFixed(1)}s`}</span>
    </div>
    {quotes.length ? <div className="max-h-72 overflow-auto"><table className="w-full text-left font-mono">
      <thead className="text-zinc-500"><tr>{["Pair", "Last / price", "Bid", "Ask", "Source", "Observed at", "Timestamp kind"].map(label => <th key={label} className="p-1">{label}</th>)}</tr></thead>
      <tbody>{quotes.map(quote => <tr key={`${quote.source}:${quote.symbol}`} className="border-t border-zinc-800">
        <td className="p-1">{quote.symbol}{quote.quote ? ` (${quote.quote})` : ""}</td>
        <td className="p-1">{quoteValue(quote.price)}</td><td className="p-1">{quoteValue(quote.bid)}</td><td className="p-1">{quoteValue(quote.ask)}</td>
        <td className="p-1">{quote.source || "unreported"}</td><td className="p-1">{numeric(quote.timestamp) != null && Math.abs(quote.timestamp!) < 8_640_000_000_000 ? new Date(quote.timestamp! * 1_000).toISOString() : "unreported"}</td><td className="p-1">{quote.timestamp_kind || "unreported"}</td>
      </tr>)}</tbody>
    </table></div> : <EmptyEvidence>No fresh quote rows available. {freshness.reason}.</EmptyEvidence>}
  </Zone>;
}

