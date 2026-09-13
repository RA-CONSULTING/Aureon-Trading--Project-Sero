# Cloud trading authority chain

The exact Google Cloud resource/IAM cutover and read-only provider audit are
documented in [AUTHORITY_COMMISSIONING.md](AUTHORITY_COMMISSIONING.md).
The fail-closed archive and acknowledgement procedure for the four retired
pull-subscription backlogs is documented in
[LEGACY_BACKLOG_ARCHIVE.md](LEGACY_BACKLOG_ARCHIVE.md).

This image runs as five private Cloud Run services: one signed release
controller and four ordered authority stages. Each service uses a dedicated
Google service account and KMS signing key; the four stages also use distinct
input subscriptions and output topics:

| Stage | Runtime identity | Input | Output | Signing key |
| --- | --- | --- | --- | --- |
| controller | `aureon-trade-controller` | signed owner release request | Firestore release state and `aureon-trade-release-receipts-v1` | `aureon-controller-signing` |
| review | `aureon-trade-review` | `aureon-trade-intents-v1` | `aureon-trade-reviewed-v1` | `aureon-review-signing` |
| dispatch | `aureon-trade-dispatch` | `aureon-trade-reviewed-v1` | `aureon-trade-dispatch-v1` | `aureon-dispatch-signing` |
| executor | `aureon-trade-executor` | `aureon-trade-dispatch-v1` | `aureon-trade-executor-results-v1` | `aureon-executor-signing` |
| receipt | `aureon-trade-receipt` | `aureon-trade-executor-results-v1` | `aureon-trade-terminal-receipts-v1` | `aureon-receipt-signing` |

The VM's attached `aureon-vm-token-broker` identity has no data-plane roles.
Its root-only broker impersonates four narrow, keyless identities. The operator
identity publishes signed release requests; the trade-bridge identity publishes
governed order intents and consumes the terminal readback subscription; the UI
identity reads only the HTTP secret; and provider organs read only the owner
provider secret. Every non-broker Aureon unit denies both metadata IPs and reads
only its root-owned, group-readable short-lived token file. The executor alone
can read the pinned owner exchange-credential secret. Each authority stage can
sign only with its own KMS key, and downstream verifiers receive only the exact
public-key grants they need.

The held release accepts `control_plane_probe` and contains the reviewed live
adapters, but order intents remain rejected while release is false. A probe requires
the deployment hold, real-order hold and exchange-mutation hold to remain active.
Its executor outcome records zero attempted and submitted orders. `order` intents
fail closed until all three release controls are explicitly true:

The supervised cloud receipt collector publishes this held probe every two minutes
while the owner authorization lease is active. Before activation it updates only
`aureon_trade_attestations/current_probe`. After activation it reads and verifies
the controller signature, then carries an exact binding to the active release
generation, request, authorization event, lease expiry, source revision and signed
state digest. The receipt service writes those bound refreshes to the separate
`aureon_trade_attestations/current_readiness` document, so activation evidence is
never overwritten.

Each readiness refresh is exchange read-only and expires after five minutes or at
the original operator lease expiry, whichever occurs first. It cannot grant,
extend or replace release authority. The executor reduces account responses to
four account-binding hashes and binary zero-or-configured-cap allowances; the cap
is at most USD 5. It signs that compact statement with `aureon-executor-signing`.
The receipt service verifies the executor signature and signs a second detached
endorsement with `aureon-receipt-signing`. The VM bridge verifies both public keys
and accepts the statement only while the independently verified controller release
is active and its generation, request, event, expiry, revision and signed-state
digest all match. A hold, replacement generation, expired lease, stale refresh,
bad signature or missing venue fails closed without an order call.

The four account reads run concurrently under an 18-second global provider
deadline after the bounded Secret Manager read. Every HTTP and KMS operation is
also bounded, and the authority image uses a 120-second worker timeout so the
bounded release verification, account reads, detached signatures and publish can
complete without Gunicorn killing a valid slow probe. The publisher stops when
the lease is inactive and refuses to publish if any of the six local runtime holds
has weakened.

The same supervised VM service owns the narrow owner order-intent bridge. The
bridge does not load exchange credentials or call exchange APIs. It leaves all
six local Unified Market Trader controls held and publishes to
`aureon-trade-intents-v1` only after independently verifying the controller's
KMS-signed active release against the current owner lease and exact source
revision. A candidate must come from a complete runtime snapshot no more than
30 seconds old, join to fresh provider timestamps and prices, pass the HNC and
trading-analysis gates, carry usable scanner cross-references, and select one
ready cloud-adapter route with provider-backed execution budget. At most one
route is selected. Spot sells without asset-balance evidence and margin routes
unsupported by the isolated adapters remain blocked.

Before a publish, the bridge durably reserves deterministic 64-hex intent and
client IDs. The reservation prevents a crash or uncertain Pub/Sub response from
causing an automatic retry. A 15-minute per-route cooldown and a 24-hour replay
window persist in the private
`/var/lib/aureon-trade-bridge/order-intent-bridge-state.json`. Sanitized
terminal and intent status is written with mode 0640 beneath
`/var/lib/aureon-control-exchange/trade-readback`. The published order is
a canonical contract-validated market intent with a positive venue-bounded
quantity and no more than USD 5 quote value. Only the fixed metadata, Firestore,
KMS, and Pub/Sub endpoints are reachable through this code path; redirects and
proxies are disabled. The sanitized status and Pub/Sub message receipt are
reported through the operator cloud-trading-control surface.

* `AUREON_LIVE_EXECUTION_RELEASE=1`
* `AUREON_DURABLE_BUDGET_LEDGER=1`
* `AUREON_ORDER_ADAPTER_READY=1`

The executor loads the pinned owner credential secret in memory and can probe all
four live provider accounts without placing an order. Live adapters bind Alpaca,
Binance, and Kraken to deterministic client order IDs and bind Capital orders to
its returned deal reference and confirmation endpoint. A Firestore transaction
atomically reserves the intent and UTC daily budget before submission. Redelivery
returns an observed effect or performs provider lookup; ambiguous outcomes become
`uncertain` and are never automatically submitted again.

Every new order also passes a read-only provider instrument preflight before the
Firestore reservation. Alpaca asset metadata must confirm active/tradable status,
fractional support and its live size/price increments; Binance `exchangeInfo`
filters must accept the exact quantity, notional and limit price; Kraken
`AssetPairs` must accept `ordermin`, `costmin`, lot decimals and tick size; and
Capital market metadata must accept the exact deal size and increment. The
normalized rules are reduced to a SHA-256 commitment stored with the effect and
carried through the terminal receipt. A missing, malformed or changed rule set
rejects before any provider mutation. Provider HTTP uses only fixed HTTPS hosts,
disables redirects and ambient proxies, and emits stable errors without response
bodies or credential-bearing URLs. Missing or malformed rules reject immediately;
a changed commitment cannot join an existing reservation. New probe attestations
require the signed `instrument_preflight_enforced` capability, so older probes
cannot authorize release.

A provider sizing rejection also carries a signed, fixed-shape per-venue
`instrument_readiness_blocker`. It contains only the stable reason code and
normalized required minimum quantity, quantity step, USD notional minimum,
price step and quantity unit when the provider supplied those values. It never
contains a symbol, submitted value, response body, endpoint, header, account or
credential. The executor preserves the exact signed intent and the USD 5 cap;
it does not round, inflate, replace or resubmit a rejected order. A cap change
is a separate signed human risk decision.

The four authority stages use `AUREON_LIVE_EXECUTION_RELEASE=1` to consult the
controller's signed state for every message. That capability flag does not grant
order authority: a missing, held, expired, or different-revision controller
state replaces it with false before the stage handler runs. Release additionally
requires a current human lease, all six requested controls, current four-provider
readback, an explicit release receipt, and the governed handoff controller.

Messages use canonical ASCII JSON, a 60-second maximum lifetime, exact object
shapes and deterministic stage IDs. KMS Ed25519 signatures join each stage to the
previous digest. Pub/Sub redelivery produces the same signed stage bytes.
