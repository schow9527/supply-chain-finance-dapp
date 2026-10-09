import pytest

from backend.app import create_app
from backend.config import ProductionConfig, normalize_database_url
from backend.config import TestingConfig
from backend.tests.conftest import assert_safe_test_database_uri


def _valid_production_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost/db")
    monkeypatch.setenv("SECRET_KEY", "a-secure-non-default-secret")
    monkeypatch.setenv("WEB3_PROVIDER_URI", "https://sepolia.example.invalid")
    monkeypatch.setenv("CHAIN_ID", "11155111")


def test_render_postgres_url_is_normalized():
    assert normalize_database_url("postgres://u:p@host/db") == "postgresql://u:p@host/db"


def test_testing_config_ignores_database_environment(monkeypatch):
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql://do-not-connect.invalid/production"
    )
    monkeypatch.setenv(
        "TESTING_DATABASE_URI", "postgresql://do-not-connect.invalid/also_production"
    )
    monkeypatch.setenv(
        "SQLALCHEMY_DATABASE_URI", "postgresql://do-not-connect.invalid/still_production"
    )
    app = create_app(TestingConfig)
    assert app.config["SQLALCHEMY_DATABASE_URI"] == "sqlite+pysqlite:///:memory:"


def test_fixture_guard_rejects_suspicious_postgres_uri():
    with pytest.raises(RuntimeError, match="non-test database"):
        assert_safe_test_database_uri(
            "postgresql://user:password@do-not-connect.invalid/production"
        )


def test_explicit_testing_database_override_is_allowed(tmp_path):
    uri = f"sqlite+pysqlite:///{(tmp_path / 'explicit.sqlite').as_posix()}"
    app = create_app({
        "TESTING": True,
        "ENV_NAME": "testing",
        "SQLALCHEMY_DATABASE_URI": uri,
    })
    assert app.config["SQLALCHEMY_DATABASE_URI"] == uri


def test_production_rejects_sqlite(monkeypatch):
    _valid_production_env(monkeypatch)
    monkeypatch.setenv("DATABASE_URL", "sqlite:///unsafe.db")
    with pytest.raises(RuntimeError, match="must not use SQLite"):
        create_app(ProductionConfig)


def test_production_rejects_default_secret(monkeypatch):
    _valid_production_env(monkeypatch)
    monkeypatch.setenv("SECRET_KEY", "dev-secret-key-sc6113-dapp")
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        create_app(ProductionConfig)


def test_production_rejects_zero_contract(monkeypatch):
    _valid_production_env(monkeypatch)
    monkeypatch.setenv("ROLE_MANAGER_ADDRESS", "0x0000000000000000000000000000000000000000")
    with pytest.raises(RuntimeError, match="RoleManager"):
        create_app(ProductionConfig)


def test_production_rejects_wrong_chain(monkeypatch):
    _valid_production_env(monkeypatch)
    monkeypatch.setenv("CHAIN_ID", "1")
    with pytest.raises(RuntimeError, match="CHAIN_ID"):
        create_app(ProductionConfig)


def test_production_session_cookie_is_secure(monkeypatch):
    _valid_production_env(monkeypatch)
    app = create_app(ProductionConfig)
    assert app.config["SESSION_COOKIE_HTTPONLY"] is True
    assert app.config["SESSION_COOKIE_SECURE"] is True
    assert app.config["SESSION_COOKIE_SAMESITE"] == "Lax"
