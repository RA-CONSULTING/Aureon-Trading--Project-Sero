"""Exercise production HTTP selection without starting any runtime or listener."""
import builtins
import sys
from types import SimpleNamespace

import pytest

from aureon.operator.security import SecurityConfig


@pytest.mark.parametrize("rate", ["nan", "inf", "-inf", "-1"])
@pytest.mark.parametrize("environment", ["development", "production"])
def test_invalid_rate_cannot_disable_or_invalidate_limiter(monkeypatch, rate, environment):
    monkeypatch.setenv("AUREON_OPERATOR_ENV", environment)
    monkeypatch.setenv("AUREON_OPERATOR_API_KEY", "offline-test-key")
    monkeypatch.setenv("AUREON_OPERATOR_RATE_RPS", rate)
    with pytest.raises(ValueError, match="must be finite and >= 0"):
        SecurityConfig.from_env()


@pytest.fixture
def startup(monkeypatch):
    from aureon.operator import operator_server as server

    for name in tuple(__import__("os").environ):
        if name.startswith("AUREON_OPERATOR_"):
            monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("AUREON_OPERATOR_ENV", "production")
    monkeypatch.setenv("AUREON_OPERATOR_API_KEY", "offline-test-key")
    monkeypatch.setattr(server, "_load_env_file", lambda: None)
    monkeypatch.setattr(server, "build_provider_set", lambda: [])
    monkeypatch.setattr(server, "describe_provider_set", lambda _: "offline fixture")
    calls = []
    app = SimpleNamespace(run=lambda **kw: calls.append(("flask", kw)))

    def build():
        calls.append(("build", {}))
        return app

    monkeypatch.setattr(server, "build_boot_app", build)
    return server, calls, app


def missing_waitress(monkeypatch):
    real_import = builtins.__import__

    def load(name, *args, **kwargs):
        if name == "waitress":
            raise ImportError("offline missing dependency")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", load)


def test_production_missing_waitress_does_not_build_runtime_or_fall_back(monkeypatch, startup):
    server, calls, _ = startup
    missing_waitress(monkeypatch)
    with pytest.raises(RuntimeError, match="production_operator_requires_waitress"):
        server.main()
    assert calls == []


def test_production_explicit_dev_server_fails_before_runtime_build(monkeypatch, startup):
    server, calls, _ = startup
    monkeypatch.setenv("AUREON_OPERATOR_DEV", "1")
    with pytest.raises(RuntimeError, match="production_operator_cannot_use_flask"):
        server.main()
    assert calls == []


def test_production_selects_waitress_with_validated_bindings(monkeypatch, startup):
    server, calls, app = startup
    monkeypatch.setitem(sys.modules, "waitress", SimpleNamespace(
        serve=lambda target, **kw: calls.append(("waitress", (target, kw)))
    ))
    server.main()
    assert calls == [("build", {}), ("waitress", (app, {
        "host": "127.0.0.1", "port": 8080, "threads": 8,
    }))]


def test_development_without_waitress_retains_explicit_local_fallback(monkeypatch, startup):
    server, calls, _ = startup
    monkeypatch.setenv("AUREON_OPERATOR_ENV", "development")
    missing_waitress(monkeypatch)
    server.main()
    assert calls == [("build", {}), ("flask", {
        "host": "127.0.0.1", "port": 8080, "threaded": True,
    })]


def test_invalid_http_worker_count_does_not_build_runtime(monkeypatch, startup):
    server, calls, _ = startup
    monkeypatch.setenv("AUREON_OPERATOR_THREADS", "0")
    monkeypatch.setitem(sys.modules, "waitress", SimpleNamespace(serve=lambda *a, **kw: None))
    with pytest.raises(ValueError, match="AUREON_OPERATOR_THREADS"):
        server.main()
    assert calls == []


def test_import_error_while_serving_cannot_start_second_server(monkeypatch, startup):
    server, calls, _ = startup

    def serve(*args, **kwargs):
        raise ImportError("failure inside HTTP serving")

    monkeypatch.setitem(sys.modules, "waitress", SimpleNamespace(serve=serve))
    with pytest.raises(ImportError, match="failure inside HTTP serving"):
        server.main()
    assert calls == [("build", {})]
