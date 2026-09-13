# Supabase production Edge Function attack-surface closure

The provider read-back on 2026-09-13 returned exactly 100 `ACTIVE` Edge
Functions in project `siihxcwetdjdsrfdexmb`. Forty-six were deployed with
gateway JWT verification disabled. Every deployed bundle was downloaded to a
temporary audit directory and reviewed without invoking the function or any
provider.

The deploy repository is now the authority for all 100 active slugs. Ninety-five
are retired from the Edge plane. Their exact names are pinned in
`production_attack_surface.json`; each maps to a self-contained inert source and
has `verify_jwt = true` in `supabase/config.toml`. This includes the old order,
credential, owner-financial, billing, payment-adjacent, global-state, provider
secret, synthetic-data, weak-authentication, and source-unavailable routes.

Five fixed-host, non-secret, database-free read-only sources are retained:

- `fetch-binance-market-data`
- `fetch-binance-symbols`
- `fetch-historical-data`
- `fetch-noaa-space-weather`
- `fetch-schumann-data`

The current production bundles for `fetch-binance-market-data`,
`fetch-noaa-space-weather`, and `fetch-schumann-data` are stale and must be
replaced. The first currently attaches an owner Binance key to public market
requests. The latter two currently generate some or all response values.
Their local replacements use public fixed-host data, contain no credential
lookup, and emit no random fallback. Schumann output is explicitly labeled as
an NOAA Kp-derived proxy and never as a direct station measurement.

The UI mounted by `frontend/src/shell/routes.tsx` has no Supabase Edge Function
invocation. Tenant and operator behavior remains on the same-origin Cloud Run
and VM control planes. Five additional inactive local routes found by the
review are also inert to prevent accidental future deployment:
`emergency-stop`, `fetch-binance-margin-data`, `gas-tank-deduct-fee`,
`unified-field-analysis`, and `update-bot-credentials`.

Before deployment, run:

```text
python scripts/validation/audit_supabase_production_edge_surface.py
```

Deploy only `all_deploy_targets` from the JSON inventory and do not use a flag
that disables JWT verification. Provider read-back must then prove:

1. every retirement target reports `verify_jwt = true`;
2. an authenticated request to each retirement target returns an inert
   `503` or `410` response and performs no provider, database, or mutation work;
3. `fetch-binance-market-data` sends no credential header;
4. NOAA responses carry provider timestamps and freshness metadata; and
5. Schumann responses say `real_derived`, include timestamp/freshness fields,
   and state that the value is not a direct station measurement.

No live provider call, database row read, credential value, or mutation was
used to create this source closure.
