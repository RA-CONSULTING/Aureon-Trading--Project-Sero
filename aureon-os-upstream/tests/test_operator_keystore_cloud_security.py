"""Cloud keystore path and pinned-secret precedence contracts."""

from __future__ import annotations

import importlib
import importlib.util
import os
import stat
from pathlib import Path

import pytest

BOUNDARY_PATH = (
    Path(__file__).resolve().parents[2]
    / "deployment/google-cloud/cloud_credential_boundary.py"
)
boundary_spec = importlib.util.spec_from_file_location(
    "cloud_credential_boundary_for_keystore_test", BOUNDARY_PATH
)
boundary = importlib.util.module_from_spec(boundary_spec)
boundary_spec.loader.exec_module(boundary)


def _isolated_keystore(tmp_path, monkeypatch):
    monkeypatch.setenv("AUREON_KEYSTORE_DIR", str(tmp_path / "operator-keystore"))
    import aureon.operator.keystore as keystore

    return importlib.reload(keystore)


def test_env_configures_an_absolute_keystore_root(tmp_path, monkeypatch) -> None:
    keystore = _isolated_keystore(tmp_path, monkeypatch)

    assert tmp_path / "operator-keystore" == keystore.CONFIG_DIR
    assert keystore.KEY_PATH.parent == keystore.CONFIG_DIR
    assert keystore.TENANTS_DIR.parent == keystore.CONFIG_DIR

    monkeypatch.setenv("AUREON_KEYSTORE_DIR", "relative/store")
    with pytest.raises(RuntimeError, match="MUST_BE_ABSOLUTE"):
        keystore._configured_root()


def test_keystore_creates_private_directory_and_files(tmp_path, monkeypatch) -> None:
    keystore = _isolated_keystore(tmp_path, monkeypatch)
    keystore.save_provider("openai", api_key="tenant-secret", tenant="tenant-a")

    paths = (
        keystore.CONFIG_DIR,
        keystore.TENANTS_DIR,
        keystore._store_path("tenant-a").parent,
    )
    files = (keystore.KEY_PATH, keystore._store_path("tenant-a"))
    assert all(path.exists() for path in (*paths, *files))
    if os.name == "posix":
        assert all(stat.S_IMODE(path.stat().st_mode) == 0o700 for path in paths)
        assert all(stat.S_IMODE(path.stat().st_mode) == 0o600 for path in files)


def test_pinned_secret_manager_values_survive_global_keystore_apply_and_delete(
    tmp_path, monkeypatch,
) -> None:
    keystore = _isolated_keystore(tmp_path, monkeypatch)
    pinned = {
        "NASA_API_KEY": "secret-manager-nasa",
        "OLLAMA_API_KEY": "secret-manager-ollama",
        "AUREON_OLLAMA_API_KEY": "secret-manager-alias",
        "AUREON_LLM_API_KEY": "secret-manager-llm-alias",
        "AUREON_LLM_BASE_URL": "https://ollama.com/v1",
        "AUREON_LLM_MODEL": "qwen3:32b",
        "AUREON_OLLAMA_MODEL": "qwen3:32b",
        "AUREON_MODEL_LOCAL": "qwen3:32b",
    }
    for name, value in pinned.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setenv(
        keystore.PINNED_ENV_VARS_ENV,
        "NASA_API_KEY,OLLAMA_API_KEY,AUREON_LLM_BASE_URL,AUREON_LLM_MODEL",
    )

    keystore.save_provider("nasa", api_key="stale-keystore-nasa")
    keystore.save_provider(
        "ollama",
        api_key="stale-keystore-ollama",
        base_url="http://127.0.0.1:11434/v1",
        model="stale-model",
    )
    keystore.save_provider("grok", api_key="ordinary-unpinned-key")
    keystore.apply_to_env()

    assert {name: os.environ.get(name) for name in pinned} == pinned
    assert os.environ["XAI_API_KEY"] == "ordinary-unpinned-key"

    keystore.delete_provider("nasa")
    keystore.delete_provider("ollama")
    assert {name: os.environ.get(name) for name in pinned} == pinned


def test_cloud_exchange_marker_prevents_stale_global_keystore_injection(
    tmp_path, monkeypatch,
) -> None:
    keystore = _isolated_keystore(tmp_path, monkeypatch)
    keystore.save_provider(
        "binance",
        api_key="stale-owner-primary",
        extra={"BINANCE_API_SECRET": "stale-owner-secondary"},
    )
    monkeypatch.setenv("AUREON_CLOUD_EXCHANGE_CREDENTIALS_PINNED", "1")
    monkeypatch.delenv("BINANCE_API_KEY", raising=False)
    monkeypatch.delenv("BINANCE_API_SECRET", raising=False)

    keystore.apply_to_env()

    assert "BINANCE_API_KEY" not in os.environ
    assert "BINANCE_API_SECRET" not in os.environ
    assert set(keystore.protected_provider_fields("binance")) == {
        "BINANCE_API_KEY", "BINANCE_API_SECRET",
    }


def test_cloud_exchange_alias_census_blocks_adversarial_keystore_extras(
    tmp_path, monkeypatch,
) -> None:
    keystore = _isolated_keystore(tmp_path, monkeypatch)
    assert (
        keystore.CLOUD_EXCHANGE_CREDENTIAL_ENV_VARS
        == boundary.CLOUD_EXCHANGE_CREDENTIAL_ENV_VARS
    )
    stale = {
        "alpaca": {
            "ALPACA_API_KEY_ID": "stale",
            "ALPACA_API_SECRET_KEY": "stale",
            "APCA_API_SECRET_KEY": "stale",
        },
        "binance": {
            "BINANCE_TESTNET_API_KEY": "stale",
            "BINANCE_TESTNET_API_SECRET": "stale",
        },
        "capital": {"CAPITAL_EMAIL": "stale", "CAPITAL_API_SECRET": "stale"},
        "kraken": {"KRAKEN_SECRET": "stale", "KRAKEN_PRIVATE_KEY": "stale"},
    }
    for provider_id, extra in stale.items():
        keystore.save_provider(provider_id, api_key="stale-primary", extra=extra)
    monkeypatch.setenv("AUREON_CLOUD_EXCHANGE_CREDENTIALS_PINNED", "1")
    for name in keystore.CLOUD_EXCHANGE_CREDENTIAL_ENV_VARS:
        monkeypatch.setenv(name, "ambient-owner-alias")

    keystore.apply_to_env()

    assert not (
        set(keystore.CLOUD_EXCHANGE_CREDENTIAL_ENV_VARS) & set(os.environ)
    )
