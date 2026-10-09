"""Enterprise onboarding and administrator review APIs."""

from __future__ import annotations

from flask import Blueprint, g, jsonify, request
from sqlalchemy.exc import IntegrityError

from backend.auth import require_auth, require_roles
from backend.errors import api_error
from backend.extensions import db
from backend.models import Enterprise, utcnow
from backend.services.blockchain import (
    RoleGrantMismatchError,
    RpcUnavailable,
    TxNotConfirmedError,
    TxNotFoundError,
    get_role_service,
)
from backend.services.validation import clean_text, normalize_wallet

enterprises_bp = Blueprint("enterprises", __name__, url_prefix="/api/enterprises")
VALID_ROLES = {"SUPPLIER", "CORE_ENTERPRISE", "FUNDER"}


@enterprises_bp.post("")
@require_auth
def create_enterprise():
    payload = request.get_json(silent=True) or {}
    wallet = normalize_wallet(payload.get("wallet_address"))
    if wallet != g.wallet_address:
        return api_error("ADDRESS_MISMATCH", "Applications may only use the authenticated wallet.", 403)
    role = payload.get("role_applied")
    role = "FUNDER" if role == "FINANCIER" else role
    if role not in VALID_ROLES:
        return api_error("INVALID_ROLE", "The requested enterprise role is invalid.", 422)
    name = clean_text(payload.get("enterprise_name"), maximum=200)
    contact = clean_text(payload.get("contact_person"), maximum=100)
    if not name or not contact:
        return api_error("INVALID_ENTERPRISE_DATA", "Enterprise name and contact are invalid.", 422)

    existing = Enterprise.query.filter_by(wallet_address=wallet).first()
    if existing and existing.status in {"PENDING", "APPROVED"}:
        return api_error(
            "ENTERPRISE_ALREADY_EXISTS", "An active application already exists.", 409
        )
    if existing:
        existing.enterprise_name = name
        existing.contact_person = contact
        existing.role_applied = role
        existing.status = "PENDING"
        existing.reject_reason = None
        existing.approval_tx_hash = None
        existing.reviewed_by = None
        existing.reviewed_at = None
        item = existing
    else:
        item = Enterprise(
            wallet_address=wallet,
            enterprise_name=name,
            contact_person=contact,
            role_applied=role,
        )
        db.session.add(item)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return api_error(
            "ENTERPRISE_ALREADY_EXISTS", "An active application already exists.", 409
        )
    return jsonify({"id": item.id, "status": item.status}), 201


@enterprises_bp.get("")
@require_roles("ADMIN")
def list_enterprises():
    query = Enterprise.query
    status = request.args.get("status")
    role = request.args.get("role_applied")
    if status:
        query = query.filter_by(status=status.upper())
    if role:
        role = "FUNDER" if role.upper() == "FINANCIER" else role.upper()
        query = query.filter_by(role_applied=role)
    return jsonify([item.to_dict() for item in query.order_by(Enterprise.created_at.desc())])


@enterprises_bp.patch("/<int:enterprise_id>")
@require_roles("ADMIN")
def review_enterprise(enterprise_id: int):
    item = db.session.get(Enterprise, enterprise_id)
    if not item:
        return api_error("NOT_FOUND", "Enterprise application was not found.", 404)
    payload = request.get_json(silent=True) or {}
    status = payload.get("status")
    if status == "REJECTED":
        reason = clean_text(payload.get("reject_reason"), maximum=1000)
        if not reason:
            return api_error("REJECT_REASON_REQUIRED", "A rejection reason is required.", 422)
        item.status = "REJECTED"
        item.reject_reason = reason
        item.approval_tx_hash = None
    elif status == "APPROVED":
        tx_hash = payload.get("tx_hash")
        if not isinstance(tx_hash, str) or len(tx_hash) != 66 or not tx_hash.startswith("0x"):
            return api_error("TX_NOT_FOUND", "A valid role grant transaction is required.", 422)
        try:
            get_role_service().verify_role_grant(tx_hash, item.wallet_address, item.role_applied)
        except TxNotFoundError:
            return api_error("TX_NOT_FOUND", "Role grant transaction was not found.", 422)
        except TxNotConfirmedError:
            return api_error("TX_NOT_CONFIRMED", "Role grant transaction is awaiting confirmations.", 409)
        except RoleGrantMismatchError:
            return api_error("ROLE_GRANT_MISMATCH", "RoleGranted event does not match the application.", 422)
        except RpcUnavailable:
            return api_error("RPC_UNAVAILABLE", "Transaction verification is unavailable.", 503)
        item.status = "APPROVED"
        item.reject_reason = None
        item.approval_tx_hash = tx_hash.lower()
    else:
        return api_error("INVALID_STATUS", "Status must be APPROVED or REJECTED.", 422)
    item.reviewed_by = g.wallet_address
    item.reviewed_at = utcnow()
    db.session.commit()
    return jsonify(item.to_dict())
