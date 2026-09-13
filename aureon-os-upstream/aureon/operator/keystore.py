"""
Aureon Operator — encrypted provider keystore.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Instance-owned API keys for the LLM switchboard, entered in the Providers UI and
kept **encrypted at rest** (Fernet) under ``$AUREON_KEYSTORE_DIR`` when set, or
``~/.aureon`` for local compatibility. The directory is mode 0700 and the key
and ciphertext files are mode 0600. Never committed.

The keystore is the *control plane*: ``apply_to_env()`` injects stored values
into ``os.environ`` under each provider's env vars (from ``provider_catalog``),
so the existing env-driven adapters pick them up on the next switchboard build.
A disabled provider has its key env removed so its line drops out.

Everything read back out is **masked** (last 4 only). No full key is ever
returned or logged.

**Per-tenant isolation.** Every function takes an optional ``tenant``. With
``tenant=None`` (the single-operator default) the global store is used, exactly
as before. With a tenant (a Supabase JWT ``sub``, set on ``g.tenant`` by the
operator gate) the keys live in an isolated per-tenant file
``~/.aureon/tenants/<tenant>/provider_keys.json.enc`` — one tenant can never read
another's keys. Critically, ``apply_to_env()`` is **global-only and never takes a
tenant**: injecting a tenant's key into the process ``os.environ`` would leak it
into every other request, so a tenant write must never call it.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import threading
from pathlib import Path
from typing import Any, Dict

from aureon.ollama_config import OLLAMA_API_KEY_ENVS
from aureon.operator.provider_catalog import get_provider, managed_env_vars

logger = logging.getLogger("aureon.operator.keystore")

KEYSTORE_DIR_ENV = "AUREON_KEYSTORE_DIR"
PINNED_ENV_VARS_ENV = "AUREON_PINNED_PROVIDER_ENV_VARS"

# This closed set mirrors deployment/google-cloud/cloud_credential_boundary.py.
# The cloud operator has no exchange bundle, so aliases absent from the public
# connection catalog must still be protected from a stale encrypted store.
CLOUD_EXCHANGE_CREDENTIAL_ENV_VARS = frozenset({
    "ALPACA_API_KEY",
    "ALPACA_API_KEY_ID",
    "ALPACA_API_SECRET",
    "ALPACA_API_SECRET_KEY",
    "ALPACA_KEY",
    "ALPACA_SECRET",
    "ALPACA_SECRET_KEY",
    "APCA_API_KEY_ID",
    "APCA_API_SECRET_KEY",
    "BINANCE_API_KEY",
    "BINANCE_API_SECRET",
    "BINANCE_KEY",
    "BINANCE_SECRET",
    "BINANCE_SECRET_KEY",
    "BINANCE_TESTNET_API_KEY",
    "BINANCE_TESTNET_API_SECRET",
    "CAPITAL_API_KEY",
    "CAPITAL_API_PASSWORD",
    "CAPITAL_API_SECRET",
    "CAPITAL_EMAIL",
    "CAPITAL_IDENTIFIER",
    "CAPITAL_PASSWORD",
    "CAPITAL_USER",
    "KRAKEN_API_KEY",
    "KRAKEN_API_SECRET",
    "KRAKEN_PRIVATE_KEY",
    "KRAKEN_SECRET",
})


def _configured_root() -> Path:
    configured = str(os.environ.get(KEYSTORE_DIR_ENV, "") or "").strip()
    if not configured:
        return Path.home() / ".aureon"
    path = Path(configured).expanduser()
    if not path.is_absolute():
        raise RuntimeError("AUREON_KEYSTORE_DIR_MUST_BE_ABSOLUTE")
    return path


CONFIG_DIR = _configured_root()
KEY_PATH = CONFIG_DIR / "provider_keys.key"
STORE_PATH = CONFIG_DIR / "provider_keys.json.enc"
TENANTS_DIR = CONFIG_DIR / "tenants"

_FIELDS = ("api_key", "base_url", "model", "enabled",
           "last_test_at", "last_test_ok", "last_test_latency_ms", "last_test_error")
_SAFE_TENANT = re.compile(r"[A-Za-z0-9_-]{1,128}")


def _provider_key_envs(info: Any) -> tuple[str, ...]:
    if str(getattr(info, "id", "") or "") == "ollama":
        return OLLAMA_API_KEY_ENVS
    return (info.key_env,) if getattr(info, "key_env", "") else ()


def _safe_tenant(tenant: str) -> str:
    """A filesystem-safe, collision-free directory name for a tenant id.

    The tenant id is a JWT ``sub`` (normally a UUID). Even though the token is signed, defend against
    path traversal: accept a strict whitelist verbatim, otherwise fall back to a SHA-256 hash — so a
    crafted ``sub`` can never escape ``TENANTS_DIR``.

    The two forms are kept in **disjoint namespaces** by prefix. Without that, they share one
    directory space and collide: a SHA-256 hex digest itself matches the whitelist, so a tenant whose
    ``sub`` is literally the digest of another tenant's crafted ``sub`` would be handed that tenant's
    store — reading their keys and taking over their rotations. ``v_`` (verbatim) and ``h_`` (hashed)
    can never produce the same name, because a verbatim id is always re-prefixed.
    """
    if _SAFE_TENANT.fullmatch(tenant):
        return f"v_{tenant}"
    return f"h_{hashlib.sha256(tenant.encode('utf-8')).hexdigest()}"


def _store_path(tenant: str | None) -> Path:
    """Where a store lives: the global file for ``None``, an isolated per-tenant file otherwise."""
    # ``None`` is the only spelling of the instance plane.  Treat even an empty
    # or otherwise unusual tenant subject as an account namespace.  Identity
    # verification already refuses an empty Supabase subject, but keeping this
    # boundary exact prevents a future caller from turning ``tenant=""`` into a
    # read or write of the owner's global store.
    if tenant is None:
        return STORE_PATH
    return TENANTS_DIR / _safe_tenant(tenant) / "provider_keys.json.enc"


def model_env(registry_name: str) -> str:
    """Uniform per-provider model-override env var (applied in default_registry)."""
    return f"AUREON_MODEL_{registry_name.upper()}"


def _ensure_private_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        path.chmod(0o700)
    except OSError:  # pragma: no cover - best effort on non-POSIX filesystems
        pass


def _protected_env_vars() -> set[str]:
    """Environment names pinned by an external secret authority.

    The cloud bootstrap writes this marker only after validating a pinned
    Secret Manager version. A stale global keystore may remain on disk, but it
    can neither replace nor delete those process values.
    """
    protected = {
        value.strip()
        for value in str(os.environ.get(PINNED_ENV_VARS_ENV, "") or "").split(",")
        if re.fullmatch(r"[A-Z][A-Z0-9_]{0,127}", value.strip())
    }
    if "OLLAMA_API_KEY" in protected:
        protected.update(OLLAMA_API_KEY_ENVS)
    if "AUREON_LLM_MODEL" in protected:
        protected.update({"AUREON_LLM_MODEL", "AUREON_OLLAMA_MODEL", model_env("local")})
    if os.environ.get("AUREON_CLOUD_EXCHANGE_CREDENTIALS_PINNED") == "1":
        # The cloud operator deliberately has no owner exchange values.  Mark
        # every exchange field as externally owned so a stale global keystore
        # cannot re-inject those values after the boot environment was scrubbed.
        protected.update(CLOUD_EXCHANGE_CREDENTIAL_ENV_VARS)
    return protected


def protected_provider_fields(provider_id: str) -> tuple[str, ...]:
    """Return this provider's env fields pinned by external secret authority.

    The result contains names only, never values.  It is used by the HTTP
    control plane to make cloud-managed rows read-only instead of accepting a
    shadow keystore value that cannot become effective.
    """
    info = get_provider(provider_id)
    if info is not None:
        candidates = {
            *_provider_key_envs(info),
            info.base_url_env,
            model_env(info.registry_name),
        }
        if str(getattr(info, "id", "") or "") == "ollama":
            candidates.update({"AUREON_LLM_MODEL", "AUREON_OLLAMA_MODEL"})
    else:
        from aureon.operator.connections_catalog import get_connection

        conn = get_connection(provider_id)
        candidates = set(conn.credential_env) if conn is not None else set()
    return tuple(sorted((candidates - {""}) & _protected_env_vars()))


def _fernet():
    from cryptography.fernet import Fernet

    _ensure_private_directory(CONFIG_DIR)
    if not KEY_PATH.exists():
        KEY_PATH.write_bytes(Fernet.generate_key())
        try:
            KEY_PATH.chmod(0o600)
        except OSError:  # pragma: no cover - best effort on odd filesystems
            pass
    return Fernet(KEY_PATH.read_bytes())


def load(tenant: str | None = None) -> Dict[str, Dict[str, Any]]:
    """Decrypt and return a keystore, or ``{}`` if missing/unreadable.

    ``tenant=None`` reads the global store; a tenant reads only that tenant's isolated file.
    """
    path = _store_path(tenant)
    if not path.exists():
        return {}
    try:
        raw = _fernet().decrypt(path.read_bytes())
        data = json.loads(raw.decode("utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception as exc:  # noqa: BLE001 — a corrupt store must not sink the operator
        logger.warning("provider keystore unreadable: %s", type(exc).__name__)
        return {}


#: Serializes every read-modify-write of a keystore. ``save_provider`` / ``delete_provider`` each
#: ``load()`` the whole store, mutate one entry, and write it all back — so two concurrent writes race
#: and the loser's change is silently discarded. Reproduced: 24 concurrent ``save_provider`` calls for
#: one tenant left exactly ONE provider stored. A user connecting two models at once would lose one.
#: Re-entrant because ``delete_provider`` calls ``load`` and ``_persist`` while already holding it.
_WRITE_LOCK = threading.RLock()


def _persist(data: Dict[str, Dict[str, Any]], tenant: str | None = None) -> None:
    """Encrypt and write a store **atomically**.

    A direct ``write_bytes`` truncates before it writes, so an interrupted write leaves a partial file
    — and a partial Fernet token cannot be decrypted. ``load`` swallows that and returns ``{}``, so the
    tenant's keys do not merely vanish: the next ``save_provider`` then persists only its own entry,
    making the loss permanent. Write a sibling temp file and ``os.replace`` it into place instead —
    atomic on POSIX within one filesystem, so a reader sees either the old store or the new one.
    """
    path = _store_path(tenant)
    _ensure_private_directory(CONFIG_DIR)
    if tenant is not None:
        _ensure_private_directory(TENANTS_DIR)
    _ensure_private_directory(path.parent)
    token = _fernet().encrypt(json.dumps(data).encode("utf-8"))
    tmp = path.with_name(f".{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    try:
        tmp.write_bytes(token)
        try:
            tmp.chmod(0o600)   # tighten before it becomes visible under the real name
        except OSError:  # pragma: no cover
            pass
        os.replace(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def _known(provider_id: str) -> bool:
    """A stored id is valid if it's an LLM provider OR a catalog connection."""
    if get_provider(provider_id) is not None:
        return True
    from aureon.operator.connections_catalog import get_connection

    return get_connection(provider_id) is not None


def save_provider(
    provider_id: str,
    *,
    api_key: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
    enabled: bool | None = None,
    extra: Dict[str, str] | None = None,
    last_test_at: str | None = None,
    last_test_ok: bool | None = None,
    last_test_latency_ms: int | None = None,
    last_test_error: str | None = None,
    tenant: str | None = None,
) -> Dict[str, Any]:
    """Merge the given fields into a provider's entry and persist. Only provided
    (non-None) fields change. ``extra`` holds secondary credential envs (e.g. a
    Telegram chat id) as ``{ENV_VAR: value}``. ``tenant`` scopes the write to that
    tenant's isolated store (``None`` ⇒ the global store). Returns the stored entry."""
    if not _known(provider_id):
        raise KeyError(f"unknown provider: {provider_id}")
    # The lock must span load→mutate→persist, not just the write: the whole store is rewritten, so a
    # concurrent save that read the same snapshot would drop this entry (or have its own dropped).
    with _WRITE_LOCK:
        data = load(tenant)
        entry = data.get(provider_id, {"enabled": True})
        if api_key is not None:
            entry["api_key"] = api_key.strip()
        if base_url is not None:
            entry["base_url"] = base_url.strip()
        if model is not None:
            entry["model"] = model.strip()
        if enabled is not None:
            entry["enabled"] = bool(enabled)
        if extra:
            merged = dict(entry.get("extra", {}))
            merged.update({k: str(v).strip() for k, v in extra.items() if v is not None})
            entry["extra"] = merged
        if last_test_at is not None:
            entry["last_test_at"] = last_test_at
        if last_test_ok is not None:
            entry["last_test_ok"] = bool(last_test_ok)
        if last_test_latency_ms is not None:
            entry["last_test_latency_ms"] = int(last_test_latency_ms)
        if last_test_error is not None:
            entry["last_test_error"] = str(last_test_error)
        data[provider_id] = entry
        _persist(data, tenant)
        return entry


def delete_provider(provider_id: str, *, tenant: str | None = None) -> None:
    """Forget a provider's stored config. For the global store also unset its env
    vars; a **tenant delete never touches ``os.environ``** (that is the leak vector)."""
    with _WRITE_LOCK:                      # same read-modify-write hazard as save_provider
        data = load(tenant)
        entry = data.get(provider_id, {})
        if provider_id in data:
            del data[provider_id]
            _persist(data, tenant)
    if tenant is not None:
        # Tenant keys never enter the process env, so there is nothing to unset.
        return
    protected = _protected_env_vars()
    info = get_provider(provider_id)
    if info:  # LLM provider
        for var in (
            *_provider_key_envs(info),
            info.base_url_env,
            model_env(info.registry_name),
            *(
                ("AUREON_LLM_MODEL", "AUREON_OLLAMA_MODEL")
                if str(getattr(info, "id", "") or "") == "ollama"
                else ()
            ),
        ):
            if var and var not in protected:
                os.environ.pop(var, None)
        return
    from aureon.operator.connections_catalog import get_connection

    conn = get_connection(provider_id)
    if conn:  # data-source connection
        for var in conn.credential_env:
            if var not in protected:
                os.environ.pop(var, None)
        for var in (entry.get("extra") or {}):
            if var not in protected:
                os.environ.pop(var, None)


def apply_to_env() -> None:
    """Inject stored config into ``os.environ`` so the switchboard uses it.

    Enabled entries set their key/base-URL/model env vars; disabled entries have
    their key env removed (dropping the line). Providers with no keystore entry
    are left untouched, so keys supplied via a real ``.env`` still work.
    """
    from aureon.operator.connections_catalog import get_connection

    if os.environ.get("AUREON_CLOUD_EXCHANGE_CREDENTIALS_PINNED") == "1":
        # Cloud instance-plane authority belongs only to the isolated executor.
        # Scrub inherited aliases here as well as refusing every later store
        # write, so this defense still closes if the caller bypassed the VM
        # site's earlier process guard.
        for name in CLOUD_EXCHANGE_CREDENTIAL_ENV_VARS:
            os.environ.pop(name, None)
    data = load()
    protected = _protected_env_vars()
    for provider_id, entry in data.items():
        enabled = bool(entry.get("enabled", True))
        key = str(entry.get("api_key", "") or "")
        info = get_provider(provider_id)
        if info is not None:
            # ── LLM provider (base_url + model semantics) ──
            base_url = str(entry.get("base_url", "") or "")
            model = str(entry.get("model", "") or "")
            if enabled:
                if key:
                    for key_env in _provider_key_envs(info):
                        if key_env not in protected:
                            os.environ[key_env] = key
                if base_url and info.base_url_env and info.base_url_env not in protected:
                    os.environ[info.base_url_env] = base_url
                if model:
                    if model_env(info.registry_name) not in protected:
                        os.environ[model_env(info.registry_name)] = model
                    if str(getattr(info, "id", "") or "") == "ollama":
                        if "AUREON_LLM_MODEL" not in protected:
                            os.environ["AUREON_LLM_MODEL"] = model
                        if "AUREON_OLLAMA_MODEL" not in protected:
                            os.environ["AUREON_OLLAMA_MODEL"] = model
            else:
                for key_env in _provider_key_envs(info):
                    if key_env not in protected:
                        os.environ.pop(key_env, None)
                if str(getattr(info, "id", "") or "") == "ollama":
                    if "AUREON_LLM_MODEL" not in protected:
                        os.environ.pop("AUREON_LLM_MODEL", None)
                    if "AUREON_OLLAMA_MODEL" not in protected:
                        os.environ.pop("AUREON_OLLAMA_MODEL", None)
                if (info.key_optional and info.base_url_env
                        and info.base_url_env not in protected):
                    os.environ.pop(info.base_url_env, None)
            continue
        conn = get_connection(provider_id)
        if conn is None:
            continue
        # ── data-source connection (primary key + extra envs) ──
        extra = entry.get("extra") or {}
        if enabled:
            if key and conn.key_env and conn.key_env not in protected:
                os.environ[conn.key_env] = key
            for var, val in extra.items():
                if val and var not in protected:
                    os.environ[var] = str(val)
        else:
            for var in conn.credential_env:
                if var not in protected:
                    os.environ.pop(var, None)
            for var in extra:
                if var not in protected:
                    os.environ.pop(var, None)


def mask(key: str) -> str:
    """Public last-4 mask for safe display (e.g. ••••1234)."""
    key = str(key or "")
    if not key:
        return ""
    return ("•" * 4) + key[-4:] if len(key) > 4 else "•" * len(key)


# Back-compat internal alias.
_mask = mask


def masked_view(tenant: str | None = None) -> Dict[str, Dict[str, Any]]:
    """Safe view of a keystore for the UI — never the full key. ``tenant`` scopes
    it to that tenant's isolated store (``None`` ⇒ global)."""
    data = load(tenant)
    view: Dict[str, Dict[str, Any]] = {}
    for provider_id, entry in data.items():
        key = str(entry.get("api_key", "") or "")
        view[provider_id] = {
            "has_key": bool(key),
            "key_masked": _mask(key),
            "base_url": str(entry.get("base_url", "") or ""),
            "model": str(entry.get("model", "") or ""),
            "enabled": bool(entry.get("enabled", True)),
            "last_test_at": entry.get("last_test_at"),
            "last_test_ok": entry.get("last_test_ok"),
            "last_test_latency_ms": entry.get("last_test_latency_ms"),
            "last_test_error": entry.get("last_test_error"),
        }
    return view


__all__ = [
    "load",
    "save_provider",
    "delete_provider",
    "apply_to_env",
    "masked_view",
    "mask",
    "model_env",
    "managed_env_vars",
    "KEYSTORE_DIR_ENV",
    "PINNED_ENV_VARS_ENV",
    "CLOUD_EXCHANGE_CREDENTIAL_ENV_VARS",
    "protected_provider_fields",
    "CONFIG_DIR",
    "STORE_PATH",
    "KEY_PATH",
]
