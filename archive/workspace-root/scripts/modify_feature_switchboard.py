"""Phase 6 patch for aureon/operator/feature_switchboard.py."""
from pathlib import Path

p = Path('C:/Users/user/.kimi_openclaw/workspace/aureon-os-upstream/aureon/operator/feature_switchboard.py')
text = p.read_text(encoding='utf-8')
lines = text.splitlines()
text_lf = '\n'.join(lines) + '\n'

# 1. Add a helper to detect when the runtime environment explicitly holds a hard
# boundary OFF. This makes the switchboard reflect the terminal safety holds.
old = '''def is_hard_boundary(flag_id: str) -> bool:
    f = _BY_ID.get(flag_id)
    return bool(f and f.kind == "hard_boundary")
'''
new = '''def is_hard_boundary(flag_id: str) -> bool:
    f = _BY_ID.get(flag_id)
    return bool(f and f.kind == "hard_boundary")


def _env_holds_off(flag: FeatureFlag) -> bool:
    """True when the runtime environment explicitly disables a hard boundary.

    Hard boundaries are armed only by a human decision. If the process env has
    the flag present and falsy (e.g. AUREON_LIVE_TRADING=0), the runtime is
    holding that boundary OFF regardless of any stored intent. Safe flags keep
    their normal precedence so launcher/.env defaults do not silently override
    a human decision.
    """
    if flag.kind != "hard_boundary":
        return False
    value = os.environ.get(flag.env_var)
    return value is not None and not _env_truthy(value)
'''
assert old in text_lf, "is_hard_boundary anchor not found"
text_lf = text_lf.replace(old, new, 1)

# 2. Modify flag_view so env holds win for hard boundaries, and store is updated.
old = '''def flag_view(flag: FeatureFlag) -> Dict[str, Any]:
    """Honest per-flag view: effective value, where it came from, and its tier."""
    stored = load().get(flag.id)
    env_present = flag.env_var in os.environ
    if stored is not None:
        enabled = bool(stored.get("enabled"))
        source = "store"
    elif env_present:
        enabled = _env_truthy(os.environ.get(flag.env_var))
        source = "env"
    else:
        enabled = flag.default
        source = "default"
    decided_at = stored.get("decided_at") if isinstance(stored, dict) else None
    if not isinstance(decided_at, (int, float)):
        decided_at = None
    return {
        **flag.to_public_dict(),
        "enabled": enabled,
        "stored": (bool(stored.get("enabled")) if stored is not None else None),
        "source": source,
        "armed": bool(flag.kind == "hard_boundary" and enabled),
        "decided_at": decided_at,
        "pending_restart": _pending_restart(flag, source, decided_at),
    }
'''
new = '''def flag_view(flag: FeatureFlag) -> Dict[str, Any]:
    """Honest per-flag view: effective value, where it came from, and its tier.

    For hard boundaries, a runtime env hold (e.g. AUREON_LIVE_TRADING=0) takes
    precedence over the encrypted store so the UI never shows armed while the
    process is held safe. The stored value is reconciled to match so the
    encrypted store itself reflects the effective runtime posture.
    """
    stored = load().get(flag.id)
    env_present = flag.env_var in os.environ
    env_value = os.environ.get(flag.env_var)
    env_enabled = _env_truthy(env_value) if env_present else None

    # Reconcile the encrypted store to runtime reality for hard boundaries.
    if flag.kind == "hard_boundary" and stored is not None and _env_holds_off(flag):
        if bool(stored.get("enabled")) is True:
            data = load()
            data[flag.id] = {"enabled": False, "decided_at": time.time(),
                             "reconciled_by_env_hold": True}
            _persist(data)
            stored = data[flag.id]

    if stored is not None and not (flag.kind == "hard_boundary" and _env_holds_off(flag)):
        enabled = bool(stored.get("enabled"))
        source = "store"
    elif env_present:
        enabled = env_enabled
        source = "env"
    else:
        enabled = flag.default
        source = "default"

    decided_at = stored.get("decided_at") if isinstance(stored, dict) else None
    if not isinstance(decided_at, (int, float)):
        decided_at = None
    return {
        **flag.to_public_dict(),
        "enabled": enabled,
        "stored": (bool(stored.get("enabled")) if stored is not None else None),
        "source": source,
        "armed": bool(flag.kind == "hard_boundary" and enabled),
        "decided_at": decided_at,
        "pending_restart": _pending_restart(flag, source, decided_at),
        "env_hold": _env_holds_off(flag),
    }
'''
assert old in text_lf, "flag_view anchor not found"
text_lf = text_lf.replace(old, new, 1)

# Write back as CRLF.
out = text_lf.replace('\n', '\r\n')
p.write_bytes(out.encode('utf-8'))
print("feature_switchboard.py patched")
