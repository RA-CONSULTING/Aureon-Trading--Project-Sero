import { createRoot } from "react-dom/client";
import { RouterProvider } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import "./index.css";
import { initNetworkMonitoring } from "./core/networkMonitor";
import { ThemeProvider } from "./components/theme-provider";
import { TooltipProvider } from "./components/ui/tooltip";
import { Toaster } from "./components/ui/toaster";
import { Toaster as Sonner } from "./components/ui/sonner";
import { router } from "./shell/routes";
import { setAuthTokenProvider } from "./services/apiClient";
import { supabase } from "./integrations/supabase/client";
import { invalidateReadOnlyPollers } from "./services/readOnlyPoller";
import { invalidateTerminalState } from "./hooks/useTerminalState";

// Initialize network monitoring before app renders
initNetworkMonitoring();

// Forward the end-user session token to every /api/* call so the operator can
// identify the tenant. No session ⇒ no header ⇒ single-operator path unchanged.
setAuthTokenProvider(async () => {
  const { data, error } = await supabase.auth.getSession();
  if (error) throw error;
  return data.session?.access_token ?? null;
});

const queryClient = new QueryClient();

// Run outside the auth callback so a new read can safely resolve its session.
// No previous account response may survive a sign-in, sign-out or token change.
let sessionRefreshTimer: number | undefined;
const { data: authEvents } = supabase.auth.onAuthStateChange(() => {
  window.clearTimeout(sessionRefreshTimer);
  sessionRefreshTimer = window.setTimeout(() => {
    queryClient.clear();
    invalidateReadOnlyPollers();
    invalidateTerminalState();
  }, 0);
});
if (import.meta.hot) {
  import.meta.hot.dispose(() => {
    window.clearTimeout(sessionRefreshTimer);
    authEvents.subscription.unsubscribe();
  });
}

// Providers wrap the whole app. Auth is enforced per-route (the operator console
// only) inside the router, so the public front door stays open even in production;
// the support-the-project card is mounted inside the console, not globally.
createRoot(document.getElementById("root")!).render(
  <ThemeProvider defaultTheme="dark">
    <QueryClientProvider client={queryClient}>
      <TooltipProvider>
        <Toaster />
        <Sonner />
        <RouterProvider router={router} />
      </TooltipProvider>
    </QueryClientProvider>
  </ThemeProvider>
);
