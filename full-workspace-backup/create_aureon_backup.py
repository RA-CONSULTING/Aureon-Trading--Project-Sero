"""Create AUREON-SERO-WORKSPACE-V1 encrypted backup compatible with restore_aureon_backup.py."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

AAD = b"AUREON-SERO-WORKSPACE-V1"
FORMAT = "AUREON-SERO-WORKSPACE-V1"
PART_SIZE = 256 * 1024 * 1024


def should_skip(rel: Path, exclude_roots: set[str]) -> bool:
    parts = rel.parts
    if not parts:
        return True
    if parts[0] in exclude_roots:
        return True
    name = parts[-1]
    if name in {".git"} and len(parts) > 1:
        # keep embedded git content if present, but skip our excluded clone entirely above
        pass
    return False


def iter_files(root: Path, exclude_roots: set[str]):
    for dirpath, dirnames, filenames in os.walk(root):
        rel_dir = Path(dirpath).relative_to(root)
        # prune excluded top-level dirs early
        if rel_dir == Path("."):
            dirnames[:] = [d for d in dirnames if d not in exclude_roots]
        else:
            top = rel_dir.parts[0]
            if top in exclude_roots:
                dirnames[:] = []
                continue
        # skip nested .git inside excluded handled; allow other .git
        for fn in filenames:
            p = Path(dirpath) / fn
            rel = p.relative_to(root)
            if should_skip(rel, exclude_roots):
                continue
            yield p, rel


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--key-file", type=Path, required=True, help="DPAPI recovery key path (created)")
    ap.add_argument("--exclude", action="append", default=[], help="Top-level dir names under source to exclude")
    ap.add_argument("--extra-file", action="append", default=[], help="hostPath|archiveRelPosix extras")
    args = ap.parse_args()

    source = args.source.resolve()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    exclude = set(args.exclude or [])

    if args.key_file.exists():
        raise SystemExit("Refusing to overwrite existing key file")

    key = os.urandom(32)
    nonce = os.urandom(12)

    # Protect key with DPAPI
    import win32crypt

    blob = win32crypt.CryptProtectData(key, "Aureon-Sero-Recovery-Key", None, None, None, 0)
    args.key_file.parent.mkdir(parents=True, exist_ok=True)
    args.key_file.write_bytes(blob)

    zip_path = out / "workspace.zip.tmp"
    aes_path = out / "workspace.aes.tmp"
    started = datetime.now(timezone.utc)

    files_meta = []
    unavailable = 0
    changed = []
    captured_bytes = 0

    print("PHASE zip", flush=True)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, allowZip64=True) as zf:
        for src, rel in iter_files(source, exclude):
            arc = Path("workspace") / Path(*rel.parts)
            posix = arc.as_posix()
            try:
                st1 = src.stat()
                h = hashlib.sha256()
                with src.open("rb") as f:
                    while True:
                        chunk = f.read(1024 * 1024)
                        if not chunk:
                            break
                        h.update(chunk)
                digest = h.hexdigest()
                # write file
                zf.write(src, posix)
                st2 = src.stat()
                if st1.st_size != st2.st_size or st1.st_mtime_ns != st2.st_mtime_ns:
                    changed.append(rel.as_posix())
                files_meta.append(
                    {
                        "path": Path(*rel.parts).as_posix(),
                        "bytes": st1.st_size,
                        "sha256": digest,
                        "mtime_ns": st1.st_mtime_ns,
                    }
                )
                captured_bytes += st1.st_size
                if len(files_meta) % 500 == 0:
                    print(f"  zipped {len(files_meta)} files...", flush=True)
            except Exception as e:
                unavailable += 1
                print(f"  UNAVAILABLE {rel}: {type(e).__name__}", flush=True)

        for item in args.extra_file:
            host, arel = item.split("|", 1)
            src = Path(host)
            try:
                st1 = src.stat()
                h = hashlib.sha256()
                data = src.read_bytes()
                h.update(data)
                digest = h.hexdigest()
                arc = Path("workspace") / Path(arel)
                zf.writestr(arc.as_posix(), data)
                files_meta.append(
                    {
                        "path": Path(arel).as_posix(),
                        "bytes": st1.st_size,
                        "sha256": digest,
                        "mtime_ns": st1.st_mtime_ns,
                    }
                )
                captured_bytes += st1.st_size
                print(f"  extra {arel} bytes={st1.st_size}", flush=True)
            except Exception as e:
                unavailable += 1
                print(f"  EXTRA_UNAVAILABLE {arel}: {type(e).__name__}", flush=True)

        snap = {
            "format": FORMAT,
            "source": str(source),
            "files": files_meta,
            "unavailable": unavailable,
            "changed_during_read": changed,
            "captured_files": len(files_meta),
            "captured_bytes": captured_bytes,
        }
        zf.writestr("snapshot-manifest.json", json.dumps(snap, indent=2))

    print("PHASE encrypt", flush=True)
    encryptor = Cipher(algorithms.AES(key), modes.GCM(nonce)).encryptor()
    encryptor.authenticate_additional_data(AAD)
    overall = hashlib.sha256()
    with zip_path.open("rb") as inf, aes_path.open("wb") as outf:
        while True:
            chunk = inf.read(4 * 1024 * 1024)
            if not chunk:
                break
            enc = encryptor.update(chunk)
            outf.write(enc)
            overall.update(enc)
        final = encryptor.finalize()
        if final:
            outf.write(final)
            overall.update(final)
        tag = encryptor.tag
    zip_path.unlink(missing_ok=True)

    print("PHASE split", flush=True)
    parts = []
    with aes_path.open("rb") as f:
        idx = 1
        while True:
            data = f.read(PART_SIZE)
            if not data:
                break
            name = f"workspace.aes.part{idx:03d}"
            part_path = out / name
            part_path.write_bytes(data)
            parts.append({"file": name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
            print(f"  wrote {name} bytes={len(data)}", flush=True)
            idx += 1
    aes_path.unlink(missing_ok=True)

    completed = datetime.now(timezone.utc)
    manifest = {
        "format": FORMAT,
        "cipher": "AES-256-GCM",
        "payload": "ZIP64 DEFLATE",
        "nonce_hex": nonce.hex(),
        "tag_hex": tag.hex(),
        "aad": FORMAT,
        "parts": parts,
        "ciphertext_sha256": overall.hexdigest(),
        "started_utc": started.isoformat(),
        "completed_utc": completed.isoformat(),
        "captured_files": len(files_meta),
        "captured_bytes": captured_bytes,
        "unavailable_files": unavailable,
        "live_files_changed_during_read": len(changed),
        "recovery_key": "Stored locally; never uploaded to GitHub",
    }
    (out / "backup-manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    # copy restore tooling pointers
    print(json.dumps({
        "ok": True,
        "out": str(out),
        "key_file": str(args.key_file),
        "parts": len(parts),
        "captured_files": len(files_meta),
        "captured_bytes": captured_bytes,
        "ciphertext_sha256": overall.hexdigest()[:16] + "...",
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
