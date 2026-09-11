"""Copy only an explicit reviewed source list into a new immutable release bundle."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from release_update import (MAX_RELEASE_BYTES, SCHEMA, ReleaseError, confined,
                            digest, durable_write, read_bytes, source_path)


def build(source: Path, selected: list, destination: Path, revision: str, release_id: str) -> dict:
    if not re.fullmatch(r"[0-9a-f]{40,64}", revision) or not re.fullmatch(r"[0-9]{8}T[0-9]{6}Z-[0-9a-f]{8,16}", release_id):
        raise ReleaseError("exact_revision_and_dated_release_required")
    if not isinstance(selected, list) or not selected or len(selected) > 20000:
        raise ReleaseError("explicit_bounded_source_list_required")
    if destination.exists() or destination.is_symlink():
        raise ReleaseError("bundle_destination_must_be_new")
    if destination.resolve().is_relative_to(source.resolve()):
        raise ReleaseError("bundle_must_be_outside_source_checkout")
    seen, rows, payload, total = set(), [], [], 0
    for item in selected:
        relative = source_path(item if isinstance(item, str) else item.get("path"))
        if relative.casefold() in seen:
            raise ReleaseError("duplicate_source_selection")
        seen.add(relative.casefold())
        data = read_bytes(confined(source, relative))
        hashed = digest(data)
        if isinstance(item, dict) and item.get("sha256") != hashed:
            raise ReleaseError("reviewed_source_hash_changed")
        total += len(data)
        if total > MAX_RELEASE_BYTES:
            raise ReleaseError("release_size_limit")
        rows.append({"path": relative, "sha256": hashed, "size": len(data)})
        payload.append((relative, data))
    destination.mkdir(parents=True, mode=0o700)
    (destination / "files").mkdir()
    for relative, data in payload:
        durable_write(confined(destination / "files", relative), data, 0o644)
    manifest = {"schema": SCHEMA, "revision": revision, "release_id": release_id,
                "files": rows, "bytes": total, "contains_runtime_state": False}
    durable_write(destination / "manifest.json", (json.dumps(manifest, sort_keys=True, indent=2) + "\n").encode())
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--paths", required=True, type=Path)
    parser.add_argument("--destination", required=True, type=Path)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--release-id", required=True)
    args = parser.parse_args()
    selected = json.loads(read_bytes(args.paths, 4 * 1024 * 1024))
    manifest = build(args.source, selected, args.destination, args.revision, args.release_id)
    print(json.dumps({"files": len(manifest["files"]), "bytes": manifest["bytes"], "revision": manifest["revision"]}))


if __name__ == "__main__":
    main()
