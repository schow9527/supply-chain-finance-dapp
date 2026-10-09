"""Liveness and dependency-readiness endpoints."""

from flask import Blueprint, current_app, jsonify
from sqlalchemy import text

from backend.config import CONTRACT_NAMES, ZERO_ADDRESS
from backend.errors import error_response
from backend.extensions import db
from backend.models import SyncState
from backend.config import ZERO_ADDRESS

health_bp = Blueprint("health", __name__, url_prefix="/api/health")


@health_bp.get("/live")
def live():
    return jsonify({"status": "live", "service": "supply-chain-finance-api"}), 200


@health_bp.get("/ready")
def ready():
    sync = _sync_check()
    checks = {
        "database": _database_check(),
        "environment": current_app.config.get("ENV_NAME", "unknown"),
        "chain_id": {"status": "ok" if current_app.config.get("CHAIN_ID") == 11155111 else "invalid",
                     "value": current_app.config.get("CHAIN_ID")},
        "contracts": _contract_check(),
        "rpc": _rpc_check(),
        "event_sync": sync,
        "latest_chain_block": sync.get("latest_chain_block"),
        "last_synced_block": sync.get("last_synced_block"),
        "sync_lag_blocks": sync.get("sync_lag_blocks"),
        "last_sync_at": sync.get("last_sync_at"),
    }
    unavailable = (checks["database"]["status"] != "ok"
                   or checks["chain_id"]["status"] != "ok"
                   or checks["contracts"]["status"] != "ok"
                   or checks["rpc"]["status"] == "unavailable")
    if unavailable:
        return error_response(
            503,
            "Service dependencies are unavailable.",
            {"status": "unavailable", "checks": checks},
        )
    return jsonify({"status": "ready", "checks": checks}), 200


def _sync_check():
    cursor = SyncState.query.filter_by(
        chain_id=current_app.config.get("CHAIN_ID"), contract_address=ZERO_ADDRESS
    ).first()
    if cursor is None:
        return {"status": "degraded", "latest_chain_block": None,
                "last_synced_block": None, "sync_lag_blocks": None,
                "last_sync_at": None}
    latest = cursor.latest_chain_block
    lag = max(0, latest - cursor.last_synced_block) if latest is not None else None
    return {"status": cursor.status or "healthy", "latest_chain_block": latest,
            "last_synced_block": cursor.last_synced_block, "sync_lag_blocks": lag,
            "last_sync_at": cursor.updated_at.isoformat() if cursor.updated_at else None,
            "error": cursor.last_error}


def _database_check():
    try:
        db.session.execute(text("SELECT 1"))
        return {"status": "ok"}
    except Exception:
        db.session.rollback()
        return {"status": "unavailable"}


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
    try:
        from web3 import Web3
        provider = Web3.HTTPProvider(provider_uri, request_kwargs={"timeout": current_app.config.get("RPC_HEALTHCHECK_TIMEOUT", 2)})
        connected = Web3(provider).is_connected()
    except Exception:
        connected = False
    return {"status": "ok" if connected else "unavailable", "configured": True}
