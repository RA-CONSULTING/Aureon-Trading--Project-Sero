# Held cloud source update

This overlay is installation tooling, not evidence that the VM was updated. Do not upload `hold-before/`, test caches or local review receipts as application source.

## Files and roles

- `deployment/google-cloud/build_release_bundle.py`: exports only a reviewed list of exact source paths/hashes to a new bundle.
- `deployment/google-cloud/release_update.py`: prepare, apply, check and rollback a dated source/unit transaction.
- `deployment/google-cloud/cloud_read_organ.py`: supervises one selected registry-owned process per systemd cgroup; verifies actual capability-gate HOLD behavior and reapplies the six action holds to the selected child environment.
- Tests use temporary directories and fake service peers. They do not start cloud services, prompts, learning or trading.

The other agent supplies `cloud_http_runtime.py`, `cloud_operator.py` and `cloud_ui_gateway.py`. Include all three and this overlay's three Python files in the reviewed release payload. Include the verified production frontend dist. Source updates to the five restored cloud boundary files belong in the same release.

## Transaction and recovery

`/srv/aureon/runtime/workspace` stays in place. Only manifest-listed source files and the explicitly selected unit files are replaced. State, private files, approvals, provider credentials, logs and unselected source stay untouched. Existing source/unit bytes are backed up privately inside `/srv/aureon/releases/<dated-id>/backup`; rollback never restores runtime data or old approval snapshots.

The bundle manifest uses schema `aureon.source-release.v1`, an exact 40–64 lowercase hex revision, a dated release ID such as `20260911T230000Z-0123456789ab`, and a nonempty `files` list of `{path, sha256, size}`. Relative paths map from `files/` to the unchanged workspace root. Bundle creation rejects non-source roots, traversal, symlinks, runtime/private paths, duplicate/case-colliding paths, oversized files and changed reviewed hashes. Source-only publication review remains necessary; the path checks cannot classify every possible sensitive source literal.

Prepare copies and verifies the selected source, compiles Python without importing it, snapshots exact service ownership/liveness and creates the rollback journal before stopping anything. There is one update lock. Apply rechecks the frozen source and service inventory, persistently disables the selected existing units' boot enablement, stops those services, atomically replaces each file while preserving original mode/UID/GID, reloads systemd, starts the selected data owners then operator then UI, checks exact-revision held HTTP readiness and enables only those selected units. The commit marker is written last. The selected services must be standalone instances as in the reviewed cloud profile; externally triggered activation units or unselected dependents require separate exclusion before applying.

This is a transaction **to the stopped service set**, with atomic individual file replacements. It is not an instantaneous whole-workspace directory swap. Every existing service that could use the changed shared source must be in the explicitly reviewed affected-service inventory. No full-fleet discovery or shutdown is inferred automatically. The retained old `cloud_organ.py` and unselected service units are not rewritten by this tool.

Failure triggers source/unit rollback and restores original service active/enabled states. New unit links are disabled before their unit files are removed. Unknown ownership, corrupted backups, changed/newer source, an unsuccessful stop or conflicting service inventory blocks rather than overwriting or killing an unrelated process. If the host is interrupted mid-update, `apply` refuses to resume a partial mixed source tree; use explicit `rollback` after inspecting its journal. A `rollback_blocked` phase needs operator review. The tool never deletes whole directories or backups.

`check` verifies current source/unit hashes against the journal's committed or rolled-back phase. It does not attest fresh provider streams. Service liveness and HTTP readiness are also not proof of trading or all-source readiness; root must finish provider/source-clock read-backs before retiring the desktop owner.

## Service ownership and holds

Known cloud HTTP units are `aureon-cloud-operator.service` and `aureon-cloud-ui.service`, using the distinct HTTP shims. They use runtime Secret Manager identifiers only; no secret value is supplied in arguments or generated unit files. The operator additionally requires a pinned tenant-auth secret containing exactly `project_url` and a public Supabase `publishable_key`; it rejects service-role material and reports `tenant_auth_ready: true` only after the isolated Secret Manager worker validates that payload. Both services remain on loopback and report `/__aureon_health` with the exact revision and `release_authority: false`.

For data/runtime services use explicit `aureon-organ@<name>.service` selections from `READ_ORGANS`. These include current analysis-only `unified_market_trader`, `unified_market_status`, `market_stream_feeder`, HNC/Queen, assessment and passive data producers. The existing `sero_autonomous_expansion` service can only be retained by the installer when it is already active. `unity_supervisor`, `operator_gateway`, `frontend_vite`, radar execution, action hubs and arbitrary services are not eligible. No second registry HTTP owner is started.

The runner validates real `deployment_hold` verdicts for trading, process execution, code execution, outbound communication and non-public network actions; an environment flag by itself fails this check. It never adopts an already-running process. It checks the new PID's cgroup and creation time, and only stops a still-matching registry owner while holding the registry's existing lock.

Every generated unit and selected registry child carries:

```text
AUREON_DEPLOYMENT_HOLD=1
AUREON_DISABLE_REAL_ORDERS=1
AUREON_DISABLE_EXCHANGE_MUTATIONS=1
AUREON_ORDER_INTENT_PUBLISH=0
AUREON_LIVE_TRADING=0
AUREON_UNIFIED_ORDER_EXECUTOR=0
```

## Installation plan — do not execute before VM discovery/review

1. Root reads the actual VM service/PID inventory, confirms the rollback snapshot, dependency availability and free space, then finalizes the affected owned-service list. Provision the VM service identity and least-privilege access to the pinned HTTP secret version separately. Nothing here changes VM size, IAM, firewall or secret contents.
2. Root freezes the isolated source checkout and verified dist at the intended pushed revision. Build `reviewed-paths.json` as a list of `{path, sha256}` for the approved deploy overlay. Do not select live runtime data or a dirty directory recursively.
3. Run `build_release_bundle.py --source <frozen-checkout> --paths <reviewed-paths.json> --destination <new-bundle-dir> --revision <full-sha> --release-id <UTC-dated-id>`. Run the finite publication secret scans against this exact bundle and its manifest.
4. Transfer the verified bundle and trusted updater through the existing authenticated cloud channel. Recheck all hashes on the VM. Run the current release's `deployment/google-cloud/test_deployment_hold.py` in its isolated temporary workspace before installation. It must prove restored release flags, matrix approvals and door approvals do not release actions or replay signals.
5. As the VM administrator, run `release_update.py prepare --bundle <verified-bundle> --service <owned-unit> ... --project <verified-project> --secret <operator-http-secret-id> --secret-version <numeric-version> --tenant-secret <supabase-tenant-secret-id> --tenant-secret-version <numeric-version>`. Defaults are the existing workspace, `/srv/aureon/releases`, and `/etc/systemd/system`. Inspect the resulting journal and exact affected-service list. It contains only pinned identifiers, never secret values.
6. Run `release_update.py apply --release /srv/aureon/releases/<dated-id>`, then `check` with the same release. Keep the journal/rollback directory. On interruption or failure, inspect and run `rollback` for that exact release; do not reuse restored approvals to resume actions.
7. Root verifies cloud HTTP revision, auth isolation, all claimed source clocks, provider read-backs, database integrity, ownership and continuity before any desktop shutdown. No live action release follows from installation, health checks or sole-host ownership.

Rollback preserves the original source/unit configuration and original service status, so the pre-update cloud must itself already have the validated deployment hold. If that original state is unheld or unverified, do not apply this update until root establishes a safe baseline. No automatic garbage collection or removal of omitted/deleted source paths is performed.
