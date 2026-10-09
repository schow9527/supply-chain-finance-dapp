"""Environment configuration and production safety checks."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
DEPLOYMENT_FILE = BASE_DIR / "contracts" / "deployments" / "11155111.json"
DEFAULT_SECRET_KEY = "dev-secret-key-sc6113-dapp"
EXAMPLE_SECRET_KEY = "replace-with-a-long-random-secret"
ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"
CONTRACT_NAMES = (
    "RoleManager",
    "ReceivableToken",
    "InvoiceRegistry",
    "FinancingPool",
    "MockStablecoin",
)

load_dotenv(BASE_DIR / ".env", override=False)


def _deployment() -> dict[str, Any]:
    try:
        return json.loads(DEPLOYMENT_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {}


def normalize_database_url(value: str) -> str:
    if value.startswith("postgres://"):
        return "postgresql://" + value[len("postgres://") :]
    return value


def _contract_env_name(name: str) -> str:
    chars = []
    for index, char in enumerate(name):
        if char.isupper() and index:
            chars.append("_")
        chars.append(char.upper())
    return "".join(chars) + "_ADDRESS"


class Config:
    ENV_NAME = "development"
    DEBUG = False
    TESTING = False
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    ALLOWED_EXTENSIONS = {"pdf"}
    CORS_RESOURCES = {r"/api/*": {"origins": "*"}}
    RPC_HEALTHCHECK_ENABLED = False
    RPC_HEALTHCHECK_TIMEOUT = 2

    @classmethod
    def init_app(cls, app) -> None:
        deployment = _deployment()
        default_db = f"sqlite:///{(BASE_DIR / 'scf_dapp.db').as_posix()}"
        app.config.update(
            SECRET_KEY=os.getenv("SECRET_KEY", DEFAULT_SECRET_KEY),
            SQLALCHEMY_DATABASE_URI=normalize_database_url(
                os.getenv("DATABASE_URL", default_db)
            ),
            UPLOAD_FOLDER=os.getenv("UPLOAD_FOLDER", str(BASE_DIR / "uploads")),
            WEB3_PROVIDER_URI=os.getenv("WEB3_PROVIDER_URI", ""),
            CHAIN_ID=int(os.getenv("CHAIN_ID", deployment.get("chainId", 11155111))),
            START_BLOCK=int(os.getenv("START_BLOCK", deployment.get("startBlock", 0))),
        )
        addresses = {}
        for name in CONTRACT_NAMES:
            env_name = _contract_env_name(name)
            address = os.getenv(env_name, deployment.get(name, ZERO_ADDRESS))
            app.config[env_name] = address
            addresses[name] = address
        app.config["CONTRACT_ADDRESSES"] = addresses


class DevelopmentConfig(Config):
    ENV_NAME = "development"
    DEBUG = True


class TestingConfig(Config):
    ENV_NAME = "testing"
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite+pysqlite:///:memory:"
    WTF_CSRF_ENABLED = False

    @classmethod
    def init_app(cls, app) -> None:
        super().init_app(app)
        # Never inherit a database URL from the shell/CI in tests.  Tests that
        # need a file database must pass it explicitly to create_app({...}).
        app.config["SQLALCHEMY_DATABASE_URI"] = cls.SQLALCHEMY_DATABASE_URI
        app.config["WEB3_PROVIDER_URI"] = "test://disabled"
        app.config["RPC_HEALTHCHECK_ENABLED"] = False


class ProductionConfig(Config):
    ENV_NAME = "production"
    RPC_HEALTHCHECK_ENABLED = True

    @classmethod
    def init_app(cls, app) -> None:
        super().init_app(app)
        database_url = os.getenv("DATABASE_URL", "")
        if database_url:
            app.config["SQLALCHEMY_DATABASE_URI"] = normalize_database_url(database_url)


CONFIGS = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}


def configure_app(app, config_object=None) -> None:
    if config_object is None:
        environment = os.getenv("APP_ENV", os.getenv("FLASK_ENV", "development")).lower()
        config_class = CONFIGS.get(environment, DevelopmentConfig)
    elif isinstance(config_object, str):
        config_class = CONFIGS.get(config_object.lower())
        if config_class is None:
            raise ValueError(f"Unknown application environment: {config_object}")
    else:
        config_class = config_object

    if isinstance(config_class, dict):
        base_config = TestingConfig if config_class.get("TESTING") else DevelopmentConfig
        app.config.from_object(base_config)
        base_config.init_app(app)
        app.config.update(config_class)
    else:
        app.config.from_object(config_class)
        init_app = getattr(config_class, "init_app", None)
        if init_app:
            init_app(app)

    app.config["SQLALCHEMY_DATABASE_URI"] = normalize_database_url(
        app.config["SQLALCHEMY_DATABASE_URI"]
    )
    if app.config.get("ENV_NAME") == "production":
        validate_production_config(app.config)


def validate_production_config(config) -> None:
    errors = []
    database_url = config.get("SQLALCHEMY_DATABASE_URI", "")
    if not os.getenv("DATABASE_URL"):
        errors.append("DATABASE_URL is required")
    elif database_url.startswith("sqlite"):
        errors.append("DATABASE_URL must not use SQLite")
    if config.get("SECRET_KEY") in {None, "", DEFAULT_SECRET_KEY, EXAMPLE_SECRET_KEY}:
        errors.append("SECRET_KEY must be changed from the default")
    if not config.get("WEB3_PROVIDER_URI"):
        errors.append("WEB3_PROVIDER_URI is required")
    if config.get("CHAIN_ID") != 11155111:
        errors.append("CHAIN_ID must be 11155111")
    invalid_contracts = [
        name
        for name, address in config.get("CONTRACT_ADDRESSES", {}).items()
        if not address or address.lower() == ZERO_ADDRESS
    ]
    if invalid_contracts:
        errors.append("contract addresses must be non-zero: " + ", ".join(invalid_contracts))
    if errors:
        raise RuntimeError("Invalid production configuration: " + "; ".join(errors))
