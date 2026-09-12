# Cloud trading authority chain

This image runs as four private Cloud Run services. Each revision uses a
different Google service account, KMS signing key, input subscription and output
topic:

| Stage | Runtime identity | Input | Output | Signing key |
| --- | --- | --- | --- | --- |
| review | `aureon-trade-review` | `aureon-trade-intents-v1` | `aureon-trade-reviewed-v1` | `aureon-review-signing` |
| dispatch | `aureon-trade-dispatch` | `aureon-trade-reviewed-v1` | `aureon-trade-dispatch-v1` | `aureon-dispatch-signing` |
| executor | `aureon-trade-executor` | `aureon-trade-dispatch-v1` | `aureon-trade-executor-results-v1` | `aureon-executor-signing` |
| receipt | `aureon-trade-receipt` | `aureon-trade-executor-results-v1` | `aureon-trade-terminal-receipts-v1` | `aureon-receipt-signing` |

`aureon-cloud-runtime` can publish only the first topic and consume only the
terminal readback subscription. The executor alone has Secret Manager access to
the pinned owner exchange-credential secret. Every stage has read-only access to
the public keys, while each private signing operation is restricted to that
stage's KMS key.

The held release accepts `control_plane_probe` and contains the reviewed live
adapters, but order intents remain rejected while release is false. A probe requires
the deployment hold, real-order hold and exchange-mutation hold to remain active.
Its executor outcome records zero attempted and submitted orders. `order` intents
fail closed until all three release controls are explicitly true:

The supervised cloud receipt collector publishes this held probe every two minutes
while the owner authorization lease is active. It stops publishing when the lease
is inactive and refuses to publish if any of the six runtime holds has weakened.

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

The current release setting remains `AUREON_LIVE_EXECUTION_RELEASE=0`. Enabling
the adapter and ledger readiness flags proves code and infrastructure presence;
it does not grant order authority. Release additionally requires a current human
lease, all six requested controls, current four-provider readback, an explicit
release receipt, and the governed handoff controller.

Messages use canonical ASCII JSON, a 60-second maximum lifetime, exact object
shapes and deterministic stage IDs. KMS Ed25519 signatures join each stage to the
previous digest. Pub/Sub redelivery produces the same signed stage bytes.
