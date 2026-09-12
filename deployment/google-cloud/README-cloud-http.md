# Current cloud profile: private held operator and built UI

This is the current Linux cloud HTTP composition in the release source checkout. It replaces the Windows DPAPI/Vite launch profile for the two cloud HTTP units only. Adding these files does not activate services. No cloud calls, production imports, service restarts, provider writes, or orders were performed by this implementation task.

The three files in this directory are `cloud_http_runtime.py`, `cloud_operator.py`, and `cloud_ui_gateway.py`. The current operator source and the complete production `frontend/dist` must be included by the release packager and independently hash verified. Tests in `tests/test_cloud_http_runtime.py` load this exact adjacent runtime module.

## Launch contract

Use the separate systemd units `aureon-cloud-operator.service` and `aureon-cloud-ui.service`. The updater owns the unit definitions. Commands use the installed virtual environment with Flask and Waitress (`.[operator]` in the current upstream project):

```text
/srv/aureon/venv/bin/python /srv/aureon/runtime/workspace/deployment/google-cloud/cloud_operator.py --source-root /srv/aureon/runtime/workspace/aureon-os-upstream --revision FULL_GIT_SHA --project PROJECT_ID --secret HTTP_SECRET_ID --secret-version NUMERIC_VERSION --tenant-secret SUPABASE_TENANT_SECRET_ID --tenant-secret-version NUMERIC_VERSION
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

The VM needs its own service account, the `cloud-platform` OAuth scope, and Secret Manager Secret Accessor on exactly the newly administered HTTP secret. No service-account JSON key, local profile, Windows DPAPI file, environment bearer fallback, or existing recovery secret is used. Both processes fetch the same pinned numeric version. Secret Manager's [access documentation](https://docs.cloud.google.com/secret-manager/docs/access-secret-version) describes the required scope, per-secret role and version access response.

The HTTP bearer secret must be 48–128 ASCII URL-safe characters (`[A-Za-z0-9_-]+`), with no newline, whitespace or JSON wrapper. The operator's second pinned secret contains exactly a canonical Supabase `project_url` and public `publishable_key`; service-role material, extra fields, alternate hosts, redirects and malformed keys are rejected. Project identity is checked against VM metadata; each returned exact numeric-project resource/version and CRC32C must match. Metadata and Secret Manager destinations are fixed, environment proxies are disabled, and response bodies are bounded. Each fetch runs as `python -I -S -B` with a stripped environment. Its anonymous stdout pipe is consumed only in parent memory. A 20-second total deadline kills and reaps the worker (a separate two-second cleanup bound); no value is written to a file, browser response or log.

The operator must hold the bearer in its process environment because that is the existing authentication factory's interface. The gateway keeps it in process memory. Protect these service accounts/processes and their host administration accordingly. The secret is fetched once per process start; rotating/revoking a version requires a controlled restart of both HTTP units to replace the in-memory value. No automatic version alias or silent fallback exists.

## API and UI behavior

Only these upstreams are reachable:

| UI route | Upstream | Behavior |
| --- | --- | --- |
| `/api/orca-observations` | `127.0.0.1:8888/api/observations` | GET/HEAD only; all credentials stripped |
| `/api/terminal-state`, `/api/flight-test` | Same exact route on `127.0.0.1:8791` | GET/HEAD only; all credentials stripped |
| Other `/api` routes | Same path/query on `127.0.0.1:8080` | Existing operator identity/HNC controls retained |

The gateway matches the currently used Vite routes, narrowing the two observation routes to exact paths instead of accidental prefix matches. It never substitutes telemetry or serves an HTML fallback for an unavailable API. Missing upstreams and redirects produce explicit uncached 502 responses. Only bounded `Accept`, `Content-Type`, operator `Authorization`, and the bridge-created `X-Aureon-Operator-Intent` receipt may travel to port 8080. The receipt is never forwarded to the passive observation ports. Browser cookies, forwarding headers and the auth-resolution marker are not forwarded. Local response streams have a total socket-shutdown deadline, including slow headers and chunk framing.

Loopback client and Host validation apply to both services. Cross-origin/cross-site requests are denied. Server bearer injection occurs only for a proven same-origin browser request with no caller `Authorization` header and no `X-Aureon-Auth-Resolution` marker. An invalid or empty caller header remains invalid or empty; a failed browser identity can never fall back to operator authority. Direct unauthenticated operator API calls remain unauthenticated. The operator verifies the bridge certificate, exact revision, route, body hash, owner admin identity, short lifetime, and a durable one-use nonce before the switchboard may persist intent. Every other protected mutation stays on the existing HNC hold. A saved switchboard request never changes the running cloud holds or grants downstream action authority.

The UI requires a built index and its referenced production assets. Deep application routes receive that index; missing asset files, hidden paths and path escapes return 404. Health does not assert that all pages/providers have fresh data.

## Verification and acceptance

Exact `GET /__aureon_health` on both ports returns only `schema`, `role`, `revision`, `ready`, `deployment_hold`, `release_authority` and `tenant_auth_ready`. Status is 200 only when service readiness and tenant-auth configuration are true; otherwise 503. `release_authority` is always false. UI readiness requires its built files plus a current matching-revision operator health response with `tenant_auth_ready: true`. The operator envelope bypasses existing authentication only for that exact passive GET health path; every other request continues through the original Flask app.

The health revision is the release argument, so the updater must independently verify deployed source/asset hashes against its manifest. A matching health response proves service composition/readiness under holds, not complete source integrity, scientific measurements, provider freshness, independent authority, live orders or production economic release.

Local verification must include the focused cloud runtime and release-updater suites plus Ruff. Tests cover metadata/version/checksum and worker deadline fixtures; strict Supabase tenant-secret validation; authentication, failed-identity preservation, passive credential stripping, protected POST hold passthrough, static routing and health binding; a real ephemeral Waitress server with a prebound socket; duplicate-port rejection; and an actual slow-header loopback response interrupted by the total deadline. Tests use offline credentials and a fixture backend; they do not attest GCP IAM, a fetched deployment secret, actual operator boot, remote browser rendering, or live provider data.

Deployment acceptance still requires: per-secret IAM readback; source and built-asset hash readback; both owned PIDs/loopback listeners with exact revision health; direct missing/invalid bearer 401; same-origin UI `/api/me` 200 without exposing the server secret; failed browser-auth marker remains 401; hostile origin rejected; passive source provenance/freshness checked independently; held controls verified without submitting real orders; restart continuity; and rollback verification. Keep the local system available until those cloud checks pass.

Run the focused tests from the release checkout root:

```text
python -m unittest discover -s deployment/google-cloud/tests -p test_cloud_http_runtime.py -v
python -m ruff check deployment/google-cloud deployment/google-cloud/tests
```
