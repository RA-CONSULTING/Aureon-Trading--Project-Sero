Historical design reference, superseded by the installed evidence contract. This file is not an operational readiness receipt or a current implementation instruction.

# HFT_UI_CARDS — `/trading/hft` mount map

Claim bar (Buzz): `LatencyHook` / `useLatency` = **UI RTT** only. Never baptise ping as tick→ack.
Trace/SLO strip stays **dark** until persisted `decision_trace_id` JSONL + six timestamps exist in the operator API (`LATENCY_READINESS_PLAN.md`).
Canonical API: Vite proxy `/api` → operator gateway **8080**. Do not treat `:8787` as the execution bus.

Page: `frontend/src/shell/pages/HftDeskPage.tsx`
Nav: `frontend/src/shell/nav.ts` → Trading → **HFT Desk** (`/trading/hft`)
Routes: generated from nav (`frontend/src/shell/routes.tsx`) — no parallel route table edit required.

## Cards mounted

| Glass card | Mounted file | Notes |
|---|---|---|
| Venues | `components/ExchangeStatusSummary.tsx` | One summary (not six venue panels side-by-side). |
| UI RTT | `components/LatencyHook.tsx` (`useLatency`) | Labeled **UI RTT**. Default WS may be `:8787`; value is not execution latency. |
| SLO / p50/p95/p99 | *(inline dark strip in HftDeskPage)* | Dark / none — not derived from UI RTT. |
| Rate-limit headroom | *(dark placeholder)* | Gap until rate-limit registry is on `/api`. |
| Tape | `components/LivePriceTicker.tsx` | Alerts/watchlists **not** mounted as extra cards. |
| Blotter totals | `components/PortfolioSummaryPanel.tsx` | Chose self-contained panel over `MetricsHQ` (needs props). |
| Positions | `components/warroom/ActivePositionsPanel.tsx` | |
| OMS queue | `components/OMSQueueMonitor.tsx` | `sessionId={null}` → component’s empty state. |
| TWAP | **not mounted** | Not proven on live path for this desk. |
| QGITA* | **not mounted** | Drawer deferred; not on glass. |
| Fills | `components/warroom/LiveTradeStream.tsx` | Hunt streams not dual-mounted. |
| Rejects / gates | `components/TradeValidationPanel.tsx` (`compact`) | Display only. |
| Latency trace table | *(inline dark table in HftDeskPage)* | Columns match plan timestamps; empty until API. |
| Sniper hold-time | `components/warroom/SniperLeaderboard.tsx` | Mounted with `symbolStats={[]}` until feed wired. |
| Mode toggle | `components/warroom/TradingModeToggle.tsx` | Toolbar. |
| Hunt on/off | `components/AutomatedHuntControl.tsx` | Toolbar. |

## Explicitly not mounted (out of HFT glass)

War Room mysticism / research / cognition / Queen / neural / Earth-Solar-NOAA / vault-KYC-billing rooms — see operator brief. Also skipped duplicates: `AlpacaStatusPanel`, `BinanceConnectionStatus`, `KrakenStatusPanel`, `CapitalStatusPanel`, `MultiExchangePanel`, `AssetPriceListPanel`, `MarketOverview`, `Watchlist`, `PriceAlerts`, `LiveStrikeStream`, `StrikeFeed`, `TWAPMonitor`, all `QGITA*` surface panels.

## First-cut “done” checklist

1. `/trading/hft` in nav + loads via shell router — **yes**
2. Merged blotter from existing components — **yes**
3. No duplicate same-job cards side by side — **yes**
4. LatencyHook labeled UI RTT — **yes**
5. Trace/SLO dark without real traces — **yes**
6. No new Python HTTP server / port / Queen iframe — **yes**

## Still gaps (honest)

- Live order-book depth DOM — still missing (Python intel only).
- Per-venue rate-limit % — placeholder.
- Wire `decision_trace_id` JSONL into `/api/terminal-state` before this page is an HFT desk (Buzz).

## Theme
Chrome only: zinc / gold / neon-green / cyan (Aureon Zorza palette). No lighthouse, solfeggio, clone-traffic, or harmonic-wave art mounted as HFT instruments. SLO/trace empty states remain **dark / none**.