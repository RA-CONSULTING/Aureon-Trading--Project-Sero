"""Phase 6 patch for aureon/saas/status.py."""
import re
from pathlib import Path

p = Path('C:/Users/user/.kimi_openclaw/workspace/aureon-os-upstream/aureon/saas/status.py')
text = p.read_text(encoding='utf-8')
# Preserve line endings by splitting and re-joining with the dominant terminator.
lines = text.splitlines()
# Detect original line ending from first newline in bytes.
bdata = p.read_bytes()
if b'\r\n' in bdata:
    terminator = '\r\n'
else:
    terminator = '\n'
text_lf = '\n'.join(lines) + '\n'

# 1. Add imports: json, Path, OPERATIONAL_CORE_SNAPSHOT_FILE.
old = "from aureon.saas.observed_runtime import observation, runtime_source_observations, process_observation\n\nlogger = logging.getLogger(\"aureon.saas.status\")\n"
new = ("from aureon.saas.observed_runtime import observation, runtime_source_observations, process_observation\n"
       "from pathlib import Path\n"
       "from aureon.core.aureon_operational_core import OPERATIONAL_CORE_SNAPSHOT_FILE\n\n"
       "logger = logging.getLogger(\"aureon.saas.status\")\n")
assert old in text_lf, "import anchor not found"
text_lf = text_lf.replace(old, new, 1)

# 2. Replace _operational_health to consume snapshot first, fallback to in-process core.
old = '''def _operational_health() -> Dict[str, Any]:
    try:
        module = sys.modules.get("aureon.core.aureon_operational_core")
        core = getattr(module, "_ops_core", None)
        if core is None:
            return {"available": False, "status": "unknown", "truth_status": "no_data",
                    "reason": "operational_core_not_observed_in_gateway_process"}
        health = core.get_health()
        if isinstance(health, dict):
            freshness = health.get("state_freshness") or {}
            meta = observation("gateway_operational_core", freshness.get("last_write"), now=time.time())
            fresh = meta["fresh"] and freshness.get("is_stale") is False
            return {**health, "available": fresh, "source_observation": meta,
                    "status": health.get("status", "unknown") if fresh else "unknown",
                    "truth_status": "real_derived" if fresh else "no_data"}
        return {"available": False, "status": "unknown", "reason": "operational_health_object_missing"}
    except Exception as exc:  # noqa: BLE001 — health probe must never crash the endpoint
        return {"available": False, "error": str(exc)}
'''
new = '''def _read_operational_core_snapshot() -> Dict[str, Any] | None:
    """Read a published operational-core health snapshot if one exists."""
    try:
        path = OPERATIONAL_CORE_SNAPSHOT_FILE
        if not path.exists():
            return None
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _operational_health() -> Dict[str, Any]:
    """Report operational-core health from a published snapshot when available.

    The gateway no longer needs _ops_core to exist in its own process; a
    separate trading/operational process can publish its health to disk.
    """
    try:
        now = time.time()
        # Prefer the published cross-process snapshot.
        snapshot = _read_operational_core_snapshot()
        if snapshot is not None:
            freshness = snapshot.get("state_freshness") or {}
            # The snapshot itself carries a source timestamp; use published_at as
            # a receipt clock and the state's last_write as the producer clock.
            meta = observation("operational_core_snapshot", freshness.get("last_write"),
                               now=now, source_path=str(OPERATIONAL_CORE_SNAPSHOT_FILE),
                               clock_kind="producer_timestamp")
            # A stale snapshot is honest "no_data", not a crash.
            fresh = meta["fresh"] and freshness.get("is_stale") is False
            status = snapshot.get("status", "unknown") if fresh else "unknown"
            return {
                **snapshot,
                "available": fresh,
                "source_observation": meta,
                "status": status,
                "truth_status": "real_derived" if fresh else "no_data",
                "source": "published_snapshot",
            }

        # Fallback: operational core lives in this process.
        module = sys.modules.get("aureon.core.aureon_operational_core")
        core = getattr(module, "_ops_core", None)
        if core is None:
            return {"available": False, "status": "unknown", "truth_status": "no_data",
                    "reason": "operational_core_not_observed_in_gateway_process",
                    "source": "in_process_probe"}
        health = core.get_health()
        if isinstance(health, dict):
            freshness = health.get("state_freshness") or {}
            meta = observation("gateway_operational_core", freshness.get("last_write"), now=now)
            fresh = meta["fresh"] and freshness.get("is_stale") is False
            return {**health, "available": fresh, "source_observation": meta,
                    "status": health.get("status", "unknown") if fresh else "unknown",
                    "truth_status": "real_derived" if fresh else "no_data",
                    "source": "in_process_probe"}
        return {"available": False, "status": "unknown", "reason": "operational_health_object_missing"}
    except Exception as exc:  # noqa: BLE001 — health probe must never crash the endpoint
        return {"available": False, "error": str(exc)}
'''
assert old in text_lf, "_operational_health anchor not found"
text_lf = text_lf.replace(old, new, 1)

# Write back preserving line endings.
out = text_lf.replace('\n', terminator)
p.write_bytes(out.encode('utf-8'))
print("status.py patched")
