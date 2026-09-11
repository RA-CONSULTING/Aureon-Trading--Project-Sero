import importlib.util
import json
from pathlib import Path
import sys

import pytest

DIRECTORY = Path(__file__).parents[1] / "deployment/google-cloud"
sys.path.insert(0, str(DIRECTORY))
spec = importlib.util.spec_from_file_location("build_release_bundle", DIRECTORY / "build_release_bundle.py")
bundle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bundle)


def test_explicit_bundle_keeps_private_files_out_and_binds_reviewed_hash(tmp_path):
    source = tmp_path / "source"
    (source / "aureon_fusion/state").mkdir(parents=True)
    code = source / "aureon_fusion/reader.py"
    code.write_bytes(b"VALUE = 1\n")
    private = source / "aureon_fusion/state/approval.json"
    private.write_text('{"private fixture":"must not travel"}')
    selected = [{"path": "aureon_fusion/reader.py", "sha256": bundle.digest(code.read_bytes())}]
    out = tmp_path / "bundle"
    manifest = bundle.build(source, selected, out, "a" * 40, "20260911T230000Z-aaaaaaaa")
    assert len(manifest["files"]) == 1
    assert (out / "files/aureon_fusion/reader.py").read_bytes() == code.read_bytes()
    assert not (out / "files/aureon_fusion/state").exists()
    assert json.loads((out / "manifest.json").read_text())["contains_runtime_state"] is False
    code.write_bytes(b"VALUE = 2\n")
    with pytest.raises(bundle.ReleaseError, match="reviewed_source_hash_changed"):
        bundle.build(source, selected, tmp_path / "second", "a" * 40, "20260911T230001Z-aaaaaaaa")
    assert not (tmp_path / "second").exists()


def test_no_bundle_overwrite_or_runtime_selection(tmp_path):
    source = tmp_path / "source"
    (source / "aureon_fusion").mkdir(parents=True)
    with pytest.raises(bundle.ReleaseError, match="runtime_or_private"):
        bundle.build(source, ["aureon_fusion/state/approval.json"], tmp_path / "out", "a" * 40, "20260911T230000Z-aaaaaaaa")
    assert not (tmp_path / "out").exists()
    with pytest.raises(bundle.ReleaseError, match="destination_must_be_new"):
        bundle.build(source, ["aureon_fusion/reader.py"], source, "a" * 40, "20260911T230000Z-aaaaaaaa")
