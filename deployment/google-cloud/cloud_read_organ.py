"""One explicitly selected registry organ per systemd cgroup, under proven HOLD."""
from __future__ import annotations

import os
from pathlib import Path
import signal
import sys
import threading

from release_update import HOLDS, READ_ORGANS, RETAIN_ONLY, ReleaseError


def configure(registry, gate, name: str, environment: dict[str, str]) -> None:
    if name not in READ_ORGANS | RETAIN_ONLY or name not in registry.ORGANS:
        raise ReleaseError("organ_outside_selected_cloud_profile")
    if any(environment.get(key) != value for key, value in HOLDS.items()):
        raise ReleaseError("all_cloud_action_holds_required")
    # Verify the actual gate implementation, not just the environment label.
    if gate.release_authorized() or registry._release_granted():
        raise ReleaseError("restored_approval_can_release_host")
    for action in ("trading_execution:execute_live_trades", "external_communication:send_message",
                   "process_control:execute", "code_generation:execute_code", "network_access:scan_network"):
        verdict = gate._check_verdict(action)
        if verdict.get("allowed") is not False or verdict.get("deployment_hold") is not True:
            raise ReleaseError("deployment_hold_contract_not_enforced")
    original = registry.ORGANS[name]
    # Change only this runner's in-memory selected launch specification. Nothing
    # is persisted to approvals, dormancy state, source or any other organ spec.
    registry.ORGANS[name] = {**original, "env": {**dict(original.get("env") or environment), **HOLDS}}


def cgroup(pid: int) -> bytes:
    return Path(f"/proc/{pid}/cgroup").read_bytes()


def start_owned(registry, name, process_factory, cgroup_reader=cgroup):
    result = registry.start(name)
    if result.get("state") != "started" or result.get("ok") is False:
        # Existing or dormant owners are never adopted or terminated by this unit.
        raise ReleaseError("registry_did_not_start_new_owned_process")
    process = process_factory(result["pid"])
    created = process.create_time()
    if cgroup_reader(process.pid) != cgroup_reader(os.getpid()):
        raise ReleaseError("started_process_not_in_owned_systemd_cgroup")
    return process, created


def stop_owned(registry, name, process, created, cgroup_reader=cgroup):
    # Serialize the owner comparison with the registry's existing launch lock.
    with registry._registry_lock() as held:
        if not held:
            return
        entry = registry._load_registry().get("organs", {}).get(name, {})
        if entry.get("pid") != process.pid:
            return
        try:
            same_process = process.is_running() and process.create_time() == created
            same_group = cgroup_reader(process.pid) == cgroup_reader(os.getpid())
        except Exception:
            return
        if same_process and same_group:
            registry.stop(name)


def main() -> int:
    if os.name != "posix" or len(sys.argv) != 2:
        raise ReleaseError("linux_selected_organ_required")
    name = sys.argv[1]
    if any(os.environ.get(key) != value for key, value in HOLDS.items()):
        raise ReleaseError("all_cloud_action_holds_required")
    import psutil
    from aureon_fusion import capability_gate as gate, organ_registry as registry
    configure(registry, gate, name, dict(os.environ))
    stopped = threading.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: stopped.set())
    process, created = start_owned(registry, name, psutil.Process)
    print("Owned registry process started under cloud deployment HOLD", flush=True)
    try:
        while not stopped.wait(3):
            if not process.is_running() or process.create_time() != created or process.status() == psutil.STATUS_ZOMBIE:
                return 1
    finally:
        stop_owned(registry, name, process, created)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ReleaseError as error:
        print(str(error), flush=True)
        raise SystemExit(2)
