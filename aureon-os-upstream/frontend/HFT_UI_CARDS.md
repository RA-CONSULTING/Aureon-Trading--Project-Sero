# HFT Desk evidence contract — 2026-09-08

Route: `/trading/hft`. Page: `src/shell/pages/HftDeskPage.tsx`.

All desk data is read through the shared `useTerminalState` poller. Vite's exact
`/api/terminal-state` proxy targets the read-only status service on port 8791;
the general operator API proxy targets port 8080. The desk creates no trading
session, order, mode change, or competing market-feed connection.

| Surface | Evidence | Missing or stale behavior |
|---|---|---|
| Runtime state | Completed tick timestamp, source age, runtime and watchdog flags | Explicit stale/unavailable banner; readiness cannot remain green |
| Venue routes | `exchanges.execution_venues` and exchange flags | Missing counts display a dash; stale routes are unavailable |
| Market tape | Independently refreshed `live_stream_cache.quotes` | Quote rows clear when cache expires or transport fails |
| Quote provenance | Provider source, observation timestamp, timestamp kind, quote currency | Missing fields remain unreported |
| UI HTTP RTT | Measured terminal-state request duration | This is a browser HTTP measurement, never execution latency |
| Accounts and positions | Existing provider HTTP receipt sidecars | Independent source/receipt timestamps; no inferred reconciled ledger count |
| OMS | `exchange_action_plan.order_intents_published` | No session queue or exchange acknowledgement inferred |
| Execution holds | Actual `exchange_action_plan.global_blockers` | Missing blockers do not imply permission |
| Fills, hold-time, latency traces | No provider rows available in current contract | Explicit empty evidence; no totals, ranking, or percentiles |

The poller shares one request stream across mounted cards, avoids overlapping
requests, times out stalled requests, and ages the source every second between
polls. HTTP receipts and file heartbeats never refresh a completed runtime tick.
The market cache is evaluated independently so fresh provider quotes remain
visible during a slow runtime tick; failed transport makes both unavailable.
Raw last observations remain available for diagnostics, separately from the
freshness-gated compatibility state.

The desk no longer mounts browser-only trading mode, Supabase hunt controls,
legacy trade-validation totals, the separate Binance browser feed, or an empty
leaderboard that would manufacture zero performance totals. A live execution
control requires its own governed backend command contract and readback.

Verification: `node --import tsx --test tests/terminal-freshness.test.ts` exercises
source aging, repeated stale receipts, clock and watchdog errors, malformed
payload rejection, fail-closed execution flags, and independent stream freshness.
These tests use isolated test fixtures; they do not supply data to the UI.

Provider account projections are captured only at existing HTTP response
boundaries in the Capital, Kraken, Binance, and Alpaca clients. They add no
provider calls. Cache hits preserve the original timestamps. Paper/testnet data
is excluded. HTTP Date and locally measured HTTP receipt times are labelled
separately; account update timestamps never stand in for snapshot freshness.
Kraken total balances do not imply available cash, and Alpaca equity, cash, and
buying power remain distinct. These observations do not grant trading, fill,
fee-reconciliation, or accounting eligibility.
