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

The deployed initial release accepts only `control_plane_probe`. A probe requires
the deployment hold, real-order hold and exchange-mutation hold to remain active.
Its executor outcome records zero attempted and submitted orders. `order` intents
fail closed until all three release controls are explicitly true:

* `AUREON_LIVE_EXECUTION_RELEASE=1`
* `AUREON_DURABLE_BUDGET_LEDGER=1`
* `AUREON_ORDER_ADAPTER_READY=1`

The checked-in image deliberately contains no live order adapter. Enabling an
environment flag therefore cannot create execution authority. A later reviewed
image must add provider order submission, durable effect claiming, uncertain
outcome reconciliation and provider readback before those controls can be set.

Messages use canonical ASCII JSON, a 60-second maximum lifetime, exact object
shapes and deterministic stage IDs. KMS Ed25519 signatures join each stage to the
previous digest. Pub/Sub redelivery produces the same signed stage bytes.

