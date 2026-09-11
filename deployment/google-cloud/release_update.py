"""Finite source-only cloud update with held services and durable rollback.

This installer never imports application modules or copies runtime state. A
transaction is atomic to the stopped service set, with atomic individual file
replacements. Boot enablement stays inhibited while file installation is partial.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import re
import stat
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path, PurePosixPath

SCHEMA = "aureon.source-release.v1"
HOLDS = {
    "AUREON_DEPLOYMENT_HOLD": "1", "AUREON_DISABLE_REAL_ORDERS": "1",
    "AUREON_DISABLE_EXCHANGE_MUTATIONS": "1", "AUREON_ORDER_INTENT_PUBLISH": "0",
    "AUREON_LIVE_TRADING": "0", "AUREON_UNIFIED_ORDER_EXECUTOR": "0",
}
READ_ORGANS = frozenset({
    "real_time_data_feeder", "schumann_real_daemon", "planetary_monitor_daemon",
    "solar_system_collector", "sero_space_weather", "aureon_radar_bridge", "hnc_core",
    "soul_protection_daemon", "mind_neural_canvas", "queen_mind", "heartbeat_daemon",
    "hnc_live_daemon", "global_energy_aggregator", "assessment_snapshot_producer",
    "harmonic_affect_producer", "market_stream_feeder", "unified_market_status",
    "unified_market_trader",
})
# Retain an already-active legacy service only; do not newly activate expansion.
RETAIN_ONLY = frozenset({"sero_autonomous_expansion"})
HTTP_UNITS = {"aureon-cloud-operator.service": "operator", "aureon-cloud-ui.service": "ui-gateway"}
BLOCKED_PARTS = frozenset({".git", ".aureon", "logs", "uploads", "node_modules", "__pycache__", "backups", "private", "secrets"})
MAX_FILE_BYTES = 32 * 1024 * 1024
MAX_RELEASE_BYTES = 512 * 1024 * 1024


class ReleaseError(RuntimeError):
    pass


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_bytes(path: Path, limit=MAX_FILE_BYTES) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise ReleaseError("source_not_regular_file")
    with path.open("rb") as handle:
        data = handle.read(limit + 1)
    if len(data) > limit:
        raise ReleaseError("source_size_limit")
    return data


def source_path(value: str) -> str:
    if not isinstance(value, str) or any(character in value for character in ("\\", "\x00", ":", "\n", "\r")):
        raise ReleaseError("invalid_source_path")
    path = PurePosixPath(value)
    if path.is_absolute() or str(path) != value or any(p in {"", ".", ".."} for p in path.parts):
        raise ReleaseError("invalid_source_path")
    workspace_python = len(path.parts) == 1 and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*\.py", value)
    sero_package_python = bool(path.parts and path.parts[0].startswith("sero_") and path.suffix == ".py")
    if not path.parts or (path.parts[0] not in {"aureon-os-upstream", "aureon_fusion", "aureon_radar", "sero_mycelium", "deployment"}
                          and not workspace_python and not sero_package_python):
        raise ReleaseError("source_root_not_allowed")
    lowered = tuple(part.lower() for part in path.parts)
    name = lowered[-1]
    if any(p in BLOCKED_PARTS or p.startswith(".env") for p in lowered):
        raise ReleaseError("runtime_or_private_path_forbidden")
    code_subtree = (path.parts[:2] == ("aureon-os-upstream", "aureon") or
                    path.parts[:3] == ("aureon-os-upstream", "frontend", "src"))
    if any(p in {"state", "autonomy"} for p in lowered) and not code_subtree:
        raise ReleaseError("runtime_or_private_path_forbidden")
    if (name.endswith((".env", ".sqlite", ".sqlite3", ".db", ".jsonl", ".log", ".dpapi", ".pem", ".key", ".enc", ".zip", ".tar", ".gz"))
            or name in {"provider_keys.json", "organ_registry.json", "brain_predictions_history.json", "miner_brain_knowledge.json"}):
        raise ReleaseError("runtime_or_private_file_forbidden")
    if name.endswith(".json") and any(marker in name for marker in ("approval", "decision", "receipt", "ledger", "history", "portfolio", "position", "credential", "secret", "token")):
        raise ReleaseError("runtime_json_forbidden")
    if path.parts[0] == "deployment" and path.parts[1:2] != ("google-cloud",):
        raise ReleaseError("deployment_path_not_allowed")
    return value


def confined(root: Path, relative: str) -> Path:
    """Refuse symlink/reparse-point traversal, including existing parent folders."""
    if root.is_symlink() or not root.is_dir():
        raise ReleaseError("root_not_real_directory")
    candidate = root.joinpath(*PurePosixPath(relative).parts)
    if not candidate.resolve().is_relative_to(root.resolve()):
        raise ReleaseError("path_escaped_root")
    cursor = root
    for part in PurePosixPath(relative).parts:
        cursor /= part
        if cursor.exists() or cursor.is_symlink():
            attributes = getattr(cursor.lstat(), "st_file_attributes", 0)
            if cursor.is_symlink() or attributes & 0x400:
                raise ReleaseError("link_in_managed_path")
    return candidate


def durable_write(path: Path, data: bytes, mode: int = 0o600, owner: tuple[int, int] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".release-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, mode)
        if owner is not None and os.name == "posix":
            os.chown(temporary, *owner)
        os.replace(temporary, path)
        if os.name == "posix":
            directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def save_journal(release: Path, journal: dict) -> None:
    durable_write(release / "journal.json", (json.dumps(journal, sort_keys=True, indent=2) + "\n").encode())


@contextlib.contextmanager
def update_lock(releases: Path):
    releases.mkdir(parents=True, exist_ok=True)
    lock = confined(releases, ".source-update.lock")
    with lock.open("a+b") as handle:
        handle.seek(0)
        if os.name == "nt":
            import msvcrt
            if lock.stat().st_size == 0:
                handle.write(b"0")
                handle.flush()
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


def organ_name(unit: str) -> str | None:
    match = re.fullmatch(r"aureon-organ@([a-z0-9_]+)\.service", unit)
    return match[1] if match and match[1] in READ_ORGANS | RETAIN_ONLY else None


def validate_service_names(services: list[str]) -> None:
    if not services or len(services) > 32 or len(set(services)) != len(services):
        raise ReleaseError("explicit_unique_owned_services_required")
    if any(unit not in HTTP_UNITS and organ_name(unit) is None for unit in services):
        raise ReleaseError("service_not_allowlisted")


def render_unit(unit: str, workspace: Path, revision: str, project: str, secret: str, version: str) -> bytes:
    """Commands contain only validated paths and secret identifiers, never values."""
    validate_service_names([unit])
    if re.search(r"[^A-Za-z0-9_./-]", str(workspace)):
        raise ReleaseError("unsupported_cloud_workspace_path")
    runner = workspace / "deployment/google-cloud"
    if unit in HTTP_UNITS:
        if not re.fullmatch(r"[a-z][a-z0-9-]{4,61}[a-z0-9]", project) or not re.fullmatch(r"[A-Za-z0-9_-]{1,255}", secret) or not re.fullmatch(r"[1-9][0-9]*", version):
            raise ReleaseError("pinned_cloud_secret_identifiers_required")
        shim = "cloud_operator.py" if HTTP_UNITS[unit] == "operator" else "cloud_ui_gateway.py"
        dist_argument = f"--dist-root {workspace}/aureon-os-upstream/frontend/dist " if HTTP_UNITS[unit] == "ui-gateway" else ""
        command = (f"/srv/aureon/venv/bin/python {runner}/{shim} "
                   f"--source-root {workspace}/aureon-os-upstream {dist_argument}"
                   f"--revision {revision} --project {project} --secret {secret} --secret-version {version}")
    else:
        command = f"/srv/aureon/venv/bin/python {runner}/cloud_read_organ.py {organ_name(unit)}"
    environment = {**HOLDS, "SERO_WORKSPACE": str(workspace),
                   "PYTHONPATH": f"{workspace}:{workspace}/aureon-os-upstream",
                   "PYTHONUNBUFFERED": "1", "PYTHONDONTWRITEBYTECODE": "1"}
    if HTTP_UNITS.get(unit) == "operator":
        environment.update({"AUREON_SUPPRESS_IMPORT_SIDE_EFFECTS": "1", "AUREON_AUDIT_MODE": "1",
                            "AUREON_LLM_ALLOW_HTTP_IN_AUDIT": "1", "AUREON_LLM_REQUEST_TIMEOUT_S": "25"})
        # Preserve the already-restored private provider config by reference only.
        # It is never read, copied into the bundle or written by this installer.
        if (Path(str(workspace)) / "aureon_radar" / ".env").is_file():
            environment["AUREON_ENV_FILE"] = f"{workspace}/aureon_radar/.env"
    lines = ["# Managed source release; no action release authority.", "[Unit]",
             "Description=Aureon held cloud service", "After=network-online.target", "Wants=network-online.target",
             "StartLimitIntervalSec=300", "StartLimitBurst=4", "[Service]", "Type=simple", "User=aureon", "Group=aureon",
             f"WorkingDirectory={workspace}", *[f"Environment={key}={value}" for key, value in environment.items()],
             f"ExecStart={command}", "Restart=on-failure", "RestartSec=20", "TimeoutStopSec=45", "KillMode=control-group",
             "UMask=0077", "NoNewPrivileges=true", "PrivateTmp=true", "ProtectHome=true", "ProtectSystem=strict",
             f"ReadWritePaths={workspace} /srv/aureon/cache", "CapabilityBoundingSet=", "RestrictSUIDSGID=true",
             "[Install]", "WantedBy=multi-user.target", ""]
    return "\n".join(lines).encode()


class Systemd:
    """Every operation is finite and restricted to the supplied unit inventory."""
    def __init__(self, workspace: Path, unit_root: Path, allowed: list[str]):
        if os.name != "posix" or os.geteuid() != 0:
            raise ReleaseError("linux_root_required_for_systemd")
        validate_service_names(allowed)
        self.workspace, self.unit_root, self.allowed = workspace, unit_root, set(allowed)

    def run(self, operation: str, *args: str, timeout=60) -> str:
        result = subprocess.run(["/bin/systemctl", operation, *args], capture_output=True, text=True, timeout=timeout)
        if result.returncode:
            raise ReleaseError("systemd_operation_failed_" + operation)
        return result.stdout

    def snapshot(self, unit: str) -> dict:
        if unit not in self.allowed:
            raise ReleaseError("service_outside_plan")
        raw = self.run("show", unit, "--property=LoadState,ActiveState,SubState,MainPID,UnitFileState,User,FragmentPath,ExecStart")
        fields = dict(line.split("=", 1) for line in raw.splitlines() if "=" in line)
        if fields.get("LoadState") == "not-found":
            return {"exists": False, "active": False, "enabled": False, "main_pid": 0}
        fragment = fields.get("FragmentPath")
        allowed_fragments = {str(self.unit_root / unit)}
        if organ_name(unit):
            allowed_fragments.add(str(self.unit_root / "aureon-organ@.service"))
        command = fields.get("ExecStart", "")
        shim = "cloud_operator.py" if HTTP_UNITS.get(unit) == "operator" else "cloud_ui_gateway.py"
        runner_names = [shim] if unit in HTTP_UNITS else ["cloud_read_organ.py", "cloud_organ.py"]
        runners = [str(self.workspace / "deployment/google-cloud" / name) for name in runner_names]
        role_argument = "--source-root " if unit in HTTP_UNITS else f" {organ_name(unit)}"
        if fields.get("LoadState") != "loaded" or fields.get("User") != "aureon" or fragment not in allowed_fragments or not any(runner in command for runner in runners) or role_argument not in command:
            raise ReleaseError("existing_service_ownership_unverified")
        active = fields.get("ActiveState")
        if active not in {"active", "inactive", "failed"}:
            raise ReleaseError("service_transition_in_progress")
        main_pid = int(fields.get("MainPID", "0"))
        if active == "active" and (fields.get("SubState") != "running" or main_pid <= 0):
            raise ReleaseError("active_service_has_no_running_owned_process")
        return {"exists": True, "active": active == "active", "enabled": fields.get("UnitFileState") == "enabled", "main_pid": main_pid}

    def stop(self, unit: str) -> None:
        self.snapshot(unit)
        self.run("stop", unit)
        if self.snapshot(unit)["active"]:
            raise ReleaseError("service_did_not_stop")

    def start(self, unit: str) -> None:
        self.snapshot(unit)
        self.run("start", unit)
        if not self.snapshot(unit)["active"]:
            raise ReleaseError("service_did_not_start")

    def reload(self) -> None:
        self.run("daemon-reload")

    def enabled(self, unit: str, value: bool) -> None:
        if unit not in self.allowed:
            raise ReleaseError("service_outside_plan")
        self.run("enable" if value else "disable", unit)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def verify_http(unit: str, revision: str) -> None:
    if unit not in HTTP_UNITS:
        return
    port = 8080 if HTTP_UNITS[unit] == "operator" else 5173
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        try:
            with opener.open(f"http://127.0.0.1:{port}/__aureon_health", timeout=3) as response:
                body = response.read(16385)
                if len(body) > 16384:
                    raise ReleaseError("health_response_too_large")
                row = json.loads(body)
            if (row.get("schema") == "aureon.cloud-http-health.v1" and row.get("revision") == revision
                    and row.get("role") == HTTP_UNITS[unit] and row.get("ready") is True
                    and row.get("deployment_hold") is True and row.get("release_authority") is False):
                return
        except Exception:
            pass
        time.sleep(1)
    raise ReleaseError("exact_revision_held_http_health_unavailable")


def prepare(bundle: Path, workspace: Path, releases: Path, units: Path, services: list[str], controller,
            *, project: str = "", secret: str = "", version: str = "") -> Path:
    validate_service_names(services)
    # Data owners first, then operator, then UI whose readiness depends on it.
    services = sorted(services, key=lambda unit: (2 if unit == "aureon-cloud-ui.service" else 1 if unit == "aureon-cloud-operator.service" else 0, unit))
    manifest = json.loads(read_bytes(bundle / "manifest.json", 4 * 1024 * 1024))
    revision, release_id = manifest.get("revision"), manifest.get("release_id")
    if manifest.get("schema") != SCHEMA or not isinstance(revision, str) or not re.fullmatch(r"[0-9a-f]{40,64}", revision):
        raise ReleaseError("manifest_schema_or_revision_invalid")
    if not isinstance(release_id, str) or not re.fullmatch(r"[0-9]{8}T[0-9]{6}Z-[0-9a-f]{8,16}", release_id):
        raise ReleaseError("dated_release_id_required")
    rows = manifest.get("files")
    if not isinstance(rows, list) or not rows or len(rows) > 20000:
        raise ReleaseError("bounded_nonempty_file_manifest_required")
    with update_lock(releases):
        for pending in releases.glob("*/journal.json"):
            previous = json.loads(read_bytes(pending, 16 * 1024 * 1024))
            if previous.get("phase") not in {"committed", "rolled_back", "prepared"}:
                raise ReleaseError("previous_transaction_requires_rollback")
        payload, seen, total = [], set(), 0
        for row in rows:
            relative = source_path(row.get("path"))
            if relative.casefold() in seen:
                raise ReleaseError("duplicate_manifest_path")
            seen.add(relative.casefold())
            data = read_bytes(confined(bundle / "files", relative))
            if row.get("sha256") != digest(data) or row.get("size") != len(data):
                raise ReleaseError("manifest_hash_or_size_mismatch")
            total += len(data)
            if total > MAX_RELEASE_BYTES:
                raise ReleaseError("release_size_limit")
            if relative.endswith(".py"):
                compile(data, relative, "exec")  # syntax preflight; no import/execution/pycache
            payload.append(("source", relative, data))
        snapshots = {unit: controller.snapshot(unit) for unit in services}
        if any(organ_name(unit) in RETAIN_ONLY and not row["active"] for unit, row in snapshots.items()):
            raise ReleaseError("legacy_expansion_may_only_be_retained")
        for unit in services:
            payload.append(("unit", unit, render_unit(unit, workspace, revision, project, secret, version)))
        release = confined(releases, release_id)
        release.mkdir(mode=0o700)  # collision is a hard error; never overwrite a prior release
        journal = {"schema": SCHEMA, "revision": revision, "release_id": release_id, "phase": "prepared",
                   "workspace": str(workspace.resolve()), "units": str(units.resolve()), "services": services,
                   "original_services": snapshots, "manifest_sha256": digest(read_bytes(bundle / "manifest.json", 4 * 1024 * 1024)),
                   "entries": [], "deployment_hold": True, "release_authority": False,
                   "runtime_state_restored": False, "data_source_freshness": "not_attested"}
        for index, (kind, relative, data) in enumerate(payload):
            root = workspace if kind == "source" else units
            target = confined(root, relative)
            before = read_bytes(target) if target.exists() else None
            mode = stat.S_IMODE(target.stat().st_mode) if before is not None else 0o644
            entry = {"kind": kind, "path": relative, "after_sha256": digest(data), "mode": mode,
                     "before_sha256": digest(before) if before is not None else None, "slot": str(index),
                     "owner": [target.stat().st_uid, target.stat().st_gid] if before is not None else None}
            durable_write(release / "staged" / str(index), data)
            if before is not None:
                durable_write(release / "backup" / str(index), before)
            journal["entries"].append(entry)
        save_journal(release, journal)
        return release


def journal_target(journal: dict, entry: dict) -> Path:
    if entry["kind"] == "source":
        source_path(entry["path"])
        return confined(Path(journal["workspace"]), entry["path"])
    if entry["kind"] == "unit" and entry["path"] in journal["services"]:
        return confined(Path(journal["units"]), entry["path"])
    raise ReleaseError("journal_entry_invalid")


def current_hash(path: Path) -> str | None:
    return digest(read_bytes(path)) if path.exists() else None


def rollback(release: Path, controller) -> dict:
    with update_lock(release.parent):
        journal = json.loads(read_bytes(release / "journal.json", 16 * 1024 * 1024))
        return _rollback(release, journal, controller)


def _rollback(release: Path, journal: dict, controller) -> dict:
    if journal["phase"] == "rolled_back":
        return journal
    # A prior committed release cannot overwrite a newer update's source.
    for entry in journal["entries"]:
        if current_hash(journal_target(journal, entry)) not in {entry["before_sha256"], entry["after_sha256"]}:
            raise ReleaseError("rollback_conflicts_with_external_or_newer_source")
        if entry["before_sha256"] is not None and digest(read_bytes(release / "backup" / entry["slot"])) != entry["before_sha256"]:
            raise ReleaseError("rollback_backup_hash_mismatch")
    journal["phase"] = "rolling_back"
    save_journal(release, journal)
    for unit in journal["services"]:
        if controller.snapshot(unit)["exists"]:
            controller.enabled(unit, False)
    for unit in reversed(journal["services"]):
        if controller.snapshot(unit)["exists"]:
            controller.stop(unit)
            if not journal["original_services"][unit]["exists"]:
                controller.enabled(unit, False)
    for entry in reversed(journal["entries"]):
        target = journal_target(journal, entry)
        if current_hash(target) == entry["before_sha256"]:
            continue
        if entry["before_sha256"] is None:
            target.unlink()  # only the exact newly-created, hash-matched managed file
        else:
            durable_write(target, read_bytes(release / "backup" / entry["slot"]), entry["mode"], entry.get("owner"))
    controller.reload()
    for unit in journal["services"]:
        original = journal["original_services"][unit]
        if original["exists"]:
            controller.enabled(unit, original["enabled"])
            if original["active"]:
                controller.start(unit)
    journal["phase"] = "rolled_back"
    journal["rolled_back_at"] = time.time()
    save_journal(release, journal)
    return journal


def check(release: Path) -> dict:
    journal = json.loads(read_bytes(release / "journal.json", 16 * 1024 * 1024))
    phase = journal.get("phase")
    if phase not in {"prepared", "committed", "rolled_back"}:
        raise ReleaseError("interrupted_transaction_requires_rollback")
    expected_key = "after_sha256" if phase == "committed" else "before_sha256"
    for entry in journal["entries"]:
        if current_hash(journal_target(journal, entry)) != entry[expected_key]:
            raise ReleaseError("release_readback_hash_mismatch")
    return journal


def apply(release: Path, controller, health=verify_http) -> dict:
    with update_lock(release.parent):
        journal = json.loads(read_bytes(release / "journal.json", 16 * 1024 * 1024))
        if journal["phase"] != "prepared":
            raise ReleaseError("only_prepared_release_may_apply_use_rollback_for_interruption")
        for entry in journal["entries"]:
            if current_hash(journal_target(journal, entry)) != entry["before_sha256"]:
                raise ReleaseError("source_changed_after_prepare")
            if digest(read_bytes(release / "staged" / entry["slot"])) != entry["after_sha256"]:
                raise ReleaseError("staged_source_hash_mismatch")
        if any(controller.snapshot(unit) != journal["original_services"][unit] for unit in journal["services"]):
            raise ReleaseError("service_inventory_changed_after_prepare")
        journal["phase"] = "stopping"
        save_journal(release, journal)
        try:
            # Persistently remove boot enablement before changing any source.
            # A reboot during installation must not auto-start a mixed tree.
            for unit in journal["services"]:
                if journal["original_services"][unit]["exists"]:
                    controller.enabled(unit, False)
            for unit in reversed(journal["services"]):
                if controller.snapshot(unit)["exists"]:
                    controller.stop(unit)
            journal["phase"] = "installing"
            save_journal(release, journal)
            for entry in journal["entries"]:
                target = journal_target(journal, entry)
                if current_hash(target) != entry["before_sha256"]:
                    raise ReleaseError("source_changed_during_install")
                durable_write(target, read_bytes(release / "staged" / entry["slot"]), entry["mode"], entry.get("owner"))
            controller.reload()
            journal["phase"] = "verifying"
            save_journal(release, journal)
            for unit in journal["services"]:
                controller.start(unit)
                health(unit, journal["revision"])
            for unit in journal["services"]:
                controller.enabled(unit, True)
            journal["phase"] = "committed"
            journal["committed_at"] = time.time()
            journal["verification_scope"] = "source_hashes_service_liveness_and_exact_revision_http_only"
            save_journal(release, journal)
            return journal
        except Exception:
            try:
                _rollback(release, journal, controller)
            except Exception:
                journal["phase"] = "rollback_blocked"
                save_journal(release, journal)
                raise ReleaseError("update_failed_rollback_requires_operator_review") from None
            raise ReleaseError("update_failed_source_rolled_back") from None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "apply", "rollback", "check"))
    parser.add_argument("--bundle", type=Path)
    parser.add_argument("--workspace", type=Path, default=Path("/srv/aureon/runtime/workspace"))
    parser.add_argument("--releases", type=Path, default=Path("/srv/aureon/releases"))
    parser.add_argument("--units", type=Path, default=Path("/etc/systemd/system"))
    parser.add_argument("--release", type=Path)
    parser.add_argument("--service", action="append", default=[])
    parser.add_argument("--project", default="")
    parser.add_argument("--secret", default="")
    parser.add_argument("--secret-version", default="")
    args = parser.parse_args()
    if args.command == "prepare":
        if args.bundle is None:
            raise ReleaseError("bundle_required")
        controller = Systemd(args.workspace, args.units, args.service)
        release = prepare(args.bundle, args.workspace, args.releases, args.units, args.service, controller,
                          project=args.project, secret=args.secret, version=args.secret_version)
        print(json.dumps({"prepared": True, "release": str(release), "requires_review_before_apply": True}))
        return 0
    if args.release is None:
        raise ReleaseError("release_required")
    journal = json.loads(read_bytes(args.release / "journal.json", 16 * 1024 * 1024))
    if args.command == "check":
        journal = check(args.release)
        print(json.dumps({key: journal.get(key) for key in ("revision", "phase", "services", "deployment_hold", "release_authority", "runtime_state_restored", "data_source_freshness")}))
        return 0
    controller = Systemd(Path(journal["workspace"]), Path(journal["units"]), journal["services"])
    result = apply(args.release, controller) if args.command == "apply" else rollback(args.release, controller)
    print(json.dumps({"revision": result["revision"], "phase": result["phase"], "release_authority": False}))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ReleaseError as error:
        print(json.dumps({"ok": False, "reason": str(error)}))
        raise SystemExit(2)
