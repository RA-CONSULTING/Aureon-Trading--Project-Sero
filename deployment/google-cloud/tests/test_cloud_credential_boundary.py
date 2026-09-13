"""Adversarial tests for the held VM credential environment."""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import subprocess
import sys


DIRECTORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DIRECTORY))
spec = importlib.util.spec_from_file_location(
    "cloud_credential_boundary", DIRECTORY / "cloud_credential_boundary.py"
)
boundary = importlib.util.module_from_spec(spec)
spec.loader.exec_module(boundary)


EXPECTED_ALIAS_CENSUS = {
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
}


def test_closed_alias_census_includes_every_consumed_legacy_spelling() -> None:
    assert set(boundary.CLOUD_EXCHANGE_CREDENTIAL_ENV_VARS) == EXPECTED_ALIAS_CENSUS

    root = DIRECTORY.parents[1]
    evidence = {
        "ALPACA_API_KEY_ID": root / "aureon_radar/multi_source_feed.py",
        "ALPACA_API_SECRET_KEY": root / "aureon_radar/multi_source_feed.py",
        "KRAKEN_SECRET": root / "aureon_radar/exchange_adapters/kraken_adapter.py",
        "BINANCE_TESTNET_API_KEY": root / "aureon-os-upstream/scripts/traders/livePaperTrade.ts",
        "BINANCE_TESTNET_API_SECRET": root / "aureon-os-upstream/scripts/traders/livePaperTrade.ts",
        "CAPITAL_EMAIL": root / "aureon-os-upstream/scripts/traders/forexTrader.ts",
    }
    for alias, path in evidence.items():
        assert alias in path.read_text(encoding="utf-8")
        assert alias in boundary.CLOUD_EXCHANGE_CREDENTIAL_ENV_VARS


def test_mapping_guard_permanently_denies_aliases_and_pins_held_modes() -> None:
    backing = {
        **{name: "ambient" for name in EXPECTED_ALIAS_CENSUS},
        **{name: "unsafe" for name in boundary.CLOUD_EXCHANGE_MODE_ENV_VARS},
        **{name: "loader" for name in boundary.CLOUD_ENV_LOADER_CONTROL_VARS},
        "NASA_API_KEY": "validated-provider",
    }
    boundary.scrub_cloud_exchange_authority(backing)
    assert backing["APCA_LIVE"] == "false"
    assert backing["BINANCE_TESTNET"] == "false"
    assert backing["CAPITAL_DEMO_MODE"] == "1"
    assert backing["KRAKEN_LIVE_ENABLED"] == "false"
    guarded = boundary.CloudCredentialEnvironment(backing)

    for name in EXPECTED_ALIAS_CENSUS:
        guarded[name] = "rehydrated"
        assert name not in guarded
        assert name not in guarded.copy()
    for name, value in boundary.CLOUD_OPERATOR_SAFE_MODE_ENV.items():
        guarded[name] = "unsafe"
        assert guarded[name] == value
        del guarded[name]
        assert guarded[name] == value
    for name in (
        boundary.CLOUD_EXCHANGE_MODE_ENV_VARS
        - boundary.CLOUD_OPERATOR_SAFE_MODE_ENV.keys()
    ):
        guarded[name] = "true"
        assert name not in guarded
    guarded["AUREON_ENV_FILE"] = "/tmp/alternate.env"
    assert "AUREON_ENV_FILE" not in guarded
    guarded.pin({"NASA_API_KEY": "validated-provider"})
    guarded["NASA_API_KEY"] = "dotenv-replacement"
    assert guarded["NASA_API_KEY"] == "validated-provider"
    guarded[boundary.CLOUD_CREDENTIAL_ISOLATION_ENV] = "0"
    assert guarded[boundary.CLOUD_CREDENTIAL_ISOLATION_ENV] == "1"
    guarded["ORDINARY_VALUE"] = "retained-until-clear"
    guarded.clear()
    assert "ORDINARY_VALUE" not in guarded
    assert guarded[boundary.CLOUD_EXCHANGE_CREDENTIALS_PINNED_ENV] == "1"


def test_real_dotenv_override_cannot_rehydrate_aliases_or_replace_pinned_provider(
    tmp_path: Path,
) -> None:
    dotenv = tmp_path / ".env"
    dotenv.write_text(
        "\n".join(
            (
                "ALPACA_API_KEY_ID=dotenv-fixture",
                "ALPACA_API_SECRET_KEY=dotenv-fixture",
                "KRAKEN_SECRET=dotenv-fixture",
                "BINANCE_TESTNET_API_KEY=dotenv-fixture",
                "CAPITAL_EMAIL=dotenv-fixture",
                "NASA_API_KEY=dotenv-replacement",
                "DRY_RUN=false",
            )
        )
        + "\n",
        encoding="utf-8",
    )
    probe = tmp_path / "probe.py"
    probe.write_text(
        "\n".join(
            (
                "import os",
                "from dotenv import load_dotenv",
                "from dotenv.main import DotEnv",
                f"load_dotenv({str(dotenv)!r}, override=True)",
                # Exercise the assignment path directly as python-dotenv 1.0.0
                # does; that release does not honor PYTHON_DOTENV_DISABLED.
                f"DotEnv({str(dotenv)!r}, override=True).set_as_environment_variables()",
                f"aliases = {sorted(EXPECTED_ALIAS_CENSUS)!r}",
                "assert not any(name in os.environ for name in aliases)",
                "assert os.environ['DRY_RUN'] == 'true'",
                "assert os.environ['NASA_API_KEY'] == 'validated-provider'",
                "os.environ['KRAKEN_SECRET'] = 'direct-rehydration'",
                "assert 'KRAKEN_SECRET' not in os.environ",
            )
        )
        + "\n",
        encoding="utf-8",
    )
    environment = dict(os.environ)
    for name in EXPECTED_ALIAS_CENSUS:
        environment.pop(name, None)
    environment.update(
        {
            "PYTHONPATH": str(DIRECTORY),
            boundary.CLOUD_CREDENTIAL_ISOLATION_ENV: "1",
            boundary.PINNED_PROVIDER_ENV_VARS_ENV: "NASA_API_KEY",
            "NASA_API_KEY": "validated-provider",
            # The installed python-dotenv version may ignore this. The guard
            # must still hold, which is what this subprocess proves.
            "PYTHON_DOTENV_DISABLED": "1",
        }
    )
    result = subprocess.run(
        [sys.executable, str(probe)],
        env=environment,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, (result.stdout, result.stderr)
