"""Phase 6 patch for aureon_fusion/organ_registry.py."""
from pathlib import Path
import re

p = Path('C:/Users/user/.kimi_openclaw/workspace/aureon_fusion/organ_registry.py')
text = p.read_text(encoding='utf-8')

# Normalize to LF for easier editing; preserve original line endings by writing back as CRLF
# (the file is mostly CRLF).
orig_crlf = '\r\n' in text
lines = text.splitlines()
text_lf = '\n'.join(lines) + '\n'

# 1. Add OBSERVED_IDENTITY_FILE constant after REGISTRY_FILE definition.
old = 'REGISTRY_FILE = FUSION_STATE / "organ_registry.json"\n\n# Capital release pin.'
new = ('REGISTRY_FILE = FUSION_STATE / "organ_registry.json"\n'
       'OBSERVED_IDENTITY_FILE = FUSION_STATE / "observed_process_identity.json"\n\n'
       '# Capital release pin.')
assert old in text_lf, "REGISTRY_FILE anchor not found"
text_lf = text_lf.replace(old, new, 1)

# 2. Add _process_creation_time helper after _excluded_pids().
old = '''def _excluded_pids() -> set:
    """This process and its ancestors — a registry CLI must never match,
    adopt, or prune itself."""
    excluded = {os.getpid()}
    try:
        import psutil
        parent = psutil.Process(os.getpid()).ppid()
        while parent:
            excluded.add(parent)
            parent = psutil.Process(parent).ppid()
    except Exception:
        pass
    return excluded
'''
new = '''def _excluded_pids() -> set:
    """This process and its ancestors — a registry CLI must never match,
    adopt, or prune itself."""
    excluded = {os.getpid()}
    try:
        import psutil
        parent = psutil.Process(os.getpid()).ppid()
        while parent:
            excluded.add(parent)
            parent = psutil.Process(parent).ppid()
    except Exception:
        pass
    return excluded


def _process_creation_time(pid) -> float | None:
    """Native process creation time (epoch) for a PID, or None if unavailable.

    A recorded creation time lets downstream observers verify that a live PID
    still belongs to the process the registry launched, not a recycled PID.
    """
    if not pid:
        return None
    try:
        import psutil
        return float(psutil.Process(pid).create_time())
    except Exception:
        return None
'''
assert old in text_lf, "_excluded_pids anchor not found"
text_lf = text_lf.replace(old, new, 1)

# 3. Modify _load_registry to capture process_created_at for adopted PIDs.
old = '''            if not entry.get("pid") and not dormant:
                found = _find_running_pid(spec)
                if found:
                    entry["pid"] = found
                    entry["adopted_external_at"] = int(time.time())
                    changed = True
'''
new = '''            if not entry.get("pid") and not dormant:
                found = _find_running_pid(spec)
                if found:
                    entry["pid"] = found
                    entry["adopted_external_at"] = int(time.time())
                    entry["process_created_at"] = _process_creation_time(found)
                    changed = True
'''
assert old in text_lf, "adoption anchor not found"
text_lf = text_lf.replace(old, new, 1)

# 4. Modify _start_locked update dict to include process_created_at.
old = '''    update = {
        "pid": proc.pid,
        "started_at": int(time.time()),
        "started_at_iso": datetime.now(timezone.utc).isoformat(),
        "cmd": cmd,
        "mode": spec["mode"],
        "log": spec["log"],
    }
'''
new = '''    update = {
        "pid": proc.pid,
        "started_at": int(time.time()),
        "started_at_iso": datetime.now(timezone.utc).isoformat(),
        "process_created_at": _process_creation_time(proc.pid),
        "cmd": cmd,
        "mode": spec["mode"],
        "log": spec["log"],
    }
'''
assert old in text_lf, "update dict anchor not found"
text_lf = text_lf.replace(old, new, 1)

# 5. Add three absent organs to ORGANS dict after bus_bridge.
old = '''    "bus_bridge": {
        "module": "aureon_fusion.bus_bridge",
        "match": "aureon_fusion.bus_bridge",
        "args": [],
        "cwd": str(WORKSPACE),
        "mode": "continuous (thought-bus unity bridge)",
        "log": str(LOGS / "organ_bus_bridge.log"),
        "env": _workspace_env(),
    },
}
'''
new = '''    "bus_bridge": {
        "module": "aureon_fusion.bus_bridge",
        "match": "aureon_fusion.bus_bridge",
        "args": [],
        "cwd": str(WORKSPACE),
        "mode": "continuous (thought-bus unity bridge)",
        "log": str(LOGS / "organ_bus_bridge.log"),
        "env": _workspace_env(),
    },
    # ── Phase 6: read-only assessment / affect / HNC live producers ───────────
    # These upstream modules publish the runtime snapshots consumed by
    # aureon/saas/observed_runtime.py. They are launched with the four safety
    # holds in force; they read state and emit JSON, never exchange mutation.
    "assessment_snapshot_producer": {
        "module": "aureon.autonomous.aureon_assessment_snapshot_producer",
        "match": "aureon.autonomous.aureon_assessment_snapshot_producer",
        "args": ["--daemon", "--interval", "60", "--quiet"],
        "cwd": str(AUREON_UPSTREAM),
        "mode": "continuous (60s read-only assessment snapshots)",
        "log": str(LOGS / "organ_assessment_snapshot_producer.log"),
        "env": _launch_env({
            "AUREON_DISABLE_REAL_ORDERS": "1",
            "AUREON_DISABLE_EXCHANGE_MUTATIONS": "1",
            "AUREON_ORDER_INTENT_PUBLISH": "0",
            "AUREON_LIVE_TRADING": "0",
            "AUREON_UNIFIED_ORDER_EXECUTOR": "0",
            "PYTHONUTF8": "1",
        }),
    },
    "harmonic_affect_producer": {
        "module": "aureon.autonomous.aureon_harmonic_affect_state",
        "match": "aureon.autonomous.aureon_harmonic_affect_state",
        "args": ["--daemon", "--interval", "60", "--quiet"],
        "cwd": str(AUREON_UPSTREAM),
        "mode": "continuous (60s harmonic affect state)",
        "log": str(LOGS / "organ_harmonic_affect_producer.log"),
        "env": _launch_env({
            "AUREON_DISABLE_REAL_ORDERS": "1",
            "AUREON_DISABLE_EXCHANGE_MUTATIONS": "1",
            "AUREON_ORDER_INTENT_PUBLISH": "0",
            "AUREON_LIVE_TRADING": "0",
            "AUREON_UNIFIED_ORDER_EXECUTOR": "0",
            "PYTHONUTF8": "1",
        }),
    },
    "hnc_live_daemon": {
        "module": "aureon.core.hnc_live_daemon",
        "match": "aureon.core.hnc_live_daemon",
        "args": [],
        "cwd": str(AUREON_UPSTREAM),
        "mode": "continuous (HNC live Λ(t) field)",
        "log": str(LOGS / "organ_hnc_live_daemon.log"),
        "env": _launch_env({
            "AUREON_DISABLE_REAL_ORDERS": "1",
            "AUREON_DISABLE_EXCHANGE_MUTATIONS": "1",
            "AUREON_ORDER_INTENT_PUBLISH": "0",
            "AUREON_LIVE_TRADING": "0",
            "AUREON_UNIFIED_ORDER_EXECUTOR": "0",
            "PYTHONUTF8": "1",
        }),
    },
}
'''
assert old in text_lf, "bus_bridge close anchor not found"
text_lf = text_lf.replace(old, new, 1)

# 6. Add write_observed_process_identity function before status_data().
old = 'def status_data() -> dict:\n    """Liveness snapshot for every supervised organ."""'
new = '''def _cwd_matches(spec: dict, process) -> bool:
    """True when the process cwd matches the organ's configured cwd."""
    expected = spec.get("cwd")
    if not expected:
        return True
    try:
        actual = process.cwd()
    except Exception:
        return False
    return Path(actual).resolve() == Path(expected).resolve()


def write_observed_process_identity() -> dict:
    """Verify every registered PID and write an identity receipt.

    The receipt follows the schema expected by
    aureon.saas.observed_runtime.py (_project kind="process_identity"):
    {schema: "aureon.process_identity.v1", generated_at, organs: {name: {
        pid, process_created_at, process_name, spec_match, cwd_match,
        verified_at}}}.

    This is cheap enough to run inside the unity_supervisor cycle; it only
    probes PIDs already recorded in the registry.
    """
    reg = _load_registry()
    now = time.time()
    rows = {}
    try:
        import psutil
        native = psutil.Process
    except Exception:
        native = None
    for name, spec in ORGANS.items():
        entry = reg["organs"].get(name, {})
        pid = entry.get("pid")
        if not pid:
            continue
        row = {"pid": pid}
        if native is None:
            row["reason"] = "native_process_reader_missing"
        else:
            try:
                proc = native(pid)
                if not proc.is_running():
                    continue
                cmdline = " ".join(proc.cmdline() or [])
                row.update({
                    "process_created_at": float(proc.create_time()),
                    "process_name": str(proc.name()).lower(),
                    "spec_match": _cmdline_matches(cmdline, spec),
                    "cwd_match": _cwd_matches(spec, proc),
                    "verified_at": now,
                })
            except Exception:
                continue
        rows[name] = row
    payload = {
        "schema": "aureon.process_identity.v1",
        "generated_at": now,
        "organs": rows,
    }
    FUSION_STATE.mkdir(parents=True, exist_ok=True)
    tmp = OBSERVED_IDENTITY_FILE.with_name(
        f"{OBSERVED_IDENTITY_FILE.name}.tmp.{os.getpid()}.{time.time_ns()}")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        _replace_with_retry(tmp, OBSERVED_IDENTITY_FILE)
    except OSError:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise
    return payload


def status_data() -> dict:
    """Liveness snapshot for every supervised organ."""
'''
assert old in text_lf, "status_data anchor not found"
text_lf = text_lf.replace(old, new, 1)

# 7. Ensure _replace_with_retry is defined before write_observed_process_identity.
# It is already defined earlier in the file (line ~924), so we're good.

# Write back as CRLF to match original.
if orig_crlf:
    out = text_lf.replace('\n', '\r\n')
else:
    out = text_lf
p.write_bytes(out.encode('utf-8'))
print("organ_registry.py patched")
