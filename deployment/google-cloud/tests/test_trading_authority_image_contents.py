from __future__ import annotations

import ast
import re
import shlex
from pathlib import Path

GOOGLE_CLOUD = Path(__file__).resolve().parents[1]
BUILD_CONTEXT = GOOGLE_CLOUD / "trading-control"
DOCKERFILE = BUILD_CONTEXT / "Dockerfile"

REVIEWED_IMAGE_FILES = {
    "Dockerfile",
    "requirements.txt",
    "cloud_state.py",
    "contract.py",
    "firestore_ledger.py",
    "live_executor.py",
    "provider_boundary.py",
    "release_controller.py",
    "release_gate.py",
    "service.py",
}
REVIEWED_PYTHON_FILES = {
    name for name in REVIEWED_IMAGE_FILES if name.endswith(".py")
}


def _docker_copy_sources(source: str) -> set[str]:
    copied: set[str] = set()
    logical_lines = re.sub(r"\\\r?\n\s*", " ", source).splitlines()
    for raw in logical_lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        instruction, _, arguments = line.partition(" ")
        assert instruction.upper() != "ADD", "ADD can import unreviewed remote or archive content"
        if instruction.upper() != "COPY":
            continue
        assert not arguments.lstrip().startswith("["), "JSON COPY syntax needs explicit review"
        fields = shlex.split(arguments, posix=True)
        assert len(fields) >= 2
        assert not fields[0].startswith("--from="), "multi-stage COPY needs explicit review"
        copied.update(fields[:-1])
    return copied


def test_trading_authority_image_contains_only_reviewed_runtime_files() -> None:
    dockerfile = DOCKERFILE.read_text(encoding="utf-8")
    copied = _docker_copy_sources(dockerfile)

    assert copied | {"Dockerfile"} == REVIEWED_IMAGE_FILES
    assert not ({".", "./", "*"} & copied)
    for relative in copied:
        path = BUILD_CONTEXT / relative
        assert path.is_file()
        assert not path.is_symlink()
        assert path.resolve().parent == BUILD_CONTEXT.resolve()

    requirements = (BUILD_CONTEXT / "requirements.txt").read_text(encoding="utf-8")
    assert all(
        "==" in line
        and not any(token in line.casefold() for token in ("git+", "file:", "../", "-e "))
        for line in requirements.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    )


def test_trading_authority_image_cannot_import_global_mutation_sources() -> None:
    available_local_modules = {path.stem for path in BUILD_CONTEXT.glob("*.py")}
    copied_local_modules = {Path(name).stem for name in REVIEWED_PYTHON_FILES}

    for name in sorted(REVIEWED_PYTHON_FILES):
        source_path = BUILD_CONTEXT / name
        tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                modules = [node.module or ""]
            else:
                continue
            for module in modules:
                top_level = module.split(".", 1)[0]
                assert top_level not in {
                    "aureon",
                    "imports",
                    "Kings_Accounting_Suite",
                }, f"{name} imports global runtime source {module}"
                if top_level in available_local_modules:
                    assert top_level in copied_local_modules, (
                        f"{name} imports unreviewed local module {module}"
                    )
