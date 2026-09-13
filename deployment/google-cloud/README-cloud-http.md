# Current cloud profile: private held operator and built UI

This is the current Linux cloud HTTP composition in the release source checkout. It replaces the Windows DPAPI/Vite launch profile for the two cloud HTTP units only. Adding these files does not activate services. No cloud calls, production imports, service restarts, provider writes, or orders were performed by this implementation task.

The three files in this directory are `cloud_http_runtime.py`, `cloud_operator.py`, and `cloud_ui_gateway.py`. The current operator source and the complete production `frontend/dist` must be included by the release packager and independently hash verified. Tests in `tests/test_cloud_http_runtime.py` load this exact adjacent runtime module.

## Launch contract

Use the separate systemd units `aureon-cloud-operator.service` and `aureon-cloud-ui.service`. The updater owns the unit definitions. Commands use the installed virtual environment with Flask and Waitress (`.[operator]` in the current upstream project):

```text
/srv/aureon/venv/bin/python /srv/aureon/runtime/workspace/deployment/google-cloud/cloud_operator.py --source-root /srv/aureon/runtime/workspace/aureon-os-upstream --revision FULL_GIT_SHA --project PROJECT_ID --secret HTTP_SECRET_ID --secret-version NUMERIC_VERSION --tenant-secret SUPABASE_TENANT_SECRET_ID --tenant-secret-version NUMERIC_VERSION --provider-secret OWNER_PROVIDER_SECRET_ID --provider-secret-version NUMERIC_VERSION
/srv/aureon/venv/bin/python /srv/aureon/runtime/workspace/deployment/google-cloud/cloud_ui_gateway.py --source-root /srv/aureon/runtime/workspace/aureon-os-upstream --dist-root /srv/aureon/runtime/workspace/aureon-os-upstream/frontend/dist --revision FULL_GIT_SHA --project PROJECT_ID --secret HTTP_SECRET_ID --secret-version NUMERIC_VERSION
```

The operator binds only `127.0.0.1:8080`; the built UI binds only `127.0.0.1:5173`. Each process reserves its port before fetching secrets or importing the production operator. Do not schedule the Windows `operator_gateway` or `frontend_vite` registry aliases on this VM: these cloud units are the sole HTTP process owners. No Vite development server is used. Remote access must use an authenticated IAP/SSH loopback tunnel; this is not a public HTTP service or a general reverse proxy.

All six environment values must already be set exactly; omission or deviation refuses startup and invalidates runtime readiness:

```text
AUREON_DEPLOYMENT_HOLD=1
AUREON_DISABLE_REAL_ORDERS=1
AUREON_DISABLE_EXCHANGE_MUTATIONS=1
AUREON_ORDER_INTENT_PUBLISH=0
AUREON_LIVE_TRADING=0
AUREON_UNIFIED_ORDER_EXECUTOR=0
```

## Secret custody and access

The VM has the `cloud-platform` OAuth scope, but its attached
`aureon-vm-token-broker` service account has no data-plane role. The root-only
`aureon-cloud-token-broker.service` is the sole Aureon unit allowed to reach
Compute Engine metadata. It impersonates the fixed UI, operator, trade-bridge,
and provider-organ accounts and rotates 30-minute tokens into their exact
root-owned files below `/run/aureon-cloud-identity`. Every workload denies both
metadata addresses and fails closed unless its own token file is valid. The UI
identity reads only the HTTP secret; the operator reads the HTTP, tenant-auth,
and owner-provider secrets. No service-account JSON key, local profile, Windows
DPAPI file, environment bearer fallback, or recovery secret is used. Secret
Manager's [access documentation](https://docs.cloud.google.com/secret-manager/docs/access-secret-version)
describes the required scope, per-secret role, and version access response.

The HTTP bearer secret must be 48–128 ASCII URL-safe characters (`[A-Za-z0-9_-]+`), with no newline, whitespace or JSON wrapper. The operator's second pinned secret contains exactly a canonical Supabase `project_url` and public `publishable_key`; service-role material, extra fields, alternate hosts, redirects and malformed keys are rejected. Its third pinned secret is an owner-only JSON object with exactly these six string fields and no duplicates or extensions:

```json
{
  "NASA_API_KEY": "REAL_OWNER_KEY",
  "NOAA_API_KEY": "REAL_OWNER_KEY",
  "USGS_API_KEY": "REAL_OWNER_KEY",
  "OLLAMA_API_KEY": "REAL_OWNER_KEY",
  "AUREON_LLM_BASE_URL": "https://ollama.com/v1",
  "AUREON_LLM_MODEL": "gpt-oss:120b-cloud"
}
```

Provider keys must be bounded printable non-whitespace ASCII and cannot be known placeholder values. The base URL is pinned to the canonical HTTPS Ollama Cloud API; the model name has a bounded identifier grammar. Project identity is checked against VM metadata; each returned exact numeric-project resource/version and CRC32C must match. Metadata and Secret Manager destinations are fixed, environment proxies are disabled, and response bodies are bounded. Each fetch runs as `python -I -S -B` with a stripped environment. Its anonymous stdout pipe is consumed only in parent memory. A 20-second total deadline kills and reaps the worker (a separate two-second cleanup bound); no value is written to a file, generated unit, browser response or log.

The operator must hold the bearer and validated owner provider values in its process environment because those are the existing authentication and provider interfaces. The gateway keeps only the HTTP bearer in process memory and never receives the provider bundle. Protect these service accounts/processes and their host administration accordingly. Each secret is fetched once per process start; rotating/revoking a version requires a controlled restart of every consuming unit to replace its in-memory value. No automatic version alias or silent fallback exists.

## API and UI behavior

Only these upstreams are reachable:

| UI route | Upstream | Behavior |
| --- | --- | --- |
| `/api/orca-observations` | `127.0.0.1:8080/api/orca-observations` | GET/HEAD only; authenticated operator route exposing a sanitized, passive terminal-state projection |
| `/api/terminal-state`, `/api/flight-test` | Same exact route on `127.0.0.1:8791` | GET/HEAD only; all credentials stripped |
| Other `/api` routes | Same path/query on `127.0.0.1:8080` | Existing operator identity/HNC controls retained |

The gateway matches the currently used Vite routes, narrowing the two observation routes to exact paths instead of accidental prefix matches. It never substitutes telemetry or serves an HTML fallback for an unavailable API. Missing upstreams and redirects produce explicit uncached 502 responses. Only bounded `Accept`, `Content-Type`, exact caller `Authorization`, and the bridge-created `X-Aureon-Operator-Intent` receipt may travel to port 8080. The receipt is never accepted from the browser or forwarded to the passive observation ports. Browser cookies, forwarding headers and the auth-resolution marker are not forwarded. Local response streams have a total socket-shutdown deadline, including slow headers and chunk framing.

Loopback client and Host validation apply to both services. Cross-origin/cross-site requests are denied. Server bearer injection occurs only for a proven same-origin browser request with no caller `Authorization` header and no `X-Aureon-Auth-Resolution` marker. An invalid or empty caller header remains invalid or empty; a failed browser identity can never fall back to operator authority. Direct unauthenticated operator API calls remain unauthenticated. The operator verifies the bridge certificate, exact revision, method, decoded path, Flask route rule, raw query hash, body hash, short lifetime, and durable one-use nonce. IAP recovery receipts require a domain-separated SHA-256 commitment of the verified administrator email; plaintext administrator identity is absent from source, unit configuration and receipts. The one marketed address uses a separate Supabase-owner receipt: before signing it, the private bridge asks this loopback operator to verify the exact bearer; owner designation requires server-controlled `app_metadata.aureon_role=owner`, the exact configured Auth user UUID, and the separately domain-separated commitment of a provider-confirmed email. At cutover those two values must be resolved from a fresh authenticated provider read-back and injected only into the loopback operator, with no owner designation in the Cloud Run entry, VM bridge, frontend build, or browser. The receipt binds the same bearer and verified owner subject, and the operator verifies both again before use. Tenant receipts likewise bind the exact bearer and asserted subject; the operator independently verifies the bearer through Supabase and joins the verified account identity to both commitments. User-controlled metadata, email alone, forged decoded claims, mismatched bearers and legacy HS256 claims cannot elevate. Only enumerated provider/connection key management and tests, tenant reasoning/streams, historical backtest, and tenant-token Telegram routes qualify for tenants. Order/trade, switchboard/release, billing mutation, arbitrary paths, and cross-mode receipts remain outside tenant custody. The fixed cloud boot profile stores encrypted switchboard decisions under `/var/lib/aureon-operator/feature-switchboard`, while tenant keystores use the service-owned state directory. Every other protected mutation stays on the existing HNC hold. A saved switchboard request never changes the running cloud holds or grants downstream action authority.

The fixed cloud boot profile stores encrypted switchboard decisions below
`/var/lib/aureon-operator/feature-switchboard`. Its private intent ledger also
stays below `/var/lib/aureon-operator`; the release ledger and sanitized trade
readback use the narrow group-mediated paths below
`/var/lib/aureon-control-exchange`. The UI requires a built index and its
referenced production assets. Deep application routes receive that index;
missing asset files, hidden paths and path escapes return 404. Health does not
assert that all pages/providers have fresh data.

## Verification and acceptance

Exact `GET /__aureon_health` on both ports returns only `schema`, `role`, `revision`, `ready`, `deployment_hold`, `release_authority` and `tenant_auth_ready`. Status is 200 only when service readiness and tenant-auth configuration are true; otherwise 503. `release_authority` is always false. UI readiness requires its built files plus a current matching-revision operator health response with `tenant_auth_ready: true`. The operator envelope bypasses existing authentication only for that exact passive GET health path; every other request continues through the original Flask app.

The health revision is the release argument, so the updater must independently verify deployed source/asset hashes against its manifest. A matching health response proves service composition/readiness under holds, not complete source integrity, scientific measurements, provider freshness, independent authority, live orders or production economic release.

Local verification must include the focused cloud runtime and release-updater suites plus Ruff. Tests cover metadata/version/checksum and worker deadline fixtures; strict Supabase and closed owner-provider secret validation; authentication, failed-identity preservation, passive credential stripping, protected POST hold passthrough, static routing and health binding; a real ephemeral Waitress server with a prebound socket; duplicate-port rejection; and an actual slow-header loopback response interrupted by the total deadline. Tests use offline credentials and a fixture backend; they do not attest GCP IAM, a fetched deployment secret, actual operator boot, remote browser rendering, or live provider data.

Deployment acceptance still requires: per-secret IAM readback for each exact numeric version; source and built-asset hash readback; both owned PIDs/loopback listeners with exact revision health; direct missing/invalid bearer 401; same-origin UI `/api/me` 200 without exposing any server secret; failed browser-auth marker remains 401; hostile origin rejected; passive source provenance/freshness checked independently; provider read-backs that disclose no credential; held controls verified without submitting real orders; restart continuity; and rollback verification. Keep the local system available until those cloud checks pass.

Run the focused tests from the release checkout root:

```text
python -m unittest discover -s deployment/google-cloud/tests -p test_cloud_http_runtime.py -v
python -m ruff check deployment/google-cloud deployment/google-cloud/tests
```
