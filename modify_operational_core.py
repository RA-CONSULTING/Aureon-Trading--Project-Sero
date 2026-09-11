"""Phase 6 patch for aureon/core/aureon_operational_core.py."""
from pathlib import Path

p = Path('C:/Users/user/.kimi_openclaw/workspace/aureon-os-upstream/aureon/core/aureon_operational_core.py')
text = p.read_text(encoding='utf-8')
lines = text.splitlines()
text_lf = '\n'.join(lines) + '\n'

# 1. Add REPO_ROOT and snapshot path constants near the top, after imports.
old = "REPO_ROOT = Path(__file__).resolve().parents[2]\n"
if old not in text_lf:
    # Maybe it's not there; add after Path import block.
    old = "from pathlib import Path\n"
    new = "from pathlib import Path\n\nREPO_ROOT = Path(__file__).resolve().parents[2]\n"
    assert old in text_lf, "pathlib import anchor not found"
    text_lf = text_lf.replace(old, new, 1)
else:
    # REPO_ROOT already exists? Let's verify.
    pass

# Ensure REPO_ROOT exists.
if "REPO_ROOT = Path(__file__).resolve().parents[2]" not in text_lf:
    old = "from pathlib import Path\n"
    new = "from pathlib import Path\n\nREPO_ROOT = Path(__file__).resolve().parents[2]\n"
    assert old in text_lf, "pathlib import anchor not found"
    text_lf = text_lf.replace(old, new, 1)

# Add OPERATIONAL_CORE_SNAPSHOT_FILE after REPO_ROOT.
old = "REPO_ROOT = Path(__file__).resolve().parents[2]\n"
new = "REPO_ROOT = Path(__file__).resolve().parents[2]\nOPERATIONAL_CORE_SNAPSHOT_FILE = REPO_ROOT / \"state\" / \"operational_core_snapshot.json\"\n"
assert old in text_lf, "REPO_ROOT anchor not found"
text_lf = text_lf.replace(old, new, 1)

# 2. Add a publish function before get_operational_core.
old = '''def get_operational_core(phase_detector=None, solar_monitor=None) -> AureonOperationalCore:
    """Get or create the operational core singleton."""
    global _ops_core
    if _ops_core is None:
        _ops_core = AureonOperationalCore(
            phase_detector=phase_detector,
            solar_monitor=solar_monitor,
        )
    return _ops_core
'''
new = '''def publish_operational_core_snapshot(core: AureonOperationalCore = None,
                                              path: Path = None) -> dict:
    """Lightweight publisher: write the core's health snapshot to disk.

    The gateway process reads this file in aureon.saas.status so it can report
    operational health without needing _ops_core to exist in its own process.
    The snapshot carries the same fields as get_health() plus published_at.
    """
    if core is None:
        core = _ops_core
    if core is None:
        return {"available": False, "reason": "operational_core_not_initialized"}
    snapshot = core.get_health()
    snapshot["published_at"] = time.time()
    snapshot["schema_version"] = "aureon-operational-core-snapshot-v1"
    snapshot["available"] = True
    target = path or OPERATIONAL_CORE_SNAPSHOT_FILE
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(f"{target.name}.tmp.{os.getpid()}.{time.time_ns()}")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(snapshot, f, indent=2, ensure_ascii=False, default=str)
            f.flush()
            os.fsync(f.fileno())
        os.replace(str(tmp), str(target))
    except OSError:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise
    return snapshot


def get_operational_core(phase_detector=None, solar_monitor=None) -> AureonOperationalCore:
    """Get or create the operational core singleton."""
    global _ops_core
    if _ops_core is None:
        _ops_core = AureonOperationalCore(
            phase_detector=phase_detector,
            solar_monitor=solar_monitor,
        )
    return _ops_core
'''
assert old in text_lf, "get_operational_core anchor not found"
text_lf = text_lf.replace(old, new, 1)

# 3. Make get_health() also publish the snapshot when called with the real singleton.
old = '''        return {
            'status': health,
            'uptime': time.time() - self._initialized_at,
            'issues': issues,
            'signal_gate': self.signal_gate.get_stats(),
            'circuit_breaker': cb_status,
            'state_freshness': state_freshness,
            'execution': self.execution_confirmer.get_stats(),
            'reconciliation': self.reconciler.get_status(),
        }
'''
new = '''        health_payload = {
            'status': health,
            'uptime': time.time() - self._initialized_at,
            'issues': issues,
            'signal_gate': self.signal_gate.get_stats(),
            'circuit_breaker': cb_status,
            'state_freshness': state_freshness,
            'execution': self.execution_confirmer.get_stats(),
            'reconciliation': self.reconciler.get_status(),
        }
        # Publish a cross-process snapshot whenever health is computed in the
        # process that owns the singleton. Failures are logged, never raised.
        if _ops_core is self:
            try:
                publish_operational_core_snapshot(core=self)
            except Exception as exc:  # noqa: BLE001
                logger.warning("operational core snapshot publish failed: %s", exc)
        return health_payload
'''
assert old in text_lf, "get_health return anchor not found"
text_lf = text_lf.replace(old, new, 1)

# Write back as CRLF.
out = text_lf.replace('\n', '\r\n')
p.write_bytes(out.encode('utf-8'))
print("aureon_operational_core.py patched")
