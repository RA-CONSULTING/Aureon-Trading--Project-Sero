# Legacy Pub/Sub backlog archive gate

`legacy_backlog_archive.py` is the one-time, fail-closed drain path for these
four retired pull subscriptions:

* `aureon-trade-review-v1`
* `aureon-trade-dispatch-v1`
* `aureon-trade-executor-v1`
* `aureon-trade-receipt-v1`

It does not delete subscriptions, publish messages, invoke an Aureon runtime,
change Cloud Run traffic, activate a release, or place an order. It performs a
bounded synchronous pull only after Google Compute Engine reports both legacy
publishers inactive and disabled or masked. Each received message is
acknowledged only after both its canonical lossless archive object and a batch
manifest have been uploaded with `ifGenerationMatch=0`, protected by an event
based hold and the exact CMEK, and downloaded at the exact provider generation.
The final root manifest re-reads every referenced message generation and hash.

This tool is not the zero-backlog retirement receipt. After it succeeds, an
independent Cloud Monitoring window must still prove every legacy subscription
has zero undelivered messages and zero oldest-unacked age before the exact-name
receipt-gated retirement phase.

## Required maintenance boundary

Use a new committed and pushed 40-character source revision. It must differ
from every earlier active release revision. Freeze image digests, the authority
contract hash, and the VM release bundle to that same revision before draining.
Do not label a build from an uncommitted tree with an older active revision.

Run the drain in an exclusive maintenance window. Stop and disable both
publishers first:

```powershell
$Gcloud = 'C:\Users\user\Aureon-cloud-tools-20260911\google-cloud-sdk\bin\gcloud.cmd'
$Freeze = 'sudo systemctl disable --now aureon-cloud-operator.service aureon-cloud-trade-receipt.service; systemctl show aureon-cloud-operator.service aureon-cloud-trade-receipt.service --property=Id --property=ActiveState --property=UnitFileState --no-pager'
& $Gcloud compute ssh aureon-sero-20260906 --project=aureon-trading --zone=europe-west1-b --tunnel-through-iap --command=$Freeze --quiet
```

The readback must show both units with `ActiveState=inactive` and
`UnitFileState=disabled` or `masked`. The archive command independently repeats
this readback before the first pull and after all four queues have returned the
required empty polls. Keep other administrators and automation from changing
these units during the operation.

## Archive storage contract

Provision a dedicated bucket in the same location as its Cloud KMS key. Before
the archive run, provider readback must prove all of these properties:

* the retention policy is locked and is at least seven days;
* uniform bucket-level access is enabled;
* public access prevention is `enforced`;
* the exact CMEK is the bucket default; and
* the bucket location exactly matches the CMEK location.

Locking a Cloud Storage retention policy is irreversible. Create and inspect
the bucket and retention duration through a separate reviewed change, then lock
it only after that review. The archive tool only reads the bucket contract; it
never creates or locks the bucket. It places an event based hold on every
message, batch, and root object, so those objects remain held until a later
explicit records-governance decision.

Use a narrow execution identity. It needs `pubsub.subscriptions.consume` on the
four named subscriptions, object create/get/list access on the one archive
bucket, bucket metadata read access, and the existing IAP/OS Login permissions
needed to read the two systemd units. It does not need subscription delete,
topic publish, Cloud Run admin, Secret Manager access, or order authority. The
Cloud Storage service agent must have CMEK encrypt/decrypt access on the one
archive key. Never put a credential value in an argument, object label, log, or
receipt.

Review the provider state without changing it:

```powershell
$ArchiveBucket = '<dedicated-archive-bucket>'
$ArchiveKey = 'projects/aureon-trading/locations/europe-west1/keyRings/<ring>/cryptoKeys/<key>'
& $Gcloud storage buckets describe "gs://$ArchiveBucket" --format=json
& $Gcloud kms keys describe $ArchiveKey --project=aureon-trading --location=europe-west1 --keyring=<ring> --format=json
```

Confirm the returned bucket metadata matches the five requirements above. Do
not copy provider JSON containing unrelated IAM members or account identifiers
into a release receipt.

## Two-step archive run

Run from the repository's `deployment/google-cloud/trading-control` directory.
Choose bounds that exceed the measured backlog while still fitting the reviewed
maintenance window. The defaults pull at most 10 messages per request, archive
at most 10,000 messages or 1 GiB in one run, stop after one hour, and require
three empty pulls per subscription.

First generate the deterministic scope hash. `plan` is local and makes no
provider request:

```powershell
$ContractSha = '<64-character-authority-contract-sha256>'
$SourceRevision = '<40-character-new-commit-sha>'
$Receipt = 'C:\Users\user\Aureon-Sero-cloud-20260911\evidence\legacy-backlog-archive-receipt.json'
$ArchiveScript = 'C:\Users\user\Aureon-Sero-cloud-20260911\deployment\google-cloud\trading-control\legacy_backlog_archive.py'

python $ArchiveScript plan `
  --contract-sha256 $ContractSha `
  --source-revision $SourceRevision `
  --bucket $ArchiveBucket `
  --cmek-key $ArchiveKey `
  --batch-size 10 `
  --max-total-messages 10000 `
  --max-total-bytes 1073741824 `
  --max-runtime-seconds 3600 `
  --empty-polls 3 `
  --minimum-retention-seconds 604800
```

Review every argument and record the printed `scope_sha256`. Then run `archive`
with byte-for-byte identical scope arguments and the explicit acknowledgement:

```powershell
$ScopeSha = '<reviewed-scope-sha256-from-plan>'
python $ArchiveScript archive `
  --gcloud $Gcloud `
  --contract-sha256 $ContractSha `
  --source-revision $SourceRevision `
  --bucket $ArchiveBucket `
  --cmek-key $ArchiveKey `
  --batch-size 10 `
  --max-total-messages 10000 `
  --max-total-bytes 1073741824 `
  --max-runtime-seconds 3600 `
  --empty-polls 3 `
  --minimum-retention-seconds 604800 `
  --acknowledge-scope-sha256 $ScopeSha `
  --receipt $Receipt
```

An upload, provider-generation mismatch, content-hash mismatch, malformed
message, changed publisher state, changed bucket contract, bound, pull, or ack
failure stops the run. A failure after one or more successful acknowledgements
is a partial run, not a completion receipt. Keep the publishers frozen and run
the same reviewed scope again. Deterministic object names, create-only uploads,
exact-generation downloads, and content checks make that restart idempotent.
Never weaken a bound merely to turn a partial run into a pass; review a new
scope and hash if a bound was genuinely too small.

The successful local receipt contains the contract hash, new source revision,
scope hash, bucket name, a hash of the CMEK resource name, final root-manifest
generation and hash, per-run counts, and the two freeze/bucket readback flags.
It contains no message body, attribute value, access token, credential, or KMS
key material. Raw message content remains only in the protected bucket.

## Mandatory zero-backlog handoff

After the archive succeeds, leave both publishers disabled and collect the
independent Cloud Monitoring receipt:

```powershell
$ZeroReceipt = 'C:\Users\user\Aureon-Sero-cloud-20260911\evidence\legacy-backlog-zero-readback.json'
$ReadbackScript = 'C:\Users\user\Aureon-Sero-cloud-20260911\deployment\google-cloud\trading-control\legacy_backlog_readback.py'
python $ReadbackScript `
  --gcloud $Gcloud `
  --contract-sha256 $ContractSha `
  --source-revision $SourceRevision `
  --window-seconds 300 `
  --receipt $ZeroReceipt
```

Accept that receipt only when it contains at least three explicit provider
points spanning at least two minutes for both backlog metrics on every one of
the four subscriptions, and every value is zero. Bind the canonical receipt
SHA-256 printed by the tool to the authority commissioning acknowledgement. The
archive command's empty pulls do not replace this provider receipt.

Subscription retirement remains a later exact-name, receipt-gated action.
This archive tool never performs it. Run `authority_commission.py apply
--phase=legacy-retirement` with the acknowledged archive receipt, archive scope
hash, and zero-backlog receipt; it validates all evidence before its first
delete, fsyncs a per-name recovery journal, and reads back absence of every
ordered prefix. If interrupted, rerun the same result path and exact evidence;
it refuses an unrecorded or out-of-order absent name. Keep the publishers
frozen while replacing
the release-controller subscription's immutable ordering configuration, and
use `subscription_replacement_readback.py` for its separate zero-backlog and
publisher-freeze receipt. Promote explicitly named Cloud Run revisions in
dependency order only after those gates pass. Restore the VM broker and bridge
through the transactional release updater, promote the private operator, and
promote the public web revision on the existing URL last. Final held-state
readback must show the new source revision, four fresh provider reads, no mixed
revision, zero order effects, and release authority still false.
