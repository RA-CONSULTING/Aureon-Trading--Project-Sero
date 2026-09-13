"""Tenant shells must not poll instance-only operator routes."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_shell_gates_every_instance_status_component_on_admin_identity() -> None:
    source = (ROOT / "frontend/src/shell/ShellLayout.tsx").read_text(encoding="utf-8")

    assert "identity.isAdmin && <LiveVitals />" in source
    assert "identity.isAdmin && <BackendStatusBanner />" in source
    assert "identity.isAdmin ? <StatusIndicator />" in source
    assert "Private account workspace" in source


def test_instance_status_components_use_only_instance_routes() -> None:
    live_vitals = (ROOT / "frontend/src/components/LiveVitals.tsx").read_text(encoding="utf-8")
    backend_banner = (ROOT / "frontend/src/components/BackendStatusBanner.tsx").read_text(encoding="utf-8")
    pulse = (ROOT / "frontend/src/hooks/useOperatorPulse.ts").read_text(encoding="utf-8")

    assert "useOperatorPulse" in live_vitals
    assert "useOperatorPulse" in backend_banner
    assert "/api/pulse" in pulse
