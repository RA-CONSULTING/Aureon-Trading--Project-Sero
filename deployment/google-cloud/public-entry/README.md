# Google Cloud HTTPS entry

This package gives the existing VM UI one public product HTTPS `run.app` address plus a private owner entry. Both serve the same application and the same governed VM runtime; there is no demo or second Aureon brain. The public entry carries Supabase user bearers without gaining operator identity. The owner entry remains protected by Google IAP. Neither entry contains operator/provider credentials or grants trading/release authority.

## Request path

1. In `iap` mode, Google Cloud Run IAP authenticates the owner and the entry independently verifies the signed IAP ES256 JWT, exact audience/issuer, short lifetime, and owner email. In `user` mode, static pages are public and browser API calls retain only the supplied Supabase bearer. Both modes check the exact HTTPS host and same-origin API/unsafe-method evidence.
2. The entry retrieves its own service-account Google ID token and sends an exact `iap` or `user` route-mode marker over certificate-pinned TLS to one private VM IP/port. IAP mode also carries the original signed IAP assertion.
3. The VM bridge verifies the Google service token's signature, audience, email, immutable numeric subject, and verified-email claim. It accepts only configured route modes; `iap` independently verifies the owner assertion while `user` stamps an auth-resolution marker that prevents operator-bearer fallback.
4. For an exact owner-IAP `POST /api/switchboard/<FLAG_ID>` only, the bridge signs the method, path, body digest, revision, ten-second lifetime, and one-use nonce with its VM-only RSA key. This authorizes persistence of human configuration intent; it grants no runtime, release, order, exchange, payment, filing, or tool authority.
5. The bridge checks the matching-revision loopback UI health on every request. It requires the six deployment holds, `ready=true`, and `release_authority=false`, then proxies the single loopback UI at `127.0.0.1:5173`.

Only after these checks does the bridge supply loopback same-origin evidence. Explicit empty/invalid `Authorization` and any `X-Aureon-Auth-Resolution` marker remain present; they cannot acquire fallback operator identity. Google/browser cookies and arbitrary forwarding/identity headers are never copied. Responses have a strict metadata allowlist, no browser cookies or redirect following, and no-store headers. All transports have finite body and wall-clock limits. Key caching lasts five minutes; unknown-key refresh is throttled.

`AUREON_PUBLIC_ORIGIN` empty is an explicit uncommissioned state: the process binds its server port but returns 503 for every request without calling metadata, private data services, or key endpoints. Configure only a provider-read-back origin; there is no wildcard `run.app` trust. Default Cloud Run readiness uses its TCP startup probe; do not configure anonymous HTTP health bypasses.

## Configuration

Both roles require:

| Variable | Value |
|---|---|
| `AUREON_PUBLIC_ROLE` | `entry` or `bridge` |
| `AUREON_PUBLIC_ACCESS_MODE` | Entry: `user` for the public product or `iap` for the private owner entry. Bridge: `hybrid` to accept both signed entry paths. |
| `AUREON_PUBLIC_ORIGIN` | Exact HTTPS origin from `gcloud run services describe ... --format=value(status.url)`; empty during bootstrap |
| `AUREON_OWNER_ORIGIN` | Bridge-only exact HTTPS origin of the private owner entry when `AUREON_PUBLIC_ACCESS_MODE=hybrid` |
| `AUREON_IAP_AUDIENCE` | `/projects/4435775023/locations/europe-west1/services/aureon-fusion-web` |
| `AUREON_ALLOWED_USER_EMAILS` | `gaxlec@gmail.com` |
| `AUREON_ENTRY_SERVICE_ACCOUNT_EMAIL` | `aureon-web-entry@aureon-trading.iam.gserviceaccount.com` |
| `AUREON_ENTRY_SERVICE_ACCOUNT_ID` | Numeric `uniqueId` read back from that service account |
| `AUREON_BRIDGE_URL` | `https://10.40.0.2:8443`; also the service-token audience |
| `AUREON_REVISION` | Full verified Git commit SHA also used by the loopback UI/operator |
| `AUREON_OPERATOR_INTENT_KEY_FILE` | Bridge-only VM path `/etc/aureon-public/bridge-key.pem`; never configure on Cloud Run |
| Hold variables | All six values in `public_entry.HOLDS` |

The entry additionally needs `AUREON_BRIDGE_CA_FILE=/app/bridge-cert.pem`. The bridge has no application source-root requirement and no access to runtime state. The intent-key path is public configuration, while the referenced private key remains VM-only credential material.

## VM installation

Install after the verified source/runtime update and loopback health checks. Keep the public bridge separate from the main runtime updater and existing 21 units. The new unit name is `aureon-public-bridge.service`; a pre-existing unit with unexpected ownership/configuration must be reviewed before replacement.

1. Run `create-bridge-certificate.sh` as root on the VM. It creates dedicated `aureon-public` system identity and `/etc/aureon-public` with execute-only traversal for other service identities, refuses to overwrite a TLS identity, and creates a 180-day certificate for `10.40.0.2`. The private key remains VM-only, root-owned and readable by the dedicated bridge group. The public certificate is readable by the loopback operator for receipt verification. Record certificate fingerprint and expiry. Rotation requires a new pinned public certificate in the entry image and coordinated bridge/operator reload.
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

The customer-facing product is `aureon-fusion-web` in `user` mode and is the only address marketed to users. A private `aureon-fusion-operator` entry preserves owner-only IAP access to the same app/runtime. Deploy the public product with unauthenticated Cloud Run ingress because the application enforces Supabase authentication on console/API routes:

```sh
gcloud run deploy aureon-fusion-web \
  --project=aureon-trading --region=europe-west1 \
  --image=REVIEWED_IMAGE_DIGEST \
  --service-account=aureon-web-entry@aureon-trading.iam.gserviceaccount.com \
  --network=aureon-sero-network --subnet=VERIFIED_ENTRY_SUBNET \
  --network-tags=aureon-web-entry --vpc-egress=private-ranges-only \
  --cpu=1 --memory=512Mi --concurrency=8 --min=0 --max=20 \
  --timeout=60 --allow-unauthenticated --no-iap \
  --env-vars-file=PUBLIC_USER_CONFIG_YAML
```

Deploy the owner entry from the same immutable image digest with direct IAP and no anonymous invoker:

```sh
gcloud run deploy aureon-fusion-operator \
  --project=aureon-trading --region=europe-west1 \
  --image=REVIEWED_IMAGE_DIGEST \
  --service-account=aureon-web-entry@aureon-trading.iam.gserviceaccount.com \
  --network=aureon-sero-network --subnet=VERIFIED_ENTRY_SUBNET \
  --network-tags=aureon-web-entry --vpc-egress=private-ranges-only \
  --cpu=1 --memory=512Mi --concurrency=8 --min=0 --max=2 \
  --timeout=60 --no-allow-unauthenticated --iap \
  --env-vars-file=PUBLIC_NON_SECRET_CONFIG_YAML
gcloud run services add-iam-policy-binding aureon-fusion-operator \
  --project=aureon-trading --region=europe-west1 \
  --member=serviceAccount:service-4435775023@gcp-sa-iap.iam.gserviceaccount.com \
  --role=roles/run.invoker
gcloud iap web add-iam-policy-binding \
  --project=aureon-trading --region=europe-west1 \
  --resource-type=cloud-run --service=aureon-fusion-operator \
  --member=user:gaxlec@gmail.com --role=roles/iap.httpsResourceAccessor
```

This project has no organization. Google documents one-time console setup/custom OAuth for the owner IAP entry. Complete that normal setup if required; do not grant anonymous access to the owner service, spoof identity headers, or publish private telemetry as an auth workaround.

Read both `status.url` values. Configure the public origin as `AUREON_PUBLIC_ORIGIN` on the bridge, the private owner origin as `AUREON_OWNER_ORIGIN`, and each entry with its own exact `AUREON_PUBLIC_ORIGIN`; then restart/update them. Read back the public invoker, owner IAP policy, service accounts, image digests, revision, network, firewall rules, and user policy. Confirm anonymous users can reach static marketing/sign-in but receive no operator identity, then test a signed-in tenant route, owner IAP routes, fresh API telemetry, a protected harmless held operation, and service restart continuity.

## Verification and operational limits

Run `python -m pytest -q test_public_entry.py` from this directory in an isolated test environment. Tests create ephemeral signing keys in memory and test actual signatures/claims plus forged/missing identities, wrong host/origin, CSRF, explicit failed auth, holds, unavailable runtime, and source constraints. Add deployed TLS/anonymous and signed-in browser receipts to commissioning evidence; local tests alone do not prove cloud deployment.

The bounded proxy supports finite HTTP JSON/static requests up to 256 KiB request and 8 MiB response, with 30-second upstream deadlines. It does not implement WebSockets, streaming SSE, uploads larger than that, or redirecting upstream responses. It fails visibly when an upstream is absent. The signed owner receipt only makes switchboard intent recording usable from the cloud. Production dispatch authorities and trading controls remain governed by the backend; this package does not enable them.

Current official references (verified 2026-09-11):

- [Direct IAP on Cloud Run, including default URLs and no-organization setup](https://docs.cloud.google.com/run/docs/securing/identity-aware-proxy-cloud-run)
- [Signed IAP headers, ES256, exact Cloud Run audience and lifetime](https://docs.cloud.google.com/iap/docs/signed-headers-howto)
- [Cloud Run Direct VPC egress and firewall limitations](https://docs.cloud.google.com/run/docs/configuring/vpc-direct-vpc)
- [IAP uses the infrastructure X-Serverless-Authorization header](https://docs.cloud.google.com/iap/docs/enabling-cloud-run)
- [Google workload ID tokens](https://docs.cloud.google.com/docs/authentication/get-id-token)
- [PyJWT validation API](https://pyjwt.readthedocs.io/en/stable/api.html)
