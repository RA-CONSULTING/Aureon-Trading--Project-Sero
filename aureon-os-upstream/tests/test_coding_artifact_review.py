from __future__ import annotations

import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from flask import Flask, g, request

from aureon.operator.coding_artifact_review import (
    CodingArtifactReview, ReviewError, current_artifact, register_coding_review_routes,
)

ADMIN = {"authenticated": True, "identity_kind": "admin", "authn_method": "operator_bearer"}


@pytest.fixture
def workspace(tmp_path: Path):
    folder = tmp_path / "frontend/public/aureon_test_artifacts/build-1"
    folder.mkdir(parents=True)
    artifact = folder / "index.html"
    artifact.write_text("<p>artifact version one</p>", encoding="utf-8")
    report = {"schema_version": "aureon-local-capability-forge-v1", "build_id": "build-1", "job_id": "job-1",
              "artifact_manifest": {"title": "Test artifact", "asset_path": str(artifact), "files": [str(artifact)]}}
    state = tmp_path / "state"
    state.mkdir()
    (state / "aureon_capability_forge_last_run.json").write_text(json.dumps(report), encoding="utf-8")
    return tmp_path, artifact, report


def decision(root: Path, *, choice="approve", key="request-test-0001", note=""):
    artifact = current_artifact(root)
    return {key: artifact[key] for key in ("artifact_id", "artifact_version", "artifact_digest")} | {
        "expected_decision_id": None, "decision": choice, "note": note, "request_key": key}


def test_read_is_observational_and_binds_real_file_bytes(workspace):
    root, artifact, _ = workspace
    result = CodingArtifactReview(root).view(ADMIN)
    assert result["available"] and result["can_decide"]
    assert result["artifact"]["files"][0]["size_bytes"] == len(artifact.read_bytes())
    assert not (root / "state/coding_artifact_decisions.sqlite3").exists()
    assert result["execution_authority"] is result["publication_authority"] is False


@pytest.mark.parametrize("choice", ["approve", "reject", "request_revision"])
def test_decisions_commit_and_read_back_across_new_ledger_instances(workspace, choice):
    root, artifact, _ = workspace
    original = artifact.read_bytes()
    payload = decision(root, choice=choice, note="specific revision feedback" if choice == "request_revision" else "")
    result = CodingArtifactReview(root).decide(payload, ADMIN)
    assert result["persisted"] is True and result["replayed"] is False
    receipt = CodingArtifactReview(root).read_receipt(result["receipt"]["receipt_id"], ADMIN)
    assert receipt == result["receipt"]
    assert receipt["decision"] == choice and receipt["authenticated"] is True
    assert receipt["scope"] == "artifact_review_only"
    assert receipt["execution_authority"] is receipt["publication_authority"] is False
    assert artifact.read_bytes() == original
    assert CodingArtifactReview(root).view(ADMIN)["can_decide"] is False


@pytest.mark.parametrize("identity", [{}, {"authenticated": False, "identity_kind": "admin", "authn_method": "operator_bearer"},
    {"authenticated": True, "identity_kind": "tenant", "authn_method": "jwt"},
    {"authenticated": True, "identity_kind": "open", "authn_method": "operator_bearer"}])
def test_identity_required_for_both_reads_and_decisions(workspace, identity):
    root, _, _ = workspace
    ledger = CodingArtifactReview(root)
    for action in (lambda: ledger.view(identity), lambda: ledger.decide(decision(root), identity), lambda: ledger.read_receipt("missingreceipt", identity)):
        with pytest.raises(ReviewError, match="authenticated_operator_required"):
            action()
    assert not ledger.path.exists()


def test_idempotency_replay_is_exact_and_cannot_change_a_decision(workspace):
    root, _, _ = workspace
    payload = decision(root)
    result = CodingArtifactReview(root).decide(payload, ADMIN)
    replay = CodingArtifactReview(root).decide(payload, ADMIN)
    assert replay["replayed"] is True and replay["receipt"] == result["receipt"]
    with pytest.raises(ReviewError, match="idempotency_key_conflict"):
        CodingArtifactReview(root).decide(payload | {"decision": "reject"}, ADMIN)
    with pytest.raises(ReviewError, match="artifact_already_decided"):
        CodingArtifactReview(root).decide(payload | {"request_key": "second-request"}, ADMIN)


@pytest.mark.parametrize("change", ["file", "report"])
def test_stale_artifact_or_report_cannot_receive_a_decision(workspace, change):
    root, artifact, report = workspace
    payload = decision(root)
    if change == "file":
        artifact.write_text("new version of content", encoding="utf-8")
    else:
        report["build_id"] = "build-2"
        (root / "state/aureon_capability_forge_last_run.json").write_text(json.dumps(report), encoding="utf-8")
    with pytest.raises(ReviewError, match="artifact_version_changed"):
        CodingArtifactReview(root).decide(payload, ADMIN)
    assert CodingArtifactReview(root).view(ADMIN)["decision"] is None


def test_conflicting_concurrent_decisions_have_one_winner(workspace):
    root, _, _ = workspace
    first = decision(root)
    def submit(index):
        try:
            return CodingArtifactReview(root).decide(first | {"request_key": f"parallel-request-{index}", "decision": "approve" if index == 0 else "reject"}, ADMIN)
        except ReviewError as exc:
            return exc.code
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(submit, range(2)))
    assert sum(isinstance(value, dict) for value in outcomes) == 1
    assert "artifact_already_decided" in outcomes


def test_lost_ack_retry_reads_the_one_durable_commit(workspace, monkeypatch):
    root, _, _ = workspace
    ledger = CodingArtifactReview(root)
    payload = decision(root)
    monkeypatch.setattr(ledger, "read_receipt", lambda *_: (_ for _ in ()).throw(ReviewError("readback_unavailable", 503)))
    with pytest.raises(ReviewError, match="readback_unavailable"):
        ledger.decide(payload, ADMIN)
    retry = CodingArtifactReview(root).decide(payload, ADMIN)
    assert retry["persisted"] and retry["replayed"]
    with sqlite3.connect(ledger.path) as connection:
        assert connection.execute("SELECT count(*) FROM coding_decisions").fetchone()[0] == 1


def test_revision_note_and_server_owned_identity_fields_are_required(workspace):
    root, _, _ = workspace
    with pytest.raises(ReviewError, match="revision_note_required"):
        CodingArtifactReview(root).decide(decision(root, choice="request_revision"), ADMIN)
    with pytest.raises(ReviewError, match="decision_request_invalid"):
        CodingArtifactReview(root).decide(decision(root) | {"actor": "forged-owner"}, ADMIN)


def test_changed_artifact_gets_a_new_review_without_reusing_old_authority(workspace):
    root, artifact, _ = workspace
    ledger = CodingArtifactReview(root)
    payload = decision(root)
    original = ledger.decide(payload, ADMIN)
    artifact.write_text("new artifact", encoding="utf-8")
    assert ledger.view(ADMIN)["decision"] is None
    assert ledger.view(ADMIN)["can_decide"] is True
    assert ledger.decide(payload, ADMIN)["receipt"] == original["receipt"]  # ACK replay is historical.
    assert ledger.view(ADMIN)["decision"] is None


def test_paths_cannot_escape_the_generated_artifact_area(workspace):
    root, _, report = workspace
    private = root / "state/private.txt"
    private.write_text("not a review artifact")
    report["artifact_manifest"] = {"files": [str(private)]}
    (root / "state/aureon_capability_forge_last_run.json").write_text(json.dumps(report), encoding="utf-8")
    with pytest.raises(ReviewError, match="artifact_path_not_reviewable"):
        current_artifact(root)


def test_receipt_tampering_fails_readback(workspace):
    root, _, _ = workspace
    ledger = CodingArtifactReview(root)
    receipt = ledger.decide(decision(root), ADMIN)["receipt"]
    receipt["decision"] = "reject"
    with sqlite3.connect(ledger.path) as connection:
        connection.execute("UPDATE coding_decisions SET receipt_json=?", (json.dumps(receipt),))
    with pytest.raises(ReviewError, match="decision_receipt_corrupt"):
        ledger.read_receipt(receipt["receipt_id"], ADMIN)


def test_http_routes_guard_identity_and_return_matching_persisted_ack(workspace):
    root, _, _ = workspace
    app = Flask(__name__)
    @app.before_request
    def fixture_identity():
        # Controlled adapter fixture. Production registration uses the existing authenticated gateway.
        g.identity_kind = request.headers.get("X-Test-Identity", "open")
        g.is_admin = g.identity_kind == "admin"
        g.tenant = "fixture-tenant" if g.identity_kind == "tenant" else None
    register_coding_review_routes(app, root=root, decision_available=lambda: True)
    client = app.test_client()
    for kind in ("open", "tenant"):
        assert client.get("/api/coding/artifact-review", headers={"X-Test-Identity": kind}).status_code == 403
        assert client.post("/api/coding/artifact-review/decisions", json=decision(root), headers={"X-Test-Identity": kind}).status_code == 403
    headers = {"X-Test-Identity": "admin"}
    response = client.post("/api/coding/artifact-review/decisions", json=decision(root), headers=headers)
    assert response.status_code == 200
    payload = response.get_json()
    receipt = client.get(f"/api/coding/artifact-review/decisions/{payload['receipt']['receipt_id']}", headers=headers)
    assert receipt.status_code == 200 and receipt.get_json()["receipt"] == payload["receipt"]
    assert receipt.headers["Cache-Control"] == "no-store"
    assert client.post("/api/coding/artifact-review/decisions", json=[], headers=headers).status_code == 400


def test_gateway_must_confirm_dispatch_before_ui_or_post_can_decide(workspace):
    root, _, _ = workspace
    app = Flask(__name__)
    @app.before_request
    def fixture_identity():
        g.identity_kind, g.is_admin, g.tenant = "admin", True, None
    register_coding_review_routes(app, root=root)
    client = app.test_client()
    view = client.get("/api/coding/artifact-review").get_json()
    assert view["available"] is True
    assert view["decision_endpoint_available"] is view["can_decide"] is False
    assert view["decision_hold_reason"] == "protected_ingress_release_unavailable"
    assert client.post("/api/coding/artifact-review/decisions", json=decision(root)).status_code == 503
    assert not CodingArtifactReview(root).path.exists()
