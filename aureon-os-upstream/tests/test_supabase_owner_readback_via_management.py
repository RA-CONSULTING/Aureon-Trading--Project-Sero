"""Offline tests for the secret-safe Supabase owner receipt bootstrap."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

MODULE = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "operations"
    / "supabase_owner_readback_via_management.py"
)
spec = importlib.util.spec_from_file_location(
    "supabase_owner_readback_via_management", MODULE
)
assert spec and spec.loader
bootstrap = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = bootstrap
spec.loader.exec_module(bootstrap)

PROJECT = "fixtureprojectref123"
TOKEN = "management_" + "m" * 32
SERVICE_ROLE = "service_role_" + "s" * 32


class Response:
    status = 200

    def __init__(self, url, body):
        self.url = url
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def geturl(self):
        return self.url

    def read(self, _limit):
        return self.body


class Opener:
    def __init__(self, body):
        self.body = body

    def open(self, request, timeout):
        assert timeout == 20
        assert request.headers["Authorization"] == "Bearer " + TOKEN
        return Response(request.full_url, self.body)


def opener_factory(body):
    return lambda *_handlers: Opener(body)


def test_fetches_exact_legacy_service_role_without_rendering_it():
    body = json.dumps(
        [
            {"name": "anon", "type": "legacy", "api_key": "a" * 32},
            {
                "name": "service_role",
                "type": "legacy",
                "api_key": SERVICE_ROLE,
            },
            {"name": "default", "type": "secret", "api_key": "z" * 32},
        ]
    ).encode()
    assert bootstrap.fetch_service_role_key(
        PROJECT,
        TOKEN,
        opener_factory=opener_factory(body),
    ) == SERVICE_ROLE
    source = MODULE.read_text(encoding="utf-8")
    assert "print(management_token" not in source
    assert "print(admin_secret" not in source
    assert "print(response" not in source


@pytest.mark.parametrize(
    "rows",
    [
        [],
        [{"name": "default", "type": "secret", "api_key": "z" * 32}],
        [
            {
                "name": "service_role",
                "type": "legacy",
                "api_key": SERVICE_ROLE,
            },
            {
                "name": "service_role",
                "type": "legacy",
                "api_key": "q" * 32,
            },
        ],
    ],
)
def test_fails_closed_when_service_role_selection_is_not_exact(rows):
    body = json.dumps(rows).encode()
    with pytest.raises(
        bootstrap.ReadbackBootstrapError,
        match="service_role_key_not_exactly_one",
    ):
        bootstrap.fetch_service_role_key(
            PROJECT,
            TOKEN,
            opener_factory=opener_factory(body),
        )


def test_child_receives_secret_only_over_stdin(monkeypatch, tmp_path):
    program = tmp_path / "supabase_owner_readback.py"
    program.write_text("# fixture\n", encoding="utf-8")
    receipt = (tmp_path / "receipt.json").resolve()
    observed = {}

    def fake_run(argv, **kwargs):
        observed["argv"] = argv
        observed.update(kwargs)
        return type("Completed", (), {"returncode": 0})()

    monkeypatch.setattr(bootstrap.subprocess, "run", fake_run)
    result = bootstrap.invoke_owner_readback(
        program=program,
        project_ref=PROJECT,
        subject="12345678-1234-4123-8123-123456789abc",
        source_revision="a" * 40,
        contract_sha256="b" * 64,
        receipt=receipt,
        admin_secret=SERVICE_ROLE,
    )
    assert result == 0
    assert SERVICE_ROLE.encode() in observed["input"]
    assert all(SERVICE_ROLE not in value for value in observed["argv"])
    assert all(
        SERVICE_ROLE not in value for value in observed["env"].values()
    )
    assert observed["close_fds"] is True
