import os

import pytest

from aureon.operator.local_http_profile import initialize, service_environment


@pytest.mark.skipif(os.name != "nt", reason="Windows account DPAPI integration")
def test_encrypted_profile_survives_readback_and_scopes_services(tmp_path):
    path = tmp_path / "http.dpapi"
    initialize(path)
    before = path.read_bytes()
    initialize(path)
    assert path.read_bytes() == before
    base = {"AUREON_DISABLE_REAL_ORDERS": "1", "AUREON_DISABLE_EXCHANGE_MUTATIONS": "1"}
    operator = service_environment("operator_gateway", base, path=path)
    frontend = service_environment("frontend_vite", base, path=path)
    token = operator["AUREON_OPERATOR_API_KEY"]
    assert token == frontend["AUREON_OPERATOR_PROXY_BEARER"]
    assert token.encode() not in before
    assert operator["AUREON_OPERATOR_ENV"] == "production"
    assert operator["AUREON_OPERATOR_HOST"] == "127.0.0.1"
    assert frontend["AUREON_UI_AUTH_MODE"] == "local-operator"
    assert frontend["NODE_ENV"] == "development"
    assert service_environment("frontend_vite", {"NODE_ENV": "production"}, path=path)["NODE_ENV"] == "development"
    assert "AUREON_OPERATOR_API_KEY" not in frontend
    assert "AUREON_OPERATOR_PROXY_BEARER" not in operator
    assert not any(key.startswith("VITE_") for key in frontend)
    assert service_environment("unified_market_trader", base, path=path) == base
    assert operator["AUREON_DISABLE_REAL_ORDERS"] == frontend["AUREON_DISABLE_REAL_ORDERS"] == "1"
    path.write_bytes(before[:-12] + b"invalid-data")
    with pytest.raises(RuntimeError, match="dpapi_failed"):
        service_environment("operator_gateway", base, path=path)


def test_absent_profile_preserves_existing_launch_environment(tmp_path):
    original = {"existing": "preserved"}
    actual = service_environment("operator_gateway", original, path=tmp_path / "missing")
    assert actual == original and actual is not original
    with pytest.raises(RuntimeError, match="commissioned_local_http_profile_missing"):
        service_environment("operator_gateway", original, path=tmp_path / "missing", required=True)
