from pathlib import Path


ROOT = Path(__file__).parents[1]
PYTHON_BASE = (
    "python:3.12-slim-bookworm@"
    "sha256:782412e85d0f0984994c290652577d4018aff08145c85b262bb63dc0c7522254"
)


def _allowed(context: Path) -> set[str]:
    return {
        line[1:]
        for line in (context / ".gcloudignore").read_text(encoding="utf-8").splitlines()
        if line.startswith("!")
    }


def test_public_entry_upload_closure_includes_only_docker_inputs():
    context = ROOT / "public-entry"
    assert _allowed(context) == {
        "Dockerfile",
        "requirements.txt",
        "public_entry.py",
        "bridge-cert.pem",
    }
    assert (context / ".gcloudignore").read_text(encoding="utf-8").splitlines().count("**") == 1
    assert (context / "Dockerfile").read_text(encoding="utf-8").splitlines()[0] == f"FROM {PYTHON_BASE}"


def test_trading_authority_upload_closure_matches_docker_copy_set():
    context = ROOT / "trading-control"
    assert _allowed(context) == {
        "Dockerfile",
        "requirements.txt",
        "contract.py",
        "service.py",
        "firestore_ledger.py",
        "provider_boundary.py",
        "live_executor.py",
        "cloud_state.py",
        "release_gate.py",
        "release_controller.py",
    }
    assert (context / ".gcloudignore").read_text(encoding="utf-8").splitlines().count("**") == 1
    assert (context / "Dockerfile").read_text(encoding="utf-8").splitlines()[0] == f"FROM {PYTHON_BASE}"
