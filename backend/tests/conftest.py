import tempfile
from pathlib import Path

import pytest
from sqlalchemy.engine import make_url

from backend.app import create_app
from backend.config import TestingConfig
from backend.extensions import db
from backend.services.blockchain import RoleGrantMismatchError, TxNotFoundError


class FakeRoleService:
    def __init__(self):
        self.roles = {}
        self.verification_error = None
        self.verified = []

    def get_role(self, wallet):
        return self.roles.get(wallet.lower(), "NONE")

    def verify_role_grant(self, tx_hash, account, role):
        self.verified.append((tx_hash, account, role))
        if self.verification_error:
            raise self.verification_error


def assert_safe_test_database_uri(uri: str) -> None:
    """Refuse destructive fixture cleanup against a production-looking DB."""
    url = make_url(uri)
    database = url.database or ""
    if url.get_backend_name() == "sqlite":
        if database in {"", ":memory:"}:
            return
        candidate = Path(database).resolve()
        temp_root = Path(tempfile.gettempdir()).resolve()
        pytest_root = (Path.cwd() / ".pytest-tmp").resolve()
        if candidate.is_relative_to(temp_root) or candidate.is_relative_to(pytest_root):
            return
    elif "_test" in database.lower():
        return
    raise RuntimeError("Refusing destructive test cleanup for a non-test database")


@pytest.fixture()
def app(tmp_path):
    application = create_app({
        "TESTING": True,
        "ENV_NAME": "testing",
        "SQLALCHEMY_DATABASE_URI": "sqlite+pysqlite:///:memory:",
        "UPLOAD_FOLDER": str(tmp_path / "uploads"),
        "ROLE_SERVICE": FakeRoleService(),
        "MAX_CONTENT_LENGTH": 1024 * 1024,
    })
    if application.config.get("TESTING") is not True:
        raise RuntimeError("Test fixture requires TESTING=True")
    assert_safe_test_database_uri(application.config["SQLALCHEMY_DATABASE_URI"])
    with application.app_context():
        db.create_all()
        yield application
        assert_safe_test_database_uri(application.config["SQLALCHEMY_DATABASE_URI"])
        db.session.remove()
        db.drop_all()
        db.engine.dispose()


@pytest.fixture()
def client(app):
    return app.test_client()
