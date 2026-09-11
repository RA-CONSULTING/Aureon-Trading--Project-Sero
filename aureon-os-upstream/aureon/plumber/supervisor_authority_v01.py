"""Authenticate supervisor measurements against explicitly provisioned public keys.

Verification proves the signature and exact expected bindings, not containment,
key-custody independence, production readiness, or permission to start a process.
The verifier is deliberately stateless: a caller must separately claim a verified
challenge durably before a future effect. No keys, receipts or measurements are
generated here; no filesystem, network, target import or process API is used.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Callable, Final

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

SCHEMA: Final = "aureon.plumber.supervisor-attestation.v01"
SIGNING_DOMAIN: Final = b"AUREON-SUPERVISOR-ATTESTATION-V01\x00"
MAX_WIRE_BYTES: Final = 16_384
MAX_JSON_DEPTH: Final = 8
_MAX_EPOCH_MS = (1 << 53) - 1
_ROLES = frozenset({"SUPERVISOR", "REVIEW", "DISPATCH", "EXECUTOR", "RECEIPT"})
_DIGEST_FIELDS = (
    "target_entrypoint_sha256", "target_source_sha256", "source_scope_sha256",
    "bootstrap_source_sha256", "interpreter_sha256", "argv_sha256",
    "environment_policy_sha256", "runtime_guard_sha256", "os_policy_sha256",
)
_WIRE_FIELDS = frozenset({
    "schema", "authority_id", "key_id", "attestation_id", "deployment_id",
    "challenge_sha256", "issued_at_ms", "expires_at_ms", "measurements", "signature_hex",
})


class SupervisorAuthorityError(ValueError):
    """A stable code; never includes an untrusted payload or key value."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise SupervisorAuthorityError(code)


def _identifier(value: object) -> None:
    _require(type(value) is str and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}", value) is not None,
             "identifier_invalid")


def _digest(value: object) -> None:
    _require(type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None and value != "0" * 64,
             "measurement_digest_invalid")


def _epoch(value: object) -> None:
    _require(type(value) is int and 0 <= value <= _MAX_EPOCH_MS, "epoch_ms_invalid")


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                      allow_nan=False).encode("utf-8")


def _object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        _require(key not in result, "duplicate_json_key")
        result[key] = value
    return result


def _invalid_constant(_: str) -> object:
    raise SupervisorAuthorityError("nonfinite_json_number")


def _bounded_nesting(raw: bytes) -> None:
    # Bound parser work independently of the host interpreter's recursion limit.
    depth, quoted, escaped = 0, False, False
    for char in raw:
        if quoted:
            if escaped:
                escaped = False
            elif char == 92:
                escaped = True
            elif char == 34:
                quoted = False
        elif char == 34:
            quoted = True
        elif char in (91, 123):
            depth += 1
            _require(depth <= MAX_JSON_DEPTH, "json_nesting_limit_exceeded")
        elif char in (93, 125):
            depth -= 1


@dataclass(frozen=True, slots=True)
class AuthorityPinV01:
    role: str
    authority_id: str
    key_id: str
    public_key_hex: str
    not_before_ms: int
    not_after_ms: int

    def __post_init__(self) -> None:
        _require(type(self.role) is str and self.role in _ROLES, "authority_role_invalid")
        _identifier(self.authority_id)
        _identifier(self.key_id)
        _digest(self.public_key_hex)
        _epoch(self.not_before_ms)
        _epoch(self.not_after_ms)
        _require(self.not_before_ms < self.not_after_ms, "authority_validity_invalid")


@dataclass(frozen=True, slots=True)
class SupervisorMeasurementsV01:
    target_id: str
    target_entrypoint_sha256: str
    target_source_sha256: str
    source_scope_sha256: str
    bootstrap_source_sha256: str
    interpreter_sha256: str
    argv_sha256: str
    environment_policy_sha256: str
    runtime_guard_sha256: str
    os_policy_sha256: str

    def __post_init__(self) -> None:
        _require(type(self.target_id) is str and re.fullmatch(r"[a-z][a-z0-9-]{0,63}", self.target_id) is not None,
                 "target_id_invalid")
        for name in _DIGEST_FIELDS:
            _digest(getattr(self, name))

    def public_dict(self) -> dict[str, str]:
        return {"target_id": self.target_id, **{name: getattr(self, name) for name in _DIGEST_FIELDS}}


@dataclass(frozen=True, slots=True)
class SupervisorExpectationV01:
    deployment_id: str
    challenge_sha256: str
    measurements: SupervisorMeasurementsV01

    def __post_init__(self) -> None:
        _identifier(self.deployment_id)
        _digest(self.challenge_sha256)
        _require(type(self.measurements) is SupervisorMeasurementsV01, "exact_measurements_required")


@dataclass(frozen=True, slots=True)
class SupervisorFreshnessPolicyV01:
    max_age_ms: int
    max_validity_ms: int
    max_clock_skew_ms: int

    def __post_init__(self) -> None:
        for value in (self.max_age_ms, self.max_validity_ms):
            _require(type(value) is int and 1 <= value <= 300_000, "bounded_freshness_policy_required")
        _require(type(self.max_clock_skew_ms) is int and 0 <= self.max_clock_skew_ms <= 60_000,
                 "bounded_clock_skew_required")


@dataclass(frozen=True, slots=True)
class VerifiedSupervisorAttestationV01:
    """Local verification result, never a transferable execution capability.

    Reverify original_wire at another trust boundary; do not trust a constructed
    Python result object or interpret verified_at_ms as a source measurement.
    """

    authority_id: str
    key_id: str
    attestation_id: str
    deployment_id: str
    challenge_sha256: str
    issued_at_ms: int
    expires_at_ms: int
    measurements: SupervisorMeasurementsV01
    verified_at_ms: int
    wire_sha256: str
    original_wire: bytes = field(repr=False)


class SupervisorAttestationVerifierV01:
    def __init__(
        self, *, trust_roots: tuple[AuthorityPinV01, ...],
        other_authorities: tuple[AuthorityPinV01, ...],
        freshness: SupervisorFreshnessPolicyV01,
        trusted_now_ms: Callable[[], int] = lambda: time.time_ns() // 1_000_000,
    ) -> None:
        _require(type(trust_roots) is tuple and 1 <= len(trust_roots) <= 32, "explicit_trust_roots_required")
        _require(type(other_authorities) is tuple and len(other_authorities) <= 128, "authority_roster_invalid")
        _require(type(freshness) is SupervisorFreshnessPolicyV01, "exact_freshness_policy_required")
        _require(callable(trusted_now_ms), "trusted_clock_required")
        for pin in trust_roots + other_authorities:
            _require(type(pin) is AuthorityPinV01, "exact_authority_pin_required")
        _require(all(pin.role == "SUPERVISOR" for pin in trust_roots), "supervisor_role_required")
        _require(all(pin.role != "SUPERVISOR" for pin in other_authorities), "other_authority_role_invalid")
        # Multiple separately pinned keys may rotate for one supervisor identity.
        for attr in ("key_id", "public_key_hex"):
            _require(len({getattr(pin, attr) for pin in trust_roots}) == len(trust_roots), "duplicate_trust_root")
        for attr in ("authority_id", "key_id", "public_key_hex"):
            _require(not ({getattr(pin, attr) for pin in trust_roots} & {getattr(pin, attr) for pin in other_authorities}),
                     "supervisor_authority_not_distinct")
        self._pins = MappingProxyType({(pin.authority_id, pin.key_id): pin for pin in trust_roots})
        self._freshness = freshness
        self._now = trusted_now_ms

    def verify(self, raw: bytes, *, expected: SupervisorExpectationV01) -> VerifiedSupervisorAttestationV01:
        _require(type(expected) is SupervisorExpectationV01, "exact_expectation_required")
        _require(type(raw) is bytes and 1 <= len(raw) <= MAX_WIRE_BYTES, "bounded_canonical_wire_required")
        _bounded_nesting(raw)
        try:
            value = json.loads(raw.decode("utf-8"), object_pairs_hook=_object, parse_constant=_invalid_constant)
            _require(type(value) is dict and set(value) == _WIRE_FIELDS, "exact_attestation_fields_required")
            _require(_canonical(value) == raw, "canonical_wire_required")
            _require(value["schema"] == SCHEMA, "attestation_schema_invalid")
            for name in ("authority_id", "key_id", "attestation_id", "deployment_id"):
                _identifier(value[name])
            _digest(value["challenge_sha256"])
            _epoch(value["issued_at_ms"])
            _epoch(value["expires_at_ms"])
            signature = value["signature_hex"]
            _require(type(signature) is str and re.fullmatch(r"[0-9a-f]{128}", signature) is not None,
                     "signature_encoding_invalid")
            measurements = value["measurements"]
            _require(type(measurements) is dict and set(measurements) == {"target_id", *_DIGEST_FIELDS},
                     "exact_measurement_fields_required")
            measured = SupervisorMeasurementsV01(**measurements)
        except SupervisorAuthorityError:
            raise
        except (UnicodeError, ValueError, TypeError, RecursionError, OverflowError):
            raise SupervisorAuthorityError("attestation_wire_invalid") from None

        pin = self._pins.get((value["authority_id"], value["key_id"]))
        _require(pin is not None, "untrusted_supervisor_authority")
        unsigned = {key: item for key, item in value.items() if key != "signature_hex"}
        try:
            Ed25519PublicKey.from_public_bytes(bytes.fromhex(pin.public_key_hex)).verify(
                bytes.fromhex(signature), SIGNING_DOMAIN + _canonical(unsigned),
            )
        except (InvalidSignature, ValueError):
            raise SupervisorAuthorityError("supervisor_signature_invalid") from None

        try:
            now = self._now()
        except Exception:
            raise SupervisorAuthorityError("trusted_clock_unavailable") from None
        _epoch(now)
        issued, expires = value["issued_at_ms"], value["expires_at_ms"]
        _require(pin.not_before_ms <= now < pin.not_after_ms and pin.not_before_ms <= issued < pin.not_after_ms,
                 "authority_not_current")
        _require(issued < expires and expires - issued <= self._freshness.max_validity_ms,
                 "attestation_validity_invalid")
        _require(expires <= pin.not_after_ms, "attestation_exceeds_authority_validity")
        _require(issued <= now + self._freshness.max_clock_skew_ms, "attestation_from_future")
        _require(now - issued <= self._freshness.max_age_ms and now < expires, "attestation_not_current")
        _require(value["deployment_id"] == expected.deployment_id, "deployment_binding_mismatch")
        _require(value["challenge_sha256"] == expected.challenge_sha256, "challenge_binding_mismatch")
        _require(measured == expected.measurements, "measurement_binding_mismatch")
        return VerifiedSupervisorAttestationV01(
            pin.authority_id, pin.key_id, value["attestation_id"], value["deployment_id"],
            value["challenge_sha256"], issued, expires, measured, now,
            hashlib.sha256(raw).hexdigest(), raw,
        )
