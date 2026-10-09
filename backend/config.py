"""Environment configuration and production safety checks."""

from __future__ import annotations

import json
import os
from datetime import timedelta
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from sqlalchemy.engine import make_url

from backend.services.addresses import ContractAddressError, canonical_address

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
        return "postgresql+psycopg://" + value[len("postgres://") :]
    if value.startswith("postgresql://"):
        return "postgresql+psycopg://" + value[len("postgresql://") :]
    return value


def positive_int_env(name: str, default: int) -> int:
    raw = os.getenv(name, str(default))
    try:
        value = int(raw)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"{name} must be a positive integer") from exc
    if value <= 0:
        raise RuntimeError(f"{name} must be a positive integer")
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
    NONCE_TTL_SECONDS = 300
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=30)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = False
    BLOCK_CONFIRMATIONS = 1
    SYNC_POLL_INTERVAL = 5
    EVENT_SYNC_BATCH_SIZE = 10
    REORG_LOOKBACK = 12
    EVENT_SYNC_ENABLED = False
    STORAGE_BACKEND = "local"
    ENABLE_ROLE_SIMULATOR = False
    PROCESS_ROLE = "web"

    @classmethod
    def init_app(cls, app) -> None:
        deployment = _deployment()
        default_db = f"sqlite:///{(BASE_DIR / 'scf_dapp.db').as_posix()}"
        process_role = os.getenv("PROCESS_ROLE", os.getenv("PROCESS_TYPE", "web")).lower()
        app.config.update(
            SECRET_KEY=os.getenv("SECRET_KEY", DEFAULT_SECRET_KEY),
            SQLALCHEMY_DATABASE_URI=normalize_database_url(
                os.getenv("DATABASE_URL", default_db)
            ),
            UPLOAD_FOLDER=os.getenv("UPLOAD_FOLDER", str(BASE_DIR / "uploads")),
            WEB3_PROVIDER_URI=os.getenv("WEB3_PROVIDER_URI", ""),
            CHAIN_ID=int(os.getenv("CHAIN_ID", deployment.get("chainId", 11155111))),
            START_BLOCK=int(os.getenv("START_BLOCK", deployment.get("startBlock", 0))),
            BLOCK_CONFIRMATIONS=int(os.getenv("BLOCK_CONFIRMATIONS", 1)),
            SYNC_START_BLOCK=int(
                os.getenv("SYNC_START_BLOCK", deployment.get("startBlock", 0))
            ),
            SYNC_POLL_INTERVAL=int(os.getenv("SYNC_POLL_INTERVAL", 5)),
            EVENT_SYNC_BATCH_SIZE=positive_int_env("EVENT_SYNC_BATCH_SIZE", 10),
            REORG_LOOKBACK=int(os.getenv("REORG_LOOKBACK", 12)),
            EVENT_SYNC_ENABLED=os.getenv("EVENT_SYNC_ENABLED", "false").lower()
            in {"1", "true", "yes"},
            STORAGE_BACKEND=os.getenv("STORAGE_BACKEND", "local").lower(),
            S3_ENDPOINT_URL=os.getenv("S3_ENDPOINT_URL", ""),
            S3_REGION=os.getenv("S3_REGION", "us-east-1"),
            S3_BUCKET=os.getenv("S3_BUCKET", ""),
            S3_ACCESS_KEY_ID=os.getenv("S3_ACCESS_KEY_ID", ""),
            S3_SECRET_ACCESS_KEY=os.getenv("S3_SECRET_ACCESS_KEY", ""),
            S3_KEY_PREFIX=os.getenv("S3_KEY_PREFIX", ""),
            RENDER_DISK_MOUNT_PATH=os.getenv("RENDER_DISK_MOUNT_PATH", ""),
            RENDER_DISK_MIN_FREE_BYTES=int(
                os.getenv("RENDER_DISK_MIN_FREE_BYTES", 100 * 1024 * 1024)
            ),
            PROCESS_ROLE=process_role,
            # Compatibility for existing deployments; PROCESS_ROLE is canonical.
            PROCESS_TYPE=process_role,
            WEB_INSTANCE_COUNT=int(os.getenv("WEB_INSTANCE_COUNT", "1")),
            ENABLE_ROLE_SIMULATOR=os.getenv("ENABLE_ROLE_SIMULATOR", "false").lower()
            in {"1", "true", "yes"},
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
    SESSION_COOKIE_SECURE = True

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
    else:
        try:
            if make_url(database_url).get_backend_name() != "postgresql":
                errors.append("DATABASE_URL must use PostgreSQL")
        except Exception:
            errors.append("DATABASE_URL is invalid")
    if config.get("SECRET_KEY") in {None, "", DEFAULT_SECRET_KEY, EXAMPLE_SECRET_KEY}:
        errors.append("SECRET_KEY must be changed from the default")
    if not config.get("WEB3_PROVIDER_URI"):
        errors.append("WEB3_PROVIDER_URI is required")
    if config.get("CHAIN_ID") != 11155111:
        errors.append("CHAIN_ID must be 11155111")
    if config.get("DEBUG"):
        errors.append("DEBUG must be false")
    if config.get("TESTING"):
        errors.append("TESTING must be false")
    if config.get("ENABLE_ROLE_SIMULATOR"):
        errors.append("role simulator must be disabled")
    process_role = config.get("PROCESS_ROLE", config.get("PROCESS_TYPE", "web"))
    if process_role not in {"web", "worker"}:
        errors.append("PROCESS_ROLE must be web or worker")
    if process_role == "web" and config.get("EVENT_SYNC_ENABLED"):
        errors.append("web process must not enable the event worker")
    if process_role == "worker" and not config.get("EVENT_SYNC_ENABLED"):
        errors.append("worker process must enable event sync")
    storage_backend = config.get("STORAGE_BACKEND", "local")
    if storage_backend == "local":
        errors.append("Production STORAGE_BACKEND must not be local")
    if process_role == "web" and storage_backend not in {"s3", "render_disk"}:
        errors.append("Production web STORAGE_BACKEND must be s3 or render_disk")
    if storage_backend == "s3":
        for key in ("S3_BUCKET", "S3_ACCESS_KEY_ID", "S3_SECRET_ACCESS_KEY"):
            if not config.get(key):
                errors.append(f"{key} is required")
    if process_role == "web" and storage_backend == "render_disk":
        errors.extend(_render_disk_config_errors(config))
        if config.get("WEB_INSTANCE_COUNT") != 1:
            errors.append("render_disk requires exactly one Web instance")
    invalid_contracts = []
    normalized_contracts = {}
    for name in CONTRACT_NAMES:
        address = config.get("CONTRACT_ADDRESSES", {}).get(name, "")
        try:
            normalized_contracts[name] = canonical_address(address, name)
        except ContractAddressError:
            invalid_contracts.append(name)
    if invalid_contracts:
        errors.append("contract addresses must be valid and non-zero: " + ", ".join(invalid_contracts))
    else:
        config["CONTRACT_ADDRESSES"] = normalized_contracts
        for name, address in normalized_contracts.items():
            config[_contract_env_name(name)] = address
    if errors:
        raise RuntimeError("Invalid production configuration: " + "; ".join(errors))


def _render_disk_config_errors(config) -> list[str]:
    """Validate path structure without touching a disk unavailable to pre-deploy."""
    errors = []
    mount_value = config.get("RENDER_DISK_MOUNT_PATH", "")
    upload_value = config.get("UPLOAD_FOLDER", "")
    mount = Path(mount_value) if mount_value else None
    upload = Path(upload_value) if upload_value else None
    if mount is None or not mount.is_absolute():
        errors.append("RENDER_DISK_MOUNT_PATH must be an absolute path")
    if upload is None or not upload.is_absolute():
        errors.append("UPLOAD_FOLDER must be an absolute path for render_disk")
    if mount is not None and upload is not None and mount.is_absolute() and upload.is_absolute():
        resolved_mount = mount.resolve(strict=False)
        resolved_upload = upload.resolve(strict=False)
        if not resolved_upload.is_relative_to(resolved_mount):
            errors.append("UPLOAD_FOLDER must be inside RENDER_DISK_MOUNT_PATH")
    return errors
