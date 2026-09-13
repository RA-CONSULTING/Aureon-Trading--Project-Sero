# Google Cloud HTTPS entry

This package gives the existing VM UI one marketed HTTPS `run.app` address. Both the designated owner and ordinary customers sign in there with Supabase Auth. A freshly verified owner enters the existing owner instance; every other verified user enters an isolated tenant plane with only their own keys. There is no demo, prelogged owner browser, or second Aureon brain. Google IAP remains a separate commissioning/recovery channel for administrators and is not a second product address. Neither entry contains operator/provider credentials or grants trading/release authority.

## Request path

1. In marketed `user` mode, static pages are public and browser API calls retain only the supplied Supabase bearer. In recovery `iap` mode, Cloud Run IAP authenticates an administrator and the entry independently verifies the signed IAP ES256 JWT, exact audience/issuer, short lifetime, and a domain-separated commitment of the provider-confirmed email. Both modes check the exact HTTPS host and same-origin API/unsafe-method evidence.
2. The entry retrieves its own service-account Google ID token and sends an exact `iap` or `user` route-mode marker over certificate-pinned TLS to one private VM IP/port. IAP mode also carries the original signed IAP assertion.
3. The VM bridge verifies the Google service token's signature, audience, email, immutable numeric subject, and verified-email claim. It accepts only configured route modes; `iap` independently verifies the recovery assertion while `user` stamps an auth-resolution marker that prevents operator-bearer fallback.
4. Before elevating any `user` request to an owner route, the VM bridge sends the exact bearer to the loopback operator's `/api/me`. The operator verifies it against the pinned Supabase project's `/auth/v1/user` endpoint. Owner status requires administrator-controlled `app_metadata.aureon_role=owner`, the exact commissioned Auth user UUID, a provider-confirmed email, and an exact configured SHA-256 commitment of that email. `user_metadata`, email alone, locally decoded JWT claims, and legacy HS256 claims can never confer owner status.
5. For an exact owner switchboard, authorization-lease, or cloud-trading-control request, the bridge signs the method, path, raw query digest, body digest, revision, route rule, ten-second lifetime, and one-use nonce with its VM-only RSA key. A Supabase-owner receipt also binds the full bearer and the verified owner-subject commitment. The operator verifies the same bearer again and joins that identity to the receipt before consuming it. The IAP recovery receipt remains separately supported. These routes persist human configuration intent; the downstream controller remains the only release authority.
6. In `user` mode, the public entry and bridge both require a canonical compact-JWT bearer shape before any API request is forwarded. For only the reviewed account-owned routes, the bridge issues a separate tenant receipt that binds the exact method, decoded path, Flask route rule, raw query digest, body digest, full bearer commitment, asserted bearer-subject commitment, revision, ten-second lifetime, and one-use nonce. The operator verifies the bearer with the configured Supabase project, then joins that verified tenant identity and exact bearer to the receipt before consuming it in a durable SQLite ledger. Route, body, query, bearer, identity, mode, or revision substitution fails before the handler runs.
7. Tenant custody is limited to provider save/delete/test, connection save/test, cognition and operator responses, their query-driven streams, bounded historical backtest, and Telegram with a request-supplied tenant bot token. Owner switchboard/release, trading/order, billing mutation, arbitrary path, and instance-credential fallback are outside the tenant schema and remain denied or held.
8. The bridge checks the matching-revision loopback UI health on every request. It requires the six deployment holds, `ready=true`, and `release_authority=false`, then proxies the single loopback UI at `127.0.0.1:5173`.

Only after these checks does the bridge supply loopback same-origin evidence. Explicit empty/invalid `Authorization` and any `X-Aureon-Auth-Resolution` marker remain present; they cannot acquire fallback operator identity. Google/browser cookies and arbitrary forwarding/identity headers are never copied. Responses have a strict metadata allowlist, no browser cookies or redirect following, and no-store headers. All transports have finite body and wall-clock limits. Key caching lasts five minutes; unknown-key refresh is throttled.

`AUREON_PUBLIC_ORIGIN` empty is an explicit uncommissioned state: the process binds its server port but returns 503 for every request without calling metadata, private data services, or key endpoints. Configure only a provider-read-back origin; there is no wildcard `run.app` trust. Default Cloud Run readiness uses its TCP startup probe; do not configure anonymous HTTP health bypasses.

## Configuration

Both roles require:

| Variable | Value |
|---|---|
| `AUREON_PUBLIC_ROLE` | `entry` or `bridge` |
| `AUREON_PUBLIC_ACCESS_MODE` | Entry: `user` for the public product or `iap` for the private recovery entry. Bridge: `hybrid` to accept both signed entry paths. |
| `AUREON_PUBLIC_ORIGIN` | Exact HTTPS origin from `gcloud run services describe ... --format=value(status.url)`; empty during bootstrap |
| `AUREON_OWNER_ORIGIN` | Bridge-only exact HTTPS origin of the private recovery entry when `AUREON_PUBLIC_ACCESS_MODE=hybrid` |
| `AUREON_IAP_AUDIENCE` | Role-specific Cloud Run resource audience: `/projects/4435775023/locations/europe-west1/services/aureon-fusion-web` on the public entry and `/projects/4435775023/locations/europe-west1/services/aureon-fusion-operator` on the private recovery entry. Preserve each service's provider-read-back value. |
| `AUREON_IAP_ADMIN_EMAIL_SHA256` | Lowercase hex SHA-256 of `b"aureon-iap-admin-email-v1\x00" + iap_email.strip().casefold().encode("utf-8")`; required only for `iap` or `hybrid`, and never replaced with plaintext identity |
| `AUREON_ENTRY_SERVICE_ACCOUNT_EMAIL` | `aureon-web-entry@aureon-trading.iam.gserviceaccount.com` |
| `AUREON_ENTRY_SERVICE_ACCOUNT_ID` | Numeric `uniqueId` read back from that service account |
| `AUREON_BRIDGE_URL` | `https://10.40.0.2:8443`; also the service-token audience |
| `AUREON_REVISION` | Full verified Git commit SHA also used by the loopback UI/operator |
| `AUREON_OPERATOR_INTENT_KEY_FILE` | Bridge-only VM path `/etc/aureon-public/bridge-key.pem`; never configure on Cloud Run |
| Hold variables | All six values in `public_entry.HOLDS` |

The entry additionally needs `AUREON_BRIDGE_CA_FILE=/app/bridge-cert.pem`. The bridge has no application source-root requirement and no access to runtime state. The intent-key path is public configuration, while the referenced private key remains VM-only credential material.

The loopback operator, and only the loopback operator, also needs the atomic owner designation below. Both variables must be present or both absent; a partial record refuses startup. The owner stays tenant-scoped when the record is absent or any check differs.

| Operator variable | Value |
|---|---|
| `AUREON_SUPABASE_OWNER_SUBJECT` | Exact canonical UUID returned by the pinned Supabase Auth server for the owner account |
| `AUREON_SUPABASE_OWNER_EMAIL_SHA256` | Lowercase hex SHA-256 of `b"aureon-supabase-owner-email-v1\\x00" + confirmed_email.strip().casefold().encode("utf-8")`; never store the plaintext email here |

Commissioning must set `app_metadata.aureon_role` to the exact string `owner` through an authenticated Supabase administrator operation and then read the user back from the provider. At cutover, resolve the exact UUID and confirmed email from that fresh provider response, compute the domain-separated email commitment locally, and inject only the UUID and commitment into the loopback operator process. Do not put either owner-designation variable in the Cloud Run entry, VM bridge, frontend build, or browser storage, and do not retain the plaintext email in the operator configuration. The separate IAP recovery commitment may be present in the recovery entry and bridge; its distinct domain prevents either commitment from being reused as the other identity proof. Never place the role in `user_metadata`, accept a browser-provided role, or derive owner status from email alone. The operator requires `AUREON_SUPABASE_URL` and `AUREON_SUPABASE_PUBLISHABLE_KEY` so every bearer is checked by the Auth server; the legacy JWT-secret verifier is deliberately ineligible for owner elevation.

## VM installation

Install after the verified source/runtime update and loopback health checks. Keep the public bridge separate from the main runtime updater and existing 21 units. The new unit name is `aureon-public-bridge.service`; a pre-existing unit with unexpected ownership/configuration must be reviewed before replacement.

1. Run `create-bridge-certificate.sh` as root on the VM. It creates dedicated `aureon-public` system identity and `/etc/aureon-public` with execute-only traversal for other service identities, refuses to overwrite a TLS identity, and creates a 180-day certificate for `10.40.0.2`. Run `public_bridge_certificate_receipt.py` before packaging: it parses the X.509 leaf, requires current validity with at least 86,400 seconds remaining and an IP SAN equal to `10.40.0.2`, and records the DER SHA-256 plus validity bounds. The private key remains VM-only, root-owned and readable by the dedicated bridge group; the receipt tool never opens it. Rotation requires a new pinned public certificate in the entry image and coordinated bridge/operator reload.
2. Install Python dependencies in a separate root-owned `/srv/aureon/public-venv`. Do not alter the application's venv. Copy only reviewed `public_entry.py` into root-owned `/srv/aureon/public-entry` (0755 directory, 0644 source). The bridge user cannot modify either.
3. Create root-owned `/etc/aureon-public/bridge.env` with 0640 `root:aureon-public` permissions from `bridge.env.example`, using the verified service identity, revision, and initially empty origin.
4. Install the reviewed unit to `/etc/systemd/system/aureon-public-bridge.service`; run `systemd-analyze verify` and `systemctl daemon-reload`. Start it explicitly. It binds only `10.40.0.2:8443`, denies all requests until commissioned, and has no ability to read `/srv/aureon/runtime`, import, cache, home directories, or the operator bearer.
5. Copy only `/etc/aureon-public/bridge-cert.pem` to the separate Cloud Run image build context. Match its SHA-256 fingerprint to the VM read-back. Never copy `bridge-key.pem` off the VM. No PEM/key files belong in Git; the Dockerfile's explicit COPY list excludes private keys.

Example dependency command, run on the VM after reviewing these files:

```sh
python3 -m venv /srv/aureon/public-venv
/srv/aureon/public-venv/bin/python -m pip install -r /path/to/reviewed/public-entry/requirements.txt
install -d -o root -g root -m 0755 /srv/aureon/public-entry
install -o root -g root -m 0644 /path/to/reviewed/public-entry/public_entry.py /srv/aureon/public-entry/public_entry.py
```

## Network and IAM

Use a dedicated, verified unused `/26` subnet in `aureon-sero-network`, region `europe-west1`, for Cloud Run Direct VPC egress. Do not assume an unused CIDR without checking existing subnets/peering routes. Its source range receives one VM ingress rule to TCP 8443 and target tag `aureon-public-bridge`, attached only to this VM. Cloud Run Direct VPC **source tags are not supported in ingress rules**; use the subnet CIDR. A Cloud Run tag can restrict its **egress**: allow the VM `/32` TCP8443 before denying other RFC1918 destinations. DNS/metadata and Google public verification-key endpoints must remain available. Keep `private-ranges-only` egress; no paid connector or Cloud NAT is required for this path.

The dedicated entry service account needs no operator-secret access and no downloaded service-account key. Cloud Run metadata supplies its own ID token without granting it project-wide Token Creator. Its numeric subject is pinned in both applications.

The customer-facing product is `aureon-fusion-web` in `user` mode and is the only address marketed to the owner and customers. A private `aureon-fusion-operator` entry preserves IAP commissioning/recovery access to the same app/runtime. Use `trading-control/cloud_run_stage.py` as the authoritative deploy renderer for both entries and all five authority services. It renders the exact contract values, immutable image digest, full nonsecret environment, Direct VPC network/subnet/tag/egress, IAP state, 90-second timeout, concurrency 8, CPU 1, memory 512Mi, min 0, max 20, startup probe and CPU behavior. Every command has an explicit source-derived revision suffix and `--no-traffic`; the tool has no promotion command.

Provider IAM commissioning separately grants the public entry's declared anonymous invoker and only the IAP service agent as recovery-entry invoker. Supply the IAP administrator principal only to the separate provider IAM operation; source, deployment manifests and receipts retain only its domain-separated commitment.

After the staged-revision attestation and VM closure, promote the authority chain tail-to-head (`receipt`, `executor`, `dispatch`, `review`, `controller`), then the recovery entry and finally the marketed entry. Promotion is a separate reviewed provider operation. Name the exact attested revision; never use `latest`. Read back `status.latestReadyRevisionName`, `status.latestCreatedRevisionName`, `status.traffic`, the serving revision image digest and environment. Acceptance requires one untagged 100% target, both latest revision names equal that target, and the exact contract digest/configuration before moving to the next service.

This project has no organization. Google documents one-time console setup/custom OAuth for the recovery IAP entry. Complete that normal setup if required; do not grant anonymous access to the recovery service, spoof identity headers, or publish private telemetry as an auth workaround.

Read both `status.url` values. Configure the public origin as `AUREON_PUBLIC_ORIGIN` on the bridge, the private recovery origin as `AUREON_OWNER_ORIGIN`, and each entry with its own exact `AUREON_PUBLIC_ORIGIN`; then restart/update them. Read back the public invoker, recovery IAP policy, service accounts, image digests, revision, network, firewall rules, Supabase app metadata and exact owner UUID. Confirm anonymous users can reach static marketing/sign-in but receive no operator identity; an ordinary signed-in user receives only the tenant plane; the designated Supabase owner receives the instance plane on the same public address; signing out immediately loses that identity; and IAP recovery remains private. Then verify fresh API telemetry, a protected harmless held operation, and service restart continuity.

## Verification and operational limits

Run `python -m pytest -q test_public_entry.py` from this directory in an isolated test environment. Tests create ephemeral signing keys in memory and test actual signatures/claims plus forged/missing identities, wrong host/origin, CSRF, explicit failed auth, holds, unavailable runtime, and source constraints. Add deployed TLS/anonymous and signed-in browser receipts to commissioning evidence; local tests alone do not prove cloud deployment.

The bounded proxy supports finite HTTP JSON/static requests up to 256 KiB request and 8 MiB response, with 30-second upstream deadlines. It does not implement WebSockets, streaming SSE, uploads larger than that, or redirecting upstream responses. It fails visibly when an upstream is absent. The identity-bound Supabase-owner receipt makes switchboard intent and bounded operator-authorization recording usable from the one public product address. The separate identity-bound tenant receipt admits only the enumerated account-owned effects. The IAP receipt preserves recovery access. Production dispatch authorities and trading controls remain governed by the backend; this package does not enable them.

Current official references (verified 2026-09-11):

- [Direct IAP on Cloud Run, including default URLs and no-organization setup](https://docs.cloud.google.com/run/docs/securing/identity-aware-proxy-cloud-run)
- [Signed IAP headers, ES256, exact Cloud Run audience and lifetime](https://docs.cloud.google.com/iap/docs/signed-headers-howto)
- [Cloud Run Direct VPC egress and firewall limitations](https://docs.cloud.google.com/run/docs/configuring/vpc-direct-vpc)
- [IAP uses the infrastructure X-Serverless-Authorization header](https://docs.cloud.google.com/iap/docs/enabling-cloud-run)
- [Google workload ID tokens](https://docs.cloud.google.com/docs/authentication/get-id-token)
- [PyJWT validation API](https://pyjwt.readthedocs.io/en/stable/api.html)
