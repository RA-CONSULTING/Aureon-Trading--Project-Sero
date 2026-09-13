"""The tenant health route must not borrow service-role authority."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = ROOT / "supabase" / "functions" / "backend-health-check" / "index.ts"


def test_backend_health_check_is_a_fixed_no_mutation_unavailable_response() -> None:
    source = SOURCE_PATH.read_text(encoding="utf-8")

    assert "PRIVILEGED_HEALTH_CHECK_DISABLED" in source
    assert "status: 503" in source
    assert "requiredPath: 'governed_operator_health'" in source
    assert "mutationAuthority: false" in source
    assert "providerCallsAttempted: 0" in source
    assert "secretPresenceDisclosed: false" in source
    assert "Deno.env.get" not in source
    assert "createClient" not in source
    assert "await req.json" not in source
    assert "functions.invoke" not in source
    assert "fetch(" not in source
    assert "SUPABASE_SERVICE_ROLE_KEY" not in source
    assert "sync-harmonic-nexus" not in source
    assert "MASTER_ENCRYPTION_KEY" not in source


def test_frontend_does_not_poll_the_retired_privileged_health_route() -> None:
    source = (ROOT / "frontend" / "src" / "hooks" / "useBackendHealth.ts").read_text(encoding="utf-8")

    assert "backend-health-check" not in source
    assert "functions.invoke" not in source
    assert "mutationAuthority: false" in source
    assert "providerCallsAttempted: 0" in source
    assert "secretPresenceDisclosed: false" in source
