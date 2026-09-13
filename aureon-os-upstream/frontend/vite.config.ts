import { defineConfig } from "vite";
import react from "@vitejs/plugin-react-swc";
import path from "path";
import { componentTagger } from "lovable-tagger";
import {
  createLoopbackIngressPlugin,
  createLoopbackProxyRoute,
  operatorAuthorizationConfig,
} from "./config/operatorProxySecurity";
import { reviewedPublicAssetsPlugin } from "./config/reviewedPublicAssets";

// https://vitejs.dev/config/
export default defineConfig(({ mode, isPreview }) => ({
  // Production output receives only the explicit tracked branding/watch
  // allowlist below. Vite must never copy ignored local runtime JSON from
  // frontend/public into an anonymously reachable Cloud Run asset.
  publicDir: false,
  server: {
    host: "127.0.0.1",
    port: 5173,
    strictPort: true,
    // HFT desk / operator glass: default proxy /api -> operator:8080 (spec). Override with AUREON_OPERATOR_URL or VITE_OPERATOR_URL.
    // Dev had no equivalent, so every /api/* call from the console 404'd against
    // Vite itself â€” including /api/cognition/field, which feeds the HNC-derived
    // visuals. Point dev at the operator so measured readings work locally too.
    proxy: {
      "^/api/orca-observations$": createLoopbackProxyRoute(
        "orca_observations",
        process.env.AUREON_OPERATOR_URL ?? process.env.VITE_OPERATOR_URL ?? "http://127.0.0.1:8080",
        {
          authorization: operatorAuthorizationConfig(
            process.env.AUREON_UI_AUTH_MODE,
            process.env.AUREON_OPERATOR_PROXY_BEARER,
          ),
          // The operator owns the sanitized passive projection. No Orca
          // mutation route or standalone provider reader is started.
        },
      ),
      "/api/terminal-state": createLoopbackProxyRoute(
        "terminal_state",
        process.env.AUREON_TERMINAL_STATE_URL ?? "http://127.0.0.1:8791",
      ),
      "/api/flight-test": createLoopbackProxyRoute(
        "flight_test",
        process.env.AUREON_TERMINAL_STATE_URL ?? "http://127.0.0.1:8791",
      ),
      "/api": createLoopbackProxyRoute(
        "operator",
        process.env.AUREON_OPERATOR_URL ?? process.env.VITE_OPERATOR_URL ?? "http://127.0.0.1:8080",
        {
          authorization: operatorAuthorizationConfig(
            process.env.AUREON_UI_AUTH_MODE,
            process.env.AUREON_OPERATOR_PROXY_BEARER,
          ),
        },
      ),
    },
  },
  preview: {
    host: "127.0.0.1",
  },
  plugins: [
    reviewedPublicAssetsPlugin(),
    createLoopbackIngressPlugin(Boolean(isPreview)),
    react(),
    mode === "development" && componentTagger(),
  ].filter(Boolean),
  resolve: {
    alias: [
      {
        find: /^@\/integrations\/supabase\/client$/,
        replacement: path.resolve(__dirname, "./src/integrations/supabase/client.ts"),
      },
      {
        find: "@",
        replacement: path.resolve(__dirname, "./src"),
      },
    ],
  },
  // Unit tests live beside the source in src/**; tests/ belongs to Playwright
  // (see playwright.config.ts testDir), whose specs cannot run under vitest.
  test: {
    include: ["src/**/*.{test,spec}.{ts,tsx}"],
    exclude: ["tests/**", "node_modules/**", "dist/**"],
  },
  build: {
    // The big trading/console route chunks (WarRoom, LegacyConsole) and recharts
    // legitimately exceed 500 kB; raise the warning bar so real regressions stand
    // out instead of drowning in expected noise. Splitting them further is staged.
    chunkSizeWarningLimit: 800,
    // Route-level chunks come from React.lazy in src/shell/nav.ts; these split
    // the big vendor groups so no chunk carries the whole platform.
    rollupOptions: {
      output: {
        manualChunks: {
          "vendor-react": ["react", "react-dom", "react-router-dom"],
          "vendor-radix": [
            "@radix-ui/react-dialog",
            "@radix-ui/react-dropdown-menu",
            "@radix-ui/react-popover",
            "@radix-ui/react-scroll-area",
            "@radix-ui/react-select",
            "@radix-ui/react-tabs",
            "@radix-ui/react-toast",
            "@radix-ui/react-tooltip",
          ],
          "vendor-charts": ["recharts"],
          "vendor-supabase": ["@supabase/supabase-js"],
        },
      },
    },
  },
}));


