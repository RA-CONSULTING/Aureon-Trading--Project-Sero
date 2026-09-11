import { useCallback, useSyncExternalStore } from "react";
import { freshnessGatedState, parseTerminalState, streamFreshness, terminalFreshness, type TerminalState } from "./terminalStateContract";
import { scheduleQuoteExpiry, terminalQuoteExpiryDeadlines } from "./terminalQuoteExpiry";
import { api } from "../services/apiClient";
export type { TerminalState, TerminalVenue, TerminalFreshness, TerminalQuote } from "./terminalStateContract";

let observedState: TerminalState | null = null;
let error: string | null = null;
let receivedAtMs: number | null = null;
let transportRttMs: number | null = null;
function makeSnapshot(nowMs = Date.now()) {
  const freshness = terminalFreshness(observedState, error, receivedAtMs, nowMs);
  const marketFreshness = streamFreshness(observedState, error, receivedAtMs, nowMs);
  const state = freshnessGatedState(observedState, freshness);
  if (state?.live_stream_cache && marketFreshness.status !== "fresh") {
    // Clone even a fresh runtime snapshot: raw evidence remains inspectable.
    return { state: { ...state, live_stream_cache: { ...state.live_stream_cache, fresh: false, usable_for_decision: false } },
      observedState, error, freshness, streamFreshness: marketFreshness, isStreamFresh: false,
      isFresh: freshness.status === "fresh", transportRttMs: error ? null : transportRttMs };
  }
  return { state, observedState, error, freshness, streamFreshness: marketFreshness, isStreamFresh: marketFreshness.status === "fresh",
    isFresh: freshness.status === "fresh", transportRttMs: error ? null : transportRttMs };
}
let snapshot = makeSnapshot();
const subscribers = new Map<() => void, number>();
let pollTimer: ReturnType<typeof setTimeout> | undefined;
let ageTimer: ReturnType<typeof setInterval> | undefined;
let activeRequest: AbortController | null = null;
let cancelStreamExpiry: (() => void) | undefined;
function publish() {
  const nowMs = Date.now();
  snapshot = makeSnapshot(nowMs);
  cancelStreamExpiry?.();
  cancelStreamExpiry = undefined;
  if (subscribers.size && snapshot.isStreamFresh) {
    // Route-level labels need a notification only when the overall stream
    // expires, not on every individual quote. This never starts a request.
    const { streamExpiresAtMs } = terminalQuoteExpiryDeadlines(observedState, error, receivedAtMs, nowMs);
    cancelStreamExpiry = scheduleQuoteExpiry(streamExpiresAtMs, publish);
  }
  subscribers.forEach((_, listener) => listener());
}

async function refresh() {
  if (activeRequest || !subscribers.size) return;
  const controller = new AbortController();
  activeRequest = controller;
  const started = performance.now();
  const timeout = setTimeout(() => controller.abort(), 10_000);
  try {
    const next = parseTerminalState(await api.get<unknown>("/api/terminal-state", { signal: controller.signal, timeoutMs: 10_000 }));
    if (activeRequest !== controller) return;
    observedState = next;
    receivedAtMs = Date.now();
    transportRttMs = Math.round(performance.now() - started);
    error = null;
  } catch (reason) {
    if (activeRequest !== controller) return;
    error = controller.signal.aborted ? "Terminal state request timed out" : reason instanceof Error ? reason.message : "Terminal state unavailable";
  } finally {
    clearTimeout(timeout);
    if (activeRequest === controller) {
      activeRequest = null;
      publish();
      if (subscribers.size) pollTimer = setTimeout(() => void refresh(), Math.min(...subscribers.values()));
    }
  }
}

/** Drop private provider receipts and any in-flight response when identity changes. */
export function invalidateTerminalState() {
  clearTimeout(pollTimer);
  const request = activeRequest;
  activeRequest = null;
  request?.abort();
  observedState = null;
  receivedAtMs = null;
  transportRttMs = null;
  error = null;
  publish();
  if (subscribers.size) void refresh();
}

/** One read-only poller shared by all cards; aging continues between requests. */
export function useTerminalState(intervalMs = 3_000) {
  const subscribe = useCallback((listener: () => void) => {
    subscribers.set(listener, Math.max(1_000, intervalMs));
    if (subscribers.size === 1) {
      publish();
      ageTimer = setInterval(publish, 1_000);
      void refresh();
    }
    return () => {
      subscribers.delete(listener);
      if (!subscribers.size) {
        clearTimeout(pollTimer);
        clearInterval(ageTimer);
        cancelStreamExpiry?.();
        cancelStreamExpiry = undefined;
        const request = activeRequest;
        activeRequest = null;
        request?.abort();
      }
    };
  }, [intervalMs]);
  return useSyncExternalStore(subscribe, () => snapshot, () => snapshot);
}
