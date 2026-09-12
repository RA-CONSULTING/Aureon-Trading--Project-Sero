"""Real temporary source/backup transactions; all service operations are fixtures."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path, PurePosixPath

import pytest

TOOL = Path(__file__).parents[1] / "deployment/google-cloud/release_update.py"
spec = importlib.util.spec_from_file_location("release_update", TOOL)
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)
UNIT = "aureon-organ@hnc_core.service"
REVISION = "a" * 40


class Services:
    def __init__(self, units, active=True):
        self.units, self.active, self.enablement, self.events = units, {UNIT: active}, {UNIT: True}, []

    def snapshot(self, unit):
        exists = (self.units / unit).exists()
        return {"exists": exists, "active": self.active.get(unit, False) if exists else False,
                "enabled": self.enablement.get(unit, False) if exists else False}

    def stop(self, unit):
        self.events.append(("stop", unit))
        self.active[unit] = False

    def start(self, unit):
        assert (self.units / unit).exists()
        self.events.append(("start", unit))
        self.active[unit] = True

    def reload(self):
        self.events.append(("reload",))

    def enabled(self, unit, value):
        self.events.append(("enabled", unit, value))
        self.enablement[unit] = value


def fixture(tmp_path, monkeypatch, *, new_file=False):
    workspace, units, bundle, releases = [tmp_path / name for name in ("workspace", "units", "bundle", "releases")]
    for path in (workspace, units, bundle / "files", releases):
        path.mkdir(parents=True)
    source = "aureon_fusion/reader.py"
    target = workspace / source
    target.parent.mkdir(parents=True)
    if not new_file:
        target.write_bytes(b"VALUE = 1\n")
    runtime = workspace / "aureon_fusion/state/approvals.json"
    runtime.parent.mkdir()
    runtime.write_text('{"fixture_approval":"untouched"}')
    (units / UNIT).write_text("original unit\n")
    data = b"VALUE = 2\n"
    payload = bundle / "files" / source
    payload.parent.mkdir(parents=True)
    payload.write_bytes(data)
    manifest = {"schema": release.SCHEMA, "revision": REVISION,
                "release_id": "20260911T230000Z-aaaaaaaa",
                "files": [{"path": source, "sha256": release.digest(data), "size": len(data)}]}
    (bundle / "manifest.json").write_text(json.dumps(manifest))
    renderer = release.render_unit
    # Exercise actual Linux unit generation even while temp filesystem tests run on Windows.
    monkeypatch.setattr(release, "render_unit", lambda unit, root, *args: renderer(unit, PurePosixPath("/srv/aureon/runtime/workspace"), *args))
    services = Services(units)
    return workspace, units, bundle, releases, target, runtime, services


def prepared(tmp_path, monkeypatch, **kwargs):
    workspace, units, bundle, releases, target, runtime, services = fixture(tmp_path, monkeypatch, **kwargs)
    staged = release.prepare(bundle, workspace, releases, units, [UNIT], services)
    return staged, target, runtime, services


def test_success_commits_only_source_and_preserves_runtime(tmp_path, monkeypatch):
    staged, target, runtime, services = prepared(tmp_path, monkeypatch)
    original_runtime = runtime.read_bytes()
    assert target.read_bytes() == b"VALUE = 1\n" and not services.events
    def health(unit, revision):
        assert target.read_bytes() == b"VALUE = 2\n"
        assert services.events[0] == ("enabled", UNIT, False)
        assert services.enablement[UNIT] is False
        assert services.events.index(("stop", UNIT)) < services.events.index(("reload",))
        assert revision == REVISION
    result = release.apply(staged, services, health)
    assert result["phase"] == "committed"
    assert release.check(staged)["phase"] == "committed"
    assert runtime.read_bytes() == original_runtime
    assert result["runtime_state_restored"] is False and result["release_authority"] is False
    assert (staged / "backup/0").read_bytes() == b"VALUE = 1\n"
    assert target.stat().st_uid == json.loads((staged / "journal.json").read_text())["entries"][0]["owner"][0]


def test_failed_health_rolls_source_back_but_keeps_new_runtime(tmp_path, monkeypatch):
    staged, target, runtime, services = prepared(tmp_path, monkeypatch)
    def failure(*args):
        runtime.write_text('{"new_runtime_receipt":"must survive rollback"}')
        raise RuntimeError("fixture health failure")
    with pytest.raises(release.ReleaseError, match="source_rolled_back"):
        release.apply(staged, services, failure)
    assert target.read_bytes() == b"VALUE = 1\n"
    assert "new_runtime_receipt" in runtime.read_text()
    assert services.active[UNIT] is True
    assert release.check(staged)["phase"] == "rolled_back"


def test_failed_new_source_is_removed_without_recursive_cleanup(tmp_path, monkeypatch):
    staged, target, runtime, services = prepared(tmp_path, monkeypatch, new_file=True)
    with pytest.raises(release.ReleaseError, match="source_rolled_back"):
        release.apply(staged, services, lambda *args: (_ for _ in ()).throw(ValueError()))
    assert not target.exists() and runtime.exists()


def test_manifest_tampering_is_refused_before_service_operations(tmp_path, monkeypatch):
    workspace, units, bundle, releases, target, runtime, services = fixture(tmp_path, monkeypatch)
    (bundle / "files/aureon_fusion/reader.py").write_bytes(b"VALUE = 99\n")
    with pytest.raises(release.ReleaseError, match="manifest_hash"):
        release.prepare(bundle, workspace, releases, units, [UNIT], services)
    assert not services.events and target.read_bytes() == b"VALUE = 1\n"


@pytest.mark.parametrize("which", ["target", "staged"])
def test_change_after_prepare_refuses_before_stopping(tmp_path, monkeypatch, which):
    staged, target, runtime, services = prepared(tmp_path, monkeypatch)
    changed = target if which == "target" else staged / "staged/0"
    changed.write_bytes(b"VALUE = 99\n")
    with pytest.raises(release.ReleaseError, match="changed_after_prepare|staged_source_hash"):
        release.apply(staged, services)
    assert services.events == []


def test_interruption_recovery_restores_source_without_replaying_state(tmp_path, monkeypatch):
    staged, target, runtime, services = prepared(tmp_path, monkeypatch)
    journal = json.loads((staged / "journal.json").read_text())
    journal["phase"] = "installing"
    release.save_journal(staged, journal)
    target.write_bytes((staged / "staged/0").read_bytes())
    services.active[UNIT] = False
    runtime.write_text('{"decision":"newer than deployment"}')
    with pytest.raises(release.ReleaseError, match="only_prepared"):
        release.apply(staged, services)
    with pytest.raises(release.ReleaseError, match="interrupted"):
        release.check(staged)
    release.rollback(staged, services)
    assert target.read_bytes() == b"VALUE = 1\n"
    assert "newer than deployment" in runtime.read_text()
    assert services.active[UNIT]


def test_backup_corruption_and_newer_source_block_rollback(tmp_path, monkeypatch):
    staged, target, runtime, services = prepared(tmp_path, monkeypatch)
    release.apply(staged, services, lambda *args: None)
    events = list(services.events)
    target.write_bytes(b"VALUE = 3\n")
    with pytest.raises(release.ReleaseError, match="external_or_newer_source"):
        release.rollback(staged, services)
    assert services.events == events and target.read_bytes() == b"VALUE = 3\n"
    target.write_bytes(b"VALUE = 2\n")
    (staged / "backup/0").write_bytes(b"damaged")
    with pytest.raises(release.ReleaseError, match="backup_hash"):
        release.rollback(staged, services)
    assert services.events == events


def test_explicit_rollback_disables_boot_before_restoring_source(tmp_path, monkeypatch):
    staged, target, runtime, services = prepared(tmp_path, monkeypatch)
    release.apply(staged, services, lambda *args: None)
    services.events.clear()
    release.rollback(staged, services)
    assert services.events[:2] == [("enabled", UNIT, False), ("stop", UNIT)]
    assert services.enablement[UNIT] is True
    assert target.read_bytes() == b"VALUE = 1\n"


@pytest.mark.parametrize("path", [
    "../escape.py", "/root/escape.py", "aureon_fusion/../../escape.py", "aureon_fusion\\escape.py",
    "aureon_fusion/C:/escape.py", "aureon_fusion/state/approvals.json", "aureon-os-upstream/.env",
    "aureon-os-upstream/provider_keys.json", "aureon-os-upstream/brain_predictions_history.json",
    "aureon_fusion/coding_decisions.json", "deployment/elsewhere.py", "aureon_fusion/private/key.txt",
])
def test_unsafe_or_private_paths_are_rejected(path):
    with pytest.raises(release.ReleaseError):
        release.source_path(path)


def test_source_subdirectories_are_not_confused_with_runtime_state():
    for path in ("aureon-os-upstream/frontend/src/state/newsEmotionStore.ts", "aureon-os-upstream/aureon/autonomy/reader.py",
                 "solar_system_collector.py", "real_time_data_feeder.py", "sero_mind/reader.py"):
        assert release.source_path(path) == path


def test_invalid_python_is_not_imported_or_installed(tmp_path, monkeypatch):
    workspace, units, bundle, releases, target, runtime, services = fixture(tmp_path, monkeypatch)
    bad = b"def broken(:\n"
    (bundle / "files/aureon_fusion/reader.py").write_bytes(bad)
    manifest = json.loads((bundle / "manifest.json").read_text())
    manifest["files"][0].update(sha256=release.digest(bad), size=len(bad))
    (bundle / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(SyntaxError):
        release.prepare(bundle, workspace, releases, units, [UNIT], services)
    assert not services.events and target.read_bytes() == b"VALUE = 1\n"


def test_http_units_enforce_all_holds_and_distinct_shims():
    for unit, shim in (("aureon-cloud-operator.service", "cloud_operator.py"), ("aureon-cloud-ui.service", "cloud_ui_gateway.py")):
        body = release.render_unit(unit, PurePosixPath("/srv/aureon/runtime/workspace"), REVISION, "fixture-project", "http-bearer", "7",
                                   "supabase-tenant", "3").decode()
        assert shim in body and "KillMode=control-group" in body
        assert "--secret-version 7" in body and "--revision " + REVISION in body
        for key, value in release.HOLDS.items():
            assert "Environment=" + key + "=" + value in body
        if unit == "aureon-cloud-operator.service":
            assert "--tenant-secret supabase-tenant --tenant-secret-version 3" in body
            for expected in ("AUREON_SUPPRESS_IMPORT_SIDE_EFFECTS=1", "AUREON_AUDIT_MODE=1",
                             "AUREON_LLM_ALLOW_HTTP_IN_AUDIT=1", "AUREON_LLM_REQUEST_TIMEOUT_S=25"):
                assert "Environment=" + expected in body
    with pytest.raises(release.ReleaseError, match="pinned_cloud_secret"):
        release.render_unit("aureon-cloud-ui.service", PurePosixPath("/srv/aureon/runtime/workspace"), REVISION, "fixture-project", "http-bearer", "latest",
                            "supabase-tenant", "3")
    with pytest.raises(release.ReleaseError, match="tenant_secret"):
        release.render_unit("aureon-cloud-operator.service", PurePosixPath("/srv/aureon/runtime/workspace"), REVISION, "fixture-project", "http-bearer", "7")


def test_operator_references_existing_private_config_without_reading_it(monkeypatch):
    monkeypatch.setattr(Path, "is_file", lambda path: path.name == ".env")
    body = release.render_unit("aureon-cloud-operator.service", PurePosixPath("/srv/aureon/runtime/workspace"), REVISION, "fixture-project", "http-bearer", "7",
                               "supabase-tenant", "3").decode()
    assert "Environment=AUREON_ENV_FILE=/srv/aureon/runtime/workspace/aureon_radar/.env" in body
    assert "Environment=AUREON_CLOUD_TRADE_READBACK_PATH=/srv/aureon/cache/trading-control/latest-terminal-receipt.json" in body


def test_terminal_receipt_collector_is_a_distinct_held_service():
    unit = "aureon-cloud-trade-receipt.service"
    body = release.render_unit(unit, PurePosixPath("/srv/aureon/runtime/workspace"), REVISION, "", "", "").decode()
    assert "cloud_trade_receipt_collector.py" in body
    assert "User=aureon" in body and "ReadWritePaths=/srv/aureon/runtime/workspace /srv/aureon/cache" in body
    for key, value in release.HOLDS.items():
        assert "Environment=" + key + "=" + value in body
    release.validate_service_names([unit])


def test_service_names_do_not_allow_foreign_units_or_duplicate_registry_http():
    for names in (["ssh.service"], [UNIT, UNIT], ["aureon-organ@operator_gateway.service"], ["aureon-organ@frontend_vite.service"]):
        with pytest.raises(release.ReleaseError):
            release.validate_service_names(names)


def test_service_identity_is_checked_from_systemd_not_just_unit_name():
    systemd = object.__new__(release.Systemd)
    systemd.workspace = PurePosixPath("/srv/aureon/runtime/workspace")
    systemd.unit_root = PurePosixPath("/etc/systemd/system")
    systemd.allowed = {UNIT}
    def row(user="aureon", launcher="cloud_organ.py"):
        return ("LoadState=loaded\nActiveState=active\nSubState=running\nMainPID=123\nUnitFileState=enabled\nUser=" + user +
                "\nFragmentPath=/etc/systemd/system/aureon-organ@.service\nExecStart=/srv/aureon/venv/bin/python "
                "/srv/aureon/runtime/workspace/deployment/google-cloud/" + launcher + " hnc_core\n")
    systemd.run = lambda *args: row()
    assert systemd.snapshot(UNIT)["active"]
    systemd.run = lambda *args: row(user="root")
    with pytest.raises(release.ReleaseError, match="ownership_unverified"):
        systemd.snapshot(UNIT)
    systemd.run = lambda *args: row(launcher="unrelated.py")
    with pytest.raises(release.ReleaseError, match="ownership_unverified"):
        systemd.snapshot(UNIT)
