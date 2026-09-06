# Aureon Trading — Project Sero

Enhanced Aureon/Sero workspace import, captured on 6 September 2026.

This repository preserves the supplied workspace in two forms:

- **Browsable source and documentation:** Fusion, radar, trading, Sero/HNC
  engines, the upstream Aureon packages, frontend code, tests, deployment
  material, and supporting projects. Credential values are replaced by
  `REDACTED_USE_CLOUD_SECRET` in this view.
- **Complete original workspace:** all **42,114 inventoried files**, containing
  **5,137,430,459 bytes**, in the authenticated encrypted
  [complete workspace release](https://github.com/RA-CONSULTING/Aureon-Trading--Project-Sero/releases/tag/workspace-2026-09-06). This includes the
  original credentials, private records, runtime state, logs, caches, binary
  assets, historical imports, and embedded Git history. No inventoried file
  was excluded from the encrypted backup.

The encrypted backup occupies 1,486,182,143 bytes across six release assets.
Its recovery key is held separately by the owner, outside this repository.
The entire archive was authenticated and all 42,114 captured file hashes were
verified before upload. This is a live file snapshot, not an atomic disk image.

## Main components

| Location | Contents |
|---|---|
| [`aureon_fusion/`](aureon_fusion/) | Enhanced Fusion runtime, governance, model integration, and component registry |
| [`aureon_radar/`](aureon_radar/) | Market feeds, exchange adapters, scanners, and radar integration |
| [`unified_margin_trader/`](unified_margin_trader/) | Unified trading components and their supplied tests |
| [`aureon-os-upstream/`](aureon-os-upstream/) | Captured upstream Aureon source with its local modifications |
| [`aureon-trading/`](aureon-trading/) | Additional trading, frontend, documentation, and deployment material |
| Workspace-root scripts | Sero, HNC, orchestration, and supporting engines |

Historical module descriptions and performance claims are retained as source
material; this import does not independently validate those claims.

## Retrieve every original file

Download the six `workspace.aes.part*` files plus `backup-manifest.json`,
`restore_aureon_backup.py`, and `RECOVERY.md` from the
[workspace release](https://github.com/RA-CONSULTING/Aureon-Trading--Project-Sero/releases/tag/workspace-2026-09-06)
into one directory. A normal Git clone contains the source and restoration
instructions; it does not automatically download the encrypted release assets.

Use the separately held recovery key and follow
[`full-workspace-backup/RECOVERY.md`](full-workspace-backup/RECOVERY.md).
The restore tool verifies encrypted-part checksums, the AES-GCM authentication
tag, and every archived file's checksum before reporting success. It refuses
to overwrite a nonempty restore destination and does not execute application
code. Original credential values are recovered from the encrypted archive.

## Google Cloud preparation

The intended Google Cloud project is `aureon-trading`.
See [`DEPLOYMENT_GOOGLE_CLOUD.md`](DEPLOYMENT_GOOGLE_CLOUD.md) for credential
mapping to Secret Manager and the deployment work still required.

This repository is a preserved workspace import. It is not yet a verified
Cloud Run image or deployment. No cloud resources, exchange requests, live
orders, or local runtime restarts were performed during the import. The supplied
Dockerfiles require review before they can run the enhanced stack on Cloud Run.
