# Google Cloud authority commissioning

`resource_contract.json` is the exact production boundary. Resolve every
command with one clean 40-character Git revision, two Artifact Registry digest
images, the provider-confirmed Supabase project and owner UUID, the
domain-separated owner-email SHA-256, and the separately domain-separated IAP
administrator SHA-256. Plaintext identities and credentials are forbidden.

The commissioning transaction has distinct phases:

1. immutable build and authority plan;
2. VM release preparation, broker bootstrap and broker-identity attachment;
3. `resource-prepare` for provider resources and exact IAM confinement;
4. no-traffic deployment of seven revisions;
5. publisher freeze, immutable subscription replacement, archive and legacy
   retirement;
6. read-only `staged-revision-attestation`;
7. VM release apply and reboot closure;
8. externally reviewed tail-to-head traffic promotion;
9. strict `finalize` cleanup and readback.

No tool in this directory promotes traffic, enables trading, publishes an
order, or grants release authority.

## Frozen source, certificate and immutable images

Use a clean detached clone at the pushed commit. On the VM, generate the public
bridge certificate receipt after the certificate exists:

```text
python public_bridge_certificate_receipt.py \
  --source-revision FULL_GIT_SHA \
  --receipt /var/lib/aureon-release/bridge-certificate-receipt.json
```

Copy only `bridge-cert.pem` and that redacted receipt from the VM. Never copy
`bridge-key.pem`. Plan and acknowledge both image builds:

```text
python immutable_image_build.py plan \
  --source ABSOLUTE_FROZEN_CLONE \
  --source-revision FULL_GIT_SHA \
  --bridge-certificate ABSOLUTE_PUBLIC_CERTIFICATE \
  --bridge-certificate-receipt ABSOLUTE_CERTIFICATE_RECEIPT \
  --bridge-certificate-receipt-sha256 EXACT_FILE_SHA256 \
  --receipt ABSOLUTE_IMAGE_PLAN

python immutable_image_build.py build [same source/certificate arguments] \
  --plan ABSOLUTE_IMAGE_PLAN \
  --acknowledge-plan-sha256 IMAGE_PLAN_SHA256 \
  --receipt ABSOLUTE_IMAGE_BUILD_RECEIPT
```

The build tool submits minimal temporary contexts tagged by the full commit,
then reads each digest from that exact Cloud Build ID's successful
`results.images` row. It never resolves provenance through a mutable tag lookup.
Use only the two `@sha256:` image values from the receipt. Image contexts,
reviewed-path manifests and VM bundle payloads
read tracked source bytes from the exact Git commit blob. Their hashes therefore
remain identical in Windows and Linux clones regardless of `core.autocrlf`.
The immutable-image receipt also binds the redacted certificate-receipt hash,
DER fingerprint, exact single IP SAN `10.40.0.2`, validity interval, and minimum
86,400-second remaining validity. Staged authority, VM release, reboot
continuity, and finalization must carry that exact certificate evidence; a
different certificate or a shortened validity window fails closed.

## Resolve and prepare the provider resources

Use these resolution arguments unchanged for every authority or Cloud Run
command:

```text
--source-revision FULL_GIT_SHA
--authority-image AUTHORITY_REPOSITORY@sha256:DIGEST
--public-entry-image PUBLIC_REPOSITORY@sha256:DIGEST
--supabase-project-ref PROVIDER_PROJECT_REF
--supabase-owner-subject PROVIDER_CONFIRMED_UUID
--supabase-owner-email-sha256 DOMAIN_SEPARATED_SHA256
--iap-admin-email-sha256 SEPARATELY_DOMAIN_SEPARATED_SHA256
```

Run `authority_commission.py plan` first and retain its `contract_sha256`.
Create the fresh redacted Supabase Auth owner receipt using
`supabase_owner_readback.py` or the protected Management API wrapper. Prepare
the VM release and install its broker-only bootstrap, then use
`vm_identity_commission.py` to attach and read back the broker service account
before IAM cleanup. Then run:

```text
python authority_commission.py apply --phase=resource-prepare \
  [resolution arguments] \
  --acknowledge-contract-sha256 CONTRACT_SHA256 \
  --supabase-owner-readback-receipt ABSOLUTE_OWNER_RECEIPT \
  --acknowledge-supabase-owner-readback-sha256 OWNER_RECEIPT_SHA256 \
  --receipt ABSOLUTE_RESOURCE_PREPARE_RECEIPT
```

This phase first installs and reads back every narrow grant. It removes the
contract-listed broad or extraneous IAM bindings only when the same provider
snapshot proves the running VM has the broker identity and exact scope
attached. If called earlier, it leaves those removals untouched and records
`destructive_iam_cleanup_deferred=true`; rerun the same phase after broker
attachment. Before staging attestation, its receipt must show
`broker_identity_readback_ok=true` and
`destructive_iam_cleanup_deferred=false`. It defers the new Cloud Run
revisions, full VM release readback, immutable subscription replacement, and
legacy subscription retirement. The compatibility spelling `--phase=prepare`
normalizes to `resource-prepare`.

## Stage seven revisions without traffic

Render and inspect the exact deploy plan, then acknowledge it:

```text
python cloud_run_stage.py plan [resolution arguments] \
  --contract ABSOLUTE_RESOURCE_CONTRACT \
  --immutable-image-build-receipt ABSOLUTE_IMAGE_BUILD_RECEIPT \
  --acknowledge-immutable-image-build-receipt-sha256 IMAGE_RECEIPT_SHA256 \
  --receipt ABSOLUTE_CLOUD_RUN_STAGE_PLAN

python cloud_run_stage.py stage [resolution arguments] \
  --contract ABSOLUTE_RESOURCE_CONTRACT \
  --plan ABSOLUTE_CLOUD_RUN_STAGE_PLAN \
  --acknowledge-plan-sha256 CLOUD_RUN_STAGE_PLAN_SHA256 \
  --immutable-image-build-receipt ABSOLUTE_IMAGE_BUILD_RECEIPT \
  --acknowledge-immutable-image-build-receipt-sha256 IMAGE_RECEIPT_SHA256 \
  --receipt ABSOLUTE_STAGE_COMMAND_RECEIPT
```

Every rendered deploy contains the exact image, service account, environment,
ingress, IAP, timeout, concurrency, CPU, memory, scaling, startup probe and
Direct VPC settings plus an explicit revision suffix and `--no-traffic`.
`cloud_run_stage.py` exposes no promotion command. Before each deploy it fsyncs
the receipt with the in-flight service. After any uncertain failure it reads
that exact revision back and records either completion or `recovery_required`.
Re-running the same acknowledged plan revalidates every completed prefix before
continuing. The final command receipt still requires staged provider
attestation.

## Replace and retire subscriptions while publishers stay frozen

Stop and disable `aureon-cloud-operator.service` before observing the
controller subscription. Keep it frozen until replacement completes. Create
the fresh zero-backlog replacement receipt, then run only:

```text
python authority_commission.py apply --phase=subscription-replacement \
  [resolution arguments and contract/owner acknowledgements] \
  --subscription-replacement-receipt ABSOLUTE_REPLACEMENT_RECEIPT \
  --acknowledge-subscription-replacement-sha256 RECEIPT_SHA256 \
  --receipt ABSOLUTE_REPLACEMENT_RESULT
```

For the four legacy pulls, keep both the operator and trade-receipt units
inactive and disabled or masked. Follow `LEGACY_BACKLOG_ARCHIVE.md`; archive
every message before acknowledgement, then collect a fresh Monitoring receipt
with explicit zero points for both metrics on all four exact subscription
names. The archive receipt timestamp must precede or equal the Monitoring
window start:

```text
python legacy_backlog_readback.py \
  --contract-sha256 CONTRACT_SHA256 \
  --source-revision FULL_GIT_SHA \
  --window-seconds 300 \
  --receipt ABSOLUTE_ZERO_BACKLOG_RECEIPT
```

Deletion is performed only by the receipt-gated phase. It requires the archive
receipt, archive scope hash, and zero-backlog receipt before its first delete,
deletes only the four contract names, verifies their absence, and verifies that
the Cloud Run snapshot did not change. Preserve the fresh deletion-time owner
readback separately from the later finalize-time owner readback:

```text
python authority_commission.py apply --phase=legacy-retirement \
  [resolution arguments and contract/owner acknowledgements] \
  --legacy-archive-receipt ABSOLUTE_ARCHIVE_RECEIPT \
  --acknowledge-legacy-archive-receipt-sha256 ARCHIVE_RECEIPT_SHA256 \
  --acknowledge-legacy-archive-scope-sha256 ARCHIVE_SCOPE_SHA256 \
  --legacy-retirement-receipt ABSOLUTE_ZERO_BACKLOG_RECEIPT \
  --acknowledge-legacy-retirement-sha256 ZERO_BACKLOG_RECEIPT_SHA256 \
  --legacy-retirement-owner-readback-receipt ABSOLUTE_DELETION_TIME_OWNER_RECEIPT \
  --acknowledge-legacy-retirement-owner-readback-sha256 DELETION_TIME_OWNER_RECEIPT_SHA256 \
  --receipt ABSOLUTE_LEGACY_RETIREMENT_RESULT
```

The result is the post-deletion
`aureon.gcp.pubsub-legacy-retirement-phase-receipt.v1`. It binds the exact
replacement-subscription configuration before and after deletion, the archive
and zero-backlog receipts at deletion time, the absent legacy names, and
unchanged Cloud Run state. Retain its canonical SHA-256 for finalization.
The phase fsyncs a separate `.progress.json` beside the requested result before
each exact-name deletion and reads the provider after each attempt. Immediately
before every delete and again after every provider readback it proves both
publisher units remain inactive and disabled or masked, the replacement
subscription remains exact, and Cloud Run remains unchanged. If a command
outcome is uncertain, keep publishers frozen and rerun with the same result
path and evidence; the tool accepts only the recorded, provider-absent ordered
prefix and resumes at the next contract name. A later fresh owner receipt may
be used for finalization, but finalization also revalidates the separately
acknowledged deletion-time owner receipt at the recorded retirement start.

## Attest the staged revisions and close the VM

With the subscriptions exact and legacy names absent, attest all seven latest
created/ready revisions. The audit checks the exact latest template for every
service and fails if any staged revision has traffic:

```text
python authority_commission.py apply --phase=staged-revision-attestation \
  [resolution arguments and contract/owner acknowledgements] \
  --immutable-image-build-receipt ABSOLUTE_IMAGE_BUILD_RECEIPT \
  --acknowledge-immutable-image-build-receipt-sha256 IMAGE_RECEIPT_SHA256 \
  --receipt ABSOLUTE_STAGED_ATTESTATION_RECEIPT
```

This phase is read-only. A valid receipt has `status=staged_attested`,
`provider_readback_ok=true`, `cloud_run_staged_without_traffic=true`,
`cloud_run_traffic_changed=false`, and
`vm_readback_deferred_to_release_receipt=true`. This is the authority receipt
accepted by `release_update.py apply`.

Generate the full reviewed source manifest after building the authenticated
frontend `dist` from the frozen commit:

```text
python generate_reviewed_paths.py \
  --source ABSOLUTE_FROZEN_CLONE \
  --source-revision FULL_GIT_SHA \
  --output ABSOLUTE_NEW_REVIEWED_PATHS_JSON
```

Build and transfer the VM bundle as described in `README-cloud-release.md`.
For the existing VM, the broker bootstrap and identity attachment occur before
resource prepare, as described above. Plan and separately acknowledge the
short interruption needed to replace its attached identity:

```text
python vm_identity_commission.py plan \
  --contract ABSOLUTE_RESOURCE_CONTRACT \
  --receipt ABSOLUTE_VM_IDENTITY_PLAN

python vm_identity_commission.py apply \
  --contract ABSOLUTE_RESOURCE_CONTRACT \
  --plan ABSOLUTE_VM_IDENTITY_PLAN \
  --acknowledge-plan-sha256 VM_IDENTITY_PLAN_SHA256 \
  --acknowledge-interruption stop-set-service-account-start:aureon-sero-20260906 \
  --receipt ABSOLUTE_VM_IDENTITY_RECEIPT
```

It attaches only
`aureon-vm-token-broker@aureon-trading.iam.gserviceaccount.com` with the
`cloud-platform` scope and reads back the restarted VM. It grants no IAM role.
Apply the VM bundle with the staged-attestation receipt, run `check`, reboot,
and create both `aureon.gcp.vm-release-readback.v1` and
`aureon.gcp.vm-reboot-continuity.v1` receipts.

## Promotion and strict finalization

Traffic promotion is deliberately outside these tools and requires a separate
reviewed operator action. Promote exact revision names only in this order:

```text
receipt -> executor -> dispatch -> review -> controller -> operator -> web
```

After each promotion, read back one untagged 100% target and the exact serving
revision. Never use a latest-revision shortcut. Once all seven services serve
the attested revisions and both VM receipts are fresh, run `finalize` with the
owner, archive, zero-backlog, post-deletion legacy-retirement, VM release, and
VM reboot receipts, the immutable-image build receipt, the deletion-time owner
receipt, and every exact SHA-256 acknowledgement. Include
`--legacy-retirement-phase-receipt` and
`--acknowledge-legacy-retirement-phase-sha256`, both
`--legacy-retirement-owner-readback-receipt` arguments, and both
`--immutable-image-build-receipt` arguments. Finalize performs no traffic or
order action. It first requires the complete strict provider snapshot, then
removes only extra IAM grants declared by the plan and reads the provider state
back again.

All success and failure receipts are redacted. A missing or stale receipt,
provider series, digest, revision, identity, unit, hash, or explicit
acknowledgement fails closed.
