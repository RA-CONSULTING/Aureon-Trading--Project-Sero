from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1] / "trading-control"
sys.path.insert(0, str(ROOT))
from contract import digest  # noqa: E402
from release_gate import LIVE_CONTROLS, RELEASE_SCHEMA, ReleaseGate  # noqa: E402


KEY = "projects/aureon-trading/locations/europe-west1/keyRings/aureon-trading-prod/cryptoKeys/aureon-controller-signing/cryptoKeyVersions/1"


class Verifier:
    def verify(self, key_version, data, signature):
        assert key_version == KEY and data and signature == "signature"


class Store:
    def __init__(self, value):
        self.value = value

    def read_release(self):
        return self.value


def state(*, active=True):
    return {
        "schema": RELEASE_SCHEMA, "state": "active" if active else "held",
        "generation": 1, "request_id": "1" * 64,
        "requested_controls_sha256": digest(LIVE_CONTROLS),
        "authorization_event_sha256": "2" * 64,
        "authorization_expires_at_ms": 1_200_000,
        "probe_receipt_sha256": "3" * 64,
        "provider_readback_sha256": "4" * 64,
        "source_revision": "5" * 40, "signed_at_ms": 1_000_000,
        "controller_key_version": KEY, "signature": "signature",
        "update_time": "2026-09-12T20:00:00Z",
    }


def intent():
    return {
        "expires_at_ms": 1_010_000,
        "authorization": {"event_sha256": "2" * 64, "expires_at_ms": 1_200_000},
    }


def test_active_signed_state_releases_only_matching_lease():
    gate = ReleaseGate(KEY, Verifier(), "5" * 40, Store(state()))
    assert gate.is_active(intent(), now_ms=1_000_000) is True
    changed = intent()
    changed["authorization"]["event_sha256"] = "9" * 64
    assert gate.is_active(changed, now_ms=1_000_000) is False


def test_held_or_expired_state_fails_closed():
    assert ReleaseGate(KEY, Verifier(), "5" * 40, Store(state(active=False))).is_active(intent(), now_ms=1_000_000) is False
    assert ReleaseGate(KEY, Verifier(), "5" * 40, Store(state())).is_active(intent(), now_ms=1_300_000) is False
