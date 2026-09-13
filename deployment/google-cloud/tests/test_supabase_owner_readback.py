"""Offline tests for the redacted Supabase Auth owner readback."""

from __future__ import annotations

import importlib.util
import sys
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path

import pytest

CONTROL = Path(__file__).resolve().parents[1] / "trading-control"
sys.path.insert(0, str(CONTROL))
MODULE = CONTROL / "supabase_owner_readback.py"
spec = importlib.util.spec_from_file_location("supabase_owner_readback", MODULE)
assert spec and spec.loader
readback = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = readback
spec.loader.exec_module(readback)

PROJECT_REF = "fixtureprojectref123"
SUBJECT = "12345678-1234-4123-8123-123456789abc"
REVISION = "a" * 40
CONTRACT = "b" * 64
ADMIN_SECRET = "offline_secret_" + "x" * 32
NOW = datetime(2026, 9, 13, 18, 0, tzinfo=UTC)


def provider_fixture(_project_ref, _subject, secret):
    assert secret == ADMIN_SECRET
    return {
        "id": SUBJECT,
        "email": "owner@example.test",
        "email_confirmed_at": "2026-09-12T12:00:00Z",
        "app_metadata": {
            "provider": "email",
            "providers": ["email"],
            "aureon_role": "owner",
        },
        "user_metadata": {"aureon_role": "untrusted"},
    }


def test_owner_readback_is_provider_bound_and_redacted():
    value = readback.make_receipt(
        project_ref=PROJECT_REF,
        subject=SUBJECT,
        source_revision=REVISION,
        contract_sha256=CONTRACT,
        admin_secret=ADMIN_SECRET,
        reader=provider_fixture,
        now=NOW,
    )
    assert value == {
        "schema": "aureon.supabase-owner-provider-readback.v1",
        "provider": "supabase_auth_admin",
        "project_ref": PROJECT_REF,
        "subject": SUBJECT,
        "app_metadata_role": "owner",
        "email_confirmed": True,
        "email_sha256": readback.email_commitment("owner@example.test"),
        "recorded_at": NOW.isoformat(),
        "source_revision": REVISION,
        "contract_sha256": CONTRACT,
    }
    rendered = str(value)
    assert "owner@example.test" not in rendered
    assert ADMIN_SECRET not in rendered
    assert "user_metadata" not in rendered


@pytest.mark.parametrize(
    "change",
    [
        lambda value: value.update(id="00000000-0000-4000-8000-000000000099"),
        lambda value: value["app_metadata"].update(aureon_role="authenticated"),
        lambda value: value.update(email_confirmed_at=None),
        lambda value: value.update(email_confirmed_at="2030-01-01T00:00:00Z"),
    ],
)
def test_owner_readback_rejects_wrong_or_unconfirmed_provider_user(change):
    value = provider_fixture(PROJECT_REF, SUBJECT, ADMIN_SECRET)
    change(value)
    with pytest.raises(readback.OwnerReadbackError, match="binding_invalid"):
        readback.make_receipt(
            project_ref=PROJECT_REF,
            subject=SUBJECT,
            source_revision=REVISION,
            contract_sha256=CONTRACT,
            admin_secret=ADMIN_SECRET,
            reader=lambda *_args: value,
            now=NOW,
        )


def test_admin_secret_is_read_from_stdin_and_never_named_in_output_fields():
    assert readback.read_admin_secret(BytesIO((ADMIN_SECRET + "\n").encode())) == (
        ADMIN_SECRET
    )
    with pytest.raises(readback.OwnerReadbackError, match="secret_invalid"):
        readback.read_admin_secret(BytesIO(b"too short\n"))
    source = MODULE.read_text(encoding="utf-8")
    assert "print(admin_secret" not in source
    assert '"admin_secret"' not in source
    assert '"access_token"' not in source
