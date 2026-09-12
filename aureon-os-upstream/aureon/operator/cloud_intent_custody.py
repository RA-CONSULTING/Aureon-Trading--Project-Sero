"""Verify one owner-authenticated cloud switchboard intent.

This is deliberately narrower than a production action release. A valid
receipt permits the operator to persist a switchboard request; it never grants
exchange, order, payment, filing, tool, or runtime mutation authority.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import re
import sqlite3
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping

from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa

INTENT_AUDIENCE = "aureon-operator-switchboard-intent"
INTENT_ISSUER = "aureon-private-bridge"
INTENT_SCHEMA = "aureon.operator.cloud-switchboard-intent.v1"
INTENT_HEADER = "X-Aureon-Operator-Intent"
MAX_INTENT_TOKEN_BYTES = 8 * 1024
MAX_INTENT_LIFETIME_SECONDS = 15
_FLAG_PATH = re.compile(r"/api/switchboard/[A-Z0-9_]{1,64}")
_REVISION = re.compile(r"[0-9a-f]{40}")
_JTI = re.compile(r"[A-Za-z0-9_-]{24,96}")
_CLAIMS = frozenset(
    {
        "aud",
        "body_sha256",
        "exp",
        "iat",
        "iss",
        "jti",
        "method",
        "mode",
        "path",
        "query_sha256",
        "revision",
        "route_rule",
        "schema",
    }
)


class CloudIntentCustodyError(RuntimeError):
    """Fixed failure codes only; never include a token or key in the message."""


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _strict_object(raw: bytes) -> dict[str, Any]:
    def pairs(values: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in values:
            if key in result:
                raise ValueError("duplicate_key")
            result[key] = value
        return result

    value = json.loads(
        raw.decode("utf-8", errors="strict"),
        object_pairs_hook=pairs,
        parse_constant=lambda _value: (_ for _ in ()).throw(ValueError("constant")),
    )
    if not isinstance(value, dict):
        raise ValueError("object_required")
    return value


def _decode_segment(value: str) -> bytes:
    if not re.fullmatch(r"[A-Za-z0-9_-]+", value):
        raise ValueError("segment_invalid")
    try:
        return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    except (ValueError, binascii.Error) as exc:
        raise ValueError("segment_invalid") from exc


def _regular_file(path: str, *, label: str, maximum: int) -> Path:
    candidate = Path(path)
    if not candidate.is_absolute():
        raise CloudIntentCustodyError(label + "_absolute_path_required")
    try:
        resolved = candidate.resolve(strict=True)
        stat = resolved.stat()
    except OSError as exc:
        raise CloudIntentCustodyError(label + "_unavailable") from exc
    if candidate.is_symlink() or not resolved.is_file() or not 0 < stat.st_size <= maximum:
        raise CloudIntentCustodyError(label + "_invalid")
    return resolved


class CloudSwitchboardIntentCustody:
    """Pinned-certificate verifier with a durable one-use receipt ledger."""

    intent_only = True
    production_action_release = False
    release_authority = False
    mutation_authority = False

    def __init__(self, *, certificate_file: str, replay_ledger: str, revision: str) -> None:
        if not _REVISION.fullmatch(str(revision or "")):
            raise CloudIntentCustodyError("intent_revision_invalid")
        certificate_path = _regular_file(
            certificate_file, label="intent_certificate", maximum=64 * 1024
        )
        try:
            certificate = x509.load_pem_x509_certificate(certificate_path.read_bytes())
            public_key = certificate.public_key()
        except (OSError, ValueError, TypeError) as exc:
            raise CloudIntentCustodyError("intent_certificate_invalid") from exc
        if not isinstance(public_key, rsa.RSAPublicKey) or public_key.key_size < 2048:
            raise CloudIntentCustodyError("intent_certificate_key_invalid")
        current = datetime.now(UTC)
        if not (
            certificate.not_valid_before_utc <= current <= certificate.not_valid_after_utc
        ):
            raise CloudIntentCustodyError("intent_certificate_expired")
        ledger = Path(replay_ledger)
        if not ledger.is_absolute() or (ledger.exists() and ledger.is_symlink()):
            raise CloudIntentCustodyError("intent_replay_ledger_path_invalid")
        try:
            ledger.parent.mkdir(parents=True, exist_ok=True)
            parent = ledger.parent.resolve(strict=True)
        except OSError as exc:
            raise CloudIntentCustodyError("intent_replay_ledger_parent_unavailable") from exc
        self._certificate = certificate
        self._public_key = public_key
        self._ledger = parent / ledger.name
        self._revision = revision
        self._fingerprint = certificate.fingerprint(hashes.SHA256()).hex()
        self._preflight_ledger()

    @classmethod
    def from_env(cls, environ: Mapping[str, str]) -> CloudSwitchboardIntentCustody | None:
        certificate = str(environ.get("AUREON_OPERATOR_INTENT_CERT_FILE") or "").strip()
        ledger = str(environ.get("AUREON_OPERATOR_INTENT_LEDGER") or "").strip()
        revision = str(environ.get("AUREON_OPERATOR_REVISION") or "").strip()
        if not certificate and not ledger and not revision:
            return None
        if not certificate or not ledger or not revision:
            raise CloudIntentCustodyError("cloud_intent_custody_config_incomplete")
        return cls(certificate_file=certificate, replay_ledger=ledger, revision=revision)

    def _connect(self) -> sqlite3.Connection:
        if self._ledger.exists() and self._ledger.is_symlink():
            raise CloudIntentCustodyError("intent_replay_ledger_path_invalid")
        connection = sqlite3.connect(str(self._ledger), timeout=5, isolation_level=None)
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=FULL")
        connection.execute("PRAGMA busy_timeout=5000")
        return connection

    def _preflight_ledger(self) -> None:
        try:
            with self._connect() as connection:
                connection.execute(
                    "CREATE TABLE IF NOT EXISTS consumed_intents ("
                    "jti TEXT PRIMARY KEY NOT NULL, token_sha256 TEXT NOT NULL, "
                    "path TEXT NOT NULL, consumed_at INTEGER NOT NULL, expires_at INTEGER NOT NULL)"
                )
                columns = connection.execute("PRAGMA table_info(consumed_intents)").fetchall()
        except (OSError, sqlite3.Error) as exc:
            raise CloudIntentCustodyError("intent_replay_ledger_unavailable") from exc
        if [row[1] for row in columns] != [
            "jti", "token_sha256", "path", "consumed_at", "expires_at"
        ]:
            raise CloudIntentCustodyError("intent_replay_ledger_schema_invalid")

    def _consume(self, *, jti: str, token: str, path: str, now: int, expires: int) -> None:
        try:
            connection = self._connect()
            try:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute("DELETE FROM consumed_intents WHERE expires_at < ?", (now - 60,))
                connection.execute(
                    "INSERT INTO consumed_intents(jti,token_sha256,path,consumed_at,expires_at) "
                    "VALUES(?,?,?,?,?)",
                    (jti, _sha(token.encode("ascii")), path, now, expires),
                )
                connection.commit()
            finally:
                connection.close()
        except sqlite3.IntegrityError as exc:
            raise CloudIntentCustodyError("cloud_intent_receipt_replayed") from exc
        except (OSError, sqlite3.Error) as exc:
            raise CloudIntentCustodyError("intent_replay_ledger_unavailable") from exc

    def authorize_and_consume(
        self,
        *,
        token: str,
        method: str,
        path: str,
        route_rule: str,
        query: bytes,
        body: bytes,
        identity_kind: str,
        is_admin: bool,
        now: int | None = None,
    ) -> dict[str, Any]:
        if (
            identity_kind != "admin"
            or is_admin is not True
            or method != "POST"
            or not _FLAG_PATH.fullmatch(path)
            or route_rule != "/api/switchboard/<flag_id>"
            or query
        ):
            raise CloudIntentCustodyError("cloud_intent_scope_denied")
        if not isinstance(token, str) or not 0 < len(token.encode("utf-8")) <= MAX_INTENT_TOKEN_BYTES:
            raise CloudIntentCustodyError("cloud_intent_receipt_missing")
        if not re.fullmatch(r"[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+", token):
            raise CloudIntentCustodyError("cloud_intent_receipt_invalid")
        try:
            encoded_header, encoded_claims, encoded_signature = token.split(".")
            header = _strict_object(_decode_segment(encoded_header))
            claims = _strict_object(_decode_segment(encoded_claims))
            self._public_key.verify(
                _decode_segment(encoded_signature),
                (encoded_header + "." + encoded_claims).encode("ascii"),
                padding.PKCS1v15(),
                hashes.SHA256(),
            )
        except (InvalidSignature, UnicodeError, ValueError, TypeError) as exc:
            raise CloudIntentCustodyError("cloud_intent_receipt_invalid") from exc
        if (
            set(header) != {"alg", "typ"}
            or header.get("alg") != "RS256"
            or header.get("typ") != "JWT"
        ):
            raise CloudIntentCustodyError("cloud_intent_receipt_header_invalid")
        if not isinstance(claims, dict) or set(claims) != _CLAIMS:
            raise CloudIntentCustodyError("cloud_intent_receipt_claims_invalid")
        issued, expires = claims.get("iat"), claims.get("exp")
        current = int(time.time()) if now is None else int(now)
        if (
            type(issued) is not int
            or type(expires) is not int
            or expires <= issued
            or expires - issued > MAX_INTENT_LIFETIME_SECONDS
            or issued > current + 2
            or expires < current - 2
        ):
            raise CloudIntentCustodyError("cloud_intent_receipt_time_invalid")
        jti = claims.get("jti")
        expected = {
            "schema": INTENT_SCHEMA,
            "aud": INTENT_AUDIENCE,
            "iss": INTENT_ISSUER,
            "method": method,
            "mode": "iap",
            "path": path,
            "route_rule": route_rule,
            "query_sha256": _sha(query),
            "body_sha256": _sha(body),
            "revision": self._revision,
        }
        if (
            not isinstance(jti, str)
            or not _JTI.fullmatch(jti)
            or any(claims.get(key) != value for key, value in expected.items())
        ):
            raise CloudIntentCustodyError("cloud_intent_receipt_join_invalid")
        self._consume(jti=jti, token=token, path=path, now=current, expires=expires)
        return {
            "schema": "aureon.operator.cloud-switchboard-intent-custody.v1",
            "intent_recording_authorized": True,
            "production_action_release": False,
            "release_authority": False,
            "mutation_authority": False,
            "certificate_fingerprint_sha256": self._fingerprint,
            "token_sha256": _sha(token.encode("ascii")),
            "path_sha256": _sha(path.encode("utf-8")),
            "body_sha256": _sha(body),
            "consumed_at": current,
        }

    def public_summary(self) -> dict[str, Any]:
        return {
            "schema": "aureon.operator.cloud-switchboard-intent-custody.v1",
            "configured": True,
            "intent_recording_authority": True,
            "scope": "owner_iap_switchboard_intent_only",
            "durable_replay_ledger": True,
            "certificate_fingerprint_sha256": self._fingerprint,
            "production_action_release": False,
            "production_ready": False,
            "release_authority": False,
            "mutation_authority": False,
        }


__all__ = [
    "CloudIntentCustodyError",
    "CloudSwitchboardIntentCustody",
    "INTENT_AUDIENCE",
    "INTENT_HEADER",
    "INTENT_ISSUER",
    "INTENT_SCHEMA",
]
