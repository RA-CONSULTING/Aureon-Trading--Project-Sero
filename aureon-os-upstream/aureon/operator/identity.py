"""
Aureon Operator — request identity resolution.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

One place that answers "who is this request?" for the whole HTTP surface, reconciling the two auth
schemes the operator supports:

  * **admin / operator** — a single static instance key (``AUREON_OPERATOR_API_KEY``), checked in
    constant time. This is the control plane; it manages the instance's own defaults and global state.
  * **owner** — a Supabase access token freshly verified by the project's Auth server and matched to
    administrator-controlled app metadata plus an immutable subject/email commitment.
  * **tenant / end user** — any other Supabase access token verified by the project's Auth server
    (current signing keys, including asymmetric keys) or by the legacy HS256 verifier. The verified
    user id becomes the tenant id, and every per-user store is namespaced by it.
  * **open** — neither secret configured: auth is disabled (dev / offline / single-operator default),
    exactly as before this module existed.

``resolve_identity`` is pure (no Flask, no env reads inside): the caller passes the ``Authorization``
header and the two secrets it computed once at app start, and gets back an :class:`Identity`. The
**zero-regression invariant** is structural — when neither tenant verifier is configured the tenant
branch is never reached, so the resolver behaves exactly like the old ``check_bearer`` static-key gate.

The Supabase JWT verifier (``verify_supabase_jwt``) lives here too so both the operator gate and the
SaaS gateway share one stdlib HS256 implementation (no new dependency).

Gary Leckey · Aureon Institute
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import http.client
import json
import re
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, Mapping
from urllib.parse import urlsplit

# ── Supabase JWT (optional, stdlib HS256) ─────────────────────────────────────

def _b64url_decode(seg: str) -> bytes:
    pad = "=" * (-len(seg) % 4)
    return base64.urlsafe_b64decode(seg + pad)


#: Small leeway for clock drift between the token issuer and this host.
_CLOCK_SKEW_S = 60.0

#: Supabase signs its *project API keys* with the same project JWT secret as user tokens. The anon key
#: is a public, client-side value — it must never be mistakable for an end user. They carry no ``sub``
#: today (so the resolver already refuses them), but reject the roles explicitly rather than rely on
#: that staying true.
_API_KEY_ROLES = frozenset({"anon", "service_role"})

_MAX_SUPABASE_USER_RESPONSE = 64 * 1024
_SHA256_HEX = re.compile(r"[0-9a-f]{64}")


def _confirmed_timestamp(value: Any) -> bool:
    """Accept only one bounded, timezone-aware provider confirmation time."""

    if not isinstance(value, str) or not 1 <= len(value) <= 64:
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None


def owner_email_commitment(email: str) -> str:
    """Return the commissioning-safe commitment for one verified owner email."""

    normalized = str(email or "").strip().casefold()
    return hashlib.sha256(
        b"aureon-supabase-owner-email-v1\x00" + normalized.encode("utf-8", errors="strict")
    ).hexdigest()


def owner_identity_commitment(subject: str) -> str:
    """Return the public, non-reversible binding used in owner intent receipts."""

    return hashlib.sha256(
        b"aureon-supabase-owner-identity-v1\x00"
        + str(subject or "").encode("utf-8", errors="strict")
    ).hexdigest()


@dataclass(frozen=True)
class SupabaseOwnerPolicy:
    """Immutable commissioning record for the one Supabase owner identity.

    ``app_metadata`` is controlled by the Auth administrator.  The subject and
    confirmed-email commitment make an accidental or malicious role assignment
    insufficient on its own.  No plaintext email is stored in configuration.
    """

    subject: str
    email_sha256: str
    app_metadata_role: str = "owner"

    def __post_init__(self) -> None:
        try:
            parsed = uuid.UUID(self.subject)
        except (ValueError, TypeError, AttributeError) as exc:
            raise ValueError("supabase_owner_subject_invalid") from exc
        if str(parsed) != self.subject.lower():
            raise ValueError("supabase_owner_subject_invalid")
        if not _SHA256_HEX.fullmatch(self.email_sha256):
            raise ValueError("supabase_owner_email_commitment_invalid")
        if self.app_metadata_role != "owner":
            raise ValueError("supabase_owner_role_invalid")

    @classmethod
    def from_env(cls, environ: Mapping[str, str]) -> SupabaseOwnerPolicy | None:
        subject = str(environ.get("AUREON_SUPABASE_OWNER_SUBJECT") or "").strip().lower()
        email_sha256 = str(
            environ.get("AUREON_SUPABASE_OWNER_EMAIL_SHA256") or ""
        ).strip().lower()
        if not subject and not email_sha256:
            return None
        if not subject or not email_sha256:
            raise ValueError("supabase_owner_identity_config_incomplete")
        return cls(subject=subject, email_sha256=email_sha256)

    def matches(self, claims: Mapping[str, Any]) -> bool:
        metadata = claims.get("app_metadata")
        email = claims.get("email")
        return bool(
            claims.get("auth_source") == "supabase_auth_server"
            and claims.get("email_confirmed") is True
            and isinstance(metadata, Mapping)
            and metadata.get("aureon_role") == self.app_metadata_role
            and claims.get("sub") == self.subject
            and isinstance(email, str)
            and hmac.compare_digest(owner_email_commitment(email), self.email_sha256)
        )


def _fetch_supabase_user(
    host: str,
    path: str,
    headers: Mapping[str, str],
    timeout: float,
) -> tuple[int, bytes]:
    """Fetch the fixed Supabase Auth user endpoint with a bounded response."""

    connection = http.client.HTTPSConnection(host, 443, timeout=timeout)
    try:
        connection.request("GET", path, headers=dict(headers))
        response = connection.getresponse()
        body = response.read(_MAX_SUPABASE_USER_RESPONSE + 1)
        if len(body) > _MAX_SUPABASE_USER_RESPONSE:
            return 0, b""
        return int(response.status), body
    except (OSError, ValueError, http.client.HTTPException):
        return 0, b""
    finally:
        connection.close()


class SupabaseAuthVerifier:
    """Verify a user token through one pinned Supabase project's Auth server.

    Supabase recommends this flow for shared-secret projects and it also works
    when the project rotates to asymmetric JWT signing keys. The project URL and
    publishable key are trusted deployment configuration; nothing in the token
    selects a destination, algorithm, or key.
    """

    def __init__(
        self,
        project_url: str,
        publishable_key: str,
        *,
        fetch: Callable[[str, str, Mapping[str, str], float], tuple[int, bytes]] = _fetch_supabase_user,
        timeout: float = 5.0,
    ) -> None:
        parsed = urlsplit((project_url or "").strip())
        host = parsed.hostname or ""
        if (
            parsed.scheme != "https"
            or parsed.port is not None
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
            or not re.fullmatch(r"[a-z0-9]{20}\.supabase\.co", host)
        ):
            raise ValueError("supabase_project_url_invalid")
        key = (publishable_key or "").strip()
        if not 20 <= len(key) <= 4096 or re.search(r"[^\x21-\x7e]", key):
            raise ValueError("supabase_publishable_key_invalid")
        if not (key.startswith("sb_publishable_") or key.count(".") == 2):
            raise ValueError("supabase_publishable_key_invalid")
        if not 0.2 <= float(timeout) <= 15.0:
            raise ValueError("supabase_auth_timeout_invalid")
        self._host = host
        self._publishable_key = key
        self._fetch = fetch
        self._timeout = float(timeout)

    def __call__(self, token: str) -> Dict[str, Any] | None:
        if (
            not isinstance(token, str)
            or not 20 <= len(token) <= 8192
            or token.count(".") != 2
            or re.search(r"[^A-Za-z0-9._-]", token)
        ):
            return None
        status, raw = self._fetch(
            self._host,
            "/auth/v1/user",
            {
                "Accept": "application/json",
                "apikey": self._publishable_key,
                "Authorization": f"Bearer {token}",
            },
            self._timeout,
        )
        if status != 200 or not raw:
            return None
        try:
            payload = json.loads(raw.decode("utf-8"))
            user_id = payload.get("id") if isinstance(payload, dict) else None
            parsed_id = uuid.UUID(user_id) if isinstance(user_id, str) else None
            if parsed_id is None or str(parsed_id) != user_id.lower():
                return None
            email = payload.get("email")
            raw_app_metadata = payload.get("app_metadata")
            aureon_role = (
                raw_app_metadata.get("aureon_role")
                if isinstance(raw_app_metadata, dict)
                else None
            )
            if not isinstance(aureon_role, str) or not re.fullmatch(
                r"[a-z][a-z0-9_-]{0,31}", aureon_role
            ):
                aureon_role = None
            return {
                "sub": str(parsed_id),
                "role": "authenticated",
                "email": email if isinstance(email, str) else None,
                # Deliberately copy only the administrator-controlled role used
                # by this service. Never return or inspect user_metadata.
                "app_metadata": (
                    {"aureon_role": aureon_role} if aureon_role is not None else {}
                ),
                "email_confirmed": _confirmed_timestamp(
                    payload.get("email_confirmed_at")
                ),
                "auth_source": "supabase_auth_server",
            }
        except (UnicodeError, ValueError, TypeError, json.JSONDecodeError):
            return None


def verify_supabase_jwt(token: str, secret: str) -> Dict[str, Any] | None:
    """Verify an HS256 Supabase JWT with the project secret. Returns claims or None.

    HS256 is **forced**, never read from the token header, so the classic algorithm-confusion attacks
    (``alg: none``, or an RS256 header verified with a public key as an HMAC secret) cannot apply —
    an attacker who cannot produce a valid HS256 signature cannot get past the compare below.

    Claim checks, all deliberate:
      * ``exp`` is **required**. A token without an expiry never expires and cannot be revoked; a
        signed-but-eternal bearer is a worse failure than a rejected login. (Supabase always sets it —
        this refuses to depend on that.)
      * ``nbf``, when present, is honored, so a not-yet-valid token is not accepted early.
      * project API-key roles are refused outright (see :data:`_API_KEY_ROLES`).
    """
    try:
        header_b64, payload_b64, sig_b64 = token.split(".")
        signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
        expected = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
        if not hmac.compare_digest(expected, _b64url_decode(sig_b64)):
            return None
        claims = json.loads(_b64url_decode(payload_b64))
        if not isinstance(claims, dict):
            return None
        now = time.time()
        exp = claims.get("exp")
        if not isinstance(exp, (int, float)) or exp < now:
            return None
        nbf = claims.get("nbf")
        if isinstance(nbf, (int, float)) and nbf > now + _CLOCK_SKEW_S:
            return None
        if claims.get("role") in _API_KEY_ROLES:
            return None
        return claims
    except Exception:  # noqa: BLE001 — any malformed token is simply invalid
        return None


# ── Request identity ──────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Identity:
    """Who a request is. ``tenant`` carries the verified Supabase ``sub`` when present."""

    kind: str            # "admin" | "owner" | "tenant" | "open"
    tenant: str | None    # Verified Supabase sub for owner/tenant identities, else None
    ok: bool             # False ⇒ the gate should 401
    auth_source: str = "none"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "kind": self.kind,
            "tenant": self.tenant,
            "ok": self.ok,
            "auth_source": self.auth_source,
        }


def build_runtime_context(*, is_admin: bool) -> Dict[str, Any]:
    """Return the non-secret runtime scope implied by an authenticated identity.

    Identity establishes which control plane a request may enter.  It does not
    establish that an exchange release is active, so the owner response keeps
    ``order_submission_enabled`` unknown while every tenant account is
    explicitly held.
    """
    if is_admin:
        return {
            "workspace_scope": "owner_instance",
            "credential_scope": "instance",
            "execution_state": "governed",
            "owner_runtime_read": True,
            "owner_runtime_control": True,
            "owner_runtime_session_effect": "not_applicable",
            "order_submission_enabled": None,
        }
    return {
        "workspace_scope": "tenant_account",
        "credential_scope": "account",
        "execution_state": "held",
        "owner_runtime_read": False,
        "owner_runtime_control": False,
        "owner_runtime_session_effect": "none",
        "order_submission_enabled": False,
    }


def _bearer_token(auth_header: str | None) -> str | None:
    if not auth_header or not auth_header.startswith("Bearer "):
        return None
    tok = auth_header[len("Bearer "):].strip()
    return tok or None


def resolve_identity(
    auth_header: str | None,
    *,
    operator_key: str,
    jwt_secret: str,
    tenant_verifier: Callable[[str], Mapping[str, Any] | None] | None = None,
    owner_policy: SupabaseOwnerPolicy | None = None,
) -> Identity:
    """Resolve a request to an :class:`Identity`. Pure — pass the secrets, get the answer.

    Order (must not regress the old static-key gate):
      1. no auth mechanism configured  → open (auth disabled; unchanged single-operator behavior).
      2. static key matches            → admin (the instance control plane).
      3. verified Supabase user matching the immutable owner policy → owner(``sub``).
      4. else a verified Supabase user → tenant(``sub``).
      5. else                          → not ok (the gate returns 401).
    """
    # A key that is only whitespace is not a key — treat it as unset, or a stray space in the env
    # would flip an open instance into permanently-locked-out (nothing could ever match it).
    operator_key = (operator_key or "").strip()
    jwt_secret = jwt_secret or ""

    # 1 — nothing configured: auth disabled, exactly as before.
    if not operator_key and not jwt_secret and tenant_verifier is None:
        return Identity(kind="open", tenant=None, ok=True, auth_source="open")

    token = _bearer_token(auth_header)
    if not token:
        return Identity(kind="open", tenant=None, ok=False)

    # 2 — the static instance key: the admin / operator plane. compare_digest raises TypeError on
    # non-ASCII str input, so compare bytes — a unicode Authorization header must be a clean 401,
    # never an unhandled 500.
    if operator_key and hmac.compare_digest(token.encode("utf-8"), operator_key.encode("utf-8")):
        return Identity(kind="admin", tenant=None, ok=True, auth_source="operator_bearer")

    # 3 — a Supabase user bearer: owner or tenant plane. Unreachable when both verifiers are absent.
    if tenant_verifier is not None or jwt_secret:
        try:
            claims = (
                tenant_verifier(token)
                if tenant_verifier is not None
                else verify_supabase_jwt(token, jwt_secret)
            )
        except Exception:  # noqa: BLE001 — identity-provider failure is a clean denial
            claims = None
        sub = claims.get("sub") if isinstance(claims, Mapping) else None
        if isinstance(sub, str) and sub:
            # Owner elevation is available only after a fresh Auth-server
            # verification. Legacy locally verified HS256 claims, including a
            # forged/user-controlled role field, always remain tenant scoped.
            if (
                tenant_verifier is not None
                and owner_policy is not None
                and owner_policy.matches(claims)
            ):
                return Identity(
                    kind="owner",
                    tenant=sub,
                    ok=True,
                    auth_source="supabase_auth_server",
                )
            return Identity(
                kind="tenant",
                tenant=sub,
                ok=True,
                auth_source=(
                    "supabase_auth_server" if tenant_verifier is not None else "legacy_hs256"
                ),
            )

    # 4 — a token was presented but matched nothing valid.
    return Identity(kind="open", tenant=None, ok=False)


__all__ = [
    "Identity",
    "SupabaseAuthVerifier",
    "SupabaseOwnerPolicy",
    "build_runtime_context",
    "owner_email_commitment",
    "owner_identity_commitment",
    "resolve_identity",
    "verify_supabase_jwt",
    "_b64url_decode",
]
