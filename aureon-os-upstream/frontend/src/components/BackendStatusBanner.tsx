/**
 * BackendStatusBanner — an honest app-wide signal of operator pulse health.
 *
 * The terminal-state feed is a separate local read-only surface. When that
 * feed is fresh, do not tell the operator that the whole stack is offline just
 * because the richer pulse call is slow.
 */
import { useState } from "react";
import { AlertTriangle, X } from "lucide-react";

import { useOperatorPulse } from "@/hooks/useOperatorPulse";
import { useTerminalState } from "@/hooks/useTerminalState";

export function BackendStatusBanner() {
  const { offline, loading } = useOperatorPulse();
  const { state: terminalState, error: terminalError, isStreamFresh } = useTerminalState();
  const [dismissed, setDismissed] = useState(false);
  const terminalFeedFresh =
    Boolean(terminalState) &&
    !terminalError &&
    terminalState.data_ready === true &&
    terminalState.stale !== true;

  // A fresh terminal feed is enough to keep the live trading surface usable;
  // only show this notice when both the pulse and terminal feed are unavailable.
  if (loading || !offline || terminalFeedFresh || dismissed) return null;

  return (
    <div
      role="status"
      aria-live="polite"
      className="flex items-start gap-3 border-b border-destructive/30 bg-destructive/10 px-4 py-2 text-sm text-destructive-foreground"
    >
      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-destructive" aria-hidden />
      <div className="min-w-0 flex-1">
        <span className="font-medium text-destructive">Operator pulse unavailable.</span>{" "}
        <span className="text-muted-foreground">
          {isStreamFresh
            ? 'Market quotes are current. Runtime analysis is unavailable or stale.'
            : 'Current runtime observations are unavailable or stale. See each panel for its source status.'}
        </span>
      </div>
      <button
        type="button"
        onClick={() => setDismissed(true)}
        aria-label="Dismiss backend status notice"
        className="shrink-0 rounded p-0.5 text-muted-foreground transition-colors hover:text-foreground"
      >
        <X className="h-4 w-4" aria-hidden />
      </button>
    </div>
  );
}

export default BackendStatusBanner;
