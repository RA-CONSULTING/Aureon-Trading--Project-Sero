"""Offline contract tests. Every signing key below is a public test fixture."""

from __future__ import annotations

import ast
import importlib.util
import json
import sys
from dataclasses import FrozenInstanceError, replace
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

SOURCE = Path(__file__).resolve().parents[1] / "aureon/plumber/supervisor_authority_v01.py"
SPEC = importlib.util.spec_from_file_location("staged_supervisor_authority_v01", SOURCE)
assert SPEC is not None and SPEC.loader is not None
module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = module
SPEC.loader.exec_module(module)

NOW = 1_788_959_000_000
# Deliberately fixed, published fixture seeds; never authority credentials.
KEY = Ed25519PrivateKey.from_private_bytes(bytes(range(32)))
OTHER_KEY = Ed25519PrivateKey.from_private_bytes(bytes(range(32, 64)))


def public_hex(key=KEY):
    return key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw).hex()


def pin(**changes):
    return module.AuthorityPinV01(**{
        "role": "SUPERVISOR", "authority_id": "fixture-supervisor",
        "key_id": "fixture-key-1", "public_key_hex": public_hex(),
        "not_before_ms": NOW - 60_000, "not_after_ms": NOW + 120_000,
        **changes,
    })


def expected():
    return module.SupervisorExpectationV01(
        "fixture-deployment", "c" * 64,
        module.SupervisorMeasurementsV01("operator", **{
            name: f"{index + 1:064x}" for index, name in enumerate(module._DIGEST_FIELDS)
        }),
    )


def verifier(*, now=NOW, roots=None, other=(), **changes):
    return module.SupervisorAttestationVerifierV01(
        trust_roots=(pin(),) if roots is None else roots, other_authorities=other,
        freshness=module.SupervisorFreshnessPolicyV01(10_000, 60_000, 5_000),
        trusted_now_ms=lambda: now, **changes,
    )


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode()


def wire(*, key=KEY, measurement_changes=None, **changes):
    expect = expected()
    unsigned = {
        "schema": module.SCHEMA, "authority_id": "fixture-supervisor", "key_id": "fixture-key-1",
        "attestation_id": "fixture-attestation", "deployment_id": expect.deployment_id,
        "challenge_sha256": expect.challenge_sha256, "issued_at_ms": NOW - 1_000,
        "expires_at_ms": NOW + 20_000,
        "measurements": {**expect.measurements.public_dict(), **(measurement_changes or {})}, **changes,
    }
    signature = key.sign(module.SIGNING_DOMAIN + canonical(unsigned)).hex()
    return canonical({**unsigned, "signature_hex": signature})


def rejects(raw, code, *, checker=None, expect=None):
    with pytest.raises(module.SupervisorAuthorityError, match=f"^{code}$"):
        (checker or verifier()).verify(raw, expected=expect or expected())


def test_valid_external_signature_preserves_original_wire_and_source_clock():
    raw = wire()
    result = verifier().verify(raw, expected=expected())
    later = verifier(now=NOW + 2_000).verify(raw, expected=expected())
    assert result.original_wire is raw
    assert later.original_wire == raw
    assert result.measurements == expected().measurements
    assert result.issued_at_ms == later.issued_at_ms == NOW - 1_000
    assert result.expires_at_ms == later.expires_at_ms == NOW + 20_000
    assert later.verified_at_ms == NOW + 2_000
    assert not hasattr(result, "production_ready")
    assert not hasattr(result, "process_start_authorized")
    with pytest.raises(FrozenInstanceError):
        result.issued_at_ms = NOW


@pytest.mark.parametrize("field", module._DIGEST_FIELDS)
def test_every_measurement_digest_is_bound_to_independent_expectation(field):
    rejects(wire(measurement_changes={field: "f" * 64}), "measurement_binding_mismatch")


def test_target_and_deployment_and_challenge_are_exactly_bound():
    rejects(wire(measurement_changes={"target_id": "operator-wsgi"}), "measurement_binding_mismatch")
    rejects(wire(deployment_id="another-deployment"), "deployment_binding_mismatch")
    rejects(wire(challenge_sha256="d" * 64), "challenge_binding_mismatch")


def test_tampering_a_well_formed_claim_without_resigning_fails():
    altered = json.loads(wire())
    altered["measurements"]["interpreter_sha256"] = "f" * 64
    rejects(canonical(altered), "supervisor_signature_invalid")
    rejects(wire(key=OTHER_KEY), "supervisor_signature_invalid")


def test_unknown_authority_or_key_and_payload_supplied_trust_are_rejected():
    rejects(wire(authority_id="not-pinned"), "untrusted_supervisor_authority")
    rejects(wire(key_id="not-pinned"), "untrusted_supervisor_authority")
    rejects(wire(public_key_hex=public_hex()), "exact_attestation_fields_required")


@pytest.mark.parametrize("change,code", [
    ({"issued_at_ms": NOW - 10_001, "expires_at_ms": NOW + 1}, "attestation_not_current"),
    ({"expires_at_ms": NOW}, "attestation_not_current"),
    ({"issued_at_ms": NOW + 5_001}, "attestation_from_future"),
    ({"issued_at_ms": NOW - 1, "expires_at_ms": NOW - 1}, "attestation_validity_invalid"),
    ({"expires_at_ms": NOW + 60_000}, "attestation_validity_invalid"),
    ({"issued_at_ms": True}, "epoch_ms_invalid"),
    ({"expires_at_ms": 1e100}, "epoch_ms_invalid"),
])
def test_time_limits_fail_closed(change, code):
    rejects(wire(**change), code)


def test_configured_clock_skew_is_bounded_and_does_not_extend_expiry():
    result = verifier().verify(wire(issued_at_ms=NOW + 5_000), expected=expected())
    assert result.issued_at_ms == NOW + 5_000
    rejects(wire(expires_at_ms=NOW), "attestation_not_current")


@pytest.mark.parametrize("changes,code", [
    ({"not_before_ms": NOW + 1}, "authority_not_current"),
    ({"not_before_ms": NOW - 500}, "authority_not_current"),
    ({"not_after_ms": NOW}, "authority_not_current"),
    ({"not_after_ms": NOW + 5_000}, "attestation_exceeds_authority_validity"),
])
def test_authority_window_covers_both_verification_and_signed_validity(changes, code):
    rejects(wire(), code, checker=verifier(roots=(pin(**changes),)))


def test_explicit_root_provisioning_and_rotation_without_trust_on_first_use():
    with pytest.raises(module.SupervisorAuthorityError, match="explicit_trust_roots_required"):
        verifier(roots=())
    rotated = pin(key_id="fixture-key-2", public_key_hex=public_hex(OTHER_KEY))
    raw = wire(key=OTHER_KEY, key_id="fixture-key-2")
    assert verifier(roots=(pin(), rotated)).verify(raw, expected=expected()).key_id == "fixture-key-2"
    rejects(wire(), "untrusted_supervisor_authority", checker=verifier(roots=(rotated,)))


@pytest.mark.parametrize("field", ["authority_id", "key_id", "public_key_hex"])
def test_supervisor_cannot_reuse_other_role_identity_or_key(field):
    reserved = pin(role="EXECUTOR", authority_id="separate-executor", key_id="separate-key", public_key_hex=public_hex(OTHER_KEY))
    reserved = replace(reserved, **{field: getattr(pin(), field)})
    with pytest.raises(module.SupervisorAuthorityError, match="supervisor_authority_not_distinct"):
        verifier(other=(reserved,))


def test_invalid_roles_and_duplicate_root_aliases_are_rejected():
    with pytest.raises(module.SupervisorAuthorityError, match="supervisor_role_required"):
        verifier(roots=(pin(role="EXECUTOR"),))
    with pytest.raises(module.SupervisorAuthorityError, match="duplicate_trust_root"):
        verifier(roots=(pin(), pin(authority_id="alias", key_id="alias-key")))


@pytest.mark.parametrize("transform,code", [
    (lambda raw: b" " + raw, "canonical_wire_required"),
    (lambda raw: raw.replace(b'"target_id":"operator"', b'"target_id":"operator","target_id":"operator"'), "duplicate_json_key"),
    (lambda raw: raw.replace(b'"schema":', b'"schema":"duplicate","schema":', 1), "duplicate_json_key"),
    (lambda raw: raw.replace(str(NOW - 1_000).encode(), b"NaN"), "nonfinite_json_number"),
    (lambda raw: b"[" * 1_100 + b"]" * 1_100, "json_nesting_limit_exceeded"),
    (lambda raw: b"x" * (module.MAX_WIRE_BYTES + 1), "bounded_canonical_wire_required"),
    (lambda raw: bytearray(raw), "bounded_canonical_wire_required"),
    (lambda raw: b"\xff", "attestation_wire_invalid"),
])
def test_untrusted_wire_shape_and_encoding_are_bounded(transform, code):
    rejects(transform(wire()), code)


def test_nesting_bound_ignores_brackets_and_escapes_inside_strings():
    rejects(wire(schema='"\\[{' * 100), "attestation_schema_invalid")


def test_unknown_missing_and_placeholder_claims_cannot_qualify():
    rejects(wire(production_ready=True), "exact_attestation_fields_required")
    rejects(wire(schema="different-schema"), "attestation_schema_invalid")
    rejects(wire(measurement_changes={"runtime_guard_sha256": "0" * 64}), "measurement_digest_invalid")
    rejects(wire(measurement_changes={"arbitrary_path": "not-needed"}), "exact_measurement_fields_required")
    altered = json.loads(wire())
    del altered["measurements"]["os_policy_sha256"]
    rejects(canonical(altered), "exact_measurement_fields_required")


def test_clock_failure_and_untrusted_error_values_are_not_reflected():
    def failed_clock():
        raise RuntimeError("PRIVATE-FIXTURE-CANARY")
    checker = module.SupervisorAttestationVerifierV01(
        trust_roots=(pin(),), other_authorities=(),
        freshness=module.SupervisorFreshnessPolicyV01(10_000, 60_000, 5_000), trusted_now_ms=failed_clock,
    )
    rejects(wire(), "trusted_clock_unavailable", checker=checker)
    rejects(wire(attestation_id="PRIVATE-FIXTURE-CANARY\n"), "identifier_invalid")


def test_import_surface_has_no_runtime_provider_filesystem_or_process_integration():
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    imports = {
        node.module.split(".")[0] for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module
    } | {alias.name.split(".")[0] for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names}
    assert imports <= {"__future__", "hashlib", "json", "re", "time", "dataclasses", "types", "typing", "cryptography"}
    assert not any(isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in {"open", "exec", "eval", "compile"} for node in ast.walk(tree))


def test_verification_is_stateless_and_does_not_claim_replay_consumption():
    raw = wire()
    checker = verifier()
    first = checker.verify(raw, expected=expected())
    second = checker.verify(raw, expected=expected())
    assert first == second
    rejects(raw, "challenge_binding_mismatch", expect=replace(expected(), challenge_sha256="e" * 64))
    assert not hasattr(first, "replay_consumed")
