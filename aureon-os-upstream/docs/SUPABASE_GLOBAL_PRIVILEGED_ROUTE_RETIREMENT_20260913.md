# Supabase global privileged route retirement audit

Date: 2026-09-13

Scope: the 27 Edge Functions confirmed as deployed in project
`siihxcwetdjdsrfdexmb` that parsed caller bodies and then used
`SUPABASE_SERVICE_ROLE_KEY` without binding write authority to the authenticated
JWT subject.

The platform `verify_jwt = true` setting supplied authentication, but every
handler then bypassed RLS with the service role. Caller-provided `user_id`,
`temporal_id`, trade records, session state, symbols, and protocol identities
therefore did not establish ownership. The two routes that also checked a
shared ingest token still did not bind a write to a JWT subject.

## Observed pre-retirement impact

| Route | Read or external effect | Service-role mutation |
| --- | --- | --- |
| `analyze-stargate-patterns` | Read `stargate_network_states`; external LLM analysis | Insert `harmonic_nexus_states` |
| `forecast-coherence` | Read `coherence_history`; external LLM forecast | None |
| `ingest-10-9-1-packet` | None | Insert `prime_seal_packets` |
| `ingest-6d-harmonic` | None | Insert `harmonic_6d_states` |
| `ingest-adaptive-learning` | None | Insert `adaptive_learning_states` |
| `ingest-decision-fusion` | None | Insert `decision_fusion_states` |
| `ingest-eckoushic-cascade` | None | Insert `eckoushic_cascade_states` |
| `ingest-exchange-learning` | None | Insert `exchange_learning_states` |
| `ingest-ftcp-detector` | None | Insert `ftcp_detector_states` |
| `ingest-integral-aqal` | None | Insert `integral_aqal_states` |
| `ingest-master-equation` | None | Insert `master_equation_field_history` and conditional `lighthouse_events` |
| `ingest-omega-equation` | None | Insert `omega_equation_states` |
| `ingest-planetary-modulation` | None | Insert `planetary_modulation_states` |
| `ingest-prism-state` | None | Insert `prism_transformation_states` |
| `ingest-probability-matrix` | None | Insert `probability_matrix_states` |
| `ingest-rainbow-bridge` | None | Insert `rainbow_bridge_states` |
| `ingest-risk-manager` | None | Insert `risk_manager_states` |
| `ingest-smart-router` | None | Insert `smart_router_states` |
| `ingest-stargate-network` | None | Insert `stargate_network_states` |
| `ingest-telescope-state` | None | Insert `telescope_observations` |
| `ingest-temporal-anchor` | None | Insert `temporal_anchor_states` |
| `ingest-terminal-state` | None | Upsert sessions and trades; update or upsert positions; insert HNC and runtime observations |
| `ingest-ticker-snapshot` | None | Insert `ticker_snapshots` |
| `ingest-trades` | None | Upsert `trade_records` |
| `ingest-unity-event` | None | Insert `unity_event_states` |
| `primelines-protocol-gateway` | Read harmonic history; external LLM validation | Insert `harmonic_nexus_states` and `stargate_network_states` |
| `sync-exchange-assets` | Fetch Binance and Kraken public asset metadata | Upsert `crypto_assets_registry` |

## In-repository caller census

Direct callers existed for pattern analysis, coherence forecasts, telescope and
ticker persistence, asset synchronization, the Primelines gateway, terminal
state, and trade receipt ingestion. They were in:

- `frontend/src/hooks/useStargatePatterns.ts`
- `frontend/src/components/CoherenceForecaster.tsx`
- `frontend/src/components/MultiSymbolForecastComparison.tsx`
- `frontend/src/hooks/useQuantumTelescope.ts`
- `frontend/src/hooks/useTickerStream.ts`
- `frontend/src/hooks/useAvailableAssets.ts`
- `frontend/src/hooks/usePrimelinesProtocol.ts`
- `frontend/src/components/HarmonicNexusPhaseField3D.tsx`
- `aureon/bridges/aureon_ui_bridge.py`
- `aureon/exchanges/kraken_margin_penny_trader.py`

The remaining route-name references in `dataStreamMonitor.ts` were health
inventory entries rather than calls. No runtime caller was found for the other
ingest functions. External callers outside this repository cannot be proven by
a source census.

## Result

All 27 handlers are self-contained `503` stubs with the stable error
`LEGACY_GLOBAL_PRIVILEGED_ROUTE_DISABLED`. They read no body or environment
secret, perform no provider call, and issue no database query or mutation.
`OPTIONS` remains available for CORS and every function keeps
`verify_jwt = true`.

Browser callers now consume read-only data or report the missing governed
operator source. Asset refresh reloads the RLS-protected registry, ticker
polling no longer writes shared snapshots, the local trader only maintains its
local observation payload, and the old UI bridge no longer calls the retired
routes.

Reactivation requires one of these designs:

1. an operator-only publisher authenticated independently of tenant JWTs; or
2. tenant-owned tables with a non-null `user_id`, writes forced to
   `auth.getUser().user.id`, an RLS-scoped client using the caller bearer token,
   replay protection, schema validation, and per-user quotas for external AI or
   provider work.
