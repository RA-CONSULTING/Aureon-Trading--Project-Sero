"""Durable review of the existing forge artifact. No code execution or publication.

ApprovalQueue and SafeCodeControl are deliberately not execution targets here:
their next-item/bounded-log contracts cannot bind an immutable artifact review.
This ledger is the decision record for the forge manifest, not another work queue.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any
from collections.abc import Callable
from contextlib import closing

REVIEW_SCHEMA = "aureon.coding-artifact-review.v1"
RECEIPT_SCHEMA = "aureon.coding-artifact-decision.v1"
REPORT_PATH = Path("state/aureon_capability_forge_last_run.json")
LEDGER_PATH = Path("state/coding_artifact_decisions.sqlite3")
DECISIONS = {"approve", "request_revision", "reject"}
AUTHORITY = {"execution_authority": False, "publication_authority": False}
_SHA = re.compile(r"^[0-9a-f]{64}$")
_KEY = re.compile(r"^[A-Za-z0-9_-]{8,128}$")


class ReviewError(RuntimeError):
    def __init__(self, code: str, status: int = 409):
        super().__init__(code)
        self.code, self.status = code, status


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode()).hexdigest()


def _strict_object(raw: bytes) -> dict[str, Any]:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate key")
            result[key] = value
        return result
    try:
        data = json.loads(raw.decode("utf-8-sig"), object_pairs_hook=pairs,
                          parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite")))
        if not isinstance(data, dict):
            raise ValueError("object required")
        return data
    except (ValueError, UnicodeError) as exc:
        raise ReviewError("artifact_report_invalid", 503) from exc


def _bounded_file(path: Path, limit: int) -> bytes:
    try:
        with path.open("rb") as stream:
            raw = stream.read(limit + 1)
        if len(raw) > limit:
            raise ReviewError("artifact_file_limit_exceeded", 422)
        return raw
    except OSError as exc:
        raise ReviewError("artifact_file_unavailable", 409) from exc


def _source_path(root: Path, value: str) -> Path:
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = root / candidate
    try:
        resolved = candidate.resolve(strict=True)
        relative = resolved.relative_to(root)
    except (OSError, ValueError) as exc:
        raise ReviewError("artifact_path_outside_workspace", 422) from exc
    # Only generated artifact areas; never treat arbitrary repo/credential paths as review files.
    parts = relative.parts
    allowed = len(parts) >= 3 and (parts[0] == "artifacts" or
        (parts[:2] == ("frontend", "public") and len(parts) >= 4 and parts[2].startswith("aureon_")))
    if not allowed or any(part.lower() in {".env", ".git", "credentials", "secrets"} for part in parts) or not resolved.is_file():
        raise ReviewError("artifact_path_not_reviewable", 422)
    return resolved


def current_artifact(root: Path) -> dict[str, Any]:
    """Read the existing private producer report and actual bytes; never execute generators."""
    root = root.resolve()
    source = root / REPORT_PATH
    if not source.is_file():
        raise ReviewError("coding_artifact_not_available", 404)
    if source.is_symlink() or source.resolve().parent != root / "state":
        raise ReviewError("artifact_report_path_invalid", 503)
    raw = _bounded_file(source, 4 * 1024 * 1024)
    report = _strict_object(raw)
    manifest = report.get("artifact_manifest")
    if report.get("schema_version") != "aureon-local-capability-forge-v1" or not isinstance(manifest, dict):
        raise ReviewError("coding_artifact_not_available", 404)
    build_id = report.get("build_id") or manifest.get("build_id")
    artifact_id = report.get("job_id") or report.get("project_id")
    if not all(isinstance(v, str) and 0 < len(v) <= 180 for v in (build_id, artifact_id)):
        raise ReviewError("artifact_version_unavailable", 422)
    declared = manifest.get("files", [])
    if not isinstance(declared, list) or any(not isinstance(item, str) or not item for item in declared):
        raise ReviewError("artifact_manifest_files_invalid", 422)
    paths = set(declared)
    for key, value in manifest.items():
        if key.endswith("_path") and isinstance(value, str) and value:
            paths.add(value)
    if not paths or len(paths) > 256:
        raise ReviewError("artifact_manifest_files_unavailable", 422)
    files = []
    total = 0
    for value in sorted(paths):
        path = _source_path(root, value)
        data = _bounded_file(path, 32 * 1024 * 1024)
        total += len(data)
        if total > 64 * 1024 * 1024:
            raise ReviewError("artifact_bundle_limit_exceeded", 422)
        row = {"path": path.relative_to(root).as_posix(), "sha256": hashlib.sha256(data).hexdigest(), "size_bytes": len(data)}
        if not any(old["path"] == row["path"] for old in files):
            files.append(row)
    report_sha256 = hashlib.sha256(raw).hexdigest()
    if hashlib.sha256(_bounded_file(source, 4 * 1024 * 1024)).hexdigest() != report_sha256:
        raise ReviewError("artifact_changed_during_read")
    files.sort(key=lambda item: item["path"])
    binding = {"artifact_id": artifact_id, "artifact_version": build_id, "report_sha256": report_sha256, "files": files}
    return {**binding, "artifact_digest": _digest(binding), "title": str(manifest.get("title") or report.get("task_family") or artifact_id)[:240],
            "source_report": REPORT_PATH.as_posix(), "review_scope": "manifest_files_and_producer_report", **AUTHORITY}


def require_review_identity(identity: dict[str, Any]) -> dict[str, str]:
    # The instance artifact belongs to the operator plane. 'open' is not authentication.
    if identity.get("identity_kind") != "admin" or identity.get("authenticated") is not True or identity.get("authn_method") != "operator_bearer":
        raise ReviewError("authenticated_operator_required", 403)
    return {"actor_id": "instance_operator", "identity_kind": "admin", "authn_method": "operator_bearer"}


class CodingArtifactReview:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.path = self.root / LEDGER_PATH

    def _connect(self, *, write: bool = False) -> sqlite3.Connection:
        if self.path.is_symlink() or self.path.resolve(strict=False).parent != self.root / "state":
            raise ReviewError("decision_ledger_path_invalid", 503)
        if write:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            connection = sqlite3.connect(self.path, timeout=5, isolation_level=None)
            connection.execute("PRAGMA synchronous=FULL")
            connection.execute("CREATE TABLE IF NOT EXISTS coding_decisions (receipt_id TEXT PRIMARY KEY, request_key TEXT UNIQUE NOT NULL, request_digest TEXT NOT NULL, artifact_id TEXT NOT NULL, artifact_digest TEXT UNIQUE NOT NULL, receipt_json TEXT NOT NULL)")
        else:
            connection = sqlite3.connect(self.path.as_uri() + "?mode=ro", uri=True, timeout=5)
        return connection

    @staticmethod
    def _receipt(raw: str) -> dict[str, Any]:
        value = json.loads(raw)
        core = {key: item for key, item in value.items() if key != "receipt_digest"}
        if value.get("schema") != RECEIPT_SCHEMA or value.get("receipt_digest") != _digest(core) or any(value.get(key) is not False for key in AUTHORITY):
            raise ReviewError("decision_receipt_corrupt", 503)
        return value

    def _latest(self, digest: str) -> dict[str, Any] | None:
        if not self.path.exists():
            return None
        with closing(self._connect()) as connection:
            row = connection.execute("SELECT receipt_json FROM coding_decisions WHERE artifact_digest=?", (digest,)).fetchone()
        return self._receipt(row[0]) if row else None

    def view(self, identity: dict[str, Any]) -> dict[str, Any]:
        actor = require_review_identity(identity)
        try:
            artifact = current_artifact(self.root)
        except ReviewError as exc:
            if exc.status != 404:
                raise
            return {"schema": REVIEW_SCHEMA, "available": False, "reason": exc.code, "artifact": None, "decision": None,
                    "observed_at": time.time(), "actor": actor, **AUTHORITY}
        decision = self._latest(artifact["artifact_digest"])
        return {"schema": REVIEW_SCHEMA, "available": True, "artifact": artifact, "decision": decision,
                "expected_decision_id": decision["receipt_id"] if decision else None,
                "can_decide": decision is None, "observed_at": time.time(), "actor": actor, **AUTHORITY}

    def read_receipt(self, receipt_id: str, identity: dict[str, Any]) -> dict[str, Any]:
        require_review_identity(identity)
        if not _KEY.fullmatch(receipt_id) or not self.path.exists():
            raise ReviewError("decision_receipt_not_found", 404)
        with closing(self._connect()) as connection:
            row = connection.execute("SELECT receipt_json FROM coding_decisions WHERE receipt_id=?", (receipt_id,)).fetchone()
        if not row:
            raise ReviewError("decision_receipt_not_found", 404)
        return self._receipt(row[0])

    def decide(self, body: Any, identity: dict[str, Any]) -> dict[str, Any]:
        actor = require_review_identity(identity)
        fields = {"artifact_id", "artifact_version", "artifact_digest", "expected_decision_id", "decision", "note", "request_key"}
        if not isinstance(body, dict) or set(body) != fields:
            raise ReviewError("decision_request_invalid", 400)
        if not isinstance(body["decision"], str) or body["decision"] not in DECISIONS or not isinstance(body["note"], str) or len(body["note"]) > 2000:
            raise ReviewError("decision_or_note_invalid", 400)
        if body["decision"] == "request_revision" and not body["note"].strip():
            raise ReviewError("revision_note_required", 400)
        if not isinstance(body["request_key"], str) or not _KEY.fullmatch(body["request_key"]) or not isinstance(body["artifact_digest"], str) or not _SHA.fullmatch(body["artifact_digest"]):
            raise ReviewError("decision_binding_invalid", 400)
        request_digest = _digest({"request": body, "actor": actor})
        connection = self._connect(write=True)
        replayed = False
        try:
            connection.execute("BEGIN IMMEDIATE")
            old = connection.execute("SELECT request_digest,receipt_json FROM coding_decisions WHERE request_key=?", (body["request_key"],)).fetchone()
            if old:
                if old[0] != request_digest:
                    raise ReviewError("idempotency_key_conflict")
                receipt = self._receipt(old[1])
                replayed = True
            else:
                artifact = current_artifact(self.root)
                if any(body[key] != artifact[key] for key in ("artifact_id", "artifact_version", "artifact_digest")):
                    raise ReviewError("artifact_version_changed")
                prior = connection.execute("SELECT receipt_id FROM coding_decisions WHERE artifact_digest=?", (artifact["artifact_digest"],)).fetchone()
                if body["expected_decision_id"] is not None or prior:
                    raise ReviewError("artifact_already_decided")
                core = {"schema": RECEIPT_SCHEMA, "receipt_id": uuid.uuid4().hex, "request_key": body["request_key"],
                        "request_digest": request_digest, "artifact": artifact, "decision": body["decision"], "note": body["note"].strip(),
                        "recorded_at": time.time(), "actor": actor, "authenticated": True,
                        "scope": "artifact_review_only", **AUTHORITY}
                receipt = {**core, "receipt_digest": _digest(core)}
                # Detect changes while checking the package, before committing a decision.
                if current_artifact(self.root)["artifact_digest"] != artifact["artifact_digest"]:
                    raise ReviewError("artifact_changed_during_decision")
                connection.execute("INSERT INTO coding_decisions VALUES (?,?,?,?,?,?)", (receipt["receipt_id"], body["request_key"], request_digest,
                    artifact["artifact_id"], artifact["artifact_digest"], _canonical(receipt)))
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
        # ACK requires a separately opened durable read; failed ACK can be retried with the same key.
        persisted = self.read_receipt(receipt["receipt_id"], identity)
        if persisted != receipt:
            raise ReviewError("decision_readback_mismatch", 503)
        return {"ok": True, "persisted": True, "replayed": replayed, "receipt": persisted, **AUTHORITY}


def register_coding_review_routes(app: Any, *, root: Path | None = None, decision_available: Callable[[], bool] | None = None) -> None:
    """Register after normal operator identity/ingress middleware; never bypass either."""
    from flask import g, jsonify, request
    ledger = CodingArtifactReview(root or Path(__file__).resolve().parents[2])

    def identity() -> dict[str, Any]:
        admin = getattr(g, "identity_kind", None) == "admin" and getattr(g, "is_admin", False) is True and getattr(g, "tenant", None) is None
        return {"authenticated": admin, "identity_kind": getattr(g, "identity_kind", None), "authn_method": "operator_bearer" if admin else None}

    def respond(action: Any):
        try:
            payload, status = action(), 200
        except ReviewError as exc:
            payload, status = {"ok": False, "error": exc.code, **AUTHORITY}, exc.status
        except (sqlite3.Error, OSError, ValueError, TypeError):
            payload, status = {"ok": False, "error": "decision_store_unavailable", **AUTHORITY}, 503
        response = jsonify(payload)
        response.status_code = status
        response.headers["Cache-Control"] = "no-store"
        return response

    def available() -> bool:
        # The registering gateway owns its release capability. Authentication is not dispatch.
        return decision_available is not None and decision_available() is True

    def view() -> dict[str, Any]:
        payload = ledger.view(identity())
        enabled = available()
        return {**payload, "decision_endpoint_available": enabled,
                "can_decide": payload.get("can_decide", False) and enabled,
                "decision_hold_reason": None if enabled else "protected_ingress_release_unavailable"}

    def decide() -> dict[str, Any]:
        actor = identity()
        require_review_identity(actor)
        if not available():
            raise ReviewError("protected_ingress_release_unavailable", 503)
        return ledger.decide(request.get_json(silent=True), actor)

    @app.get("/api/coding/artifact-review")
    def coding_artifact_review_get():
        return respond(view)

    @app.get("/api/coding/artifact-review/decisions/<receipt_id>")
    def coding_artifact_decision_get(receipt_id: str):
        return respond(lambda: {"ok": True, "persisted": True, "receipt": ledger.read_receipt(receipt_id, identity()), **AUTHORITY})

    @app.post("/api/coding/artifact-review/decisions")
    def coding_artifact_decision_post():
        return respond(decide)
