import pytest

from backend.app import create_app
from backend.config import ProductionConfig, normalize_database_url, validate_production_config
from backend.config import TestingConfig
from backend.tests.conftest import assert_safe_test_database_uri


def _valid_production_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost/db")
    monkeypatch.setenv("SECRET_KEY", "a-secure-non-default-secret")
    monkeypatch.setenv("WEB3_PROVIDER_URI", "https://sepolia.example.invalid")
    monkeypatch.setenv("CHAIN_ID", "11155111")
    monkeypatch.setenv("STORAGE_BACKEND", "s3")
    monkeypatch.setenv("S3_BUCKET", "private-test-bucket")
    monkeypatch.setenv("S3_ACCESS_KEY_ID", "test-access")
    monkeypatch.setenv("S3_SECRET_ACCESS_KEY", "test-secret")


def test_render_postgres_url_is_normalized():
    assert normalize_database_url("postgres://u:p@host/db") == "postgresql+psycopg://u:p@host/db"
    assert normalize_database_url("postgresql://u:p@host/db") == "postgresql+psycopg://u:p@host/db"
    assert normalize_database_url("postgresql+psycopg://u:p@host/db") == "postgresql+psycopg://u:p@host/db"


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
    with pytest.raises(RuntimeError, match="must use PostgreSQL"):
        create_app(ProductionConfig)


def test_production_rejects_missing_s3_credentials(monkeypatch):
    _valid_production_env(monkeypatch)
    monkeypatch.delenv("S3_SECRET_ACCESS_KEY")
    with pytest.raises(RuntimeError, match="S3_SECRET_ACCESS_KEY"):
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


def test_production_rejects_local_storage(monkeypatch):
    _valid_production_env(monkeypatch)
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    with pytest.raises(RuntimeError, match="must not be local"):
        create_app(ProductionConfig)


def test_production_allows_render_disk_without_s3_credentials(monkeypatch, tmp_path):
    _valid_production_env(monkeypatch)
    monkeypatch.setenv("STORAGE_BACKEND", "render_disk")
    monkeypatch.setenv("RENDER_DISK_MOUNT_PATH", str(tmp_path))
    monkeypatch.setenv("UPLOAD_FOLDER", str(tmp_path))
    monkeypatch.delenv("S3_BUCKET")
    monkeypatch.delenv("S3_ACCESS_KEY_ID")
    monkeypatch.delenv("S3_SECRET_ACCESS_KEY")
    app = create_app(ProductionConfig)
    assert app.config["STORAGE_BACKEND"] == "render_disk"


def test_production_render_disk_rejects_relative_and_outside_paths(monkeypatch, tmp_path):
    _valid_production_env(monkeypatch)
    monkeypatch.setenv("STORAGE_BACKEND", "render_disk")
    monkeypatch.setenv("RENDER_DISK_MOUNT_PATH", "relative")
    monkeypatch.setenv("UPLOAD_FOLDER", "relative")
    with pytest.raises(RuntimeError, match="absolute"):
        create_app(ProductionConfig)
    monkeypatch.setenv("RENDER_DISK_MOUNT_PATH", str(tmp_path / "mount"))
    monkeypatch.setenv("UPLOAD_FOLDER", str(tmp_path / "outside"))
    with pytest.raises(RuntimeError, match="inside"):
        create_app(ProductionConfig)


def test_production_render_disk_requires_one_web_instance(monkeypatch, tmp_path):
    _valid_production_env(monkeypatch)
    monkeypatch.setenv("STORAGE_BACKEND", "render_disk")
    monkeypatch.setenv("RENDER_DISK_MOUNT_PATH", str(tmp_path))
    monkeypatch.setenv("UPLOAD_FOLDER", str(tmp_path))
    monkeypatch.setenv("WEB_INSTANCE_COUNT", "2")
    with pytest.raises(RuntimeError, match="exactly one"):
        create_app(ProductionConfig)


def test_production_worker_does_not_require_pdf_storage(monkeypatch):
    _valid_production_env(monkeypatch)
    monkeypatch.setenv("PROCESS_ROLE", "worker")
    monkeypatch.setenv("EVENT_SYNC_ENABLED", "true")
    monkeypatch.setenv("STORAGE_BACKEND", "disabled")
    monkeypatch.delenv("RENDER_DISK_MOUNT_PATH", raising=False)
    monkeypatch.delenv("UPLOAD_FOLDER", raising=False)
    app = create_app(ProductionConfig)
    assert app.config["PROCESS_ROLE"] == "worker"


def test_production_rejects_missing_rpc(monkeypatch):
    _valid_production_env(monkeypatch)
    monkeypatch.delenv("WEB3_PROVIDER_URI")
    with pytest.raises(RuntimeError, match="WEB3_PROVIDER_URI"):
        create_app(ProductionConfig)


@pytest.mark.parametrize("field,value,message", [
    ("DEBUG", True, "DEBUG"),
    ("TESTING", True, "TESTING"),
    ("ENABLE_ROLE_SIMULATOR", True, "role simulator"),
    ("EVENT_SYNC_ENABLED", True, "web process"),
])
def test_production_rejects_unsafe_runtime_flags(monkeypatch, field, value, message):
    _valid_production_env(monkeypatch)
    app = create_app(ProductionConfig)
    config = dict(app.config)
    config[field] = value
    with pytest.raises(RuntimeError, match=message):
        validate_production_config(config)
