# Private Windows operator HTTP commissioning

The installed local deployment uses the workspace organ registry for
`operator_gateway` and `frontend_vite`. It does not run the container preflight
images in `docker-compose.operator.yml` or `docker-compose.saas.yml` as servers.
Those images intentionally have no network and cannot serve a production UI.

Run `python -m aureon.operator.local_http_profile --initialize` as the Windows
account owning both services. This creates an account-protected DPAPI file at
`~/.aureon/operator-http.dpapi`; it never writes or prints a plaintext bearer.
The registry loads this profile only into the two HTTP processes at spawn time.
For these commissioned services a missing profile or loader prevents startup.
Corrupt profiles must be recovered under the original Windows account; do not
fall back to open authentication. Back up the encrypted profile with the Windows
account recovery material, outside source control.

The operator receives these server-side settings:

| Setting | Local deployment |
| --- | --- |
| AUREON_OPERATOR_ENV | production |
| AUREON_OPERATOR_API_KEY | DPAPI-decrypted, process environment only |
| AUREON_OPERATOR_HOST | 127.0.0.1 |
| AUREON_OPERATOR_PORT | 8080 |
| AUREON_OPERATOR_RATE_RPS | 40 |
| AUREON_OPERATOR_RATE_BURST | 160 |
| AUREON_OPERATOR_MAX_BODY | default 262144 bytes; bounded by ingress |
| AUREON_OPERATOR_TRUSTED_PROXY_CIDRS | unset; forwarded clients are untrusted |
| AUREON_OPERATOR_HTTP_PROCESSES | 1 |
| AUREON_OPERATOR_REPLICAS | 1 |

The UI receives `AUREON_UI_AUTH_MODE=local-operator` and
`AUREON_OPERATOR_PROXY_BEARER`. These are server-only variables, never `VITE_`
variables. The proxy supplies the operator credential only for a loopback request
with same-origin evidence and no caller Authorization or failed-auth marker.
An invalid caller credential is rejected and cannot become an operator request.

The `frontend_vite` process pins `NODE_ENV=development` so its development JSX
transform receives the matching React runtime. This does not alter production
builds. Vite remains a local development UI server; a deployed static frontend
and its protected production ingress remain separate commissioning work.

Use registry restart controls after changing deployment configuration. Verify
the old process is gone and the new process creation time changed; an
`already_running` or `stop_failed` result is not activation. An elevated Windows
process requires an authorized elevated restart. Keep the trader and feed
services running while restarting this HTTP pair.

Verify missing/invalid direct credentials yield401; authenticated `/api/me`
identifies the operator; same-origin UI requests succeed; cross-origin UI
requests fail; receipts use no-store. The rate limiter is process-local, hence
the one-process/one-replica limit.

HTTP authentication and rate limiting do not release protected operations.
The running operator still needs the independent production release composition,
durable ingress custody, executor isolation, and exact signed result readbacks.
Backtesting and artifact-decision handlers default to unavailable dispatch.
Changing a capability flag, using the route-test seam, or clearing economic
holds is not a substitute for installing and verifying those services.
