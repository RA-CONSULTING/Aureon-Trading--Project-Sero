# Aureon full workspace backup recovery

The [GitHub workspace release](https://github.com/RA-CONSULTING/Aureon-Trading--Project-Sero/releases/tag/workspace-2026-09-06)
contains a complete encrypted file backup, including original source, credentials, private
records, state, logs, caches, and embedded Git history. The separate browsable
source view has credential values removed. The original local workspace was
not modified by this upload operation.

Keep `Aureon-Sero-Recovery-Key.dpapi` with these recovery tools. It is protected
by Windows for the current user account; it is never uploaded to GitHub.
Losing access to that Windows account without first exporting a portable key
can prevent recovery. Keep a separate secure backup of the recovery material.

## Verify or restore on this Windows account

Install Python dependencies if required:

```powershell
python -m pip install cryptography pywin32
```

Download all six `workspace.aes.part*` assets, `backup-manifest.json`,
`restore_aureon_backup.py`, and `RECOVERY.md` from the workspace release into
one directory. GitHub Release storage is used because the organisation's
Git LFS budget was unavailable. A Git clone does not download release assets.

From the directory containing this guide, verify every archived file:

```powershell
python restore_aureon_backup.py --backup C:\path\to\downloaded-backup --key-file Aureon-Sero-Recovery-Key.dpapi
```

To restore, add `--restore C:\path\to\new-empty-folder`. The tool refuses to
overwrite existing files. It verifies authenticated encryption, each encrypted
part's SHA-256, and every archived file's SHA-256. No source code is executed.

## Portable recovery or cloud migration

Before moving to another Windows account or to Linux, export a portable key:

```powershell
python restore_aureon_backup.py --backup C:\path\to\downloaded-backup --key-file Aureon-Sero-Recovery-Key.dpapi --export-key C:\secure-location\portable-recovery-key.txt
```

Treat the portable key as a password for the entire workspace. Keep it in
your password manager or another approved secret store, separately from the
archive. Never commit it to GitHub. On Linux, install `cryptography` and pass
the portable file using `--key-file` to the same restoration script.

For Google Cloud Run, transfer only the required current application credentials
to Google Secret Manager and reference them from the service's Variables &
Secrets settings. Do not restore the whole private workspace into a container
build context. See `DEPLOYMENT_GOOGLE_CLOUD.md` in the repository.

This is a file-content backup captured while the local system was running,
not an atomic disk image. Windows ACLs, alternate data streams, and process
memory are not represented. The encrypted internal manifest records captured
paths, bytes, hashes, times, and any files that changed while being read.
