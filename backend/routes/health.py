"""Liveness and dependency-readiness endpoints."""

from __future__ import annotations

import hashlib
import time

from flask import Blueprint, current_app, jsonify
from sqlalchemy import text

from backend.config import BASE_DIR, CONTRACT_NAMES, ZERO_ADDRESS
from backend.errors import error_response
from backend.extensions import db
from backend.models import SyncState
from backend.storage import get_storage

health_bp = Blueprint("health", __name__, url_prefix="/api/health")


@health_bp.get("/live")
def live():
    return jsonify({"status": "live", "service": "supply-chain-finance-api"}), 200


@health_bp.get("/ready")
def ready():
    rpc = _rpc_check()
    sync = _sync_check(rpc)
    checks = {
        "database": _database_check(),
        "migrations": _migration_check(),
        "configuration": _configuration_check(),
        "environment": current_app.config.get("ENV_NAME", "unknown"),
        "chain_id": {"status": "ok" if current_app.config.get("CHAIN_ID") == 11155111 else "invalid",
                     "value": current_app.config.get("CHAIN_ID")},
        "contracts": _contract_check(),
        "rpc": rpc,
        "storage": _storage_check(),
        "event_sync": sync,
        "latest_chain_block": sync.get("latest_chain_block"),
        "last_synced_block": sync.get("last_synced_block"),
        "sync_lag_blocks": sync.get("sync_lag_blocks"),
        "last_sync_at": sync.get("last_sync_at"),
    }
    unavailable = (checks["database"]["status"] != "ok"
                   or checks["migrations"]["status"] != "ok"
                   or checks["configuration"]["status"] != "ok"
                   or checks["storage"]["status"] != "ok")
    if unavailable:
        return error_response(
            503,
            "Service dependencies are unavailable.",
            {"status": "unavailable", "checks": checks},
        )
    degraded = any(
        checks[name]["status"] not in {"ok", "healthy"}
        for name in ("rpc", "storage", "event_sync")
    )
    return jsonify({"status": "degraded" if degraded else "ready", "checks": checks}), 200


def _sync_check(rpc):
    latest = rpc.get("latest_chain_block") if rpc.get("status") == "ok" else None
    cursor = SyncState.query.filter_by(
        chain_id=current_app.config.get("CHAIN_ID"), contract_address=ZERO_ADDRESS
    ).first()
    if cursor is None:
        return {"status": "degraded", "latest_chain_block": latest,
                "last_synced_block": None, "sync_lag_blocks": None,
                "last_sync_at": None}
    lag = max(0, latest - cursor.last_synced_block) if latest is not None else None
    max_lag = max(0, int(current_app.config.get("SYNC_MAX_LAG_BLOCKS", 12)))
    status = cursor.status or "healthy"
    error = cursor.last_error
    if rpc.get("status") != "ok":
        status = "degraded"
        error = error or rpc.get("error", "RPC_UNAVAILABLE")
    elif lag is not None and lag > max_lag:
        status = "degraded"
        error = error or "SYNC_LAG_EXCEEDED"
    return {"status": status, "latest_chain_block": latest,
            "last_synced_block": cursor.last_synced_block, "sync_lag_blocks": lag,
            "last_sync_at": cursor.updated_at.isoformat() if cursor.updated_at else None,
            "error": error, "max_lag_blocks": max_lag}


def _database_check():
    try:
        db.session.execute(text("SELECT 1"))
        return {"status": "ok"}
    except Exception:
        db.session.rollback()
        return {"status": "unavailable"}


def _migration_check():
    if current_app.config.get("ENV_NAME") != "production":
        return {"status": "ok", "check": "production-only"}
    try:
        from alembic.config import Config as AlembicConfig
        from alembic.migration import MigrationContext
        from alembic.script import ScriptDirectory
        alembic = AlembicConfig(str(BASE_DIR / "backend" / "migrations" / "alembic.ini"))
        alembic.set_main_option("script_location", str(BASE_DIR / "backend" / "migrations"))
        head = ScriptDirectory.from_config(alembic).get_current_head()
        with db.engine.connect() as connection:
            current = MigrationContext.configure(connection).get_current_revision()
        return {"status": "ok" if current == head else "incomplete"}
    except Exception:
        return {"status": "unavailable"}


def _configuration_check():
    return {"status": "ok"}


def _storage_check():
    try:
        storage = get_storage()
        result = {"backend": current_app.config.get("STORAGE_BACKEND")}
        if hasattr(storage, "health_details"):
            result.update(storage.health_details())
        else:
            result["status"] = "ok" if storage.health_check() else "unavailable"
        return result
    except Exception:
        return {"status": "unavailable", "backend": current_app.config.get("STORAGE_BACKEND")}


def _contract_check():
    addresses = current_app.config.get("CONTRACT_ADDRESSES", {})
    missing = [name for name in CONTRACT_NAMES
               if not addresses.get(name) or addresses[name].lower() == ZERO_ADDRESS]
    return {"status": "ok" if not missing else "incomplete", "missing": missing}


def _rpc_check():
    provider_uri = current_app.config.get("WEB3_PROVIDER_URI", "")
    if not provider_uri:
        return {"status": "unavailable", "configured": False}
    if not current_app.config.get("RPC_HEALTHCHECK_ENABLED"):
        return {"status": "degraded", "configured": True, "check": "disabled"}
    cache = current_app.extensions.setdefault("rpc_health_cache", {})
    provider_fingerprint = hashlib.sha256(provider_uri.encode("utf-8")).hexdigest()
    now = time.monotonic()
    ttl = max(0, int(current_app.config.get("RPC_HEALTHCHECK_CACHE_TTL", 30)))
    if (cache.get("provider") == provider_fingerprint
            and now - cache.get("checked_at", 0) < ttl):
        return dict(cache["result"])
    try:
        from web3 import Web3
        provider = Web3.HTTPProvider(
            provider_uri,
            request_kwargs={"timeout": current_app.config.get("RPC_HEALTHCHECK_TIMEOUT", 2)},
        )
        web3 = Web3(provider)
        actual_chain_id = int(web3.eth.chain_id)
        latest = int(web3.eth.block_number)
        expected_chain_id = int(current_app.config.get("CHAIN_ID", 11155111))
        if actual_chain_id != expected_chain_id:
            result = {
                "status": "invalid",
                "configured": True,
                "error": "RPC_CHAIN_MISMATCH",
                "expected_chain_id": expected_chain_id,
                "actual_chain_id": actual_chain_id,
                "latest_chain_block": None,
            }
        else:
            result = {
                "status": "ok",
                "configured": True,
                "chain_id": actual_chain_id,
                "latest_chain_block": latest,
            }
    except Exception as exc:
        response = getattr(exc, "response", None)
        http_status = getattr(response, "status_code", None)
        error_type = type(exc).__name__
        current_app.logger.warning(
            "rpc_healthcheck_failed error_type=%s http_status=%s",
            error_type, http_status,
        )
        result = {
            "status": "unavailable",
            "configured": True,
            "error": "RPC_UNAVAILABLE",
            "error_type": error_type,
            "http_status": http_status,
            "latest_chain_block": None,
        }
    cache.update(provider=provider_fingerprint, checked_at=now, result=result)
    return dict(result)
